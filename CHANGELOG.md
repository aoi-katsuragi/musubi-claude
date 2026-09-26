# Changelog

All notable changes to `musubi-claude` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-09-26

### Changed
- **First standalone public release.** Moved out of
  `~/Vaults/fleet-tools/plugins/musubi-claude/` into its own public
  repo at `github.com/sourceblender/musubi-claude`.
- **Runtime extraction.** The `musubi_harness` shared runtime the
  adapter depended on at `../lib/` (fleet-tools layout) is now the
  real PyPI package `musubi-harness>=1.0.0`. The
  `parents[3]/lib/musubi_harness/` filesystem walk is gone — the
  harness is imported the normal way. Same identity, namespace,
  delivery-mode, and canonical-tool policy; same `MUSUBI_HARNESS_BIN`
  env override and `harness_bin` config override escape hatches.

### Added
- `.claude-plugin/marketplace.json` so users can install via
  `claude plugin marketplace add sourceblender/musubi-claude &&
  claude plugin install musubi-claude@sourceblender`.
- Apache-2.0 LICENSE.
- `tests/test_runtime_binding.py` — verifies the binding exposes
  the harness contract and contains no `parents[3]/lib` filesystem
  walk.
- `tests/test_stop_envelope.py` — exercises the Claude-specific Stop
  hook payload → envelope projection against the production defects
  that motivated it (event id stability, alias conflict refusal,
  `isMeta` fallback, ambiguous-prompt refusal, transcript-session
  mismatch refusal, fail-open degraded sink).

### Migration from `0.3.x`
- `pip install musubi-harness` is now required (Claude Code does
  this automatically when the plugin loads; for local development
  it's part of the dev install).
- `pip install -e ../musubi-harness` is no longer required for local
  development.
- The fleet-tools copy at `~/Vaults/fleet-tools/plugins/musubi-claude/`
  continues to work as the development head during the transition
  window. Any new fix lands here first, then backports.

[Unreleased]: https://github.com/sourceblender/musubi-claude/compare/HEAD
[0.4.0]: https://github.com/sourceblender/musubi-claude/releases/tag/v0.4.0
