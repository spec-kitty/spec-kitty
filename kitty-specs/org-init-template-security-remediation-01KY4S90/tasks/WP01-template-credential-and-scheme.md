---
work_package_id: WP01
title: Skip GIT_TOKEN on template path + reject plaintext schemes
dependencies: []
requirement_refs:
- FR-001
- FR-007
- NFR-002
tracker_refs: []
planning_base_branch: feat/doctrine-org-init-from-template
merge_target_branch: feat/doctrine-org-init-from-template
branch_strategy: Planning artifacts for this mission were generated on feat/doctrine-org-init-from-template. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/doctrine-org-init-from-template unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-org-init-template-security-remediation-01KY4S90
base_commit: dd56dd53d4f80079dab9c969c7dd6e85fb516bda
created_at: '2026-07-22T11:53:45.666536+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Credential and scheme
assignee: ''
agent: cursor
shell_pid: '65016'
history:
- at: '2026-07-22T11:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/doctrine/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/doctrine/sources/git_source.py
- src/specify_cli/doctrine/template_render/resolve.py
- tests/specify_cli/doctrine/test_template_render_resolve.py
- tests/specify_cli/doctrine/test_sources.py
role: implementer
tags: []
task_type: implement
---

# Work Package Prompt: WP01 – Skip GIT_TOKEN on template path + reject plaintext schemes

## ⚡ Do This First: Load Agent Profile

```
/ad-hoc-profile-load python-pedro
```

## Objectives & Success Criteria

- Template git resolve MUST NOT inject `GIT_TOKEN` into HTTPS URLs (FR-001).
- `http://` and `git://` template locations fail closed with `template.scheme_rejected` before fetch (FR-007).
- Default `GitSource` callers keep `inject_token=True` behaviour.
- Tests prove both behaviours (NFR-002 token half).

## Context & Constraints

- Spec: `kitty-specs/org-init-template-security-remediation-01KY4S90/spec.md`
- Plan: same dir `plan.md`; contract `contracts/credential-injection.md`
- C-002: remediate inside existing seams; do not redesign GitSource for all callers beyond an opt-out flag.
- C-003: skip injection on template path (not allowlist).

## Branch Strategy

- **Planning base branch**: `feat/doctrine-org-init-from-template`
- **Merge target branch**: `feat/doctrine-org-init-from-template`
- Lane worktree allocated by `implement`; merge back to feature PR branch only (C-001).

## Subtasks & Detailed Guidance

### Subtask T001 – RED: no GIT_TOKEN on template HTTPS resolve

- Add/extend tests in `tests/specify_cli/doctrine/test_template_render_resolve.py`.
- With `GIT_TOKEN` set, resolve/factory path for template must construct/use GitSource with injection disabled; assert fetch URL has no `oauth2:` userinfo (mock `_inject_token` / factory capture).

### Subtask T002 – `inject_token` on GitSource

- Add `inject_token: bool = True` to `GitSource` dataclass.
- `_inject_token` returns URL unchanged when `inject_token` is False.
- Template `_resolve_git` constructs with `inject_token=False` (update Protocol/`git_source_factory` call site as needed).

### Subtask T003 – RED+green scheme reject

- Tests: `http://…` and `git://…` → `ResolveError` with `rule_id == "template.scheme_rejected"`.
- HTTPS, SSH (`ssh://`, `git@`), and local paths still classify/resolve as today.

### Subtask T004 – Wire scheme guard

- Reject rejected schemes in `resolve_template_source` (or classify + early return) **before** `mkdtemp`/fetch.
- Export `RULE_TEMPLATE_SCHEME_REJECTED = "template.scheme_rejected"`.

## Test Strategy

```bash
PWHEADLESS=1 pytest tests/specify_cli/doctrine/test_template_render_resolve.py tests/specify_cli/doctrine/test_sources.py -q
```

## Risks & Mitigations

- Private HTTPS templates that relied on GIT_TOKEN via `--template` break → document in WP03; SSH still works.

## Review Guidance

- Confirm inject_token default True preserves existing doctrine pack fetch behaviour.
- Confirm http/git rejected without network.

## Activity Log

### 2026-07-22 – Prompt generated
**Agent**: system
**Action**: Prompt generated via /spec-kitty.tasks
- 2026-07-22T12:07:17Z – user – shell_pid=65016 – Review passed: security remediation verified
