---
work_package_id: WP01
title: doctor coordination acts only on the Missions named (#7552)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-003
- C-003
- C-004
- C-005
- SC-001
- SC-002
planning_base_branch: fix/7549-doctor-scope-lock-hygiene
merge_target_branch: fix/7549-doctor-scope-lock-hygiene
branch_strategy: Planning artifacts for this mission were generated on fix/7549-doctor-scope-lock-hygiene. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7549-doctor-scope-lock-hygiene unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Bug fixes
history:
- at: '2026-11-11T16:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/cli/commands/test_doctor_coordination_scope_7552.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/doctor.py
- src/specify_cli/cli/commands/_coordination_doctor.py
- src/specify_cli/missions/_read_path_resolver.py
- src/specify_cli/cli/commands/decision.py
- src/runtime/next/runtime_bridge.py
- src/specify_cli/coordination/surface_resolver.py
- tests/specify_cli/cli/commands/test_doctor_coordination_scope_7552.py
- tests/specify_cli/cli/commands/test_doctor_coordination.py
- tests/specify_cli/cli/commands/test_coordination_doctor.py
- tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py
- tests/specify_cli/cli/commands/test_doctor_flatten_remote_reverify_4979.py
- tests/specify_cli/cli/commands/test_coordination_remedy_5113.py
- tests/architectural/test_mission_resolver_walker_gate.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – doctor coordination acts only on the Missions named (#7552)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according
to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: check the `review_ref` field in the event log (`spec-kitty agent tasks status`).
- Address every feedback item; record progress with `spec-kitty agent tasks add-history WP01 --note "..."`.

## Objectives & Success Criteria

- FR-001: `doctor coordination --fix` with neither `--mission` nor `--all-missions` refuses with
  `COORDINATION_FIX_SCOPE_REQUIRED`, exit 1, nothing mutated, message names both options.
- FR-002: `--fix --all-missions` keeps today's repository-wide repair.
- FR-003: `--fix --mission A` reports and repairs only A, including stranded-revert markers.
- FR-004: `--mission` with `--all-missions` refuses with `COORDINATION_FIX_SCOPE_CONFLICT`, exit 1.
- FR-005/FR-006/FR-007: the scan (and `--mission`) find Missions held only by a coordination worktree or only by their own
  Mission branch; a Mission branch contributes only the Mission whose `mission_branch`/`coordination_branch` is that branch.
- SC-001, SC-002.

## Context & Constraints

- Read [plan.md](../plan.md) D-1..D-7 and [research/code-grounding.md](../research/code-grounding.md) §1.
- C-003: without `--fix` nothing is mutated (branch-only discovery is read-only git: `ls-tree`, `cat-file`).
- C-004: `--mission` keeps the canonical selector ladder; ambiguity fails closed.
- Do not touch `src/specify_cli/consolidation/**` (C-002; #7544's run). Remedy strings there that mention
  `doctor coordination --fix` are a recorded residual.

## Branch Strategy

- **Strategy**: single work branch per the computed lane (`lanes.json`).
- **Planning base branch**: `fix/7549-doctor-scope-lock-hygiene` (via the Mission branch)
- **Merge target branch**: `fix/7549-doctor-scope-lock-hygiene`
- Execution workspaces are allocated per computed lane from `lanes.json`; run
  `spec-kitty agent action implement WP01 --agent claude --mission doctor-scope-lock-hygiene-01M75NSF`.

## Subtasks & Detailed Guidance

### T001 – Red tests first (separate commit)

New file `tests/specify_cli/cli/commands/test_doctor_coordination_scope_7552.py`, driving the real `doctor` Typer app
through `CliRunner` against real git repositories in `tmp_path` (reuse fixtures/helpers from
`test_doctor_coordination.py` / `test_coordination_doctor.py` where they exist).

Cases (each must be RED on the planning base):
1. Two Missions A, B each with a `coordination_branch` key whose branch was never created (the `NEVER_CREATED` flatten
   finding). `--fix` alone → exit 1, `COORDINATION_FIX_SCOPE_REQUIRED` in output (JSON mode too), both `meta.json`
   byte-identical.
2. Same fixture, `--fix --mission A` → A flattened, B byte-identical.
3. Same fixture, `--fix --all-missions` → both flattened (positive control for FR-002).
4. `--fix --mission A --all-missions` → exit 1, `COORDINATION_FIX_SCOPE_CONFLICT`, nothing changed.
5. A stranded-revert finding for B (seed a reconcile marker the way existing strand tests do, or monkeypatch
   `_check_stranded_coord_revert` to return a finding with `extra={"mission_id": B_id, ...}`) is not reported under
   `--mission A`, and `_heal_one_strand` is not called for it under `--fix --mission A`.
6. Branch-only Mission: create Mission C's directory + `meta.json` (with `mission_branch` and `coordination_branch`
   both `kitty/mission-c-<mid8>`) committed ONLY on branch `kitty/mission-c-<mid8>`; root checkout on the target with no
   `kitty-specs/c-*`; no worktree for that branch. `doctor coordination --json` reports `COORDINATION_WORKTREE_MISSING`
   for C; `--fix --mission <mid8>` materializes `.worktrees/<...>-coord`.
7. FR-007: the same Mission branch also carries Mission D's directory whose meta names another branch → D is not reported
   from that branch.

Commit: `test(doctor): red tests for doctor coordination --fix scope and branch-only discovery (#7552)`.

### T002 – Scope gate

- `doctor.py`: add `--all-missions` (bool) option; help text: "With --fix, repair every Mission in the repository.
  Without it, --fix needs --mission." Update the docstring's Examples (`--fix --mission <handle>`, `--fix --all-missions`).
- `run_coordination_health(json_output, fix, check_staleness, mission, all_missions=False)`: before collecting findings,
  if `mission and all_missions` → emit `COORDINATION_FIX_SCOPE_CONFLICT`; if `fix and not mission and not all_missions`
  → emit `COORDINATION_FIX_SCOPE_REQUIRED`. Both exit 1 via `typer.Exit(1)` and use `_doctor_shared._json_error` in
  JSON mode (mirror `_emit_mission_resolver_error`). Hoist the codes/messages to module constants (S1192).
- Keep `run_coordination_health` ≤ 15 complexity: extract `_refuse_unscoped_fix(...)`.

### T003 – Scope the strand check

- `_collect_coordination_findings(..., mission_filter)` currently calls `_check_stranded_coord_revert(repo_root)`
  unconditionally. When a Mission is resolved, keep only findings whose `extra["mission_id"]` equals the resolved
  `mission_id`. A marker finding with no `mission_id` (unparseable) is kept only in the unscoped run.
- The fixers consume the same findings list, so scoping the collection scopes the fix.

### T004 – Discovery records

- Introduce a small frozen dataclass in `_coordination_doctor.py`, e.g. `_ScannedMission(meta: dict[str, object],
  mission_dir: Path | None)`; `mission_dir` is set only for a root-checkout directory (the only one the `NEVER_CREATED`
  flatten may edit).
- Unscoped: today's walk, plus `coord_worktree_mission_names(repo_root)` entries not already seen (read their
  `meta.json` from the coordination worktree copy, `mission_dir=None`), plus `branch_only_mission_metas(repo_root)`.
- Placement-seam reader in `missions/_read_path_resolver.py`, next to `coord_worktree_mission_names`:
  `branch_only_mission_metas(repo_root) -> list[BranchOnlyMission]` (dir name, branch, meta, or an error string).
  Enumerate local `refs/heads/kitty/mission-*` (`git for-each-ref --format=%(refname:short)` through `kernel.git`'s
  runner), skip `is_lane_branch`, list `kitty-specs/*/meta.json` with `kernel.git.listing.tree_paths(..., glob=True)`,
  skip directory names present on disk in the root checkout or a coordination worktree, read with `blob_at`, JSON-decode,
  keep when `meta.get("mission_branch") == branch or meta.get("coordination_branch") == branch`. Any `GitCommandError` /
  decode error → an entry carrying the error, which the doctor renders as a `warning`
  (`COORDINATION_BRANCH_META_UNREADABLE`).
- `--mission`: try `resolve_mission`; on `MissionNotFoundError`, match branch-only records by exact `mission_id`, its
  first 8 chars, or `mission_slug`; 0 → re-raise not-found; >1 → `AMBIGUOUS_HANDLE`.
- Confirm `materialize_coord_surface_for_write(repo_root, slug)` succeeds for case 6; if it needs the meta on disk, record
  the friction and call it with what the seam needs (do not hand-roll `git worktree add`).

### T005 – Remedies, existing tests, allowlist

- Update operator remedy strings that say `doctor coordination --fix` without a Mission so they name `--mission`:
  `_coordination_doctor.py` (`:124`, `:651`, `:694`; use the Mission slug where the finding knows it),
  `cli/commands/decision.py:330`, `runtime/next/runtime_bridge.py:419`, `coordination/surface_resolver.py:227`.
- Existing tests that run `--fix` unscoped: add `--all-missions` (behaviour-preserving) or `--mission`. Update the help
  golden in `test_doctor_cli_surface_golden.py`.
- If `_coordination_doctor.py` no longer iterates `kitty-specs/` itself, drop it from `_LEGACY_WALKER_ALLOWLIST`
  (drain). If it still does (today's root walk is kept), leave the entry.

## Test Strategy (targeted; never `make test-full`)

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/test_doctor_coordination_scope_7552.py \
  tests/specify_cli/cli/commands/test_doctor_coordination.py tests/specify_cli/cli/commands/test_coordination_doctor.py \
  tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py tests/specify_cli/cli/commands/test_doctor_flatten_remote_reverify_4979.py \
  tests/specify_cli/cli/commands/test_coordination_remedy_5113.py tests/architectural/test_mission_resolver_walker_gate.py -q
```

plus the test files that grep for every remedy string you changed.

## Definition of Done

- T001 red commit precedes the fix commit; all listed tests green; `ruff check`, `ruff format --check --force-exclude`
  and `mypy` clean on changed files; no function above complexity 15.

## Risks

- Remedy-string pins in tests; the help golden.
- Branch enumeration in large repositories (NFR-001: one `ls-tree` per Mission branch).

## Reviewer Guidance

- Verify red→green on the T001 tests; verify B is byte-identical under `--fix --mission A`; verify no mutation without `--fix`.
