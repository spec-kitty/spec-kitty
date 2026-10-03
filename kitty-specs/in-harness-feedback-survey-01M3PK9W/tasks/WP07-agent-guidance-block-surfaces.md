---
work_package_id: WP07
title: Agent Guidance Block Across Harness Surfaces
dependencies:
- WP05
requirement_refs:
- C-002
- C-008
- FR-005
- FR-006
- FR-007
- FR-009
- FR-010
planning_base_branch: feat/in-harness-feedback-survey
merge_target_branch: feat/in-harness-feedback-survey
branch_strategy: Planning artifacts for this mission were generated on feat/in-harness-feedback-survey. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/in-harness-feedback-survey unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-in-harness-feedback-survey-01M3PK9W
base_commit: ac7ab80dcef1a7c545dd73a238fe51873577d285
created_at: '2026-09-30T16:47:35.524255+00:00'
subtasks:
- T036
- T037
- T038
- T039
- T040
- T041
phase: Phase 3 - Triggers
assignee: ''
agent: cursor
history:
- at: '2026-09-30T07:59:37Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/feedback/agent_block.py
create_intent:
- src/specify_cli/feedback/agent_block.py
- tests/specify_cli/feedback/test_agent_block.py
- tests/specify_cli/feedback/test_agent_block_surfaces.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/feedback/agent_block.py
- src/specify_cli/skills/command_installer.py
- src/specify_cli/shims/generator.py
- src/specify_cli/cli/commands/dispatch.py
- src/charter/offering/skills/spec-kitty/SKILL.md
- packs/built-in/missions/mission-steps/software-dev/tasks/prompt.md
- packs/built-in/missions/mission-steps/software-dev/tasks-finalize/prompt.md
- packs/built-in/pack-manifest.yaml
- tests/specify_cli/regression/_twelve_agent_baseline/**
- tests/architectural/test_docs_cli_reference_parity.py
- tests/specify_cli/feedback/test_agent_block.py
- tests/specify_cli/feedback/test_agent_block_surfaces.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Agent Guidance Block Across Harness Surfaces

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `cursor`

If the profile cannot be loaded, run `spec-kitty agent profile list` and pick the best match.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete.
- **Report progress**: Update the Activity Log as you address each item.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

Every agent-facing surface of the three triggers tells the agent, after the command succeeds, to run the Feedback Survey Check. Every other command stays unchanged.

| Trigger | Agent surfaces that must carry the block |
|---|---|
| `planning_complete` | `tasks` and `tasks-finalize` prompt-backed commands, via their **pack source prompts**. These reach the skills installer, the slash-command asset generator, and the `spec-kitty next` runtime prompt builder. Also the `tasks-finalize` CLI-driven **shim** (Markdown + TOML). |
| `mission_end` | `consolidate`: the CLI-wrapper **skill** body in `command_installer.py` and the CLI-driven **shim** (Markdown + TOML) in `shims/generator.py`. |
| `op_close` | The dispatch capsule's human "close it with …" guidance (`cli/commands/dispatch.py`, human output only; JSON unchanged) and the shipped `spec-kitty` skill's close section (`src/charter/offering/skills/spec-kitty/SKILL.md`). |

The block text has one canonical definition in `feedback/agent_block.py`. The pack prompts carry an exact rendered copy between markers, and a drift test enforces equality. Generated agent copies (`.claude/`, `.cursor/`, `.agents/skills/`, …) are **never** hand-edited (C-008).

## Context & Constraints

- `spec.md`: FR-005, FR-006, FR-007, FR-009, FR-010, C-002, C-008.
- `plan.md`: Key Design Decision 1; IC-05 risks. `research.md`: R-01.
- Why two mechanisms: the `spec-kitty next` runtime (`src/runtime/next/prompt_builder.py`) sits below `specify_cli` in the enforced layer chain (`kernel <- charter <- {runtime, …} <- specify_cli`), so it cannot import a Python helper. Prompt-backed commands therefore get the block from their pack source prompt. CLI-driven commands (thin shims with "no workflow logic") get it from the Python helper.
- Existing precedent: `prepend_agent_upgrade_check` (`src/specify_cli/agent_upgrade_prompt.py`) is called from `skills/command_renderer.py`, `skills/command_installer.py`, and `template/asset_generator.py`. The shim generator does **not** carry it today.
- Pack edits trip the pack-manifest regeneration gate: run `spec-kitty doctrine regenerate-graph` after editing pack prompts and commit `packs/built-in/pack-manifest.yaml` (CLAUDE.md, "Pack Tiers"). This is consumer product behaviour, so it belongs in `packs/built-in/`, never `packs/internal/`.
- Snippet gate: `tests/architectural/test_docs_cli_reference_parity.py::test_doctrine_source_snippets_are_registered` checks that `spec-kitty …` commands in bash fences of doctrine sources are registered. `spec-kitty feedback` exists after WP05.

### The canonical block (render per trigger)

````markdown
## Feedback Survey Check

Run this once, only after the command above has succeeded, and only when a human is in the loop (skip it entirely in unattended or automated runs):

```bash
spec-kitty feedback --agent-check --trigger <TRIGGER> --agent <your-agent-key> --json
```

If JSON `action` is `none`, continue silently; do not mention the survey.
If `action` is `prompt`, ask the human using your host-native question UI (plain text if you have none), with the exact wording from the JSON `survey` object: the rating (1-5), the optional comment, and the optional email. Then ask the consent question "Send feedback?". Offer "Skip" and "Don't ask again" at the first question. Never answer on the human's behalf and never pre-fill answers. If the comment is longer than `comment_max_length`, tell the human it will be cut before asking for consent.

Record exactly one result:

```bash
spec-kitty feedback --agent-submit --trigger <TRIGGER> --agent <your-agent-key> --rating <1-5> [--comment "<text>"] [--email "<address>"] --consent yes --json
spec-kitty feedback --agent-choice skip --trigger <TRIGGER> --json    # human skipped or declined
spec-kitty feedback --agent-choice never --trigger <TRIGGER> --json   # human chose "Don't ask again"
```

Show the returned `message` if present, then continue. Never report delivery problems: sending is fire-and-forget.
````

For CLI-driven commands, the block additionally opens with: "Run the command above with `SPEC_KITTY_NON_INTERACTIVE=1` so it never waits for terminal input." (See plan IC-05 on pseudo-terminal harnesses.)

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `feat/in-harness-feedback-survey`
- **Merge target branch**: `feat/in-harness-feedback-survey`

> Populated automatically by `finalize-tasks`; enter your lane with `spec-kitty agent action implement WP07 --agent <name>`.

## Subtasks & Detailed Guidance

### Subtask T036 – Red-first surface tests

- **Purpose**: Prove presence **and** absence per surface through the production render functions (non-vacuity tactic: production path, positive and negative control on the same fixture).
- **Steps** (`tests/specify_cli/feedback/test_agent_block_surfaces.py`):
  1. Skills installer: call the same function the installer uses (`_render_command_skill` or its public caller) for `tasks`, `tasks-finalize`, `consolidate` → contains `## Feedback Survey Check` with the right `--trigger`; for `status`, `dashboard`, `implement`, `review` → does **not**.
  2. Shims: `generate_shim_content_for_agent(cmd, agent)` for `consolidate` and `tasks-finalize` across one Markdown agent (`claude`) and one TOML agent (`gemini`) → contains the block; for `status` → does not.
  3. Runtime: `runtime.next.prompt_builder.build_prompt("tasks", …)` on a minimal mission fixture (reuse fixtures from `tests/specify_cli/next/` or `tests/runtime/`) → contains the block. **Negative control**: `build_prompt("plan", …)` does not.
  4. Slash-command asset generator: render `tasks-finalize/prompt.md` through `template/asset_generator.py` for one Markdown agent → contains the block.
- **Files**: `tests/specify_cli/feedback/test_agent_block_surfaces.py`

### Subtask T037 – `feedback/agent_block.py`

- **Steps**:
  1. `TRIGGER_BY_COMMAND: Mapping[str, SurveyTrigger] = {"tasks": planning_complete, "tasks-finalize": planning_complete, "consolidate": mission_end}`.
  2. `render_feedback_survey_block(trigger: SurveyTrigger, *, cli_driven: bool) -> str`: renders the canonical block above with `<TRIGGER>` substituted, prefixed by the non-interactive sentence when `cli_driven`.
  3. `append_feedback_survey_check(body: str, command: str, *, cli_driven: bool) -> str`: returns `body` unchanged if `command` is not a trigger command or the block marker `## Feedback Survey Check` is already present (idempotent, mirroring `prepend_agent_upgrade_check`); otherwise appends the block separated by a blank line.
  4. `PACK_BLOCK_BEGIN = "<!-- spec-kitty:feedback-survey-check:begin -->"`, `PACK_BLOCK_END = "<!-- spec-kitty:feedback-survey-check:end -->"` for the pack prompts.
  5. `op_close_guidance_line() -> str` for dispatch: one line pointing at `spec-kitty feedback --agent-check --trigger op_close --agent <your-agent-key> --json` after closing the Op, "when a human is in the loop".
  6. Unit tests in `tests/specify_cli/feedback/test_agent_block.py`: idempotency, non-trigger passthrough, trigger substitution, the `cli_driven` prefix.
- **Files**: `src/specify_cli/feedback/agent_block.py`, `tests/specify_cli/feedback/test_agent_block.py`

### Subtask T038 – Wire into the CLI-wrapper skill body and shim generator

- **Steps**:
  1. `command_installer.py::_render_command_skill`: in the CLI-wrapper branch, after building `body` and before `prepend_agent_upgrade_check`, call `append_feedback_survey_check(body, command, cli_driven=True)`. Do **not** touch the prompt-backed branch; those get the block from pack prompts (T039).
  2. `shims/generator.py`: in `generate_shim_content` and `generate_shim_content_toml`, append the block for `consolidate` and `tasks-finalize` (`cli_driven=True`). Keep the "No workflow logic" docstring accurate by amending it: "…except the post-command Feedback Survey Check for trigger commands (see `specify_cli.feedback.agent_block`)". For TOML, apply the same `"""` escaping already used there.
  3. Refresh `tests/specify_cli/regression/_twelve_agent_baseline/**` using the regeneration mechanism documented in `tests/specify_cli/regression/test_twelve_agent_parity.py` or `__init__.py`. Read it first; if baselines are hand-maintained, regenerate by calling the generator, never by hand-typing. Run `tests/specify_cli/regression/` afterwards.
- **Files**: `src/specify_cli/skills/command_installer.py`, `src/specify_cli/shims/generator.py`, `tests/specify_cli/regression/_twelve_agent_baseline/**`

### Subtask T039 – Pack source prompts, drift test, graph regeneration

- **Steps**:
  1. Append the rendered block (`cli_driven=False`, trigger `planning_complete`) between `PACK_BLOCK_BEGIN`/`PACK_BLOCK_END` at the end of `packs/built-in/missions/mission-steps/software-dev/tasks-finalize/prompt.md` and `.../tasks/prompt.md`. In `tasks/prompt.md`, place it where the prompt tells the agent that finalization succeeded (near the final report step) rather than at the very end if that reads more naturally, but keep it inside the markers.
  2. Drift test in `test_agent_block.py`: extract the text between the markers from both pack prompts and assert it equals `render_feedback_survey_block(SurveyTrigger.planning_complete, cli_driven=False)`. **Positive control**: the extractor finds the markers (fail loudly if absent rather than comparing empty strings).
  3. Run `spec-kitty doctrine regenerate-graph` (use the in-repo CLI: `uv run --frozen spec-kitty doctrine regenerate-graph`) and commit the updated `packs/built-in/pack-manifest.yaml`. Run the pack-manifest gate tests it points to.
  4. Do **not** edit `.claude/`, `.cursor/`, `.agents/skills/`, or other generated copies in this repository; they refresh via `spec-kitty upgrade`.
- **Files**: the two pack prompts, `packs/built-in/pack-manifest.yaml`, `tests/specify_cli/feedback/test_agent_block.py`

### Subtask T040 – Op-close guidance

- **Steps**:
  1. `cli/commands/dispatch.py`: after the existing human-output lines telling the agent to close the Op with `spec-kitty profile-invocation complete …` (around line 231), print one more dim line from `op_close_guidance_line()`. The `--json` payload (`payload.to_dict()`) must be unchanged; add a test asserting the JSON key set is identical to before.
  2. `src/charter/offering/skills/spec-kitty/SKILL.md`: in the section that documents closing the Op, add a short "After closing" paragraph with the op_close check command and the "human in the loop only / never answer on the human's behalf" rule. This is a doctrine source file: run the terminology guard (`tests/architectural/test_no_legacy_terminology.py`) and the snippet gate afterwards.
- **Files**: `src/specify_cli/cli/commands/dispatch.py`, `src/charter/offering/skills/spec-kitty/SKILL.md`
- **Notes**: Touching `src/charter/offering/**` pulls in `tests/charter/` and `tests/doctrine/` as owning-subsystem tests (CLAUDE.md blast-radius rule 2). Run their fast tier.

### Subtask T041 – Domain-matched campsite: fix the vacuous snippet-gate glob

- **Purpose**: `test_doctrine_source_snippets_are_registered` scans `src/charter/offering/missions/mission-steps/**/*.md`, a path retired when mission steps moved to `packs/built-in/missions/mission-steps/`. It is therefore vacuous for the prompts this WP edits (charter Standing Order 5: gates must be non-vacuous).
- **Steps**:
  1. Add `packs/built-in/missions/mission-steps/**/*.md` to the gate's scanned globs (keep the old glob only if other files still live there; it currently matches nothing).
  2. Add a non-vacuity floor: assert the scanned file count is > 0 for each glob, so the gate cannot silently scan nothing again.
  3. Run the gate. If it goes red on **pre-existing** snippet drift unrelated to this mission, revert T041, open a GitHub issue with the failing snippets, command, and evidence (charter "Pre-existing Failure Reporting Rule"), and note it in the Activity Log and `traces/tooling-friction.md`. Do not fix unrelated prompts here.
- **Files**: `tests/architectural/test_docs_cli_reference_parity.py`

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/feedback tests/specify_cli/skills tests/specify_cli/regression -q
uv run --frozen pytest tests/test_template/test_asset_generator.py tests/specify_cli/invocation/cli/test_dispatch.py -q
uv run --frozen pytest tests/architectural/test_docs_cli_reference_parity.py tests/architectural/test_no_legacy_terminology.py tests/architectural/test_layer_rules.py -q
uv run --frozen pytest tests/charter tests/doctrine -q -m "fast or unit"
uv run --frozen mypy --strict src/specify_cli/feedback/agent_block.py src/specify_cli/shims/generator.py src/specify_cli/skills/command_installer.py src/specify_cli/cli/commands/dispatch.py
uv run --frozen ruff check src/specify_cli tests/specify_cli/feedback
uv run --frozen ruff format --check src/specify_cli tests/specify_cli/feedback
make test-fast
```

Also run the pack-manifest gate named by `regenerate-graph`. Record commands and counts in the Activity Log.

## Risks & Mitigations

- **Baseline churn** → regenerate via the documented mechanism and review the diff: only the trigger commands' files should change.
- **The runtime prompt misses the block** → T036 step 3 is the guard; if `build_prompt("tasks")` does not render `tasks/prompt.md`, trace which template it renders and put the block there. Record the finding in the Activity Log.
- **Wording drift between pack and Python** → the drift test.

## Review Guidance

- Diff the regenerated baselines: only `consolidate`/`tasks-finalize` shim files change.
- Confirm there are no edits to generated agent directories in the repository root.
- Confirm the dispatch `--json` payload is unchanged.
- Confirm T041's gate change has a non-vacuity floor, or that an issue was filed and the change reverted.

## Activity Log

> **CRITICAL**: Append entries in chronological order: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-09-30T07:59:37Z – system – Prompt created.
