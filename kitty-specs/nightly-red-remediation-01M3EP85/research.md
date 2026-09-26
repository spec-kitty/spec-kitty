# Research: Nightly red remediation

Evidence comes from the 4-agent review squad (read-only) run against `main` @ `ae0ff2fb`. Its output is posted on #5045 as [comment 5844901490](https://github.com/spec-kitty/spec-kitty/issues/5045#issuecomment-5844901490).

## R-1 Fixture drift causes (FR-001..FR-007)

- **Decision:** Treat every one of the 25 integration failures, plus the performance resume-budget failure, as a stale fixture, and re-pin it against the current contract.
- **Rationale:** each cause maps to a deliberate product change:

| Cause | Product change | Governing record |
|---|---|---|
| A | 2fd7eabf01 | ADR 2026-09-24-2 |
| B / C1 | 6545dc532f, 7da1750ebb | Epic #5001 FR-012, #4982 |
| C2 | Fixture writes `mission_id=<slug>`, violating the `LanesManifest` invariant (`lanes/models.py:145`) | — |
| C3 | b8878872a9 (bisected) | #4764 |
| D | 788db8ffb4 | #4758 |
| E | f33a70fb6c | events 10.4 / events#69 |

- **Alternatives considered:**
  - *Relax the gates.* Rejected: it reopens the defects those gates close.
  - *xfail.* Rejected by C-001.

## R-2 Merge dry-run refusal (FR-008)

- **Decision:** Catch `CoordinationWorktreeUnmaterialized` and `CoordinationBranchDeleted` on the dry-run path. Render the same message and hint the real merge uses (`executor.py:~3354-3369`), then `Exit(1)`. With `--json`, emit a single JSON error document.
- **Rationale:** the real merge path already defines the operator-facing contract, and a traceback is never an acceptable CLI outcome.
- **Alternative rejected:** fall back to the primary checkout in the forecast. That violates ADR 2026-09-24-2.

## R-3 Fresh-stop wedge (FR-009)

**Mechanism** (confirmed by reading `executor.py`):

1. `_load_or_create_merge_state` persists a fresh `state.json` (`resolve.py:240`).
2. `_phase_gates_and_state` then runs. It can `Exit(1)` on "Merge gates failed" (`:568`), the canonical-history guard, or a declined hollow-review confirmation.
3. That phase runs **before** `_capture_reconciliation_claim` writes the marker.
4. The next plain merge loads the leftover state as `is_resume=True`. `detect_legacy_in_flight_state` finds no marker and refuses the run as pre-fix.

- **Decision:** Generalise the #4764 rule, which clears only this run's own fresh state, from the readiness check to the whole pre-mutation gate phase. On a fresh run, any `typer.Exit` raised from `_phase_gates_and_state` clears that run's `state.json` before re-raising.
- **Second decision:** `merge --abort` also removes the post-fix marker, so an aborted transaction leaves no marker that could mask a later genuine pre-fix state.
- **Rationale:**
  - No mutation has happened at that point, so "the mission is unchanged" must hold on disk too.
  - A single authority avoids a second marker-write site.
  - A genuine pre-fix resume stays refused.
- **Alternative rejected:** write the marker at state creation. That spreads the FR-012 stamp across two sites. It would also make an aborted-before-mutation run look like a real in-flight post-fix transaction on the next run, triggering resume semantics (for example "Resuming merge… 0/N") for work that never began.

## R-4 Nightly interpreter leg (FR-010)

- **Findings:**
  - A job-level `timeout-minutes` kill cancels the whole job, so the later `if: always()` steps never run. The run's steps stayed "pending", which confirms this.
  - The `nightly-summary` job only echoes each result and always exits 0.
- **Decision:**
  - Add a step-level `timeout-minutes` on the suite step, strictly below the job cap. A step timeout fails only that step, and later `if: always()` steps still run.
  - Raise the job cap to leave headroom for sync, upload and escalation.
  - Add a per-test `--timeout` so a genuine deadlock fails one test.
  - Make `nightly-summary` exit 1 on any `needs.*.result` other than `success`.
- **Budget:**
  - A local 4-worker 3.13 run took 29m42s. Scaled to a 4-vCPU runner with collection overhead, the step budget is ceil(~40 × 1.5) = 60 minutes and the job cap is 75 minutes.
  - Re-derive both from the first honest run using the file's ceil(×1.5) method.
- **Alternative rejected:** sharding the leg now. That is a larger change and is noted as a follow-up.

## R-5 Doctor-ops sweep gate (FR-011)

- **Findings:**
  - 95% of the timed window is one-time `ProfileInvocationExecutor.__init__`, which parses the doctrine graph twice.
  - The 100 closes themselves take 0.03s cumulative.
  - Locally the test measures 1.4–1.6s against a 2.0s budget.
- **Decision:**
  - Build the executor outside the timed window, so the test measures what its name says.
  - Add a scaling assertion (1k vs 10k spine) that fails when per-close cost grows with spine size.
  - Re-derive the absolute budget with headroom (5.0s, matching its siblings).
- **Follow-up (C-004):** the doctrine-graph double-parse and a lazy registry are deferred to a separate issue.
