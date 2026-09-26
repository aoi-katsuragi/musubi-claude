# musubi-claude

First-class Claude Code adapter for [Musubi](https://github.com/sourceblender/musubi) memory.
SessionStart continuity, Stop capture, a read-only recall MCP facade plus durable remember,
and the recall/continuity skills. Built on the shared [`musubi-harness`](https://github.com/sourceblender/musubi-harness)
runtime so the Claude and Codex seats share one contract and never diverge.

| | |
| --- | --- |
| License | Apache-2.0 |
| Plugin name | `musubi-claude` |
| Marketplace | `sourceblender` |
| Runtime dep | [`musubi-harness>=1.0.0,<2.0.0`](https://pypi.org/project/musubi-harness/) |
| Companion repos | [`musubi-codex`](https://github.com/sourceblender/musubi-codex), [`musubi-livekit`](https://github.com/sourceblender/musubi-livekit), [`musubi-hermes`](https://github.com/sourceblender/musubi-hermes), [`musubi-openclaw`](https://github.com/sourceblender/musubi-openclaw) |

**Shadow-only by default.** Nothing is written to Musubi until `delivery_mode`
is explicitly set to `verified`.

## Install

> ⚠️ **Local-only install.** This plugin is published for general use, but the
> maintainer does not auto-install it on anyone's machine. Add the marketplace,
> review the manifest, and install in a controlled, tested way that fits your
> environment.

```bash
claude plugin marketplace add sourceblender/musubi-claude
claude plugin install musubi-claude@sourceblender
```

The plugin depends on the `musubi-harness` PyPI package; `pip install
musubi-harness` happens automatically when Claude Code loads the plugin.

## What it does

- **Stop hook → automatic capture.** On each completed turn, `musubi-claude-stop`
  derives the last completed **primary** turn from the transcript and shadow-
  enqueues one `TurnEnvelope` through the shared harness core. In `verified`
  delivery_mode it additionally stages the event and runs **one** bounded
  shared-drainer pass — it never POSTs Musubi directly, and it injects the
  configured identity (`tool_environment`) so the drainer resolves the seat
  regardless of the hook's working directory.
- **SessionStart hook → bounded continuity.** `musubi-claude-session-start`
  emits a small, owned-scope recent-chronology block, explicitly labelled as
  chronology (not semantic relevance) and as historical, untrusted data. It
  fails open: any outage yields a labelled "unavailable" note, never a false
  empty-memory set.
- **Recall MCP (`musubi-claude-mcp`).** Five truthful tools: `musubi_recent`,
  `musubi_search`, `musubi_get`, and `musubi_status` are read-only; durable
  `musubi_remember` queues one load-bearing memory through the shared outbox.
  Recall is untrusted historical data, never instructions; `queued` is never
  reported as `verified` (verified requires an exact-readback receipt);
  `musubi_think` is intentionally absent.
- **Skills.** `musubi-recall` and `musubi-continuity` — the standing reflexes
  for deliberate recall and for inspecting capture/delivery health.

## The Claude-specific difference

Claude Code's Stop hook supplies `session_id` + `transcript_path` + `prompt_id`
+ `last_assistant_message` (the latter two were shape-probed in 2026-07 →
2026-08), so the adapter binds the event's own identity and answer rather
than reconstructing them from the transcript. The event id is deterministic
and stable — `claude-code:<session_id>:<prompt_id>` — so a Stop retry or
resume re-enqueues the same id and the harness dedupes it.

## Identity is deployment configuration — never derived from the host

`actor` / `presence` / `zone` come from `MUSUBI_ACTOR` / `MUSUBI_PRESENCE` /
`MUSUBI_ZONE`, or from `$PLUGIN_DATA/config.json` (identity all-or-nothing).
Partial or absent identity is **refused**, never guessed. `presence` is the
Musubi `actor/seat` form (e.g. `aoi/command-chair`); the shared runtime
enforces `actor == presence-prefix` and owned-namespace scope, so no adapter
can read or write under another actor's seat.

### Configuring identity

Either:

```bash
export MUSUBI_ACTOR=aoi
export MUSUBI_PRESENCE=aoi/command-chair
export MUSUBI_ZONE=home
export MUSUBI_DELIVERY_MODE=shadow  # or 'verified' to enable remote writes
```

…or write `~/.claude/plugins/data/musubi-claude/config.json`:

```json
{
  "actor": "aoi",
  "presence": "aoi/command-chair",
  "zone": "home",
  "delivery_mode": "shadow"
}
```

Identity keys must be all-or-nothing. `MUSUBI_HARNESS_BIN` and
`MUSUBI_MEMORY_DATA_BIN` may be set in either env or `config.json` to
override the PATH lookup for `musubi-harness` and `memory-data`.

## Failure is visible, never silent

Any parse/config/enqueue/delivery failure appends to
`$PLUGIN_DATA/degraded.jsonl` and the hook still exits 0 — capture degrades
visibly and never breaks the session. The diagnostic sink intentionally
holds only structured failure codes (`reason`, `seat`, `session_id`) and
never the conversation content that produced the failure.

## Migration from the in-fleet-tools copy

`0.3.x` lived at `~/Vaults/fleet-tools/plugins/musubi-claude/` as a
workspace-internal copy. `0.4.0` is the first standalone release with
the harness extracted to its own PyPI package:

- `parents[3]/lib` filesystem walk is gone — `musubi-harness` is a real
  pip dependency now.
- `pip install -e ../musubi-harness` is no longer required for local
  development; the plugin dev install uses `pip install -e .` which
  pulls `musubi-harness>=1.0.0` from PyPI.
- The in-fleet-tools copy continues to work as the dev head during the
  transition window. Any new fix lands here first, then backports.

## Development

```bash
git clone https://github.com/sourceblender/musubi-claude
cd musubi-claude
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install ruff mypy pytest pytest-cov
ruff check scripts tests
ruff format --check scripts tests
mypy scripts
pytest
```

CI is `ruff` + `mypy --strict` + `pytest` on Python 3.12.

## License

Apache-2.0.
