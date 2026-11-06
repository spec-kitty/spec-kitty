---
work_package_id: WP07
title: S1 migrate consolidation readers and add the single-door gate
dependencies:
- WP06
requirement_refs:
- FR-005
- FR-006
- SC-002
- C-013
- NFR-006
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T036
- T037
- T038
- T039
- T040
- T041
phase: Phase 2 - S1 one status read contract
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/architectural/test_status_read_single_door.py
- tests/consolidation/test_unmaterialized_preflight_reads.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/done_bookkeeping.py
- src/specify_cli/consolidation/forecast.py
- src/specify_cli/consolidation/phase_advance.py
- src/specify_cli/consolidation/preflight.py
- src/specify_cli/consolidation/entry_preflight.py
- src/specify_cli/consolidation/coord_strand.py
- tests/architectural/test_status_read_single_door.py
- tests/architectural/test_single_mission_surface_resolver.py
- tests/architectural/_surface_resolution_scan.py
- tests/architectural/test_no_read_side_bypass.py
- tests/architectural/test_read_surface_placement_guard.py
- tests/consolidation/test_unmaterialized_preflight_reads.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 - S1 migrate consolidation readers and add the single-door gate

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP07 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP07 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Objectives & Success Criteria

1. FR-005: the consolidation status readers move onto the door (`done_bookkeeping`, `forecast`, `phase_advance`, `preflight`, `entry_preflight`, `coord_strand`, and `coordination/transaction.py`'s `preflight_refusal` read). `done_bookkeeping.py:~610`'s raw `git show` goes through the WP04/WP05 ref reader.
2. FR-006 / SC-002 / C-013: a new architectural gate `tests/architectural/test_status_read_single_door.py` with an **empty allowlist**, a scanned-file floor (>= 1250 files), a caller floor frozen at the measured count, and planted-violation self-tests for: a direct call, an aliased import, an attribute call, `STATUS_STATE` through a local alias, a hand-joined `status.events.jsonl` path, and "retired names absent". 0 live violations; 100% of planted ones detected.
3. Amend (do not bypass) the four standing gates that bless the old body: `test_single_mission_surface_resolver.py`, `_surface_resolution_scan.py`, `test_no_read_side_bypass.py`, `test_read_surface_placement_guard.py`. No second authority beside them (charter DIRECTIVE_044, plan Complexity Tracking).
4. NFR-006: the gate (and each amended gate) completes in <= 5 s locally on the full `src/` tree.

## Context & Constraints

- Read: WP05 `status/read_surface.py`; WP06 census of migrated call sites (in its completion summary / history); plan Charter Check rows "Single canonical authority" and "Standing order 5"; tactic `architectural-gate-non-vacuity` (`spec-kitty charter context --action implement` lists it).
- `coordination/transaction.py` is owned by WP10 (parallel). Your hunk is the `preflight_refusal` read only; WP10 edits the write label in a different function. Keep it minimal and record the out-of-map edit.
- **#7274 (NOT merged)** touches consolidation neighbours; rebase only if it lands first.
- No transient allowlist; if a call site cannot migrate, migrate it anyway or stop and report.
- C-011 red-first: gate self-mutation arms red before the live scan goes green.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T036 - Red-first: unmaterialized preflight

- `tests/consolidation/test_unmaterialized_preflight_reads.py::test_unmaterialized_preflight_reports_real_lanes`: a `lanes_with_coord` Mission with committed coordination events and the coordination worktree removed; `spec-kitty consolidate --dry-run` (and the preflight entry) reports the real WP lanes from the branch, not an empty history or the stale root copy. Red on the base.

### Subtask T037 - Migrate consolidation readers

- One reader at a time; keep behaviour otherwise identical. Replace `read_dir(STATUS_STATE)` and direct resolver calls with `resolve_status_read` + `read_status_events` / `materialize_status`.
- `done_bookkeeping.py:~610` raw `git show` -> ref reader (typed errors).
- `coordination/transaction.py::preflight_refusal`: read through the door (out-of-map).
- Respect the bookkeeping/rollback invariants in CLAUDE.md "Consolidation & Preflight Patterns"; do not change refusal codes.

### Subtask T038 - The single-door gate

- AST scan of `src/`: flag any call to the old resolver bodies, `read_dir(...STATUS_STATE...)`, `read_event_log`/`read_event_stream_log` outside `status/read_surface.py` and the write seam, and any `Path` join producing `status.events.jsonl` outside allowed modules (the door, the store, the write seam: define the allowed set as module constants, not an allowlist of call sites).
- Self-tests: write planted source snippets to `tmp_path` for each arm and assert detection (red first: commit arms against an empty implementation).
- Floors: assert scanned files >= 1250 and door callers >= the measured count (freeze the number you measure; comment it).

### Subtask T039 - Amend the four standing gates

- Wherever they name `resolve_status_surface_with_anchor` as canonical, change them to name the door; keep their other checks. Share scanning helpers through `_surface_resolution_scan.py` rather than duplicating.

### Subtask T040 - Gate speed and floors

- Time each gate (`pytest --durations=0`); <= 5 s each. Cache parsed ASTs at module scope if needed.

### Subtask T041 - Quality gates and blast radius

See Validation.

## Validation

```bash
cd <workspace>
uv run --frozen pytest tests/consolidation/test_unmaterialized_preflight_reads.py tests/architectural/test_status_read_single_door.py tests/architectural/test_single_mission_surface_resolver.py tests/architectural/test_no_read_side_bypass.py tests/architectural/test_read_surface_placement_guard.py -q --durations=10
uv run --frozen pytest tests/consolidation tests/coordination -q -n auto --dist loadfile
uv run --frozen pytest tests/consolidation/test_single_rollback_authority.py tests/architectural/test_layer_rules.py -q
make test-fast
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy --strict <touched src files>
```

Named gate files only; never a bare `tests/architectural/` sweep or `make test-full`.

## Tracer files

Return tracer lines in your completion summary (`- **[YYYY-MM-DD][implement WP07] ...**`, naming the trace file); the orchestrator appends them. Include the frozen caller floor.

## Risks & Mitigations

- Vacuous gate: planted arms + floors guard it.
- Gate too slow: shared AST cache.
- Conflicts with WP10 on `transaction.py`: different functions; rebase carefully.

## Review Guidance

- Empty allowlist, floors, six planted arms; four standing gates amended, not duplicated; consolidation readers on the door; <= 5 s.

## Definition of Done

- T036-T041 done; tests green; tracer lines returned.

## Progress & Status

- `spec-kitty agent tasks mark-status T036 T037 T038 T039 T040 T041 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP07 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
