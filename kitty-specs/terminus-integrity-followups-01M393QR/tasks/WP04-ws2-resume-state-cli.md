---
work_package_id: WP04
title: WS2 resume state and CLI strategy authority
dependencies: []
requirement_refs:
- FR-003
- FR-004
planning_base_branch: fix/terminus-integrity-followups
merge_target_branch: fix/terminus-integrity-followups
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-integrity-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-integrity-followups unless the human explicitly redirects the landing branch.
created_at: '2026-09-24T07:20:00+00:00'
subtasks:
- T016
- T017
- T018
phase: Phase 1 - Parallel fan (file-isolated)
history:
- at: '2026-09-24T07:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/state.py
create_intent:
- tests/merge/test_resume_strategy_authority.py
execution_mode: code_change
owned_files:
- src/specify_cli/merge/state.py
- src/specify_cli/cli/commands/merge.py
- tests/merge/test_resume_strategy_authority.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – WS2 resume state and CLI strategy authority

## ⚡ Do This First: Load Agent Profile
Use the `/ad-hoc-profile-load` skill to load `python-pedro` (role `implementer`, agent `claude`) before
reading further. State what you applied, then continue.

## Markdown Formatting
Wrap HTML/XML tags in backticks. Use language identifiers in fenced code blocks.

## Objectives & Success Criteria

Provide the additive `MergeState` fields + the lane-tip CAS helper + the resume strategy precedence with the
H1 flip-REFUSE, so WP05 can wire resume anchoring against pure-additive fields (no cross-WP required-kwarg
change). Success (FR-003, FR-004):

- `MergeState` gains additive fields (all default None/empty; legacy state deserializes cleanly):
  `pre_mutation_coord_sha`, `pre_mutation_coord_ref`, `pre_interrupt_lane_tips: dict[str,str]`. (The
  `strategy` field already exists; its persist happens in WP05's executor reseed — do NOT persist it here.)
- A pure, unit-testable lane-tip CAS helper on/near `MergeState` (e.g. `lane_tip_cas_ok(repo, lane_id,
  persisted_sha) -> bool`): compares the persisted SHA as a **git OBJECT** — accepts the live state being the
  persisted commit OR a descendant OR a **strict ancestor** (behind-HEAD is the #4982 window, post-plan D/F8);
  the lane BRANCH ref may be **gone** (already consolidated), so never require branch-ref existence; REFUSE
  only on true divergence (persisted commit unrelated to the live target tip). An absent required base ⇒ the
  caller REFUSEs (H4).
- `cli/commands/merge.py`: resume resolves strategy with precedence **explicit `--strategy` > persisted >
  config > SQUASH**; an explicit `--strategy` that **contradicts** the persisted value ⇒ REFUSE (H1).

**Read first**: `work/epic-5001-research/followup-debbie.md`, `data-model.md` (§2), `contracts/invariants.md`
(INV-2), and current `merge/state.py` (`MergeState`, `pre_mutation_target_sha`) + `cli/commands/merge.py`
(`_dispatch_resume`, the `resolved_strategy = strategy or config or SQUASH` site ~748-749, `--strategy`
default None ~636). Verify anchors. Tests: `PWHEADLESS=1 .venv/bin/python -m pytest
tests/merge/test_resume_strategy_authority.py -o addopts="" -q`.

## Subtasks

### T016 — MergeState additive fields + lane-tip CAS helper (merge/state.py)
- Add the three additive fields with safe defaults; ensure (de)serialization round-trips and a legacy state
  (fields absent) loads without error.
- Implement the lane-tip CAS helper as a pure function (object-compare via `git merge-base --is-ancestor` in
  both directions, or a small reachability probe). Behind-HEAD (persisted is a descendant of live, i.e. live is
  ancestor) MUST be accepted, not refused. Missing branch ref MUST NOT auto-REFUSE — resolve the persisted SHA
  as an object. Divergence (neither is an ancestor of the other) ⇒ False. Keep it ≤ McCabe 15.

### T017 — resume strategy precedence + H1 (cli/commands/merge.py)
- On the resume path, read `state.strategy` and compute the effective strategy with precedence explicit >
  persisted > config > SQUASH. If an explicit `--strategy` is passed AND differs from the persisted value ⇒
  REFUSE fail-closed with a clear message (H1 strategy-flip guard). Fresh (non-resume) runs are unchanged here
  (the persist itself is WP05's executor reseed).
- Keep the H2 legacy-marker refusal and any existing guards ordered BEFORE strategy consumption (post-plan HELD).

### T018 — unit tests (tests/merge/test_resume_strategy_authority.py, red-first)
- Precedence table: (explicit only), (persisted only → used), (config fallback), (SQUASH default), (explicit
  overrides persisted when equal is fine). 
- H1: explicit `--strategy merge` while persisted `squash` ⇒ REFUSE (and vice-versa).
- Lane-tip CAS: persisted==live ⇒ OK; live is descendant ⇒ OK; live is strict ancestor (behind-HEAD) ⇒ OK
  (regression for D/F8 — this is the bug being preserved, must NOT refuse); divergent ⇒ REFUSE; branch ref
  absent but object reachable ⇒ OK. 
- Absent required base ⇒ helper/caller REFUSE (H4).

## Definition of Done
- FR-003 (precedence + H1) and FR-004 (CAS helper + fields) landed; #4985/#4991 unblock via WP05's persist,
  #4982/#4997 via WP05's anchoring.
- Every branch (each precedence arm, H1, each CAS case, H4) has a direct unit test (NFR-001).
- Legacy `MergeState` deserialization proven. `ruff`/`mypy`/`ruff format --check` clean.
- Do NOT persist the strategy here and do NOT edit `executor.py` (WP05).

## Risks / reviewer guidance
- Import the CAS helper directly from `specify_cli.merge.state` at its call site (both `executor.py` and
  `cli/merge.py` already import from that submodule) — do NOT add it to `merge/__init__.py` `__all__` (unowned —
  post-tasks paula M2).
- Reviewer: the load-bearing case is the CAS **accepting behind-HEAD** — if it refuses, it breaks the exact
  #4982 window (post-plan D/F8). Verify that test. Verify H1 REFUSEs on a true flip but not on an equal explicit
  value. Confirm no executor edit and no strategy persist crept in.
