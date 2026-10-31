# Implementation Plan: Promote org-pack interview selections on upgrade

**Branch**: `issue-6686-org-pack-selection-promotion` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/org-pack-selection-promotion-01M67HVC/spec.md`

## Summary

`4.0.0rc8_promote_interview_selections` resolves an interview selection against the
built-in pack only, so an org-pack (or project-pack) selection is reported
"Unresolved interview selections skipped (not promoted)" while `charter interview`
resolves the same id and promotes it. The technical approach: move the per-kind
resolution loop out of both writers into one selection resolver in
`src/charter/activation/selection.py`, exported from `charter.activation.api`, built
on the same layer-aware `IdentityIndex.build(repo_root)` authority `charter context`
and the interview already use (#6406/#6407). Both writers then call the resolver;
the write path (`resolve_activation_write_target` + `promote_activations`) is
untouched.

## Technical Context

**Language/Version**: Python 3.11+ (repo targets 3.11; `from __future__ import annotations` style throughout)
**Primary Dependencies**: ruamel.yaml, typer/rich (CLI), pytest (tests); no new third-party dependency
**Storage**: YAML on disk — `.kittify/config.yaml`, `.kittify/charter/activation.yaml` (activation ledger), `.kittify/charter/interview/answers.yaml`
**Testing**: pytest, unit + CLI-level (`typer.testing.CliRunner`), architectural gates under `tests/architectural/`; `uv run pytest <paths>`
**Target Platform**: Linux/macOS developer machines and CI (the `spec-kitty` CLI)
**Project Type**: single Python package (`src/charter`, `src/specify_cli`)
**Performance Goals**: one `IdentityIndex` build per writer run; the migration still resolves no doctrine when no selection exists
**Constraints**: `charter.activation.api` is the only sanctioned seam for `src/specify_cli` (architectural boundary ratchet, shrink-only); the activation layer must not depend on `specify_cli`; public-API re-export identity is gate-pinned
**Scale/Scope**: 1 new module (~90 lines), 1 seam re-export, 2 call sites rewritten, ~4 test modules touched

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | How this plan satisfies it |
| --- | --- |
| Single canonical authority (charter, Governing Principles) | One resolver over the existing `IdentityIndex`; no second lookup table, no new precedence rule (C-003). |
| Architectural Integrity Standard (`DIRECTIVE_001`) | The shared loop lives in `charter.activation`, behind `charter.activation.api`; `specify_cli` keeps depending on the seam only (NFR-003). |
| Prefer Durable Fixes (`DIRECTIVE_052`) | The class is "a writer resolves selections its own way"; the fix closes the class for both writers instead of patching the migration's lookup. |
| Locality of Change (`DIRECTIVE_024`) | Blast radius: one new module, one seam export, two call sites, plus their tests. |
| ATDD-First Discipline / `DIRECTIVE_034` | Red-first: the org-pack promotion test is written and observed failing through the migration entry point before the resolver exists. |
| Test quality (`DIRECTIVE_041`, `mutation-aware-test-design`) | Every new assertion is paired on the same fixture (known org id promotes while an unknown id is still reported), and the CLI path is exercised for the interview half. |
| `__all__` convention (C-007) | The new module declares `__all__`; the seam lists the symbol; the re-export identity gate gets its row. |
| Burn-down Policy (C-004) | Draining `charter.activation.catalog` and `charter.activation.layer_roots` from `interview.py` removes two ratchet rows, so the boundary baseline count is lowered in the same change. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/org-pack-selection-promotion-01M67HVC/
├── plan.md              # This file
├── research.md          # Phase 0 output (grounding, code map, decisions D-1..D-5)
├── spec.md              # Mission specification
├── checklists/          # Specification quality checklist
├── tasks/               # Work-package tasks (Phase 2 output)
└── traces/              # Mission tracer files
```

### Source Code (repository root)

```
src/
├── charter/
│   └── activation/
│       ├── selection.py            # NEW: the one selection resolver (+ __all__)
│       ├── api.py                  # seam: re-export SelectionResolver / SelectionResolution
│       ├── identity_index.py       # unchanged authority (IdentityIndex.build)
│       └── activation_engine.py    # unchanged write primitive promote_activations
└── specify_cli/
    ├── upgrade/migrations/
    │   └── m_4_0_0rc8_promote_interview_selections.py   # use the shared resolver
    └── cli/commands/charter/
        └── interview.py                                   # use the shared resolver, drop its loop

tests/
├── charter/activation/test_selection_resolver.py         # NEW: resolver unit tests (layers, ambiguity, dedupe)
├── upgrade/migrations/test_m_4_0_0rc8_promote_interview_selections.py  # org/project-pack promotion, unresolved control
├── specify_cli/cli/commands/test_charter_interview_promotion.py         # CLI parity: same stem for the same id
└── architectural/
    ├── test_charter_activation_api_reexport.py            # + seam row
    ├── charter_activation_boundary_baseline.yaml          # drained rows removed, count lowered
    └── _baselines.yaml                                    # boundary_baseline count 234 -> 232
```

## Phase 0 — Research

Recorded in [research.md](./research.md): the reproduction (org id reported unresolved),
the code map of both writers, and decisions D-1..D-5 (route through `IdentityIndex`;
one resolver behind the seam; share resolution but keep each writer's error policy;
promote stems; built-in behaviour unchanged). No `NEEDS CLARIFICATION` remains.

## Phase 1 — Design

### The resolver's contract (no `contracts/` file needed; this is an internal seam)

`src/charter/activation/selection.py`

```python
@dataclass(frozen=True)
class UnresolvedSelection:
    kind: ArtifactKind
    raw_id: str
    ambiguous: bool          # a declared identity no file stem can represent

@dataclass(frozen=True)
class SelectionResolution:
    stems: dict[str, list[str]]          # "activated_<kind>" -> stems, selection order, deduped
    unresolved: list[UnresolvedSelection]

class SelectionResolver:
    identity: IdentityIndex

    @classmethod
    def build(cls, repo_root: Path) -> SelectionResolver      # IdentityIndex.build(repo_root)
    def stem(self, kind, raw_id) -> str | None                # None when no layer knows it
    def stems(self, kind, raw_ids) -> set[str]                # present-list comparison: unknown ids kept as written
    def resolve(self, selections: Mapping[ArtifactKind, Sequence[str]], *,
                refuse_ambiguous: bool = False) -> SelectionResolution
```

- `build` is the only constructor call sites use, so both writers index exactly the
  layers `charter context` does.
- `resolve` runs the single loop: probe the index, dedupe by stem, collect unknown ids
  and unrepresentable identities. With `refuse_ambiguous=True` it raises the index's
  `ActivationIdCollisionError` (interview: Decision `file_name_collision`); without it
  the ambiguity is reported (upgrade: "reported, never dropped silently").
- The migration keeps its `_seeded_list_hints` and write path; `_StemResolver` and
  `_resolve_selections` are deleted in favour of the shared resolver.
- `interview.py` drops `_promote_interview_selections`'s own loop, its
  `IdentityIndex.from_roots` construction and its `layer_roots`/`catalog` imports.
- `_stem_spelled_config` (narrow mode) uses `SelectionResolver.stems`, the same rule.

### Data model

No persisted structure changes: `answers.yaml`, the activation ledger and
`charter.yaml` keep their shapes (C-001). The resolver returns in-memory values only.

### Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| An interview refusal (collision) is silently downgraded to a warning by sharing the loop | `refuse_ambiguous=True` keeps `ActivationIdCollisionError`; the existing CLI test that renders the refusal stays green unchanged. |
| Layer precedence drifts from `charter context` | The resolver owns no precedence: it delegates to `IdentityIndex.build`, which `charter context` also uses. |
| Built-in-only projects change behaviour | Built-in is the last layer in the index; NFR-002 pins the existing migration/interview suites unchanged. |
| The migration now builds the index for a project whose doctrine root is broken | Keep the existing `resolve_offering_root` failure path and its "Could not resolve doctrine root" result; `SelectionResolver.build` is called inside the same guarded block. |
| Boundary ratchet goes stale after the drain | Remove the two `interview.py` rows and lower `boundary_baseline` in `_baselines.yaml` in the same change. |

## Phase 2 — Tasks

Work-package decomposition lives in `tasks/` after `/spec-kitty.tasks`. The red-first
order is fixed: the org-pack promotion test (migration entry point) fails first, then
the resolver lands, then both call sites move onto it, then the interview CLI parity
test and the architectural gates.

## Complexity Tracking

No charter violations. The only structural growth is one module plus one seam
re-export; it removes a duplicated resolution loop, so net complexity falls.
