---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-12T21:23:28Z'
reviewer_agent: reviewer-renata
wp_id: WP15
---

# WP15 review cycle 1: REJECT (reviewer-renata), test-pin gaps only

The full evidence is in wp15-review-verdict.md (orchestrator scratchpad). The release job and the fleet_main fix are correct, and the lint commit makes no logic change. The reviewer ran 33 mutations of the workflow; 7 of them slipped past the pins. Every remedy goes in the tests only. The orchestrator has recorded F5 (the hand-off list and the tag procedure) in the DD-115 addendum, so it needs no action from you.

| id | severity | where | problem | remedy |
|---|---|---|---|---|
| F1 | high | tests/ci/test_mission_status_api_build.py `_release_order_violations` (~2118-2124) | The fail-closed pin only looks for the substrings `"if !"` and `"exit 1"`. If the ancestor check is changed to `if ! git merge-base ... origin/main \|\| true; then`, the release job fails open and every pin stays green. The same weakness misses `sha256sum -c ... \|\| true`. | Pin the exact text of the ancestor step and the exact checksum loop line. Reject any `\|\|`, `true` or `; :` after those commands. Add a revert row for each of the two `\|\| true` mutations. |
| F2 | medium | same file `_release_publish_violations` (~2142) | Neither the semver regex gate nor the `--prerelease` case is pinned. Deleting either one leaves the pins green. | Pin the exact `grep -Eq` line together with its `exit 1`, and the `*-*) flags+=(--prerelease)` line. Add revert rows. |
| F3 | medium | same file `_release_order_violations` | The "exactly 8 assets" check is not pinned: `-ne 9` or `-ne 0` stays green. | Pin the count line and its `exit 1`. Add a revert row. |
| F4 | low | same file | The pin counts steps that contain `gh release create`, not occurrences of the command, so a second call in the same step passes. `tail -n 1` in the ls-remote pipeline is also not pinned. | Require exactly one occurrence of `gh release create` across the release job's `run` text, and pin `tail -n 1`. Add revert rows. |
| F6 | info | workflow header comment, line 5 | The comment says the workflow is "not listed in ci-fleet-verdict.yml", but it is listed (DD-77). | Fix the comment. You own the workflow. |

Re-run the reviewer's 7 escaping mutations (listed in the verdict file) and show that each one now goes red.
