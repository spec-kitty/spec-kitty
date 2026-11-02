# Contracts — none for this mission

This mission changes no product surface: it removes an environment-derived input from one
characterisation test (`test_golden_applied_dry_run`) and leaves `src/` untouched (FR-004). There
is no wire contract, no CLI contract and no cross-package interface to pin here.

The observable contract this mission keeps is the pinned dry-run text itself, asserted directly in
`tests/upgrade/test_upgrade_outcome_rendering.py::_GOLDEN_APPLIED_DRY_RUN`.
