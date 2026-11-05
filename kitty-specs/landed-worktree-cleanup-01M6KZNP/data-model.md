# Data Model

## WorktreeEntry (kernel, from `git worktree list --porcelain`)

| Field | Type | Notes |
|-------|------|-------|
| path | Path | as reported |
| head | str \| None | commit SHA; None for a bare entry |
| branch | str \| None | short name; None when detached or bare |
| detached | bool | |
| bare | bool | |
| locked | bool | `locked` line present (reason ignored) |
| prunable | bool | `prunable` line present |

The first entry is the main worktree.

## WorktreeVerdict

| Field | Type | Notes |
|-------|------|-------|
| path | Path | |
| branch | str \| None | |
| tip | str \| None | |
| verdict | `landed` \| `not_landed` \| `mission_owned` \| `unproven` \| `excluded` | |
| reason | str | stable machine code (see below) |
| detail | str | human text |
| removable | bool | true only for `landed` |
| ignored_paths | list[str] | at most five ignored path names a removal deletes (for example `.venv/`, `.env`), sorted |
| ignored_count | int | all ignored paths a removal deletes; `0` unless the local-state step found the worktree otherwise clean |

Reason codes: `UNCOMMITTED_CHANGES`, `CONTENT_NOT_ON_PRIMARY`, `PROCESS_RUNNING`, `LOCKED`, `PRUNABLE`, `MISSION_LANE`, `PRIMARY_REF_MISSING`, `PRIMARY_UNRESOLVED`, `NESTED_REPOSITORY`, `NO_OWN_COMMITS`, `REFLOG_MISSING`, `DETACHED_OUTSIDE_WORKTREES`, `PROCESS_PROOF_UNAVAILABLE`, `ABSORPTION_UNSUPPORTED`, `MAIN_WORKTREE`, `CURRENT_WORKTREE`, `BRANCH_IN_OTHER_WORKTREE`, `LANDED`. (Amended at closeout, #7173 squad: `PRIMARY_UNRESOLVED`, `NESTED_REPOSITORY`, `NO_OWN_COMMITS`, `REFLOG_MISSING`, `DETACHED_OUTSIDE_WORKTREES`, `detail`, `ignored_paths`, `ignored_count`.)

### Verdict rule (ordered, first match wins)

(Amended at closeout, #7173 squad; source of truth: `src/specify_cli/workspace/landed_worktrees.py` module docstring and `_structural` / `_local_state` / `_absorption` / `_own_commits` / `_after_probe`.)

1. main worktree (`MAIN_WORKTREE`) or the worktree the command runs in (`CURRENT_WORKTREE`) → `excluded`
2. prunable (directory missing) → `excluded` (`PRUNABLE`; git's own `worktree prune` territory)
3. bare → `excluded` (`MAIN_WORKTREE`)
4. detached and outside `<repo>/.worktrees/` → `excluded` (`DETACHED_OUTSIDE_WORKTREES`; spec-kitty's own scratch checkouts)
5. branch is a Mission branch → `mission_owned` (`MISSION_LANE`)
6. locked → `not_landed` (`LOCKED`)
7. local state → `not_landed`: dirty by the guard's predicate (tracked or untracked, `NothingIsResidue`), an index entry flagged `assume-unchanged` / `skip-worktree`, or a status that cannot be read (`UNCOMMITTED_CHANGES`); an ignored path holding a repository store (`.git`, `.hg`, `.jj`, `.svn`, or a bare or renamed git dir) (`NESTED_REPOSITORY`). Other ignored paths are recorded in `ignored_paths` / `ignored_count`.
8. primary branch not resolved from `origin/HEAD` or a common name (`main`, `master`, `develop`) → `unproven` (`PRIMARY_UNRESOLVED`); `origin/<primary>` missing → `unproven` (`PRIMARY_REF_MISSING`); no HEAD → `not_landed` (`CONTENT_NOT_ON_PRIMARY`)
9. tip not absorbed into `origin/<primary>` → `not_landed` (`CONTENT_NOT_ON_PRIMARY`); `AbsorptionUnsupported` → `unproven` (`ABSORPTION_UNSUPPORTED`)
10. a branch whose tip is an ancestor of `origin/<primary>` and whose reflog records no commit → `not_landed` (`NO_OWN_COMMITS`, remove by hand); no reflog → `unproven` (`REFLOG_MISSING`)
11. process proof unavailable → `unproven` (`PROCESS_PROOF_UNAVAILABLE`); a process cwd inside → `not_landed` (`PROCESS_RUNNING`)
12. otherwise → `landed` (`LANDED`)

**Invariant**: only `landed` is ever passed to the guard, and the prune re-evaluates the verdict for that worktree immediately before removing it.

## PruneOutcome

| Field | Type | Notes |
|-------|------|-------|
| path, branch, tip | | |
| removed | bool | |
| branch_deleted | bool | false for detached, or a branch checked out elsewhere |
| kept_ref | str \| None | `refs/spec-kitty/discarded/<branch>` (or `<branch>@<short-sha>` when an earlier, different tip holds that name) when a branch tip no local branch or tag reaches was recorded; `refs/spec-kitty/discarded/detached/<sha>` for such a detached tip (amended at closeout, #7173 squad: remote-tracking refs do not count) |
| recreate | str | `git branch <b> <sha>` or `git worktree add --detach <path> <sha>` |
| refusal | str \| None | guard refusal code when the guard refused |

## WorktreeSelection / WorktreeDisposition (upgrade)

- `WorktreeSelection`: `mode` ∈ {`none`, `named`, `all`}, `named: tuple[Path, ...]`.
- `WorktreeDisposition`: `path`, `branch`, `action` ∈ {`skip_mission`, `skip_not_selected`, `upgrade`}.
- Rule: Mission or detached → `skip_mission` regardless of selection (unchanged #5457); otherwise `upgrade` iff mode is `all` or the resolved path is in `named`.
- A named path that is not a direct child of `.worktrees/` is refused before any write (`UPGRADE_WORKTREE_NOT_FOUND`).
