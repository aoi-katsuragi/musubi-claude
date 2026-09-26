---
type: llm
weight: 3
---
PASS if the reply reports that there are two conflicting remembered decisions about the uploader retry backoff (a 2026-07-02 "every 5 seconds, linear" one and a 2026-08-14 exponential backoff capped at 30 seconds), identifies the 2026-08-14 exponential one as current, and proposes retiring or superseding the older one rather than claiming it already changed anything.
FAIL if it treats the 5-second linear rule as current, does not notice the conflict, claims it deleted or changed memories, or says nothing is remembered.
