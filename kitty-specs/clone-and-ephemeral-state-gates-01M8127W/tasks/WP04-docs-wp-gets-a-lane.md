---
work_package_id: WP04
title: Docs work packages get a lane in lane topologies (#7809)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- C-003
- C-004
- C-005
- SC-001
planning_base_branch: issue-7809-clone-ephemeral-state-gates
merge_target_branch: issue-7809-clone-ephemeral-state-gates
branch_strategy: Planning artifacts for this mission were generated on issue-7809-clone-ephemeral-state-gates. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7809-clone-ephemeral-state-gates unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-clone-and-ephemeral-state-gates-01M8127W
base_commit: 7fbbee86234ee687d370aab8246c989c6fb44f01
created_at: '2026-11-22T07:37:15.136238+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
- T021
history: []
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/ownership/kind_normalisation.py
create_intent:
- src/specify_cli/ownership/kind_normalisation.py
- tests/lanes/test_kind_normalisation_7809.py
- tests/lanes/test_docs_wp_gets_a_lane_7809.py
- docs/changelog/unreleased/7809.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/ownership/kind_normalisation.py
- src/specify_cli/cli/commands/agent/mission_finalize.py
- src/specify_cli/cli/commands/agent/mission_finalize_lanes.py
- src/specify_cli/cli/commands/agent/mission_finalize_bootstrap.py
- src/specify_cli/cli/commands/agent/mission_finalize_seams.py
- tests/lanes/test_kind_normalisation_7809.py
- tests/lanes/test_docs_wp_gets_a_lane_7809.py
- docs/adr/4.x/2026-11-06-3-topology-is-settled-once-at-first-finalize.md
- docs/changelog/unreleased/7809.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Docs work packages get a lane in lane topologies (#7809)

## Objective (#7809)

In a lane Mission, a docs work package (`planning_artifact`) is placed on `lane-planning`, whose branch is the target branch. Every gate then looks for its work there. Operator rulings:

- **Normalise kind:** in a lane topology, `finalize-tasks` rewrites a `planning_artifact` WP that owns any path outside `kitty-specs/` to `execution_mode: code_change`, with a notice.
- **Refuse, split it:** a mixed `kitty-specs/` + other-paths WP is refused with a split remedy.
- **Count it:** the size-based topology settlement counts such a WP as a code lane.

`single_branch` is untouched. A started WP is never rewritten (frozen membership, ADR `2026-10-04-2`).

## Grounding

- **Lane placement by kind.** `src/specify_cli/lanes/compute.py:955-964` puts `planning_artifact` WPs on `lane-planning`. `lanes/branch_naming.py:615` maps that lane to the target.
- **Inference / frontmatter writes.** `src/specify_cli/cli/commands/agent/mission_finalize_bootstrap.py:220-236` writes the inferred `execution_mode` only when absent. You need an explicit rewrite path for the normalised kind.
- **Settlement.**
  - `mission_finalize.py:1312-1330` calls `_decide_topology_by_size` (`mission_finalize_lanes.py:627`).
  - `_count_code_lanes_for_settlement` (`:~590-612`) runs `compute_lanes(... LANES_WITH_COORD)` and `count_code_lanes`.
  - Settlement applies in `_apply_topology_settlement` (`:660`).
  - The size rule: `lanes/topology_settlement.py:102`.
- **Frozen membership preflight.** `mission_finalize.py:~1335` (`_preflight_frozen_lane_membership`). The started WP ids are available there.
- **Kitty-specs ownership refusal.** `INVALID_WP_OWNED_FILES_KITTY_SPECS` in `mission_finalize_seams.py` / `mission_finalize_bootstrap.py` / `mission.py`; grep for it. The check exempts a `planning_artifact` WP confined to `kitty-specs/` or `docs/`. After normalisation, a mixed WP is `code_change` and the existing check refuses it. Add the split remedy to that message for this case.
- **Ownership manifests.** `specify_cli/ownership/models.py` (`OwnershipManifest`, `WorkProductKind`).
- **Existing fixtures.** `tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py` has `make_default_mission(..., planning=(i,))` (`:80`), `run_finalize` and `_assert_lanes_with_coord`; its tests at `:198` / `:207` settle with planning WPs. This file is out-of-matrix: if you change it (some assertions may flip because docs WPs now count), disclose it. `tests/consolidation/test_wp_evidence.py::test_lane_window_is_lane_branch_for_code_and_target_for_planning` (`:212`) pins planning evidence; leave it unless your change flips it.

## Design

- **New pure module `src/specify_cli/ownership/kind_normalisation.py`.**
  - `normalise_kinds_for_lane_topology(manifests: Mapping[str, OwnershipManifest], *, started_wp_ids: frozenset[str]) -> KindNormalisation`, a frozen dataclass holding the new manifests and a tuple of `(wp_id, paths_outside_kitty_specs)`.
  - A path is "outside" when it does not start with `kitty-specs/`, globs included.
  - Started WPs are untouched.
- **finalize-tasks.**
  - **Settlement count.** Normalise before `_count_code_lanes_for_settlement` ("Count it").
  - **Lane topology.** When the effective topology is a lane topology (settled this run to `lanes_with_coord`, or an explicit `lanes` / `lanes_with_coord` / `coord`), use the normalised manifests for lanes, ownership validation and the frontmatter write. Persist `execution_mode: code_change` (not in `--validate-only`, and not in `--refresh-planning-commit`'s zero-mutation mode).
  - **single_branch** (settled or explicit): the original manifests, unchanged.
  - **Output.** Human: one `Notice:` line per rewritten WP. JSON: `kind_normalised` (see `contracts/finalize-kind-normalisation.md`).
- **ADR.** Amend ADR `2026-11-06-3` (Amendment 2026-11-22): docs WPs count toward settlement, kind normalisation in lane topologies, the mixed-WP refusal, and the frozen-membership exception. Link #7809 and #7759.
- **Follow-up (C-004).** Record in the WP history that the `execution_mode` template guidance in `spec-kitty-open-packs` needs updating. Do not edit `packs/built-in/`.

## Subtasks

- **T016** Red-first CLI acceptance test `tests/lanes/test_docs_wp_gets_a_lane_7809.py`:
  - a default Mission with WP01 code (`src/a/**`), WP02 code (`src/b/**`) and WP03 docs (`docs/x.md`, `planning_artifact`) → `finalize-tasks` settles `lanes_with_coord`, WP03 has its own lane in `lanes.json`, frontmatter `execution_mode: code_change`, notice printed;
  - a Mission with one code WP plus a docs WP plus a kitty-specs-only WP → settles `lanes_with_coord` because the docs WP counts;
  - a mixed WP → refused `INVALID_WP_OWNED_FILES_KITTY_SPECS` with the split text;
  - a two-WP Mission → `single_branch`, kinds unchanged.

  Commit it red.
- **T017** Pure rule plus `tests/lanes/test_kind_normalisation_7809.py`.
- **T018** Settlement count uses the normalised kinds.
- **T019** Apply plus persist in lane topologies; notice and JSON.
- **T020** Mixed-WP split remedy text.
- **T021** ADR amendment and the changelog fragment `docs/changelog/unreleased/7809.fixed.md`.

## Tests to run

- New files, `tests/lanes/`.
- `tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py` and the other `test_finalize*` tests there: out-of-matrix, run them and disclose them.
- `tests/consolidation/test_wp_evidence.py`, `tests/specify_cli/ownership/` (out-of-matrix: disclose).
- Gates: `tests/architectural/test_layer_rules.py`, `test_no_dead_symbols.py`.
- `make test-fast`.

## Do This First

1. Load the agent profile named in the frontmatter (`/spk-charter-profile-load`). Read `.kittify/charter/charter.md` and `CLAUDE.md`.
2. Read `kitty-specs/clone-and-ephemeral-state-gates-01M8127W/research.md`, which holds the code grounding, the squad corrections and the operator rulings, and this Mission's `spec.md` and `plan.md`.
3. Implement only in the workspace that `spec-kitty agent action implement <WP> --mission clone-and-ephemeral-state-gates-01M8127W --agent <you>` resolves. Never `cd` into a reconstructed path.

## Working rules (binding)

- **ATDD, red-first.** The first commit on the lane is the failing acceptance test, through the pre-existing entry point named below. It is committed on its own BEFORE any implementation commit. Record the red run (command + failing count) in the WP history (`spec-kitty agent tasks add-history`).
- **Gates.** Code must pass `ruff check`, `ruff format --check --force-exclude <files>`, and `mypy` on touched files with zero new issues. No new `# noqa` / `# type: ignore` without an inline rationale. Keep Sonar complexity at 15 or below, hoist repeated literals into constants, and test every new branch.
- **Tests to run.** Your new tests, the test files of every module you touch (find them with `grep -rl "<module>" tests --include="*.py"`), the owning subsystem directories named below, `make test-fast`, and the named architectural gates. Never run a full `tests/architectural/`, `make test-full`, or e2e/performance sweep (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
- **Out-of-matrix disclosure (#7801).** If you change any test under an out-of-matrix directory (for example `tests/specify_cli/cli/commands`, `tests/specify_cli/review`, `tests/specify_cli/lanes`, `tests/specify_cli/tasks`, `tests/integration`, `tests/contract`; the full list is `out_of_matrix_test_dirs` in `.github/ci-module-registry.yml`), name each file in your WP history as "nightly-only" and run it locally.
- **Changelog fragment.** Use the path in `owned_files`. Follow `docs/changelog/unreleased/README.md` and run `uv run --frozen python -m scripts.docs.check_changelog_style`.
- **Terminology.** Mission, work package, lane. Never `feature` in new prose or identifiers.
- **No push from the CLI.** Add no `git push` to any code path. Contact no remote outside `kernel.git.remote`.

## Hand-off to review

Move to `for_review` with `spec-kitty agent tasks move-task <WP> --to for_review --mission clone-and-ephemeral-state-gates-01M8127W`, after committing on the lane and pushing the lane branch to origin.

## Reviewer note (binding, because of #7802)

After approving, the reviewer pushes the lane branch so origin holds the approval's `lane_head`. The reviewer then confirms with `git ls-remote origin <lane-branch>` that the remote tip equals, or contains, the stamped SHA before ending the session.
