"""Claude deployment binding for the shared Musubi plugin runtime.

This is the only host-specific runtime code the Claude adapter owns: it
names this plugin's state root and re-exports the harness's runtime
helpers. All identity, namespace, delivery-mode, and canonical-tool
POLICY lives in ``musubi_harness.plugin_runtime`` so the Claude and Codex
seats can never silently evolve different memory boundaries.

Compared with the in-fleet-tools version, the filesystem walk that
located ``../lib/musubi_harness/`` is gone — the harness is a real
PyPI dependency now (``musubi-harness>=1.0.0``), installed via pip,
imported the normal way. Same escape hatches: ``MUSUBI_HARNESS_BIN``
env override, ``harness_bin`` config override, ``shutil.which`` PATH
lookup. Same state root: ``$PLUGIN_DATA`` (set by Claude Code) or
``~/.local/state/musubi-claude``.
"""

from __future__ import annotations

from musubi_harness.plugin_runtime import (
    PluginRuntime,
    RuntimeConfig,
    RuntimeConfigError,
)

STATE_NAME = "musubi-claude"


# Re-export the harness's PluginRuntime so it reads $PLUGIN_DATA (Claude
# Code's per-plugin data dir) or falls back to ~/.local/state/musubi-claude
# in a non-hook shell.
_runtime = PluginRuntime(STATE_NAME)

# The shared thin bindings (mcp-facade, continuity) bind to this exact
# instance so adapter behaviour cannot diverge from the harness contract.
runtime = _runtime
data_root = _runtime.data_root
plugin_config = _runtime.plugin_config
runtime_config = _runtime.runtime_config
harness_bin = _runtime.harness_bin
memory_data_bin = _runtime.memory_data_bin
tool_environment = _runtime.tool_environment
require_owned_namespace = _runtime.require_owned_namespace

# Re-export the harness's exception type so adapter scripts can catch
# identity/config failures uniformly.
__all__ = [
    "PluginRuntime",
    "RuntimeConfig",
    "RuntimeConfigError",
    "STATE_NAME",
    "runtime",
    "data_root",
    "plugin_config",
    "runtime_config",
    "harness_bin",
    "memory_data_bin",
    "tool_environment",
    "require_owned_namespace",
]
