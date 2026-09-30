# Work Packages: Owned-checkout lifecycle authority

**Inputs**: `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/`, which holds `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` and `occurrence_map.yaml`.
**Prerequisites**: plan.md (Implementation Concern Map IC-01..IC-14, Staging Strategy, Test Layout), spec.md (FR-001..FR-026).
**Tests**: required. ATDD red-first is binding: charter C-011, spec C-007.
**Mode**: bulk edit (`change_mode: bulk_edit`). Every WP complies with `occurrence_map.yaml`.

**Subtask tracking**: `Txxx` rows are reference rows. Record completion with `spec-kitty agent tasks mark-status Txxx --status done`.

**Staging rules for every WP** (plan: Staging Strategy):
- Conversion is top-down.
- Transitional surfaces are the six shared seams plus every other function marked TRANSITIONAL(WP18). The six shared seams keep a temporary dual keyword (`owned=` plus legacy `effective_root=`) until WP18.
- **`TRANSITIONAL(WP18)` convention:** every transitional legacy parameter, field, property, alias or factory anywhere in `src/` or `tests/` carries a `# TRANSITIONAL(WP18): <reason>` comment. WP18 T096 deletes exactly everything `grep -rn "TRANSITIONAL(WP18)" src tests` finds; T097 asserts that grep is empty.
- The transitional `OwnedMission` is a legacy factory **function** in `core/owned_mission.py` (the minter module, so G3 holds). It accepts the old positional arguments and mints an `OwnedCheckout`; it and the legacy `OwnedCheckout` property names are marked `TRANSITIONAL(WP18)` and live until WP18.
- mypy runs with `follow_imports = "skip"` for `specify_cli.*`: type-check callers and callees of a changed signature in the same invocation.
- The dead-symbol gate (`tests/architectural/test_no_dead_symbols.py`) is judged at the **mission tip** (WP18), not per lane or per intermediate WP. Expected transient reds: `OwnedCheckout` until WP02, `resolve_owned_create_root` until WP10, `adopt_owned_checkout` until WP08. WP18 asserts it green.
- **Bridging markers:** every bridging call site carries `# bridging: WP<n> converts`, naming the WP that converts it. The converting WP's DoD asserts `grep -rn "bridging: WP<self>" src` is empty; WP18 asserts `grep -rn "# bridging:" src` is empty.
- **TRANSITIONAL budget:** each WP that adds `TRANSITIONAL(WP18)` markers lists them exactly in its DoD with the expected `grep -c` count. WP18 T096 fails on any marker that no WP's DoD lists.
- **Red-first proofs are commits:** the red test commit precedes the fix commit; reviewers verify the order in `git log`. No Activity-Log-only or `git stash` proofs.
- **Error codes:** import them from WP01's `OwnedRefusalCode` `StrEnum`; never repeat a code literal (Sonar S1192).
- **mypy:** always `--strict`; callers and callees in one invocation; pre-existing errors are baselined by count, never hidden by dropping `--strict` or narrowing the file list.
- Every WP leaves the tree green: its targeted tests, ruff check/format and mypy all pass.

**Carried prior art (#5009)**: commits carried with `git cherry-pick -x <sha>` keep author Samuel Goff. Re-expressed fixes carry a `Co-authored-by: Samuel Goff <samuel@defpix.com>` trailer.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | `OwnedCheckout` value object (private mint, invariants, `files()`, transitional legacy properties) | WP01 | |
| T002 | Re-export plus the `mission_runtime` public-surface gate | WP01 | [P] |
| T003 | Carrier unit tests incl. symlink and case-variant identity; `ci-windows.yml` filter | WP01 | [P] |
| T004 | AST gate scanner module (reference forms, identifier ban, annotation forms, FQN exemption) | WP01 | |
| T005 | Gate self-mutation tests (green) | WP01 | |
| T006 | `resolve_owned_mission` returns the fact; `allowed_topologies`; topology sets | WP02 | |
| T007 | `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` refusal | WP02 | [P] |
| T008 | `resolve_owned_create_root` → typed `OwnedCreateRoot` | WP02 | [P] |
| T009 | `adopt_owned_checkout` (exclusions, mission-surface-conflict preserved); `OWNED_CHECKOUT_IS_MISSION_WORKTREE` for an explicit lane/coordination worktree | WP02 | |
| T010 | Transitional `OwnedMission` legacy factory function plus `effective_root_kwargs` accepting the fact, marked TRANSITIONAL(WP18); annotation retype | WP02 | |
| T011 | Shared integration fixtures (`owned_checkouts`, `r_snapshot`, `stale_root_copy`) with self-tests | WP02 | |
| T012 | Amend ADR 2026-09-03-1 | WP03 | [P] |
| T013 | Amend ADR 2026-08-12-1 | WP03 | [P] |
| T014 | Note in ADR 2026-06-07-1 (public `OwnedCheckout`) | WP03 | [P] |
| T015 | Glossary entry "owned checkout" plus docs tooling | WP03 | |
| T016 | Red-first seam tests: owned WP fields, missing WP scoped to P, stale copy | WP04 | |
| T017 | `placement_seam(owned=)` / `PlacementSeam.owned` (dual keyword) | WP04 | |
| T018 | `mission_context_for` / `resolve_action_context` / `_resolve_wp_bearing_fields` take the fact | WP04 | |
| T019 | Delete `_require_owned_single_branch`; topology from the fact | WP04 | |
| T020 | `locate_work_package(owned=)` (dual keyword) | WP04 | [P] |
| T021 | Convert the remaining bare owned roots in `resolution.py` and `mission_runtime/context.py` | WP04 | |
| T022 | Red-first: owned workspace kind and same-slug cache isolation | WP05 | |
| T023 | `resolve_workspace_for_wp(owned=)` owned arm (dual keyword) | WP05 | |
| T024 | Cache keyed on the resolved `tasks_dir` plus cache-clear tests | WP05 | |
| T025 | `enforce_checkout_identity` owned arm | WP05 | [P] |
| T026 | Campsite extractions for complexity ≤ 15 | WP05 | |
| T027 | Carry #5009 4ff6ff0c0; drop the parallel-source test; add a registered-coordination control | WP06 | |
| T028 | `surface_resolver.primary_read_targets_coord_worktree(path, *, owned)` | WP06 | |
| T029 | Route all six `status_service` shape-guard sites; read and write contracts gain `owned` | WP06 | |
| T030 | `transaction.py` `.worktrees` check → `is_under_worktrees_segment`; convert its owned roots | WP06 | [P] |
| T031 | FR-013/FR-014 same-path tests | WP06 | |
| T032 | `TransitionRequest.owned` (collapses `effective_root` and `owned_mission`; dual keyword) | WP07 | |
| T033 | `status_transition`: consume the fact, remove re-validation, owned read contract | WP07 | |
| T034 | Pipeline readers: `transition_pipeline`, `emit`, `bootstrap` | WP07 | |
| T035 | `commit_router` / `write_seam` conversions | WP07 | [P] |
| T036 | `agent_tasks_ports.MissionHandle.owned` | WP07 | [P] |
| T037 | NFR-002 exactly-one-validation test (`move-task`) | WP07 | |
| T038 | Red-first acceptance: O3, O4, O10, US2, US7 | WP08 | |
| T039 | `_owned_checkout.py`: option, resolver/adopter, refusal emitter, stale-copy reporter | WP08 | |
| T040 | `context resolve --owned-checkout` plus validated adoption; delete `operation_context.py` | WP08 | |
| T041 | Stale-copy warning in the context payload and `warnings[]` | WP08 | |
| T042 | Campsite: `resolve_context` (15) | WP08 | [P] |
| T043 | Re-home the `operation_context` tests | WP08 | |
| T044 | Red-first acceptance: O1, O2, US1, US6 | WP09 | |
| T045 | `agent tasks status --owned-checkout` plus stale-copy field; campsite `_st_load_work_packages` / `setup_plan` | WP09 | |
| T046 | `setup-plan --owned-checkout` commits in P | WP09 | |
| T047 | `agent action implement`/`review` refusal `OWNED_ACTION_UNSUPPORTED` | WP09 | [P] |
| T048 | `tasks.py` options onto `OwnedCheckoutOption`; golden contracts | WP09 | |
| T049 | FR-020 invalid-path matrix across the new flags | WP09 | |
| T050 | Characterisation tests for `_create_mission_core_impl` | WP10 | |
| T051 | Decompose `_create_mission_core_impl` to ≤ 15; drop the `mission_creation.py` C901 ignore | WP10 | |
| T052 | Carry #5009 a37e9ee39 (red) | WP10 | |
| T053 | Governance reads from the owned root through `resolve_owned_create_root` (re-express 1f42f76ea) | WP10 | |
| T054 | Template-marker test plus charter-authoring ratchet (FR-017) | WP10 | |
| T055 | Remaining conversions in `mission_creation` / `mission_create`; `mission_create.py` onto `OwnedCheckoutOption` | WP10 | |
| T056 | *Retired id: moved to WP19 (T101)* | — | |
| T057 | Red-first at the runtime entry points: O5, O8 (both injections), FR-009 composition, stale-copy board, lanes_with_coord runtime twin | WP11 | |
| T058 | Campsite: `query_current_state` (`next_step` / `_print_standard_human` moved to WP19 T103) | WP11 | |
| T059 | *Retired id: moved to WP19 (T103)* | — | |
| T060 | `DecideNextContext.owned`, `_dn_*`, composition policy, git cwd | WP11 | |
| T061 | Board authority with the fact; resolve before persisting the advance | WP11 | |
| T062 | #4867: `CoordinationWorkspaceUnavailable` → blocked `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` | WP11 | |
| T063 | Remaining conversions in the `runtime/next` bridge modules; the six marked legacy entry keywords (`next_cmd` part moved to WP19 T105) | WP11 | |
| T064 | Red-first: non-owned review base; owned review AS4/AS5 | WP12 | |
| T065 | `claim_commit_for_wp` helper plus uniqueness pin | WP12 | |
| T066 | Campsite: `_state_to_action` (decision.py) | WP11 | |
| T067 | `decision.py` takes the fact | WP11 | |
| T068 | Campsite `_build_wp_prompt`; `prompt_builder` takes the fact; scoped review diff; fail closed | WP12 | |
| T069 | Replace and delete the three commit-subject matchers | WP12 | |
| T070 | Red-first: lane-cycle post-write refusal; O6 end-to-end | WP13 | |
| T071 | Campsite: `finalize_tasks`, `_commit_finalize_artifacts`, `_run_bootstrap_loop` | WP13 | |
| T072 | Finalize plan phase in memory | WP13 | |
| T073 | Finalize apply phase; owned status read | WP13 | |
| T074 | Option migration, owned-root conversions, stale-copy field | WP13 | |
| T075 | Characterisation tests for `accept()` | WP14 | |
| T076 | Decompose `accept()` to ≤ 15; drop the `accept.py` C901 ignore | WP14 | |
| T077 | Stop re-validating at `accept.py:342`; consume the fact | WP14 | |
| T078 | Convert `accept.py` owned roots; option migration | WP14 | |
| T079 | FR-022 accept ratchet | WP14 | |
| T080 | Convert `acceptance/__init__.py` | WP15 | |
| T081 | Convert `acceptance/execution_context.py` and `gates_core.py` | WP15 | [P] |
| T082 | Convert `acceptance/matrix.py` | WP15 | [P] |
| T083 | Acceptance-package test updates plus the FR-022 ratchet | WP15 | |
| T084 | Convert `tasks_move_task.py` | WP16 | |
| T085 | Convert `tasks_mark_status.py` / `tasks_shared.py` | WP16 | [P] |
| T086 | Convert `tasks_parsing_validation.py` / `tasks_verdict_persistence.py` | WP16 | [P] |
| T087 | Convert `spec_commit_cmd.py` / `mission_check_prerequisites.py`; option migration | WP16 | |
| T088 | FR-022 ratchet: existing owned `move-task` / `mark-status` / `spec-commit` tests | WP16 | |
| T089 | Command-level exactly-one-validation assertions | WP16 | |
| T090 | Convert `tasks/issue_matrix.py` | WP17 | [P] |
| T091 | Campsite plus conversion: `review/cycle.py` | WP17 | |
| T092 | Convert `consolidation/baseline.py` | WP17 | [P] |
| T093 | Convert `git/commit_helpers.py`, `missions/_read_path_resolver.py` | WP17 | [P] |
| T094 | Convert `migration/runtime_state_cutover.py`, `migration/backfill_runtime_state.py` | WP17 | [P] |
| T095 | Commit the G1–G6 gate assertions red (record offender counts) | WP18 | |
| T096 | Delete exactly everything `grep -rn "TRANSITIONAL(WP18)" src tests` finds (the six shared seams' dual keyword plus every other marked surface) | WP18 | |
| T097 | Sweep leftovers (re-point `OwnedMission(...)` tests, rename `org_layer.py` walrus) → gate green; TRANSITIONAL grep empty; `_baselines.yaml` section cap 0 | WP18 | |
| T098 | SC-001 end-to-end walkthrough test (quickstart), incl. stale copy and cwd matrix | WP18 | |
| T099 | NFR-002 / NFR-003 measurements (`performance` marker) | WP18 | |
| T100 | Terminology guard, docs freshness, NFR-005 diff-cover, final targeted validation | WP18 | |
| T101 | Carry #5009 edaa9cd83 and 1be5352ee (`cherry-pick -x`); adapt the call shape (was T056) | WP19 | |
| T102 | Red-first through the real `next`: O5, O9, stale copy, FR-023 pairing, FR-022 `lanes_with_coord` in-process CLI twin, FR-003 count | WP19 | |
| T103 | Campsite `next_step` / `_print_standard_human`; `next_cmd` through `resolve_owned_or_adopt(NEXT_OWNED_TOPOLOGIES)`; handle resolution in P; delete `_emit_checkout_ownership_error` (was T059) | WP19 | |
| T104 | `stale_repository_root_copy` in the `next` payload (owned runs only) | WP19 | |
| T105 | Remaining `next_cmd` conversions; no caller left for WP11's legacy keywords | WP19 | |

---

## Phase 1 — Foundation

## Work Package WP01: Validated ownership fact and gate harness (Priority: P0)

**Goal**: add `mission_runtime.OwnedCheckout`, which can only be minted privately, plus the AST scanner and its self-mutation tests.
**Independent Test**: carrier unit tests and gate self-tests pass; the `mission_runtime` surface gate is green.
**Prompt**: `tasks/WP01-validated-ownership-fact-and-gate-harness.md`
**Requirement Refs**: FR-001, NFR-006, C-003

### Included Subtasks
T001 `OwnedCheckout` value object (WP01)
T002 Re-export plus public-surface gate (WP01)
T003 Carrier unit tests, identity cases, `ci-windows.yml` filter (WP01)
T004 AST gate scanner module (WP01)
T005 Gate self-mutation tests (WP01)

### Dependencies
- None (starting package). **Estimated prompt size**: ~450 lines.

## Work Package WP02: Sole ownership minter and shared fixtures (Priority: P0)

**Goal**: `core/owned_mission.py` becomes the only minter: validator, create root, validated adoption and the repository-root refusal. Add the shared integration fixtures.
**Independent Test**: minter and adoption unit tests; fixture self-tests; the existing `tests/core/test_checkout_ownership.py` stays green.
**Prompt**: `tasks/WP02-sole-ownership-minter-and-shared-fixtures.md`
**Requirement Refs**: FR-002, FR-020, FR-021, FR-023, C-001

### Included Subtasks
T006 `resolve_owned_mission` returns the fact; `allowed_topologies` (WP02)
T007 `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` (WP02)
T008 `resolve_owned_create_root` typed (WP02)
T009 `adopt_owned_checkout` (WP02)
T010 Transitional `OwnedMission` factory function (WP02)
T011 Shared integration fixtures (WP02)

### Dependencies
- Depends on WP01. **Estimated prompt size**: ~500 lines.

## Work Package WP03: ADR amendments and glossary (Priority: P1)

**Goal**: record the validated-fact design, per-command topology, validated flagless adoption and the owned-checkout term.
**Independent Test**: the docs freshness, docs index and terminology gates pass.
**Prompt**: `tasks/WP03-adr-amendments-and-glossary.md`
**Requirement Refs**: FR-024, C-005, C-008

### Included Subtasks
T012 ADR 2026-09-03-1 amendment (WP03)
T013 ADR 2026-08-12-1 amendment (WP03)
T014 ADR 2026-06-07-1 note (WP03)
T015 Glossary entry plus docs tooling (WP03)

### Dependencies
- None. **Estimated prompt size**: ~250 lines.

## Phase 2 — Seams

## Work Package WP04: Placement seam and mission-runtime resolution (Priority: P0)

**Goal**: close the fall-back to the repository root at its source. The placement seam and WP-bearing resolution read from the owned checkout.
**Independent Test**: seam tests show WP fields under P; a missing WP is unresolved and scoped to P; a stale repository-root copy never wins.
**Prompt**: `tasks/WP04-placement-seam-and-mission-runtime-resolution.md`
**Requirement Refs**: FR-006, FR-007, FR-011, FR-023

### Included Subtasks
T016–T021 (WP04)

### Dependencies
- Depends on WP02. **Estimated prompt size**: ~500 lines.

## Work Package WP05: Workspace resolution owned arm (Priority: P0)

**Goal**: `resolution_kind="owned_checkout"`, per-checkout caches and the identity-guard owned arm.
**Independent Test**: owned kind with a null lane; the same slug in R and P gives distinct WP sets in one process; a mismatched fact is refused.
**Prompt**: `tasks/WP05-workspace-resolution-owned-arm.md`
**Requirement Refs**: FR-006, FR-011, FR-019
**Owned consumers**: also `core/stale_detection.py`, `lanes/implement_support.py` and `cli/commands/implement.py` (the `resolution_kind` / `runs_in_checkout_root` consumers, including stale_detection's `resolve_workspace_for_wp(owned=)` pass-through).

### Included Subtasks
T022–T026 (WP05)

### Dependencies
- Depends on WP04. **Estimated prompt size**: ~400 lines.

## Work Package WP06: Status surface authority (Priority: P0)

**Goal**: owned single_branch checkouts under `.worktrees/` read and write status through `surface_resolver`. Coordination protections are unchanged.
**Independent Test**: #5009's `.worktrees` finalize read goes green; a same-path registered coordination worktree is still refused.
**Prompt**: `tasks/WP06-status-surface-authority.md`
**Requirement Refs**: FR-013, FR-014, C-002

### Included Subtasks
T027–T031 (WP06)

### Dependencies
- Depends on WP02. **Estimated prompt size**: ~400 lines.

## Work Package WP07: Status transition pipeline takes the fact (Priority: P0)

**Goal**: `TransitionRequest.owned`. The status transaction stops re-validating, and ports carry the fact.
**Independent Test**: existing status-transition tests stay green; `move-task --owned-checkout` validates exactly once.
**Prompt**: `tasks/WP07-status-transition-pipeline.md`
**Requirement Refs**: FR-003, NFR-002

### Included Subtasks
T032–T037 (WP07)

### Dependencies
- Depends on WP04, WP06. **Estimated prompt size**: ~450 lines.

## Phase 3 — Commands and runtime

## Work Package WP08: CLI owned helper, context resolve and flagless adoption (Priority: P1)

**Goal**: one shared CLI owned surface, `context resolve --owned-checkout`, validated flagless adoption, and deletion of `operation_context.py`.
**Independent Test**: O3/O4/O10 and the US2/US7 acceptance scenarios, through the real CLI.
**Prompt**: `tasks/WP08-cli-owned-helper-context-resolve-and-adoption.md`
**Requirement Refs**: FR-006, FR-007, FR-020, FR-021, NFR-004

### Included Subtasks
T038–T043 (WP08)

### Dependencies
- Depends on WP02, WP05. **Estimated prompt size**: ~500 lines.

## Work Package WP09: Owned status, plan setup and unsupported-action refusals (Priority: P1)

**Goal**: `agent tasks status` and `setup-plan` gain `--owned-checkout`; `agent action implement`/`review` refuse with a typed code; golden contracts are updated. Closes the #3449 and #4252 CLI legs.
**Independent Test**: O1/O2, US1-AS1..AS3, US6 and the FR-020 invalid-path matrix.
**Prompt**: `tasks/WP09-owned-status-plan-setup-and-refusals.md`
**Requirement Refs**: FR-004, FR-005, FR-007, FR-018, FR-020

### Included Subtasks
T044–T049 (WP09)

### Dependencies
- Depends on WP07, WP08. **Estimated prompt size**: ~500 lines.

## Work Package WP10: Mission creation — decompose and owned governance reads (Priority: P1)

**Goal**: `_create_mission_core_impl` ≤ 15, the `mission_creation.py` C901 ignore removed, and create-time governance read from the owned checkout.
**Independent Test**: characterisation tests stay green; a37e9ee39 goes green; the template-marker test; the charter-authoring ratchet.
**Prompt**: `tasks/WP10-mission-creation-decompose-and-owned-governance.md`
**Requirement Refs**: FR-016, FR-017, FR-026

### Included Subtasks
T050–T055 (WP10)

### Dependencies
- Depends on WP02, WP08 (`mission_create.py` uses `OwnedCheckoutOption`). **Estimated prompt size**: ~500 lines.

## Work Package WP11: `next` runtime takes the fact (Priority: P0)

**Goal**: `runtime/next` carries the `OwnedCheckout` fact: `DecideNextContext.owned`, board authority resolved before the advance is persisted, composition policy and git cwd from P, the lifecycle store, `decision.py` on the fact, and the typed #4867 refusal. The five `next_cmd`-facing entry points keep one marked legacy keyword until WP19 converts the caller.
**Independent Test**: at the runtime entry points: O5 (no wedge, workspace P), O8 (both injections), FR-009 composition, the stale-copy board, and the `lanes_with_coord` runtime twin.
**Prompt**: `tasks/WP11-next-runtime-takes-the-fact.md`
**Requirement Refs**: FR-007, FR-008, FR-009, FR-012, FR-023

### Included Subtasks
T057, T058, T060–T063 (runtime part), T066, T067 (WP11). T056/T059 moved to WP19.

### Dependencies
- Depends on WP05, WP07, WP08. **Estimated prompt size**: ~420 lines.

## Work Package WP19: `next` CLI entry takes the fact (Priority: P0)

**Goal**: `next_cmd.py` validates once through `resolve_owned_or_adopt(NEXT_OWNED_TOPOLOGIES)`, resolves a handle-less run in P, adopts flaglessly, emits `stale_repository_root_copy` in owned runs, and hands the fact to WP11's runtime. Carries #5009 edaa9cd83 and 1be5352ee.
**Independent Test**: through the real `next`: O5 (runtime half; US3-AS1 full-prompt row strict xfail until WP12), O9, the stale copy, the FR-023 pairing, the FR-022 `lanes_with_coord` in-process CLI twin, the FR-003 count of exactly 1, and US3-AS6 (a branch-flip test hook on R between validation and prompt build, proving the validation count stays 1 and every output stays under P).
**Prompt**: `tasks/WP19-next-cli-entry-takes-the-fact.md`
**Requirement Refs**: FR-002, FR-007, FR-008, FR-022, FR-023

### Included Subtasks
T101–T105 (WP19)

### Dependencies
- Depends on WP11, WP08. **Estimated prompt size**: ~330 lines.

## Work Package WP12: Prompt building and unified review base (Priority: P1)

**Goal**: the prompt builder takes the fact, and one topology-agnostic claim-commit helper, `claim_commit_for_wp(mission_dir, wp_id)`, serves every review path. The three subject matchers are deleted.
**Independent Test**: FR-025 non-owned red→green; US3-AS4/AS5; FR-009 prompt governance (a P-only marker reaches the prompt); WP19's strict-xfail US3-AS1 full-prompt row turns green.
**Prompt**: `tasks/WP12-decision-prompt-and-unified-review-base.md`
**Requirement Refs**: FR-008, FR-009, FR-010, FR-025

### Included Subtasks
T064, T065, T068, T069 (WP12)

### Dependencies
- Depends on WP11, WP19. **Estimated prompt size**: ~400 lines.

## Work Package WP13: Atomic finalize-tasks (Priority: P1)

**Goal**: every finalize refusal happens before any write; owned finalize works under `.worktrees/`.
**Independent Test**: lane-cycle refusal leaves `git status --porcelain --ignored` and the ignored files' content hashes unchanged; O6 is green end to end.
**Prompt**: `tasks/WP13-atomic-finalize-tasks.md`
**Requirement Refs**: FR-007, FR-013, FR-015

### Included Subtasks
T070–T074 (WP13)

### Dependencies
- Depends on WP07, WP08. **Estimated prompt size**: ~500 lines.

## Phase 4 — Conversion sweep

## Work Package WP14: Decompose and convert accept (Priority: P2)

**Goal**: `accept()` ≤ 15, its C901 ignore removed, no re-validation, and all owned roots converted.
**Independent Test**: characterisation tests; the existing accept and owned-accept tests stay green.
**Prompt**: `tasks/WP14-decompose-and-convert-accept.md`
**Requirement Refs**: FR-003, FR-022, FR-026

### Included Subtasks
T075–T079 (WP14)

### Dependencies
- Depends on WP07, WP08, WP10 (`ruff.toml` ordering). **Estimated prompt size**: ~500 lines.

## Work Package WP15: Acceptance package conversion (Priority: P2)

**Goal**: convert the `specify_cli/acceptance/*` owned roots to the fact.
**Independent Test**: the `tests/acceptance/` suite stays green.
**Prompt**: `tasks/WP15-acceptance-package-conversion.md`
**Requirement Refs**: FR-001, FR-022

### Included Subtasks
T080–T083 (WP15)

### Dependencies
- Depends on WP04, WP07, WP13, WP14. **Estimated prompt size**: ~300 lines.

## Work Package WP16: Task command conversion (Priority: P2)

**Goal**: `move-task`, `mark-status`, the task helpers, `spec-commit` and `check-prerequisites` consume the fact.
**Independent Test**: the existing owned `move-task`/`mark-status`/`spec-commit` tests are unchanged and green; the commands validate once.
**Prompt**: `tasks/WP16-task-command-conversion.md`
**Requirement Refs**: FR-003, FR-022

### Included Subtasks
T084–T089 (WP16)

### Dependencies
- Depends on WP07, WP08, WP09. **Estimated prompt size**: ~400 lines.

## Work Package WP17: History and support module conversion (Priority: P2)

**Goal**: convert the issue matrix, review cycle, consolidation baseline, commit helpers, read-path resolver and migrations.
**Independent Test**: each module's existing tests stay green.
**Prompt**: `tasks/WP17-history-and-support-conversion.md`
**Requirement Refs**: FR-001, FR-022

### Included Subtasks
T090–T094 (WP17)

### Dependencies
- Depends on WP04, WP07, WP13, WP14, WP15, WP16. **Estimated prompt size**: ~350 lines.

## Phase 5 — Closure

## Work Package WP18: Single-authority gate closure and end-to-end proof (Priority: P0)

**Goal**: commit the gate red, delete every transitional surface (the six shared seams plus every other function marked TRANSITIONAL(WP18)), turn the gate green, and prove SC-001 end to end.
**Independent Test**: `tests/architectural/test_owned_checkout_single_authority.py` goes red→green; the quickstart walkthrough passes with 0 R-snapshot differences.
**Prompt**: `tasks/WP18-gate-closure-and-end-to-end-proof.md`
**Requirement Refs**: FR-001, NFR-001, NFR-002, NFR-003, NFR-005
**Success Criteria closed here**: SC-001 and SC-003 (T098), SC-004 (T095–T097), SC-002 (O1–O10 index, T100), SC-005 (assertion-preservation check, T100)

### Included Subtasks
T095–T100 (WP18)

### Dependencies
- Depends on WP01–WP17 and WP19. **Estimated prompt size**: ~480 lines.

---

## Dependency Graph

```
WP01 → WP02 → {WP04, WP06}
WP04 → WP05 → WP08
{WP04, WP06} → WP07
{WP02, WP08} → WP10
{WP07, WP08} → {WP09, WP13}
{WP05, WP07, WP08} → WP11
{WP08, WP11} → WP19
{WP11, WP19} → WP12
{WP07, WP08, WP10} → WP14
{WP07, WP08, WP09} → WP16
{WP04, WP07, WP13, WP14} → WP15
{WP04, WP07, WP13, WP14, WP15, WP16} → WP17
WP03: independent
all → WP18
```

**Parallel waves**:
1. {WP01, WP03}
2. {WP02}
3. {WP04, WP06}
4. {WP05, WP07}
5. {WP08}
6. {WP09, WP10, WP11, WP13}
7. {WP14, WP16, WP19}
8. {WP12, WP15}
9. {WP17}
10. {WP18}

**MVP**: WP01–WP09 deliver #3449, #4252 and #5026 end to end for status, planning and context. The rest completes the lifecycle, the defect-class closure and the ratchet removal.
