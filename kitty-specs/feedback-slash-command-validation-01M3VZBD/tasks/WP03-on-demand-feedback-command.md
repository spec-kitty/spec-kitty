---
work_package_id: WP03
title: On-demand /spec-kitty.feedback command
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
planning_base_branch: feat/in-harness-feedback-survey
merge_target_branch: feat/in-harness-feedback-survey
branch_strategy: Planning artifacts for this mission were generated on feat/in-harness-feedback-survey. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/in-harness-feedback-survey unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-feedback-slash-command-validation-01M3VZBD
base_commit: efe829420612f6d91e08df5039123c2956c7a036
created_at: '2026-10-01T20:02:11.207112+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 2 - Command
history:
- at: '2026-10-01T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: packs/built-in/missions/mission-steps/software-dev/feedback/
create_intent:
- packs/built-in/missions/mission-steps/software-dev/feedback/prompt.md
- packs/built-in/missions/mission-steps/software-dev/feedback/step.yaml
- tests/specify_cli/feedback/test_feedback_command_surface.py
execution_mode: code_change
model: ''
owned_files:
- packs/built-in/missions/mission-steps/software-dev/feedback/**
- src/specify_cli/shims/registry.py
- src/specify_cli/skills/command_installer.py
- tests/specify_cli/feedback/test_feedback_command_surface.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – On-demand /spec-kitty.feedback command

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: set at claim time

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` in the event log (`spec-kitty agent tasks status`) or the Activity Log. Address every feedback item and log what you changed.

---

## Objectives & Success Criteria

- `/spec-kitty.feedback` exists for all 13 slash-command agents and the 4 Agent Skills agents, generated from one pack source.
- The prompt has the agent ask rating, comment (stating the limit from the check response) and email through the harness question UI, then call `spec-kitty feedback --agent-submit`.
- It uses `--trigger on_demand`, so the weekly offer is not consumed. No new CLI flag.
- Unavailable cases (no endpoint, CI, non-interactive) produce a plain message and no send.
- Spec refs: FR-001 to FR-005, SC-006, C-003, C-005.

## Context & Constraints

- Read `kitty-specs/feedback-slash-command-validation-01M3VZBD/{spec,plan,research,contracts/agent-check-on-demand.md}`, `.kittify/charter/charter.md`, and `CLAUDE.md` sections on template source location and pack tiers.
- **Edit pack SOURCE only; never edit `.claude/`, `.agents/` or other agent copies.** `packs/built-in/` ships to consumers; this command is consumer-facing, so built-in is correct.
- WP01 and WP02 must be merged first: the prompt relies on the structured error codes and the wording.
- Use `spec-kitty@head` style invocation only where the existing prompts do; follow the conventions in the existing `packs/built-in/missions/mission-steps/software-dev/*/prompt.md` files and in `src/specify_cli/feedback/agent_block.py` for the handshake wording.
- Vendor-neutral wording; examples use `example.test` or loopback only.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated by `spec-kitty agent mission finalize-tasks`. Do not edit by hand.

## Subtasks & Detailed Guidance

### Subtask T011 – Registration spike

- **Purpose**: Pick the lowest-impact way to add a consumer command, before writing code.
- **Steps**: Read `src/specify_cli/shims/registry.py` (`CONSUMER_SKILLS`, `PROMPT_DRIVEN_COMMANDS`, `CLI_DRIVEN_COMMANDS`) and `src/specify_cli/skills/command_installer.py` (`PROMPT_BACKED_COMMANDS`, `CLI_WRAPPER_COMMANDS`, the assertion that the two cover `CONSUMER_SKILLS`). Prompt-backed commands map to step directories under `packs/built-in/missions/mission-steps/software-dev/`.
  - Preferred: prompt-backed `feedback` with a new step directory `feedback/{step.yaml,prompt.md}`.
  - If a mission-step directory trips mission-step contract or DRG gates because `feedback` is not a mission step, record the failure and instead extend the CLI-wrapper mechanism so a thin command can carry a full instruction body.
  - Record the decision and evidence in the Activity Log. Also check `src/specify_cli/runtime/agent_commands.py`, `tool_surface/providers/slash_commands.py` and `migration/rewrite_shims.py` for places that enumerate commands.
- **Files**: none changed in this subtask.

### Subtask T012 – Red tests

- **Purpose**: Specify generation and non-throttling first.
- **Steps**: Create `tests/specify_cli/feedback/test_feedback_command_surface.py`:
  - `feedback` is in `CONSUMER_SKILLS` and in exactly one classification set.
  - Generation for at least `.claude`, `.codex` (skills) and `.opencode` produces a `spec-kitty.feedback` file (cover all 17 via the project's existing agent roster helpers if cheap).
  - The generated prompt mentions `--trigger on_demand`, `--agent-check`, `--agent-submit`, `--agent-choice` is not required, and contains no literal `2000`.
  - With the weekly offer already claimed, `agent_check(SurveyTrigger.ON_DEMAND, ...)` still returns `action: prompt` and does not change stored preferences (use the existing fixtures in `conftest.py`).
- **Files**: new test file.

### Subtask T013 – Pack source prompt

- **Purpose**: The command body, authored once.
- **Steps**: Write `prompt.md` and `step.yaml` in the new step directory (shape copied from the existing step directories, not from old missions). Prompt flow:
  1. Run the startup upgrade check block like the other commands.
  2. `spec-kitty feedback --agent-check --trigger on_demand --agent <your harness id> --json`.
  3. If `action` is `none`, tell the user why in plain words and stop.
  4. Ask rating (1 to 5), then the comment using the `survey` wording text exactly (it states the limit), then optional email, then consent with the text "Send feedback", all through the host question UI. No plain-text terminal fallback.
  5. `spec-kitty feedback --agent-submit --trigger on_demand --agent <harness> --rating … [--comment …] [--email …] --consent yes --json`.
  6. On `invalid_input`, tell the user which field failed and re-ask only that question; never submit until valid. On `comment_truncated`, tell the user. On `no_endpoint` or `not_sent`, report plainly.
- **Files**: `packs/built-in/missions/mission-steps/software-dev/feedback/prompt.md`, `step.yaml`.

### Subtask T014 – Register the command

- **Purpose**: Make the installers generate it everywhere.
- **Steps**: Per the T011 decision, add `feedback` to `CONSUMER_SKILLS` and the right classification set, and to `PROMPT_BACKED_COMMANDS` (or the wrapper mechanism). Keep the set-equality assertions true.
- **Files**: `src/specify_cli/shims/registry.py`, `src/specify_cli/skills/command_installer.py`.
- **Notes**: Other tests may pin the command lists or counts; update them with a one-line justification in the Activity Log (a small, well-justified out-of-map edit is acceptable).

### Subtask T015 – Pins, graph, freshness

- **Purpose**: Keep the repo gates green.
- **Steps**: Run `spec-kitty doctrine regenerate-graph` then `spec-kitty doctrine regenerate-graph --check`. Run the specific gates: `tests/docs/test_check_cli_reference_freshness.py` (a prompt-only command should not change the visible CLI count; if it does, re-pin with a note), and the command-surface and pack-manifest tests that failed in T014. Regenerate `docs/api/cli-commands.md` and `_completion_manifest.json` only if a gate demands it.
- **Files**: generated artefacts as required by the gates.

## Test Strategy

- `uv run --frozen pytest tests/specify_cli/feedback/test_feedback_command_surface.py -q`
- Then `uv run --frozen pytest tests/specify_cli/feedback -q` and the specific registry, installer and pack gates you touched (find them with `grep -rl "CONSUMER_SKILLS\|PROMPT_BACKED_COMMANDS" tests/`).
- Do not run `tests/architectural/` as a whole; run only the gate files implicated.
- ruff check, ruff format --check, mypy strict on changed Python.

## Risks & Mitigations

- New step directory trips mission-step or DRG gates → handled by the T011 fallback.
- Classification sets drift out of sync → set-equality assertions already guard this.
- Hand-editing agent copies → forbidden; regenerate instead.

## Review Guidance

- Confirm only pack source and registry were edited, no agent-copy edits.
- Confirm `--trigger on_demand`, no new flag, no hardcoded limit, "Send feedback" consent text.
- Confirm the throttle test, the generation test and the pack graph check pass.

## Activity Log

> Entries are chronological, oldest first; append new entries at the end.
> Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`

- 2026-10-01T20:00:00Z – system – Prompt created.
