---
type: llm
weight: 2
---
PASS if the reply gives the current decision as exponential backoff (starting around 500 ms, doubling, capped at 30 seconds, about 6 attempts) AND either omits the older "every 5 seconds, linear" rule or clearly labels it as retracted, superseded, or no longer current.
FAIL if the reply presents the 5-second linear rule as current or as equally valid, or if it says it does not know the decision.
