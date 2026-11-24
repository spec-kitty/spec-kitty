---
affected_files: []
cycle_number: 2
mission_slug: setup-plan-coord-lifecycle-commit-01M84SXJ
reproduction_command:
reviewed_at: '2026-11-23T22:57:16Z'
reviewer_agent: claude
wp_id: WP01
---

---
affected_files:
- src/specify_cli/cli/commands/agent/mission_setup_plan.py
- tests/coordination/test_setup_plan_coord_lifecycle_3933.py
cycle_number: 2
mission_slug: setup-plan-coord-lifecycle-commit-01M84SXJ
reproduction_command: see "B2 reproduction" below (in-process, a monkeypatched guard that injects the foreign commit after it returns)
reviewed_at: '2026-11-23T23:10:00Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review — cycle 2 — CHANGES REQUESTED

Reviewer: `claude::reviewer-renata`. Implementer: `claude::implementer-ivan`.
Reviewed head `3be41b81` (red `91400c0b`, fix `bcfec285`). Target `issue-3933-lifecycle-event-placement` (`1890a6c2`).

The cycle-1 B1 repro is fixed. S1, S2 and S3 are resolved. Two must-fix items remain. Both belong to the same data-loss class as B1, and both are small.

## Verified (passes)

- **B1, through the real CLI, text and `--json`.** A foreign writer advances the coordination branch with commit-tree and a CAS update-ref, and the worktree is not resynced.
  - Result: rc 1, `SETUP_PLAN_LIFECYCLE_UNCOMMITTED` with `COORD_STATUS_SURFACE_DIVERGED` in the diagnostic.
  - The branch tip is unchanged and the foreign event survives on the branch.
- **Lagging-HEAD variant.** I dropped the last committed line (`PlanStarted`) from the coordination worktree's log, then ran setup-plan.
  - Result: rc 1, `COORD_STATUS_SURFACE_DIVERGED`, branch unmoved, and the committed event survives.
- **Extra uncommitted lines in the worktree log.** They are committed (`committed`) and the worktree ends clean. This is correct: only loss is refused.
- **Mutation.** With the `_lifecycle_log_divergence` call removed, `test_coord_setup_plan_never_erases_events_the_branch_committed` goes red (rc 0, so the event is erased). The other tests stay green, so the guard test is load-bearing.
- **`# noqa: BLE001`.**
  - It is narrow: one call, with an inline FR-004 rationale.
  - `except Exception` does not catch `KeyboardInterrupt` or `SystemExit`.
  - A narrower tuple would be guesswork, because the router already converts `CalledProcessError`, `RuntimeError` and the lock timeout itself.
  - Accepted.
- **S2.** On every coordination topology the log is committed at create, so an absent log after setup-plan's own emission means the best-effort emission (`_emit_spec_plan_phase_events`) failed. Refusing there is the right fail-loud answer. Accepted.
- **Non-coordination topologies.** These pass: `test_non_coordination_setup_plan_is_unchanged[single_branch|default_before_settlement]` and the golden-path file.
- **Gates.** ruff, `ruff format --check --force-exclude`, mypy (0 issues) and C901 are all clean.

## B2 (blocking): the guard is not tied to the commit, so a foreign commit landing after the guard is still erased with rc 0

`_lifecycle_log_divergence` reads `HEAD` and the worktree log. `commit_for_mission` then runs `git commit --only <log>` on whatever `HEAD` is at commit time. So the guard has three gaps:

- It runs outside the L1 status lock (`_coord_status_locks` is taken only inside `_safe_commit_group`).
- Nothing binds the commit to the `HEAD` the guard checked.
- The router already supports this binding (`expected_parent_sha`), and the fix does not use it.

**B2 reproduction.** I wrapped `_lifecycle_log_divergence` so that it calls the real guard, then runs the test file's own `_advance_coord_branch_with_foreign_event(mission)`, then returns the guard's verdict. I then ran setup-plan in-process (`_run_setup_plan_in_process`).

- Result: exit 0, and `lifecycle_commit: {"status": "committed", ...}`.
- The foreign event is **gone** from the coordination branch. This is the cycle-1 B1 symptom, reached through the check-vs-commit window.

`BookkeepingTransaction` runs its guard, its append and its commit under L1. Setup-plan's guard runs unlocked. Any ref mover that does not append to the worktree file can therefore land in this window. That includes the plumbing writer the cycle-1 repro modelled.

**Fix (small):**

- Have the guard read and return the `HEAD` SHA it checked (`git rev-parse HEAD` in `surface_root`).
- Pass that SHA to `commit_for_mission(..., expected_parent_sha=<that sha>)`. A moved branch is then refused instead of overwritten, and setup-plan renders the refusal as `SETUP_PLAN_LIFECYCLE_UNCOMMITTED`.
- Taking `coord_status_lock` around the guard and the commit is a good addition but does not replace this, because lock-free plumbing writers ignore it.
- Add the red test above: a foreign commit injected right after the guard returns must give rc 1, an unmoved branch and a surviving event.

## B3 (blocking): the refusal tells the operator to commit the stale log, which erases the events

`_refuse_uncommitted_lifecycle` always ends with: "They stay uncommitted there; commit them in that checkout or re-run setup-plan once the refusal is fixed."

On a `COORD_STATUS_SURFACE_DIVERGED` refusal, committing that checkout's log is the exact operation the guard just refused. It drops the committed events. This was observed in the text-mode output: the message is the house divergence remedy (`git checkout HEAD -- ...` keeps the committed events) immediately followed by this contradictory instruction.

**Fix:** when the diagnostic is a divergence or unreadable refusal, do not print "commit them in that checkout". Point to the diagnostic's own remedy, and say that setup-plan's own events must then be re-recorded by re-running setup-plan, since `checkout HEAD --` discards them. Pin the wording in a test.

## Non-blocking

- **N3.** The inherited divergence text speaks of "a rolled-back consolidation" and a "stranded `done`". In setup-plan's context (planning, nothing consolidated) that is misleading. Consider a lead line in setup-plan's own words before the house text. Not required.
- **N4.** Coverage claim. My measured diff coverage on `mission_setup_plan.py` is **97.3%** (75 lines, missing 782 and 816), not 100%. Those lines run only through the subprocess CLI tests. This is above the ≥90% gate; please correct the figure in the PR.
- **#7822.** The pre-review gate's `no_coverage — no changed files detected for this WP` on this resubmission matches the known #7822 (a single_branch Mission, a resubmitted WP with code commits). It is not a defect of this WP.

## Tests run (reviewer, head 3be41b81)

| Command | Result |
|---|---|
| `pytest tests/coordination/ tests/specify_cli/cli/commands/agent/test_mission_setup_plan_phases.py test_setup_plan_branch_match.py test_setup_plan_commits_lifecycle_3933.py test_setup_plan_read_surface.py tests/integration/test_placement_partition_golden_path.py -n auto --dist loadfile` | 994 passed |
| `make test-fast` | 3222 passed, 7 skipped |
| `pytest tests/architectural/test_no_legacy_terminology.py test_layer_rules.py test_ruff_format_enforcement.py` | 180 passed |
| Reviewer probes (B1 in CLI text mode, lagging HEAD, extra uncommitted lines, B2 race) | 4 run. B1, lagging HEAD and extra lines behave correctly; the B2 race erases the foreign event |
| Mutant (guard call removed): `tests/coordination/test_setup_plan_coord_lifecycle_3933.py` | `never_erases` red, the rest green |
| `diff-cover` vs target, `mission_setup_plan.py` | 97.3% |
