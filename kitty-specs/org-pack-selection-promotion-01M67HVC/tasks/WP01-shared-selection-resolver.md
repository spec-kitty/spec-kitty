---
work_package_id: WP01
title: The shared selection resolver
dependencies: []
requirement_refs:
- FR-003
- NFR-001
- C-003
planning_base_branch: issue-6686-org-pack-selection-promotion
merge_target_branch: issue-6686-org-pack-selection-promotion
branch_strategy: Planning artifacts for this mission were generated on issue-6686-org-pack-selection-promotion. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6686-org-pack-selection-promotion unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Foundational
history:
- at: '2026-10-30T23:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- src/charter/activation/selection.py
- tests/charter/activation/test_selection_resolver.py
execution_mode: code_change
owned_files:
- src/charter/activation/selection.py
- src/charter/activation/api.py
- tests/charter/activation/test_selection_resolver.py
- tests/architectural/test_charter_activation_api_reexport.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The shared selection resolver

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) and behave
according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: implementer
- **Agent/tool**: claude

---

## Objectives & Success Criteria

One module, `src/charter/activation/selection.py`, owns the rule that turns an interview
selection (a declared id or a stem, in any layer's spelling) into an activation stem. It is
built on the layer-aware `IdentityIndex.build(repo_root)` that `charter context` already uses
(#6406/#6407), so org-pack and project-pack ids resolve. It is exported from
`charter.activation.api`, the only sanctioned seam for `specify_cli`.

Done when:

- `SelectionResolver`, `SelectionResolution` and `UnresolvedSelection` exist and are exported
  from both `charter.activation.selection.__all__` and `charter.activation.api.__all__`.
- `tests/charter/activation/test_selection_resolver.py` pins layer lookup (org and project),
  dedupe by stem, unknown ids, ambiguity under both policies, and one index build per run.
- `tests/architectural/test_charter_activation_api_reexport.py` lists the new symbol(s) in
  `_SEAM_TABLE`.

## Context & Constraints

- Read `kitty-specs/org-pack-selection-promotion-01M67HVC/plan.md` (Phase 1 contract) and
  `research.md` (D-1..D-5) first.
- `src/charter/activation/identity_index.py` is the authority. Do not add a second precedence
  rule, a second scan of the doctrine roots, or a local cache keyed on anything but the index.
- `src/charter/activation/api.py` is identity-only: `X as X` re-exports, no wrappers, never a
  `charter.offering` symbol (its module docstring and the negative gate both say so).
- The activation layer must not import `specify_cli` (the boundary runs the other way).
- Follow `python-conventions` and the repo's `__all__` convention (C-007): explicit `__all__`
  in the new module, symbols listed in the seam's `__all__` too.
- Import rule from `identity_index.py`: it must not import `charter.activation.resolver` or
  `profile_resolution`. Your module *may* import `identity_index` — it is the layer below it.

## Branch Strategy

- **Strategy**: single_branch — plan, implement and land on the topic branch.
- **Planning base branch**: `issue-6686-org-pack-selection-promotion`
- **Merge target branch**: `issue-6686-org-pack-selection-promotion`

## Subtasks & Detailed Guidance

### Subtask T001 – Create the selection resolver module

- **Purpose**: One rule for "selection id in, activation stem out", used by both writers.
- **Steps**:
  1. Create `src/charter/activation/selection.py` with a module docstring that names the defect
     (#6686) and the authority (`IdentityIndex`), and `__all__`.
  2. `@dataclass(frozen=True) class UnresolvedSelection: kind: ArtifactKind; raw_id: str; ambiguous: bool`
     plus a `urn` property returning `f"{kind.operator_token}:{raw_id}"`.
  3. `@dataclass(frozen=True) class SelectionResolution` with
     `stems: dict[str, list[str]]` (keyed `activated_<kind.plural>`, selection order, deduped)
     and `unresolved: list[UnresolvedSelection]`.
  4. `class SelectionResolver` holding one `IdentityIndex`, with:
     - `build(cls, repo_root: Path) -> SelectionResolver` → `IdentityIndex.build(repo_root)`
       (the single constructor call sites use; no second layer lookup);
     - `stem(self, kind, raw_id) -> str | None` → `None` when no layer knows the token, else the
       index's stored spelling (raising `ActivationIdCollisionError` for a known id no stem can
       represent, exactly as `IdentityIndex.stored_spelling` does);
     - `stems(self, kind, raw_ids) -> set[str]` for present-list comparison: a token that
       resolves to no stem is kept as written (the migration's existing comparison rule);
     - `resolve(self, selections: Mapping[ArtifactKind, Sequence[str]], *, refuse_ambiguous: bool = False) -> SelectionResolution`
       running the single loop: probe, dedupe by stem, collect unknown ids (`ambiguous=False`)
       and unrepresentable identities (`ambiguous=True`); with `refuse_ambiguous=True` raise the
       index's `ActivationIdCollisionError` instead of recording the ambiguity.
- **Files**: `src/charter/activation/selection.py`
- **Notes**: Keep it under ~120 lines and free of I/O beyond what the index does. A `kind` maps
  to its allow key with `f"activated_{kind.plural}"`; only kinds with at least one resolved stem
  appear in `stems()`.

### Subtask T002 – Export the resolver from the seam

- **Steps**: add `from charter.activation.selection import ... as ...` (identity form) to
  `src/charter/activation/api.py` and the same names to its `__all__`, in the module's existing
  style and grouping.
- **Files**: `src/charter/activation/api.py`
- **Notes**: The seam's completeness gate compares `__all__` to `_SEAM_TABLE` one-for-one, so
  T002 and T004 must agree on the exact symbol set.

### Subtask T003 – Resolver unit tests

- **Purpose**: Prove the shared rule, independently of either writer.
- **Steps**: create `tests/charter/activation/test_selection_resolver.py`, `pytestmark = [pytest.mark.unit, pytest.mark.fast]`, reusing the shared fixture builder
  `tests/charter/org_pack_identity_support.py` (`write_identity_org_pack`) for the org layer.
  Cover:
  - an org-pack declared id and its stem both resolve to the stem;
  - a project-layer artifact (`project_pack_root`) resolves too;
  - a built-in id still resolves (no regression);
  - the same artifact named twice (declared id + stem) appears once, in first-seen order;
  - an unknown id lands in `unresolved` with `ambiguous=False` and contributes no stem;
  - `refuse_ambiguous=True` raises `ActivationIdCollisionError` on the collision fixture from
    `tests/charter/activation/test_stored_spelling_6527.py`, while the default records it in
    `unresolved` with `ambiguous=True` (same fixture, two policies — positive control);
  - one index build per resolver: `build` is called once and `resolve` on two kinds does not
    rebuild (monkeypatch `IdentityIndex.build` with a counter, assert one call).
- **Files**: `tests/charter/activation/test_selection_resolver.py`
- **Notes**: Do not assert on the index's private tables; assert on the resolver's public
  output. Use real built-in artifact ids (e.g. `DIRECTIVE_010`) rather than mocks.

### Subtask T004 – Seam identity-gate row

- **Steps**: add one `(symbol, "charter.activation.selection")` row per exported symbol to
  `_SEAM_TABLE` in `tests/architectural/test_charter_activation_api_reexport.py`.
- **Files**: `tests/architectural/test_charter_activation_api_reexport.py`
- **Notes**: The gate asserts by identity, so exporting a copy/alias fails.

## Test Strategy

```bash
uv run pytest tests/charter/activation/test_selection_resolver.py tests/architectural/test_charter_activation_api_reexport.py tests/architectural/test_no_dead_modules.py -q
uv run ruff check src/charter/activation/selection.py src/charter/activation/api.py tests/charter/activation/test_selection_resolver.py
uv run mypy src/charter/activation/selection.py
```

The compiler/typecheck command must pass as well as the tests: a passing pytest run does not
replace `mypy` diagnostics.

## Risks & Mitigations

- **Second source of precedence**: forbidden; delegate to `IdentityIndex` only.
- **Dead module**: `test_no_dead_modules.py` requires reachability — the seam export and WP02/WP03
  call sites provide it; if they land later, land this WP with the seam export (the gate follows
  the import graph, and `api.py` is imported widely).
- **`__all__` drift**: seam `__all__` and `_SEAM_TABLE` must match exactly.

## Review Guidance

- Check the resolver has no doctrine-root scan of its own and no ordering logic that duplicates
  `IdentityIndex`.
- Check `resolve()` on an empty selection returns empty stems/unresolved (the migration relies on
  it not building the index when there is no selection — WP02 keeps that guard outside).
- Confirm the seam re-export is by identity, not a wrapper.

## Progress & Status

Record each subtask with `spec-kitty agent tasks mark-status T001 --status done` (and so on).
Report the commands you ran and their results in `tasks/WP01-*.md` review notes or the mission
tracer (`spec-kitty agent tracer-append --mission org-pack-selection-promotion-01M67HVC
--category approach --entry "..."`).
