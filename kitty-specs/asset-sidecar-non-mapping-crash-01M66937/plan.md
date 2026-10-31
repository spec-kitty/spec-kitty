# Implementation Plan: Org asset sidecar with non-mapping YAML no longer crashes repository load

**Branch**: `issue-6735-asset-sidecar-non-mapping-crash` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/asset-sidecar-non-mapping-crash-01M66937/spec.md`
**Input**: Mission specification from `kitty-specs/asset-sidecar-non-mapping-crash-01M66937/spec.md`

## Summary

A top-level non-mapping YAML document in an `*.asset.yaml` (or any other kind's)
overlay sidecar makes `BaseArtifactRepository._apply_overlay_file` crash with
`AttributeError: 'list' object has no attribute 'get'` at
`src/charter/offering/base.py:319` (`item_id = data.get("id")`), aborting the
whole repository load (issue #6735; in `doctor charter-packs` it fails the org
asset containment check closed). The fix adds an explicit non-mapping guard in
the base loader — in both `_apply_overlay_file` (org/project overlays) and
`_load_built_in_items` (where six kinds' `_pre_validate` hooks read `data`
before Pydantic can reject the document) — so a present-but-non-mapping
document is treated as malformed and skipped with the usual
`Skipping invalid <layer> <kind> <file>: <reason>` `UserWarning`, exactly like
invalid YAML, schema-invalid documents and unreadable files today. A
parametrized regression test covers all 11 repository kinds sharing
`BaseArtifactRepository`, red-first on pre-fix main.

## Technical Context

**Language/Version**: Python 3.11 (repo-standard `uv` environment, Python 3.11+ per `pyproject.toml`)
**Primary Dependencies**: `ruamel.yaml` (YAML parse), `pydantic` (model validation), `pytest` (tests)
**Storage**: N/A (in-repository YAML load path only)
**Testing**: `uv run pytest` — fast doctrine/unit lanes under `tests/charter_offering/`; markers `fast`, `doctrine`; red-first per DIRECTIVE_034 (test-first bug fixing)
**Target Platform**: cross-platform Python (CLI tool)
**Project Type**: single (CLI package `specify_cli` / `charter` in one repo)
**Performance Goals**: none new — the guard is one `isinstance` check per parsed file
**Constraints**: no public API change; the skip-warning text must keep the `Skipping invalid <layer> <kind> <file>: <reason>` shape parsed by `_charter_pack_collect`; single fix site in `src/charter/offering/base.py` (DIRECTIVE_024 locality, DIRECTIVE_044 single canonical authority)
**Scale/Scope**: one source file touched (`src/charter/offering/base.py`, ~2 load sites + one shared helper), one test module added/extended under `tests/charter_offering/`, changelog entry

## Charter Check

- **Architectural alignment**: the fix lands in the existing base-class seam
  (`BaseArtifactRepository`), not per repository kind — no new surface, no
  second authority. PASS.
- **ATDD-first**: the defect gets a failing test through the pre-existing entry
  point (repository construction with `org_dirs=[...]`) before the fix. PASS.
- **Locality / smallest viable diff** (DIRECTIVE_024, `change-apply-smallest-viable-diff`):
  two guard insertions sharing one helper in one file; no drive-by refactors. PASS.
- **Terminology**: "overlay", "sidecar", "layer", "provenance" used per the
  existing module vocabulary. PASS.
- No charter violations to justify.

## Project Structure

### Documentation (this mission)

```
kitty-specs/asset-sidecar-non-mapping-crash-01M66937/
├── spec.md              # authored (FR-001..FR-003, NFR-001..002, C-001..003, SC-001..003)
├── research.md          # grounding: repro, root cause, decisions D1-D5
├── plan.md              # this file
├── data-model.md        # Phase 1 (loader data shapes; no persistent entities)
└── tasks/               # Phase 2 (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/charter/offering/base.py        # the fix: non-mapping guard, both load sites
tests/charter_offering/
├── test_base_org_layer.py          # existing base-layer behaviour (unchanged, ratchet)
└── test_non_mapping_sidecar_skip.py  # new: parametrized per-kind regression
docs/changelog/CHANGELOG.md         # [Unreleased] entry (user-facing)
```

**Structure Decision**: single-project layout, existing module seams. The new
test module lives beside the existing `BaseArtifactRepository` tests under
`tests/charter_offering/` and parametrizes over the 11 repository kinds so the
per-kind matrix cannot drift from the class list without a test edit.

## Complexity Tracking

No charter violations; none to justify.

## Implementation Concern Map

### IC-01 — Non-mapping guard in the base loader

- **Purpose**: make a present-but-non-mapping YAML document skip with the usual
  warning instead of crashing, in both the overlay tier (`_apply_overlay_file`)
  and the built-in tier (`_load_built_in_items`, before `_pre_validate` runs).
- **Relevant requirements**: FR-001, FR-002, NFR-001, NFR-002
- **Affected surfaces**: `src/charter/offering/base.py`
- **Sequencing/depends-on**: none
- **Risks**: warning-text drift breaking `_parse_skipped_glossary_pack_warning`
  (mitigated: reuse the exact `Skipping invalid …` shape and mirror the
  missions repository's `expected a YAML mapping, got <type>` wording);
  over-broad `except` would mask real bugs (mitigated: explicit `isinstance`
  guard, not a wider except tuple — research.md D2).

### IC-02 — Per-kind regression matrix, red-first

- **Purpose**: prove the fix per repository kind (the issue's explicit ask) and
  prove the test can fail (fails on pre-fix main for every kind whose org
  overlay reaches `data.get`).
- **Relevant requirements**: FR-001, FR-003, SC-001, SC-002, SC-003, C-001
- **Affected surfaces**: `tests/charter_offering/test_non_mapping_sidecar_skip.py` (new)
- **Sequencing/depends-on**: IC-01 conceptually, but authored **before** the
  fix lands (red-first); committed in the red state, then turned green by IC-01.
- **Risks**: per-kind fixture drift (mitigated: one shared fixture factory,
  parametrized over `(repository class, glob, minimal valid artifact)`); a kind
  whose schema makes "one valid sibling artifact" hard (handled per-kind with
  the minimal model-valid mapping; sibling inclusion assertion proves load
  continues — the non-vacuity positive control).
