---
affected_files: []
cycle_number: 1
mission_slug: nightly-reds-remediation-01M6VYS1
reproduction_command:
reviewed_at: '2026-11-07T22:46:17Z'
reviewer_agent: claude-opus-reviewer
wp_id: WP03
---

# WP03 review (reviewer-renata, claude-opus-reviewer): CHANGES REQUESTED

Commit e788a0336e. #7181 (both nodes) and #7182 Group A are correct. One blocking finding is in Group B.

## F1 (Medium, blocking): reachable generate legs deleted as "unreachable"

`tests/specify_cli/cli/commands/test_charter_ambiguous_directives.py:67-88` (`test_colliding_directive_selection_refuses_the_interview`) deletes the old test's `generate` legs. The commit and the docstring call them unreachable under the refusal. WP03 T011 and the binding rule ("drop only the post-interview assertions that are unreachable"; "deleting a pin without a stronger home: STOP") allow only unreachable legs to go. I reproduced the exact fixture in a scratch script (no repo edits) and both legs are still reachable on this head:

- `required=False`: the interview refuses but saves the answers (`selected_directives: [TEAM-SEC, DIRECTIVE_001]`, `selected_paradigms: [atomic-design]`). Then `charter generate --from-interview --json` exits 0 and writes `charter.yaml`. The old leg (`generated.exit_code == 0`) still holds and is now unpinned. Note: that generate reports `selected_directives: []` and `selected_paradigms: []`, so every saved selection is gone, including the resolvable DIRECTIVE_001 and the paradigm. Pin whatever the intended behaviour is. If dropping all selections after a refused interview is not intended, raise it with the operator; do not leave it untested.
- `required=True`: `charter generate --no-from-interview --mission-type software-dev --json` against the same fixture exits 1. Its error names `Cannot store directive 'TEAM-SEC' ...`, `.kittify/config.yaml` stays byte-identical and no `charter.yaml` is written. Every assertion of the old required leg (exit != 0, "TEAM-SEC" in output, config unchanged, no charter.yaml) survives with the flag swapped from `--from-interview` (no answers now) to `--no-from-interview`. The named home, `test_generate_rejects_ambiguous_required_directive_without_interview`, uses a different fixture: a project-layer overlay against a built-in stem, with no org-vs-org collision and no raw-id sentinel file `TEAM-SEC.directive.yaml` declaring COMPANY-SEC. So it does not cover this case. The sentinel guards against activating COMPANY-SEC "under the guise of TEAM-SEC", which is exactly the generate-side risk the old leg pinned.

Failure scenario: a regression that lets `generate` store COMPANY-SEC for the colliding required id (or lets generate after a refused interview crash or change its selection handling) would pass the whole suite. The interview leg passes, and the only other generate test uses a different collision shape.

Fix (test only, same file): after the interview assertions, restore the generate leg for each param.
- required=False: `generate --from-interview --json` gives exit 0, and neither TEAM-SEC nor COMPANY-SEC is in `build_active_charter_service(tmp_path).directives` or in the generate payload's `selected_directives`. Also pin the observed selection outcome, or escalate it.
- required=True: `generate --no-from-interview --mission-type software-dev --json` gives exit != 0, "Cannot store directive 'TEAM-SEC'" in the output, config bytes unchanged and no `.kittify/charter/charter.yaml`.

Then re-run the file plus `tests/charter/activation/test_stored_spelling_6527.py`.

## F2 (Low, not blocking)

`tests/specify_cli/test_charter_activate_cli.py:314-319` (`test_no_cascade_does_not_activate_referenced`): the commit says the seed makes it non-vacuous. But the test still never checks the activate result or that the direct activation was written, so a failing activate (exit 1, nothing written) still passes it. Add `assert result.exit_code == 0` and `_CASCADE_SOURCE_ID in data["activated_agent_profiles"]`, as the sibling test already does.

## Verified OK

- #7181 `test_charter_generate_autotrack.py:350-356`: typed envelope pinned with the code. It is stronger than before.
- #7181 `test_charter_status_freshness.py:208-235`: the CLI route to `invalid` is retired by #6557. The computer `invalid` state is pinned in `tests/specify_cli/charter_freshness/test_computer.py:451-556`.
- #7182 Group A: every original assertion is kept, and the seeds follow #6685. `TestDeactivate` is untouched.

Evidence (reviewer, foreground): the four owned files + test_status_broken_charter_6557 + test_stored_spelling_6527 + test_interview_leaves_absent_key_absent_6685 + test_charter_activate_commands_core + test_computer: 156 passed, 1 skipped. ruff and format clean.
