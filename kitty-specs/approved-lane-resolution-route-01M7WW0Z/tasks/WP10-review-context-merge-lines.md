---
work_package_id: WP10
title: Review context lists merge resolutions
dependencies: []
requirement_refs:
- FR-007
planning_base_branch: fix/approved-lane-resolution-route
merge_target_branch: fix/approved-lane-resolution-route
branch_strategy: Planning artifacts for this mission were generated on fix/approved-lane-resolution-route. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/approved-lane-resolution-route unless the human explicitly redirects the landing branch.
subtasks:
- T037
- T038
- T039
phase: Phase 2 - Behaviour
history:
- at: '2026-11-20T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/review/
create_intent:
- tests/review/test_review_context_merge_lines.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/review/wp_range.py
- src/specify_cli/review/context_block.py
- tests/review/test_review_context_merge_lines.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP10 – Review context lists merge resolutions

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

The re-approval is the only guard on a conflict resolution (C-001, Edge Case "residual by design"). A plain range diff blends the resolution into the sibling's already-approved content and can hide a novel line. So the review context must point the reviewer at each merge's own resolution (FR-007, US5, `contracts/review-context-merges.md`):

- `resolve_wp_review_range` (the single owner of the review range, ADR `2026-11-08-2`) lists **every** merge commit in `base..tip`, with `git rev-list --merges --full-history`, no pathspec, so history simplification never drops a merge.
- `render_review_context` prints, after the REVIEW COMMANDS lines, one line per merge:
  `RESOLUTION MERGE (operator-authored, review these bytes): git show --remerge-diff <sha>`
- On a git without remerge-diff (< 2.36) it prints instead:
  `RESOLUTION MERGE <sha12>: this git cannot show the resolution (needs git >= 2.36); review the merge by hand`
- A range with no merges renders byte-for-byte as today.
- The renderer stays pure (no git, no filesystem, no clock) and keeps C-001 of the review-context contract: commands only, never patch text.

Done means: T037 tests red then green, existing `tests/review/test_context_block.py`, `test_wp_range.py`, `test_wp_range_default_coord.py` and `test_wp_range_git_calls.py` green unchanged.

## Context & Constraints

- Read: `.kittify/charter/charter.md`; mission `spec.md` (US5, FR-007, Edge Case on git without remerge-diff), `plan.md` IC-06, `research.md` R-08, `contracts/review-context-merges.md`, `data-model.md` (`WpReviewRange` gains `merges` and `remerge_available`), `tasks.md`.
- Squad evidence: architect F6 and doctrine finding 5 (`squad2/`): FR-007 must not render bytes; range data belongs in `wp_range`; reviewer-renata FR-007 finding (a pathspec-limited merge listing silently omits merges).
- The review-context contract lives in another Mission's directory (`kitty-specs/review-context-wp-diff-01M774QF/contracts/review-context-block.md`). This WP does not edit it. WP13 records the amendment in ADR `2026-11-08-2`. You update the `context_block.py` module docstring (`:1-44`, the shape block and the C-001 sentence) so the code's own contract text names the new line.
- **Integrity invariants**:
  - C-001 (this Mission): nothing here attributes or approves anything; the line is advisory text for the reviewer.
  - C-002: no gate verdict changes; review proceeds when the resolution cannot be shown (US5 AS2).
  - C-006 single authority: `wp_range` remains the only range owner; reuse `specify_cli.git.merge_tree_probe.remerge_diff_available` (`src/specify_cli/git/merge_tree_probe.py:48-54`) rather than a new version probe. Do not add a third remerge probe: you list commands, you do not run `--remerge-diff`.
  - Fail-soft (wp_range's own FR-013/NFR-004 rule, docstring `:61-63`): a failed merge listing never raises; it names the step in `listing_gap` and leaves `merges` empty. The renderer then prints the existing "listing incomplete" note, so a reviewer is told to run the commands.
- NFR-002 of the review range (a constant number of git processes, `tests/review/test_wp_range_git_calls.py`): today the recorded range costs **6** git processes for both 1 and 200 commits (measured at HEAD 4aeef9f7; budget `_BUDGET = 10`, derived `_DERIVED_BUDGET = 12`). You add exactly one `rev-list` per range, and the `git --version` probe only when at least one merge was found. The budget fixtures have no merges, so the expected new count is 7. That test file is not owned by this WP: do not edit it; if your change breaks it, fix the code.
- Terminology: Mission, review range, "resolution merge". Never "sync".

## Branch Strategy

- **Strategy**: set by finalize-tasks
- **Planning base branch**: fix/approved-lane-resolution-route
- **Merge target branch**: fix/approved-lane-resolution-route

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implement command: `spec-kitty agent action implement WP10 --agent claude --mission approved-lane-resolution-route-01M7WW0Z`

## Current code at HEAD (read before editing)

- `src/specify_cli/review/wp_range.py` (650 lines)
  - Module docstring `:1-63`; note `:38-43`: the commit list follows git's default walk with **default history simplification**, so a merge whose combined diff does not touch the owned files is not listed. That is exactly why the new list must not reuse `_log`.
  - `WpReviewRange` (`:184-226`): `frozen=True, slots=True`; invariant in `__post_init__` (`:210-214`); `unavailable` constructor (`:221-235`).
  - `_Listing` (`:431-445`) with `attempt(step, action)`: the fail-soft wrapper you reuse.
  - `_log` (`:448-450`), `_count` (`:474-476`, the `run_git(..., "rev-list", ...)` pattern).
  - `_ListingRequest` (`:480-487`), `_listing` (`:490-523`): the four existing steps.
  - `resolve_wp_review_range` (`:596-650`): builds the range from `_listing(...)`.
- `src/specify_cli/review/context_block.py` (360 lines)
  - Docstring `:1-44` (shape, budget rule, C-001 sentence at `:42-43`).
  - `BYTE_BUDGET` (`:58`), `LABEL_LEN` (`:60`), `_COMMANDS_HEADING` (`:71`).
  - `_command_lines` (`:214-220`); `render_review_context` (`:320-360`): the command lines are printed outside the byte budget (ruling Q11, comment `:335`), after `*outside` and before the requirements (`:351-360`).
  - `_unavailable_lines` (`:309-314`): an unavailable range has no base/tip and so no merges.
- `src/specify_cli/git/merge_tree_probe.py::remerge_diff_available` (`:48`): one `git --version`; unreadable means unavailable (fail-closed for verdicts; for this advisory line it means "cannot show").
- Layering: `specify_cli.review` importing `specify_cli.git.merge_tree_probe` stays inside `specify_cli`; `tests/architectural/test_layer_rules.py` lists `review` (`:195`) — run it.

## Subtasks & Detailed Guidance

### Subtask T037 – Red tests

- **Purpose**: pin the merge listing and the renderer lines before writing them.
- **File**: `tests/review/test_review_context_merge_lines.py` (new).
- **Renderer-level tests (pure, fast, no git)**: build `WpReviewRange` values by hand (copy the construction pattern of `tests/review/test_context_block.py`) and call `render_review_context`.
  1. `test_merges_render_one_labelled_line_each`: a range with `merges=("a"*40, "b"*40)` and `remerge_available=True` renders exactly two lines `  RESOLUTION MERGE (operator-authored, review these bytes): git show --remerge-diff <full sha>`, in range order, after the `git diff` command line and before `CITED REQUIREMENTS:`. Full SHAs in commands, as the module's rule says (`:32-35`).
  2. `test_merges_without_remerge_support_render_the_cannot_show_line`: `remerge_available=False` renders `RESOLUTION MERGE <sha12>: this git cannot show the resolution (needs git >= 2.36); review the merge by hand` per merge and no `--remerge-diff` command.
  3. `test_no_merges_renders_unchanged`: for each fixture range in `test_context_block.py` style (recorded, derived, unscoped, with notes), the output with the new fields at their defaults is equal to the output computed from a range built without them. Since the new fields have defaults, compare against a frozen expected list for one representative range so a reordering is caught.
  4. `test_merge_lines_do_not_consume_the_byte_budget`: a range whose commit list exactly fills `BYTE_BUDGET` still prints every merge line (they are command lines, outside the budget like REVIEW COMMANDS, ruling Q11), and the commit list is not shortened because of them.
  5. `test_unavailable_range_prints_no_merge_line`.
- **Range-level tests (real git, `pytest.mark.git_repo`)**: reuse the recorded-lane fixture approach of `tests/review/test_wp_range_git_calls.py:39-58` (`characterization_support._bootstrap_one_lane_coord`, `allocate_lane_worktree`, `transition`, `_commit_in`).
  6. `test_range_lists_a_hand_merge`: in the WP window, create a side branch that touches only an **out-of-map** path, and merge it into the lane with a hand-edited resolution of an owned file; submit for review. `resolve_wp_review_range(...).merges` contains the merge SHA. Red today: the field does not exist.
  7. `test_merge_with_no_owned_change_is_still_listed`: two merges in the range, the first clean and touching only a non-owned path (default history simplification under the owned pathspec drops it from `commits`), the second with its own content. Both are in `merges` (reviewer-renata's two-merge scenario). This pins `--full-history` and "no pathspec".
  8. `test_range_without_merges_is_unchanged`: the existing fixture's range has `merges == ()`.
  9. `test_merge_listing_failure_is_fail_soft`: monkeypatch the new listing step's git call to raise `GitCommandError`; the range keeps its base/tip, `merges == ()`, and `listing_gap` names `merges`.
- **Validation**: run, confirm red for the expected reasons (`TypeError` on the unknown field, `AttributeError` on `.merges`), record in WP history.

### Subtask T038 – `merges` and `remerge_available` on the range (`wp_range.py`)

- **Purpose**: the range owner lists merges with full history; the renderer stays pure.
- **Steps**:
  1. Append to `WpReviewRange` (after `tip_off_branch`, defaults keep every positional/keyword construction valid): `merges: tuple[str, ...] = ()` and `remerge_available: bool = True`. The default `True` only matters for hand-built ranges with merges; production always sets it when merges exist. Update the class docstring.
  2. Add to `_Listing` a `merges: tuple[str, ...] = ()` field and a step in `_listing`:

     ```python
     def _merges() -> None:
         result = run_git(request.repo_root, "rev-list", "--merges", "--full-history", "--reverse", rev_range)
         listing.merges = tuple(line for line in result.stdout.decode("ascii", "replace").split() if line)
     ```

     Register it with `listing.attempt("merges", _merges)` after the existing four steps (the step name appears in `listing_gap`). No pathspec, no `--` separator needed. `--reverse` keeps range order (oldest first), matching the commit list.
  3. In `resolve_wp_review_range` (`:596-650`): set `merges=listing.merges`; compute `remerge_available = remerge_diff_available(repo_root) if listing.merges else True`. The version probe runs only when a merge exists, so ranges without merges keep today's process count (+1 for `rev-list`).
  4. Update the module docstring's Listing section (`:30-52`): a new bullet for `merges` explaining why it does not use the commit list's pathspecs (simplification drops merges) and that it is listed so the reviewer reads each resolution (FR-007, this Mission).
  5. `__all__`: no change needed (the dataclass is already exported).
- **Edge cases**:
  - octopus merges are listed too (`--merges` = more than one parent); `--remerge-diff` on an octopus shows nothing useful, but listing it is still correct (the reviewer must look). Do not special-case.
  - a range with `base == tip`: `rev-list` returns nothing; fine.
  - `tip_off_branch`: merges are still listed from `base..tip` (the submitted range), not from the live head.
  - Merges that the tool made (lane auto-rebase merges, dependency merges at allocation) appear when inside the window. That is intended: the label says "operator-authored" because a merge inside a review window after FR-005 is typically the incorporate resolution; if you find the label misleading for tool merges in tests, keep the contract wording (it is fixed by `contracts/review-context-merges.md`) and record the observation as a tracer note for WP13.
- **Validation**: `tests/review/test_wp_range_git_calls.py` still passes (7 ≤ 10, and equal for 1 and 200 commits).

### Subtask T039 – Renderer lines in `context_block.py`

- **Purpose**: print the labelled command per merge, commands only, within the existing budget rules.
- **Steps**:
  1. Constants: `_MERGE_LABEL = "RESOLUTION MERGE (operator-authored, review these bytes):"` and a format for the cannot-show line. Keep the exact strings of `contracts/review-context-merges.md`.
  2. Helper `_merge_lines(review_range) -> list[str]`: for each sha, either `f"{_INDENT}{_MERGE_LABEL} git show --remerge-diff {sha}"` or `f"{_INDENT}RESOLUTION MERGE {_label(sha)}: this git cannot show the resolution (needs git >= 2.36); review the merge by hand"`. Indent with `_INDENT` so they read as items under REVIEW COMMANDS.
  3. In `render_review_context` (`:320-360`), append `*_merge_lines(review_range)` right after `*commands` and before the requirement lines. They are outside the byte budget, like the command lines (ruling Q11): do not subtract them from `remaining`.
  4. Do not touch `review_diff_command` / `review_log_command`: the review prompt's worktree topology carries `review_diff_command` as its `diff_command` (`:202-211`, ruling Q13), and changing it would ripple into prompts.
  5. Update the docstring shape block (`:7-31`): add `? RESOLUTION MERGE (operator-authored, review these bytes): git show --remerge-diff <sha>` (repeated per merge) and the cannot-show variant under REVIEW COMMANDS; amend the C-001 sentence (`:42-43`) to say the merge lines are commands, still no patch text, with a reference to this Mission's FR-007.
  6. Keep `render_review_context` at complexity ≤ 15 (it is small today; the new call is one line).
- **Validation**: `tests/review/test_context_block.py` unchanged and green; T037 renderer tests green.

## Test Strategy

Red first. Targeted commands:

```bash
uv run --frozen pytest -q tests/review/test_review_context_merge_lines.py
uv run --frozen pytest -q tests/review/test_context_block.py tests/review/test_wp_range.py tests/review/test_wp_range_default_coord.py tests/review/test_wp_range_git_calls.py
uv run --frozen pytest -q tests/integration/review/test_review_range_acceptance.py tests/agent/test_workflow_mixed_dependency_review_context.py tests/specify_cli/bulk_edit/test_review_gate_single_branch_range.py tests/characterization/test_trio_pure_cores.py
uv run --frozen pytest -q tests/architectural/test_layer_rules.py tests/architectural/test_no_legacy_terminology.py
make test-fast
```

(The files above are every test that imports `resolve_wp_review_range` or `render_review_context` at HEAD: `grep -rln "resolve_wp_review_range\|render_review_context" tests/`.) No `make test-full`, no bare `tests/architectural/`.

Quality gates (zero findings, no suppressions, complexity ≤ 15):

```bash
uv run --frozen ruff check src/specify_cli/review/wp_range.py src/specify_cli/review/context_block.py tests/review/test_review_context_merge_lines.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/review/wp_range.py src/specify_cli/review/context_block.py tests/review/test_review_context_merge_lines.py
uv run --frozen mypy src/specify_cli/review/wp_range.py src/specify_cli/review/context_block.py
```

## Tracer notes

Code WPs cannot own `kitty-specs/` paths. Record notes for `traces/{tooling-friction,approach,design-decisions}.md` with `spec-kitty agent tasks add-history WP10 --note "<trace: ...> ..."`: the measured git-process count before/after; the decision that merge lines sit outside the byte budget; the observation (if any) that tool-made merges inside a window get the "operator-authored" label; the fact that the review-context contract file belongs to another Mission and is amended through ADR `2026-11-08-2` by WP13.

## Risks & Mitigations

- **History simplification hides merges.** Mitigation: separate `rev-list --merges --full-history` with no pathspec; test 7 proves it.
- **Process budget (NFR-002 of #7578).** Mitigation: one extra `rev-list`; version probe only when merges exist; measure with `test_wp_range_git_calls.py`.
- **Renderer purity.** Mitigation: availability is a field computed in `wp_range`; the renderer reads it only.
- **Byte budget regressions** for ranges with many merges: the lines are outside the budget by design (like the command lines); document it in the docstring.
- **Downstream prompt text**: both review entry points (`agent action review` and the `next` review step) render through `render_review_context`, so they get the lines automatically; no change in `workflow.py` is needed (and it is owned by WP08).

## Review Guidance

Anti-fake checks (from `squad2/reviewer-renata.md`, FR-007 finding):

- **Silent omission**: the two-merge test where the first merge touches no owned path must list both; a pathspec-limited listing fails it.
- **Commands, not bytes**: no patch text in the block (C-001 kept); the line runs as printed (`git show --remerge-diff <full sha>`).
- **Unchanged without merges**: byte equality for a range with no merges.
- **Cannot-show path**: the review proceeds; no exception, no gate change.
- **Budget**: `test_wp_range_git_calls.py` green and unmodified.
- Confirm ruff, `ruff format --check --force-exclude` and mypy were run on the changed files.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP10 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP10 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
