---
work_package_id: WP09
title: '#5113 - Materialize the coordination worktree before a decision write'
dependencies: []
requirement_refs:
- FR-013
- FR-014
- C-006
planning_base_branch: claude/charter-load-mission-q9ajcz
merge_target_branch: claude/charter-load-mission-q9ajcz
branch_strategy: Planning artifacts for this mission were generated on claude/charter-load-mission-q9ajcz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/charter-load-mission-q9ajcz unless the human explicitly redirects the landing branch.
subtasks:
- T024
- T025
- T026
- T027
- T028
- T029
phase: Phase 1 - Decision ledger on fresh coordination Missions (wave 1)
task_type: implement
execution_mode: code_change
owned_files:
- src/specify_cli/coordination/surface_resolver.py
- src/specify_cli/decisions/service.py
- src/specify_cli/cli/commands/decision.py
- tests/specify_cli/cli/commands/test_decision_fresh_coord_5113.py
- tests/coordination/test_materialize_coord_surface.py
- tests/mission_runtime/test_coord_read_seam.py
- tests/mission_runtime/test_coord_read_seam_callers.py
- tests/cli/commands/test_merge_status_commit.py
authoritative_surface: src/specify_cli/decisions/service.py
create_intent:
- tests/specify_cli/cli/commands/test_decision_fresh_coord_5113.py
- tests/coordination/test_materialize_coord_surface.py
agent_profile: python-pedro
role: implementer
agent: claude
model: ''
assignee: ''
shell_pid: ''
history:
- at: '2026-09-26T13:17:07Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
---

# Work Package Prompt: WP09 – #5113: Materialize the coordination worktree before a decision write

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

#5113 has been reproduced with the real `create_mission_core` on the coordination topology (research Part B):

- The coordination branch exists, but `.worktrees/` is absent.
- `spec-kitty agent decision open --json` exits 1 with an **uncaught** `CoordinationWorktreeUnmaterialized` (a raw traceback, no JSON).
- It also leaves `decisions/DM-<id>.md`, `decisions/index.json` and `decisions/index.json.lock` behind, which is a half-recorded Decision Moment.

Success means:

1. **FR-013.** `decision open` / `resolve` / `defer` / `cancel` materialize an absent coordination worktree **before any write**. They use a new coordination-layer helper `materialize_coord_surface_for_write(repo_root, mission_slug) -> None` that reuses the canonical materializer `CoordinationWorkspace.resolve`. The command returns the `decision_id`, and `decision list` shows it (US6 AS1, SC-006).
2. When materialization itself fails, or the coordination branch is remote-only, the command fails with a structured JSON error. The decision index, the decision artifact and every `status.events.jsonl` are **byte-identical** to before, and no `.lock` sidecar is created (US6 AS2).
3. The CLI verbs render `StatusReadPathNotFound`, and therefore `CoordinationWorktreeUnmaterialized`, as `{"error", "code", "next_step"}` JSON: no traceback, and no new `DecisionErrorCode` (the orchestrator `upstream_contract.json` is unchanged).
4. **FR-014 (this WP's share).** `CoordinationWorktreeUnmaterialized.next_step` (`coordination/surface_resolver.py`) stops promising self-materialization and stops naming `doctor workspaces --fix`, which cannot create worktrees (#2240). It names `spec-kitty doctor coordination --mission <slug> --fix`, and says that coordination writes such as `decision` now materialize on demand. The pinned words "materializ" stay and "flatten" stays absent.
   - WP10 delivers the doctor fixer and the round-trip test proving the command works.
   - The EMPTY/husk warning `_COORD_EMPTY_FALLBACK_WARNING` (#1890) is **unchanged**: a husk is a different state, and `doctor workspaces` is right for it (PD-10).
5. Read paths (`decision list`, `decision verify`) **never** materialize (research D2).
6. C-006: which partition each ledger file lives on is unchanged.

## Context & Constraints

- **Spec**: US6 (AS1–AS3), FR-013, FR-014, SC-006, C-006, and the Intent Summary "Folded scope" (an independent slice with no naming dependency).
- **Plan**: PD-9 and PD-10, and Risk 4 (concurrent materialization).
- **Research Part B**: D1 (helper design, callers, import rule), D2 (read paths), D3 (remedy wording and pins), D4 (test design and fixture), D5 (complexity), D6 (proposed WP, of which this is the first half), and D7 (risks: concurrency, dry-run, contracts).
- **Data model**: "Decision ledger (FR-013)" gives the write sequence. "State: coordination surface" gives UNMATERIALIZED → Materialized, or Refused.
- **tasks.md**: WP09 + WP10 split. `surface_resolver.py` is owned solely by WP09. `_coordination_doctor.py`, `doctor.py` and the other remedy emitters are WP10's; do not edit them.
- **Canonical sources** (DIRECTIVE_044):
  - reuse `CoordinationWorkspace.resolve` (`coordination/workspace.py`);
  - reuse `probe_coord_state` and `read_primary_meta` (`missions/_read_path_resolver.py`);
  - reuse `resolve_declared_mid8` and `_coord_branch_is_local_head` (`coordination/surface_resolver.py`).
  - Do **not** reuse the private `commit_router._materialise_coord_worktree` or `status_transition._resolve_fallback_coord_worktree` (D1 alternatives b and c).

**Implementation command**: `spec-kitty agent action implement WP09 --agent <name>`. The dependency list is empty.

## Branch Strategy

- **Strategy**: Planning artifacts for this mission were generated on `claude/charter-load-mission-q9ajcz`. During `/spec-kitty.implement` this WP may branch from a dependency-specific base, but completed changes must merge back into `claude/charter-load-mission-q9ajcz` unless the human explicitly redirects the landing branch.
- **Planning base branch**: `claude/charter-load-mission-q9ajcz`
- **Merge target branch**: `claude/charter-load-mission-q9ajcz`

> Execution worktrees are allocated per computed lane from `lanes.json`. Use the workspace `spec-kitty agent action implement` resolves.

## Subtasks & Detailed Guidance

### Subtask T024 – Red-first integration tests on a real fresh coordination Mission

- **File**: `tests/specify_cli/cli/commands/test_decision_fresh_coord_5113.py` (new). Markers: `integration`, `git_repo` (check `pytest.ini`).
- **Fixture**:
  - Reuse `_init_git_repo` and `_create_mission(repo, slug, MissionTopology.COORD)` from `tests/integration/test_placement_partition_golden_path.py`. That is the real `create_mission_core` with only `is_worktree_context` patched, and it yields branch present, worktree absent.
  - Import those helpers, or hoist a module-local `fresh_coord_mission` fixture that calls them. Do not copy-paste them (canonical sources).
  - The existing fixtures `_coord_declared_no_worktree` and `_coord_materialized` in `test_decision_single_authority.py` **cannot** reproduce UNMATERIALIZED (D4). Do not use them.
- **Drive the CLI** through `typer.testing.CliRunner` against the real `decision` Typer app, the pre-existing entry point. Find the app object in `cli/commands/decision.py`.
- **Tests** (from D4):
  1. `test_open_materializes_and_returns_id`: exit 0; the JSON payload has `decision_id`; `.worktrees/<slug>-<mid8>-coord` exists (get the path from `CoordinationWorkspace.worktree_path(...)`, do not compose it); `decision list --json` contains the id. **Red on HEAD** (traceback plus partial files).
  2. `test_resolve_materializes`: open, then `git worktree remove` the coord worktree to return to UNMATERIALIZED, then `decision resolve` exits 0 with status `resolved`.
  3. `test_materialization_failure_is_byte_identical[open|resolve]`. Create a *real* failure by writing `.worktrees` as a **regular file**: `resolve`'s `mkdir` then raises `FileExistsError`, while the probe still reads UNMATERIALIZED.
     - Snapshot every file under `kitty-specs/<slug>/`, bytes plus the sorted file list, before and after.
     - Assert equality: no `decisions/` dir and no `index.json.lock`.
     - Assert exit 1, JSON `code == "COORDINATION_WORKTREE_UNMATERIALIZED"`, and no `Traceback` in the output.
     - For `resolve`, first open successfully on a materialized coordination surface, then remove the worktree and plant the obstacle.
  4. `test_remote_only_branch_refuses_before_write`: `git update-ref refs/remotes/origin/<b> <b>`, then `git branch -D <b>`. The same byte-identity and JSON assertions as test 3.
  5. `test_list_and_verify_never_materialize`: on UNMATERIALIZED, `decision list --json` and `decision verify --json` exit 0, and `.worktrees/` is still absent afterwards (D2 guard).
  6. `test_dry_run_never_materializes`: `decision open --dry-run` leaves `.worktrees/` absent.
- **Red-first**: run on HEAD and record the failures in the Activity Log (tests 1–4 red; 5–6 green on HEAD, which is expected, as guards).

### Subtask T025 – `materialize_coord_surface_for_write` helper + unit tests

- **File**: `src/specify_cli/coordination/surface_resolver.py`, next to `resolve_for_write`.
- **Body** (D1):
  1. `meta = read_primary_meta(repo_root, mission_slug)`. Check its signature in `missions/_read_path_resolver.py`. If `coordination_branch` is absent or empty, return (flat, SINGLE_BRANCH or LANES Missions).
  2. `mid8 = resolve_declared_mid8(meta, mission_slug)`; then `state = probe_coord_state(..., coordination_branch=...)`, with the exact keyword arguments from its definition.
  3. If `state` is not `CoordState.UNMATERIALIZED`, return. MATERIALIZED and EMPTY need nothing; DELETED is left to raise downstream, as today.
  4. If `not _coord_branch_is_local_head(repo_root, coord_branch)`, raise `CoordinationWorktreeUnmaterialized(...)` **before any write**. Construct it the way existing raisers do (grep for `CoordinationWorktreeUnmaterialized(` in this module). A remote-only branch is never auto-materialized (#4970 parity with `write_target_degrade`).
  5. Otherwise call `CoordinationWorkspace.resolve(repo_root, mission_slug, mid8)`. Catch exactly `OSError | subprocess.SubprocessError | CoordinationWorkspaceBranchMismatch | CoordinationWorkspaceIdentityUnresolved` (the same narrowed set as `coordination/status_transition.py`'s fallback), then **re-probe once**: if the state is now MATERIALIZED or EMPTY, return (plan Risk 4, a concurrent CLI race). Otherwise raise `CoordinationWorktreeUnmaterialized(...)` `from exc`.
- **Complexity**: keep it ≤ CC 8. Extract `_raise_unmaterialized(...)` if the construction repeats (S1192).
- **`__all__`**: add the helper, following the module's convention.
- **Unit tests** (`tests/coordination/test_materialize_coord_surface.py`, new), one per arm, all on real tmp git (reuse the T024 fixture helpers):
  - no coordination branch in meta → no-op;
  - MATERIALIZED → no-op, with no second worktree;
  - EMPTY → no-op;
  - UNMATERIALIZED plus a local branch → the worktree exists afterwards;
  - remote-only → raises and nothing is created;
  - resolve raising (the `.worktrees` regular-file obstacle) → raises `CoordinationWorktreeUnmaterialized` with a `__cause__`;
  - the race: simulate by materializing between the probe and `resolve` via a `monkeypatch` of `CoordinationWorkspace.resolve` that first materializes and then raises `OSError` → the helper returns without raising. This is the only permitted monkeypatch, and it wraps the real call.

### Subtask T026 – Wire the helper into the decision service

- **File**: `src/specify_cli/decisions/service.py`.
- **`open_decision`**: insert the call **after** the `if dry_run:` early return and **before** `_locate_or_create_open_entry(...)`, which creates the `.lock` sidecar and the index:
  ```python
  # #5113 / FR-013: resolve every write target BEFORE any ledger write. A fresh
  # coordination Mission has its branch but no worktree; materialize it through the
  # canonical materializer so the ledger write and the event emit land on a real
  # surface. Function-local import: decisions.* sits on the charter cold-import path
  # (tests/architectural/test_cold_import_status_boundary.py).
  from specify_cli.coordination.surface_resolver import materialize_coord_surface_for_write  # noqa: PLC0415
  materialize_coord_surface_for_write(repo_root, mission_slug)
  _events_path(repo_root, mission_slug)  # pre-resolve: any placement failure fails before write
  ```
  Keep `mission_dir = _ledger_dir(...)` where it is. If `_ledger_dir` could itself raise on UNMATERIALIZED (read it), move the materialize call before it. It must still stay after `dry_run`, and `dry_run` must still not materialize. If `_ledger_dir` is needed for the dry-run response, restructure so that dry-run only reads.
- **`_terminal_command`**: the same call after its `if dry_run:` return and before `_apply_terminal_under_lock(...)`. This covers resolve, defer and cancel.
- **Keep** `emit.py::_mission_dir` unchanged. Do not thread an `events_path` through the public `emit_decision_*` API (D1).
- **Check** every other caller routes through these two functions (`grep -rn "open_decision\|_terminal_command\|resolve_decision\|defer_decision\|cancel_decision" src`): the specify/plan/charter interviews, widen, and `orchestrator_api/commands.py`. Do not edit those files. The orchestrator API already maps `StatusReadPathNotFound`; verify it with a test run.
- **Validation**:
  - [ ] T024 tests 1–4 are green.
  - [ ] `open_decision` and `_terminal_command` complexity is unchanged or +1.

### Subtask T027 – Structured CLI error handler

- **File**: `src/specify_cli/cli/commands/decision.py`.
- **Steps**:
  1. Add `_handle_status_read_path_error(exc: StatusReadPathNotFound) -> None` next to `_handle_action_context_error`. It emits `{"error": str(exc), "code": exc.error_code, "next_step": getattr(exc, "next_step", None)}` as sorted JSON to stderr, matching the existing handlers' stream and shape, and then raises `typer.Exit(1)`.
  2. Add `except StatusReadPathNotFound as exc: _handle_status_read_path_error(exc); return` to `cmd_open`, `cmd_resolve`, `cmd_defer` and `cmd_cancel`, **after** the more specific excepts. `CoordinationWorktreeUnmaterialized` subclasses `StatusReadPathNotFound`.
  3. Watch complexity: each `cmd_*` gains one `except` branch. If a `cmd_*` would exceed CC 10, extract the shared except chain into a small wrapper (campsite, D5).
  4. `tests/architectural/test_cli_error_surface_seam.py` governs CLI error surfaces. Run it; if it asks for registration, follow its pattern. Its baseline is registered in `_baselines.yaml` under `test_cli_error_surface_seam`. Growing that baseline needs a justification comment. **Prefer a shape that does not grow it.** If growth is unavoidable, stop and report, because `_baselines.yaml` is owned by WP07.
- **Test**: T024 tests 3–4 assert the JSON shape and the absence of a traceback.

### Subtask T028 – Rewrite the unmaterialized-coordination remedy; update pins

- **File**: `src/specify_cli/coordination/surface_resolver.py`, `CoordinationWorktreeUnmaterialized.__init__` → `self.next_step`.
- **New text** (adjust the wording, keep the substance):
  > The coordination branch {coordination_branch!r} declared in meta.json exists in git, but its coordination worktree has not been materialized yet. Coordination writes such as `spec-kitty agent decision open` materialize it on demand; to materialize it now, run `spec-kitty doctor coordination --mission {mission_slug} --fix`. Keep the `coordination_branch` key in meta.json as-is — the branch is not lost, only not yet checked out.
- It must contain "materializ" and must not contain "flatten". Also update the module docstring line near the top that mentions `doctor workspaces --fix` for this state, but only where it describes UNMATERIALIZED, not the husk.
- **Do not change** `_COORD_EMPTY_FALLBACK_WARNING` or the EMPTY warning at ≈L1178. Those are husk and EMPTY recovery (#1890).
- **Pins to update** (all owned by WP09):
  - `tests/mission_runtime/test_coord_read_seam.py` (≈L177: "materializ" stays);
  - `tests/mission_runtime/test_coord_read_seam_callers.py` (≈L189, L232, L416);
  - `tests/cli/commands/test_merge_status_commit.py` (≈L881 asserts `"doctor workspaces --fix" in output` for this exception's own `next_step`). Re-pin it to `doctor coordination --mission` and `--fix`.
  - Grep `tests/` for other assertions on this exception's text: `grep -rn "doctor workspaces --fix" tests | xargs grep -l "Unmaterialized\|UNMATERIALIZED"`. Pins owned by WP10 (`test_bridge_parity.py`, `test_implement_placement_routing.py`, `test_record_analysis_placement.py`) pin **other** emitters; leave them.
- **Validation**: the pinned suites are green; `test_surface_resolver_coord_empty_warning.py` is green, **unedited**.

### Subtask T029 – Quality gates and blast radius

Run the Test Strategy commands and record the exact commands plus counts. Also run `grep -rl "decisions.service\|open_decision\|resolve_decision" tests` and include those files, which cover the interviews, widen and orchestrator-api.

## Test Strategy

- **Red-first**: T024 tests 1–4 fail on HEAD through the CLI entry point.
- **Real git**: real `create_mission_core` and real `git worktree`. Failures are real obstacles (a regular file at `.worktrees`), not mocks. The single race-simulation monkeypatch in T025 wraps the real call.
- **Commands** (D6 blast radius):

```bash
.venv/bin/python -m pytest tests/specify_cli/cli/commands/test_decision_fresh_coord_5113.py tests/coordination/test_materialize_coord_surface.py -q
.venv/bin/python -m pytest tests/specify_cli/decisions tests/specify_cli/cli/commands/test_decision_single_authority.py tests/specify_cli/coordination tests/coordination tests/mission_runtime/test_coord_read_seam.py tests/mission_runtime/test_coord_read_seam_callers.py tests/cli/commands/test_merge_status_commit.py -q
.venv/bin/python -m pytest $(grep -rl "decisions.service\|open_decision\|resolve_decision" tests --include=*.py | tr '\n' ' ') -q
.venv/bin/python -m pytest tests/architectural/test_cold_import_status_boundary.py tests/architectural/test_cli_error_surface_seam.py tests/architectural/test_no_read_side_bypass.py tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_legacy_terminology.py -q
make test-fast
```

- **NFR gates**:

```bash
FILES="src/specify_cli/coordination/surface_resolver.py src/specify_cli/decisions/service.py src/specify_cli/cli/commands/decision.py"
.venv/bin/ruff check $FILES tests/specify_cli/cli/commands/test_decision_fresh_coord_5113.py tests/coordination/test_materialize_coord_surface.py
.venv/bin/ruff check --select C901 $FILES
.venv/bin/ruff format --check $FILES tests/specify_cli/cli/commands/test_decision_fresh_coord_5113.py tests/coordination/test_materialize_coord_surface.py
.venv/bin/mypy $FILES
```

## Definition of Done

- [ ] A fresh coordination Mission can open, resolve, defer and cancel Decision Moments. The worktree is materialized once.
- [ ] A materialization failure or a remote-only branch leaves `kitty-specs/<slug>/` byte-identical, emits structured JSON, and shows no traceback.
- [ ] List, verify and dry-run never materialize.
- [ ] The remedy text names `doctor coordination --mission <slug> --fix`. The husk and EMPTY text is unchanged.
- [ ] No new `DecisionErrorCode`, and `upstream_contract.json` is unchanged.
- [ ] Gates are clean, the cold-import boundary is green, and `make test-fast` is green.

## Risks & Mitigations

- **Concurrent materialization**: the one re-probe after a failed `resolve` handles it (plan Risk 4). Git spawns outside every lock (D7).
- **A materialized EMPTY coordination surface routes STATUS_STATE to primary**: intended, and it matches where the creation events live (D7).
- **A later `spec-commit` still routes `decisions/` to coordination** (the split-ledger residual, see #5023): out of scope (C-006). Note it in the PR.
- **Error-surface baseline growth**: prefer the shape that does not grow it; otherwise escalate.

## Review Guidance

- Materialization happens after dry-run and before `_locate_or_create_open_entry` / `_apply_terminal_under_lock`.
- The import is function-local, with a rationale (cold-import path).
- The byte-identity test snapshots **all** files under the Mission dir, including the absence of the lock sidecar.
- The remedy text is truthful only once WP10 lands. Confirm WP10 is scheduled right after, in the same mission merge.
- mypy was run.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)

**Initial entry**:

- 2026-09-26T13:17:07Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
