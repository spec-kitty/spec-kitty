# Code grounding: doctor coordination scope and decisions runtime lock hygiene

Read-only grounding run for sub-epic #7549 (#7552, #7498; context #7540 items 4 and 5, #7493 / PR #7499, epic #2017).
Base: `origin/main` at `2e9ca559`. Reader: the implementer of this Mission (software engineer, Spec Kitty core).

The checkout is a shallow clone (50 commits), so the 90-day churn and fix history below come from the
in-file history notes (issue numbers in docstrings), not from `git log`.

## 1. `doctor coordination` (#7552)

### Sites and sizes

| File | Lines | Responsibility |
|------|-------|----------------|
| `src/specify_cli/cli/commands/doctor.py` | 1724 | Typer shell. `coordination_health` (`:1500-1576`) only parses options and calls `run_coordination_health`. |
| `src/specify_cli/cli/commands/_coordination_doctor.py` | 2079 | Every check and fixer: git version, tracked-`.worktrees/` hygiene, coord worktree health, lane sparse drift, stranded-revert markers, Gap-1 staleness, and the four `--fix` handlers. |
| `src/specify_cli/context/mission_resolver.py` | 1076 | The sanctioned Mission enumeration (`_iter_mission_dirs`) and handle resolution (`resolve_mission`). |
| `src/specify_cli/missions/_read_path_resolver.py` | ~2180 | Placement-seam read helpers: `coord_worktree_mission_names`, `default_mission_topic_dir`. |

### What `--mission` already does

`--mission <handle>` exists (FR-012). `_resolve_mission_dirs` (`_coordination_doctor.py:910`) maps it through
`resolve_mission` (mission_id → mid8 → slug, `AmbiguousHandleError` / `MissionNotFoundError` propagate, no
silent fallback), and `run_coordination_health` (`:1996`) renders those as `MISSION_NOT_FOUND` /
`AMBIGUOUS_HANDLE`, exit 1.

### The real gaps

1. **`--fix` without `--mission` is repo-wide with no confirmation.** `run_coordination_health` runs every
   fixer over every finding. `_apply_never_created_fix` → `_fix_never_created_branches` calls the destructive
   `flatten_coordination_metadata` for every `COORDINATION_WORKTREE_NEVER_CREATED` finding. This is the 58-Mission
   flatten of #7540 item 4.
2. **`--mission` does not scope the repo-level checks or their fixer.** `_collect_coordination_findings` always
   runs `_check_stranded_coord_revert(repo_root)` over every `pending_coord_reconcile` marker, and
   `_apply_stranded_revert_fix` heals every live strand it finds (a `git revert` on the coordination branch).
   So `--fix --mission A` can revert a stranded `done` on Mission B. The finding carries
   `extra["mission_id"]` / `extra["mission_slug"]`, so it can be filtered.
3. **The unfiltered scan does not use the resolver.** `_resolve_mission_dirs` (no filter) walks
   `kitty-specs/*` itself. It is on the `_LEGACY_WALKER_ALLOWLIST` of
   `tests/architectural/test_mission_resolver_walker_gate.py`. The resolver's `_iter_mission_dirs` already adds
   `coord_worktree_mission_names` (FR-061 / #7282) and the topic holder's copy (`_topic_holder_or`), so it finds a
   settled default Mission whose `meta.json` lives only in its coordination worktree. The doctor walk does not.
4. **A Mission whose `meta.json` lives only on a branch ref, with no checkout holding it, is invisible to both.**
   This is #7540's state after `consolidate --abort` removed the coordination worktree: the repository root
   checkout is back on the target branch (no Mission directory), and the coordination worktree is gone. Only the
   Mission branch `kitty/mission-<slug>-<mid8>` carries `kitty-specs/<dir>/meta.json`. That is exactly the
   `COORDINATION_WORKTREE_MISSING` case `--fix` exists to repair, and why the workaround was an in-process
   `materialize_coord_surface_for_write(repo_root, slug)`, which needs only the slug.

### Read primitives available

- `kernel.git.listing.tree_entries(cwd, ref, pathspecs=...)` / `blob_at(cwd, ref, path)` read a ref's tree and a
  blob without a checkout (owned by `kernel.git`; `tests/architectural/test_git_path_listing_owner.py` keeps
  porcelain parsing there).
- `lanes.branch_naming.parse_mission_slug_from_branch`, `is_lane_branch` classify `kitty/mission-*` refs.
- `_check_coordination_worktree_health(repo_root, meta)` and `_check_lane_sparse_checkout_drift(repo_root, meta)`
  take a meta mapping, not a directory, so a ref-read meta can be checked as is. The only directory use is
  `extra["meta_path"]` for the `NEVER_CREATED` flatten, which must not be offered for a ref-only Mission (there
  is no file to edit; a flatten there is a branch write and out of scope).

## 2. Decisions runtime lock (#7498, #7540 item 5)

### Sites and sizes

| File | Lines | Responsibility |
|------|-------|----------------|
| `src/specify_cli/decisions/lock.py` | 216 | The one owner of the lock path (`LOCK_FILENAME = "index.json.lock"`, `lock_path`), the waits and the refusal. `decisions_lock` (`:~170`) acquires through `kernel.locks.machine_file_lock`. |
| `src/kernel/locks.py` | — | The single raw-lock door. **G3: release truncates, never unlinks** (preserves inode identity). |
| `src/specify_cli/coordination/coherence.py` | 1096 | `is_decisions_runtime_lock` (`:177`, depth-exact regex), folded into `is_self_bookkeeping_churn` (`:172`). |
| `src/specify_cli/git/commit_helpers.py` | — | `safe_commit` (`:1802`) / `preflight_commit` (`:1613`): stages with `git add --force -- <path>` (`:1330`, `:1344`); path policy step 6a refuses only `.worktrees/`. |
| `src/specify_cli/git/ref_advance.py` | — | The landing reset's dirty scan; an untracked/ignored path that a tracked path in the target tree overlaps is an `OBSTRUCTION` ("would be overwritten by reset --hard to …"). |
| `src/specify_cli/decisions/service.py` | — | `_ensure_runtime_lock_ignore` writes a mission-local `decisions/.gitignore` rule — only for the owned `repair-runtime-lock` route. |
| `src/specify_cli/core/git_ops.py` | — | `exclude_from_git_index` / `git_exclude_file`: append to the COMMON-dir `info/exclude`, which git honours for the root checkout and every linked worktree. |

### `is_decisions_runtime_lock` callers

`coherence.is_self_bookkeeping_churn` (every dirty gate using it or `is_toolchain_generated_churn` /
`ResidueContext.is_disposable`), `implement_cores` (`:35`, `:287`, `:809` — planning auto-commit staging, #7493),
`lanes/implement_support` (`:193` — claim check, #7493), `acceptance/ledger_dirt` (`:57`).

### The defect chain

1. The lock is untracked by design: release truncates and never unlinks (#5925, kernel G3). Nothing ignores it in a
   consumer project (this repository happens to ignore `*.lock` in its own `.gitignore`; consumer projects do not),
   so after any decision write it is untracked dirt in the checkout where the PRIMARY ledger lives.
2. `safe_commit` stages each requested path with `git add --force`, and its path policy does not know the lock. A
   `spec-commit kitty-specs/<m>/decisions/*` (or any batch naming it) commits it — the tracer reports of `spec-commit`
   committing the lock. `--force` also overrides any ignore rule, so an exclude alone is not enough.
3. Once a Mission branch tracks the lock, landing that branch resets the repository root checkout to a tree that
   tracks `kitty-specs/<m>/decisions/index.json.lock`. The local untracked (empty) copy overlaps that tracked path, so
   `ref_advance._dirty_reason` reports it as an `OBSTRUCTION` and the landing refuses. The display line is the porcelain
   entry (`!!` when an ignore rule matches, e.g. `*.lock` in this repository), which is why it was "labelled `!!`".
4. `doctor`/the operator cannot simply delete it: unlinking a lock file breaks mutual exclusion for any process that
   already opened the old inode (kernel G3). A held lock is non-empty (the holder writes a `LockRecord` right after
   locking); an unheld one is empty.

### Lane checkouts (#7498 gap 2)

The decision service writes the lock on the placement surface (`service._ledger_dir`), never in a lane checkout. With
the pattern in the common-dir `info/exclude`, an untracked lock is invisible to every `git status`-based gate in every
worktree (`_check_uncommitted_worktree_changes`, `_validate_worktree_clean`, the move-task lane auto-commit). A
tracked lock (an old commit) is not excluded by any ignore rule; the `safe_commit` backstop stops new ones.

## 3. Invariants that must survive

- **Placement seam owns surfaces.** Discovery reads the placement seam (`mission_resolver`, `_read_path_resolver`);
  materialization stays `coordination.surface_resolver.materialize_coord_surface_for_write`.
- **No silent selector fallback** (WP07 of 083; `resolve_mission` raises; doctor renders `MISSION_NOT_FOUND` /
  `AMBIGUOUS_HANDLE`).
- **`doctor` without `--fix` is read-only**; `--fix` is the only mutating mode and is error-code-scoped and idempotent.
- **Lock concurrency:** never unlink a lock file (kernel G3); only `kernel.locks` takes raw OS locks
  (`tests/architectural/test_lock_primitive_ban.py`); lock order anchor → sidecar → status (`decisions/lock.py`).
- **`safe_commit` refuses before any index mutation** (step order in its docstring); the owned
  `repair-runtime-lock` index-only removal (`_validate_runtime_lock_removal`) must stay possible.
- **Remote re-verification before a flatten** (`_coord_branch_remote_skip_reason`, #4979) stays.

## 4. Gates and ledgers touching these files

- `tests/architectural/test_mission_resolver_walker_gate.py` — `_coordination_doctor.py` is on its legacy allowlist;
  moving the walk to the resolver lets the entry go.
- `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py` — the `doctor coordination` help/option golden;
  a new option changes it.
- `tests/architectural/test_lock_primitive_ban.py`, `test_git_path_listing_owner.py`, `test_no_read_side_bypass.py`,
  `test_json_contract_enumeration.py`, `test_exemption_registry_ratchet.py` (module-level filename lists count as
  exemptions; keep literals function-local or reuse `is_decisions_runtime_lock`).
- Migration ledger gates only if a migration is added (`test_migration_order_manifest.py`).

## 5. Test seams and cost

- `tests/specify_cli/cli/commands/test_doctor_coordination.py`, `test_coordination_doctor.py`,
  `test_doctor_flatten_remote_reverify_4979.py`, `test_coordination_remedy_5113.py`: real git repos in `tmp_path`,
  `CliRunner` over the doctor app; a few seconds each.
- `tests/decisions/`, `tests/git/` (safe_commit), `tests/mission_runtime/test_self_bookkeeping_allowlist.py`.
- A lanes_with_coord end-to-end `implement` is expensive (mission scaffold + finalize); the `safe_commit` backstop and
  the common-dir exclude are each one choke point, so a pin at the choke point plus one CLI-level `spec-commit` run
  covers every topology without a full lanes_with_coord build.

## 6. Interactions

- **#7544** (coordination closeout; consolidate paths hit the lock): this Mission does not touch consolidation or
  rollback. The landing obstruction disappears when no branch tracks the lock; the obstruction message only gets a
  precise label.
- **#7545 / PR #7557** (CLI commits its own writes; edits `coherence.is_self_bookkeeping_churn`): this Mission does not
  edit `coherence.py`, so no textual conflict.
