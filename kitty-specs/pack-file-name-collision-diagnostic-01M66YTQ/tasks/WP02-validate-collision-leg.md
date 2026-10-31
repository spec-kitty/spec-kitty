---
work_package_id: WP02
title: Validate reports the collision
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-006
- FR-007
- C-002
- C-004
planning_base_branch: issue-6743-pack-file-name-collision-diagnostic
merge_target_branch: issue-6743-pack-file-name-collision-diagnostic
branch_strategy: Planning artifacts for this mission were generated on issue-6743-pack-file-name-collision-diagnostic. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6743-pack-file-name-collision-diagnostic unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pack-file-name-collision-diagnostic-01M66YTQ
base_commit: dca6308f515de8c3d5273686edb368c5b498e366
created_at: '2026-10-30T18:22:53.684515+00:00'
subtasks:
- T005
- T006
- T007
- T008
phase: Phase 2 - User Story 1 (MVP)
history:
- at: '2026-10-30T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/org_charter.py
- tests/charter/packs/test_org_charter_hooks.py
- tests/specify_cli/cli/commands/charter/test_charter_pack_tooling.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Validate reports the collision

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the profile in the frontmatter
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log before starting; address every item and
record it with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

`spec-kitty charter pack validate <pack>` must report a file-name collision
between the pack being validated and the built-in layer as an **error**, naming
the file name, both files, both declared ids and which file to rename.

Done when:

- The validate door (`validate_pack_with_org_charter`) returns a `ValidationResult`
  with `ok=False` for the issue's example pack.
- `render_validation_result` and the existing `--json` shape carry it with
  `category: "file_name_collision"` and no schema change.
- A same-id override, a disjoint pack, and a pack with distinct file names stay
  clean, including a pack validated from a directory that is not inside any
  repository.

## Context & Constraints

- Spec FR-002, FR-006, FR-007; C-002 (no `charter.offering` → `charter.activation`
  import), C-004 (no repo-config dependence).
- Plan DD-2; WP01 provides `IdentityIndex.file_name_collisions()`.
- Wire the leg in `src/charter/activation/org_charter.py::validate_pack_with_org_charter`
  — the documented "CLI's validation door". Do **not** touch
  `src/charter/offering/packs/pack_validator.py`.
- Reuse `ValidationIssue` / `ValidationResult` from
  `charter.offering.packs.pack_validator` unchanged.

## Branch Strategy

- Planning base and merge target: `issue-6743-pack-file-name-collision-diagnostic`.
- Execute in the lane worktree allocated by
  `spec-kitty agent action implement WP02 --agent python-pedro --mission pack-file-name-collision-diagnostic-01M66YTQ`.

## Subtasks & Detailed Guidance

### Subtask T005 – Red test: the validate door reports the collision

- **Purpose**: red-first proof through the real validation entry point.
- **Steps**:
  1. In `tests/charter/packs/test_org_charter_hooks.py`, add a test that builds a
     temp pack with `directives/024-locality-of-change.directive.yaml` declaring
     `ACME_024` (the built-in schema fields a `Directive` requires) and calls
     `validate_pack_with_org_charter(pack)`.
  2. Assert `result.ok is False`, exactly one error with
     `category == "file_name_collision"`, and that `issue.message` contains the
     file name `024-locality-of-change`, both ids (`ACME_024`, `DIRECTIVE_024`)
     and the rename advice.
  3. Run it; confirm it fails today (0 errors).
- **Files**: `tests/charter/packs/test_org_charter_hooks.py`

### Subtask T006 – Implement the collision leg

- **Purpose**: FR-002 / FR-004.
- **Steps**:
  1. In `validate_pack_with_org_charter`, after `validate_pack(...)`, build
     `IdentityIndex(org_roots=[pack_dir], project_root=None, offering_root=resolve_offering_root())`
     — pack + built-in only (C-004). Do not read `.kittify/config.yaml`.
  2. Query `file_name_collisions()` and turn every record into one error
     `ValidationIssue(severity="error", artifact_type=kind.plural, artifact_id=None,
     file=<the validated pack's file, else the first declaration path>,
     message=record.message(label=_pack_level_label(pack_dir)), category="file_name_collision")`.
  3. `_pack_level_label(pack_dir)`: read `pack.yaml` through
     `charter.offering.packs.pack_descriptor.load_pack_descriptor` and return the
     declared `pack_level` for files under `pack_dir`; on any failure return
     `"org"` (the deprecation window tolerates a missing descriptor). Built-in
     files keep the index's `built-in` layer label.
  4. Append the issues to `result.errors` and recompute `result.ok`.
- **Files**: `src/charter/activation/org_charter.py`
- **Notes**: keep the helper small and private; if `result.ok` is derived in
  `ValidationResult`, set `ok=len(errors) == 0` explicitly.

### Subtask T007 – CLI test: exit code and `--json` category

- **Purpose**: FR-007 through the production path.
- **Steps**:
  1. In `tests/specify_cli/cli/commands/charter/test_charter_pack_tooling.py`, add
     a `CliRunner` test invoking `["charter", "pack", "validate", str(pack)]` and
     asserting `exit_code == 1`, plus a `--json` variant asserting the payload's
     `errors[*]["category"] == "file_name_collision"` and `ok is False`.
  2. Reuse the file's existing fixture style for a temp pack.
- **Files**: `tests/specify_cli/cli/commands/charter/test_charter_pack_tooling.py`

### Subtask T008 – Positive controls

- **Purpose**: FR-006 — the new error must never fire on legitimate content.
- **Steps**:
  1. Same pack, file renamed to `acme-024-local-strictness.directive.yaml`
     declaring `ACME_024`: no `file_name_collision`, `result.ok is True`.
  2. Same pack name but the **same** declared id as the built-in
     (`DIRECTIVE_024`): no `file_name_collision` (deliberate override path).
  3. Run the validation from `monkeypatch.chdir` into a temp repo-less directory
     and confirm identical results (C-004).
- **Files**: `tests/charter/packs/test_org_charter_hooks.py`

## Test Strategy

```bash
uv run pytest tests/charter/packs/test_org_charter_hooks.py \
              tests/specify_cli/cli/commands/charter/test_charter_pack_tooling.py \
              tests/charter/packs/test_pack_validator.py -q
uv run mypy src/charter/activation/org_charter.py
uv run ruff check src/charter/activation/org_charter.py
uv run spec-kitty charter pack validate packs/internal   # must stay 0 errors
```

## Risks & Mitigations

- Reading repo config would make the command environment-dependent (C-004) → the
  control test chdirs outside a repo.
- Double-reporting: a built-in-only collision must still be reported once, not once
  per side.

## Review Guidance

- Is the index built from the pack path and the built-in root only?
- Does the error name the validated pack's file as the thing to rename?
- Are `pack_validator.py` and the JSON schema untouched?

## Progress & Status

- `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP02 --to <status>`
