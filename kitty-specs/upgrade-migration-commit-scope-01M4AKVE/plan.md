# Implementation Plan: Schema-3 upgrade commits only what it changed

**Branch**: `fix/upgrade-migration-commit-scope` | **Date**: 2026-10-07 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/upgrade-migration-commit-scope-01M4AKVE/spec.md`

Planning answers (operator, 2026-10-07): eight work packages with disjoint files; Python 3.13, no new dependencies; real-git behavioural tests; avoid the files of the maintainer's PR #5856; the P0 work package ships as its own PR first (Decision `01M4AYQTE5WGNXKW7411AVYP79`). Scope and rule come from the validation squad aggregate (`<operator-local squad notes>`).

## Summary

`spec-kitty upgrade` on a 2.x project commits the operator's untracked, staged and unstaged work because the schema-3 migration runner commits with `git add -A` and retries with `--no-verify` (#5443, P0). The fix removes that commit step so upgrade's baseline-scoped commit (`capture_upgrade_baseline` → `commit_touched_checkout` → `safe_commit --only`) is the single authority, and closes the holes that authority then exposes: no commit after a failed upgrade, ignored paths never committed, manual review only for files missing the version marker (commit the rest), the migration's own untracks carried, explicit messages for every no-commit case, and a clean rollback (#4763). The mission then applies the same rule to the other automatic commits — metadata writers (#5229), the work-package claim (#5673), merge bookkeeping (`bake.py`) — removes the dead sweeping helpers and shipped text, adds a `src/` gate that starts empty with one canonical merge-conclusion owner, and fixes the `safe-commit` CLI path bugs (#5401, #5671, #4722).

## Technical Context

**Language/Version**: Python 3.13 (CI gate on 3.12; nightly interpreter matrix on 3.13)
**Primary Dependencies**: existing seams only — `upgrade/autocommit.py` (`capture_upgrade_baseline`, `prepare_upgrade_commit_files`, `commit_touched_checkout`), `git/commit_helpers.py::safe_commit` (`add --force --` + `commit --only --`, hooks honoured), `kernel.git` status helpers, `kernel.atomic`, `kernel.resolution.resolve_rejecting_loops`, `migration/schema_version.CURRENT_SCHEMA_CAPABILITIES`, the placement seam for `CommitTarget`. No dependency added, upgraded or removed (DIRECTIVE_051: not triggered).
**Storage**: files in git working trees (`.kittify/`, `kitty-specs/`, agent command/skill files)
**Testing**: pytest. Real-git behavioural tests (`git_repo` + `non_sandbox`) through the pre-existing entry points (`spec-kitty upgrade` via `sys.executable -m specify_cli` with `PYTHONPATH=<checkout>/src`, `implement`, consolidation bake, `safe-commit`/`spec-commit`); pure helpers `unit` + `fast`. The #5443 reproduction is `@pytest.mark.p0_repro(issue=5443)` until the fix commit; every other defect gets a `regression` test red before its fix. Fixtures scrub `GIT_*`/`SPEC_KITTY_*` from the environment, isolate HOME/XDG, pin HOME state and agent config, and use a non-protected branch. Mutant-killing assertions only (no shape pins). Targeted runs locally; CI owns full suites.
**Target Platform**: Linux/macOS/Windows developer machines and CI
**Project Type**: single project (CLI)
**Performance Goals**: no new subprocess per file; the ignored-path baseline uses one extra `kernel.git.status_entries(..., untracked="normal", ignored=True)` probe (ignored directories collapse to one `!! dir/` entry; review M5)
**Constraints**: do not edit `upgrade/finalize.py`, `upgrade/outcome.py`, `cli/commands/upgrade.py`'s import block, repair step, `finalize_upgrade(...)` kwargs or help text, nor #5856's four test files; `_completion_manifest.json` must stay fresh (no help-text changes); changelog entries under 900 characters (NFR-003); no gate allowlist, only the two canonical owners exempt by symbol (ADR 2026-09-30-1)
**Scale/Scope**: ~14 source files, ~8 new test modules, 3 shipped text files, 2 docs

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — pass: upgrade keeps one commit authority (its baseline commit); every other site passes its own written-path list to `safe_commit`; merge conclusions get one owner.
- **Architectural gate discipline (Standing Order 5, ADR 2026-09-30-1)** — pass: the new gate starts empty with a non-vacuous planted-hit test and a scanned-file floor; no allowlist, no baseline entry.
- **ATDD-first (C-011) / bug-fix discipline (DIRECTIVE_041/034)** — pass: each code WP's first commit is its red test through the pre-existing entry point; WP08 (changelog only) carries a recorded documentation-WP exemption whose red is the changelog style guard plus the in-scope issue check run on the planning base.
- **User customisation preservation / ownership boundaries for mutating flows** — this mission is their enforcement for commits.
- **Campsite cleaning** — scoped to the touched functions (e.g. split `_finalizer_step_commit_churn` exclusion logic into a helper); no unrelated refactors.
- **Terminology canon** — pass (Mission, work package; never "feature"; avoid "lane-merge" phrasing in new prose outside baselined files).

No violations.

## Project Structure

### Documentation (this mission)

```
kitty-specs/upgrade-migration-commit-scope-01M4AKVE/
├── plan.md  research.md  data-model.md  quickstart.md
├── traces/  decisions/  checklists/
└── tasks.md (Phase 2)
```

`contracts/`: none — no interface or payload is added; `meta.json` carries `"contracts": "none"` with a rationale.

### Source Code (repository root)

Refreshed from the WP `owned_files` (2026-10-07). **The `owned_files` frontmatter of each WP prompt is authoritative**; this listing is a summary. Recorded out-of-map edits (after the owner lands): `migration/runner.py` `_update_schema_version` (WP02 T006), `upgrade/runner.py` `_stamp_schema_version` (WP02 T013), one call site in `upgrade/autocommit.py` (WP07 T044).

```
# WP01 (P0, PR 1)
src/specify_cli/migration/runner.py                     # step 10 removed; rollback/backup hygiene; ignore lines kept
src/specify_cli/upgrade/migrations/m_3_0_0_canonical_context.py, m_3_1_2_globalize_commands.py, m_3_2_0a4_safe_globalize_commands.py
src/specify_cli/upgrade/autocommit.py                   # ignored-at-baseline and index-deletion exclusions, no-commit reasons
src/specify_cli/cli/commands/upgrade.py                 # commit gated on success; holds no longer suppress; one reason per no-commit case
src/specify_cli/upgrade/runner.py                       # upgraded-worktree commit block (_upgrade_worktrees) gets the same rules
tests/upgrade/{_legacy_upgrade_fixture.py, test_upgrade_commit_scope_5443.py, test_upgrade_commit_outcomes_5443.py, test_upgrade_no_commit_reasons_unit.py, test_upgrade_git_paths.py, test_commit_decision.py, migrations/test_m_3_2_0a4_safe_globalize_commands.py}
tests/specify_cli/migration/{test_runner.py, test_runner_rollback_hygiene_unit.py}
# WP02
src/specify_cli/upgrade/metadata.py, src/specify_cli/migration/backfill_identity.py
tests/upgrade/{test_metadata_schema_roundtrip.py, test_metadata_writers_5229.py, test_metadata_final_file_5229.py}, tests/specify_cli/migration/test_runner_schema_stamp_5229.py
# WP03
src/specify_cli/cli/commands/{implement_claim.py, implement_phases.py, implement.py}
tests/specify_cli/cli/commands/{test_implement_claim.py, test_implement_phases.py, test_implement_runtime_frontmatter_claim.py, test_implement_characterization.py, test_implement_claim_scope_5673.py}
# WP04
src/specify_cli/consolidation/mission_number/bake.py
tests/consolidation/{test_ordering_bake_seam.py, test_bake_commit_scope_meta_only.py}
# WP05
src/specify_cli/git/merge_conclusion.py                 # canonical merge-conclusion owner (conclude_in_progress_op)
src/specify_cli/lanes/{auto_rebase.py, consolidation.py, worktree_allocator.py}, src/specify_cli/coordination/coherence.py, src/specify_cli/cli/commands/agent/workflow.py
tests/architectural/{_commit_scope_census.py, test_commit_scope_owner.py}, tests/git_ops/{test_merge_conclusion_owner.py, test_merge_conclusion_owner_unit.py}, tests/lanes/test_merge_conclusion_routing.py
# WP06
src/specify_cli/core/vcs/{git.py, protocol.py}, src/specify_cli/core/{git_ops.py, __init__.py}
tests/git_ops/{test_git.py, test_vcs_integration.py, test_git_ops.py, test_sweeping_helpers_removed.py}, tests/architectural/test_shipped_text_path_scoped_commits.py
src/charter/offering/skills/{spec-kitty-implement-review/SKILL.md, spec-kitty-implement-review/references/rejection-loop-checklist.md, spec-kitty-git-workflow/SKILL.md, spec-kitty-git-workflow/references/git-operations-matrix.md, spec-kitty-charter-doctrine/SKILL.md}
packs/built-in/{toolguides/GIT_WORKTREE_PR_WORKFLOW.md, toolguides/git-worktree-pr-workflow.toolguide.yaml, pack-manifest.yaml, toolguide.graph.yaml}
docs/api/upgrade-lifecycle.md, docs/guides/how-to/installation/upgrade-project.md
# WP07
src/kernel/resolution.py, src/specify_cli/git/commit_helpers.py, src/specify_cli/cli/commands/{safe_commit_cmd.py, spec_commit_cmd.py}, src/specify_cli/coordination/commit_router.py, src/mission_runtime/owned_checkout.py
tests/kernel/{test_resolution.py, test_resolve_commit_path.py}, tests/specify_cli/cli/commands/{test_safe_commit_cmd.py, test_safe_commit_cli.py, test_safe_commit_symlink_loop.py, test_safe_commit_paths_5401_5671_4722.py, test_spec_commit_symlink_5671.py}
tests/git_ops/test_safe_commit_link_and_stage_detail.py, tests/coordination/test_commit_router_symlink_paths.py, tests/integration/upgrade/{__init__.py, test_upgrade_carries_migration_untracks.py}
# WP08
docs/changelog/CHANGELOG.md                             # PR 2 bullets only; the #5443 bullet is the orchestrator's PR 1 landing fold
```

**Structure Decision**: single project; each WP owns a disjoint file set (see tasks).

## Complexity Tracking

None.

## Implementation Concern Map

> Implementation concerns are NOT work packages; `/spec-kitty.tasks` maps them.

### IC-01 — Upgrade commit path (P0)
- **Purpose**: the upgrade commits exactly the paths it wrote, never after a failure, never ignored paths, holding back only genuinely customised files.
- **Relevant requirements**: FR-001..FR-008, FR-012, FR-019..FR-021, FR-023; SC-001..SC-004, SC-007
- **Affected surfaces**: `migration/runner.py`, `m_3_0_0_canonical_context.py`, `m_3_1_2_globalize_commands.py`, `m_3_2_0a4_safe_globalize_commands.py`, `upgrade/autocommit.py`, `cli/commands/upgrade.py` (commit decision + `_finalizer_step_commit_churn` only), `upgrade/runner.py` (`_upgrade_worktrees` commit block, `origin/main` `:554-555`/`:609-612`: same rules for each upgraded worktree)
- **Sequencing/depends-on**: none
- **Risks**: PR #5856 adjacency in `upgrade.py`; environment-sensitive fixtures (cold vs warm HOME, `agents.available`); the 3.2.5 untrack carry must not commit deletions the operator staged.

### IC-02 — Schema metadata writers (#5229)
- **Purpose**: the final `metadata.yaml` keeps every key and carries the canonical capability map.
- **Relevant requirements**: FR-011
- **Affected surfaces**: `upgrade/metadata.py::ProjectMetadata.save`, `migration/backfill_identity.py::backfill_project_uuid`; recorded out-of-map edits after WP01: `upgrade/runner.py::_stamp_schema_version` and `migration/runner.py::_update_schema_version` (Decision `01M4B6G3J0YNZ57WSHJXDMJS6N`)
- **Sequencing/depends-on**: IC-01 (both runner files belong to WP01)
- **Risks**: legacy list → map conversion; header/comment preservation.

### IC-03 — Work-package claim (#5673)
- **Relevant requirements**: FR-009, SC-006
- **Affected surfaces**: `implement_claim.py::claim_commit_paths`, `implement_phases.py::_ensure_vcs_in_meta` (return a changed flag)
- **Risks**: topology variants (single_branch, lanes, coord); the planning-artifacts commit is out of scope.

### IC-04 — Merge bookkeeping (bake.py)
- **Relevant requirements**: FR-010, SC-006
- **Affected surfaces**: `consolidation/mission_number/bake.py` (:372-401 primary checkout → `safe_commit` + seam target + `MERGE_BOOKKEEPING`, refuse when off-target/detached/meta dirty → unbaked; :555 temp worktree → `commit --only -- rel_meta`)
- **Risks**: protected-branch guard on the primary path; fake-subprocess tests in `test_ordering_bake_seam.py`.

### IC-05 — Merge-conclusion owner and gate
- **Relevant requirements**: FR-013, SC-005
- **Affected surfaces**: one owner, `src/specify_cli/git/merge_conclusion.py::run_committing_op` and `::conclude_in_progress_op(worktree, *, env, message=None, ...)`, asserting MERGE_HEAD/REVERT_HEAD/CHERRY_PICK_HEAD/SQUASH_MSG or a fresh spec-kitty temp worktree; routed sites `lanes/auto_rebase.py:918/1007`, `lanes/consolidation.py:844(→ --amend --only -- <restored>, a C-005 recorded exception), 1013, 1337, 1411`, `lanes/worktree_allocator.py:1429/1550/1647`, `coordination/coherence.py:736`, `cli/commands/agent/workflow.py:661`; gate `tests/architectural/test_commit_scope_owner.py` + `_commit_scope_census.py` reusing `_destructive_op_census`.
- **Sequencing/depends-on**: IC-01, IC-04, IC-06 (their sites must be gone before the gate can start empty) and IC-07 (`safe_commit`'s temp-index commit must exist inside the exempt symbol scope; Decision `01M4B6FZNNSTP6DPN2AAEDEQHZ`)
- **Risks**: behaviour-preserving routing in hot merge paths; documented AST blind spots (plumbing `commit-tree`/`update-ref` outside the gate; follow-up issue filed at closeout).

### IC-06 — Remove sweeping helpers and shipped text
- **Relevant requirements**: FR-014, FR-015
- **Affected surfaces**: `core/vcs/git.py` + `protocol.py` (`commit`), `core/git_ops.py` + `core/__init__.py` (`init_git_repo`), their tests; `src/charter/offering/skills/spec-kitty-implement-review/SKILL.md:301/:836`, `.../spec-kitty-git-workflow/references/git-operations-matrix.md:38`, `packs/built-in/toolguides/GIT_WORKTREE_PR_WORKFLOW.md:32` (+ regenerate the pack manifest), `docs/api/upgrade-lifecycle.md:130`, `docs/guides/how-to/installation/upgrade-project.md:105`.
- **Risks**: pack-manifest freshness; docs freshness and markdownlint budgets.

### IC-07 — safe-commit / spec-commit path normalisation
- **Relevant requirements**: FR-016..FR-018, FR-022
- **Affected surfaces**: `kernel/resolution.py` (new `resolve_commit_path`: parents resolved, final component never followed, looping leaf refused), `git/commit_helpers.py` (`preflight_commit` :1307, `_normalize_expected_parent_path_bytes` :1060, `_stage_requested_files` detail), `cli/commands/safe_commit_cmd.py` (:420, :179, :228, :250, rename sources, cross-boundary refusal, lone-unknown error), `spec_commit_cmd.py:143`, `mission_runtime/owned_checkout.py:223`, `coordination/commit_router.py:1318/:1976`.
- **Risks**: exception-type contracts (`RuntimeError` prefix kept); 3.12 vs 3.13 `Path.resolve` loop behaviour.

### IC-08 — Changelog
- **Relevant requirements**: NFR-003, SC-004 documentation; one `### Fixed` entry per user-visible change, each under 900 characters, plus a bullet for the removed public exports. The #5443 (P0) entry is not WP08's: the orchestrator writes it as a landing fold when PR 1 is cut; WP08 authors PR 2's bullets only.

## Landing plan (Decision `01M4AYQTE5WGNXKW7411AVYP79`)

1. After WP01 is approved, the orchestrator opens PR 1 from a branch off current `origin/main` carrying WP01's commits (test → fix), the mission record so far, and the #5443 changelog bullet, which the orchestrator writes as a landing fold when PR 1 is cut (from WP01's Activity Log draft). WP08 does not write that bullet.
2. After PR 1 lands, merge `origin/main` into `fix/upgrade-migration-commit-scope` before WP08 starts. The mission continues; at the end, consolidate as usual and land PR 2 (WP02–WP08; WP08 = PR 2's changelog bullets) rebased onto `main` with PR 1 merged.
