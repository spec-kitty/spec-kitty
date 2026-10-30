---
work_package_id: WP01
title: Non-mapping sidecar skip in the base loader, red-first
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6735-asset-sidecar-non-mapping-crash
merge_target_branch: issue-6735-asset-sidecar-non-mapping-crash
branch_strategy: Planning artifacts for this mission were generated on issue-6735-asset-sidecar-non-mapping-crash. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6735-asset-sidecar-non-mapping-crash unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-asset-sidecar-non-mapping-crash-01M66937
base_commit: e272858ada5a19e75cebdedca9ca0930cf191256
created_at: '2026-10-30T11:37:33.513150+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Defect fix
history:
- at: '2026-10-30T11:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/base.py
create_intent:
- tests/charter_offering/test_non_mapping_sidecar_skip.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/offering/base.py
- tests/charter_offering/test_non_mapping_sidecar_skip.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Non-mapping sidecar skip in the base loader, red-first

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `<div>`, `<script>`
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Issue spec-kitty/spec-kitty#6735: an org asset sidecar whose YAML is not a
mapping (e.g. a top-level list `- a`) crashes the asset repository load with
`AttributeError: 'list' object has no attribute 'get'` at
`src/charter/offering/base.py:319` (`item_id = data.get("id")` inside
`_apply_overlay_file`), because the per-file
`except (YAMLError, ValidationError, OSError)` envelope cannot catch it.

Done means:

1. A present-but-non-mapping YAML document is skipped with the usual
   `Skipping invalid <layer> <kind> <file>: <reason>` `UserWarning` in **both**
   the overlay tier (`_apply_overlay_file`, org and project layers) and the
   built-in tier (`_load_built_in_items`, before `_pre_validate` runs) — the
   repository constructs and every valid sibling artifact still loads.
2. A regression test per repository kind (all 11
   `BaseArtifactRepository` subclasses) exists and is green after the fix, and
   was demonstrably red on pre-fix main (red-first, DIRECTIVE_034).
3. Existing malformed-sidecar behavior (invalid YAML, `ValidationError`,
   `OSError`, missing `id`, empty file) is byte-for-byte unchanged.
4. The changelog carries an `[Unreleased]` entry for #6735.

## Context & Constraints

- Spec: `kitty-specs/asset-sidecar-non-mapping-crash-01M66937/spec.md`
  (FR-001 overlay skip, FR-002 built-in skip, FR-003 ratchet on existing
  behavior; NFR-001 single fix site, NFR-002 warning shape stability).
- Plan: `kitty-specs/asset-sidecar-non-mapping-crash-01M66937/plan.md`
  (IC-01 guard, IC-02 per-kind matrix).
- Research: `kitty-specs/asset-sidecar-non-mapping-crash-01M66937/research.md`
  — grounding, root cause, decisions D1-D5 (read it before coding).
- Quickstart repro: `kitty-specs/asset-sidecar-non-mapping-crash-01M66937/quickstart.md`.
- **Fix shape (D2)**: explicit `isinstance(data, Mapping)` guard after the
  `None` early-return, in both load sites, sharing one small helper in
  `src/charter/offering/base.py`. Never widen the `except` tuple. Import
  `Mapping` from `collections.abc` (repository precedent:
  `src/charter/offering/missions/repository.py`).
- **Warning text (D3)**: reason wording
  `expected a YAML mapping, got {type(data).__name__}` inside the existing
  `f"Skipping invalid {layer} {self._kind} {yaml_file.name}: ..."` shape.
  `_charter_pack_collect._parse_skipped_glossary_pack_warning` parses that
  fixed shape — do not invent a second format.
- **Empty file stays absence (D4)**: `data is None` → early return, no warning.
- The 11 repository kinds for the parametrized matrix:
  `AssetRepository`, `DirectiveRepository`, `TacticRepository`,
  `ToolguideRepository`, `GlossaryPackRepository`, `PackSkillRepository`,
  `StyleguideRepository`, `ParadigmRepository`, `ProcedureRepository`,
  `MissionStepContractRepository` (`charter.offering.missions.step_contracts`),
  `MissionTypeProfileRepository` (`charter.activation.mission_type_profile_repository`).
  `AgentProfileRepository`, `MissionTypeRepository` and
  `MissionTemplateRepository` do NOT inherit the base class — out of scope.
- No public API change. No new dependencies. Single fix site
  (DIRECTIVE_024 locality, DIRECTIVE_044 single canonical authority).

## Branch Strategy

- **Strategy**: feature branch `issue-6735-asset-sidecar-non-mapping-crash` off `main`
- **Planning base branch**: `issue-6735-asset-sidecar-non-mapping-crash`
- **Merge target branch**: this WP's changes merge back into the mission
  branch `issue-6735-asset-sidecar-non-mapping-crash`; the mission branch's
  pull request targets `main`, and the operator merges it — never push `main`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first per-kind org-overlay regression tests

- **Purpose**: prove the defect per repository kind through the pre-existing
  entry point (repository construction with `org_dirs`), in the red state,
  before the fix exists.
- **Steps**:
  1. Create `tests/charter_offering/test_non_mapping_sidecar_skip.py` with a
     parametrized test over the 11 kinds. Fixture per kind: a `tmp_path`
     built-in dir with one minimal valid artifact of that kind (so the
     "valid sibling still loads" positive control is on the same fixture),
     and an org dir containing one sidecar file matching the kind's glob whose
     content is a top-level list (`- a\n`).
  2. Assert: construction does not raise; `pytest.warns(UserWarning,
     match="Skipping invalid org .*")` captures the skip; the valid sibling
     artifact is present in the repository.
  3. Add one project-layer case (spec.md User Story 1, scenario 3): the same
     non-mapping sidecar supplied via `project_dir=` on `AssetRepository` (or
     the nearest existing project-layer entry point) is skipped identically
     with a `Skipping invalid project …` warning — the org and project layers
     share `_apply_overlay_layer`, so one case pins the shared seam.
  3. Run `uv run pytest tests/charter_offering/test_non_mapping_sidecar_skip.py -q`
     and record the failure output (the red proof). Commit the red state.
- **Files**: `tests/charter_offering/test_non_mapping_sidecar_skip.py` (new).
- **Parallel?**: No — this is the critical path.
- **Notes**: minimal valid artifact data per kind can be taken from the
  existing per-kind repository tests (e.g.
  `tests/charter_offering/test_base_org_layer.py` for directives/tactics,
  `tests/charter_offering/assets/test_repository.py` for assets). Use
  `pytest.mark.fast` + the module's existing marker conventions
  (`pytestmark = [pytest.mark.fast, pytest.mark.doctrine]` is the charter-offering norm).

### Subtask T002 – Built-in-tier regression tests

- **Purpose**: pin the same semantics in the built-in tier, where six kinds'
  `_pre_validate` hooks read `data` before Pydantic can reject a non-mapping
  document (directive, tactic, toolguide, paradigm, styleguide, procedure).
- **Steps**:
  1. Add a test: `DirectiveRepository` with a built-in dir whose only file is
     a top-level list (`001.directive.yaml` containing `- a`) constructs with a
     `Skipping invalid built-in directive …` warning (crashes pre-fix).
  2. Add a test: `AssetRepository` with a non-mapping built-in asset file is
     skipped with the same warning shape (already true pre-fix via Pydantic —
     this pins the uniform semantics so the guard cannot regress it).
- **Files**: same module as T001.
- **Parallel?**: No.
- **Notes**: the directive case is the red one; the asset case is the
  same-fixture positive control for tier symmetry.

### Subtask T003 – Implement the guard in the base loader

- **Purpose**: make a non-mapping document skip with the usual warning in both
  tiers.
- **Steps**:
  1. In `src/charter/offering/base.py`, add a small module-level (or private
     method) helper that returns the skip reason for a non-mapping document
     (e.g. `expected a YAML mapping, got list`), or a shared
     `_skip_non_mapping(...)` warn-and-skip helper used by both load sites.
  2. In `_apply_overlay_file`: after `if data is None: return`, guard
     `isinstance(data, Mapping)` — **before** `self._pre_validate(data,
     yaml_file)`, not only before `data.get("id")`: six kinds' `_pre_validate`
     reads `data` (via `reject_inline_refs`), so they crash on a non-mapping
     overlay at that earlier line. If not a `Mapping`, emit the usual
     `Skipping invalid {layer_name} {self._kind} {yaml_file.name}: <reason>`
     `UserWarning` (`stacklevel=4`) and return.
  3. In `_load_built_in_items`: same guard after the `None` continue and
     **before** `self._pre_validate(data, yaml_file)` (that is the crash order
     for the six kinds), warning `Skipping invalid built-in {self._kind} …`
     (`stacklevel=3`).
  4. Re-run the module from T001/T002: all green.
- **Files**: `src/charter/offering/base.py`.
- **Parallel?**: No.
- **Notes**: keep the docstrings of both methods accurate (the overlay
  docstring already documents skip semantics — extend it to name the
  non-mapping case). Type hints stay `dict[str, Any]`-compatible; a `Mapping`
  check is narrower than the annotation, no signature changes.

### Subtask T004 – Changelog entry [P]

- **Purpose**: user-facing change (repository loads no longer crash on a
  malformed sidecar).
- **Steps**: add under `[Unreleased]` in `docs/changelog/CHANGELOG.md` a bold
  impact-first lead with `(#6735)`, then before/after, under 1,200 characters.
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Parallel?**: Yes.

### Subtask T005 – Suites and gates

- **Purpose**: no regression, gates green.
- **Steps**:
  1. `uv run pytest tests/charter_offering/test_non_mapping_sidecar_skip.py tests/charter_offering/test_base_org_layer.py -q`
  2. `uv run pytest tests/charter_offering/ -q -m fast` (or the repo's fast
     charter-offering lane if narrower — do NOT run full heavy suites).
  3. `uv run ruff check src/charter/offering/base.py tests/charter_offering/test_non_mapping_sidecar_skip.py`
     and `uv run ruff format --check` on the same files.
  4. `uv run mypy src/charter/offering/base.py` (or the repo's mypy
     invocation for the charter package).
- **Files**: none (verification only).
- **Parallel?**: No (final).

## Test Strategy

- Red-first is mandatory: T001/T002 land as a failing suite on pre-fix main,
  and the red output is recorded in the WP history before T003 starts.
- Every kind gets its own parametrized case (the issue's explicit ask).
- Positive control on the same fixture (valid sibling artifact still loads)
  keeps the skip assertions non-vacuous (tactic
  `acceptance-criteria-non-vacuity`).
- No `xfail`, no skips, no marker games to force green (`NO_FAKE_GREEN`).

## Risks & Mitigations

- Warning-text drift → reuse the exact pinned shape; run the glossary-pack
  skip-parse tests (`tests/charter_offering/test_charter_pack_health_glossary_pack.py`
  and the `_charter_pack_collect` tests) as part of T005.
- Over-broad except masking real bugs → explicit `isinstance` guard only.
- Fixture drift across kinds → one shared factory parametrized per kind.
- Diff-cover ≥90% on changed lines → the new guard lines are exercised by the
  new tests (both tiers, both warning shapes).

## Review Guidance

- Verify the guard is in BOTH load sites and runs BEFORE `_pre_validate` in
  the built-in tier.
- Verify the warning matches
  `Skipping invalid <layer> <kind> <file>: expected a YAML mapping, got <type>`.
- Verify no `except` tuple was widened and `None` handling is untouched.
- Verify the red-first proof: the test module's history should show the
  pre-fix failure output.
- Verify all 11 kinds are in the parametrize list (grep
  `class \w*Repository(BaseArtifactRepository` in `src/` to cross-check).

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
