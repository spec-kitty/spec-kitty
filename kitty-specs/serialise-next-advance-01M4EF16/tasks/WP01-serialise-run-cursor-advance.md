---
work_package_id: WP01
title: Serialise the run-cursor advance (lock + CAS + engine/bridge refusal)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-5854-serialise-next
merge_target_branch: issue-5854-serialise-next
branch_strategy: Planning artifacts for this mission were generated on issue-5854-serialise-next. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5854-serialise-next unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-serialise-next-advance-01M4EF16
base_commit: 4b62559907f4cf481d7ede02f50d78a3fa5c5438
created_at: '2026-10-08T19:50:49.778477+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
phase: Phase 1 - Implementation
history:
- at: '2026-10-08T19:39:08Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/runtime/next/
create_intent:
- src/runtime/next/run_lock.py
- tests/runtime/test_run_lock.py
- tests/runtime/test_next_advance_true_concurrency.py
- tests/next/test_engine_serialisation.py
- tests/next/test_next_concurrency.py
execution_mode: code_change
model: ''
owned_files:
- src/runtime/next/_internal_runtime/engine.py
- src/runtime/next/run_lock.py
- src/runtime/next/runtime_bridge.py
- src/runtime/next/runtime_bridge_engine.py
- tests/runtime/test_run_lock.py
- tests/runtime/test_next_advance_true_concurrency.py
- tests/next/test_engine_serialisation.py
- tests/next/test_next_concurrency.py
- tests/next/test_runtime_bridge_unit.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Serialise the run-cursor advance

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the
frontmatter before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load `spec-kitty charter context --action implement --json` and apply ATDD-first
(red before green), smallest-viable-diff, and locality of change.

---

## Objectives & Success Criteria

Close **#5854** and **#5682** by construction. On the final commit:

- Two overlapping `next --result success` advances on one run never both complete a
  step — the later-committing one is refused with a named reason (SC-001, SC-002).
- The engine path returns a `blocked` Decision on a stale plan and never re-applies
  `success` via `next_step` (FR-002).
- The run-cursor read-modify-write is serialised by a per-run-dir lock covering
  `_commit_advance`, `provide_decision_answer`, and the retrospective-rollback
  writer (FR-003, FR-004).
- Snapshot writes use a unique staging temp (FR-006).
- Refusals reuse the existing `kind=blocked` + `reason` + exit-1 contract — no new
  kind, no new exit code (FR-005).
- Every independent part is pinned red-first; reverting any one part turns at least
  one test red (SC-003). NFR-001 (lock span excludes executor dispatch), NFR-002
  (exactly one acquire/release uncontended), NFR-003 (only `kernel.locks`).

## Context & Constraints

Read first (do not re-derive):
- `kitty-specs/serialise-next-advance-01M4EF16/research.md` — the verified
  two-layer root cause, the adjudicated design, the writer inventory, prior-art
  tests, and the squad dispositions. **This is the authoritative design.**
- `kitty-specs/serialise-next-advance-01M4EF16/plan.md` — the Implementation
  Concern Map (IC-01..IC-05) and the structure decision.
- `kitty-specs/serialise-next-advance-01M4EF16/spec.md` — FR/NFR/SC and the
  non-vacuity controls each test must satisfy.
- `.kittify/charter/charter.md` — DIRECTIVE_043 (single lock primitive), layer
  rules, terminology.

Hard constraints:
- **Layer rule (C-001):** `src/runtime/next/**` and `src/kernel/**` MUST NOT import
  `specify_cli`. The `specify_cli` mission-write lock is not reusable here.
- **Single lock primitive (NFR-003, DIRECTIVE_043):** all cross-process locking
  goes through `kernel.locks.machine_file_lock`. No raw `fcntl`/`msvcrt`/`filelock`.
  `tests/architectural/test_lock_primitive_ban.py` stays green (empty allowlist).
- **Lock hold (NFR-001):** acquire the run-cursor lock ONLY around the commit
  read→validate→append→write; NEVER hold it across composition executor dispatch
  (`runtime_bridge.py` `_dn_composition_dispatch` / `_dispatch_via_composition`).
- **No deadlock (C-002):** the run-index lock in `get_or_start_run` is released
  before any run-cursor lock is acquired; never hold both nested.
- **Minimise bridge churn (C-003):** keep the lock/CAS logic in `engine.py` /
  `run_lock.py`; keep `runtime_bridge*.py` edits to the threading + refusal only
  (the sibling branch `issue-5883-mission-writer-followups` rewrites that file).
- **Terminology:** "Mission"/"run"/"run cursor"; never introduce `feature*`.
- **Contract (FR-005):** reuse `StaleAdvancePlan` → the existing EDGE-003 `blocked`
  Decision mapping; add no new Decision kind and no new exit code.

Key current-main anchors (verified @ c0a08ad6):
- `engine.py:410` `plan_advance`, `:429` its re-read, `:277` `apply_result`,
  `:599-627` `commit_advance`/`StaleAdvancePlan`, `:529-571` `_commit_advance`,
  `:129-140` `_write_snapshot` (fixed `state.json.tmp`), `:797-873`
  `provide_decision_answer`.
- `runtime_bridge.py:549-553` bootstrap read of `issued_step_id` into
  `ctx.current_step_id`; `:950-963` `_dn_plan_composition_advance`; `:1234-1248`
  `_dn_advance_engine` (the `next_step` fallback); `:924-947` `_advance_failed_decision`
  (EDGE-003 blocked shape); `:1079-1095` `_dn_capture_pre_speculative_state`,
  `:1111/1121` `_dn_rollback_buffered_run_state` (the rollback writer).
- `runtime_bridge_engine.py:209-270` `advance_run_state_after_composition` (commit leg).
- Exemplar lock module: `src/runtime/next/run_index.py:124-131` (`_lock_path`,
  `index_lock`); primitive: `src/kernel/locks.py` (`machine_file_lock`,
  `LockAcquireTimeout`); unique temp: `src/kernel/atomic.py` (`atomic_write`).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed
> lane from `lanes.json`; do not reconstruct the path.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first engine + lock tests

- **Purpose**: Pin the engine-level parts before writing them (ATDD).
- **Files**: `tests/runtime/test_run_lock.py` (new),
  `tests/next/test_engine_serialisation.py` (new).
- **Steps**:
  1. `test_run_lock.py`: assert the helper returns a `SyncMachineFileLock` whose
     path is `<run_dir>/state.json.lock` (a dedicated sidecar, never `state.json`),
     and that a held lock blocks a second blocking acquire until released
     (reuse the barrier/`machine_file_lock` idioms; no sleep).
  2. `test_engine_serialisation.py`, using the light `_start` scaffold from
     `tests/next/test_engine_commit_primitives.py` (import or mirror it):
     - **CAS unit** (pins T005): `plan_advance` then force the on-disk
       `issued_step_id` to differ from the caller-evaluated step, then
       `commit_advance` → `StaleAdvancePlan`, nothing written. Positive control:
       a matching expected step commits and issues the next step.
     - **held-lock-blocks** (pins T006, deterministic, per-PR): acquire the
       run-cursor lock in the test, then call the commit path with a short
       blocking timeout and assert it raises `LockAcquireTimeout` (i.e. the commit
       path really takes the lock). Red when the lock is removed from the commit.
       **Same-fixture positive control (required, non-vacuity):** on the SAME
       fixture with the lock free, an uncontended commit completes and issues the
       next step — so the negative assertion proves the lock, not an unrelated
       timeout.
     - **provide_decision_answer under lock** (pins T006): same held-lock-blocks
       probe against `provide_decision_answer`; plus a no-overlap positive control
       that records the answer.
     - **unique-temp collision pair** (pins T004): the discriminating same-fixture
       pair from FR-006 — two writers to one run_dir corrupt/lose a write under the
       FIXED `state.json.tmp` name and both succeed under unique temp names. (Drive
       the two writers into the shared staging window deterministically — a
       `monkeypatch`/interleave on the stage-then-replace, not a filename-equality
       proxy.)
  - Mark the behavioral race repros `@pytest.mark.p0_repro(issue=5682)` /
    `(issue=5854)` and `@pytest.mark.regression` while red (they run in the
    nightly p0-repro lane); remove `p0_repro` and keep `regression` once green.
- **Notes**: run these against the unmodified source first and confirm RED. Use
  injected interleaves / barriers, never sleeps.

### Subtask T002 – Red-first bridge/e2e tests + invert the fallback pin

- **Purpose**: Pin the bridge parts and the end-to-end races; invert the pin that
  currently enshrines the #5854 fallback.
- **Files**: `tests/next/test_next_concurrency.py` (new),
  `tests/runtime/test_next_advance_true_concurrency.py` (new),
  `tests/next/test_runtime_bridge_unit.py` (modify — invert one test).
- **Steps**:
  1. `test_next_concurrency.py` (per-PR, p0_repro while red):
     - **#5682 composition window**: monkeypatch
       `runtime_bridge_composition._dispatch_via_composition` to run ONE peer
       `engine.next_step(...)` after the real dispatch, then assert the outer
       `decide_next_via_runtime(...)` returns `kind == "blocked"` and does not
       complete the peer's step. (Fixtures: `_next_mission_scaffold.scaffold_software_dev`
       + `advance_to_step` to `implement`, WP01 `for_review`.)
     - **#5854 engine path**: force `commit_advance` stale and assert
       `_dn_decision_materialize(ctx)` (or the full entry) returns `blocked` and
       `runtime_next_step` is called 0 times; nothing written.
     - **answer-vs-next**: one-shot monkeypatch of `engine._read_snapshot` to run a
       peer `next_step` between the answer's read and write; assert neither mutation
       is lost. (Fixture: `test_provide_decision_answer_characterisation._input_run`.)
  2. `test_next_advance_true_concurrency.py` (`@pytest.mark.stress`): a
     `threading.Barrier` releases two advances that both read the same issued step
     INTO the commit window simultaneously; assert exactly one completes and the
     other refuses — RED with the lock removed but the CAS retained. This is the
     TRUE-concurrency proof the CAS alone cannot satisfy.
  3. In `test_runtime_bridge_unit.py`, **invert**
     `test_pre_resolution_is_not_reused_for_a_different_issued_step` (keep the
     `_stale` `commit_advance` monkeypatch; now assert the result is `blocked` and
     `runtime_next_step` call count is 0). Do NOT delete it; leave its sibling
     resolve-before-persist assertions untouched.
- **Notes**: confirm each is RED on the base before moving on.

### Subtask T003 – Add the per-run-dir lock helper

- **Purpose**: One owning module for the run-cursor lock resource.
- **Files**: `src/runtime/next/run_lock.py` (new).
- **Steps**: mirror `run_index.py`: a `_lock_path(run_dir)` returning
  `run_dir / "state.json.lock"` (dedicated sidecar, never the payload — lock
  guarantee G1), and a `run_cursor_lock(run_dir)` returning
  `machine_file_lock(lock_path, blocking=True, timeout_s=<~10s>)`. Add `__all__`.
  Keep it stdlib + `kernel` only.
- **Notes**: the timeout must be comfortably below `STALE_AFTER_S_DEFAULT` (60 s);
  10 s matches `run_index._LOCK_TIMEOUT_S`.

### Subtask T004 – Unique snapshot staging temp

- **Purpose**: Two writers to one run_dir must not collide on the staging path (FR-006).
- **Files**: `engine.py` `_write_snapshot` (`:129-140`).
- **Steps**: replace the fixed `state.json.tmp` with a unique temp (prefer
  `kernel.atomic.atomic_write`, or `tempfile.mkstemp` in-dir then `os.replace`),
  preserving the fsync-then-replace durability. This lands independently of the
  lock and also protects the lock-free run-start writer.

### Subtask T005 – Expected-step compare-and-swap (close #5682)

- **Purpose**: Refuse an advance whose run cursor changed since the caller
  evaluated its step — on both paths — by WIDENING the existing `StaleAdvancePlan`
  authority (not a new parallel gate; doctrine note).
- **Files**: `engine.py` (`plan_advance`, `commit_advance`, `AdvancePlan`),
  `runtime_bridge.py` (thread `ctx.current_step_id`), `runtime_bridge_engine.py`
  (carry it through the composition commit leg).
- **Steps**:
  1. Carry the caller-evaluated `issued_step_id` into the advance (e.g. an
     `expected_issued_step` on `AdvancePlan` set from `ctx.current_step_id`, or a
     parameter threaded into `plan_advance`/`commit_advance`). A `None` default
     preserves today's behavior for callers that do not pass it.
  2. In `commit_advance`, under the lock (T006), re-read `state.json` and raise
     `StaleAdvancePlan` when the live `issued_step_id` differs from the
     caller-evaluated step (in addition to the existing `!= plan.source` check).
     Keep the message shape; this is the SAME authority with a widened window.
  3. Thread the value from the bridge bootstrap (`runtime_bridge.py:552`) through
     `_dn_plan_composition_advance` → `advance_run_state_after_composition` and the
     engine path, so both paths carry it.
- **Notes**: minimal signatures; do not restructure the bridge.

### Subtask T006 – Lock the commit read-modify-write

- **Purpose**: Serialise the three cursor writers (FR-003, FR-004).
- **Files**: `engine.py` (`_commit_advance`, `provide_decision_answer`),
  `runtime_bridge.py` (`_dn_rollback_buffered_run_state` + its capture
  `_dn_capture_pre_speculative_state`).
- **Steps**: wrap each write path in `run_cursor_lock(run_dir)` from T003, so the
  re-read (T005 CAS), the `_append_event` calls, and the `_write_snapshot` all
  happen under one held lock. Acquire just before the commit re-read; release after
  the snapshot write. Do NOT wrap composition executor dispatch. Run-start
  (`start_mission_run`) stays lock-free.
- **Notes**: if the rollback writer is already gone (sibling merged), skip that
  edit and note it in the Activity Log.

### Subtask T007 – Engine path refuses a stale plan (close #5854's second half)

- **Purpose**: The engine path must behave like the composition path.
- **Files**: `runtime_bridge.py` `_dn_advance_engine` (`:1234-1248`).
- **Steps**: on `StaleAdvancePlan` return a `blocked` Decision with a named reason
  via the existing `_advance_failed_decision` / EDGE-003 shape; also catch
  `LockAcquireTimeout` and map it to the same `blocked` shape. Remove the
  `runtime_next_step(result=…)` fallback. Update the docstring (it currently says
  the refusal "is tracked in #5854").

### Subtask T008 – Green + quality + tracer

- **Purpose**: Prove red→green and non-vacuity; keep the gates clean.
- **Steps**:
  1. Run the repros: confirm each was RED on the base and is now GREEN.
  2. Half-by-half: revert each part in turn (CAS, engine-refusal, answer-guard,
     lock, unique-temp) and confirm at least one test goes red; restore. **Record
     the five-row revert→red-witness mapping (which part reverted → which named
     test went red) in the PR's Tests-run section**, so the reviewer can verify
     SC-003 objectively rather than trust an unverifiable claim.
  3. Blast radius: `make test-fast`; `pytest tests/runtime tests/next
     tests/specify_cli/next -q`; the stress test serially
     (`-m stress -p no:xdist`); the targeted gates
     `tests/architectural/test_lock_primitive_ban.py`,
     `test_layer_rules.py`, `test_no_legacy_terminology.py`.
  4. `ruff check` + `ruff format --check --force-exclude` on changed files; `mypy`
     on changed modules; keep every function complexity ≤ 15.
  5. Append dated entries to `kitty-specs/serialise-next-advance-01M4EF16/traces/`
     (approach + design-decisions + any tooling friction).
  6. Record exact commands + passed/failed counts for the PR *Tests run* section.

## Test Strategy (required — ATDD-first)

- Red-first: every part has a test that is RED on the WP base and GREEN on the
  final commit; reverting one part turns at least one red (SC-003).
- Deterministic: injected interleaves (`monkeypatch`) and `threading.Barrier`;
  NEVER `sleep`.
- Markers: `p0_repro(issue=5682|5854)` + `regression` while red (nightly p0-repro
  lane); drop `p0_repro`, keep `regression` once green; `stress` for the
  true-concurrency barrier test (parallel-unsafe, serial lane).
- Typecheck: `mypy` on every changed module in addition to pytest.

## Risks & Mitigations

- **Lock held too long** → breach of the 10 s/60 s ceilings. Mitigation: acquire
  only around the commit; assert (NFR-001) the lock span excludes dispatch.
- **Deadlock with the run-index lock** → verify the index lock is released in
  `get_or_start_run` before the run-cursor lock is taken (C-002).
- **Scope under-reach** → a green suite while a race stays live. Mitigation: the
  true-concurrency barrier test + the held-lock-blocks test pin the lock itself,
  not only the CAS.
- **Sibling-branch churn** → keep bridge edits minimal (C-003); if the rollback
  writer is already deleted upstream, skip T006's rollback edit and note it.

## Review Guidance

- Confirm red→green on the WP base vs final commit, and the half-by-half reverts.
- Confirm the CAS is folded into `StaleAdvancePlan` (one authority), not a parallel
  bridge gate.
- Confirm the lock routes through `kernel.locks` only and the lock span excludes
  executor dispatch.
- Confirm the refusal reuses `blocked`/exit-1 (no new kind/exit).
- Confirm `mypy`/`ruff`/`ruff format`/complexity ≤ 15 are clean on changed files.

## Activity Log

- 2026-10-08T19:39:08Z – system – Prompt created.
