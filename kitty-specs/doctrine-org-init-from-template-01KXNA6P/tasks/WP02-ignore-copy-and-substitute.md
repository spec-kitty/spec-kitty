---
work_package_id: WP02
title: Ignore-Copy, Substitute & Pipeline
dependencies:
- WP01
requirement_refs:
- C-003
- FR-007
- FR-008
- FR-009
- FR-010
- NFR-003
tracker_refs: []
planning_base_branch: feat/doctrine-org-init-from-template
merge_target_branch: feat/doctrine-org-init-from-template
branch_strategy: Planning artifacts for this mission were generated on feat/doctrine-org-init-from-template. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/doctrine-org-init-from-template unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Render pipeline
assignee: ''
agent: "cursor"
shell_pid: "20564"
history:
- at: '2026-07-16T12:22:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/doctrine/template_render/
create_intent:
- src/specify_cli/doctrine/template_render/ignore_copy.py
- src/specify_cli/doctrine/template_render/substitute.py
- src/specify_cli/doctrine/template_render/pipeline.py
- tests/specify_cli/doctrine/test_template_render_ignore_copy.py
- tests/specify_cli/doctrine/test_template_render_substitute.py
- tests/specify_cli/doctrine/test_template_render_pipeline.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/doctrine/template_render/ignore_copy.py
- src/specify_cli/doctrine/template_render/substitute.py
- src/specify_cli/doctrine/template_render/pipeline.py
- tests/specify_cli/doctrine/test_template_render_ignore_copy.py
- tests/specify_cli/doctrine/test_template_render_substitute.py
- tests/specify_cli/doctrine/test_template_render_pipeline.py
role: implementer
tags: []
task_type: implement
---

# Work Package Prompt: WP02 – Ignore-Copy, Substitute & Pipeline

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: (select from available agents)

---

## Objectives & Success Criteria

- Full template trees copy to PACK_PATH excluding `.templateignore` matches and built-ins (`.git/`, `.templateignore`).
- Every literal `{{ORG_NAME}}` / `{{LOCAL_PATH}}` in text files is substituted; leftovers fail the render.
- One pipeline entrypoint runs validate → resolve → copy → substitute with temp cleanup and fail-closed behaviour (FR-010).

## Context & Constraints

- Depends on WP01 types, validators, and resolve helpers.
- Do not edit `cli/commands/doctrine.py` (WP03).
- Prefer staging into a temp dir then moving into PACK_PATH when the destination did not previously exist.
- Complexity ceiling 15; keep walk/copy/substitute as separate functions.

## Branch Strategy

- **Planning base branch**: `feat/doctrine-org-init-from-template`
- **Merge target branch**: `feat/doctrine-org-init-from-template`

```bash
spec-kitty agent action implement WP02 --agent <name>
```

## Subtasks & Detailed Guidance

### Subtask T006 – RED: `.templateignore` + built-in exclude copy tests

- **Purpose**: Prove FR-007 before implementation.
- **Steps**:
  1. Fixture template with nested files, `.templateignore` listing e.g. `kitty-specs/` and a sample dir, plus a fake `.git/` tree.
  2. Assert ignored paths absent at destination; kept paths present; `.templateignore` itself not delivered; `.git/` never copied.
- **Files**: `tests/specify_cli/doctrine/test_template_render_ignore_copy.py`
- **Parallel?**: No with T007

### Subtask T007 – Implement ignore matcher + full-tree copy

- **Purpose**: Full-tree project scaffold copy (planning choice A).
- **Steps**:
  1. Parse `.templateignore` (comments, blanks, `fnmatch`-style patterns; directory patterns ending `/`).
  2. Always union built-in excludes.
  3. Copy preserving relative structure under destination.
- **Files**: `src/specify_cli/doctrine/template_render/ignore_copy.py`
- **Parallel?**: No

### Subtask T008 – RED: token substitute + leftover-token tests

- **Purpose**: Lock FR-008 / FR-009.
- **Steps**:
  1. Fixtures with both tokens in YAML/Markdown; binary-ish undecodable file left unchanged.
  2. Assert replacements and that remaining tokens raise/return failure.
- **Files**: `tests/specify_cli/doctrine/test_template_render_substitute.py`
- **Parallel?**: Yes with T006/T007 once paths agreed

### Subtask T009 – Implement substitute walk + leftover assert

- **Purpose**: Plain-text token replace only (C-003).
- **Steps**:
  1. Walk destination; UTF-8 decode; replace; rewrite.
  2. Second pass or same pass tracking leftovers → fail with clear message.
  3. Undecodable files: skip substitute, do not fail solely for binary (research.md).
- **Files**: `src/specify_cli/doctrine/template_render/substitute.py`
- **Parallel?**: No

### Subtask T010 – Orchestrate pipeline

- **Purpose**: Single call for CLI (WP03).
- **Steps**:
  1. `render_org_pack(request: RenderRequest) -> None` (or result type).
  2. Order: validate org/local → resolve template → overwrite guard (caller may own force check; document) → copy → substitute → cleanup temp source when `cleanup=True`.
  3. Apply LOCAL_PATH default `pack` when omitted.
  4. On mid-flight failure after writes started, leave destination not presented as success (clean temp staging when possible).
  5. Unit-test pipeline happy path + validation short-circuit.
- **Files**: `src/specify_cli/doctrine/template_render/pipeline.py`, update `__init__.py` exports
- **Parallel?**: No

Note: WP01 owns `__init__.py`. For exports of pipeline symbols, either re-export via a minimal additive edit coordinated as out-of-map with rationale, **or** keep pipeline imported as `template_render.pipeline` from CLI without changing WP01's `__init__`. Prefer importing `pipeline` directly from WP03 to avoid ownership conflict.

## Test Strategy

```bash
PWHEADLESS=1 uv run pytest \
  tests/specify_cli/doctrine/test_template_render_ignore_copy.py \
  tests/specify_cli/doctrine/test_template_render_substitute.py \
  tests/specify_cli/doctrine/test_template_render_pipeline.py -q
```

## Risks & Mitigations

- Over-broad ignore patterns deleting needed files → unit fixtures with positive and negative paths.
- Ownership: do not modify WP01 files except documented export approach above.

## Review Guidance

- Confirm PACK_PATH receives full tree (not only `pack/`).
- Confirm leftover tokens fail.
- Confirm temp git clones cleaned when `cleanup=True`.

## Activity Log

- 2026-07-16T12:22:00Z – system – Prompt created via /spec-kitty.tasks
- 2026-07-16T12:46:05Z – cursor – shell_pid=20564 – Assigned agent via action command
- 2026-07-16T12:58:39Z – cursor – shell_pid=20564 – Ready for review: ignore-copy, substitute, pipeline; tests green
- 2026-07-16T13:01:07Z – user – shell_pid=20564 – Review passed: ignore-copy, substitute, pipeline; tests green
- 2026-07-16T13:05:31Z – user – shell_pid=20564 – Done override: Merged lane-c (includes WP01–WP03) into feat/doctrine-org-init-from-template
