# Code grounding: #5641 (finalize-tasks keeps per-WP status commits after a failed final commit)

Read-only grounding run, 2026-10-04, against `skupstream/main` @ `05004fea33`.
Every behavioural claim below was settled by a run (the exploration harness drove
the real `finalize-tasks` command through `CliRunner` against real git
repositories created by `create_mission_core`), unless marked "read".

## The flow (read)

- `src/specify_cli/cli/commands/agent/mission_finalize.py`
  - `finalize_tasks` (~5404-5678): the `except typer.Exit` / `except Exception`
    arms (~5639-5676) run the FR-015/NFR-001 guard only when
    `not commit_landed.landed`: `_restore_mission_write_scope` (bytes of the
    Mission directory, snapshot scope `ctx.planning_dir`), the owned derived-view
    restore, and `_restore_owned_head`.
  - `_capture_owned_head` / `_restore_owned_head` (~4756-4830): owned-only.
    `_restore_owned_head` returns at once when `owned is None`; for an owned run
    it runs a mixed `git reset <sha>` (not compare-and-swap).
  - The comment at ~5427-5432 lists the coordination-branch commits under a
    non-owned `coord` / `lanes_with_coord` topology as "NOT COVERED
    (pre-existing, tracked in #5343)".
  - `_run_commit_pipeline` (~4367-4547): `_emit_local_canonical_events`
    (WPCreated / TasksCompleted to the status write dir, uncommitted) ->
    `bootstrap_canonical_state` -> lane computation -> acceptance-matrix scaffold
    -> `_commit_finalize_artifacts` (the one final `commit_for_mission(kind=
    TASKS_INDEX)`) -> `commit_landed.landed = commit_outcome.commit_created`.
- `src/specify_cli/status/bootstrap.py` `bootstrap_canonical_state` (~162-203):
  reads existing events through `read_events_transactional` (the same surface
  the transactional writer targets), then one
  `emit_status_transition_transactional` per unseeded WP. Each is its own commit
  on the status surface. The status emitter does NOT go through
  `commit_for_mission`, so failing only the `TASKS_INDEX` commit is an honest,
  minimal injection.

## Which topologies are affected (run)

Two WPs, non-owned, Mission created on a non-protected topic branch, only the
final `TASKS_INDEX` commit made to fail:

| Topology | Status-surface branch after the failed run | Checkout dirty against its own HEAD |
|---|---|---|
| `coord` | coordination branch advanced (per-WP commits kept) | no: the coordination worktree is clean at the advanced tip; the primary Mission directory is restored |
| `lanes_with_coord` | same as `coord` | no |
| `lanes` | **current branch** advanced | **yes**: ` M status.events.jsonl`, ` D status.json` |
| `single_branch` | **current branch** advanced | **yes**: same |
| flat legacy Mission (no topology; existing `repo` fixture) | unchanged | no (the "primary-uncommitted" path) |

So the triage note's reading was half right: the flat repository-root path does
not commit per WP, but non-owned `lanes` and `single_branch` Missions do, and
they are the ones whose checkout ends up dirty against its own HEAD. On a
protected target (`lanes` on `main`) the bootstrap refuses before any commit
(`PROTECTED_BRANCH_REFUSED`), so nothing is left behind there.

## What a retry does today (run)

- `coord` / `lanes_with_coord`: the second run reads the coordination log, sees
  the seeds, `newly_seeded: 0`, and succeeds. No double seed. The triage note
  was right for these.
- `lanes` / `single_branch`: the second run reads the restored (pre-run) log,
  seeds again (`newly_seeded: 2`), and succeeds. History then carries four
  `status transition` commits for two WPs, and the final log holds only the
  second run's seeds: the first run's committed events were dropped from the log
  by the byte restore and then by the next commit. The issue's "seeds twice"
  claim holds for these topologies.

## The sanctioned restore route and the gates (read)

- `git/ref_advance.py::restore_branch_ref` is the compare-and-swap ref restore
  (`git update-ref <ref> <new> <expected_old>`). With the default
  `resync_checkouts=False` the caller owns the index and working tree.
  `resync_checkouts=True` (hard reset of each checkout) is allowed ONLY inside
  `consolidation/rollback.py` (`tests/consolidation/test_single_rollback_authority.py::test_resyncing_restore_lives_only_in_the_authority`).
- Precedent for a non-consolidation caller: `core/mission_creation.py` and
  `cli/commands/agent/mission_create.py` restore a branch with
  `restore_branch_ref(..., expected_current_sha=...)` and then the index with
  `git read-tree <captured index tree>` -- no `reset --hard`.
- `tests/architectural/test_destructive_op_routing.py`: censuses `reset --hard`,
  `worktree remove --force`, `merge --abort`, `stash push` literals under
  `src/specify_cli/`. The fix adds none of these, so no allowlist change.
- `tests/architectural/test_git_path_listing_owner.py`: no path-listing argv
  (`status --porcelain`, `diff --name-only`, ...) outside `src/kernel/git/`. The
  fix lists no paths through git; it reuses the existing byte snapshot.
- `test_status_events_writes_gate.py` / `test_status_unsafe_allowlist.py`: the
  fix restores bytes through the existing `_restore_mission_write_scope`, the
  same helper the guard already uses for the Mission directory; check the gates
  still pass.
- `test_no_dead_symbols.py` (`__all__` of `src/charter` and `src/kernel` only):
  not implicated unless a public symbol is added there. Retiring
  `_capture_owned_head` / `_restore_owned_head` must leave no dead references.
- `test_issue_named_test_census.py`: name test files after the contract.

## Existing tests and cost (read + run)

- `tests/specify_cli/cli/commands/agent/test_finalize_atomicity.py` is the owning
  suite (real git, real CLI): 9 tests, ~1 minute locally; CI runs it in the
  `execution_context` module (`.github/ci-module-registry.yml`), selected by
  `module-tests.yml` with `-m "not performance and not stress"` (so a
  `regression`-marked test there runs on every PR that selects the module).
  `test_coord_topology_lane_cycle_refusal_restores_the_mission_directory_only`
  deliberately pins only the Mission directory under `coord` (the boundary this
  mission widens).
- Owned-checkout atomicity: `tests/integration/test_owned_lifecycle_acceptance_finalize.py`
  (and siblings) exercise `_restore_owned_head`.

## Churn (read)

- `mission_finalize.py`: 52 commits in 90 days, 30 of them fixes. Hot file; keep
  the change narrow and the helpers small.
- `status/bootstrap.py`: 7 commits in 90 days. Not changed by the fix.

## Interactions (read)

- PR #5633 (merged today) added the `COORD_STATUS_SURFACE_DIVERGED` guard that
  refuses a coordination status write when the worktree lost committed events.
  The `coord` case of #5641 leaves the coordination worktree clean (not
  diverged), so that guard does not fire here; the `lanes` / `single_branch`
  case is not a coordination worktree.
- Open PR #5650 decomposes `consolidation/executor.py`: not touched.
- Open PR #5639 edits `pytest.ini`, `tests/conftest.py`,
  `tests/_support/p0_repro.py`: not touched.
- #5343 (plan/apply redesign) stays out of scope; the narrow fix is independent
  of it (operator ruling on #5641).
