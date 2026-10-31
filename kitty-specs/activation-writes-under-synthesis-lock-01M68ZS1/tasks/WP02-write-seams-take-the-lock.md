---
work_package_id: WP02
title: Take the existing synthesis lock at the activation write seams
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-003
- SC-002
planning_base_branch: issue-6719-activation-writes-under-synthesis-lock
merge_target_branch: issue-6719-activation-writes-under-synthesis-lock
branch_strategy: Planning artifacts for this mission were generated on issue-6719-activation-writes-under-synthesis-lock. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6719-activation-writes-under-synthesis-lock unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
- T007
- T008
phase: Phase 2 - Write seams
history:
- at: '2026-10-31T13:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/pack_manager.py
- src/charter/activation/preset_application.py
- src/charter/activation/activation_engine.py
- src/charter/activation/activation_ledger.py
- src/charter/activation/ERROR_CODES.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Take the existing synthesis lock at the activation write seams

## ⚡ Do This First: Load Agent Profile

```bash
spec-kitty agent profile show python-pedro
spec-kitty charter context --action implement --include agent-profile:python-pedro
```

## Objective

Put the **existing** run-wide charter synthesis lock (#6453) around the activation-config and synthesis-manifest
read-modify-write windows of the four write seams #6719 names. Do **not** create a lock, a lock path or a lock
module: the lock is `charter.activation.synthesizer.synthesis_lock.synthesis_lock`, and
`charter.activation.bundle_restamp.restamp_bundle_hash` is the precedent (it already wraps its manifest RMW).

## Context

- `synthesis_lock(repo_root)` yields the lock path, waits a bounded 10 s (`_SYNTHESIS_LOCK_TIMEOUT_S`, read at
  call time), is re-entrant per thread, raises `SynthesisLockHeldError` /
  `SynthesisLockUnavailableError` (both `KittyInternalConsistencyError` with `.code` and `.body`).
- The invariant is the *window*, not the write: each seam reads its document, derives a plan in memory, then
  commits. A lock around the commit alone still lets a stale read win. Hold the window across read → plan →
  commit (→ restamp), and keep the preflight/validation reads outside it where they are read-only.
- `charter synthesize` / `charter resynthesize` hold the lock for their whole command, so a seam that takes it
  is serialized against them.

## Subtasks

### T004 — `ActiveCharterManager.activate` / `.deactivate` (`src/charter/activation/pack_manager.py`)

Wrap the body from `resolve_activation_write_target(...)` through `commit_plan(...)` **and** the trailing
`restamp_bundle_hash(repo_root)` in one `with synthesis_lock(repo_root):`. Docstring: state that the read-plan-write
is one unit under the run-wide synthesis lock and that the lock nests (re-entrant) with `restamp_bundle_hash`.
Keep the existing "no-op plan writes nothing" semantics; a no-op still reads under the lock but writes nothing.

### T005 — `preset_application` (`src/charter/activation/preset_application.py`)

`apply_preset_plan` must take the window for its read-modify-write (the `--force` deny-clearing arm reads
`_read_target` and writes). Where the plan itself is computed outside (`plan_preset_application`), the CLI
window in WP03 spans plan+apply; keep `apply_preset_plan` self-guarding too so a programmatic caller is safe.
Document the choice in a docstring line.

### T006 — `activation_engine.promote_activations` (`src/charter/activation/activation_engine.py`)

Make the append-only primitive take the lock for its own read-modify-write, so every caller is serialized
(`reach_only._promote` already nests it inside a synthesis run; `org_charter._promote_org_required_to_config`
from the interview path does not). Re-entrancy makes the nested case a no-op acquisition. Add a docstring
sentence that the primitive is self-guarding and re-entrant.

### T007 — `activation_ledger.apply_ledger_migration` (`src/charter/activation/activation_ledger.py`)

Hold the window across the whole apply: the ledger write, `_stamp_before_strips` → `_stamp_manifest` (the
manifest read-modify-write #6719 names), and the legacy-key strips. Do not lock only `_stamp_manifest`: the
stamp's hash must describe the document the strips produce, and a lock that ends between them re-opens the
window. Update the `apply_ledger_migration` and `_stamp_manifest` docstrings to say the RMW runs under the
run-wide synthesis lock.

### T008 — `src/charter/activation/ERROR_CODES.md`

Document `CHARTER_SYNTHESIS_LOCK_HELD` and `CHARTER_SYNTHESIS_LOCK_UNAVAILABLE` for the activation write
surface: what is refused, that nothing is written, and the bounded-wait-then-retry remedy. Cite #6453 (owner of
the lock) and #6719 (this mission).

## Definition of Done

- `uv run pytest tests/charter/activation/test_activation_writes_under_synthesis_lock.py -q` — T001/T002 green,
  T003 green for the non-CLI assertions (`apply_ledger_migration` refusal included).
- No new lock file, module, path or ordering rule (NFR-001); grep your diff for `synthesis_lock_path`,
  `machine_file_lock`, `LOCK_DIRECTORY` — the diff must not add a path.
- These suites stay green (run them, do not assume):
  `tests/charter/synthesizer/test_synthesis_lock.py`, `test_synthesis_lock_cli.py`,
  `test_synthesize_activation_append.py`, `tests/charter/test_activate_restamps_bundle_hash.py`,
  `tests/charter/activation/`, `tests/charter/presets/`, plus the activation-ledger migration tests
  (`uv run pytest tests/charter -k "ledger or activate or preset" -q`).
- `uv run ruff check` and `uv run ruff format --check` clean on every touched file; `mypy` clean on the touched
  modules if the repo gate covers them.
- No `precondition_changed` behaviour removed: the guard stays as the second line of defence.

## Risks

- Nested acquisition must stay re-entrant (`charter deactivate --resynthesize` runs a synthesis inside the
  command). If a deadlock appears, the lock is being taken through a different path — fix the caller, do not
  add a second lock.
- A lock held while doing slow I/O (identity index scans) lengthens the window for a concurrent run; take the
  lock after the cheap preflight reads and keep only the document RMW inside.
- Do not make `--dry-run` / `--list-topics` paths wait (C-002): those never reach these seams, so verify with a
  test or a manual run rather than by adding `synthesis_lock_unless` everywhere.

## Reviewer guidance

The diff must read as "the existing lock, applied at four seams". Reject any new lock primitive, any
sleep/poll-based retry, any broadened `except` that swallows the lock errors, and any change that makes a
read-only path take the lock.
