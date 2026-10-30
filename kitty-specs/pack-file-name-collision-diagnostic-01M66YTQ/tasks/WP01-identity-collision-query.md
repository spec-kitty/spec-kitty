---
work_package_id: WP01
title: Identity collision query
dependencies: []
requirement_refs:
- FR-001
- FR-004
- FR-005
- NFR-001
- NFR-002
- C-001
- C-005
planning_base_branch: issue-6743-pack-file-name-collision-diagnostic
merge_target_branch: issue-6743-pack-file-name-collision-diagnostic
branch_strategy: Planning artifacts for this mission were generated on issue-6743-pack-file-name-collision-diagnostic. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6743-pack-file-name-collision-diagnostic unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pack-file-name-collision-diagnostic-01M66YTQ
base_commit: dca6308f515de8c3d5273686edb368c5b498e366
created_at: '2026-10-30T17:54:53.255807+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Foundational
history:
- at: '2026-10-30T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/activation/test_file_name_collision_diagnostic_6743.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/identity_index.py
- tests/charter/activation/test_identity_index.py
- tests/charter/activation/test_file_name_collision_diagnostic_6743.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Identity collision query

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in
the frontmatter (or any user-defined profile), and behave according to its
guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`)
before starting. Address every feedback item; record what you changed with
`spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

Add **one** detection query to `charter.activation.identity_index.IdentityIndex`:
"which file names stand for more than one declared id". It must be computed from
the per-kind tables the index already builds, and it must be the only place the
collision set is computed — the writer refusal (`stored_spelling` /
`collision_error`) and both diagnostics read the same data.

Done when:

- `IdentityIndex.file_name_collisions()` returns a `FileNameCollision` for every
  stem whose entries declare more than one distinct id, in `(kind, file_name)`
  order, with declarations in index precedence order.
- The issue's own case is reproduced by a unit test: an org directive file named
  `024-locality-of-change.directive.yaml` declaring `ACME_024` next to the
  built-in `024-locality-of-change` declaring `DIRECTIVE_024`.
- A same-id override and a disjoint pack on the same fixture family produce no
  record (positive control).
- `FileNameCollision.declarations` equals
  `ActivationIdCollisionError.declarations` for the same fixture.
- `ActivationIdCollisionError`'s message is unchanged (existing tests stay green).

## Context & Constraints

- Spec: `kitty-specs/pack-file-name-collision-diagnostic-01M66YTQ/spec.md`
  (FR-001, FR-004, FR-005; NFR-001, NFR-002; C-001, C-005)
- Plan: `kitty-specs/pack-file-name-collision-diagnostic-01M66YTQ/plan.md` (DD-1, DD-4)
- Research: `kitty-specs/pack-file-name-collision-diagnostic-01M66YTQ/research.md`
- Doctrine: `spec-kitty charter context --action implement`, then
  `--include directive:034-test-first-development` and
  `--include tactic:acceptance-criteria-non-vacuity`.

Constraints:

- **No extra I/O.** The query reads the memoised `_table(kind)` (`entries`,
  `ids_by_stem`). It must not call `_scan()` and must not re-read any file: one
  index build per command is the only scan, and the query adds nothing on top of
  it. If a caller passes `kinds=`, only those tables are built.
- **Layering.** `identity_index.py` must not import `charter.activation.resolver`
  or `charter.activation.profile_resolution` (module docstring rule); importing
  `activation_engine` is already done and stays.
- **No behaviour change** to resolution or writing (C-005). `stored_spelling`,
  `stem`, `collision_error` keep their semantics and messages.

## Branch Strategy

- Planning base branch and merge target are both
  `issue-6743-pack-file-name-collision-diagnostic`.
- This work package executes in the lane worktree that
  `spec-kitty agent action implement WP01 --agent python-pedro --mission pack-file-name-collision-diagnostic-01M66YTQ`
  allocates from `lanes.json`. Never create or pick a worktree by hand.

## Subtasks & Detailed Guidance

### Subtask T001 – Red test: the query reports the org-vs-built-in directive collision

- **Purpose**: prove the defect before the fix (ATDD, DIRECTIVE_034).
- **Steps**:
  1. In `tests/charter/activation/test_identity_index.py`, add a test next to
     `test_stored_spelling_refuses_a_declared_id_whose_file_name_another_layer_uses`.
     Reuse that file's `project` fixture and `_write` helper.
  2. Write `acme/directives/024-locality-of-change.directive.yaml` declaring
     `ACME_024`, build `IdentityIndex.build(project)`, and assert the query returns
     exactly one record for `ArtifactKind.DIRECTIVE` whose `file_name` is
     `024-locality-of-change` and whose declarations are, in order,
     `("org", "ACME_024", <org file>)` then `("built-in", "DIRECTIVE_024", <built-in file>)`.
  3. Run it and confirm it fails because `file_name_collisions` does not exist.
- **Files**: `tests/charter/activation/test_identity_index.py`
- **Notes**: the built-in path is found today with
  `kind_vocabulary._built_in_scan_dir(D)` then `rglob(...)`; copy that pattern.

### Subtask T002 – Implement `FileNameCollision` + `file_name_collisions()`

- **Purpose**: FR-001 / FR-004 / NFR-001 / NFR-002.
- **Steps**:
  1. Add a frozen dataclass `FileNameCollision` with `kind`, `file_name`,
     `declarations: tuple[tuple[str, str, Path | None], ...]`
     (`(layer, declared id, path)`, precedence order), a `sort_key` property
     returning `(kind.value, file_name)`, and a `message(*, label=None)` method.
  2. Add `IdentityIndex.file_name_collisions(*, kinds: Sequence[ArtifactKind] | None = None)`
     returning a tuple of records: for each requested kind (default: every
     `ArtifactKind` with a non-empty `glob_pattern`), group
     `self._table(kind).entries` by `stem`, keep groups with more than one
     distinct `declared_id`, and sort the result by `sort_key`.
  3. `message()` renders: the file name, each participating file as
     `the <layer> file <path> declares '<id>'` joined with `; `, and the rename
     advice — naming the non-built-in file(s) when a built-in file participates,
     else "Rename one of them" — mirroring `ActivationIdCollisionError`'s wording
     closely enough that a reader sees one story. The optional `label` callable
     maps `(layer, path) -> str` so the validate surface can name a pack by the
     level its `pack.yaml` declares. Keep the message free of machine-local paths
     beyond the real file paths the operator needs.
- **Files**: `src/charter/activation/identity_index.py`
- **Parallel?**: yes with T003 (same file, sequence them if both editors touch
  `collision_error`).
- **Notes**: export via `__all__` (charter rule for public symbols).

### Subtask T003 – Share the per-stem declarations helper with `collision_error()`

- **Purpose**: FR-005 — one computation, two views.
- **Steps**:
  1. Extract the `sharing = [item for item in table.entries if item.stem == file_name]`
     logic into a private helper (`_declarations_for_stem(table, stem)`), used by
     both `collision_error()` and `file_name_collisions()`.
  2. Do **not** change `ActivationIdCollisionError`'s constructor arguments, its
     message, or its attributes: `tests/charter/activation/test_stored_spelling_6527.py`
     and `test_identity_index.py` pin the exact string.
- **Files**: `src/charter/activation/identity_index.py`

### Subtask T004 – Agreement test with the writer refusal, plus controls

- **Purpose**: FR-005 and the non-vacuity positive controls for FR-006.
- **Steps**:
  1. New file `tests/charter/activation/test_file_name_collision_diagnostic_6743.py`
     (`pytestmark = [pytest.mark.unit, pytest.mark.fast]`).
  2. On one fixture, build the index twice (or once) and assert
     `collision.declarations == [(where, declared) for where, declared in error.declarations]`
     where `error` comes from `pytest.raises(ActivationIdCollisionError)` on
     `stored_spelling(D, "DIRECTIVE_024")`. The `where` strings differ in the
     "file " prefix; normalise explicitly in the test rather than changing
     production wording.
  3. Same fixture family controls, each asserted in the same test or a sibling
     test on the same builder: a same-id override (`ACME_024` declared by a
     differently-named file) yields no collision, and a disjoint org pack yields
     no collision. The control must fail if the query is made to always return [].
- **Files**: `tests/charter/activation/test_file_name_collision_diagnostic_6743.py` (new)

## Test Strategy

```bash
uv run pytest tests/charter/activation/test_identity_index.py \
              tests/charter/activation/test_file_name_collision_diagnostic_6743.py \
              tests/charter/activation/test_stored_spelling_6527.py -q
uv run mypy src/charter/activation/identity_index.py
uv run ruff check src/charter/activation/identity_index.py tests/charter/activation/
```

## Risks & Mitigations

- Accidentally scanning → assert via `monkeypatch` on `IdentityIndex._scan` that a
  second `file_name_collisions()` call performs no further scans.
- Message drift with the writer refusal → the agreement test asserts the data, and
  the existing exact-string tests protect the wording.

## Review Guidance

- Is the query reading only memoised tables?
- Does `collision_error()` still produce byte-identical output?
- Are the three controls (collision / same-id / disjoint) on one fixture family?

## Progress & Status

- `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP01 --to <status>`
