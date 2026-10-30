---
work_package_id: WP02
title: One authority in the doctor's containment flow
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-006
- FR-008
- NFR-001
- NFR-002
- NFR-004
- C-001
- C-004
- SC-001
- SC-002
- SC-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 2 - Runtime and doctor
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/drg_activation.py
- src/specify_cli/cli/commands/_charter_pack_collect.py
- src/specify_cli/cli/commands/_profile_health_render.py
- tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – One authority in the doctor's containment flow

> **CANCELED — folded into WP01 (review finding F1).** This package was planned and
> then canceled before implementation: the boundary between it and WP01 cut through
> one atomic refactor, so WP01 could not be independently delivered (at WP01's first
> head the activation wrappers still called the two-argument predicate, and
> `doctor charter-packs` reported a failed containment check for every project with
> org packs). Its subtasks T007–T012 moved into WP01 unchanged and were delivered
> there. This file is kept as the record of the canceled package.

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(`python-pedro`), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile show python-pedro` and follow it from
there.

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status` for the `review_ref` field before starting. If review feedback
exists, it is your TODO list and must be addressed before this package is complete. Record what you
changed with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

The doctor's containment flow reads the pack registry **once**, inside `load_org_drg`, because the
fragment now carries the root (WP01). This package deletes the two activation wrappers and
`_org_pack_roots_by_name`, re-points both doctor halves onto the offering predicates through the
`charter.drg` facade, and keeps every refusal identical.

Done when:

- One `_collect_org_layer_data` run and one `_render_org_layer_section` run each call
  `charter.offering.drg.org_pack_config.load_pack_registry` exactly **once** (three before this
  mission).
- `charter.activation.drg_activation` no longer defines or exports `find_org_body_path_escapes`,
  `find_org_asset_path_escapes` or `_org_pack_roots_by_name`.
- `doctor charter-packs` produces the same findings, messages, JSON keys and exit codes as before:
  the #6418 tests keep their assertions, including RC=1 for dot-dot and absolute escapes on both
  the `body_path` and the asset `path`, and RC=0 for contained controls.
- The activation-seam gate passes with `tests/architectural/charter_activation_boundary_baseline.yaml`
  **unchanged**.
- The dead-symbol gate passes: the facade names gain live callers (the doctor).

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6731. Read `spec.md`, `plan.md`, `tasks.md` and WP01's prompt in
  `kitty-specs/org-drg-fragment-pack-root-01M66YJG/` before starting.
- WP01 has already landed in your base: `OrgDRGFragment.pack_root`, `OrgPackRootUnavailableError`,
  `find_body_path_escapes(fragment)` and `find_asset_path_escapes(fragment)` exist and are
  re-exported by `charter.drg`. Until this package lands, the activation wrappers call the old
  two-argument form and the doctor's containment check is broken — that is expected at your base.
- **Do not** touch `packs/`, `src/charter/offering/**` or the offering tests (WP01 owns them).
- **Do not** edit `charter_activation_boundary_baseline.yaml`. Both doctor files keep importing
  `load_org_drg` from `charter.activation.drg_activation`, so their baseline rows stay accurate; no
  row is added or drained. If the gate disagrees, the import change is wrong — fix the import, not
  the baseline.
- Keep the two `except Exception` channels and their exact message prefixes
  (`org-layer body_path check failed:`, `org-layer asset path check failed:`), and the human
  half's `not checked` rendering. They are pinned by tests and are how an operator tells "the check
  could not run" from "nothing found".

## Branch Strategy

- **Strategy**: `single_branch` topology; implementation commits on
  `kitty/mission-org-drg-fragment-pack-root-01M66YJG` and merges back into it.
- **Planning base branch**: `kitty/mission-org-drg-fragment-pack-root-01M66YJG`
- **Merge target branch**: `kitty/mission-org-drg-fragment-pack-root-01M66YJG`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not change by hand.

## Subtasks & Detailed Guidance

### Subtask T007 – Red counting test: one registry read per doctor run

- **Purpose**: Pin the acceptance criterion itself (FR-006 / NFR-001 / SC-001), red before the fix.
- **Steps**:
  1. In `tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py`, add a test that
     monkeypatches `charter.activation.drg_activation.load_pack_registry` with a counting wrapper
     (delegate to the real function), runs `_collect_org_layer_data(tmp_repo_with_org_pack)`, and
     asserts `len(calls) == 1`.
  2. Add the same count assertion for `_render_org_layer_section` (use `_render`).
  3. Add a positive control in the same module: assert the real registry read happened (`calls`
     non-empty and `result["configured_packs"]` names the pack), so a broken probe cannot pass by
     counting zero calls.
  4. Run it: it must fail with 3 reads before T008–T010.
- **Files**: `tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py`
- **Parallel?**: No.
- **Notes**: Count reads, not time. Do not weaken the assertion to `<= 2`.

### Subtask T008 – Delete the wrappers and the re-read

- **Purpose**: FR-004. Remove the second authority and its home.
- **Steps**:
  1. Delete `find_org_body_path_escapes`, `find_org_asset_path_escapes` and
     `_org_pack_roots_by_name` from `src/charter/activation/drg_activation.py`.
  2. Drop them from `__all__`, and drop the imports that become unused (`Sequence`,
     `AssetPathEscape`, `BodyPathEscape`, `find_asset_path_escapes`, `find_body_path_escapes`,
     `load_pack_registry` — verify each; `load_org_drg` still needs `load_pack_registry`).
  3. Update the module docstring's "Provides:" list so it describes what the module actually
     provides now.
- **Files**: `src/charter/activation/drg_activation.py`
- **Parallel?**: No.
- **Notes**: `load_org_drg` is untouched apart from nothing — it already reads the registry once and
  stamps the fragments.

### Subtask T009 – JSON half onto the facade

- **Purpose**: FR-005 for `_collect_org_layer_data`.
- **Steps**:
  1. In `_record_body_path_escapes` and `_record_asset_path_escapes`
     (`src/specify_cli/cli/commands/_charter_pack_collect.py`), import the predicate from
     `charter.drg` instead of `charter.activation.drg_activation`.
  2. Aggregate per fragment in fragment order:
     `escapes = [escape for fragment in fragments for escape in find_body_path_escapes(fragment)]`
     (and the asset equivalent), inside the existing `try`.
  3. Leave the `repo_root` parameters alone if they are still used elsewhere in the module; drop a
     parameter only if it becomes unused, and then update the two call sites in
     `_collect_org_layer_data`.
- **Files**: `src/specify_cli/cli/commands/_charter_pack_collect.py`
- **Parallel?**: Yes (independent of T010).
- **Notes**: Finding order must stay fragment order — the JSON arrays are compared by tests.

### Subtask T010 – Human half onto the facade

- **Purpose**: FR-005 for `_render_org_layer_section`'s two helpers.
- **Steps**:
  1. In `_render_org_body_path_escapes` and `_render_org_asset_path_escapes`
     (`src/specify_cli/cli/commands/_profile_health_render.py`), import from `charter.drg` and
     aggregate the same way.
  2. Keep the "not checked" branch and its exception text verbatim.
- **Files**: `src/specify_cli/cli/commands/_profile_health_render.py`
- **Parallel?**: Yes.
- **Notes**: The two halves must stay parallel in shape; a reviewer will diff them against each
  other.

### Subtask T011 – Re-point the doctor tests and assert the absence

- **Purpose**: The pinned refusals must keep pinning the *live* seam.
- **Steps**:
  1. Re-point the four `monkeypatch.setattr(drg_activation, "find_org_…_escapes", _boom)` targets
     at `charter.drg`'s predicate names, so the "a check that could not RUN is reported" tests still
     inject a crash into the path the doctor actually calls.
  2. Add a test asserting `charter.activation.drg_activation` has no `find_org_body_path_escapes`,
     `find_org_asset_path_escapes` or `_org_pack_roots_by_name` attribute, with `load_org_drg` as
     the positive control (the probe can see a symbol that is there). Keep it in the doctor module
     or a small `tests/charter/activation/` module — your choice, but it must live inside this WP's
     `owned_files`; extend `owned_files` in the frontmatter if you add a file.
  3. Keep every existing assertion in the module unchanged: RC matrix, message text, JSON shape,
     truncation, truncated `… and N more` tails, `fine-logo` not named, etc.
- **Files**: `tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py`
- **Parallel?**: No.
- **Notes**: A monkeypatch of a deleted symbol silently "passes" because setattr on a module
  creates the attribute — that is why (2) matters.

### Subtask T012 – Verification

- **Purpose**: Prove the package, including the architectural ratchets.
- **Steps**:
  1. `uv run --frozen pytest tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py tests/charter_offering/drg/test_org_body_path_escapes.py tests/charter_offering/assets/test_org_asset_path_escapes.py -q`
  2. `uv run --frozen pytest tests/architectural/test_runtime_charter_activation_boundary.py tests/architectural/test_no_dead_symbols.py -q`
  3. `uv run --frozen pytest tests/charter -q` (activation module regression; keep it scoped)
  4. `uv run --frozen ruff check` and `ruff format --check` on the four touched files;
     `uv run --frozen mypy` on the touched `src` files (match the repo's configured invocation).
  5. Run the doctor command end to end on a fixture repo to eyeball the human output once
     (`spec-kitty doctor charter-packs`); record the result.
  6. Record results with `spec-kitty agent tasks add-history WP02 --note "..."`.
- **Files**: none (verification only)
- **Parallel?**: No.
- **Notes**: Do not run a full heavy suite. `cancelled` CI runs are not failures.

## Test Strategy

- T007 is the acceptance proof (a count, not a shape): three reads before, one after.
- The existing #6418 refusal matrix is the regression contract; do not rewrite those assertions.
- The absence test (T011.2) needs its `load_org_drg` positive control, or it would pass on an empty
  module.

## Risks & Mitigations

- **Silently passing crash injection** after the symbol moves → re-point the monkeypatch (T011.1)
  and assert absence positively (T011.2).
- **Seam-gate drift** → keep `load_org_drg` imports where they are; never edit the baseline.
- **Output drift** from aggregation order → aggregate in fragment order and keep the existing
  message strings; the doctor tests compare exact text.

## Review Guidance

- Confirm the registry is read once and only inside `load_org_drg` (`grep load_pack_registry src/`).
- Confirm the two doctor halves are still parallel and share the predicate, so JSON and human output
  cannot disagree.
- Confirm no test was weakened: assertions and message strings unchanged except monkeypatch targets.
- Confirm `charter_activation_boundary_baseline.yaml` and `charter/activation/api.py` are untouched.

## Progress & Status

Progress, history and status live in the status event log (`status.events.jsonl`) — never in this
prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
