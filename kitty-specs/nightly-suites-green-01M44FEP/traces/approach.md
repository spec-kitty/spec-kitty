# Approach: nightly-suites-green-01M44FEP

Running log of the approach and how it changes. Append dated entries of one to three sentences.

## Approach at the end of planning (2026-10-05)

Four nightly jobs are red on `main` @ `9adc68803f` for three unrelated causes. Each is fixed at its structural cause in its own lanes and delivered as one pull request.

- **Track A (WP01 to WP04)**: a bare-slug coordination Mission cannot consolidate onto a protected target. Order: two tidy-first enablers (teardown identity read, structured seed-refusal field), then the directory alias authority and partition classification, then the consolidation consumers and the one-directory end state; the refused-seed backstop runs alongside.
- **Track B (WP05, WP06)**: performance tests bound to runner speed. A calibration spike sets runner-relative limits; a planted-work test proves the assertion can fail; a git-subprocess count pin gives a clock-free signal per pull request.
- **Track C (WP07)**: the commit-recipe gate flags help text and ran only nightly. Tidy-first move to the architectural battery, then fixtures, a recipe-shape classifier, and an allowlist reduced to live hits.
- **WP08**: the Track A decision record, registration of both records, changelog and docs index.

Red first throughout (charter C-011, spec C-005): enabler commits, then a failing test through the pre-existing entry point, then the fix. For Track B "red" is the previous absolute assertion failing at a throttle level where the start-up floor is at least 1.9 s, with the cited nightly result.

## Operator rulings that shape the approach (2026-10-05)

1. **Alias authority** (`specify.track-a.bare-slug-fix`): keep the composed coordination directory; one exact alias set {primary directory name, composed `<slug>-<mid8>`}, consumed by the partition classifier, the bookkeeping exemption and the teardown metadata read. Only the body of `_is_bookkeeping` changes in `consolidation/reconciliation.py`.
2. **Alias plus fold to one directory**: the target ends with one directory, the primary one, holding the full event log; seeded composed-directory records are projected back onto the primary directory on landing.
3. **Move the gate**: the recipe scanner test moves to `tests/architectural/`; the `tests/specify_cli/cli/commands` directory stays nightly-only and is cross-referenced, not promoted.

## Entries

- 2026-10-05 (tasks): Decomposed into 8 work packages on 8 lanes (`lane-a` to `lane-g` plus `lane-planning`). WP01, WP05, WP06 and WP07 can start together; WP04 runs alongside WP02 and WP03.
- 2026-10-05 (tasks): Stop conditions written into the prompts: a fold that needs a new destructive git operation (WP03); clean and planted ratio ranges that overlap (WP05); any edit in a path owned by a running mission (all).
- 2026-10-05 (post-tasks squad): The adversarial review changed six work packages. WP08 became `code_change` with docs-only ownership on its own lane (`lane-h`), because a planning-lane claim waives code-lane ancestry and would never see its dependencies. WP01 adds `SeedReport.uncommitted_paths` and commits the teardown test red first; WP04 names files from that field, adds a twice-refused case and a stop condition for its control. WP02 must keep one `mid8` derivation in the commit router, add no new raise, and read only the literal primary directory. WP05 hosts its functional tests in `tests/architectural/test_perf_limit_authority.py`, commits the six-nightly-row positive control and bounds the plant at 0.3 to 0.7 of the floor. WP06 chooses the pin's home from the job-selection dry run and samples with sibling files in both orders. WP03 keeps imports function-local and makes the foreign-directory gate test unconditional; its T012 and T014 await the architect's mechanism.
- 2026-10-05 (implement): every work package got a separate profile-loaded reviewer; five of eight were rejected at least once (WP02 and WP07 twice). The rejections found real defects: a count pin that included harness-forced calls, a classifier that dropped f-string interpolations, a printed recovery command that could not succeed, an alias that raised on unsafe input, and one defect introduced by an orchestrator instruction (a mid8 shape check that re-created the original failure).
- 2026-10-05 (implement): reviewers proved red-first in throwaway worktrees at the red commits and ran mutations in scratch copies; that caught vacuous or order-dependent tests that reading the diff would not.
- 2026-10-05 (implement): operator steer mid-run: changing a mock is not test tampering. A test-design scrutiny then showed the nightly reproduction asserted only exit 0 behind mocks of the bookkeeping commit and the `done` record. It now runs the real consolidation; that removed the need for the reconciliation change under the default strategy.
- 2026-10-05 (implement): the performance calibration was first specified as long local series (30 and 10 runs); that cost about three hours of one implementer. Operator ruling: local runs prove non-vacuity only, limits are calibrated on the CI runner.
- 2026-10-05 (closeout): follow-ups were filed first (#5748 to #5753), then seven small ones were folded on a branch cut from the integrated tip while the last work package was in review.
- 2026-10-05 (closeout): the pre-PR squad on the rebuilt branch found that a fold added from a follow-up printed a remedy that did not recover and a false "before any state change" notice; it was narrowed and now prints no command. Lesson: a remedy line is a claim, and needs an end-to-end "follow the advice" test before it ships.
- 2026-10-05 (closeout): the closeout run of the owning directories found what no named-file run had: three more tests on fixtures with an uncomposed coordination branch, and behind them a real gap (the seed carries every coordination-kind file into the composed directory, the fold only handled the status pair). Operator ruling: generalise the fold. A second review round then confirmed the remaining limit: a coordination file written under the composed name during the Mission is refused, not carried forward (#5751).
