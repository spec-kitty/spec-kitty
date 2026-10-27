---
work_package_id: WP01
title: 'charter activate output: --only consistency and org-required freeze warning'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
planning_base_branch: issue-6457-activate-output-identity
merge_target_branch: issue-6457-activate-output-identity
branch_strategy: Planning artifacts for this mission were generated on issue-6457-activate-output-identity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6457-activate-output-identity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-activate-output-and-identity-01M5ZA9X
base_commit: d2279fbd4a214dad222edd782ff44a9b5101f65b
created_at: '2026-10-27T18:43:11.401211+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Implementation
history:
- at: '2026-10-27T18:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/specify_cli/cli/commands/charter/test_activate_output_6457.py
- tests/charter/test_skill_freeze_warning_6458.py
- tests/charter/activation/test_activation_engine_freeze_warning.py
execution_mode: code_change
owned_files:
- src/charter/activation/activation_engine.py
- src/charter/activation/pack_manager.py
- src/specify_cli/cli/commands/charter/activate.py
- tests/specify_cli/cli/commands/charter/test_activate_only_6408.py
- tests/specify_cli/cli/commands/charter/test_activate_output_6457.py
- tests/charter/test_skill_freeze_warning_6458.py
- tests/charter/activation/test_activation_engine_freeze_warning.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – charter activate output: --only consistency and org-required freeze warning

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address every feedback item; record progress with `spec-kitty agent tasks add-history WP01 --note "..."`.

## Review Feedback

*[Filled from the status event log when returned from review.]*

---

## Objectives & Success Criteria

- FR-001: under `--only`, no absent-key preservation warning ("Initialized from the N ...", "initialized from the N mission types ...", "The effective <kind> set could not be resolved ...; initialized from ...") is printed.
- FR-002: `--only` on an absent `mission_type_activations` key prints no "What stopped being in force cannot be listed" warning (nothing was in force) and reports `No longer in force (0): (none)`.
- FR-003: `--only` on a kind whose effective set cannot be resolved prints exactly one warning: `What stopped being in force cannot be listed: the effective set could not be resolved because <reason>.`
- FR-004: every `--only` run prints `Now listed for <kind> (<N>): <id>, <id>` (ids in written order) before the `No longer in force` line.
- FR-005: `activate skill <id>` on an ABSENT `activated_skills` key prints the freeze warning and does NOT print the `--only` recommendation (`FROZEN_LIST_NOTE`).
- FR-006: `activate skill <id> --only` prints the freeze warning on every run (absent or present key).
- FR-007: the freeze warning is emitted only for kinds with `ArtifactKind.effective_when_absent == "required"` (today only `skill`); `toolguide` with and without `--only` never prints it; a plain skill activation on a PRESENT key does not print it.
- C-001: the written activation list, deny list and exit code are unchanged for every case — assert the written list in each new CLI test.

Freeze warning text (operator-approved, Decision Moment `skill_freeze_warning`), for kind token `skill`, plural `skills`:

```
Kind 'skill' now has an explicit activation list, so the org packs' required skills are frozen at their current values: a skill an org pack later adds to required_skills will not reach this project.
```

## Context & Constraints

- Spec: `kitty-specs/activate-output-and-identity-01M5ZA9X/spec.md`; plan IC-01..IC-03; research.md (line citations and red-first reproductions).
- Charter: tidy-first (T001 is its own commit), red-first, complexity <= 15, no new `noqa`/`type: ignore`, warning texts live once in `activation_engine` (C-004).
- Out of scope (epic #6518, #6684, #6685): the allow-list vs org-required-floor semantics; do not change what any path writes.
- `NARROW_UNRESOLVED_WARNING` is also used by the interview promotion planner (`_plan_promotion`); keep the constant and its text unchanged there.

## Branch Strategy

- **Strategy**: lanes (computed by finalize-tasks)
- **Planning base branch**: issue-6457-activate-output-identity
- **Merge target branch**: issue-6457-activate-output-identity

Execution worktrees are allocated per computed lane from `lanes.json`; use the workspace `spec-kitty agent action implement` resolves.

## Subtasks & Detailed Guidance

### Subtask T001 – Tidy-first: preservation value object

- **Purpose**: let the narrow path know *why* the effective set was unresolved.
- **Steps**: in `pack_manager.py` add a frozen dataclass (e.g. `_Preservation`: `ids`, `warnings`, `in_force`, `unresolved_reason: str | None = None`). `_preservation_ids` returns it (set `unresolved_reason=effective.reason` on the generic unresolved branch AND on the mission-type branch); `_preservation_set` subtracts the deny on `ids` and returns it; `activate` reads its fields. No output change.
- **Validation**: existing `tests/specify_cli/cli/commands/charter/test_activate_*.py` and `tests/charter/test_skill_activation.py` green, unchanged. Commit alone ("refactor(charter): ...").

### Subtask T002 – Red-first #6457 tests

- **File**: `tests/specify_cli/cli/commands/charter/test_activate_output_6457.py` (CLI via `CliRunner` on `charter_app`, `--no-compile`; reuse the fixture style of `test_activate_only_6408.py`).
- Cases: (a) empty project, `activate mission-type software-dev --only`: no "initialized from", no "could not be resolved", `Now listed for mission-type (1): software-dev`, `No longer in force (0): (none)`, ledger `mission_type_activations == ["software-dev"]`; (b) toolguide with an unreadable declared org pack (see `test_only_with_an_unresolvable_effective_set_...`): exactly one "could not be resolved because" warning, no "initialized from", list `[gherkin]`; (c) positive control: same fixture as (b) WITHOUT `--only` still prints the "initialized from" preservation warning; (d) present-list `--only` prints the Now-listed line with the written count.
- Run them and record they fail on the T001 commit.

### Subtask T003 – `--only` warning selection

- In `activate`: when narrowing, `warnings = narrow.warnings` (replace, do not concatenate).
- In `_narrow_inputs`: present → previous = present; in_force → previous = preserved; `kind is None` (mission-type, absent key) → previous = [] and no warning; otherwise previous = [] and the reasoned warning.
- In `activation_engine.py` add `narrow_unresolved_warning(reason: str | None) -> str` next to `NARROW_UNRESOLVED_WARNING` (returns the constant when `reason` is falsy, else the constant with `because <reason>` before the final period). Export it in `__all__` if the module lists one.

### Subtask T004 – "Now listed" line

- Add `listed: list[str] = field(default_factory=list)` to `ActivationResult`; set it from `plan.new_list or []` in `activate`.
- `_render_activation_result(result, registration, *, only, kind)`: under `only`, print `Now listed for {kind} ({len}): {escape(', '.join(listed)) or '(none)'}` before the `No longer in force` line. Update the one call site.

### Subtask T005 – Red-first #6458 tests

- **Files**: `tests/charter/test_skill_freeze_warning_6458.py` (CLI; reuse `tests/charter/skill_pack_support.py` fixtures: org pack with skills `required-one, x, y`, `required_skills: [required-one]`) and `tests/charter/activation/test_activation_engine_freeze_warning.py` (pure `plan_activation` unit tests).
- Cases: plain absent key → warning present, `--only` advice absent, ledger `[required-one, x]`; plain present key → warning absent; `--only` absent and present → warning present; toolguide plain + `--only` → warning absent (control). Engine: `plan_activation(..., effective_when_absent="required")` absent key and with `narrow_base` → warning; `"all"` → none.

### Subtask T006 – Engine freeze warning

- Add a public helper/constant in `activation_engine.py`, e.g. `org_required_freeze_warning(kind: str, plural: str) -> str` producing the approved text.
- `_materialise_absent`: for `effective_when_absent == "required"`, the in-force message ends after "so nothing in force was deactivated." (no `FROZEN_LIST_NOTE`), and the freeze warning is appended as its own warning (independent of `in_force`). `"all"` kinds are unchanged.
- `plan_activation` narrow branch: when `effective_when_absent == "required"`, append the freeze warning to the narrowed plan's warnings (plural from `yaml_key.removeprefix("activated_")`). Keep `_with_deny` behaviour.
- Keep each function <= complexity 15 (extract a helper if needed).

### Subtask T007 – Gates

```bash
uv run --frozen ruff check src/charter/activation/activation_engine.py src/charter/activation/pack_manager.py src/specify_cli/cli/commands/charter/activate.py <new tests>
uv run --frozen ruff format --check --force-exclude <same files>
uv run --frozen mypy src/charter/activation/activation_engine.py src/charter/activation/pack_manager.py src/specify_cli/cli/commands/charter/activate.py
uv run --frozen pytest <new tests> tests/specify_cli/cli/commands/charter/ tests/charter/test_skill_activation.py -q
uv run --frozen pytest tests/charter/ tests/charter_offering/ -q -p no:randomly -n auto --dist loadfile
```

## Test Strategy

Red-first for every FR (T002, T005 before T003/T006). Same-fixture positive controls (FR-001 via (c); FR-005/FR-007 via present-key and toolguide controls).

## Risks & Mitigations

- Existing `test_activate_only_6408.py` assertions on "could not be resolved" remain satisfied by the reasoned narrow warning; if a test there asserts the concatenation, re-pin it (a stale assertion of the bug) and say so in the history note.
- Never change written lists: every new CLI test asserts the ledger list.

## Review Guidance

- Reviewer (different profile): verify red-first evidence, written lists unchanged, freeze warning text exactly as approved, no `--only` advice for skills, mypy/ruff/format clean, complexity <= 15.
