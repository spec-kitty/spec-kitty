# Design decisions — centralized-runtime detection is project local

Mission: `centralized-runtime-detection-is-project-local-01M68ZFE` · Issue #6551

## D-1 — Fix the predicate, not the ledger

The issue offers two remedies: (a) make `uses_centralized_runtime` read the
project's `metadata.yaml` before the operator's home; (b) treat a `skipped` record
as settled for migrations whose `target_version` is below the project's stamped
version.

**Decision: (a) only.** (b) changes ledger *selection* semantics, which ADR
`2026-10-17-1` §3 and constraint C-001 freeze, and it would permanently un-arm a
legacy migration for a project that is still genuinely legacy. It also only hides
the non-determinism: `detect()` would still disagree between machines, it would
just no longer be consulted. (a) restores the property the ledger's own
`skipped`-is-re-evaluated rule assumes — that `detect()` is a function of project
state — as a single-predicate change with two call sites.

## D-2 — A readable stamp of 2.0.0 or later wins outright

A readable `.kittify/metadata.yaml` is the project's own statement of which
runtime model it was created or last migrated under. At `>= 2.0.0` the answer is
`True` with no home consultation. The home check survives *only* for
metadata-less shapes, which the existing `tests/upgrade/test_compat.py` cases pin
(a repo with `.kittify/` but no stamp stays `False`; a worktree without
`.kittify/` is runtime-managed only when the home is bootstrapped).

## D-3 — Fail closed on an unparseable stamp

`InvalidVersion` (including the `"unknown"` default that `ProjectMetadata.load`
supplies for a file with no version key) still returns `False`. A project we
cannot date is not assumed modern; this is today's behaviour and the change does
not need to invent a new assumption to fix #6551.

## D-4 — Proof at the production entry point, not only at the helper

Tactic `acceptance-criteria-non-vacuity` requires the real entry point. The
regression test therefore drives the actual `upgrade --project --yes` command
through the repo's `typer.testing.CliRunner` harness and asserts the *head commit
does not move* (the upgrade auto-commits whatever it touched, so a clean
`git status` alone would miss the defect). Two positive controls share the
fixture shape: the ledger still records both legacy ids after the run, and a
project stamped below 2.0.0 under the same empty home still receives the missions.

## Out of scope (recorded for the PR's `## Deferred`)

1. **Repair of already-affected projects.** Projects that already committed the
   frozen overrides need them repointed or removed; that is #6548's surface, and
   the issue's own "ledger `success` record later than the stamped version"
   marker is a suggestion for *that* work, not this one.
2. **The three other migrations that read the global home directly**
   (`2.1.3_restore_prompt_commands`, `2.1.4_enforce_command_file_state`,
   `3.1.2_globalize_commands`). They do not go through
   `uses_centralized_runtime`, and the issue did not measure them under this
   trigger. A regression test that converges a project and re-runs `upgrade`
   under an empty `SPEC_KITTY_HOME` is the right follow-up; folding an
   unreproduced change to three more migrations into a one-predicate fix is not.
3. **The ledger-settlement alternative** (see D-1) — rejected with its reason
   above, so the operator can see the reasoning rather than a silent omission.
# design-decisions
