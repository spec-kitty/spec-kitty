---
affected_files: []
cycle_number: 1
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-01T20:56:00Z'
reviewer_agent: claude
wp_id: WP06
---

# WP06 review, cycle 1: changes requested

Reviewer: claude (reviewer-renata, opus). Lane-d tip `86f8387d5e`, base `e7b085d26c` (lane-a).

## What already passes

- **Create → seed → commit wiring:**
  - `write_dir(STATUS_STATE)` materializes the worktree and runs WP03's create-time empty seed: `carried=()`, no commit.
  - `_emit_create_events(status_dir=)` writes `MissionCreated` and `SpecifyStarted` into the coordination Mission dir.
  - `_commit_coord_create_events` commits them in place on the coordination branch, carrying `COORD_SEED_TRAILER: <mission_id>`.
- **Discriminator:**
  - A created Mission is therefore post-fix from birth by the D4 discriminator. WP04's loud EMPTY applies, and `test_no_split_brain_warning_after_new_coord_create` plus `test_legacy_empty_coord_still_warns` keep both sides.
  - I-SEED-10 never fires spuriously after create: the dir is tracked and the trailer is present.
- **Expected divergence** (`is_expected_coordination_divergence`):
  - It fails closed (reports a divergence) on every git-probe error: merge-base, rev-list and diff-tree, with `-m --first-parent` for merges.
  - It accepts only commits touching this Mission's own COORD-kind paths, and rejects any target commit that touches them since the merge base.
  - It cannot mask a divergence that touches a PRIMARY or foreign path, and `test_genuinely_diverged_legacy_still_reported` pins that.
- **Rollback, at the injected points:**
  - The minted branch and worktree are removed when the failure comes after the seed commit.
  - A reused branch is CAS-reset, not deleted. The test is non-vacuous: it asserts the tip moved before the failure.
- **Dead symbols:** `COORD_SEED_TRAILER` is now imported by name. `test_no_dead_symbols` and `test_dead_symbol_allowlist_contract` are fully green on lane-d.
- **The B1 guard re-pin** in `test_accept_matrix_coord_partition.py` keeps its falsifiability: it asserts `acceptance-matrix.json` is absent, not that the dir is absent.
- **Static checks:** ruff check, C901 and mypy --strict are clean.
- **Diff coverage:** 94.4% over the raw diff (187/198).

## Blocking

**B1 (HIGH, regression): a healthy coordination Mission now fails the resume probe.**
- `check-prerequisites --resume-probe` reads `feature_dir/status.events.jsonl` (`mission_check_prerequisites.py:_mission_created_snapshot_problems`, L236-239). Create no longer writes that file for coordination topologies.
- Probe on a freshly created, healthy default (`coord`) Mission:

  | | `exit` | `resume_state` | problems |
  |---|---|---|---|
  | base `e7b085d26c` | 0 | `found` | — |
  | tip | **1** | **`malformed`** (`MISSION_RESUME_MALFORMED`) | `["status.events.jsonl is missing"]` |

- The re-pin of `test_mission_created_persistence_failure_is_nonzero_and_probe_recoverable` (`"status.events.jsonl is missing"`) hid this. That message is now produced for EVERY coordination Mission, healthy or not.
- **Required:**
  - Make `_mission_created_snapshot_problems` read the `MissionCreated` event from the coordination surface for coordination-routed Missions. Use the read resolver / `placement_seam(...).read_dir(STATUS_STATE)`, or `git show <coordination_branch>:…` when the worktree is absent.
  - This is an out-of-map edit to `mission_check_prerequisites.py`; declare it.
  - Add a test that the probe on a healthy coord create returns `found`/exit 0.
  - Restore the failure test's assertion to name the missing `MissionCreated` event, or the genuinely absent coordination log, not a message that every Mission produces.

**B2 (HIGH): a seed failure after materialization leaves a half-built coordination surface.**
- `_seed_coord_surface_for_create` builds the rollback context, then calls `write_dir`, and returns the context only on success. `_coord_rollback_holder` is filled after it returns.
- If `write_dir` raises after `materialize_coord_surface_for_write`, the context is lost. Causes include a seed failure, `STATUS_LOCK_HELD` and `COORD_SEED_GIT_PROBE_FAILED`.
- The generic rollback's `git branch -D` then fails because the branch is still checked out in the worktree.
- Reviewer probe (monkeypatched to raise):

  | Failure injected in | Branch left | Worktree left |
  |---|---|---|
  | `coord_seed._seed_coord_surface` | `['kitty/mission-probe-…-01M3WK5H']` | yes |
  | `_emit_create_events` | none | no |
  | `_commit_coord_create_events` | none | no |

  The first row is exactly the "half-seeded coordination branch" US1.5 forbids. The existing rollback tests inject only at `_commit_create_scaffold`.
- **Required:**
  - Append the rollback context to the holder BEFORE calling `write_dir`, which is what the docstring already claims.
  - Add parametrized rollback tests at three injection points: inside the seed or `write_dir`, `_emit_create_events`, and `_commit_coord_create_events`.

**B3 (NEW red gate): formatting churn in five format-exempt files.**
- The five changed files are all on `[tool.ruff.format].exclude`:
  - `src/specify_cli/cli/commands/_coordination_doctor.py`
  - `src/specify_cli/missions/_create.py`
  - `tests/coordination/test_coord_staleness.py`
  - `tests/coordination/test_surface_resolver_coord_empty_warning.py`
  - `tests/specify_cli/cli/commands/test_coordination_doctor.py`
- All five were whole-file reformatted. `tests/architectural/test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_still_genuinely_reformats` is now RED: "5 exclude entries are already formatted…".
- Semantic vs raw changed lines, measured against a formatted base:

  | File | Semantic | Raw |
  |---|---|---|
  | `_coordination_doctor.py` | 37 | 609 |
  | `test_coord_staleness.py` (not WP06-owned) | 5 | 339 |
  | `test_coordination_doctor.py` | 120 | 259 |
  | `test_surface_resolver_coord_empty_warning.py` | 58 | 91 |
  | `_create.py` | 188 | 211 |

  This is conflict bait for every other lane touching these files.
- **Required:** revert every formatting-only hunk and keep the semantic edits. Do not touch `pyproject.toml`. The ratchet must be green. This is the same issue WP12 was rejected for.

**B4 (MEDIUM): the #4863 abort re-pin weakened the true-no-op check.**
- `test_abort_valid_coord_mission_without_state_is_true_noop` now compares only the COMMITTED coordination blob (`git show <branch>:…`).
- An abort that appended an UNCOMMITTED row to the live coordination-worktree log would pass. In this test the worktree still exists, so the on-disk file is readable.
- **Required:**
  - Also compare the coordination worktree's on-disk `status.events.jsonl` bytes before and after.
  - Assert that the repository root checkout does not regain a `status.events.jsonl`. A write to the root would be a #5440 regression.

**B5 (MEDIUM): the owned-create plus coordination-topology claim is inaccurate and unpinned.**
- `_seed_coord_surface_for_create` documents that owned creates "fall through to the old PRIMARY path, byte-identical". They do not.
  - `_scaffold_mission_dir` drops `status.events.jsonl` from the scaffold for every coordination topology, regardless of `owned`.
  - `_build_create_result(status_log_path=None)` then treats it as a non-coordination create.
  - The emitted log lands in the owned PRIMARY dir but is no longer in the scaffold commit tuple.
- `resolve_create_topology` says "an explicit `--topology` always wins". Unless something refuses `--owned-checkout --topology coord|lanes_with_coord`, that combination is reachable.
- **Required, either:**
  - refuse the combination (`OWNED_TOPOLOGY_UNSUPPORTED`) with a test; or
  - pin its actual behaviour, where the creation events land and get committed somewhere, with a test, and correct the docstring.

## Non-blocking

- **N1:** `_teardown_coordination_worktree_if_present` (the `force_recreate` path) suppresses every exception. That is acceptable because `CoordinationWorkspace.teardown` refuses a dirty worktree and `_delete_branch` then raises a clear error. Add a test that `force_recreate` over a DIRTY eager worktree refuses rather than discarding records.
- **N2:** NFR-001 was not independently measured. The +1.0 s create median is plausible, given an extra worktree add, a seed and a coordination commit. Keep the budget assertion's actual numbers in the PR.
- **N3:** the uncovered diff lines include rollback branches: `mission_creation.py` 775 and 1936, `_create.py` 214/230/465/477, and the doctor at 1009/1405/1420-1431. B2's new tests should cover the first group.

## Tests run by the reviewer (`-n 3 --dist loadfile`, tip `86f8387d5e`)

| Suite | Result |
|---|---|
| `tests/core/` + `tests/missions/` + `tests/coordination/` + test_coordination_doctor + test_birth_cutover + test_zeitgeist_moment_handler + test_mission_creation_specify_started + test_mission_create | 1425 passed, 3 skipped |
| The 15 `grep -rlE "mission_creation\|ensure_coordination_branch\|_coordination_doctor\|mission create" tests/integration` files + the 4 B1 guards (accept_matrix_coord_partition, issue_verdict_coord_legacy_md_preservation, issue_verdict_selfmat_hardening) + test_issue_4863_merge_abort_no_state | 158 passed |

Named gates, run individually:

| Gate | Result |
|---|---|
| layer_rules | 74 passed |
| no_dead_symbols | 36 passed — **green** |
| dead_symbol_allowlist_contract | 4 passed |
| no_write_side_rederivation | 27 passed |
| write_surface_placement_guard | 17 passed |
| no_legacy_terminology | 96 passed |
| status_events_writes_gate | 1 failed — inherited: census `coord_seed` |
| mission_resolver_walker_gate | 1 failed — inherited: `coord_seed.py:420` |
| destructive_op_routing | 1 failed — inherited: `commit_router._dirty_paths_in_checkout` |
| **ruff_format_exclude_ratchet** | **1 failed — NEW, B3** |
