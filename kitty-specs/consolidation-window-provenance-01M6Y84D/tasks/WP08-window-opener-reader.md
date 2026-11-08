---
work_package_id: WP08
title: Window opener reader, gap typing and dossier SHA classification
dependencies:
- WP07
requirement_refs:
- FR-004
- FR-005
- FR-021
- FR-022
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T041
- T042
- T043
- T044
- T045
- T046
phase: Phase 2 - Record and unify inputs
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/wp_attribution.py
create_intent:
- tests/consolidation/test_window_opener.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/wp_attribution.py
- tests/consolidation/test_window_opener.py
- tests/architectural/test_dossier_sha_provenance.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Window opener reader, gap typing and dossier SHA classification

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
- **Report progress**: `spec-kitty agent tasks add-history WP08 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

One home for the window rules (C-001, FR-004, FR-021, FR-022): a reader in `src/specify_cli/consolidation/wp_attribution.py` that, given a work package's events and two predicates bound by the caller to the one lane tip, returns `WindowOpen(sha)` or `WindowGap(reason, ...)`.

Done means:

1. `WindowGapReason` (closed enum: `NOT_RECORDED`, `CAPTURE_FAILED`, `LANE_BRANCH_MISSING`, `NOT_ON_LANE`, with report strings "not recorded", "capture failed", "lane branch missing", "not on lane"), `WindowOpen`, `WindowGap` exist with `__all__` entries (C-007 convention).
2. `window_opener_events(events, wp_id, *, cycle: bool)` is the **one** opener selector (data-model section 3 steps 1-3, contract R-1).
3. `window_open_of(events, wp_id, *, on_lane, is_ancestor) -> WindowOpen | WindowGap` implements binding (step 4-5), contract R-2..R-5, and performs **no git read**.
4. `approval_window_open_stamp` is re-expressed through `window_opener_events(..., cycle=False)` with **unchanged** behaviour (today's first-claim rule, kept for `single_branch` derivation, FR-011). `first_governed_open_stamp` is untouched (named variant "lane anchor").
5. `("status.events.jsonl", "policy_metadata.wp_window.open_sha")` is classified `BRANCH_RELATIVE` in `DOSSIER_SHA_FIELDS` (FR-005).
6. Unit tests cover every rule; corpus unchanged (the reader is not yet called by the gate; WP19 wires it).

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/data-model.md` section 3 (**the algorithm, step by step**; outcome table; `on_lane` definition) and section 4 lifecycle.
- `kitty-specs/consolidation-window-provenance-01M6Y84D/contracts/status-event-wp-window.md` — reader rules R-1..R-7, JSON Schema (for R-5 validation).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md` — FR-004, FR-005, FR-021, FR-022, US1-3..US1-7, Edge Cases (clock skew, rewind, review rejection, branch missing, not on lane), Assumption "Returned to planned excludes review rejections".
- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-07 (Risks: one selector, predicates passed by caller, test list).
- Code: `wp_attribution.py` — `stamp_of` (~243), `first_governed_open_stamp` (~665), `approval_window_open_stamp` (~683), `_ENTERED_IMPLEMENTATION_LANES`, `is_migration_event`. `status/lane_head.py` (`WP_WINDOW_KEY` from WP07).
- `tests/architectural/test_dossier_sha_provenance.py` — `DOSSIER_SHA_FIELDS` (~96), the `lane_head` row (~119-121) to copy, the scanner that discovers SHA fields (check it walks nested dicts so it reports `policy_metadata.wp_window.open_sha`; if it does not, the row is still required by FR-005 and the mutation control at ~270 shows how the gate behaves).
- Cross-cutting: C-009, C-013, C-014, NFR-004 (each function <= 15; split the selector into `_cycle_start_index`, `_candidates`, `_skip_leading_branch_missing`, `_bind`), NFR-005.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP08 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Subtasks & Detailed Guidance

### Subtask T041 – Value types

- **Steps**: In `wp_attribution.py` add:
  - `class WindowGapReason(StrEnum)` with values `not_recorded`, `capture_failed`, `lane_branch_missing`, `not_on_lane` and a `report_text` property returning the space-separated form.
  - `@dataclass(frozen=True) class WindowOpen: sha: str`.
  - `@dataclass(frozen=True) class WindowGap: reason: WindowGapReason; cause: str | None = None; detail: str = ""; sha: str | None = None; malformed: bool = False`.
  - Add all three plus the two functions of T042/T043 to the module's `__all__`.

### Subtask T042 – `window_opener_events(events, wp_id, *, cycle)`

- **Rules** (data-model section 3; implement exactly):
  1. Filter to events of `wp_id`; ignore migration events (`is_migration_event`).
  2. `cycle=True`: the cycle starts **after** the work package's last event with `to_lane == planned` whose `from_lane` is **not** in {`for_review`, `in_review`, `approved`, `done`} (the genesis seed counts as a cycle start). Find it in event-log order (the order of `events` as read by `read_events`, not re-sorted by `at`). `cycle=False`: no cycle start (the whole history).
  3. Candidates: the cycle's events with `to_lane` in {`claimed`, `in_progress`}, in event-log order. `blocked` is never a candidate.
  4. `cycle=True` only: drop **leading** candidates whose `policy_metadata.wp_window.gap.reason == "lane_branch_missing"`. Return a small result object: `OpenerSelection(candidates: tuple[StatusEvent, ...], skipped_branch_missing: int)`.
  5. `cycle=False`: no skip; return candidates as-is.
- **Notes**: Keep it pure; no git.

### Subtask T043 – `window_open_of(events, wp_id, *, on_lane, is_ancestor)`

- **Binding** (data-model section 3 step 4-5, contract R-1(d)-(e), R-2..R-5):
  1. Selection with `cycle=True`. No candidates and `skipped_branch_missing > 0` -> `WindowGap(LANE_BRANCH_MISSING, detail=<detail of last skipped>)`. No candidates at all -> `WindowGap(NOT_RECORDED)` (incl. a work package approved by a forced path that never entered `claimed`/`in_progress`).
  2. Parse each candidate's `wp_window` with `_parse_wp_window(value) -> _Parsed | None`: validate `schema_version == 1`, exactly one of `open_sha` (40 lowercase hex) / `gap` (`reason` in the closed set; `capture_failed` requires `cause` in {`git_error`, `probe_error`}; `lane_branch_missing` forbids `cause`), no extra keys. A violation -> treated as absent with `malformed=True` (R-5): never trusted, never fatal.
  3. First remaining candidate has no usable value: no key -> `WindowGap(NOT_RECORDED)`; malformed -> `WindowGap(NOT_RECORDED, malformed=True)`; `capture_failed` -> `WindowGap(CAPTURE_FAILED, cause, detail)`. **An unrecorded opener is never replaced by a later recorded one.**
  4. Otherwise, among remaining candidates carrying `open_sha` (ignore SHA-less candidates after the first SHA-bearing one): choose the one whose SHA `is_ancestor(candidate_sha, other_sha)` for **every** other; if no such SHA exists (unrelated SHAs), choose the first in event-log order.
  5. `on_lane(chosen_sha)` false -> `WindowGap(NOT_ON_LANE, sha=chosen_sha)` (covers "not an ancestor of the lane tip" and "does not resolve in this clone"; never a probe error, FR-022). Else `WindowOpen(chosen_sha)`.
  6. `on_lane` and `is_ancestor` are callables passed by the caller (bound to the one lane tip the approved bound resolves; WP19 binds them). Type them `Callable[[str], bool]` and `Callable[[str, str], bool]`. Document that `is_ancestor(a, b)` means "a is an ancestor of or equal to b" and must not raise (callers wrap git errors as False).

### Subtask T044 – `approval_window_open_stamp` through the selector

- **Steps**: Re-implement as: first candidate of `window_opener_events(events, wp_id, cycle=False)`, return `stamp_of(candidate)` or `None`. Keep its docstring rationale (first entry only, `blocked` opens nothing) and add a sentence that the selector is shared with `window_open_of`. Behaviour must be byte-identical: run `tests/integration/test_single_branch_approval_windows.py` and the `write_branch_bound` tests before and after.

### Subtask T045 – Dossier SHA classification [P]

- **Steps**: In `tests/architectural/test_dossier_sha_provenance.py`, add beside the `lane_head` row:
  ```python
  # status/transition_pipeline.py: the window-open SHA on a work package's
  # opening transition (wp_window, Mission consolidation-window-provenance-01M6Y84D);
  # provenance of the lane branch, valid for one consolidation attempt.
  ("status.events.jsonl", "policy_metadata.wp_window.open_sha"): _BR,
  ```
  Match the existing comment style. This map is a classification registry, not an allowlist (plan Charter Check row "NFR-005 vs FR-005").

### Subtask T046 – Unit tests `tests/consolidation/test_window_opener.py`

- **Test names** (build `StatusEvent` lists in memory; fake predicates):
  - `test_single_recorded_claim_opens_window`
  - `test_no_wp_window_key_is_not_recorded_gap` (FR-004, read per event)
  - `test_mixed_log_straddling_upgrade_reads_per_event`
  - `test_capture_failed_carries_cause_and_detail`
  - `test_leading_lane_branch_missing_is_skipped_then_in_progress_sha_opens` (US1-5)
  - `test_only_lane_branch_missing_openers_give_lane_branch_missing_gap`
  - `test_unrecorded_first_opener_is_not_replaced_by_later_recorded_one`
  - `test_rewind_to_planned_starts_new_cycle` (US1-6, `in_progress -> planned`)
  - `test_review_rejection_to_planned_does_not_reset` (US1-7, `in_review -> planned`; also `approved -> planned`)
  - `test_review_rejection_to_in_progress_does_not_reset`
  - `test_blocked_opens_nothing` (US1-3)
  - `test_migration_events_never_open_or_reset` (US1-4)
  - `test_skewed_clock_rework_cannot_narrow_window` (rework event `at` earlier than the claim, but its SHA is a descendant: topology order wins)
  - `test_unrelated_shas_fall_back_to_log_order`
  - `test_sha_not_on_lane_is_not_on_lane_gap`
  - `test_unresolvable_sha_is_not_on_lane_gap` (on_lane returns False; no exception)
  - `test_malformed_value_is_not_recorded_and_flagged` (unknown version, both branches, neither, bad hex, extra key, `lane_branch_missing` with a cause)
  - `test_forced_approval_without_opener_is_not_recorded`
  - `test_approval_window_open_stamp_unchanged_first_claim_rule` (cycle=False: first claim even after a rewind; no skip)

## Test Strategy

ATDD: write the unit tests first. Pure tests (no git) for the reader; run the existing `single_branch` integration tests for T044.

## Definition of Done

```bash
uv run --frozen pytest -q tests/consolidation/test_window_opener.py
uv run --frozen pytest -q tests/architectural/test_dossier_sha_provenance.py
uv run --frozen pytest -q tests/integration/test_single_branch_approval_windows.py
uv run --frozen pytest -q tests/consolidation/ -k "attribution or write_branch or canceled or window"
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py tests/consolidation/test_reconciliation_intended_verdicts.py
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py
uv run --frozen ruff check src/specify_cli/consolidation/wp_attribution.py tests/consolidation/test_window_opener.py tests/architectural/test_dossier_sha_provenance.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/consolidation/wp_attribution.py tests/consolidation/test_window_opener.py tests/architectural/test_dossier_sha_provenance.py
uv run --frozen mypy src/specify_cli/consolidation/wp_attribution.py
make test-fast
```

- [ ] Corpus golden file unchanged; intended verdicts all still `xfailed`.
- [ ] `approval_window_open_stamp` behaviour unchanged (integration tests green before and after).
- [ ] The reader performs no git read (no import of `git_probes` / `kernel.git` used inside it).
- [ ] Complexity <= 15 for every new function.
- [ ] **Tracer files**: dated entries in `kitty-specs/consolidation-window-provenance-01M6Y84D/traces/design-decisions.md` (any rule ambiguity you resolved and why) and `traces/tooling-friction.md`. Format `- **[YYYY-MM-DD][implement WP08] <summary>.** <detail>`. No `kitty-specs/` in your checkout: `spec-kitty agent tasks add-history WP08 --note "..."`.
- [ ] Never run `make test-full`.

## Risks & Mitigations

- **Soundness of the opener rule**: every FR-021 clause has a named test; the reviewer checks them clause by clause.
- **Wall-clock re-sort**: never sort events by `at`; the caller passes events in log order.
- **Two opener implementations**: T044 removes the duplicate rule.

## Review Guidance

- Reviewer profile: `reviewer-renata`.
- **Model tier: top** (soundness-critical rule).
- Walk FR-021 and contract R-1 (a)-(e) against the code; each clause must map to a branch and a test.
- Confirm the review-rejection interpretation is implemented exactly as the spec Assumption states.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP08 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP08 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
