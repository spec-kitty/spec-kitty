---
work_package_id: WP02
title: charter org add / charter org remove CLI door
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-003
- FR-004
- FR-005
- FR-006
- FR-009
- FR-010
- NFR-003
- NFR-004
- C-003
- C-004
planning_base_branch: issue-6267-charter-org-pack-registration
merge_target_branch: issue-6267-charter-org-pack-registration
branch_strategy: Planning artifacts for this mission were generated on issue-6267-charter-org-pack-registration. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6267-charter-org-pack-registration unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-org-pack-registration-01M6BTTJ
base_commit: 64f0664f1f5e6e21e1fddcf2ac3a46d2cba4f23b
created_at: '2026-11-01T19:16:11.872941+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 2 - Story packages
history:
- at: '2026-11-01T15:20:00Z'
  actor: planner-priti
  action: 'Prompt generated via planning artifacts for #6267'
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/org.py
create_intent:
- tests/cli/test_charter_org_registration.py
execution_mode: code_change
model: deepseek-v4.1-flash-1017
owned_files:
- src/specify_cli/cli/commands/charter/org.py
- tests/cli/test_charter_org_registration.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – `charter org add` / `charter org remove` CLI door

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

## Objectives & Success Criteria

`spec-kitty charter org add <name> --local-path <dir> [--url <url>] [--ref <ref>]
[--source-type git|https|artifactory|api] [--subdir <dir>] [--force] [--json]` registers an org
Charter Pack with the current project after validating it, and `spec-kitty charter org remove <name>`
retires it. Both are purely local, both fail closed, both write nothing on a refusal, and both can
report JSON.

## Context & Constraints

- Spec: `kitty-specs/charter-org-pack-registration-01M6BTTJ/spec.md` (FR-001, FR-003–FR-006,
  FR-009, FR-010, NFR-003, NFR-004, C-003, C-004).
- Plan: `kitty-specs/charter-org-pack-registration-01M6BTTJ/plan.md` (Design decisions 3–9).
- Owner module: `src/specify_cli/cli/commands/charter/org.py` (already holds `init`/`validate`,
  registered by `_app.py` — no registration change needed).
- Project root: `specify_cli.core.paths.locate_project_root()`.
- Validation door: `charter.packs.validate_pack_with_org_charter` (the same one `org validate`
  calls) with `render_validation_result` for output.
- Write seam: `charter.drg.register_org_pack` / `unregister_org_pack` (WP01).

## Branch Strategy

- **Strategy**: `issue-6267-charter-org-pack-registration`
- **Planning base branch**: `main`
- **Merge target branch**: `main`

## Subtasks & Detailed Guidance

### Subtask T006 – Failing CLI acceptance tests

- **Purpose**: red-first through the pre-existing entry point (the `charter_app` Typer app).
- **Steps**: create `tests/cli/test_charter_org_registration.py` (markers `unit`, `fast`) with a
  `tmp_path` project fixture (`.kittify/config.yaml` + a pack scaffolded by
  `charter org init`), and tests mirroring spec User Stories 1–3 plus the edge cases. The first run
  must fail with `No such command 'add'` / `No such command 'remove'`.
- **Files**: `tests/cli/test_charter_org_registration.py`
- **Notes**: use `typer.testing.CliRunner` and ``runner.invoke(app, [...], env={"SPECIFY_REPO_ROOT": str(tmp_path)})``
  or run inside `monkeypatch.chdir(project)` — whichever the existing CLI tests use for root
  resolution; assert on both exit code and file bytes.

### Subtask T007 – `org add` option parsing and input refusals

- **Purpose**: all cheap refusals before any I/O that can write.
- **Steps**: implement `add` with the options above. Refuse (exit 1, nothing written):
  blank name; reserved names `built-in` and `project`; `--ref` or `--source-type` without `--url`;
  a `--source-type` outside the four accepted values; an invalid `--subdir` (let `OrgPackConfig`
  raise and render the message); no project root.
- **Files**: `src/specify_cli/cli/commands/charter/org.py`
- **Notes**: keep imports of the heavy registry/validation modules inside the command body, matching
  the module's existing style.

### Subtask T008 – Add preconditions and validation

- **Purpose**: never register something the readers will reject.
- **Steps**: build `OrgPackConfig(name=..., local_path=..., [subdir], [source_type], [url], [ref])`;
  resolve `effective_root(project_root)`; if the root exists, run
  `validate_pack_with_org_charter(root)` and exit 1 with the rendered errors on failure; without
  `--url` the root must exist (exit 1 naming the path when it does not); with `--url` an absent root
  is fine and the command prints the `spec-kitty charter fetch <name>` follow-up.
- **Notes**: an `OrgPackEnvVarUnsetError` from `effective_root` renders as a normal refusal, not a
  traceback.

### Subtask T009 – Duplicate refusal and `--force`

- **Steps**: existing name without `--force` → exit 1 naming `--force`; with `--force` replace in
  place through `register_org_pack(..., replace=True)`, preserving declaration order.

### Subtask T010 – `org remove`

- **Steps**: unknown name → exit 1 listing configured names; otherwise remove and print the pack
  directory that stays on disk (C-003: never delete files).

### Subtask T011 – `--json` and refusal rendering

- **Steps**: `--json` on both commands: `add` → `{pack, config, replaced, validated, fetched}`;
  `remove` → `{removed, config}`. Use `console.emit_json` for success and the module's existing
  coded-error helper style for refusals.

### Subtask T012 – No-network assertion

- **Steps**: add a test that fails if any network primitive is touched during `add`/`remove`
  (monkeypatch `socket.socket` to raise, or patch the snapshot/git source entry points) and run it
  over both commands.

## Test Strategy

```bash
uv run pytest tests/cli/test_charter_org_registration.py -q
uv run pytest tests/cli/test_doctrine_org_commands.py -q   # existing init/validate behaviour unchanged
uv run ruff check src/specify_cli/cli/commands/charter/org.py tests/cli/test_charter_org_registration.py
uv run mypy src/specify_cli/cli/commands/charter/org.py
```

## Risks & Mitigations

- Writing on a refused path → every refusal test asserts byte-identical config.
- Expanding a templated `local_path` → store verbatim; resolve only for validation.
- `--help` latency → no module-level import of the registry/validation stack.

## Review Guidance

- Walk each spec acceptance scenario against a test name.
- Confirm the refusal assertions each have their positive control on the same fixture.
- Confirm `charter fetch` / `charter org validate` behaviour is untouched.
