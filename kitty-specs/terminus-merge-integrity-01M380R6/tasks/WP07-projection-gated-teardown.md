---
work_package_id: WP07
title: Projection + gated teardown (S-B)
dependencies:
- WP06
requirement_refs:
- FR-004
planning_base_branch: fix/terminus-merge-integrity
merge_target_branch: fix/terminus-merge-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-merge-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-merge-integrity unless the human explicitly redirects the landing branch.
subtasks:
- T032
- T033
- T034
- T035
phase: Phase 3 - Serialized executor lane
history:
- at: '2026-09-23T21:36:42Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/bookkeeping_projection.py
create_intent:
- tests/coordination/test_projection_teardown.py
execution_mode: code_change
owned_files:
- src/specify_cli/merge/bookkeeping_projection.py
- src/specify_cli/coordination/teardown.py
- tests/coordination/test_projection_teardown.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Projection + gated teardown (S-B)

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

Concurrent committed work must survive a merge. Success (FR-004; traces #4981 #4970 #4973):

- Before teardown, **ALL** commits added to the coord ref after the bookkeeping checkpoint are
  projected onto the target — not only `status.events.jsonl` / `status.json` (today's bug).
- Teardown is **gated** on the projection + a reachability check succeeding, and the coord-ref
  advance is CAS (coord tip unchanged since checkpoint) or teardown aborts.
- **Callee internals only** — the executor call sites are already wired by WP06; this WP changes what
  `bookkeeping_projection` projects and what `teardown` requires, not where they are called.

## Context & Constraints

- Spec: [../spec.md](../spec.md) US2 scenario 1, FR-004. Research D4; DEBRIEF §3 S-B, §4 (#4981/#4970/#4973).
- Data model: [../data-model.md](../data-model.md) `CoordCheckpoint` — teardown may proceed only if
  all post-checkpoint commits are projected AND the coord tip advances under CAS.
- **Grounded anchors** (verify in-tree; names are the durable anchors):
  - `_project_status_bookkeeping_to_target(...)` ≈ `bookkeeping_projection.py:282`. Today it projects
    only the `status.events.jsonl`/`status.json` byte-sets (see the module note ≈ `:34`, and the
    union/rematerialize helpers ≈ `:247`/`:268`). Widen to ALL post-checkpoint commits.
  - `teardown_coordination_topology(...)` ≈ `coordination/teardown.py:125`;
    `_destroy_coordination_worktree` ≈ `:98`; `_persist_retrospective` ≈ `:66`. Today teardown
    persists only the retrospective then destroys, with no reachability/CAS gate.
  - The coord checkpoint is captured by `_capture_coord_checkpoint` (executor, ≈ `:806`) and reaches
    these callees via the `_MergeRunState` fields WP06 scaffolded — consume those fields; do not add
    new executor call sites.
- Locality (C-004): only `bookkeeping_projection.py`, `teardown.py`, + the new test. Do NOT edit
  `executor.py` (WP06/WP09 own it) or `coherence.py` (WP08 owns the heal).

## Branch Strategy

- **Strategy**: serialized executor lane, after WP06.
- **Planning base branch / Merge target branch**: `fix/terminus-merge-integrity`.

## Subtasks & Detailed Guidance

### T032 – Red: post-checkpoint commit survives; changed coord tip aborts teardown
- **Purpose**: reproduce #4981 (TDD red).
- **Steps**: create `tests/coordination/test_projection_teardown.py`.
  1. Append a NON-status commit (e.g. an arbitrary coord-ref file commit, mirroring a concurrent
     verdict/emit) to the coord ref AFTER the bookkeeping checkpoint. Drive projection+teardown.
     Assert — in the harness, by inspecting the target ref once `_project_status_bookkeeping_to_target`
     + `teardown_coordination_topology` have run — that the commit is **reachable from the target ref**
     (fails today: only status files are projected, so it dies in teardown). This terminates on a
     diff-inspectable ref state, not a real post-integration event.
  2. Assert that when the coord tip changed since the checkpoint, teardown **aborts** (CAS) rather
     than destroying the branch (fails today: no CAS gate).
- **Files**: `tests/coordination/test_projection_teardown.py`.

### T033 – Fix: project ALL post-checkpoint coord commits
- **Purpose**: complete step B of the transaction (D4).
- **Steps**: in `_project_status_bookkeeping_to_target` (≈ `:282`), project every commit added to the
  coord ref after `tip_sha_at_checkpoint` onto the target — not just the status byte-sets. Keep the
  existing status-event union/rematerialize for the status files, but add the general
  post-checkpoint commit projection so concurrent verdict/emit commits land. Bound the work to
  commits after the checkpoint (O(#post-checkpoint commits)).
- **Files**: `src/specify_cli/merge/bookkeeping_projection.py`.
- **Notes**: preserve the append-only status-log semantics (WP08 owns the SHA-scoped heal — do not
  range-revert here).

### T034 – Fix: teardown gated on reachability + coord-ref CAS
- **Purpose**: never tear down over unprojected/moved coord state (D4).
- **Steps**: in `teardown_coordination_topology` (≈ `:125`), before `_destroy_coordination_worktree`,
  require (a) the reachability check passes (consume WP06's verifier result / the projected set) and
  (b) the coord tip advances from `tip_sha_at_checkpoint` under CAS (unchanged since checkpoint) —
  else abort teardown with a structured, non-zero refusal. Persist the retrospective only after the
  gate passes.
- **Files**: `src/specify_cli/coordination/teardown.py`.
- **Notes**: the coord/worktree/marker triple stays ONE coupled decision (CLAUDE.md merge-retention
  invariant) — abort tears down nothing partially.

### T035 – Verify red→green + gates
- **Steps**: confirm RED→GREEN; run `PWHEADLESS=1 .venv/bin/python -m pytest tests/coordination/
  tests/merge/ tests/terminus/ -q` and paste output. `ruff check` + `ruff format --check` + `mypy
  src/specify_cli/merge/bookkeeping_projection.py src/specify_cli/coordination/teardown.py` clean.

## Test Strategy

- Owning subsystem `tests/coordination/` in full, plus `tests/merge/` and the `tests/terminus/`
  Tier-0 gate (#4981 repro flips green).
- Compiler gate on both typed sources.

## Risks & Mitigations

- **Projecting only status files** (today's bug) drops concurrent commits — T033 projects all.
- **Teardown over a moved coord tip** — CAS gate (T034).
- **Range-reverting the status log** here would collide with WP08 — leave the heal to WP08.

## Definition of Done

- `test_projection_teardown.py` RED on the mission base, GREEN on the fix; WP01's #4981 repro flips
  GREEN and the Tier-0 property test stays green.
- ALL post-checkpoint coord commits (not only status files) are projected onto the target before
  teardown, bounded O(#post-checkpoint commits) (NFR-003).
- Teardown aborts (structured, non-zero) when the coord tip moved since checkpoint (CAS), tearing
  down nothing partially (coupled triple).
- Only callee internals changed — no new executor call sites (WP06 owns wiring).
- Happy-path merge suite stays green (NFR-004); `ruff` + `mypy` clean, no new `# type: ignore`.

## Review Guidance

- Confirm a concurrent post-checkpoint commit is reachable from the target ref once the harness has
  run projection + teardown (inspected on the ref, not deferred to real integration).
- Confirm teardown aborts when the coord tip moved since checkpoint.
- Confirm only callee internals changed (no new executor call sites).
- Confirm the append-only status semantics are preserved (no range-revert — that is WP08).

## Activity Log

> **CRITICAL**: chronological order, append to END, current UTC time.

- 2026-09-23T21:36:42Z – system – Prompt created.

### Updating Status

`spec-kitty agent tasks move-task WP07 --to <lane>`.
