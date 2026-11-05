# Research: what git actually does around a pruned worktree's reflogs

Measured on git 2.43 in throwaway repositories while designing the fix for
#7211. Each point decided a piece of the implementation.

## 1. Both reflogs really disappear with the prune

`git worktree remove <path>` deletes `.git/worktrees/<id>/`, including
`logs/HEAD`; `git branch -D <branch>` deletes the branch reflog. A commit made
while the worktree was detached, and later left behind, is reached only by
`logs/HEAD`; one dropped with `reset --hard` only by the branch reflog. The
issue's reproduction confirms both.

**Decision**: read both reflogs before anything is removed, and write the
records before the first destructive command.

## 2. `git rev-list <shas> --not --all` is the reachability test

The issue proposes it, and it answers exactly "is this commit reached by any
ref right now" without walking anything else. Candidate entries come from the
reflogs, so their ancestors are covered transitively.

**Decision**: one `rev-list` per prune, intersected with the candidate entries
so an ancestor that is not itself an entry cannot be mistaken for one.

## 3. `--exclude=refs/heads/<branch>` is not reliable

The first design tried `--not --exclude=refs/heads/<branch> --all` so the branch
about to be deleted counted as gone. Measured: with a linked worktree present,
`git rev-list --exclude=refs/heads/main --all` still lists main's commits, and
`--exclude` with `--branches` behaves the same. Even where it works it is
unnecessary: the deleted branch's tip is protected by the landing proof and then
by the guard's discarded ref, and a reflog-only commit is not an ancestor of
that tip.

**Decision**: plain `--not --all`. The review round that found this also turned
it into a test of the rule itself.

## 4. `git cherry` marks patch-equivalent commits `-`, and omits merges

`git cherry <primary> <sha>` prints one `- <sha>` line per commit whose patch is
already upstream, `+ <sha>` otherwise. It emits nothing for a merge, and it can
print only `-` lines for a merge's non-merge ancestors.

**Decision**: all-`-` output skips the record, anything else keeps it; and a
`rev-list --merges <sha> --not <primary>` probe answers "not provable" first.
Without that probe, a merge carrying an edit of its own (both parents' patches
on the primary) was dropped — found by the independent review, reproduced as a
regression that fails when the probe is disabled.

## 5. Rebase landings would otherwise churn

This repository lands by rebase, so a landed branch's reflog holds the
pre-rebase commits, which are patch-equivalent to the rebased ones on
`origin/main`. Recording a ref per superseded commit would pin those objects
forever and slow every `for-each-ref`.

**Decision**: the patch proof is the one narrowing; it can only decline to
duplicate something, never drop something it cannot prove.
