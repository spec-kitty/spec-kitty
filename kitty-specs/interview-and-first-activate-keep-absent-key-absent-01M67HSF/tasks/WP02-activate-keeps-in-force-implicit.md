---
work_package_id: WP02
title: Activate keeps an in-force artifact implicit
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
- FR-008
- NFR-002
- SC-002
- SC-003
- SC-004
- C-001
- C-003
- C-005
- C-006
- C-007
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts were generated on main. The mission's implementation runs on issue-6685-interview-and-first-activate-keep-absent-key-absent and merges back into main through the operator's PR.
subtasks:
- T005
- T006
- T007
- T008
phase: Phase 2 - The first activation keeps an in-force artifact implicit
history:
- at: '2026-10-30T23:30:00Z'
  actor: system
  action: Prompt authored for the #6685 mission
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- src/charter/activation/activation_engine.py
- src/charter/activation/pack_manager.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/activation_engine.py
- src/charter/activation/pack_manager.py
- tests/charter/test_activation_preserves_effective_4253.py
- tests/charter/test_activation_engine_freeze_warning.py
- tests/charter/test_pack_manager.py
- tests/charter/test_skill_freeze_warning_6458.py
- tests/charter/test_interview_leaves_absent_key_absent_6685.py
- tests/specify_cli/cli/commands/charter/test_activate_only_6408.py
- tests/acceptance/charter_pack_cutover/test_promotion.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6685'
---

# Work Package Prompt: WP02 – Activate keeps an in-force artifact implicit

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status`).
- Address every feedback item, and record each change with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

- On an absent `activated_<kind>` key of an `all`-when-absent kind, `charter activate <kind> <id>` without `--only` writes **no** allow list when the artifact is already in the in-force set. `PackContext.activated_<kind>` stays `None`, every artifact effective before is still effective, and the result names the artifact as activated while saying the key stays absent (FR-003, FR-005, SC-002, SC-003).
- `charter synthesize --dry-run --json` after that first activation reports `fresh_project_seed_dry_run` (FR-006).
- Unchanged, each with its own pin (FR-004): `mission-type`, a `required`-when-absent kind (`skill`), an unresolved effective set, an artifact that is not in force, and a denied artifact (deny-only write, allow key still absent).
- `--only` and `--narrow-activation` unchanged (FR-007/C-003): the list is the selection plus the org-required ids, and the output names what stopped being in force.
- A second identical activation changes no byte (FR-008, NFR-002).

## Context & Constraints

- Spec: `kitty-specs/interview-and-first-activate-keep-absent-key-absent-01M67HSF/spec.md`. Plan, including its **Design** table: `.../plan.md`.
- The plan/commit seam is `plan_activation()` + `commit_plan()` in `src/charter/activation/activation_engine.py`; the caller is `ActiveCharterManager.activate` in `src/charter/activation/pack_manager.py`. `plan.new_list is None` already means "leave the allow key absent" (the D-09 deny-only branch uses it).
- The new guard must sit **after** the narrow branch and **after** the D-09 deny-only branch, and must be exactly: key absent, `effective_when_absent == "all"`, `effective_ids_in_force`, and the artifact in the in-force set. Everything else falls through to today's materialisation.
- `mission-type` reaches `plan_activation` with `effective_when_absent="all"` but its preservation is a substitute (`in_force=False`), so the guard cannot fire for it — pin that with a test rather than adding a kind branch.
- Zero drop is the invariant (#4253, C-001): not writing leaves the unrestricted state, which is stronger than today's materialised copy.
- Complexity ≤ 15 per function. No new `# noqa` / `# type: ignore` without a narrow, justified reason.

## Branch Strategy

- **Strategy**: planning artifacts were generated on `main`; implementation runs on `issue-6685-interview-and-first-activate-keep-absent-key-absent`.
- **Planning base branch**: `main`
- **Merge target branch**: `main` (via the operator's PR; never push `main`)

Implementation command:

```bash
spec-kitty agent action implement WP02 --agent pi --mission interview-and-first-activate-keep-absent-key-absent-01M67HSF
```

## Subtasks

### T005 — End-to-end red-first reproduction for the first activation

Extend `tests/charter/test_interview_leaves_absent_key_absent_6685.py` with the activate case:

1. Same #6685 fixture (no activation key).
2. `charter activate directive <stem>` through the CLI, exit code 0.
3. Assert `PackContext.from_config(project).activated_directives is None`, every previously effective directive is still effective, and `charter synthesize --dry-run --json` reports `fresh_project_seed_dry_run`.

Red on main: the key is written with the whole in-force set (38 entries).

### T006 — `plan_activation` keeps an in-force artifact implicit

Add the guard described above. Rename/refresh the warning so it says what happened: the kind keeps no explicit activation set because the artifact was already in force, so the key stays absent and artifacts shipped later stay active; `charter activate <kind> <id> --only` writes an explicit list. Update `plan_activation`'s and `_preservation_set`'s docstrings where they promise materialisation.

### T007 — Activation pins: #4253 rows, freeze-warning rows, `--only` ratchet, skill/mission-type ratchet

- `tests/charter/test_activation_preserves_effective_4253.py`: `test_first_activation_keeps_every_previously_effective_directive` and `test_first_activation_of_a_procedure_keeps_the_rest_effective` now assert the key stays absent **and** keep the zero-drop assertion; `test_default_activation_warning_says_the_materialised_list_is_frozen` moves its freeze assertion to a case that still materialises (e.g. `skill`, or an unresolvable set) and gains the new message assertion. Leave `test_an_explicitly_restricted_set_is_still_respected`, `test_an_explicitly_empty_set_is_still_respected`, `test_mission_type_seeding_spans_both_org_packs` and `test_resolved_set_still_reports_nothing_deactivated` behaviourally unchanged.
- `tests/charter/test_activation_engine_freeze_warning.py`, `tests/charter/test_pack_manager.py`: add the new branch and the "artifact not in force still materialises" row.
- `tests/charter/test_skill_freeze_warning_6458.py`: pin that `skill` still materialises.
- `tests/specify_cli/cli/commands/charter/test_activate_only_6408.py`: unchanged, run it as the `--only` ratchet.

### T008 — The FR-015 acceptance row for the activating caller

In `tests/acceptance/charter_pack_cutover/test_promotion.py`, move the `resynthesize` row into `KEY_STAYS_ABSENT`, and adjust `_assert_preflight_seeded_from_effective_set` so it compares the preflight's proposal against the in-force set when the activation wrote no list — keep the "control: the preflight ran" and "not narrower" assertions.

## Definition of Done

- Both end-to-end cases green, and red on `main` (record both in the tracer).
- `uv run --frozen pytest tests/charter tests/acceptance/charter_pack_cutover -q` green (plus the interview test file from WP01).
- `uv run --frozen ruff check` and `ruff format --check --force-exclude` clean on the touched files.
