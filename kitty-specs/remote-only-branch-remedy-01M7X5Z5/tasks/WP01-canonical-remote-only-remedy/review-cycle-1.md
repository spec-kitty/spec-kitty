---
affected_files: []
cycle_number: 1
mission_slug: remote-only-branch-remedy-01M7X5Z5
reproduction_command:
reviewed_at: '2026-11-20T19:49:52Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review, cycle 1: changes requested (reviewer: claude::reviewer-renata)

## Blocking

### B1 (high). The printed fetch + branch pair does not run in a single-branch or shallow clone
`remote_only_steps` prints `git -C <root> fetch <remote> <b>`, then `git -C <root> branch <b> <remote>/<b>`.
When `remote.<remote>.fetch` does not cover `refs/heads/<b>`, the fetch writes only FETCH_HEAD, creates no
`refs/remotes/<remote>/<b>`, and the printed branch step fails. This affects `git clone --single-branch` and every
`git clone --depth N` (shallow implies single-branch), which is common in CI.

Reproduced:

    git init -b main src; (cd src; git commit --allow-empty -m a; git branch kitty/mission-x-coord)
    git clone --single-branch --branch main src clone
    git -C $PWD/clone fetch origin kitty/mission-x-coord      # rc 0, "-> FETCH_HEAD" only
    git -C $PWD/clone branch kitty/mission-x-coord origin/kitty/mission-x-coord
    # fatal: not a valid object name: 'origin/kitty/mission-x-coord'  (rc 128)

The suite already has this exact case: `test_single_branch_clone_remote_only_coord_branch_is_not_deleted`
(test_coord_branch_remote_probe_4979.py). It was re-pinned to the new text but only checks substrings, so it now
pins a remedy that does not work on its own fixture. The old text at least said "(or fix a stale
`remote.origin.fetch` refspec)"; the new one drops that, so this case gets worse.

Suggested fix, which keeps the operator's order and the resolved remote: give the fetch an explicit destination,
`git -C <root> fetch <remote> <b>:refs/remotes/<remote>/<b>`. Verified: on the same single-branch clone this
creates the tracking ref, and the printed `git branch <b> <remote>/<b>` then succeeds. If you think this changes the
binding form the operator ruled on, ask the operator instead of keeping the broken pair.
Pin it: in the 4979 single-branch test (or a new one), run the printed steps with `shlex.split` and assert
that the local branch exists afterwards, the same way the 5113 round-trip test does.

## Non-blocking (note in the tracer, or fix if cheap)

- N1 (low). `git -C <root>` puts the path in the text unquoted. A root with spaces gives a command that does not
  copy-paste. This was already true in the doctor text, but the builder is now the one owner, so quoting with
  `shlex.quote` there would fix all three sites. Branch names with slashes are fine (checked).
- N2 (info). After the red commit, the red test's no-tracking-ref case was relaxed from `fetch coord-remote <b>`
  to `fetch origin <b>` plus the "if origin does not hold the branch…" hint. The NFR-002 design choice and the
  fixture's template `origin` explain this, and I accept it. In that fixture the printed fetch fails loudly on
  `origin`, and the hint names `coord-remote`.
- N3 (info). The remote arm no longer prints the manual `git worktree add` fallback. This is fine because the doctor
  command is the follow-up, but say so in the tracer.

## Verified (PASS)
- The red commit fails on the base: e44b8c61's test file run against the 9b4472ae source gives 2 failed.
- `coord_remedy.py` imports only stdlib, `kernel.git.remote` and `kernel.git.runner`, and contacts no remote:
  `configured_remotes`, `resolve_remote` and `rev-parse` are local reads.
- All three sites delegate to the builder. The parity test compares against the builder's output, not a literal.
  The only `origin` literals left in `src/` are out of scope: `policy.py:140` (#7726, C-005),
  `consolidation/preflight.py:125` and `tasks_parsing_validation.py:777`.
- The 5113 re-pins keep their intent. The round-trip still executes the printed steps, and pruning the tracking
  ref keeps the three-step form covered.
- Anti-pattern checklist: 1 dead code PASS, 2 synthetic fixture PASS, 3 silent empty return PASS (the
  GitCommandError→False case is documented), 4 FR coverage PASS (FR-001..005), 5 frozen surface N/A,
  6 locked decision PASS, 7 shared files N/A (WP02 does not touch these files), 8 fragility PASS.
- Commands run:
  - targeted 9-file suite: 153 passed
  - test_layer_rules + test_remote_contact_owner: 121 passed
  - ruff check, ruff format --check --force-exclude, C901 and mypy on the touched files: all clean
