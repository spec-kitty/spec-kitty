# Mission Specification: An explicit run scope for legacy-edge reconciliation

**Mission Branch**: `issue-6728-reconcile-run-scope`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue #6728 — "Replace the Ellipsis sentinel in `legacy_applies_edges` / `_is_legacy_applies` with an explicit run scope" (follow-up from the pre-merge architecture review of `synthesis-record-integrity-01M5ZBC9`, #6456).

## Intent Summary

- **Primary actor:** a maintainer reading or changing the charter synthesis reconciler (`src/charter/activation/synthesizer/reconcile.py`); no end user sees this change.
- **Trigger and outcome:** a reconcile run strips legacy edges. #6456 taught the code that a *full* run and a *topic-scoped* run strip the dead project-intent `requires --> mission_type:*` edge differently. It expressed that difference by adding `dead_edge_regenerated_urns: Collection[str] | None | EllipsisType = ...` to `_is_legacy_applies` and `legacy_applies_edges`, where the sentinel meant "use the same set as `regenerated_urns`". After this mission the run scope is a named, typed value (`RunScope.FULL` / `RunScope.TOPIC_SCOPED`) and no signature in the module defaults to `...`.
- **Invariant (no behaviour change):** for every input the old signatures accepted from a real caller, the edges stripped and the notices emitted are identical. Only the *two* combinations that actually occur stay expressible: full run `(regenerated, dead-edge unfiltered)` and topic-scoped run `(regenerated, dead-edge filtered by the regenerated set)`.
- **Grounding (2026-10-30):** the sentinel is live on `main@512567eee7` (added by #6456, commit `f3b0a864b6`); `git log -S dead_edge_regenerated_urns` returns only that commit; no open or merged PR references #6728, and `docs/changelog/CHANGELOG.md` has no entry for it. Not fixed, not superseded.
- **Scope note:** this is not a bulk edit (`occurrence_map.yaml` at the repo root belongs to #4562 and is untouched); the parameter is removed at six call sites, not migrated across the tree.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The run scope is a name, not a magic literal (Priority: P1)

A maintainer reads `_is_legacy_applies` / `legacy_applies_edges`. Today the parameter `dead_edge_regenerated_urns` has three states (a set, `None`, and `...`), and only two of them are ever passed; the third is a default nobody writes. The maintainer must reconstruct the meaning of `...` from the body (`dead_filter = regenerated_urns if dead_edge_regenerated_urns is ... else ...`).

**Why this priority**: it is the whole issue. Until the scope is named, #6456's distinction is one typo away from drifting silently.

**Independent Test**: `inspect.signature` over the two functions shows a required keyword-only `run_scope` and no parameter whose default is `Ellipsis`; a full run and a topic-scoped run of the same fixture strip the dead edge differently, and the difference is expressed by the two enum members only.

**Acceptance Scenarios**:

1. **Given** `_is_legacy_applies` and `legacy_applies_edges`, **When** their signatures are inspected, **Then** neither has a parameter annotated `EllipsisType` nor defaulted to `...`, and each carries a keyword-only `run_scope: RunScope` that callers must pass.
2. **Given** an overlay carrying the dead `directive:PROJECT_001 --requires--> mission_type:software-dev` edge on a directive the run did not regenerate, **When** the run is `RunScope.FULL`, **Then** the edge is stripped and reported; **When** the same run is `RunScope.TOPIC_SCOPED`, **Then** the edge is kept.
3. **Given** the same overlay on a directive the run *did* regenerate, **When** the run is either scope, **Then** the edge is stripped.

---

### User Story 2 - One spelling of the scope inside the module (Priority: P2)

`merge_project_overlay` already takes `topic_scoped: bool`. The reconciler therefore has two ways to say "this run is topic-scoped" unless the boolean is converted to the typed scope at exactly one point.

**Why this priority**: a second spelling is how the next magic literal gets introduced. It is P2 because the diff is still correct without it, only less obviously so.

**Independent Test**: `merge_project_overlay(topic_scoped=True)` and `legacy_applies_edges(..., run_scope=RunScope.TOPIC_SCOPED)` agree edge-for-edge on one fixture; the modules under `src/` contain exactly one conversion from the boolean to the enum.

**Acceptance Scenarios**:

1. **Given** a fixture with a regenerated and an untargeted legacy edge, **When** `merge_project_overlay(topic_scoped=flag)` runs for both flags, **Then** the surviving edge set equals what `legacy_applies_edges(..., run_scope=RunScope.TOPIC_SCOPED if flag else RunScope.FULL)` classifies as stripped.
2. **Given** a search of `src/` for `RunScope.`, **When** the conversion is located, **Then** it appears once (in `merge_project_overlay`) and `resynthesize_pipeline.py` names the scope explicitly rather than relying on a default.

---

### User Story 3 - #6456's distinction cannot drift unnoticed (Priority: P1)

The #6456 rule — an `applies` edge is stripped only from an owner the run regenerated, in *both* scopes — is the part most likely to be mis-edited while the scope is being named, because it sits in the same function.

**Why this priority**: this is the drift the issue asks to be pinned; a refactor that quietly widens or narrows it changes which stored directive links survive a synthesis run.

**Independent Test**: a fixture with a regenerated and an untargeted synthesized reach-only source is classified identically under `RunScope.FULL` and `RunScope.TOPIC_SCOPED`, and identically to what `merge_project_overlay` does for every `topic_scoped` value.

**Acceptance Scenarios**:

1. **Given** a regenerated synthesized tactic, an untargeted one, and a synthesized styleguide, each with a legacy `applies` edge, **When** a run strips under either scope with `regenerated_urns={regen}`, **Then** exactly the regenerated owner is stripped.
2. **Given** the same fixture with `regenerated_urns=None`, **When** either scope runs, **Then** every synthesized source is stripped (the pre-existing "no filter" behaviour).
3. **Given** a hand-authored (non-synthesized) styleguide with the same edge, **When** either scope runs, **Then** it is never stripped.

### Edge Cases

- `regenerated_urns is None` (no filter) with `RunScope.TOPIC_SCOPED`: the dead-edge filter is also `None`, so the result equals `RunScope.FULL`. This is the old `...`-default behaviour and must stay identical.
- A dead edge whose source is a `PROJECT_*` directive *not* in `synthesized_urns`: governed by the dead-edge rule only (it never needs to be a reach-only kind), in both scopes.
- A caller that omits `run_scope`: a `TypeError` (it is keyword-only and required). No default is reintroduced.
- Another caller in the future wanting a dead-edge filter that is neither `None` nor the regenerated set: no longer expressible; that is the point of the issue (there were only two real combinations) and is recorded here so a future need reopens the design instead of adding a fourth state.
- `reconcile_synthesis`/`_graph_delta` (the delta path) keeps its current behaviour: dead edge unfiltered, which is `RunScope.FULL`.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Typed run scope replaces the sentinel | As a maintainer, I want `_is_legacy_applies` and `legacy_applies_edges` to take a required keyword-only `run_scope: RunScope` so that the run scope is named in the signature instead of encoded as `...`. (#6728) | High | Open | [build] | no — the parameter does not exist on today's code |
| FR-002 | No `Ellipsis` sentinel left in the module | As a maintainer, I want `EllipsisType` gone from `reconcile.py` (import and annotations) and a regression test that fails if an `Ellipsis` default returns to these two signatures. (#6728) | High | Open | [build] | no — `EllipsisType` is imported and defaulted today |
| FR-003 | Full run strips the dead edge wherever it sits | As a maintainer, I want `RunScope.FULL` to keep stripping the dead `PROJECT_* --requires--> mission_type:*` edge on a directive the run did not regenerate, exactly as today's `None`. (#6728, #6456) | High | Open | [ratchet] | yes — green on today's code via `dead_edge_regenerated_urns=None`; paired with FR-004 on one fixture, so a leak between scopes turns it red |
| FR-004 | Topic-scoped run filters the dead edge by the regenerated set | As a maintainer, I want `RunScope.TOPIC_SCOPED` to keep the dead edge of a directive it did not regenerate and strip it when it did, exactly as today's `...` default. (#6728, #6456) | High | Open | [ratchet] | yes — green on today's code via the `...` default; the same fixture as FR-003 proves the two scopes still differ |
| FR-005 | `applies` stripping is scope-independent | As a maintainer, I want the legacy `applies` rule (regenerated owner only, `None` = no filter) to be identical under both scopes so that naming the scope cannot widen or narrow #6456. (#6456) | High | Open | [ratchet] | yes — paired with FR-003/FR-004 on one shared fixture: it is green on both scopes today, and a scope wired into the `applies` branch turns it red while FR-003/FR-004 stay green |
| FR-006 | One conversion from `topic_scoped` to the scope | As a maintainer, I want `merge_project_overlay`'s existing `topic_scoped: bool` mapped to `RunScope` in exactly one place, and `resynthesize_pipeline.py` to pass the scope explicitly, so that the module has one spelling of the scope inside. (#6728) | Medium | Open | [build] | no — the pipeline relies on the sentinel default today |
| FR-007 | Delta path keeps `RunScope.FULL` | As a maintainer, I want `_graph_delta` to pass `RunScope.FULL` explicitly, preserving today's `dead_edge_regenerated_urns=None` behaviour in the reconciliation delta. (#6728) | Medium | Open | [ratchet] | yes — green today with `None`; red if the delta starts filtering by the fresh-node set |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Behaviour unchanged for every existing caller | Every test in `tests/charter/synthesizer/` that passes today passes byte-identically after the change, with only the call sites' scope argument added. | Reliability | High | Open |
| NFR-002 | Static gates clean on touched files | `mypy --strict` (repo config), `ruff check` and `ruff format --check` report zero issues on the touched files; diff coverage on changed lines ≥ 90 %. | Maintainability | High | Open |
| NFR-003 | Complexity does not grow | No touched function exceeds cyclomatic complexity 15, and `_is_legacy_applies` loses a branch (the sentinel ternary) rather than gaining one. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Public bool stays | `merge_project_overlay`'s exported `topic_scoped: bool = False` key word keeps working (it is not the sentinel and is used by tests and the pipeline); only its internals change. | Technical | High | Open |
| C-002 | No new module or package | `RunScope` lives in `reconcile.py` next to `SynthesizeMode`; no new file, no export-widening beyond `__all__`. | Technical | High | Open |
| C-003 | No second authority | The dead-edge filter is derived in one function (the enum member), not re-implemented at each call site. | Technical | High | Open |
| C-004 | No bulk-edit artefact | `occurrence_map.yaml` and the bulk-edit gate are untouched; this is a parameter redesign, not a repository-wide rename. | Technical | Medium | Open |
| C-005 | Terminal state only | No new `Ellipsis`/`...`/`NotImplemented` placeholder: the two scopes are the complete set, and a future third scope is a design change. | Business | Medium | Open |

### Key Entities

- **`RunScope`**: the enum (`FULL`, `TOPIC_SCOPED`) naming how much of the project overlay a reconcile run re-emits; it owns the derivation of the dead-edge filter from the run's regenerated set.
- **`regenerated_urns`**: the owner set a run re-emitted; `None` means "no filter", which predates the scope and is unchanged.
- **Legacy edge**: a `<reach-only kind> --applies--> <directive>` edge on a synthesized artifact (#6404/#6442/#6456), or the dead `directive:PROJECT_* --requires--> mission_type:*` edge (#6443).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `grep -c EllipsisType src/charter/activation/synthesizer/reconcile.py` returns 0, and a test inspecting both signatures finds no `...` default. — [build] · no-op passable: no
- **SC-002**: 100 % of the fixture combinations in the new tests classify their edges identically under `RunScope.FULL`/`RunScope.TOPIC_SCOPED` and under `merge_project_overlay(topic_scoped=False/True)`. — [build] · no-op passable: no
- **SC-003**: The targeted suites (`tests/charter/synthesizer/`, plus `tests/charter/test_project_registration.py`) pass with a test count unchanged except for the added cases, and no existing assertion was edited to keep it green. — [ratchet] · no-op passable: yes — the count and assertions are the check
- **SC-004**: `RunScope` appears in exactly one conversion from `topic_scoped` and in the explicit call sites in `resynthesize_pipeline.py`/`reconcile.py`; no default scope is inferred anywhere. — [build] · no-op passable: no

## Assumptions

- The sentinel's third state (`...`) has no caller other than "use `regenerated_urns`", as #6728 states and this mission re-verified by grep; the two scopes cover every call site.
- The reconciler is internal to `src/charter` (reached from `specify_cli` only through `charter.activation.api`); changing two of its function signatures is not a released-contract change.
- `[ratchet]` rows earn their keep only as paired positive controls on one fixture (the tactic's half-by-half rule); each names its partner.

## Out of Scope

- Any change to *which* edges synthesis writes, strips or reports in production (`suggests` edges, notices, deltas): behaviour is frozen by this mission.
- `_is_dead_mission_type_edge`'s own signature (its `regenerated_urns: Collection[str] | None = None` filter is the primitive the scope feeds, and stays a plain optional set).
- Widening `RunScope` to a third scope, or moving it to a shared module, without a fresh issue.
