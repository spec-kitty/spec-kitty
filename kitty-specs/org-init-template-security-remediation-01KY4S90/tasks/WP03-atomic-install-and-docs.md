---
work_package_id: WP03
title: Atomic force install, PipelineError guards, docs
dependencies: []
requirement_refs:
- FR-002
- FR-008
- FR-009
- FR-011
tracker_refs: []
planning_base_branch: feat/doctrine-org-init-from-template
merge_target_branch: feat/doctrine-org-init-from-template
branch_strategy: Planning artifacts for this mission were generated on feat/doctrine-org-init-from-template. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/doctrine-org-init-from-template unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-org-init-template-security-remediation-01KY4S90
base_commit: dd56dd53d4f80079dab9c969c7dd6e85fb516bda
created_at: '2026-07-22T11:56:21.448891+00:00'
subtasks:
- T009
- T010
- T011
phase: Phase 3 - Install and docs
assignee: ''
agent: cursor
shell_pid: '67809'
history:
- at: '2026-07-22T11:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/doctrine/template_render/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/doctrine/template_render/pipeline.py
- tests/specify_cli/doctrine/test_template_render_pipeline.py
- docs/api/cli-commands.md
role: implementer
tags: []
task_type: implement
---

# Work Package Prompt: WP03 – Atomic force install, PipelineError guards, docs

## ⚡ Do This First: Load Agent Profile

```
/ad-hoc-profile-load python-pedro
```

## Objectives & Success Criteria

- `--force` install uses move-aside-then-swap so mid-failure does not destroy the prior pack without recovery path (FR-008).
- `assert source is not None` and destination-exists-without-force become explicit `PipelineError` (FR-009).
- Docs describe credential skip for `--template` (FR-002) and that `.templateignore` `fnmatch` `*` may cross `/` (FR-011).

## Context & Constraints

- Do not clear `pr:deferred` (C-001).
- Update `docs/api/cli-commands.md` `spec-kitty doctrine org init` section (currently missing `--template` options).

## Branch Strategy

- **Planning base branch**: `feat/doctrine-org-init-from-template`
- **Merge target branch**: `feat/doctrine-org-init-from-template`

## Subtasks & Detailed Guidance

### Subtask T009 – Atomic force

- Replace `rmtree(pack_path)` then `move(staging)` with: backup = `pack_path.with_name(pack_path.name + ".bak-<nonce>")`; `move(pack_path, backup)`; `move(staging, pack_path)`; then `rmtree(backup)`.
- On failure after move-aside, best-effort restore from backup.
- Add unit coverage for force overwrite preserving prior content on simulated install failure if practical; at minimum cover successful force path and that backup is cleaned on success.

### Subtask T010 – Explicit guards

- If `source is None` after resolve without error → `PipelineError` (rule e.g. `pipeline.source_missing`).
- Destination exists without force inside `_install_staging` → `PipelineError` (not bare `RuntimeError`), or keep unreachable but type-consistent.

### Subtask T011 – Docs

- In `docs/api/cli-commands.md` under `doctrine org init`: document `--template`, `--org-name`, `--local-path`, `--branch`, `--force`.
- State: `--template` HTTPS fetch does **not** inject `GIT_TOKEN` (use SSH or embed credentials if needed).
- State: `.templateignore` uses fnmatch subset; `*` can match across `/` — not full gitignore.

## Test Strategy

```bash
PWHEADLESS=1 pytest tests/specify_cli/doctrine/test_template_render_pipeline.py -q
```

## Risks & Mitigations

- Crash leaving `.bak-*` → document operator cleanup; best-effort restore.

## Review Guidance

- No `assert` for required resolve result; force path is move-aside-then-swap.
- Docs mention credential skip + fnmatch caveat.

## Activity Log

### 2026-07-22 – Prompt generated
**Agent**: system
**Action**: Prompt generated via /spec-kitty.tasks
- 2026-07-22T12:07:22Z – user – shell_pid=67809 – Review passed: security remediation verified
