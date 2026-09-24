---
work_package_id: WP08
title: 'Coherence integrity: SHA-scoped heal + topology residue (S-B heal + C-3)'
dependencies:
- WP07
requirement_refs:
- FR-005
- FR-009
planning_base_branch: fix/terminus-merge-integrity
merge_target_branch: fix/terminus-merge-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-merge-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-merge-integrity unless the human explicitly redirects the landing branch.
subtasks:
- T036
- T037
- T038
- T039
phase: Phase 3 - Serialized executor lane
history:
- at: '2026-09-23T21:36:42Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/coherence.py
create_intent:
- tests/coordination/test_coherence_integrity.py
execution_mode: code_change
owned_files:
- src/specify_cli/coordination/coherence.py
- tests/coordination/test_coherence_integrity.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Coherence integrity: SHA-scoped heal + topology residue

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

`coordination/coherence.py` is the single owner of two coupled defects (PR-priti: one owner in the
serial lane). Success (FR-005, FR-009; traces #4973 #4978):

- **Strand heal** reverts only explicitly recorded SHAs — never a `git revert captured..HEAD` range
  that can erase a third party's later event on the append-only log (#4973).
- `is_coord_residue_churn` threads the mission's **stored topology** — planning artifacts on
  lanes/single_branch missions are never classified as coord residue and `reset --hard`ed (#4978).

## Context & Constraints

- Spec: [../spec.md](../spec.md) US2 scenario 3 (FR-005), US5 scenario 1 (FR-009). Research D8;
  DEBRIEF §3 C-3, §4 (#4973/#4978). The classifier's own docstring already says it is only valid
  under COORD.
- **Grounded anchors** (verify in-tree; names are the durable anchors):
  - `is_coord_residue_churn(...)` ≈ `coherence.py:113`; it returns
    `kind_is_coordination_residue(kind, MissionTopology.COORD)` ≈ `:158` — the hard-coded
    `MissionTopology.COORD` is the bug (docstring warns it is only correct under coord, ≈ `:79`).
  - The strand-heal revert: a blind `git revert captured_sha..HEAD` range would re-apply / erase
    later events (see the heal region ≈ `:235`/`:292-302`). Make it SHA-scoped.
- Locality (C-004): only `coherence.py` + the new test. Do NOT edit `teardown.py`/`bookkeeping_projection.py`
  (WP07) or `executor.py` (WP06/WP09).

## Branch Strategy

- **Strategy**: serialized executor lane, after WP07.
- **Planning base branch / Merge target branch**: `fix/terminus-merge-integrity`.

## Subtasks & Detailed Guidance

### T036 – Red: SHA-scoped heal + topology-aware residue
- **Purpose**: reproduce #4973 (range revert erases a reopen) and #4978 (topology-blind residue).
- **Steps**: create `tests/coordination/test_coherence_integrity.py`.
  1. Build an append-only status log where a third party appended a later event AFTER the SHA the
     heal recorded. Drive the strand heal. Assert it reverts ONLY the recorded SHA and the third
     party's later event **survives** (fails today: the range revert erases it → #4973).
  2. Build a lanes/single_branch mission with dirty planning artifacts (issue-matrix, traces,
     decisions, status log). Drive `is_coord_residue_churn` with the mission's actual topology.
     Assert the artifacts are NOT classified as coord residue (fails today: hard-coded COORD → they
     would be `reset --hard`ed → #4978).
- **Files**: `tests/coordination/test_coherence_integrity.py`.

### T037 – Fix: SHA-scoped strand heal
- **Purpose**: content-scoped revert, never a range (FR-005, D-R3).
- **Steps**:
  1. Replace any `git revert <captured_sha>..HEAD` range (≈ `:302`) with a revert of ONLY the
     explicitly recorded SHA(s): `git revert --no-edit <sha>` per recorded SHA. A range revert sweeps
     in every commit between `captured_sha` and `HEAD` — including a third party's later append —
     which is exactly the #4973 erasure.
  2. If multiple SHAs are recorded, revert each individually (still SHA-scoped), in a deterministic
     order; never collapse them into a contiguous range.
  3. Preserve the existing "already-coherent → no-op" behavior (`healed = False` when nothing was
     reverted) and the swallowed-diagnostic reporting (`error` carries the revert diagnostic).
  4. Preserve the append-only invariant: the heal appends revert commits, it never rewrites history
     of the status log.
- **Files**: `src/specify_cli/coordination/coherence.py`.
- **Notes**: keep the heal function `<=15` complexity; extract a `_revert_recorded_sha(repo, sha)`
  helper if needed (ruff C901 / Sonar S3776). Hoist repeated revert-command tokens/messages to
  module constants if used `>=3` times (Sonar S1192).

### T038 – Fix: topology-aware residue classification
- **Purpose**: thread stored topology (C-3, D8).
- **Steps**: change `is_coord_residue_churn` (≈ `:113`) to accept/thread the mission's **stored
  topology** and pass it to `kind_is_coordination_residue(kind, topology)` instead of the hard-coded
  `MissionTopology.COORD` (≈ `:158`). Churn is classified as coord residue ONLY under COORD topology;
  on lanes/single_branch, planning artifacts are preserved. Thread the topology from the caller (the
  merge dirty gate reads it from the stored mission manifest).
- **Files**: `src/specify_cli/coordination/coherence.py`.
- **Notes**: the caller (the executor dirty gate) already has the stored topology after WP06's
  scaffold — accept it as a parameter; do not read the manifest a second time here.

### T039 – Verify red→green + gates
- **Steps**: confirm RED→GREEN; run `PWHEADLESS=1 .venv/bin/python -m pytest tests/coordination/
  tests/terminus/ -q` and paste output. `ruff check` + `ruff format --check` + `mypy
  src/specify_cli/coordination/coherence.py` clean.

## Test Strategy

- Owning subsystem `tests/coordination/` in full plus the `tests/terminus/` repros for #4973/#4978.
- Compiler gate on `coherence.py`.

## Risks & Mitigations

- **Range revert** under a shape-only guard erases a reopen — SHA-scoped only (T037).
- **Topology-blind classifier** destroys planning artifacts — thread stored topology (T038).
- **Double-reading the manifest** — accept topology as a parameter from the caller.

## Definition of Done

- `test_coherence_integrity.py` RED on the mission base, GREEN on the fix; WP01's #4973/#4978 repros
  flip GREEN.
- The strand heal reverts only recorded SHAs (per-SHA `git revert`), never a range; a third party's
  later append survives; the append-only invariant holds.
- `is_coord_residue_churn` classifies via the caller-supplied stored topology; lanes/single_branch
  planning artifacts are never `reset --hard`ed.
- `ruff check` + `ruff format --check` + `mypy src/specify_cli/coordination/coherence.py` clean; no
  new `# type: ignore`; the heal + classifier stay `<=15` complexity.

## Review Guidance

- Confirm the heal reverts only recorded SHAs; a third party's later event survives.
- Confirm residue classification uses stored topology (planning artifacts survive on lanes/single_branch).
- Confirm topology is accepted as a parameter (no second manifest read here).
- Confirm no history rewrite of the append-only status log.

## Activity Log

> **CRITICAL**: chronological order, append to END, current UTC time.

- 2026-09-23T21:36:42Z – system – Prompt created.

### Updating Status

`spec-kitty agent tasks move-task WP08 --to <lane>`.
