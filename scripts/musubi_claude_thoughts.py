"""Live thoughts: messages from other agents, delivered into this session.

Musubi's thought plane carries agent-to-agent messages and serves them live on
``GET /v1/thoughts/stream`` (server-sent events, a ping every 30 s, replay from
``Last-Event-ID``). This module is the client behind the plugin's monitor:
Claude Code runs it for the whole interactive session, and every line it prints
reaches Claude as a notification, without anyone asking.

Output contract (one line per thought, nothing else except rare status lines)::

    musubi thought from <presence> [<thought_id>] (untrusted data): <text>

The text is the thought's own content, flattened to one line and capped. It is
labelled untrusted because it is: another agent wrote it, and a thought that
says "run this" is a message about something, never an instruction to follow.

Monitor processes receive no plugin settings, so the connection comes from a
small JSON file (``--config``) that the plugin's SessionStart hook writes
(``write_config``): url, token, namespace and presence, nothing else, in a
0700 directory, created 0600 with no window, only in ``verified`` mode. The
monitor reads it ONCE at start (waiting briefly for SessionStart to write it)
and keeps the values in memory, so another session's SessionEnd removing the
file can't deafen a running stream. It never follows redirects, so the bearer
token can't be forwarded elsewhere. Its own status lines carry only locally
generated text (never a URL, response body or exception text). It prints at
most one "unavailable" line per outage, and keeps ``Last-Event-ID`` across
reconnects so nothing is repeated or skipped.

Musubi stores each thought in its sender's namespace (``<presence>/thought``)
and the stream matches a namespace exactly, so the monitor opens one stream per
watched sender (the ``thought_sources`` setting); the server filters each to
thoughts addressed to this presence or to ``all``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

READ_TIMEOUT = 75.0  # the server pings every 30 s
TEXT_CHARS = 300
BACKOFF = (1, 2, 5, 10, 30, 60)
CONFIG_WAIT_SECONDS = 15.0
_OPTION = "CLAUDE_PLUGIN_OPTION_"
_PRINT_LOCK = threading.Lock()
_PRESENCE = re.compile(r"^[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*$")


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


_OPENER = urllib.request.build_opener(_RefuseRedirects)


def load_config(path: Path) -> dict[str, Any] | None:
    """The connection file, or None if it is missing or incomplete."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    if not all(isinstance(raw.get(k), str) and raw[k].strip() for k in ("url", "token")):
        return None
    namespaces = raw.get("namespaces")
    if not isinstance(namespaces, list) or not namespaces or not all(isinstance(n, str) and n for n in namespaces):
        return None
    config: dict[str, Any] = {"url": raw["url"].strip(), "token": raw["token"].strip(), "namespaces": namespaces}
    if isinstance(raw.get("presence"), str):
        config["presence"] = raw["presence"]
    return config


def stream_url(config: dict[str, Any], namespace: str) -> str:
    base = str(config["url"]).rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    return f"{base}/thoughts/stream?" + urllib.parse.urlencode({"namespace": namespace})


def parse_events(lines: Iterable[str]) -> Iterator[dict[str, str]]:
    """Minimal SSE parser: yields {'event','id','data'} per dispatched event."""
    event: dict[str, str] = {}
    data: list[str] = []
    for raw in lines:
        line = raw.rstrip("\r\n")
        if not line:
            if data:
                event["data"] = "\n".join(data)
                yield event
            event, data = {}, []
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if field == "data":
            data.append(value)
        elif field in ("event", "id"):
            event[field] = value


def format_thought(event: dict[str, str], own_presence: str | None) -> str | None:
    """One notification line for a thought event, or None to stay quiet."""
    if event.get("event", "message") != "thought":
        return None
    try:
        thought: Any = json.loads(event.get("data", ""))
    except json.JSONDecodeError:
        return None
    if not isinstance(thought, dict):
        return None
    sender = str(thought.get("from_presence") or "unknown")
    if own_presence and sender == own_presence:
        return None  # our own outgoing thought echoed back
    text = " ".join(str(thought.get("content") or "").split())
    if not text:
        return None
    if len(text) > TEXT_CHARS:
        text = text[: TEXT_CHARS - 1] + "…"
    thought_id = str(thought.get("object_id") or event.get("id") or "?")
    return f"musubi thought from {sender} [{thought_id}] (untrusted data): {text}"


def _lines(response: Any) -> Iterator[str]:
    for raw in response:
        yield raw.decode("utf-8", errors="replace")


def wait_for_config(path: Path, *, wait: float = CONFIG_WAIT_SECONDS, sleep: Any = time.sleep) -> dict[str, Any] | None:
    """Read the connection file once, giving SessionStart a moment to write it."""
    deadline = time.monotonic() + wait
    started = time.time() - 30  # a file older than this session is a crash leftover
    while True:
        try:
            fresh = path.stat().st_mtime >= started
        except OSError:
            fresh = False
        config = load_config(path) if fresh else None
        if config is not None or time.monotonic() >= deadline:
            return config
        sleep(0.5)


def run(config: dict[str, Any], *, max_cycles: int | None = None, sleep: Any = time.sleep) -> int:
    """One stream per watched namespace, in threads; returns when all stop."""
    threads = [
        threading.Thread(target=run_one, args=(config, ns), kwargs={"max_cycles": max_cycles, "sleep": sleep}, daemon=True)
        for ns in config["namespaces"]
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return 0


def _emit(line: str) -> None:
    with _PRINT_LOCK:
        print(line, flush=True)


def run_one(config: dict[str, Any], namespace: str, *, max_cycles: int | None = None, sleep: Any = time.sleep) -> int:
    """Stream one namespace forever (Claude Code stops the monitor). ``max_cycles`` bounds tests."""
    last_id: str | None = None
    failures = 0
    announced_down = False
    cycles = 0
    url = stream_url(config, namespace)
    while max_cycles is None or cycles < max_cycles:
        cycles += 1
        headers = {"Accept": "text/event-stream", "Authorization": f"Bearer {config['token']}"}
        if last_id:
            headers["Last-Event-ID"] = last_id
        try:
            request = urllib.request.Request(url, headers=headers)
            with _OPENER.open(request, timeout=READ_TIMEOUT) as response:
                if announced_down:
                    _emit(f"musubi thoughts: {namespace} reconnected")
                failures, announced_down = 0, False
                for event in parse_events(_lines(response)):
                    if event.get("id"):
                        last_id = event["id"]
                    line = format_thought(event, config.get("presence"))
                    if line:
                        _emit(line)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                _emit(f"musubi thoughts: {namespace} refused (HTTP {int(exc.code)}); check the Musubi token and its read scope")
                return 0
            failures += 1
        except (OSError, ValueError):
            failures += 1
        if failures and not announced_down and failures >= 3:
            _emit(f"musubi thoughts: {namespace} unavailable; retrying quietly")
            announced_down = True
        sleep(BACKOFF[min(failures, len(BACKOFF) - 1)] if failures else 1)
    return 0


def write_config(env: dict[str, str] | None = None) -> str:
    """SessionStart: write (or remove) the monitor's connection file. Returns a status word."""
    env = dict(os.environ) if env is None else env
    data = env.get("CLAUDE_PLUGIN_DATA", "").strip()
    if not data:
        return "no_data_dir"
    folder = Path(data).expanduser() / "monitor"
    target = folder / "stream.json"
    url = env.get(_OPTION + "MUSUBI_URL", "").strip()
    token = env.get(_OPTION + "MUSUBI_TOKEN", "").strip()
    actor = env.get(_OPTION + "ACTOR", "").strip()
    seat = env.get(_OPTION + "SEAT", "").strip()
    mode = env.get(_OPTION + "DELIVERY_MODE", "").strip()
    if not (url and token and actor and seat) or mode != "verified":
        target.unlink(missing_ok=True)
        return "disabled"
    presence = f"{actor}/{seat}"
    # Musubi stores a thought in its SENDER's namespace (<presence>/thought) and the
    # stream matches that namespace exactly, so we watch each source's namespace.
    sources = [p.strip() for p in env.get(_OPTION + "THOUGHT_SOURCES", "").split(",") if p.strip()]
    sources = [p for p in dict.fromkeys(sources) if _PRESENCE.fullmatch(p) and p != presence][:20]
    if not sources:
        target.unlink(missing_ok=True)
        return "no_sources"
    payload = json.dumps({"url": url, "token": token, "namespaces": [f"{p}/thought" for p in sources], "presence": presence})
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(folder, 0o700)
    tmp = folder / f".stream.{os.getpid()}.tmp"
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    return "written"


def remove_config(env: dict[str, str] | None = None) -> None:
    """SessionEnd: remove the connection file (a running monitor already holds its copy)."""
    env = dict(os.environ) if env is None else env
    data = env.get("CLAUDE_PLUGIN_DATA", "").strip()
    if data:
        (Path(data).expanduser() / "monitor" / "stream.json").unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stream Musubi thoughts as monitor lines.")
    parser.add_argument("--config", help="connection file written by the SessionStart hook")
    parser.add_argument("--write-config", action="store_true", help="SessionStart: write or remove the file")
    parser.add_argument("--remove-config", action="store_true", help="SessionEnd: remove the file")
    args = parser.parse_args(argv)
    try:
        if args.write_config:
            write_config()
            return 0
        if args.remove_config:
            remove_config()
            return 0
        if not args.config:
            return 0
        config = wait_for_config(Path(args.config))
        if config is None:
            return 0  # shadow mode or no token: nothing to stream, stay silent
        return run(config)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:  # noqa: BLE001 - class name only, never exception text
        print(f"musubi thoughts: stopped ({type(exc).__name__})", file=sys.stderr, flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
