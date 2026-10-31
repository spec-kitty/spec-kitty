# Implementation Plan: One synthesis-ownership reader, one unreadable-record error

**Branch**: `issue-6767-synthesis-ownership-single-reader` | **Date**: 2026-10-31 | **Spec**: `kitty-specs/synthesis-ownership-single-reader-01M68ZJM/spec.md`
**Input**: Mission specification from `kitty-specs/synthesis-ownership-single-reader-01M68ZJM/spec.md`

## Summary

Three code paths answer "what did synthesis create?" with different sources, different fallback
behaviour and two different errors for one condition (#6767). This mission collapses them onto one
reader — the synthesis manifest plus its provenance sidecars, with the created-artifacts record as
the one documented fallback — and one coded error,
`SynthesisMembershipUnreadableError` / `SYNTHESIS_MEMBERSHIP_UNREADABLE`. `reach_only_ids` and
`synthesis_owned_directive_ids` both consume that reader, and the `charter synthesize --json`
envelope stops parsing the sidecar itself: it wraps the strict sidecar reader and catches its coded
error. Delivery gating and the collision remedy keep their outcomes; the fail-closed refusal from
#6454 is untouched.

## Technical Context

**Language/Version**: Python 3.11 (repo floor), Pydantic v2 models for the manifest and sidecar
**Primary Dependencies**: `ruamel.yaml` (parse), `pydantic` (sidecar validation), `kernel.atomic`
(record writes), `kernel.errors.KittyInternalConsistencyError` (coded refusal)
**Storage**: YAML files under `.kittify/charter/` — `synthesis-manifest.yaml` (commit record),
`provenance/<kind>-<slug>.yaml` (per-artifact sidecar), `synthesized-artifacts.yaml` (every id
synthesis ever created) and the legacy `synthesized-tactics.yaml`
**Testing**: pytest (`pytestmark = pytest.mark.fast` for the unit suites), plus the CLI suites that
pin the `charter synthesize --json` envelope and the `charter context` coded refusal
**Target Platform**: Linux/macOS CLI
**Project Type**: single project (`src/`, `tests/`)
**Performance Goals**: no new I/O on the no-candidate path; one parse of a sidecar per entry
**Constraints**: no new file format, no new module, no weakened refusal, no public name lost
**Scale/Scope**: 3 production modules changed, 1 error class added, 1 error class retired,
3 consumer call sites converged, ~4 test modules touched

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Note |
| --- | --- | --- |
| Single canonical authority | Pass | The point of the mission: one reader owns the answer, one error owns the refusal. |
| Architecture: shared package boundaries | Pass | Reader stays in `charter.activation.synthesizer.manifest`; no new boundary (C-002). |
| ATDD-first / red-first | Pass | The red test goes through the two pre-existing entry points (`reach_only_ids`, `synthesis_owned_directive_ids`) and the envelope builder. |
| Locality of change (DIRECTIVE_024) | Pass | Four production files, all on the ownership read path. |
| Boy Scout Rule (DIRECTIVE_025) | Pass | The retired private error and the duplicate parser are removed, not bypassed. |
| Terminology canon | Pass | "Synthesis ownership record" = manifest + sidecars + created-artifacts record; no new domain term introduced. |
| Tests as scaffold (DIRECTIVE_041) | Pass | Every new test guards a real ownership branch or the coded refusal; no fixture-only assertions. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Pass | Targeted suites only; CI owns the full sweep. |

No violations, so no complexity justification is required.

## Project Structure

### Documentation (this mission)

```
kitty-specs/synthesis-ownership-single-reader-01M68ZJM/
├── plan.md              # This file
├── research.md          # Phase 0 output (discovery decisions D1-D5)
├── spec.md              # Specification (FR-001..FR-010, NFR, C, SC)
├── issue-matrix.json    # #6767 + cited context issues
├── quickstart.md        # Phase 1 output
├── tasks.md             # Phase 2 output (tasks step)
└── tasks/               # Per-work-package task files (tasks step)
```

### Source Code (repository root)

```
src/
├── charter/activation/synthesizer/
│   ├── errors.py         # + SynthesisMembershipUnreadableError (the one coded error)
│   ├── manifest.py       # + synthesized_urns / synthesized_slugs / sidecar_artifact_urn /
│   │                     #   manifest_slugs / created-record read+write primitives
│   │                     # - _synthesized_urns, _SynthesisOwnershipUnreadableError
│   └── reach_only.py     # - its own manifest/sidecar readers; activation policy stays
├── charter/activation/api.py                  # + re-export the one error (and the reader)
└── specify_cli/cli/commands/charter/
    ├── _synthesis.py     # envelope reads the sidecar through the strict reader
    ├── _collision_remedy.py # catches the one coded error
    └── __init__.py       # re-export list follows the renamed helper

tests/
├── charter/synthesizer/test_synthesis_ownership_reader.py   # NEW: the one reader's matrix
├── charter/synthesizer/test_manifest.py                     # ownership + remedy assertions
├── charter/synthesizer/test_reach_only_delivery.py          # fixtures gain sidecars
├── cli/test_charter_context_coded_error_6454.py             # import path
└── specify_cli/cli/commands/charter/test_synthesis_report_6404.py  # envelope degradation
```

**Structure Decision**: single project, existing layout. The reader lives with the record it owns
(`manifest.py`) and `reach_only.py` becomes a consumer; no new module, no new package.

## Complexity Tracking

No charter violations to justify.

## Implementation Concern Map

### IC-01 — The record module owns both records and the one reader

- **Purpose**: Give the synthesis ownership record one home: the manifest, its sidecars, and the
  created-artifacts record, with one reader and one fallback policy.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-005, FR-009, C-001, C-002, NFR-004
- **Affected surfaces**: `src/charter/activation/synthesizer/manifest.py`,
  `src/charter/activation/synthesizer/errors.py`
- **Sequencing/depends-on**: none (first)
- **Risks**: the created-artifacts record's IO moves out of `reach_only.py`; every caller there must
  move with it in the same work package or the tree breaks. The record's on-disk format must not
  change (C-001), including the header comment.

### IC-02 — Both ownership consumers read only through it

- **Purpose**: Make `reach_only_ids` and `synthesis_owned_directive_ids` consumers of the one
  reader, deleting the two private readers they use today.
- **Relevant requirements**: FR-004, FR-005, FR-010, C-003, C-004
- **Affected surfaces**: `src/charter/activation/synthesizer/reach_only.py`,
  `src/charter/activation/synthesizer/manifest.py` (`synthesis_owned_directive_ids`),
  `src/charter/activation/api.py`, the delivery fixtures in
  `tests/charter/synthesizer/test_reach_only_delivery.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: delivery fixtures build manifests without sidecars; they must describe a real synthesis
  tree (sidecar per entry). The lazy read must survive: no overlay or no synthesized-shape edge must
  still answer empty without touching the record.

### IC-03 — One sidecar parser, and the display path that wraps it

- **Purpose**: Remove the second YAML parse of the provenance sidecar; the JSON envelope takes its
  `artifact_id` from the strict reader and degrades to `null` on the coded error.
- **Relevant requirements**: FR-006, FR-007, FR-008, C-004
- **Affected surfaces**: `src/specify_cli/cli/commands/charter/_synthesis.py`,
  `src/specify_cli/cli/commands/charter/__init__.py`,
  `src/specify_cli/cli/commands/charter/_collision_remedy.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: the envelope is a strict-JSON contract asserted by several suites — it must never
  raise, and non-directive entries must still carry `artifact_id: null`. The collision remedy's
  wording names the offending file, which the coded error must expose.

### IC-04 — Evidence, docs and the cross-cutting guards

- **Purpose**: The changelog entry, the documented error code, and the guard tests that keep the
  convergence from drifting back (one reader, one parser, one code).
- **Relevant requirements**: FR-009, SC-001, SC-002, SC-003, SC-004, NFR-001, NFR-002
- **Affected surfaces**: `docs/changelog/CHANGELOG.md`, module docstrings, the architectural
  guard test (no production `YAML(` parse of the sidecar outside the record module)
- **Sequencing/depends-on**: IC-01, IC-02, IC-03
- **Risks**: a full docs-reference rebuild reads a shared global cache (other agents on this host
  rewrite it); regenerate only what this diff changes and verify with
  `check_docs_freshness --ci`.

## Phase 1 design notes

### The one reader

```python
def synthesized_urns(repo_root: Path, kind: str) -> frozenset[str]:
    """URNs of *kind* artifacts synthesis created. The only reader of the ownership record."""
```

1. Manifest path exists or is a symlink? No → `frozenset()` (nothing synthesized; the record is not
   read).
2. `load_yaml` the manifest. Unreadable/invalid (OSError, ValueError, YAMLError) → step 4.
3. For each manifest entry of `kind`: `sidecar_artifact_urn(repo_root, entry)` — the validated
   sidecar's `artifact_urn`, `None` for `project-direct-write`. Any failure there → step 4. Union the
   URNs.
4. `_recorded_urns(repo_root, kind, cause)`: the created-artifacts record's ids of that kind (legacy
   tactics record unioned in) as `{f"{kind}:{id}"}`, with the existing warning. The record has no
   answer when it is absent, unreadable, lists no id of the kind, or the kind is not tracked there →
   raise the one coded error naming the cause and the file at fault.

`synthesized_slugs(repo_root, kind)` = the URN id segment of that set, for `reach_only_ids`.

### The one error

```python
class SynthesisMembershipUnreadableError(KittyInternalConsistencyError):
    code = "SYNTHESIS_MEMBERSHIP_UNREADABLE"
    # record_path, offending_artifact, reason, kind
```

Bodies keep the two existing shapes' substance in one message: what could not be read, which file,
why, and the remedy — restore the manifest (or the sidecar) from version control; do not delete the
created-artifacts record.

### Data flow after the change

```
reach_only_ids ─┐
synthesis_owned_directive_ids ─┼─> synthesized_urns / synthesized_slugs
                               │      └─ manifest ─┬─> sidecar_artifact_urn (strict, contained)
                               │                  └─> created-artifacts record (fallback)
charter synthesize --json ─────┘            (wraps sidecar_artifact_urn, catches the coded error)
```
