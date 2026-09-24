---
work_package_id: WP06
title: Reconciliation gate scaffold + verifier (S-D)
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-012
planning_base_branch: fix/terminus-merge-integrity
merge_target_branch: fix/terminus-merge-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-merge-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-merge-integrity unless the human explicitly redirects the landing branch.
subtasks:
- T025
- T026
- T027
- T028
- T029
- T030
- T031
phase: Phase 3 - Serialized executor lane
history:
- at: '2026-09-23T21:36:42Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/reconciliation.py
create_intent:
- src/specify_cli/merge/reconciliation.py
- tests/merge/test_reconciliation.py
execution_mode: code_change
owned_files:
- src/specify_cli/merge/executor.py
- src/specify_cli/merge/reconciliation.py
- src/specify_cli/merge/git_probes.py
- tests/merge/test_reconciliation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Reconciliation gate scaffold + verifier (S-D)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (frontmatter) before parsing the rest of
this prompt, and behave according to its guidance.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

Apply the resolved boundaries (no architectural decisions — the seam shape is already decided in the
plan) and TDD discipline. State what you applied, then continue.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use fenced code-block language identifiers.

---

## Objectives & Success Criteria

This is the **MVP** and the head of the serialized executor lane. It makes the epic invariant
executable. Success (FR-001, FR-002, FR-012; NFR-005):

- A **scaffold** lands ALL new `_MergeRunState` fields + the linear-caller phase slot + a
  `reconciliation.py` stub in ONE change (so the following serial WPs edit a stable dataclass).
- `MergeOutcomeVerifier.verify(target_ref, approved_wp_set) -> VerifyResult` is **fail-closed and
  Lamport-sourced**, compares the **target tree** against the approved-WP commit set by
  **reachability**, and excludes canceled/removed code by **patch-id equivalence**.
- The gate runs **before any teardown**, between `_phase_commit_and_assert` and cleanup; on FAIL it
  refuses, exits non-zero, tears down nothing, mutates nothing, and names the divergence.
- The manifest is **reseeded from `state.target_branch`** right after `_load_or_create_merge_state`
  (so the 28 `lanes_manifest.target_branch` read-sites see the persisted target — this is the wiring
  half of C-1; WP09 owns the resolution/persistence half).
- **FR-012**: pre-fix in-flight state is detected and refused (no retro-heal).
- **NFR-005**: a non-vacuous call-site gate enumerates all **6 terminus entry points** and a
  self-mutation test proves a 7th, unrouted path fails the gate.

**Scope discipline (PR-priti):** `executor.py` (2663 lines) is already decomposed into ~50
`_phase_*` functions over one `_MergeRunState` (`:256`). Do **NOT** decompose it further — that is
out-of-domain (DIRECTIVE_024) and would rewrite every hunk the fix needs. Add fields + one phase
slot + wiring only.

## Context & Constraints

- Spec: [../spec.md](../spec.md) US1, FR-001/FR-002/FR-012, NFR-003/NFR-005, C-001/C-003.
- Contract: [../contracts/terminus-reconciliation.md](../contracts/terminus-reconciliation.md) — read
  the FULL `verify` pre/post-conditions, the 6 entry points, and the terminus-command contract.
- Research: [../research.md](../research.md) D3 + **D3+ (amended) verifier claim integrity** +
  dispositions PP-F3/RN-Q4, RN-F4, RN-Q3, RN-F5. DEBRIEF §3 S-D.
- **Grounded anchors** (verify in-tree; names are the durable anchors — line numbers drift from the
  debrief's `upstream/main` HEAD):
  - `class _MergeRunState` ≈ `executor.py:256`.
  - Home the gate between `_phase_commit_and_assert` (≈ `executor.py:1587`) and cleanup
    (≈ `executor.py:1966`). Reuse `_capture_coord_checkpoint` (≈ `:806`) / `_CoordCheckpoint`.
  - `_load_or_create_merge_state` (imported from `merge/resolve.py` ≈ `executor.py:118`); insert the
    manifest reseed-from-state right after it loads (≈ `:2280-2288`).
  - **Lamport reduction** = `status/reducer.py` `materialize` / `materialize_snapshot`
    (≈ `:367`/`:405`), NEVER LWW `reduce_parsed` (≈ `reducer.py:180`, imported from
    `spec_kitty_events.diary` at `:17`). Routing choice stays inside `specify_cli` — do NOT modify
    `spec_kitty_events` (C-002).
  - `git_probes.py` — extend with the ancestry→tree-equality integration check; `_branch_trees_equal`
    (≈ `:57`) already exists as the tree-equality primitive; the ancestry-only probe lives ≈ `:31-54`.
  - Existing (circular) asserts to REPLACE the trust of, not delete: `_assert_merged_wps_done_on_target`
    (`done_bookkeeping.py`), `_phase_porcelain_invariant`. The gate is the tree-authoritative
    post-condition these lacked.
- Locality (C-004): `executor.py`, `reconciliation.py` (new), `git_probes.py`, + the new test.

## Branch Strategy

- **Strategy**: head of the single serialized executor lane. Requires WP01 (repros) + WP02 (CAS) landed.
- **Planning base branch / Merge target branch**: `fix/terminus-merge-integrity`.

## Subtasks & Detailed Guidance

### T025 – Red: `MergeOutcomeVerifier.verify` reachability + fail-closed claim
- **Purpose**: pin the verifier contract before wiring (TDD red; complements WP01's Tier-0 property).
- **Steps**: create `tests/merge/test_reconciliation.py`. Unit-test the verifier directly:
  1. PASS iff every approved WP's approved commit SHAs are reachable from `target_ref` AND no
     excluded patch-id is reachable.
  2. FAIL(divergence) when an approved SHA is missing OR an excluded patch-id is present; FAIL never
     mutates.
  3. **Fail-closed claim**: refuse when the coord surface is unresolved/unmaterialized, or when the
     derived claim is empty while the manifest lists WPs (cross-check against manifest `all_wp_ids`).
  4. **Non-vacuous excluded-check** even when the canceled set is empty (planted-canceled-commit).
  5. O(#approved commits), not O(repo history) (NFR-003).
- **Files**: `tests/merge/test_reconciliation.py`.
- **Notes**: source approved SHAs from lane-branch tips (never status rows) — mirror WP01's helper.

### T026 – Scaffold: `_MergeRunState` fields + phase slot + `reconciliation.py` stub (ONE change)
- **Purpose**: give the serial lane a stable dataclass to edit (PR-priti).
- **Steps**:
  1. Add all new `_MergeRunState` fields the seam needs in ONE commit: e.g.
     `approved_wp_set`, `coord_checkpoint`, `reconciliation_result`, `target_expected_old_sha`,
     `projected_since_checkpoint` (name to match downstream WP07/WP08/WP09 needs — enumerate them
     here so later WPs only assign, never add). Default them so existing construction sites compile.
  2. Add the linear-caller **phase slot** — a `_phase_reconcile_before_teardown(run)` function
     inserted into the phase sequence between `_phase_commit_and_assert` and cleanup, initially a
     pass-through stub that the following subtasks fill.
  3. Create `src/specify_cli/merge/reconciliation.py` with the `MergeOutcomeVerifier`,
     `VerifyResult`/`Divergence` value objects, and the `verify(...)` signature as a stub raising
     `NotImplementedError` (filled in T027/T028).
- **Files**: `src/specify_cli/merge/executor.py`, `src/specify_cli/merge/reconciliation.py`.
- **Notes**: this subtask must not change behavior — it is the scaffold. Keep each `_phase_*` and
  `verify` `<=15` complexity.

### T027 – Verifier claim integrity (fail-closed + Lamport + tree-tip SHAs)
- **Purpose**: D3+ — the claim the gate trusts must be non-vacuous on the claim axis too.
- **Steps**: in `reconciliation.py`, build `approved_wp_set` **once per transaction**:
  - approved commit SHAs from **lane-branch git tips** (via `LaneIdentity`), never status rows;
  - WP membership (approved vs canceled) through the **Lamport** wrapper
    (`status/reducer.py` `materialize`/`materialize_snapshot`), never `reduce_parsed`;
  - **fail-closed**: if the coord surface is unresolved/unmaterialized, or the derived claim is empty
    while the manifest lists WPs, `verify` returns a refusal (never passes vacuously — closes PP-F3).
- **Files**: `src/specify_cli/merge/reconciliation.py`.
- **Notes**: this routing choice is entirely inside `specify_cli`; it does NOT touch, re-pin, or fix
  `spec_kitty_events` (#4990 stays out of scope, C-002). Because the claim is Lamport-sourced, a
  wall-clock-later approval cannot green-wash a committed rejection *in the gate's own claim*.

### T028 – Verifier reachability (excluded-by-patch-id; git_probes ancestry→tree-equality)
- **Purpose**: catch cherry-picked/rebased/re-lettered copies of canceled code (RN-F4).
- **Steps**:
  1. Reachability: every approved SHA reachable from `target_ref` (ancestry via `git_probes`).
  2. Excluded-commit check by **patch-id equivalence** (`git patch-id`), not SHA alone, sourcing the
     canceled set from `acceptably_canceled_wp_ids` mapped to lane tips — so a re-lettered/cherry-
     picked copy of canceled code is still caught.
  3. Extend `git_probes.py` with the ancestry→tree-equality integration check (reuse
     `_branch_trees_equal` ≈ `:57`); expose a helper the verifier calls.
- **Files**: `src/specify_cli/merge/reconciliation.py`, `src/specify_cli/merge/git_probes.py`.
- **Notes**: keep O(#approved commits) (NFR-003) — do not diff the whole tree.

### T029 – Wire the gate into the executor + manifest reseed-from-state
- **Purpose**: run the gate before teardown and fix the C-1 wiring half.
- **Steps**:
  1. Fill `_phase_reconcile_before_teardown(run)`: build the checkpoint (reuse `_capture_coord_checkpoint`),
     call `verify`; on FAIL refuse + non-zero + recovery guidance, **no teardown, no mutation**; on
     PASS continue to cleanup. The gate sits strictly between `_phase_commit_and_assert` (≈ `:1587`)
     and cleanup (≈ `:1966`).
  2. Inline the **manifest reseed-from-state**: right after `_load_or_create_merge_state` loads
     (≈ `:2280-2288`), set `run.lanes_manifest.target_branch = run.state.target_branch` so the 28
     read-sites see the persisted target. (WP09 owns resolving/persisting `state.target_branch`; this
     WP only makes the executor consume it — flag the dependency to WP09.)
  3. Scope the PASS success message to **"approved-WP commit reachability"** (NOT verdict-integrity —
     #4990 out of scope; FR-013).
- **Files**: `src/specify_cli/merge/executor.py`.

### T030 – FR-012 legacy refuse + NFR-005 non-vacuous call-site gate
- **Purpose**: forward-only legacy handling + a gate no future path can bypass (DIRECTIVE_043).
- **Steps**:
  1. FR-012: detect pre-fix in-flight `MergeState`/coord state (schema/marker absent) at the
     reconciliation entry and **refuse with a recovery instruction**; never retro-apply the new
     guarantees to auto-heal it (D6).
  2. NFR-005: add a non-vacuous call-site gate (concrete floor + self-mutation test + shrink-only
     allowlist) enumerating all **6 terminus entry points** — `merge`, `merge --resume`,
     `merge --abort`, `upgrade`, `agent issue-verdict`, `doctor coordination --fix`. The self-mutation
     test proves a 7th, unrouted terminus path fails the gate. Home the allowlist test under
     `tests/merge/test_reconciliation.py` (or a sibling in `tests/merge/`).
- **Files**: `src/specify_cli/merge/executor.py`, `tests/merge/test_reconciliation.py`.
- **Notes**: the allowlist is shrink-only — adding a terminus path without routing it through the
  gate must fail the test.

### T031 – Verify red→green + gates
- **Steps**: confirm WP01's Tier-0 property test flips RED→GREEN for the in-scope children;
  run `PWHEADLESS=1 .venv/bin/python -m pytest tests/merge/ tests/terminus/ -q` and paste output.
  `ruff check` + `ruff format --check` + `mypy src/specify_cli/merge/executor.py
  src/specify_cli/merge/reconciliation.py src/specify_cli/merge/git_probes.py` clean. Confirm the
  happy-path merge suite stays green (NFR-004).

## Test Strategy

- Owning subsystem `tests/merge/` in full + `tests/terminus/` (the shared Tier-0 gate).
- Every new branch/helper gets a focused test in THIS WP (Sonar new-code coverage).
- Compiler gate on all three typed sources.

## Risks & Mitigations

- **Vacuous pass** (claim via READ resolver degrades to empty primary) — fail-closed claim (T027).
- **Green-wash** via LWW membership (#4990) — Lamport-sourced claim (T027).
- **7th unrouted path** bypasses the gate — self-mutation test (T030).
- **God-module rewrite** — forbidden; add fields + one phase slot + wiring only (PR-priti).
- **Over-claiming verdict-integrity** — success message scoped to reachability (T029, FR-013).

## Review Guidance

- Confirm the gate runs BEFORE any teardown and FAIL mutates nothing.
- Confirm the claim is fail-closed, Lamport-sourced, and tree-tip-derived (not status rows).
- Confirm excluded-check is by patch-id and non-vacuous when canceled set is empty.
- Confirm the manifest reseed makes the 28 read-sites see the persisted target.
- Confirm the 6-entry-point allowlist + self-mutation test.
- Confirm `executor.py` was NOT decomposed further.

## Activity Log

> **CRITICAL**: chronological order, append to END, current UTC time.

- 2026-09-23T21:36:42Z – system – Prompt created.

### Updating Status

`spec-kitty agent tasks move-task WP06 --to <lane>`.
