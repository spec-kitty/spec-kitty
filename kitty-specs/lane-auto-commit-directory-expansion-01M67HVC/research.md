# Discovery: lane auto-commit hands `safe_commit` a collapsed directory (#6750)

Mission: `lane-auto-commit-directory-expansion-01M67HVC` · Issue: spec-kitty/spec-kitty#6750
Discovery actor: pi / implementation sub-agent · 2026-10-30

## Grounding: the defect still reproduces on `main`

Reproduced on this checkout (`main` @ `512567eee7`, spec-kitty 4.0.0rc8) with the
issue's own recipe: a throwaway git fixture on branch `repro-fixture`,
`core.hooksPath` pointing at an **empty** hooks directory, one committed
README, and two untracked files under `.zig-cache/`. Injecting only the
resolver's synthetic workspace boundary and calling the real
`tasks_move_task._mt_commit_lane_deliverables`, nothing else mocked:

```
Warning: could not auto-commit lane deliverables for WP01: safe_commit: commit
14f87b4b1af05b864ccb0b206c821f99d7da2935 landed, but it also carries path(s) the
operation did not request (a pre-commit hook staged them): .zig-cache/one.bin,
.zig-cache/two.bin
HEAD moved: True
committed paths: ['.zig-cache/one.bin', '.zig-cache/two.bin']
status: <clean>
hooks dir: []
```

Three independent facts in one run, each of which the fix must flip:

1. HEAD advanced and both children landed — the commit is not an untouched
   failed attempt, yet…
2. …the collector reported "could not auto-commit", and
3. the error asserted as fact that "a pre-commit hook staged them" while the
   hook directory was empty.

Neither is superseded: `git log -S _lane_deliverable_paths` shows no later fix,
`docs/changelog/CHANGELOG.md` has no entry for #6750, and there is no open or
merged PR mentioning #6750.

## Where the seam is

| Site | File | Today |
| --- | --- | --- |
| Collector status read | `cli/commands/agent/tasks_move_task.py::_mt_commit_lane_deliverables` | `status_entries(worktree_path, untracked=None)` — the repo's `status.showUntrackedFiles` decides, i.e. a new directory arrives as one collapsed `?? dir/` entry |
| Path collection | `…::_lane_deliverable_paths` | forwards each entry's path verbatim — a collapsed entry becomes a **directory** argument |
| Entry validation | `git/commit_helpers.py::preflight_commit` | normalizes each path, checks the `.worktrees/` policy and protection, never asks "is this path a directory?" |
| Post-landing guard | `…::_assert_committed_paths_requested` | compares `git diff-tree` **file** paths against the literal requested set; a directory can never match its children, so it raises `SafeCommitUnrequestedPaths` whose message hardcodes "a pre-commit hook staged them" |
| Collector failure arm | `…::_mt_commit_lane_deliverables` | `except Exception` prints "could not auto-commit", flattening a `SafeCommitRecoveryFailed` (commit landed) into "nothing happened" |

The guard's docstring states the invariant it relies on — "every caller already
expands directories to files before `safe_commit`" — and the public
`safe-commit` CLI honours it (`cli/commands/safe_commit_cmd.py::_expand_arguments`,
#2739 B11), but nothing enforces it for the other raw callers. That is the seam
this mission closes.

## Decisions

- **D1 — Expand in the collector, refuse at the seam.** The collector's job is to
  recover an implementer's finished deliverables, so refusing a new directory
  would trade one dead end for another: expand the untracked entries to the exact
  file set (`untracked="all"`, the same expansion the `safe-commit` CLI already
  performs). Independently, `preflight_commit` refuses any directory argument
  **before** HEAD/index mutation with a truthful files-only message, so a future
  caller cannot re-open the class. Evidence: `_expand_arguments` /
  `_worktree_status_entries` in `safe_commit_cmd.py` already own this expansion
  policy for the CLI; reusing `status_entries(untracked="all")` keeps one
  expansion rule instead of adding a second.
- **D2 — Keep the post-landing guard, fix its attribution.** The guard is the only
  structural detector of a hook that stages files itself (#5903). It must keep
  firing for a real hook-swept path (negative control in the tests) — its message
  stays truthful because after D1 the only remaining cause *is* an external
  stager. `SafeCommitUnrequestedPaths` keeps its type and `error_code` (C-002).
- **D3 — The collector must not describe a landed commit as untouched.** It
  re-raises/renders `SafeCommitRecoveryFailed` as "landed, but …" with the SHA,
  and reserves "could not auto-commit" for a pre-mutation failure.
- **D4 — Ownership sweep of the non-owned collector is out of scope.** See open
  question OQ-1.

## Open questions

- **OQ-1 (maintainer decision, deferred).** The *non-owned* lane collector commits
  every `git status` entry, so an unignored generated tree (`.zig-cache/`, a build
  cache) is swept into the lane commit merely because it is unignored; the owned
  checkout path already refuses out-of-scope files with
  `OWNED_DELIVERABLE_SCOPE_REFUSED` (and `owned_files` matching lives in
  `consolidation/wp_evidence`). Filtering the non-owned set by the WP's
  `owned_files` changes user-visible policy: any stray untracked file would then
  block the `for_review` move (the readiness guard sees a dirty tree) instead of
  being committed. That is a maintainer call about what a lane is allowed to
  contain, not a defect fix, and it is recorded in the PR's `## Deferred` section.
- **OQ-2.** Whether to align the collector's status read with the CLI's cached
  whole-worktree read (one `git status --untracked-files=all` per command) — not
  needed for this fix; the collector reads status once per move already.

## Evidence gathered

- Issue #6750 body (release-source pin `v4.0.0rc7` @ `1b0fe9fc`), incl. the
  bounded reproduction recipe.
- `git/commit_helpers.py` `_assert_committed_paths_requested` (#5903),
  `SafeCommitRecoveryFailed` / `SafeCommitIndexResidue` / `SafeCommitUnrequestedPaths`
  contracts, `preflight_commit` validation order.
- `cli/commands/safe_commit_cmd.py::_expand_arguments` + `_changed_paths_under`
  (#2739 B11 directory contract) and `spec_commit_cmd._refuse_directory_arguments`.
- `cli/commands/agent/tasks_move_task.py::_mt_commit_lane_deliverables`,
  `_lane_deliverable_paths`, `_drop_lane_coord_residue` (#2549), the owned-scope
  guard (#5100).
- Reproduction run recorded above.
