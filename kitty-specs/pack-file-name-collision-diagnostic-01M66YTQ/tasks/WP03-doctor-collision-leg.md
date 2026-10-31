---
work_package_id: WP03
title: Doctor reports the collision across the chain
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-007
- NFR-002
- NFR-003
- NFR-004
planning_base_branch: issue-6743-pack-file-name-collision-diagnostic
merge_target_branch: issue-6743-pack-file-name-collision-diagnostic
branch_strategy: Planning artifacts for this mission were generated on issue-6743-pack-file-name-collision-diagnostic. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6743-pack-file-name-collision-diagnostic unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pack-file-name-collision-diagnostic-01M66YTQ
base_commit: dca6308f515de8c3d5273686edb368c5b498e366
created_at: '2026-10-30T19:10:51.643590+00:00'
subtasks:
- T009
- T010
- T011
- T012
phase: Phase 3 - User Story 2
history:
- at: '2026-10-30T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/cli/commands/test_doctor_charter_packs_file_name_collision.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/_charter_pack_collect.py
- src/specify_cli/cli/commands/_profile_health_render.py
- src/specify_cli/cli/commands/doctor.py
- tests/specify_cli/cli/commands/test_doctor_charter_packs_file_name_collision.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Doctor reports the collision across the chain

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the profile in the frontmatter
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log before starting; address every item and
record it with `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Objectives & Success Criteria

`spec-kitty doctor charter-packs` must report a file-name collision across the
configured chain (project, org packs, built-in) as an **error**, in the human
output and in `--json`, and exit 1 — instead of printing
`Collisions: none — every artifact resolves from a single layer.`

Done when:

- `org_drg["file_name_collisions"]` is always present (empty list on a clean tree).
- A colliding chain appends exactly one message to `org_drg["errors"]`, so
  `CharterPackHealthReport.healthy` is false and RC=1.
- The human renderer prints a `File-name collisions` block naming the file name,
  both layers, both ids and the rename advice.
- The existing `Collisions:` (same-id override) section and `PackHealth` output are
  unchanged, and the command never raises on a broken chain.

## Context & Constraints

- Spec FR-003, FR-007; NFR-002, NFR-003, NFR-004.
- Plan DD-3. WP01 provides `IdentityIndex.file_name_collisions()`.
- Follow the established pattern in `_charter_pack_collect.py`
  (`_run_cross_grain_check`, `_run_operating_procedures_check`): a `_run_*_check(report, ...)`
  helper called from `doctor.py` **before** `exit_code` is derived, appending to
  `org_drg["errors"]` and always writing a structured list.
- Do not add a new health field and do not assemble a parallel report.

## Branch Strategy

- Planning base and merge target: `issue-6743-pack-file-name-collision-diagnostic`.
- Execute in the lane worktree allocated by
  `spec-kitty agent action implement WP03 --agent python-pedro --mission pack-file-name-collision-diagnostic-01M66YTQ`.

## Subtasks & Detailed Guidance

### Subtask T009 – Red test: doctor reports the chain collision

- **Purpose**: red-first proof through the real command, including the chain case
  (`validate` cannot see it).
- **Steps**:
  1. New file `tests/specify_cli/cli/commands/test_doctor_charter_packs_file_name_collision.py`
     (`pytestmark = [pytest.mark.unit, pytest.mark.fast]`), modelled on
     `test_doctor_charter_packs_collisions.py` (`contextlib.chdir`, `.kittify/config.yaml`,
     `CliRunner` on `doctor_app`).
  2. Fixture: an org pack (`pack/directives/...` or `tactics/shared.tactic.yaml`
     declaring `org-a`) plus a project pack (`.kittify/charter-packs/<kind>/shared.tactic.yaml`
     declaring `proj-b`) that share a file name.
  3. Text test: RC=1 and the output names `shared`, `org`, `project`, `org-a`, `proj-b`.
     `--json` test: `payload["org_drg"]["file_name_collisions"]` is a non-empty list
     of dicts with `kind`, `file_name`, `declarations`.
  4. Control on the same fixture family: distinct file names → the list is `[]`.
  5. Run it; confirm it fails today.
- **Files**: `tests/specify_cli/cli/commands/test_doctor_charter_packs_file_name_collision.py` (new)

### Subtask T010 – Implement the collector and the check leg

- **Purpose**: FR-003 / FR-007 / NFR-003.
- **Steps**:
  1. `_collect_file_name_collisions(repo_root) -> list[dict[str, object]]`: build
     `IdentityIndex.build(repo_root)`, query `file_name_collisions()`, and emit
     `{"kind", "file_name", "declarations": [{"layer", "declared_id", "path"}]}`
     per record, already sorted by the index (NFR-002).
  2. `_run_file_name_collision_check(report, repo_root)`: on success write the
     structured list to `org_drg["file_name_collisions"]`; when non-empty append
     one message (naming count, the file name(s) and the rename advice) to
     `org_drg["errors"]`; on any exception append
     `f"file-name collision scan error: {exc}"` to `org_drg["errors"]` and leave the
     key unset-with-no-claim or an empty list — never raise (NFR-003).
  3. Add both to `__all__` if that module's convention lists the `_run_*` helpers.
- **Files**: `src/specify_cli/cli/commands/_charter_pack_collect.py`

### Subtask T011 – Render and wire

- **Purpose**: the human surface and the exit code.
- **Steps**:
  1. In `_profile_health_render.py`, add a renderer that prints
     `\n[bold red]File-name collisions[/bold red] — <n> file name(s) stand for more than one id\n`
     and one indented, `escape`d line per collision. Called from the human path only.
  2. In `doctor.py::charter_packs`, call `_run_file_name_collision_check(report, repo_root)`
     beside `_run_cross_grain_check(report)` (before `exit_code` is derived), and
     call the renderer beside `_render_cross_grain_findings(report)` on both the
     no-packs path and the normal path.
- **Files**: `src/specify_cli/cli/commands/_profile_health_render.py`,
  `src/specify_cli/cli/commands/doctor.py`

### Subtask T012 – Determinism, no-crash and no-slowdown

- **Purpose**: NFR-002 / NFR-003 / NFR-004.
- **Steps**:
  1. Test: two consecutive runs on the colliding fixture produce byte-identical
     `file_name_collisions` lists.
  2. Test: `_run_file_name_collision_check` on a repo whose chain config is
     malformed records an error entry and does not raise.
  3. Time `spec-kitty doctor charter-packs` (and `charter pack validate packs/internal`)
     before/after on this checkout; record both numbers in the PR body.
- **Files**: the new test file

## Test Strategy

```bash
uv run pytest tests/specify_cli/cli/commands/test_doctor_charter_packs_file_name_collision.py \
              tests/specify_cli/cli/commands/test_doctor_charter_packs_collisions.py \
              tests/specify_cli/cli/commands/test_doctor_charter_packs.py \
              tests/specify_cli/cli/commands/test_doctor_operating_procedures.py -q
uv run mypy src/specify_cli/cli/commands/_charter_pack_collect.py src/specify_cli/cli/commands/_profile_health_render.py
uv run ruff check src/specify_cli/cli/commands/
uv run spec-kitty doctor charter-packs   # this repo must stay clean of the new finding
```

## Risks & Mitigations

- Section order in the human output is asserted by golden tests → append the new
  block after the existing findings, do not reorder.
- A collector exception must not turn RC=1 into a traceback (NFR-003).

## Review Guidance

- Is the structured key always present?
- Does the exit code come from the existing `healthy` flag, not a new field?
- Is the existing override-collision section untouched?

## Progress & Status

- `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP03 --to <status>`
