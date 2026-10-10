---
work_package_id: WP04
title: Mission-status oracle remote-arm parity (#5990)
dependencies: []
requirement_refs:
- FR-006
planning_base_branch: fix/nightly-suites-green-rework
merge_target_branch: fix/nightly-suites-green-rework
branch_strategy: Planning artifacts for this mission were generated on fix/nightly-suites-green-rework. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/nightly-suites-green-rework unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-suites-green-rework-01M4J5EN
base_commit: 437e22e3954504fd401a18aebc8830c48243e929
created_at: '2026-10-10T06:30:32.898902+00:00'
subtasks:
- T012
- T013
- T014
phase: Phase 2 - Test oracle parity
history:
- at: '2026-10-10T05:45:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/contract/_mission_status_oracles.py
- tests/contract/test_mission_status_reality.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Mission-status oracle remote-arm parity (#5990)

## ⚡ Do This First: Load Agent Profile
Use `/spk-charter-profile-load` to load `python-pedro` (implementer, claude).

## Objectives & Success Criteria

`test_corpus_fallback_list_equals_the_independent_derivation` and `test_corpus_project_report_equals_the_oracles` (nightly `interpreter-3.13-shard-4`, #5990) fail only when online: the production resolver `_coord_branch_exists` (`src/specify_cli/coordination/surface_resolver.py:691`) has three arms, including a **live `git ls-remote` arm** `_coord_branch_exists_via_remote` (:675), fail-closed-to-present (the #2614 data-loss guard). The independent test **oracle** `derive_fallbacks` (`tests/contract/_mission_status_oracles.py:193`) mirrors only local heads + `refs/remotes/` (arm 2, via `derived_but_remote_present:210`), NOT the live arm. On the online nightly, three coordination branches were still live on origin → resolver says *present*, oracle says *deleted-fallback* → "only the oracle has [3]".

Done when: the oracle mirrors the resolver's live-remote authority so scan and oracle agree when remotes are online; both corpus tests pass (FR-006).

## Context & Constraints
- **C-002**: the resolver is correct and deliberate — fix the ORACLE's blind spot; keep the independent derivation genuinely independent (re-derive via the same live-remote primitive, don't just call the resolver).
- Do NOT prune remotes to dodge the test.

## Subtasks
- **T012** — Red-first: understand the divergence (local reproduction is green because the fork has no live refs for those coord branches; reproduce the asymmetry by simulating a remote-live-but-local-absent coord branch, or by unit-testing the oracle against a stubbed `ls-remote` HIT).
- **T013** — In `drift_oracle` / `derived_but_remote_present`, for each derived fallback also consult the resolver's live-remote primitive (`remote_branch_lookup` / `git ls-remote <remote> <coord_branch>`), treating HIT and unreachable-ERROR as present (matching the resolver's fail-closed rule), and subtract those missions from the expected `fallbacks` set.
- **T014** — Verify both corpus tests green (online path); keep the oracle's local-only derivation for the offline case intact.

**Adversarial findings (F6/F7) — must hold:**
- **F6 (independence)**: the oracle must RE-DERIVE remote presence from the live primitive itself (its own `git ls-remote` / `remote_branch_lookup` call), NOT by calling the resolver — otherwise the contract test degenerates into "both sides compute the same thing" and can no longer catch a resolver regression. At least one arm must still be able to diverge if the resolver's classification regressed.
- **F7 (red-first pins the asymmetry)**: the nightly condition (3 named coord branches live on origin, absent locally) is not reproducible in the fork; T012's stubbed-`ls-remote`-HIT repro must encode the ASYMMETRY (remote-live + local-absent → resolver=present, un-hardened oracle=fallback), not merely pass locally.

## Branch Strategy
Planning base / merge target: `fix/nightly-suites-green-rework`. Lane from `lanes.json`.

## Validation
```bash
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -q \
  "tests/contract/test_mission_status_reality.py::test_corpus_fallback_list_equals_the_independent_derivation" \
  "tests/contract/test_mission_status_reality.py::test_corpus_project_report_equals_the_oracles"
```
(Setup is slow ~200s — single targeted run.)

## Definition of Done
Both corpus tests green; oracle mirrors all three resolver arms when online; still independent; `ruff` clean.

## Reviewer Guidance (opus)
Confirm the oracle now re-derives remote presence via the live primitive (not by delegating to the resolver), matching the documented three-arm fail-closed rule; confirm no remote pruning or expected-set weakening.
