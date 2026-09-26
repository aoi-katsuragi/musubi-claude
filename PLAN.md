# Plan: Standalone `musubi-claude` Claude Code plugin

> Status: plan only — no source written yet. This document is the design that
> we'll execute in subsequent steps once approved.

## Goals

1. Move the loose, in-fleet-tools copy of the Claude Code Musubi adapter out
   of `~/Vaults/fleet-tools/plugins/musubi-claude/` into a standalone
   public-open-source plugin repo at `~/Projects/musubi-claude`.
2. Extract the shared host-neutral runtime (`musubi_harness/`) into its own
   repo + PyPI package (`musubi-harness`), so the Codex sibling
   (`musubi-codex`) and the Claude sibling (`musubi-claude`) share one
   contract from a versioned source of truth — not from a symlink or a copy
   in fleet-tools.
3. Make the plugin installable as a normal Claude Code plugin:
   `claude plugin marketplace add sourceblender/musubi-claude` then
   `claude plugin install musubi-claude@sourceblender`.
4. Keep the existing in-tree fleet-tools copy working during the migration
   window, with a documented migration path.

## Non-goals (this iteration)

- No code change to the adapter logic itself. The whole point is packaging:
  the Stop hook, SessionStart hook, recall MCP facade, recall/continuity
  skills, and the bounded shadow/verified delivery contract all move
  verbatim. Any drift fix goes through the same fleet-tools→standalone PR
  flow that already exists.
- No new public surface. Tool names (`musubi_recent`, `musubi_search`,
  `musubi_get`, `musubi_status`, `musubi_remember`) and skill names
  (`musubi-recall`, `musubi-continuity`) are unchanged.
- No Claude.ai / Cowork submission in this iteration. Public GitHub
  distribution via own marketplace; Anthropic directory submission is a
  follow-up.

## What the user already has, in one paragraph

`~/Vaults/fleet-tools/plugins/musubi-claude/` is a working Claude Code plugin
(directory-shaped, with `.claude-plugin/plugin.json`, `hooks/hooks.json`,
`.mcp.json`, two skills, three scripts, and a runtime binding) that imports
`musubi_harness` from fleet-tools' `lib/` at runtime via
`musubi_claude_runtime.py`. The user wants to ship this as a real
open-source plugin: a real public GitHub repo, a real PyPI dependency for
the shared harness, a real `marketplace.json`, and proper release hygiene.

## The repo shape we will land

Two new repos, both under the `sourceblender` GitHub org:

### `sourceblender/musubi-harness` (PyPI: `musubi-harness`)

- Pure Python package, no plugin-specific bindings.
- Source: the existing `~/Vaults/fleet-tools/lib/musubi_harness/` plus the
  `plugin_runtime.py` / `plugin_mcp.py` / `plugin_continuity.py` modules
  the Claude and Codex adapters currently depend on.
- Layout: `src/musubi_harness/` (src-layout), `pyproject.toml` with PEP 621
  metadata, `ruff` + `mypy --strict` + `pytest`, type hints preserved.
- CLI shims live here too: `musubi-harness`, `musubi-harness-conformance`
  (currently shells in `bin/` of fleet-tools) become console-script entries
  of the same package.
- Versioned semver. `1.0.0` is the cut that contains
  `PluginRuntime`, `PluginMcpFacade`, `PluginContinuity`, and the
  SQLite-backed outbox + drainer contract.
- README explicitly states the cross-plugin contract: "this is the
  single source of truth that the Claude Code, Codex, and any future
  host adapters bind to; never import from a host adapter."

### `sourceblender/musubi-claude` (Claude Code plugin)

```
musubi-claude/
├── .claude-plugin/
│   └── plugin.json              # name: musubi-claude, deps: musubi-harness
├── .mcp.json                    # musubi-claude MCP server → scripts/musubi-claude-mcp
├── hooks/
│   └── hooks.json               # SessionStart + Stop → scripts/musubi-claude-{session-start,stop}
├── skills/
│   ├── musubi-recall/SKILL.md   # recall contract
│   └── musubi-continuity/SKILL.md  # delivery health contract
├── scripts/
│   ├── musubi_claude_runtime.py # the ONLY host-specific binding
│   ├── musubi-claude-mcp
│   ├── musubi-claude-session-start
│   └── musubi-claude-stop
├── tests/
│   ├── test_adapter.py          # hook payload → envelope projection
│   ├── test_continuity.py       # bounded chronology, fail-open
│   ├── test_mcp_facade.py       # five-tool schema, validation, remember truth
│   └── test_runtime.py          # identity refusal, namespace policy
├── pyproject.toml               # names the plugin, deps: musubi-harness
├── README.md                    # install + configuration + identity policy
├── CHANGELOG.md                 # release-please-managed
├── LICENSE                      # Apache-2.0
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── SECURITY.md
└── .github/
    ├── workflows/
    │   ├── ci.yml               # ruff + mypy + pytest on PR + main
    │   └── release-please.yml   # automated PyPI release for musubi-harness
    ├── ISSUE_TEMPLATE/
    └── PULL_REQUEST_TEMPLATE.md
```

Plugin-name scoping rules (from `docs.claude.com/en/docs/claude-code/plugins/manifest-reference`):
`name` is `musubi-claude`, kebab-case, no spaces, becomes the namespace
prefix on every skill and subagent. Skills invoke as
`/musubi-claude:musubi-recall` and `/musubi-claude:musubi-continuity`.

### Marketplace file inside the same repo

Per the docs ("Publish through your own marketplace" →
[link](https://docs.claude.com/en/docs/claude-code/plugins/publish#publish-through-your-own-marketplace)),
the cleanest install path is to put `.claude-plugin/marketplace.json`
beside `plugin.json` with one entry whose `source` is `"./"`. Users add
the marketplace once:

```bash
claude plugin marketplace add sourceblender/musubi-claude
claude plugin install musubi-claude@sourceblender
```

…and receive updates via `claude plugin update musubi-claude@sourceblender`.

## The dependency boundary (the most important detail)

The current `musubi_claude_runtime.py` does this:

```python
def _shared_lib() -> Path:
    candidates: list[Path] = [Path(__file__).resolve().parents[3] / "lib"]
    configured = os.environ.get("MUSUBI_HARNESS_BIN")
    if not configured:
        try:
            raw = json.loads((_bootstrap_data_root() / "config.json").read_text(...))
            configured = raw.get("harness_bin") if isinstance(raw, dict) else None
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            configured = None
    installed = configured or shutil.which("musubi-harness")
    if installed:
        candidates.append(Path(installed).expanduser().resolve().parent.parent / "lib")
    for candidate in candidates:
        if (candidate / "musubi_harness" / "plugin_runtime.py").is_file():
            return candidate
    raise ImportError("musubi_shared_runtime_unavailable")
```

In the standalone repo, that lookup dies. The plugin no longer sits at
`parents[3]/../lib` relative to fleet-tools. The replacement is a
normal Python import:

```python
from musubi_harness.plugin_runtime import (
    PluginRuntime,
    RuntimeConfig,
    RuntimeConfigError,
)

_runtime = PluginRuntime(STATE_NAME)  # no development_root, no fleet-tools coupling
```

This is the one substantive code change in the migration, and it's
deliberately small: the `musubi_harness` API surface that
`musubi_claude_runtime.py` consumes (`data_root`, `plugin_config`,
`runtime_config`, `harness_bin`, `memory_data_bin`, `tool_environment`)
is what the extracted `musubi-harness` package will export from day one.

`harness_bin()` becomes a wrapper around `shutil.which("musubi-harness")`
once the PyPI package installs the console script. The current
`MUSUBI_HARNESS_BIN` env override still works (it points at any
alternative location) and the `config.json` `harness_bin` field still
works (a deployment-config override for environments where the binary
isn't on PATH). Same escape hatches, fewer filesystem-shape assumptions.

## What stays in fleet-tools/plugins/musubi-claude

`fleet-tools/plugins/musubi-claude/` becomes the dev workspace — the place
where the Claude adapter gets edited first, where the harness is developed
in lock-step with both seats, and where conformance tests run against the
latest unreleased harness. CLAUDE.md inside fleet-tools gets a one-paragraph
note that points at `sourceblender/musubi-claude` for installation and that
fleet-tools's copy is the development head.

A `MIGRATION.md` inside `~/Projects/musubi-claude/` lists:

1. What changed in the file layout (paths into `.claude/`).
2. That identity, namespace, and delivery policy are unchanged.
3. That `musubi-harness` is now a separate PyPI dep and what it replaces
   in fleet-tools' `lib/`.
4. That updating fleet-tools copy → standalone repo is a single PR for
   any future adapter change, and the merge direction.

## What goes into the marketplace entry

`.claude-plugin/marketplace.json`:

```json
{
  "name": "sourceblender",
  "owner": {
    "name": "Eric Mey",
    "email": "ericmey@gmail.com"
  },
  "metadata": {
    "description": "Sourceblender Claude Code plugins"
  },
  "plugins": [
    {
      "name": "musubi-claude",
      "source": "./",
      "description": "First-class Claude Code adapter for Musubi memory: SessionStart continuity, Stop capture, a read-only recall MCP facade plus durable remember, and recall/continuity skills. Shadow-only by default — no remote write until delivery_mode is explicitly set to verified.",
      "category": "productivity",
      "keywords": ["musubi", "memory", "agents", "claude-code", "plugin"]
    }
  ]
}
```

## `plugin.json`

```json
{
  "name": "musubi-claude",
  "displayName": "Musubi Memory (Claude Code)",
  "version": "0.4.0",
  "description": "First-class Claude Code adapter for Musubi memory: SessionStart continuity, Stop capture, a read-only recall MCP facade (recent/search/get/status) plus durable remember, and recall/continuity skills. Shadow-only by default — no remote write until delivery_mode is explicitly set to verified. Built on the shared musubi-harness runtime so the Claude and Codex seats share one contract.",
  "author": {
    "name": "Eric Mey",
    "email": "ericmey@gmail.com",
    "url": "https://github.com/sourceblender"
  },
  "homepage": "https://github.com/sourceblender/musubi-claude",
  "repository": "https://github.com/sourceblender/musubi-claude",
  "license": "Apache-2.0",
  "keywords": ["musubi", "memory", "agents", "claude-code", "plugin"]
}
```

`userConfig` is intentionally **not** declared. Identity is operational,
not plugin-config: it must come from `MUSUBI_ACTOR` / `MUSUBI_PRESENCE` /
`MUSUBI_ZONE` env or `$PLUGIN_DATA/config.json` (all-or-nothing). A user
filling in a `/plugin configure` dialog would be the wrong UI for that
contract — it'd invite partial identity.

## What the existing Claude Code plugin docs tell us to do, vs. what we will do

Pulled from `https://docs.claude.com/en/docs/claude-code/plugins/{create,manifest-reference,publish,marketplace-reference}`:

| Doc rule | How we honour it |
| --- | --- |
| `name` is required, kebab-case, no spaces → becomes the namespacing prefix for skills/agents | `musubi-claude` |
| Put `.claude-plugin/plugin.json` only at `.claude-plugin/`; everything else at the plugin root | Yes |
| `~/.claude/plugins/` holds fetched installs; `${CLAUDE_PLUGIN_ROOT}` resolves there | We rely on this for `scripts/` and `hooks/` paths |
| `${CLAUDE_PLUGIN_DATA}` for state, not `${CLAUDE_PLUGIN_ROOT}` | `$PLUGIN_DATA` env (Claude Code's `PLUGIN_DATA` is set from `~/.claude/plugins/data/<id>/`) keeps the existing state-root logic working |
| `mcpServers` accepts a `.json` file or inline map; one per plugin | `.mcp.json` with one server `musubi-claude` → `scripts/musubi-claude-mcp` |
| `hooks` shape matches `hooks` in `settings.json` | Yes, same shape we already have |
| `claude plugin validate --strict ./musubi-claude` is the authoritative check | Add to CI; gate releases on it |
| Marketplace file at `.claude-plugin/marketplace.json` listing the plugin | Yes, single plugin, `source: "./"` |
| `claude plugin marketplace add sourceblender/musubi-claude` then `claude plugin install musubi-claude@sourceblender` is the install path | Documented in README |
| Auto-update is off by default for own marketplaces | Documented; users opt in |
| Versions are pinned by `version` in `plugin.json`; increment or users stay stale | `0.4.0` for the standalone cut, with a clear upgrade note vs `0.3.5` fleet-tools |

## Release process

- `musubi-harness` ships via release-please (matches the openclaw-musubi
  and musubi repos' pattern).
- `musubi-claude` ships via release-please too. Plugin version is bumped
  in `plugin.json` and in the marketplace entry.
- The first standalone release of `musubi-claude` is `0.4.0` (the prior
  `0.3.5` is the last fleet-tools-only version).
- CI runs `claude plugin validate --strict ./` plus Python `pytest`,
  `ruff`, `mypy --strict`. PyPI release of `musubi-harness` triggers
  via release-please PR merge on the harness repo.

## Identity policy, restated (unchanged from fleet-tools)

- `actor` / `presence` / `zone` come from env (`MUSUBI_*`) or from
  `$PLUGIN_DATA/config.json`. All-or-nothing — partial identity is
  refused, never guessed.
- `presence` is `<actor>/<seat>`; `musubi_harness` enforces
  `actor == presence-prefix`.
- One seat cannot read or write under another seat's namespace.
- `delivery_mode` defaults to `shadow`. `verified` is the explicit
  remote-write gate; nothing leaves disk until then.
- A `shadow`, `pending`, or `accepted` local record is NEVER reported as
  `verified` — only `verified` with an exact `object_id` after readback
  is a receipt.
- Failures degrade visibly (`degraded.jsonl`) and the hook always
  exits 0.

## Step-by-step execution (post-approval)

1. **Cut `sourceblender/musubi-harness` repo.**
   - Init at `~/Projects/musubi-harness/`, src-layout, `pyproject.toml`,
     `LICENSE` (Apache-2.0), `README.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`,
     `SECURITY.md`, `CHANGELOG.md`.
   - Copy `~/Vaults/fleet-tools/lib/musubi_harness/` into
     `src/musubi_harness/`. Verify imports are absolute and complete.
   - Add `bin/musubi-harness` and `bin/musubi-harness-conformance` as
     console-script entries of the new package, with their implementation
     moved into `src/musubi_harness/cli/`.
   - Add `ruff` + `mypy --strict` + `pytest` config and a passing CI.
   - Tag `v1.0.0` and publish to PyPI as `musubi-harness`.
2. **Cut `sourceblender/musubi-claude` repo.**
   - Init at `~/Projects/musubi-claude/`, populate with the layout above.
   - Rewrite `musubi_claude_runtime.py` to import `musubi_harness` directly
     (no `parents[3]/lib` walk, no `config.json` `harness_bin` lookup of
     fleet-tools). Keep the env-override + PATH-lookup + `harness_bin`
     config-override behaviour.
   - Copy `scripts/musubi-claude-mcp`, `scripts/musubi-claude-session-start`,
     `scripts/musubi-claude-stop` verbatim.
   - Copy the two `skills/*/SKILL.md` verbatim.
   - Add `hooks/hooks.json` and `.mcp.json` verbatim.
   - Add `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
     per the values above.
   - Add `pyproject.toml` with `dependencies = ["musubi-harness>=1.0.0"]`.
   - Add a thorough `README.md` (install, configure, identity, fail-open,
     shadow vs verified, troubleshooting) — adapted from the fleet-tools
     README.
   - Add tests under `tests/` covering: Stop-hook envelope projection,
     prompt-id ambiguity refusal, fail-open continuity, MCP five-tool
     schema and the queued-vs-verified distinction.
   - CI: `claude plugin validate --strict ./`, `ruff`, `mypy --strict`,
     `pytest`.
   - Tag `v0.4.0`.
3. **Document the migration.**
   - Add `MIGRATION.md` in both repos (harness and plugin) describing:
     what changed, why, what didn't change, and how to roll back.
   - Add a one-paragraph note in `fleet-tools/CLAUDE.md` saying the
     in-tree plugin is now the development head and the canonical
     install lives at `sourceblender/musubi-claude`.
4. **Validate the install end-to-end.**
   - In a clean worktree, run
     `claude plugin marketplace add sourceblender/musubi-claude` (using
     the GitHub source), then `claude plugin install musubi-claude@sourceblender`.
   - Start a session with the plugin, run `/musubi-claude:musubi-recall`
     and `/musubi-claude:musubi-continuity`, confirm both surface.
   - Trigger a Stop event, confirm `degraded.jsonl` is created in
     `~/.claude/plugins/data/musubi-claude/` and the hook exits 0.
5. **Submit to Anthropic's directory (follow-up, not this iteration).**
   - Only after the public install path is validated and the README is
     final. Submissions need a paid claude.ai plan.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| `musubi-harness` PyPI name collision | Confirm availability on PyPI before `pip install musubi-harness`. If taken, fall back to `musubi-harness-runtime` (less ideal) or `sourceblender-musubi-harness` (worst case). |
| `parents[3]/lib` shape assumption leaks into other adapters | After `musubi_harness` is published, grep fleet-tools for `parents[3]` and `../lib` to find any other adapter that needs the same surgery. The Codex sibling (`plugins/musubi-codex`) has the same pattern. |
| `claude plugin validate --strict` warns on missing fields | Add `version`, `description`, `author.name`, `repository`, `license` in `plugin.json` (done above). |
| `name` is not kebab-case | `musubi-claude` is kebab-case. |
| Path in `.mcp.json` or `hooks.json` not under plugin root | Already use `${CLAUDE_PLUGIN_ROOT}/scripts/...` (the existing plugin does this correctly). |
| Marketplace `name` collides with a reserved name | `sourceblender` is not on the reserved list and isn't impersonating an official Anthropic marketplace. |
| License mismatch between `musubi-claude` (Apache-2.0) and `openclaw-musubi` (MIT) | Both `musubi-claude` and `musubi-harness` are Apache-2.0 per the user's explicit choice. `openclaw-musubi` is MIT and is unrelated — different project, separate repo, different maintainer relationship. |
| Public disclosure of in-progress contract details | The Stop hook transcript-projection logic, the prompt-id-ambiguity rule, the `isMeta` fallback, the continuity fail-open behaviour — all already in the fleet-tools README and shared with the codex seat. Nothing new is being disclosed. |
| Fleet-tools CI breaks when `lib/musubi_harness/` is the source of truth that `musubi-harness` is published from | Document a one-time `pip install -e ../musubi-harness` step for fleet-tools development until fleet-tools's copy is updated to import the installed package. |

## Open questions for the user, before we execute

- PyPI name availability for `musubi-harness` — verify before tagging
  v1.0.0. If unavailable, fall back per the risk table above.
- Org name: `sourceblender` (the existing remote) — confirm before
  pushing.
- License: **Apache-2.0** for both `musubi-claude` and `musubi-harness`
  (confirmed). Note that `openclaw-musubi` is MIT — unrelated project,
  separate repo, no license alignment needed.
- Author email in `plugin.json`: `ericmey@gmail.com` (matches
  openclaw-musubi). Confirm.
