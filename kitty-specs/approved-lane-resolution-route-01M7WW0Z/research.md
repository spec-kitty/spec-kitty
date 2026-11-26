# Research: Approved-lane conflict resolution route

Inputs:
- the pre-spec squad (squads/01-pre-spec-and-post-specify.md);
- the post-specify brownfield squad reports;
- the operator rulings of 2026-11-20;
- code at `main` 6ed0494ef.

Format per decision: Decision / Rationale / Alternatives considered.

## R-01: How the route incorporates the sibling lane (FR-001)

- **Decision**: operator ruling DM-01M7WX8AX56E23AXBZRWGNX4EM (2026-11-20) selected option (b): extend the canonical lane sync point.
  - Command: `spec-kitty agent action implement <WP> --mission <m> --incorporate <lane>`.
  - It merges the named sibling lane at its newest approval stamp into the lane checkout (new module `lanes/incorporate.py`; `lanes/lifecycle_sync.py` is unchanged). On a conflict it exits with a distinct non-zero code (operator ruling).
  - It stops on a conflict and leaves the merge in progress for hand resolution.
  - It refuses when the sibling has no approval stamp, or the stamp is not on the sibling branch.
  - The remedy prints, in order:
    1. the send-back command (`approved_bound.move_back_command`);
    2. `implement --incorporate`;
    3. a resolve-and-commit instruction;
    4. the for_review move;
    5. an independent review approval;
    6. `consolidate --mission <m>`.
- **Rationale**:
  - The rollback restores the Mission branch, so the existing sync point (merging the Mission branch) brings in nothing (#7755).
  - `_authoring_merges` trusts a second parent only when another lane's approval stamp reaches it, so the sibling must be merged at its stamp, not its live tip.
  - Option (b) keeps the #7285 A-10 rule: no raw `git merge` and no `cd .worktrees` in a remedy.
- **Alternatives considered**: (a) amend A-10 for approved code lanes and print a raw `git merge <stamp-sha>`. This is smaller, but it reverses a pinned rule and is not a canonical surface.

## R-02: Naming the sibling lane(s) and the halt reason (FR-002, FR-003)

- **Decision**:
  - `consolidate_lane_into_mission` returns the auto-rebase report instead of discarding it.
  - `StaleCheckResult` gains `halt_reason`, `conflicted_paths` and `sibling_lanes`.
  - `phase_advance` computes the siblings: the lanes consolidated earlier in this run whose pre-run tips reach the commits that changed the overlapping paths. It uses `run.state.pre_mutation_refs` / the claim's lane tips.
  - It passes the siblings, plus `approved_wp_ids` from `run.approved_wp_set`, into the pure renderer.
  - FR-003 reasons: `conflict` (with the exact Manual-classified paths), `no_lane_checkout` (`_try_auto_rebase_if_stale` returns early), and `merge_in_progress` (`_abort_with_failure` left the merge).
- **Rationale**: `stale_check` stays pure and status-free. The data comes from the run, which already knows the lane order and tips. A three-lane control pins exact-set naming.
- **Alternatives considered**: keep a ref to the in-run Mission tip (rejected by the operator, default (a) of DM-01M7WW1RVG4TQ9S2CABCCVK9G9).

## R-03: The auto-rebase record (FR-005)

- **Decision**:
  - `lanes/auto_rebase.attempt_auto_rebase` is the single writer for consolidate, the orchestrator-api (through `consolidate_lane_into_mission`) and the implement sync point (`lifecycle_sync`).
  - It writes `refs/spec-kitty/auto-rebase/<lane-branch>/<merge-sha>`, pointing at the merge commit, immediately after it creates the merge commit.
  - FR-004 treats a merge as tool-made only if such a ref exists and points at that exact SHA.
  - Refs are deleted when the rollback undoes the merge (IC-02) and when lane cleanup removes the lane branch.
  - The record is never read by the reconciliation gate (C-002 / C-003).
  - The per-run `ConsolidationState.lane_rebase_moves` stays the rollback's CAS source (it carries the `before` tip). It is now recorded on every auto-rebase merge, not only on `lane_result.success`.
- **Rationale**:
  - A durable ref outlives `--abort`, re-baseline and a fresh run.
  - It covers every writer uniformly.
  - It is checked by SHA, not by message or parent shape, so a message-forged merge and a hand merge of the Mission branch into the lane are not exempt.
  - Threat model: deliberate local edits to refs or `state.json` are out of model, as for the event log. The gate never trusts the record, so a forged ref only changes which message the operator sees; the gate still refuses unreviewed own content.
- **Alternatives considered**:
  - Extend only `lane_rebase_moves`: cleared by re-baseline and `--abort`, absent on a fresh run, in-memory for the orchestrator-api.
  - A parent-shape check: forgeable by the same hand merge the old remedy prescribed.
  - Commit-message matching: forgeable.

## R-04: The FR-004 predicate (one authority)

- **Decision**:
  - Extract from `reconciliation_authorship._drop_unreviewed_merges` a public predicate, "this merge is reached by one of its own lane's approval stamps".
  - `_drop_unreviewed_merges` and a new `approved_bound.unreviewed_resolution_merges(...)` both use it.
  - The new function runs from `_approved_bound_verdict` after tiers 1 and 2. That makes it reachable from the CLI claim, `--dry-run` and `reconciliation.approved_bound_refusal` (the orchestrator-api pre-check).
  - A merge is refused when all of these hold:
    - it is on an approved code lane;
    - it is beyond the claim base;
    - it is not reached by its own lane's stamps;
    - it has no auto-rebase record;
    - `merge_own_changed_paths` (guarded by R-06) lists at least one non-bookkeeping path.
  - New code: `BoundRefusalCode.RESOLUTION_MERGE_UNREVIEWED`.
  - `content_commits` is unchanged.
- **Rationale**:
  - The squad showed that two "reviewed" definitions disagree on the three-lane case, and a shared predicate prevents that.
  - Changing `content_commits` would change tier 2 and the gate re-check, and would refuse the run's own merges at gate time.
- **Alternatives considered**:
  - Un-skip merges in `content_commits`: wide blast radius.
  - Reuse `lane_exempt_commits` anchors: these are other lanes' stamps, so the result disagrees with the gate.

## R-05: Rollback restores the run's own lane moves (FR-009)

- **Decision**:
  - In `rollback.py`, for each `lane_rebase_moves[branch] = [before, after]`:
    - restore `after -> before` with compare-and-swap through `restore_branch_ref`;
    - then `resync_checkouts_to_tip` for the lane checkout;
    - reset `refs/spec-kitty/lane-tip/<branch>` through `lane_tip.py`;
    - delete the auto-rebase ref.
  - If the lane is no longer at `after`, report the new outcome `LANE_MOVED_SINCE_AUTO_REBASE` (not restored, record kept, not re-baselineable).
  - Every other lane move stays report-only.
  - Re-pin `test_lane_branches_are_report_only_even_with_a_recorded_post_tip` and `test_record_never_records_a_lane_branch` to the narrow rule. Add a test that a non-recorded lane move is still report-only.
  - Red first: reproduce at the base the harm on the next run. The left-over merge is either refused or fails the gate; record the actual code. The squad found that the `--resume` lane-tip CAS accepts descendants.
- **Rationale**: the single rollback authority (AST pin) holds. The ADR 2026-09-19-1 A2 reversal is limited to the tool's own recorded move.
- **Alternatives considered**: teach `--resume` to tolerate the merges (rejected by the operator, default (b)).

## R-06: The effective-attribute guard (FR-010)

- **Decision**:
  - In `git_probes`, before `n_way_merge_blob` attributes a fold and before `merge_own_changed_paths` reports paths, run one batched `git check-attr --stdin merge` over the paths involved (all changed paths of the merge for the remerge probe).
  - Correction from tasks authoring: plain `set` is safe (git's built-in merge). `text` and `binary` are NOT safe on their own, because a configured `merge.text.driver` or `merge.binary.driver` overrides the built-in (reproduced). A committed built-in value is decided by the operator question on committed attributes (default (a): honoured only when `check-attr --source <pre-run target tip>` agrees with the effective value and no driver is configured for that name; git < 2.40 refuses).
  - Refuse (probe error, fail closed) when the effective `merge` attribute is set to anything other than unspecified, unset or `set` (or an honoured committed built-in, above), unless both hold:
    - the value names a spec-kitty registered driver (`lanes/consolidation._MERGE_DRIVERS`) and the path matches that driver's registered pattern;
    - the configured `merge.<name>.driver` command equals the registered command.
  - Also refuse when `merge.default` is configured.
  - `check-attr` covers `info/attributes`, the working-tree and uncommitted `.gitattributes`, `core.attributesFile` and `GIT_ATTR_SOURCE`.
  - Use or add a small kernel git helper only if none exists.
- **Rationale**:
  - The squads reproduced `merge=union` and custom-driver bypasses of both `merge-tree` and `show --remerge-diff`.
  - Allowing only the registered triples keeps spec-kitty's own runs working.
- **Alternatives considered**:
  - Run the probes with a sanitized attribute source (`--attr-source` / empty config): this would also disable spec-kitty's own drivers and diverge from the landing merge, which is run with them.
  - Refuse whenever any attribute is set: refuses every repository.

## R-07: Reconciliation hint (FR-006)

- **Decision**:
  - Add a claim field `unreviewed_merges: tuple[UnreviewedMerge, ...]` (sha, lane_id, wp_ids, own_paths, own_blobs), populated where `_drop_unreviewed_merges` drops a merge. The field is additive; existing fields stay byte-identical.
  - `_with_attribution_hint` shows the re-review hint instead of the `--dependency-ref` hint when every un-attributable blob in the divergence is one of those merges' own-path blobs.
  - It does not show the hint when the divergence also carries a canceled clause (N4).
- **Rationale**:
  - Once FR-004 exists, this shape reaches the gate only for tool merges with own content, merges made during a run, or frozen claims, so it is tested at renderer level.
  - The hint channel is the existing one, and `describe()` is unchanged.
- **Alternatives considered**: branch on `path_contributions` counts. That is too coarse: it would also fire for genuinely foreign content on a shared path.

## R-08: Review context merge lines (FR-007)

- **Decision**:
  - `resolve_wp_review_range` lists the merge commits in the range with `git rev-list --merges --full-history <base>..<tip>`; no pathspec simplification drops merges.
  - The range object carries them.
  - `context_block` prints, after the range commands, one labelled line per merge: `RESOLUTION MERGE (operator-authored, review these bytes): git show --remerge-diff <sha>`.
  - When `remerge_diff_available` is false, it prints a "cannot show the resolution on this git" line.
  - Review-context contract C-001 (commands only, no patch text) is kept, and its text is amended to name the new line.
- **Rationale**: the renderer stays pure, and `wp_range` stays the range owner.
- **Alternatives considered**: render the patch bytes inline. That breaks C-001 and the byte budget.

## R-09: #7497 (FR-011)

- **Decision**:
  - Write a red-first test with `build_canceled_lane_on_approved_dependency`. Steps: A approved; C fully canceled and merged into A; A re-approved by an unforced review whose stamp descends from that merge; fresh consolidate.
  - Assert the preconditions. Expect `CANCELED_REACHABLE_VIA_DEPENDENCY`.
  - Likely mechanism: `_fully_canceled_lane_own_commits` anchors C on A's live tip (`reconciliation_kernel.py:214`), so C's own commits become empty once A merges C. The fix anchors C on A as of C's cut (C's lane base or first-claim stamp; a merge-base equals C's tip once A merged C). A second candidate mechanism is the first-parent-only `_carrier_spines` with a `--no-ff` merge; the WP identifies which applies first.
  - If the test is green at the base, keep it as a ratchet pin and close #7497 with that evidence.
- **Rationale**: the operator ruled "fold, fix included", and this is red first.
- **Alternatives considered**: none. This is a probe.

## R-10: The orchestrator-api stance

- **Decision**:
  - `orchestrator-api consolidate-mission` gets FR-004 through `approved_bound_refusal`. It lists the new code in `data.preflight_error_codes` and bumps `CONTRACT_VERSION` 1.29.0 → 1.30.0.
  - Its stale-lane remedy uses the same renderer. It passes `approved_wp_ids`, so the approved-lane route is printed there too.
  - It has no attestation flag (unchanged).
- **Rationale**: one renderer, and the contract versioning rule C-007.
- **Alternatives considered**: keep today's remedy text on the orchestrator-api. That would be a second wording, which C-006 forbids.
