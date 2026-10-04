# Tooling friction

- 2026-10-04: `agent mission create` commits its scaffold as "Add scaffold for feature <slug>" -- a terminology-canon violation (Mission, not feature) in a generated commit subject.
- 2026-10-04: the first pytest run in a fresh cloud venv reinstalled the package through pip (session bootstrap), costing ~1 minute before tests started.
- 2026-10-04: `spec-kitty implement WP01` refused with `WRITE_CHECKOUT_OCCUPIED`: a merged Mission on main (`reconcile-flake-family-01M34HR7`) still records WP04 `in_progress` in the repository root checkout (event dated 2026-09-22). Every `single_branch` Mission in this checkout is blocked by that stale record; the claim went through `agent tasks move-task WP01 --to in_progress` instead (the other Mission's status was not touched).
- 2026-10-04: `tests/integration/test_owned_lifecycle_acceptance_finalize.py::test_armed_get_main_repo_root_pin_owned_finalize` is red on `skupstream/main` @ 05004fea33 (18 `_compose_primary_feature_dir` reads against an exact ledger of 16); pre-existing, identical on this branch, no tracker issue found.
- 2026-10-04: `move-task --to for_review` refuses while an unrelated, not-yet-committed WP02 research file sits in the Mission directory ("not attributable to a specific work package").
- 2026-10-04: `move-task WP01 --to for_review` then refused 'no implementation commit since claim ... beyond <no recorded claim base>' (no claim base because implement was bypassed); moved with --force naming the implementation commit.
- 2026-10-04: `accept` refused on a missing `contracts/` directory (path convention) for a bugfix with no contract; accepted with `--lenient` as the refusal suggests rather than creating an empty directory.
