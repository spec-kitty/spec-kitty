---
work_package_id: WP04
title: Release gates on green nightly
dependencies:
- WP03
requirement_refs:
- C-005
- FR-008
planning_base_branch: feat/ci-coverage-honesty
merge_target_branch: feat/ci-coverage-honesty
branch_strategy: Planning artifacts for this mission were generated on feat/ci-coverage-honesty. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/ci-coverage-honesty unless the human explicitly redirects the landing branch.
subtasks:
- T018
- T019
- T020
phase: Phase 4 - Release gate
history:
- at: '2026-09-25T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/release_nightly_gate.py
- tests/ci/test_release_nightly_gate.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/release.yml
- scripts/ci/release_nightly_gate.py
- tests/ci/test_release_nightly_gate.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
Use `/ad-hoc-profile-load` to load `python-pedro` (implementer, claude) before anything else.

---

## Objectives & Success Criteria
Make a green nightly a release precondition. Read `contracts/ci-workflow-contract.md` (release section), `research.md` (D7).

**Success**: `pytest tests/ci/test_release_nightly_gate.py` green; `release.yml` blocks build/publish unless a nightly for the exact release SHA is green.

## Subtasks

### T018 — release gate helper (`scripts/ci/release_nightly_gate.py`, FR-008)
CLI `--tag <release_tag> [--dispatch] [--timeout <s>]`:
- Resolve tag → `release_sha`. Query `ci-nightly.yml` runs where `head_sha == release_sha`.
- `success` run exists → exit 0.
- Else with `--dispatch`: `workflow_dispatch` `ci-nightly.yml` **by the tag ref** (`ref=<tag>` — dispatch CANNOT take a bare SHA; the tag points at the SHA so the run's head_sha matches), input `mode=full`; poll to terminal; exit 0 only on `success`.
- In-flight nightly for the SHA → wait for terminal result, don't race.
- Token absent → **fail closed** (releases run in-repo with a token; never silent pass), never echo the token (C-005).

### T019 — release.yml wiring
Add a `nightly-gate` job that runs the helper with `RELEASE_NIGHTLY_DISPATCH_TOKEN` (PAT/GitHub App — the default `GITHUB_TOKEN` won't trigger a nested run) and `permissions: actions: write`. `build-release` gains `needs: [nightly-gate]` (publish-pypi transitively). Fail closed on any non-success.

### T020 — unit tests (`tests/ci/test_release_nightly_gate.py`)
Mock GitHub client: green-exists→pass; none→dispatch(by tag)→green→pass; none→dispatch→red→fail; in-flight→wait→decide; token-absent→fail-closed.

## Branch Strategy
Planning base `feat/ci-coverage-honesty` → main via squashed PR. Lane worktree per `lanes.json`. Depends on WP03.

## Definition of Done
- Gate blocks publish without a green nightly for the release SHA; dispatch by tag; fail-closed token handling; tests green; ruff/mypy clean; workflow valid.
- **PR body must call out the operator prerequisite**: create secret `RELEASE_NIGHTLY_DISPATCH_TOKEN`.

## Reviewer guidance
Verify: dispatch by tag not SHA; needs-edge blocks publish; token-absent fails closed (not silent pass); no token leak; operator-secret prerequisite documented.
