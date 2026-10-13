---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-12T22:13:44Z'
reviewer_agent: reviewer-renata
wp_id: WP16
---

# WP16 review cycle 1: REJECT (reviewer-renata), README only

The full evidence is in wp16-review-verdict.md (orchestrator scratchpad). The code, the hostOrigin stage, both digests (`7007f777…ebb6`), the docs gates and the T084 scans are all green. The orchestrator has settled F8 (the README is the sole carrier of the chmod and not-on-PyPI notes; DD-115 is corrected), F9 and F10 on the planning branch. F7 (the accepted-Host 405 Boot error body) is a slice-4 wrap-up fold and is out of scope here.

| id | severity | where | problem | remedy |
|---|---|---|---|---|
| F1 | medium | README.md:70 | It says a missing or unusable `project.slug` "logs `mission_dir_unreadable`" but does not mention the visible effect: `GET /api/v1/project` answers 500. | Reword: it answers `500` on `/project` with the diagnostic `mission_dir_unreadable`. Note that the oracle names it `projection_refused` with the same status and body (FR-004). |
| F2 | medium | README.md:108-120 | The divergence list omits DD-99 (Q-3 interim). The service reads no git, so whether a directory exists decides, and a husk coordination folder is not told apart from a registered worktree. | Add a bullet for DD-99 (Q-3). |
| F3 | low | README.md:108-120 | Further decided divergences are not listed: DD-95 C2-2 (`"claude\n"` gives a null tool), DD-81 (insertion order of annotation-only WPs), DD-86 to DD-88 and DD-104 (leak-pattern class translation; `\b` refused), DD-85 (optional members of the wrong type read as absent). | Add these as one bullet each, or as one grouped bullet. |
| F4 | low | README.md:74 | The annotation sentence is imprecise. | Reword to: a Work Package with annotation rows but no transition is held in the `uninitialized` lane; it counts toward `wpTotal` and the progress denominator, but in no Lane count. |
| F5 | low | README.md:9-14 | `server.address` is not named. | Name the key once. Say that BindGuard refuses any value other than `127.0.0.1`, including `localhost`. |
| F6 | low | README.md:110 | "the mission's decision record" gives no path. | Cite `kitty-specs/mission-status-read-api-overview-01M4EMSA/traces/design-decisions.md`. |
| F11 | low | docs/development/reference/ci-gate-mechanics.md (~886) | "supersedes the earlier plan" refers to a plan this page's reader does not have. | Cite "operator ruling 2026-10-11 (DD-77)" instead. |

Afterwards, re-run `AllowlistReadmeParityTest` (the allowlist fence must stay the first code fence), `tests/ci/test_mission_status_api_build.py`, the `tests/docs` spelling and changelog tests, and `check_changelog_style`.
