---
work_package_id: WP03
title: ADR set - short-lived checkouts, cleanup amendment draft, worktree-free coordination write
dependencies: []
requirement_refs:
- FR-020
- FR-038
- FR-080
- FR-081
- FR-082
- FR-083
- FR-084
- C-003
- C-005
- C-007
- C-016
- SC-010
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
- T015
- T016
phase: Phase 1 - Governing ADRs
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: docs/adr/
create_intent:
- kitty-specs/lane-worktree-model-hardening-01M6QY1M/upstream/adr-2026-11-06-1-amendment-draft.md
- docs/adr/4.x/2026-11-06-4-coordination-branch-written-by-commit.md
- docs/adr/4.x/2026-11-06-5-gates-over-worktree-less-coordination.md
- docs/adr/4.x/2026-11-06-6-committed-ledger-is-the-coordination-blob.md
execution_mode: planning_artifact
model: ''
owned_files:
- docs/adr/3.x/2026-04-03-1-execution-lanes-own-worktrees-and-mission-branches.md
- kitty-specs/lane-worktree-model-hardening-01M6QY1M/upstream/adr-2026-11-06-1-amendment-draft.md
- docs/adr/4.x/2026-11-06-4-coordination-branch-written-by-commit.md
- docs/adr/4.x/2026-11-06-5-gates-over-worktree-less-coordination.md
- docs/adr/4.x/2026-11-06-6-committed-ledger-is-the-coordination-blob.md
- docs/adr/4.x/2026-10-22-1-the-java-write-service-is-the-canonical-event-writer.md
role: implementer
tags: []
task_type: plan
tracker_refs: []
---

# Work Package Prompt: WP03 - ADR set: short-lived checkouts, cleanup amendment draft, worktree-free coordination write

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `architect-alphonso`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP03 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Objectives & Success Criteria

Four record groups (S3 #7279, S5 #7280, S9 #7284). All Proposed (C-016); options the rulings leave open stay open with a recommendation (A-12).

1. FR-020: amendment to ADR `2026-04-03-1` Core Decision 3 (lane branch long-lived, lane checkout held for one workflow action).
2. FR-038: `upstream/adr-2026-11-06-1-amendment-draft.md` for the #7275 owner (the S4 ADR lives only on #7275).
3. FR-080 to FR-082: three Proposed core ADRs C-1, C-2, C-3.
4. FR-083/FR-084: the D-6 amendment on ADR `2026-10-22-1` naming the records and adding step 4a, cross-linking the final spec-kitty-events ADRs.

SC-010: every ADR `2026-10-22-1` D-6 bullet maps to exactly one of the five records (C-1, C-2, C-3, events 0007, events 0008) plus the amendment, and each record names its confirmation tests.

## Context & Constraints

- Read: charter; `spec.md` User Stories 6-8, FR-020 to FR-022, FR-030 to FR-039a, FR-080 to FR-084, C-003 to C-007; `research.md` R-5, R-9, R-10; `data-model.md` §4, §6; `upstream/doctrine-and-write-service-adr-map.md`; decisions DM `01M6QY371KRY5XXQMDQ4WZR1YE` (write-service ADRs), `01M6QY3BFCGCA7CXE4TZ9W70WH` (short-lived checkouts), `01M6QY3G2XHBENKNJBK98Q5TF8` (cleanup owner), `01M6QY3MJVZV3GJXJQBPED6NRG` (destructive authority), `01M6QY4B7P4T68TE7JE30FRJV6` (S5 seam).
- **spec-kitty-events ADRs are final** (sibling session, branch `issue-7284-coordination-ref-write-adrs` in spec-kitty-events): `docs/adr/0007-write-service-commits-coordination-status-by-ref.md` and `docs/adr/0008-read-service-reads-coordination-ledger-from-git-objects.md`. Do NOT write or copy them (C-003: spec-kitty-events is read-only here). Link them by repository + path + branch. If `/home/user/spec-kitty-events` is checked out, read them there (`git -C /home/user/spec-kitty-events show origin/issue-7284-coordination-ref-write-adrs:docs/adr/0007-...md`).
- Events contract facts to cite (mission-write `1.0.1-SNAPSHOT`): new codes `COORDINATION_REF_MOVED`, `COORDINATION_REF_CHECKED_OUT`, `COORDINATION_LEDGER_UNREADABLE`; `WriteSurface` `coordination_transaction_append` is replaced by `coordination_ref_commit`; `checkout_append` narrows to the repository root checkout only.
- C-005: S4 (#7264) and S10 (#7265) are consumed, not designed. C-2 cites #7274's late-window pass by reference.
- C-007: no lease implementation; FR-020 records it as follow-up.
- ADR numbers fixed: `2026-11-06-4`, `-5`, `-6`.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T011 - Amend ADR 2026-04-03-1 Core Decision 3

- Append `## Amendment 2026-11-06: lane branches are long-lived, lane checkouts belong to one workflow action` to `docs/adr/3.x/2026-04-03-1-execution-lanes-own-worktrees-and-mission-branches.md`. It must record (FR-020): acquire and release points (implement/review action boundaries); releasing commits or refuses; the lane tip is recorded before a guarded removal; attached (not detached) checkouts so the lane-tip hook fires; re-entry (`spec-kitty agent action implement <WP>`); harness working directories across turns; the review lock outside the checkout; auto-rebase without a held checkout; migration of existing checkouts; confirmation criteria citing WP08 (`tests/specify_cli/lanes/test_for_review_gate_parity.py`) and WP09 (`tests/architectural/test_lane_checkout_single_seam.py`, `tests/lanes/test_lane_checkout_helper.py`). State that the one lane-checkout helper `open_lane_checkout` (WP09) is the future lease acquire, and that the lease implementation is a follow-up Mission (C-007).

### Subtask T012 - ADR 2026-11-06-1 amendment draft [P]

- Create `kitty-specs/lane-worktree-model-hardening-01M6QY1M/upstream/adr-2026-11-06-1-amendment-draft.md`, a ready-to-paste section for the #7275 owner. It extends scope to consolidation cleanup, pr-mode cleanup and the prune backstop for Mission lanes, and adds: the O3-local landing proof (target at the gate-passed tip `reconciliation_passed_target_sha`; relaxes `_assert_named_landing_ref`); "probe unavailable means keep and report" (A-11, NFR-008); the residue versus never-`--force` rule; a named tool-owned scratch exemption (`.kittify/runtime/merge/<id>/workspace`); lane-tip and tombstone (`refs/spec-kitty/discarded/*`) ops as guarded; the `clear_tip` data-loss fix stays in S5; deferred sites (allocation recut). Include a short header: who lands it, after which PR, binding target `guarded_landed_removal(repo_root, LandedRemoval(...), context=, processes_in=, absorbed=)`.

### Subtask T013 - Core ADR C-1: coordination branch written by commit [P]

- `docs/adr/4.x/2026-11-06-4-coordination-branch-written-by-commit.md` (FR-080). Content:
  - the coordination branch stays the lifecycle home and is written by commit with no coordination worktree (write-service migration step 4, #6117);
  - covers every coordination-partition kind (events, notes, trace, issue matrix, decision artefacts) and `status.json` handling (options + recommendation);
  - ref read contract: links WP01's ADR (`2026-11-06-2`);
  - **retired CLI-side codes**: `COORD_STATUS_SURFACE_DIVERGED`, `COORD_STATUS_SURFACE_UNREADABLE`, `BOOKKEEPING_WORKTREE_MISSING`, `FALLBACK_COORD_WORKTREE_UNRESOLVED` and `COORDINATION_WORKTREE_UNMATERIALIZED` retire with the worktree (state when: at step 4a, not now);
  - events-side contract additions it relies on (cite ADR 0007): `COORDINATION_REF_MOVED`, `COORDINATION_REF_CHECKED_OUT`, `COORDINATION_LEDGER_UNREADABLE`; `coordination_ref_commit` replaces `coordination_transaction_append`; `checkout_append` narrows to the repository root checkout;
  - drain-and-remove migration of existing coordination worktrees under the destructive guard (C-004);
  - confirmation tests (named as future tests, marked "to be written by the step-4 Mission").

### Subtask T014 - Core ADR C-2: gates over a worktree-less coordination branch [P]

- `docs/adr/4.x/2026-11-06-5-gates-over-worktree-less-coordination.md` (FR-081): ref-reading gates unchanged (approval bound, claim, attribution, for_review per WP08); the late window reads a pinned ref, citing S10's #7265 pass (#7274) without re-deciding; the fence between service writes and consolidation (options + recommendation); how resume and rollback lose the coordination checkout role (`resync_checkouts_to_tip`, `pre_mutation_coord_sha`, resume-recovery checkout roles).

### Subtask T015 - Core ADR C-3: committed ledger is the coordination blob [P]

- `docs/adr/4.x/2026-11-06-6-committed-ledger-is-the-coordination-blob.md` (FR-082): amends the publication seam and the read API pull (ADR `2026-10-01-2`) to read git objects for coordination Missions; the `events tail` cursor gets a source ref (options: commit SHA vs blob offset; recommend one); cite events ADR 0008 for the read service; JGit vs subprocess left open (A-12).

### Orchestrator-mandated points (spec-kitty-events PR #215) - record each in C-1, C-2, C-3 or the D-6 amendment

1. **Rollout ordering** (C-1 and the D-6 amendment): `coordination_ref_commit` goes live only in the same release as both C-1's artefact rule (notes / trace / issue-matrix / decisions / byproducts, #7266) and the drain plus removal of existing coordination worktrees (migration steps 4 and 4a together). Otherwise every existing coordination Mission gets `COORDINATION_REF_CHECKED_OUT`, because there is no Python fallback writer (ADR `2026-10-22-1` D-5).
2. **destinationRef** (C-1): ADR `2026-10-27-1` D-3 keeps `destinationRef` null today; for `coordination_ref_commit` it becomes required and non-empty. `transition_unit_from` must set it and use a tree-relative `missionDirectory`.
3. **Oracle fallback parity** (C-3): the oracle fallback (`probe_coord_state` UNMATERIALIZED -> primary dir) changes for Java/Python parity on a missing ref (events ADR 0008 D-1). Tie it to WP01's read contract (a missing ref is a typed error, not a primary-dir read).
4. **Write fence** (C-2): the fence can rely on the compare-and-swap alone. Status commits run with an emptied `core.hooksPath`. A held ref lock maps to `SERVICE_BUSY`, a deleted ref to `COORDINATION_BRANCH_DELETED`, any other move to `COORDINATION_REF_MOVED`. Present this as the recommended option (A-12) with the alternatives considered.

Cite the events draft as spec-kitty-events PR #215 alongside the branch reference.

### Subtask T016 - D-6 amendment, mapping table, links

- Append `## Amendment 2026-11-06: D-6 records and step 4a` to `docs/adr/4.x/2026-10-22-1-the-java-write-service-is-the-canonical-event-writer.md`: step 4a (coordination writes by commit; coordination worktree retired); a table mapping each D-6 obligation bullet (quote each one) to exactly one record (C-1, C-2, C-3, events 0007, events 0008) with its confirmation tests (SC-010).
- Cross-link C-1/C-2/C-3 to each other and to the events ADRs (repository `spec-kitty/spec-kitty-events`, branch `issue-7284-coordination-ref-write-adrs`).

## Validation

```bash
cd /home/user/spec-kitty
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
git diff --check
```

Plus any docs frontmatter/link validator under `scripts/docs/`. SC-010 self-check: every D-6 bullet appears exactly once in the mapping table.

## Tracer files

Append to `kitty-specs/lane-worktree-model-hardening-01M6QY1M/traces/{tooling-friction,approach,design-decisions}.md` (`- **[YYYY-MM-DD][implement WP03] ...**`), or return the lines in your completion summary if your workspace must not change Mission files.

## Risks & Mitigations

- Writing into spec-kitty-events: forbidden (C-003); link only.
- Re-deciding S4/S10: cite, never redesign (C-005).

## Review Guidance

- SC-010 mapping complete; retired codes and events codes listed in C-1; amendment draft carries every FR-038 element; all Proposed; appended sections only.

## Definition of Done

- Six owned files written; terminology guard green.

## Progress & Status

- `spec-kitty agent tasks move-task WP03 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks mark-status T011 T012 T013 T014 T015 T016 --status done --mission lane-worktree-model-hardening-01M6QY1M`
