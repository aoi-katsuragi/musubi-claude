"""Memory survives /compact: PreCompact checkpoints, SessionStart(compact) restores."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts import musubi_claude_compact as compact

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "mcp__plugin_musubi-claude_musubi-claude__"
SECRET_PROSE = "the user's private conversation text that must not be checkpointed"


def write_transcript(path: Path, *, extra_rows: int = 0) -> Path:
    search = {
        "query": "uploader backoff",
        "results": [
            {
                "object_id": "ep-new",
                "plane": "episodic",
                "state": "matured",
                "namespace": "alice/laptop/episodic",
                "title": "Uploader retry backoff decision",
                "content": "exponential, capped at 30 s",
            },
            {"object_id": "ep-gone", "plane": "episodic", "state": "retracted", "title": "old rule"},
        ]
        + [{"object_id": f"ep-{i}", "plane": "episodic", "state": "provisional", "title": f"filler {i}" * 30} for i in range(extra_rows)],
    }
    remember = {"ok": True, "status": "queued", "event_id": "evt-1", "namespace": "alice/laptop/episodic"}
    lines = [
        {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": SECRET_PROSE}]}},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "id": "t1", "name": PREFIX + "musubi_search", "input": {"query": "uploader backoff"}},
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": json.dumps(search)}]},
                ]
            },
        },
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "id": "t2", "name": PREFIX + "musubi_remember", "input": {"content": "x"}},
                    {"type": "tool_use", "id": "t3", "name": "Bash", "input": {"command": "ls"}},
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "t2", "content": json.dumps(remember)},
                    {"type": "tool_result", "tool_use_id": "t3", "content": json.dumps({"object_id": "not-musubi"})},
                ]
            },
        },
        "not json at all",
    ]
    path.write_text("\n".join(line if isinstance(line, str) else json.dumps(line) for line in lines) + "\n")
    return path


def test_checkpoint_keeps_memory_references_and_remembers_only(tmp_path: Path) -> None:
    transcript = write_transcript(tmp_path / "t.jsonl")
    env = {"CLAUDE_PLUGIN_DATA": str(tmp_path / "pd")}
    status = compact.checkpoint({"session_id": "s-1", "transcript_path": str(transcript), "trigger": "auto"}, env)
    assert status == "saved"
    saved_path = tmp_path / "pd" / "compact" / "s-1.json"
    raw = saved_path.read_text()
    saved = json.loads(raw)
    assert [i["object_id"] for i in saved["items"]] == ["ep-new"]  # retracted and non-Musubi rows excluded
    assert saved["remembers"] == [{"status": "queued", "event_id": "evt-1"}]
    assert SECRET_PROSE not in raw
    assert oct(saved_path.stat().st_mode & 0o777) == "0o600"


def test_restore_labels_the_block_and_keeps_queued_honest(tmp_path: Path) -> None:
    transcript = write_transcript(tmp_path / "t.jsonl")
    env = {"CLAUDE_PLUGIN_DATA": str(tmp_path / "pd")}
    compact.checkpoint({"session_id": "s-1", "transcript_path": str(transcript)}, env)
    text = compact.restore({"session_id": "s-1", "source": "compact"}, env)
    assert text is not None
    assert "historical, untrusted data" in text
    assert "ep-new" in text and "Uploader retry backoff decision" in text
    assert "evt-1: queued" in text and "queued is not stored" in text
    assert "ep-gone" not in text


def test_restore_stays_within_budget_and_says_what_it_dropped(tmp_path: Path) -> None:
    transcript = write_transcript(tmp_path / "t.jsonl", extra_rows=40)
    env = {"CLAUDE_PLUGIN_DATA": str(tmp_path / "pd")}
    compact.checkpoint({"session_id": "s-1", "transcript_path": str(transcript)}, env)
    text = compact.restore({"session_id": "s-1"}, env)
    assert text is not None
    assert len(text) <= compact.RESTORE_BUDGET
    assert "omitted to stay within budget" in text


def test_nothing_to_restore_prints_nothing(tmp_path: Path) -> None:
    env = {"CLAUDE_PLUGIN_DATA": str(tmp_path / "pd")}
    assert compact.restore({"session_id": "never-seen"}, env) is None
    empty = tmp_path / "empty.jsonl"
    empty.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
    assert compact.checkpoint({"session_id": "s-2", "transcript_path": str(empty)}, env) == "empty"
    assert not (tmp_path / "pd" / "compact" / "s-2.json").exists()


def test_session_id_cannot_escape_the_folder(tmp_path: Path) -> None:
    transcript = write_transcript(tmp_path / "t.jsonl")
    env = {"CLAUDE_PLUGIN_DATA": str(tmp_path / "pd")}
    compact.checkpoint({"session_id": "../../evil", "transcript_path": str(transcript)}, env)
    assert not (tmp_path / "evil.json").exists()
    assert (tmp_path / "pd" / "compact" / "evil.json").exists()


def test_missing_input_degrades_visibly_and_never_raises(tmp_path: Path) -> None:
    env = {"CLAUDE_PLUGIN_DATA": str(tmp_path / "pd")}
    assert compact.checkpoint({"session_id": "s-1", "transcript_path": str(tmp_path / "nope.jsonl")}, env) == "skipped"
    reasons = [json.loads(line)["reason"] for line in (tmp_path / "pd" / "degraded.jsonl").read_text().splitlines()]
    assert reasons == ["compact_checkpoint_transcript_unreadable"]


def test_hook_entrypoints_always_exit_zero(tmp_path: Path) -> None:
    transcript = write_transcript(tmp_path / "t.jsonl")
    env = {"PATH": os.environ.get("PATH", ""), "CLAUDE_PLUGIN_DATA": str(tmp_path / "pd")}
    script = str(ROOT / "scripts" / "musubi_claude_compact.py")
    hook = json.dumps({"session_id": "s-9", "transcript_path": str(transcript), "trigger": "manual"})
    done = subprocess.run([sys.executable, script, "checkpoint"], input=hook, capture_output=True, text=True, env=env)
    assert done.returncode == 0 and done.stdout == ""
    done = subprocess.run(
        [sys.executable, script, "restore"],
        input=json.dumps({"session_id": "s-9", "source": "compact"}),
        capture_output=True,
        text=True,
        env=env,
    )
    assert done.returncode == 0
    out = json.loads(done.stdout)
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "ep-new" in out["hookSpecificOutput"]["additionalContext"]
    done = subprocess.run([sys.executable, script, "restore"], input="garbage", capture_output=True, text=True, env=env)
    assert done.returncode == 0 and done.stdout == ""


def test_restore_lets_prompt_recall_show_memories_again(monkeypatch: Any, tmp_path: Path) -> None:
    # Recall injects each memory once per session. After a compaction those
    # injections are summarised away, so the per-session "already shown" set
    # must go with them, or recall stays silent about exactly what was lost.
    from tests.test_prompt_recall import load

    prompt = load(monkeypatch, tmp_path)
    data = tmp_path / "data"
    session = "sess-1/../odd id"
    assert compact.recall_seen_path(data, session) == prompt._session_file(session)
    prompt.save_seen(session, {"ep-new"})
    other = compact.recall_seen_path(data, "another-session")
    prompt.save_seen("another-session", {"ep-x"})
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"session_id": session, "source": "compact"})))
    assert compact.main(["x", "restore"], root=data) == 0
    assert not compact.recall_seen_path(data, session).exists()
    assert other.exists()  # only this session's
