---
work_package_id: WP05
title: 'Ledger: single derived-view writer, execution-state projection refresh, hook sites, ledger-floor guard'
dependencies:
- WP01
requirement_refs:
- FR-008
- FR-009
- FR-010
- NFR-004
planning_base_branch: claude/spec-kitty-mission-impl-8u6zmc
merge_target_branch: claude/spec-kitty-mission-impl-8u6zmc
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-mission-impl-8u6zmc. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-mission-impl-8u6zmc unless the human explicitly redirects the landing branch.
subtasks:
- T021
- T022
- T023
- T024
- T025
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/status/test_execution_projection.py
- tests/architectural/test_ledger_floor.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/status/views.py
- src/specify_cli/status/progress.py
- src/specify_cli/status/lifecycle.py
- src/specify_cli/status/emit.py
- src/specify_cli/coordination/status_transition.py
- tests/status/test_execution_projection.py
- tests/architectural/test_ledger_floor.py
role: implementer
tags: []
tracker_refs: []
---

# WP05 — Ledger: single derived-view writer, execution-state projection refresh, hook sites, ledger-floor guard

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Give the ledger flag (`ledger.projection`, default on) a working subject: after every durably
persisted lane transition, refresh the derived, gitignored execution-state projection under
`.kittify/derived/<mission>/` from a write-free snapshot — without ever touching the tracked
`kitty-specs/<mission>/status.json` a second time. Fix the latent campsite defect where the derived
writers call the *writing* `materialize()` (rewriting a file that a lane transition, or `materialize`,
already wrote), single-source the writer via an optional `snapshot:` parameter, wire the refresh into
every fan-out hook site on both the flat and transactional paths, and back the "ledger never affects
lane state" invariant (FR-010) with a non-vacuous architectural guard.

## Context

**Why this WP exists.** Issue #4971 / spec.md User Story 3: a developer with drain off (Team Kitty
frozen) still wants an always-fresh local execution-state snapshot for the upcoming local dashboard.
D-2's decision (data-model.md, research.md R3) picked option (c): auto-refresh the *derived* projection
only — the lane ledger (`status.events.jsonl`), the tracked `status.json`, the decision ledger, the
runtime run journal and `kitty-ops/` are a non-optional floor that no flag in this mission may touch
("Git carries DONE", #4311; spec.md Invariant, FR-010).

**What depends on it.** WP04's NFR-001/NFR-004 integration walk (`tests/integration/test_hosted_posture_matrix.py`)
exercises all 4 combinations of {ledger on/off} × {drain on/off} and asserts lane-ledger bytes,
tracked-status bytes, status-ref commit count and the reduced snapshot are identical across all four —
this WP's refresh path must be provably inert with respect to those surfaces. WP08 (operator docs)
references the `ledger:` config section this WP implements.

**Key design decisions carried from plan.md (read plan.md's final "Post-plan squad folds" section —
F-3 and F-4 supersede the earlier D3 prose where they conflict):**

- **F-4 (single derived-view writer).** `write_derived_views` (`status/views.py:68`) currently calls
  the *writing* `materialize()` at line 90 — it rewrites the tracked `kitty-specs/<mission>/status.json`
  every time a derived view is regenerated, which is a latent defect independent of this mission (a
  campsite fix, not new scope). `generate_progress_json` (`status/progress.py:209`) has the same
  defect at line 221. Fix: add an optional `snapshot: StatusSnapshot | None = None` parameter to both,
  plus to `generate_lifecycle_json` (`status/lifecycle.py:451`) for symmetry, even though
  `generate_lifecycle_json` → `derive_mission_lifecycle` (`status/lifecycle.py:350`) already builds its
  snapshot write-free via `reduce(read_events(feature_dir))` (line 369) and does **not** call
  `materialize()` today — verify this yourself against live code before assuming it needs the same fix;
  add the parameter anyway so all three generators share one shape and `refresh_execution_projection`
  can call all three uniformly. When `snapshot` is given, use it and skip the writing `materialize()`
  call entirely. When omitted, preserve the exact existing behaviour (the `spec-kitty materialize` CLI
  command and any other caller that does not pass `snapshot` must keep writing the tracked file exactly
  as before — do not change that call's observable behaviour).
- **`materialize_if_stale`** (`status/views.py:244`) is the other caller of `write_derived_views` /
  `generate_progress_json` / `generate_lifecycle_json` (lines 295–297); it must pass the write-free
  `snapshot = reduce(read_events(feature_dir))` construction — the exact same construction it already
  builds for its own return value at lines 300–301 — through the new `snapshot:` parameter, so its
  regeneration path stops rewriting tracked `status.json` too.
- **F-3 (projection hook sites).** The flat path hooks live in `status/emit.py`, independent of the
  `fan_out` flag, right next to (not inside) each `_saas_fan_out` call site: the single-transition
  shell around line 931–938 and the batch shell around line 1089–1097. The transactional path hooks
  live in `coordination/status_transition.py`, registered as a **post-commit deferred outbound**
  (`txn.defer_outbound(...)`) — never called synchronously inside the transaction — next to every
  `_defer_fan_out` / `queue_saas_emission` site and the one direct `_emit._saas_fan_out` site. Verify
  and enumerate all of them against live code; as of this writing they are: the non-transactional
  coord-tail fan-out at `coordination/status_transition.py:420-442` (`_fan_out_committed_coord_tail`,
  direct `_emit._saas_fan_out` call at line 434), the shared `_defer_fan_out` helper at lines 1054-1072
  (itself called from the single-door transactional path at line 1534 and the batch transactional path
  at line 1773 — hooking once inside `_defer_fan_out` covers both call sites without duplication), and
  the inner-state annotation door's own `txn.defer_outbound(...)` call around line 1688-1690 (this path
  carries only an `InnerStateChanged` annotation, not a lane-transition `StatusEvent` — still worth a
  refresh since the annotation is a durably persisted change to the mission's event log). Re-grep before
  writing code: line numbers drift.
- The refresh is **best-effort**: it must never raise into the transition/fan-out path. Catch and log;
  a projection refresh failure must never fail, delay, or roll back the caller's transition.
- The refresh only fires when `ledger_posture(project_root).enabled` is `True` (WP01 provides
  `specify_cli.core.hosted_posture.ledger_posture(project_root: Path | None = None) -> LedgerPosture`
  with fields `enabled: bool`, `source: str`; default `True` when `.kittify/config.yaml`'s
  `ledger.projection` key is absent, unparseable, or non-boolean).

## Subtask T021: ATDD red-first — `tests/status/test_execution_projection.py`

**Purpose**: Write the acceptance tests for this WP's whole behaviour *before* any implementation
change, in their own commit, so (a) is provably RED against live code and the rest go green only once
T022-T024 land.

**Steps**:
1. Create `tests/status/test_execution_projection.py` with these cases (verify each function name,
   module path, and line number against live code before writing the assertion — cite what you find):
   - **(a) Single-writer regression (RED today).** Call `write_derived_views(feature_dir, derived_dir)`
     and separately `generate_progress_json(feature_dir, derived_dir)` against a fixture mission whose
     tracked `kitty-specs/<mission>/status.json` already exists and is up to date. Snapshot the file's
     bytes and mtime before the call, call again, and assert both are **unchanged** — i.e. the writing
     `materialize()` at `views.py:90` / `progress.py:221` is not invoked a second time when nothing
     changed. This assertion is RED against current `main` (confirm by running it before touching
     `views.py`/`progress.py` — record the failure in the PR) and turns GREEN only after T022's
     `snapshot:` parameter lands and `materialize_if_stale` is updated to pass it.
   - **(b) Ledger on ⇒ refresh matches reduce.** With `ledger_posture` mocked/configured on, drive a
     lane transition through `emit_status_transition` (flat path) and separately through the
     transactional path (`coordination/status_transition.py`'s public entry point — find it), then
     assert `.kittify/derived/<slug>/status.json`, `board-summary.json`, `progress.json` and
     `lifecycle.json` exist and their content matches `reduce(read_events(feature_dir)).to_dict()` (plus
     each file's own transform, e.g. `_build_board_summary`).
   - **(c) Ledger off ⇒ no automatic refresh; `spec-kitty materialize` still works.** With
     `ledger_posture` off, drive the same transition and assert nothing new appears under
     `.kittify/derived/`. Then invoke the on-demand materialize path (`materialize_if_stale` or the CLI
     command backing `spec-kitty materialize` — find it) directly and assert it still produces the
     files, proving the flag gates only the *automatic* hook, not the on-demand command (FR-009/FR-010).
   - **(d) Git-op-in-progress ⇒ skipped.** With `git_operation_in_progress(repo_root)` monkeypatched
     `True`, drive a transition with ledger on and assert no file under `.kittify/derived/` is
     created/modified, and the transition itself still succeeds (no exception).
   - **(e) Coordination transactional path refreshes post-commit.** Using a coordination-topology
     mission fixture (find the existing fixture pattern in `tests/coordination/` — e.g.
     `tests/coordination/test_status_write_authority.py`), drive a transition through the transactional
     door and assert the projection under `.kittify/derived/<slug>/` reflects the post-commit state
     (i.e. the refresh fired as a deferred outbound, not before commit).
2. Commit this test file on its own (before any of T022-T024's source changes), per the mission's
   ATDD-first / C-011 discipline (see plan.md Charter Check) and per CLAUDE.md's red-first test
   discipline. Run it and record which cases are RED/GREEN before touching source, in your PR notes.

**Files**: `tests/status/test_execution_projection.py` (new, ~250-350 lines covering 5 cases).
**Validation**: `pytest tests/status/test_execution_projection.py -v` — case (a) RED, others may be
RED or skip-pending until T023/T024 land; re-run after each subtask to track the flip to green.

## Subtask T022: Single-writer refactor (F-4, campsite fix)

**Purpose**: Stop `write_derived_views`, `generate_progress_json`, and (for symmetry) `generate_lifecycle_json`
from calling the *writing* `materialize()`/re-deriving from scratch when a snapshot is already in hand,
without changing the observable behaviour of any existing caller that omits the new parameter.

**Steps**:
1. In `src/specify_cli/status/views.py`, change `write_derived_views`'s signature to:
   ```python
   def write_derived_views(
       feature_dir: Path,
       derived_dir: Path,
       *,
       snapshot: StatusSnapshot | None = None,
   ) -> None:
   ```
   Inside, replace the unconditional `snapshot = materialize(feature_dir)` (line 90) with: use the
   passed-in `snapshot` when not `None`; otherwise fall back to `materialize(feature_dir)` exactly as
   today. Everything after that line (mission_slug resolution, `_atomic_write_json` calls) is
   unchanged.
2. In `src/specify_cli/status/progress.py`, apply the same shape to `generate_progress_json`
   (line 209): add `*, snapshot: StatusSnapshot | None = None`, and inside, use the passed snapshot when
   given, else fall back to `materialize(feature_dir)` (line 221) exactly as today. `StatusSnapshot` is
   already imported in this module (`.models`).
3. In `src/specify_cli/status/lifecycle.py`, add the same `snapshot: StatusSnapshot | None = None`
   parameter to `generate_lifecycle_json` (line 451) and thread it into `derive_mission_lifecycle`
   (line 350) — add the same optional parameter there too, since `generate_lifecycle_json` delegates to
   it. Inside `derive_mission_lifecycle`, when `snapshot` is given, use it directly (skip the
   `has_event_log` / `reduce(read_events(...))` construction at lines 364-375, but still run the
   `resolve_mission_identity` / `mission_slug` backfill at line 372-373 against the passed snapshot).
   When omitted, preserve today's exact behaviour. Confirm your read: `derive_mission_lifecycle` already
   builds its snapshot via `reduce(read_events(...))`, not `materialize()` — it does **not** carry
   today's single-writer defect; you are adding the parameter for interface symmetry with the other two
   generators, not fixing a second instance of the bug. State this explicitly in your PR notes so a
   reviewer does not go looking for a defect that is not there.
4. In `src/specify_cli/status/views.py`'s `materialize_if_stale` (line 244), change the write call site
   (lines 294-297) to build the write-free snapshot **once** —
   `snapshot_for_refresh = reduce(read_events(feature_dir))` — and pass it as `snapshot=snapshot_for_refresh`
   to all three generator calls, so this on-demand-but-stale-triggered path also stops rewriting tracked
   `status.json` a second time. Do not change `materialize_if_stale`'s own return-value construction at
   lines 300-308 (it already does the equivalent read-free reduce for its own return).
5. Double check every other existing caller of these three functions (`grep -rn "write_derived_views\|generate_progress_json\|generate_lifecycle_json" src/`) still calls them positionally/without
   `snapshot=` and therefore keeps its current writing behaviour unchanged.

**Files**: `src/specify_cli/status/views.py` (~15 lines changed), `src/specify_cli/status/progress.py`
(~10 lines changed), `src/specify_cli/status/lifecycle.py` (~15 lines changed across two functions).
**Validation**: T021 case (a) turns GREEN. Existing tests for `write_derived_views`,
`generate_progress_json`, `generate_lifecycle_json`, and `materialize_if_stale` (find them under
`tests/status/`) still pass unmodified — their calls omit `snapshot=` and must observe identical output.

## Subtask T023: `refresh_execution_projection` (write-free projection refresh)

**Purpose**: Add the one new function that all hook sites call: a write-free, best-effort refresh of
the derived projection under the **repository root's** `.kittify/derived/<canonical-slug>/`, never the
coord/lane worktree's copy.

**Steps**:
1. In `src/specify_cli/status/views.py`, add:
   ```python
   def refresh_execution_projection(feature_dir: Path, repo_root: Path) -> bool:
       """Best-effort, write-free refresh of the derived execution-state projection.

       Reads the event log, reduces a snapshot without writing it back to the
       tracked ``status.json``, and refreshes ``.kittify/derived/<canonical-slug>/``
       under the REPOSITORY ROOT (never a coord/lane worktree copy). Returns
       ``True`` when files were written, ``False`` on a no-op (git operation in
       progress, or a caught failure). Never raises into the caller — this sits
       on the hot path of every lane transition and fan-out hook.
       """
   ```
2. Resolve the canonical mission slug the same way `_stale_check_slug` does (`resolve_mission_identity(feature_dir).mission_slug or feature_dir.name`) — reuse `_stale_check_slug` directly rather than
   reimplementing it.
3. Resolve the **repository root**, not `feature_dir`'s own root: `feature_dir` may itself be a
   coord/lane worktree path (e.g. `.worktrees/<slug>-<mid8>-lane-<id>/kitty-specs/<slug>/`). The
   `repo_root` parameter is supplied by the caller (every hook site already has a `repo_root`/
   `request.repo_root`/`identity.repo_root` in scope — thread it through, do not re-derive it here).
   Grep for how other status/coordination code resolves "the main repo root from a worktree" (e.g.
   `canonicalize_feature_dir` in `status/emit.py`, or `identity.repo_root` in
   `coordination/status_transition.py`) and follow the same pattern the hook site already uses — this
   function should stay a pure consumer of the `repo_root` it is handed, not another root-resolution
   authority (single canonical authority, DIRECTIVE_044).
4. Build `derived_dir = repo_root / ".kittify" / "derived"` (same construction as
   `materialize_if_stale`, line 266).
5. Guard: if `git_operation_in_progress(repo_root)` is `True`, return `False` immediately — no read, no
   write.
6. Build the snapshot **once**, write-free: `snapshot = reduce(read_events(feature_dir))`, then stamp
   `mission_number`/`mission_type` from `resolve_mission_identity(feature_dir)` exactly as
   `materialize_if_stale`'s return-value construction does (lines 300-308) — this is the "same
   construction `materialize_if_stale` returns" the plan calls for.
7. Call `write_derived_views(feature_dir, derived_dir, snapshot=snapshot)`,
   `generate_progress_json(feature_dir, derived_dir, snapshot=snapshot)`, and
   `generate_lifecycle_json(feature_dir, derived_dir, snapshot=snapshot)` (using the `snapshot=`
   parameters from T022, threading the same snapshot into all three, mirroring FR-009's
   write-once-per-transition intent even though each generator writes a distinct file).
8. Wrap steps 6-7 in `try/except Exception`: log a warning (reuse the module's existing logger pattern,
   e.g. the one at `emit.py`'s batch-materialize `except Exception` block at line 1080) and return
   `False`. Never let an exception from this function reach the caller.
9. Return `True` on success.
10. Export `refresh_execution_projection` from the module's public surface (it already has an `__all__`
    or is imported by name elsewhere — check and add it consistently).

**Files**: `src/specify_cli/status/views.py` (new function, ~45-60 lines).
**Validation**: unit-test `refresh_execution_projection` directly in
`tests/status/test_execution_projection.py` (or a small addition there): success case writes 4 files
matching `reduce(read_events(...))`; git-op-in-progress case returns `False` and writes nothing; an
injected failure (monkeypatch `write_derived_views` to raise) returns `False` and does not propagate.

## Subtask T024: Hook sites (F-3) + ledger-floor architectural guard

**Purpose**: Wire `refresh_execution_projection` into every fan-out call site on both the flat and
transactional paths, gated on `ledger_posture`, and back FR-010 (the ledger flag must never be
reachable from the surfaces that are the non-optional floor) with a non-vacuous architectural test.

**Steps**:
1. Re-grep `src/specify_cli/status/emit.py` for `_saas_fan_out(` and `src/specify_cli/coordination/status_transition.py`
   for `_saas_fan_out`, `_defer_fan_out`, `queue_saas_emission`, and `txn.defer_outbound` before
   editing — line numbers in this prompt are a starting point (as of this writing: `emit.py` ~931-938
   flat, ~1091-1097 batch; `status_transition.py` ~434 direct, ~1054-1072 `_defer_fan_out` helper
   (covers its two callers at ~1534 and ~1773), ~1688-1690 inner-state annotation door) — cite what you
   actually find in your PR notes.
2. **`status/emit.py` flat path** (next to the `_saas_fan_out(...)` call inside the `if fan_out:` block
   around line 931-938): call `refresh_execution_projection(canonical_feature_dir, request.repo_root)`
   **independent of the `fan_out` flag** — i.e. outside/alongside the `if fan_out:` guard, not inside
   it, since FR-009 refreshes on every durably persisted transition regardless of whether SaaS fan-out
   ran. Gate it on `ledger_posture(...).enabled`. Skip entirely (no call at all, not even the guard
   check) when `request.repo_root` is `None` — there is no repository root to derive `.kittify/derived/`
   against.
3. **`status/emit.py` batch path** (next to the batch `_saas_fan_out(...)` loop around line 1089-1097):
   same shape — call once per persisted batch (not once per event; the whole batch belongs to one
   feature_dir/repo_root), gated on `ledger_posture` and independent of `fan_out`.
4. **`coordination/status_transition.py` — `_fan_out_committed_coord_tail`** (~420-442, the direct
   `_emit._saas_fan_out` call at ~434): this function already runs post-commit/post-lock-release. Add
   a call to `refresh_execution_projection` after the fan-out loop, gated on `ledger_posture`, using
   this function's own `repo_root` parameter and a resolved feature_dir for the coord tail (find how
   this function resolves its own feature_dir — it may need one passed in or resolved the same way its
   fan-out does).
5. **`coordination/status_transition.py` — `_defer_fan_out`** (~1054-1072): this helper is the shared
   choke point for both the single-door transactional path (~1534) and the batch transactional path
   (~1773). Add one line registering the refresh as a deferred outbound, alongside the existing
   `txn.defer_outbound(...)` / `queue_saas_emission(...)` calls in this function:
   ```python
   if ledger_posture(txn.repo_root).enabled:
       txn.defer_outbound(lambda: refresh_execution_projection(txn.feature_dir, txn.repo_root))
   ```
   (adjust to the actual `BookkeepingTransaction` attribute names — confirm `txn.repo_root` and
   `txn.feature_dir` against `coordination/transaction.py`'s class body before writing this). This is
   the "post-commit deferred outbound" placement F-3 calls for — never call
   `refresh_execution_projection` synchronously inside the transaction body.
6. **`coordination/status_transition.py` — inner-state annotation door** (~1688-1690, the
   `txn.defer_outbound(_deferred_resolved_binding_fan_out(annotation, mission_slug))` call): add a
   sibling `txn.defer_outbound(...)` registering the same refresh, gated the same way. This path
   persists an `InnerStateChanged` annotation rather than a lane-transition `StatusEvent` — still a
   durably persisted change worth reflecting in the projection.
7. Import `ledger_posture` and `refresh_execution_projection` at the top of both modules (WP01 already
   ships `specify_cli.core.hosted_posture.ledger_posture`).
8. **Complexity discipline**: `emit_status_transition` at line 783 already carries a
   `# NOSONAR — central orchestration hub` complexity waiver — it is a hub, not a place to grow.
   Extract a small private helper (e.g. `_refresh_projection_if_ledger_on(feature_dir, repo_root)`,
   shared by both the flat and batch call sites in `emit.py`) rather than inlining the `ledger_posture`
   check plus the `None`-repo_root guard at each of the two call sites. Keep both `emit_status_transition`
   and `emit_status_transition_batch` at or under the repo's complexity ceiling of 15 (`ruff`'s `C901` /
   Sonar `S3776`, see CLAUDE.md "Sonar Expectations") — measure before and after with
   `ruff check --select C901 src/specify_cli/status/emit.py` and record both counts in your PR notes.
9. Write the ledger-floor architectural guard, `tests/architectural/test_ledger_floor.py`, modelled on
   the existing sink/reference-scanning shape in `tests/architectural/test_egress_consent_boundary.py`
   (read it first) and the self-mutation-check pattern used by drain's own gate test (WP04's
   `tests/architectural/test_hosted_drain_gate.py`, not yet written when you start this WP — coordinate
   by grepping for whichever arch test already exists at review time, or follow
   `test_egress_consent_boundary.py`'s shape directly if `test_hosted_drain_gate.py` does not exist
   yet). The gate must assert, by AST/reference scan (not a name-substring `grep`, which a rename could
   dodge — see `test_egress_consent_boundary.py`'s own rationale for why a sink/reference scan beats a
   name scan):
   - `ledger_posture` and `drain_posture` (both from `specify_cli.core.hosted_posture`) are **not**
     referenced from `src/specify_cli/status/store.py`, `src/specify_cli/status/reducer.py`,
     `src/specify_cli/coordination/transaction.py`, anything under `src/specify_cli/decisions/`, or
     `src/specify_cli/events/decision_log.py`.
   - In `src/specify_cli/coordination/status_transition.py`, `ledger_posture` is referenced **only**
     inside the projection-hook call sites you added in steps 4-6 above (name each function/line the
     test permits) — any other reference is a red build.
   - A **self-mutation check**: temporarily (in the test itself, via a monkeypatched/synthetic AST tree
     or a fixture file under a temp dir — do not actually mutate the real source) prove that removing
     one of the permitted hook-site references would turn the test red, so the guard is provably
     non-vacuous (same discipline NFR-002 asks of the drain gate).

**Files**: `src/specify_cli/status/emit.py` (~25-35 lines, incl. one extracted helper),
`src/specify_cli/coordination/status_transition.py` (~20-30 lines across 3 sites),
`tests/architectural/test_ledger_floor.py` (new, ~150-220 lines).
**Validation**: T021 cases (b), (d), (e) turn GREEN. `pytest tests/architectural/test_ledger_floor.py -v`
passes and its self-mutation check fails loudly when the assertion under test is disabled (prove this
manually once, then leave the guard in its passing state).

## Subtask T025: Validation sweep

**Purpose**: Prove the whole WP is safe against its blast radius, per CLAUDE.md's "Test policy — what
you must run for a change" and the calibrated blast-radius rule (this WP touches `status/` and
`coordination/status_transition.py`, both cross-referenced subsystems).

**Steps**:
1. Run the new/changed tests directly:
   ```bash
   pytest tests/status/test_execution_projection.py -v
   pytest tests/architectural/test_ledger_floor.py -v
   ```
2. Run the full owning subsystem directories:
   ```bash
   pytest tests/status/ -q
   ```
   and the coordination tests that exercise `status_transition.py` — find them precisely
   (`grep -rl "status_transition" tests/coordination/` and `tests/status/`; as of this writing this
   includes at least `tests/coordination/test_status_write_authority.py` — confirm and list every hit
   you actually run in your PR notes, not just this one).
3. Run the CLI tests covering `spec-kitty materialize` (find them:
   `grep -rl "materialize" tests/specify_cli/cli/commands/`) to confirm T022's single-writer refactor
   left the on-demand command's observable output unchanged.
4. Run the existing archive byte-identity guard, `tests/architectural/test_archive_root_byte_identical.py`
   (covers the `reducer.py` ~370-380 region you read in T023) — this WP must not perturb archived
   snapshot replay.
5. Run `ruff check .`, `ruff format --check .`, and `mypy` (per repo config) restricted to (or at least
   covering) every file this WP touches; fix everything to zero issues rather than suppressing (no new
   `# noqa`/`# type: ignore` — see CLAUDE.md "Code Style").
6. Run the shared fast-tier baseline:
   ```bash
   make test-fast
   ```
7. Record every command you ran and its passed/failed counts under a `## Tests run` section in your
   final PR/handoff notes, per CLAUDE.md's test-run policy — including the pre-fix RED run from T021
   step (a) and the post-fix GREEN run.
8. Classify any red you did not cause using the baseline-red gotcha (CLAUDE.md, "Test-run baseline-red
   gotcha") before treating it as yours to fix.

**Files**: none new — this subtask is verification only.
**Validation**: all listed commands pass (or any failure is classified per the baseline-red gotcha and
noted); diff coverage on touched files ≥90% (NFR-005).

## Definition of Done

- `tests/status/test_execution_projection.py` exists, was committed RED-first (case (a) failing against
  pre-refactor `views.py`/`progress.py`), and all 5 cases (a)-(e) pass against the finished code.
- `write_derived_views`, `generate_progress_json`, and `generate_lifecycle_json` accept an optional
  `snapshot:` parameter; every existing caller that omits it observes unchanged behaviour (verified by
  the pre-existing test suite passing unmodified); `materialize_if_stale` passes a write-free
  `reduce(read_events(...))` snapshot through all three and no longer rewrites tracked `status.json`
  when regenerating derived views.
- `status/views.py::refresh_execution_projection(feature_dir, repo_root) -> bool` exists, is write-free
  with respect to the tracked `status.json`, writes only under the repository root's
  `.kittify/derived/<canonical-slug>/`, skips (returns `False`, no I/O) during a git operation, and
  never raises into a caller.
- The refresh fires from every enumerated hook site (`emit.py` flat and batch; `status_transition.py`'s
  coord-tail, `_defer_fan_out` shared helper, and inner-state annotation door) — independent of the
  `fan_out` flag — gated on `ledger_posture(...).enabled`, and registered as a post-commit deferred
  outbound on every transactional path (never called synchronously inside a transaction).
- `tests/architectural/test_ledger_floor.py` exists, non-vacuously proves `ledger_posture`/`drain_posture`
  are unreferenced from `status/store.py`, `status/reducer.py`, `coordination/transaction.py`,
  `decisions/**`, and `events/decision_log.py`, and that `status_transition.py` references
  `ledger_posture` only at the permitted hook sites, with a working self-mutation check.
- FR-010's floor holds: no test or manual check shows the lane ledger, its commit, the tracked
  `status.json`, the decision ledger, the runtime run journal, or `kitty-ops/` differing between ledger
  on and ledger off.
- `emit_status_transition` and `emit_status_transition_batch` stay at or under complexity 15
  (extracted helper, not inline growth of the NOSONAR hub).
- Full validation sweep (T025) run and recorded, `make test-fast` green, ruff/ruff format/mypy clean on
  touched files.

## Risks

- **Silent regression of the campsite fix.** The T022 refactor touches functions called from many
  places (`spec-kitty materialize`, `materialize_if_stale`, this WP's own new hook). A caller that
  quietly starts passing `snapshot=` where it should not (or vice versa) could make the tracked
  `status.json` stale or double-written. Mitigation: T021 case (a) plus the full `tests/status/` run
  and the archive byte-identity guard (T025) are the safety net — do not skip either.
- **Wrong repo-root resolution inside `refresh_execution_projection`.** If a coord/lane worktree's
  `feature_dir` is used to derive `repo_root` instead of the caller-supplied repository root, the
  projection lands under the worktree's own (usually nonexistent-in-practice, or worse, divergent)
  `.kittify/derived/`, defeating the dashboard's single query source. Mitigation: this function must
  never re-derive `repo_root` itself — thread the caller's value through, and add a test that drives the
  transactional coord path (T021 case (e)) and asserts the file lands under the *main* repo root, not
  the worktree.
- **Hook site drift.** Line numbers cited in this prompt (and in plan.md's F-3) will have moved by the
  time you implement, especially if WP02/WP03 land drain-gate code in adjacent lines first. Re-grep
  every site before editing; an incomplete enumeration silently leaves a fan-out path unrefreshed and
  no test will catch it unless T021's cases exercise every real call path (flat single, flat batch,
  transactional single, transactional batch, coord-tail, inner-state annotation) — cover all of them,
  not just the two the prompt spells out in the most detail.
- **Complexity creep in `emit.py`'s NOSONAR hub.** Sonar/ruff `C901` will not warn until the ceiling is
  crossed, but the file is explicitly flagged as a hub not to grow. Extract the helper in step 8 of T024
  before, not after, you discover the function is over budget.
- **Best-effort masking a real bug.** The broad `try/except Exception` in `refresh_execution_projection`
  is required (FR-009's "never affects lane state" guarantee), but it can hide a genuine defect during
  development. Log at `warning` level with enough context (mission slug, exception) to debug from logs
  alone, and do not silently swallow during your own testing — check the log output while iterating.

## Reviewer Guidance

- Confirm the T021 test file was genuinely committed and run RED before the T022 source change landed
  (ask for the commit history / recorded pre-fix run, per ATDD-first / C-011).
- Walk every hook site named in T024 against live code yourself — do not trust this prompt's line
  numbers. Confirm each one calls `refresh_execution_projection` independent of `fan_out`, gated on
  `ledger_posture`, and (on transactional paths) via `txn.defer_outbound`, never synchronously.
- Confirm `refresh_execution_projection` resolves `.kittify/derived/` against the **repository root**
  parameter, not anything derived from `feature_dir` alone — this is the easiest place for a coord/lane
  regression to slip through.
- Confirm `write_derived_views`/`generate_progress_json`/`generate_lifecycle_json`'s existing callers
  (grep for all of them) are unaffected — the refactor must be additive-only for every caller that does
  not pass `snapshot=`.
- Run `tests/architectural/test_ledger_floor.py` yourself and deliberately break one of its guarded
  invariants locally (e.g. add a stray `ledger_posture` import to `status/reducer.py`) to confirm the
  gate actually goes red — do not accept a gate that only asserts something trivially true.
- Confirm the FR-010 floor claim empirically: run a lane transition with ledger on and one with ledger
  off against the same starting fixture, and diff the tracked `status.json`, `status.events.jsonl`, and
  the git commit produced — they must be identical apart from the derived, gitignored files.
- Check `ruff check --select C901` output for `emit.py` before and after this WP's diff.

## Implementation Command

```bash
spec-kitty agent action implement WP05 --agent claude
```
