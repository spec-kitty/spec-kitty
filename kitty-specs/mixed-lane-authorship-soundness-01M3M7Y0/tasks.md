# Work Packages: Mixed-lane authorship soundness

**Inputs**: Design documents from `kitty-specs/mixed-lane-authorship-soundness-01M3M7Y0/`
**Prerequisites**: plan.md (Design D-1…D-5), spec.md, research.md (R-1…R-10), data-model.md, contracts/attribution-and-verdicts.md, quickstart.md

**Tests**: Required by the spec (C-006 red-first, SC-001…SC-007, NFR-005). Every WP ships its own focused tests.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Subtask rows are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

**Order of work (operator brief)**: campsite tidy → #5047 fixture → #5046 red-first → capture → gate → production-path proof and residual pins.

---

## Work Package WP01: Terminus fixture tidy + committed-then-canceled mixed-lane builder (Priority: P1)

**Goal**: Behaviour-preserving extraction of the three terminus builders' shared scaffolding, then a single-call builder that plants a canceled WP's lane commits (add/modify/delete, optional superseding or undoing survivor commits, optional lane-sync merge) with or without `lane_head` attribution before the coord workspace resolves; correct the recorded fixture limitation (#5047).
**Independent Test**: Existing terminus tests that use the three builders pass unchanged; a new fixture test builds every variant and shows (a) a post-build `update-ref` still consolidates, (b) a missing coord worktree dir yields the unmaterialized abort.
**Prompt**: `tasks/WP01-terminus-fixture-mixed-lane-canceled-builder.md`
**Requirement Refs**: FR-007, FR-008, SC-005

### Included Subtasks

T001 Extract shared repo-init / coord-cut / lane-cut scaffolding from the three builders (behaviour-preserving) (WP01)
T002 Fixture hygiene: `.worktrees/` ignored in the init commit, explicit-path adds, `_event(..., policy_metadata=None)` (WP01)
T003 New builder `build_coord_mission_mixed_lane_canceled` with plant variants and optional attribution stamps (WP01)
T004 [P] Fixture behaviour test: post-build ref mutation still consolidates; missing coord worktree dir → unmaterialized (FR-008) (WP01)
T005 Builder/fixture docstrings record the real limitation (retracting the #5047 claims) (WP01)

### Dependencies

- None (starting package).

### Risks & Mitigations

- The extraction must not change any existing builder's output; run every `tests/terminus/test_repro_*.py` that imports the three builders before and after.
- Real-CLI runs are slow (~70 s each); keep the new fixture test to two consolidations.

**Estimated prompt size**: ~260 lines

---

## Work Package WP02: Red-first real-CLI reproductions of #5046 (Priority: P1)

**Goal**: Pin the defect RED through `spec-kitty consolidate` before any product change, plus same-builder positive controls that must stay green.
**Independent Test**: On the mission base, the FAIL/REFUSE/survivor-undone cases are RED (today they exit 0 with canceled content on the target) and the positive controls are GREEN.
**Prompt**: `tasks/WP02-red-first-real-cli-repros-5046.md`
**Requirement Refs**: FR-003, FR-004, FR-005, FR-006, SC-001, SC-002, SC-003, SC-004, SC-007

### Included Subtasks

T006 FAIL repros (add + modify + delete in one build) under default squash and under `--strategy merge`, asserting the FAIL verdict text, exit ≠ 0, target restored (WP02)
T007 Survivor-undone repros (survivor add → canceled delete; survivor v1 → canceled back to v0) (SC-007) (WP02)
T008 REFUSE repro: committed-then-canceled WP with no `lane_head` stamps (WP02)
T009 [P] Positive controls: superseded (rewrite, delete, self-revert, lane-sync merge inside the canceled session) under both strategies; never-implemented squash twin of the 5018 pin; legacy all-approved lane with no stamps (WP02)
T010 Record the red/green matrix on the mission base in the WP activity log (WP02)

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- A repro that only checks the exit code cannot tell FAIL from REFUSE (post-spec BLOCKER 1): assert the verdict text.
- Keep one consolidation per build; group paths per build to bound runtime (NFR-004).

**Estimated prompt size**: ~280 lines

---

## Work Package WP03: WP commit attribution capture (Priority: P1)

**Goal**: Stamp `policy_metadata["lane_head"]` on every persisted transition of a lane-mapped WP through the one pure seam, with the git probe injected by the two status shells; campsite the `cutover_eligibility` misreading of `policy_metadata`.
**Independent Test**: Emitting transitions for a WP in a lane with an existing branch persists `lane_head` = that branch head; no lanes.json / planning lane / missing branch / git error → no stamp and the transition still persists; the pipeline module stays free of git/subprocess.
**Prompt**: `tasks/WP03-wp-commit-attribution-capture.md`
**Requirement Refs**: FR-001, C-001, C-002, NFR-002

### Included Subtasks

T011 New `status/lane_head.py`: best-effort `probe_lane_head` (lanes.json via placement seam → lane → created branch → rev-parse) (WP03)
T012 `prepare_transition(..., lane_head_probe=None)`: merge the stamp into `policy_metadata` before `build_status_event`; `None` = no stamp (WP03)
T013 Inject the probe at the four call sites (`status/emit.py` single + batch, `coordination/status_transition.py` single + batch) + a pin test that all four pass it (WP03)
T014 [P] Campsite: `status/cutover_eligibility.py` keys runtime-state detection on claim keys, not any `policy_metadata` (WP03)
T015 Unit tests for probe, stamping, injection pin, cutover eligibility; named status gates (WP03)

### Dependencies

- None (parallel with WP01/WP02).

### Risks & Mitigations

- Pipeline purity pin (`tests/status/test_transition_pipeline.py:369-380`) and cold-import boundary: keep git in `lane_head.py`, import function-locally from the shells.
- The probe runs inside the status lock: exactly one rev-parse.

**Estimated prompt size**: ~300 lines

---

## Work Package WP04: Pure per-WP attribution resolver (Priority: P1)

**Goal**: `consolidation/wp_attribution.py`: reconstruct work windows from events, resolve a canceled WP's non-merge commits on the lane spine, and derive its unsuperseded per-path canceled content with pre-state — or a typed unattributable reason.
**Independent Test**: Unit tests over real throwaway git repos + synthetic event lists cover every window rule, stamp-validity rule, contested/review rule, merge/bookkeeping exclusion, supersession, pre-state (R1), and every unattributable reason.
**Prompt**: `tasks/WP04-pure-per-wp-attribution-resolver.md`
**Requirement Refs**: FR-001, FR-002, FR-004, FR-005, NFR-002

### Included Subtasks

T016 Window reconstruction from events (implementation incl. blocked; review windows; open/no-stamp detection) (WP04)
T017 Commit resolution: stamp validity (ancestor-or-equal of lane tip), `(open, close]` first-parent ∩ lane spine, non-merge only (WP04)
T018 Contested/review attribution rules (overlapping implementation windows; review window only when uncontested) (WP04)
T019 Canceled content: single newest→oldest spine walk, bookkeeping filter, newest non-merge toucher, pre-state, net-zero drop (WP04)
T020 Typed outcome + reason vocabulary; fail-closed on `StoreError` / `GitProbeError` (WP04)
T021 Unit tests (git-backed) for T016–T020 (WP04)

### Dependencies

- Depends on WP03 (stamp key constant and format).

### Risks & Mitigations

- Must not reuse the tolerant `_lane_first_parent_spine` (returns `[]` on error → vacuous PASS).
- Iterate events in append order (never wall-clock).

**Estimated prompt size**: ~380 lines

---

## Work Package WP05: Gate wiring — canceled-content axis and mixed-lane refusal (Priority: P1)

**Goal**: In `consolidation/reconciliation.py`, detect mixed lanes via `excluded_canceled_wp_ids`, refuse on unattributable canceled WPs, carry `canceled_content` on the claim, and add a strategy-independent verifier step producing FAIL (`Divergence.canceled_content`) or REFUSE (merged-with-independent-change / probe error); leave `authored_*`/`excluded_*` byte-identical.
**Independent Test**: WP02's RED repros turn GREEN (FAIL/REFUSE verdict text), positive controls stay GREEN, `test_repro_5018` stays GREEN; unit tests cover every verdict-table row of the contract.
**Prompt**: `tasks/WP05-gate-canceled-content-axis-and-refusal.md`
**Requirement Refs**: FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-003, C-003

### Included Subtasks

T022 Claim: mixed-lane detection + entered-implementation check + refusal claim with actionable reason (WP05)
T023 Claim: `canceled_content` field populated from WP04; existing fields untouched (WP05)
T024 Verifier: `_canceled_content_divergence` step for every strategy (FAIL / REFUSE / no finding per the contract table) (WP05)
T025 `Divergence.canceled_content` + `describe()` rendering + recovery wording (WP05)
T026 Correct the `_collect_excluded` docstring; keep `verify()` ≤ complexity 15 (WP05)
T027 Unit tests per verdict-table row + precedence + byte-identical existing claim fields; run WP02 repros green (WP05)

### Dependencies

- Depends on WP02 (red first), WP04, and WP07 (REFUSE must restore the target for WP02's REFUSE repro to go green).

### Risks & Mitigations

- issue 5018-class false FAIL: pinned by WP02 positive controls and `test_repro_5018`.
- Keep the new logic in the verifier method + WP04 module; `build_approved_wp_set` only wires.

**Estimated prompt size**: ~360 lines

---

## Work Package WP06: Production-path proof, residual pins, docs (Priority: P2)

**Goal**: Prove FR-001 through the real workflow (SC-006, half-by-half revert), pin the documented residuals as strict expected failures, add the NFR-001 benchmark, and document the attribution stamp.
**Independent Test**: The production-path twin FAILs/PASSes as specified with no hand-written stamps; each residual test is a strict xfail; the benchmark asserts the ≤ 1 s overhead.
**Prompt**: `tasks/WP06-production-path-proof-residual-pins-docs.md`
**Requirement Refs**: FR-001, FR-009, NFR-001, SC-006, C-007

### Included Subtasks

T028 SC-006 production-path twin: transitions driven through the status shells / CLI with no hand-written stamps; FAIL and superseded PASS (time-boxed) (WP06)
T029 Half-by-half revert proof recorded (revert capture alone → REFUSE; revert gate alone → PASS) (WP06)
T030 [P] Residual strict xfails: hunk-level supersession (FR-009); another approved lane authored the identical state; post-cancel commit; never-claimed WP's commits (WP06)
T031 [P] NFR-001 benchmark (5 WPs / 50 commits mixed lane) (WP06)
T032 Document the `lane_head` stamp and the canceled-content axis in `docs/architecture/status-model.md` (WP06)

### Dependencies

- Depends on WP03 and WP05.

### Risks & Mitigations

- Driving real transitions in a fixture repo may need the mission scaffold the CLI expects: time-box; if blocked, drive the production shells (`emit_status_transition`) directly and record the gap in the tooling-friction tracer.

**Estimated prompt size**: ~300 lines

---

## Work Package WP07: Every REFUSE restores the target (Priority: P1)

**Goal**: FR-010 — apply the existing CAS rollback to every reconciliation REFUSE (today only FAIL rolls back, so a REFUSE exits 1 with the advanced target in place); correct the misleading executor comment. Operator decision `01M3MAB8FTDKKVVTXPREK75AEP`.
**Independent Test**: A red-first test shows a REFUSE leaving the advanced target; after the change the target is at its pre-mutation tip; FAIL/PASS behaviour unchanged.
**Prompt**: `tasks/WP07-refuse-restores-target.md`
**Requirement Refs**: FR-010, FR-005

### Included Subtasks

T033 Red-first test: REFUSE after the advance leaves the target advanced (WP07)
T034 Roll back on REFUSE via the existing CAS helper; correct the comment (WP07)
T035 Tests: REFUSE/FAIL/PASS/CAS-mismatch/unknown-tip; neighbour files (WP07)

### Dependencies

- None (parallel).

### Risks & Mitigations

- Tests asserting a refused target stays advanced: judge each (stale → re-pin with rationale).

**Estimated prompt size**: ~150 lines

---

## Closeout (orchestrator, not a WP)

- File follow-up issues under the parent epic before the PR (C-007): `--dry-run` surfacing of the new verdicts; hunk-level supersession; the `for_review` gate counting a sibling WP's commits; post-cancel commits; commits by a never-claimed WP.
- Update CLAUDE.md's consolidation paragraph and the CHANGELOG; correct `VerifyResult.recovery_guidance()`'s REFUSE sentence if WP05 has not.
- WP07 review nits: `_phase_reconcile_before_teardown` docstring ("mutates NOTHING") and the call-site comment near `executor.py:3321`; rollback helper warning text ("reconciliation failure") + assert it in the CAS test.
- Follow-up issue: the squash-projection refusal (`_assert_squash_projected_content_landed`, reachable after PASS and on the resume short-circuit) exits 1 without rolling back the target.
- WP01 review note: split commit bcd6ae7b at closeout into (a) behaviour-preserving extraction + hygiene, (b) new builder, (c) tests (tidy-first, Standing Order #2).
- WP05 review folds (closeout, reconciliation.py): REFUSE text double period (`consolidate..` — `_mixed_lane_unattributable_refusal` / `_refuse_merged_independent_change` end with "." and `recovery_guidance()` appends ". "); REFUSE guidance says "has been restored" before the best-effort rollback runs — hedge or print after; FAIL guidance's "no refs/worktrees were mutated beyond what already landed" is stale since FAIL rolls back; production-path `assert isinstance(outcome, Attributed)` nit.
- Follow-up issue: under `--strategy merge`, a post-approval bookkeeping-only side-branch merge on a mixed lane false-FAILs via the pre-existing excluded-SHA axis (safe direction; identical on base).
