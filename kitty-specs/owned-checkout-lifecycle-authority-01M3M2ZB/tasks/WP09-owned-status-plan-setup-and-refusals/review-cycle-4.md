---
affected_files: []
cycle_number: 4
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T09:33:13Z'
reviewer_agent: claude
wp_id: WP09
---

# WP09 review: cycle 4, changes requested

Reviewed commits: 186cec51c (red) and 2f12e9370 (fix).

## Verified as fixed

**The 7-row table now matches adoption.** Bare `status --json`, with R holding one active mission:

| Row | b3dc01fff | 2f12e9370 |
|---|---|---|
| R | default | default |
| Lane worktree listed in `lanes.json` | default | default |
| Stale lane worktree | default | default |
| Coordination worktree | default | default |
| Plain linked checkout | default | default |
| Owned P outside R | default (leak) | `mission_required` |
| Owned P under `R/.worktrees` | default (leak) | `mission_required` |

**Red-first holds.** At 186cec51c the stale-lane and plain-linked rows fail (2 failed, 6 passed).

**Single authority.**
- `invoking_checkout_would_adopt` defers entirely to `adopt_owned_checkout` and does no topology classification of its own.
- The listing of `kitty-specs/` and the `meta.json` filter only gather handles.
- The early `toplevel == repository_root` return mirrors adoption's own first check.
- The declared out-of-map edit is minimal.

**Fail-safe edges.**
- An unreadable worktree registry answers False, because adoption catches `WorktreeRegistryUnavailable` and returns None.
- A mission-surface conflict answers True. This is pinned by `test_would_adopt_true_on_mission_surface_conflict`.

**Gates.** Targeted tests pass (769). ruff check and format are clean, complexity is ≤ 11, and mypy `--strict` is clean on the touched sources.

## Issues

**Issue A [HIGH] `core/owned_mission.py` `invoking_checkout_would_adopt` runs one full adoption per mission directory. It is unbounded git and claim cost on the #4677 default path, and it breaks NFR-002.**

Measured directly:
- In this repository, calling the predicate from the lane-h worktree (517 mission directories) took **53.4 s**. It made **1692 git subprocesses**, 517 `adopt_owned_checkout` calls and **516 `resolve_ownership_claim` calls**, and answered False.
- A synthetic end-to-end test used R with 1 active mission and 100 merged ones. Bare `status --json` from a lane worktree took 0.1 s at b3dc01fff and **2.3 s** at 2f12e9370. From R it took 0.1 s at both. The cost grows linearly with the number of missions.

This path is exactly the #4677 convenience agents use from lane worktrees. It also turns a non-owned run into N ownership-claim resolutions, while NFR-002 and T044 (d) require 0 for non-owned runs.

Required fix:
- Bound the predicate to a constant number of git calls, whatever the number of missions. Make it resolve 0 ownership claims for non-owned checkouts (R, lane, stale lane, coordination, plain linked).
- Example: pre-filter candidate handles with a cheap necessary condition that `owned_mission.py` itself exposes, so the rule keeps a single authority. For instance, read the checkout's branch once and keep only missions whose `meta.json` `target_branch` equals it. That is the minter's own branch rule, so it should be factored out and shared, not re-implemented. Only then ask `adopt_owned_checkout` about the survivors.
- Add pins:
  - a fixture with many (≥ 50) missions: bare status from a lane worktree and from a plain linked checkout makes 0 `resolve_ownership_claim` calls and a constant number of `adopt_owned_checkout` calls (0 or 1);
  - the owned-P rows still refuse.
- Show the pins red first.

**Issue B [LOW] `tests/core/test_adopt_owned_checkout.py:76` has an unused `# type: ignore[arg-type]`.**
- mypy `--strict` flags it (`unused-ignore`).
- The line predates WP09 (4c3dd3a3b1, WP02), and it is already flagged at 186cec51c.
- WP09 edits this file (adding the predicate tests), so the campsite rule applies: remove the ignore, or type `counting` so it is not needed. The file must be mypy-clean.
