---
work_package_id: WP05
title: Remaining JSON adoption and empty-success repair
dependencies:
- WP02
requirement_refs:
- FR-005
- FR-006
- FR-007
- FR-008
- FR-012
planning_base_branch: fix/cli-boundary-robustness
merge_target_branch: fix/cli-boundary-robustness
branch_strategy: Planning artifacts for this mission were generated on fix/cli-boundary-robustness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-boundary-robustness unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-boundary-robustness-01M2NQCB
base_commit: 325aa2113f0903c6d020aa4e2dacfa539db21d70
created_at: '2026-09-16T20:50:37.013612+00:00'
subtasks:
- T021
- T022
- T023
- T024
- T025
phase: Phase 2 - Parallel command adoption
history:
- at: '2026-09-16T20:02:57Z'
  actor: codex
  action: Prompt generated via mission tasks workflow
authoritative_surface: src/specify_cli/
create_intent:
- tests/specify_cli/cli/commands/test_remaining_json_boundary_contract.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/tasks_status_cmd.py
- src/specify_cli/agent_utils/status.py
- src/specify_cli/cli/commands/glossary.py
- src/specify_cli/cli/commands/archive.py
- src/specify_cli/cli/commands/materialize.py
- src/specify_cli/cli/commands/verify.py
- src/specify_cli/cli/commands/validate_encoding.py
- src/specify_cli/cli/commands/research.py
- src/specify_cli/cli/commands/validate_tasks.py
- src/specify_cli/cli/commands/dashboard.py
- tests/specify_cli/cli/commands/test_remaining_json_boundary_contract.py
- tests/specify_cli/cli/commands/agent/test_tasks_status_cmd_seam.py
tags: []
tracker_refs:
- '#4533'
- '#4643'
---

# Work Package Prompt: WP05 – Remaining JSON adoption and empty-success repair

## Objective

Fix the exit-zero masking bug in agent task status and opt the rest of the explicitly assigned command callers into WP02’s shared JSON boundary without changing command-specific successful payloads.

## Context and constraints

- Depends on WP02.
- #4643’s key boundary: `agent_utils/status.py` is a data builder. It must return pure data, print nothing, and must not attach an `error` key to an empty successful result. `tasks_status_cmd.py` owns rendering/transport.
- A zero-work-package mission is successful and remains exit 0.
- Glossary’s bare `[]` success is intentional and must not be normalized.
- Archive/materialize are folded #4533 surfaces.
- Five otherwise-unowned `get_project_root_or_exit` callers are assigned here: verify, validate_encoding, research, validate_tasks, dashboard.
- Surgical edits only in status/glossary; freeze existing complexity suppressions and display refactors.

## Branch strategy

- Planning base / merge target: `fix/cli-boundary-robustness`.
- Runtime allocates the lane after WP02 from `lanes.json`.
- Start with: `spec-kitty agent action implement WP05 --agent <name>`
- WP03 and WP04 may proceed concurrently.

## Owned-file boundary

The exact command/data files, the new boundary-contract test, and the existing task-status seam test are owned. The existing seam test must be updated because it pins #4643's prose-plus-`Exit(0)` behavior that this package intentionally removes from JSON mode; human-mode behavior remains covered. Do not modify WP02 helpers, other caller files, architecture tests, or mission artifacts. New follow-up issues discovered during enumeration belong to closeout, not code expansion here.

## Subtasks and detailed guidance

### T021 – RED: #4643 and adoption regression matrix

Create `test_remaining_json_boundary_contract.py`. First add an issue-pinned `@pytest.mark.regression` case using the pre-existing agent task-status entry point and a mission with zero WP files.

Assert:

- exit code is 0;
- `json.loads(stdout)` succeeds;
- the returned command success shape contains empty collections/counts as appropriate;
- no `error` key and no “No work packages found” prose appears;
- stderr has no traceback.

Add table-driven not-in-project cases for the explicitly owned caller commands and focused error/empty cases for glossary/archive/materialize where stable fixtures exist.

### T022 – Restore data-builder versus command ownership

In `agent_utils/status.py`, make the zero-WP branch return the same domain data structure as non-empty status with empty collections. Remove console output and any error-shaped key from that successful result.

In `tasks_status_cmd.py`, choose rendering based on `json_output`:

- JSON: emit the returned data once through the console JSON seam.
- Human: preserve the useful “no work packages” presentation on the human stream.
- Both: remain exit 0 for empty status.

Do not refactor `show_kanban_status` or `_display_status_board`; the plan explicitly freezes their complexity.

### T023 – Adopt glossary, archive, and materialize

For each owned command module:

- Opt project-root failures into the WP02 helper when JSON was requested.
- Route adopted error paths through the canonical envelope.
- Route bare JSON printing through the console seam where needed.
- Preserve command-specific successful values, especially glossary’s bare list/empty list.
- Preserve non-JSON prose and exit status.

Exercise #4533’s archive/materialize boundary cases. Do not absorb unrelated archive behavior or glossary C901 debt.

### T024 – Opt otherwise-unowned root callers in

Update the JSON-capable paths in:

- `verify.py`
- `validate_encoding.py`
- `research.py`
- `validate_tasks.py`
- `dashboard.py`

Pass each command’s resolved JSON flag into `get_project_root_or_exit(json_output=...)`. Because WP02 defaulted the parameter, non-JSON callers remain unchanged. Only modify error rendering needed for stdout parseability; do not normalize successes or restructure command logic.

### T025 – Verify shapes, exits, and streams

Complete the matrix:

- empty-success at exit 0 with no error key;
- canonical error object at each adopted JSON failure;
- raw stdout parseability with no Rich/prose bytes;
- corresponding non-JSON exit equality;
- unchanged happy-path parsed payloads;
- no tracebacks.

Include issue identifiers #4643 and #4533 in test descriptions and ensure coverage directly invokes public commands rather than only private builders.

## Test strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_remaining_json_boundary_contract.py -q
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/ tests/status/ tests/specify_cli/cli/commands/test_glossary_show.py tests/specify_cli/cli/commands/test_glossary_validate.py tests/specify_cli/cli/commands/test_materialize.py -q
ruff check src/specify_cli/agent_utils/status.py src/specify_cli/cli/commands/agent/tasks_status_cmd.py src/specify_cli/cli/commands/glossary.py src/specify_cli/cli/commands/archive.py src/specify_cli/cli/commands/materialize.py src/specify_cli/cli/commands/verify.py src/specify_cli/cli/commands/validate_encoding.py src/specify_cli/cli/commands/research.py src/specify_cli/cli/commands/validate_tasks.py src/specify_cli/cli/commands/dashboard.py tests/specify_cli/cli/commands/test_remaining_json_boundary_contract.py
```

Run whole-repo format and mypy gates before handoff.

## Definition of done

- #4643 is red-first covered and fixed at the data/command ownership boundary.
- Empty status is valid success JSON at exit 0 with no error key.
- All explicitly assigned callers opt into JSON-aware root failure.
- Glossary/archive/materialize adopted errors are canonical.
- Every successful shape remains command-specific and unchanged.
- Tests prove stdout discipline and exit fidelity.

## Risks and mitigations

- **Error-shaped empty success**: assert absence of the key, not merely falsy value.
- **Success normalization**: snapshot/compare parsed values before altering transport.
- **Large status/glossary functions**: make surgical branch edits only.
- **Missed caller flag**: table-drive all five otherwise-unowned callers.

## Reviewer guidance

Trace zero-WP data from builder to command. Reject any console call in the builder and any error key at exit zero. Check the five caller files explicitly, compare human/JSON exits, and ensure the diff does not broaden into unrelated command cleanup.

## Adoption inventory

| Surface | Primary owned condition | Success-shape invariant |
|---|---|---|
| agent tasks status | zero work packages | normal status object with empty collections |
| glossary | empty/error paths | historical object or bare list remains unchanged |
| archive | not in project / adopted errors | historical successful archive payload |
| materialize | not in project / adopted errors | historical successful materialize payload |
| verify | not in project | existing verification success payload |
| validate-encoding | not in project | existing validation success payload |
| research | not in project | existing research success payload |
| validate-tasks | not in project | existing validation success payload |
| dashboard | not in project | existing launch/status success behavior |

## Empty-success example properties

The exact keys remain command-owned, but the zero-WP result must satisfy all of:

- it is serializable without special error handling;
- collection fields are empty collections, not prose sentinels;
- count fields, if present, are zero;
- no top-level or nested `error` is invented merely because the result is empty;
- the command exits zero;
- human mode may still explain the empty state on the human stream.

## Implementation evidence to retain

- #4643 red-on-base/green-on-head proof.
- Before/after parsed success value for each changed success path.
- Table-driven raw stdout and exit results for all five otherwise-unowned callers.
- Search evidence that the status builder does not print.
- Focused suite and quality-gate results.

## Self-review checklist

- [ ] The data builder returns data and never chooses a stream.
- [ ] Zero WPs has no error key and exits zero.
- [ ] Every assigned root caller forwards its resolved JSON flag.
- [ ] Glossary’s bare list success remains bare.
- [ ] Archive/materialize errors use WP02 rather than local mappings.
- [ ] No status/glossary complexity refactor slipped in.
- [ ] Non-JSON UX remains useful.
- [ ] Only owned files changed.

## Activity log

### 2026-09-16 – Prompt generated

The plan’s helper-ripple amendment is represented as explicit ownership rather than an implicit follow-up.
