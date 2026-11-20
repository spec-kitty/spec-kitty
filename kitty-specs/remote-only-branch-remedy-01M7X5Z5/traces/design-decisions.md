# Design decisions

- 2026-11-20 — No `CoordState.REMOTE_ONLY` member: 49 uses / 14 probe callers; the split is decided at the single ref-read failure point instead.
- 2026-11-20 — Remote-only error is a subtype of the unreadable-ref error so ~60 existing catch/relay sites keep working and `next` relays the new code.
- 2026-11-20 — Classification only on the failure path (NFR-001), keyed on the local head not resolving; a corrupt local ref keeps the unreadable code.
- 2026-11-20 — `policy._missing_destination_remedy` (#7726) left as is (different semantics).
- 2026-11-20 — Builder follow-up is passed verbatim (a backticked command or a clause); an earlier draft guessed whether to backtick it, which was fragile.
- 2026-11-20 — Remedy steps carry `git -C <root>` so they run from anywhere; re-pinned 5113/4979 assertions accordingly (5113 round-trip now prunes the tracking ref to keep the three-step form covered).
- 2026-11-20 — The prefix fixture carries a second remote (`origin`, from the git template) besides `coord-remote`; with no tracking ref, local config cannot tell which holds the branch. Added an honest 'if origin does not hold the branch…' note instead of a network probe.
- 2026-11-20 — Review cycle 1 B1: the fetch step now names its destination (`fetch <remote> <b>:refs/remotes/<remote>/<b>`) so it works in single-branch/shallow clones, where a bare fetch writes only FETCH_HEAD; the 4979 single-branch test now runs the printed steps. N1: the root is `shlex.quote`d.
- 2026-11-20 — Review N3: the remote-only arm no longer prints the manual `git worktree add` fallback. Deliberate: once the printed `git branch` step runs, the branch is a local head and the doctor follow-up (`--fix`) materializes the worktree; the local-head arm keeps the manual fallback for when the doctor cannot.
- 2026-11-20 — Review N2 (accepted): the red test's no-tracking-ref case asserts the resolved default remote plus the "if origin does not hold the branch" hint, because the fixture carries a template `origin` remote.
