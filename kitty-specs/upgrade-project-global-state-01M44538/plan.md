# Implementation Plan: Upgrade writes project-global state once

**Branch**: `issue-5457-upgrade-project-global-state` (planning base = consolidation target) | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/upgrade-project-global-state-01M44538/spec.md`, grounded in [`research/code-grounding.md`](research/code-grounding.md), with the post-specify squad folded in ([`research/squad-dispositions.md`](research/squad-dispositions.md)).

## Summary

Remove the #5457 defect class at the source, and teach every integration merge site one declared rule.

1. **Write placement.** `MigrationRunner._upgrade_worktrees` skips any *integrating worktree*: a linked
   worktree on a `kitty/mission-…` branch, or one with an unreadable branch. Project-global state is
   then written and committed only in the repository root checkout. That one change fixes Paths A, B
   and C for every future upgrade.
2. **Classification.** `state/contract.py` declares `.kittify/metadata.yaml` *primary-owned*, and one
   predicate is derived from that declaration. Five integration merge sites consume the predicate,
   each with a fixed resolution side:
   - stale check: does not count the path;
   - lane → mission merge: ours, the mission side;
   - mission → target squash or merge: ours, the target side;
   - auto-rebase lane sync: theirs, the coordination or mission side;
   - dependency-lane merge: ours, the dependent lane.

   The stale check also stops counting content-identical overlaps (same mode and blob at both tips).
   With these rules, projects already in the broken state heal on their next `consolidate`, lane sync
   or `implement`.
3. **Docs.** A new 4.x ADR, amendments to ADRs `2026-07-07-1` and `2026-05-14-1`, a recovery how-to
   and a CHANGELOG entry.

## Engineering Alignment (planning questions resolved from the brief and the grounding)

| # | Question | Answer (source) |
|---|----------|-----------------|
| 1 | Where does the "primary-owned" fact live? | `StateSurface.primary_owned: bool` in `state/contract.py`, plus `primary_owned_paths()` and `is_primary_owned_path(rel)` (exact match, anchored at the repository root). Not `coordination/coherence.py`, which owns a different fact (grounding §3; architect lens). |
| 2 | How does upgrade recognise an integrating worktree? | `core/git_ops.get_current_branch(worktree)` returns `None` (treated as integrating, fail safe) or a branch name. The branch is integrating when `lanes/branch_naming.parse_mission_slug_from_branch(branch) is not None`. There is one skip point, in `_upgrade_worktrees`, which `upgrade_worktrees_only` also routes through. |
| 3 | Mechanism at the merge sites: a merge driver or an explicit resolver? | An explicit shared resolver, `resolve_primary_owned_conflicts(worktree, env)`, in `lanes/consolidation.py`, next to `reconcile_derived_status_snapshot_conflicts` (which the dependency merge already imports). It keeps stage 2 ("ours"), or removes the path when stage 2 is absent. A driver was rejected because git never invokes one on modify/delete, and auto-rebase deliberately does not seed attributes (disposition #10). |
| 4 | Mechanism for auto-rebase? | A new `R-PRIMARY-OWNED-BOOKKEEPING` branch in `_resolve_managed_artifact_conflicts`, reusing `_resolve_take_theirs` with its rule id parametrised. Not added to the per-hunk `conflict_classifier.RULES` (disposition #5). |
| 5 | Ordering inside the squash? | `_resolve_planning_conflicts` → `resolve_primary_owned_conflicts` → `reconcile_derived_status_snapshot_conflicts`. The status reconciler refuses a set that contains anything other than `status.json`, so the primary-owned resolution has to run before it (disposition #6). |
| 6 | Red tests: old wheels or simulation? | Simulation through the real CLI entry points (decision `01M44580VWDA5VDH5V7ZVZV8DD`). Set an older recorded version so that real migrations apply, and use real `git worktree` lanes and a real coordination worktree. The issue's verbatim scripts, run against the real 4.0.0rc4 and 3.2.7 wheels, provide the before and after live evidence at pre-consolidate time. |
| 7 | Result reporting and exit status | Untouched (C-001, C6 boundary). Skipped worktrees contribute nothing to `warnings`, `errors` or `worktree_failures`. |

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml, and git (subprocess) as in the existing modules. Nothing new.
**Storage**: git trees and refs; `.kittify/metadata.yaml` (YAML).
**Testing**: pytest. Real-git fixtures. Real-CLI subprocess tests via `tests/conftest.py::run_cli` and the `isolated_env` fixture. Focused unit tests for each new helper and branch.
**Target Platform**: Linux, macOS and Windows (git ≥ 2.38 for the existing consolidation paths; nothing new is required).
**Project Type**: single Python project (`src/specify_cli`).
**Performance Goals**: NFR-001: zero migration evaluations in integrating worktrees. The stale check adds at most two `git ls-tree` calls per stale-candidate lane, and only when an overlap exists.
**Constraints**: C-001 to C-008 in the spec. In particular: no restructuring of upgrade's result computation; no module-level filename list in `lanes/`; existing refusal texts and codes stay byte-identical; `implement.py` stays untouched.
**Scale/Scope**: about 6 source files and 2 ADR amendments, plus 1 new ADR, a how-to and the CHANGELOG.

## Charter Check

| Charter rule | How the plan complies |
|--------------|-----------------------|
| Single canonical authority | One declaration (the state contract), one predicate, and one shared merge-site resolver. The auto-rebase leg reuses the existing managed-artifact arm. |
| Architectural alignment / layer rules | `lanes/` and `upgrade/` import `specify_cli.state.contract`, `specify_cli.lanes.branch_naming` and `specify_cli.core.git_ops`. All of these are intra-`specify_cli`, with no new cross-package edge (architect lens: `contract.py` has only kernel-level dependencies, so no cycle). |
| ATDD-first / SO-4 red-first | Every WP commits its red test through the pre-existing entry point (the `spec-kitty` CLI, or the production function the CLI calls) before the fix commit. Any tidy-first enabler commits come before the red test. |
| SO-2 campsite / boy-scout | Scoped to the files touched. The tests that pin the defect are re-pinned (FR-011), and `_resolve_take_theirs` gets its rule id parametrised. No new files are pulled into the set. |
| SO-5 gate discipline / no new ratchets (C-007) | No new gate or allowlist. These existing gates must stay green: `test_exemption_registry_ratchet.py`, `test_no_dead_symbols.py`, `test_layer_rules.py`, `test_merge_pipeline_ratchets.py`, `test_destructive_op_routing.py`, `test_state_contract.py`. |
| No destructive remedies (#3931/#5078) | The recovery is re-running the normal commands. The resolver only touches declared paths inside an ephemeral merge, with no tree-wide reset. The existing dependency-merge `reset --hard` to the pre-loop ref is unchanged. |
| Terminology canon | "Mission", "repository root checkout", and the primary sense named every time; no `feature` aliases. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Each WP runs its targeted files plus the named gate files, never the bare `tests/architectural/` directory or `make test-full`. |

Post-design re-check: no violations, so the Complexity Tracking section is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/upgrade-project-global-state-01M44538/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── research/code-grounding.md, research/squad-dispositions.md
├── traces/{tooling-friction,approach,design-decisions}.md
└── tasks.md, tasks/WP*.md      (from /spec-kitty.tasks)
```

Contracts: none. The mission changes no external interface; `meta.json` records `"contracts": "none"` with a rationale.

### Source Code (repository root)

```
src/specify_cli/
├── state/contract.py                 # +primary_owned field, primary_owned_paths(), is_primary_owned_path()
├── upgrade/runner.py                 # skip integrating worktrees in _upgrade_worktrees (one seam)
├── lanes/stale_check.py              # drop primary-owned + content-identical overlaps
├── lanes/consolidation.py            # resolve_primary_owned_conflicts(); wired into _run_squash_merge and the MERGE branch of _merge_branch_into
├── lanes/worktree_allocator.py       # dependency-lane merge calls the resolver before the status reconcile
└── lanes/auto_rebase.py              # R-PRIMARY-OWNED-BOOKKEEPING managed arm; _resolve_take_theirs(rule_id=…)

tests/
├── specify_cli/test_state_contract.py (+ new unit tests for the predicate)
├── upgrade/                          # re-pinned test_upgrade_worktree_commit.py and the #4972 tests; new integrating-worktree tests
├── e2e/ or integration/              # real-CLI paths A/B/C: upgrade → consolidate / review
├── lanes/                            # stale rule, merge-site resolver, dependency merge, auto-rebase arm
└── integration/test_lane_lifecycle_sync.py  # coordination lane sync with a divergent metadata.yaml

docs/
├── adr/4.x/2026-10-04-2-upgrade-writes-project-global-state-once.md   (new)
├── adr/3.x/2026-07-07-1-…md, adr/3.x/2026-05-14-1-…md                  (amendments)
├── a how-to for recovering a mission upgraded mid-flight (location chosen by the docs WP per Divio)
└── changelog/CHANGELOG.md [Unreleased]
```

**Structure Decision**: single-project layout as above. Each concern stays inside its owning module. No new module is created except tests.

## Implementation Concern Map

### IC-01 — Primary-owned declaration

- **Purpose**: one declared fact plus a derived, exact, root-anchored predicate that every consumer uses.
- **Relevant requirements**: FR-004, C-002, C-008, NFR-004.
- **Affected surfaces**: `src/specify_cli/state/contract.py` (`StateSurface`, `to_dict`, `project_metadata` entry, two new functions, `__all__` / `state/__init__.py` export if the module convention requires it); `tests/specify_cli/test_state_contract.py`.
- **Sequencing/depends-on**: none.
- **Risks**: `to_dict` key set is pinned by `test_state_contract.py:83`. Matching must not be by basename (#4933). The ratchet scans only consumer modules; consumers must call the function and never restate the literal.

### IC-02 — Upgrade write placement

- **Purpose**: upgrade writes, stamps and commits nothing in integrating worktrees; non-integrating worktrees are unchanged.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-011, NFR-001, C-001; Stories 1–3 (fresh upgrade paths).
- **Affected surfaces**: `src/specify_cli/upgrade/runner.py` (`_upgrade_worktrees`, a new `_is_integrating_worktree` helper); `tests/upgrade/test_upgrade_worktree_commit.py`, `tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py` (re-pin onto non-integrating worktrees); a new real-CLI test module for paths A/B/C (upgrade → consolidate / review).
- **Sequencing/depends-on**: none (it does not need IC-01).
- **Risks**:
  - Existing fixtures create worktrees on arbitrary branch names. Those stay "non-integrating", which is what keeps the #4972 tests meaningful; re-pin only where a fixture represents a lane or coordination branch.
  - `test_genuine_worktree_migration_still_mints_fresh_stamp_not_main_aligned` pins the defect for integrating branches. Re-pin it, do not delete it.
  - Keep result and exit computation untouched (C6 runs in parallel and edits the same file; keep the diff to the skip seam).

### IC-03 — Consolidation merge sites and the stale rule

- **Purpose**: the stale check, lane → mission merge, mission → target squash or merge, and dependency-lane merge resolve or ignore primary-owned bookkeeping. The stale check also ignores content-identical overlaps. Genuine conflicts are still refused byte-identically.
- **Relevant requirements**: FR-005, FR-006, FR-007, FR-012, FR-013, FR-009, NFR-002; Story 4 AS-1/2/3/5, Story 5.
- **Affected surfaces**: `src/specify_cli/lanes/stale_check.py`; `src/specify_cli/lanes/consolidation.py` (`resolve_primary_owned_conflicts`, `_run_squash_merge` ordering, the MERGE branch of `_merge_branch_into`); `src/specify_cli/lanes/worktree_allocator.py` (`_merge_dependency_lane_tips`); tests in `tests/lanes/` (`test_merge.py`, stale-check tests, dependency-merge tests) plus real-CLI `consolidate` recovery tests.
- **Sequencing/depends-on**: IC-01.
- **Risks**:
  - The squash ordering (disposition #6).
  - The MERGE branch must commit only when no unmerged path remains; otherwise abort and raise exactly as today.
  - In the dependency merge, commit only when the index is clean; otherwise fall through to the existing status reconcile and fail-closed path.
  - `_merge_branch_into` also serves `--strategy merge` mission → target, where ours is the target, which is the correct side.
  - REBASE is out of scope.
  - Under #4892 the resolver may only touch declared paths.

### IC-04 — Auto-rebase managed-artifact rule

- **Purpose**: the lane sync after a coordination commit, and consolidate's auto-rebase, resolve a primary-owned path to stage 3 (the coordination or mission side) under the audited rule `R-PRIMARY-OWNED-BOOKKEEPING`.
- **Relevant requirements**: FR-008, FR-009; Story 3, Story 4 AS-4, Story 5 AS-3.
- **Affected surfaces**: `src/specify_cli/lanes/auto_rebase.py` (`_resolve_take_theirs` rule-id parameter as a tidy-first enabler; a new branch in `_resolve_managed_artifact_conflicts`; a new `RULE_ID_PRIMARY_OWNED` constant); `tests/lanes/test_auto_rebase*.py`, `tests/integration/test_lane_lifecycle_sync.py`.
- **Sequencing/depends-on**: IC-01.
- **Risks**: the rule id must show in the audit commit message. A coordination lane worktree has a sparse checkout, so take stage 3 through the existing sparse helpers.

### IC-05 — Decision records and operator docs

- **Purpose**: record the decision and the residuals; give operators the recovery path.
- **Relevant requirements**: FR-010; Assumptions (residuals); C-003.
- **Affected surfaces**:
  - a new ADR `docs/adr/4.x/2026-10-04-2-upgrade-writes-project-global-state-once.md`, run through `python -m scripts.docs.freshen_adr_inventory` and the docs index regeneration if the repo convention requires it;
  - in-place amendments to `docs/adr/3.x/2026-07-07-1-ignored-surface-backfill-migration-pattern.md` and `docs/adr/3.x/2026-05-14-1-stale-lane-auto-rebase-classifier-policy.md`;
  - a recovery how-to;
  - `docs/changelog/CHANGELOG.md` `[Unreleased]`;
  - a short note in `docs/architecture/branch-target-routing.md` or `git-worktrees.md`.
- **Sequencing/depends-on**: IC-02, IC-03, IC-04, so the docs describe shipped behaviour.
- **Risks**: docs freshness (`updated:` frontmatter); `scripts/docs/check_docs_freshness.py --ci`; `tests/architectural/test_no_legacy_terminology.py`; the `test_adr_content_invariance` frontmatter rules.

## Test strategy (per requirement)

| Requirement | Red-first test (pre-existing entry point) | Positive control on the same fixture |
|-------------|-------------------------------------------|--------------------------------------|
| FR-001/002 | `spec-kitty upgrade --yes` (real CLI) on an older recorded version with a lane worktree on `kitty/mission-…-lane-a`: no new commit on the lane branch, an unchanged lane `metadata.yaml`, one upgrade commit on the root branch | the same fixture with a second worktree on `feature/x`: that one is upgraded and committed (FR-003) |
| Story 1/2/3 | real CLI: upgrade, then `consolidate` (two lanes; one lane squash into `work`) and `agent action review` (lanes_with_coord) | — (covered by the Story 5 controls) |
| FR-005/006 | real CLI `consolidate` on the broken-state fixture with lane worktrees removed (Story 4 AS-2) | a different `.gitattributes` content on the same fixture is still stale (Story 5 AS-1) |
| FR-012 | real CLI `consolidate` on the broken-state fixture with lane worktrees present (Story 4 AS-1) | a source-file conflict still raises the merge failure |
| FR-007 | `consolidate` default squash, divergent `metadata.yaml`, plus a mixed `status.json` conflict | a source-file conflict still raises `TARGET_BRANCH_CONTENT_CONFLICT` byte-identically |
| FR-008 | `sync_lane_after_coordination_commit`, the production function `agent action review` calls, on a coordination and lane fixture; the audit message names the rule | a non-classified path still raises `LANE_AUTO_REBASE_FAILED` |
| FR-013 | `implement` for a dependent WP (real CLI, through `worktree_allocator`) with a divergent dependency-lane `metadata.yaml` | a source conflict still raises `DependencyLaneMergeConflictError` |
| FR-004 | unit: the predicate is exact and root-anchored (`sub/.kittify/metadata.yaml` and `metadata.yaml` do not match) | `.kittify/config.yaml` and `.gitattributes` are not primary-owned (C-008) |

For each compound fix (IC-03), revert each half in turn and confirm the matching scenario goes red (tactic `acceptance-criteria-non-vacuity`).

## Complexity Tracking

None.
