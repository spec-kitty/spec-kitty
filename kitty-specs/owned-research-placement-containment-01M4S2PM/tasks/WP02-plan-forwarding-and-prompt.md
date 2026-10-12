---
work_package_id: WP02
title: Owned plan forwarding + discovery-prompt affordance (#5882)
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- NFR-001
- C-002
- C-003
- SC-003
planning_base_branch: issue-5882-owned-research-placement-and-plan
merge_target_branch: issue-5882-owned-research-placement-and-plan
branch_strategy: Planning artifacts for this mission were generated on issue-5882-owned-research-placement-and-plan. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5882-owned-research-placement-and-plan unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
phase: Phase 2 - Plan authoring path
history:
- at: '2026-10-12T22:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/lifecycle.py
create_intent:
- tests/specify_cli/cli/commands/test_plan_owned_forwarding.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/lifecycle.py
- packs/built-in/missions/mission-steps/software-dev/research/prompt.md
- tests/specify_cli/cli/commands/test_plan_owned_forwarding.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5882'
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile with the `/spk-charter-profile-load` skill (profile: `python-pedro`, role: implementer). Then continue.

# Work Package Prompt: WP02 – Owned plan forwarding + discovery-prompt affordance (#5882)

## Objectives & Success Criteria

- `spec-kitty plan --help` lists `--owned-checkout`, and `spec-kitty plan --mission <slug> --owned-checkout P` forwards the validated owned fact to the owned-aware `setup_plan` seam (FR-004, SC-003).
- The research discovery prompt surfaces the owned selector affordance for the authoring commands it invokes (FR-005).
- Non-owned `plan` behaviour is unchanged (NFR-001). Coord topology stays out of scope (C-002, cross-link #2683); non-goals honoured (C-003).
- Changelog `[Unreleased]` entry added. `ruff`/`mypy` clean.

## Context & Constraints

- Grounding: `../analysis-report.md` (§2 Surface B) and `../plan.md` IC-02.
- `lifecycle.py` `plan(...)` (246) is a thin wrapper over `agent_feature.setup_plan(feature=..., json_output=...)`; the `setup_plan` seam ALREADY accepts `owned_checkout: OwnedCheckoutOption`. The wrapper simply never exposes/forwards it.
- The wrapper also runs an interactive `run_plan_interview` keyed on `locate_project_root()`; that interview is already skipped in `--json` (agent) mode, which is the owned-flow path — leave interactive-owned interview resolution as a documented follow-up (C-003), do NOT over-reach.
- No prompt template renders an owned selector today; keep the prompt change a light, correct affordance (note that an owned single-branch run passes `--owned-checkout <P>`), not an unconditional flag that would mislead non-owned runs.

## Subtasks & Detailed Guidance

### Subtask T005 – ATDD: top-level `plan` owned forwarding reproduction (RED first)

- **Purpose**: Pin the forwarding contract before the change.
- **Steps**: Add `tests/specify_cli/cli/commands/test_plan_owned_forwarding.py`: (a) `spec-kitty plan --help` output contains `--owned-checkout`; (b) invoking the top-level `plan` with `--owned-checkout P` passes an `OwnedCheckout` (or the path) through to `setup_plan` — assert via a `monkeypatch`/spy on `agent_feature.setup_plan` capturing the `owned_checkout` kwarg. RED on base: `--owned-checkout` is `No such option`.
- **Validation**: `.venv/bin/python -m pytest tests/specify_cli/cli/commands/test_plan_owned_forwarding.py -q` → RED.

### Subtask T006 – Expose + forward `--owned-checkout` on top-level `plan`

- **Purpose**: Complete the owned plan authoring path.
- **Steps**: Add `owned_checkout: OwnedCheckoutOption = None` to `lifecycle.plan(...)` and forward it: `agent_feature.setup_plan(feature=mission_slug, json_output=json_output, owned_checkout=owned_checkout)`. Guard the interactive interview: skip it (as today) in `--json` mode; when `owned_checkout is not None` and not `--json`, keep current interview behaviour but do not resolve it against the primary for an owned run (document the follow-up; do not implement owned interview resolution here).
- **Files**: `src/specify_cli/cli/commands/lifecycle.py`.

### Subtask T007 – Surface the owned selector in the research discovery prompt

- **Purpose**: Generated discovery prompts render the ownership affordance for the authoring commands they invoke (FR-005).
- **Steps**: In `packs/built-in/missions/mission-steps/software-dev/research/prompt.md`, where it directs `spec-kitty research --mission <handle>`, add a short note: for an owned single-branch Mission, pass `--owned-checkout <owned-checkout-path>` (or run the command from inside the owned checkout, which auto-adopts it). Keep it a one-line affordance; do not rewrite the prompt.
- **Files**: `packs/built-in/missions/mission-steps/software-dev/research/prompt.md`.

### Subtask T008 – Validate green + changelog

- **Steps**: Add a `docs/changelog/CHANGELOG.md` `[Unreleased]` entry (bold impact-first lead + `(#5882)`, before→after). Run `tests/specify_cli/cli/commands/test_plan_owned_forwarding.py` + the lifecycle command tests; `ruff`/format/`mypy` on changed files; `pytest tests/architectural/test_no_legacy_terminology.py` (prompt text touched).

## Definition of Done

- `plan` exposes + forwards `--owned-checkout`; prompt affordance added; changelog entry present; non-owned `plan` unchanged; lint/type/terminology clean.

## Reviewer Guidance

- Confirm the forwarding reaches `setup_plan` with the owned fact and non-owned `plan` is unchanged; confirm the prompt note is correct for both owned and non-owned runs; confirm coord topology (#2683) is explicitly out of scope.
