---
affected_files: []
cycle_number: 1
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-02T01:51:40Z'
reviewer_agent: claude
wp_id: WP10
---

# WP10 review (reviewer-renata, cycle 1): CHANGES REQUESTED

Lane head reviewed: `bcca41a4eb` (base `7afabf4eff`). The core migration is sound. The tracer and issue matrix now write in place, and a copy2 spy shows 0 router copies for TRACER_FILE/ISSUE_MATRIX on a MATERIALIZED coordination Mission. The B1 guards are green, diff coverage is 100% (84/84), and both re-pins are legitimate. Five items block approval. Each needs a test.

## Blocking

### B1. Rendered outcome lines are printed with Rich markup on (rule c)
- `src/specify_cli/cli/commands/agent/tracer_append.py:179-180` and `src/specify_cli/cli/commands/agent/acceptance_verdict.py:267-268` call `console.print(line)` without `markup=False`.
- Reviewer probe: a surface diagnostic containing `[/red]` raises `rich.errors.MarkupError` (`closing tag '[/red]' ... doesn't match any open tag`). The error-reporting path crashes and masks the refusal it was reporting. Other bracketed text is silently eaten.
- Peer WPs all pass `markup=False`: lane-f `tasks_map_requirements.py:668`, lane-k `spec_commit_cmd.py:430`, lane-l `mission_setup_plan.py:285`.
- Fix: `console.print(line, markup=False)` at both sites. Add a test whose diagnostic contains `[/red]`.

### B2. Not every arm renders the per-surface outcome, and named reason codes drop out of the JSON (rules c and d)
- The router's `error` results carry per-path `refused` fates with named reason codes (`commit_router._safe_commit_error_result`, `commit_router.py:768-782`: PROTECTED_BRANCH_REFUSED, STATUS_LOCK_HELD, ...).
- `tracer_append.py`: the `result.status == "error"` arm (≈L146-152) and the `refused` arm (≈L133-144) emit only `diagnostic`. They render no `render_commit_outcome` lines and carry no `surfaces` key in JSON.
- `acceptance_verdict.py::_emit_write_outcome`: the `refused` and `error` arms (≈L248-259) have the same gap.
- The acceptance-verdict success text arms (`_run_criterion_mode` ≈L384-387, `_run_negative_invariant_mode`) print only the green tick, with no surface lines. The tracer success arm does render them.
- Fix:
  - On every arm, merge `**commit_outcome_payload(result)` into the JSON payload and print `render_commit_outcome(result)` lines (with `markup=False`) in text mode.
  - Keep the exit code coming from `commit_outcome_exit_code` together with the legacy status checks.
  - Add one test per arm: an `error` result with a named `refused` fate must expose `surfaces[0].refused[0].reason` in JSON and render the line in text.

### B3. T057 (acceptance-verdict `write_dir`) has no discriminating test; the mutation survives
- Mutation: reverting `_matrix_write_dir` to `placement_seam(...).read_dir(ACCEPTANCE_MATRIX)` leaves 403 passed, 1 skipped across `tests/specify_cli/acceptance`, `tests/acceptance`, `tests/integration/test_accept_matrix_coord_partition.py` and `tests/integration/test_issue_2404_acceptance_matrix_write_surface.py`.
- All 3 tests in `tests/acceptance/test_acceptance_matrix_write_dir.py` are GREEN at base `7afabf4eff`, so the T057 leg had no red-first test.
- A scenario that does discriminate (reviewer probe):
  1. pre-fix EMPTY Mission (`make_prefix_coord_mission(worktree="empty")`), root matrix with FR-001 and FR-002 pending, committed;
  2. `acceptance_verdict(FR-001=pass)`;
  3. `git worktree remove --force <coord worktree>`, which leaves an UNMATERIALIZED local head that carries the committed verdict;
  4. `acceptance_verdict(FR-002=pass)`.
  - HEAD: exit 0, and the coordination branch holds `{FR-001: pass, FR-002: pass}`.
  - read_dir mutant: a raw `CoordinationWorktreeUnmaterialized`.
- Fix: add this test. It also pins the lost-update protection the binding correction asked for. Also tighten `test_remote_only_refuses_before_any_write`: `pytest.raises((typer.Exit, Exception))` accepts any crash, so pin the actual exception type, `CoordinationWorktreeUnmaterialized`.

### B4. `scaffold_acceptance_matrix` still stages at root, so copy2 still fires for ACCEPTANCE_MATRIX (decision `plan.design.owning-copy-flip-allocation`)
- `src/specify_cli/acceptance/matrix.py` (≈L918-927), a WP10-owned file, calls `write_and_commit_acceptance_matrix(repo_root, mission_slug, feature_dir, ...)` with the PRIMARY `feature_dir`.
- Reviewer probe with a copy2 spy on a MATERIALIZED coordination Mission: `scaffold_acceptance_matrix(root_dir, ..., home_dir=coord_dir, repo_root=repo)` triggers `shutil.copy2(<root>/kitty-specs/<m>/acceptance-matrix.json -> <coord worktree>/kitty-specs/<m>/acceptance-matrix.json)`. It also returns the root path.
- The new comment at `matrix.py:532-542` and the design-decisions entry say this is "left for WP15". That is not accurate:
  - WP15 (approved, lane-m) owns only `mission_finalize.py`.
  - WP15 already resolves `home_dir` through `write_dir(ACCEPTANCE_MATRIX)` (lane-m `mission_finalize.py:3739-3765`).
  - WP15 cannot edit `matrix.py`.
- The binding correction said to cover this caller or record it as read-only/unaffected. It is a root-staging writer, so it is neither. Once WP20 drops copy2, this scaffold write is lost for coordination Missions.
- Fix:
  - When `repo_root` is given, write at `home` (the declared/write home), not `feature_dir`, and return the path actually written.
  - With every caller migrated, `primary_paths_created_this_invocation` can become empty.
  - Correct the comment.
  - Add a copy2-spy test showing that no router copy happens for ACCEPTANCE_MATRIX.
  - This is safe in lane-h: MATERIALIZED gives the coordination dir (in place), EMPTY gives `writes_to_planning_dir`, so a bare write with no seam call, and UNMATERIALIZED makes `read_dir` raise, which the caller catches.

### B5. The binding correction's PUBLISHED test is missing
- The binding correction asked for one post-consolidation (D23) test of the migrated writers. `test_write_seam_surfaces.py` unit-tests `_commit_post_consolidation_write` directly. `test_issue_3033_post_consolidation_write.py` uses `write_artifact(files=...)`, not the migrated `stage=`/`write_dir` writers.
- Reviewer probe (behaviour is correct): `_build_e2_mission_coord` then `append_tracer_finding(...)` and `write_issue_matrix(...)` both return `committed` on `main` with a single `primary` SurfaceOutcome.
- Fix: add that test, with acceptance-verdict too if cheap.

## Non-blocking (address or record)
- N1. `write_issue_matrix` re-resolves `write_dir` inside its `stage=` thunk, which runs inside `issue_verdict`'s locked splice.
  - This departs literally from the binding correction ("never ... resolve write_dir lazily inside _stage, within the locked splice").
  - In practice it is idempotent (the pre-lock call already materialized), and `write_artifact`'s gate already calls `write_dir` again inside the lock.
  - To make it literal, consider an optional keyword `matrix_dir: Path | None = None` (resolve lazily when it is `None`), passed by `issue_verdict`.
- N2. `acceptance_verdict` resolves `write_dir` before the matrix read and the criterion validation, so an unknown-criterion or no-matrix invocation still materializes and seeds. The binding correction requires this seed-before-lock side effect to be recorded explicitly in `design-decisions`. `design-decisions.md:122` records the resolve-before-lock, but not the seed side effect.
- N3. Process: there is no separate red-first commit. I reproduced the retro-verified red: 18 failed / 7 passed at `7afabf4eff`. However:
  - 5 of the issue-matrix reds are only `TypeError`s from the signature change.
  - With the base signature restored, 4 of 5 pass at base; only `.surfaces` is red.
  - 0 of 3 acceptance tests are red.
- N4. The `tests/tasks/test_issue_matrix_write_dir.py::test_issue_matrix_write_prefix_empty_seeds_then_writes_in_place` docstring promises "one seed commit", but the test never asserts the seed count (the tracer twin does).

## Verified OK (no action)
- **`write_issue_matrix` signature change:** dropping `feature_dir` is justified. All callers are updated (`scaffold_issue_matrix`, `issue_verdict`, `issue_matrix_migration`, and 4 test files), and no other lane adds a caller.
- **Tracer re-pin:** legitimate under D22. It still pins data preservation: original plus new finding on the coordination branch, and no root residue. The remote-only refusal is still pinned.
- **Legacy-md re-pin:** legitimate, superseded by `owning-copy-flip-allocation`. It is not one of the B1 row-preservation guards, which are unchanged and green, and its falsifiability is kept.
- **`fold_into_caller_commit`:** the `declared_read_surface` predicate is correct for coord, lanes_with_coord, lanes, single_branch and owned.
- **`gates_core.py`:** leaving it untouched is correct; its `commit=False` leg is read-only evaluation.
- **IN_PLACE router claim:** verified for TRACER_FILE and ISSUE_MATRIX.
- **`test_no_read_side_bypass.py`:** only WP10's own entry was removed.
- **Lane state:** the lane is clean and no stash leaked.
- **Static checks:** ruff and format are clean. mypy shows the same single pre-existing error as base, at `issue_matrix_migration.py:254`. C901 is ≤ 15.
