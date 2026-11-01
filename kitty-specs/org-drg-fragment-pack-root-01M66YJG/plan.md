# Implementation Plan: An org DRG fragment carries its effective pack root

**Branch**: `kitty/mission-org-drg-fragment-pack-root-01M66YJG` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/org-drg-fragment-pack-root-01M66YJG/spec.md` (spec-kitty/spec-kitty#6731)

## Summary

`load_org_pack` already receives each org pack's effective root (`subdir` applied) and writes it
into `OrgDRGFragment.source_ref` as a display string. The #6418 containment wrappers in
`charter/activation/drg_activation.py` (`find_org_body_path_escapes`,
`find_org_asset_path_escapes`) then call `_org_pack_roots_by_name` → `load_pack_registry` to recover
that same root. One fact, two authorities, and a gap if `.kittify/config.yaml` changes between them.

The change carries the root on the fragment as a pydantic `PrivateAttr` (typed, excluded from
serialization), makes both offering containment predicates fragment-only, deletes the two
activation wrappers and `_org_pack_roots_by_name`, and routes both doctor halves through the
`charter.drg` facade. Behaviour is unchanged: the same findings, messages, JSON keys and exit
codes, pinned by the existing #6418 tests.

Measured before the change on the example-org fixture: one `_collect_org_layer_data` run reads the
pack registry **three** times (once in `load_org_drg`, once per wrapper). After: **one**.

## Technical Context

**Language/Version**: Python 3.11 (repo target)
**Primary Dependencies**: pydantic v2 (`PrivateAttr`), Typer/rich (doctor CLI), pytest
**Storage**: N/A — reads `.kittify/config.yaml` and pack roots on disk
**Testing**: pytest; touched modules stay in the `unit`/`fast` tier; architectural gates
(`test_runtime_charter_activation_boundary.py`, `test_no_dead_symbols.py`) run in CI
**Target Platform**: any (path handling is platform-neutral; existing Windows-form escape tests
stay)
**Project Type**: single project — `src/charter` (offering + activation layers), `src/specify_cli`
(doctor CLI)
**Performance Goals**: no measurable cost change; the change removes two registry reads and two
config parses per doctor run (NFR-001 counts them, not times them)
**Constraints**: no serialized-surface change (NFR-003); no new activation-seam baseline row
(NFR-002); no `packs/` edit (C-003); no operator-visible output change (C-001)
**Scale/Scope**: 5 source files, 3 test modules, one 1–2 WP mission

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | How this plan satisfies it |
| --- | --- |
| **Single canonical authority** (`DIRECTIVE_044`) | This mission *is* that principle applied: one pack→root fact, carried by the loader that resolved it. The registry stops being a second lookup for containment. |
| **Architectural alignment** (`DIRECTIVE_001`, ADR `2026-10-06-2` §1) | Both containment predicates stay in `charter.offering`; `specify_cli` reaches them through the `charter.drg` facade, not through a `charter.activation` internal. No new `(file, module)` pair in `charter_activation_boundary_baseline.yaml`. |
| **ATDD-first** (`DIRECTIVE_034`) | Red-first through the production entry point: a counting test on `_collect_org_layer_data`/`_render_org_layer_section` (three registry reads today, one after) and a fragment-only-signature test, both red before the change. |
| **`__all__` convention (C-007)** | New public names (`OrgPackRootUnavailableError`, the fragment-level predicates on the `charter.drg` facade) are added to each module's `__all__` and have live non-test callers (the doctor), so `test_no_dead_symbols.py` stays green. |
| **Locality of change** (`DIRECTIVE_024`) | No change to pack loading, merge, validation or pack content; the diff is the root carriage, two signatures, four call sites, and the deletions. |
| **Don't weaken a gate** | The architectural seam gate and its baseline file are untouched; the #6418 doctor tests keep their assertions. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/org-drg-fragment-pack-root-01M66YJG/
├── plan.md              # This file
├── spec.md              # Mission specification
├── checklists/requirements.md
├── decisions/           # DM for the asset-predicate type contract (resolved)
├── traces/              # tooling-friction.md, approach.md, design-decisions.md
└── tasks.md             # /spec-kitty.tasks output
```

### Source Code (repository root)

```
src/charter/
├── drg.py                                  # facade: re-export both predicates + the typed error
├── activation/
│   └── drg_activation.py                   # DELETE the 2 wrappers + _org_pack_roots_by_name
└── offering/
    ├── assets/
    │   ├── __init__.py                     # unchanged export list
    │   └── repository.py                   # find_asset_path_escapes(fragment)
    └── drg/
        └── org_pack_loader.py              # OrgDRGFragment.pack_root (PrivateAttr),
                                            # find_body_path_escapes(fragment),
                                            # OrgPackRootUnavailableError

src/specify_cli/cli/commands/
├── _charter_pack_collect.py                # JSON half: aggregate the per-fragment predicate
└── _profile_health_render.py               # human half: same aggregation, same try/except shape

tests/
├── charter_offering/drg/test_org_body_path_escapes.py
├── charter_offering/assets/test_org_asset_path_escapes.py
└── specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py
```

**Structure Decision**: single project. The offering layer owns the fragment and the containment
predicates; the activation layer stops owning a containment concern it only wrapped; the runtime
(`specify_cli`) reaches them through `charter.drg`.

## Design

### 1. Carried root on the fragment

```python
class OrgDRGFragment(BaseModel):
    ...
    _pack_root: Path | None = PrivateAttr(default=None)

    @property
    def pack_root(self) -> Path:
        if self._pack_root is None:
            raise OrgPackRootUnavailableError(self.pack_name)
        return self._pack_root
```

`load_org_pack` stamps `fragment._pack_root = pack_root` (the module that owns the class and the one
place that already receives the effective root) immediately before returning, after the
discovered-node append. Properties:

- `model_dump()`, `model_dump_json()` and `model_json_schema()` are unchanged — private attributes
  are not part of a pydantic model's serialized or schema surface (NFR-003).
- `model_copy()` carries private attributes, so a copy still knows its root.
- A fragment rebuilt through `model_validate(fragment.model_dump())` has no root; accessing
  `pack_root` raises `OrgPackRootUnavailableError(pack_name)` instead of judging containment
  against a default path (FR-007). The doctor's existing broad handler turns that into
  "not checked"/`errors`, never into "none".

### 2. Fragment-only offering predicates

- `find_body_path_escapes(fragment: OrgDRGFragment) -> list[BodyPathEscape]` reads
  `fragment.pack_root`; the signature loses its `pack_root` parameter.
- `find_asset_path_escapes(fragment: OrgDRGFragment) -> list[AssetPathEscape]` reads
  `fragment.pack_name` and `fragment.pack_root`; the asset module imports the fragment type from
  `charter.offering.drg.org_pack_loader` (resolved DM `01M66YN5CCFXQF4DBWDSVNSJBG`: one named type
  beats a Protocol that restates the fragment's surface, and `charter.offering.assets` already
  imports `charter.offering.drg.org_pack_config`, so the sibling direction exists).

Both keep their current docstrings' judgement rules verbatim (authored nodes only; org-provenance
assets only; an `assets/` symlinked outside the pack is every asset's finding; nothing is opened).

### 3. Deletions and the facade

- Delete `find_org_body_path_escapes`, `find_org_asset_path_escapes`, `_org_pack_roots_by_name` and
  their now-unused imports from `charter/activation/drg_activation.py`; drop them from its
  `__all__`; update the module docstring's "Provides" list.
- `charter/drg.py` re-exports `find_body_path_escapes`, `find_asset_path_escapes` and
  `OrgPackRootUnavailableError` (the offering facade for runtime consumers).

### 4. Doctor call sites

Both halves keep their structure (one `try`, "a check that could not RUN is not a check that
PASSED") and aggregate per fragment in fragment order:

```python
from charter.drg import find_body_path_escapes

try:
    escapes = [escape for fragment in fragments for escape in find_body_path_escapes(fragment)]
except Exception as exc:
    ...
```

Fragment order preserves today's finding order, so messages and JSON arrays are byte-identical.
The `load_org_drg` import keeps its existing `charter.activation.drg_activation` reach, so the
baseline rows stay accurate and no row is added or drained.

## Complexity Tracking

No charter violations. The single judgement call (asset predicate type contract) is recorded and
resolved as DM `01M66YN5CCFXQF4DBWDSVNSJBG`.

## Implementation Concern Map

### IC-01 — The fragment carries its effective root

- **Purpose**: Make the loader's resolved root available on the fragment without adding it to any
  serialized surface, and define the loud failure when it is absent.
- **Relevant requirements**: FR-001, FR-002, FR-007, NFR-003
- **Affected surfaces**: `src/charter/offering/drg/org_pack_loader.py`, `src/charter/drg.py`
- **Sequencing/depends-on**: none
- **Risks**: A fragment constructed outside the loader (dump/reload) has no root — the typed error
  is the contract, not a fallback. Keep the stamp at the single return point of `load_org_pack`.

### IC-02 — One authority in the containment flow

- **Purpose**: Collapse both predicates onto the carried root, delete the activation wrappers and
  the registry re-read, and route the doctor through the offering facade.
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-006, FR-008, NFR-001, NFR-002
- **Affected surfaces**: `src/charter/offering/assets/repository.py`,
  `src/charter/offering/drg/org_pack_loader.py`, `src/charter/activation/drg_activation.py`,
  `src/charter/drg.py`, `src/specify_cli/cli/commands/_charter_pack_collect.py`,
  `src/specify_cli/cli/commands/_profile_health_render.py`
- **Sequencing/depends-on**: IC-01 (the predicate reads the carried root)
- **Risks**: The existing doctor tests monkeypatch the deleted activation symbols; re-point those
  monkeypatch targets at the `charter.drg` facade. Keep the two `except Exception` channels and
  their message prefixes (`org-layer body_path check failed:`, `org-layer asset path check
  failed:`) exactly as they are — they are pinned by tests and are what "not checked" reads as.
