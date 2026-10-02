# Contract: seed (one-time carry-over to the coordination surface)

**Operation:** `seed_coord_surface(request: SeedRequest) -> SeedReport` (new, `src/specify_cli/coordination/coord_seed.py`). The only caller is `establish_coord_write_location` (see `write-location-accessor.md`). It is never called on a read path.
**Requirements:** FR-002, FR-004, FR-004a, FR-004b, FR-003a; C-003, C-004. Decisions: `specify.design.fork-check`, `specify.design.seed-mechanism`.

## Preconditions

- The Mission is coordination-routed (`coord` or `lanes_with_coord`, owned or not).
- The coordination worktree exists and the state is `EMPTY`: the worktree root exists and the Mission dir is absent.
- The caller holds no workspace lock. It may hold the status lock, which is reentrant.

## Procedure

1. **Lock.** Acquire `feature_status_lock(lock_root, coord_mission_dir_name(slug, mid8), timeout=BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS)`. `lock_root` is `owned.owned_root` when owned, else `repo_root` (as `transaction.py:290-291`). The key matches `coord_status_lock` and `commit_router._coord_status_locks`. The timeout is bounded (`status/locking.py:54`, 10 s); the default `-1` would wait forever and make `STATUS_LOCK_HELD` unreachable.
2. **Re-check.** Re-probe the state. If it is `MATERIALIZED`, return an empty report (another writer seeded first, so the seed is idempotent), **unless a seed commit is pending**: a seed commit is **pending** iff the coordination branch history has no `Spec-Kitty-Coordination-Seed: <mission_id>` trailer **and** the coordination tip has no COORD-kind blob under the Mission dir, i.e. the Mission dir is wholly untracked, which only a refused seed leaves. A never-seeded pre-fix MATERIALIZED Mission (#5519 shape) has committed COORD blobs at the tip, so it never matches. In that case, run step 9 only (the commit with the trailer) and return.
3. **Clean up.** Remove stale `kitty-specs/.<dir>.seed-*` temp dirs.
4. **Collect.** Gather root COORD records from the repository root checkout's Mission dir. These are the files whose `kind_for_mission_file` is a COORD kind: the status log, `decisions.events.jsonl`, `traces/*.md`, `tasks/*/review-cycle-*.md`, `issue-matrix.json` and `acceptance-matrix.json`. PRIMARY files are never collected.
5. **Read the coordination side.** The coordination-side content is the branch-tip blobs of **COORD-kind** files under `kitty-specs/<dir>/` (classified with `kind_for_mission_file`), if any; otherwise it is empty. PRIMARY files on the branch tip (a pre-fix branch cut after the first target commit) are ignored. When the branch carries the seed marker (post-fix regression), the accessor first restores the COORD-kind paths from the tip, with an explicit pathspec rather than a whole-dir checkout, and that restored content is the coordination side.
6. **Apply the prefix rule per log stream**, on event-id sequences `R` (root) and `C` (coordination):
   - `C` empty, or `C` a proper prefix of `R`: the output is `C` + `R[len(C):]`, using the root lines.
   - `R` a prefix of `C`, or equal: the output is `C`.
   - Otherwise: release everything and raise `COORD_SEED_FORK_REFUSED`.
7. **Non-log records.** Take the coordination copy if present, else the root copy. When both exist and differ, add a warning; the root copy is kept untouched.
8. **Write.** Write the output tree into `kitty-specs/.<dir>.seed-<pid>-<ulid>/`, then `os.rename` it to `kitty-specs/<dir>/`. The rename is atomic within the worktree's filesystem.
9. **Commit.** Commit on the coordination branch through `commit_for_mission(kind=STATUS_STATE, files=<coordination paths>)`, with the message `chore(<mission>): seed coordination surface` and the trailer `Spec-Kitty-Coordination-Seed: <mission_id>`, built from the one shared constant `COORD_SEED_TRAILER` in `coord_seed.py`, which create's commit also uses (Decision Moment `plan.design.seed-trailer-ownership`). The trailer is the post-fix discriminator (research D4). Then record `coord_commit`.
10. **Restore the root checkout.** For each carried root file: if it is tracked and dirty, run `git checkout -- <path>`; if it is untracked, remove it. Committed history is never rewritten (C-004).
11. **Release** the lock and return the `SeedReport`.

Create-time seed: steps 4-7 find nothing (the scaffold no longer writes the status log to the root checkout), so step 8 creates an empty Mission dir. Create then emits the creation events into it and commits them (IC-05).

## Postconditions

- The coordination Mission dir exists and holds every carried record. The state is `MATERIALIZED`.
- In each log, no event id appears twice.
- The coordination branch carries the seed commit, so a later fresh clone that materializes the worktree sees `MATERIALIZED` and never seeds again.
- No PRIMARY-partition file exists in the coordination Mission dir (US1.3).
- The coordination branch carries a commit with the `Spec-Kitty-Coordination-Seed: <mission_id>` trailer, unless the seed commit was refused (see Errors). In that case the next seed attempt re-commits the seed with the trailer.

## Errors

| Code | Condition | State after |
|------|-----------|-------------|
| `COORD_SEED_FORK_REFUSED` (new) | both logs non-empty, and neither event-id sequence is a prefix of the other | unchanged. The message names both paths, both refs, the first diverging event id on each side, and the reconcile steps: inspect with `spec-kitty doctor decisions`; keep the coordination log; re-open any root-only decisions with `spec-kitty agent decision open ...`; then remove the root copy. |
| `STATUS_LOCK_HELD` | lock timeout | unchanged |
| commit refusal (`PROTECTED_BRANCH_REFUSED` on the coordination ref, …) | step 9 refused | Mission dir present and uncommitted (records are not lost). The triggering write proceeds. A loud warning names the Mission, the refused ref and the reason. The next seed attempt re-commits it with the trailer: the next COORD write finds the seed pending (a seed commit is **pending** iff the coordination branch history has no `Spec-Kitty-Coordination-Seed: <mission_id>` trailer **and** the coordination tip has no COORD-kind blob under the Mission dir, i.e. the Mission dir is wholly untracked, which only a refused seed leaves. A never-seeded pre-fix MATERIALIZED Mission (#5519 shape) has committed COORD blobs at the tip, so it never matches) and retries the commit before its own write. The commit router is not changed. If the ref is still protected, the warning repeats. Reported in `SeedReport.warnings` (spec edge case "Refused seed commit"). |

## Compatibility

- Pre-fix Missions heal at their first COORD write. Their history on the target branch is untouched.
- A Mission already forked and `MATERIALIZED` (the #5519 shape) never reaches the seed, so it is not locked out. `doctor decisions` reports it.
