# Research: `doctor ops` across every checkout (#6661)

Grounded on `512567eee7` (main), 2026-10-30. Issue #6661, remaining scope after
#6664 landed the mission-step half.

## Reproduction (evidence)

A scratch repository with one committed seed commit, a linked worktree `lane` on
branch `topic`, and a started-only record written by hand at
`lane/kitty-ops/01KTBE0RQY9XKTV0PE49PJDMRM.jsonl`:

```
$ cd primary && spec-kitty doctor ops --json
[]
exit=0
$ cd ../lane && spec-kitty doctor ops --json
[]
exit=0
```

Direct calls on the same tree:

```
list_orphan_ops(primary)                      -> []
locate_op_record_root(primary, <id>)          -> /tmp/ground6661/lane     # already finds it
list(_repository_checkouts(primary))          -> [primary, lane]           # already enumerates
```

So the shared enumeration and the custody lookup both already see the lane; only
the sweep does not use them. Confirms the issue text and its triage comment
(`doctor/ops.py:43-51`, `:173`).

## Code survey

- `src/specify_cli/doctor/ops.py`
  - `list_orphan_ops(repo_root)` globs `<repo_root>/kitty-ops/*.jsonl` and reads
    the closure spine under the same root (`closed_invocation_ids(repo_root)`).
  - `close_stale_ops(repo_root, ...)` enumerates through `list_orphan_ops`, then
    builds one `ProfileInvocationExecutor(repo_root, propagator=...)` with no
    `record_root`, so `complete_invocation` reads/writes root-checkout paths.
  - Per-op outcomes already handled: `closed_abandoned`, `already_closed`,
    `parse_warning`, `error`, and `commit` = `committed` /
    `not_committed:<refusal>` / `skipped:<reason>`.
- `src/specify_cli/invocation/op_custody.py`
  - `_repository_checkouts(project_root)` yields every checkout from
    `git worktree list --porcelain`, resolved. Private today; `locate_op_record_root`
    is its only caller.
  - `resolve_op_record_root` / `locate_op_record_root` are the #6564 custody pair.
- `src/specify_cli/invocation/executor.py`
  - `ProfileInvocationExecutor(repo_root, ..., record_root=None)`; `record_root`
    defaults to `repo_root`. The writer, the closure spine, the auto-commit and the
    doctor-sweep closed-id cache all key off `record_root`; the profile registry and
    the glossary chokepoint's governance read stay on `repo_root`.
- `src/specify_cli/session_presence/open_ops.py`
  - Calls `list_orphan_ops(repo_root)` on every session start/stop. Its module
    docstring makes the contract explicit: "scan-only, makes no git calls, must add
    < 0.5 s at 1,000 Op files". A performance test pins the budget; a test comment
    says "no git calls". **This is the hard constraint on the fix.**
- `src/specify_cli/cli/commands/doctor.py`
  - `ops` renders `path.relative_to(repo_root)` in both the table and the `--json`
    payload, which raises `ValueError` for a record outside the root checkout.
  - `_run_ops_sweep` owns exit codes (`1` on errors or fresh Ops left).
- `_op_git.py` test helpers already build real repositories, linked worktrees and
  seed ULID records (`run_git`, `track_op_record_on_current_branch`).

## Decisions

- **D1 — keep `list_orphan_ops` single-checkout.** Folding `git worktree list` into
  it would put a subprocess on the session-start path and silently widen a surface
  with a published latency budget. The doctor keeps the checkout-aware enumeration;
  session presence keeps the root-only scan, and both the docstring and a test say so.
- **D2 — one enumeration owner.** Promote `op_custody._repository_checkouts` to a
  public `repository_checkouts(project_root)` and use it from `doctor/ops.py`. A
  second walk (even a five-line one) is how custody and the sweep drift apart.
  Fallback when git is absent/failing is `[project_root]`, which is today's behavior.
- **D3 — one executor per owning checkout.** The owning checkout of a record is its
  `kitty-ops/` parent's parent, so `close_stale_ops` can derive it from the record
  path: `ProfileInvocationExecutor(repo_root, record_root=checkout, propagator=...)`.
  Governance stays on `repo_root`; the spine append, the auto-commit and the
  closed-id cache land where the record lives. Executors are cached per checkout so
  a sweep still reads each spine once (the #4424 linear-time property).
- **D4 — path reporting without schema change.** Report each record relative to the
  project root with `os.path.relpath`, so a worktree record renders
  `../lane/kitty-ops/<id>.jsonl`. Root records keep `kitty-ops/<id>.jsonl`, the JSON
  payload stays `[{"path": ...}]`, and no machine-local absolute path is printed.
- **D5 — order.** Project root first, then `git worktree list` order, and file-name
  order within a checkout; de-duplicate by resolved checkout path so a nested or
  repeated checkout cannot list or close a record twice.

## Open questions resolved before planning

- *Does the fix need a new flag or `--checkout` selector?* No. `doctor ops` is a
  repository-wide sweep by definition; the checkout set is discovered, not chosen.
- *Should the sweep prune or skip a worktree listed by git but gone on disk?* Skip:
  there is no `kitty-ops/` to read. Pruning is `git worktree prune`'s job and is out
  of scope.
- *Does `--close-stale` need the pre-write admission check (#6664)?* The executor
  already enforces it inside `complete_invocation`; the sweep just has to hand it a
  correct `record_root`, which D3 does.
- *What about `logged` closure reads for a record whose checkout is the lane but
  whose spine was written by an older CLI into the root?* An older CLI could not
  have written a lane record at all (pre-#6564 every record went to the root), so
  record and spine are together. No cross-checkout spine lookup is needed.
