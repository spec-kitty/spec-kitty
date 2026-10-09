# Approach — serialise-next-advance

Running log of how the approach evolves. Append dated entries; do not rewrite history.

## Initial approach (from the operator brief + pre-spec research)

- **[2026-10-08][research] Two-layer root cause confirmed on main c0a08ad6.**
  (1) The advance never records which step its caller evaluated: bootstrap reads
  `snapshot.issued_step_id` (runtime_bridge.py ~551) but `plan_advance`
  re-reads `state.json` (engine.py:429) and `commit_advance`'s stale check
  (engine.py:599-627) only covers that *second* read, not the bootstrap→plan
  window — the #5682 mechanism on both the composition and engine paths.
  (2) No mutual exclusion covers read→plan→write on a run dir; `_write_snapshot`
  uses a fixed `state.json.tmp` (engine.py:129-140); `provide_decision_answer`
  (engine.py:797-873) is a third unlocked writer.
- **[2026-10-08][research] Chosen direction (to be validated by the post-spec/post-plan squads):**
  (a) thread the bootstrap-evaluated `issued_step_id` into plan+commit and refuse on
  mismatch, on both paths; (b) hold a per-run-dir `kernel.locks.machine_file_lock`
  around the read→plan→write span (exemplar: `run_index.py`), covering
  `provide_decision_answer`, with a unique temp name in `_write_snapshot`;
  (c) make `_dn_advance_engine` refuse a stale plan with a `blocked` Decision +
  named reason (like composition's EDGE-003), instead of the `next_step` fallback.
- **[2026-10-08][research] Constraint:** the runtime layer cannot import
  `specify_cli` (layer rules), so PR #5890's `mission_write_lock` is not reusable;
  `kernel.locks` is the only lock door (gated by `test_lock_primitive_ban.py`).

## WP01 implementation (lane-a)

- **[2026-10-08][implement] Landed the adjudicated design, five parts, ATDD red-first.**
  (1) Expected-step CAS: `AdvancePlan.expected_issued_step` (default `None`),
  threaded from `plan_advance`; `commit_advance`'s staleness authority widened in
  one place (`_refuse_stale_plan`) to also refuse when the live on-disk
  `issued_step_id` != the caller-evaluated step. Bridge threads
  `ctx.current_step_id` through both `_dn_plan_composition_advance` and
  `_dn_preresolve_wp_workspace`.
  (2) New `src/runtime/next/run_lock.py` (`run_cursor_lock` /
  `run_cursor_lock_path`), a `run_index.py`-style dedicated `state.json.lock`
  sidecar over `kernel.locks.machine_file_lock` (blocking, 10s). NON-reentrant:
  `fcntl` conflicts across fds even in one process, so the held-lock-blocks probe
  works same-thread and the inner `_commit_advance` never re-acquires.
  (3) `_write_snapshot` now stages a UNIQUE `tempfile.mkstemp` temp (fsync →
  `os.replace`), cleaning it up on a failed publish.
  (4) The lock wraps the commit read→validate→append→write in `commit_advance`
  and `next_step`, the whole RMW in `provide_decision_answer` (via the extracted
  `_apply_decision_answer`), and the retrospective capture + rollback writer in
  the bridge. It is NEVER held across composition executor dispatch.
  (5) `_dn_advance_engine` refuses a stale plan / lock timeout with a `blocked`
  Decision (named reason, EDGE-003 shape) and no longer falls back to
  `runtime_next_step`.
- **[2026-10-08][implement] Half-by-half proven:** reverting each of the five
  parts turns at least one named test red (CAS→cas-refuses; engine-refusal→
  inverted bridge unit test; answer-guard→provide_decision_answer held-lock;
  lock→commit held-lock + true-concurrency barrier; unique-temp→collision pair).
