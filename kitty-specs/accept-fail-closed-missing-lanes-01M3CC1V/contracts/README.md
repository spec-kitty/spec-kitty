# Contracts

This mission is a contained fail-closed bug fix (#4891) with no new API/data
contracts. The behavioural contract is the acceptance matrix
(`../acceptance-matrix.json`): with `lanes.json` absent, `spec-kitty accept` must
exit non-zero, set `summary.ok=False`, record the skipped/blocked matrix checks,
and record no `accepted_at`/`accept_commit`. The regression tests
(`tests/characterization/test_trio_pure_cores.py`,
`tests/cross_cutting/misc/test_acceptance_support.py`) are the executable form.
