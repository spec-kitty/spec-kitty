---
work_package_id: WP05
title: Executor integration (single executor.py owner)
dependencies:
- WP03
- WP04
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-005
planning_base_branch: fix/terminus-integrity-followups
merge_target_branch: fix/terminus-integrity-followups
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-integrity-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-integrity-followups unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-terminus-integrity-followups-01M393QR
base_commit: c95c59616264f38f3b4a54ea8832214fcd78cd39
created_at: '2026-09-24T08:46:39.596356+00:00'
subtasks:
- T019
- T020
- T021
- T022
- T023
phase: Phase 2 - Serial integration (executor.py single owner)
history:
- at: '2026-09-24T07:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/executor.py
create_intent:
- tests/merge/test_executor_terminus_integrity.py
execution_mode: code_change
owned_files:
- src/specify_cli/merge/executor.py
- tests/merge/test_executor_terminus_integrity.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Executor integration

## ⚡ Do This First: Load Agent Profile
Use the `/ad-hoc-profile-load` skill to load `python-pedro` (role `implementer`, agent `claude`) before
reading further. State what you applied, then continue.

## Markdown Formatting
Wrap HTML/XML tags in backticks. Use language identifiers in fenced code blocks.

## Objectives & Success Criteria

The single `executor.py` owner: wire the WS1 honest message and the WS2 resume anchoring against the additive
`MergeState` fields (WP04) and the reconciliation API (WP03). This is the riskiest WP (data-loss-sensitive
resume). Depends on WP03 + WP04. Success (FR-002, FR-003, FR-004, FR-005):

- **FR-002** honest squash pass-message: the squash success line must not assert excluded-commit reachability
  was verified beyond what the axis computed. CRITICAL: do NOT strip `enforce_closed_world` in the
  `_reconciliation_claim_for_gate` `replace(captured, verify_reachability=False)` (post-plan architect — the
  axis silently no-ops to PASS if you do).
- **FR-003** strategy reseed: persist the resolved strategy **that attempt-1 actually executes** into
  `MergeState` (mirror the landed C-1 target reseed at ~`executor.py:2735`), so resume reads a truthful value
  (post-plan F14; the executor default is SQUASH at ~2661/2932).
- **FR-004 / FR-005** resume anchoring: `_resolve_pre_mutation_coord_sha` (mirror `_resolve_pre_mutation_target_sha`
  ~1782-1794 byte-for-byte: `if persisted: return; else capture+save once`), persist `pre_interrupt_lane_tips`
  at the FIRST pre-mutation capture, and consume the PERSISTED coord base at the reconciliation-claim
  `coord_base` consumption site (not the live `_capture_coord_checkpoint`) — otherwise resume re-poisons the
  window (post-plan F3/F9). Use WP04's lane-tip CAS on resume; REFUSE on absent base (H4) or true divergence.

**Read first**: `work/epic-5001-research/followup-debbie.md`, `data-model.md` (§2), `contracts/invariants.md`
(INV-2), and current `merge/executor.py`: `_reconciliation_claim_for_gate` (~1865), `_resolve_pre_mutation_target_sha`
(~1766-1794), the two coord-checkpoint captures (`_capture_pre_mutation_coord_checkpoint` ~2795 and the LIVE
`_capture_coord_checkpoint` ~1816 consumed as `coord_base` ~1818), `_reconciliation_pass_message` (~1891), the
resume/phase list (~2705-2762), and the strategy defaults (~2661/2932). VERIFY all anchors — they drift. Depend
on WP03's `reconciliation` API + WP04's `MergeState` fields / CAS helper (develop against their signatures).

## Subtasks

### T019 — honest squash pass-message (FR-002)
- Make `_reconciliation_pass_message` / the squash success line state that content attribution was verified via
  the squash content axis (once WP03 lands) — or, if the axis is deferred for a case, say so honestly. Ensure
  `enforce_closed_world` is NOT stripped anywhere the claim is `replace`d for squash.

### T020 — strategy reseed persist (FR-003)
- At the reseed site (mirroring the C-1 target reseed), write the resolved strategy attempt-1 executes into
  `MergeState.strategy`. On the resume path, the effective strategy already comes from WP04's cli precedence;
  ensure the executor consumes it consistently (no second SQUASH default overriding it).

### T021 — read-persisted-first coord/lane-tip anchors (FR-004)
- Add `_resolve_pre_mutation_coord_sha(state, run)` mirroring `_resolve_pre_mutation_target_sha` exactly:
  `if state.pre_mutation_coord_sha: return it`; else capture the coord tip once (at the FIRST pre-mutation
  capture, ~2795, before `_phase_merge_lanes`) and persist. Likewise persist `pre_interrupt_lane_tips` once at
  that first capture. Never overwrite on a later resume (that re-poisons — F3).

### T022 — anchor claim + lane-tip CAS on resume (FR-004/FR-005)
- At the reconciliation-claim `coord_base` consumption site (~1818), consume the PERSISTED coord sha (T021),
  not the live checkpoint (F9). On resume, validate each lane against `pre_interrupt_lane_tips` via WP04's CAS
  helper; REFUSE (fail-closed) on true divergence (H3) or an absent required base (H4). Confirm #4985/#4991
  land on the correct non-default target (the #5012 FIX-A destination_ref override already handles the
  housekeeping commit — do not regress it).

### T023 — unit tests (tests/merge/test_executor_terminus_integrity.py, red-first)
- Strategy: a fresh `--strategy merge` persists `merge`; a resume with no `--strategy` reads `merge`.
- Coord-base no-re-poison: simulate a resume (and a resume-of-a-resume) and assert the persisted
  `pre_mutation_coord_sha` / lane tips are NOT overwritten by attempt-2's live state (regression for F3/F9).
- Message honesty: the squash pass-message reflects the axis result; `enforce_closed_world` survives the
  `replace`.
- Absent persisted base on a resume that requires it ⇒ REFUSE (H4).

## Definition of Done
- FR-002/003/004/005 wired; with WP03/WP04, #4982/#4997/#4985/#4991 go green at integration.
- The transaction boundary (verify → FAIL → CAS-rollback → exit-1) is preserved; no teardown/push/exit-0 before
  verify. Squash-FAIL rides the existing rollback unchanged.
- Every new branch has a unit test (NFR-001); re-poison regression proven. `ruff`/`mypy`/`ruff format --check`
  clean; new helpers ≤ McCabe 15.

## Risks / reviewer guidance
- Reviewer: the two load-bearing regressions are (1) `enforce_closed_world` NOT stripped in the squash
  `replace` (else the P0 axis no-ops), and (2) read-persisted-first anchors NOT overwritten on resume (else
  #4982 is restored). Verify both with the T023 tests. Confirm the persisted strategy equals attempt-1's
  executed value (F14). This WP owns `executor.py` alone — no other WP edits it.
