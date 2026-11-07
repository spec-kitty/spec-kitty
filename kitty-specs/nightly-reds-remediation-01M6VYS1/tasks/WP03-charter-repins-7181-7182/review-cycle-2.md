---
affected_files: []
cycle_number: 2
mission_slug: nightly-reds-remediation-01M6VYS1
reproduction_command: spec-kitty agent tasks move-task WP03 --to approved --mission nightly-reds-remediation-01M6VYS1 --agent claude-opus-reviewer
reviewed_at: '2026-11-07T23:05:23Z'
reviewer_agent: claude-opus-reviewer
wp_id: WP03
---

Approved by claude-opus-reviewer: approval:WP03

# WP03 review, cycle 2 (reviewer-renata, claude-opus-reviewer): APPROVED

Rework commit 9171de6d94 (on top of e788a0336e). Head reviewed: 966bcf838e.

## F1: addressed
`tests/specify_cli/cli/commands/test_charter_ambiguous_directives.py` restores both `generate` legs on the exact org-vs-org TEAM-SEC/COMPANY-SEC fixture, with the raw-id sentinel file:
- required=True: `generate --no-from-interview --mission-type software-dev --json` must exit 1 (stricter than the old `!= 0`), must name `Cannot store directive 'TEAM-SEC'`, must leave config.yaml byte-identical and must write no charter.yaml. Every assertion of the old leg is back.
- required=False: `generate --from-interview --json` must exit 0 and must write charter.yaml. Neither colliding id may be in `selected_directives` or the delivered set. The leg pins the observed drop of all saved selections (`selected_directives == []`, `selected_paradigms == []`) and comments that it describes current behavior and does not endorse it.

The leg compares parsed activation lists, not raw bytes. I checked this with a scratch probe that made no repo edits. On this fixture `generate` appends `charter: .kittify/charter/charter.yaml` to config.yaml and also seeds `mission_type_activations` (software-dev, documentation, research, plan), so a raw-bytes comparison would fail for legitimate reasons. The risk this leg guards is that the colliding directive gets stored. `activated_directives == []` and the delivered-set check pin that, so the assertion is strong enough. Non-blocking note: the commit message calls the extra content "charter tracking", but generate also seeds `mission_type_activations`, and `activated_tactics` is not re-checked. Neither weakens the collision pin.

## F2: addressed
`tests/specify_cli/test_charter_activate_cli.py::test_no_cascade_does_not_activate_referenced` now asserts `exit_code == 0` and that `_CASCADE_SOURCE_ID` is in `activated_agent_profiles` before it checks the not-cascaded lists.

## Nothing else weakened
The rework adds lines only (+40/-1, and the -1 is the bare `_activate` call that is now assigned). The cycle-1 verified items are unchanged.

## Evidence (reviewer, foreground)
- 4 WP03 files + test_status_broken_charter_6557 + test_stored_spelling_6527 + test_interview_leaves_absent_key_absent_6685 + test_charter_activate_commands_core + test_computer: 156 passed, 1 skipped (122.98s)
- ruff check on the two touched files: all checks passed. ruff format --check --force-exclude: clean.
