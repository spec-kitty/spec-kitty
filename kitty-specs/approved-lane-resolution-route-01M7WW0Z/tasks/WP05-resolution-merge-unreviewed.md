---
work_package_id: WP05
title: Claim-time RESOLUTION_MERGE_UNREVIEWED
dependencies:
- WP01
- WP02
- WP04
requirement_refs:
- FR-004
- FR-005
- FR-012
- NFR-001
- NFR-002
- C-002
- C-003
planning_base_branch: fix/approved-lane-resolution-route
merge_target_branch: fix/approved-lane-resolution-route
branch_strategy: Planning artifacts for this mission were generated on fix/approved-lane-resolution-route. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/approved-lane-resolution-route unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approved-lane-resolution-route-01M7WW0Z
base_commit: 28452d1f50373f51506ed1127d3f5fc08b887347
created_at: '2026-11-25T09:40:04.170807+00:00'
subtasks:
- T023
- T024
- T025
- T026
- T027
- T028
phase: Phase 2 - Behaviour
history:
- at: '2026-11-20T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_resolution_merge_unreviewed.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/approved_bound.py
- src/specify_cli/consolidation/reconciliation_bound.py
- tests/consolidation/test_resolution_merge_unreviewed.py
- tests/consolidation/test_approved_bound_residuals.py
- tests/consolidation/test_dependency_merge_attribution_7307.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 - Claim-time RESOLUTION_MERGE_UNREVIEWED

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
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

Consolidate (and `--dry-run`, and `orchestrator-api consolidate-mission` through the same public entry point) refuses **before any mutation**, with the new approved-bound code `RESOLUTION_MERGE_UNREVIEWED`, when a merge commit on an approved code lane:

1. is beyond the claim base (not already on the target's pre-run tip);
2. is reached by **none of its own lane's** approval stamps (the predicate WP04 extracted from `_drop_unreviewed_merges`, shared with the gate, never re-implemented);
3. has no auto-rebase record (`refs/spec-kitty/auto-rebase/<lane-branch>/<merge-sha>`, WP02's module), and
4. carries at least one non-bookkeeping own path according to `merge_own_changed_paths` (behind WP01's attribute guard).

Done means:

- The named refusal fires on the #5604 hand-merge shape, the message-forged shape and the hand merge of the Mission branch; no branch moves (SC-003).
- It does not fire on a clean merge, on a recorded tool merge, or on a merge an own stamp reaches.
- The three-lane case fires (a dependent lane's stamp reaching the merge does not exempt it).
- A predicate-agreement test pins that the claim refuses exactly the merges the gate would drop and that carry own content.
- `--dry-run` reports `CLAIM_REFUSED_FORECAST` naming the code.
- `test_dependency_merge_attribution_7307.py` no longer returns early; each test pins its code, and one assertion still exercises the gate's own unreviewed-merge rule with the claim check bypassed (FR-012).
- The strict xfail in `test_approved_bound_residuals.py` is converted to a passing assertion of the new code (no XPASS).
- `content_commits` is unchanged, so tier 2 and the gate re-check (`lane_tips_moved_refusal`) are unchanged.

## Context & Constraints

Read before coding:

- `.kittify/charter/charter.md` (binding), then `spec-kitty charter context --action implement`.
- `kitty-specs/approved-lane-resolution-route-01M7WW0Z/spec.md` (US3, FR-004, FR-005, FR-012, Edge Cases), `plan.md` (IC-03), `research.md` (R-03, R-04), `data-model.md` (refusal table), `contracts/refusal-codes.md` (exact text shape), `contracts/auto-rebase-record.md`.
- Squad findings that shaped this WP: architect F7, F8, F9, F10 (`squads/01-pre-spec-and-post-specify.md`, squad 2 rows on FR-004 and FR-012).

Integrity invariants (binding for every line you write):

- **C-001**: no conflict resolution is attributed without a review approval that reaches it. This WP only refuses; it never attributes.
- **C-002**: no new attestation, flag, record or override lifts a FAIL or REFUSE. The auto-rebase record only decides whether THIS claim-time refusal fires; the gate never reads it. Do not add an attestation flag for the new code.
- **C-003**: `_drop_unreviewed_merges` stays as is; FR-004 reuses its reach rule through WP04's public predicate.
- **C-004**: re-approval counts only as an unforced, independent review approval. You read stamps through `approval_stamp(s)` (which already applies #5721); do not add a second reader.
- **C-005**: no forecast of conflicts (that is #7324) and no `--dependency-ref` change (#7766).
- **C-006**: one refusal renderer (`approved_bound.render_refusals`), one bound verdict (`_approved_bound_verdict`), one own-content probe (`git_probes.merge_own_changed_paths`), one record reader (WP02's `lanes/auto_rebase_record.py`).
- **C-007**: the orchestrator-api contract bump is WP09's; you only make `refusal_codes()` recognise the code (it iterates `BoundRefusalCode`, so adding the member is enough).
- **NFR-002 fail closed**: every git probe error refuses (raise `GitProbeError`; the callers already turn it into a pre-mutation refusal: `phase_claim._exit_on_claim_probe_error`, `phase_claim.py:829-844`, and the orchestrator's `except RuntimeError` envelope). A missing record is "not a tool merge", never "pass".
- **NFR-001**: beyond the existing enumeration, at most one own-content probe per merge on an approved lane that no own stamp reaches and that has no record, plus WP01's one attribute query per probed merge. A Mission with no such merge runs zero own-content probes.

Current code you build on (HEAD of the planning base):

- `src/specify_cli/consolidation/approved_bound.py`
  - `BoundRefusalCode` (`:63-68`), `BoundRefusal` (`:71-88`), `move_back_command` (`:95-97`), `_send_back_recovery` (`:123-130`), the three `_*_block` renderers (`:133-182`), `render_refusals` (`:185-201`, a `blocks` dict keyed by code: a new member without a block raises `KeyError`), `refusal_codes` (`:204-212`), `commits_beyond` (`:447-462`), `content_commits` (`:465-479`, skips merges at `:474`; DO NOT change), `check_lane` (`:515-565`), `__all__` (`:568-584`).
- `src/specify_cli/consolidation/reconciliation_bound.py`
  - `_LaneScope` (`:74-91`), `_approved_bound_verdict` (`:150-246`), `_stamps_by_lane` (`:249-253`), `_lane_verdict` (`:265-312`), `_render_lane_verdicts` (`:315-324`), `approved_bound_refusal` (`:403-446`, the orchestrator-api door), `lane_tips_moved_refusal` (`:449-496`, gate re-check; DO NOT change).
- `src/specify_cli/consolidation/reconciliation_authorship.py:294-312` `_drop_unreviewed_merges` (first-parent spine, own stamps only); after WP04 it calls the extracted public predicate. Read WP04's landed name in that module's `__all__` before you import it.
- `src/specify_cli/consolidation/reconciliation_kernel.py:313-326` `_lane_first_parent_spine` (the gate's spine reader; it tolerates an unresolvable range by returning `[]`).
- `src/specify_cli/consolidation/git_probes.py:740-766` `merge_own_changed_paths` (raises on octopus merges and on git < 2.36; after WP01 also on an unregistered merge attribute or driver).
- `src/specify_cli/consolidation/reconciliation_claim.py:299-339` (not owned): `bound_verdict` / `lane_bound` partials and `_compound_refusal` (`:426-445`). Because the new refusal is part of `_BoundVerdict.refusal`, it is compounded and forecast automatically. You do not edit this file.
- `src/specify_cli/consolidation/forecast.py:478-487` (not owned): `--dry-run` turns `claim_integrity_refusal` into `CLAIM_REFUSED_FORECAST`. No edit needed.
- WP02 gives `lanes/auto_rebase_record.py` with `is_recorded(...)` (read its landed signature; the contract is "a ref exists AND resolves to exactly this SHA").

## Branch Strategy

- **Strategy**: Planning artifacts were generated on fix/approved-lane-resolution-route; completed changes must merge back into fix/approved-lane-resolution-route.
- **Planning base branch**: fix/approved-lane-resolution-route
- **Merge target branch**: fix/approved-lane-resolution-route

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implement command: `spec-kitty agent action implement WP05 --agent claude --mission approved-lane-resolution-route-01M7WW0Z`

## Subtasks & Detailed Guidance

### Subtask T023 - Red tests: the named code, no mutation, all controls, predicate agreement

- **Purpose**: pin FR-004 before writing it, with controls that a lazy implementation (always refuse, never refuse, message match, parent-shape match, "any stamp reaches it") fails.
- **Files**: `tests/consolidation/test_resolution_merge_unreviewed.py` (new).
- **Fixtures to reuse** (do not build a new harness):
  - `tests/terminus/post_approval_support.py`: `build_post_approval_mission(tmp_path, "lanes" | "coord")`, `lane_worktree`, `LATE_PATH`, `LATE_CONTENT`. Both work packages are approved through the production shell, so stamps are real.
  - The evil-merge shape in `tests/consolidation/test_approved_bound_residuals.py:41-56` (`_add_evil_merge`: a merge of the approved lane tip and the Mission branch tip whose tree adds `LATE_PATH`). That IS "a hand merge of the Mission branch into the lane with own content" (US3 AS5).
  - `tests/terminus/conftest.py`: `run_terminus`, `git_rev`; `tests/terminus/rollback_harness.py`: `ref_shas`, `reflog_shas` (`:51`), `state_path` (`:24`), `flat`.
- **How "no mutation" is proven (SC-003), everywhere in this WP**: end-state SHAs are NOT enough. Today's late path (land every lane, gate FAIL, roll back) also ends with identical `ref_shas`, so a refusal wired at the gate under the new code name would pass an end-state comparison. Assert instead, before and after the run: `len(reflog_shas(mission, b))` is unchanged for the target, the Mission/coordination branch and every lane branch (a land-then-rollback leaves extra reflog entries even when the tip comes back), AND no pre-mutation snapshot was persisted (`state_path(mission)` is `None`, or the record it names carries no `pre_mutation_refs`; read at the base which of the two a claim-time refusal leaves and pin that one). Note: `rollback_harness.full_snapshot` (`:74`) holds SHAs, bookkeeping and event-log bytes, NOT reflog lengths; do not rely on it for this.
  - For claim-level (in-process) tests, the real-git builders in `tests/consolidation/test_dependency_merge_attribution_7307.py:281-317` (`_build_post_approval_merge`) and `build_approved_wp_set`.
- **Tests to write first** (each is red at the base and says why, EXCEPT the ones labelled **control**: those are green at the base, because they assert the absence of a code that does not exist yet, and must stay green; record them as controls in history, not as red):
  1. `test_hand_merge_with_own_content_is_refused_before_any_branch_moves` (both topologies): `_add_evil_merge`, run `consolidate --mission <slug> --yes`; assert exit != 0, `RESOLUTION_MERGE_UNREVIEWED` in output, the merge's short SHA, the lane id and `WP01` named, and no mutation proven by reflog lengths and no snapshot (Context, "How no mutation is proven"); `ref_shas` equality alone does not count. Red today: the run lands every lane, then fails at the gate and rolls back; the code does not exist.
  2. **control** `test_clean_post_approval_merge_is_not_refused`: a merge whose `--remerge-diff` is empty (merge the Mission branch tip with no edit). Assert the code is absent (the run may still succeed or fail for other reasons; assert only the code, and assert the claim has no refusal via `build_approved_wp_set`).
  3. **control** `test_recorded_tool_merge_is_not_refused`: create the merge, then write its record with WP02's `record()` (never by hand-writing a ref, so the test follows the contract). Assert the code is absent. Add the end-verdict note of US3 AS3: when the recorded merge auto-resolved non-bookkeeping content, the gate still judges it; assert only that the claim does not carry the new code, never exit 0.
  4. `test_message_forged_merge_is_refused`: commit message `auto-rebase(lane=lane-a): 1 conflicts resolved by classifier rules` and no record. Refused.
  5. `test_hand_merge_of_the_mission_branch_is_refused`: parents `[lane tip, mission tip]` (the shape `lane_cleanup.own_auto_rebase_move` accepts) and no record. Refused. This kills the parent-shape discriminator.
  6. `test_three_lane_case_uses_the_own_lane_predicate`: lane-c depends on lane-b; lane-b carries the unreviewed merge M_b; lane-c merges lane-b after M_b and lane-c is re-approved (its stamp reaches M_b). Assert lane-b is refused naming M_b. Red with a lazy "any lane's stamp" rule (`lane_exempt_commits` anchors include other lanes' stamps, `reconciliation_bound.py:284-293`).
  7. `test_claim_and_gate_agree_on_dropped_merges` (predicate agreement): over the fixtures above, collect (a) the merges the new function refuses (the `commits` of the `RESOLUTION_MERGE_UNREVIEWED` refusals of the normal claim) and (b) the gate side, taken from where the gate ACTUALLY drops merges: WP04's `claim.unreviewed_merges` (filled inside `_collect_authored` at the drop site), on a claim built with the FR-004 check bypassed (monkeypatch the new function, at the name `reconciliation_bound` looks up, to return `()`, the same bypass T027 uses; a refused claim carries no `unreviewed_merges`). Filter (b) to entries with at least one non-bookkeeping `own_paths` entry and no record (`is_recorded` false). Assert (a) == (b) as sets of SHAs. Do NOT recompute (b) by calling the extracted predicate over a spine you build: that compares the code with itself. Precondition: no fixture in this test raises a probe error (WP04's sink skips such merges, which would make (b) silently smaller); assert each fixture's merges probe cleanly. Use public names; import private ones only through `tests/consolidation/reconciliation_family.py` if the facade moved them.
  8. `test_probe_error_refuses`: monkeypatch `git_probes.merge_own_changed_paths` (patch where the new code looks it up) to raise `GitProbeError`; assert the claim does not pass (a refusal or a raised `GitProbeError`, which `phase_claim` turns into a pre-mutation exit). Also an octopus merge with own content (reuse `_octopus_merge_with_own_file` shape) refuses.
  9. **control** `test_merge_reached_by_own_stamp_is_not_refused`: re-approve the WP after the merge (`rework_and_reapprove` style: unforced, distinct reviewer); assert the code is absent.
  10. `test_union_attribute_attack_refuses_at_claim_with_no_branch_moves` (FR-010 x FR-004, real git, through the real CLI): a CONFLICT shape, because an attribute only changes how git recomputes a conflicted path: the lane edits line 1 of a shared file `p.py`, the Mission branch edits the same line differently, and an operator hand-merges the Mission branch into the approved lane with the union bytes as the resolution (no record, no own stamp reaches it). Write `p.py merge=union` into `.git/info/attributes` (the common dir). Precondition (asserted): without the attribute, `merge_own_changed_paths(repo, merge) == ["p.py"]`. Run `consolidate --mission <slug> --yes`: it must refuse (the FR-010 probe refusal surfaced by `phase_claim._exit_on_claim_probe_error`, or `RESOLUTION_MERGE_UNREVIEWED`; assert which one and pin it), with no mutation (reflog lengths, no snapshot). Red without WP01's guard (the remerge recomputes the union bytes, "no own content", the claim passes). This test exists because the probe-level attack tests (WP01) cannot catch a claim that swallows the probe error or reads WP04's advisory field.
- **Validation**: run the file at the base (after WP01/WP02/WP04 landed) and record the red output summary with `spec-kitty agent tasks add-history WP05 --note "T023 red: ..." --mission approved-lane-resolution-route-01M7WW0Z`.
- **Edge cases**: a lane whose approved WP has no stamp or a stamp not on the lane already refuses with `APPROVAL_STAMP_MISSING` / `APPROVAL_STAMP_NOT_ON_LANE`; the new check must not add a second refusal for that lane (its own stamps are unknown). A planning lane and a `single_branch` Mission are not bounded here (the write-branch path, `reconciliation_bound.py:198-208`, is unchanged).

### Subtask T024 - `BoundRefusalCode.RESOLUTION_MERGE_UNREVIEWED`, `unreviewed_resolution_merges()`, renderer text

- **Purpose**: one new code in the existing family, one pure-over-probes function, one block in the one renderer.
- **Files**: `src/specify_cli/consolidation/approved_bound.py`.
- **Steps**:
  1. Add `RESOLUTION_MERGE_UNREVIEWED = "RESOLUTION_MERGE_UNREVIEWED"` to `BoundRefusalCode` (`:63-68`) as the LAST member, so `refusal_codes()` (`:204-212`) picks it up and the orchestrator's `data.preflight_error_codes` gains it with no further change. Update the class docstring ("three refusals" becomes four).
  2. Add `unreviewed_resolution_merges(repo_root, *, lane_id, branch, wp_ids, spine_merges, own_stamps, is_recorded, is_bookkeeping) -> tuple[BoundRefusal, ...]` (name per research R-04; keep parameters keyword-only). Shape:
     - input `spine_merges`: the merge commits on the lane's first-parent spine that are beyond the claim base (enumerated by the caller, see T025);
     - for each merge, skip it when WP04's predicate says one of `own_stamps` reaches it;
     - skip it when `is_recorded(sha)` is True (WP02);
     - otherwise call `merge_own_changed_paths(repo_root, sha)` and keep the non-bookkeeping paths; a non-empty list yields one `BoundRefusal(code=RESOLUTION_MERGE_UNREVIEWED, lane_id, branch, wp_ids, commits=(sha,), path=<first own path>)`. Record the own-path count for the text (add a field only if needed, with a default, so existing constructors stay valid).
     - let `GitProbeError` propagate (fail closed). Do not catch it.
     - **The verdict never comes from WP04's advisory field** (`claim.unreviewed_merges`, which skips merges whose probe raised) **nor from any memo that swallows probe errors.** Its only source is this function's own call of `merge_own_changed_paths`, which raises.
     - Pass the claim's pre-run target tip as `attributes_source=` to `merge_own_changed_paths` (operator ruling: WP01's option (a) on committed attributes; read WP01's landed keyword name).
     - Order of checks matters for NFR-001: the predicate and the record check (cheap, no remerge) run before `merge_own_changed_paths`.
  3. Inject collaborators (`is_recorded`, the predicate) as callables or import them at module level; keep the function testable without a real ref store. Do not import `specify_cli.lanes` at module import time if it creates a cycle; follow the lazy-import pattern already used at `:270-272` and `:330-333`.
  4. Add `_unreviewed_merge_block(group, mission, term)` and register it in the `blocks` dict of `render_refusals` (`:196-200`) AFTER the three existing entries. Text per `contracts/refusal-codes.md`:
     - one line per merge: `RESOLUTION_MERGE_UNREVIEWED: lane <id> (<WP ids>): merge <sha> carries its own content on <n> path(s) (e.g. '<path>') and no review approval of the lane reaches it.` (the first line starts with `<CODE>: ` so `refusal_codes` sees it; later lines must NOT start with a code token);
     - then the recovery: one `move_back_command` per distinct WP (reuse, do not reword; a `done` WP needs `--force --note "<why>"`, say so in one line), then `Resolve the conflict if needed, submit for review, and have an independent reviewer approve again: the new approval must reach merge <sha>.`, then `spec-kitty consolidate --mission <slug>`.
     - Use the existing `_short` (7 chars) for consistency with the other blocks unless the reviewer asks for 12; record the choice in the WP history (the contract example says sha12, the renderer convention is 7).
  5. Export the new name in `__all__`.
- **Complexity**: keep each new function at C901 <= 15; split the per-merge decision into `_merge_needs_review(...) -> tuple[str, ...]` if needed.
- **Tests**: renderer unit tests in the new test file: one refusal, two merges on one lane, two lanes, mixed with a `LANE_MOVED_AFTER_APPROVAL` refusal (block order: existing codes first, new code last), and `refusal_codes(text)` returning the new code exactly once.

### Subtask T025 - Wire it into `_approved_bound_verdict` after tiers 1 and 2

- **Purpose**: one placement reaches the CLI claim, `--resume`, `--dry-run` and `approved_bound_refusal` (orchestrator-api) at once, before any mutation.
- **Files**: `src/specify_cli/consolidation/reconciliation_bound.py`.
- **Steps**:
  1. Extend `_LaneVerdict` (`:65-71`) with `unreviewed: tuple[BoundRefusal, ...] = ()`.
  2. In `_lane_verdict` (`:265-312`) after the tier-1 / tier-2 computation, compute the lane's unreviewed merges, but only when tier 1 produced no `APPROVAL_STAMP_MISSING` / `APPROVAL_STAMP_NOT_ON_LANE` refusal (own stamps must be known and on the lane). Inputs:
     - own stamps: `scope.stamps_by_lane[lane.lane_id]` (already the approved, non-canceled WPs' stamps, `:249-253`);
     - spine merges: the gate's spine (`first_parent_commits_in_range(coord_base_ref, tip)` as `_lane_first_parent_spine` reads it) restricted to merges that the claim base does not reach. You need `coord_base_ref` in `_LaneScope`: add the field and pass it from `_approved_bound_verdict` (the parameter already exists at `:156`). Enumerate merges with ONE history query per lane (for example `git rev-list --first-parent --merges <coord_base_ref>..<tip>` through a probe in `git_probes`; if no such probe exists and `git_probes.py` belongs to WP01, compose from `first_parent_commits_in_range` + `is_merge_commit` and record the extra cost; do NOT edit `git_probes.py`, it is WP01's file);
     - is_bookkeeping: `scope.is_bookkeeping`.
     - Use the frozen lane `tip` the caller resolved (`:237`), never the live branch name.
  3. Extend `_render_lane_verdicts` (`:315-324`) to append `render_refusals(<all unreviewed>, mission_slug)` AFTER the tier-1 and tier-2 parts. Tier-1 refusals and unreviewed refusals may be rendered in one `render_refusals` call (the dict order keeps the new block last) or as a third part; either way the first line of the whole text stays the first refusal's code (the orchestrator reads `codes[0]`).
  4. Leave `content_commits`, `check_lane`, `lane_tips_moved_refusal` and `write_branch_bound` untouched (research R-04: changing `content_commits` changes tier 2 and the gate re-check, and would refuse this run's own auto-rebase merges at gate time).
  5. `_compound_refusal` (`reconciliation_claim.py:426`) needs no change: it appends `verdict.refusal`, which now carries the new block after the existing approved-bound codes. Verify that with a test (a mixed-lane refusal plus an unreviewed merge shows both under "This Mission also has:").
- **Complexity**: `_lane_verdict` is already long; extract `_unreviewed_lane_merges(scope, lane, branch, tip, tier_one)` to keep it <= 15.
- **Edge cases**:
  - A merge reachable from the claim base (already on the target) is out of scope.
  - A fully canceled lane is never bounded (`_bound_lanes`, `:117-130`); do not judge it.
  - A canceled WP on a mixed lane contributes no stamp (`_bound_approved_wp_ids`, `:108-114`), as the gate's `_approved_stamps` does (`reconciliation_authorship.py:283-291`); agreement test covers it.
  - `--resume`: this run's own interrupted-attempt auto-rebase merges carry a record (WP02), so they are not refused.
  - An approved-reviewed attestation is an approval for `approval_stamp` (`approved_bound.py:284-291`), on the claim and at the gate alike; the semantics are unchanged (C-002), and the attestation itself is refused for a WP whose newest approval is a stamped review approval.

### Subtask T026 - Forecast: `--dry-run` reports `CLAIM_REFUSED_FORECAST` naming the code

- **Purpose**: the preview must not be green while the run refuses.
- **Files**: `tests/consolidation/test_resolution_merge_unreviewed.py` only (no source change expected: `forecast.py:478-487` already maps a claim refusal to `CLAIM_REFUSED_FORECAST`).
- **Steps**: on the hand-merge fixture run `consolidate --mission <slug> --dry-run --json` (`run_terminus` or `characterization_support.run_in_process` with `consolidate_args(mission, "forecast")`); parse the JSON; assert `error_code == "CLAIM_REFUSED_FORECAST"` and the message names `RESOLUTION_MERGE_UNREVIEWED`; assert no mutation with reflog lengths and no snapshot (Context), not end-state SHAs. The ADR names a corpus cell `forecast|single_lane|post_approval_commit` for the sibling code; follow the same naming in the test id (`forecast|single_lane|post_approval_resolution_merge`).
- **If it is not red-then-green**: when the forecast does not report the code after T025, do not patch `forecast.py` (not owned); record the gap and raise it with the orchestrator.
- **Extra assertions**:
  - the forecast payload's message names the merge short SHA and the lane (the claim text is embedded verbatim, `forecast.py:483`);
  - the forecast and the real run agree: run the real `consolidate` on a copy of the same fixture (`characterization_support.copy_mission`) and assert both name `RESOLUTION_MERGE_UNREVIEWED` (parity, as `test_forecast_fresh_run_parity.py` does for other codes);
  - a control Mission with only a clean post-approval merge forecasts no `RESOLUTION_MERGE_UNREVIEWED`.
- **Why red today**: the code does not exist, and today's forecast of this shape is the gate-level FAIL (or a later refusal), not a claim refusal.

### Subtask T027 - FR-012: make the #7307 tests non-vacuous

- **Purpose**: today three tests `return` on any claim refusal (`test_dependency_merge_attribution_7307.py:334-337`, `:340-345`, `:348-356`). After T025 they would silently pin nothing.
- **Files**: `tests/consolidation/test_dependency_merge_attribution_7307.py`.
- **Steps**:
  1. Run each at the base first and write down whether the claim refuses today and with which text (record it in the WP history).
  2. Replace each early return with an explicit expectation:
     - `..._fails_under_merge` / `..._fails_under_squash`: assert `claim.refusal` names `RESOLUTION_MERGE_UNREVIEWED` (the evil merge `u/evil.txt` has own content and lane-b's stamp `b_tip` does not reach it);
     - `test_post_approval_merge_of_canceled_dependency_fails`: lane-c is fully canceled (WP03 excluded); the canceled-dependency resolution or the new code may refuse first. Pin the exact code(s) you observe after T025 and explain the order in a comment (the precedence matrix, `test_refusal_precedence_matrix.py:1-45`, puts `canceled_dependency` before `bound` and compounds them).
  3. Keep the gate layer pinned (defence in depth, C-003): add one test (or one block in each) that builds the claim with the FR-004 check bypassed (monkeypatch the new function, at the name `reconciliation_bound` looks up, to return `()`), then asserts `MergeOutcomeVerifier.verify(...)` is not PASS under merge and under squash, exactly as the old assertions did. A regression that deletes `_drop_unreviewed_merges` must turn this red.
  4. Mutation check, run by hand and recorded in history: make the claim refuse for an unrelated reason (for example drop the WP03 stamp) and confirm the tightened tests fail.
- **Note**: `test_post_approval_octopus_merge_with_own_content_is_refused` (`:394-401`) passes a refused claim to the verifier; after T025 the claim refuses (the probe raises on an octopus). Keep the verifier assertion and add `assert claim.refusal is not None or <GitProbeError raised>` so both layers are visible.

### Subtask T028 - Convert the strict xfail in `test_approved_bound_residuals.py`

- **Purpose**: the residual of ADR 2026-10-04-5 (line 174, "content inside a merge commit") is closed by FR-004 under a new code; a strict xfail that expects `LANE_MOVED_AFTER_APPROVAL` would keep failing as expected (vacuous) or XPASS.
- **Files**: `tests/consolidation/test_approved_bound_residuals.py`.
- **Steps**:
  1. Remove the `@pytest.mark.xfail` (`:59-63`) and change `_CODE` to `RESOLUTION_MERGE_UNREVIEWED`.
  2. Rewrite the module docstring (`:1-19`): the residual is now refused by the claim-time check; tool merges are told apart by the auto-rebase record (WP02), not by message or parent shape.
  3. Also assert no mutation (reflog lengths before and after for every branch, and no snapshot written; Context), and that the merge SHA is named.
  4. Run it red first (before T025 the plain assertion fails), then green.
- **Docs**: the ADR text change is WP13's; leave a history note naming the residual so WP13 picks it up.
- **Edge cases**:
  - The fixture's merge (`commit-tree` with parents `HEAD` and the coordination tip) has the auto-rebase parent shape and no record. It must refuse; this is the strongest form of the "hand merge of the Mission branch" control, so keep it parametrised over `lanes` and `coord` if runtime allows.
  - `test_approved_bound.py::_conflict_resolved_merge` (`:508-527`) exercises `check_lane` only; it is unaffected (it does not go through `_approved_bound_verdict`). Do not change it.
- **Validation**: the converted test passes; `pytest --runxfail` is not needed any more; `grep -n "xfail" tests/consolidation/test_approved_bound_residuals.py` returns nothing.

## Binding addendum (orchestrator ruling 2026-11-20, WP02 and WP04 reviews)

1. Lane-committed attributes. A merge with an auto-rebase record (`is_recorded`) is exempt from RESOLUTION_MERGE_UNREVIEWED only when the FR-010 guard `assert_registered_merge_behaviour(repo, <the merge's changed paths vs either parent>, attributes_source=<pre-run target tip>)` passes.
   - If the guard refuses or errors, the merge is treated as unrecorded (judged as a hand merge). This is fail closed.
   - `is_recorded` raising (a foreign value) is also a refusal.
   - Red test: a recorded auto-rebase merge on a lane whose committed `.gitattributes` sets `merge=union` on the merged path (not set on the target tip) refuses with RESOLUTION_MERGE_UNREVIEWED.
2. Forged record is harmless (defence-in-depth test).
   - Setup: a hand merge with its own content on an approved lane, plus a forged `refs/spec-kitty/auto-rebase/<lane>/<sha>` written with `git update-ref`.
   - Expected: the claim-time refusal may be skipped, but consolidate still does not land the content. The gate FAILs it on the attribution axis, the target is restored, and exit is non-zero.
   - Record the result for WP13, which lists it in the ADR as defence in depth.
3. When WP05 imports `is_recorded` / `recorded_merges` (WP02), and `merge_reviewed_by_own_stamps` / `own_approval_stamps` (WP04), adding them back to their modules' `__all__` is recorded leeway in WP05.
   - `tests/architectural/test_no_dead_symbols.py` must be green on WP05's lane.
4. `is_recorded` raises on a record that names a different commit. Treat that as a refusal.
   - A missing `unreviewed_merges` entry never means "clean": re-probe or refuse (WP04 reviewer note).
5. Pre-sync stamps (orchestrator ruling 2026-11-25, WP04 rebase delta). After the rebase, WP04's shared reader is `own_approval_stamps(lane, work_packages, approval_stamps, presync_stamps=None)`. Main's #7802 makes each approved WP's pre-sync stamp a reach anchor after its `lane_head` stamp.
   - The claim-time check MUST pass the pre-sync stamps, as `_approved_stamps` does (`presence.approval_presync_stamps`), so that the claim and the gate read one definition.
   - Red test: a merge reached only by an approved WP's pre-sync stamp, and not by its `lane_head` stamp, is treated as reviewed at claim time, the same as at the gate.
6. Merge inside a canceled WP's window (reviewer binding probe, WP08 review cycle 2, 2026-11-25). The setup: a merge whose resolution adds its own content (for example `src/canceled.py`) sits inside a canceled WP's window, and that WP is canceled at that merge. Later, an approved WP on the same lane is approved at a commit whose stamp reaches the merge. Today the merge is dropped from the canceled window and counts as "reviewed" under #7307, although no approved WP's review window held it.
   - Add a real-git test of exactly this shape. The test must refuse, either with RESOLUTION_MERGE_UNREVIEWED or through the canceled-content axis. It must never land.

## Test Strategy

Red first for every behavioural change; record each red run in the WP history.

Targeted commands (no full heavy suites, no bare `tests/architectural/`):

```bash
uv run --frozen pytest tests/consolidation/test_resolution_merge_unreviewed.py -q
uv run --frozen pytest tests/consolidation/test_approved_bound_residuals.py tests/consolidation/test_dependency_merge_attribution_7307.py -q
# blast radius of approved_bound.py / reconciliation_bound.py
uv run --frozen pytest tests/consolidation/test_approved_bound.py tests/consolidation/test_lane_approval_windows.py tests/consolidation/test_write_branch_bound.py tests/consolidation/test_claim_integrity_refusal.py tests/consolidation/test_refusal_precedence_matrix.py tests/consolidation/test_refusal_precedence_matrix_windows.py tests/consolidation/test_lane_window_query_count.py tests/consolidation/test_resume_frozen_anchors.py tests/consolidation/test_forecast_fresh_run_parity.py tests/consolidation/test_claim_inputs_parity.py -q
uv run --frozen pytest tests/terminus/test_post_approval_commit_refused.py tests/terminus/test_post_approval_resume.py tests/terminus/test_unstamped_approval_attestation.py tests/orchestrator_api/test_consolidate_mission_post_approval.py -q
# every other test that builds a claim over a lane with a merge (find them, run them)
grep -rln "build_approved_wp_set\|approved_bound_refusal" tests/ --include="*.py"
uv run --frozen pytest tests/consolidation/test_single_rollback_authority.py -q
make test-fast
```

Gate files this WP implicates: `tests/architectural/test_layer_rules.py` (no new cross-layer import), `tests/architectural/test_no_legacy_terminology.py` (renderer prose). Run them by name.

NFR-001 pin: add a process-count test modelled on `tests/consolidation/test_lane_window_query_count.py` (count calls reaching `git_probes.run_command` or the kernel remerge helper):
- a passing Mission with no post-approval merge runs zero `show --remerge-diff`;
- a lane with one unreviewed merge (the refusing case) runs exactly one;
- **on a PASSING claim**: a lane with one unrecorded CLEAN post-approval merge (no own content, so not refused) runs exactly one `--remerge-diff` for that merge across the WHOLE claim build. Today both this WP's check and WP04's `unreviewed_merges` sink (which probes every dropped merge on a claim that passed the bound) probe it, so the count is two without a memo.

**This WP owns the per-claim probe memo, if one is needed** to meet the passing-claim count (WP04 adds none). Rules: one memo per claim build, never across runs; it stores only SUCCESSFUL probe results; a `GitProbeError` is never stored as "no paths" (it propagates to this WP's verdict, and on WP04's advisory path it is skipped exactly as WP04 does today); this WP's verdict reads the memo only for a result its own raising call produced. Threading the memo into WP04's sink touches `reconciliation_authorship.py` / `reconciliation_claim.py` (WP04's files, in your base): limit that edit to passing the memo through, list it in history, and stop and report to the runner if it needs more. If `test_lane_window_query_count.py` breaks because of the extra per-lane merge enumeration, keep the enumeration per lane (not per WP) and record the delta; never raise `_PER_WP_BUDGET` silently.

Quality gates (zero findings, no suppressions, complexity <= 15):

```bash
uv run --frozen ruff check src/specify_cli/consolidation/approved_bound.py src/specify_cli/consolidation/reconciliation_bound.py tests/consolidation/test_resolution_merge_unreviewed.py tests/consolidation/test_approved_bound_residuals.py tests/consolidation/test_dependency_merge_attribution_7307.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/consolidation/approved_bound.py src/specify_cli/consolidation/reconciliation_bound.py tests/consolidation/test_resolution_merge_unreviewed.py tests/consolidation/test_approved_bound_residuals.py tests/consolidation/test_dependency_merge_attribution_7307.py
uv run --frozen mypy src/specify_cli/consolidation/approved_bound.py src/specify_cli/consolidation/reconciliation_bound.py tests/consolidation/test_resolution_merge_unreviewed.py
```

Tracer notes: this code WP cannot own `kitty-specs/` paths. Record friction, approach and design notes for `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md` with `spec-kitty agent tasks add-history WP05 --note "<trace: approach|design|friction> ..." --mission approved-lane-resolution-route-01M7WW0Z`. At minimum record: the spine/base choice for the merge enumeration, the short-SHA width decision, and the observed pre-fix codes of the #7307 tests.

## Risks & Mitigations

- **Two definitions of "reviewed" drift apart** (squad finding: the bound's anchors include other lanes' stamps; the gate uses only own stamps). Mitigation: import WP04's predicate; the agreement test (T023 #7) fails on any divergence.
- **Refusing the tool's own merges**: an earlier release's auto-rebase merge has no record; it refuses only if it carries own content (spec Edge Cases). Merges from this run's interrupted attempt carry WP02's record.
- **Blast radius on existing tests**: any fixture with a post-approval merge that carries own content and no record now refuses at claim time. Expected and correct. **Bounded leeway** (tasks.md "Recorded leeway"): you may adjust such an existing test you do not own ONLY if its file is named in this WP's Test Strategy command lists (the blast-radius commands below, including the files the `grep -rln` line finds and you then run). For each one, record the file, the test, the before/after expectation and the rationale in history (`spec-kitty agent tasks add-history WP05 --note "leeway: <file>::<test>: <old> -> <new>, because ..."`). Re-pin to the new code; never delete a test or weaken an assertion (Standing Order 5). A test outside those files that needs a change: stop and report to the runner.
- **Merge enumeration base**: using the claim base alone could judge merges that the gate does not see (merges off the first-parent spine). Mitigation: enumerate the gate's spine, restricted to merges beyond the claim base; the agreement test is the proof.
- **Performance**: the remerge probe is expensive. Mitigation: predicate and record checks first; one enumeration per lane.
- **Ordering in compound refusals**: the orchestrator reads `codes[0]`. Mitigation: new block always last.

## Additional required test (analysis A13)

- `test_refuses_naming_the_git_version_below_remerge_support`: patch the cached git version below 2.36. A hand-merge fixture must refuse before any mutation, and the message must name the git version (spec edge case: git without remerge-diff).

## Review Guidance

Anti-fake checks (from `squad2/reviewer-renata.md`), each must hold:

- The negative control is not only a message forgery: the hand merge of the Mission branch (auto-rebase parent shape) is refused (renata HIGH on FR-005).
- The predicate is the shared one: grep the diff for a second reach rule (`lane_exempt_commits`, `every_stamp`, a time comparison); the three-lane test fails on "any stamp" (renata MEDIUM on FR-004).
- The record is checked by exact SHA through WP02's module, never by commit message or parent shape; the gate never reads the record (C-002/C-003).
- FR-012 tests assert codes, and one assertion still runs the gate with the claim check bypassed (renata MEDIUM on FR-012).
- The xfail is gone and the test asserts the new code (architect F9, daphne finding 3).
- `content_commits` and `lane_tips_moved_refusal` are byte-identical in the diff.
- A probe error refuses (test T023 #8), and a Mission with no unreviewed merge makes zero remerge calls (NFR-001 test); a PASSING claim with one unrecorded clean merge makes exactly one.
- The claim-level union attack (T023 #10) refuses through the real CLI with no mutation.
- The verdict's only source is this WP's own raising probe call: grep the diff for any read of `unreviewed_merges` in `approved_bound.py` / `reconciliation_bound.py` (must be none) and for a memo that stores an exception as an empty result.
- The agreement test (T023 #7) takes the gate side from `claim.unreviewed_merges` on a bypassed claim, not from a recomputation.
- No-mutation assertions use reflog lengths and "no snapshot", never end-state `ref_shas` alone.
- Every out-of-map test edit is in a file named in the Test Strategy, with a rationale in history.
- The implementer ran ruff, format with `--force-exclude`, and mypy on the owned files, with zero findings and no new suppressions.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) - never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history <WPID> --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task <WPID> --to <status>`
- **View history and status**: `spec-kitty agent tasks status`

### Optional Phase Subdirectories

For large missions, organize prompts under `tasks/` to keep bundles grouped while maintaining lexical ordering.
