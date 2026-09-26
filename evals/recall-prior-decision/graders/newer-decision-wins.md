---
type: llm
weight: 2
---
PASS if the reply gives the current decision as the NEWER one (2026-08-14): exponential backoff starting around 500 ms, doubling, capped at 30 seconds, about 6 attempts; AND it either notes that an older decision (2026-07-02, every 5 seconds, linear) exists and was superseded or conflicts, or clearly treats the newer one as the one in force.
FAIL if the reply presents the 5-second linear rule as current, presents both as equally valid without choosing, or says it does not know the decision.
