# Research: `doctor workspaces --remote` (#7214)

## Evidence

**Reproduction (2026-11-05, against the landed check as merged with PR #7196).**
A bare `upstream.git` holds the rebased landing commit, a bare `origin.git` still
sits at the pre-landing `main`, and a git worktree `land-7214` holds the commit:

```
tip=4bd0e3f4ce289fa305d5f972ca7e13c490604980 upstream=4bd0e3f4ce2… origin=32929decaade…
primary_ref: refs/remotes/origin/main
  main      excluded    MAIN_WORKTREE
  land-7214 not_landed  CONTENT_NOT_ON_PRIMARY | 4bd0e3f4ce28 has work not on refs/remotes/origin/main
```

The commit *is* on `upstream/main`; the verdict is wrong only because the proof
reads one hardcoded ref. `--prune` therefore removes nothing.

**Where the ref is read.** `_context` in `src/specify_cli/workspace/landed_worktrees.py`
builds `primary_ref = f"refs/remotes/origin/{primary}"`, `_primary_resolved`
consults `refs/remotes/origin/HEAD`, and `_absorption` / `_own_commits` read
`ctx.primary_ref`. `prune_landed` re-derives the context, so the remote has to
travel with it or the re-assessment would check a different ref than the report.

**The runbook already knows the remote is not always `origin`.**
`docs/development/how-to/pr-landing.md` steps 2-3 fetch the PR and `main` from
`upstream`; step 12 said `git fetch origin` and recorded the fork limit as
"remote selection is tracked in #7214".

**The kernel already owns the remote vocabulary.** `kernel.git.remote` exports
`configured_remotes(cwd)` and `tracking_ref(remote, branch)`, so this Mission
reuses them rather than minting a second reader. `describe_remote_head` answers
the `<remote>/HEAD` question by contacting the remote (`git remote show`), which
the check must never do, so the local symbolic-ref read stays in the workspace
module with that note.

**No test asserts the two `unproven` detail strings** (`PRIMARY_REF_MISSING`,
`PRIMARY_UNRESOLVED`) — the assessment suite asserts the `(verdict, reason)`
pair only, so the message text can gain the correct remedy without touching it.

## Decisions

**D1 — explicit `--remote <name>`, default `origin`.** Of the issue's three
options, this is the only one that neither guesses nor weakens the proof.
Auto-detecting "the remote that points at the canonical repository" means
deciding canonicality from names/URLs, which is exactly the ambiguity that made
the maintainer follow the runbook in the first place; and "accept a tip any
remote-tracking ref contains" lets a stale fork's `origin/main` vouch for a
landing that never happened upstream. An explicit option keeps one named
remote's single primary ref as the authority, keeps the default
byte-compatible, and makes the flag itself the documentation.

**D2 — the primary branch name comes from the named remote's `HEAD`.** A fork
clone's `origin/HEAD` may name the fork's default branch, which is not
necessarily the canonical trunk; and `resolve_primary_branch` is `origin`-biased.
So: `refs/remotes/<remote>/HEAD` first when it is a symbolic ref, else the
existing resolver for the *name*, and the "only a guess" refusal stays unless the
name is a common primary name or the named remote's `HEAD` vouches for it.

**D3 — an unconfigured remote is an error, not a report.** `--remote upstrem`
must not produce "every worktree unproven" — that is the failure mode the issue
is about. The assessment returns `error` naming the configured remotes, the CLI
prints it and exits 1. A repository with *no* remote keeps the older answer,
because there is no name to compare and an existing test pins that behaviour.

**D4 — message text gains the remedy for the remote it names.** `PRIMARY_REF_MISSING`
becomes `refs/remotes/<remote>/<primary> does not exist locally: run `git fetch <remote>``
and `PRIMARY_UNRESOLVED` becomes `… set it with `git remote set-head <remote> <branch>``.
The old text advised `origin` unconditionally, i.e. the wrong remote in exactly
the clone under discussion. No verdict, reason, exit code or JSON key changes.

**D5 — the printed prune remedy carries the remote.** `remove with: spec-kitty
doctor workspaces --prune --remote upstream`, because a copy-pasted `--prune`
without the flag is the same silent no-op this Mission fixes.

**D6 — the assessment's own `to_json()` shape is not extended.** It is pinned by
`landed-worktree-cleanup-01M6KZNP`'s `data-model.md`; the remote travels on the
`WorktreeAssessment` attribute and in the CLI payload, so a sibling Mission's
machine contract is not reopened from here (the same reasoning that deferred
#7215).

## Open questions

- **Should `upgrade`'s worktree selection get the same option?** Out of scope:
  #7215 tracks that surface, and it does not prove a landing.
- **Auto-detecting a fork→`upstream` default** stays a product decision the
  operator may take later; this Mission deliberately does not add it (D1).
