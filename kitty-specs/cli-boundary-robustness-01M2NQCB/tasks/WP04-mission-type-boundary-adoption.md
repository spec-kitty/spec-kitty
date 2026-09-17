---
work_package_id: WP04
title: Mission-type and mission alias adoption
dependencies:
- WP02
requirement_refs:
- FR-002
- FR-003
- FR-005
- FR-007
- FR-008
- FR-010
- FR-011
- FR-012
planning_base_branch: fix/cli-boundary-robustness
merge_target_branch: fix/cli-boundary-robustness
branch_strategy: Planning artifacts for this mission were generated on fix/cli-boundary-robustness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-boundary-robustness unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-boundary-robustness-01M2NQCB
base_commit: 325aa2113f0903c6d020aa4e2dacfa539db21d70
created_at: '2026-09-16T20:50:16.182230+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
phase: Phase 2 - Parallel command adoption
history:
- at: '2026-09-16T20:02:57Z'
  actor: codex
  action: Prompt generated via mission tasks workflow
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/cli/commands/test_mission_type_boundary_contract.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/mission_type.py
- src/specify_cli/cli/commands/charter/mission_type.py
- tests/specify_cli/cli/commands/test_mission_type_boundary_contract.py
tags: []
tracker_refs:
- '#4598'
- '#4600'
- '#4601'
---

# Work Package Prompt: WP04 – Mission-type and mission alias adoption

## Objective

Contain malformed configuration at the mission-type command boundary, restore the activated-only default across every alias, and adopt the canonical JSON contract for mission-type errors without restructuring the large command module.

## Context and constraints

- Depends on WP02’s contract/helper.
- This WP owns #4600 Instance 2: `existing_mission_types(repo_root)` can raise `CharterPackConfigError` before the existing narrow handler.
- The loud, actionable, file-naming content-load message belongs here in the command layer, never in bootstrap.
- #4598 must be fixed at the leaking call site by passing `include_inactive=False`; do not coerce framework sentinels inside the canonical callee.
- Verify all registrations: `mission list`, `mission-type list`, `charter mission-type list`, and the separately delegated `doctrine mission-type list`.
- `mission_type.py` is approximately 1,700 lines. Scout registrations and data flow first; make surgical changes and freeze unrelated complexity.

## Branch strategy

- Planning base / merge target: `fix/cli-boundary-robustness`.
- Runtime allocates a dependency-aware lane worktree after WP02.
- Start with: `spec-kitty agent action implement WP04 --agent <name>`
- WP03 and WP05 may run concurrently.

## Owned-file boundary

Only the two mission-type command modules and the new boundary test may change. Do not alter charter service/domain loaders, shared helpers, doctrine delegation modules, or architectural gates. Validate doctrine routing through public invocation rather than editing it.

## Subtasks and detailed guidance

### T016 – Scout and land red-first issue coverage

Before source edits, map each registration/callback in the two owned modules and note which delegates to which function. Create `test_mission_type_boundary_contract.py` with failing acceptance cases for:

- #4600 Instance 2: valid UTF-8 but parseable-invalid config causes `existing_mission_types`/list to raise today; expected result is a named domain message, non-zero exit, no traceback.
- #4598: partial charter, default list hides inactive types across all aliases.
- #4601: unknown `mission-type show <name> --json` returns canonical JSON rather than prose.

Mark the #4600 case `@pytest.mark.regression` and preserve red-on-base evidence.

### T017 – Contain content-load failures in the command layer

Move/extend the command-layer protection so configuration access that occurs before the current `try` is included. Catch the specific charter configuration exception, not `Exception`.

The rendered error must:

- name the offending config path when available;
- state that loading/parsing/decoding failed in actionable terms;
- exit non-zero using the command’s established code;
- emit no raw traceback or exception class dump;
- use canonical JSON when `--json` applies and human stderr otherwise.

Apply equivalent protection to the `show_mission_type` path identified by the plan.

### T018 – Correct activated-only defaults at the call site

At the no-subcommand or alias forwarding site identified near the plan’s census, pass the concrete `include_inactive=False` default. Confirm the canonical charter list behavior remains authoritative.

Test:

- default: activated types only;
- explicit include-inactive flag: activated union inactive;
- all four aliases produce equivalent lists;
- no `OptionInfo`/`ArgumentInfo` repr appears.

Do not change the callee’s public default semantics or add sentinel type checks.

### T019 – Adopt canonical JSON errors

Replace owned divergent JSON error mappings and prose/bare-print branches with WP02’s shared contract/transport. Include unknown show targets, config-loading errors, project-root failures, and other in-scope sibling JSON errors in the touched modules.

Use condition-specific stable codes. Preserve successful JSON shapes and per-command exits. Consolidating repeated `[red]Error:[/red]` strings is allowed only insofar as routing them through the shared error emission removes stream divergence.

### T020 – Alias and success invariance verification

Complete an invocation matrix for:

- `mission list`
- `mission-type list`
- `charter mission-type list`
- `doctrine mission-type list`
- `mission-type show <unknown> --json`
- malformed config in list/show
- explicit include-inactive

For JSON cases, parse raw stdout. For all cases, reject tracebacks and placeholder repr. Compare success payloads/visible lists with pre-existing expectations.

## Test strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_mission_type_boundary_contract.py -q
PWHEADLESS=1 .venv/bin/python -m pytest tests/cli/test_charter_mission_type_commands.py tests/cli/test_mission_type_malformed_yaml_cli_boundary.py tests/charter/test_mission_type_activation.py -q
ruff check src/specify_cli/cli/commands/mission_type.py src/specify_cli/cli/commands/charter/mission_type.py tests/specify_cli/cli/commands/test_mission_type_boundary_contract.py
```

Run repository format and mypy gates after focused tests.

## Definition of done

- #4600 Instance 2 is red-first covered and produces a named non-traceback domain error.
- Default list behavior hides inactive types across every registration.
- Explicit opt-in still reveals inactive types.
- Owned JSON errors use the single shared envelope with stdout discipline.
- Successful output is unchanged.
- No unrelated refactor of the large module occurred.

## Risks and mitigations

- **Missed alias**: test public invocations, especially the separate doctrine delegation path.
- **Over-broad catch**: catch the domain-specific config exception and keep programmer errors visible.
- **Wrong default layer**: concrete value at forwarding call site only.
- **God-module churn**: scout first and confine edits to listed sites.

## Reviewer guidance

Demand the registration map and red-first evidence. Review exception scope and error path/file naming. Compare all aliases, inspect default forwarding, and reject local JSON envelope definitions or unrelated complexity cleanups.

## Alias acceptance matrix

| Public form | Default fixture expectation | Explicit inactive expectation |
|---|---|---|
| `mission list` | activated only | activated + inactive |
| `mission-type list` | activated only | activated + inactive |
| `charter mission-type list` | activated only | activated + inactive |
| `doctrine mission-type list` | activated only | activated + inactive |

Additional failure matrix:

| Invocation | Condition | Expected contract |
|---|---|---|
| list alias | parseable-invalid config | named command error, no traceback |
| show alias | parseable-invalid config | named command error, no traceback |
| `mission-type show missing --json` | unknown type | canonical error object |
| list JSON success | partial charter | unchanged success shape |

## Error-message requirements

- Identify configuration as the failed resource.
- Include the concrete config path when available from the domain error.
- Describe the failure without dumping a Python repr.
- In JSON mode, put the description under `error.message` only.
- In human mode, use the established error console.
- Never label a malformed configuration as an empty mission-type set.

## Implementation evidence to retain

- Scout notes showing the four public registration paths.
- #4600 Instance-2 red-on-base and green-on-head output.
- Parsed JSON for unknown-type and configuration failures.
- Default/explicit alias result comparisons.
- Existing mission-type suite result counts.

## Self-review checklist

- [ ] Specific charter configuration exceptions are caught at the command boundary.
- [ ] The config-load call itself is inside the protected region.
- [ ] `include_inactive=False` is passed at the leaking forwarding site.
- [ ] Doctrine delegation is tested without editing its unowned module.
- [ ] JSON output has no Rich prefix.
- [ ] Success shapes and explicit opt-in remain intact.
- [ ] No unrelated complexity/refactor churn appears.
- [ ] Only owned files changed.

## Activity log

### 2026-09-16 – Prompt generated

Post-plan Amendment A and multi-registration edge case are explicit acceptance gates.
