---
work_package_id: WP02
title: The upgrade promotion resolves across layers
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-004
- FR-005
- FR-006
- C-001
- C-002
planning_base_branch: issue-6686-org-pack-selection-promotion
merge_target_branch: issue-6686-org-pack-selection-promotion
branch_strategy: Planning artifacts for this mission were generated on issue-6686-org-pack-selection-promotion. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6686-org-pack-selection-promotion unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
phase: Phase 2 - The reported defect
history:
- at: '2026-10-30T23:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_promote_interview_selections.py
- tests/upgrade/migrations/test_m_4_0_0rc8_promote_interview_selections.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – The upgrade promotion resolves across layers

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) and behave
according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: implementer
- **Agent/tool**: claude

---

## Objectives & Success Criteria

`4.0.0rc8_promote_interview_selections` resolves an interview selection through the shared
resolver from WP01, so a selection that names an org-pack or project-pack artifact is promoted
into a present `activated_<kind>` list instead of being reported unresolved. Everything else the
migration does — absent-key rule, deactivation deny, seeded-list hint, one-run settle, dry run,
bundle re-stamp — is unchanged.

Done when:

- The org-pack and project-pack promotion tests pass through the migration entry point.
- The unknown-id control on the same fixture still reports
  `Unresolved interview selections skipped (not promoted): directive:<id>`.
- `_StemResolver` and `_resolve_selections` are gone; the module uses the shared resolver.
- `uv run pytest tests/upgrade/migrations/test_m_4_0_0rc8_promote_interview_selections.py -q` is green.

## Context & Constraints

- Read the module docstring of `src/specify_cli/upgrade/migrations/m_4_0_0rc8_promote_interview_selections.py`
  first: every rule in it (absent key never written, present list gains only what it lacks,
  settled-once, seeded-list hint) is a contract you must keep.
- **Red first** (DIRECTIVE_034, `test-first-bug-fixing`): write the org-pack test, run it, and
  record the red before touching the migration source. The bug is that the *migration* still
  resolves built-in-only at that moment, even though WP01's resolver exists.
- The write path is out of scope (C-001): keep `resolve_activation_write_target` and
  `promote_activations` exactly as they are used today.
- Mission-step-contract selections stay out of scope (C-002). If the shared resolver happens to
  resolve a kind it did not before, do not add a test that pins it unless it works — and say so
  in the PR's Deferred section either way.
- Keep imports lazy where they are lazy today (registry discovery must not build the index when
  there is no selection).

## Branch Strategy

- **Strategy**: single_branch — implement and land on the topic branch.
- **Planning base branch**: `issue-6686-org-pack-selection-promotion`
- **Merge target branch**: `issue-6686-org-pack-selection-promotion`

## Subtasks & Detailed Guidance

### Subtask T005 – Red org-pack promotion test

- **Purpose**: Pin the reported defect before the fix.
- **Steps**: in `tests/upgrade/migrations/test_m_4_0_0rc8_promote_interview_selections.py` add a
  test that:
  1. builds a project with `_project(tmp_path, "QA_003")` (an org-pack directive declared id)
     and `write_identity_org_pack` from `tests/charter/org_pack_identity_support.py`;
  2. seeds a present list: `seed_activation_ledger(project, activated_directives=[ARCHITECTURE_STEM])`;
  3. runs `PromoteInterviewSelectionsMigration().apply(project)`;
  4. asserts the written `activated_directives` list is `[ARCHITECTURE_STEM, "qa-003-no-fake-green"]`
     and that no warning names `QA_003`.
- **Files**: `tests/upgrade/migrations/test_m_4_0_0rc8_promote_interview_selections.py`
- **Notes**: Run it before the source change and copy the failure into your progress note: it must
  fail on the missing stem / the unresolved warning, not on an import error.

### Subtask T006 – Project-pack promotion and the unknown-id control

- **Steps**: add two tests on the same fixture shape:
  - a project-layer pack artifact selected by declared id is promoted (build the pack under
    `.kittify/charter-packs/<name>/` or the `project_pack_root` layout the identity tests use —
    follow `tests/charter/activation/test_identity_index.py` for the exact project-layer layout);
  - `_project(tmp_path, "QA_003", UNKNOWN_ID)` promotes the org stem **and** reports
    `directive:<UNKNOWN_ID>` — the positive control that proves the unresolved path still works.
- **Files**: `tests/upgrade/migrations/test_m_4_0_0rc8_promote_interview_selections.py`
- **Notes**: This is the non-vacuity pairing: one fixture, both outcomes asserted in one run.

### Subtask T007 – Rewire the migration onto the shared resolver

- **Steps**:
  1. Delete `_StemResolver` and `_resolve_selections`; construct the resolver once, where
     `resolve_offering_root()` is called today, inside the same `try` that turns a broken doctrine
     root into `MigrationResult(success=False, errors=["Could not resolve doctrine root: ..."])`.
     Build it with `SelectionResolver.build(project_path)` (the index already resolves the
     offering root); keep the "no selection at all" early return before it so no doctrine is read.
  2. Use `resolver.resolve(...)` for the selection set: `PROMOTED_KINDS` in order; feed
     `selections.stems` (a `dict[str, list[str]]`) and `selections.unresolved` into the existing
     `_present_lists`, `_promotions`, `_seeded_list_hints` flow.
  3. Format the unresolved warning from `UnresolvedSelection.urn` so the message text is
     byte-identical to today: `_unresolved_warning([entry.urn for entry in resolution.unresolved])`.
     An `ambiguous=True` entry is part of the same warning (the upgrade reports, never refuses).
  4. Use `resolver.stems(kind, listed)` for the present-list comparison that `_StemResolver.stems`
     provided.
- **Files**: `src/specify_cli/upgrade/migrations/m_4_0_0rc8_promote_interview_selections.py`
- **Notes**: Keep the module docstring accurate — update the closing paragraph that says "Only the
  built-in doctrine layer resolves interview ids" to say the resolution goes through the shared
  layer-aware resolver (#6686), with the same "reported, never dropped silently" rule.

### Subtask T008 – Move the ambiguity test to the shared report

- **Steps**: `test_an_unrepresentable_directive_id_is_reported_as_unresolved` currently
  monkeypatches `module.resolve_selected_id_to_stem`; that symbol is gone. Rewrite it against the
  real shared path: use the collision fixture (a directive whose declared id no file stem can
  represent, see `tests/charter/activation/test_stored_spelling_6527.py`) and assert the result
  still succeeds with the unresolved warning naming that id. If building a real collision fixture
  in this module is disproportionate, patch `SelectionResolver.stem` on the migration module's
  resolver class — not the removed helper — and keep the assertion on the warning text.
- **Files**: `tests/upgrade/migrations/test_m_4_0_0rc8_promote_interview_selections.py`
- **Notes**: The behaviour contract is "reported, never silently dropped or reinterpreted"; the
  test must still pin that, not the old helper's name.

## Test Strategy

```bash
uv run pytest tests/upgrade/migrations/test_m_4_0_0rc8_promote_interview_selections.py -q
uv run pytest tests/upgrade/ tests/charter/activation -q      # the migration's neighbours
uv run ruff check src/specify_cli/upgrade/migrations/m_4_0_0rc8_promote_interview_selections.py
uv run mypy src/specify_cli/upgrade/migrations/m_4_0_0rc8_promote_interview_selections.py
```

## Risks & Mitigations

- **Absent key accidentally written**: unchanged code path, but re-run the absent-key tests; the
  no-op result must still be `_NOTHING_TO_PROMOTE`.
- **Warning text drift**: the unresolved message text is asserted in several tests; keep it exact.
- **Eager doctrine read**: the early return for "no selection" must stay before the resolver build.
- **Dry run**: `_discard` and the deep copy stay; the preview is still the primitive's own outcome.

## Review Guidance

- Confirm the red run is recorded and the new test would fail without the resolver (revert the
  migration source alone and watch it go red — the half-by-half proof).
- Confirm no `resolve_selected_id_to_stem(offering_root=...)` call remains in this module and the
  built-in-only docstring paragraph is corrected.
- Confirm `resolve_activation_write_target`/`promote_activations` usage is untouched.

## Progress & Status

Record each subtask with `spec-kitty agent tasks mark-status T00x --status done`, and append the
red run output to the mission tracer with `spec-kitty agent tracer-append`.
