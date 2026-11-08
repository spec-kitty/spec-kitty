---
description: "Work packages for Mission consolidation-window-provenance-01M6Y84D"
---

# Work Packages: Consolidation window provenance and reconciliation split

**Inputs**: Design documents from `kitty-specs/consolidation-window-provenance-01M6Y84D/`
**Prerequisites**: plan.md (Implementation Concern Map IC-01..IC-17), spec.md (US1-US6, FR-001..FR-023, NFR-001..NFR-010, C-001..C-014), research.md (R-01..R-18), data-model.md, contracts/status-event-wp-window.md, quickstart.md

**Tests**: Required. The spec makes tests the deliverable of Phase 1 (FR-016, FR-017, FR-018, NFR-008) and demands red-first tests through the entry point for every Phase 4 behaviour change (NFR-002, NFR-010).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Phases are strict (plan.md, "Phases are strict"): no work package of a later phase may start before every work package of the earlier phase is approved. The dependency graph encodes that: every Phase 2 work package depends on every Phase 1 work package (C-008: characterization merges before any code moves), Phase 3 is one sequential chain behind the facade, and Phase 4 is one sequential chain because every Phase 4 work package edits the shared golden file `verdict_corpus.json` and the intended-verdict pins.

**Prompt Files**: Each work package references a matching prompt file in `tasks/`. This file is the high-level checklist; the prompts carry the detail.

**Model tiers** (plan.md Model-tier notes): *cheap* work packages are implemented by TokenFactory models (glm-5.3) and reviewed by Claude; *mid* and *top* work packages are implemented by Claude. Each prompt's Review Guidance carries a `Model tier:` line.

**Cross-cutting constraints (every work package)**: C-009 (no rollback or branch-restore caller outside `rollback.py`; `tests/consolidation/test_single_rollback_authority.py` stays green), C-013 (targeted test runs only, never `make test-full`), C-014 (ruff, ruff format and mypy with zero findings, no new suppressions), NFR-004 (complexity <= 15), NFR-005 (net 0 new allowlist entries or suppressions), NFR-009 (changed-line coverage >= 90%).

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

# Phase 1 - Pin and decide (no behaviour change)

## Work Package WP01: Window-model ADR, glossary and closed-world amendment pointer (Priority: P0)

**Goal**: Write the Proposed ADR `2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition` that every later change follows, add the glossary entries, and add the amendment pointer to `2026-09-29-1-closed-world-refuse-on-mixed-lanes`.
**Independent Test**: The ADR exists with valid frontmatter, maps all nine base/window notions (research R-02) to the window model or a named window variant, cites ADRs by full slug, and the docs gates pass.
**Prompt**: `tasks/WP01-window-model-adr-and-glossary.md`
**Requirement Refs**: FR-001, FR-006, C-001, C-010, C-011, C-012

### Included Subtasks

T001 Draft the ADR skeleton, frontmatter, context and decision drivers (WP01)
T002 Write the decision: recording point, `wp_window` key, typed window gap, window opener (FR-021), exemption anchors, two recording tiers (WP01)
T003 Write `ClaimInputs` with its three sources, the durability horizon, the missing-window fallback and the frozen anchor set on resume (WP01)
T004 Write the nine-notion mapping table, named window variants, named residuals, degraded anchors and limits (WP01)
T005 [P] Add glossary entries to `docs/context/orchestration.md` and the amendment pointer to `docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md` (WP01)
T006 Run the docs gates and fix findings (WP01)

### Implementation Notes

- Planning-artifact work package: every owned file is under `docs/`.
- The `2026-10-04-5` amendment pointer and its residual-list sync move to WP21, after the behaviour changes are known (research R-09).

### Parallel Opportunities

- Runs alongside WP02, WP03 and WP04.

### Dependencies

- None (starting package).

### Risks & Mitigations

- ADR prefix collisions (three `2026-09-29-1-*` files): cite by full slug (C-011).
- Do not state the `--dry-run` approved-bound claim either way until WP02's corpus pins it (R-09).

---

## Work Package WP02: Characterization corpus with an in-process runner and window-state axis (Priority: P0)

**Goal**: Pin today's actual verdict (status, refusal code, divergence fields, exit code) for every cell of mode x lane shape x approval-stamp state x window state in a golden file, computed in process so seeded mutations can reach it.
**Independent Test**: `uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py` passes on unchanged code and regenerating the golden file produces a zero diff.
**Prompt**: `tasks/WP02-characterization-corpus.md`
**Requirement Refs**: FR-016, NFR-001, C-008, SC-005

### Included Subtasks

T007 Build the in-process corpus runner for forecast and fresh-run cells (WP02)
T008 Build the resume-cell path: SIGKILL harness after claim capture, then in-process resume (WP02)
T009 Assemble the lane-shape scenario builders from existing fixtures (WP02)
T010 Implement the explicit window-state injector (recorded, not recorded, capture failed, lane branch missing, not on lane) (WP02)
T011 Implement golden serialization, SHA normalization, deterministic ordering and the regeneration switch (WP02)
T012 Generate `verdict_corpus.json`, including the exception and weaker-check cells pinned as passing (WP02)
T013 Pin the `--dry-run` verdict on the post-approval fixture (R-09) and record the finding (WP02)

### Implementation Notes

- Reuse `tests/terminus/post_approval_support.py`, `tests/terminus/approved_content_support.py`, `tests/terminus/rollback_harness.py` and the `tests/consolidation/test_reconciliation.py` fixtures.
- Builders and runner live in `tests/consolidation/characterization_support.py` so WP05, WP06 and Phase 4 reuse them.

### Parallel Opportunities

- Runs alongside WP01, WP03 and WP04.

### Dependencies

- None (starting package).

### Risks & Mitigations

- A subprocess runner would make every seeded mutation vacuous: compute verdicts in process (R-18).
- Golden instability: normalize SHAs to stable labels and sort keys.

---

## Work Package WP03: Refusal-precedence matrix (Priority: P0)

**Goal**: A table-driven pin of the claim-time refusal text and order for every pair of `build_approved_wp_set` refusals that can occur together, with a swapped-order control and an explicit list of pairs that cannot co-occur.
**Independent Test**: `uv run --frozen pytest -q tests/consolidation/test_refusal_precedence_matrix.py` passes; the swapped-order control proves the pin can fail.
**Prompt**: `tasks/WP03-refusal-precedence-matrix.md`
**Requirement Refs**: FR-017, C-006

### Included Subtasks

T014 Inventory the claim-time refusals in `build_approved_wp_set` order and their short-circuit sites (WP03)
T015 Build pairwise fixtures that make two refusals co-occur (WP03)
T016 Write the matrix test: assert both markers present, then their order and text (WP03)
T017 Add the swapped-order control and the "cannot co-occur" table with each short-circuit site (WP03)

### Implementation Notes

- Today's order: dependency refs -> unresolvable branches -> canceled dependency -> mixed lane -> bound -> evidence -> presence -> authored -> excluded, with `_compound_refusal` appending the bound after "This Mission also has:".

### Parallel Opportunities

- Runs alongside WP01, WP02 and WP04.

### Dependencies

- None (starting package).

### Risks & Mitigations

- A fixture yielding one refusal passes vacuously: assert both markers before order.

---

## Work Package WP04: Import-surface pin, RECONCILIATION_FAMILY helper and patch-lookup guard (Priority: P0)

**Goal**: Pin every name importable from `specify_cli.consolidation.reconciliation` (with object identity), add the `RECONCILIATION_FAMILY` patch helper, and add a guard that fails when a test string-patches a reconciliation name that the patched module does not look up itself.
**Independent Test**: `uv run --frozen pytest -q tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py` passes; both controls prove the pins can fail.
**Prompt**: `tasks/WP04-surface-pin-and-family-guard.md`
**Requirement Refs**: FR-018, FR-020, C-005

### Included Subtasks

T018 Write the name-list generator (AST scan of `src/` and `tests/` imports plus string-literal dotted patch targets) (WP04)
T019 Generate and check in `tests/consolidation/reconciliation_surface.json` (WP04)
T020 Write the surface-pin test (name set + object identity) and the removed-name control (WP04)
T021 Write `tests/consolidation/reconciliation_family.py` modelled on `executor_family.py` (WP04)
T022 Write the patch-lookup guard covering string, f-string-constant, `mock.patch` and module-object `setattr` forms; it also fails when the patched name is looked up in any other reconciliation module (narrowed interception), counting a facade forward reference as a facade lookup (WP04)
T023 Add the stale-patch and narrowed-patch controls proving the guard fails (WP04)

### Implementation Notes

- Before the split the family is `(reconciliation,)` and the guard passes.

### Parallel Opportunities

- Runs alongside WP01, WP02 and WP03.

### Dependencies

- None (starting package).

### Risks & Mitigations

- A hand-written name list drifts: generate it from code.

---

## Work Package WP05: Intended-verdict strict-xfail pins (Priority: P0)

**Goal**: Pin each intended verdict that Phase 4 will deliver, and the parallel-claims named residual, as separate strict `xfail(raises=AssertionError)` tests, so each Phase 4 fix flips exactly one named test.
**Independent Test**: `uv run --frozen pytest -q tests/consolidation/test_reconciliation_intended_verdicts.py` reports only `xfailed`.
**Prompt**: `tasks/WP05-intended-verdict-pins.md`
**Requirement Refs**: FR-016, NFR-002

### Included Subtasks

T024 Pin the commit-between-two-approvals intended refusal, incl. the gap-then-recorded mixed lane (NFR-002 a, b) (WP05)
T025 Pin the rewound work package intended window (NFR-002 c) (WP05)
T026 Pin the #5048(b) read-error intended refusal (NFR-002 d) (WP05)
T027 Pin the three resume frozen-anchor intended verdicts (NFR-002 e, f, g) (WP05)
T028 Pin the forecast's excluded canceled set and resolved coordination base (NFR-002 h) (WP05)
T029 Pin the parallel-claims named residual (WW-6) (WP05)

### Dependencies

- Depends on WP02 (runner, builders, injector) and WP04 (`RECONCILIATION_FAMILY` for the probe patch).

### Risks & Mitigations

- An xfail that fails for the wrong reason: `raises=AssertionError`, strict, and a precondition assertion before the verdict assertion.

---

## Work Package WP06: Seeded-mutation harness and mutation table (Priority: P0)

**Goal**: For every check Phase 3 will move, one deterministic seeded mutation applied through `RECONCILIATION_FAMILY` in the corpus process turns at least one named corpus cell red; a checked-in table names check -> function -> mutation -> expected red cell.
**Independent Test**: `uv run --frozen pytest -q tests/consolidation/test_reconciliation_seeded_mutations.py` passes (each mutation is asserted to turn its cell red; the unmutated control is green).
**Prompt**: `tasks/WP06-seeded-mutation-harness.md`
**Requirement Refs**: NFR-008, SC-005, C-008

### Included Subtasks

T030 Define the mutation table (check -> mutated function -> mutation -> expected red cell(s)) (WP06)
T031 Implement the mutation application through `RECONCILIATION_FAMILY` (WP06)
T032 Implement the per-mutation test asserting its named cells go red, plus the unmutated green control (WP06)
T033 Verify every check scheduled to move in Phase 3 has a row (WP06)

### Dependencies

- Depends on WP02 and WP04.

---

# Phase 2 - Record and unify inputs (no verdict change)

## Work Package WP07: LaneHeadReading and `wp_window` capture on opening transitions (Priority: P1) MVP

**Goal**: Record the window-open SHA, or a typed window gap (`lane_branch_missing`, `capture_failed`), under `policy_metadata.wp_window` on every non-migration move of a lane-mapped work package into `claimed` / `in_progress`, reusing the one lane-head reading; the move is never refused.
**Independent Test**: `uv run --frozen pytest -q tests/status/test_wp_window_capture.py tests/status/test_lane_head.py tests/status/test_transition_pipeline.py` passes; the corpus is unchanged.
**Prompt**: `tasks/WP07-wp-window-capture.md`
**Requirement Refs**: FR-002, FR-003, NFR-006, C-002, C-003

### Included Subtasks

T034 Introduce `LaneHeadReading` and `CaptureCause` in `status/lane_head.py`; keep `probe_lane_head` a thin sha adapter (WP07)
T035 Add the reading-returning probe and inject it from both composition shells (WP07)
T036 Write `wp_window` in `_stamped_policy_metadata` per data-model section 2, keeping `lane_head` byte-identical (WP07)
T037 Export `WP_WINDOW_KEY` from `status/lane_head.py`, re-export from `status/__init__.py`, and replace WP02's local stand-in constant in `characterization_support.py` with the import (WP07)
T038 Write `tests/status/test_wp_window_capture.py` (all rows of the writer table, incl. `move-task --to claimed` before `implement`) (WP07)
T039 Keep the status boundary and cold-import gates green (WP07)
T040 Add the changelog fragment (no version bump) (WP07)

### Dependencies

- Depends on WP01, WP02, WP03, WP04, WP05, WP06 (Phase 1 complete).

### Risks & Mitigations

- Changing `lane_head` for an existing event shape: WP-3 additivity, pinned by test.

---

## Work Package WP08: Window opener reader, gap typing and dossier SHA classification (Priority: P1)

**Goal**: One reader `window_open_of` in `wp_attribution` implementing the FR-021 window opener and the four gap reasons, sharing one selector `window_opener_events(..., cycle)` with `approval_window_open_stamp`; classify the new SHA key `BRANCH_RELATIVE`.
**Independent Test**: `uv run --frozen pytest -q tests/consolidation/test_window_opener.py tests/architectural/test_dossier_sha_provenance.py` passes; the corpus is unchanged.
**Prompt**: `tasks/WP08-window-opener-reader.md`
**Requirement Refs**: FR-004, FR-005, FR-021, FR-022

### Included Subtasks

T041 Add `WindowOpen`, `WindowGap`, `WindowGapReason` value types (WP08)
T042 Implement `window_opener_events(events, wp_id, *, cycle)` (cycle start, candidates, skip, bind) (WP08)
T043 Implement `window_open_of(events, wp_id, *, on_lane, is_ancestor)` with contract-violation handling (WP08)
T044 Re-express `approval_window_open_stamp` through the selector with `cycle=False`, behaviour unchanged (WP08)
T045 Add `("status.events.jsonl", "policy_metadata.wp_window.open_sha")` as `BRANCH_RELATIVE` in `DOSSIER_SHA_FIELDS` (WP08)
T046 Write unit tests: rewind, review rejection, leading branch-missing skip, skewed clock, unrelated SHAs, unresolvable SHA, malformed key (WP08)

### Dependencies

- Depends on WP07.

---

## Work Package WP09: ClaimInputs and its one constructor (Priority: P1)

**Goal**: One frozen `ClaimInputs` value with three sources (`LIVE`, `LIVE_THEN_SAVED`, `SAVED`) built by one constructor and adopted by `forecast.py`, `phase_claim.py` and `phase_gate.py`, keeping every per-mode quirk so zero verdicts change; a parity test pins equal fields and each known divergence as its own strict `xfail`.
**Independent Test**: `uv run --frozen pytest -q tests/consolidation/test_claim_inputs_parity.py tests/consolidation/test_reconciliation_characterization.py` passes with the golden file unchanged.
**Prompt**: `tasks/WP09-claim-inputs.md`
**Requirement Refs**: FR-012, FR-013, C-004

### Included Subtasks

T047 Define `ClaimInputSource` and the frozen `ClaimInputs` dataclass (WP09)
T048 Implement the constructor with one small resolver per source (WP09)
T049 Implement the thin `build_claim(..., inputs)` adapter over `build_approved_wp_set` (WP09)
T050 Adopt `ClaimInputs` in `forecast.py`, preserving the empty excluded set and live coordination base (WP09)
T051 Adopt `ClaimInputs` in `phase_claim.py`, keeping `_enforce_resume_anchor_integrity` / `lane_tip_cas_ok` first (WP09)
T052 Adopt `ClaimInputs` in `phase_gate.py`, preserving the gate rebuild's live `mission_branch` (WP09)
T053 Write `tests/consolidation/test_claim_inputs_parity.py` with one strict `xfail` per known divergence (WP09)

### Dependencies

- Depends on WP01, WP02, WP03, WP04, WP05, WP06 (Phase 1 complete).

---

# Phase 3 - Behaviour-preserving split (one sequential chain)

## Work Package WP10: Extract the shared kernel and the claim types (Priority: P2)

**Goal**: Move the shared kernel symbols into `reconciliation_kernel.py` and `ApprovedWpCommitSet` with its content dataclasses into `reconciliation_claim_types.py`, re-exported by the facade; zero verdict change.
**Independent Test**: corpus, precedence matrix, surface pin, family guard and seeded mutations all pass unchanged.
**Prompt**: `tasks/WP10-extract-kernel-and-claim-types.md`
**Requirement Refs**: FR-019, C-005, C-006, NFR-001

### Included Subtasks

T054 Move the kernel symbols to `reconciliation_kernel.py` (WP10)
T055 Move `ApprovedWpCommitSet` and the content dataclasses to `reconciliation_claim_types.py`, field order unchanged (WP10)
T056 Add facade re-exports and extend `RECONCILIATION_FAMILY` (WP10)
T057 Add the fresh-interpreter import smoke test for new modules (WP10)
T058 Check `CHURN_SURFACE_MODULES` for the `_is_bookkeeping` home and run the oracle gates (WP10)

### Dependencies

- Depends on WP07, WP08, WP09 (Phase 2 complete).

---

## Work Package WP11: Move the rendering, closed-world and approved-bound checks (Priority: P2)

**Goal**: Move the refusal/clause text helpers, the closed-world check (with external dependency refs) and the approved bound (with write-branch and the lane-tip re-check) into their own modules behind the facade.
**Independent Test**: oracle gates unchanged; the seeded mutations for the closed world and the bound still turn their cells red.
**Prompt**: `tasks/WP11-move-rendering-closed-world-bound.md`
**Requirement Refs**: FR-019, FR-020, NFR-001

### Included Subtasks

T059 Move rendering helpers to `reconciliation_rendering.py` (WP11)
T060 Move the closed-world check and external dependency refs to `reconciliation_closed_world.py` (WP11)
T061 Move the approved bound, write-branch and lane-tip re-check to `reconciliation_bound.py` (WP11)
T062 Update facade re-exports, family tuple and any flagged patch targets (WP11)
T063 Run the oracle gates and record the module sizes (WP11)

### Dependencies

- Depends on WP10.

---

## Work Package WP12: Move the verifier (Priority: P2)

**Goal**: Move `VerifyStatus`, `Divergence` (whole), `VerifyResult`, `MergeOutcomeVerifier`, their helpers and `claim_integrity_refusal` (it and `MergeOutcomeVerifier` call each other, so they share a module) into `reconciliation_verifier.py`.
**Independent Test**: oracle gates unchanged; the verifier mutations still turn their cells red.
**Prompt**: `tasks/WP12-move-verifier.md`
**Requirement Refs**: FR-019, C-006

### Included Subtasks

T064 Move the verifier symbols and `claim_integrity_refusal` to `reconciliation_verifier.py`; one forward reference (`unmet_approved_content`, moves in WP15) (WP12)
T065 Update facade re-exports and the family tuple (WP12)
T066 Retarget the `merge_tree_write_tree_available` patch in `test_reconciliation.py` and the `path_state_at` patch in `test_canceled_dependency_attribution.py` (WP12)
T067 Run the oracle gates and record the module size (WP12)

### Dependencies

- Depends on WP11.

---

## Work Package WP13: Move the canceled pair (mixed lane + canceled dependency) (Priority: P2)

**Goal**: Move the mixed-lane resolver and the canceled-dependency resolution as one slice into `reconciliation_canceled.py`, retargeting their patches.
**Independent Test**: oracle gates unchanged; the canceled-pair mutations still turn their cells red.
**Prompt**: `tasks/WP13-move-canceled-pair.md`
**Requirement Refs**: FR-019, FR-020, NFR-008

### Included Subtasks

T068 Move the mixed-lane and canceled-dependency symbols to `reconciliation_canceled.py` (WP13)
T069 Update facade re-exports and the family tuple (WP13)
T070 Retarget the canceled-slice patches in `test_reconciliation.py` and `test_canceled_dependency_attribution.py` (`path_state_at` was retargeted by WP12) (WP13)
T071 Run the oracle gates and record the module size (WP13)

### Dependencies

- Depends on WP12.

---

## Work Package WP14: Move the claim orchestration (Priority: P2)

**Goal**: Move `build_approved_wp_set` (refusal order whole), the compound-refusal helper and the terminus vocabulary into `reconciliation_claim.py` (`claim_integrity_refusal` already moved with the verifier in WP12); update the reducer-lock census owner path and the dead-symbol allowlist keys with net 0.
**Independent Test**: oracle gates unchanged; `tests/ci/test_reducer_lock_census.py` and `tests/architectural/test_dead_symbol_allowlist_contract.py` pass.
**Prompt**: `tasks/WP14-move-claim-orchestration.md`
**Requirement Refs**: FR-019, C-006, NFR-005

### Included Subtasks

T072 Move the claim orchestration symbols (not `claim_integrity_refusal`, which WP12 moved to the verifier) to `reconciliation_claim.py` (WP14)
T073 Update facade re-exports and the family tuple (WP14)
T074 Update the census owner path in `tests/ci/test_reducer_lock_census.py` (WP14)
T075 Re-key or keep in place `TERMINUS_ENTRY_POINTS` / `UnroutedTerminusPathError` in `dead_symbol_allowlist.yaml` (net 0) (WP14)
T076 Run the oracle gates and the literal-pin gates (WP14)

### Dependencies

- Depends on WP13.

---

## Work Package WP15: Move authorship + presence and reduce the facade (Priority: P2)

**Goal**: Move the authored walk and the presence check as one slice (one spine walk) into `reconciliation_authorship.py`, reduce `reconciliation.py` to docstring plus re-exports, verify module sizes, and re-run every seeded mutation against the moved checks.
**Independent Test**: oracle gates byte-identical to Phase 1; facade has zero `def`/`class`; every module <= 1,200 lines.
**Prompt**: `tasks/WP15-move-authorship-presence-and-facade.md`
**Requirement Refs**: FR-019, FR-020, C-007, NFR-003, NFR-008, SC-006

### Included Subtasks

T077 Move the authorship and presence symbols to `reconciliation_authorship.py` (WP15)
T078 Move any remaining definitions out of the facade; facade = docstring + re-exports + `__all__` (WP15)
T079 Retarget the `_final_authored_walk` and `commits_in_range` patches (WP15)
T080 Re-run and, where needed, retarget the seeded mutations; assert every moved check still has a red cell (WP15)
T081 Verify NFR-003 sizes and the facade has no logic (WP15)
T082 Run the full Phase 3 verification set (WP15)

### Dependencies

- Depends on WP14.

---

# Phase 4 - Behaviour changes, red-first (one sequential chain)

## Work Package WP16: A history-read error is never a deletion (#5048(b)) (Priority: P1)

**Goal**: In `_final_authored_walk`, use `git_probes.path_state_at`: `None` is a genuine deletion, a `GitProbeError` refuses the claim naming the path and error; red-first through in-process `consolidate`.
**Independent Test**: the red-first test fails on the parent commit and passes after the fix; the positive control (genuine deletion) passes on both.
**Prompt**: `tasks/WP16-history-read-error-refuses.md`
**Requirement Refs**: FR-014, NFR-002, NFR-010, SC-004

### Included Subtasks

T083 Write the failing test through in-process `consolidate` with the probe patched at its lookup home; commit it red (WP16)
T084 Add the genuine-deletion positive control (WP16)
T085 Implement the fix with `path_state_at` and the existing unreadable-history refusal wording (WP16)
T086 Flip the NFR-002 (d) intended-verdict pin and regenerate only its golden cells (WP16)

### Dependencies

- Depends on WP15 (Phase 3 complete).

---

## Work Package WP17: Forecast uses the fresh run's claim inputs (Priority: P1)

**Goal**: The `LIVE` source derives the excluded canceled work packages like the fresh run, resolves the coordination base to the SHA the fresh run resolves, and reads the same status directory, so forecast and fresh-run claim inputs are equal on an unmutated state.
**Independent Test**: every parity `xfail` from WP09 flips to pass in its own fix commit; any forecast verdict change is red-first through `consolidate --dry-run --json`.
**Prompt**: `tasks/WP17-forecast-claim-input-parity.md`
**Requirement Refs**: FR-012, FR-013, NFR-002, NFR-010, SC-003

### Included Subtasks

T087 Write the red-first tests through `consolidate --dry-run --json` for the excluded canceled set (WP17)
T088 Align the `LIVE` excluded canceled set with the fresh-run derivation (WP17)
T089 Resolve the forecast coordination base to a SHA and read the fresh run's status directory (WP17)
T090 Flip the parity `xfail`s and the NFR-002 (h) pin; regenerate only the named golden cells (WP17)

### Dependencies

- Depends on WP16.

---

## Work Package WP18: Resume reads one frozen anchor set (Priority: P1)

**Goal**: On `--resume`, one frozen claim-time anchor set from `ClaimInputs` (`SAVED`) feeds all four `_closed_world_anchors` consumers (mixed-lane resolver, approved bound, fully-canceled lane, approved-reviewed attestation); red-first through `consolidate --resume` on the SIGKILL harness.
**Independent Test**: three red-first tests (NFR-002 e, f, g) fail on the parent commit and pass after; the fresh run's verdict is unchanged.
**Prompt**: `tasks/WP18-resume-frozen-anchors.md`
**Requirement Refs**: FR-015, NFR-002, NFR-010, SC-004

### Included Subtasks

T091 Build the SIGKILL resume fixture: kill after anchor `save_state`, before `_phase_merge_lanes`; assert `state.json` holds the frozen dependency tip (WP18)
T092 Write and commit red the closed-world test (NFR-002 e) (WP18)
T093 Write and commit red the approved-bound test (NFR-002 f) (WP18)
T094 Write and commit red the fully-canceled-lane test, or the unreachable-flip record (NFR-002 g) (WP18)
T095 Thread the frozen anchor set from `ClaimInputs` into all four consumers (WP18)
T096 Flip the NFR-002 (e, f, g) pins and regenerate only their golden cells (WP18)

### Dependencies

- Depends on WP17.

---

## Work Package WP19: Lane missions adopt the window model (Priority: P1)

**Goal**: On a code lane with at least one `WindowOpen`, each approved work package covers only its window, a gap work package falls back to `(claim base, approval stamp]`, the exemption anchors are the closed-world anchors plus other lanes' approval stamps (never the lane's own), and a commit outside every window and anchor is refused with `LANE_MOVED_AFTER_APPROVAL` naming the commit and the work package approved before it; an all-gap lane runs today's check unchanged.
**Independent Test**: red-first tests through `consolidate` and `consolidate --dry-run` for US2-1, US2-5, US2-7 and the gap-then-recorded mixed lane fail before and pass after; US2-2/3/4/6 and US3-1/2/4/5 pass before and after.
**Prompt**: `tasks/WP19-lane-window-model.md`
**Requirement Refs**: FR-007, FR-008, FR-009, FR-021, FR-022, FR-023, NFR-002, NFR-007, NFR-010, SC-001, C-010

### Included Subtasks

T097 Write the red-first tests through `consolidate` / `--dry-run` (US2-1, US2-5, US2-7, gap-then-recorded) and commit them red (WP19)
T098 Write the over-refusal guards that must stay green (US2-2/3/4/6, US3-1/2/4/5, attested approval) (WP19)
T099 Generalise the `write_branch_bound` window machinery to lane windows with degraded windows (WP19)
T100 Implement the lane leg of `_approved_bound_verdict`: windows, exemption anchors, all-gap fallback (WP19)
T101 Pass the one resolved lane tip to the classifier on every path incl. `approved_bound_refusal` (WP19)
T102 Add the `window_gaps` field to the claim and populate it (WP19)
T103 Add the NFR-007 query-count test; flip the NFR-002 (a, b, c-lanes) pins; regenerate only the named cells; write the FR-007 changelog fragment (WP19)

### Dependencies

- Depends on WP18.

---

## Work Package WP20: Gap report output and `single_branch` recorded windows (Priority: P1)

**Goal**: The fresh run, resume and forecast list every fallback work package with its gap reason (human block and `window_gaps` in the dry-run JSON); `single_branch` reads the recorded window-open SHA when present and reports its absence.
**Independent Test**: tests through `consolidate`, `--resume` and `--dry-run --json` show the gap report; `tests/integration/test_single_branch_approval_windows.py` stays green.
**Prompt**: `tasks/WP20-gap-report-and-single-branch.md`
**Requirement Refs**: FR-010, FR-011, NFR-002, NFR-010, SC-002

### Included Subtasks

T104 Implement the gap report renderer (human block and JSON entries) (WP20)
T105 Print the gap report on the fresh run and the resume (WP20)
T106 Add `window_gaps` to the dry-run JSON payload and human forecast (WP20)
T107 Make `single_branch` approval windows read the recorded window-open SHA when present; flip the NFR-002 (c) `single_branch` pin (WP20)
T108 Tests through the entry points, plus the gap-report changelog fragment (WP20)

### Dependencies

- Depends on WP19.

---

## Work Package WP21: Closeout: docs sync, ADR residuals and verification sweep (Priority: P2)

**Goal**: Bring `CLAUDE.md`, the `2026-10-04-5` ADR (amendment pointer and residual list) and the Mission ADR in line with what shipped, draft the spec-kitty-events#229 follow-up comment, and run the Mission-wide verification sweep (sizes, complexity, coverage, gates).
**Independent Test**: docs gates pass; the closeout checklist in the prompt is complete with recorded command output.
**Prompt**: `tasks/WP21-closeout-docs-and-verification.md`
**Requirement Refs**: FR-001, FR-006, NFR-004, NFR-005, NFR-009, C-009, C-011, C-012, C-013, C-014

### Included Subtasks

T109 Update `CLAUDE.md` consolidation sections (residual list, `--dry-run` sentence per R-09, window provenance paragraph) and write the WP16 / WP18 changelog fragments (WP21)
T110 Add the amendment pointer and residual sync to `docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md` (WP21)
T111 Sync the Mission ADR with what shipped (sanctioned out-of-map edit) (WP21)
T112 Draft the spec-kitty-events#229 follow-up comment text for operator posting (WP21)
T113 Run the Mission-wide verification sweep, the tracer assessment and the issue-matrix evidence collection, and record the results (WP21)

### Implementation Notes

- `code_change` execution mode although no code changes: the T113 sweep needs the integrated code, so this work package runs in a lane that builds on the code lane rather than in the planning lane.

### Dependencies

- Depends on WP20.

---

## Dependency & Execution Summary

- **Phase 1** (parallel): WP01, WP02, WP03, WP04 start immediately; WP05 and WP06 follow WP02 + WP04.
- **Phase 2**: WP07 and WP09 start once all of WP01..WP06 are approved (in parallel); WP08 follows WP07.
- **Phase 3** (sequential, behind the facade): WP10 -> WP11 -> WP12 -> WP13 -> WP14 -> WP15. WP10 depends on WP07, WP08, WP09.
- **Phase 4** (sequential, red-first): WP16 -> WP17 -> WP18 -> WP19 -> WP20 -> WP21.
- **Routing hint**: WP02 (in-process runner) and WP18 (SIGKILL resume fixtures) decide which state a resume really reaches; route them to the same implementer or review them together.
- **MVP scope**: Phase 1 + WP07/WP08 (windows recorded and readable) is the smallest shippable slice; FR-007 (WP19) is the soundness payoff.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01, WP21 |
| FR-002, FR-003 | WP07 |
| FR-004, FR-005 | WP08 |
| FR-006 | WP01, WP21 |
| FR-007, FR-008, FR-009 | WP19 |
| FR-010, FR-011 | WP20 |
| FR-012, FR-013 | WP09, WP17 |
| FR-014 | WP16 |
| FR-015 | WP18 |
| FR-016 | WP02, WP05 |
| FR-017 | WP03 |
| FR-018 | WP04 |
| FR-019 | WP10, WP11, WP12, WP13, WP14, WP15 |
| FR-020 | WP04, WP11, WP13, WP15 |
| FR-021 | WP08, WP19 |
| FR-022 | WP08, WP19 |
| FR-023 | WP19 |
| NFR-001 | WP02, WP10, WP11 |
| NFR-002 | WP05, WP16, WP17, WP18, WP19, WP20 |
| NFR-003 | WP15 |
| NFR-004, NFR-005, NFR-009 | WP14, WP21 (and every WP's review) |
| NFR-006 | WP07 |
| NFR-007 | WP19 |
| NFR-008 | WP06, WP13, WP15 |
| NFR-010 | WP16, WP17, WP18, WP19, WP20 |
| SC-001 | WP19 |
| SC-002 | WP20 |
| SC-003 | WP17 |
| SC-004 | WP16, WP18 |
| SC-005 | WP02, WP06 |
| SC-006 | WP15 |
| C-001, C-010, C-011, C-012 | WP01, WP19, WP21 |
| C-002, C-003 | WP07 |
| C-004 | WP09 |
| C-005 | WP04, WP10 |
| C-006 | WP03, WP10, WP12, WP14 |
| C-007 | WP15 |
| C-008 | WP02, WP06 |
| C-009, C-013, C-014 | WP21 (and every WP's review) |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | ADR skeleton and context | WP01 | P0 | No |
| T002 | ADR decision: recording, key, gap, opener, anchors | WP01 | P0 | No |
| T003 | ADR: ClaimInputs, horizon, fallback, frozen anchors | WP01 | P0 | No |
| T004 | ADR: nine-notion table, variants, residuals | WP01 | P0 | No |
| T005 | Glossary + closed-world amendment pointer | WP01 | P0 | Yes |
| T006 | Docs gates | WP01 | P0 | No |
| T007 | In-process runner (forecast, fresh) | WP02 | P0 | No |
| T008 | Resume cells via SIGKILL | WP02 | P0 | No |
| T009 | Lane-shape builders | WP02 | P0 | Yes |
| T010 | Window-state injector | WP02 | P0 | Yes |
| T011 | Golden serialization + regen switch | WP02 | P0 | No |
| T012 | Generate verdict_corpus.json | WP02 | P0 | No |
| T013 | Pin --dry-run post-approval verdict (R-09) | WP02 | P0 | No |
| T014 | Refusal inventory | WP03 | P0 | No |
| T015 | Pairwise fixtures | WP03 | P0 | No |
| T016 | Matrix test | WP03 | P0 | No |
| T017 | Swapped-order control + cannot-co-occur table | WP03 | P0 | No |
| T018 | Surface name generator | WP04 | P0 | No |
| T019 | reconciliation_surface.json | WP04 | P0 | No |
| T020 | Surface pin + removed-name control | WP04 | P0 | No |
| T021 | reconciliation_family.py | WP04 | P0 | Yes |
| T022 | Patch-lookup guard | WP04 | P0 | No |
| T023 | Stale-patch control | WP04 | P0 | No |
| T024 | Pin commit between two approvals | WP05 | P0 | Yes |
| T025 | Pin rewound work package | WP05 | P0 | Yes |
| T026 | Pin #5048(b) | WP05 | P0 | Yes |
| T027 | Pin resume frozen anchors (e, f, g) | WP05 | P0 | Yes |
| T028 | Pin forecast inputs (h) | WP05 | P0 | Yes |
| T029 | Pin parallel-claims residual | WP05 | P0 | Yes |
| T030 | Mutation table | WP06 | P0 | No |
| T031 | Mutation application via family | WP06 | P0 | No |
| T032 | Per-mutation red test + green control | WP06 | P0 | No |
| T033 | Coverage of every moved check | WP06 | P0 | No |
| T034 | LaneHeadReading + CaptureCause | WP07 | P1 | No |
| T035 | Reading probe injected by both shells | WP07 | P1 | No |
| T036 | Write wp_window in _stamped_policy_metadata | WP07 | P1 | No |
| T037 | WP_WINDOW_KEY export + re-export | WP07 | P1 | No |
| T038 | test_wp_window_capture.py | WP07 | P1 | No |
| T039 | Status boundary + cold-import gates | WP07 | P1 | No |
| T040 | Changelog fragment | WP07 | P1 | Yes |
| T041 | WindowOpen / WindowGap types | WP08 | P1 | No |
| T042 | window_opener_events selector | WP08 | P1 | No |
| T043 | window_open_of reader | WP08 | P1 | No |
| T044 | approval_window_open_stamp via selector | WP08 | P1 | No |
| T045 | DOSSIER_SHA_FIELDS row | WP08 | P1 | Yes |
| T046 | Reader unit tests | WP08 | P1 | No |
| T047 | ClaimInputSource + ClaimInputs | WP09 | P1 | No |
| T048 | Constructor with per-source resolvers | WP09 | P1 | No |
| T049 | build_claim adapter | WP09 | P1 | No |
| T050 | Adopt in forecast.py | WP09 | P1 | No |
| T051 | Adopt in phase_claim.py | WP09 | P1 | No |
| T052 | Adopt in phase_gate.py | WP09 | P1 | No |
| T053 | Parity test + strict xfails | WP09 | P1 | No |
| T054 | Move kernel | WP10 | P2 | No |
| T055 | Move claim types | WP10 | P2 | No |
| T056 | Facade re-exports + family | WP10 | P2 | No |
| T057 | Import smoke test | WP10 | P2 | No |
| T058 | CHURN_SURFACE_MODULES + oracle gates | WP10 | P2 | No |
| T059 | Move rendering | WP11 | P2 | No |
| T060 | Move closed world | WP11 | P2 | No |
| T061 | Move approved bound | WP11 | P2 | No |
| T062 | Facade, family, patch targets | WP11 | P2 | No |
| T063 | Oracle gates + sizes | WP11 | P2 | No |
| T064 | Move verifier + claim_integrity_refusal | WP12 | P2 | No |
| T065 | Facade + family | WP12 | P2 | No |
| T066 | Retarget merge_tree_write_tree_available + path_state_at | WP12 | P2 | No |
| T067 | Oracle gates + size | WP12 | P2 | No |
| T068 | Move canceled pair | WP13 | P2 | No |
| T069 | Facade + family | WP13 | P2 | No |
| T070 | Retarget canceled patches | WP13 | P2 | No |
| T071 | Oracle gates + size | WP13 | P2 | No |
| T072 | Move claim orchestration | WP14 | P2 | No |
| T073 | Facade + family | WP14 | P2 | No |
| T074 | Census owner path | WP14 | P2 | No |
| T075 | Allowlist re-key (net 0) | WP14 | P2 | No |
| T076 | Oracle + literal-pin gates | WP14 | P2 | No |
| T077 | Move authorship + presence | WP15 | P2 | No |
| T078 | Facade reduced to re-exports | WP15 | P2 | No |
| T079 | Retarget authorship patches | WP15 | P2 | No |
| T080 | Re-run seeded mutations | WP15 | P2 | No |
| T081 | NFR-003 sizes | WP15 | P2 | No |
| T082 | Phase 3 verification set | WP15 | P2 | No |
| T083 | Red test #5048(b) | WP16 | P1 | No |
| T084 | Genuine-deletion control | WP16 | P1 | No |
| T085 | path_state_at fix | WP16 | P1 | No |
| T086 | Flip pin (d) | WP16 | P1 | No |
| T087 | Red tests forecast excluded set | WP17 | P1 | No |
| T088 | Align LIVE excluded set | WP17 | P1 | No |
| T089 | Resolve forecast coord base + status dir | WP17 | P1 | No |
| T090 | Flip parity xfails + pin (h) | WP17 | P1 | No |
| T091 | SIGKILL resume fixture | WP18 | P1 | No |
| T092 | Red test (e) closed world | WP18 | P1 | No |
| T093 | Red test (f) approved bound | WP18 | P1 | No |
| T094 | Red test (g) fully-canceled lane | WP18 | P1 | No |
| T095 | Thread frozen anchors to four consumers | WP18 | P1 | No |
| T096 | Flip pins (e, f, g) | WP18 | P1 | No |
| T097 | Red tests lane windows | WP19 | P1 | No |
| T098 | Over-refusal guards | WP19 | P1 | No |
| T099 | Generalise window machinery | WP19 | P1 | No |
| T100 | Lane leg of the bound | WP19 | P1 | No |
| T101 | One lane tip on every path | WP19 | P1 | No |
| T102 | window_gaps on the claim | WP19 | P1 | No |
| T103 | NFR-007 count + flip pins (a, b, c) | WP19 | P1 | No |
| T104 | Gap report renderer | WP20 | P1 | No |
| T105 | Gap report on fresh run + resume | WP20 | P1 | No |
| T106 | window_gaps in dry-run JSON | WP20 | P1 | No |
| T107 | single_branch reads recorded window | WP20 | P1 | No |
| T108 | Entry-point tests + changelog | WP20 | P1 | No |
| T109 | CLAUDE.md sync | WP21 | P2 | No |
| T110 | 2026-10-04-5 pointer + residuals | WP21 | P2 | Yes |
| T111 | Mission ADR sync | WP21 | P2 | Yes |
| T112 | #229 follow-up draft | WP21 | P2 | Yes |
| T113 | Verification sweep | WP21 | P2 | No |
