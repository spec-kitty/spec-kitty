---
work_package_id: WP19
title: Lane missions adopt the window model
dependencies:
- WP18
requirement_refs:
- FR-007
- FR-008
- FR-009
- FR-021
- FR-022
- FR-023
- NFR-002
- NFR-007
- NFR-010
- SC-001
- C-010
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T097
- T098
- T099
- T100
- T101
- T102
- T103
phase: Phase 4 - Behaviour changes, red-first
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/consolidation/reconciliation_bound.py
- src/specify_cli/consolidation/reconciliation_claim.py
- src/specify_cli/consolidation/reconciliation_claim_types.py
- tests/consolidation/test_reconciliation_intended_verdicts.py
- tests/consolidation/test_reconciliation_seeded_mutations.py
- tests/consolidation/characterization/verdict_corpus.json
- tests/consolidation/test_lane_approval_windows.py
- tests/consolidation/test_lane_window_query_count.py
- docs/changelog/unreleased/7403-lane-approval-window-refusal.changed.md
- tests/consolidation/test_refusal_precedence_matrix_windows.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/write_branch_bound.py
- src/specify_cli/consolidation/approved_bound.py
- src/specify_cli/consolidation/reconciliation_bound.py
- src/specify_cli/consolidation/reconciliation_claim.py
- src/specify_cli/consolidation/reconciliation_claim_types.py
- src/specify_cli/consolidation/wp_attribution.py
- tests/consolidation/test_lane_approval_windows.py
- tests/consolidation/test_lane_window_query_count.py
- tests/consolidation/test_write_branch_bound.py
- tests/consolidation/test_reconciliation_intended_verdicts.py
- tests/consolidation/test_reconciliation_seeded_mutations.py
- tests/consolidation/characterization/verdict_corpus.json
- docs/changelog/unreleased/7403-lane-approval-window-refusal.changed.md
- tests/consolidation/test_refusal_precedence_matrix_windows.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP19 – Lane missions adopt the window model

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP19 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

This is the soundness payoff of the Mission (FR-007, SC-001, closes the "commit between two approvals on one lane" residual of #5721). On a **code lane where at least one approved work package has a `WindowOpen`**:

1. Each approved work package with a `WindowOpen(sha)` covers only `(sha, newest approval stamp]`.
2. Each approved work package with a `WindowGap` falls back to a degraded window `(claim base, approval stamp]` (FR-009, data-model WW-7).
3. The **exemption anchors** are the closed-world anchors (dependency-lane tips of lanes not fully canceled, target pre-consolidation tip) **plus the approval stamps of other bounded lanes**. The lane's **own** approval stamps are **not** exemption anchors (operator ruling `01M6YAFYHT0RMVZB03THW1WWSE`, data-model WW-2a, research R-15).
4. A lane content commit outside every window and every exemption anchor is refused with the existing code `LANE_MOVED_AFTER_APPROVAL`, naming the commit and the work package approved before it (`write_branch_bound._preceding_wp`). No new refusal code (C-010).
5. The window opener is the FR-021 rule implemented by WP08's `window_open_of` (cycle after the last rewind to `planned`; a review rejection keeps the window, R-16; leading `lane_branch_missing` openers skipped; topology order with log-order fallback). You **call** it; you do not re-implement it.

On a code lane where **every** approved work package has a `WindowGap`, today's `check_lane` runs **unchanged, with today's anchors (own stamps included)**, so verdict and refusal text are byte-identical (FR-023, WW-3).

Done means: red-first tests through `consolidate` and `consolidate --dry-run` for US2-1, US2-5, US2-7, the gap-then-recorded mixed lane and the rewound work package fail on the parent commit and pass after; the over-refusal guards (US2-2/3/4/6, US3-1/2/4/5, attested approval, skewed clock, leading branch-missing opener) pass before and after; the claim carries `window_gaps`; the NFR-007 query-count test passes; the strict `xfail` pins for NFR-002 (a), (b) and (c-lanes) are removed; the golden diff touches only those named cells.

## Context & Constraints

Read before coding:

- `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md` — US2 (all 7 scenarios), US3 (1, 2, 4, 5), FR-007, FR-008, FR-009, FR-021, FR-022, FR-023, NFR-002 (a)(b)(c), NFR-007, NFR-010, C-010, Edge Cases (dependency chain, attested approval, rework, rewind, clock skew, mixed lane, planning lanes).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/data-model.md` — section 3 (`window_open_of`, `on_lane`), section 4 (`WorkPackageWindow`, WW-1..WW-7), section 5 (`GapEntry`, `window_gaps` field rule).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-13 (Purpose and Risks are your acceptance criteria).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/research.md` — R-03, R-15, R-16.
- `contracts/status-event-wp-window.md` — reader rules R-1..R-6.
- The Mission ADR `docs/adr/4.x/2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md` (WP01).

Code as it stands before Phase 3 (line numbers drift after the split; locate the post-split home with `grep -n "def _approved_bound_verdict" src/specify_cli/consolidation/*.py`, planned home `reconciliation_bound.py`):

- `reconciliation.py:2208-2277` `_approved_bound_verdict`: resolves each lane tip **once** (`resolve_commit`, ~2258), calls `check_lane` with `anchors=[*_closed_world_anchors(...), *stamp_anchors]` (~2268), where `stamp_anchors = approval_stamp_anchors(...)` (~2202-2205, ~2251) holds the stamps of **every** bounded lane, the lane's own included. That own-stamp inclusion is why the US2 stray commit passes today.
- `reconciliation.py:2144-2149` `_BoundVerdict`; `:2354-2388` `approved_bound_refusal` (the `orchestrator-api` door, calls `_approved_bound_verdict`); `:1797-1799` the bound refusal becomes `_refusal_claim(...)`; `:1845-1866` the passing claim is assembled; `:1884-1903` `_compound_refusal`.
- `reconciliation.py:623-804` `ApprovedWpCommitSet` (last field today: `no_implementation_attested_wp_ids`, ~804). Post-split home: planned `reconciliation_claim_types.py`.
- `approved_bound.py:493-509` `stamp_refusal`; `:512-558` `check_lane` (tier 1: own stamps are `covered`, exempt set from `lane_exempt_commits(claim_base, anchors)` at ~546); `:462-476` `content_commits`; `:182-198` `render_refusals`.
- `write_branch_bound.py:54-139` `ApprovalWindow`, `_WindowReach`, `approval_windows`, `_window_reach`, `_preceding_wp`, `_outside`, `_window_refusals`; `:142-190` `check_write_branch` (tier 1 then tier 2 — **the template for the lane leg**); `:193-229` the window refusal text (`_window_finding`, `render_write_branch_refusals`).
- `wp_attribution.py:732` `lane_exempt_commits`; WP08 added `WindowOpen`, `WindowGap`, `WindowGapReason` (`report_text`), `window_opener_events`, `window_open_of`.
- `git_probes.py:403-460` `sha_reachable_from` (merge-base, never raises), `resolve_commit` (rev-parse), `commits_in_range` (rev-list).
- WP18 threaded a frozen anchor set into the closed-world anchor consumers on `--resume`. **Keep it.** Use whatever anchor value `_approved_bound_verdict` receives after WP18; never fall back to a live dependency-lane read on the window path.

Test support to reuse (do not copy-paste): `tests/consolidation/characterization_support.py` (WP02: `build_shape`, `set_window_state`, `run_in_process`, `CellResult`, `assert_cells_match`, `regenerate_cells`), `tests/terminus/post_approval_support.py` (`build_post_approval_mission`, `add_post_approval_commit`, `strip_approval_stamps`, `rework_and_reapprove`, `lane_worktree`), `tests/terminus/rollback_harness.py` (`ref_shas`), `tests/consolidation/test_reconciliation_intended_verdicts.py` (WP05 fixtures and the `require()` precondition rule).

Cross-cutting: C-009 (`tests/consolidation/test_single_rollback_authority.py` green), C-013, C-014, NFR-004 (every function you add or change ≤ 15; extract a `_lane_verdict(...)` helper out of the `_approved_bound_verdict` loop), NFR-005 (no allowlist entry, no `# noqa`, no `# type: ignore`), NFR-009.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP19 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Design in one paragraph (read before T099)

Mirror `check_write_branch` (`write_branch_bound.py:142-190`) on each code lane. **Tier 1** is `check_lane` unchanged: stamp refusals first (`APPROVAL_STAMP_MISSING` / `APPROVAL_STAMP_NOT_ON_LANE`, WW-4), then content after every own approval stamp, rendered with today's text. **Tier 2** runs only when tier 1 passed: a content commit in `claim_base..tip` that is in no window's covered set and not in the exempt set is refused, one `BoundRefusal` per commit naming the preceding work package. The exempt set is computed **once per lane** from the exemption anchors (closed-world anchors + other lanes' stamps) and passed to both tiers (NFR-007). Removing the own stamps from tier 1's exempt set changes no tier-1 verdict, because `check_lane` already excludes everything its own stamps reach through `commits_beyond(tip, [claim_base, *own_stamps])` (`approved_bound.py:547`); write that argument into the docstring. Consequence (record it with `spec-kitty agent tracer-append --category design-decisions`): content after the last approval keeps today's tier-1 text; the new window text (NFR-002 (b)) appears for commits tier 1 cannot see (between approvals, abandoned cycle).

## Subtasks & Detailed Guidance

### Subtask T097 – Red-first tests through `consolidate` / `--dry-run`, committed red

- **Purpose**: NFR-002 (a), (b), (c-lanes), NFR-010. Each test must fail on the parent commit (WP18's tip) for the stated reason and pass after T100.
- **File**: `tests/consolidation/test_lane_approval_windows.py` (new). Mark the module `pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`.
- **Fixture** `two_wp_lane_with_stray(tmp_path, *, stray: bool, wp01_window: str = "recorded", wp02_window: str = "recorded")`: one code lane carrying WP01 and WP02, built through the real status pipeline so `wp_window` is written by WP07's capture. Sequence: WP01 `planned → claimed → in_progress`, commit WP01 work, review, approve (stamp S1); if `stray`, commit X on the lane (a real content path, e.g. `src/stray.py`); WP02 `claimed → in_progress` (recorded `open_sha` reaches X), commit WP02 work, review, approve (stamp S2). Apply `set_window_state` only for non-`recorded` states. If WP05 already factored this builder into `characterization_support.py`, import it instead.
- **Preconditions** use a `require(condition, message)` helper raising `RuntimeError` (never `assert`): X exists on the lane; X is an ancestor of S2 (`git merge-base --is-ancestor X S2`); WP02's opener carries `wp_window.open_sha`.
- **Tests** (exact names):
  1. `test_stray_commit_between_two_approvals_refuses` (US2-1): run `consolidate --mission <slug> --yes` in process (`run_in_process`). Assert exit code 1, `LANE_MOVED_AFTER_APPROVAL` in output, X's 7-char short SHA and `WP01` in the refusal line, and `ref_shas` of the target, the mission branch and both lane branches unchanged.
  2. `test_stray_commit_between_two_approvals_forecast_refuses` (US2-5): `consolidate --mission <slug> --dry-run --json`. Assert exit 1, payload `error_code == "CLAIM_REFUSED_FORECAST"`, `LANE_MOVED_AFTER_APPROVAL`, short X and `WP01` in `error`; refs unchanged.
  3. `test_own_lane_approval_stamp_does_not_exempt` (US2-7): same fixture; the precondition "X is an ancestor of S2" is the point; assert the fresh-run refusal.
  4. `test_gap_then_recorded_stray_commit_refuses` (NFR-002 (a) mixed, WW-7 second sentence): `wp01_window="not_recorded"`, `stray=True`. Fresh run and `--dry-run --json`, both refuse naming X and WP01.
  5. `test_rewound_wp_commit_from_abandoned_cycle_refuses` (NFR-002 (c), lanes): WP01 claimed, commit C1, `in_progress → planned` (a rewind, `move-task --to planned`), claimed again, commit C2, approved. Assert refusal naming C1, not C2.
- **Red-first**: commit this file alone first (`test(WP19): red-first lane window tests`), run it, confirm every test fails **because no refusal is raised** (not a fixture error), and record the commit SHA and the failure summary with `spec-kitty agent tasks add-history WP19 --note "red: <sha> 5 failed (no refusal)"`.
- **Do not**: hand-write events for the recorded state; assert on full refusal prose (assert code, short SHA, WP id); patch any reconciliation function.

### Subtask T098 – Over-refusal guards (pass before and after)

- **Purpose**: FR-008, FR-009, FR-023 and the FR-007 exception. Each must pass on the parent commit **and** after T100. Commit them with the red tests (they show green on the red commit).
- **Tests** (same file, exact names):
  1. `test_same_fixture_without_stray_passes` (US2-2): `stray=False`; fresh run exits 0.
  2. `test_reviewer_fix_during_review_passes` (US2-3): commit a fix while WP02 is `in_review`, then approve; exit 0.
  3. `test_rejected_and_reapproved_wp_passes[in_progress]` / `[planned]` (US2-4, R-16): reject WP02 from `in_review` to the parametrized lane (a review rejection, no reset), rework commit, re-approve; exit 0.
  4. `test_dependency_chain_stray_is_exempt` (US2-6, FR-007 exception): lane A = the stray fixture; lane B `depends_on_lanes: [lane-a]`, merges lane A's tip (containing X), then its WP03 is approved. Exit 0; no refusal names X. Reuse `build_shape(tmp_path, "dependency_chain")` if it allows the stray step; otherwise extend locally.
  5. `test_all_gap_lane_passes_and_lists_every_wp` (US3-1): every WP `not_recorded`, no late commit; exit 0; `build_approved_wp_set(...)` on the same repo returns `window_gaps` naming WP01 and WP02 with reason `"not recorded"` (claim-level assertion; WP20 renders it).
  6. `test_all_gap_lane_post_approval_refusal_text_is_todays` (US3-2, US3-5): every WP `not_recorded`, `add_post_approval_commit`; the claim refusal text equals `render_refusals([check_lane(<today's arguments>)], slug)` computed in the test with today's anchor list (closed-world anchors + every bounded lane's stamps). Byte equality.
  7. `test_gap_wp_covers_stray_before_recorded_wp` (US3-4, WW-7 weaker check): WP01 recorded, stray X after WP01's approval, WP02 `not_recorded`; exit 0; `window_gaps` lists WP02 only.
  8. `test_attested_approval_window_runs_to_attested_stamp`: strip WP02's approval stamp (`strip_approval_stamps`), run → `APPROVAL_STAMP_MISSING` (unchanged, WW-4); run `consolidate --attest-approved-reviewed WP02 --attest-reason "checked"` → exit 0.
  9. `test_skewed_clock_rework_does_not_narrow_window` (FR-021, D-3): WP01 rejected and reworked, the rework `in_progress` event's `at` rewritten to 1 s **before** WP01's claim `at` (rewrite every copy of the log and commit it, like `set_window_state`); exit 0.
  10. `test_leading_branch_missing_opener_is_skipped` (US1-5): rewrite only WP02's first opener's `wp_window` to `{"schema_version": 1, "gap": {"reason": "lane_branch_missing", "detail": "test"}}`; exit 0 and `window_gaps` is empty.
- **Notes**: if a guard is red on the parent commit, the fixture is wrong; fix the fixture, never the expectation.

### Subtask T099 – Generalise the `write_branch_bound` window machinery to lanes

- **File**: `src/specify_cli/consolidation/write_branch_bound.py`.
- **Steps**:
  1. Add `GapEntry` in `wp_attribution.py` (frozen dataclass: `wp_id: str`, `lane_id: str`, `reason: str` (a `WindowGapReason.report_text`), `cause: str | None = None`, `detail: str = ""`), with a classmethod `from_gap(wp_id, lane_id, gap: WindowGap)`. Add it to `__all__`. It lives beside `WindowGap` (the one home of the window rules) so the claim types module can import it without importing git code.
  2. Add `bind_lane_predicates(repo_root: Path, tip: str) -> tuple[Callable[[str], bool], Callable[[str, str], bool]]`: `on_lane(sha) = resolves_commit(repo_root, sha) and sha_reachable_from(repo_root, sha, tip)`; `is_ancestor(a, b) = sha_reachable_from(repo_root, a, b)`. Neither raises (FR-022: an unresolvable SHA is `NOT_ON_LANE`, never a probe error).
  3. Add `classify_windows(events, wp_ids, *, on_lane, is_ancestor) -> dict[str, WindowOpen | WindowGap]` (pure, calls `window_open_of` per work package).
  4. Generalise `ApprovalWindow` without breaking `single_branch`: keep the class and `degraded` exactly; build lane windows as `ApprovalWindow(wp_id, open_stamp=<WindowOpen.sha or None>, approval_stamp=<stamp>)`. A `WindowGap` gives `open_stamp=None`, which `_window_reach` already reads as "opens at the claim base" (A-8). Do **not** change `approval_windows` here (WP20 changes its `single_branch` derivation).
  5. Add `check_lane_windows(repo_root, *, events, lane_id, branch, approved_wp_ids, claim_base, exemption_anchors, windows, is_bookkeeping, tip) -> tuple[tuple[BoundRefusal, ...], tuple[BoundRefusal, ...]]` returning `(tier_one, tier_two)`: compute `exempt = lane_exempt_commits(repo_root, claim_base, exemption_anchors)` **once**; tier 1 = `check_lane(..., anchors=exemption_anchors, exempt=exempt, tip=tip)`; if it refuses return `((refusal,), ())`; else tier 2 = `_window_refusals(..., windows=windows, exempt=exempt)`.
  6. Add `render_lane_window_refusals(refusals, mission_slug) -> str`: the window block (one `_window_finding`-style line per commit, then the move-back recovery), starting with `LANE_MOVED_AFTER_APPROVAL: `. Reuse `_window_finding`; the single_branch-only `_TOOL_COMMIT_HINT` stays out of the lane text. `render_write_branch_refusals` stays byte-identical.
  7. Add the new public names to `__all__`.
- **In `approved_bound.py`** (the only change there): `check_lane(..., exempt: frozenset[str] | None = None)` keyword; when `None`, compute it as today (`:546`). Behaviour for every existing caller is unchanged.
- **Unit tests** in `tests/consolidation/test_write_branch_bound.py`: `test_bind_lane_predicates_unresolvable_sha_is_not_on_lane`, `test_classify_windows_gap_and_open`, `test_check_lane_windows_tier_one_refusal_returned_alone`, `test_check_lane_windows_stray_between_windows_names_preceding_wp`, `test_check_lane_exempt_keyword_matches_computed_exempt`. Existing tests in that file stay green unchanged.

### Subtask T100 – The lane leg of `_approved_bound_verdict`

- **File**: post-split home of `_approved_bound_verdict` (planned `reconciliation_bound.py`).
- **Steps**:
  1. Build per-lane stamp lists once: `stamps_by_lane = {lane.lane_id: [approval stamps of _bound_approved_wp_ids(lane, ...) that are not None]}`. Keep `approval_stamp_anchors` (other callers may use it) and its output order.
  2. Extract `_lane_verdict(repo_root, lane, *, events, tip, claim_base, closed_world, stamps_by_lane, ...)` returning a small frozen `_LaneVerdict(tier_one: tuple[BoundRefusal, ...], tier_two: tuple[BoundRefusal, ...], gaps: tuple[GapEntry, ...])`.
  3. In `_lane_verdict`: `on_lane, is_ancestor = bind_lane_predicates(repo_root, tip)` with the **tip the loop already resolved** (FR-022). `classes = classify_windows(events, approved, ...)`. `gaps` = one `GapEntry` per `WindowGap`.
  4. **All-gap lane** (no `WindowOpen` in `classes`): call `check_lane` exactly as today, `anchors=[*closed_world, *<every bounded lane's stamps in today's order>]`, **no** `exempt` keyword. Return its refusal as tier 1. This is FR-023 by construction.
  5. **Window lane**: `exemption_anchors = [*closed_world, *(stamp for other in lanes if other.lane_id != lane.lane_id for stamp in stamps_by_lane[other.lane_id])]`. Select other lanes **by lane id, never by SHA set difference** (a dependent lane's stamp can equal this lane's tip; it must stay an anchor). Build windows from `classes` and the approval stamps; call `check_lane_windows`.
  6. Collect across lanes in lane order. Render: tier-1 refusals of all lanes through `render_refusals` (today's text), then, if any, the tier-2 block from `render_lane_window_refusals`, joined by `"\n"`. When there is no tier-2 refusal the text is byte-identical to today.
  7. A lane whose tip does not resolve keeps today's `continue` (no verdict, no gaps).
- **Do not**: change refusal order inside `build_approved_wp_set` (C-006); add a refusal code; touch `lane_tips_moved_refusal` (the gate re-check is not windowed); touch planning lanes, canceled work packages (WW-5) or `_write_branch_verdict` (WP20).

### Subtask T101 – One resolved lane tip on every path

- **Purpose**: FR-022: claim, forecast, resume, gate rebuild and `approved_bound_refusal` all reach the classifier through `_approved_bound_verdict`, so binding the predicates to the tip resolved in its loop covers every path. Prove it.
- **Tests** (in `test_lane_approval_windows.py`):
  - `test_approved_bound_refusal_matches_claim_refusal`: on the US2-1 fixture, `approved_bound_refusal(repo, feature_dir, manifest, coord_base_ref=<the fresh run's base>, excluded_window_base=<target tip>)` equals the `refusal` of `build_approved_wp_set(...)` with the same inputs (byte equality).
  - `test_classifier_reads_the_tip_the_bound_resolved`: spy `bind_lane_predicates` through `monkeypatch.setattr` on the module that looks it up (the bound module, not the facade) and assert every recorded `tip` equals the lane's entry in `claim.bound_lane_tips`.
  - `test_not_on_lane_open_sha_is_a_gap_not_a_probe_error`: `set_window_state(..., "not_on_lane")` for every WP; consolidate raises no probe-error refusal; the verdict equals the all-gap verdict; `window_gaps` reason is `"not on lane"`.

### Subtask T102 – `window_gaps` on the claim

- **Steps**:
  1. `_BoundVerdict` gains `window_gaps: tuple[GapEntry, ...] = ()`, sorted by `(lane_id, wp_id)`.
  2. `ApprovedWpCommitSet` gains `window_gaps: tuple[GapEntry, ...] = ()` appended **last** (data-model section 5; positional constructions stay valid; C-006).
  3. Populate it on the passing claim (`:1845-1866` today) **and** on the claim produced by a bound refusal (`_refusal_claim`, add a defaulted keyword). On a `_compound_refusal` it may stay empty; record that choice with `spec-kitty agent tracer-append --category design-decisions`.
  4. Do **not** render anything (WP20). Do not change `orchestrator-api` (no envelope change, spec Assumption).
- **Check**: `tests/consolidation/test_reconciliation_surface_pin.py` stays green (new names are additions; if the pin rejects additions, stop and ask the orchestrator: WP04 owns it).

### Subtask T103 – NFR-007 query count; flip pins (a), (b), (c-lanes); regenerate named cells only

- **Query count** — `tests/consolidation/test_lane_window_query_count.py` (new):
  - Fixture `one_lane_mission(tmp_path, *, wps: int, commits_per_wp: int)`: one code lane, `wps` work packages built sequentially (claim → `commits_per_wp` content commits → review → approve), real status pipeline.
  - Seam: wrap `specify_cli.consolidation.git_probes.run_command` with `monkeypatch.setattr`, counting calls whose `cmd[1]` is `"rev-list"` or `"merge-base"` (`rev-parse` does not count). Measure only `approved_bound_refusal(...)` on a passing lane.
  - `test_window_check_cost_is_independent_of_commit_count[3]` / `[6]`: count at `commits_per_wp=2` equals count at `commits_per_wp=20`.
  - `test_window_check_cost_grows_linearly_with_wps`: `count(6) - count(3) <= 3 * _PER_WP_BUDGET` with `_PER_WP_BUDGET = 8` (a named constant with a comment deriving it: 1 `on_lane` merge-base, ≤ k² topology merge-bases, 2 window rev-lists, 1 tier-1 stamp rev-list).
  - `test_exempt_set_computed_once_per_lane`: spy `lane_exempt_commits` in the module that looks it up; exactly one call per window lane.
- **Flip pins** in `tests/consolidation/test_reconciliation_intended_verdicts.py`: remove the `xfail` from `test_commit_between_two_approvals_is_refused`, `test_gap_then_recorded_stray_commit_is_refused`, `test_window_refusal_names_commit_and_preceding_wp`, and from the **`lanes`** case of `test_rewound_wp_window_opens_after_rewind`. If the `xfail` marks the whole parametrized test, split it: `pytest.param("lanes", id="lanes")` and `pytest.param("single_branch", id="single_branch", marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason="NFR-002 (c) single_branch, FR-011/FR-021, flipped by WP20"))`. Leave `test_parallel_claims_window_is_not_over_wide` (named residual WW-6) and every WP16/17/18 test untouched.
- **Regenerate only named cells** (WP02 helpers): `regenerate_cells([...])` with the keys of the (a), (a-mixed), (b) and (c-lanes) cells, or `SPEC_KITTY_REGEN_VERDICT_CORPUS=1` then inspect. Then the machine check (post-tasks squad R-03; run after the fix commit and on the final commit) must print exactly the allowed keys below:
  ```bash
  BASE=$(git rev-parse <red-commit>^)   # WP18's tip
  ALLOWED='<the (a), (a-mixed), (b), (c-lanes) keys and any applicable resume twins, comma-separated, recorded in the history note before regenerating>'
  uv run --frozen python -c "import sys; from tests.consolidation.characterization_support import changed_cells; c = changed_cells('$BASE'); a = sorted(sys.argv[1].split(',')); print(c); assert c == a, ('changed cells differ from the allowed list', c, a)" "$ALLOWED"
  ```
  The table names the cells:

  | Cell (find the key with `grep -n` on the variant names WP02 used: `between_two_approvals`, `gap_then_recorded`, `rewound`) | Before | After |
  |---|---|---|
  | fresh, two-WP lane, stamp present, window recorded, between-two-approvals (a) | pass, exit 0 | refuse `LANE_MOVED_AFTER_APPROVAL`, exit 1 |
  | forecast twin of (a) | pass, exit 0 | refuse, error code `CLAIM_REFUSED_FORECAST`, `LANE_MOVED_AFTER_APPROVAL` in the message, exit 1 |
  | fresh + forecast, gap-then-recorded (a mixed) | pass | refuse as above |
  | the (b) refusal-text cell | pass, no text | the window text naming `<sha:X>` and `WP01` |
  | fresh + forecast, rewound work package, lanes (c) | pass | refuse naming the abandoned-cycle commit |
  | resume twins of the above | only if WP02 recorded them as applicable | same flip |

  **Must not change**: the dependency-chain cell (FR-007 exception), the US3-4 weaker-check cell, the FR-023 all-gap text cell, the skewed-clock and leading-branch-missing cells, every post-approval cell (tier-1 text is unchanged by design), every all-gap cell. **Any other changed cell is a STOP**: revert the JSON, investigate (a fixture that records a claim after its lane work is the usual cause), and report to the orchestrator; never regenerate it silently.
- **Seeded mutations** (`tests/consolidation/test_reconciliation_seeded_mutations.py`): must stay green. Edit only a mutation-table row whose expected red cell is one of the flipped cells, and record why in the WP history.
- **Changelog fragment (this work package owns it; orchestrator decision 2026-11-08)**: create `docs/changelog/unreleased/7403-lane-approval-window-refusal.changed.md` with exactly one entry, section `changed`, no version bump:
  `- **\`spec-kitty consolidate\` refuses a commit made between two approvals on a lane** (#7403, #5721). **Before:** a commit made after one work package's approval and before the next one started landed, because the later approval stamp reached it. **After:** each approved work package covers only its recorded window, and such a commit is refused with \`LANE_MOVED_AFTER_APPROVAL\`, naming the commit and the work package approved before it. A commit another lane's approval stamp reaches stays exempt.`
  Run `uv run --frozen python -m scripts.docs.check_changelog_style` and `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`. WP20 keeps its own gap-report fragment; do not write that one.
- **Precedence-matrix rows** (post-tasks squad R-06; this WP introduces the window refusal text, so it owns its rows): in a **new** file `tests/consolidation/test_refusal_precedence_matrix_windows.py` that imports WP03's pair fixtures and normalizer from `tests/consolidation/test_refusal_precedence_matrix.py` (do **not** edit WP03's file: it belongs to another lane, and editing it would merge the two lanes), **add** one pair row per refusal the tier-2 window refusal can compose with through `_compound_refusal` (mixed-lane, canceled-dependency) and per refusal it can precede or follow on the same claim, each with its full normalized text, using WP03's fixture conventions. **STOP rule**: if WP03's unchanged matrix goes red (an existing row's text or order changed) it is a STOP — revert, investigate (usually a WP03 fixture that commits lane work before its `claimed` event, which the window model now refuses), and report to the orchestrator. Record the new row count in the history note.
- **Fix commit**: see the commit plan below; record its SHA in the WP history.

## Commit plan (red first; post-tasks squad R-12)

1. **Red commit** — T097 tests + T098 guards (`test(WP19): red-first lane window tests`): 5 red, guards green.
2. **Fix commit** — T099-T102 **plus** the four WP05 pin flips (T103 "Flip pins", the `lanes` (c) case split out) **plus** the named-cell regeneration and the new precedence-matrix file. The pins flip in the **same** commit as the code that makes them pass, so no commit on the lane has a strict `xfail` XPASSing (red on that commit).
3. **Follow-up commit** — the T103 query-count test, if not already in the red commit, and the changelog fragment.

Never squash these, never amend the red commit. Each commit must be green except the red commit's five named tests.

## Test Strategy

ATDD/red-first: T097 + T098 committed first (5 red, 10+ green), then T099-T102, then T103. Unit tests for the window machinery sit beside the entry-point tests, never instead of them (NFR-010).

## Definition of Done

Run and record exact commands with pass/fail counts in the WP history:

```bash
uv run --frozen pytest -q tests/consolidation/test_lane_approval_windows.py tests/consolidation/test_lane_window_query_count.py tests/consolidation/test_write_branch_bound.py tests/consolidation/test_approved_bound.py tests/consolidation/test_approved_bound_residuals.py
uv run --frozen pytest -q -rxX tests/consolidation/test_reconciliation_intended_verdicts.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py tests/consolidation/test_refusal_precedence_matrix.py tests/consolidation/test_refusal_precedence_matrix_windows.py tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py tests/consolidation/test_reconciliation_seeded_mutations.py tests/consolidation/test_claim_inputs_parity.py tests/consolidation/test_resume_frozen_anchors.py
uv run --frozen pytest -q tests/integration/test_single_branch_approval_windows.py tests/orchestrator_api/test_consolidate_mission_post_approval.py tests/orchestrator_api/test_single_branch_bound_preflight.py
uv run --frozen pytest -q tests/consolidation/ tests/terminus/
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_exemption_registry_ratchet.py tests/architectural/test_no_legacy_terminology.py
uv run --frozen ruff check src/specify_cli/consolidation tests/consolidation/test_lane_approval_windows.py tests/consolidation/test_lane_window_query_count.py
uv run --frozen ruff check --select C901 src/specify_cli/consolidation
uv run --frozen ruff format --check --force-exclude src/specify_cli/consolidation/write_branch_bound.py src/specify_cli/consolidation/approved_bound.py src/specify_cli/consolidation/reconciliation_bound.py src/specify_cli/consolidation/reconciliation_claim.py src/specify_cli/consolidation/reconciliation_claim_types.py src/specify_cli/consolidation/wp_attribution.py tests/consolidation/test_lane_approval_windows.py tests/consolidation/test_lane_window_query_count.py tests/consolidation/test_write_branch_bound.py tests/consolidation/test_reconciliation_intended_verdicts.py
uv run --frozen mypy src/specify_cli/consolidation/write_branch_bound.py src/specify_cli/consolidation/approved_bound.py src/specify_cli/consolidation/reconciliation_bound.py src/specify_cli/consolidation/wp_attribution.py
make test-fast
```

- [ ] Red-first evidence: the red commit SHA (5 failed for "no refusal", guards green) and the fix commit SHA are in the WP history. **Because lane SHAs can become unreachable after a squash consolidation with cleanup** (post-tasks squad R-14), also paste, for each red test, its full test id and the assertion message pytest printed (`uv run --frozen pytest -q -rf <test>` at the red SHA), so the PR and the post-merge mission review can check the red without checking out the SHA.
- [ ] `-rxX`: the four flipped tests now pass; `[single_branch]` rewound, the WW-6 residual and no other pin changed.
- [ ] Golden diff ⊆ the named cells in the T103 table; no other cell changed.
- [ ] Every refusal test asserts `ref_shas` unchanged (NFR-010).
- [ ] No new `# noqa`, `# type: ignore` or allowlist entry; every added or changed function ≤ 15.
- [ ] Classify every red in `tests/consolidation/` / `tests/terminus/` per the CLAUDE.md baseline-red gotcha; a red caused by a fixture that records a claim after its lane work is reported (file, test) to the orchestrator before you change any file outside `owned_files`.
- [ ] **Tracer files** (canonical writer only, no hand edits of `traces/*.md`, no `add-history` fallback; post-tasks squad R-02): `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category design-decisions --actor "implement WP19" --entry "<summary>. <detail>"` for the two-tier design and the tier-1 text consequence; other lanes selected by lane id; the compound-refusal gaps choice; the `_PER_WP_BUDGET` derivation; the precedence-matrix row count before/after; `--category tooling-friction` for any friction. The command works from any checkout (lane worktree included) and commits to the coordination surface itself.
- [ ] `changed_cells(<red commit>^)` equals the allowed list recorded before regenerating (T103 machine check).
- [ ] Precedence matrix: the new tier-2 rows live in `test_refusal_precedence_matrix_windows.py` and pass; WP03's `test_refusal_precedence_matrix.py` is unchanged and green (its existing rows are the STOP check); row count recorded.
- [ ] `docs/changelog/unreleased/7403-lane-approval-window-refusal.changed.md` exists with the one FR-007 entry; the changelog style and spelling checks pass.
- [ ] Never run `make test-full`.

## Risks & Mitigations

- **Over-refusal from fixtures that record claims after the work**: since WP07, every pipeline move writes `wp_window`, so a fixture that commits lane work before its `claimed` event now opens its window after that work. Classify; never weaken the rule.
- **Own-stamp exemption leaking back**: `test_own_lane_approval_stamp_does_not_exempt` plus selection of other lanes by lane id.
- **Dependency chain refused**: `test_dependency_chain_stray_is_exempt`.
- **All-gap text drift**: the all-gap branch calls `check_lane` with today's exact anchors and no `exempt` keyword; `test_all_gap_lane_post_approval_refusal_text_is_todays`.
- **Complexity creep in `_approved_bound_verdict`**: the `_lane_verdict` extraction.

## Review Guidance

- Reviewer profile: `reviewer-renata`.
- **Model tier: top** (soundness-critical; IC-13).
- Verify WW-2, WW-2a, WW-3, WW-7 one by one against code and tests.
- Check the red commit really fails for "no refusal" (re-run it at the red SHA).
- Check the tier-1/tier-2 interpretation of NFR-002 (b) in the tracer entry; the operator can overturn it.
- Check `approved_bound_refusal` (the `orchestrator-api` door) yields the same text as the claim (T101).
- Check no golden cell outside the T103 table changed.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP19 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP19 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
