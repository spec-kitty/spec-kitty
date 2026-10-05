---
affected_files: []
cycle_number: 1
mission_slug: nightly-suites-green-01M44FEP
reproduction_command:
reviewed_at: '2026-10-05T06:02:41Z'
reviewer_agent: reviewer-renata
wp_id: WP06
---

# WP06 review cycle 1: changes requested

Reviewer: reviewer-renata. File: `tests/cli/commands/test_owned_checkout_git_calls.py`.

1. **Pin the default posture (14), not the forced-drain one (18)** (`:75`, `:154`). Four of the 18 `setup-plan` calls (`git config --get remote.origin.url` and `git remote get-url origin`, twice) exist only because the autouse `_drain_posture_enabled` fixture (`tests/conftest.py:2262`) forces hosted drain on. They run under a 2.0 s deadline in a daemon thread, so a slow runner could yield 17: the flake class this mission removes. Add the existing `drain_off` fixture to `owned_mission` and pin `setup-plan` at 14. Out-of-process `GIT_TRACE2_EVENT` gives 7 / 14 / 7.
2. **Correct the explanation at `:37-41`.** The difference is the drain posture, not the in-process runner. State that the pinned counts equal the out-of-process figures.
3. **Module docstring:** state the per-pull-request home (`cli` module shard) and the residual gap: changes only under `core/owned_mission.py`, `core/git_ops.py`, `kernel/git_topology.py`, `status/*` or `mission_runtime/context.py` do not select `cli` and reach this pin in the nightly.

Not required, recommended: the file takes 38 to 52 s. With drain off, `setup-plan` is 14 on repeat runs too, so a module-scoped fixture would cut about 25 s. Adopt it only if the cold-count guarantee (first invocation after a cache reset) is kept and re-sampled.
