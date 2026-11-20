# Decision Moment `01M7WX8AX56E23AXBZRWGNX4EM`

- **Mission:** `approved-lane-resolution-route-01M7WW0Z`
- **Origin flow:** `specify`
- **Slot key:** `specify.route.sibling-incorporation-command`
- **Input key:** `sibling_incorporation_command`
- **Status:** `resolved`
- **Created:** `2026-11-20T16:39:54.021709+00:00`
- **Resolved:** `2026-11-20T17:05:28.322420+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

FR-001: the re-review route must incorporate the SIBLING lane (at its approval-stamp SHA) into the stale approved lane, because rollback restored the Mission branch. No CLI command does that today, and the #7285 A-10 rule (pinned by tests/lanes/test_stale_remediation_cli_command.py:76-96) forbids raw 'git merge' / 'cd .worktrees' recipes in the remedy. Which route?

## Options

- (b) Extend the canonical lane sync point: spec-kitty agent action implement <WP> --incorporate <lane> merges the sibling lane approval stamp into the lane checkout and stops on a conflict for hand resolution (recommended; keeps A-10)
- (a) Amend A-10 for approved code lanes only: the remedy prints a raw git merge of the sibling stamp SHA in the lane checkout
- Other

## Final answer

(b) Extend the canonical sync point: spec-kitty agent action implement <WP> --mission <m> --incorporate <lane> merges the sibling lane approval-stamp SHA into the lane checkout and stops on a conflict for hand resolution. A-10 unchanged. Remedy order: send back (move-task), implement --incorporate, resolve+commit, for_review, independent approval, re-run consolidate. (operator, 2026-11-20)

## Rationale

_(none)_

## Change log

- `2026-11-20T16:39:54.021709+00:00` - opened
- `2026-11-20T17:05:28.322420+00:00` - resolved (final_answer="(b) Extend the canonical sync point: spec-kitty agent action implement <WP> --mission <m> --incorporate <lane> merges the sibling lane approval-stamp SHA into the lane checkout and stops on a conflict for hand resolution. A-10 unchanged. Remedy order: send back (move-task), implement --incorporate, resolve+commit, for_review, independent approval, re-run consolidate. (operator, 2026-11-20)")
