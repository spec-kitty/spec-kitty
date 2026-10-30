---
work_package_id: WP01
title: 'Failure-text guidance: data, rendering, red-first regression test'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
planning_base_branch: issue-6633-accept-path-conventions-name-overrides
merge_target_branch: issue-6633-accept-path-conventions-name-overrides
branch_strategy: Planning artifacts for this mission were generated on issue-6633-accept-path-conventions-name-overrides. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6633-accept-path-conventions-name-overrides unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-accept-path-conventions-name-overrides-01M66F7N
base_commit: e0ca4a3d5e3c0ef3a3d2a8949df7b5b70359c091
created_at: '2026-10-30T13:24:05.443120+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Implementation
history:
- at: '2026-10-30T13:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/validators/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/validators/paths.py
- tests/agent/test_validators_unit.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Failure-text guidance: data, rendering, red-first regression test

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history <WPID> --note "..."`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks; use language identifiers in code blocks.

---

## Objectives & Success Criteria

- The strict path-convention failure text (`PathValidationResult.format_errors()`) names `project.path_conventions` and `.kittify/config.yaml`, prints a copy-pasteable YAML example listing exactly the missing remappable keys, and names the `.kittify/overrides/missions/<mission-type>/mission.yaml` route for dropping a key with no directory.
- The #3783 contract holds: `--lenient` named, ordered before `mkdir -p`, no unconditional "are required by the active mission" claim; the existing test `test_format_errors_names_lenient_before_mkdir_and_drops_unconditional_claim` passes UNMODIFIED.
- A red-first regression test pins the key names (not a literal snapshot of the whole text).
- No validation semantics change (NFR-002).

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6633. Read it in full before starting.
- Spec: `kitty-specs/accept-path-conventions-name-overrides-01M66F7N/spec.md` (FR-001/FR-002/FR-003, C-001..C-003).
- Plan/research: `plan.md`, `research.md`, `data-model.md` in the same directory.
- The single seam is `format_errors()` — consumed by `PathValidationError.__init__` and `summary_core.evaluate_path_conventions` (which wraps output verbatim). Do not add a second copy of remediation text.
- `ARTIFACT_ROUTED_KEYS` (currently `{"deliverables"}`) is importable from `specify_cli.config.path_conventions`; a missing key in that set must never be suggested for `project.path_conventions` — the #5298 `contracts: none` waiver governs it.
- ADR `docs/adr/3.x/2026-08-28-1-project-path-convention-override-precedes-doctrine.md` documents the override; its Negative consequence names exactly this discoverability cost.
- Mission-type slug: derive from `mission.path.name` (e.g. `.kittify/missions/software-dev` → `software-dev`); when the mission object has no meaningful resolver path (hand-built stubs in tests, neutral org missions), use `None` and render a generic `<mission-type>` placeholder. Never guess.

## Branch Strategy

- **Strategy**: populated by `spec-kitty agent mission finalize-tasks`
- **Planning base branch**: `main`
- **Merge target branch**: `main`

> Do NOT change these manually.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first regression test

- **Purpose**: Pin the fix through the pre-existing entry point before the fix exists (ATDD-First Discipline; DIRECTIVE_034).
- **Steps**: In `tests/agent/test_validators_unit.py`, add a test that builds a mission stub declaring `workspace: src/`, `tests: tests/`, `documentation: docs/` (mirror `_MissionStub`), runs `validate_mission_paths(..., strict=True, feature_dir=...)` against a tmp repo containing only a Go-style root (e.g. `internal/`), catches `PathValidationError`, and asserts on `str(excinfo.value)`:
  - `project.path_conventions` and `.kittify/config.yaml` appear;
  - each missing remappable key name (`workspace`, `tests`, `documentation`) appears in the YAML example;
  - the mission-override route (`.kittify/overrides/missions/` and `mission.yaml`) appears;
  - `--lenient` still appears before `mkdir -p`.
  Add a second scenario where `docs/` exists: the snippet then lists only `workspace` and `tests`. Assert key names, not a verbatim snapshot.
- **Files**: `tests/agent/test_validators_unit.py`
- **Parallel?**: No — first.
- **Notes**: Run it against the un-fixed tree and record the failure (red proof). A `priority:P3` issue needs no `p0_repro` marker.

### Subtask T002 – New result fields

- **Purpose**: Carry the render inputs (data-model.md).
- **Steps**: Add to `PathValidationResult`:
  - `remappable_missing_keys: list[str] = field(default_factory=list)` — missing keys a `project.path_conventions` override could remap;
  - `mission_type: str | None = None` — mission-type slug for the override path.
  Document both fields with the #6633 rationale, matching the existing field-docstring style.
- **Files**: `src/specify_cli/validators/paths.py`

### Subtask T003 – Populate the fields in validate_mission_paths

- **Purpose**: The validator knows which keys are missing and remappable, and the mission type.
- **Steps**: At the point a missing path is recorded, append `key` to `remappable_missing_keys` when `key not in ARTIFACT_ROUTED_KEYS`. Derive `mission_type` once from `getattr(mission, "path", None)` — use its `.name` only when the path is a `Path`; store `None` otherwise. Set both on the `PathValidationResult`.
- **Files**: `src/specify_cli/validators/paths.py`
- **Notes**: Research missions with `path_prefix` still work — the fields are render inputs only.

### Subtask T004 – Render the guidance in format_errors

- **Purpose**: The operator reads the honest routes at the moment of blockage.
- **Steps**: In `format_errors()`, after the existing `--lenient` sentence and before `Required Actions:`, append (each gated on non-empty inputs):
  1. When `remappable_missing_keys` is non-empty: a block naming `project.path_conventions` in `.kittify/config.yaml` with a copy-pasteable YAML snippet listing exactly those keys, one `key: <directory>` line each, plus a pointer to the ADR.
  2. A line naming `.kittify/overrides/missions/<mission_type>/mission.yaml` (with the real slug when `mission_type` is set, the literal `<mission-type>` placeholder otherwise) as the route for dropping a key the project has no directory for.
  Keep the addition bounded (~10 lines of output; NFR-001).
- **Files**: `src/specify_cli/validators/paths.py`
- **Notes**: Both the suggestions branch and the no-suggestions branch of the current text keep working; the guidance belongs to the shared tail so it prints in both.

### Subtask T005 – Verify

- **Steps**: `uv run pytest tests/agent/test_validators_unit.py -q`; `uv run pytest tests/specify_cli/acceptance/test_path_conventions_all_types.py -q` (remap semantics untouched); `uv run ruff check src/specify_cli/validators/paths.py tests/agent/test_validators_unit.py`; `uv run mypy src/specify_cli/validators/paths.py` (matching CI's configured invocation). No full heavy suites (NO_FULL_HEAVY_SUITES_IN_MISSION).

## Test Strategy

- The regression test (T001) is the deliverable's proof; run it red before the fix, green after.
- Existing contract tests in the same file must pass unmodified — if one fails, the change broke a contract, do not edit the test.

## Risks & Mitigations

- Degraded rendering for hand-built results → default-empty fields, non-empty gates.
- Overlong output → bounded blocks, one line per missing key only.

## Review Guidance

- Confirm the printed example lists exactly the missing remappable keys (partial-missing scenario).
- Confirm `deliverables` is never suggested and the #3730 test is untouched.
- Confirm no semantics change: `is_valid`, waiver handling, artifact routing untouched.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
