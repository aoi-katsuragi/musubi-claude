---
type: regex
target: mock_calls
pattern: 'musubi_'
match: not_contains
# with-only: in the no-plugin arm there is no mocked server, so mock_calls is
# unavailable and this check would fail there and inflate the delta. It stays a
# pass/fail indicator on the plugin arm, where it is the whole point.
arm: with-only
---
