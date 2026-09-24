# Tracer — Tooling Friction

Log any Spec Kitty / tooling friction encountered while running this mission (e.g. coord/lane
allocation, gate behavior). Candidates already tracked: issue-matrix per-WP approval gate + review-
cycle-artifact commit friction (#5007).

## Append log (during implement)
- (planning) seeded.

## Live #4966 self-hit (planning, 2026-09-24)
`spec-kitty agent decision open` (plan-phase DM for the degrader policy) failed with
`MISSION_NOT_FOUND: meta.json not found for mission 'coord-read-fail-closed-01M38VVH'` — even though
`meta.json` exists on the primary partition. Cause = the exact #4966 defect: this coord-topology
mission's coord worktree is materialised, so `decisions/service.py::_mission_dir` resolves meta.json
through the status-only husk (which lacks it). The bug under repair blocked its own mission's CLI
decision path. Worked around by recording the plan decision inline in research.md (no CLI DM). This
is first-hand evidence for the #4966 acceptance test.
