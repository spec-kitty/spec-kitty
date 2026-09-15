---
work_package_id: WP01
title: Validation & Template Resolve
dependencies: []
requirement_refs:
- C-001
- C-002
- C-004
- FR-003
- FR-004
- FR-005
- FR-006
- FR-010
tracker_refs: []
planning_base_branch: feat/doctrine-org-init-from-template
merge_target_branch: feat/doctrine-org-init-from-template
branch_strategy: Planning artifacts for this mission were generated on feat/doctrine-org-init-from-template. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/doctrine-org-init-from-template unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Library foundation
assignee: ''
agent: "cursor"
shell_pid: "16591"
history:
- at: '2026-07-16T12:22:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/doctrine/template_render/
create_intent:
- src/specify_cli/doctrine/template_render/__init__.py
- src/specify_cli/doctrine/template_render/validation.py
- src/specify_cli/doctrine/template_render/resolve.py
- tests/specify_cli/doctrine/test_template_render_validation.py
- tests/specify_cli/doctrine/test_template_render_resolve.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/doctrine/template_render/__init__.py
- src/specify_cli/doctrine/template_render/validation.py
- src/specify_cli/doctrine/template_render/resolve.py
- tests/specify_cli/doctrine/test_template_render_validation.py
- tests/specify_cli/doctrine/test_template_render_resolve.py
role: implementer
tags: []
task_type: implement
---

# Work Package Prompt: WP01 – Validation & Template Resolve

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: (select from available agents)

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objectives & Success Criteria

- Operators' ORG_NAME / LOCAL_PATH inputs are validated fail-closed with named `rule_id`s matching the doctrine-template contract.
- TEMPLATE strings resolve to a readable local root or a temp git checkout at the effective ref.
- Dual branch surface works: `--branch` and/or `#ref` (and safe `@ref` forms); conflicting refs error with `branch.conflict`.
- No CLI changes in this WP.

## Context & Constraints

- Spec: `kitty-specs/doctrine-org-init-from-template-01KXNA6P/spec.md`
- Plan / research / contract: same mission directory
- Reuse `specify_cli.doctrine.sources.git_source.GitSource` — do not invent a second clone stack.
- Audience: operators creating their own doctrine; template is consumed as-is.
- Keep functions ≤ complexity 15; extract helpers as needed.

## Branch Strategy

- **Planning base branch**: `feat/doctrine-org-init-from-template`
- **Merge target branch**: `feat/doctrine-org-init-from-template`
- Execution worktrees are allocated per computed lane from `lanes.json` after finalize.

Implementation command:

```bash
spec-kitty agent action implement WP01 --agent <name>
```

## Subtasks & Detailed Guidance

### Subtask T001 – RED: ORG_NAME / LOCAL_PATH validation unit tests

- **Purpose**: Lock validation contract before implementation (ATDD).
- **Steps**:
  1. Create `tests/specify_cli/doctrine/test_template_render_validation.py`.
  2. Cover format / length / reserved `doctrine-org` / placeholder (`ORG_NAME`, `{{ORG_NAME}}`, contains `TODO`).
  3. Cover LOCAL_PATH empty + placeholder cases.
  4. Assert `rule_id` and that invalid cases do not mutate input (no sanitising).
- **Files**: `tests/specify_cli/doctrine/test_template_render_validation.py`
- **Parallel?**: No (defines package import path with T002)

### Subtask T002 – Implement validation helpers + rule_id errors

- **Purpose**: Satisfy FR-004 / FR-006 / C-001.
- **Steps**:
  1. Add `validation.py` with `validate_org_name` / `validate_local_path` returning a small result type (`ok`, `rule_id`, `message`).
  2. Regex: `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`; length 2–64; reserved case-insensitive `doctrine-org`.
  3. Export from package `__init__.py`.
  4. Make T001 green.
- **Files**: `src/specify_cli/doctrine/template_render/validation.py`, `__init__.py`
- **Parallel?**: No

### Subtask T003 – RED: TEMPLATE parse + branch conflict unit tests

- **Purpose**: Lock TEMPLATE parsing and branch merge rules.
- **Steps**:
  1. Create `tests/specify_cli/doctrine/test_template_render_resolve.py`.
  2. Cases: local path; HTTPS; HTTPS`#branch`; `ssh://…#branch`; `git@host:path` without eating userinfo as branch; `--branch` alone; equal dual sources; conflicting dual sources → `branch.conflict`.
- **Files**: `tests/specify_cli/doctrine/test_template_render_resolve.py`
- **Parallel?**: Yes with T002 once package exists

### Subtask T004 – Implement local/git TEMPLATE resolve via GitSource

- **Purpose**: Satisfy FR-003 / FR-010 resolve failures.
- **Steps**:
  1. Implement `parse_template_ref` + `resolve_template_source(template, branch) -> ResolvedTemplateSource`.
  2. Local: expand user path, require existing directory.
  3. Git: clone via `GitSource` into `tempfile.mkdtemp`, set `cleanup=True`.
  4. On failure return structured errors; leave no orphan partial clone when possible (GitSource already cleans failed first install).
- **Files**: `src/specify_cli/doctrine/template_render/resolve.py`
- **Parallel?**: No

### Subtask T005 – Package public types

- **Purpose**: Stable API for WP02 pipeline.
- **Steps**:
  1. Define `RenderRequest` / `ResolvedTemplateSource` dataclasses (see data-model.md).
  2. Export from `__init__.py` with clear `__all__`.
  3. Document that LOCAL_PATH default `pack` is applied by pipeline, not silently inside validators.
- **Files**: `src/specify_cli/doctrine/template_render/__init__.py` (and types module if extracted)
- **Parallel?**: No

## Test Strategy

```bash
PWHEADLESS=1 uv run pytest tests/specify_cli/doctrine/test_template_render_validation.py tests/specify_cli/doctrine/test_template_render_resolve.py -q
```

Mock or stub `GitSource.fetch` for unit tests; one optional integration mark is fine but not required in WP01.

## Risks & Mitigations

- Ambiguous `@` on `git@host:repo` → only parse `@ref` on `https://` and `ssh://` URLs; document `#ref` as preferred.
- Leaking tokens in errors → rely on GitSource redaction; never log raw `GIT_TOKEN`.

## Review Guidance

- Confirm every failure path names `rule_id` + offending value.
- Confirm no silent lowercasing/hyphenating of ORG_NAME.
- Confirm GitSource reuse (import site), not a parallel clone helper.

## Activity Log

- 2026-07-16T12:22:00Z – system – Prompt created via /spec-kitty.tasks
- 2026-07-16T12:31:28Z – cursor – shell_pid=10753 – Assigned agent via action command
- 2026-07-16T12:39:31Z – cursor – shell_pid=10753 – Ready for review: validation + resolve; 41 unit tests green
- 2026-07-16T12:41:43Z – cursor – shell_pid=16591 – Started review via action command
- 2026-07-16T12:44:03Z – user – shell_pid=16591 – Review passed: validation + resolve; 41 unit tests green
- 2026-07-16T13:05:29Z – user – shell_pid=16591 – Done override: Merged lane-c (includes WP01–WP03) into feat/doctrine-org-init-from-template
