---
affected_files: []
cycle_number: 3
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-25T22:32:00Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review cycle 3 (claude::reviewer-renata): REJECT

Commit reviewed: 63b4f6c3.

## The three cycle-2 findings: all resolved

- **Explicit single_branch: resolved.** Probe case A now returns `main`, today's behaviour.
- **Remote-only branch: resolved.** Probe case B now raises `PLANNING_CHECKOUT_MISSING`, and the message starts with `git branch <b> origin/<b>`.
- **refname:short: resolved.** The probe now lists full refnames. The new tag test is non-vacuous: with a same-named tag, `for-each-ref --format=%(refname:short)` prints `heads/kitty/mission-x`, so the old code would fail that test.

Checks: 33 tests pass, and ruff, C901, format and mypy are clean.

Not findings:
- A remote's `HEAD` symref does not match the `kitty/mission-*` pattern.
- `_claims_default_mission` reads whether `merged_at` is present. That matches `mission_has_landed` closely enough, because `mission reopen` clears `merged_*` from meta.json as well as recording the reopen event.

## Findings (reproduced with the standalone script probe_c3.py on real git)

1. **[MEDIUM] src/mission_runtime/resolution.py:1178 (raised at :1291, and at src/specify_cli/coordination/planning_commit.py:295): wrong remedy for a default Mission that has no coordination branch.**
   - Reproduction (case D): a default Mission settled as `single_branch` (`topology_source: default`, `topology: single_branch`, no `coordination_branch`) whose repository root checkout was switched back to `main`.
   - Result: `PLANNING_CHECKOUT_MISSING`. The message calls `kitty/mission-sd-01M8EEEE` "the coordination branch" and says to run `spec-kitty doctor coordination --mission sd-01M8EEEE --fix`.
   - That Mission has no coordination branch or worktree, and the doctor skips any Mission without `coordination_branch` (`_coordination_identity` returns None, `_coordination_doctor.py:324`). The remedy therefore does nothing, and the operator is left stuck.
   - The same text is raised from `planning_lane_target` when meta.json is found but no checkout holds the branch.
   - Recommendation: say "the coordination branch" and name the doctor only when the Mission records a `coordination_branch`. Otherwise name the real remedy, `git switch <branch>` in the repository root checkout. Add a test for a default single_branch Mission.

2. **[LOW] src/mission_runtime/resolution.py:1201 and :1216: a remote whose name contains "/" is silently missed.**
   - Git allows remote names with "/", for example `my/fork`.
   - Reproduction (case C): the ref `refs/remotes/my/fork/kitty/mission-rs-01M8DDDD`, whose meta.json describes a default, not-landed Mission, is not claimed. The pattern `refs/remotes/*/kitty/mission-*` does not match it, and `_branch_and_remote` would split it as remote `my` and branch `fork/kitty/mission-...` anyway.
   - `planning_write_ref` then returns `main` silently (NFR-002).
   - Recommendation: list `refs/remotes/` and split each refname on the `/kitty/mission-` namespace (everything before it is the remote). Add a test with a remote named `my/fork`.
