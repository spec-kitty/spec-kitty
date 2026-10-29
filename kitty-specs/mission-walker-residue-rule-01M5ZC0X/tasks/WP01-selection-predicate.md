---
work_package_id: WP01
title: Read-side predicate and Mission selection
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-008
- NFR-001
- C-001
- C-002
- C-003
- C-005
- NFR-003
planning_base_branch: issue-5875-mission-walker-is-mission-dir
merge_target_branch: issue-5875-mission-walker-is-mission-dir
branch_strategy: Planning artifacts for this mission were generated on issue-5875-mission-walker-is-mission-dir. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5875-mission-walker-is-mission-dir unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Selection
history:
- at: '2026-10-27T19:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/context/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/context/mission_resolver.py
- src/specify_cli/cli/commands/agent/mission_feature_resolution.py
- tests/specify_cli/context/test_mission_selection.py
- tests/specify_cli/cli/commands/agent/test_mission_feature_resolution.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Read-side predicate and Mission selection

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Selection lists a `kitty-specs/` child only when **a `meta.json` exists on disk AND `is_mission_dir` accepts it** (operator ruling 2026-10-27, decisions D1/D2 in `../research.md` §4). The agent-side candidate lister agrees exactly.

Done when:
- In a git repo, a spec.md-only folder (tracked or untracked) is **not** listed by `list_missions_for_selection`, `sole_mission_for_selection` or `_list_feature_spec_candidates`.
- A folder whose `meta.json` carries a `mission_id` is listed (committed or not), with **no git subprocess** when every listed child has an identity (NFR-001).
- A tracked legacy `meta.json` without a `mission_id` is listed. An untracked one without a `mission_id` is not.
- On a non-git root, a `meta.json` with no id is listed (existence fallback).

## Context & Constraints

- Read `../spec.md`, `../plan.md` ("Predicate design") and `../research.md`.
- `is_mission_dir`, `_carries_identity`, `probe_tracked_mission_paths`, `tracked_mission_paths` and `_UNSET`/`_Unset` already exist in `src/specify_cli/context/mission_resolver.py`. Reuse them.
- **Do NOT change** `is_kitty_specs_residue`, `RESIDUE_NOTICE`, `residue_notice`, `residue_notice_path` or `_build_index`/`_index_entry` (C-002). The index already requires an identity.
- No new command or migration (C-001). Complexity ≤ 15, no new `noqa`/`type: ignore`. ruff, `ruff format --check --force-exclude` and mypy must be clean on touched files.
- Terminology: "Mission", never "feature", in new text.

## Branch Strategy

Planning branch `issue-5875-mission-walker-is-mission-dir`, final merge target the same branch. The topology is `single_branch`, so you work in the repository root checkout. There is no lane worktree. Commit with `git commit` on that branch (end every commit message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Never push.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first selection tests

In `tests/specify_cli/context/test_mission_selection.py`:
- The existing fixture puts `003-legacy` (spec.md only) in the listing, and tests like `test_lists_three_including_legacy_in_slug_order` and `test_legacy_spec_only_mission_has_none_mid8_and_slug_fallback` pin the OLD rule. Rewrite them to pin the NEW rule: spec.md-only is excluded. Keep a test that a `meta.json` without a `mission_id` is listed **when git tracks it, or on a non-git root**.
- Note that `tmp_path` fixtures are non-git roots, so existence fallback applies there. Add git-repo cases (`git init`, `git add`, `git commit` with `-c user.name=t -c user.email=t@t`, following `tests/context/test_is_mission_dir.py`'s `repo` fixture style) for: untracked spec.md-only → excluded; tracked spec.md-only → excluded; untracked meta.json with id → included; untracked meta.json without id → excluded; tracked meta.json without id → included.
- Add an NFR-001 test: monkeypatch `specify_cli.context.mission_resolver.probe_tracked_mission_paths` (or `tracked_mission_paths`) to raise / count calls, and assert **zero** calls when all children carry an identity and **at most one** call when several id-less children exist.
- Run them and confirm they FAIL on the current code before T002/T003. Record that in the Activity Log.

### Subtask T002 – `is_selectable_mission_dir`

Add a public function next to `is_mission_dir`:

```python
def is_selectable_mission_dir(path: Path, *, repo_root: Path, tracked: frozenset[str] | None | _Unset = _UNSET) -> bool:
```

Semantics (plan "Predicate design"):
1. `(path / "meta.json")` is not a file → False.
2. `_carries_identity(path)` → True (no git call).
3. Resolve `tracked` (probe with `probe_tracked_mission_paths(repo_root)` when `_UNSET`).
4. `tracked is None` → True (non-git / unusable git: existence fallback, `meta.json` exists).
5. Else `is_mission_dir(path, repo_root=repo_root, tracked=tracked)`.

Walkers must probe **lazily and at most once per walk**. Add a small private helper, for example a `_LazyTracked` class with a `get()` method that memoizes, or a closure. Pass the result to the predicate only when step 2 does not already decide. Keep the docstring precise. Say why it is stricter than `is_kitty_specs_residue` (a `spec.md` on disk does not make a folder selectable, by operator ruling. The write-seam rule keeps shielding it so upgrade can repair it).

### Subtask T003 – Selection uses it

`list_missions_for_selection`: replace the `spec.md or meta.json exists` test with the predicate (one lazy tracked memo per call). Update its docstring and `sole_mission_for_selection`'s, plus any module-header text that describes the population rule (FR-008: document why the index differs, that is, identity required). `list_missions_for_selection` probes with `probe_tracked_mission_paths`, never `tracked_mission_paths`, so a broken index degrades to file presence instead of crashing selection.

### Subtask T004 – Agent candidates agree

`src/specify_cli/cli/commands/agent/mission_feature_resolution.py::_list_feature_spec_candidates`: use `is_selectable_mission_dir` with one lazy memo, against `main_repo_root` as `repo_root`. Keep the returned dict shape (`spec_exists` stays). Update `tests/specify_cli/cli/commands/agent/test_mission_feature_resolution.py`: the spec.md-only candidate case now expects exclusion. Keep the meta.json-only case included. Red first.

### Subtask T005 – Blast-radius fixtures

Other tests may build spec.md-only "Missions" and expect `next` / `setup-plan` / `agent tasks status` auto-select or listing to see them. Find them:
`grep -rln "spec.md" tests/ | xargs grep -ln "sole_mission\|list_missions_for_selection\|_list_feature_spec_candidates\|setup-plan\|setup_plan\|tasks status\|next_cmd"`
and run the obvious candidates: `tests/specify_cli/cli/commands/test_next_owned_fact.py`, `tests/integration/test_owned_lifecycle_acceptance_next.py`, `tests/integration/test_colliding_mission_flow.py`, `tests/specify_cli/cli/commands/agent/test_mission_setup_plan_phases.py`, `tests/specify_cli/cli/commands/migrate/` (backfill-wp-status `known_mission_slugs`), and `tests/cli`. Where a fixture means "a real Mission", give it a `meta.json` with a `mission_id`. Do not weaken an assertion. Record each such edit outside the owned files as a one-line rationale in the Activity Log.

## Test Strategy

Red first (T001, T004). Then run: `uv run --frozen pytest tests/specify_cli/context tests/context tests/specify_cli/cli/commands/agent -q` plus the T005 files, and `make test-fast`. Record commands and counts in the Activity Log.

## Risks & Mitigations

- Hidden fixture dependence (T005). Mitigation: grep plus targeted runs.
- A broken git index in selection. Mitigation: `probe_tracked_mission_paths` (it degrades with a warning).

## Review Guidance

Reviewer: check the predicate order (identity before any git call), the single lazy probe, that the write-seam functions are untouched, that the docstrings explain the difference, and that no assertion was weakened in T005 edits.

## Activity Log

- 2026-10-27T19:20:00Z – system – Prompt created.
- 2026-10-27T21:30:00Z – claude (python-pedro) – T001/T004 red first: 15 new/rewritten tests failed on the base (commit b9bebcf3), e.g. test_git_tracked_spec_only_is_excluded, test_at_most_one_probe_for_several_idless_children, test_list_candidates_excludes_spec_only_folder, test_candidates_probe_git_at_most_once.
- 2026-10-27T21:30:00Z – claude (python-pedro) – T002–T004 in c46ad0f8: is_selectable_mission_dir + LazyTrackedMissionPaths (memo object passed as tracked=), wired into list_missions_for_selection and _list_feature_spec_candidates. Write-seam functions and the index untouched.
- 2026-10-27T21:30:00Z – claude (python-pedro) – T005 out-of-map fixture edits (spec.md-only fixtures meant real Missions, so they now get a meta.json with a mission_id; no assertion changed): tests/agent/test_agent_feature.py (2 ambiguous-remediation tests), tests/specify_cli/cli/commands/agent/test_mission_cli_golden_contract.py (setup-plan envelope), tests/specify_cli/cli/commands/agent/test_mission_handle_not_found.py (_make_mission).
- 2026-10-27T21:30:00Z – claude (python-pedro) – Tests: `pytest tests/specify_cli/context tests/context tests/specify_cli/cli/commands/agent` 2995 passed / 3 failed before the fixture fixes (the 3 fixed above, re-run 29 passed); blast radius (grep list + next_owned_fact, owned_lifecycle_acceptance_next, colliding_mission_flow, migrate_backfill_*, tests/cli) 1700 passed / 3 failed (2 fixed above, 2 passed on re-run; tests/architectural/test_archive_root_byte_identical.py red on the base too, pre-existing); `make test-fast` 2476 passed, 6 skipped.
