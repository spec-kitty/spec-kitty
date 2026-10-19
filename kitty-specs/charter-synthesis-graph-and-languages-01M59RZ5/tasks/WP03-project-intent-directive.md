---
work_package_id: "WP03"
subtasks:
  - "T011"
  - "T012"
  - "T013"
  - "T014"
  - "T015"
title: "Project-intent directive: rename, dead edge, migration"
task_type: "implement"
phase: "Phase 2 - Synthesis graph"
execution_mode: "code_change"
dependencies: ["WP02"]
requirement_refs: ["FR-006", "FR-007", "FR-008", "FR-019", "SC-003"]
owned_files:
  - "src/charter/activation/synthesizer/targets.py"
  - "src/charter/activation/synthesizer/interview_mapping.py"
  - "src/charter/activation/synthesizer/reconcile.py"
  - "src/charter/activation/synthesizer/legacy_rename.py"
  - "src/charter/activation/api.py"
  - "src/specify_cli/cli/commands/charter/synthesize.py"
  - "src/specify_cli/cli/commands/charter/resynthesize.py"
  - "src/specify_cli/upgrade/migrations/m_4_0_0rc8_project_intent_directive_rename.py"
  - "src/specify_cli/upgrade/migrations/order_manifest.txt"
  - "tests/charter/synthesizer/test_legacy_rename.py"
  - "tests/charter/synthesizer/test_project_intent_directive.py"
  - "tests/charter/synthesizer/test_interview_mapping.py"
  - "tests/specify_cli/upgrade/migrations/test_m_4_0_0rc8_project_intent_directive_rename.py"
  - "tests/charter/fixtures/synthesizer/directive/**"
  - "docs/adr/3.x/2026-04-19-6-harness-owned-generated-artifact-charter-handoff.md"
authoritative_surface: "src/charter/activation/synthesizer/"
create_intent:
  - "src/charter/activation/synthesizer/legacy_rename.py"
  - "src/specify_cli/upgrade/migrations/m_4_0_0rc8_project_intent_directive_rename.py"
  - "tests/charter/synthesizer/test_legacy_rename.py"
  - "tests/charter/synthesizer/test_project_intent_directive.py"
  - "tests/specify_cli/upgrade/migrations/test_m_4_0_0rc8_project_intent_directive_rename.py"
agent_profile: "python-pedro"
role: "implementer"
agent: "claude"
model: "claude-sonnet-5-5"
---

# Work Package Prompt: WP03 – Project-intent directive: rename, dead edge, migration

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## Objective

Rename the always-synthesized directive from `mission-type-scope-directive` to `project-intent-directive`, and give it a project-intent title. Stop emitting, and strip, its dead `requires --> mission_type:*` edge. Converge existing projects through one charter-layer helper that an upgrade migration and synthesize/resynthesize both call (FR-006..FR-008).

## Context

- Read `spec.md` (User Story 2, scenarios 1-4; FR-008 lists every path) and `plan.md` (D-04, D-10).
- The directive's declared id (`PROJECT_00N`) and its graph URN `directive:PROJECT_00N` do not change. Only slug-keyed files, the overlay node label and stem tokens change.
- The interview section label `mission_type`, its `project_intent` alias and provenance `source_section` are kept.
- What the directive leaves on disk. Inspect this repository's `.kittify/`, and `tests/fixtures/charter_pack_cutover/`, for both shapes:
  - artifact `.kittify/charter-packs/directive/NNN-mission-type-scope-directive.directive.yaml`;
  - harness input `.kittify/charter/generated/directives/NNN-mission-type-scope-directive.directive.yaml` (ADR 2026-04-19-6). If it is missing, the next synthesize raises `GeneratedArtifactMissingError`;
  - provenance `directive-project-001.yaml` (`adapter_id: project-direct-write`; `source_input_ids` and `source_section` hold the old path) or `directive-mission-type-scope-directive.yaml` (`artifact_slug`);
  - synthesis manifest entry (`path`, `slug`, plus `content_hash`, `manifest_hash`, `bundle_content_hash`);
  - overlay `.kittify/charter-packs/graph.yaml` node label and any `requires --> mission_type:*` edge;
  - stem tokens such as `001-mission-type-scope-directive` in the resolved activation write target (`resolve_activation_write_target`).

### Subtask T011: Red-first tests

- **`tests/charter/synthesizer/test_project_intent_directive.py`** (`@pytest.mark.regression`, #6443):
  - a fresh synthesis gives slug `project-intent-directive` and a project-intent title;
  - there is no `requires --> mission_type:*` edge, even when the answer names a shipped mission type such as `software-dev`;
  - reconcile strips such an edge from an existing overlay and reports it.
- **`tests/charter/synthesizer/test_legacy_rename.py`:** covers both provenance shapes, and checks for each:
  - every path in FR-008 moved, with the artifact body unchanged;
  - the manifest hashes are valid (`finalize_manifest`) and the bundle is restamped;
  - stem tokens are rewritten;
  - the id and URN are unchanged;
  - a second run is a no-op;
  - a target collision is refused with nothing changed;
  - synthesize after rename works (no `GeneratedArtifactMissingError`).
- **`tests/specify_cli/upgrade/migrations/test_m_4_0_0rc8_project_intent_directive_rename.py`:**
  - `detect` is true on legacy and false after;
  - `apply` delegates to the helper;
  - dry-run writes nothing;
  - the ledger records success.
- Confirm each fails before the fix.

### Subtask T012: Synthesis side (FR-006, FR-007)

- **`targets.py`:** slug `project-intent-directive` (around line 101), and an explicit "Project Intent Directive" title instead of the generic fallback.
- **Delete the mission-type edge source and its now-unused helpers:** `_mission_type_evidence_urns` and its call (`targets.py` around lines 193-279), `interview_mapping.mission_type_urn_candidate` and `_MISSION_TYPE_URN_BY_NORMALIZED_ID`. Keep `_MISSION_IDENTIFIER_ANSWERS`, which the answer preference uses.
- **`reconcile.py`:** add a predicate for `directive:PROJECT_* --requires--> mission_type:*` overlay edges whose source is a synthesized directive. Strip and report such edges through the same notice path as legacy `applies` edges.

### Subtask T013: Rename helper (FR-008)

- New `src/charter/activation/synthesizer/legacy_rename.py`: `rename_legacy_project_intent_directive(repo_root: Path, *, dry_run: bool = False) -> RenameReport`, exported from `charter.activation.api`.
- **Phase 1: preflight, no writes.**
  - Locate the legacy files.
  - Compute the targets through `artifact_naming.artifact_filename`.
  - Refuse if any target exists, or if a manifest slug collides.
- **Phase 2: the moves**, using atomic writes:
  - move the artifact file and the generated input;
  - rewrite the manifest `path`/`slug` and recompute hashes through `finalize_manifest`;
  - move and rewrite the provenance;
  - set the overlay label and drop the dead edge;
  - rewrite stem tokens in the activation write target;
  - then restamp the bundle hash once.
- **Fail closed:** an unreadable input refuses with a clear message.
- **Complexity** ≤ 15 per function; extract a step per file kind.
- **Callers:** call it at the start of `cli/commands/charter/synthesize.py` and `resynthesize.py`, before any write, and surface its report or refusal.

### Subtask T014: Migration

- `src/specify_cli/upgrade/migrations/m_4_0_0rc8_project_intent_directive_rename.py`:
  - `migration_id = "4.0.0rc8_project_intent_directive_rename"`, `target_version = "4.0.0rc8"`, `clone_local_effect = False`;
  - `detect` finds legacy slug-keyed files;
  - `apply` calls the helper through `charter.activation.api` and honours `dry_run`;
  - a refusal returns `success=False` with the helper's message.
- Append the id to `order_manifest.txt` in execution order (version-monotonic; it is not a tie).
- These must pass: `tests/architectural/test_migration_order_manifest.py` and the registry tests.

### Subtask T015: Pinned tests, fixtures, ADR (FR-019 part)

- Update the tests that pin the old slug; find them with `git grep -l mission-type-scope-directive tests`, about 25 files.
- Re-key the fixture-adapter directive fixtures under `tests/charter/fixtures/synthesizer/directive/` through the documented regeneration path.
- The acceptance cutover golden (`tests/acceptance/charter_pack_cutover/`) changes too. That path is not owned, so ask the orchestrator before editing it.
- Amend ADR `docs/adr/3.x/2026-04-19-6-harness-owned-generated-artifact-charter-handoff.md` with a dated note: the directive slug is renamed, and the helper and migration converge existing projects.

## Definition of Done

- The T011 tests were red before the fix and are green after it, and the markers are converted.
- These pass:
  - `tests/charter/synthesizer/`, `tests/charter/test_default_in_force_snapshot.py`
  - `tests/specify_cli/upgrade/migrations/`
  - `tests/architectural/test_migration_order_manifest.py`, `tests/architectural/test_runtime_charter_activation_boundary.py`, `tests/architectural/test_no_dead_symbols.py`
- ruff, format and `mypy --strict` are clean on changed files.

## Risks

- **Two provenance shapes, and stem tokens in either `config.yaml` or `charter.yaml`.** Test both.
- **Synthesize before upgrade could create a second `PROJECT_00N` file.** The pre-step prevents it, and a test pins that.
- **Editing a shipped migration is forbidden.** This is a new migration.

## Reviewer Guidance

- Walk through the FR-008 path list against the helper.
- Verify a second run is a no-op, and that a collision changes nothing.
- Verify the id and URN are untouched.
