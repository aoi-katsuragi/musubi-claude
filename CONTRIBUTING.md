# Contributing

Thanks for your interest in `musubi-claude`. This plugin is one of
several host adapters in the `musubi-*` family; it binds the Claude Code
host to the shared [`musubi-harness`](https://github.com/sourceblender/musubi-harness)
runtime.

## Ground rules

1. **The dependency arrow points one way.** `adapter → harness`, never the
   reverse. If you find yourself wanting to import from a host adapter,
   the change belongs there, not here.
2. **No new runtime dependencies beyond `musubi-harness`.** Every other
   transport dep (MCP, agent framework, etc.) belongs in the harness or
   in a specific adapter — not in this one.
3. **Identity policy is non-negotiable.** `actor` / `presence` / `zone`
   must come from env or `$PLUGIN_DATA/config.json`, all-or-nothing.
   Never derive identity from the host.
4. **`queued` and `verified` stay distinct.** A local row is a durable
   promise; a verified row with an exact `object_id` is a receipt. If a
   PR risks collapsing the two, it will be reverted.

## Claude-specific responsibility

The harness is host-neutral. This adapter is the one that knows how
Claude Code's Stop and SessionStart hooks behave. Three things have
caused production defects and are tested for:

- **Event id is bound to the event's own identity**, `claude-code:<session>:<prompt>`,
  so retries dedupe.
- **The Stop event's `last_assistant_message` is authoritative** — never
  reconstructed from the transcript.
- **`prompt_id_ambiguous` is refused closed** when two records under the
  same promptId disagree on content.

PRs that change Stop-hook envelope projection must update or extend
`tests/test_stop_envelope.py` accordingly. The tests are the contract
the production code has shipped against.

## Development setup

```bash
git clone https://github.com/sourceblender/musubi-claude
cd musubi-claude
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install ruff mypy pytest pytest-cov
```

## Before opening a PR

```bash
ruff check scripts tests
ruff format --check scripts tests
mypy scripts
pytest
claude plugin validate --strict .
```

CI runs the same checks on every PR. `claude plugin validate --strict`
is the authoritative manifest check; the marketplace and plugin JSON
must round-trip cleanly.

## Pull request flow

1. Open a PR from a topic branch.
2. Describe the contract change and which adapters are affected.
3. CI must be green before review.
4. A maintainer reviews for contract integrity, dependency discipline,
   and type strictness. New code lands `mypy --strict`-clean.
5. Merge via squash. The release-please bot opens a follow-up PR to
   cut the plugin version.

## Releases

Releases are managed by release-please. Conventional Commit messages
on `main` drive the next version proposal; merging the release-please
PR cuts the new plugin version and tags `v<X.Y.Z>` on GitHub.

The marketplace entry's `version` is bumped to match `plugin.json`'s
`version`. Users who have already added the marketplace will receive
updates via `claude plugin update musubi-claude@sourceblender`.

## Security issues

Please email `ericmey@gmail.com` rather than opening a public issue.
See `SECURITY.md`.
