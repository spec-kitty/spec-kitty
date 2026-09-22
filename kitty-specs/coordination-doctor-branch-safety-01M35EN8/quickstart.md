# Quickstart: Verify Coordination Doctor Branch Safety

Audience: Spec Kitty core engineer reviewing issue #4920.

1. Run the real-Git contract:
   `uv run --extra test pytest -q tests/coordination/test_coord_staleness.py`.
2. Confirm the wrong-branch case exits 1, reports
   `COORDINATION_BRANCH_STALE_FIX_BLOCKED`, and leaves all refs unchanged.
3. Confirm the correct-branch control exits 0 and advances the declared coordination
   ref to the target SHA.
4. Run `make test-fast` and the full `tests/coordination` subsystem before PR handoff.
