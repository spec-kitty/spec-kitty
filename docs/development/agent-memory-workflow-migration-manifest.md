---
title: Agent-Memory Workflow Migration Manifest (Bucket 2)
description: Audit manifest mapping 49 workflow/CI/git/status-and-sync mechanics memory entries to their repo-native home, an echo, a learned fact, or a private disposition.
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
type: reference
related:
- docs/development/agent-memory-migration-manifest.md
- docs/development/how-to/review-gates.md
- docs/development/how-to/pr-landing.md
- docs/operations/sync-drain.md
- docs/architecture/artifact-placement-seam.md
---

# Agent-Memory Workflow Migration Manifest (Bucket 2)

> **Historical record (2026-08 memory-migration audit).** Kept as a record of a one-off audit; not current guidance. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../plans/4-0-0-milestone-roadmap.md).

Mission `workflow-mechanics-self-doc-01M02SF1` is the "Bucket 2" follow-up to
`self-documenting-repo-01M0287X` (Bucket 1, see
[`agent-memory-migration-manifest.md`](agent-memory-migration-manifest.md)).
Where Bucket 1 migrated the operator's gate-remedy / recovery-runbook /
env-friction memory entries (G1&#8211;G6), Bucket 2 audits the remaining
~49 **workflow, CI, git, and status/mission/sync mechanics** entries &#8212;
product mechanics an agent still has to learn the hard way when no canonical
doc says them for itself.

The audit that produced the disposition for each entry
(`work/bucket2-workflow-memory-audit.md`) is gitignored and does not exist in
this worktree or in CI, exactly like Bucket 1's working file &#8212; so this
manifest is the **committed authority** for the migration, not a pointer to
one. The companion test,
[`tests/docs/test_workflow_migration_manifest_complete.py`](../../tests/docs/test_workflow_migration_manifest_complete.py),
parses the three cluster tables below at runtime and enforces that every row
carries a recognised token and every path-bearing token resolves to a real
file &#8212; it is the enforcement half of this manifest, not just a report of
it.

**Out of scope (C-004, same as Bucket 1):** deleting the resolved entries
from the operator's live `MEMORY.md` file is a manual, per-operator checklist
tracked on [#3448](https://github.com/Priivacy-ai/spec-kitty/issues/3448).
This manifest produces the resolution map; the operator applies it at their
own pace.

## Resolution vocabulary

Each row below carries exactly one resolution token:

| Token | Meaning |
|---|---|
| `home:` | The lesson now lives at this repo path because a WP in **this** mission created the file or added the section that says it for itself. |
| `already-home:` | The lesson was **already** covered by an existing repo path before this mission touched anything &#8212; the memory entry is a deletable echo. |
| `learned-fact:` | Too narrow or environment-specific for a doc; captured as a git-tracked, team-shared note under `.kittify/memory/`. |
| `keep-private` | Operator-working-style calibration or single-agent-harness behaviour; deliberately not codified into a shared repo surface. |
| `charter-candidate` | The lesson proposes a new governance rule; routing to the charter is operator-gated and not assumed by this manifest. |

## Cluster A &#8212; Landing / git (17)

| Memory entry | Resolution |
|---|---|
| `feedback_fork_pr_landing_push` | **already-home:** [`GIT_WORKTREE_PR_WORKFLOW.md`](../../packs/built-in/toolguides/GIT_WORKTREE_PR_WORKFLOW.md) &#8212; "Fork PR pushes go over SSH" is already codified harness-neutral; the replacement-PR half is in `pr-landing.md` &sect;9. |
| `feedback_force_with_lease_rejection` | **already-home:** [`GIT_WORKTREE_PR_WORKFLOW.md`](../../packs/built-in/toolguides/GIT_WORKTREE_PR_WORKFLOW.md) &#8212; "(stale info) = origin moved; fetch + cherry-pick, never plain `--force`" is verbatim there. |
| `feedback_rebase_check_before_landing_push` | **already-home:** [`pr-landing.md`](how-to/pr-landing.md) &sect;3 (rebase-first) + &sect;9 (fetch-before-push). |
| `feedback_reuse_clone_per_mission_branch` | **keep-private** &#8212; "prefer one clone + branch-per-mission" is an operator clone-vs-worktree preference; the safety half is the separately-resolved `feedback_one_mission_per_checkout`. |
| `feedback_no_branch_switch_during_bg_tests` | **already-home:** [`GIT_WORKTREE_PR_WORKFLOW.md`](../../packs/built-in/toolguides/GIT_WORKTREE_PR_WORKFLOW.md) &#8212; "don't move a worktree's HEAD while a background job reads it" is present with rationale. |
| `feedback_one_mission_per_checkout` | **home:** [`git-worktrees.md`](../architecture/git-worktrees.md) &#8212; "Cross-Mission Concurrency Is a Different Question" section (WP05): two missions in one checkout race the shared git HEAD/index. |
| `feedback_no_git_stash_in_lane_worktrees` | **already-home:** [`GIT_WORKTREE_PR_WORKFLOW.md`](../../packs/built-in/toolguides/GIT_WORKTREE_PR_WORKFLOW.md) &#8212; the shared `refs/stash` stack across worktrees is documented, plus `known-friction-points.md`. |
| `feedback_isolate_pr_review_agents` | **already-home:** [`pr-landing.md`](how-to/pr-landing.md) &sect;2 (one isolated worktree per PR) + &sect;8 (read-only landing worktree). |
| `feedback_isolation_review_needs_pushed_commit` | **keep-private** &#8212; Claude-Code-harness `isolation:"worktree"` behaviour (seeds from a pushed commit), not a Spec Kitty product mechanic. |
| `feedback_isolation_worktree_seeds_from_primary_repo` | **keep-private** &#8212; same harness-specific worktree-seeding detail; kept out of the harness-neutral toolguide. |
| `feedback_claim_pr_before_working` | **already-home:** [`pr-landing.md`](how-to/pr-landing.md) &sect;1 "Claim before touching" &#8212; verbatim. |
| `feedback_pr_landing_plus_lightweight_squad` | **already-home:** [`pr-landing.md`](how-to/pr-landing.md) &sect;8 "Adversarial squad" &#8212; the 2-lens floor, fold-by-default, and immediate-file discipline are all present. |
| `feedback_landing_pass_lessons_0704` | **already-home:** [`pr-landing.md`](how-to/pr-landing.md) &sect;9 (lease via `rev-parse`) and &sect;3 (changelog symlink); the "Closes-partial-issue" half is the separately-resolved `feedback_pr_closing_keyword_parsing`. |
| `feedback_small_fix_pr_with_charter_files_is_stale_stack` | **home:** [`pr-landing.md`](how-to/pr-landing.md) &#8212; "Stale-stack diagnostic: two-dot vs three-dot diff" subsection (WP04): a small-fix PR carrying charter files under a two-dot diff but not a three-dot one is smuggled governance. |
| `feedback_pr_closing_keyword_parsing` | **home:** [`GITHUB_TRACKER.md`](../../packs/built-in/toolguides/GITHUB_TRACKER.md) &#8212; "Closing keywords &#8212; one issue per keyword" section (WP08): `Closes #A,#B` only auto-closes `#A`; repeat the keyword per issue. |
| `reference_history_compression_by_path_bucket` | **home:** [`compress-mission-history.md`](how-to/compress-mission-history.md) (WP04, new how-to): the path-bucket `git commit-tree` snapshot-chain recipe + tree-parity proof. |
| `feedback_post_merge_history_compression` | **home:** [`compress-mission-history.md`](how-to/compress-mission-history.md) &#8212; same how-to; the "never `rebase -i`" reasoning and phase-boundary technique are the other half of the same recipe. |

## Cluster B &#8212; CI (14)

| Memory entry | Resolution |
|---|---|
| `feedback_collect_universe_once_reuse` | **keep-private** &#8212; **corrected this run**: the audit's working draft proposed `learned-fact:`, but WP09 did not create a matching `.kittify/memory/` note, so that path-check would fail. The anti-pattern is unique to `_gate_coverage.collect_universe` (already fixed in code) and too narrow for a doc; kept private rather than routed to a nonexistent file. |
| `feedback_precision_runs_not_full_suite_local` | **keep-private** &#8212; the general principle (CI owns the full sweep) is already home in `CLAUDE.md`/`testing-parallel.md`; "only targeted runs locally" is operator-environment calibration. |
| `feedback_no_full_arch_suite_locally` | **keep-private** &#8212; environment-specific to the operator's machine, and in tension with `pr-landing.md`'s "run `tests/architectural/` locally on the rebased tip"; kept private rather than codifying a machine-specific limit. |
| `reference_ci_label_skip_guard` | **home:** [`known-friction-points.md`](reference/known-friction-points.md) (WP03): the `pr:deferred` / `pr:skip-ci` job-skip guard, cited to `ci-quality.yml`. |
| `reference_red_main_ci_release_policy` | **already-home:** [`red-main-and-release-readiness.md`](reference/red-main-and-release-readiness.md), plus ADR `2026-07-17-1` and charter Standing Order #9 &#8212; fully codified across multiple surfaces already. |
| `feedback_classify_reds_against_true_mission_base` | **home:** [`pr-landing.md`](how-to/pr-landing.md) &#8212; "Multi-WP lanes: classify against the true base, not the lane tip" subsection (WP04): `git merge-base <mission-branch> upstream/main`, not the lane tip. |
| `feedback_path_filter_unskips_suites_on_new_path_push` | **already-home:** [`pr-landing.md`](how-to/pr-landing.md) &#8212; "shard path-filters mask pre-existing failures&#8230; your own folds trigger this too" is documented verbatim. |
| `feedback_module_move_into_critical_path_coverage` | **home:** [`coverage-signals.md`](reference/coverage-signals.md) (WP03) &#8212; "Remedy: `git mv` into a critical-path dir needs `fast`-marked coverage" section. |
| `feedback_green_pr_regardless_of_red_origin` | **already-home:** [`pr-landing.md`](how-to/pr-landing.md) &sect;4 &#8212; "fold the fix in by default&#8230; keep main green even for a red the PR did not cause." |
| `feedback_ci_fix_landing_discipline` | **already-home:** [`pr-landing.md`](how-to/pr-landing.md) &sect;4, plus `review-gates.md`'s Typer/click version-skew section and `known-friction-points.md`'s stale-install entry. |
| `feedback_verify_lint_inputs_tracked` | **home:** [`known-friction-points.md`](reference/known-friction-points.md) (WP03) &#8212; `charter lint`'s project-DRG input (`.kittify/doctrine/graph.yaml`) is gitignore-adjacent; confirm it is tracked and in-diff before trusting a `charter lint` result. |
| `feedback_no_backticks_in_shell_double_quotes` | **already-home:** [`EFFICIENT_LOCAL_TOOLING.md`](../../packs/built-in/toolguides/EFFICIENT_LOCAL_TOOLING.md) &#8212; "Shell quoting" section: backticks inside double quotes run as command substitution; use `--body-file`/heredoc. |
| `feedback_dispatched_impl_foreground_tests` | **already-home:** [`EFFICIENT_LOCAL_TOOLING.md`](../../packs/built-in/toolguides/EFFICIENT_LOCAL_TOOLING.md) &#8212; "Gate execution mode" section: run gates in the foreground; backgrounding stalls the handoff. |
| `feedback_no_recursionerror_is_not_no_cycle` | **learned-fact:** [`no-recursionerror-is-not-no-cycle.md`](../../.kittify/memory/no-recursionerror-is-not-no-cycle.md) &#8212; narrow verification discipline: absence of a crash does not prove absence of a cycle; trace the call graph. |

## Cluster C &#8212; Status / mission / sync (18)

| Memory entry | Resolution |
|---|---|
| `reference_issue_matrix_approval_gate_mechanics` | **home:** [`review-gates.md`](how-to/review-gates.md) (WP01) &#8212; "Issue-matrix discovery and `issue-verdict --actor`" section covers the genuinely-absent discovery-surface and `--actor`-required half; the verdict vocabulary/schema/`.json`-canonical rule was **already-home** at `ERROR_CODES.md` and `spec-kitty-mission-review/SKILL.md` (Gate 4) before this mission and is cited from `review-gates.md` rather than restated. |
| `project_in_mission_issue_matrix_verdict` | **already-home:** [`spec-kitty-mission-review/SKILL.md`](../../src/charter/offering/skills/spec-kitty-mission-review/SKILL.md) &#8212; the non-terminal `in-mission` verdict (accepted at `approved`, rejected on `done`) is already documented there. |
| `reference_flat_missions_still_require_lanes` | **home:** [`execution-lanes.md`](../architecture/execution-lanes.md) (WP05) &#8212; the `MissingLanesError` contract; the stale `AGENTS.md`/`CLAUDE.md` line that claimed a retired `lanes.json`-absent legacy fallback was fixed in the same pass (WP07). |
| `feedback_lane_move_task_sync_hang` | **already-home:** [`known-friction-points.md`](reference/known-friction-points.md) &#8212; "`move-task` can hang on sync-daemon fan-out" entry, plus `review-gates.md`'s pre-review regression-gate section. |
| `reference_merge_review_artifact_invariant` | **home:** [`review-gates.md`](how-to/review-gates.md) (WP01) &#8212; "Review-cycle artifacts and the merge gate" section: `terminal_wp_latest_review_artifact_must_not_be_rejected`, its shared implementation across `merge`/`merge --dry-run`/`review` Gate 1, and the schema. **Corrected this run**: the original memory entry's framing (a frontmatter-based mechanism) describes retired behaviour &#8212; see "Corrections surfaced this run" below. |
| `reference_sync_identity_form_split` | **learned-fact:** [`sync-identity-form-split.md`](../../.kittify/memory/sync-identity-form-split.md) &#8212; **corrected this run**: the original memory cited issue #883 as the tracking reference; that citation does not resolve to this defect and has been dropped rather than carried forward. |
| `reference_sync_drain_gate_chain` | **home:** [`sync-drain.md`](../operations/sync-drain.md) (WP02, new runbook) &#8212; the 3-gate drain order (`saas_disabled` &rarr; `missing_auth` &rarr; `missing_team`) and the `sync doctor` false-green trap. |
| `feedback_seam_classification_two_axes_and_gate_vacuity` | **home:** [`artifact-placement-seam.md`](../architecture/artifact-placement-seam.md) (WP05) &#8212; "Two-Axis Resolver-Site Classification" (Axis A raise-or-degrade, Axis B anchor-root); the gate-vacuity half ("prove the gate reads its authority at runtime&#8212;an alias/re-export defeats it") is the sibling addition in [`architectural-gate-non-vacuity.tactic.yaml`](../../packs/built-in/tactics/architectural-gate-non-vacuity.tactic.yaml) (WP08). |
| `reference_review_cycle_artifact_frontmatter_trap` | **home:** [`review-gates.md`](how-to/review-gates.md) &#8212; consolidated into the same "Review-cycle artifacts and the merge gate" section: `move-task --review-feedback-file` provenance guard, cycle numbering under lock. |
| `feedback_review_artifact_no_hand_author` | **home:** [`review-gates.md`](how-to/review-gates.md) &#8212; "Never instruct an agent to hand-write an `approved` review-cycle artifact to unblock a gate" is stated directly in the merge-gate section (WP01); the doctrine-layer rationale (two-party review integrity) is the sibling enrichment "Never manufacture or self-certify an approved artifact" in [`reviewer-implementer-role-separation.tactic.yaml`](../../packs/built-in/tactics/reviewer-implementer-role-separation.tactic.yaml) (WP08). The charter-routing recommendation the original audit flagged for this entry is superseded by that tactic shipping &#8212; no open `charter-candidate` remains for it. |
| `project_lane_bare_python_imports_primary` | **already-home:** [`EFFICIENT_LOCAL_TOOLING.md`](../../packs/built-in/toolguides/EFFICIENT_LOCAL_TOOLING.md) &#8212; "Python environment isolation (uv)" section, plus `known-friction-points.md`: a bare `python`/`pytest` in a lane or clone imports the PRIMARY `src`; always `uv run`. |
| `reference_rejected_then_fixed_approval_override` | **home:** [`review-gates.md`](how-to/review-gates.md) &#8212; "The `--skip-review-artifact-check` escape hatch" subsection: the arbiter-override path, mandatory `--note`, and the `ReviewOverride.complete` gating condition. |
| `feedback_read_write_partition_symmetry` | **home:** [`artifact-placement-seam.md`](../architecture/artifact-placement-seam.md) (WP05) &#8212; "Partition-Move Audit Checklist": when a partition classification moves, grep every reader, classify both axes, and prove it with an e2e test rather than a unit read alone. |
| `feedback_seam_bypass_stale_comment` | **home:** [`canonical-source-unification.tactic.yaml`](../../packs/built-in/tactics/canonical-source-unification.tactic.yaml) (WP08) &#8212; "Seam-bypass via stale comment" failure mode: a "can't reuse the seam" comment is a red flag to verify, not a fact to trust. |
| `feedback_lane_base_guard_vs_moving_upstream` | **learned-fact:** [`lane-base-vs-moving-upstream.md`](../../.kittify/memory/lane-base-vs-moving-upstream.md) &#8212; narrow dispatch heuristic: guard a lane base against a fixed rebase-target SHA, not a moving `is-ancestor upstream/main` check. |
| `feedback_no_legacy_resolver_paths` | **already-home:** [`2026-07-01-1-no-legacy-compat-branches-in-resolvers.md`](../adr/3.x/2026-07-01-1-no-legacy-compat-branches-in-resolvers.md) &#8212; the exact rule (require canonical + migrate; forbidden `if <field> is None: <legacy fallback>`) is that ADR's whole subject. |
| `feedback_gate_unmask_cannot_self_validate` | **already-home:** [`quality-and-tech-debt-standing-orders.md`](reference/quality-and-tech-debt-standing-orders.md) &#8212; "A gate-unmask cannot self-validate&#8230; pair every un-mask with a pre-merge full-gate dry-run; never ship a mission-diff-scoped assertion to the main branch." |
| `feedback_execution_state_impl_discipline` | **already-home:** [`030-test-and-typecheck-quality-gate.directive.yaml`](../../packs/built-in/directives/030-test-and-typecheck-quality-gate.directive.yaml), plus directives `025-boy-scout-rule`, `034-test-first-development`, and `041-tests-as-scaffold-not-friction` &#8212; the tagged-and-reduced-tests, ruff/mypy-clean, and fix-don't-rationalize pointers echo existing directives. |

## Corrections surfaced this run

Running this audit against the live, shipped state of the WP01&#8211;WP09
work (rather than trusting the audit's own draft text) surfaced four cases
where the working draft was itself stale or imprecise &#8212; the mission's
thesis proven in miniature, same as Bucket 1's four corrections:

1. **Review-cycle / merge-gate mechanism is event-sourced, not
   frontmatter-based.** The audit's working draft framed
   `reference_merge_review_artifact_invariant` around parsing on-disk
   `review-cycle-N.md` frontmatter. WP01 found the shipped gate
   (`terminal_wp_latest_review_artifact_must_not_be_rejected`) reads the
   reduced status snapshot's event-sourced `review`/`review_result` slots and
   **never** parses on-disk frontmatter; a hand-edited `review-cycle-N.md`
   has zero effect on the gate. `review-gates.md` documents the current
   mechanism, not the retired one the memory described.
2. **Sync-drain gate order corrected**: the drain is `saas_disabled` &rarr;
   `missing_auth` &rarr; `missing_team`, and `spec-kitty sync migrate` is
   **not** one of the three gates &#8212; it is a separate, mostly-obsolete
   legacy-queue command that some older notes mislabelled as "gate 2".
   `sync-drain.md` states this explicitly rather than repeating the stale
   framing.
3. **`reference_sync_identity_form_split`'s #883 citation was a
   mis-citation.** The issue number did not resolve to the identity-form
   split it was attached to in the working draft; rather than carry a
   dangling reference forward, the `.kittify/memory/` note drops it.
4. **`feedback_collect_universe_once_reuse` reclassified from
   `learned-fact:` to `keep-private`.** The audit's working draft proposed a
   `.kittify/memory/` note for this entry, but WP09 (the learned-facts
   seeding WP) did not create one &#8212; the underlying anti-pattern was
   already fixed in code and judged too narrow for a shared note. Routing it
   to `learned-fact:` here would point the manifest's own path-check at a
   file that does not exist; `keep-private` reflects what actually shipped.
