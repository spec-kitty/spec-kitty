---
title: Lanes review claim and lanes create on a protected target
description: Grounding note for the sequenced bugfixes #7589 (review claim empty changeset) and #7632 (lanes create on a protected target).
doc_status: draft
kind: Reference
audience:
- profile: internal/system-architect
  guidance_text: Check the root causes, the chosen fix seams and the dispositioned siblings.
updated: '2026-11-13T00:00:00Z'
---
# Lanes review claim and lanes create on a protected target

Grounding for two sequenced bugfixes, delivered as one pull request with separate commits.
Base: `origin/main` `1fb3b55f`.

## #7589: the review claim fails with an empty changeset

**Reproduced on an unprotected target.** With the `lanes` fixture's protection lifted and the
up-front `in_review` workaround removed from `_review_args`
(`tests/integration/review/test_review_range_acceptance_action.py`), the claim exits 1 with
`safe_commit: nothing to commit for destination_ref='main' (empty changeset)`. So #7632's
refusal does not mask it, and #7589 goes first.

**Root cause.** On a Mission with no coordination branch, `commit_workflow_change`
(`cli/commands/agent/workflow_executor.py`) commits through the legacy leaf
`_commit_via_legacy_safe_commit` (`cli/commands/agent/workflow.py`). The transactional emit has
already committed the claim's rows. The leaf's advisory porcelain pre-check should see the paths
clean and return, but `_resolve_legacy_porcelain_root` picks `.worktrees/<slug>-coord` whenever
that directory exists. The fixture's `lanes` Mission is a re-declared `lanes_with_coord`
Mission, so the coordination worktree is still on disk and does not contain the Mission's paths.
`git status` exits 128, the pre-check answers "not committed", and `safe_commit`'s index
authority then raises `SafeCommitStagedTreeUnchanged`, which the leaf let escape as a failure.
`coordination/commit_router.py::_is_empty_changeset_error` already treats the same type as the
benign no-op it is.

**Fix.** The leaf catches `SafeCommitStagedTreeUnchanged` (the typed signal only, never the
prose) and records the commit that already carries the paths, through the same
`_already_present_receipt_sha` the pre-check arm uses. The protected-branch refusal and every
other `safe_commit` error still raise.

**Residual.** `_resolve_legacy_porcelain_root` still picks `.worktrees/<slug>-coord` by
existence alone, so on a coord-less Mission with such a directory left on disk the pre-check
never short-cuts and each claim costs one extra `safe_commit` staging round. That is harmless
now and belongs to #7633 (coordination-less commits pick their checkout by a raw probe).

## #7632: `create --topology lanes` on a protected target is admitted

**Root cause.** `protected_mint_applies` (`core/mission_creation_decisions.py`) mints a Mission
branch only for `single_branch`. A `lanes` create on a protected target therefore mints nothing,
its scaffold commit is refused, and every later bookkeeping write is refused with
`PROTECTED_BRANCH_REFUSED` (`coordination/policy.py`).

**Fix (operator ruling Q2, 2026-11-13).** Create refuses up front, before any write, with the
named code `LANES_PROTECTED_TARGET_REFUSED` and two remedies: an unprotected target branch, or
`--topology lanes_with_coord`. It does not mint a branch.

**Protection predicate.** The refusal asks the predicate the later bookkeeping refusal asks:
`ProtectionPolicy.is_protected` (configured `protected_branches`, else the defaults, with the
operator hatch). It does not use `is_protected_target` (the #5100 "primary plus configured"
mint rule): with `protected_branches: []` the primary branch is writable for bookkeeping, so a
`lanes` Mission there works and must stay admitted. An owned create also reads the owned
checkout's configuration (the union `ProtectionPolicy.resolve_for_owned` uses).

**ADR.** Recorded as an amendment of ADR `2026-11-06-3` (topology is settled once at first
finalize), which owns create-time topology.

## Discovery

**Similar surfaces.**

| Surface | Disposition |
|---|---|
| `coordination/transaction.py` `commit_idempotent`: the coordination path wraps the same typed no-op into `BookkeepingCommitFailed` after a fail-open pending check | Not reached by #7589 (a `lanes` Mission has no coordination branch). The file is owned by the parallel #7594/#7633 runs; surfaced to the operator, not changed here. |
| `coordination/write_seam.py` `_EMPTY_CHANGESET_PREFIX` does not match the typed message | File separately (post-consolidation write, not status). |
| `cli/commands/implement_claim.py` warns on an already-committed claim bundle | File separately (soft warning). |
| `invocation/executor.py` records the no-op as a refusal | File separately (minor). |
| Coordination root picked by existence only (`tasks_move_task.py`, `tasks_shared.py`, `mission_finalize_planning_pin.py`, `_resolve_legacy_porcelain_root`) | Overlaps #7633 (coordination-less commits pick their checkout by a raw probe). Refs #7633, not changed here. |
| Tests that pin today's `lanes`-on-protected admission (`tests/core/test_mission_create_protected_single_branch.py`, the `protected/lanes/plain` golden, the branch-coverage rows, CLI `--topology lanes --target-branch main`) | In scope: the ruling changes the behavior they pin. |
| Hand-built `lanes` fixtures on protected `main` (`review_range_fixtures.py`, `tests/terminus/lanes_fixture.py`, `coord_topology_fixture.py`) | Unaffected by a create-time refusal. The review fixture is fixed in scope: `_adapt_to_lanes` now builds the admitted shape (`main` un-protected), and `_review_args` claims with `--agent` for every fixture. |
| Test helpers that create `lanes` on protected `main` through `create_mission_core` (`test_concurrent_appenders.py`, `test_add_history_event_log.py`, `test_structured_actor_annotations_6400.py`) | In scope: they un-protect `main` first (`_unprotect_main`), the shape create admits. |
| `lanes_with_coord` review claim on protected `main`: the claim lands on the coordination branch, then a follow-up commit routed to `main` is refused | New defect, filed as #7637. The review fixture keeps a protection lift for `lanes_with_coord` only, citing #7637. |
| `migration/backfill_topology.py` restamps or derives `lanes` with no protected-target check | File separately: a migration of an existing Mission, not create. |

**Tracked issues.** No duplicate of either bug. Refs: #7633 (coordination-less checkout
probe), #3536 (the earlier commit-router fix of the same refusal), #4625 (two branch policies
between create and commit), #5100 (protected-target mint), #7578 (the fixture workaround).
Parent epic #7545.
