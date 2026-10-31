# Implementation Plan: Enforce the implementation-commit review prerequisite from the `code_producing` capability

**Branch**: `issue-6328-code-producing-review-gate` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/issue-6328-code-producing-review-gate-01M68ZQ1/spec.md`

**Branch contract (from `setup-plan`)**: current branch `issue-6328-code-producing-review-gate`;
planning/base branch `issue-6328-code-producing-review-gate`; merge target
`issue-6328-code-producing-review-gate`; `branch_matches_target = true`.

## Summary

The review-readiness pre-flight (`_validate_ready_for_review`, Check 2) applies its
worktree-state prerequisite — including "an implementation commit exists" — only
when `mission_type == MISSION_TYPE_SOFTWARE_DEV`. Replace that family-name literal
with the mission type's `code_producing` capability, which this mission also adds
(the unlanded `#6327` prerequisite) as a lazy, memoised facet on
`ResolvedMissionType` with a public accessor on `charter.activation.api`.

Technical approach: mirror the `requires_substantive_spec` capability that `#6315`
already shipped — authored `bool | None` field on the charter-offering
`MissionType` DTO, one built-in default map, a resolver that prefers the declared
value and falls back to that map, a `cached_property` behind a thunk so the FSM
hot path triggers no extra roster read, and a `*_for(repo_root, mission_type)`
public accessor that swallows resolution errors and returns the built-in default.
The consumer then calls the accessor instead of comparing the family name.

## Technical Context

**Language/Version**: Python 3.11+ (repo `pyproject.toml`; `uv run`)
**Primary Dependencies**: pydantic v2 (`MissionType` is a frozen `BaseModel` with
`extra="forbid"`), Typer/rich for the CLI surface — all already in the tree, no new
dependency
**Storage**: YAML mission-type descriptors under
`src/charter/offering/missions/mission_types/`, resolved through the layered
(built-in / org / project) `PackContext`; no database
**Testing**: pytest. Red-first unit tests at the two seams (capability resolution;
review-readiness pre-flight) plus the built-in-parity ratchet
**Target Platform**: the `spec-kitty` CLI, cross-platform (Linux/macOS/Windows)
**Project Type**: single project — one Python package tree (`src/`), split into the
`charter.*` governance packages and the `specify_cli.*` / `mission_runtime` / `lanes`
runtime packages
**Performance Goals**: the capability must not add a read to the FSM hot path;
`resolve_mission_type_context(...).action_sequence` stays a single layered-roster
read (the NFR-001 100 ms budget named in that module's docstring)
**Constraints**: `specify_cli` may reach the capability only through
`charter.activation.api`; `MissionType` is `extra="forbid"` so the new field must be
declared, not smuggled through; `_validate_ready_for_review`'s collaborator signature
is a live monkeypatch contract and must not gain a required parameter
**Scale/Scope**: 5 files in `src/` (2 charter, 1 charter API re-export, 1 CLI
consumer, plus the built-in YAML mission-type descriptors only if a default needs
authoring — it does not, the built-in defaults live in the map) and 3 test files.
No contract change to any external/HTTP surface.

## Charter Check

*GATE: re-checked after Phase 1 design. Result: **pass**, no violations.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority (`DIRECTIVE_044`) | One built-in default map (`BUILTIN_CODE_PRODUCING`) beside `BUILTIN_REQUIRES_SUBSTANTIVE_SPEC`, one resolver, one public accessor. No second list of "types that produce code" anywhere, and the consumer-side literal is deleted rather than shadowed. |
| Architectural alignment (`DIRECTIVE_001`) / Internal Runtime Boundary | The CLI consumes `charter.activation.api`, never `charter.activation.mission_type_profiles`. This is the boundary the existing `mission_check_prerequisites` consumer already respects, and the boundary gate that enforces it is the architectural test suite. |
| ATDD-first (`DIRECTIVE_034`, ATDD-First Discipline) | Red-first: the custom code-producing type bypass is demonstrated failing through the pre-existing `_validate_ready_for_review` entry point before the fix, then turning green; the built-in parity test is the same-fixture positive control. |
| `__all__` Declaration Convention (C-007) | Both modules touched declare their public surface in `__all__`; the new accessor is added to it in `mission_type_profiles.py` and `api.py`. |
| Code quality (ruff/mypy) | `uv run ruff check`, `uv run mypy` narrow check on the changed packages; the `follow_imports = "skip"` `Any`-leak hazard documented at the sibling consumer applies here too, so the accessor result is bound to a `bool`-annotated local. |
| Testing requirements (`NO_FULL_HEAVY_SUITES_IN_MISSION`) | Targeted pytest only; CI owns the full sweep. |
| Change-scope reconciliation (`RECONCILE_CHANGE_SCOPE_TENSIONS`) | Smallest viable diff: the `#6327` prerequisite is the minimum needed for the consumer to exist, and it is modelled on an existing capability rather than invented. |
| Pre-existing Failure Reporting Rule | The `#6715`-era reds on `main` (`#6801`, `#6816`, `#5927`) are cited in the PR body if they appear on the head, never silenced. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/issue-6328-code-producing-review-gate-01M68ZQ1/
├── plan.md              # This file
├── research.md          # Phase 0 output (grounding + decisions)
├── data-model.md        # Phase 1 output (the capability's shape and invariants)
├── quickstart.md        # Phase 1 output (how to verify by hand)
├── checklists/
│   └── requirements.md  # spec quality gate
└── tasks/               # Phase 2 output (/spec-kitty.tasks)
```

No `contracts/` directory is created: this mission defines no HTTP/REST/GraphQL/event
interface. The only externally visible surface is Python-internal (a function on an
existing public seam), which `data-model.md` and this plan capture. `meta.json`
records `"contracts": "none"` with a rationale.

### Source Code (repository root)

```
src/
├── charter/
│   ├── offering/missions/
│   │   └── models.py                       # MissionType: add `code_producing: bool | None`
│   └── activation/
│       ├── mission_type_profiles.py        # BUILTIN_CODE_PRODUCING, _resolve_code_producing,
│       │                                   # ResolvedMissionType.code_producing,
│       │                                   # code_producing_for, __all__
│       └── api.py                          # re-export code_producing_for
└── specify_cli/cli/commands/agent/
    └── tasks_parsing_validation.py         # _validate_ready_for_review Check 2:
                                            # delete the family-name literal, use the accessor
tests/
├── charter/
│   └── test_code_producing_capability.py                       # NEW: capability + accessor
└── specify_cli/cli/commands/agent/
    └── test_ready_for_review_code_producing_gate.py            # NEW: pre-flight red-first + parity
```

**Structure Decision**: single project, existing package layout unchanged. Both new
test files sit beside their subjects, matching the neighbours
(`tests/charter/test_resolved_mission_type_context.py`,
`tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py`).

## Complexity Tracking

No Charter Check violations; the table is intentionally empty.

## Design

### D1 — Where the capability lives

- `charter.offering.missions.models.MissionType` gains
  `code_producing: bool | None = None` (declared, so `extra="forbid"` accepts it),
  documented in the class docstring beside `requires_substantive_spec`.
- `charter.activation.mission_type_profiles.BUILTIN_CODE_PRODUCING` is the one
  built-in map: `software-dev: True`, `research: False`, `documentation: False`,
  `plan: False`. A `MappingProxyType`, matching its sibling.
- `ResolvedMissionType.code_producing` is a `@cached_property` backed by
  `_code_producing_thunk`, `False` for the neutral bundle. Populated at the single
  construction site from `_resolve_code_producing(type_key, is_registered=…,
  pack_context=…)`, which reads the layered roster the same way
  `_resolve_requires_substantive_spec` does.
- `code_producing_for(repo_root, mission_type) -> bool` resolves through
  `resolve_mission_type_context` and falls back to the built-in map on any
  exception. Re-exported from `charter.activation.api` and added to both `__all__`s.

### D2 — How the consumer asks

In `_validate_ready_for_review`, Check 2's guard becomes a call to a small
module-local helper that binds the accessor result to a `bool`-annotated local
(the mypy `follow_imports = "skip"` `Any`-leak idiom already used by
`mission_check_prerequisites._requires_substantive_spec`):

```python
def _is_code_producing(main_repo_root: Path, mission_type: str) -> bool:
    from charter.activation.api import code_producing_for  # boundary: public seam only
    produces_code: bool = code_producing_for(main_repo_root, mission_type)
    return produces_code
```

and the guard becomes `if _is_code_producing(main_repo_root, mission_type):`.

`MISSION_TYPE_SOFTWARE_DEV` is then unused by this module and its import is dropped
(the constant itself stays in `core/constants.py`; other modules still use it).

Resolution-failure semantics: `_is_code_producing` never raises (the accessor
swallows and falls back), so an unreadable charter config leaves `software-dev`
gated (`True` from the map) and unknown types ungated (`False`). This is the
deliberate fail-open-for-the-gate / fail-closed-for-the-check split recorded in
research Decision 5.

### D3 — What is deliberately NOT done

- No change to `lanes/for_review_gate.py`, `consolidation.wp_evidence`, or the
  `single_branch` gates (`#6715` / `#5939`). Verified by an empty-diff assertion in
  the PR body, not by a test (a test that asserts "these files are unchanged" is a
  git-blame gate, not a behaviour gate).
- No new parameter on `_validate_ready_for_review` (C-003).
- No change to the other three built-ins' effective verdicts: they keep skipping
  the whole Check 2 block, which is exactly today's behaviour.
- No re-keying of the runtime template-tier / step-graph `software-dev` comparisons;
  they belong to their own follow-ups under `#6315`.

## Implementation Concern Map

### IC-01 — The `code_producing` capability and its public accessor

- **Purpose**: Give consumers one authoritative answer to "does this mission type
  produce committed code?" so no further `software-dev` literal gets written.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001,
  NFR-002, NFR-004, SC-005
- **Affected surfaces**: `src/charter/offering/missions/models.py`,
  `src/charter/activation/mission_type_profiles.py`, `src/charter/activation/api.py`,
  `tests/charter/test_code_producing_capability.py` (new)
- **Sequencing/depends-on**: none — this is the prerequisite for IC-02
- **Risks**: the lazy facet must not read the roster eagerly; the neutral
  (typeless) bundle must answer `False` rather than raise; `extra="forbid"` means
  the field must be declared before any YAML may set it.

### IC-02 — The review-readiness prerequisite keyed on the capability

- **Purpose**: Close the actual defect: a custom code-producing type with no
  implementation commit is refused at review-readiness, and a non-code type keeps
  bypassing.
- **Relevant requirements**: FR-006, FR-007, FR-008, NFR-003, C-001, C-002, C-003,
  SC-001, SC-002, SC-003, SC-004
- **Affected surfaces**:
  `src/specify_cli/cli/commands/agent/tasks_parsing_validation.py`,
  `tests/specify_cli/cli/commands/agent/test_ready_for_review_code_producing_gate.py`
  (new), and the existing suites that construct `_validate_ready_for_review`
- **Sequencing/depends-on**: IC-01
- **Risks**: the collaborator signature is a monkeypatch contract — no required
  parameter; the research-type bypass test
  (`tests/integration/test_coord_loop_depgraph.py:333`) must still pass unchanged;
  `--force` must still short-circuit before the capability is consulted.

### IC-03 — Changelog, docs and the ratchet proof

- **Purpose**: Record the user-facing change and prove the evidence gates were not
  touched.
- **Relevant requirements**: FR-008, SC-004
- **Affected surfaces**: `docs/changelog/CHANGELOG.md` (`[Unreleased]`),
  `docs/` reference page for the mission-type capability surface if one exists
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: `docs/api/cli-commands.md` regeneration reads a shared global cache;
  regenerate only what this diff changes and verify with
  `check_docs_freshness --ci`.
