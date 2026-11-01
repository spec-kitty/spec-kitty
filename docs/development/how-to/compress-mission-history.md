---
title: 'Compress mission history: path-bucket snapshot-chain recipe'
description: 'The path-bucket git commit-tree recipe for compressing a noisy mission branch into a clean, reviewable history with a proven tree-parity guarantee, and why not git rebase -i.'
doc_status: active
updated: '2026-08-15T00:00:00Z'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/development/how-to/pr-landing.md
- docs/development/how-to/review-gates.md
kind: How-To
---
# Compress mission history: path-bucket snapshot-chain recipe

**Audience**: Maintainers who need to turn a noisy mission branch (dozens of
bookkeeping commits — planning notes, status transitions, claim/review
churn) into a clean, reviewable history before a PR lands.

**When to apply**: This is **not a default landing step** — mission history is
generally good, and folds are one commit each for lineage
([pr-landing.md §5](pr-landing.md#5-folds-remediation-commits-on-the-contributor-branch)).
Compress only when a branch genuinely carries noisy admin churn that drowns
the handful of meaningful commits, and only **before** the operator merges —
once a PR is rebase-merged its commits are individually on `origin/main` and
compressing would mean force-pushing `main`, which is forbidden.

## Why not `git rebase -i`

Mission branches interleave planning-artifact edits (`kitty-specs/*/spec.md`,
`plan.md`, `tasks.md`, `status.events.jsonl`) with code and doc commits across
many phase boundaries. Reordering those with `git rebase -i` produces a
conflict storm — the same `kitty-specs/` files are touched by nearly every
commit in the branch, so reordering forces a manual conflict resolution at
almost every step, and `rebase -i` is also unavailable in some non-interactive
harnesses this repo's agents run in.

The alternative used here works by **partitioning by path, not by
reordering**: build a small number of new commits, each taking the branch's
**final** state for one set of paths. Because every new commit takes the
already-final content, there is nothing to merge and nothing to conflict —
the recipe is mechanical, not interactive.

## The recipe

1. **Snapshot and back up.**

   ```bash
   FINAL=$(git rev-parse HEAD)
   git branch -f backup/<slug>-pre-history-compress HEAD
   ```

   The backup branch is the recovery path if anything below goes wrong —
   keep it until the tree-parity proof in step 4 has been verified.

2. **`git reset --mixed <merge-base>`** — keep the working tree, drop the
   commit history back to the branch's base:

   ```bash
   BASE=$(git merge-base upstream/main HEAD)
   git reset --mixed "$BASE"
   ```

   `--mixed` (the default) unstages everything but leaves every file in the
   working tree at `$FINAL`'s content — nothing is lost, only the commit
   history is rolled back. (`--soft` also works and additionally leaves
   everything staged; `--mixed` is used here so each bucket below stages
   explicitly, which keeps the buckets honest — you cannot accidentally
   commit a path you did not intend to touch.)

3. **Re-stage and commit by path bucket** — one commit per concern, into a
   clean narrative. Typical buckets in this repo:

   | Bucket | Paths |
   |---|---|
   | Mission admin | `kitty-specs/*/meta.json`, `status.events.jsonl`, `tasks/.gitkeep`, `tasks/README.md` |
   | Mission planning substance | `spec.md`, `plan.md`, `tasks.md`, `decisions/`, `occurrence_map.yaml` |
   | Documentation | `docs/` |
   | Code + tests | `src/`, `tests/` |

   For a WP-structured mission, bucket **per WP** instead (or in addition):
   each WP's owned files become one commit, so the compressed history still
   shows the mission's real work-package seams.

   ```bash
   git add kitty-specs/<mission>/meta.json kitty-specs/<mission>/status.events.jsonl \
     kitty-specs/<mission>/tasks/.gitkeep kitty-specs/<mission>/tasks/README.md
   git commit -m "chore(<mission>): mission admin bookkeeping"

   git add docs/development/how-to/<new-page>.md docs/development/how-to/pr-landing.md
   git commit -m "docs(<scope>): <summary>"

   # ...repeat per bucket, until every changed path has been staged and committed
   ```

   Keep the original rationale prose in each grouped message, preserve every
   `Co-Authored-By` trailer that was on the commits it summarizes, and end
   the message with a `History note: squashed from <shas>` line so the
   pre-compression commits stay traceable from the compressed one.

4. **Tree-parity proof** — the whole safety argument for this recipe in one
   command:

   ```bash
   NEW_HEAD=$(git rev-parse HEAD)
   git diff "$FINAL" "$NEW_HEAD"    # MUST be empty
   ```

   An empty diff proves the compressed history's final tree is byte-identical
   to the original branch's final tree — the recipe changed *how the history
   is told*, not *what the branch contains*. If this diff is **not** empty,
   stop: some path was double-staged, mis-bucketed, or dropped — fix the
   bucket commits (or reset to the backup branch and start over) before
   proceeding. Never force-push a compressed history that fails this check.

   A second check catches leakage between buckets: the per-commit changed-file
   counts should sum to the total changed-file count, with no path appearing
   in more than one bucket commit.

   ```bash
   git diff --stat "$BASE" "$FINAL" -- <bucket-pathspec>   # per bucket
   git diff --stat "$BASE" "$FINAL"                        # total
   ```

## Handling deletions and renames

`git add <pathspec>` already stages **deletions** of tracked files within the
pathspec (git ≥ 2.0), so the simple recipe handles a deleted file correctly as
long as that path falls inside a bucket's pathspec. The one case to watch is the
**explicit-file-list** variant of step 3 (`git add fileA fileB …`): if you hand-list
paths, add `-A` (`git add -A <pathspec>`) or you may omit a now-absent deleted file.
**Renames that cross bucket boundaries** are the genuinely awkward case (the old
path lands in one bucket, the new path in another). Check first:

```bash
git diff --diff-filter=DR --name-status "$BASE" "$FINAL"   # deletions/renames
```

If a cross-bucket rename exists, build that bucket's commit with `git commit-tree`
against a **cumulative** temporary index — each commit's tree = the previous
commit's tree plus this bucket's final paths — so the *terminal* commit's tree
reconstructs the full `$FINAL` tree (not just the last bucket):

```bash
export GIT_INDEX_FILE=$(mktemp)          # scratch index, cumulative across buckets
git read-tree "$FINAL"^{tree}            # seed the full final tree
TREE=$(git write-tree)
git commit-tree "$TREE" -p <prev-new-commit> -F msg.txt   # → next commit sha
```

Each commit's tree is built from `$FINAL` cumulatively, so the *terminal* commit
already equals `$FINAL` — then **re-run the step-4 tree-parity check**
(`git diff "$FINAL" "$NEW_HEAD"` must be empty), which is the real guarantee
regardless of how the trees were built.
This matters only once a rename or deletion means "the final content of this
bucket's paths" is not simply
"whatever is currently on disk at those paths."

## After compression

```bash
git push --force-with-lease <remote> <branch>
```

See [push discipline](pr-landing.md#9-push-discipline) for the lease-sha
mechanics before force-pushing. Keep the `backup/<slug>-pre-history-compress`
branch until the PR has landed — it is the recovery path if a later step
reveals the tree-parity proof was checked against the wrong `$FINAL`.

## See also

- [pr-landing.md §4](pr-landing.md#4-classify-every-red-check) — classifying
  reds before compressing, including the true-base note for multi-WP lanes.
- [pr-landing.md §5](pr-landing.md#5-folds-remediation-commits-on-the-contributor-branch) —
  when landing folds (not compression) is the right tool instead.
