---
expect:
  query: string
---
{"query": "{{input.query}}", "results": [
 {"object_id": "ep-7f3a91", "namespace": "alice/laptop/episodic", "plane": "episodic", "state": "matured", "score": 0.912,
  "title": "Uploader retry backoff decision",
  "content": "Decision (2026-08-14): the uploader retries with exponential backoff starting at 500 ms, doubling each attempt, capped at 30 seconds, max 6 attempts."},
 {"object_id": "ep-2c0d14", "namespace": "alice/laptop/episodic", "plane": "episodic", "state": "retracted", "score": 0.874,
  "title": "Uploader retry backoff (superseded)",
  "content": "Decision (2026-07-02): the uploader retries every 5 seconds, linear, forever. RETRACTED 2026-08-14: replaced by exponential backoff."}
]}
