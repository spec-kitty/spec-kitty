# WP01 review cycle 1 — red-first measurement

Reviewer: reviewer-renata (self-review round, small mission) · 2026-11-02

## Checklist

| Item | Verdict | Evidence |
| --- | --- | --- |
| Red evidence is real and at the pre-existing entry point | PASS | both failures come from `upgrade --project --yes --no-worktrees` through the real `upgrade` command; the assertion messages name the kept file |
| Fixture measures what it claims | PASS | the ledger is seeded `skipped` for the three targets plus `3.2.0a4_safe_globalize_commands`, and the test asserts the seeded result before acting |
| Positive control present | PASS | `test_same_commit_leaves_the_same_tracked_state_in_both_homes` proves removal is observable on the same fixture shape |
| No gate weakened | PASS | no `skip`, no `xfail`, no assertion loosened; `NFR-003` hold rule asserted in its own test |
| Home ownership respected | PASS | requests `canonical_home`; never pins `SPEC_KITTY_HOME` locally, never patches `Path.home()` |
| Issue scope | PASS | no `src/` change in this WP; no collision with `tests/upgrade/test_upgrade_empty_home_noop.py` (#6946) |
| Conventions | PASS after fix | `ruff check`/`ruff format` clean |

## Findings and disposition

1. **F1 (style, fixed)** — helper name typo `_markded_command_file` → `_marked_command_file`.
2. **F2 (style, fixed)** — file was not `ruff format` clean; reformatted.

Both fixed in commit `test(upgrade-empty-home-command-migrations): apply review round 1`.

## Verdict

APPROVE. The module covers FR-003, FR-004, FR-005, NFR-003 and the guard half of
NFR-001; the red assertions are the ones WP02 must turn green without editing them.
