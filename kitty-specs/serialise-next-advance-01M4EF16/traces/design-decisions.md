# Design Decisions — serialise-next-advance

Running log of design choices and their rationale. Append dated entries.

## Decisions carried in from research (to be ratified in spec/plan)

- **[2026-10-08][research] Structural fix over a symptomatic patch.** The target
  invariant is: "Advancing a run is serialised: a stale advance is refused with a
  named reason, never silently re-planned as success; at most one `next` mutates a
  run at a time." Prefer closing the defect class by construction (a locked,
  compare-and-swap advance) over patching one path.
- **[2026-10-08][research] Refusal must fit the existing `next` JSON contract.**
  A stale/contended advance should surface as the existing `Decision kind=blocked`
  + `reason` with no new kind and no new exit code (composition's EDGE-003 shape).
  If it cannot, that is an owner/ADR decision point.
- **[2026-10-08][research] Lock-ordering caution.** `get_or_start_run` already
  takes the run-index lock during bootstrap; a new per-run-dir lock must not
  deadlock against it. `STALE_AFTER_S_DEFAULT`=60s vs the ~10s hold ceiling bounds
  how long an advance may hold the lock (composition dispatch runs executors).
- **[2026-10-08][research] Fold the `provide_decision_answer` race** (no issue yet;
  file one or cover it in the PR). Do NOT fold #5112 (livelock), #5099, #5853, #5855.
  Residual: a refusing stale path can make loops spin on `blocked` (#5112).
- **[2026-10-08][research] Adjudicated design after the architect+implementer squad.**
  Lock-scope divergence resolved from source toward the architect lens: a SHORT
  commit-span per-run-dir lock (`<run_dir>/state.json.lock` via
  `kernel.locks.machine_file_lock`) + a bootstrap-anchored expected-`issued_step_id`
  CAS threaded into plan/commit — NOT a lock held across the composition executor
  (that would breach the 10s `_MAX_HOLD_DEFAULT`/NFR-002 ceiling and risk the 60s
  stale-reclaim). The CAS closes the bootstrap→plan window; the lock only atomizes
  the commit RMW.
- **[2026-10-08][research] Lock must cover FOUR writers**, not two: `_commit_advance`,
  `provide_decision_answer`, the retrospective rollback (`runtime_bridge.py:1111/1121`),
  and (unique-temp fix only, no lock) run-start `_write_snapshot`. The rollback writer
  is deleted by the unmerged sibling `issue-5883-*`; on current main it is live, so we
  cover it, and drop that coverage if the sibling lands first.
- **[2026-10-08][research] Engine path refuses + catches `LockAcquireTimeout`** (not
  just `StaleAdvancePlan`); refusal reuses `kind=blocked`+`reason`+exit 1 — no new
  kind/exit code. Short 4.x ADR to record the run-dir writer model.
- **[2026-10-08][research] Acceptance gate = all THREE red-first repros** (#5682
  composition window, #5854 engine double-apply, answer-vs-next) + the inverted pin.
  Biggest risk is scope under-reach: fixing only `_dn_advance_engine` leaves #5682 and
  the answer race live.

## WP01 implementation (lane-a)

- **[2026-10-08][implement] Non-reentrant run-cursor lock; lock in the public
  `commit_advance`, not inside `_commit_advance`.** The expected-step CAS re-read
  MUST be inside the lock for the true-concurrency TOCTOU to close, so the lock
  wraps `_refuse_stale_plan` + `_commit_advance` in the public `commit_advance`
  (and `next_step` wraps its own `_commit_advance`); the shared inner
  `_commit_advance` stays lock-free so there is no nesting and no self-deadlock
  with a non-reentrant lock. Non-reentrant is deliberate: it lets the
  deterministic held-lock-blocks probe run in a single thread (separate fds
  conflict under `fcntl`).
- **[2026-10-08][implement] Retrospective capture + rollback locked individually,
  not as one span.** The capture (`_dn_capture_pre_speculative_state`) and the
  rollback writer (`_dn_rollback_buffered_run_state`) each acquire the lock
  briefly; they do not hold one span across the engine advance, which would
  deadlock the non-reentrant lock that `commit_advance` takes between them. Each
  cursor writer is still individually serialised (FR-003/FR-004). The rollback
  logs and skips on a lock timeout, consistent with its log-only failure mode.
- **[2026-10-08][implement] Engine-path refusal surfaces a mapped `blocked`
  Decision from `_dn_advance_engine` (return type widened to
  `NextDecision | Decision`); `_dn_decision_materialize` short-circuits a returned
  `Decision`, discarding any retrospective buffer. The `next_step` fallback is
  removed; `LockAcquireTimeout` is caught alongside `StaleAdvancePlan`.
