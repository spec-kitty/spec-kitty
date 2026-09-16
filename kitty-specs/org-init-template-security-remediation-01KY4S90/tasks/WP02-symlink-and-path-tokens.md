---
work_package_id: WP02
title: Symlink skip + path-token reject + single-pass leftovers
dependencies: []
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
- FR-010
- NFR-002
- NFR-003
tracker_refs: []
planning_base_branch: feat/doctrine-org-init-from-template
merge_target_branch: feat/doctrine-org-init-from-template
branch_strategy: Planning artifacts for this mission were generated on feat/doctrine-org-init-from-template. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/doctrine-org-init-from-template unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-org-init-template-security-remediation-01KY4S90
base_commit: dd56dd53d4f80079dab9c969c7dd6e85fb516bda
created_at: '2026-07-22T11:54:44.793734+00:00'
subtasks:
- T005
- T006
- T007
- T008
phase: Phase 2 - Copy and substitute
assignee: ''
agent: cursor
shell_pid: '66088'
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
- src/specify_cli/doctrine/template_render/ignore_copy.py
- src/specify_cli/doctrine/template_render/substitute.py
- tests/specify_cli/doctrine/test_template_render_ignore_copy.py
- tests/specify_cli/doctrine/test_template_render_substitute.py
role: implementer
tags: []
task_type: implement
---

# Work Package Prompt: WP02 – Symlink skip + path-token reject + single-pass leftovers

## ⚡ Do This First: Load Agent Profile

```
/ad-hoc-profile-load python-pedro
```

## Objectives & Success Criteria

- Symlink entries are skipped; host file contents never appear via `copy2` follow (FR-003, FR-004).
- Path components containing `{{ORG_NAME}}` / `{{LOCAL_PATH}}` fail with `substitute.path_token` (FR-005).
- Content leftovers still fail with `substitute.leftover_tokens` (FR-006), detected in the same pass as replacement (FR-010).

## Context & Constraints

- Spec scenarios 2–4; contract `contracts/path-token-rejection.md`.
- C-003: skip symlinks; reject path tokens (do not rename).

## Branch Strategy

- **Planning base branch**: `feat/doctrine-org-init-from-template`
- **Merge target branch**: `feat/doctrine-org-init-from-template`

## Subtasks & Detailed Guidance

### Subtask T005 – RED symlink

- In `test_template_render_ignore_copy.py`: create template with symlink to a secret file outside the tree; after copy, dest must not contain that secret’s bytes as a regular file.

### Subtask T006 – Skip symlinks

- In `copy_template_tree`, before `is_file()`/`copy2`: `if path.is_symlink(): continue`.
- Do not follow link targets.

### Subtask T007 – RED path tokens

- Fixture with file or dir name containing `{{ORG_NAME}}` or `{{LOCAL_PATH}}` → `SubstituteError` rule `substitute.path_token`.

### Subtask T008 – Implement path scan + single-pass leftovers

- Scan relative path components under destination for placeholders; return `RULE_PATH_TOKEN = "substitute.path_token"`.
- In `_substitute_file`, after replace, if placeholders remain in that file’s text, return leftover error immediately (or accumulate); remove mandatory second full-tree leftover pass (or make it redundant/no-op for already-checked files). Keep FR-006 behaviour.

## Test Strategy

```bash
PWHEADLESS=1 pytest tests/specify_cli/doctrine/test_template_render_ignore_copy.py tests/specify_cli/doctrine/test_template_render_substitute.py -q
```

## Risks & Mitigations

- Templates that relied on symlinks for shared files will omit those entries — document; doctrine templates should use real files.

## Review Guidance

- Prove secret file contents never appear under destination.
- Prove path-token failure does not succeed the pack.

## Activity Log

### 2026-07-22 – Prompt generated
**Agent**: system
**Action**: Prompt generated via /spec-kitty.tasks
- 2026-07-22T12:07:19Z – user – shell_pid=66088 – Review passed: security remediation verified
