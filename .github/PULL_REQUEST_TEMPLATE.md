## What this PR does

<!--
musubi-claude is a thin Claude Code host binding for the shared
musubi-harness runtime. Describe the Claude-specific change here.
-->

## Why

<!--
Link to an issue if one exists. State the problem and the chosen
solution.
-->

## Harness contract impact

- [ ] No change to `shadow` / `pending` / `accepted` / `verified` / `dead`
- [ ] No change to recall tool schemas (`musubi_recent`, `musubi_search`,
      `musubi_get`, `musubi_status`, `musubi_remember`)
- [ ] No change to identity policy (env-or-config, all-or-nothing)
- [ ] No change to namespace policy (`actor == presence-prefix`)
- [ ] No change to `musubi-harness` API surface

If any of the above is checked off as "change", describe it here and
note whether the change belongs in the harness rather than in this
adapter:

## Stop-hook envelope changes

If this PR changes `scripts/musubi-claude-stop`:

- [ ] `tests/test_stop_envelope.py` updated or extended
- [ ] Event id stability preserved (claude-code:<session>:<prompt>)
- [ ] Alias conflict refusal preserved
- [ ] `isMeta` fallback preserved
- [ ] Ambiguous prompt refusal preserved
- [ ] Transcript-session mismatch refusal preserved
- [ ] Fail-open degraded sink preserved

## Checklist

- [ ] `ruff check scripts tests` is clean
- [ ] `ruff format --check scripts tests` is clean
- [ ] `mypy scripts` is clean
- [ ] `pytest` is green
- [ ] `claude plugin validate --strict .` is clean
