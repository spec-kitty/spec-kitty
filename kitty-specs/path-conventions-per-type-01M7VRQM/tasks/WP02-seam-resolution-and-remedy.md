---
work_package_id: WP02
title: Per-type resolution, waiver effect and remedy text at the accept seam
dependencies:
- WP01
- WP03
requirement_refs:
- FR-002
- FR-006
- FR-007
- FR-008
- FR-012
- C-001
- C-003
- C-004
- SC-001
- SC-002
- SC-003
- NFR-003
planning_base_branch: issue-7566-path-conventions-per-type
merge_target_branch: issue-7566-path-conventions-per-type
branch_strategy: Planning artifacts for this mission were generated on issue-7566-path-conventions-per-type. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7566-path-conventions-per-type unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-path-conventions-per-type-01M7VRQM
base_commit: 86642e498f02cb60112c0fa24b7305f8289b7895
created_at: '2026-11-20T09:12:24.903153+00:00'
subtasks:
- T010
- T011
- T012
- T013
- T014
phase: Phase 2 - Behaviour
history:
- at: '2026-11-20T07:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/acceptance/summary_core.py
create_intent:
- tests/specify_cli/acceptance/test_path_conventions_per_type.py
execution_mode: code_change
owned_files:
- src/specify_cli/acceptance/summary_core.py
- src/specify_cli/validators/paths.py
- tests/agent/test_validators_unit.py
- tests/specify_cli/acceptance/test_path_conventions_all_types.py
- tests/specify_cli/acceptance/test_acceptance_support.py
- tests/specify_cli/acceptance/test_path_conventions_per_type.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Per-type resolution, waiver effect and remedy text at the accept seam

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Record status moves as `claude::python-pedro` (no model name).

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log; address all feedback before completion.

## Markdown Formatting

Wrap HTML/XML tags in backticks; use language identifiers in code blocks.

## Objectives & Success Criteria

- `evaluate_path_conventions` (the single caller of `validate_mission_paths`, C-001) resolves overrides for the Mission's own type: per-type, then flat, then the mission default (FR-002, contract `contracts/precedence-contract.md`).
- It honours both waivers: a per-run reason argument (wired by WP04) and the `meta.json` declaration (WP03 reader). Path misses become the warning text, and metadata strictness is untouched (FR-009 effect, FR-010, C-006).
- The failure text leads with the per-type remap snippet for the failing type (FR-006). It offers no `mkdir -p` for remappable keys (FR-007), names `contracts: none` beside the `contracts/` mkdir (FR-007), demotes the mission.yaml copy to a last resort that freezes the definition (FR-008), and names the narrow waivers before `--lenient` (FR-012).
- SC-001: in an open-packs-shaped fixture, software-dev accepts through `software-dev.workspace: packs/`, while research and documentation keep their defaults.

## Context & Constraints

- Spec: FR-002, FR-006 to FR-008, FR-010, FR-012, C-001, C-003, C-004, SC-001, SC-003, SC-004. Research R-3, R-4, R-5.
- WP01 provides `ProjectPathConventions.for_mission_type(type_id)`. WP03 provides `read_path_conventions_waiver_from_meta`.
- The Mission's type: `get_mission_type(feature_dir) or MISSION_TYPE_SOFTWARE_DEV`, the same expression `specify_cli.mission.get_mission_for_feature` uses (R-3). Import from `specify_cli.mission`.
- `validate_mission_paths` gains an optional `mission_type: str | None = None` keyword. When given, it is the `PathValidationResult.mission_type`; otherwise keep `_mission_type_slug(mission)`.
- Pins to update **deliberately**, never loosened. Write the reason in each test docstring:
  - `tests/agent/test_validators_unit.py::test_strict_failure_names_project_path_conventions_and_drop_route` (the per-type snippet now; the override path is still named, as a last resort);
  - `::test_strict_failure_keeps_mkdir_for_artifact_path_after_lenient_and_remap` (the new order: remap < waiver < `--lenient` < mkdir);
  - `::test_lenient_warning_names_remap_and_drops_mkdir_for_build_paths`;
  - `::test_format_errors_names_lenient_before_mkdir_and_drops_unconditional_claim` must still pass as written;
  - `tests/specify_cli/acceptance/test_acceptance_support.py::test_no_override_still_blocks_strict` (full-text payload).
- C901 ≤ 15. `_remap_guidance_lines` / `format_errors` will grow, so split them into small line-builders.

## Branch Strategy

- **Planning base branch**: `issue-7566-path-conventions-per-type`
- **Merge target branch**: `issue-7566-path-conventions-per-type`
- Implement with `spec-kitty agent action implement WP02 --agent claude --mission path-conventions-per-type-01M7VRQM`.

## Subtasks & Detailed Guidance

### Subtask T010 – Red-first seam tests and the open-packs fixture

New file `tests/specify_cli/acceptance/test_path_conventions_per_type.py`, driving `summary_core.evaluate_path_conventions` with real packaged missions (`get_mission_by_name` or the helpers `test_path_conventions_all_types.py` already uses; mirror them).

Fixture (tmp_path), shaped like spec-kitty-open-packs:
- `packs/`, `docs/`, `scripts/` present; **no** `src/`, `tests/`, `research/`;
- `.kittify/config.yaml`:

  ```yaml
  project:
    path_conventions:
      software-dev:
        workspace: packs/
        tests: packs/
  ```
- One Mission directory per built-in type with a `meta.json` carrying `mission_type`.

Tests:
1. software-dev, strict (`strict_metadata=True`): no path violation for `workspace`/`tests` (the remaining artifact `contracts/` either exists in the Mission dir or is waived with `contracts: none` in the fixture, so the result is fully clean).
2. documentation, strict: `workspace` and `documentation` resolve to `docs/` (present) → clean. Prove it is not remapped: put a sentinel where `packs/` is the only satisfier for a key the documentation Mission declares, e.g. remove `docs/` in a variant test and assert the violation names `docs/`, not `packs/`.
3. research, strict: `workspace` still names `research/` under the deliverables prefix, never `packs/`.
4. Flat plus per-type: flat `workspace: apps/` (`apps/` present) and per-type `software-dev.workspace: packs/` → software-dev checks `packs/`, documentation checks `apps/`.
5. Non-fakeable: per-type `workspace: packs/` with `packs/` absent → strict blocks, naming `packs/`.
6. `meta.json` waiver (`path_conventions: waived` + rationale) with `src/` missing and no override → no violations; the returned warning contains the misses and the rationale notice.
7. A malformed `meta.json` waiver → violations still present, and the text contains the waiver warning.
8. The per-run reason argument (`path_conventions_waiver_reason="layout migration"`) → no violations; the warning contains the reason notice. With `strict_metadata=True` it is unchanged elsewhere (the function does not touch metadata; assert only the path outcome here; WP04 covers metadata end to end).
9. NFR-001: patch `load_project_path_conventions` with a spy and assert one call per evaluation.

Confirm red.

### Subtask T011 – Per-type resolution

In `evaluate_path_conventions`:

```python
mission_type = get_mission_type(feature_dir) or MISSION_TYPE_SOFTWARE_DEV
conventions = load_project_path_conventions(repo_root)
path_overrides = conventions.for_mission_type(mission_type) if isinstance(conventions, ProjectPathConventions) else dict(conventions)
```

The `isinstance` keeps the existing spy test (`patch(..., return_value={})`) working. Pass `mission_type=mission_type` to `validate_mission_paths`. Do not add a second caller.

### Subtask T012 – Waiver effect

- `evaluate_path_conventions(..., path_conventions_waiver_reason: str | None = None)`.
- Read `read_path_conventions_waiver_from_meta(planning_read_dir)` only when the result has misses (keeps the common clean path cheap), mirroring `_contracts_waiver_effect`. Put this in a helper `_path_conventions_waiver_effect(...) -> tuple[bool, str | None]` returning (waived, notice-or-warning).
- Advisory when `not strict_metadata`, or the per-run reason is set, or the meta waiver is well-formed.
- Notices (constants, S1192):
  - `path conventions waived for this run (--waive-path-conventions): <reason>`
  - `path conventions waived by meta.json (path_conventions: waived): <rationale>`
- A malformed meta waiver's warning is attached to the blocking text via `_with_notice`, like the contracts waiver.
- Combine with the existing contracts notice; both may appear. Keep the return contract `(violations, warning, dedup_tokens)`.

### Subtask T013 – Remedy text

Target strict text for a software-dev Mission missing `src/`, `tests/` and the `contracts/` artifact:

```text
Path Convention Errors:
  - Software Dev Kitty expects workspace path: src/ (not found)
  - Software Dev Kitty expects tests path: tests/ (not found)
  - Software Dev Kitty expects deliverables path: kitty-specs/010-mission/contracts/ (not found)

If this project's real layout differs, remap these paths for software-dev Missions in `.kittify/config.yaml` (other mission types keep their own conventions; see ADR project-path-convention-override-precedes-doctrine):

  project:
    path_conventions:
      software-dev:
        workspace: <real-directory>/  # where this project keeps its workspace
        tests: <real-directory>/  # where this project keeps its tests

To accept this Mission without the path check while keeping metadata validation strict:
  - for this run: `accept --waive-path-conventions --waive-reason "<why>"`
  - for every run: set "path_conventions": "waived" and a "path_conventions_rationale" in the Mission's meta.json
`accept --lenient` also turns these into warnings, but skips strict metadata validation too.

Last resort: copying the packaged mission.yaml to `.kittify/overrides/missions/software-dev/mission.yaml` and deleting a key drops it, but freezes that mission definition at this CLI version.

Required Actions:
  - mkdir -p kitty-specs/010-mission/contracts/
  - or, if this Mission defines no interfaces, declare "contracts": "none" with a "contracts_rationale" in its meta.json
```

Rules:
- The remap block and the last-resort line appear only when `remappable_missing_keys` is non-empty (unchanged condition, so `test_artifact_routed_missing_key_gets_no_path_conventions_hint` keeps passing). An unknown type renders `<mission-type>:`.
- The waiver and `--lenient` block always appears in `format_errors`. It replaces the old "Run `accept --lenient` ..." sentence. Keep the substring `--lenient`, and keep it before any `mkdir -p` (#3783).
- The `contracts: none` line appears only when `"contracts"` is in `missing_artifact_tokens`. `result.suggestions` itself is unchanged (the pins on it stay).
- `format_warnings` (the advisory text): the warnings, then the remap block and last-resort line (when remappable), then the suggestions plus the contracts line. **No** waiver or `--lenient` lines (the operator already waived).
- Mark the copy route as a last resort only. Do not present it as an equal alternative.

### Subtask T014 – Pins and verification

Update the pins listed above, adding a docstring note citing #7566 and the new order. Then run:

```bash
uv run --frozen pytest -q tests/agent/test_validators_unit.py tests/specify_cli/acceptance/ tests/specify_cli/config/test_path_conventions_reader.py tests/specify_cli/test_validate_mission_paths_single_caller.py tests/architectural/test_lifted_root_validate_mission_paths_single_caller.py tests/specify_cli/test_org_mission_type_resolution.py
uv run --frozen ruff check <touched>; uv run --frozen ruff format --check --force-exclude <touched>; uv run --frozen mypy src/specify_cli/acceptance/summary_core.py src/specify_cli/validators/paths.py
```

## Test Strategy

Red-first seam tests with real packaged missions and an on-disk fixture; unit tests for the text; deliberate pin updates.

## Risks & Mitigations

- `get_mission_type(feature_dir)` and the Mission's resolved type disagree. Both read `meta.json` the same way, and a typed-but-unresolvable type already raises earlier.
- Text growth pushes C901. Split the builders.

## Review Guidance

- The precedence matches `contracts/precedence-contract.md` exactly.
- Grep the diff: no `mkdir -p` for a remappable key; `--lenient` index < `mkdir -p` index; the remap snippet index < the waiver index < the `--lenient` index.
- `validate_mission_paths` still has exactly one production caller.

## Progress & Status

`spec-kitty agent tasks mark-status T010 T011 T012 T013 T014 --status done --mission path-conventions-per-type-01M7VRQM`.
