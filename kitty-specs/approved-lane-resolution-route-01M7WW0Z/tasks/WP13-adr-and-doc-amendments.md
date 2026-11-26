---
work_package_id: WP13
title: ADR, contract and doc amendments
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
- WP06
- WP07
- WP08
- WP09
- WP10
- WP11
- WP12
- WP14
requirement_refs:
- FR-013
planning_base_branch: fix/approved-lane-resolution-route
merge_target_branch: fix/approved-lane-resolution-route
branch_strategy: Planning artifacts for this mission were generated on fix/approved-lane-resolution-route. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/approved-lane-resolution-route unless the human explicitly redirects the landing branch.
subtasks:
- T051
- T052
- T053
- T054
phase: Phase 3 - Surfaces and proof
history:
- at: '2026-11-20T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: docs/adr/
create_intent:
- docs/changelog/unreleased/5604-approved-lane-resolution-route.fixed.md
execution_mode: code_change
model: ''
owned_files:
- docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md
- docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md
- docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md
- docs/adr/4.x/2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md
- CLAUDE.md
- docs/changelog/unreleased/5604-approved-lane-resolution-route.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP13 – ADR, contract and doc amendments

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `architect-alphonso`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Record the model this Mission shipped (FR-013), so a maintainer can find, from the governing ADRs and CLAUDE.md, why consolidate behaves as it now does. Every point below must be present, accurate to the code **as merged by WP01..WP12 and WP14** (read their final diffs and WP histories first; do not document the plan where the code differs), and pass the terminology and docs checks.

Checklist (the document review checks each line):

1. ADR `2026-10-04-5`: re-review is the sanctioned exit for a conflict between approved lanes; the new claim-time refusal `RESOLUTION_MERGE_UNREVIEWED` (predicate, exemption by the auto-rebase record, remedy, orchestrator-api code and contract version); the residual "Content inside a merge commit" (`:174`) is resolved for merges with own non-bookkeeping content, and what remains open.
2. ADR `2026-09-29-1`: the #7630 trust model (a reviewed merge authors what it brought in from trusted roots: the Mission branch as frozen, the target's pre-run tip, other approved lanes' **approval stamps**, never live tips); the FR-010 fail-closed rule for merge probes; the FR-006 hint (re-review instead of `--dependency-ref` for dropped merges).
3. ADR `3.x/2026-09-19-1`: a narrow reversal of Decision A2 "lane branches are report-only": a lane is restored only from this run's own recorded auto-rebase move, under compare-and-swap, inside the single rollback authority; the new outcome `LANE_MOVED_SINCE_AUTO_REBASE` is not re-baselineable; the residual at `:293-294` is closed.
4. ADR `2026-11-08-2` plus the review-context contract: the review range lists every merge (`--full-history`, no pathspec), and the review context prints a labelled `git show --remerge-diff <sha>` line (or a cannot-show line); C-001 (commands only) kept.
5. The stale-remedy rule of #7285 (A-10): kept, with the approved-lane route and `implement --incorporate <lane>` added (operator ruling DM-01M7WX8AX56E23AXBZRWGNX4EM, option b).
6. CLAUDE.md: the residual sentence about lane auto-rebase merges surviving a rollback is fixed; the new code, the new outcome, the auto-rebase record and the route are added where the surrounding paragraphs describe those systems.
7. A changelog fragment in `docs/changelog/unreleased/`.

## Context & Constraints

- Read first: `.kittify/charter/charter.md`; mission `spec.md` (FR-013 and every FR it cites), `plan.md` IC-09, `research.md` R-01..R-10, `data-model.md`, all four `contracts/*.md`, `squads/01-pre-spec-and-post-specify.md` (the squad 2 dispositions name the ADR gaps), `tasks.md`.
- Then read the merged work: `git log --oneline` on the Mission branch for WP01..WP12 and WP14, each WP's history notes (`spec-kitty agent tasks status`, and the tracer notes the code WPs recorded through `add-history`), and the final code of: `consolidation/approved_bound.py` (the new code and `render_refusals` text), `consolidation/reconciliation_authorship.py` (the shared predicate), `consolidation/reconciliation_claim_types.py` (`unreviewed_merges`), `consolidation/reconciliation_verifier.py` (the hint), `consolidation/git_probes.py` + `consolidation/merge_attribute_guard.py` (FR-010), `lanes/auto_rebase.py` + `lanes/auto_rebase_record.py` (the record), `consolidation/rollback.py` + `state.py` (FR-009), `lanes/stale_check.py` + `lanes/incorporate.py` (route), `review/wp_range.py` + `review/context_block.py` (FR-007), `orchestrator_api/envelope.py` (`CONTRACT_VERSION`), `consolidation/reconciliation_canceled.py` (FR-011 outcome: fixed or ratchet pin).
- **Invariants to state accurately, not weaken in prose**: C-001 (no mechanical attribution of a resolution), C-002 (no new verdict-lifting attestation; the auto-rebase record never exempts anything at the gate), C-003 (the #7307 rule that an unreviewed merge authors nothing stays), C-004 (only an unforced independent review approval restamps), fail closed (probe errors refuse; FR-009 reports and keeps the record).
- **Ownership limits**: this is a `code_change` WP (brief), so it cannot own `kitty-specs/` paths. The review-context contract file lives in another Mission (`kitty-specs/review-context-wp-diff-01M774QF/contracts/review-context-block.md`); do not edit it. Record its amendment inside ADR `2026-11-08-2` (which governs the review range) and point at `review/context_block.py`'s docstring, which WP10 updated. Say so in the amendment text, and record the limitation as a tracer note.
- ADR style: an amendment is a new dated section at the end of the decision history, in the house format of the existing ones (for example `## Amendment 2026-11-07: a lane's own dependency merges are its work (#7307)` in `2026-09-29-1`, `:409-444`). Do not rewrite earlier sections; where an earlier sentence is now false, add a short "(Amended 2026-11-2x, see below)" pointer next to it. Bump the frontmatter `updated:` value. Use today's date of the amendment (the day you write it).
- Terminology: Mission (never "feature"), consolidate / lane consolidation, incorporate, name the sense of "merge" (lane consolidation merge vs. a merge commit on a lane). Never "sync" (except existing identifiers like `lifecycle_sync`). Run the terminology guard.
- Issue references: #5604 (with its recurrence comment), #7754, #7755, #7767, #5721 (merge-commit slice), #7497, #7307, #7285, #7626/#7630 (the trust model: the code docstrings cite #7626; the spec cites #7630; name both once, and use the one the merged code uses afterwards), #7766 and #7324 (out of scope, cross-reference only).

## Branch Strategy

- **Strategy**: set by finalize-tasks
- **Planning base branch**: fix/approved-lane-resolution-route
- **Merge target branch**: fix/approved-lane-resolution-route

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implement command: `spec-kitty agent action implement WP13 --agent claude --mission approved-lane-resolution-route-01M7WW0Z`

## Current documents at HEAD (read before editing)

- `docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md` (368 lines): Decision `:35-142` ("Merge commits are dropped" at `:52`); Residuals `:168-188` ("Content inside a merge commit" at `:174`; "Any new approval ... restamps the lane, forced or not" at `:180`); amendments from `:195` to the 2026-11-18 one at `:345`. Frontmatter `updated: '2026-11-10T00:00:00Z'`.
- `docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md` (568 lines): Amendment 2026-11-07 (#7307) `:409-444`, including "A merge after the approval is not reviewed work (closed in review)"; the newest amendment is 2026-11-12 (#7560) at `:454`.
- `docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md` (816 lines): A2 one snapshot, "**Lane branches are report-only**" `:196-206`; follow-up residual "A stale lane auto-rebased during lane consolidation keeps its merge commit after a rollback (lanes are report-only)" `:293-294`; follow-up 2026-10-31 rebaseline rule `:530-563` (the coordination-anchor rule `:544-550` says a lane that moved during a failed attempt is accepted by the per-lane CAS unless it diverged); `rebaselineable` stricter than `fully_restored` (`:551`ff).
- `docs/adr/4.x/2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md` (735 lines): Amendment 2026-11-12 (#7578) `:582` (review range); Amendment 2026-11-18 (#7726) `:648`.
- `CLAUDE.md`: the stale-lane sentence in "Execution Workspace Strategy" (`:491-493`: "its remedy prints `spec-kitty agent action implement <WP> --mission <handle>` (the lane sync point), never a `cd .worktrees/...` + `git merge` recipe"); the approved-claim paragraph's residual list (`:566`, "content inside a merge commit (strict `xfail`; ...)"); the rollback paragraph (`:572`: "Lane branches (`snapshot_lane_branches`) are report-only: snapshotted, never recorded, never restored." and the residual "lane auto-rebase merge commits ... survive a rollback (#3536, #5371, #5372 out of scope)").
- `docs/changelog/unreleased/README.md`: fragment naming `<id>.<section>.md`, one section per file, entry format and the style/spelling checks.

## Subtasks & Detailed Guidance

### Subtask T051 – ADR 2026-10-04-5 amendment

- **Purpose**: the approved-claim ADR is where `LANE_MOVED_AFTER_APPROVAL` and its siblings are explained; the new code belongs to the same family (`BoundRefusalCode`).
- **Steps**: add `## Amendment 2026-11-2x: an unreviewed resolution merge is refused at claim time; re-review is the exit (#5604, #5721)` with:
  1. **Problem** in three sentences: approved lanes that conflict; the old stale remedy prescribed a hand merge; the gate dropped it as unreviewed (#7307) and refused late, after landing and rollback.
  2. **Decision**: the claim refuses `RESOLUTION_MERGE_UNREVIEWED` before the first mutation when a merge on an approved code lane, beyond the claim base, is reached by none of **its own lane's** approval stamps (the predicate shared with the gate's `_drop_unreviewed_merges`, name the public function WP04 extracted), has no auto-rebase record, and carries at least one non-bookkeeping own path (`merge_own_changed_paths` behind the FR-010 guard). Name where it runs (claim, `--dry-run` as `CLAIM_REFUSED_FORECAST`, `orchestrator-api consolidate-mission` through `approved_bound_refusal`, contract version as merged), its compound order, and its remedy text (copy the final rendered shape from `approved_bound.render_refusals`).
  3. **The auto-rebase record**: `refs/spec-kitty/auto-rebase/<lane-branch>/<merge-sha>`, written by `attempt_auto_rebase` for every merge it makes, read only by this refusal, deleted by the rollback restore and by lane cleanup. It never exempts anything at the gate; a forged ref only changes which message the operator sees (threat model as the event log). A tool merge that auto-resolved a non-bookkeeping conflict is still judged by the gate (spec US3 AS3).
  4. **Re-review is the sanctioned exit**: send back, `implement --incorporate <sibling>` (merges the sibling at its approval stamp), resolve, `for_review`, independent unforced approval that reaches the resolution merge, consolidate. Approach C (mechanical attribution of a resolution) is rejected (operator ruling 2026-11-20).
  5. **Residual updates**: the "Content inside a merge commit" residual (`:174`) is closed for a merge with own non-bookkeeping content (pinned by the converted test in `tests/consolidation/test_approved_bound_residuals.py`, WP05); state what stays open: a merge whose own content is bookkeeping-only, a reviewed novel line in an approved resolution (the review is the guard; FR-007 makes it visible), earlier-release merges without a record are treated as hand merges, and the orchestrator-api "up-front check only" residual (`:179`) where it still applies. Add a pointer "(Amended 2026-11-2x)" after the `:52` sentence "Merge commits are dropped" and after the `:174` residual.
  6. **Confirmation**: name the test files that pin it (WP04, WP05, WP09, WP12 and WP14 tests).
- **Validation**: every code identifier you name exists in the merged code (`grep -rn "<name>" src/`).

### Subtask T052 – ADR 2026-09-29-1 and ADR 3.x 2026-09-19-1 amendments

- **ADR 2026-09-29-1** (`## Amendment 2026-11-2x: the reviewed-merge trust model and fail-closed merge probes (#7630, #5604)`):
  1. Record the #7626/#7630 trust model that the code already implements and the ADR never recorded (squad finding "ADR gap"): `_authoring_merges` lets a merge on an approved lane's reviewed spine author what it brought in only when every non-first parent is reachable from a trusted root (`_trusted_history_roots`: the Mission branch as the claim measures it and as the run froze it, the target's pre-run tip, and other approved lanes' **approval stamps**); never the live Mission branch, never the lane's own stamps. Keep it distinct from #7307's own-dependency-merge rule (SHA-only).
  2. The shared predicate (WP04): one public function decides "own lane's stamps reach this merge", used by the gate and by the claim-time refusal; the additive claim field `unreviewed_merges` (sha, lane, WPs, own paths, own blobs); existing claim fields byte-identical.
  3. FR-010: every merge probe the gate and claim rely on (`n_way_merge_blob`, `merge_own_changed_paths`, the kernel remerge path) runs one batched `git check-attr --stdin merge` and raises `GitProbeError` (so the gate REFUSEs) when the effective merge attribute is set by anything but spec-kitty's registered driver triples (name, command, pattern) or when `merge.default` is configured; covers info attributes, an uncommitted working-tree `.gitattributes`, `core.attributesFile` and a custom driver in any config scope. Say why a sanitized attribute source was rejected (R-06).
  4. FR-006: the un-attributable refusal's hint names re-review instead of `--dependency-ref` when every un-attributable blob is the own-path blob of a dropped merge, and never when a canceled clause is present; `Divergence.describe()` unchanged; `--dependency-ref` laundering stays with #7766.
  5. FR-011 outcome: whether the #7497 shape was red (and fixed by anchoring the canceled lane on its dependency as of its cut) or green (ratchet pin; #7497 closed with the evidence). Read WP11's history note; state exactly one.
- **ADR 3.x 2026-09-19-1** (`### Amendment 2026-11-2x — the rollback restores the run's own auto-rebase lane moves (#7767)`):
  1. Narrow reversal of A2 (`:196-206`): a lane is restored only from this run's `ConsolidationState.lane_rebase_moves[branch] = [before, after]`, now recorded on every auto-rebase merge; compare-and-swap `after -> before` through `restore_branch_ref` inside `rollback.py` (the AST pin `tests/consolidation/test_single_rollback_authority.py` holds); then the lane checkout resync (`resync_checkouts_to_tip`, residue-only; a dirty checkout refuses the resync and is reported, #5638), the lane work-tip ref reset through `lanes/lane_tip.py`, and the auto-rebase record deleted. Every other lane move stays report-only; `post_mutation_refs` never records a lane.
  2. The new outcome `LANE_MOVED_SINCE_AUTO_REBASE` (report line, recovery hint as merged), not re-baselineable, record kept, entry survives the re-baseline; `--abort` reports it.
  3. Close the residual at `:293-294` with a pointer, and note on the coordination-anchor rule (`:544-550`) that a restored lane is back at its pre-run tip, so the per-lane CAS no longer meets the left-over merge.
  4. Red-first evidence: quote the harm WP03 recorded at the base (the actual refusal or FAIL code the next run met).
- **Validation**: both ADRs' frontmatter `updated:` bumped; earlier text untouched except pointers.

### Subtask T053 – ADR 2026-11-08-2 / review-context contract amendment, and the stale-remedy rule

- **ADR 2026-11-08-2** (`## Amendment 2026-11-2x (#5604): the review range lists merge resolutions`):
  1. `resolve_wp_review_range` lists every merge in `base..tip` with `git rev-list --merges --full-history` and no pathspec, because the commit list's default history simplification can drop a merge; the range carries `merges` and `remerge_available`.
  2. The review context prints, per merge, `RESOLUTION MERGE (operator-authored, review these bytes): git show --remerge-diff <sha>`, or the cannot-show line on git < 2.36; the lines sit outside the byte budget like the command lines (ruling Q11); no patch text is rendered (contract C-001 kept).
  3. State that this amends the review-context contract of Mission `review-context-wp-diff-01M774QF` (`contracts/review-context-block.md`) and that `review/context_block.py`'s docstring is the living copy of the shape (WP10 updated it). Name the git-process cost (one more `rev-list`; the version probe only when a merge exists).
- **Stale-remedy rule (#7285, FR-091 A-10)**: record where the rule lives. There is no dedicated ADR for #7285 in `docs/adr/` (only the CHANGELOG and the pinned tests in `tests/lanes/test_stale_remediation_cli_command.py`). Put the rule's amendment in ADR `2026-10-04-5`'s amendment (T051 point 4) as its own paragraph: A-10 is kept (no `git merge`, no `cd .worktrees` in a remedy); for an approved code lane the remedy prints the re-review route with `implement --incorporate <lane>`, ruled by the operator (DM-01M7WX8AX56E23AXBZRWGNX4EM, option b; option a, a raw `git merge <stamp>`, rejected); non-approved callers are unchanged; the incorporate refusal codes WP08 introduced (`INCORPORATE_*`, read the merged module) and its conflict exit behaviour. Mirror it in CLAUDE.md (T054).

### Subtask T054 – CLAUDE.md and the changelog fragment

- **CLAUDE.md** (owned; edit surgically, keep the long paragraphs' structure):
  1. Execution Workspace Strategy, `:491-493`: extend the stale-lane sentence: for an approved code lane the remedy names the sibling lane(s), the auto-rebase halt reason and paths, and prints the re-review route (`move-task <WP> --to in_progress`, `spec-kitty agent action implement <WP> --mission <handle> --incorporate <lane>`, resolve and commit, `for_review`, independent approval, `consolidate`); still never a `cd .worktrees/...` + `git merge` recipe.
  2. The approved-claim paragraph (around `:566`): add `RESOLUTION_MERGE_UNREVIEWED` to the codes, with one sentence on its predicate, the auto-rebase record exemption (claim only, never the gate), and where it runs; update the residual "content inside a merge commit (strict `xfail`; ...)" to say what is closed and what stays.
  3. The rollback paragraph (`:572`): replace "Lane branches (`snapshot_lane_branches`) are report-only: snapshotted, never recorded, never restored." with the narrow rule (restored only from the run's own recorded auto-rebase move; `LANE_MOVED_SINCE_AUTO_REBASE`, not re-baselineable); remove "lane auto-rebase merge commits" from the "survive a rollback" residual list, keeping the rest of that list intact.
  4. Optionally one line in the Consolidation section naming the FR-010 rule (merge probes fail closed on unregistered merge attributes/drivers). Keep CLAUDE.md consistent with the charter; if anything here disagrees with the charter, flag it instead of choosing.
- **Changelog fragment** `docs/changelog/unreleased/5604-approved-lane-resolution-route.fixed.md` (one `fixed` file; the `--incorporate` option is described inside the same entry as the fix's route; if the reviewer wants an `added` entry, that is a second file and an ownership change, so raise it rather than adding it). Format per the README: one or more bullets, bold lead, issue refs, **Before:** / **After:**. Cover: the stale remedy for approved lanes (#7754, #7755); `RESOLUTION_MERGE_UNREVIEWED` at claim time (#5604, #5721); `implement --incorporate`; review context merge lines; rollback restores the run's own lane auto-rebase merges (#7767); merge probes fail closed on clone-local merge attributes and drivers; #7497 outcome; orchestrator-api contract version.

## Test Strategy

Documentation WP: the gates are the docs checks plus the terminology guard. No pytest suite beyond the named gate files.

```bash
uv run --frozen pytest -q tests/architectural/test_no_legacy_terminology.py
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
uv run --frozen python -m scripts.docs.check_spelling
uv run --frozen pytest -q tests/architectural/test_adr_hygiene_6164_retirement.py tests/architectural/test_adr_hygiene_convergence_retirement.py tests/architectural/test_dead_builtin_doc_paths.py
make test-fast
```

Also run `uv run --frozen python -m scripts.docs.check_docs_freshness --help` and run it the way CI does for the files you touched if it applies to `docs/adr/` (read `.github/workflows/ci-router.yml` around the docs job to see the exact invocation). No `make test-full`, no bare `tests/architectural/`.

Accuracy check (the reviewer will repeat it): for every identifier, code, file path and contract version you wrote, `grep -rn` it in `src/` and `tests/` on the merged Mission branch.

## Tracer notes

This WP cannot own `kitty-specs/` paths. Record notes with `spec-kitty agent tasks add-history WP13 --note "<trace: ...> ..."`: the review-context contract living in another Mission's directory (amended through ADR `2026-11-08-2` instead), the absence of a #7285 ADR (rule recorded in ADR `2026-10-04-5`), the #7626/#7630 numbering, and any place where the merged code differs from `plan.md` / `research.md` (document the code).

## Risks & Mitigations

- **Documenting the plan instead of the code.** Mitigation: read the merged diffs and WP histories first; grep every identifier.
- **Over-claiming integrity.** The record is operator-writable and never trusted by the gate; a reviewed novel line lands by design. Say both plainly.
- **Rewriting history.** Amend by appending dated sections and pointers; never edit an older decision's text beyond a pointer.
- **CLAUDE.md drift from the charter.** If the charter and CLAUDE.md disagree after your edit, flag it to the orchestrator; do not resolve silently.
- **Terminology regressions** (`ceremony`, `status-writing`, "feature", "sync"). Mitigation: the guard plus a manual read.

## Residuals to record (analysis A14)

- The review context labels every merge inside the review window "operator-authored", including recorded tool auto-rebase merges. Record this as a documented residual in the ADR 2026-11-08-2 amendment.
- A lane superseded under the 2026-11-24 ruling: lane cleanup keeps its lane-tip ref but clears its auto-rebase records (WP02, `_after_branch_deleted`). If an operator recreates that branch from the kept tip and resumes, its tool merges read as hand merges. This fails closed toward `RESOLUTION_MERGE_UNREVIEWED`. Record it as a residual in the ADR 2026-10-04-5 amendment (reviewer note, WP02 rebase delta 2026-11-25).
- `merge.renormalize=true`: consolidate now refuses a clone with this setting, with a named reason. Mixed Windows/Unix teams often set it for line-ending hygiene. Say this in the operator docs and the ADR 2026-10-04-5 amendment, and name the setting to change. The probes pin it off regardless (WP01 `MERGE_PROBE_CONFIG_PINS`). The refusal is kept, per the reviewer's recommendation on WP01 cycle 3 (2026-11-25), because without it a renormalized merge would surface as unattributable content.

## Further items to document (rulings and review notes of 2026-11-25)

- `merge.renormalize=true`: the named refusal at consolidate is KEPT (operator ruling DM-01M8982NAYZYWKTG4ZQRAFCYRD), together with the probe pin. Document the refusal and its remedy in the ADR amendment and in the user docs.
- Review-window semantics: an approved commit that lies only inside a canceled WP's review window is refused as `CONTESTED_COMMIT`. `--attest-canceled-superseded` lifts the refusal. This Mission keeps that behaviour (operator ruling DM-01M8982ZZ67KACF9KEQDD1SDZ2); a separate issue is filed. Document it as today's rule.
- `--incorporate` is "at least as strict as consolidate", not exactly as strict. The only closed-world anchors are attestation stamps, and `planning_prefix=None`. Both choices fail toward refusal (WP08 review 3).
- Usability gap: only `spec-kitty consolidate --attest-canceled-superseded` can record the attestation that `--incorporate` needs, and running it also starts a consolidation. Document the gap (WP08 cycle 3). A follow-up is filed as #7866.
- Accepted behaviour change (WP06 review 1): a recorded tool merge dropped as unreviewed, carrying auto-resolved content, now gets the re-review hint. When only some items are covered, the scoped `--dependency-ref` sentence follows (WP06 cycle 2).
- `contracts/stale-remedy.md` is superseded by main's #7754 reopen step (`move-task <WP> --to planned --review-feedback-file <file>`) and by WP07's `--incorporate` refresh line (scope ruling DM-01M88RZDBP57ZTYJHC5NP0ZH4R). Update the contract to match the landed text.

## Further items to document (review rulings, 2026-11-25, second batch)

ADR 2026-10-04-5 amendment:
- `RESOLUTION_MERGE_UNREVIEWED` judges every merge a lane reaches through any parent, not only its first-parent spine (WP05 cycle 2). A merge on another bound lane's own spine is left to that lane.
- Named sub-case: a merge inside a canceled WP's window is refused under the same code. Re-approval cannot lift it; the remedy is to rebuild the lane (reviewer ruling, WP05 review 1).
- Asymmetry for one-side conflict resolutions (reviewer ruling, 2026-11-25):
  - The gate's attribution axis treats a byte-for-byte one-side resolution as non-content (#7854/#7855 hotfix). A dropped approved change belongs to the presence axis: `APPROVED_CONTENT_MISSING`, pinned by `test_one_side_merge_dropping_an_approved_edit_fails_approved_content_missing`. By design (#5571) the presence axis judges only paths the landing side left alone; when the landing side also edited the path, the gate still FAILs, through the unattributable axis.
  - The claim check refuses the same merge with `RESOLUTION_MERGE_UNREVIEWED`, naming it ("The merge kept one side of a conflicted path; the other side's change is dropped."), because it is an unreviewed resolution decision.
  - The claim check is the stricter of the two and runs first, so the combined outcome fails closed.
- Addendum 2 result: a forged auto-rebase record skips the claim-time refusal, but the gate still FAILs attribution and the target is restored (defence in depth).
- The residual "content inside a merge commit" (`:174`) is closed for merges that carry their own non-bookkeeping content.

ADR 2026-09-19-1 amendment and CLAUDE.md rollback paragraph:
- Lanes are no longer purely "report-only". A lane is restored only from the run's own recorded and verified auto-rebase move: a 2-parent merge whose first parent is `before`, named by WP02's durable record. The restore is a compare-and-swap that refuses when a checkout is dirty. An unverified move is reported as `UNCHANGED_BY_RUN`; a probe error is reported as `NOT_RESTORED`.
- New outcome `LANE_MOVED_SINCE_AUTO_REBASE`. It counts as OK for `fully_restored`, so `--abort` can finish, but it is not re-baselineable, so its record stays.
- Residual: a rollback killed between a lane restore and saving the record leaves a stale entry. A second `--abort` clears it, and lane cleanup keeps the lane (fails closed).
- Remove "lane auto-rebase merge commits" from the CLAUDE.md "survive a rollback" residual list.

Stale remedy, #7861 and the orchestrator path (ADR and CLAUDE.md):
- Replace the CLAUDE.md #7755 sentence (sibling branch "to `git merge`") with the `implement <WP> --mission <m> --incorporate <lane> --agent <agent>` route at the sibling's approval stamp (scope ruling DM-01M88RZDBP57ZTYJHC5NP0ZH4R).
- Every printed `implement` line carries `--agent`.
- #7861 / T050 reversal (operator ruling DM-01M89KDT5DZQ4DX6ZFX54HY3J3): REVIEW_CYCLE is a COORD-partition kind, so `move-task --to planned --review-feedback-file` now commits its evidence to the coordination branch on a protected-main coordination Mission. With no coordination surface it still fails closed.
- The orchestrator-api `consolidate-mission` path has no rollback door. Lanes consolidated before a refusal stay on the Mission branch, and the re-run is `orchestrator-api consolidate-mission` (or the host `consolidate`). The shared stale text says rolling back "can" remove the change (WP09 review).
- `--incorporate` attribute-source residuals (WP07 review): the attributes are read from the Mission branch tip, not the pre-run target tip. A Mission-branch move between that read and the merge only affects honouring an already-reviewed union.

## Further items to document (third batch; reviewer blocking checklist for WP13, 2026-11-25)

The reviewer checks each item below as blocking. These items are additions; the two batches above still apply.
- **`.gitattributes` fold.** The tool's auto-rebase merge honours `.gitattributes` committed on the lane (`merge=union`, `-merge`, `binary`). So a tool-recorded merge counts as exempt from `RESOLUTION_MERGE_UNREVIEWED` only when two things hold: the FR-010 guard passes, and the `merge` attributes at the merge and at each parent equal those at the pre-run target tip (WP05 binding addendum 1, committed-tree-only rule, operator ruling (a)). Document this in the FR-010 section of ADR 2026-09-29-1 and in the ADR 2026-10-04-5 amendment.
- **Squash, cherry-pick and fast-forward residuals** (#7497, WP11). When a re-approved dependency lane's content reaches the target through a fast-forward, a `merge --squash` or a cherry-pick, the canceled WP's change lands as approved content. Only the re-approval guards it, by reviewing that content. Record this residual in the ADR 2026-09-29-1 amendment.
- **Octopus probe/print disagreement** (WP10). The tool's merge probe treats octopus merges as unjudgeable (fail closed). The printed `git show --remerge-diff` command shows them on current git, so the probe and the reviewer's command can disagree depending on the git version. Record this in the ADR 2026-11-08-2 / review-context amendment.
- **Superseded-lane record clearing** (WP02 delta). Lane cleanup keeps a superseded lane's lane-tip ref but clears its auto-rebase records. If the branch is recreated from the kept tip and the run resumed, its tool merges read as hand merges, which fails closed toward `RESOLUTION_MERGE_UNREVIEWED`. The second batch already lists this item; this entry confirms it is on the blocking list.
- **Dependent-lane route gap, deferred to #7880** (operator ruling 2026-11-26). When a stale lane depends on the sibling it must incorporate, the route's first `implement` re-entry runs the dependency self-heal before `--incorporate`. That self-heal merges the dependency's live tip, conflicts with `DEPENDENCY_LANE_MERGE_CONFLICT`, and asks for a manual merge. Record this as a residual in the ADR 2026-10-04-5 amendment, and in the operator docs for the stale remedy, with the workaround: follow that message, then continue the printed route. State that the residual affects usability, not integrity: a post-approval commit on the dependency lane is still refused by that lane's own bound check (`LANE_MOVED_AFTER_APPROVAL`), and the dependent lane's re-approval must cover the manual merge (WP14 review).
- Each of these items, and each item of the two earlier batches, must appear in the landed ADR or doc text. In the WP13 review hand-off, give a checklist that maps every item to its file:line.

## Review Guidance

- Check each of the seven checklist points above against the merged code (squad 2 dispositions in `squads/01-pre-spec-and-post-specify.md`: FR-013 must cover 2026-10-04-5, 2026-09-29-1, 2026-09-19-1, 2026-11-08-2 plus the contract, the #7285 rule and the CLAUDE.md residual sentence).
- Anti-fake checks from `squad2/reviewer-renata.md` relevant to documentation: the FR-005 record must be described as never exempting at the gate (trust boundary stated, no forgery-resistance claim); FR-009 must be described as restoring only from the run's own recorded move, never from `post_mutation_refs`; FR-011 must state exactly one outcome (fixed, or ratchet pin with #7497 closed) matching WP11's evidence.
- The changelog fragment passes the style and spelling checks and names the issues.
- The terminology guard passes; no "feature" for Mission, no bare "routing" or "residue" without its sense.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP13 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP13 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
