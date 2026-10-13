---
affected_files: []
cycle_number: 2
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-12T21:31:12Z'
reviewer_agent: reviewer-renata
wp_id: WP15
---

# WP15 review cycle 2: REJECT (reviewer-renata), one evasion left

The full evidence is in wp15-review-verdict.md (orchestrator scratchpad). All 9 earlier escapes, tried as real workflow edits, now turn red, and so do 5 new evasions. The exact-text pins catching whitespace-only changes is acceptable for fail-closed publication steps.

| id | severity | where | problem | remedy |
|---|---|---|---|---|
| G1 | high | tests/ci/test_mission_status_api_build.py `_release_exact_violations` | The pins check only the `run:` text of the ancestor, verify and resolve steps, not the step's other keys. With `continue-on-error: true` on "Require the tagged commit to be on main", or on the tag re-resolution step, the release tests stay green. A failed provenance check then no longer blocks publishing. An added `if:`, `shell:` or `env:` slips through the same way. | Pin the WHOLE step mapping of every release-job step that gates publishing: ancestor, download, count/verify, resolve and publish. The key set must be exact (e.g. `name` and `run`, plus `env` where it exists today), so any extra key goes red. Also pin the release JOB mapping: no job-level `continue-on-error`, the exact `if:`, `needs`, `permissions` and `timeout-minutes`, and no `strategy`. Add revert rows: `continue-on-error: true` on each gating step and at job level; an added `if: always()` on the publish step; an added `shell: bash {0}` (which drops `-e`) on the ancestor step. |

Run the mutations as real edits to the workflow in a scratch worktree, or as in-memory edits of the parsed YAML, and show each one red.
