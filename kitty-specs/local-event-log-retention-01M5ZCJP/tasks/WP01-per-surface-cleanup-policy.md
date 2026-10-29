---
work_package_id: WP01
title: Per-surface cleanup policy (#5212)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-013
- SC-001
planning_base_branch: issue-6610-local-event-log-retention
merge_target_branch: issue-6610-local-event-log-retention
branch_strategy: Planning artifacts for this mission were generated on issue-6610-local-event-log-retention. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6610-local-event-log-retention unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-local-event-log-retention-01M5ZCJP
base_commit: c4dc933920e9aa82a8f113c9184e060b1c130d05
created_at: '2026-10-27T19:29:07.635320+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Foundation
history:
- at: '2026-10-27T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/state/
create_intent:
- tests/core/test_state_cleanup_policy.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/state/contract.py
- tests/core/test_state_cleanup_policy.py
- tests/specify_cli/test_state_contract.py
- tests/specify_cli/test_state_doctor.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Per-surface cleanup policy (#5212)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

Every entry of the state registry `STATE_SURFACES` (`src/specify_cli/state/contract.py`) declares a **required** cleanup policy: a retention rule and the command that cleans it (or none). The serialized form (`StateSurface.to_dict()`) carries it. Invariant tests make the committed tier unprunable by construction.

Done when:
- `RetentionRule` (StrEnum) and `CleanupPolicy` (frozen dataclass) exist in `contract.py`, exported from the module's public surface the same way `AuthorityClass` / `GitClass` are.
- `StateSurface.cleanup_policy` is keyword-only with **no default**; constructing a `StateSurface` without it raises `TypeError` (FR-002).
- All 62 surfaces carry a policy; `to_dict()` includes `"cleanup_policy": {"retention": ..., "cleanup_command": ...}` (FR-001).
- Invariants (FR-003/FR-004) pass and a self-mutation case proves the tracked-surface invariant is non-vacuous.
- `surfaces_by_retention(rule)` returns the surfaces with that rule (selector for WP02, FR-013).

## Context & Constraints

- Spec: `kitty-specs/local-event-log-retention-01M5ZCJP/spec.md` (FR-001..FR-004, FR-013). Data model: `data-model.md` (rule table + invariants). Research: `research.md` §1, §4, §5.
- Charter: ATDD-first (red commit before implementation), single canonical authority, complexity ≤ 15, no new `noqa` / `type: ignore`.
- `StateSurface` is a frozen dataclass at `contract.py:87-127`; it already has defaulted fields (`deprecated`, `atomic_write`, `notes`, `target_owned`, `ignored_via_agent_block`). A required field after defaulted ones must be `field(kw_only=True)` (Python 3.10+). Every existing constructor call already uses keyword arguments.
- Sibling issues NOT built here (C-005): #5213 (new authority classes), #3970 (postcondition report). Do not touch `AuthorityClass`.
- **Test placement**: `tests/specify_cli/` (root) only runs nightly (`.github/ci-module-registry.yml` `out_of_matrix_test_dirs`). New tests go in `tests/core/` (module `core_misc`, per-PR). Keep edits to the existing nightly files minimal (only what the new key forces).

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-6610-local-event-log-retention`
- **Merge target branch**: `issue-6610-local-event-log-retention`

Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty agent action implement WP01 --agent claude --mission local-event-log-retention-01M5ZCJP`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first ATDD tests

- **Purpose**: pin the user-observable contract before the code exists (charter C-011: separate commit, RED on the base).
- **File**: `tests/core/test_state_cleanup_policy.py` (new). Mark tests `pytest.mark.fast` (check `tests/core/` neighbours for the marker convention).
- **Tests** (each a separate function):
  1. `test_every_surface_declares_a_cleanup_policy` — every `s.cleanup_policy` is a `CleanupPolicy` with a `RetentionRule`.
  2. `test_to_dict_emits_cleanup_policy` — every `s.to_dict()["cleanup_policy"]` equals `{"retention": s.cleanup_policy.retention.value, "cleanup_command": s.cleanup_policy.cleanup_command}` and round-trips through `json.dumps`.
  3. `test_policy_is_required` — `StateSurface(...)` with every other field but no `cleanup_policy` raises `TypeError`.
  4. `test_tracked_surfaces_are_never_prunable` — for every surface with `git_class == GitClass.TRACKED`, the rule is not `LEDGER_RETENTION` and not `REBUILDABLE`.
  5. `test_prunable_surfaces_are_gitignored` — every `LEDGER_RETENTION` / `REBUILDABLE` surface has `git_class == GitClass.IGNORED`.
  6. `test_invariant_rejects_a_prunable_tracked_surface` (self-mutation, non-vacuity): build a copy of `canonical_status_log` with `dataclasses.replace(..., cleanup_policy=CleanupPolicy(RetentionRule.LEDGER_RETENTION, CLEANUP_EVENT_LOGS_COMMAND))` and assert the invariant helper used by test 4 flags it. Factor the predicate into a small test-local function so both tests use it.
  7. `test_local_tier_is_pinned` — `{s.name for s in surfaces_by_retention(LEDGER_RETENTION)} == {"runtime_run_snapshot", "runtime_run_event_log", "runtime_frozen_template", "glossary_fallback_events"}` and `REBUILDABLE` == `{"derived_mission_views", "op_invocation_index"}` (ADR 2026-10-13-2 D-3 local tier).
  8. `test_retention_surfaces_name_the_cleanup_command` — every `LEDGER_RETENTION`/`REBUILDABLE` policy has `cleanup_command == "spec-kitty doctor event-logs --apply"`.
  9. `test_owner_lifecycle_names_a_command` — every `OWNER_LIFECYCLE` policy has a non-empty `cleanup_command`.
  10. `test_deprecated_surfaces_are_retired` — `s.deprecated` ⇔ rule is `RETIRED`.
- Commit these alone: `test(state): pin the per-surface cleanup policy contract (#5212)`. Confirm they fail (ImportError/AttributeError is an acceptable RED for a new symbol).

### Subtask T002 – Types and the required field

- In `contract.py`, after `StateFormat`:
  ```python
  class RetentionRule(StrEnum):
      """How a state surface is retained and who removes it (#5212)."""
      NEVER = "never"
      LEDGER_RETENTION = "ledger_retention"
      REBUILDABLE = "rebuildable"
      OWNER_LIFECYCLE = "owner_lifecycle"
      MANUAL = "manual"
      RETIRED = "retired"

  CLEANUP_EVENT_LOGS_COMMAND = "spec-kitty doctor event-logs --apply"

  @dataclass(frozen=True)
  class CleanupPolicy:
      retention: RetentionRule
      cleanup_command: str | None = None
      def to_dict(self) -> dict[str, Any]: ...
  ```
  Give each enum value a one-line meaning in the class docstring (mirror `data-model.md`). The module constant avoids repeating the command string ≥3 times (Sonar S1192).
- `StateSurface`: add `cleanup_policy: CleanupPolicy = field(kw_only=True)` (import `field`). Document it in the class docstring. Add `"cleanup_policy": self.cleanup_policy.to_dict()` to `to_dict()`.
- Check whether `contract.py` declares `__all__`; if it does, add the new names.

### Subtask T003 – Classify all 62 surfaces

Add `cleanup_policy=CleanupPolicy(...)` to every `StateSurface(...)` in `STATE_SURFACES`. Guidance (verify each owner command exists with `grep`/`spec-kitty --help`; if a named command does not exist, use `MANUAL` with `None` rather than inventing one):

| Rule | Surfaces |
|---|---|
| `NEVER` | every `tracked` surface (project_config, project_metadata, migration_ledger, migration_state_ledger, op_invocation_record, all charter_* tracked rows, project_pack_graph, feature_metadata, canonical_status_log, canonical_status_snapshot, wp_prompt_frontmatter, wp_activity_log, tasks_status_block); `review_feedback_artifact` (git-internal review record); the non-deprecated global authoritative/secret rows (sync_config, sync_credentials, tracker_cache); lock-file surfaces (runtime_update_lock) — a lock is never unlinked (kernel/locks.py G3) |
| `LEDGER_RETENTION` + `CLEANUP_EVENT_LOGS_COMMAND` | runtime_run_snapshot, runtime_run_event_log, runtime_frozen_template, glossary_fallback_events |
| `REBUILDABLE` + `CLEANUP_EVENT_LOGS_COMMAND` | derived_mission_views, op_invocation_index |
| `OWNER_LIFECYCLE` + command | workspace_context (`spec-kitty context cleanup`), merge_resume_state (`spec-kitty consolidate --abort`), worktrees_root (`spec-kitty consolidate`), runtime_feature_index (`CLEANUP_EVENT_LOGS_COMMAND` — it drops a deleted run's entry; the file itself is never deleted), skills_install_manifest / shared_skills_projection (`spec-kitty upgrade` or `spec-kitty agent config sync` — verify), runtime_version_stamp / runtime_staging_dirs (`spec-kitty upgrade` — verify) |
| `MANUAL` | the remaining ignored local surfaces with no owning cleanup (charter_lint_report, sync_local_commit_state, encoding_provenance_global_log, legacy_migration_scratch, runtime_agent_logs, mission_pycache, dossier_snapshot, dossier_parity_baseline, charter_context_state) |
| `RETIRED` | every `deprecated=True` row |

Where the choice is a judgment call, add a short `notes` addition only if it prevents a real misreading; do not rewrite existing notes.

### Subtask T004 – Selector and existing tests

- Add `surfaces_by_retention(rule: RetentionRule) -> list[StateSurface]` beside the existing query helpers near the end of `contract.py` (mirror `get_surfaces_by_authority`'s naming and shape — if the existing helpers are named `get_surfaces_by_*`, name it `get_surfaces_by_retention` for consistency and update the test/plan wording accordingly).
- Run `tests/specify_cli/test_state_contract.py` and `tests/specify_cli/test_state_doctor.py`; if any asserts the exact `to_dict()` key set or the JSON of `spec-kitty doctor state-roots --json`, extend the expectation with `cleanup_policy` (an additive key). This is adding coverage for a new key, not changing an asserted behaviour; record it in the commit message.
- `grep -rn "to_dict()" src/specify_cli/state/ src/specify_cli/cli/commands/doctor*.py` to find serializers that consume surfaces and confirm nothing breaks on the new key.

## Test Strategy

```bash
uv run --frozen pytest tests/core/test_state_cleanup_policy.py -q
uv run --frozen pytest tests/specify_cli/test_state_contract.py tests/specify_cli/test_state_doctor.py tests/specify_cli/test_gitignore_contract.py -q
uv run --frozen pytest tests/architectural/test_lifted_root_gitignore_contract.py tests/architectural/test_charter_pack_path_authority.py tests/architectural/test_lifted_state.py -q
uv run --frozen ruff check src/specify_cli/state/contract.py tests/core/test_state_cleanup_policy.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/state/contract.py tests/core/test_state_cleanup_policy.py
uv run --frozen mypy src/specify_cli/state/contract.py
```

## Risks & Mitigations

- Misclassifying a surface: the invariants (tracked ⇒ not prunable, prunable ⇒ ignored, pinned local tier) catch the dangerous direction. A wrong `MANUAL` vs `OWNER_LIFECYCLE` is harmless to data.
- Exact-key assertions elsewhere on `to_dict()`: grep and extend.

## Review Guidance

- RED commit precedes implementation and fails on the base.
- The self-mutation test really fails the invariant (not a tautology).
- No surface uses a command that does not exist.
- `mypy` clean; complexity unchanged.

## Progress & Status

Record notes with `spec-kitty agent tasks add-history WP01 --note "..."`; mark subtasks with `spec-kitty agent tasks mark-status T001 --status done`.
