---
work_package_id: WP09
title: 'MergeState authority: single target + owned lock (C-1, C-2)'
dependencies:
- WP08
requirement_refs:
- FR-007
- FR-008
planning_base_branch: fix/terminus-merge-integrity
merge_target_branch: fix/terminus-merge-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-merge-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-merge-integrity unless the human explicitly redirects the landing branch.
subtasks:
- T040
- T041
- T042
- T043
phase: Phase 3 - Serialized executor lane
history:
- at: '2026-09-23T21:36:42Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/state.py
create_intent:
- tests/merge/test_merge_state_authority.py
execution_mode: code_change
owned_files:
- src/specify_cli/core/paths.py
- src/specify_cli/merge/resolve.py
- src/specify_cli/merge/state.py
- src/specify_cli/cli/commands/merge.py
- tests/merge/test_merge_state_authority.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 – MergeState authority: single target + owned lock (C-1, C-2)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (frontmatter) before parsing the rest of
this prompt, and behave according to its guidance.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

Apply the resolved boundaries and TDD discipline. State what you applied, then continue.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use fenced code-block language identifiers.

---

## Objectives & Success Criteria

Collapse the merge-target and merge-lock split-brains to one persisted authority each. Success
(FR-007, FR-008; traces #4985 #4991 #4996 second half):

- **C-1 single target**: the landing branch is resolved once (precedence **explicit `--target` >
  persisted MergeState target > meta.json**), persisted into MergeState, and is the sole authority
  for all phases and every `--resume`; `--resume` never re-derives from meta.
- **C-2 owned lock**: `owner_token = merge-state-id` (stable across resume); `--abort` releases only
  a lock whose owner matches the aborting invocation and can never free a different mission's live merge.

## Context & Constraints

- Spec: [../spec.md](../spec.md) US4 (both scenarios), FR-007/FR-008. Research D5, D7; DEBRIEF §3
  C-1/C-2, §4 (#4985/#4991/#4996). Dispositions RN-F3/PP-F1 (C-1 real authority) and PP-F2 (lock
  owner_token must be state-id, not pid).
- Data model: [../data-model.md](../data-model.md) `MergeTarget` (precedence + persisted) and
  `MergeLock` (owner_token).
- **Grounded anchors** (verify in-tree; names are the durable anchors):
  - C-1 real authority is `core/paths.py resolve_merge_target_branch` (via `merge/resolve.py:284`);
    the executor drives off `run.lanes_manifest.target_branch` (28 read-sites) seeded from meta
    BEFORE state load. WP06 already inlined the **manifest reseed-from-state** after
    `_load_or_create_merge_state` (≈ `executor.py:2280-2288`) — THIS WP makes `state.target_branch`
    the correctly-resolved value that reseed consumes.
  - `merge/state.py` `acquire_merge_lock` ≈ `:370` already writes a lock body — set `owner_token`.
  - `cli/commands/merge.py` `_dispatch_abort` ≈ `:462` unlinks the global lock today — gate it on
    owner match.
- **Documented out-of-map edit (permitted, record the rationale)**: one edit to `executor.py`'s
  lock-acquire call site is permitted to pass `owner_token = merge-state-id`. It is serial after WP06
  (no `_MergeRunState` collision). Note it explicitly in the WP + PR. Do NOT make any other
  `executor.py` change here.
- Locality (C-004, widened): `core/paths.py`, `resolve.py`, `state.py`, `merge.py`, + the new test
  (+ the one documented executor lock-acquire line).

## Branch Strategy

- **Strategy**: serialized executor lane, after WP08.
- **Planning base branch / Merge target branch**: `fix/terminus-merge-integrity`.

## Subtasks & Detailed Guidance

### T040 – Red: target precedence across crash + owned-lock abort
- **Purpose**: reproduce #4985/#4991 and #4996 second half (TDD red).
- **Steps**: create `tests/merge/test_merge_state_authority.py`.
  1. Start `merge --target develop`, simulate a crash (persist MergeState), then `--resume` with NO
     `--target`. Assert it lands on `develop` (persisted), NOT meta's default main (fails today).
  2. Assert precedence: an explicit `--target` beats a stale persisted value beats meta.
  3. Start two concurrent merges (two owner tokens); `--abort` one. Assert only the aborting
     invocation's lock is freed; the other's live lock is untouched (fails today: global unlink).
- **Files**: `tests/merge/test_merge_state_authority.py`.

### T041 – Fix: single persisted merge target
- **Purpose**: one resolved authority (C-1, D5).
- **Steps**:
  1. In `core/paths.py resolve_merge_target_branch` + `merge/resolve.py` (≈ `:284`), resolve the
     target once with precedence `--target` > persisted `MergeState.target_branch` > meta.json.
  2. Persist the resolved target into MergeState (`state.py`) at first resolution; `--resume` reads
     this, never re-derives from meta.
  3. Confirm the value flows to the executor's 28 read-sites via WP06's reseed (do not re-wire the
     executor beyond the one permitted lock line).
- **Files**: `src/specify_cli/core/paths.py`, `src/specify_cli/merge/resolve.py`,
  `src/specify_cli/merge/state.py`.
- **Notes**: keep `resolve_merge_target_branch` `<=15` complexity; the precedence is a small,
  testable pure function — unit-test each branch (Sonar new-code coverage).

### T042 – Fix: owned merge lock
- **Purpose**: owner_token = merge-state-id (C-2, D7, PP-F2).
- **Steps**:
  1. In `state.py acquire_merge_lock` (≈ `:370`), write `owner_token = merge-state-id` into the lock
     body (stable across resume — a pid cannot survive the crash the lock protects).
  2. In `cli/commands/merge.py _dispatch_abort` (≈ `:462`), release the lock ONLY when its
     `owner_token` matches the aborting invocation's merge-state-id; never blanket-unlink. A
     stale/dead-owner lock is reclaimable only via an explicit liveness check.
  3. The one permitted `executor.py` edit: pass `owner_token = merge-state-id` at the lock-acquire
     call site.
- **Files**: `src/specify_cli/merge/state.py`, `src/specify_cli/cli/commands/merge.py`
  (+ the one documented `executor.py` lock-acquire line).

### T043 – Verify red→green + gates
- **Steps**: confirm RED→GREEN; run `PWHEADLESS=1 .venv/bin/python -m pytest tests/merge/
  tests/terminus/ -q` and paste output. `ruff check` + `ruff format --check` + `mypy
  src/specify_cli/core/paths.py src/specify_cli/merge/resolve.py src/specify_cli/merge/state.py
  src/specify_cli/cli/commands/merge.py` clean.

## Test Strategy

- Owning subsystem `tests/merge/` in full plus the `tests/terminus/` repros for #4985/#4991/#4996.
- Compiler gate on all four typed sources.

## Risks & Mitigations

- **owner_token = pid** cannot survive a crash (`--resume` = new pid) — pin to merge-state-id (PP-F2).
- **Blanket unlink** on abort frees a live merge (#4996) — gate on owner match.
- **Un-documented executor edit** — only the one lock-acquire line, with rationale recorded.

## Definition of Done

- `test_merge_state_authority.py` RED on the mission base, GREEN on the fix; WP01's #4985/#4991/#4996
  repros flip GREEN.
- The landing target is resolved once (`--target` > persisted > meta), persisted into MergeState, and
  read by all phases + `--resume`; `--resume` never re-derives from meta.
- `owner_token = merge-state-id` (stable across resume); `--abort` frees only a lock it owns and never
  a different mission's live merge.
- The single permitted `executor.py` lock-acquire edit is documented in the WP + PR with rationale;
  no other executor change.
- Happy-path merge suite green (NFR-004); `ruff` + `mypy` clean over all four sources; no new
  `# type: ignore`; `resolve_merge_target_branch` stays `<=15` complexity.

## Review Guidance

- Confirm `--resume` lands on the persisted target, not meta.
- Confirm precedence `--target` > persisted > meta (unit-tested per branch).
- Confirm `--abort` frees only the owning lock; the one executor edit is documented.
- Confirm `owner_token` is the merge-state-id, not a pid (PP-F2).

## Activity Log

> **CRITICAL**: chronological order, append to END, current UTC time.

- 2026-09-23T21:36:42Z – system – Prompt created.

### Updating Status

`spec-kitty agent tasks move-task WP09 --to <lane>`.
