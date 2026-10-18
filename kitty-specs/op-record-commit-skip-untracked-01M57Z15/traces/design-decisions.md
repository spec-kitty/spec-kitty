# Design decisions

- **[2026-10-18][specify] Operator: keep the current-branch commit, but skip it when `kitty-ops/` is untracked or ignored.** Rejected: disk-only by default with an opt-in setting; a dedicated `refs/spec-kitty/ops` ref; committing only on the primary branch. The "dogfood opt-in" answer is satisfied by construction, because this repository tracks Op records. Disposition: binding for this Mission. The alternatives are open decisions in the PR (#6410).
- **[2026-10-18][specify] Resolve the primary branch with `bias=False`.** Feature-branch bias would make the checked-out topic branch "primary" in an origin-less repository, and that would defeat the predicate. Disposition: superseded by the post-spec squad fold below (an own resolver; the `bias=False` fallback still returns the current branch).
- **[2026-10-18][specify] Post-spec squad (reviewer-renata) folded.** Five MAJOR findings were folded:
  - an own primary resolver, because the `bias=False` fallback returns the issue branch;
  - a predicate that matches only ULID-shaped records;
  - `check-ignore --no-index`;
  - fixture rework;
  - the doctor's human output.

  Four MINOR findings were folded: the third caller, the NFR bound, the stale-local-ref OR check, and the doc drift. Disposition: fixed in spec.
- **[2026-10-18][implement] Tracked decision carried as a small dataclass, not a bool.** The plan's `op_commit_skip_reason(..., tracked: bool | None)` could not name the primary branch in the reason. Disposition: `PrimaryTracking(tracked, primary)` from `probe_primary_tracking`; the executor caches it per instance and only caches a successful probe, so a probe failure is retried on the next close.
- **[2026-10-18][implement] Probe failure is a skip, never a commit.** An undecidable question must not turn into an unwanted commit; `_op_commit_skip_reason` catches `OpCommitProbeError` and returns a reason naming it.
- **[2026-10-18][closeout] Pre-PR squad folded.**
  - Correctness lens (debugger-debbie, BLOCKER): the protected-main refusal passed the guard's message through, and that message advises the forbidden override. Now sanitized to `protected branch '<b>'`.
  - Correctness lens, also folded: detached HEAD now skips before it refuses; a dangling `origin/HEAD` falls through to the ladder; `ValueError` from git is treated as a probe error.
  - Boundary lens (architect-alphonso, BLOCKER): `test_git_path_listing_owner` failed on a raw `ls-tree`. It now uses `kernel.git.listing.tree_paths`.
  - Boundary lens, also folded: the ladder reuses `COMMON_PRIMARY_BRANCHES`; added an ADR 2026-10-13-2 amendment for skipped (uncommitted) records and a branch-target routing note.
  - Disposition: fixed.
- **[2026-10-18][closeout] Kept a pinned duplicate of the Op-record regex in `coordination/coherence.py`.** Importing it would add the first `coordination -> invocation` edge. Disposition: kept duplicate; a later move to `invocation/writer.py` is noted in the PR.
- **[2026-10-18][closeout] Linked worktree: the Op record commit lands on the repository root checkout's branch.** This happens because `repo_root` resolves to the main checkout, and it predates this change. Disposition: deferred, noted in the PR.
