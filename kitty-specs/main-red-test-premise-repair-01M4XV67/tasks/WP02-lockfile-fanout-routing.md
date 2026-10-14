---
work_package_id: WP02
title: Lock-file reducer bump selects upgrade and status shards
dependencies: []
requirement_refs:
- FR-004
- NFR-002
- C-003
- SC-004
planning_base_branch: issue-6240-main-red-test-premise-repair
merge_target_branch: issue-6240-main-red-test-premise-repair
branch_strategy: Planning artifacts for this mission were generated on issue-6240-main-red-test-premise-repair. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6240-main-red-test-premise-repair unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - Close the routing gap
history:
- at: '2026-10-14T18:41:26Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- .github/workflows/ci-router.yml
- scripts/ci/gate_selection.py
- tests/architectural/test_workflow_coherence.py
- tests/architectural/test_gate_selection_authority.py
- tests/ci/test_fanout_derivation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Lock-file reducer bump selects upgrade and status shards

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter, and behave according to its guidance before reading the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission main-red-test-premise-repair-01M4XV67`). Address every item before you finish.

## Objectives & Success Criteria

- A changed-path set of only `uv.lock` selects the `upgrade` and `status` module shards. A set of only `pyproject.toml` gets no `upgrade` from this new group. Covers FR-004, NFR-002, C-003, SC-004.
- Operator ruling (decision 01M4XV6HM7WHEB2B8QG67N29HT): `pyproject.toml` must NOT be in the new group, so a rename or non-version edit to the manifest never triggers the upgrade shards.

## Context & Constraints

- Gap: the spec-kitty-events 10.4.6 bump (#6205) touched `uv.lock` and `pyproject.toml`. Neither selects the `upgrade` module shards. `mission_state` lists them but gates only the audit job (`ci-router.yml` about :310-345). `upgrade` is selected only by `src/specify_cli/upgrade/**`.
- **Shape precedent (router YAML only; its fan-out map does NOT fit, see T007):** commit 5908cbbec2 (`git show 5908cbbec2`) added the non-src fan-out group `mission_type_definitions` in lockstep across the ci-router filter and `outputs:` (line ~140 and ~251), `GROUP_MODULE_FANOUT` (`scripts/ci/gate_selection.py:80-91`) and `_DELIBERATELY_UNGATED_FILTER_GROUPS` (`tests/architectural/test_workflow_coherence.py` ~:333-346). Also check `tests/architectural/test_gate_selection_authority.py` (~:288 pins a group's module set; every fan-out target must be a registry module), `tests/ci/test_fanout_derivation.py` (`FANOUT_ALLOWLIST` and census checks; a census-derived module missing from both the hand set and the allowlist reds), and `tests/architectural/test_consumer_census_routing.py`. `scripts/ci/consumer_census.py` (~:231) maps census paths to groups; check whether a lock-file group needs an entry there or is exempt.
- Group name suggestion: `reducer_lock`. Its path list is exactly `'uv.lock'`. It must stay non-src (never a `src/**` glob, so it can never mask an unmapped src change). Add a short comment above it in ci-router citing #6238 and the operator ruling.
- Use `.venv/bin/python -m pytest -n0`, targeted files only. Watch for `uv.lock` artifactory rewrites (`git checkout uv.lock` before staging). Do not edit `uv.lock` itself.

## Branch Strategy

- **Strategy**: single_branch. Runs in the write checkout on `issue-6240-main-red-test-premise-repair` after WP01.
- **Planning base branch**: issue-6240-main-red-test-premise-repair
- **Merge target branch**: issue-6240-main-red-test-premise-repair (the PR targets `main`)
- Implement command: `spec-kitty agent action implement WP02 --agent claude --mission main-red-test-premise-repair-01M4XV67`

## Subtasks

### T006 – ci-router group + output
Add the filter group with `- 'uv.lock'` and the matching `outputs:` line in the same shape as `mission_type_definitions` (full-mode/unmatched OR). Keep YAML literal (GitHub Actions needs literal YAML; the transcription guard pins it).

### T007 – Separate dependency fan-out map (post-tasks review, HIGH)
Do NOT add the group to `GROUP_MODULE_FANOUT`. That map feeds `FANOUT_GROUPS`, which the pack consumer census validates. `uv.lock` is not a pack path, so the census derives nothing for it. `tests/ci/test_fanout_derivation.py::test_derivation_is_non_vacuous` (:62-66) would fail, and so would `test_hand_fanout_routed_members_are_all_re_derived` (:76-100), because `status` is derived in no group. Instead:
- add `DEPENDENCY_MODULE_FANOUT: dict[str, frozenset[str]] = {"reducer_lock": frozenset({"upgrade", "status"})}` next to it in `scripts/ci/gate_selection.py`. Comment it: non-census by design (a lock file is not a pack path); #6238; operator ruling (decision 01M4XV6HM7WHEB2B8QG67N29HT, `pyproject.toml` excluded);
- union it in `select_modules` (around :440) the same way the pack fan-out is unioned. Keep it out of `FANOUT_GROUPS`, so the census, census-routing and census-cost machinery stays pack-scoped;
- confirm `upgrade` and `status` are registry modules (`.github/ci-module-registry.yml` :83, :127).

### T008 – Lockstep pins
- `tests/architectural/test_gate_selection_authority.py`: an explicit assertion `DEPENDENCY_MODULE_FANOUT["reducer_lock"] == frozenset({"upgrade", "status"})`, plus an "every target is a registry module" loop over the new map.
- `tests/architectural/test_workflow_coherence.py`: register `reducer_lock` wherever the coherence and transcription guards enumerate non-src or deliberately-ungated filter groups (follow what the guards demand when run; precedent 5908cbbec2 shows the shape).
- Run `tests/ci/test_fanout_derivation.py` and `tests/architectural/test_consumer_census_routing.py` to prove they stay green untouched.

### T009 – Focused selection test, with a mutation proof
Create `tests/ci/test_reducer_lock_routing.py`, modelled on `tests/ci/test_mission_state_audit_routing.py`, asserting:
- a lock-only change (`uv.lock`) selects `upgrade` and `status`, and does not select ALL modules (guard against a vacuous pass through an unmatched-src or run-all path; assert a specific module like `charter` is NOT selected);
- a manifest-only change (`pyproject.toml`) does not select `upgrade`;
- the ci-router `reducer_lock` filter list is exactly `['uv.lock']` (parse the YAML), so `pyproject.toml` can never be added silently.
Mutation proof (required; record it in the WP history): temporarily remove `uv.lock` from the group (or the map entry), run the new test, see it fail, then restore.

Verification:
```bash
.venv/bin/python -m pytest -n0 -q tests/ci/ tests/architectural/test_workflow_coherence.py tests/architectural/test_gate_selection_authority.py tests/architectural/test_consumer_census_routing.py
ruff check scripts/ci/gate_selection.py <tests> && uv run --no-sync ruff format --check --force-exclude <changed .py files>
```

## Definition of Done

- T006–T009 marked done. A single commit `ci(router): route uv.lock changes to the upgrade and status shards (#6238)` with this session's trailers. The WP is moved to for_review with test counts in the history.

## Reviewer Guidance

- Re-run the mutation proof. `pyproject.toml` is absent from the new group. The group is non-src. Every lockstep site is updated. There's a red-on-mutation feel: removing `uv.lock` from the group should red the new test.
