---
work_package_id: WP01
title: Red acceptance on the fork shapes
dependencies: []
requirement_refs:
- FR-005
- SC-001
- SC-002
- SC-003
planning_base_branch: fix/7560-dependency-ref-spine-base
merge_target_branch: fix/7560-dependency-ref-spine-base
branch_strategy: Planning artifacts for this mission were generated on fix/7560-dependency-ref-spine-base. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7560-dependency-ref-spine-base unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-base-window-bound-01M78XB4
base_commit: 30ebc1c7218043fed63257cc29cd136721179d50
created_at: '2026-11-12T22:29:01.675585+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Reproduction
history:
- at: '2026-11-12T22:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/consolidation/
create_intent:
- tests/consolidation/test_dependency_ref_mission_base_7560.py
execution_mode: code_change
owned_files:
- tests/consolidation/test_dependency_ref_mission_base_7560.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Red acceptance on the fork shapes

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status` for a `review_ref`. Address every feedback item, and record progress with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

Reproduce #7560 **red-first through the pre-existing entry point** (`spec-kitty consolidate`), the Charter Standing Order 4 / `test-first-bug-fixing` discipline:

- The two reported shapes refuse today. These tests are `pytest.mark.xfail(strict=True, reason="#7560 ...")` and must fail as xfails on this branch now. WP04 removes the marks.
- Soundness ratchets on the same fork fixture are **green now** and must stay green: genuine post-base Mission work keeps refusing.
- A non-fork control is green now and stays green, with the verdict unchanged.

Done when `pytest tests/consolidation/test_dependency_ref_mission_base_7560.py` reports only `xfailed` + `passed`, with no `XPASS` and no failures.

## Context & Constraints

- Root cause: [research/code-grounding.md](../research/code-grounding.md). Every reconciliation window is `window_base..ref`, where `window_base` is the target's pre-run tip. On a fork that tip need not reach the commit the Mission branch was cut from, so pre-Mission history reads as Mission work.
- Reproduced at unit level by the scratch repro (report 2: the refusal names `base^`, the upstream pin).
- Read `tests/consolidation/test_dependency_ref_forecast.py` (it uses the terminus harness `build_coord_mission`, `restamp_approvals_at_lane_tips`, `run_terminus`) and `tests/terminus/conftest.py` (`_init_fixture_repo`, `_cut_coord_branch`, `_cut_lane_branch`, `_commit_status_events`, `_finish_coord_mission`, `_stamped_approve_events`).
- Do **not** edit `tests/terminus/conftest.py`. Build the fork shape inside the new test module from the harness's private helpers (import them, as other tests do), or post-process a built mission.
- `pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`.

## Branch Strategy

- **Planning base branch**: `fix/7560-dependency-ref-spine-base`
- **Merge target branch**: `fix/7560-dependency-ref-spine-base`
- Execution worktrees are allocated per computed lane from `lanes.json`; run `spec-kitty agent action implement WP01 --agent claude --mission mission-base-window-bound-01M78XB4`.

## Subtasks & Detailed Guidance

### Subtask T001 – Fork-shape fixture builder (report 2)

- **Purpose**: a real coord-topology Mission whose base the target lacks, with no upstream merge inside a lane.
- **Shape** (mirror report 2: base = upstream pin + one overlay commit; the target never received either):
  1. `_init_fixture_repo(...)` gives `main` with one `init` commit (call it `R`).
  2. Make an "upstream" line from `R`: 3–5 commits that add *and later delete* some files (for example add `up/a.py`, `up/b.py`, then delete `up/b.py`), so a pre-base deletion exists. Tag the tip `PIN` (keep a branch `upstream` pointing at it).
  3. Put `main` at `PIN`, then commit one overlay commit (for example `overlay/cfg.txt`). This commit is the Mission base `B`.
  4. Build the rest exactly like `build_coord_mission`: planning artifacts committed (the scaffold commit that adds `kitty-specs/<slug>/`, whose first parent is `B`), coord branch cut, one lane per WP with real code, stamped approvals, status committed on `main`, coord fast-forwarded, `_finish_coord_mission`.
  5. Finally rewind the **target** so it lacks `B`: `main` back to `R` (`git checkout -q main && git reset -q --hard R` in the repo root; the coordination worktree holds the coord branch, so it is unaffected). Assert `git merge-base --is-ancestor B main` fails.
- Return the `CoordMission` plus `R`, `PIN`, `B`, and the pre-base deleted path.
- **Notes**: if a consolidate preflight refuses for an unrelated reason (for example because the status log is no longer on `main`), adjust the fixture, never the product. A common fix is to leave a commit on `main` above `R` that carries the status log, without carrying `B`'s history. Record what you had to do in the docstring.

### Subtask T002 – Report-1 shape

- Same builder, plus: after the lanes exist, make `upstream` advance by 1–2 commits (`U`), merge `U` into WP02's lane with `git merge --no-ff`, and restamp approvals at lane tips (`restamp_approvals_at_lane_tips`), exactly as `_plant_dependency_branch` does. `U`'s history includes pre-base upstream commits that `main` lacks.

### Subtask T003 – Strict-xfail acceptance (both shapes)

All tests run with `--strategy merge` unless noted, through `run_terminus(mission, ["consolidate", "--mission", slug, ...])`.

1. Report 2, declared: `--dry-run --dependency-ref <PIN sha>`. **Today**: exit≠0, `DEPENDENCY_REF_COVERS_MISSION_WORK` naming a pre-base commit. **Expected**: exit 0, and no `would FAIL` / `would REFUSE`. Mark xfail-strict.
2. Report 2, plain: `--dry-run`. **Today**: un-attributable content naming pre-base commits. **Expected**: exit 0. xfail-strict.
3. Report 2, real run (`--yes --strategy merge`). **Expected**: exit 0, and the gate passes (the existing helper `reached_reconciliation_verdict` / output checks). xfail-strict.
4. Report 1, declared: `--dry-run --dependency-ref upstream` then the real run. **Expected**: exit 0. xfail-strict.
5. Report 2 under the default **squash** strategy (no `--strategy`): `--dry-run` passes. **Today** the squash axis flags the pre-base deletion and blobs. xfail-strict.

Assert on stable tokens (`Error code: ...`, `un-attributable`) normalised with `" ".join(stdout.split())`, never on wrapped prose.

### Subtask T004 – Soundness ratchets (green now, green after)

On the report-2 fixture:

1. A **post-base direct commit** on the coordination/Mission branch carrying content (not bookkeeping), plus a non-namespace branch `side` pointing at it, declared `--dependency-ref side`: refuses `DEPENDENCY_REF_COVERS_MISSION_WORK`.
2. A **removed WP's commit smuggled** into a lane through a second-parent merge, made after the base and undeclared: the plain `--dry-run` refuses with un-attributable content naming that commit. It must name *that* commit; pre-base commits may also be listed today. Assert only on the smuggled commit's sha.
3. Declaring a lane branch: refuses (namespace / spine code).

These pass today. Keep them unmarked.

### Subtask T005 – Non-fork control

`build_coord_mission` unchanged (target reaches base) plus `_plant_dependency_branch`-style lane merge: `--dry-run --dependency-ref dep-branch` exits 0 and the undeclared run refuses, the same as `test_dependency_ref_forecast.py`. One test is enough. It guards NFR-001.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/consolidation/test_dependency_ref_mission_base_7560.py -q -rxX
uv run --frozen ruff check tests/consolidation/test_dependency_ref_mission_base_7560.py
uv run --frozen ruff format --check --force-exclude tests/consolidation/test_dependency_ref_mission_base_7560.py
uv run --frozen mypy tests/consolidation/test_dependency_ref_mission_base_7560.py
```

## Risks & Mitigations

- **A vacuous xfail** (the test fails for a fixture error, not the bug): each xfail test must first assert its fixture invariants (`B` not an ancestor of `main`; `PIN == B^`) *outside* the xfail-sensitive assertion. Put those asserts in the fixture itself, so a broken fixture errors instead of xfailing. Also assert that today's failure output contains the bug's own token (`DEPENDENCY_REF_COVERS_MISSION_WORK` or `un-attributable`). Do this in a separate always-run helper test, so the xfail is proven to be the bug.
- **Runtime**: each real-run test costs seconds; keep it to the scenarios listed.

## Review Guidance

- Verify the xfails are caused by #7560 (the helper test that asserts today's token).
- Verify the ratchets are meaningful: each must refuse for the post-base commit, not only for pre-base noise.
- No product code changed in this WP.
