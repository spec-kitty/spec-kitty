# Tracer — Approach

Mission: **runindex-feature-runs-port**

## Plan of attack
1. Grounding squad (done): traced every reader/writer of feature-runs.json + run_dir
   consumers; brownfield point-cut; abspath audit; red-first reproducers.
2. Campsite-clean the run-index surface FIRST (distinct behaviour-preserving step): hoist the
   repeated entry-key literals + run-store path segments to named constants, no behaviour change.
3. Red-first regression tests through the real `next` entry point: copy, move, two-process
   concurrent start (issue-pinned `@pytest.mark.regression`).
4. Introduce the RunIndex port (`src/runtime/next/run_index.py`) — sole reader/writer, locked
   RMW, repo-relative token, containment refusal. Rewire `runtime_bridge_io.py` to delegate.
5. Heal migration + `doctor run-index` for legacy absolute indexes.
6. Empty-allowlist gates (single reader; never-persist-absolute).
7. Validate: `make test-fast` + touched module tests + the specific gate files.

## What worked
- The provenance heal (`m_3_2_7`) + `doctor provenance` pair is an exact template.
- run_store is deterministic (`repo_root/.kittify/runtime/runs`) → the token is always
  `.kittify/runtime/runs/<run_id>`, making both serialize and heal trivial and robust.

<!-- append during implementation -->

## Implementation notes (append)
- Port `src/runtime/next/run_index.py` created: constants + lock (`index_lock`) + file I/O
  (`read_index_file`/`write_index_file`) + `serialize_run_dir`/`resolve_run_dir`/`save_index`.
- `runtime_bridge_io` rewired: `get_or_start_run` is now a two-phase locked flow
  (`_run_ref_for_entry`, `_start_new_run` helpers) — reuse under lock (phase 1), start
  outside lock (phase 2), commit under lock with same-mission recheck + orphan rmtree
  (phase 3). `_require_run_state`/`_existing_run_ref`/`_resolve_run_dir_for_mission` resolve
  the token via the port. `load_feature_runs`/`save_feature_runs` are thin delegates.
- Heal migration `m_4_0_0rc5_heal_run_index_paths` + `doctor run-index` sibling.
- Gates: `tests/architectural/test_run_index_single_reader.py` (empty allowlist, AST,
  non-vacuous self-mutation); never-persist-absolute is a port-level invariant test.
- Red-first: all 6 regression tests RED on unfixed code, GREEN post-fix; CLI reproducers
  confirmed copy/move/concurrent on 4.0.0rc5.
- mypy: my modules clean; 21 pre-existing errors in engine.py/runtime_bridge_engine.py/
  prompt_builder.py (spec_kitty_events.mission_next payload drift) are NOT in the diff.
