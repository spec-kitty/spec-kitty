---
work_package_id: WP01
title: charter context --profile renders the profile-cited sections
dependencies: []
requirement_refs:
- FR-003
- SC-002
planning_base_branch: issue-6990-dispatch-brief-governance-payload
merge_target_branch: issue-6990-dispatch-brief-governance-payload
branch_strategy: Planning artifacts for this mission were generated on issue-6990-dispatch-brief-governance-payload. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6990-dispatch-brief-governance-payload unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
phase: Phase 1 - Foundation
history:
- at: '2026-11-01T15:21:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- tests/charter/test_context_profile_option.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/charter/context.py
- tests/charter/test_context_profile_option.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – `charter context --profile` renders the profile-cited sections

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission dispatch-brief-governance-payload-01M6BV2S`) and address every item before handing back.

## Objectives & Success Criteria

- `spec-kitty charter context --action <a> --profile <id>` renders the same text
  `spec-kitty dispatch "<request>" --profile <id>` embeds for that action,
  profile-cited directive sections included. Spec FR-003, SC-002.
- Without `--profile`, the command's output is byte-identical to today.
- `--json`'s `text`/`context` fields honour `--profile`; the structured blocks
  (`directives`, `tactics`, `styleguides`, `references`, …) stay unchanged and
  profile-agnostic (they are DRG projections, not profile-cited prose).
- An unknown profile id does not fail the command: it renders without profile
  sections (the existing `_load_agent_profile` miss path) and says so on stderr.

## Context

`ProfileInvocationExecutor._resolve_routing_and_context()` calls
`build_charter_context(repo_root, profile=<id>, action=<a>, mark_loaded=False)`
and re-embeds `ctx_result.text` on the payload. On this repository that text is
23,668 bytes, of which 188 lines (≈18.7 KB) are the "Profile-Cited Directives
(<id>)" block. `spec-kitty charter context` has no `--profile` option today
(`src/specify_cli/cli/commands/charter/context.py`), so the only command that can
render those sections is `dispatch` itself — which is the surface #6990 is
trying to stop re-embedding. WP02's brief payload prints
`spec-kitty charter context --action <a> --profile <id>` as its fetch command, so
this option is what makes that reference honest (spec C-002).

Relevant reading:
- `src/charter/activation/context.py` — `build_charter_context(profile=...)`,
  `_load_agent_profile`, and where `profile_record` feeds the renderers.
- `src/charter/activation/context_renderers/profile_sections.py` — the block that
  appears only when a profile is passed.

## Subtask T001 — Failing test first

Write `tests/charter/test_context_profile_option.py` and run it before touching
source; it must fail for the right reason (unknown option / missing block).

Use a fixture project that renders real charter context, following the patterns
already used by `tests/charter/test_context_selection_render.py` and
`tests/charter/test_every_load_delivery.py` (patch or build a minimal
`.kittify/charter/charter.yaml`; a real built-in profile such as
`python-pedro` is available, so no profile mock is needed). Assert:

1. `charter context --action <a> --profile python-pedro` output contains
   `Profile-Cited Directives (python-pedro)`.
2. `charter context --action <a>` (same fixture, same action) does **not** — the
   same-fixture positive/negative control the acceptance-criteria-non-vacuity
   tactic requires, so the absence assertion cannot pass vacuously.
3. `--json --profile python-pedro` carries the profile-cited text in `text` and
   `context`, and the structured `directives` list is unchanged between the two
   runs.
4. An unknown `--profile nope` exits 0 and renders without the profile block.

Drive the real Typer app (`specify_cli.app`), the way the sibling charter CLI
tests do; do not call `build_charter_context` directly as the only assertion.

## Subtask T002 — Implement

In `src/specify_cli/cli/commands/charter/context.py`:

- Add `profile: str | None = typer.Option(None, "--profile", help=...)`, worded so
  it reads as the profile whose cited doctrine is rendered — the same id
  `dispatch --profile` accepts.
- Pass it to `build_charter_context(..., profile=profile)` on the text path.
- The `--include` path and `build_charter_context_json` stay untouched; the JSON
  envelope's `text`/`context` already come from `result.text`.
- Keep the docstring honest: `--profile` changes the rendered text only.

Match the module's existing style (no new imports if avoidable, lazy imports
kept lazy, comments only where they explain a decision).

## Test strategy

- `uv run pytest tests/charter/test_context_profile_option.py -q`
- Regression guard on the neighbour surfaces you touched:
  `uv run pytest tests/charter -q -x -k "context"` (bounded, not a full sweep)
- `uv run pytest tests/architectural/test_docs_cli_reference_parity.py -q`
  (option additions must not disturb the Typer surface set)

## Definition of Done

- The new test file fails before the change (recorded in the hand-off notes) and
  passes after it.
- No `--profile` output change when the option is omitted.
- `ruff check` and the file's mypy-strict posture are clean for the touched file.
- No gate skipped, xfailed or weakened.

## Risks

- `_load_agent_profile` on an unknown id may warn via the catalog-miss path; do
  not convert a miss into an exception (spec: the fetch must still work).
- Do not accidentally make `--profile` imply `--mark-loaded`; first-load state is
  out of scope and `dispatch` deliberately passes `mark_loaded=False`.

## Reviewer guidance

- Compare the rendered text of `charter context --action <a> --profile <id>` with
  what `dispatch --profile <id>` embeds for the same action; they must agree.
- Check the negative control is on the same fixture as the positive one.
