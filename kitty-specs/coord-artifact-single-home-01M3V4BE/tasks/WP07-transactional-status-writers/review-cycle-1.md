---
affected_files: []
cycle_number: 1
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-01T21:21:54Z'
reviewer_agent: claude
wp_id: WP07
---

# WP07 review, cycle 1: changes requested

Reviewer: claude (reviewer-renata, opus). Lane-o tip `b35b12f6f2`, base `e7b085d26c` (linear; no further merges in the range).

## What already passes

- **Writers route through `write_dir`.** `BookkeepingTransaction._acquire_locked`, `status_transition._resolve_fallback_coord_worktree`, `agent_tasks_ports.RealCoordCommitRouter.feature_write_dir` and `lanes/recovery.reconcile_status` now route through `placement_seam(...).write_dir(STATUS_STATE)`.
- **No read-root derivation remains.** No `resolve_feature_dir_for_mission` or bare `CoordinationWorkspace.resolve` write derivation is left in the four owned modules, and the two read-side-bypass allow-list entries were removed (a shrink).
- **Typed refusals propagate unchanged.**
- **Inherited lane-a regressions are GREEN on lane-o:**
  - status-events census (`coord_seed` added with a sound "byte-level carry, not a transition emitter" justification);
  - walker gate;
  - destructive-op routing (`_dirty_paths_in_checkout` reuses `ref_advance._dirty_entries`, and the baseline entry was trimmed).
- **`COORD_RECORD_IN_ROOT_CHECKOUT` behaviour.** The WP05 refine and B16 tests are green within `tests/coordination/` (418-file dir run, below).
- **Owned seed anchor.** `_restore_root_files` now anchors on `_lock_root(request)`. The new owned EMPTY test is real: red at `c30aa1c8e5` with `ValueError`, carried records, both checkouts clean.
- **Lock order.** The status lock comes before the workspace lock (the `write_dir` boundary tests). T042's reason for testing at the `write_dir` boundary, not through the full emit, is accepted: the outer `feature_status_lock` waits unbounded, so a full-emit contention test would hang instead of fail.
- **#5410.** Still red at base and tip: `tests/characterization/test_trio_json_envelope.py::TestImplementRecoverJson::test_coord_mission_no_crashed_sessions` (unmaterialized coordination error). It is identical at `e7b085d26c`, so not WP07's.
- **Static checks.** ruff check, C901 and `ruff format --check --force-exclude` are clean. mypy --strict errors in the touched modules are identical in count to base (inherited).

## Blocking

**B1 (NEW red gate): `commit_router.py` was fully formatted.**
- It is on `[tool.ruff.format].exclude`. Five formatting-only collapses (L700, L1009, L1228, L1661, L1686) plus a blank line made it format-clean, so `tests/architectural/test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_still_genuinely_reformats` is now RED: "['src/specify_cli/coordination/commit_router.py'] already formatted".
- **Required:** revert those formatting-only hunks. Keep only the `_dirty_paths_in_checkout` change, and do not touch `pyproject.toml`. This is the same rule WP06 and WP12 were rejected for.

**B2: the T037 deviation is not justified, and the post-fix EMPTY row is missing.**
- The prompt makes the move-task CLI the binding entry point for every T037 scenario. The module docstring claims UNMATERIALIZED/EMPTY cannot be driven through the CLI, because `_mt_current_event_lane` reads blank via `git show <coordination_branch>:…` for a never-seeded pre-fix Mission.
- **Reviewer probe, which contradicts that claim.** Setup:
  - `make_prefix_coord_mission(COORD, worktree="absent"|"empty")` plus your own `_write_wp01_task_file` (WP01 `planned`, committed in the root log, as finalize-tasks does);
  - then `spec-kitty agent tasks move-task WP01 --to claimed --agent testbot --json` through `CliRunner`, **without `--force`**.

  Both states exit 0. The coordination log holds 6 events (carried plus new), and `status_events_path` names the coordination worktree.
- **Required:**
  - Drive the UNMATERIALIZED-local, pre-fix EMPTY, second-move-task and MATERIALIZED-forked scenarios through the CLI, as T037 specifies. Keep the transactional-shell tests as additional unit coverage if you like.
  - Add the **post-fix EMPTY row** (post-tasks squad R-m3), which is missing entirely. Seed via `write_dir`, delete the coordination Mission dir, then run move-task. Assert:
    - a loud WARNING;
    - `RESTORED_FROM_BRANCH`;
    - the event lands on the coordination log;
    - nothing is written to the root checkout.
  - Add the T037 pre-fix-EMPTY assertions that are absent:
    - `event_lamport` of the new event is strictly greater than every carried event;
    - exactly one `chore(<mission>): seed coordination surface` commit;
    - the root copy is restored.
  - Parametrize over `coord` and `lanes_with_coord` where not already done.
- If a specific shape genuinely blocks the CLI (for example no root `planned` event), name it in a test, and route the read-side fix to the coordinator. The common pre-fix shape does not block.

**B3: diff coverage is 88.1%, below the ≥90% NFR-003 gate.** Measured over the diff against `e7b085d26c`, 74/84 changed statements:

| File | Uncovered lines |
|---|---|
| `transaction.py` | 149, 157 (`_canonical_coord_mission_slug` composed and bare fallbacks); 228-230 (the `BookkeepingWorktreeMissing` wrap of an unexpected `write_dir` failure) |
| `lanes/recovery.py` | 825-826 |
| `status_transition.py` | 302, 312 |
| `coord_seed.py` | 518 |

Add focused tests for each branch, especially the wrap: an unexpected exception must become `BookkeepingWorktreeMissing`, while typed refusals propagate.

**B4: 15 new unused `# noqa` suppressions (NFR-005, "no new suppressions").**
- `PLC0415` ×11, `SLF001` ×1 and `BLE001` ×2 across `commit_router.py`, `status_transition.py`, `transaction.py` and `lanes/recovery.py`. None of those rules is enabled, so each is a RUF100 unused-directive.
- The WP04 binding correction already ruled out `# noqa: PLC0415`. Remove them, keeping the rationale as plain comments where useful.

## Non-blocking (record a decision or fix while in there)

- **N1 (`commit_idempotent` widening):**
  - Dropping the `self._staged_paths and` precondition also turns the "every requested path was missing on disk" case into a silent no-op receipt. `implement.py:1014` does `continue` for absent sources, and previously raised "commit() called with no events or artifacts".
  - Narrower alternative: no-op on zero staged paths only when every requested path is already present and identical at the destination HEAD.
  - Otherwise record the accepted risk in `design-decisions` and pin the motivating case (seed carried the content first) with a test.
- **N2 (walker gate, judged against your question):**
  - Generalizing the single scaffold-snapshot exemption into `_FUNCTION_LEVEL_EXEMPTIONS` and adding `coord_seed._cleanup_stale_seed_temp_dirs` IS allowlist growth (1 → 2). It is function-scoped, the rationale is valid (it is not mission-identity resolution, and `MissionResolver` has no API for it), and the gate has no baseline.
  - Accepted, but a structural alternative avoids the exemption: put the seed scratch dir outside `kitty-specs/`, for example `<coord_wt>/.spec-kitty-seed-tmp/`, and `os.rename` into `kitty-specs/<dir>`. That is the same filesystem and still atomic, and nothing kitty-specs-tainted is enumerated.
  - Consider it as a follow-up, or record why not.
- **N3 (census):** the new census comment cites `#<see mission tracer>`, which is a placeholder; put the real issue or tracer reference. The gate's own message also asks for the matching `design-notes/WP03-gates.md` update; note where the justification lives.
- **N4 (owned seed test):** it covers only the CLEAN-root path, where `_restore_root_files` is a no-op. Add a dirty-tracked or untracked root-copy variant under `owned_root`, so the `git checkout`/unlink actually runs against the owned checkout.
- **N5 (`_dirty_paths_in_checkout` parsing):** `entry[3:].split(" (", 1)[0]` mis-parses quoted porcelain paths (spaces or non-ASCII) and rename entries (`old -> new`). Either ask `_dirty_entries` for structured output, or add a test with a space in the path.

## Tests run by the reviewer (`-n 3 --dist loadfile`, tip `b35b12f6f2`)

| Suite | Result |
|---|---|
| `tests/coordination/` + `tests/specify_cli/coordination/` + `tests/status/` + `tests/lanes/` + test_coord_read_seam_callers + test_agent_tasks_ports_write_dir | 2870 passed, 18 skipped |
| 214 further files matching `agent_tasks_ports\|move-task\|move_task\|status_transition\|BookkeepingTransaction\|coordination.transaction\|lanes.recovery\|reconcile_status` (outside the dirs above, excluding e2e/stress) | 3539 passed, 28 skipped, 2 xfailed, **1 failed**: `test_trio_json_envelope::…no_crashed_sessions` (#5410, red at base too) |
| 40 matching integration files + the 4 B1 guards | 575 passed, 1 skipped |

Named gates, run individually:

| Gate | Result |
|---|---|
| layer_rules | 74 passed |
| no_write_side_rederivation | 27 passed |
| write_surface_placement_guard | 17 passed |
| status_events_writes_gate | 25 passed (census green) |
| mission_resolver_walker_gate | 4 passed (green) |
| destructive_op_routing | 37 passed (green) |
| no_legacy_terminology | 96 passed |
| no_read_side_bypass | 38 passed |
| no_dead_symbols / dead_symbol_allowlist_contract | 1 failed each — `COORD_SEED_TRAILER`, transitional, WP06 |
| **ruff_format_exclude_ratchet** | **1 failed — NEW (B1)** |
