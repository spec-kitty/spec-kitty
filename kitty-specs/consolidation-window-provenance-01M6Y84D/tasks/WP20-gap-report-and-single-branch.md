---
work_package_id: WP20
title: Gap report output and single_branch recorded windows
dependencies:
- WP19
requirement_refs:
- FR-010
- FR-011
- NFR-002
- NFR-010
- SC-002
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T104
- T105
- T106
- T107
- T108
phase: Phase 4 - Behaviour changes, red-first
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/consolidation/reconciliation_bound.py
- tests/consolidation/test_reconciliation_intended_verdicts.py
- tests/consolidation/characterization/verdict_corpus.json
- src/specify_cli/consolidation/window_gap_report.py
- tests/consolidation/test_window_gap_report.py
- tests/consolidation/test_window_gap_report_entry_points.py
- docs/changelog/unreleased/7403-lane-approval-windows.changed.md
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/window_gap_report.py
- src/specify_cli/consolidation/phase_claim.py
- src/specify_cli/consolidation/forecast.py
- src/specify_cli/consolidation/write_branch_bound.py
- src/specify_cli/consolidation/reconciliation_bound.py
- tests/consolidation/test_window_gap_report.py
- tests/consolidation/test_window_gap_report_entry_points.py
- tests/consolidation/test_write_branch_bound.py
- tests/consolidation/test_forecast_seam.py
- tests/specify_cli/cli/commands/test_merge_cli_golden.py
- tests/consolidation/test_reconciliation_intended_verdicts.py
- tests/consolidation/characterization/verdict_corpus.json
- docs/changelog/unreleased/7403-lane-approval-windows.changed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP20 – Gap report output and single_branch recorded windows

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
- **Report progress**: `spec-kitty agent tasks add-history WP20 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

WP19 judges lanes by their windows and puts every fallback work package on the claim (`ApprovedWpCommitSet.window_gaps`, a sorted tuple of `GapEntry`). This work package makes that weaker check **visible** and brings `single_branch` onto the same window model (FR-010, FR-011, SC-002):

1. **Gap report, human**: the fresh run, the resume and the forecast print one block, heading `Window gaps (judged by the approval-stamp bound)`, one line per entry, whenever the claim carries at least one gap — on a pass **and** before a claim-time refusal. No gap, no block.
2. **Gap report, JSON**: the dry-run payload (`consolidate --dry-run --json`) always carries `window_gaps: [ {wp_id, lane_id, reason, cause?, detail?} ]` (`[]` when there is none). A forecast refusal that happens after the claim was built carries it too. The `orchestrator-api` envelope is **unchanged** (spec Assumption; ADR named residual).
3. **`single_branch`**: approval windows read the recorded window-open SHA (WP08's `window_open_of`, FR-021 opener) when the work package has a `WindowOpen`; otherwise they keep today's derivation (`approval_window_open_stamp`, first-claim rule) and the work package is reported as a window gap with the classifier's reason. Today's `single_branch` verdicts stay green (`tests/integration/test_single_branch_approval_windows.py`), except the named flip NFR-002 (c) for a rewound `single_branch` work package.
4. One changelog fragment covers the gap report and the `single_branch` recorded window (this work package). WP19 owns its own fragment for the FR-007 refusal (`docs/changelog/unreleased/7403-lane-approval-window-refusal.changed.md`); do not repeat that entry. **No version bump** (operator ruling, research R-14).

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md` — FR-010, FR-011, SC-002, US3 (1, 3, 4), Assumptions "`single_branch` gap reporting" and "orchestrator-api", Edge Cases "`single_branch` Missions".
- `kitty-specs/consolidation-window-provenance-01M6Y84D/data-model.md` — section 5 (`GapReport`, `GapEntry`, surfaces, heading text, JSON shape), section 3 (reason strings), section 4 (`ApprovalWindow` generalisation).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-13 (the gap-report half and the `single_branch` sentence).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/quickstart.md` section 4 (the expected `--dry-run` commands and the heading).
- WP19's prompt (`tasks/WP19-lane-window-model.md`): `GapEntry` (in `wp_attribution.py`), `bind_lane_predicates`, `classify_windows`, `_BoundVerdict.window_gaps`, `ApprovedWpCommitSet.window_gaps`.

Code (line numbers are pre-Phase-3 / pre-WP17; locate with `grep -n`):

- `src/specify_cli/consolidation/phase_claim.py:520-548`: the claim build, then `_pin_dependency_refs`, `_print_dependency_refs`, `_print_no_implementation_lifts` (~538), then `claim_integrity_refusal` and `_refuse_claim_before_mutation` (~546-548). The fresh run and `--resume` both pass here (`_print_dependency_refs` ~573-588 is the style to copy).
- `src/specify_cli/consolidation/forecast.py:86-94` `_emit_dry_run_error`; `:380-475` `_refuse_unattributable_in_forecast` (builds the claim, returns `None` today; three refusal exits after the claim: claim integrity ~431-438, verifier REFUSE ~456-465, verifier FAIL ~466-475); `:668-692` the success payload and its human `console.print_json`.
- `src/specify_cli/consolidation/write_branch_bound.py:77-88` `approval_windows` (today: `approval_window_open_stamp` per work package), `:142-190` `check_write_branch`.
- `_write_branch_verdict` (`reconciliation.py:2313-2351` pre-split; planned home `reconciliation_bound.py`): binds the Mission branch tip once (`tip = resolve_commit(...)`, ~2337) and calls `check_write_branch`.
- Dry-run payload key pins: `tests/consolidation/test_forecast_seam.py:40-54` and `tests/specify_cli/cli/commands/test_merge_cli_golden.py:112-126` (`EXPECTED_DRY_RUN_PAYLOAD_KEYS`). The second lives in an out-of-matrix directory (nightly only): update it anyway.
- Changelog rules: `docs/changelog/unreleased/README.md` (`<id>.<section>.md`, one section per file).

Cross-cutting: C-009, C-012 (user-facing text says "Mission"; the heading and lines contain no "feature" and no bare "merge"), C-013, C-014, NFR-004 (≤ 15; keep `_refuse_unattributable_in_forecast` under the ceiling by extracting a helper), NFR-005, NFR-009.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP20 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Red-first order

Write `tests/consolidation/test_window_gap_report_entry_points.py` (T108) and the `single_branch` unit tests (T107) **first** and commit them red (`test(WP20): red-first gap report and single_branch window tests`). Every entry-point test fails on the parent commit because no gap block / no `window_gaps` key exists; the rewound `single_branch` pin is still an `xfail`. Record the red SHA and failure summary with `spec-kitty agent tasks add-history WP20 --note "red: <sha> N failed"`. **Also record the entry-point red for (c)-`single_branch`** (post-tasks squad R-07): at the red SHA, run `uv run --frozen pytest -q -rxX tests/consolidation/test_reconciliation_intended_verdicts.py -k "rewound and single_branch"` and paste its summary (`1 xfailed`) into the same note; that strict-`xfail` pin (WP05) is this WP's entry-point red under NFR-010, and the fix commit flips it. Then T104-T107, then the fix commit.

## Subtasks & Detailed Guidance

### Subtask T104 – The gap report renderer

- **File**: `src/specify_cli/consolidation/window_gap_report.py` (new, flat module, `__all__` declared, no git, no I/O).
- **Constants** (module level, used ≥ 2 times each):
  - `GAP_REPORT_HEADING = "Window gaps (judged by the approval-stamp bound)"`
  - `WINDOW_GAPS_KEY = "window_gaps"`
- **Functions**:
  1. `gap_report_lines(entries: Sequence[GapEntry]) -> list[str]`: `[]` when empty; else the heading, then one line per entry in the given order (WP19 already sorts by `(lane_id, wp_id)`):
     - `  - WP02 (lane-a): not recorded`
     - `  - WP03 (lane-b): capture failed (git_error): <detail>`
     - `  - WP04 (lane-a): not on lane: <detail>` — append `: <detail>` only when `detail` is non-empty; append ` (<cause>)` only when `cause` is set (capture failed only).
  2. `gap_report_json(entries: Sequence[GapEntry]) -> list[dict[str, str]]`: one dict per entry with keys `wp_id`, `lane_id`, `reason` always; `cause` only when set; `detail` only when non-empty. Values are plain strings (`reason` is the report text, e.g. `"not recorded"`).
- **Tests** (`tests/consolidation/test_window_gap_report.py`, pure unit, no git):
  - `test_no_entries_renders_nothing`
  - `test_heading_then_one_line_per_entry_in_order`
  - `test_cause_shown_only_for_capture_failed`
  - `test_detail_omitted_when_empty`
  - `test_json_omits_absent_cause_and_detail`
  - `test_json_reason_strings_are_the_report_texts` (parametrize over every `WindowGapReason`)
- **Do not**: import `rich` here (the callers print); add a refusal code; mention "feature".

### Subtask T105 – Print the gap report on the fresh run and on the resume

- **File**: `src/specify_cli/consolidation/phase_claim.py`.
- **Steps**:
  1. Add `_print_window_gaps(claim: ApprovedWpCommitSet | None) -> None`: when `claim` is `None` or `claim.window_gaps` is empty, return; else `console.print(line, markup=False, soft_wrap=True)` for each line of `gap_report_lines(claim.window_gaps)`, the heading styled like the neighbouring notices (`[yellow]` on the heading only, through a separate `console.print` call with markup on and the heading text escaped).
  2. Call it right after `_print_no_implementation_lifts(...)` and **before** `claim_integrity_refusal(...)`, so a claim-time refusal prints the gap report first (the operator sees which work packages got the weaker check even when the run refuses).
  3. The resume reaches the same function, so one call site covers both modes. Do not add a second call in the executor.
- **Notes**: a claim build that raised `GitProbeError` never reaches the call (`_exit_on_claim_probe_error`); that is correct (no claim, no report). Keep the function ≤ 5 lines of logic; no new imports at module level beyond the renderer.

### Subtask T106 – `window_gaps` in the dry-run payload and the human forecast

- **File**: `src/specify_cli/consolidation/forecast.py`.
- **Steps**:
  1. Change `_refuse_unattributable_in_forecast(...)` to return the claim it built (`ApprovedWpCommitSet | None`; `None` on the early `return` when the target does not resolve). Extract the post-claim verdict handling into `_forecast_verdict_or_exit(claim, result, *, json_output)` if the function would exceed complexity 15.
  2. `_emit_dry_run_error(..., extra: Mapping[str, object] | None = None)`: when `json_output`, merge `extra` into the payload (keys never override `error` / `error_code`); when human, print the gap block lines (passed via `extra`'s gaps) **before** the `Error:` line. Every existing caller passes nothing and is byte-identical.
  3. At the three refusal exits that follow the claim build, pass `extra={WINDOW_GAPS_KEY: gap_report_json(claim.window_gaps)}` when the claim has gaps.
  4. In `run_dry_run_forecast`, keep the returned claim and add `payload[WINDOW_GAPS_KEY] = gap_report_json(claim.window_gaps) if claim else []` (always present). In human mode, print `gap_report_lines(...)` before the existing `console.print_json(...)`.
  5. Update `EXPECTED_DRY_RUN_PAYLOAD_KEYS` in `tests/consolidation/test_forecast_seam.py` and `tests/specify_cli/cli/commands/test_merge_cli_golden.py`: add `"window_gaps",  # added for the window gap report (#7403, 2026-11)`. Add one assertion in each: `assert payload["window_gaps"] == []` on their clean fixture.
- **Do not**: change any other payload key or `error_code`; touch `orchestrator-api`; add a CLI flag.

### Subtask T107 – `single_branch` approval windows read the recorded window-open SHA

- **Files**: `src/specify_cli/consolidation/write_branch_bound.py`, the post-split home of `_write_branch_verdict` (planned `reconciliation_bound.py`).
- **Steps**:
  1. `approval_windows(events, stamps, *, classes: Mapping[str, WindowOpen | WindowGap] | None = None)`: for each work package, `open_stamp = classes[wp].sha` when `classes` is given and holds a `WindowOpen`; otherwise `approval_window_open_stamp(events, wp_id)` exactly as today (FR-011: keep today's derivation). With `classes=None` the function is byte-identical to today.
  2. Add `check_write_branch_windows(repo_root, *, events, lane_id, branch, approved_wp_ids, claim_base, anchors, is_bookkeeping, tip) -> tuple[tuple[BoundRefusal, ...], tuple[GapEntry, ...]]`: bind `on_lane, is_ancestor = bind_lane_predicates(repo_root, tip)` to the one Mission-branch tip, `classes = classify_windows(events, approved, ...)`, `gaps = (GapEntry.from_gap(wp, lane_id, gap) for each WindowGap)`, then run today's tier 1 and tier 2 with `approval_windows(events, stamps, classes=classes)`. Keep `check_write_branch(...)` as a thin wrapper returning only the refusals, so its callers and tests are unchanged.
  3. `_write_branch_verdict` calls `check_write_branch_windows` and sets `_BoundVerdict(window_gaps=...)` on both the refusal and the pass. The refusal text stays `render_write_branch_refusals` (byte-identical).
  4. A `single_branch` gap is reported although its verdict comes from the derived window (spec Assumption); the heading stays the same block (data-model section 5).
- **Unit tests** (`tests/consolidation/test_write_branch_bound.py`):
  - `test_approval_windows_without_classes_is_todays_derivation`
  - `test_approval_windows_reads_recorded_open_after_rewind` (classes give `WindowOpen(S1)` while the first-claim stamp is `S0`: the window opens at `S1`)
  - `test_check_write_branch_windows_reports_gap_and_keeps_derivation` (no `wp_window` on the opener: verdict equals `check_write_branch`, one gap `"not recorded"`)
  - `test_check_write_branch_wrapper_unchanged`
- **Flip** in `tests/consolidation/test_reconciliation_intended_verdicts.py`: remove the `xfail` from the `single_branch` case of `test_rewound_wp_window_opens_after_rewind` (WP19 split the parametrization). Leave every other pin untouched.

### Subtask T108 – Entry-point tests and the changelog fragment

- **File**: `tests/consolidation/test_window_gap_report_entry_points.py` (new; `pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`). Drive the CLI in process with WP02's `run_in_process`; build with `build_shape` / WP19's two-WP-lane builder and `set_window_state`; use `require(...)` (raises `RuntimeError`) for preconditions.
- **Tests** (exact names):
  1. `test_fresh_run_prints_gap_report_for_all_gap_lane` (US3-1): every WP `not_recorded`; exit 0; output contains the heading, `WP01 (lane-a): not recorded` and `WP02 (lane-a): not recorded`.
  2. `test_fresh_run_without_gaps_prints_no_block`: all recorded; exit 0; heading absent.
  3. `test_fresh_run_refusal_prints_gap_report_first`: the gap-then-recorded stray fixture; exit 1; the heading and `WP01 (lane-a): not recorded` appear **before** `LANE_MOVED_AFTER_APPROVAL` in the output; refs unchanged (`rollback_harness.ref_shas`).
  4. `test_resume_prints_gap_report_and_keeps_the_verdict` (US3-3, NFR-010): an all-gap Mission (every WP `not_recorded`, the pre-upgrade shape); `interrupt_after_claim(mission)` (SIGKILL after the claim anchors were saved, WP02 harness); `require` that `state.json` holds `pre_interrupt_lane_tips`; `consolidate --resume` in process; exit code equals the fresh run's on an identical copy (`shutil.copytree` before the kill); the heading and both WP lines are printed. Zero hand-written `state.json`.
  5. `test_dry_run_json_carries_window_gaps` (FR-010): `--dry-run --json`; `payload["window_gaps"] == [{"wp_id": "WP01", "lane_id": "lane-a", "reason": "not recorded"}, {"wp_id": "WP02", "lane_id": "lane-a", "reason": "not recorded"}]`.
  6. `test_dry_run_json_window_gaps_empty_when_all_recorded`: `payload["window_gaps"] == []`.
  7. `test_dry_run_refusal_payload_carries_window_gaps`: gap-then-recorded fixture; exit 1; `error_code == "CLAIM_REFUSED_FORECAST"` and `payload["window_gaps"]` names WP01.
  8. `test_dry_run_human_prints_gap_block`: `--dry-run` without `--json`; heading present before the JSON block.
  9. `test_capture_failed_gap_shows_cause`: `set_window_state(..., "capture_failed")` on WP02 only; human line `WP02 (lane-a): capture failed (git_error): test`; JSON entry carries `"cause": "git_error"`, `"detail": "test"`.
  10. `test_single_branch_unrecorded_window_is_reported` (FR-011): `build_shape(tmp_path, "single_branch")` with `wp_window` stripped from every opener; exit code equals today's (pass); the heading lists each approved WP with `not recorded`.
- **Changelog** `docs/changelog/unreleased/7403-lane-approval-windows.changed.md`, one entry, section `changed` (style of the README example; the FR-007 refusal entry is WP19's own fragment):
  - `- **\`spec-kitty consolidate\` lists the work packages it judged without a recorded window** (#7403). A work package whose window was not recorded (for example in a Mission started before this release) is still judged by its approval stamp, and the fresh run, \`--resume\` and \`--dry-run\` now list it under "Window gaps"; \`--dry-run --json\` carries them as \`window_gaps\`.`
- Run `uv run --frozen python -m scripts.docs.check_changelog_style` and `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.

### Golden corpus

- Expected change: **only** the NFR-002 (c) `single_branch` rewound cells WP02 named (`fresh|single_branch|stamp=present|window=recorded|rewound` and its forecast twin; WP02 T012 step 2 requires both, post-tasks squad R-07): pass → refuse `LANE_MOVED_AFTER_APPROVAL` naming the abandoned-cycle commit. If either cell is missing, stop and ask the orchestrator (it is a WP02 defect, not a reason to skip the witness).
- Regenerate with WP02's `regenerate_cells([...])` and run the machine check (post-tasks squad R-03) after the fix commit and on the final commit:
  ```bash
  BASE=$(git rev-parse <red-commit>^)   # WP19's tip
  ALLOWED='<the two single_branch rewound keys, comma-separated>'
  uv run --frozen python -c "import sys; from tests.consolidation.characterization_support import changed_cells; c = changed_cells('$BASE'); a = sorted(sys.argv[1].split(',')); print(c); assert c == a, ('changed cells differ from the allowed list', c, a)" "$ALLOWED"
  ```
  **Any other changed cell is a STOP**: revert and report. The gap report is output, not verdict: it must not change any cell's status, code or exit code; if WP02 serialized raw output text for a cell (the FR-023 cell pins refusal text), the gap block must not appear in that text (all-gap lanes print the block **before** the refusal; confirm the serializer reads the refusal text, not the whole output, or stop and report).

## Test Strategy

Red-first entry-point tests (T108 1-10, T107 unit tests) committed before the implementation; pure renderer tests beside them. `tests/integration/test_single_branch_approval_windows.py` is the over-refusal guard for T107 and must stay green unchanged.

## Definition of Done

Run and record exact commands with pass/fail counts in the WP history:

```bash
uv run --frozen pytest -q tests/consolidation/test_window_gap_report.py tests/consolidation/test_window_gap_report_entry_points.py tests/consolidation/test_write_branch_bound.py tests/consolidation/test_forecast_seam.py
uv run --frozen pytest -q tests/integration/test_single_branch_approval_windows.py tests/specify_cli/cli/commands/test_merge_cli_golden.py
uv run --frozen pytest -q -rxX tests/consolidation/test_reconciliation_intended_verdicts.py
uv run --frozen pytest -q tests/consolidation/test_lane_approval_windows.py tests/consolidation/test_reconciliation_characterization.py tests/consolidation/test_reconciliation_seeded_mutations.py tests/consolidation/test_claim_inputs_parity.py tests/consolidation/test_reconciliation_surface_pin.py
uv run --frozen pytest -q tests/orchestrator_api/test_consolidate_mission_post_approval.py tests/orchestrator_api/test_single_branch_bound_preflight.py
uv run --frozen pytest -q tests/consolidation/ tests/terminus/
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py tests/architectural/test_no_dead_modules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_legacy_terminology.py
uv run --frozen ruff check src/specify_cli/consolidation tests/consolidation/test_window_gap_report.py tests/consolidation/test_window_gap_report_entry_points.py
uv run --frozen ruff check --select C901 src/specify_cli/consolidation
uv run --frozen ruff format --check --force-exclude src/specify_cli/consolidation/window_gap_report.py src/specify_cli/consolidation/phase_claim.py src/specify_cli/consolidation/forecast.py src/specify_cli/consolidation/write_branch_bound.py src/specify_cli/consolidation/reconciliation_bound.py tests/consolidation/test_window_gap_report.py tests/consolidation/test_window_gap_report_entry_points.py tests/consolidation/test_write_branch_bound.py tests/consolidation/test_forecast_seam.py tests/specify_cli/cli/commands/test_merge_cli_golden.py
uv run --frozen mypy src/specify_cli/consolidation/window_gap_report.py src/specify_cli/consolidation/phase_claim.py src/specify_cli/consolidation/forecast.py src/specify_cli/consolidation/write_branch_bound.py
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
make test-fast
```

- [ ] Red-first evidence: red SHA (entry-point tests failing for "no gap block / no `window_gaps`") and fix SHA in the WP history. **Because lane SHAs can become unreachable after a squash consolidation with cleanup** (post-tasks squad R-14), also paste, for each red test, its full test id and the assertion message pytest printed (`uv run --frozen pytest -q -rf <test>` at the red SHA), so the PR and the post-merge mission review can check the red without checking out the SHA.
- [ ] `-rxX`: the `single_branch` rewound case passes; WW-6 residual still `XFAIL`; no other pin changed.
- [ ] `changed_cells(<red commit>^)` equals the two `single_branch` rewound keys (machine check above).
- [ ] The (c)-`single_branch` pin's `xfailed` summary at the red SHA is in the history note.
- [ ] `orchestrator-api` envelope and contract version untouched (`git diff --stat src/specify_cli/orchestrator_api` empty).
- [ ] `pyproject.toml` version untouched; no new `# noqa` / `# type: ignore` / allowlist entry.
- [ ] **Tracer files** (canonical writer only, no hand edits of `traces/*.md`, no `add-history` fallback; post-tasks squad R-02): `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category design-decisions --actor "implement WP20" --entry "<summary>. <detail>"` for gap report printed before a claim refusal; JSON on forecast refusals; `single_branch` gap reported although its verdict comes from the derived window; `--category tooling-friction` for any friction. The command works from any checkout (lane worktree included) and commits to the coordination surface itself.
- [ ] Never run `make test-full`.

## Risks & Mitigations

- **Payload consumers pinning the key set**: both pins updated in this work package; the key is additive.
- **Gap text leaking into a pinned refusal text**: the golden check above.
- **`single_branch` regression**: `approval_windows(classes=None)` byte-identical and the integration file green; the recorded window only differs from the first-claim stamp after a rewind (FR-021) or a topology tie-break.
- **Complexity of `_refuse_unattributable_in_forecast`**: extract the verdict handling.

## Review Guidance

- Reviewer profile: `reviewer-renata`.
- **Model tier: mid to top** (output surfaces are mechanical; the `single_branch` window source is soundness-relevant).
- Check every surface of FR-010: fresh run, resume (SIGKILL fixture, no hand-written state), forecast human and JSON, forecast refusal.
- Check `check_write_branch` callers still get byte-identical refusals; check the `single_branch` gap is reported but never refuses (C-010).
- Check user-facing text against C-012.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP20 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP20 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
