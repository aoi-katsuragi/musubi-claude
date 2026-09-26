---
name: setup
description: One-time install of the musubi-harness runtime this plugin needs, into the plugin's own environment. Run it after installing or updating the plugin, or when Musubi memory says it is not set up.
disable-model-invocation: true
allowed-tools: Bash(musubi-claude-setup *) Bash(musubi-claude-health *)
---

# Set up Musubi memory

This installs the pinned `musubi-harness` package into this plugin's own data
directory. It needs the network once; after that, capture and recall run
offline. It never changes anything outside the plugin's data directory.

1. Run exactly this with Bash, and nothing else:
   `musubi-claude-setup --plugin-data "${CLAUDE_PLUGIN_DATA}"`
2. Report its last line verbatim (the installed version and where). If it
   failed, quote the error line verbatim and stop — do not retry with a
   different command, do not `pip install` anything yourself.
3. Then run `musubi-claude-health --plugin-data "${CLAUDE_PLUGIN_DATA}"` and tell
   the user, in two or three plain sentences:
   - whether the identity is configured (if `identity.ok` is false, say they
     need to fill in **Musubi actor** and **Seat** in `/config` → musubi-claude);
   - which delivery mode is active (`shadow` keeps everything on this machine;
     `verified` sends to Musubi and reads each record back).
4. Tell the user to restart Claude Code (or run `/mcp` and reconnect
   `musubi-claude`) so the memory tools start with the new environment.

Never print or ask for a token here.
