# Tooling friction

- `gh issue view` is unavailable in this cloud session (GraphQL 403); issue and PR text read through `gh api` REST instead.
- Assigning #7729 to the HiC (charter Tracker Ticket Assignment Rule) was refused by this session's permission layer; left for the operator.
- `move-task WP01 --to for_review` on this single_branch Mission printed "Pre-review regression gate: no_coverage — no changed files detected for this WP", although the WP's window (claim commit aa70fe2) contains the test and fix commits. The gate was skipped, not failed; worth a look by whoever owns the pre-review gate's single_branch window read.
- `tests/architectural/test_no_dead_modules.py` needs a manual allowlist line for every new auto-discovered migration (the category is a standing convention, not drained debt).
- Each test module that drives `MigrationRunner` or imports the upgrade registry spends ~100 s in collection/import here, while each test body runs in under 1 s.
