---
description: "Work packages for the approved-lane conflict resolution route Mission"
---

# Work Packages: Approved-lane conflict resolution route

**Inputs**: design documents in `kitty-specs/approved-lane-resolution-route-01M7WW0Z/`:
- spec.md
- plan.md
- research.md (R-01 to R-10)
- data-model.md
- contracts/
- quickstart.md
- squads/

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md.

**Tests**: required. The spec mandates red-first tests for every behavioural fix (NFR-004, Standing Order 4).

**Organization**: subtasks (`Txxx`) roll up into work packages (`WPxx`). Each WP prompt is `tasks/WPxx-<slug>.md`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can run in parallel.
- Subtasks are reference rows. Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Ownership map (no overlap)

| WP | owned_files (summary) |
|----|------------------------|
| WP01 | `src/specify_cli/consolidation/git_probes.py`, `src/specify_cli/git/merge_tree_probe.py` (per-run git-version cache, NFR-001), `src/specify_cli/consolidation/merge_attribute_guard.py` (new), `tests/consolidation/test_merge_attribute_guard.py` (new) |
| WP02 | `src/specify_cli/lanes/auto_rebase.py`, `src/specify_cli/lanes/auto_rebase_record.py` (new), `src/specify_cli/consolidation/lane_cleanup.py`, `tests/lanes/test_auto_rebase_record.py` (new) |
| WP03 | `src/specify_cli/consolidation/rollback.py`, `src/specify_cli/consolidation/state.py`, `tests/consolidation/test_rollback_authority.py`, `tests/consolidation/test_rollback_own_lane_moves.py` (new) |
| WP04 | `src/specify_cli/consolidation/reconciliation_authorship.py`, `src/specify_cli/consolidation/reconciliation_claim.py`, `src/specify_cli/consolidation/reconciliation_claim_types.py`, `tests/consolidation/test_reviewed_merge_predicate.py` (new) |
| WP05 | `src/specify_cli/consolidation/approved_bound.py`, `src/specify_cli/consolidation/reconciliation_bound.py`, `tests/consolidation/test_resolution_merge_unreviewed.py` (new), `tests/consolidation/test_approved_bound_residuals.py`, `tests/consolidation/test_dependency_merge_attribution_7307.py` |
| WP06 | `src/specify_cli/consolidation/reconciliation_verifier.py`, `tests/consolidation/test_unreviewed_merge_hint.py` (new) |
| WP07 | `src/specify_cli/lanes/stale_check.py`, `src/specify_cli/lanes/consolidation.py`, `src/specify_cli/consolidation/phase_advance.py`, `tests/lanes/test_stale_remediation_cli_command.py`, `tests/lanes/test_approved_lane_stale_remedy.py` (new) |
| WP08 | `src/specify_cli/lanes/incorporate.py` (new), `src/specify_cli/cli/commands/agent/workflow.py`, `tests/lanes/test_incorporate_sibling_lane.py` (new) |
| WP09 | `src/specify_cli/orchestrator_api/consolidation.py`, `src/specify_cli/orchestrator_api/envelope.py`, `docs/api/orchestrator-api.md`, `src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md`, `tests/orchestrator_api/test_consolidate_mission_resolution_merge.py` (new), `tests/specify_cli/orchestrator_api/test_contract_version.py` (re-pinned to 1.30.0) |
| WP10 | `src/specify_cli/review/wp_range.py`, `src/specify_cli/review/context_block.py`, `tests/review/test_review_context_merge_lines.py` (new) |
| WP11 | `src/specify_cli/consolidation/reconciliation_canceled.py`, `src/specify_cli/consolidation/reconciliation_kernel.py`, `src/specify_cli/consolidation/wp_attribution.py` (carrier-fix leeway only), `tests/consolidation/test_canceled_via_reapproved_dependency_7497.py` (new) |
| WP12 | `tests/terminus/approved_lane_route_support.py` (new), `tests/terminus/test_approved_lane_resolution_route.py` (new) |
| WP14 | `tests/terminus/test_approved_lane_resolution_route_three_lane.py` (new) |
| WP13 | `docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md`, the ADR 2026-09-29-1 file, `docs/adr/3.x/2026-09-19-1-*.md`, `docs/adr/4.x/2026-11-08-2-*.md`, `CLAUDE.md`, `docs/changelog/unreleased/<new fragment>` |

Recorded leeway:

- **WP05, bounded test leeway**: WP05 may adjust an existing test it does not own only when (a) its fixture carries an unrecorded post-approval merge with its own content, which now refuses at claim time, and (b) its file is named in WP05's Test Strategy command lists. Each change is a re-pin to the new code (never a deletion or a weakened assertion, Standing Order 5) and is listed in WP05's history with the file, the test, the old and new expectation and the rationale. Any other file: stop and report to the runner.
- **WP05, probe-memo wiring**: if the NFR-001 passing-claim count needs a per-claim memo (WP05 owns it; WP04 adds none), WP05 may thread it through WP04's `reconciliation_authorship.py` / `reconciliation_claim.py`, limited to passing the memo, listed in history.
- **WP11**: owns `src/specify_cli/consolidation/wp_attribution.py` only for the carrier fix of T041 (no other WP owns it); `_lane_first_parent_spine` in `reconciliation_kernel.py` must not change (WP05's agreement test and WP04's sink depend on it). WP01 adds one read-only public accessor, `registered_merge_driver_specs()`, to `src/specify_cli/lanes/consolidation.py` (owned by WP07), next to the existing `merge_driver_attribute_lines()`. It exposes the `_MERGE_DRIVERS` registry. This is a one-function, out-of-map edit; the reason is that the registry is private and its owning file belongs to WP07. WP07 depends on WP01, so its lane contains the accessor.

Operator ruling (WP01, committed merge attributes, 2026-11-20): option (a). It honours a built-in `union`/`set` value from the COMMITTED tree only when `git check-attr --source <pre-run target tip>` equals the effective value, no clone-local source sets it, no `merge.<name>.driver` is configured, and git >= 2.40; clone-local sources still refuse. WP05 and WP06 pass the pre-run target tip to the probes. WP08 (operator ruling): `--incorporate` exits non-zero (distinct constant) on a conflict. WP03 (operator ruling): `LANE_MOVED_SINCE_AUTO_REBASE` is a settled outcome that keeps the record.

---

## Phase 1: Foundations

## Work Package WP01: Merge probes fail closed on effective merge attributes (Priority: P1)

**Goal**: the clean-fold recognizer and the own-content remerge probe refuse whenever an unregistered merge attribute or driver applies.
**Independent Test**: red attack tests for each route, run against both probes, plus a positive control that uses only spec-kitty's own drivers.
**Prompt**: `tasks/WP01-merge-probe-attribute-guard.md`
**Requirement Refs**: FR-010, NFR-001, NFR-002

### Included Subtasks

T001 Red attack tests: `merge=union` via info attributes, uncommitted working-tree `.gitattributes`, and `core.attributesFile`; a custom `merge.<x>.driver`; `merge.default`; a registered driver name redefined to another command. Run each against `n_way_merge_blob` and `merge_own_changed_paths` (WP01)
T002 Add the `registered_merge_driver_specs()` accessor in `lanes/consolidation.py` (recorded leeway); the drift test compares de-duplicated rendered lines (WP01)
T003 Implement `merge_attribute_guard.py`: one batched `git check-attr --stdin merge` call, registered-triple allowance, the `merge.default` check, and fail closed with `GitProbeError` (WP01)
T004 Wire the guard into `n_way_merge_blob` and `merge_own_changed_paths` (and the kernel remerge path they share), caching the merge config per run; read the git version once per run in `src/specify_cli/git/merge_tree_probe.py` through `kernel.git.read_cache.cached_git_read`, pinned by a subprocess-count test (NFR-001) (WP01)
T005 [P] Positive control: a consolidation fixture with only spec-kitty's own drivers installed is unchanged, including another Mission's `kitty-specs/**` paths; the committed-attribute tests for the confirmed ruling ((a) or (b)) (WP01)

### Dependencies

- None.

---

## Work Package WP02: Durable auto-rebase record (Priority: P1)

**Goal**: every auto-rebase merge leaves `refs/spec-kitty/auto-rebase/<lane-branch>/<merge-sha>`, and lane cleanup removes those refs.
**Independent Test**: an auto-rebase (clean and auto-resolved) writes the ref with the exact SHA. A write failure halts the auto-rebase. Cleanup deletes the refs.
**Prompt**: `tasks/WP02-auto-rebase-record.md`
**Requirement Refs**: FR-005, NFR-002

### Included Subtasks

T006 Red tests for the record contract (`contracts/auto-rebase-record.md`); tests that pass at HEAD are labelled controls (WP02)
T007 New module `lanes/auto_rebase_record.py`: `record()`, `is_recorded(sha)`, `delete_for_lane()`, `delete(sha)`, each through the kernel git helpers (WP02)
T008 Write the ref in `attempt_auto_rebase` right after the merge commit. On a write failure, undo the merge, re-record the lane-tip ref, and report a halt (no unrecorded tool merge) (WP02)
T009 Delete the lane's refs in `lane_cleanup` when the lane branch is removed (WP02)

### Dependencies

- None.

---

## Work Package WP04: Shared reviewed-merge predicate and claim field (Priority: P1)

**Goal**: one public predicate, "this merge is reached by one of its own lane's approval stamps", extracted from `_drop_unreviewed_merges`, plus the additive claim field `unreviewed_merges`.
**Independent Test**: unit tests on the predicate. The claim records dropped merges with sha, lane, WPs, own paths and own blobs. Existing claim fields stay byte-identical (snapshot test).
**Prompt**: `tasks/WP04-reviewed-merge-predicate.md`
**Requirement Refs**: FR-004, FR-006, C-003

### Included Subtasks

T010 Red tests: the predicate, the three-lane case, and the claim field population (WP04)
T011 Extract the public predicate. `_drop_unreviewed_merges` calls it, with no behaviour change (WP04)
T012 Add `UnreviewedMerge` and `unreviewed_merges` to the claim types. Populate them where merges are dropped, with own paths and blobs from the existing probe. Advisory only: a skipped probe error never becomes a verdict; no memo here (WP05 owns it) (WP04)
T013 Byte-identity check on the existing claim fields, with a build-twice determinism precondition before the golden comparison (WP04)

### Dependencies

- None.

---

## Work Package WP08: `implement --incorporate <lane>` (Priority: P1)

**Goal**: the canonical lane sync point merges a named sibling lane at its newest approval stamp into the lane checkout, and stops on a conflict for hand resolution.
**Independent Test**: a clean incorporation creates a merge whose second parent is the stamp. A conflict leaves the merge in progress with a clear message. Unknown lanes, unstamped lanes, a stamp not on the branch, and an approved WP that was not sent back all refuse.
**Prompt**: `tasks/WP08-implement-incorporate.md`
**Requirement Refs**: FR-001, C-004, C-006

### Included Subtasks

T014 Red tests at the CLI level for the clean, conflict and refusal cases; "unchanged without the flag" compares against a golden recorded at the base (WP08)
T015 New module `lanes/incorporate.py`: resolve the sibling lane and its newest approval stamp (reuse the `approved_bound` stamp reader), check the stamp is on the sibling branch, and merge in the lane checkout (WP08)
T016 Add the `--incorporate` option to `agent action implement` (`cli/commands/agent/workflow.py`). It runs after the normal sync point and only when the WP is `in_progress` or `claimed` (WP08)
T017 Messages: the conflict list, and next steps (resolve, commit, for_review) (WP08)

### Dependencies

- None.

---

## Phase 2: Behaviour

## Work Package WP03: Rollback undoes the run's own auto-rebase lane moves (Priority: P1)

**Goal**: the rollback restores each lane from `lane_rebase_moves` under compare-and-swap, resyncs the checkout, resets the lane work-tip and deletes the auto-rebase ref. A lane that has moved since is the kept outcome `LANE_MOVED_SINCE_AUTO_REBASE`.
**Independent Test**:
- Red first: the next run is harmed by the leftover merge at the base.
- Then the lane is restored.
- A moved lane is reported, not restored, and is not re-baselineable.
- A non-recorded lane move is still report-only.
**Prompt**: `tasks/WP03-rollback-own-lane-moves.md`
**Requirement Refs**: FR-009, NFR-002, C-006

### Included Subtasks

T018 Red reproduction of the observed harm at the base, on a fixture built with `allocate_lane_worktree` (both lanes edit one shared file). Harm pinned on the CLEAN shape: the next run exits 0 and names no commit of the first run's recorded move. The failed-after-the-auto-rebase shape is mandatory. Record the actual code in the WP history (WP03)
T019 Re-pin the two report-only tests in `test_rollback_authority.py` to the narrow rule, and add a test that a non-recorded move is still report-only (WP03)
T020 Implement the lane restore in `rollback.py` (CAS `after -> before`, `resync_checkouts_to_tip`, the lane-tip reset through `lane_tip.py`, ref delete through WP02's module) (WP03)
T021 The new outcome `LANE_MOVED_SINCE_AUTO_REBASE`: counts as settled for `fully_restored`, `rebaselineable` is False and the record is kept (an operator-overrulable design decision). Covers the `--abort` report line (WP03)
T022 State lifetime: keep `lane_rebase_moves` entries for unrestored lanes across the re-baseline (`state.py`, `rollback.rebaseline_after_full_restore`) (WP03)

### Dependencies

- WP02 (ref delete)
- WP07 (moves recorded on every auto-rebase)

---

## Work Package WP05: Claim-time `RESOLUTION_MERGE_UNREVIEWED` (Priority: P1)

**Goal**: refuse before any mutation when a merge on an approved code lane carries its own non-bookkeeping content, none of its own lane's stamps reach it, and it has no auto-rebase record. Also tighten the #7307 tests and convert the residual xfail.
**Independent Test**:
- The named refusal fires and no branch moves.
- Controls:
  - a recorded tool merge is not refused;
  - a message-forged merge and a hand merge of the Mission branch are refused;
  - a clean merge is not refused;
  - the three-lane case fires;
  - the claim and the gate agree.
**Prompt**: `tasks/WP05-resolution-merge-unreviewed.md`
**Requirement Refs**: FR-004, FR-005, FR-012, NFR-001, NFR-002, C-002, C-003

### Included Subtasks

T023 Red tests: the named code; no mutation proven by reflog lengths and no snapshot written; all controls (labelled when green at the base); the predicate agreement with the gate side taken from WP04's `unreviewed_merges`; a claim-level `merge=union` attack through the real CLI (WP05)
T024 `BoundRefusalCode.RESOLUTION_MERGE_UNREVIEWED`, `unreviewed_resolution_merges()` in `approved_bound.py`, and the `render_refusals` text (`contracts/refusal-codes.md`) (WP05)
T025 Call it from `_approved_bound_verdict` (`reconciliation_bound.py`) after tiers 1 and 2. Add the `_compound_refusal` order and `refusal_codes`. Leave `content_commits` untouched. The verdict comes only from its own raising probe (never from `unreviewed_merges` or an error-swallowing memo); NFR-001 count test on a passing claim, with the per-claim memo if needed (WP05)
T026 Forecast: the `--dry-run` cell reports `CLAIM_REFUSED_FORECAST` naming the code (WP05)
T027 FR-012: replace the early returns in `test_dependency_merge_attribution_7307.py` with pinned codes, and keep a gate-level assertion with the claim check bypassed (WP05)
T028 Convert the strict xfail in `test_approved_bound_residuals.py` (the post-approval merge shape) to assert the new code (WP05)

Binding addendum for WP05 (orchestrator ruling 2026-11-20): a recorded auto-rebase merge is exempt only when the FR-010 guard passes with the committed-tree rule. `is_recorded` raising is a refusal, and a missing `unreviewed_merges` entry means re-probe or refuse. Add a defence-in-depth test that a forged record ref cannot land content. Re-adding the consumed WP02/WP04 symbols to `__all__` is recorded leeway (see the WP05 prompt).

### Dependencies

- WP01 (guarded probe)
- WP02 (record)
- WP04 (predicate)

---

## Work Package WP06: Gate hint names re-review for dropped merges (Priority: P2)

**Goal**: `_with_attribution_hint` names the re-review route instead of `--dependency-ref` when every un-attributable blob is the own-path blob of an `unreviewed_merges` entry, and does not when there is a canceled clause.
**Independent Test**: renderer-level tests on claim fields. Covers the hand-merge shape, canceled and mixed divergences (N4), and foreign content (unchanged).
**Prompt**: `tasks/WP06-gate-hint-re-review.md`
**Requirement Refs**: FR-006

### Included Subtasks

T029 Red renderer tests for the four shapes (WP06)
T030 Implement the hint branch in `reconciliation_verifier.py`. `Divergence.describe()` is unchanged. Correct the stale `is_legitimate_merge_resolution` docstring (FR-010, after WP01); under WP01's ruling (a), pass the pre-run target tip to the two probe call sites (WP06)
T031 Keep `_with_attribution_hint` at complexity ≤ 15 (extract a helper) (WP06)

### Dependencies

- WP01 (the docstring correction and the probe keyword)
- WP04

---

## Work Package WP07: Approved-lane stale remedy, siblings and halt reason (Priority: P1)

**Goal**:
- The stale refusal for approved code lanes names exactly the sibling lane(s), the halt reason and the conflicted paths.
- It prints the runnable route (`contracts/stale-remedy.md`).
- The auto-rebase move is recorded on every merge, not only on success.
**Independent Test**:
- Remedy text tests, covering the three-lane exact-set control and the `no_lane_checkout` and `merge_in_progress` reasons.
- Each printed command executes on the fixture.
- Non-approved callers are unchanged.
**Prompt**: `tasks/WP07-approved-lane-stale-remedy.md`
**Requirement Refs**: FR-001, FR-002, FR-003

### Included Subtasks

T032 Red tests: the approved-lane remedy text (through `consolidate_lane_into_mission`), exact siblings, halt reasons (including the guarded-abort cause where feasible and the half-resolved bytes surviving), unchanged non-approved text (a ratchet), and the re-pinned A-10 test (WP07)
T033 `StaleCheckResult`: `halt_reason`, `conflicted_paths`, `sibling_lanes`. Add the approved-lane branch to the pure renderer, reusing `approved_bound.move_back_command` (WP07)
T034 `lanes/consolidation.py`: return the `AutoRebaseReport` instead of discarding it, accept `approved_wp_ids` and `sibling_candidates`, and report the no-checkout and merge-in-progress cases. Probe `MERGE_HEAD`/`REBASE_HEAD`/`CHERRY_PICK_HEAD` BEFORE `attempt_auto_rebase` and skip the attempt (`merge_in_progress`), so an operator's half-resolved bytes survive (WP07)
T035 `phase_advance.py`: derive `approved_wp_ids` from `run.approved_wp_set` and the sibling candidates through the one public helper `lanes.consolidation.sibling_candidates_before(lanes_manifest, lane_id, *, integrated_lane_ids, pre_run_tips) -> tuple[SiblingCandidate, ...]`, which WP09 also calls. Record `lane_rebase_moves` on every auto-rebase merge (WP07)
T036 Execute-each-printed-command test on a two-lane conflicting fixture (needs WP08's command) (WP07)

Binding DoD for WP07 (from WP08 review item 3, reviewer-accepted recorded leeway): `--incorporate` calls WP01's attribute guard through WP01's shared pinned-config helper before merging, and refuses with `INCORPORATE_MERGE_ATTRIBUTES_REFUSED`. This needs a real-git `merge=union` red test. The edit to `src/specify_cli/lanes/incorporate.py` is recorded leeway (see the WP07 prompt). It is a blocking review check.

### Dependencies

- WP01 (its leeway accessor lives in `lanes/consolidation.py`, which this WP owns)
- WP08 (the `--incorporate` command named by the remedy)

---

## Work Package WP10: Review context lists merge resolutions (Priority: P2)

**Goal**: `wp_range` lists every merge in the review range with full history. `context_block` prints a labelled `git show --remerge-diff <sha>` line per merge, or a "cannot show" line.
**Independent Test**: a range with a hand merge lists it, a range with no merges is unchanged, and git without remerge-diff prints the note.
**Prompt**: `tasks/WP10-review-context-merge-lines.md`
**Requirement Refs**: FR-007

### Included Subtasks

T037 Red tests (WP10)
T038 Add `merges` to the range (`git rev-list --merges --full-history`) in `wp_range.py` (WP10)
T039 Renderer lines in `context_block.py`, commands only, within the byte-budget rules (WP10)

### Dependencies

- None.

---

## Work Package WP11: #7497 canceled content via a re-approved dependency lane (Priority: P2)

**Goal**: a red-first proof of the #7497 shape, and a fix if it is red.
**Independent Test**: A approved; C fully canceled and merged into A; A re-approved (unforced); fresh consolidate. Expected: `CANCELED_REACHABLE_VIA_DEPENDENCY`. A control without the re-approval keeps today's verdict.
**Prompt**: `tasks/WP11-canceled-via-reapproved-dependency.md`
**Requirement Refs**: FR-011

### Included Subtasks

T040 Red-first test using `build_canceled_lane_on_approved_dependency`, with asserted preconditions (WP11)
T041 If red: identify the mechanism first. One candidate is the live-tip anchor in `_fully_canceled_lane_own_commits`. The other is first-parent-only `_carrier_spines` with a `--no-ff` merge. Fix it by anchoring C on A as of C's cut (C's lane base, or its first-claim stamp; not `merge-base`, which equals C's tip once A merged C), and/or by walking the carrier lane's full history (`canceled_spine_content` in `wp_attribution.py` under the carrier-fix leeway). Never change `_lane_first_parent_spine`. Escalate rather than relax the expected code (`reconciliation_canceled.py` / `reconciliation_kernel.py`) (WP11)
T042 If green at the base: keep the test as a ratchet pin, and record the evidence for closing #7497 in the WP history (WP11)
T043 Mutation check: drop the fix (or invert the precondition) and the test goes red (WP11)

### Dependencies

- None.

---

## Phase 3: Surfaces and proof

## Work Package WP09: orchestrator-api surface (Priority: P2)

**Goal**: `consolidate-mission` refuses with `RESOLUTION_MERGE_UNREVIEWED` in `preflight_error_code(s)`. `CONTRACT_VERSION` goes from 1.29.0 to 1.30.0. Its stale remedy passes `approved_wp_ids`, so the approved-lane route is printed there too.
**Independent Test**: envelope tests for the new code and the version, and a stale-remedy text test via the orchestrator-api path.
**Prompt**: `tasks/WP09-orchestrator-api-surface.md`
**Requirement Refs**: FR-004, FR-001, C-007

### Included Subtasks

T044 Red envelope tests (WP09)
T045 Pass `approved_wp_ids` and the siblings (from WP07's `sibling_candidates_before`) into `consolidate_lane_into_mission` from `orchestrator_api/consolidation.py` (WP09)
T046 Bump the contract version to 1.30.0; REQUIRED doc edits: `docs/api/orchestrator-api.md` (version line, version history, preflight-code table) and the operator-skill contract reference; re-pin `tests/specify_cli/orchestrator_api/test_contract_version.py`; a test that the doc's version line equals `CONTRACT_VERSION` (WP09)

### Dependencies

- WP05
- WP07

---

## Work Package WP12: End-to-end route: support module, two-lane route and controls (Priority: P1)

**Goal**: the support module, and the two-lane route through the real CLI under squash AND `--strategy merge` with unforced transitions by distinct actors; N1 to N3; SC-003 proven by reflog lengths and "no snapshot written"; the residual control (a reviewed novel line lands).
**Independent Test**: this is the test. A strict `xfail` or `skip` on a happy-path step blocks approval; a route gap is recorded with `spec-kitty agent tasks add-history` and reported to the runner, who reopens the WP owning the failing surface.
**Prompt**: `tasks/WP12-end-to-end-route.md`
**Requirement Refs**: FR-008, SC-001, SC-002, SC-003

### Included Subtasks

T047 Support module: two independent approved lanes with adjacent-hunk edits to one shared file (`git merge-tree` exits 1, asserted as a fixture precondition); the three-lane builder for WP14 (lane-c depends on lane-b, lane-d a non-overlapping exact-set control); the `run_route` driver; reflog-length and no-snapshot helpers (WP12)
T048 Happy path under squash and under `--strategy merge` (coordination topology): stale refusal, then the printed commands, then the hand resolution, then the independent approval, then consolidate exit 0 (WP12)
T049 N1 (an unreviewed hand resolution refuses whatever it contains, with and without a novel line), N2 (merge after re-approval), N3 (forced or self re-approval): each refuses, with no branch moved (WP12)
T050 SC-003 no-mutation proof (reflog lengths, no snapshot, with a land-then-rollback control) and the residual control (route followed, novel line, independent approval: exit 0 and the line lands) (WP12)

### Dependencies

- WP03
- WP05
- WP06
- WP07
- WP08
- WP09
- WP10
- WP11

---

## Work Package WP14: End-to-end route: three-lane and rollback cases (Priority: P1)

**Goal**: SC-004 end to end (the next run after a rollback is not refused because of the run's own merge, plus the foreign-commit control); the three-lane route with exact siblings (lane-c depends on lane-b; lane-d a non-overlapping control); the three-lane dependent-stamp refusal; the remaining matrix cells (lanes topology under squash and `--strategy merge`).
**Independent Test**: this is the test. A strict `xfail` or `skip` on a happy-path step blocks approval; a route gap is recorded with `spec-kitty agent tasks add-history` and reported to the runner, who reopens the WP owning the failing surface.
**Prompt**: `tasks/WP14-end-to-end-three-lane-and-rollback.md`
**Requirement Refs**: FR-008, FR-009, SC-004

### Included Subtasks

T055 SC-004: a clean auto-rebase, a gate FAIL once and a rollback; lane-b restored and its record gone; the next CLI run exits 0 naming no commit of the first run's move; control: a foreign commit after the rollback is refused `LANE_MOVED_AFTER_APPROVAL`, never reset (WP14)
T056 Three-lane route: exact sibling sets (lane-d never named), one send-back and review cycle per conflicting lane, final exit 0 (WP14)
T057 Three-lane: lane-c's stamp reaching lane-b's unreviewed merge does not excuse it (`RESOLUTION_MERGE_UNREVIEWED`, no branch moved) (WP14)
T058 Remaining matrix cells: the two-lane route on the lanes topology under squash and `--strategy merge`, and N1 there (WP14)

### Dependencies

- WP12

---

## Work Package WP13: ADR, contract and doc amendments (Priority: P2)

**Goal**: record the model (FR-013) and add the changelog fragment.
**Independent Test**: a document review checks every FR-013 point, and the terminology guard passes.
**Prompt**: `tasks/WP13-adr-and-doc-amendments.md`
**Requirement Refs**: FR-013

### Included Subtasks

T051 ADR 2026-10-04-5 amendment: re-review as the sanctioned exit; the `RESOLUTION_MERGE_UNREVIEWED` refusal and the auto-rebase record; the residual at line 174 resolved (WP13)
T052 ADR 2026-09-29-1 amendment (the #7630 trust model, the FR-010 fail-closed rule) and ADR 3.x 2026-09-19-1 amendment (narrow lane restore, the new outcome) (WP13)
T053 ADR 2026-11-08-2 / review-context contract amendment (merge lines); the stale-remedy rule (#7285 A-10 kept, `--incorporate` added) (WP13)
T054 CLAUDE.md: fix the residual sentence about lane auto-rebase merges surviving a rollback, and add the new code and route. Changelog fragment in `docs/changelog/unreleased/` (WP13)

### Dependencies

- WP01, WP02, WP03, WP04, WP05, WP06, WP07, WP08, WP09, WP10, WP11, WP12, WP14.

---

## Closeout ownership (runner)

- The runner fills `issue-matrix.json` (FR/WP/verdict per issue), claims the issues and posts the tracker comments at closeout (charter Standing Order 8). FR-011's ratchet branch is recorded there.
- NFR-003, NFR-004, C-001 and C-005 are enforced through every WP's validation section, through the design, or as a scope boundary. They are not mapped to a single WP.

## Parallelization

- **Phase 1 (independent, start together):** WP01, WP02, WP04, WP08, WP10, WP11.
- **Phase 2:** WP07 (after WP01, WP08), WP06 (after WP01, WP04), WP05 (after WP01, WP02, WP04), WP03 (after WP02, WP07).
- **Phase 3:** WP09 (after WP05, WP07), WP12 (after WP03, WP05, WP06, WP07, WP08, WP09, WP10, WP11), WP14 (after WP12), WP13 last (after every other WP, including WP12 and WP14).
- **Critical path:** WP08 -> WP07 -> WP03 -> WP12 -> WP14 -> WP13. WP12's added dependencies (WP06, WP09, WP11) do not lengthen it: WP12 already waits on WP03, and WP06, WP09 and WP11 each finish no later than WP03 on the planned schedule (WP09 and WP03 both wait on WP07).

**MVP:** WP08 + WP07, the runnable route, closes #7754, #7755 and the remedy side of #5604.
