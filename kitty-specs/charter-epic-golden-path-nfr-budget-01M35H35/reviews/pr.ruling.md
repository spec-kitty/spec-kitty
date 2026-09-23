# Operator ruling — pre-merge squad (PHASE=pr)

Recorded 2026-09-23 by the orchestrator from the operator's answer.

## Ruling 7 — PR-TESTS-002 (golden-path margin vs. uncached session venv bootstrap)

Question put: on Actions, the golden path's ~52.78s setup is dominated by the session-scoped
`test_venv` fixture's uncached, network-variable `pip install -e`, paid because the test runs
first in `tests/e2e/`. There is a single 102.56s sample, 7.44s under the hard ≤110s bar
(Ruling 2). What should the mission do?

Operator answer: **Get more samples; do not change the test.** The golden-path test and the
shared test infrastructure stay as they are. Closure evidence on the real PR is **three Actions
`tests (e2e)` runs, all with the golden path's setup + call ≤110s**. If any run lands above 110s,
Ruling 2 applies: the mission returns to the operator. The bootstrap cost is recorded in
the PR body as a known risk for the maintainers.

This ruling closes PR-TESTS-002 for this mission. Its acceptance bar is the three-run
evidence, and no code change is required.
