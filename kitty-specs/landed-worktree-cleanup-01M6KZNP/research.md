# Research: Landed worktree cleanup and upgrade worktree scope (#7173)

Phase 0 record. All cited lines were re-verified on `origin/main` at `dc7a3ca5` (2026-11-04).

## 1. Code grounding

| Claim (issue) | Verified location | Finding |
|---------------|-------------------|---------|
| upgrade auto-commits each worktree | `src/specify_cli/cli/commands/upgrade.py:836-847` (no-migrations path) and `:2196-2207` (migrations path) | Confirmed. Both pass `auto_commit=should_auto_commit_for_worktree(...)`. |
| Policy visible only in `--plan-json` | `upgrade.py:1899` `commit_policy.worktrees_enabled` | Confirmed; the normal preview names no worktree. |
| Worktree scope | `src/specify_cli/upgrade/runner.py:164-195` `_is_integrating_worktree` / `_worktrees_to_upgrade` | Only `.worktrees/` is scanned; Mission (`kitty/mission-…`) and detached worktrees are already skipped (#5457). The exposure is non-Mission branches under `.worktrees/`, i.e. landing worktrees. |
| Tests pin the commit | `tests/upgrade/test_upgrade_worktree_commit.py` (`NON_INTEGRATING_PREFIX = "wip/"`) | Confirmed. |
| No read surface | `spec-kitty doctor workspaces` (`_workspace_husk_doctor.py`) | Reports husks only. |

## 2. Red-first reproduction (temp repository, CLI from this checkout)

Script: two landing worktrees under `.worktrees/` (one rebase-merged into `main`, one open with an unpushed commit), version stamp 3.2.1.

- `spec-kitty upgrade --dry-run`: the preview lists migrations only; no worktree is named.
- `spec-kitty upgrade --yes`: a new commit `chore: apply spec-kitty upgrade changes (3.2.1 -> 4.0.0rc8)` landed on **both** `land-merged` and `land-open` (the latter on top of its unpushed commit).
- `spec-kitty doctor workspaces`: "No workspace husks found.", exit 0; the landed worktree is not mentioned.
- Fixture lesson: a cherry-pick made in the same second reproduces the original SHA, so tests must force a different committer date to model a real rebase merge.

## 3. Architectural alignment

- **Decision**: reuse `lanes/lane_tip.is_absorbed` legs 2-3 (ancestor; `git merge-tree --write-tree` no-op) with `base=None`. **Rationale**: the same proof `DESTROYED_LANE` relies on; covers merge, rebase and squash landings offline. **Alternatives**: `git cherry` (misses squash merges); tree equality with `origin/main` (wrong once main moves on).
- **Decision**: removal and branch deletion route through `git/destructive_guard.py`. **Rationale**: `tests/architectural/test_destructive_op_routing.py` forbids any other `worktree remove --force` / `branch -D` site, with no allowlist. Two operator rulings extend the guard: a no-force removal mode, and a `LANDED` intent that records the tip under `refs/spec-kitty/discarded/<branch>` when the branch's commits exist on no other ref (rebase merge + deleted remote head).
- **Decision**: residue classifier `coordination.coherence.NothingIsResidue`. **Rationale**: an operator landing worktree is not Mission-scoped; nothing in it is disposable. `TOOL_OWNED` would make everything disposable and is confined by the gate.
- **Decision**: guard's dirty predicate with `treat_untracked_as_dirty=True`. Ignored paths (`.venv`, build output) stay obstruction-gated, so a landed worktree with a virtualenv is still removable, which is where the reported 36 GB went.
- **Decision**: Mission ownership via `parse_mission_slug_from_branch` (the predicate upgrade already uses). Mission lane and coordination worktrees are report-only; `consolidate`, `retain_worktrees`, `DESTROYED_LANE` / `LANE_WORK_TIP_UNKNOWN` keep owning them.
- **Decision**: nothing touches the Migration Ledger. The upgrade change is CLI selection, not a migration; no `order_manifest.txt` entry.
- **Decision**: no hosted surface, no fetch. A stale `origin/<primary>` can only under-report.
- **Decision**: process proof by scanning `/proc/<pid>/cwd`; where `/proc` is unavailable the verdict is "unproven" and nothing is removed.

## 4. Related issues and in-flight work

| Item | Relation |
|------|----------|
| #5457 (closed) | Integrating worktrees skipped by upgrade; reused predicate. |
| #5712, #5747 (open) | Upgrade worktree scope for Mission branches; not changed here. |
| #3970 (open) | Machine-readable cleanup postcondition report; `--json` here is compatible in spirit, not a fix. |
| #4041 (open) | Archived Mission keeps its coordination worktree; out of scope (Mission-owned is report-only). |
| #6450, #6661 (closed) | Earlier worktree-dirt and linked-worktree sweep issues; no overlap left. |
| PR #7094, PR #7116 (open) | Touch `upgrade.py`; keep this diff local to the worktree paths to limit conflicts. |

## 5. Tidy-first

- Add a full `git worktree list --porcelain` parser to `kernel/git/listing.py` and route `status/doctor_husks.registered_worktree_paths` through it, behaviour-preserving, as the first commit. About ten other hand-rolled parsers exist; migrating them is out of scope (campsite note only).

## 6. Supply chain

No dependency is added, upgraded or removed; DIRECTIVE_051 controls not triggered.
