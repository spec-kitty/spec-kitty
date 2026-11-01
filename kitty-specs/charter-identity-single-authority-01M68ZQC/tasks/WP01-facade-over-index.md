---
work_package_id: WP01
title: The facades answer from the identity index
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-008
- NFR-004
- NFR-005
planning_base_branch: issue-6433-charter-identity-single-authority
merge_target_branch: issue-6433-charter-identity-single-authority
branch_strategy: Planning artifacts for this mission were generated on issue-6433-charter-identity-single-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6433-charter-identity-single-authority unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - One authority
history:
- at: '2026-10-30T12:55:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/activation/test_identity_facade_6433.py
execution_mode: code_change
owned_files:
- src/charter/activation/kind_vocabulary.py
- src/charter/activation/identity_index.py
- tests/charter/test_directive_resolution_memoization.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The facades answer from the identity index

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (`spec-kitty agent profile show python-pedro`) and behave according to it before parsing the rest of this prompt.

## Objectives & Success Criteria

- `resolve_artifact_urn`, `resolve_config_id` and `resolve_selected_id_to_stem` answer from `IdentityIndex`; no scan-and-match loop remains behind them.
- The facade accepts exactly the spellings the index accepts (stem, declared id, `<kind>:<id>` URN, normalised directive id), and refuses a genuinely unknown token with the same `UnknownArtifactIdError` message it raises today.
- A directive declared id that no filename can represent still raises `UnrepresentableDirectiveIdError`.
- A caller-threaded `ResolutionPass` still yields one layer scan per kind (NFR-004).

## Context & Constraints

- Read: `spec.md` (FR-001..FR-003, FR-008, C-001..C-004), `plan.md` (IC-01), `research.md` §2, §4.
- `identity_index.py` imports `kind_vocabulary`, so the facade imports `IdentityIndex` inside the function, with `# noqa: PLC0415`.
- `IdentityIndex._scan` currently calls `_scan_roots`/`_scan_dir_matches` directly. Give `from_roots` an optional `resolution_pass` and read the file list through `kind_vocabulary._iter_artifact_paths(..., resolution_pass=self._pass)` so scans and id reads are memoised; derive the layer per path.
- The directive rule is direction-specific and must not be flattened: the index's `declared_id` stays permissive (compile and the consistency check rely on it); the facade refuses a declared directive id with no representable stem, which is `index.stem(kind, token) is None` while `declared_id` is not.
- Error messages are part of the contract (C-002). Reuse `unknown_artifact_id_error(...)` and the existing `UnrepresentableDirectiveIdError` text verbatim.

## Branch Strategy

- **Strategy**: single branch on `issue-6433-charter-identity-single-authority`; planning base and merge target are the same branch.
- **Planning base branch**: `issue-6433-charter-identity-single-authority`
- **Merge target branch**: `issue-6433-charter-identity-single-authority`

## Subtasks & Detailed Guidance

### Subtask T001 – Write the failing parity tests first

- **Purpose**: prove the divergence before changing behaviour.
- **Steps**: create `tests/charter/activation/test_identity_facade_6433.py` with a fixture that has a built-in artifact, an org-pack artifact whose stem differs from its id, and a project-layer artifact. Assert: (a) for every entry the index indexes, `resolve_artifact_urn(kind, stem|declared_id)` returns `<kind>:<id>` and equals the index's answer; (b) a `<kind>:<id>` URN and a normalised directive id resolve to the same URN as the stem (red today); (c) `resolve_config_id` returns the stem for every declared id and raises `UnrepresentableDirectiveIdError` for a directive id whose file name another layer binds to a different id; (d) `resolve_selected_id_to_stem` answers stem/declared-id/unknown identically to before; (e) a `ResolutionPass` threaded through several `resolve_config_id` calls performs one `_iter_artifact_paths` scan per kind (monkeypatch-count); (f) `ArtifactKind.ANTI_PATTERN` (no files, nothing indexed) still refuses with `UnknownArtifactIdError` (analysis A2).
- **Files**: `tests/charter/activation/test_identity_facade_6433.py`.
- **Parallel?**: no.
- **Notes**: keep the existing modules (`test_kind_vocabulary.py`, `test_config_stem_parity.py`, `test_directive_identity_mapping.py`) untouched; they are the behaviour pins. Analysis A1: the facade is also consumed by `_cascade_shared.drg_urn_to_config_id` and the two upgrade migrations, so run their modules too (`tests/charter/test_kind_vocabulary.py`, `tests/upgrade/` slices that call `resolve_selected_id_to_stem`) and record any assertion that newly passes as intentional widening in the WP history, never as a regression to revert.

### Subtask T002 – Let the index read through the resolution pass

- **Purpose**: keep one scan per pass once the facades build an index per call.
- **Steps**: add `resolution_pass: kind_vocabulary.ResolutionPass | None = None` to `IdentityIndex.from_roots`; replace `_scan`'s direct `_scan_roots`/`_scan_dir_matches` loop with `kind_vocabulary._iter_artifact_paths(..., resolution_pass=self._pass)`; compute `_layer_of(path.parent, ...)` or an equivalent path-based layer.
- **Files**: `src/charter/activation/identity_index.py`.
- **Notes**: `_iter_artifact_paths` returns the same order the index used, so first-match precedence is unchanged (C-004).

### Subtask T003 – `resolve_artifact_urn` delegates

- **Purpose**: one rule for stem/id → URN.
- **Steps**: build the index from the same roots; resolve `declared = index.declared_id(...)`; return the URN when the token is known *and* (for a directive declared id) `index.stem_for_declared_id(...)` is not `None` or the token is itself a file stem; otherwise raise `unknown_artifact_id_error(...)`.
- **Review round 1 correction**: the unrepresentable directive case keeps this entry point's long-standing single refusal type (`UnknownArtifactIdError`); `resolve_config_id` is the surface that names it precisely (`UnrepresentableDirectiveIdError`). C-002 forbids changing the failure contract here.
- **Files**: `src/charter/activation/kind_vocabulary.py`.
- **Notes**: delete the now-dead private helpers only if nothing else uses them (`_declares_id` may still be used elsewhere — check).

### Subtask T004 – `resolve_config_id` delegates

- **Purpose**: one rule for URN → stem.
- **Steps**: parse and validate the URN as today (same `ValueError` shapes), then `stem = index.stem_for_declared_id(kind, artifact_id)`; return it; if it is `None` and the index knows the id, raise `UnrepresentableDirectiveIdError`; otherwise raise the same unknown-id error text as today.
- **Review round 1 correction**: `stem_for_declared_id` tries a directive id verbatim first and its normalised form second, so a slug-named `id:` (`CHOSEN-POLICY`) still resolves and `directive:24` resolves too.
- **Files**: `src/charter/activation/kind_vocabulary.py`.
- **Parallel?**: yes, after T003.
- **Notes**: the directive "highest matching layer whose stem round-trips" rule is `_representable_stem`; verify with the shadowed-stem fixture.

### Subtask T005 – `resolve_selected_id_to_stem` delegates

- **Purpose**: remove the third scan.
- **Steps**: directive branch keeps the `UnrepresentableDirectiveIdError` re-raise; both branches resolve through the index; unknown stays `None`.
- **Files**: `src/charter/activation/kind_vocabulary.py`.
- **Parallel?**: yes, after T003.

## Test Strategy

```bash
uv run pytest tests/charter/activation/test_identity_facade_6433.py -q
uv run pytest tests/charter/test_kind_vocabulary.py tests/charter/test_config_stem_parity.py \
  tests/charter/test_directive_identity_mapping.py tests/charter/test_kind_vocabulary_recursion_parity.py -q
uv run ruff check src/charter/activation/kind_vocabulary.py src/charter/activation/identity_index.py
uv run ruff format --check src/charter/activation/kind_vocabulary.py src/charter/activation/identity_index.py
uv run mypy src/charter/activation/kind_vocabulary.py src/charter/activation/identity_index.py
```

## Risks & Mitigations

- Import cycle: function-local import; never move `IdentityIndex` into a module-level import of `kind_vocabulary`.
- Malformed-YAML fast path: accepted, documented; do not restore a second reader.
- Complexity: keep each facade under the complexity ceiling by extracting a shared private helper if needed.

## Review Guidance

- Confirm the index — not a new helper — decides the outcome in every path.
- Confirm the ambiguous-directive refusal and the unknown-token message are byte-identical to before.
- Confirm no existing behaviour pin changed.
