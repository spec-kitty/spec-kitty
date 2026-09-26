---
work_package_id: WP02
title: 'Finding B: single shared catalog.mission accessor'
dependencies: []
requirement_refs:
- C-004
- C-005
- FR-004
- NFR-003
planning_base_branch: fix/silent-write-hardening-residuals
merge_target_branch: fix/silent-write-hardening-residuals
branch_strategy: Planning artifacts for this mission were generated on fix/silent-write-hardening-residuals. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/silent-write-hardening-residuals unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
history:
- event: created
  at: '2026-09-23T19:24:56Z'
  actor: architect-alphonso
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent: []
execution_mode: code_change
owned_files:
- src/charter/activation/charter_yaml_io.py
- src/charter/activation/language_scope.py
- src/specify_cli/cli/commands/charter/generate.py
- src/specify_cli/charter_runtime/preflight/references_refresh.py
- tests/specify_cli/cli/commands/charter/test_recompile_preserves_mission_4908.py
- tests/specify_cli/charter_runtime/test_references_parity_refresh.py
role: implementer
tags: []
tracker_refs:
- '#4993'
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else in this prompt, load your assigned agent profile:

```
/ad-hoc-profile-load python-pedro
```

This profile governs your implementation style, boundaries, and quality standards for this work package.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks.

---

## Objective

Consolidate the **two** divergent readers of `charter.yaml` `catalog.mission` onto **one shared accessor**
in `charter/activation/charter_yaml_io.py`, using the canonical loader (`load_charter_yaml`, ruamel
round-trip). This removes the parser-drift risk (`YAML(typ="safe")` vs round-trip) over one field.

Read `contracts/catalog-mission-accessor-contract.md` first. Note: issue #4993 says "three readers" — the
true count is **two** (the claimed third reads `catalog.languages`); WP04 records that correction.

## Key context (verified on current main)

- Canonical loader `charter/activation/charter_yaml_io.py::load_charter_yaml` (~509-522): ruamel round-trip,
  `preserve_quotes`; empty→`CommentedMap()`, missing→`FileNotFoundError`.
- Template shape: `charter/activation/language_scope.py::_read_compiled_languages` (~48-79) already does
  `load_charter_yaml → document.get("catalog") → catalog.get("languages")` inside a
  `(YAMLError, OSError, UnicodeDecodeError)` guard. Mirror this exactly.
- Reader 1 (already canonical): `cli/commands/charter/generate.py::_read_catalog_mission_from_charter_yaml`
  (~211-256) — already imports `load_charter_yaml` lazily.
- Reader 2 (the divergence): `charter_runtime/preflight/references_refresh.py::_read_catalog_mission_and_template_set`
  (~103-131) — hand-rolls `YAML(typ="safe")` (`~122`). It also reads a `template_set` alongside `mission`;
  keep that behavior, but route the `catalog.mission` read through the shared accessor.
- Both callers already reach `charter.activation.*` lazily elsewhere → no import-layer violation.

## Subtasks

### T006 — Add the shared accessor `[P]`

**Purpose**: One SSOT reader of a `catalog.<field>`.
**Steps**:
1. In `charter_yaml_io.py`, add `read_catalog_field(repo_root, field) -> Any | None` implementing the
   `_read_compiled_languages` shape once: resolve `repo_root / CHARTER_YAML`, `.exists()` guard,
   `load_charter_yaml` inside `try/except (YAMLError, OSError, UnicodeDecodeError)` → None, then
   `document.get("catalog")` → `catalog.get(field)` (None if catalog absent/not a dict/field absent).
2. Add a thin `read_catalog_mission(repo_root)` = `read_catalog_field(repo_root, "mission")`.
3. Add these to `__all__` if the module declares one (C-007 convention).

### T007 — Delegate Reader 1 `[P]`

**Steps**: Collapse `generate.py::_read_catalog_mission_from_charter_yaml`'s body to a lazy
`from charter.activation.charter_yaml_io import read_catalog_mission` + delegate. Preserve the function's
existing signature/return contract and any surrounding fallback semantics (do not reintroduce the #2940
`from_interview` abort — read the SSOT).

### T008 — Delegate Reader 2 `[P]`

**Steps**: In `references_refresh.py::_read_catalog_mission_and_template_set`, replace the ad-hoc
`YAML(typ="safe")` read of `catalog.mission` with the shared accessor. Keep the `template_set` read (route
it through `read_catalog_field(repo_root, "template_set")` too, if it reads that field the same way — verify).
Remove the now-dead `YAML(typ="safe")` import if nothing else uses it.

### T009 — Campsite: route `language_scope` through the accessor `[P]`

**Steps**: Refactor `_read_compiled_languages` to call `read_catalog_field(repo_root, "languages")` so all
three `catalog.*` reads share one accessor. Behavior must be byte-identical (it is the template shape). If
this proves to widen scope or risk, leave `_read_compiled_languages` as-is and note the deferral — it is a
campsite nicety, not a requirement.

### T010 — Tests + grep proof `[P]`

**Steps**:
1. Add accessor unit tests: normal doc, absent `catalog`, absent field, malformed doc → uniform `None`;
   a quoted/commented mission value resolves identically.
2. Extend `test_recompile_preserves_mission_4908.py` and `test_references_parity_refresh.py` to assert both
   callers resolve the identical value through the accessor.
3. Add/execute a grep proof that exactly one `catalog.mission` reader remains (see quickstart.md); if a test
   is the right home for this invariant, add a small guard test.

## Branch Strategy

Planning base and final merge target: `fix/silent-write-hardening-residuals`. Execution worktree allocated
per `lanes.json` lane during `/spec-kitty.implement`; do not hand-create branches.

## Definition of Done

- One accessor reads `catalog.mission`; both former readers delegate (FR-004); grep proof green (NFR-003 / SC-002).
- Uniform absent/malformed result across callers; canonical ruamel parser only.
- No behavior change for valid documents (parity tests green).
- No new dependency (C-004); Mission terminology only (C-005).
- `ruff` + `mypy` clean on owned files.

## Reviewer guidance

Confirm no second parser survives for `catalog.mission`. Confirm the #2940 abort is not reintroduced.
Verify the import edges are within existing lazy `charter.activation` usage (no new boundary violation).
