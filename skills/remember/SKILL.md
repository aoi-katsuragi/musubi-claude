---
name: remember
description: Save one fact, decision, or commitment to your Musubi memory, and report honestly whether it is stored yet.
argument-hint: "<what to remember>"
disable-model-invocation: true
allowed-tools: mcp__plugin_musubi-claude_musubi-claude__musubi_remember
---

Remember this: **$ARGUMENTS**

1. If it is empty, ask what to remember. If it contains a password, API key,
   token, or other secret, refuse and say why - memory is not a secret store.
2. Call `musubi_remember` once with the text as `content`, 2-4 short topical
   `topics`, and a stable `idempotency_key` derived from the text.
3. Report the result word for word in meaning:
   - `verified` with an `object_id` → stored in Musubi; give the object_id.
   - `queued` → saved locally and queued; **not yet confirmed stored**. In
     shadow mode it stays queued by design.
   - an error or `dead` → not stored; quote the reason.
   Never say "saved to memory" for anything short of `verified`.
