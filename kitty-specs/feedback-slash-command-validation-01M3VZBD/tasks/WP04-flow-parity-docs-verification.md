---
work_package_id: WP04
title: Flow parity, docs and verification
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- FR-014
planning_base_branch: feat/in-harness-feedback-survey
merge_target_branch: feat/in-harness-feedback-survey
branch_strategy: Planning artifacts for this mission were generated on feat/in-harness-feedback-survey. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/in-harness-feedback-survey unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-feedback-slash-command-validation-01M3VZBD
base_commit: 781d93bcd1742bc0eac7e833b5d02548eb48796e
created_at: '2026-10-01T20:27:13.734747+00:00'
subtasks:
- T016
- T017
- T018
- T019
phase: Phase 3 - Polish
history:
- at: '2026-10-01T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: docs/
create_intent:
- tests/specify_cli/feedback/test_flow_parity.py
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/feedback/test_flow_parity.py
- docs/guides/how-to/collaboration/give-feedback.md
- docs/context/feedback.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Flow parity, docs and verification

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: set at claim time

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` in the event log (`spec-kitty agent tasks status`) or the Activity Log. Address every feedback item and log what you changed.

---

## Objectives & Success Criteria

- A parity test shows the shared input table gives identical accept/reject results and identical sanitized values through the validator, the terminal form and `agent_submit` (NFR-003, FR-014).
- Docs describe the command, the validation rules and the visible limit; the changelog has an entry.
- Targeted gates pass and the exact commands and counts are recorded for the PR.

## Context & Constraints

- Read `kitty-specs/feedback-slash-command-validation-01M3VZBD/{spec,plan,quickstart}.md`, `.kittify/charter/charter.md`.
- WP01, WP02 and WP03 must be merged first. Reuse the table constants from `tests/specify_cli/feedback/test_validation_table.py`.
- Docs are vendor-neutral: no company names other than Spec Kitty, examples use `example.test` or loopback only.
- Root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`; edit the latter.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated by `spec-kitty agent mission finalize-tasks`. Do not edit by hand.

## Subtasks & Detailed Guidance

### Subtask T016 – Flow-parity test

- **Purpose**: Prove no flow is weaker than another.
- **Steps**: Create `tests/specify_cli/feedback/test_flow_parity.py`. For each case in the shared tables run it through the parsers, through the terminal form (drive its input function with the case, as `test_terminal_form.py` does) and through `agent_submit` (no endpoint or a loopback server, so nothing real is sent). Assert the same accept/reject outcome and same cleaned value. Also assert each flow calls the shared parsers (for example by patching them and counting calls) so a flow that skips validation is caught.
- **Files**: `tests/specify_cli/feedback/test_flow_parity.py`.
- **Parallel?**: Yes with T017 and T018.

### Subtask T017 – Docs

- **Purpose**: Users and maintainers can find the command and the rules.
- **Steps**: In `docs/guides/how-to/collaboration/give-feedback.md` describe `/spec-kitty.feedback`, that it ignores the weekly throttle, the rating, comment (with the visible limit and cleaning rules) and email rules. Update `docs/context/feedback.md` with the shared validator and the `on_demand` trigger. Remove stale references to the old comment question wording.
- **Files**: the two docs.
- **Parallel?**: Yes.

### Subtask T018 – Changelog

- **Purpose**: Release note.
- **Steps**: Add an entry under the unreleased section of `docs/changelog/CHANGELOG.md` for the new command and the stricter validation.
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Parallel?**: Yes.

### Subtask T019 – Targeted gates

- **Purpose**: Evidence for the PR.
- **Steps**: Run, and record exact commands and passed/failed counts in the Activity Log:
  - `uv run --frozen pytest tests/specify_cli/feedback -q`
  - the specific registry/installer/pack gate files touched in WP03
  - `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q`
  - `uv run --frozen ruff check` and `uv run --frozen ruff format --check` on changed paths
  - `uv run --frozen mypy --strict src/specify_cli/feedback`
  - `spec-kitty doctrine regenerate-graph --check`
- Do not run `make test-full` or whole-repo suites.

## Test Strategy

- The parity test is the new test; everything else is the gate list in T019.

## Risks & Mitigations

- Parity test gives false comfort if a flow skips the parsers → the call-count assertion.
- Vendor names creeping into docs → search the diff before finishing.

## Review Guidance

- Confirm parity test covers all three entry points and the shared tables.
- Confirm docs are vendor-neutral and accurate to the shipped behavior.
- Confirm recorded gate commands and counts are present.

## Activity Log

> Entries are chronological, oldest first; append new entries at the end.
> Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`

- 2026-10-01T20:00:00Z – system – Prompt created.
