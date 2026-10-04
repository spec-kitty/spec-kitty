# Retry evidence: a second finalize-tasks after a failed one (#5641, FR-005)

Recorded 2026-10-04 by driving the real `finalize-tasks` command (`CliRunner`
against the real `mission` app) on a real two-WP Mission created with
`create_mission_core` on a non-protected topic branch. The first run fails ONLY
its final `TASKS_INDEX` commit; the second run is unpatched. "Seed commits" are
`chore(spec-kitty): status transition WPnn` commits on the status-surface branch
since the fixture commit; "planned events" are the `planned` seeds in the
committed `status.events.jsonl` at the branch tip after the retry.

| Source | Topology | Seed commits left by the failed run | Retry exit | Retry `newly_seeded` | Seed commits after retry | `planned` events in log |
|---|---|---|---|---|---|---|
| base (`skupstream/main` @ `05004fea33`) | `coord` | 2 | 0 | 0 | 2 | 2 |
| base | `lanes` | 2 | 0 | **2** | **4** | 2 |
| this branch | `coord` | **0** | 0 | 2 | 2 | 2 |
| this branch | `lanes` | **0** | 0 | 2 | 2 | 2 |

Reading:

- Before the fix, a `coord` retry did not seed twice: the bootstrap reads the
  coordination log the transactional writer targets (the triage note was right
  there). A `lanes` retry did: it read the restored working-tree log, seeded
  again, and history carried four seed commits for two WPs. The final log held
  only the retry's two seeds, so the first run's committed events were dropped
  from the log while staying in history.
- After the fix the failed run leaves no seed commit, so the retry is an
  ordinary first run on both topologies: one seed commit and one `planned`
  event per WP. No separate retry fix is needed (FR-005 holds through FR-001).

Harness: a throwaway pytest module (not committed) run once with
`PYTHONPATH=<base worktree>/src` against `skupstream/main` and once against this
branch; its body is the same fixture as
`tests/specify_cli/cli/commands/agent/test_finalize_atomicity.py::_two_wp_mission`.
