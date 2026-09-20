---
work_package_id: WP01
title: 'Catalog compiler: completeness, determinism, campsite'
dependencies: []
requirement_refs:
- C-001
- C-004
- FR-007
- FR-008
- FR-009
- NFR-002
- NFR-004
- NFR-005
planning_base_branch: issue-4785-charter-catalog-coherence
merge_target_branch: issue-4785-charter-catalog-coherence
branch_strategy: Planning artifacts for this mission were generated on issue-4785-charter-catalog-coherence. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4785-charter-catalog-coherence unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Foundation
history:
- at: '2026-09-19T21:23:09Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/test_catalog_completeness_4785.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/charter/activation/compiler.py
- tests/charter/test_catalog_completeness_4785.py
- tests/charter/test_builtin_reader_relocation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Catalog compiler: completeness, determinism, campsite

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

This WP is the **foundation** for WP03's recompile-by-default: it makes a full
`catalog.references` recompile **complete** and **diff-stable**. (Issue #4785, Finding 4.)

Done when:
- A full recompile resolves the real `summary` for every directive present in the
  authoritative typed-doctrine enumeration — **zero** entries read
  `Definition unavailable in bundled doctrine.` for a directive that has a bundled definition
  (FR-007).
- A directive id with genuinely no bundled definition surfaces via the existing
  `graph.unresolved` diagnostics channel — **never** a silent placeholder catalog row (FR-007).
- `catalog.references` entries are emitted in a canonical, deterministic order (NFR-005).
- A second consecutive recompile of an unchanged store is a **zero-line diff of the
  `catalog.references` section**; `metadata.generated_at` is preserved when the catalog content
  is byte-unchanged (FR-008 / NFR-002).
- The dead, uncalled `_build_references_from_yaml` is removed (FR-009).

## Context & Constraints

- **Single authority (C-001)**: `catalog.references` is written ONLY by `compile_charter` /
  `write_compiled_charter`. Do not add a second/minimal writer.
- Read: `.kittify/charter/charter.md`, `kitty-specs/charter-catalog-coherence-01M2XQQF/{plan.md,research.md,data-model.md,contracts/behavior-contracts.md,quickstart.md}`.
- **Root-cause map** (from grounding): `_render_kind_references` (`compiler.py:1094-1125`) calls
  `repository.get(raw_id)`; the DRG transitive closure (`_resolve_transitive_reference_graph`,
  `compiler.py:1242+`) surfaces directive ids the activation-filtered typed repository cannot
  resolve → miss → `_doctrine_yaml_reference(source=None)` → the literal placeholder at
  `compiler.py:1489`. Two candidate mechanisms: (a) DRG bare/semantic id vs canonical
  `DIRECTIVE_NNN` key mismatch; (b) a project-dir `directive/` (singular) vs `directives/`
  (plural) loader split. **Pin the exact mechanism with the red-first repro (T001) before fixing.**
- **LAYER RULE (binding, `tests/architectural/test_layer_rules.py`)**: compiler.py is the CHARTER
  layer. Do **NOT** import `drg_urn_to_config_id` (it lives in `specify_cli`, a HIGHER layer —
  importing it breaks the enforced `kernel <- charter <- … <- specify_cli` chain). Use the
  **in-layer** bridges only: `resolve_config_id` (`src/charter/activation/kind_vocabulary.py:546`,
  URN→config-stem — compiler.py already imports from `kind_vocabulary` at line 34, extend that) and
  `normalize_directive_id` (`src/charter/offering/drg/migration/id_normalizer.py:22`). The
  `DirectiveRepository.get` already tries `normalize_directive_id`, so the miss is a
  **URN/config-stem-key mismatch** — `resolve_config_id("directive:"+raw_id, …)` is the likely
  correct bridge; confirm with the T001 repro before choosing.
- `write_compiled_charter` (def `compiler.py:502`, in this owned file) already preserves authored
  sections byte-for-byte — do not regress that. `_build_metadata_dict` stamps `generated_at` at
  `:684-686`; `_build_catalog_dict` at `:648` (both in the owned file, so T005 fits here).

## Branch Strategy

- **Strategy**: rebase-merge to `main` via non-draft PR (operator merges)
- **Planning base branch**: `issue-4785-charter-catalog-coherence`
- **Merge target branch**: `main`
- Execution worktree is allocated per computed lane from `lanes.json`.
- Implement command: `spec-kitty agent action implement WP01 --agent claude`

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first repro (RED before any fix)
- **Purpose**: Pin the observable defect through the pre-existing entry point.
- **Steps**: In `tests/charter/test_catalog_completeness_4785.py`, add `@pytest.mark.regression`
  tests referencing #4785: (1) after a recompile, assert no directive in the authoritative typed
  enumeration renders `Definition unavailable in bundled doctrine.`; (2) assert two consecutive
  recompiles produce an identical `catalog.references` section (byte-equal after excluding
  `metadata.generated_at`). Both must be RED on the base.
- **Files**: `tests/charter/test_catalog_completeness_4785.py` (new).

### Subtask T002 – Resolve DRG-surfaced ids to the canonical repository key
- **Purpose**: Close the summary gap at the resolution seam, not the fallback string.
- **Steps**: In `_render_kind_references`, normalize each `raw_id` through the existing canonical-id
  bridge before `repository.get(...)` so transitively-reached directives resolve to their typed
  model + real `intent` summary.
- **Files**: `src/charter/activation/compiler.py`.

### Subtask T003 – Genuine misses → diagnostics, not silent placeholders
- **Purpose**: A truly-absent definition must not masquerade as a real catalog row.
- **Steps**: The bug is the **directive/DRG-kind else-branch at `compiler.py:1123-1124`** (after
  `model = repository.get(raw_id)` at `:1113` returns None → appends
  `_doctrine_yaml_reference(source=None)`). Fix ONLY that branch: on a genuine miss, route the id
  into the existing `diagnostics` list via the `graph.unresolved` format at `compiler.py:1233-1235`.
  **Do NOT gut `_doctrine_yaml_reference` / the `:1489` placeholder wholesale** — the paradigm path
  (`:1146`, `source=paradigm_sources.get(...)` which can also be None) legitimately renders through
  it. Guard against wrongly-eager resolution (contract C4 / spec US4-2).
- **Files**: `src/charter/activation/compiler.py`.

### Subtask T004 – Deterministic canonical ordering (NFR-005)
- **Purpose**: A recompile must not reorder entries.
- **Steps**: Emit `catalog.references` in a stable canonical order (e.g. sorted by `id`) independent
  of dict/set iteration or graph-walk order.
- **Files**: `src/charter/activation/compiler.py`.

### Subtask T005 – Preserve `generated_at` when catalog byte-unchanged (FR-008/NFR-002)
- **Purpose**: Make a no-op recompile a true no-op at the section level.
- **Steps**: In the compile/write path, when the newly-computed `catalog` content equals the existing
  on-disk `catalog`, preserve the existing `metadata.generated_at` rather than restamping `now`.
- **Files**: `src/charter/activation/compiler.py`.

### Subtask T006 – Delete dead `_build_references_from_yaml` (FR-009, campsite)
- **Purpose**: Remove the uncalled second reference-builder (def `compiler.py:1030`) so nobody
  patches the wrong copy. Confirmed zero prod callers.
- **Steps**: Remove it + its now-dead internal `_doctrine_yaml_reference` calls (`:1055/:1064/:1084`)
  and any orphaned imports. **Companion test breakage (do in THIS WP)**:
  `tests/charter/test_builtin_reader_relocation.py` imports `_build_references_from_yaml` (`:45`) and
  exercises it in two tests (`:70/:95`, `:111/:135`) — delete or rewrite those two tests so the WP01
  commit is green at its boundary (this test file is added to `owned_files`). Behavior-preserving for
  production.
- **Files**: `src/charter/activation/compiler.py`, `tests/charter/test_builtin_reader_relocation.py`.

### Subtask T007 – Turn repros green + extend compiler/parity tests
- **Purpose**: Prove the fix and pin it.
- **Steps**: Make T001 GREEN. Reconcile existing `tests/charter/test_compiler*.py` and
  `tests/specify_cli/charter_runtime/test_references_parity_refresh.py` to the completeness +
  determinism behavior (out-of-map edits with a one-line rationale each; do not silently green).
- **Files**: `tests/charter/test_catalog_completeness_4785.py`; existing compiler/parity tests (out-of-map, rationale).

## Test Strategy

- `PYTHONPATH=src python -m pytest tests/charter/test_catalog_completeness_4785.py tests/charter/test_compiler.py tests/specify_cli/charter_runtime/test_references_parity_refresh.py -q`
- Record RED-before / GREEN-after evidence in the Activity Log.

## Risks & Mitigations

- **Wrongly-eager resolution**: normalizing too aggressively could resolve ids that SHOULD stay
  unresolved. Mitigate with the T003 diagnostic path + a test asserting a genuinely-unknown id still
  degrades to a diagnostic (contract C4).
- **`generated_at` compare**: compare the computed catalog against on-disk catalog content only
  (exclude the timestamp itself) to decide preservation.

## Review Guidance

- Verify the fix is at the resolution seam, not a widened fallback string.
- Verify no second catalog writer was introduced (C-001/C-004).
- Verify authored sections + `charter.md` remain byte-identical.

## Activity Log

- 2026-09-19T21:23:09Z – system – Prompt created.
