---
work_package_id: WP01
title: Create claim refuses a Mission worktree
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- SC-001
- SC-002
- C-001
- C-002
- C-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Create-seam refusal
history:
- at: '2026-11-03T13:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/
create_intent:
- tests/specify_cli/cli/commands/agent/test_mission_create_owned_worktree_refusal.py
execution_mode: code_change
owned_files:
- src/specify_cli/core/owned_mission.py
- tests/core/test_owned_mission_minter.py
- tests/specify_cli/cli/commands/agent/test_mission_create_owned_worktree_refusal.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6956'
---

# Work Package Prompt: WP01 – Create claim refuses a Mission worktree

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) and behave according
to its guidance before parsing the rest of this prompt.

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting; if
this WP was returned from review, resolve every feedback item first and record each with
`spec-kitty agent tasks add-history WP01 --note "..."`.

## Objectives & Success Criteria

- `resolve_owned_create_root` refuses a **registered coordination worktree** and a **registered lane
  worktree** with the leaf's existing `OWNED_CHECKOUT_IS_MISSION_WORKTREE` code, before
  `OwnedCreateRoot` is minted.
- `agent mission create <slug> --owned-checkout <coord-worktree|lane-worktree> --json` exits 1 with
  that code and leaves the claimed checkout's HEAD, index and worktree untouched; no
  `kitty-specs/<slug>` is created anywhere.
- A **legitimate** linked owned checkout still creates, including one that merely lives under
  `.worktrees/` but whose directory name is not a lane-worktree name (same-fixture positive
  control).
- At most **one** worktree-registry read per minted claim, shared by both legs (NFR-001); an
  unreadable registry refuses with `WorktreeRegistryUnavailable.error_code` (NFR-002).
- `resolve_owned_mission`, `adopt_owned_checkout` and the leaf's `lanes.json` lane check are
  unchanged; `tests/architectural/test_owned_checkout_single_authority.py` stays green with an
  empty allowlist.

## Context & Constraints

- Read first: `kitty-specs/owned-create-root-refuses-mission-worktree-01M6GRFM/spec.md`,
  `research.md` (decisions 1–4), `plan.md` (IC-01, IC-03).
- The defect: `src/specify_cli/core/owned_mission.py:485` — `resolve_owned_create_root` runs
  `_require_owned_claim` and returns; the Mission-worktree check
  `_require_not_mission_worktree` (`:224`) is called only from `resolve_owned_mission` (`:388`).
  `src/specify_cli/cli/commands/agent/mission_create.py:601` mints the root **before any git
  operation**, so an admitted claim is the claim the scaffold then uses.
- Charter rules that bind this WP: single canonical authority (plan C-001), ATDD-first,
  DIRECTIVE_034 (test-first bug fixing), DIRECTIVE_024 (locality of change).
- `NO_FULL_HEAVY_SUITES_IN_MISSION`: run targeted suites and the architectural gates, not the full
  matrix.
- Do **not** add a new refusal code, a new predicate owner, a new registry reader, or a
  registry-branch-based lane test. The two legs are exactly:
  - coordination → `_is_coordination_worktree` (registry-verified, `-coord`, needs no Mission);
  - lane → the same classification says `WorktreeTopology.LANE_WORKTREE` **and**
    `specify_cli.lanes.branch_naming.parse_lane_worktree_dir(<checkout dir name>)` is not `None`.
  Neither leg alone is sufficient; that is the carrier-contract trap the positive control pins.

## Branch Strategy

- **Strategy**: single_branch mission
- **Planning base branch**: `kitty/mission-owned-create-root-refuses-mission-worktree-01M6GRFM`
- **Merge target branch**: `main`

## Subtasks & Detailed Guidance

### T001 – Red-first coordination-worktree refusal through the CLI

- **Purpose**: pin the reported scenario through the real command before the fix exists.
- **Steps**: create
  `tests/specify_cli/cli/commands/agent/test_mission_create_owned_worktree_refusal.py`. Build a
  fixture in `tmp_path`:
  1. repository root `R` (git init, `.kittify` + `provision_test_charter(R)`, an empty
     `kitty-specs/`, one commit — model it on
     `tests/specify_cli/cli/commands/agent/test_mission_create_phases.py:348`);
  2. a coordination worktree registered on `R` at `R/.worktrees/<slug>-<mid8>-coord` via
     `git worktree add -qb <coord-branch> <path>` (the `-coord` suffix plus registration is what
     makes it coordination; `CoordinationWorkspace.worktree_path` names the real shape);
  3. `runner = CliRunner()`, `monkeypatch.chdir(R)`, invoke
     `["create", "<slug>", "--owned-checkout", str(coord_path), "--json"]` on
     `specify_cli.cli.commands.agent.mission.app`.
  Assert: exit code 1; the last JSON line's `error.code` is `OWNED_CHECKOUT_IS_MISSION_WORKTREE`;
  `R/kitty-specs/<slug>` does not exist; the coordination worktree's `git status --porcelain` is
  empty and its HEAD sha is unchanged.
  **Positive control on the same fixture**: a second create naming an ordinary linked owned
  checkout (`git worktree add -qb <topic> <P>`) succeeds (exit 0) and scaffolds
  `P/kitty-specs/<slug>`.
- **Files**: the new test module.
- **Notes**: mark the module `pytest.mark.integration` and `pytest.mark.git_repo` (real git
  subprocesses), matching the neighbouring mission-create tests. If the full create is too heavy,
  keep the positive control on the same fixture and assert the scaffold exists in `P` — do not
  weaken the refusal assertion itself.

### T002 – Red-first lane-worktree refusal, and the carrier-contract control

- **Purpose**: the second leg of the residual, without trading a false admission for a false
  refusal.
- **Steps**: same module:
  1. lane fixture: mission dir `R/kitty-specs/<slug>` with `meta.json` and a `lanes.json` writing one
     lane (`write_lanes_json`), then `predict_lane_worktree(R, SLUG, "lane-a")` → register that
     path with `git worktree add -qb <lane_branch> <path>`; create naming it must refuse with
     `OWNED_CHECKOUT_IS_MISSION_WORKTREE`;
  2. positive control: an owned checkout registered at `R/.worktrees/owned-under-worktrees`
     (registered, non-coord, **name does not parse as a lane-worktree name**) must be admitted by
     the create.
- **Files**: the new test module.
- **Notes**: the positive control is the point of the test: `WorktreeTopology.LANE_WORKTREE` alone
  classifies this checkout as a lane worktree, so a lane leg keyed on classification alone would
  refuse a legitimate checkout. Do not drop it to make the suite shorter.

### T003 – One shared classification read

- **Purpose**: keep the git-call budget honest before adding a second consumer of the registry.
- **Steps**: in `src/specify_cli/core/owned_mission.py` add a private helper (name it for what it
  returns, for example `_classify_registered_worktree(checkout, repository_root) -> WorktreeTopology`)
  that calls `classify_worktree_topology(checkout, repo_root=repository_root)` and translates
  `WorktreeRegistryUnavailable` into `ActionContextError(exc.error_code, str(exc))`. Re-point
  `_require_not_mission_worktree` at it (the coord leg becomes `topology is
  WorktreeTopology.COORD_WORKTREE`) — its observable behaviour and message must not change.
- **Files**: `src/specify_cli/core/owned_mission.py`.
- **Notes**: keep the import lazy inside the function (the module's lazy-import discipline). Do not
  change `_is_coordination_worktree`; adoption still calls it and still catches the registry
  exception to refuse adoption.

### T004 – The two legs on the create claim

- **Purpose**: refuse where the claim is minted, so the refusal lands before the scaffold decision.
- **Steps**: in `resolve_owned_create_root`, after `_require_owned_claim` and before minting, run a
  new private guard (for example `_require_not_create_mission_worktree(claim.claimed_checkout,
  repository_root)`) that:
  1. classifies once through T003's helper;
  2. raises `ActionContextError(OWNED_CHECKOUT_IS_MISSION_WORKTREE, <create-specific text>)` when
     the classification is `COORD_WORKTREE`;
  3. raises the same code when it is `LANE_WORKTREE` **and**
     `parse_lane_worktree_dir(claimed_checkout.name)` is not `None`.
  Add one module-level refusal-text constant for the create altitude (the leaf's
  `_MISSION_WORKTREE_REFUSAL` says "registered to this mission", which is not true at create);
  both messages name the remedy "pass a linked owned checkout instead".
- **Files**: `src/specify_cli/core/owned_mission.py`.
- **Notes**: no topology, branch or Mission-existence check joins this guard (C-003). A husk (the
  `-coord` name without registration) is **not** refused — the registry disposes.

### T005 – Minter unit pins

- **Purpose**: pin both legs and both controls at the seam, cheaply.
- **Steps**: extend `tests/core/test_owned_mission_minter.py` with create-root cases (a new
  section next to the existing "T008: resolve_owned_create_root" block):
  - registered coordination worktree → `OWNED_CHECKOUT_IS_MISSION_WORKTREE`;
  - registered lane worktree → same code;
  - `.worktrees/<name>` registered but not lane-shaped → accepted, returns `OwnedCreateRoot`;
  - `-coord` name **not** registered (husk) → accepted;
  - unreadable registry (monkeypatch the registry read to raise `WorktreeRegistryUnavailable`) →
    refused with that exception's `error_code`;
  - one registry read per mint: monkeypatch/instrument
    `specify_cli.coordination.surface_resolver.read_worktree_registry` with a counting wrapper and
    assert exactly one call for a refused coordination claim.
- **Files**: `tests/core/test_owned_mission_minter.py`.
- **Notes**: reuse the existing `_owned_pair` / `git` helpers and the `SLUG`/`MID`/`TARGET`
  constants. Every refusal case gets its positive control in the same fixture family (this is the
  spec's non-vacuity rule).

### T006 – Targeted verification

- **Purpose**: prove the leaf and the gates are untouched.
- **Steps**: run, from the repository root:
  - `uv run --frozen pytest tests/core/test_owned_mission_minter.py tests/specify_cli/cli/commands/agent/test_mission_create_owned_worktree_refusal.py tests/specify_cli/cli/commands/agent/test_mission_create_phases.py -q`
  - `uv run --frozen pytest tests/specify_cli/cli/commands/test_owned_checkout_helper.py tests/core/test_adopt_owned_checkout.py -q`
  - `uv run --frozen pytest tests/architectural/test_owned_checkout_single_authority.py tests/architectural/test_mission_runtime_surface.py -q`
  - `uv run --frozen ruff check src/specify_cli/core/owned_mission.py tests/core/test_owned_mission_minter.py tests/specify_cli/cli/commands/agent/test_mission_create_owned_worktree_refusal.py`
  - `uv run --frozen mypy src/specify_cli/core/owned_mission.py` (or the repository's configured
    mypy invocation for `src/`)
- **Files**: none.
- **Notes**: do not run the full matrix; CI owns it. Record the exact commands and outcomes in the
  WP history (`spec-kitty agent tasks add-history WP01 --note "..."`).

## Definition of Done

- T001–T006 complete and recorded; each refusal test was seen **red** before T004 landed.
- Both legs refuse through the real CLI entry point, and both positive controls still create.
- Leaf behaviour, adoption and the single-authority allowlist are unchanged.
- No new refusal code, predicate owner, registry reader, or public CLI surface.
