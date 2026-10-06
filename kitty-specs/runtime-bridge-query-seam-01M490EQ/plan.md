# Implementation Plan: Extract the runtime_bridge query/answer decision-builder seam

**Branch**: `issue-2560-runtime-bridge-query-seam` (stacked on #5822) | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/runtime-bridge-query-seam-01M490EQ/spec.md`

## Summary

Split `src/runtime/next/runtime_bridge.py` (3,575 LOC on the stacked base) along its read/advance fault line. Three new sibling modules, each with one owner:

1. **`runtime_bridge_decision_mapping.py`** (lower): runtime-`NextDecision` → CLI-`Decision` mapping shared by the advance path, the engine adapter and the read path.
2. **`runtime_bridge_decision_log.py`** (side): the coordination-aware decision-log wrapper used by both the advance path and the answer path.
3. **`runtime_bridge_query.py`** (upper): the read path — query mode and answer mode.

The bridge keeps the advance path (`decide_next_via_runtime` + `_dn_*`, CLI guards) and re-exports the public names as plain imports. The engine adapter imports the mapping module at the top level, which removes its deferred `_rb` back-edge. Behaviour is unchanged.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: none new; internal modules under `src/runtime/next/` only
**Storage**: N/A (run state under `.kittify/runtime/` is untouched)
**Testing**: pytest (+xdist, `--dist loadfile`); characterisation tests through the public entries; a module-layout test (defining module, re-export identity, import graph with a planted-edge mutation); a scratch dead-patch probe run before/after (not committed)
**Target Platform**: the `spec-kitty` CLI
**Project Type**: single
**Performance Goals**: no change (pure code move; import time unchanged within noise)
**Constraints**: behaviour-preserving (C-001); `src/runtime/next/` only (C-002); no delegates (C-003); layer rules shrink-only (C-004)
**Scale/Scope**: ~1,500 LOC moved out of the bridge; ~10 test files repointed

## Charter Check

| Charter rule | How this plan meets it |
|---|---|
| Single canonical authority | Each moved name is defined in exactly one module; the bridge re-exports public names as the same objects; `TASKS_GLOB` gets one owner (mapping). |
| Architectural alignment | Follows the sibling convention `runtime_bridge_<name>.py`; dependency direction bridge → query → mapping, engine → mapping; no new back-edge into the bridge. |
| ATDD-first / SO #4 red-first | The module-layout test is written first and fails on the base (names still defined in the bridge, engine still imports the bridge); characterisation tests land before each move where coverage is thin. |
| SO #1 adversarial squad | Advisory squad at the plan point-cut (architecture + test-integrity lenses); findings folded below in "Squad findings". |
| SO #2 campsite | The bridge's header comment block (#2531 decomposition map) is rewritten for the new layout; stale "KEEP-IN-PLACE" notes about `_wrap_with_decision_git_log` are removed. |
| SO #3 tracer files | Seeded under `traces/`; appended during implement. |
| SO #5 gate discipline | The layout test has a concrete floor (named symbols) and a self-mutation test (a planted bridge import in a temp copy of the engine is flagged). No allowlist. |
| SO #8 mission hygiene | Issue-matrix row for #2560; mission-opening comment posted; implementer ≠ reviewer. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Targeted surface + named gate files only. |

## Design decisions

### D-1 — Two-layer split, not one "query" module

The query/answer cluster depends on helpers the advance path also uses (grounding §#2560). The engine adapter also calls `_map_runtime_decision` / `_is_wp_iteration_step`. A single query module would either import the bridge (cycle) or force the bridge's advance path to import the query module for its mapping. Splitting off a lower mapping module gives one import direction: bridge → query → mapping; bridge → mapping; engine → mapping.

**Mapping module gets**: `_prompt_exists`, `_materialize_decision`, `TASKS_GLOB`, `_WP_ITERATION_STEPS`, `_is_wp_iteration_step`, `_has_claimable_planned_wp`, `_finalized_task_board_override_step`, `_reduced_wp_lane`, `_count_wp_endings`, `_MERGED_MISSION_DONE_REASON`, `_merged_mission_short_circuit`, `_WpIterationResolution`, the WP-board family (`_WpBoardAction`, `_WP_BOARD_DECLINE`, `_inspect_board_recovery_command`, `_wp_blocked_action`, `_wp_task_surface_error`, `_wp_dispatch_action`, `_resolve_wp_board_implement_action`, `_resolve_wp_board_review_action`, `_resolve_wp_board_action`), `_wp_iteration_action_and_state`, `_build_wp_iteration_decision`, `_build_decision_required_prompt_file`, `_map_wp_step_decision`, `_map_non_wp_step_decision`, `_map_runtime_decision`.

**Stays in the bridge** (advance-path only): `_should_advance_wp_step`, `_wp_blocks_step`, the CLI guards, `_resolve_runtime_feature_dir`, `_resolve_planned_wp_workspace` (only `_dn_*` callers), `_resolve_owned_coordination_workspace` / `_is_transient_git_worktree_contention` (external caller `coordination/coord_seed.py` imports them from the bridge; out of scope, C-002), `DecideNextContext`, `_owned_coordination_unavailable_decision`, `decide_next_via_runtime` and every `_dn_*`.

`_merged_mission_short_circuit` and `_finalized_task_board_override_step` are short-circuits that produce a Decision, used by both `decide_next_via_runtime` and `query_current_state`; they sit with the mapping because both entries need them and they depend on nothing above it.

### D-2 — `_wrap_with_decision_git_log` gets its own module

Options considered:

| Option | Verdict |
|---|---|
| Move into `runtime_bridge_identity.py` | Rejected. Identity is a leaf (imports nothing in `runtime.next`) and `runtime_bridge_io.py` imports it at the top level. The wrapper calls `_io_seam.resolve_commit_target`, so identity would have to import io: an io ↔ identity cycle. |
| Keep in the bridge; the query module reaches it through a deferred `from runtime.next import runtime_bridge` | Rejected. It re-creates the `_rb` back-edge pattern mission 1 (#2561) just removed and that this mission removes from the engine. A test patching it would again have to know which module the lookup goes through. |
| Move into `runtime_bridge_io.py` | Rejected. The io seam is already 1,578 LOC and owns narrow I/O ports; the wrapper is coordination policy (topology routing, owned-checkout refusal mapping, commit-target choice), not a port. |
| **New `runtime_bridge_decision_log.py`** | **Chosen.** Holds `DecisionGitLogUnavailable`, `_mission_routes_through_coordination`, `_is_owned_coordination_unavailable`, `_wrap_with_decision_git_log`. It imports identity + io (both already below it) and is imported by the bridge (`_dn_bootstrap`) and the query module (`answer_decision_via_runtime`). No cycle, no deferred bridge import. |

`_is_owned_coordination_unavailable` moves with it because the wrapper calls it; the bridge's `_dn_bootstrap` calls it on the new module.

`runtime_bridge_io.resolve_commit_target` raises `DecisionGitLogUnavailable` through a deferred `from runtime.next.runtime_bridge import DecisionGitLogUnavailable` (`runtime_bridge_io.py:1564`). That deferred import is repointed at `runtime_bridge_decision_log`. It stays deferred, because decision_log imports io at the top level, but it no longer reaches into the bridge (squad A-3). Moving `resolve_commit_target` itself is out of scope: io owns it and `tests/runtime/test_bridge_io.py` pins it.

### D-3 — Public names are plain re-exports

`from runtime.next.runtime_bridge_query import MissionNotFoundError, QueryModeValidationError, answer_decision_via_runtime, query_current_state` and `from runtime.next.runtime_bridge_decision_log import DecisionGitLogUnavailable` at the bridge's top level. `__all__` is unchanged (8 names). No wrapper function (C-003). `next_cmd.py` reads them by attribute on the bridge module, `decision_verbs.py` and others import them by name: both keep working with the identical objects. `test_no_dead_symbols` keeps recognising the 4 façade names through the `_runtime_bridge_module()` call sites.

### D-4 — Seam calls through module aliases

Matching the existing siblings, the bridge calls moved names as `_mapping.<name>`, `_query.<name>` and `_decision_log.<name>`, and keeps no self-alias. Consequence: a test that patches `runtime_bridge.<moved name>` raises AttributeError (loud). The bridge drops every import it no longer uses (FR-005), so a patch of an imported name only the moved code used is also loud.

### D-5 — False-green control: dead-patch probe

A scratch pytest plugin (kept out of the repo) records every `monkeypatch.setattr` / `mock.patch` / `mock.patch.object` on a `runtime.next.runtime_bridge*` module and whether its fake was invoked. It runs over the whole targeted surface on the stacked base (baseline) and again after the move. It records a call **count** per patch, not a ran/didn't-run bit, because one patch can steer two callers (the bridge's `_dn_bootstrap` and a moved callee) and stop reaching only one of them (squad T-2). Any `(test, patched name)` whose call count drops after the move is a false green created by the move and is repointed at the owning module, with an assertion that the fake ran. The probe cannot see a patch that is never meant to run (`_raising` fakes, `assert_not_called`, `== []` checks), so it is paired with a **static cross-check** (squad T-4). An AST pass computes the go-silent set S: names the moved code reads that the slimmed bridge still binds (`get_mission_type`, `_compute_wp_progress`, `_state_to_action`, `_build_prompt_or_error`, `now_utc_iso`, `runtime_emitter_for_mission`, `seed_runtime_emitter`, `is_acceptable_ending`, `Lane`, `logger`, `_io_seam`, `_engine_adapter`, `_cores`). A scan of the tests then finds every patch of a name in S on the bridge, and each hit gets a recorded disposition (live via a kept bridge caller, or repointed) in `research.md` R-6, whatever the probe says. When a test's import of a moved private name is repointed, every patch in the same `with` block is reviewed with it, and each repointed patch gets a "fake ran" assertion (squad T-1). Patches that were already dead on the base are listed and fixed when they are in the touched test files (campsite), or listed under Deferred otherwise.

### D-6 — Gates that name moved code by path

- `tests/architectural/test_no_write_side_rederivation.py`: the coord-writer census pair `("src/runtime/next/runtime_bridge.py", "_wrap_with_decision_git_log")` and the `_WRITE_DIR_CONSUMER_MODULES` entry are repointed at `runtime_bridge_decision_log.py` (the bridge stays in the consumer list only if it still consumes `write_dir`).
- `tests/architectural/test_runtime_emitter_seam.py` S8: the "seam obtained only through the factory" check covers `_dn_bootstrap` in the bridge and `answer_decision_via_runtime` in the query module (both files must import the factory by name and never construct the Protocol).
- `tests/architectural/test_coord_read_residuals_closeout.py`: the floor counts `get_mission_type(feature_dir)` reads across `src/runtime/next/`; moving reads between files in that directory keeps the count. Docstrings naming `runtime_bridge.py` line numbers are updated if they mention moved reads.
- `tests/architectural/test_runtime_emitter_seam.py` F7 (bypass needles): scans the bridge's `_dn_*`. Those stay in the bridge, so the check keeps covering them. The answer path builds `answer_emitter` through `_wrap_with_decision_git_log`, which S8's extension covers.
- `tests/runtime/test_bridge_decision_builder.py` (squad T-6): the bare-`_materialize_decision` call count and the "zero raw `Decision(...)`" scan read only the bridge's source. Both are extended to the bridge plus the three new modules, so the property still covers the moved code. Without this, the count test fails loudly at 0.
- `tests/architectural/test_no_write_side_rederivation.py:131`: once the wrapper moves, the bridge no longer calls `write_dir`, so the bridge entry in `_WRITE_DIR_CONSUMER_MODULES` is **replaced** by `runtime_bridge_decision_log.py` (squad A-5).
- `tests/architectural/test_coord_read_residuals_closeout.py:541,549` filter offenders on the substring `"runtime_bridge.py"`. That is widened to the `runtime_bridge` file prefix so the moved `get_mission_type` reads stay covered by the "clean, not pinned" check (squad T-6).
- `tests/architectural/test_no_dead_symbols.py`: run, because the new modules declare names that must be recognised live.
- `tests/architectural/test_read_surface_placement_guard.py:328`: its docstring names the bridge as a `read_dir` consumer, which was already stale. It is reworded while repointing (campsite).
- `tests/architectural/test_topology_inference_retired.py`: the bridge stays in the "formerly deriving modules" list; the new modules are inside `src/` and covered by the all-`src/` scan.

### D-7 — Remaining back-edges and the canonical gate (added after #5822 merged)

#5822's landing pass made `tests/runtime/test_bridge_no_compat_delegates.py` the canonical gate against forwarders and seam→bridge back-edges. Its Deferred section hands the remaining back-edges to #2560, and the orchestrator confirmed that:

- **`runtime_bridge_guards.py` (new)** owns the guard facts io reads (`_check_requirement_mapping_ready`, `_check_bare_prose_requirements_ready`, `_occurrence_gate_failures`, `_has_raw_dependencies_field`, with `_load_wps_manifest_findings`, the two `_log_requirement_extraction_warnings*` helpers, `SPEC_ARTIFACT`, `TASKS_ARTIFACT`) and the WP-advance guard composition reads (`_should_advance_wp_step`, `_wp_blocks_step`). It imports mapping and cores and never io, the bridge, composition or the engine. io and composition then import it at the top level, and their deferred `_rb` imports go away.
- **`_resolve_runtime_feature_dir` moves to `runtime_bridge_identity.py`.** That module already owns primary-feature-dir resolution and is a leaf whose resolver imports are function-local. `decision.py`'s deferred import of it points at identity.
- **`_check_cli_guards` stays in the bridge.** It is advance-path guard composition over io's fact port and the guards module.
- **Gates.** The canonical gate gets rows for the moved names, grouped by owning seam (decision_mapping, decision_log, query, guards, identity). The layout gate keeps ownership and import direction, and adds the invariant that no `runtime_bridge_*` module imports `runtime_bridge`. The no-delegate and no-attribute rows that the canonical gate now covers are removed from the layout gate, so each property has one authority.
- **Out of scope.** Making the underscore seam names public (#5822 Deferred note). This mission keeps the convention the bridge docstring documents and records the suggestion under Deferred.

## Project Structure

### Documentation (this mission)

```
kitty-specs/runtime-bridge-query-seam-01M490EQ/
├── spec.md
├── plan.md              # this file
├── research.md          # dependency map + baseline evidence
├── data-model.md        # module ownership table
├── quickstart.md        # how to verify the split
├── contracts/
│   └── module-layout.md # the import-direction + re-export contract
├── traces/              # tracer files
└── tasks.md             # /spec-kitty.tasks output
```

### Source Code (repository root)

```
src/runtime/next/
├── runtime_bridge.py                     # advance path + public re-exports (shrinks)
├── runtime_bridge_decision_mapping.py    # NEW — shared decision mapping (lower)
├── runtime_bridge_decision_log.py        # NEW — decision-log wrapper (side)
├── runtime_bridge_query.py               # NEW — query + answer read path (upper)
├── runtime_bridge_engine.py              # drops the deferred bridge import; imports mapping
└── (identity / io / cores / composition / retrospective unchanged)

tests/runtime/
└── test_bridge_query_seam_layout.py      # NEW — FR-001..FR-004 layout + import-graph contract
tests/next/, tests/runtime/, tests/specify_cli/next/, tests/integration/ …
                                          # patches repointed at owning modules
tests/architectural/
├── test_no_write_side_rederivation.py    # census path repointed (D-6)
└── test_runtime_emitter_seam.py          # S8 follows answer_decision_via_runtime (D-6)
```

**Structure Decision**: single project; three new sibling modules under `src/runtime/next/`, named per the existing `runtime_bridge_<name>.py` convention (C-005).

## Complexity Tracking

No charter violation. One new module more than the issue suggested (decision-log), justified in D-2.

## Implementation Concern Map

### IC-01 — Characterisation + probe baseline

- **Purpose**: pin the observable behaviour of every moved function whose branches the current suite leaves unexercised, and record the dead-patch baseline, before any code moves.
- **Relevant requirements**: FR-007, FR-006 (baseline half)
- **Affected surfaces**: tests under `tests/runtime/`, `tests/next/`
- **Sequencing/depends-on**: none
- **Risks**: characterisation tests that patch `runtime_bridge.<name>` would themselves become false greens after the move; they drive public entries with real fixtures and patch nothing on the bridge.

### IC-02 — Decision-mapping module + engine back-edge removal

- **Purpose**: create the lower mapping module, move the shared mapping names, point the bridge and the engine adapter at it.
- **Relevant requirements**: FR-002, FR-004, FR-005 (partial)
- **Affected surfaces**: `runtime_bridge.py`, `runtime_bridge_decision_mapping.py`, `runtime_bridge_engine.py`; tests patching `_is_wp_iteration_step`, `_map_runtime_decision`, `_wp_iteration_action_and_state`, `_build_wp_iteration_decision`, `_resolve_wp_board_action`, `_count_wp_endings`, `_materialize_decision`, `_prompt_exists`, `_merged_mission_short_circuit`, `_finalized_task_board_override_step`, `_map_wp_step_decision`
- **Sequencing/depends-on**: IC-01
- **Risks**: the engine's deferred import exists because of a cycle; the mapping module must import neither the engine nor the bridge (checked by the layout test).

### IC-03 — Decision-log module

- **Purpose**: move the decision-log wrapper and its coordination helpers to their own module (D-2).
- **Relevant requirements**: FR-008, FR-009 (write-side census)
- **Affected surfaces**: `runtime_bridge.py`, `runtime_bridge_decision_log.py`, `tests/architectural/test_no_write_side_rederivation.py`; tests patching `_wrap_with_decision_git_log`, `_mission_routes_through_coordination`
- **Sequencing/depends-on**: IC-02
- **Risks**: `DecisionGitLogUnavailable` is caught by class outside the package; the re-export must be the same class.

### IC-04 — Query module + public re-exports

- **Purpose**: move the read path, re-export the public names from the bridge, drop the bridge imports nothing uses any more.
- **Relevant requirements**: FR-001, FR-003, FR-005, FR-009 (emitter seam S8)
- **Affected surfaces**: `runtime_bridge.py`, `runtime_bridge_query.py`, `tests/architectural/test_runtime_emitter_seam.py`; tests patching `query_current_state`'s collaborators
- **Sequencing/depends-on**: IC-02, IC-03
- **Risks**: the largest false-green exposure (`get_mission_type`, `_compute_wp_progress`, `runtime_provide_decision_answer`, `runtime_emitter_for_mission`, `load_mission_template_file`, `get_or_start_run`).

### IC-06 — Guards module + identity: last back-edges

- **Purpose**: move the guard facts and the WP-advance guard to `runtime_bridge_guards.py`, and `_resolve_runtime_feature_dir` to identity, so no seam imports the bridge (D-7).
- **Relevant requirements**: FR-010, FR-004, FR-006
- **Affected surfaces**: `runtime_bridge.py`, `runtime_bridge_guards.py` (new), `runtime_bridge_identity.py`, `runtime_bridge_io.py`, `runtime_bridge_composition.py`, `runtime.next.decision`; `tests/runtime/test_bridge_no_compat_delegates.py`; tests that patch the moved names
- **Sequencing/depends-on**: IC-04
- **Risks**: io's fact port and composition's guard read those names at call time through `_rb`. After the move they must read them on the guards module, so a test that patched `runtime_bridge.<guard>` to steer io's fact port must now patch the guards module (loud: the name leaves the bridge).

### IC-05 — False-green sweep + layout contract + docs

- **Purpose**: run the probe after the move, repoint every patch that stopped running with a "fake ran" assertion, finish the layout test, and rewrite the bridge/engine header docs for the new layout.
- **Relevant requirements**: FR-006, FR-004 (mutation test), NFR-001..NFR-004
- **Affected surfaces**: tests named by the probe diff; `runtime_bridge.py` / `runtime_bridge_engine.py` module docstrings
- **Sequencing/depends-on**: IC-06
- **Risks**: a repointed patch that now intercepts may change which branch a test exercises; each is checked against the test's intent, not just made green.

## Accepted deltas under C-001

- **Logger names.** Moved code that logs through the module `logger` (`_wrap_with_decision_git_log`, `_query_*`) or through `logging.getLogger(__name__)` (`answer_decision_via_runtime`) now logs under `runtime.next.runtime_bridge_decision_log` / `runtime.next.runtime_bridge_query` instead of `runtime.next.runtime_bridge`. Message text and level do not change. Logger names are not a documented contract. No test filters on the bridge logger name for moved code (squad T-7 checked). Records still reach handlers on the `runtime.next` / root loggers. This delta is accepted and recorded, so it is not hidden.

- **Doc-only rewording in moved code.** `runtime_bridge_identity._resolve_runtime_feature_dir`'s "boundary-safe fold-in" paragraph was reworded for its new home: the bridge, not identity, is the module that already imports `_read_path_resolver`. Text only (WP06 review nit 3).

## Squad findings (plan point-cut, advisory)

Two profile-loaded lenses ran on 2026-10-06: architect-alphonso (architecture / import graph) and reviewer-renata (test integrity). Dispositions:

| # | Finding | Severity | Disposition |
|---|---|---|---|
| A-1 | No import cycle for mapping / decision_log / engine → mapping (checked by import in a fresh interpreter) | holds | — |
| A-2 | D-1 partition is closed; layout test should state the full allowed DAG, incl. engine ↛ query | note | Folded: `_FORBIDDEN_IMPORTS[engine]` includes query |
| A-3 | io → bridge deferred import of `DecisionGitLogUnavailable` survives the move | should-fix | Folded into D-2: repoint at decision_log |
| A-4 / T-7 | Logger names change for moved code | should-fix | Folded: accepted delta, recorded above |
| A-5 | Gates D-6 missed (F7 scope, no_dead_symbols, write-dir consumer replace, read-surface docstring) | should-fix | Folded into D-6 |
| A-6 | Layer ledger keyed by subpackage; unaffected | holds | — |
| A-7 | External private importers only use names that stay | holds | — |
| A-8 | composition → bridge (`_should_advance_wp_step`) and io → bridge (`_resolve_runtime_feature_dir`, guard helpers) back-edges remain | note | Recorded as Deferred in the PR; FR-004's "no back-edge" is scoped to the engine |
| T-1 | Repointing a moved-name import leaves sibling `_state_to_action` / `_build_prompt_or_error` patches dead (`test_runtime_bridge_blocked_paths.py`, `test_prompt_file_invariant.py`) | blocking | Folded into D-5: same-`with`-block review, plus a "fake ran" assertion |
| T-2 | Mixed patches (one live caller, one moved) invisible to a ran-bit probe | blocking | Folded: the probe compares call counts |
| T-3 | Query/answer tests go silent (`test_query_mode_unit.py` `_compute_wp_progress`; `test_runtime_bridge_unit.py:622/626` + negative `emitter_calls == []`) | should-fix | Folded into IC-05 via the static cross-check |
| T-4 | The probe cannot see never-meant-to-run patches | blocking | Folded into D-5: static cross-check over S with a per-hit disposition |
| T-5 | Probe hook points; `sys.modules` fakes; `raising=False` / `create=True` | should-fix | Already hooked at `_patch.__enter__` and the string form. `sys.modules` fakes stay valid because `next_cmd` resolves the bridge by name. No `raising=False` / `create=True` on `runtime_bridge*` today; noted |
| T-6 | Source-text gates in `test_bridge_decision_builder.py` and `test_coord_read_residuals_closeout.py` | should-fix | Folded into D-6 |
| T-9 | IC-01 gaps | should-fix | Folded into IC-01 (list below) |

**IC-01 characterisation targets** (baseline coverage over the 111-path surface found 8 moved functions with missed lines). Everything is driven through public entries or pure functions, with patches only on the owning module or below:
`_build_decision_required_prompt_file` (`question=None` → None, success → path string, builder raises → None); `answer_decision_via_runtime` (the missing-feature-dir branch asserts the exact "cannot answer decision" text, and the `ActionContextError` re-raise keeps the typed code); `_query_read_runtime_plan`'s `QueryModeValidationError` re-raise; the `query_current_state` blocked-query branch on a task-surface error, plus removal of its temporary run store; `_resolve_wp_board_action` (`ActionContextError` → decline, `accept`/`done` → decline, unknown board step → decline); `_count_wp_endings` (no `tasks/` → `(0, 0)`); `_reduced_wp_lane(None)`; `_resolve_wp_board_review_action`'s re-read race; `_wrap_with_decision_git_log`'s owned-caller re-raise of `CoordinationWorkspaceUnavailable`.
