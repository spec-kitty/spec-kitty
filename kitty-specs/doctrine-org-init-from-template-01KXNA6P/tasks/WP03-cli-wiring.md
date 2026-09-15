---
work_package_id: WP03
title: CLI Wiring & Compatibility
dependencies:
- WP02
requirement_refs:
- FR-001
- FR-002
- NFR-001
- NFR-002
tracker_refs: []
planning_base_branch: feat/doctrine-org-init-from-template
merge_target_branch: feat/doctrine-org-init-from-template
branch_strategy: Planning artifacts for this mission were generated on feat/doctrine-org-init-from-template. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/doctrine-org-init-from-template unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
phase: Phase 3 - Operator surface
assignee: ''
agent: "cursor"
shell_pid: "24810"
history:
- at: '2026-07-16T12:22:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/doctrine.py
- tests/cli/test_doctrine_org_commands.py
role: implementer
tags: []
task_type: implement
---

# Work Package Prompt: WP03 – CLI Wiring & Compatibility

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: (select from available agents)

---

## Objectives & Success Criteria

- `spec-kitty doctrine org init` accepts `--template`, `--org-name`, `--local-path`, `--branch` and renders via the WP02 pipeline.
- Without `--template`, behaviour matches today’s minimal scaffold (FR-001 / NFR-002).
- Errors print rule_id / resolve step and offending value (NFR-001); exit non-zero on failure.
- Existing CliRunner tests in `tests/cli/test_doctrine_org_commands.py` remain green; new template cases added.

## Context & Constraints

- Contract: `kitty-specs/doctrine-org-init-from-template-01KXNA6P/contracts/cli-org-init-template.md`
- Quickstart examples should match flag names.
- Keep `org_init` thin — no business logic beyond option parsing, overwrite guard, dispatch, and messaging.
- Do not edit `template_render/` except if a one-line import path fix is required (record rationale).

## Branch Strategy

- **Planning base branch**: `feat/doctrine-org-init-from-template`
- **Merge target branch**: `feat/doctrine-org-init-from-template`

```bash
spec-kitty agent action implement WP03 --agent <name>
```

## Subtasks & Detailed Guidance

### Subtask T011 – RED: CliRunner template-path + minimal-scaffold regression

- **Purpose**: ATDD for FR-001 / FR-002 operator surface.
- **Steps**:
  1. Keep existing scaffold + overwrite tests intact.
  2. Add cases: local TEMPLATE happy path (tiny fixture tree with tokens + `.templateignore`); invalid ORG_NAME; missing `--org-name` when `--template` set; `--force` overwrite path for template mode.
  3. Prefer fixture under `tmp_path` rather than depending on `~/projects/doctrine-template`.
- **Files**: `tests/cli/test_doctrine_org_commands.py`
- **Parallel?**: No

### Subtask T012 – Wire options on `org_init`

- **Purpose**: Operator-visible extension of the existing command only.
- **Steps**:
  1. Add Typer options `--template`, `--org-name`, `--local-path`, `--branch`.
  2. If template omitted → existing minimal scaffold path unchanged.
  3. If template set → require org-name; build `RenderRequest`; call pipeline; honour `--force` with same exists-guard semantics.
  4. Keep complexity of `org_init` ≤ 15 (extract `_run_minimal_scaffold` / `_run_template_render` helpers in the same module if needed).
- **Files**: `src/specify_cli/cli/commands/doctrine.py`
- **Parallel?**: No

### Subtask T013 – Error surfacing + success output

- **Purpose**: NFR-001 actionable errors; clear success for operators.
- **Steps**:
  1. Map validation/resolve/pipeline failures to red Rich messages including rule_id and value.
  2. On success, print destination and a short note that the full template tree was rendered (not only three files).
  3. Ensure exit code 1 on all failure paths.
- **Files**: `src/specify_cli/cli/commands/doctrine.py`
- **Parallel?**: No

## Test Strategy

```bash
PWHEADLESS=1 uv run pytest tests/cli/test_doctrine_org_commands.py -q
```

Also run the doctrine template_render unit suite as a smoke regression:

```bash
PWHEADLESS=1 uv run pytest tests/specify_cli/doctrine/test_template_render_*.py -q
```

## Risks & Mitigations

- Breaking minimal scaffold → run legacy tests first after wiring.
- Requiring org-name without template → Typer/`callback` guard must be template-gated only.

## Review Guidance

- Diff `org_init` carefully: minimal path should be byte-stable aside from helper extraction.
- Confirm PACK_PATH vs LOCAL_PATH remain distinct options.
- Confirm help text mentions operators creating their own doctrine / template optional.

## Activity Log

- 2026-07-16T12:22:00Z – system – Prompt created via /spec-kitty.tasks
- 2026-07-16T13:01:16Z – cursor – shell_pid=24810 – Assigned agent via action command
