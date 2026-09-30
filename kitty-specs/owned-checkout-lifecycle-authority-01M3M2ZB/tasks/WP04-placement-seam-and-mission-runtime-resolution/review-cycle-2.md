---
affected_files: []
cycle_number: 2
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-28T22:07:26Z'
reviewer_agent: claude
wp_id: WP04
---

# WP04 review feedback, cycle 2 (reviewer-renata)

**Verdict: CHANGES REQUESTED.** Commits reviewed: 79f58195c (red) and 639b1defa (fix).

The architecture is now right. The owned arm reads the fact. The remaining items are correctness at the coordination edges, one missing single authority, and missing pins.

## Verified good

- **F1 behaviour (checked independently, with counting spies on `get_main_repo_root`, `candidate_feature_dir_for_mission`, `resolve_handle_to_read_path` and `subprocess.run`).** Every owned call made 0 folds, 0 handle walks and 0 git calls. The calls checked were:
  - `mission_context_for`
  - `resolve_artifact_surface` for SPEC and for STATUS_STATE
  - `placement_seam(...).read_dir` with a mid8 handle
  - `locate_work_package`, both found and missing
  - `resolve_action_context` for implement and for tasks_outline with a mid8 handle
  - a handle mismatch

  `_mission_context_for_owned` and `_resolve_status_surface_dir_owned` read `owned.*` directly.
- **F2 path.** A materialised coordination worktree now resolves to `R/.worktrees/<slug>-coord/...`: it exists and is stamped COORD. UNMATERIALIZED raises `OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`.
- **Red-first.** At 79f58195c, 5 tests are red for the F2/F3/F4 reasons. All are green at the tip.
- **Tree hygiene.** The lane tree is clean, the stash stack is empty, and no stray files were committed.
- **Tests and lint.** Targeted tests: 467 passed. `ruff check` is clean, and C901 ≤ 11 holds.

## Ruling on the marker count (9 → 16)

The 7 private helpers carry marked legacy Path parameters: `_resolve_mission_slug`, `_resolve_wp_bearing_fields`, `_resolve_coordination_branch`, `_resolve_topology`, `_resolve_mission_id`, `_resolve_status_surface_dir` and `_assemble_core_fragments`. **This is accepted.**

- The plan's Staging Strategy sanctions "any other function a WP must keep dual for a later WP". T021's table lists `_resolve_wp_bearing_fields` and `_resolve_status_surface_dir` as dual.
- Each helper now has a self-contained owned arm, and its legacy arm is a separate branch.
- Removing the legacy Path from the internals now would force the legacy arm either to mint a fact (a G3 violation) or to duplicate the legacy helpers.
- WP18's job per helper is therefore to delete the parameter and its legacy branch. That is mechanical.

Two bookkeeping defects must be fixed with it (see R5).

## Blocking

### R1 (F1 pins missing): the zero-fold behaviour is true but no test enforces it

Cycle-1 F1 asked for these tests, and none were added:

- `test_primary_kinds_read_dir_is_mission_dir_with_zero_git_calls` still does not monkeypatch `get_main_repo_root` to raise. Its docstring still explains the omission away. Patch `specify_cli.core.paths.get_main_repo_root` and `specify_cli.missions._read_path_resolver.candidate_feature_dir_for_mission` to raise. Assert this for `placement_seam`, `mission_context_for`, `resolve_artifact_surface`, `locate_work_package` and `resolve_action_context` under `owned=`.
- A resolver that raises whenever it is called (the `FakeMissionResolver` pattern) is never consulted with a fact.
- An explicit `topology` that conflicts with the fact raises `OwnedRefusalCode.OWNED_TOPOLOGY_UNSUPPORTED`. The code exists; the test does not.
- The target branch comes from the fact even when `meta.json` says otherwise.

### R2 (F2/F3): the coordination edges are still wrong

Probe: the tests' `_lanes_with_coord_repo` with a `lanes_with_coord` fact, run in each coordination state.

1. **UNMATERIALIZED fails PRIMARY kinds too.**
   - Observed: `resolve_artifact_surface(..., SPEC, owned=fact)` raises `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`.
   - Cause: `_mission_context_for_owned` eagerly assembles the status surface for every kind.
   - Why it matters: T019 table row 3 says a PRIMARY kind reads `owned.mission_dir` under any topology. The UNMATERIALIZED window (mission create → first coordination materialisation) is exactly when spec and plan are written.
   - Required: scope the fail-closed to COORD-partition kinds, for example by building the status surface lazily or resolving it only for non-primary kinds. Add a test: UNMATERIALIZED + SPEC returns `owned.mission_dir`, and UNMATERIALIZED + STATUS_STATE raises.
2. **EMPTY silently falls back to PRIMARY for a COORD kind.**
   - Observed: with the coordination worktree root present but its mission directory removed, `STATUS_STATE` returns `P/kitty-specs/<slug>` stamped **PRIMARY**.
   - Why it matters: `CoordState.EMPTY` is documented as "a fail-closed condition, never a silent primary fallback" (#1716). The default arm fails closed through `resolve_status_surface` → `StatusReadPathNotFound`. The new owned helper copied the legacy fallback. This is the silent PRIMARY substitution for a COORD kind that T019 says to escalate.
   - Required: fail closed with a typed error on EMPTY for COORD-partition kinds, and add a test.
3. **The F3 stamp heuristic.**
   - The current rule is `surface_kind = PRIMARY if read_dir == owned.mission_dir else COORD`. It mis-stamps exactly the EMPTY case above, where the directories coincide in a coordination topology.
   - Required: derive the stamp from the declared, topology-collapsed home instead of path equality. That is: COORD when `routes_through_coordination(owned.topology)` and the kind is not a primary artifact kind, else PRIMARY. This reproduces all 4 rows of the table.
   - With (2) fixed, stamp and path always agree. Keep the row-2 test and add a coordination-topology EMPTY test.

### R3 (F4): one canonical authority, and the matcher is too permissive

1. **Two copies.** `_owned_handle_matches` exists twice, in `resolution.py` and in `support.py` (the charter's single canonical authority).
   - A clean single home exists: `mission_runtime/identity.py`, which already exports `mid8_from_slug` and `resolve_mid8` through `mission_runtime.__all__`.
   - Required: add ONE public predicate there, for example `handle_names_mission(handle: str, mission_slug: str) -> bool`, and export it. Update `tests/architectural/test_mission_runtime_surface.py`. Both sites call it and the private copies are deleted.
   - Alternative: a public `OwnedCheckout.names_handle(handle)` method is equally acceptable. It is one authority on the fact itself and needs no surface change.
2. **Over-permissive prefix.**
   - Current rule: `len(handle) >= 8 and handle.upper()[:8] == mid8`. Probe: `placement_seam(R, "01M1A900-something-else", owned=fact)` is **accepted**.
   - Required: the mission-id form must be a full ULID, meaning 26 characters of Crockford base32, whose first 8 equal the mid8. The fact does not carry `mission_id`, so validate the shape.
   - Add a negative test for an arbitrary string that merely starts with the mid8.

### R4 (F5): one new mypy error remains, and the bridging markers are mislabelled

1. **Residual mypy error.** I ran one `mypy --strict --explicit-package-bases` invocation over 96 files: the seams, every caller of `placement_seam`, `locate_work_package`, `resolve_artifact_surface`, `resolve_placement_only`, `declared_read_surface`, `read_dir_for` and `effective_root_kwargs`, plus the callees `owned_checkout.py`, `identity.py` and `owned_mission.py`.
   - Base 2a61b0e3b: 48 errors. Head: 49.
   - The new one is `src/specify_cli/cli/commands/agent/mission_finalize.py:3353`: `Argument 3 to "placement_seam" has incompatible type "**dict[str, Path]"`, from the literal-dict splat.
   - Fix it the same way as the other sites (`effective_root_kwargs(...)`, or `owned=owned` where the value is already the fact), with a bridging marker naming the converting WP.
   - The 4 errors in `accept.py`/`gates_core.py` are confirmed pre-existing: 4 on base, 4 on head.
2. **Mislabelled markers.** In `tasks_move_task.py`, the 3 sites that now pass `owned=st.owned` are already in final form, yet they carry `# bridging: WP16 converts`. Remove the marker there. Otherwise WP16 must "convert" lines that need no change.
   - The `effective_root_kwargs(...)` sites (4 in `tasks_move_task.py`, 3 in `agent_tasks_ports.py`) are correct and minimal as bridges.
3. **Undeclared edits.** Declare the edits to `tasks_move_task.py`, `agent_tasks_ports.py` and `mission_finalize.py` as out-of-map, with a one-line rationale each, in the commit body and the Activity Log.

### R5: marker bookkeeping

- **The DoD was not amended.** WP04's DoD still says "**9** markers", although the DoD requires the list to be amended in the same PR, and WP18 T096 step 9b still budgets "WP04 9". Both fail at WP18 against 16.
  - Amend the WP04 DoD list to name all 16, per file. Also update WP18 T096 step 9b's WP04 count, as a declared planning-artifact edit.
- **The Activity Log claim is false.** It says that "after WP18 deletes every marked line … effective_root reaches zero occurrences". In fact 61 non-marker `effective_root` references remain in the legacy-branch bodies of `resolution.py`.
  - Restate it: per helper, WP18 deletes the marked parameter **and** its legacy branch.
- **Unmarked parameter.** `_refuse_both(owned, effective_root)` carries an unmarked `effective_root: Path | None` parameter, a G5 hit. Mark it, since it is transitional infrastructure WP18 deletes, and count it in the DoD.

## Non-blocking

- `_resolve_status_surface_dir_owned` keeps `resolver` with `# noqa: ARG001` but then passes it to `_resolve_mission_id`, so the noqa is stale. Remove it.
