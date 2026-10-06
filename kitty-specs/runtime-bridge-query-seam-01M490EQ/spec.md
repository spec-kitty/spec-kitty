# Mission Specification: Extract the runtime_bridge query/answer decision-builder seam

**Mission Branch**: `issue-2560-runtime-bridge-query-seam` (stacked on `issue-2561-retire-runtime-bridge-delegates`, PR #5822)
**Created**: 2026-10-06
**Status**: Draft
**Input**: GitHub issue #2560 plus the orchestrator brief for mission 2 of 3 (#2561 → #2560 → #2562), and the grounding notes in `GROUNDING.md` §"#2560" on `origin/spike/runtime-bridge-grounding-2560-2562`.

## Intent Summary

- **Primary actor**: a Spec Kitty maintainer changing the `spec-kitty next` read path (query mode, answer mode) or the advance path that shares its decision mapping.
- **Trigger**: today the read-side logic (`query_current_state`, `answer_decision_via_runtime` and their builders) and the decision-mapping helpers that both the read path and the advance path use all sit inside `src/runtime/next/runtime_bridge.py` (3,575 LOC on the stacked base). The engine adapter reaches back into the bridge through a deferred import to call two of those helpers.
- **Outcome**: the read path and the decision mapping each have one owning module under `src/runtime/next/`. The engine adapter no longer imports the bridge. Every caller outside the package keeps working unchanged. Behaviour does not change.
- **Invariant**: a test that steers this code by patching a module attribute must patch the module that owns the name. A stale patch must fail loudly (AttributeError) rather than pass while patching nothing.
- **Back-edges**: after the move no `runtime_bridge_*` module imports the bridge (FR-010, added after #5822 merged).
- **Boundary**: #2562 (the engine run-advance dedup, the significance/RACI gap and the `provide_decision_answer` noqa) and every module outside `src/runtime/next/` stay out of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read path has its own module (Priority: P1)

A maintainer debugging `spec-kitty next` without `--result` (query mode) or `--answer` (answer mode) opens one module that holds the whole read path: the query entry, its decision builders, its mission-context and plan-read helpers, and the answer entry.

**Why this priority**: this is the largest coherent cluster still inline in the bridge, and the issue's headline.

**Independent Test**: import the query module directly and drive `query_current_state` / `answer_decision_via_runtime` against a real fixture mission. The same objects are reachable as `runtime.next.runtime_bridge.<name>`.

**Acceptance Scenarios**:

1. **Given** a mission with a started run, **When** `query_current_state` is called through `runtime.next.runtime_bridge`, **Then** it returns the same Decision as before the move (characterisation tests stay green unchanged).
2. **Given** the CLI's `_runtime_bridge_module()` attribute access in `next_cmd.py`, **When** it reads `query_current_state`, `answer_decision_via_runtime`, `QueryModeValidationError` or `MissionNotFoundError`, **Then** it gets the very objects the query module defines (`is` identity).

### User Story 2 - Decision mapping shared without a cycle (Priority: P1)

A maintainer changing how a runtime `NextDecision` maps to a CLI `Decision` (step / WP iteration / decision_required / terminal) finds that mapping in one lower module that both the advance path (bridge, engine adapter) and the read path import. The engine adapter imports it at the top level instead of reaching back into the bridge.

**Why this priority**: without it the query module would need to import the bridge (cycle), and the engine's `_rb` back-edge stays.

**Independent Test**: an import-graph check proves the mapping module imports neither the bridge, the query module, nor the engine adapter; the engine adapter has no import of `runtime.next.runtime_bridge`.

**Acceptance Scenarios**:

1. **Given** the engine adapter's `advance_run_state_after_composition`, **When** it maps a composition-backed advance, **Then** it calls the mapping module's `_map_runtime_decision` / `_is_wp_iteration_step` directly, with no deferred import of `runtime.next.runtime_bridge`.
2. **Given** a test that patches the mapping helper the engine adapter uses, **When** it patches it on the mapping module, **Then** the fake is invoked (the test proves it ran).

### User Story 3 - Stale test patches fail loudly (Priority: P1)

A maintainer whose old test patches `runtime_bridge.<name>` to steer the moved code gets an AttributeError instead of a silent pass.

**Why this priority**: mission 1 (#2561) found exactly this false-green class; a behaviour-preserving move must not create new dead patches.

**Independent Test**: a dead-patch probe run over the test surface reports, for every patch of a `runtime_bridge` attribute, whether the fake ran. Comparing the probe before and after the move shows no patch that ran before and stops running after.

**Acceptance Scenarios**:

1. **Given** a name the bridge no longer uses after the move, **When** a test patches `runtime_bridge.<name>`, **Then** the patch raises AttributeError (the bridge does not keep the import).
2. **Given** a name both the bridge and a moved module still use (e.g. `get_mission_type`, `_compute_wp_progress`, `_state_to_action`), **When** a test patches it on the bridge to steer the moved code, **Then** that test is repointed at the owning module and asserts that its fake ran.

### Edge Cases

- A moved function raises a typed exception the CLI catches by class (`MissionNotFoundError`, `QueryModeValidationError`, `DecisionGitLogUnavailable`): the re-export must be the same class object, or `except` clauses stop matching.
- `next_cmd.py` and tests that install a fake `runtime.next.runtime_bridge` module in `sys.modules` keep working, because only attribute names on the bridge are read.
- A patch that targets a public re-export on the bridge (`runtime_bridge.query_current_state`) still intercepts callers that read it through the bridge (the CLI), but not code inside the query module. Each such patch is reviewed by its call path.
- Architectural gates that name `src/runtime/next/runtime_bridge.py::<function>` by path (the coord-writer census, the write-dir consumer list) must be repointed at the function's new home, never deleted to go green.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Query module owns the read path | As a maintainer, I want `query_current_state`, its four `_build_*query*` builders, the three `_query_*` helpers, `_is_read_path_error` and `answer_decision_via_runtime` defined in one query module under `src/runtime/next/`, so that the read path has one owner. | High | Open | [build] | no — the move is checked by asserting each name's `__module__` / defining file |
| FR-002 | Mapping module owns the shared decision mapping | As a maintainer, I want `_materialize_decision`/`_prompt_exists`, the `_map_*` mappers, `_build_decision_required_prompt_file`, the WP-board family, `_wp_iteration_action_and_state`, `_build_wp_iteration_decision`, `_is_wp_iteration_step`, the merged-mission and finalized-board short-circuits (with `_count_wp_endings`, `_has_claimable_planned_wp`) and `_wp_task_surface_error` defined in one lower mapping module, so that the read and advance paths share it without an import cycle. | High | Open | [build] | no — asserted by defining module and by the import-graph check in FR-004 |
| FR-003 | Public names stay plain re-exports | As a CLI caller, I want `query_current_state`, `answer_decision_via_runtime`, `QueryModeValidationError`, `MissionNotFoundError` and `DecisionGitLogUnavailable` importable from `runtime.next.runtime_bridge` as the same objects the owning modules define, with no forwarding function, so that callers outside the package do not change. | High | Open | [ratchet] | no — an `is`-identity test fails if a delegate or a copy replaces the re-export |
| FR-004 | No new cycle; engine back-edge removed | As a maintainer, I want the mapping module to import neither the bridge, the query module nor the engine adapter, the query module not to import the bridge, and the engine adapter to call the mapping module directly with no import of `runtime.next.runtime_bridge`, so that the dependency direction is bridge → query → mapping and engine → mapping. | High | Open | [build] | no — an AST import check over the live files fails on any such edge, with a planted-edge mutation test |
| FR-005 | Unused bridge imports dropped | As a maintainer, I want every import the bridge no longer uses after the move removed from `runtime_bridge.py`, so that a stale `runtime_bridge.<name>` patch raises AttributeError. | High | Open | [build] | no — ruff F401 plus the dead-patch probe in FR-006 |
| FR-006 | Shared-name patches repointed with proof | As a maintainer, I want every test patch of a `runtime_bridge` attribute that steers moved code repointed at the owning module, and each repointed test to assert that its fake ran, so that no false-green patch survives the move. | High | Open | [build] | no — the before/after dead-patch probe lists each patch that stopped running; that list must be empty |
| FR-007 | Characterisation before the move | As a maintainer, I want moved functions whose current test coverage leaves branches unexercised to get characterisation tests through the public entry points before the move, so that the move is proven behaviour-preserving. | High | Open | [ratchet] | yes — characterisation tests pass on both sides by design; paired with FR-001/FR-002 which do fail on a no-op |
| FR-008 | Decision-log wrapper placement decided and recorded | As a maintainer, I want `_wrap_with_decision_git_log` and its coordination helpers placed where both the bridge's advance path and the query module's answer path can import them without a cycle or a deferred bridge import, with the reason recorded in the plan, so that the choice is reviewable. | Medium | Open | [build] | no — FR-004's import check covers the chosen module |
| FR-009 | Path-pinned gates follow the move | As a maintainer, I want every architectural gate entry that names a moved function by `runtime_bridge.py` path repointed at the new file, so that the gates keep scanning the live code. | Medium | Open | [ratchet] | no — the gates' own live-definition floors fail on a stale path |
| FR-010 | No seam reads the bridge | As a maintainer, I want the last seam→bridge back-edges removed (io's deferred reads of `_resolve_runtime_feature_dir` and the guard facts, composition's deferred read of `_should_advance_wp_step`) by moving those names to modules below the bridge, so that no `runtime_bridge_*` module imports `runtime_bridge` at all. Added 2026-10-06 on orchestrator direction after #5822 merged (its Deferred section hands these back-edges to #2560). | High | Open | [build] | no — the layout gate asserts the empty set of bridge imports across every `runtime_bridge_*` module, with a planted-edge mutation test |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bridge shrinks | `runtime_bridge.py` loses at least 1,000 LOC versus the stacked base (3,575 LOC). | Maintainability | High | Open |
| NFR-002 | Complexity ceiling | Every function in a new or changed module has cyclomatic complexity ≤ 15 (ruff C901); no new `noqa`. | Maintainability | High | Open |
| NFR-003 | Static checks clean | `ruff check`, `ruff format --check --force-exclude` on changed files report 0 issues; mypy over `src/runtime/next/` reports no error beyond the 21 present on the base. | Maintainability | High | Open |
| NFR-004 | Test surface green | The targeted surface (every test file referencing `runtime_bridge`, plus `tests/runtime`, `tests/next`, `tests/specify_cli/next`, plus the implicated architectural gate files) passes, except failures that also fail on the base and are recorded as environmental/pre-existing. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Behaviour-preserving | No observable behaviour change: same Decision fields, same exceptions, same events, same git-log commits. One accepted, recorded delta: log records from moved code carry the new module's logger name (plan "Accepted deltas"). | Technical | High | Open |
| C-002 | Stay in the package | Source changes stay inside `src/runtime/next/`; test changes stay in tests of that code and the named architectural gates. No change to mission-create, consolidation or lanes code. | Technical | High | Open |
| C-003 | No delegates | No forwarding delegate or self-alias is reintroduced in `runtime_bridge.py`; re-exports are plain imports. | Technical | High | Open |
| C-004 | Layer rules shrink-only | The `runtime` outbound ledger and layer rules are not widened. | Technical | High | Open |
| C-005 | Sibling naming | New modules are named `runtime_bridge_<name>.py` under `src/runtime/next/`. | Technical | Medium | Open |
| C-006 | #2562 out of scope | The engine run-advance dedup, the significance/RACI gap and the `provide_decision_answer` noqa are not touched. | Business | High | Open |
| C-007 | Stacked branch | The branch is stacked on #5822 and merges after it; the mission-1 branch is never rewritten or pushed. | Business | High | Open |

### Key Entities

- **Bridge (`runtime_bridge.py`)**: the residual advance path (`decide_next_via_runtime` and its `_dn_*` phases, the CLI guards) plus the public re-exports.
- **Query module**: the read path — query mode and answer mode entries and their private builders.
- **Mapping module**: the decision mapping shared by the advance and read paths — Decision materialisation, runtime-to-CLI decision mappers, the WP-board / WP-iteration resolution, and the merged / finalized-board short-circuits.
- **Decision-log wrapper**: the coordination-aware wrapper that commits decision-log events to git; used by the advance path and the answer path.
- **Dead patch**: a test patch of a module attribute whose fake is never invoked by the code under test.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `runtime_bridge.py` is at most 2,575 LOC — [build] · no-op passable: no
- **SC-002**: `grep -n "import runtime_bridge\b" src/runtime/next/runtime_bridge_engine.py` finds nothing — [build] · no-op passable: no
- **SC-003**: The before/after dead-patch probe lists zero patches that ran before the move and stopped running after it — [build] · no-op passable: yes — paired with the probe's own positive control (a planted dead patch is reported)
- **SC-004**: The targeted test surface has no failure that is not also present on the stacked base — [ratchet] · no-op passable: yes — paired with SC-001/SC-002

## Assumptions

- PR #5822 (mission 1) merged into `main` on 2026-10-06 (rebased and compacted by the landing pass); this branch was rebased onto `main` with `--onto`, dropping the pre-merge #5822 commits. The landing pass added `tests/runtime/test_bridge_no_compat_delegates.py`, the canonical no-forwarder / no-back-edge gate, which this mission extends.
- Known environmental reds (`tests/runtime/test_reassess_under_lock.py` on a dirty worktree; the "Unknown mission type None" test-order pollution between `test_composition_success_skips_legacy_dispatch` and `test_next_advance_first_contact_5310.py` / `test_next_command_integration.py` in one `-n0` process) reproduce on the base and are not fixed here.
