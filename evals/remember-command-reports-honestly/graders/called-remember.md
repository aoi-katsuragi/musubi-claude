---
type: tool_used
tool: mcp__plugin_musubi-claude_musubi-claude__musubi_remember
input_match: 'db2\.internal\.example'
# with-only: the plugin's tool cannot be called without the plugin, so scoring
# this in the no-plugin arm would inflate the delta mechanically.
arm: with-only
---
