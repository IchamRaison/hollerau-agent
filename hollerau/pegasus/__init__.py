"""pegasus: a complete, code-driven baseline buyer (Vincent's lane: runner, guards, bench).

- `economics`: every allowed non-price structure priced with the kit's cost function
- `claims`: arguments the arena verifies (falling indices, notice, should-cost, forecast, scorecard, rival offer)
- `agent`: anchor, concessions in total cost C, up to 3 iso-C sheets, accept/hold/walk rules
- `guard`: fail-closed pre-send check (IDs known, figures equal the facts, no leak) + `guard_move` for `contracts.Move`
- `play`: one worker per supplier thread (RFQ without timeouts), closing before the wave cap
- `bench` (sandbox) and `cli` (practice/sandbox/final): both call `sessions.require_validation`.
"""
