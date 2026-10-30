---
work_package_id: WP01
title: Interview promotes into present lists only
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-005
- FR-006
- FR-007
- FR-008
- NFR-001
- NFR-002
- SC-001
- SC-003
- SC-004
- C-001
- C-002
- C-003
- C-007
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts were generated on main. The mission's implementation runs on issue-6685-interview-and-first-activate-keep-absent-key-absent and merges back into main through the operator's PR.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - The interview stops filling an absent key
history:
- at: '2026-10-30T23:30:00Z'
  actor: system
  action: Prompt authored for the #6685 mission
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- tests/charter/test_interview_leaves_absent_key_absent_6685.py
- src/specify_cli/cli/commands/charter/interview.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/charter/interview.py
- tests/charter/test_interview_leaves_absent_key_absent_6685.py
- tests/specify_cli/cli/commands/test_charter_interview_promotion.py
- tests/acceptance/charter_pack_cutover/test_promotion.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6685'
---

# Work Package Prompt: WP01 – Interview promotes into present lists only

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status`).
- Address every feedback item, and record each change with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

- On a project with no `activated_<kind>` key, `charter interview` with selections and without `--narrow-activation` writes **no** activation key, for every kind it promotes (FR-001, SC-001).
- `charter synthesize --dry-run --json` after such an interview reports `fresh_project_seed_dry_run`, and `_catalog_is_established(repo)` is `False` (FR-006).
- The interview output names each key it left absent, says the whole kind is in force while the key is absent, and names `charter interview --narrow-activation` as the way to write the selection (FR-002).
- A **present** list still gains exactly the interview ids it lacks, on the authoritative activation surface, and no other entry changes (FR-007).
- Every artifact in force before the interview, and every resolving selection that is not deactivated, is in force after it (FR-005, SC-003).
- A second identical run changes no byte (FR-008, SC-004, NFR-002).
- The interview resolves no effective set on its non-narrowing path (NFR-001).

## Context & Constraints

- Spec: `kitty-specs/interview-and-first-activate-keep-absent-key-absent-01M67HSF/spec.md`. Plan, including its **Design** section: `.../plan.md`.
- The writer is `_promote_interview_selections` in `src/specify_cli/cli/commands/charter/interview.py`. Its docstring already calls the seeding "the #6408 residual"; that sentence is what this WP removes.
- **The precedent to follow:**
  - `src/specify_cli/upgrade/migrations/m_4_0_0rc8_promote_interview_selections.py` — "An absent key is never written", and it passes `effective_sets={}` to `promote_activations`.
  - `_promote_org_required_to_config` in `src/charter/activation/org_charter.py` — "An absent key is never seeded."
  - #6629 / #6683: `charter synthesize` reads a *present* list as an operator's activation, so a seeded list re-creates the synthesis block.
- Keep the single write seam: `promote_activations(...)` with `resolve_activation_write_target`. Do not add a `save` call.
- `--narrow-activation` is unchanged: it keeps `effective_sets` and `_narrow_bases` and writes the selection plus the org-required ids.
- Complexity ≤ 15 per function; repeated literals become module constants; no new `# noqa` / `# type: ignore` without a narrow, justified reason.
- Terminology: "activation ledger" for `.kittify/charter/activation.yaml`; "Migration Ledger" for the upgrade ledger. Never "the ledger" bare.

## Branch Strategy

- **Strategy**: planning artifacts were generated on `main`; implementation runs on `issue-6685-interview-and-first-activate-keep-absent-key-absent`.
- **Planning base branch**: `main`
- **Merge target branch**: `main` (via the operator's PR; never push `main`)

Implementation command:

```bash
spec-kitty agent action implement WP01 --agent pi --mission interview-and-first-activate-keep-absent-key-absent-01M67HSF
```

## Subtasks

### T001 — End-to-end red-first reproduction for the interview writer

New file `tests/charter/test_interview_leaves_absent_key_absent_6685.py`, `pytest.mark.integration` + `pytest.mark.git_repo`:

1. Build the #6685 shape: `git init`, `.kittify/config.yaml` holding only `mission_type_activations`, no `activated_*` key.
2. Run `charter interview --defaults --selected-directives <stem> --selected-paradigms <stem>` through `typer.testing.CliRunner` and `charter_app`.
3. Assert no `activated_*` key anywhere on the activation surface, `_catalog_is_established(project) is False`, and the output names the absent key.
4. Run `charter synthesize --dry-run --json` and assert `mode == "fresh_project_seed_dry_run"`.

Red on main: the interview writes `activated_directives` (38 entries) and `activated_paradigms` (14), and `synthesize` fails with `GeneratedArtifactMissingError`. Run it and record the red in `traces/approach.md` (via `spec-kitty agent tracer-append`).

### T002 — The interview promotes into present lists only

In `_promote_interview_selections`:

1. When `narrow` is off, read the write target once and keep only the promotions whose key the target already holds (`config_data.get(key) is not None`).
2. Emit one message per dropped key: the key stays absent because the whole kind is in force while it is absent, nothing was written, and `charter interview --narrow-activation` writes the selection as an explicit list.
3. Pass `effective_sets={}` to `promote_activations` on that path — do not resolve an effective set at all.
4. Leave the narrow path as it is.
5. Update the docstring: drop "This seeding is the #6408 residual", state the absent-key rule and the precedent, keep the write-target and best-effort notes.

### T003 — Focused interview tests: absent, present, narrowed, denied, idempotent

Update `tests/specify_cli/cli/commands/test_charter_interview_promotion.py`:

- `test_interview_promotes_selections_preserving_builtins_on_absent_key` becomes the absent-key pin: no key written, and every previously effective id still in force (`resolve_effective_sets` / `PackContext`).
- Tests that assert the selected id lands in the list (`test_interview_normalizes_canonical_form_directive_id`, `test_interview_promotion_is_idempotent_across_runs`, the denied-reselection and stale-deny tests, the two restamp tests) move to a **present** list fixture, keeping their original assertion.
- Add: the absent-key message text; the narrowing path unchanged on an absent key; a present list that already holds the selection gains nothing.

### T004 — The FR-015 acceptance row for the interview caller

In `tests/acceptance/charter_pack_cutover/test_promotion.py`, move the `interview` row into `KEY_STAYS_ABSENT` (the control assertion at the row already keeps the zero-drop check). Keep the `org_charter_union` and `resynthesize` rows as they are — WP02 moves the activating one.

## Definition of Done

- The new end-to-end test is green, and the same test is red on `main` (record both).
- `uv run --frozen pytest tests/charter/test_interview_leaves_absent_key_absent_6685.py tests/specify_cli/cli/commands/test_charter_interview_promotion.py tests/acceptance/charter_pack_cutover/test_promotion.py -q` is green.
- `uv run --frozen ruff check` and `ruff format --check --force-exclude` clean on the touched files.
