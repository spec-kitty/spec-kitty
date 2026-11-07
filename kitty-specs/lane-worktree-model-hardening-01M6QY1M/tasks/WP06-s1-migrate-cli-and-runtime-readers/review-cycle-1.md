---
affected_files: []
cycle_number: 1
mission_slug: lane-worktree-model-hardening-01M6QY1M
reproduction_command:
reviewed_at: '2026-11-06T17:36:55Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP06
---

# WP06 review cycle 1 (reviewer-renata): changes requested

Most of WP06 is sound: the red-first order holds, and 9481f8b743 only fixes the test harness. The parity matrix (7 readers x 8 cells) shows 0 divergent cells. The N4 tests pass. `transition()` never reads the door. The allowlist is back to 231. The test re-points weaken no assertion. The dead-symbol gate passes (37 passed). Three defects block approval.

**Issue 1 (blocking): `agent status materialize` no longer writes status.json for any landed Mission, but still reports success, and other commands still send users to it.**
`MissionStatus.materialize` treats `CONSOLIDATED_TARGET` as read only. The door picks `CONSOLIDATED_TARGET` for every Mission with `merged_at`, whatever its topology, and its path is the repository root checkout's Mission dir.
Reproduction: a `single_branch` matrix Mission with `merged_at` set and status.json deleted.
- Lane base acf712250a: `agent status materialize` exits 0 and recreates status.json.
- WP06: it exits 0 and prints "Materialized ... 3 events -> 1 WPs", but status.json is not written.
- `agent status validate` then still says "status.json is missing (run 'spec-kitty agent status materialize' to generate)". The user is stuck in a loop.
Callers that rely on the file being written:
- `status/validate.py:327` and `status/doctor.py:399` (their advice);
- the heal advice of `upgrade/migrations/m_zz_verdict_provenance_backfill.py:155`;
- the drift advice of `consolidation/executor.py:826`;
- the command's own docstring ("writes status.json").
The ADR does not forbid this write: `agent status materialize` is an explicit regenerate command, not a status read.
Fix: write status.json for `CONSOLIDATED_TARGET`. Alternatively, refuse with an actionable message and update every piece of advice above. Add a test for a landed Mission. Also make the output honest for a ref source: say that status.json was not written.

**Issue 2 (blocking): two out-of-matrix tests are red because of WP06, and the WP lists them as pre-existing.**
- `tests/specify_cli/cli/commands/test_implement_placement_reachability.py::test_unmaterialized_coordination_worktree_is_refused_as_not_finalized`
- `tests/specify_cli/cli/commands/test_implement_placement_reachability.py::test_empty_coordination_worktree_is_refused_as_not_finalized`
Both pass at the lane base acf712250a (an archive of that commit) and on the repository root checkout. Both fail on the lane (exit 0 instead of 1). They pin the old N4 behaviour: an empty or absent coordination worktree read as "not finalized". The `claim_preflight` migration onto the door changes that on purpose, since the claim now reads the committed coordination branch.
Fix: re-pin both tests to the ADR 2026-11-06-2 behaviour, with a short rationale. If the refusal is still wanted, keep it deliberately instead. Correct the attribution of failures in your summary. The other failure I spot-checked, `test_residue_shared_walkers_6669::test_cutover_repo_probes_git_once_per_walk`, does fail at the base.

**Issue 3 (blocking): `agent status doctor/lifecycle/validate` crash on an unreadable coordination ref.**
The door is now resolved lazily in `_status_path_or_refuse` (`ms.status_read_surface()`), outside any handler. A `StatusSurfaceRefUnreadable` therefore escapes as an uncaught exception: exit 1, empty stdout, and no `{"error": ...}` envelope under `--json`. The `StatusSurfaceRefUnreadable` clause you added to `_resolve_mission_status_for_repo` never runs, because `MissionStatus.load` does not call the door.
Reproduction: an absent coordination worktree, with the tip commit object of the coordination branch deleted (your `_break_coordination_ref`).
Fix: catch the exception where the surface is resolved and route it through `_output_error`. Add one test per command (or a parametrized one).

**Non-blocking**
- `events tail` has a new `status_surface_on_ref` refusal and now refuses where it used to print nothing for an empty or absent coordination worktree. That changes the events-tail CLI error table (`kitty-specs/events-tail-multi-log-and-json-01M66F8A/contracts/cli-contract.md`). It is not an orchestrator-api or 1.24.0 contract change. It needs a changelog fragment, or a docs note in WP18. The refusal message itself is actionable.
- The doctor/lifecycle/validate refusals on a ref source are actionable: they name the ref and say what to do.
- `mypy --strict` reports 3 errors in the touched files (status_service.py:345/352, tasks_shared.py:785). They are on unchanged lines and were already there.
