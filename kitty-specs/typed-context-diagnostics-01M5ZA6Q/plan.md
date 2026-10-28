# Implementation Plan: Typed context JSON diagnostics

**Branch**: `issue-6460-typed-context-diagnostics` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/typed-context-diagnostics-01M5ZA6Q/spec.md`

## Summary

Governance resolution diagnostics become typed entries (`code` from a closed five-value set, `message` with today's wording). The governance resolution carries them; `charter context --json` serialises them as `{code, message}` under the unshipped schema 1.4.0; `doctor` warns on `UNKNOWN_SELECTION_DROPPED` by code; text renderers print `.message`. Separately (#6461), document the interview JSON `narrowed` field and type the synthesis slug helpers' `reconciliation` parameter.

## Engineering Alignment

- Codes live beside the existing `CharterEncodingDiagnostic` StrEnum in `src/charter/activation/_diagnostics.py` (one home for charter-activation diagnostic codes), mirrored in `src/charter/activation/ERROR_CODES.md`.
- `GovernanceResolution.diagnostics: list[GovernanceDiagnostic]`; every producer site in `resolver.py` names its code. `UNKNOWN_SELECTION_DIAGNOSTIC` stays as the message template (resolver-internal); its `charter.activation.api` re-export moves to the code type once `doctor` no longer needs it.
- `collect_governance_diagnostics` keeps returning `list[str]` (messages): it is a text view that also carries `GovernanceResolutionError.issues`, which have no code.
- Context JSON keeps `context_schema_version` `1.4.0`.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml (existing); no dependency added, removed or upgraded (DIRECTIVE_051 supply-chain checks: not applicable)
**Storage**: N/A (JSON on stdout; golden JSON fixtures in tests)
**Testing**: pytest; red-first ATDD tests through `charter context --json` and `doctor`'s governance check; targeted module tests + `make test-fast`; ruff, ruff format, mypy --strict on touched files
**Target Platform**: Spec Kitty CLI (Linux/macOS/Windows)
**Project Type**: single
**Performance Goals**: N/A (no hot path change)
**Constraints**: lands before 4.0.0rc8 is tagged; complexity <= 15; no new suppressions; diff-cover >= 90%
**Scale/Scope**: ~8 source files, ~12 test files, 3 docs files

## Charter Check

- Single canonical authority: one code enum, one producer (resolver), one serialiser; no prefix parsing left. PASS.
- Architectural alignment: changes stay in `charter.activation` (in core, ADR 2026-10-16-1 + Amend 2026-10-19) and its `api` seam; `specify_cli` imports through `charter.activation.api`. No layer/package/gate change. Not affected by ADR 2026-10-22-1 (event writer), ADR 2026-10-19-1 (activation ledger), epics #6518/#6117/#6608 or spec-kitty-events #92 (see research.md). PASS.
- ATDD-first: red tests committed before implementation per WP. PASS.
- Terminology: Mission, never feature; terminology guard run (charter + prose touched). PASS.
- `__all__` convention (C-007): new names exported and called from `src/`. PASS.
- No full heavy suites in mission work. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/typed-context-diagnostics-01M5ZA6Q/
├── plan.md, research.md, data-model.md, quickstart.md
├── contracts/context-json-diagnostics.md
└── tracer/ (tooling-friction.md, approach.md, design-decisions.md)
```

### Source Code (repository root)

```
src/charter/activation/_diagnostics.py        # + GovernanceDiagnosticCode, GovernanceDiagnostic
src/charter/activation/ERROR_CODES.md         # + governance diagnostic codes part
src/charter/activation/resolver.py            # producers emit typed entries
src/charter/activation/context_json.py        # serialise {code, message}
src/charter/activation/context_contract.py    # ledger comment
src/charter/activation/compact.py             # render .message
src/charter/activation/api.py                 # export code/type; drop UNKNOWN_SELECTION_DIAGNOSTIC re-export
src/runtime/next/prompt_builder.py            # render .message
src/specify_cli/runtime/doctor.py             # classify by code
src/charter/activation/synthesizer/reach_only.py  # typed reconciliation parameter (#6461)
docs/api/charter-commands.md                  # {code, message}, codes, `narrowed`
docs/changelog/CHANGELOG.md                   # rc8 entry reworded
tests/...                                     # ATDD + updated assertions + regenerated goldens
```

**Structure Decision**: single project; existing modules only, no new module.

## Implementation Concern Map

### IC-01 — Typed governance diagnostics contract

- **Purpose**: give every governance diagnostic a closed code and carry it to context JSON and doctor.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001..003, C-001..003
- **Affected surfaces**: `_diagnostics.py`, `ERROR_CODES.md`, `resolver.py`, `context_json.py`, `context_contract.py`, `compact.py`, `api.py`, `prompt_builder.py`, `doctor.py`, docs/api, changelog, tests + goldens
- **Sequencing/depends-on**: none
- **Risks**: golden fixtures and many string assertions change; seam-test stubs passing raw strings must keep yielding a sane payload.

### IC-02 — Interview `narrowed` docs and typed slug helpers (#6461)

- **Purpose**: close #6461 items 1 and 3.
- **Relevant requirements**: FR-006, FR-007, C-004
- **Affected surfaces**: `docs/api/charter-commands.md` (interview section), `synthesizer/reach_only.py`, its tests
- **Sequencing/depends-on**: none (touches a different docs section from IC-01)
- **Risks**: sibling mission M2 edits `reach_only.py`; keep the change to two signatures plus one import.
