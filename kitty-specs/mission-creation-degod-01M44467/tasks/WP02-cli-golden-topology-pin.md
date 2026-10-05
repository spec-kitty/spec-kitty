---
work_package_id: WP02
title: CLI golden cells and topology fallback pin
dependencies: []
requirement_refs:
- FR-002
- FR-010
- NFR-001
- NFR-002
- C-008
planning_base_branch: issue-5634-mission-creation-degod
merge_target_branch: issue-5634-mission-creation-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5634-mission-creation-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5634-mission-creation-degod unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-creation-degod-01M44467
base_commit: 861c8b74dd9c159c4feaf31f2c70e825e8562f32
created_at: '2026-10-04T20:24:13.828989+00:00'
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 1 - Behaviour freeze
history:
- at: '2026-10-04T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py
- tests/specify_cli/cli/commands/agent/golden/mission_create_cli.json
- tests/specify_cli/cli/commands/agent/test_mission_create_topology_fallback.py
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py
- tests/specify_cli/cli/commands/agent/golden/**
- tests/specify_cli/cli/commands/agent/test_mission_create_topology_fallback.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – CLI golden cells and topology fallback pin

## ⚡ Do This First: Load Agent Profile

Load the profile canonically before reading further: run `spec-kitty agent profile show python-pedro` (skill `spk-doctrine-profile-load` / `/ad-hoc-profile-load`), then `spec-kitty charter context --action implement --json`.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

If this WP was returned from review, the event log (`spec-kitty agent tasks status --mission mission-creation-degod-01M44467`) and the Activity Log carry the feedback. Address every item.

---

## Objectives & Success Criteria

Pin the **command surface** of `spec-kitty agent mission create` and its **derived default topology** with real repositories and **zero patches** (spec FR-002, FR-010):

- CLI golden cells capture, normalised the same way as WP01: the JSON envelope (sorted keys), `error_code` and exit code for each case.
- Derived default topology cells:
  - on the Primary Branch with `origin/HEAD` → `coord`;
  - on a non-primary branch → `lanes`;
  - `--pr-bound` on an unprotected Primary Branch, from a topic branch → `lanes`;
  - `--pr-bound` on the Primary Branch → `coord`;
  - **no `origin/HEAD`** on a non-common branch → `coord` (the CLAUDE.md "Create-time topology" caveat; follow-up: #5707);
  - `--owned-checkout` with no `--topology` → `single_branch`.
- One success smoke and one refusal smoke per behaviour family (spec "Behaviour families" 1–6).
- A decision-level pin (`test_mission_create_topology_fallback.py`) that calls the **existing** `_resolve_default_topology_phase` and `coord_topology_reachable`, not a copy, on real repositories. It names both Primary Branch inputs: `resolve_primary_branch(repo, bias=True)` for the topology default and `bias=False` for the protection check. This documents the divergence #5707 tracks.
- All new tests are green on the unchanged base and red on a planted break of each pinned dimension, recorded in the Activity Log.
- After approval these files are **frozen** (NFR-001): later WPs may not edit them.

## Context & Constraints

- Spec: FR-002, FR-010, C-007 (CLI topology code is **not** edited), "Behaviour families".
- Code under test (read-only for this WP):
  - `src/specify_cli/cli/commands/agent/mission_create.py::_resolve_default_topology_phase` (~line 372) and `_emit_create_core_error_and_exit` (~line 470).
  - `src/specify_cli/coordination/surface_authority.py::coord_topology_reachable` (~line 162).
  - `src/specify_cli/core/git_ops.py::resolve_primary_branch`.
- Helpers to reuse: `tests/_factories/coord_mission.py` has `_invoke_mission_create_cli(repo, args)` (~line 351), `_cli_create_args(slug, topology, *extra)` (~line 364), `_set_up_bare_remote(repo)`, `_init_repo_with_target`, `_write_protected_branches`.
  - Read `_invoke_mission_create_cli` first. If it patches `locate_project_root` or `is_worktree_context`, do **not** use it; write a local invoker that does `monkeypatch.chdir(repo)` and calls `CliRunner().invoke(app, ["create", ...])`, where `app` is `specify_cli.cli.commands.agent.mission.app`.
  - `chdir` is a working-directory change, not a module patch, and is allowed.
  - The process may run inside a lane worktree. If the CLI refuses because of the worktree context with no flag to bypass it, record that in the Activity Log and use the narrowest real workaround (for example running the invoker from a subprocess with `cwd=repo`: `subprocess.run([sys.executable, "-m", "specify_cli", "agent", "mission", "create", ...], cwd=repo)`). Never patch.
- The existing `tests/specify_cli/cli/commands/agent/test_mission_create_default_topology_matrix.py` patches `resolve_primary_branch`. Leave it alone (WP08/WP09 own patch migration). Your file adds the **real-repo** pins it lacks.
- Normalisation: reuse the whitelist from WP01 by copying the same four regex rules into a tiny local helper. Do **not** import from WP01's module: the lanes run in parallel and WP01's file may not exist yet in your lane. Record "duplicated by design for lane independence" in a comment.

## Branch Strategy

- **Strategy**: populated by finalize-tasks · **Planning base**: `issue-5634-mission-creation-degod` · **Merge target**: `issue-5634-mission-creation-degod`

## Subtasks & Detailed Guidance

### Subtask T006 – CLI golden harness

- **Steps**:
  1. A local invoker that returns `(exit_code, parsed_json_or_None, stdout_tail)`. Always pass `--json`, `--branch-strategy already-confirmed` and a unique slug.
  2. Snapshot file `tests/specify_cli/cli/commands/agent/golden/mission_create_cli.json`, with the same `{"base_commit", "cells"}` shape and `SPEC_KITTY_REGEN_GOLDEN=1` regeneration as WP01. Regeneration refuses to run under xdist.
  3. Capture: exit code, the JSON envelope with whitelisted normalisation (ULID, mid8, timestamps, tmp paths), `topology`, `error_code` and the repository-root `HEAD` after the call.

### Subtask T007 – Derived default-topology cells

- **Steps**: build each repository state for real:
  - Primary with `origin/HEAD`: `_init_repo_with_target(target_branch="main")` + `_set_up_bare_remote`.
  - Non-primary: `target_branch="feat-x"`.
  - `--pr-bound` unprotected / protected: `_write_protected_branches(repo, ("main",))` for the protected variant.
  - No `origin/HEAD`: `git remote remove origin` (or `git remote set-head origin -d`) while standing on a non-common branch such as `feat-x` with `main` present. The expected **observed** default is whatever today's code yields; the caveat says `coord`. Capture it and do not assert your expectation over the code.
  - `--owned-checkout <path>` with no `--topology`: a real `git worktree add` sibling.

### Subtask T008 – Per-family smoke cells

- One success and one refusal CLI cell per behaviour family:
  1. flat: `--topology lanes` on a topic branch; refusal: invalid slug.
  2. protected single_branch: `--topology single_branch` on protected `main`; refusal: dirty checkout under the mint (`stray.txt`).
  3. coordination: `--topology coord` on `main`; refusal: a duplicate create (same slug twice, **committing the first mission's `spec.md` in between**: a genesis-only prior is abandoned and does not refuse).
  4. owned: `--owned-checkout`; refusal: an owned path that is not a worktree of this repo (whatever the CLI refuses with today).
  5. refusals and rollback: `--commit-to-target` with `--topology lanes`.
  6. derived default: covered by T007.

### Subtask T009 – Decision-level topology fallback pin

- **Purpose**: FR-010. #5707 will later change this deliberately, and it needs a pin that names both inputs.
- **Steps**: in `test_mission_create_topology_fallback.py`:
  1. On a real no-`origin/HEAD` repository standing on `feat-x` with `main` present, assert `resolve_primary_branch(repo)` (default bias=True) and `resolve_primary_branch(repo, bias=False)`, and record both values in the test via named variables `primary_for_topology_default` and `primary_for_protection`.
  2. Call `_resolve_default_topology_phase(explicit_topology=None, repo_root=repo, current_branch="feat-x", pr_bound=False)` and assert the result that the code returns today.
  3. Call `coord_topology_reachable` for the pr-bound arm on the same inputs.
  4. Add a parametrised truth table for `coord_topology_reachable(pr_bound, primary_protected, current_is_primary)` (8 rows). It is pure, so no repository is needed.
  5. Planted break: temporarily flip `bias` in `_resolve_default_topology_phase` (`resolve_primary_branch(repo_root, bias=False)`) and confirm a cell goes red. Revert and record it.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py tests/specify_cli/cli/commands/agent/test_mission_create_topology_fallback.py -n 4 --dist loadfile -q --durations=10
SPEC_KITTY_REGEN_GOLDEN=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py -n0 -q && git diff --exit-code tests/specify_cli/cli/commands/agent/golden/
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_mission_create.py tests/specify_cli/cli/commands/agent/test_mission_create_default_topology_matrix.py -q
uv run --frozen ruff check <new files> && uv run --frozen ruff format --check --force-exclude <new files>
.venv/bin/mypy <new files>
make test-fast
```

## Risks & Mitigations

- **CLI worktree guard when run from a lane worktree**: prefer `chdir` into the temporary repository; fall back to a subprocess; never patch.
- **Non-deterministic envelope fields**: normalise only via the whitelist. If a field is still non-deterministic, report it in the Activity Log and capture a stable projection of it (for example presence plus type). Do not widen the normaliser.
- **Runtime**: keep it to about 12 CLI cells; NFR-002 budgets 45 s for WP01 + WP02 together.

## Review Guidance

- No `monkeypatch.setattr`, `mock.patch` or `patch.object` in the new files; `monkeypatch.chdir` is allowed.
- The fallback pin calls the real functions (grep the imports).
- Re-run one planted break.
- Snapshot regeneration on the lane base is reproducible.

## Post-tasks squad folds (binding; they supersede conflicting text above)

1. The envelope's `spec_kitty_version` changes on every release, so project **that field only** to `{"present": true, "type": "str"}`. Any other field you find non-deterministic needs orchestrator sign-off before it gets a projection; report it and stop. Projections are part of the frozen whitelist.
2. Same mid8 and ULID numbering as WP01 fold 2 (`<MID8#n>`).
3. Record planted breaks as `git diff` patch blocks in the Activity Log.
4. Do not import `tests/_factories/coord_mission.py` in the frozen golden file, because WP08 edits it. Vendor the few builder lines you need. `clone_template` and `provision_test_charter` are allowed (they are in the freeze set).

## Activity Log

- 2026-10-04T20:00:00Z – system – Prompt created
