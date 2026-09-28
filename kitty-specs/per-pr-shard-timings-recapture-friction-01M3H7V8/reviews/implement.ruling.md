# Implementation ruling — orchestrator, 2026-09-28

**Subject:** WP03's new workflow `.github/workflows/ci-charter-shard-recapture.yml` fails two
closed architectural registries that enumerate every file in `.github/workflows/`. The
orchestrator reproduced both failures on the WP03 lane at `054b6434d`:

- `tests/architectural/test_no_duplicate_suite_execution.py::test_every_live_workflow_is_classified_and_every_exclusion_is_declared`
- `tests/architectural/test_workflow_coherence.py::test_pytest_workflow_set_equals_model_allowlist_live`

No WP's `owned_files` covers either registry, and neither plan.md nor tasks.md mentions them.
Shipping without them turns the PR's `architectural-heavy` check red. Precedent `b17a81506`
(#4667) shows the cost of the other order: the previous scheduled workflow
(`ci-stale-running-sweep.yml`) landed first, turned `main` red, and was registered afterwards in a
separate fix that also refreshed `tests/release/pinning_rule_inventory.json`.

**Ruling: fold the registrations into WP03. Do not defer them to a follow-up.** WP03's write scope
widens to exactly the registry entries its own workflow requires. That means one entry per
registry that enumerates workflows, mirroring the existing `ci-stale-running-sweep.yml` entries,
plus any pin inventory the new SHA-pinned actions must appear in. Nothing else in those files
changes.

This is a **deliberate widening beyond the spec text**. It is recorded here and must be named as
such in the PR body and in the `sk-land` hand-off. `owned_files` cannot be widened through the CLI
after bootstrap (ledger SK-314-class limitation), so this ruling is the record of the widened scope.
