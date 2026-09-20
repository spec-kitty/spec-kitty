---
work_package_id: WP03
title: Topology-aware mission_number bake (#4474)
dependencies:
- WP01
requirement_refs:
- FR-011
planning_base_branch: issue-4764-terminus-safety-invariant
merge_target_branch: issue-4764-terminus-safety-invariant
branch_strategy: Planning artifacts for this mission were generated on issue-4764-terminus-safety-invariant. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4764-terminus-safety-invariant unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
history:
- created by planner-priti at 2026-09-19T19:43:00Z
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/ordering.py
create_intent:
- tests/merge/test_issue_4474_topology_aware_bake.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/merge/ordering.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before ANY other action, load the `python-pedro` profile via `/ad-hoc-profile-load` (skill `spk-doctrine-profile-load`, or `spec-kitty charter context --action implement` + `spec-kitty agent profile show python-pedro`). Adopt its identity, implementer-only boundaries, and TDD/type-safety discipline. Do not proceed until the profile is loaded.

## Objective

Fix #4474's actual defect: the `mission_number` bake **fail-opens** on a **merge-ready** coord-topology mission. At `merge/ordering.py`, when the mission-branch tree lacks `meta.json` (which it can on coord topologies), the bake logs a warning and `return False` — the number is silently lost and `doctor` stays stuck at `pending`. Make the write-back **topology-aware** (reach the correct primary-tree `meta.json` surface) OR **surface** the unbaked field as a queryable event + a merge-summary line — never a silent log-only fail-open. Delivers **FR-011**.

**This is DISTINCT from FR-006** (WP02), which prevents baking a *not*-merge-ready mission (baking too early → split-brain). FR-011 is the OPPOSITE mode: a genuinely merge-ready mission LOSING its number. Do not conflate them.

## Context

- **Spec**: FR-011 (mission_number bake is topology-aware, never a silent fail-open); D7 (the delivering requirement for #4474, which was originally folded in name only); US1 tail (the same bake fail-open surfaced by #4474). Edge Cases + Domain Language: **fail-open** = a guard that silently proceeds/skips on an unmet condition; the invariant replaces fail-open with refuse-or-surface.
- **Contract**: `contracts/terminus-safety-contract.md` → **C-MERGE (BAKE)**: `mission_number` write-back reaches the correct meta.json surface, or the unbaked field is surfaced as a queryable event + merge-summary line — never a silent fail-open.
- **Data model**: `data-model.md` → `mission_number` field concern (FR-011 topology-aware write-back on a merge-ready coord mission; no silent loss).
- **Research** (`research.md`): `merge/ordering.py:398-414` composes the meta.json path inside the mission-branch tree and `return False` (skip, number lost, `doctor` stuck at `pending`) when it is absent — which on coord topologies it can be.
- **Seam anchors** (verified on this branch):
  - `src/specify_cli/merge/ordering.py:135` — `assign_next_mission_number(target_branch_path, mission_specs_dir)`
  - `src/specify_cli/merge/ordering.py` ~`:388-398` — composes the in-branch meta path via `compose_meta_json_path`; **keeps** the `path_is_under_worktrees(meta_path)` guard (`return False` when the resolved path is under `.worktrees/` — this guard prevents re-polluting the mission-branch tree and MUST stay)
  - `src/specify_cli/merge/ordering.py` ~`:407` — `return False` when `meta_path` resolves under `.worktrees/`
  - `src/specify_cli/merge/ordering.py` ~`:414` — `return False` when `meta_path` does not exist on the mission branch (the #4474 silent-loss site)
  - `_bake_mission_number_into_mission_branch`, `_mark_mission_number_baked`, `_is_assigned_mission_number` (the bake cluster, `__all__` around `:43-48`)

## Per-Subtask Guidance

### T011 — RED-first #4474 regression test

Create `tests/merge/test_issue_4474_topology_aware_bake.py`, `@pytest.mark.regression`, issue-pinned to #4474. Two cases (FOLD 4 — do NOT settle for the cheap surface-only escape):
- **Preferred-outcome case (primary reachable)**: a NORMAL merge-ready coord mission where the primary tree IS reachable. Assert the PREFERRED outcome — `mission_number` is genuinely PERSISTED to the primary-tree `meta.json` and `doctor` flips `pending`→`assigned`. Surfacing-only (an event/summary line without a persisted number) is INSUFFICIENT for this case and must fail the test.
- **Genuinely-unreachable fallback case (separately constructed)**: a mission where the primary-tree `meta.json` genuinely cannot be reached. Assert the fallback — the unbaked field is surfaced as a queryable event + a merge-summary line (never a silent `return False`).

Both drive through the pre-existing merge/bake entry point (C-004). RED before T012, GREEN after.

### T012 — Topology-aware write-back or surfacing

Choose the durable fix per FR-011:
- **Preferred**: make the write-back reach the correct (primary-tree) `meta.json` for a coord-topology mission, so the number persists where `doctor`/selectors read it. Do NOT resolve into `.worktrees/` — keep the existing `path_is_under_worktrees` guard; the fix is reaching the PRIMARY tree, not the coord worktree.
- **Fallback (if the write genuinely cannot reach the surface)**: surface the unbaked field as a queryable event + a merge-summary line so a successful merge never silently loses `mission_number`. A logger-only warning is NOT sufficient — it must be observable by `doctor` and/or the merge summary.

Whichever path, the not-merge-ready case remains WP02's concern (FR-006) — this WP only changes the merge-ready behavior. **When the primary tree is reachable, the number MUST be persisted, not merely surfaced** (FOLD 4) — surfacing is the fallback for the genuinely-unreachable case only.

**Architectural re-pin note (FOLD 4 / paula, verified live).** `tests/architectural/test_no_dead_symbols.py` hash-pins the bodies of `_is_assigned_mission_number` (`ordering.py:1318`), `_mark_mission_number_baked` (`:1320`), and `_already_baked` (`:1315`). If the fix changes the BODY of any of those three, re-pin via `scripts/... _refresh_dead_symbol_hashes.py` in the SAME commit (a body change without a re-pin reds the architectural battery). If the fix stays inside `_bake_mission_number_into_mission_branch` (NOT pinned), no re-pin is needed. Confirm which functions you actually touched before deciding.

## Branch Strategy

- **Planning base branch** and **merge target branch**: `issue-4764-terminus-safety-invariant`.
- Implement on the **single mission branch** directly — NOT lane worktrees. PR to `main` opens later; the operator merges.
- Commit the T011 red-first test as a distinct commit before the T012 implementation.

## ATDD / Test Strategy (red-first defect)

- **#4474** issue-pinned `@pytest.mark.regression` (T011): a merge-ready coord-topology bake test that is RED before the fix (number silently lost / `doctor` stuck at `pending`) and GREEN after.
- Run the full `tests/merge/` directory (owning subsystem) plus any `doctor` tests that read `mission_number`. Record commands + counts.

## Definition of Done

- [ ] **When the primary tree is reachable, the number is PERSISTED (doctor flips pending→assigned), not merely surfaced** (FOLD 4).
- [ ] A genuinely-unreachable case surfaces the unbaked field as a queryable event + merge-summary line — never a silent `return False`.
- [ ] The `path_is_under_worktrees` guard is preserved (no re-pollution of the mission-branch tree).
- [ ] The surfacing (fallback only) is observable by `doctor` and/or the merge summary, not a logger-only warning.
- [ ] T011 regression tests (both cases) green; full `tests/merge/` green.
- [ ] If the fix changed the body of `_is_assigned_mission_number`/`_mark_mission_number_baked`/`_already_baked`, the dead-symbol hashes were re-pinned in the same commit (FOLD 4 / paula).
- [ ] `ruff` + `ruff format --check` + `mypy` clean; C901 ≤ 15; no new escaping error type.
- [ ] `[Unreleased]` CHANGELOG note (impact-first, no version — C-005).

## Risks

- **Re-polluting the mission-branch tree** by resolving the write into `.worktrees/`. Mitigation: keep `path_is_under_worktrees`; target the PRIMARY tree.
- **Conflating with FR-006** (WP02) — accidentally changing the not-merge-ready bake behavior. Mitigation: scope strictly to the merge-ready fail-open.
- **Non-observable surfacing** — a logger warning that `doctor` cannot see. Mitigation: emit a queryable event / merge-summary line.
- **Cheap surface-only escape (FOLD 4)** — surfacing when the primary tree was actually reachable, avoiding the harder persist. Mitigation: the reachable-primary test case demands a persisted number.
- **Silent architectural-battery red (FOLD 4)** — a body change to a hash-pinned dead symbol without a re-pin. Mitigation: re-pin in the same commit if `_is_assigned_mission_number`/`_mark_mission_number_baked`/`_already_baked` bodies changed.

## Reviewer Guidance (reviewer-renata)

- Confirm the fix addresses the MERGE-READY fail-open (FR-011), distinct from FR-006's not-merge-ready prevention.
- Confirm the reachable-primary case PERSISTS the number (doctor pending→assigned), not merely surfaces it (FOLD 4); surfacing is the genuinely-unreachable fallback only.
- Confirm no silent `return False` remains on the merge-ready path.
- Confirm the `.worktrees/` guard is intact and the write reaches the primary tree.
- Confirm any dead-symbol body change was re-pinned in the same commit (FOLD 4 / paula).
- Confirm the #4474 test is genuinely red-first through the real bake entry point.
