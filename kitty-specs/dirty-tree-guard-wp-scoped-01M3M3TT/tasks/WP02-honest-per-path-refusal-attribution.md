---
work_package_id: WP02
title: Honest per-path refusal attribution
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-009
- NFR-002
planning_base_branch: issue-5007-dirty-tree-guard-wp-scoped
merge_target_branch: issue-5007-dirty-tree-guard-wp-scoped
branch_strategy: Planning artifacts for this mission were generated on issue-5007-dirty-tree-guard-wp-scoped. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5007-dirty-tree-guard-wp-scoped unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-dirty-tree-guard-wp-scoped-01M3M3TT
base_commit: cc471ad044b7879282d9f850ef19b973effd56c1
created_at: '2026-09-28T17:24:23.332192+00:00'
subtasks:
- T005
- T006
- T007
- T008
history:
- at: '2026-09-28T15:25:37Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/tasks_parsing_validation.py
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/cli/commands/agent/tasks_parsing_validation.py
- tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP02 – Honest per-path refusal attribution

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for
this work package's `task_type` and `authoritative_surface`.

Mission: `dirty-tree-guard-wp-scoped-01M3M3TT` (GitHub issue `spec-kitty/spec-kitty#5007`). Read
`../spec.md` and `../plan.md` in full before writing any code — plan.md's Design Approach and
Decisions section (b) and Implementation Concern Map (IC-02) is the authoritative description of
this WP's scope; this prompt summarizes it, it does not replace it.

---

## ⛔ Mission-level pre-implement gate — check this before claiming this WP (this WP is the chokepoint)

**Do not claim this WP until BOTH of the following hold:**

1. **WP01 (this mission) has reached `approved`/`done`** — this WP calls `owning_wp_for_path`,
   which WP01 introduces (plan.md IC-02 "Sequencing/depends-on"); the CLI's dependency-readiness
   gate already enforces this via the `dependencies: [WP01]` frontmatter above.
2. **Sibling mission `lane-history-safe-handoff-5151-01M3JR6R` (issue #5151)'s own WP02 has landed
   OR been reviewed/approved on its own branch.** Per spec.md Constraint C-002 and Clarifications
   Q1 — this is spec.md's own bar. (An earlier draft of plan.md's Design Decision (b) stated a
   stricter, unauthorized "merged to `main`" bar; the operator ruled on 2026-09-28 to keep the
   original bar, and plan.md and this gate were corrected accordingly. Operator ruling:
   *"Implement for this mission may start once sibling mission
   lane-history-safe-handoff-5151-01M3JR6R's WP02 is approved (reviewed/approved on its own
   branch); this mission builds off main and rebases onto #5151 at PR time; the residual same-file
   risk is accepted as a small conflict in a different function."*)

   #5151's WP02 owns the exact same two files this WP touches
   (`tasks_parsing_validation.py`, `test_tasks_parsing_validation.py`), editing a **different**
   function (`_check_kitty_specs_contamination` and neighbours — lane-history-provenance refusal,
   NOT `_validate_research_artifacts`, which this WP fixes). Verify with one of:

   1. `spec-kitty agent tasks status --mission lane-history-safe-handoff-5151-01M3JR6R --json` —
      WP02 lane is `approved`, `done`, or otherwise landed on `main`;
   2. `gh pr view <PR#> --json state,mergedAt,reviewDecision` on #5151's WP02 PR —
      `state == "MERGED"` or `reviewDecision == "APPROVED"`;
   3. `git log main --oneline -- src/specify_cli/cli/commands/agent/tasks_parsing_validation.py` —
      a commit plausibly matching WP02's described change is present.

   If none confirms WP02 has landed or been reviewed/approved, **stop and report** — do not proceed.
   Whether #5151's WP02 has merged already or is only approved-but-unmerged when you branch for this
   WP, per the operator's ruling you rebase this mission's branch onto #5151 at PR time — if the
   shared-file changes are already present when you branch/rebase, expect to see
   `_check_kitty_specs_contamination`-area changes already present and untouched by you; do not
   revert or "clean up" anything in that area, it is out of this WP's scope.

---

## Objective

Replace the single hardcoded `"owned by {wp_id}"` refusal header in
`_validate_research_artifacts` with a per-blocking-line attribution that is true in every case: the
moving WP's own residue is named as such (when true), and an unattributable path is explicitly
stated as "not attributable to a specific work package" — never a blanket claim that the WP being
moved owns every blocking path regardless of which case actually applies. Also add missing test
coverage for the pre-existing blocking-lines truncation ("... and N more") branch, which has no
current test in this file (FR-009's second half). Deliver this test-first: the first commit is a
failing test pinning the corrected wording, RED against WP01's already-landed final state.

## Context

**The message-half of the same root cause.** WP01 fixed *classification* — a cross-WP dirty path is
now correctly routed to `benign`. This WP fixes *narration*: even where the current fail-closed
block is correct (a genuinely unattributable path), the *message* is actively misleading today — it
always says `"owned by {wp_id}"` for the WP being moved, in
`src/specify_cli/cli/commands/agent/tasks_parsing_validation.py::_validate_research_artifacts`
(current code, `guidance.append(f"Blocking: {len(blocking)} uncommitted file(s) owned by
{wp_id}:")` — a single header for the whole blocking list, not per-line).

**A blocking line's owner is never a *different*, specific WP.** FR-001/002/003 (WP01) already
route any path attributable to another WP's task directory into `benign` — so by the time a path
reaches this WP's attribution logic, only two outcomes are reachable for a *blocking* line: the
moving WP's own residue (FR-007, `owner == wp_id`), or "not attributable" (FR-004, `owner is None`).
Your attribution logic reflects exactly these two cases — never invent a third "owned by a different
WP" branch for a *blocking* line (spec.md FR-005's own note makes this explicit).

**Mixed-outcome refusals need per-line attribution, not one shared header (User Story 2 AC3,
SC-004).** A single `move-task` call's blocking list can contain both kinds in the same refusal
(e.g. one path under the moving WP's own directory, plus one unattributable path) — each guidance
line must carry its own determined owner, not one header applied to the whole list.

**Seam placement is binding (plan.md Design Decision (f)):** this WP only *consumes* WP01's
`owning_wp_for_path` via a direct import from `specify_cli.review.dirty_classifier` — mirroring the
existing `classify_dirty_paths` import already at line 289 of this file. **Never reimplement or
duplicate the WP-directory regex here, and never inspect `dirty_classifier.py`'s internals
(`wp_task_pattern`/`_is_review_handoff_survivor_path`) directly.**

**Complexity risk (plan.md Risks section).** Adding per-path attribution to
`_validate_research_artifacts`'s guidance-construction loop risks pushing its cyclomatic complexity
past the charter's ceiling of 15 (`ruff` `C901`/Sonar `S3776`). Mitigate by extracting a small,
independently-testable helper — `_attribute_blocking_path(path: str, wp_id: str, mission_slug: str)
-> str` — that wraps the `owning_wp_for_path` call and returns the attribution phrase, keeping
`_validate_research_artifacts` itself a simple per-line loop over that helper.

**NFR-002 (no new leak surface).** The corrected refusal message must stay repo-relative in every
case — `owning_wp_for_path` (and this WP's new helper) operate on the same repo-relative path
strings `classify_dirty_paths` already receives; do not introduce any absolute checkout path into
the message (SK-223 precedent — a documented past leak class in this codebase).

**Do NOT spawn sub-agents.** Implement every subtask below yourself, sequentially, in this one WP.

**Baseline** (re-confirm before your first commit, against WP01's already-landed final state on
this branch):

```bash
.venv/bin/python -m pytest tests/review/test_dirty_classifier.py tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py tests/specify_cli/acceptance/test_accept_dirty_kitty_ops.py -q
```

Expected: should still pass in full (WP01 must not have broken anything) — confirm the exact count
before starting; it will differ from plan.md's pre-WP01 77-passed baseline since WP01 added new
tests. Record whatever you observe as your own WP's starting baseline.

---

## Subtask T005: RED-first test pinning the corrected FR-005 wording (SC-004)

**Purpose**: Per charter ATDD-first (C-011), commit a failing test — before any implementation
commit — that pins the corrected wording: a blocking path that is *not* the moving WP's own residue
must produce `"not attributable to a specific work package"`, not `"owned by {wp_id}"`.

**Steps**:
1. Read the existing `test_validate_research_artifacts_*` tests in
   `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py` (lines ~656–719 as of
   this writing — re-read live, do not trust the line numbers) to match the file's `_make_subproc`
   fixture and `patch("specify_cli.review.dirty_classifier.classify_dirty_paths", ...)` mocking
   convention exactly.
2. Add a new test, e.g. `test_validate_research_artifacts_unattributable_path_not_owned_by_moving_wp`,
   that: mocks `classify_dirty_paths` to return a blocking list containing one path that is NOT
   under the moving WP's own task directory (simulating an unattributable path reaching this point —
   which, post-WP01, can only happen for a genuinely unattributable path, since WP01 already routes
   other-WP paths to `benign`); calls `_validate_research_artifacts` with a concrete `wp_id` (e.g.
   `"WP01"`) and `mission_slug`; asserts the returned guidance text contains `"not attributable to a
   specific work package"` for that line and does **not** contain `"owned by WP01"` anywhere in the
   guidance for that path.
3. Run this test now, before touching `tasks_parsing_validation.py`'s production code, and confirm
   it FAILS (the current code hardcodes `"owned by {wp_id}"` unconditionally) — this is your RED
   proof. Commit this test alone as the WP's first commit, message stating it is RED-first per
   charter C-011.

**Files**: `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py` (one new test,
~25–35 lines).

**Validation**: `.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py -k unattributable_path_not_owned -v` — RED now, GREEN after T006.

---

## Subtask T006: `_attribute_blocking_path` helper + per-line `_validate_research_artifacts` rewrite (FR-005, NFR-002)

**Purpose**: Implement the fix — replace the single hardcoded header with per-line attribution,
without pushing `_validate_research_artifacts` past the complexity ceiling.

**Steps**:
1. In `src/specify_cli/cli/commands/agent/tasks_parsing_validation.py`, add a new helper near
   `_validate_research_artifacts`:

   ```python
   def _attribute_blocking_path(path: str, wp_id: str, mission_slug: str) -> str:
       """Return the honest attribution phrase for one blocking dirty path.

       FR-001/002/003 already route any path owned by a *different* WP into
       ``benign`` (see dirty_classifier.classify_dirty_paths), so a blocking
       path's determined owner is always either the moving WP itself
       (its own residue) or "not attributable" — never a different, specific
       WP. See spec.md FR-005 / User Story 2.
       """
       from specify_cli.review.dirty_classifier import owning_wp_for_path

       owner = owning_wp_for_path(path, mission_slug)
       if owner == wp_id:
           return f"owned by {wp_id}"
       return "not attributable to a specific work package"
   ```

   Import `owning_wp_for_path` directly from `specify_cli.review.dirty_classifier` — mirror the
   existing local import style already used for `classify_dirty_paths` a few lines above in this
   same function (a function-local import, not a module-top-level one, matching the existing
   pattern in this file).

2. Rewrite the guidance-construction block in `_validate_research_artifacts` to build a per-line
   attribution instead of one shared header. Current code (approximate, re-read live before
   editing):

   ```python
   guidance.append(f"Blocking: {len(blocking)} uncommitted file(s) owned by {wp_id}:")
   guidance.append("")
   guidance.append("Modified files in kitty-specs/:")
   for line in blocking_lines[:5]:
       guidance.append(f"  {line}")
   if len(blocking_lines) > 5:
       guidance.append(f"  ... and {len(blocking_lines) - 5} more")
   ```

   Replace with a per-line-attributed version — header states only the count (no ownership claim),
   and each shown line carries its own attribution phrase built from `_attribute_blocking_path`,
   applied to the corresponding blocking path (`blocking_lines` is zipped with `blocking`/`blocking_set`
   already a few lines above — reuse the existing `zip(raw_lines, raw_paths, ...)` pairing rather
   than re-deriving it). Concretely, build a list of `(porcelain_line, file_path)` pairs for the
   first 5 blocking entries, and for each pair append something like:

   ```python
   guidance.append(f"Blocking: {len(blocking)} uncommitted file(s):")
   guidance.append("")
   guidance.append("Modified files in kitty-specs/:")
   for line, file_path in blocking_pairs[:5]:
       attribution = _attribute_blocking_path(file_path, wp_id, mission_slug)
       guidance.append(f"  {line} ({attribution})")
   if len(blocking_pairs) > 5:
       guidance.append(f"  ... and {len(blocking_pairs) - 5} more")
   ```

   The exact phrasing/formatting is your call as long as: (a) the count in the header no longer
   asserts ownership, (b) each shown blocking line carries its own attribution phrase, (c) the
   phrase is exactly `f"owned by {wp_id}"` when true and exactly `"not attributable to a specific
   work package"` when not (spec.md's own literal wording — match it verbatim so downstream tooling
   or documentation quoting these strings does not silently drift). Keep the rest of the function
   (the commit-command guidance below the blocking-lines block) unchanged.

3. Verify `_validate_research_artifacts`'s cyclomatic complexity stays at or under 15 after this
   edit — `ruff check` will flag `C901` if not; if it does, extract further (e.g. a small
   `_build_blocking_guidance_lines(...)` helper) rather than suppressing the check.

**Files**: `src/specify_cli/cli/commands/agent/tasks_parsing_validation.py` (new
`_attribute_blocking_path` helper + edited guidance-construction block in
`_validate_research_artifacts`, ~25–40 lines changed/added).

**Validation**: re-run T005's test — should now be GREEN.

---

## Subtask T007: Unit coverage — mixed-outcome, FR-009 truncation branch, existing-test wording updates (SC-004, FR-009)

**Purpose**: Cover the per-line-attribution mixed-outcome case explicitly, close the FR-009
truncation-branch coverage gap, and update the two existing wording-assertion tests whose expected
strings this WP's change legitimately affects.

**Steps**:
1. **Mixed-outcome test (User Story 2 AC3, SC-004)**: add a test that mocks `classify_dirty_paths`
   to return a blocking list with TWO paths — one under the moving WP's own task directory (or any
   path where `owning_wp_for_path` returns the moving `wp_id`), one that is genuinely
   unattributable. Assert the guidance text contains `"owned by {wp_id}"` attributed specifically to
   the first path's line, and `"not attributable to a specific work package"` attributed
   specifically to the second path's line — not one shared header applied to both.
2. **FR-009 truncation-branch test (currently zero coverage in this file — verified: none of the
   three existing `_validate_research_artifacts` tests constructs more than one blocking path)**:
   construct a blocking list of more than 5 paths (spec's own example uses "N more" — pick ≥6 so the
   truncation branch fires), mix in at least one own-WP-owned and one unattributable path among the
   shown (first 5) and/or truncated entries, and assert both: (a) `"... and N more"` still appears
   with the correct count, and (b) each of the shown (first 5) lines carries the correct
   attribution.
3. **Update the two existing wording-assertion tests** whose expected strings this WP's change
   affects:
   - `test_validate_research_artifacts_blocks_research_commit_format` — currently asserts `"Blocking:
     1 uncommitted file(s) owned by WP01" in text`. Update the assertion to match your new header
     wording (which no longer claims ownership in the header) plus the per-line attribution for that
     one path (which, in this test's single-path-under-the-moving-WP fixture, should still resolve
     to `"owned by WP01"` — the difference is *where* that phrase appears, not whether it's true
     here). Keep the rest of the test's assertions (`'research(WP01)'`, `"move-task WP01 --to
     for_review"`) unchanged — they are unaffected by this WP's change.
   - `test_validate_research_artifacts_benign_only_passes_with_note` — this test's assertions are
     about the `benign`-only path (console note, not blocking guidance) and are unlikely to need a
     wording change; re-read it and confirm — if genuinely unaffected, leave it unmodified and note
     that explicitly in your commit message rather than silently skipping it.
   This is expected, in-scope churn per FR-005 — distinct from WP01's Design Decision (c) pinned
   tests, which live in a different file/code path and are NOT touched by this WP.

**Files**: `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py` (2–3 new test
functions + edits to 1–2 existing tests, ~60–90 lines changed/added).

**Validation**: `.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py -v` — every existing test in the file passes (updated wording where legitimately
affected); every new test passes.

---

## Subtask T008: Confirm GREEN — full targeted surface + owning module fast tier + run-only files (SC-004, NFR-002)

**Purpose**: Prove T005's RED-first test is now GREEN, T007's coverage is GREEN, and nothing in this
mission's blast radius (including files this WP does not edit but that import from it) regressed.

**Steps**:
1. Re-run T005's test and confirm GREEN.
2. Run the full targeted surface:
   ```bash
   .venv/bin/python -m pytest tests/review/test_dirty_classifier.py tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py tests/specify_cli/cli/commands/agent/test_tasks.py tests/specify_cli/acceptance/test_accept_dirty_kitty_ops.py -q
   ```
   Confirm zero failures.
3. Run the two run-only files this mission's blast radius names but this WP does not edit:
   ```bash
   .venv/bin/python -m pytest tests/cli/test_move_task_planned_guard.py -q
   ```
   (`tasks_move_task.py` imports directly from `tasks_parsing_validation.py`, per plan.md review
   finding PLAN-VERIFY-001 — confirm this stays green.)
4. Run the owning-module fast tier (aggregate module `execution_context`'s registered `test_dirs`):
   ```bash
   .venv/bin/python -m pytest tests/mission_runtime tests/runtime tests/specify_cli/cli/commands/agent -q
   ```
5. `ruff check src/specify_cli/cli/commands/agent/tasks_parsing_validation.py
   tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py` and `ruff format --check`
   the same files. Confirm the `C901` complexity check passes for
   `_validate_research_artifacts` (see T006 step 3).
6. Do NOT run `tests/architectural/` in full or `make test-full` locally — CI's architectural-heavy
   battery and the routed `tests-cli` job cover this diff's paths (see tasks.md's Gate set section).
7. Record the exact commands and pass counts for the PR body.

**Files**: none (verification only).

**Validation**: all commands above exit 0 with zero failures/errors.

---

## Definition of Done

- [ ] T005: failing test pinning the corrected FR-005 wording — committed RED-first (own commit,
  before any implementation code), confirmed RED against WP01's already-landed final state.
- [ ] T006: `_attribute_blocking_path` helper added; `_validate_research_artifacts`'s guidance
  construction rewritten to per-line attribution; header no longer claims ownership unconditionally;
  `owning_wp_for_path` imported directly from `specify_cli.review.dirty_classifier`, never
  reimplemented; `_validate_research_artifacts`'s cyclomatic complexity stays ≤ 15.
- [ ] T007: mixed-outcome test (SC-004) added; FR-009 truncation-branch test added (previously zero
  coverage); the two existing wording-assertion tests updated where legitimately affected by the new
  wording, left unmodified with a stated rationale where not.
- [ ] T008: T005 confirmed GREEN; full targeted surface + run-only files + owning module fast tier +
  ruff all pass.
- [ ] Per-subtask completion recorded via `spec-kitty agent tasks mark-status T005 T006 T007 T008
  --status done`.
- [ ] Reviewer has verified, via `git log`, that this WP's first commit was RED against WP01's final
  commit and GREEN at this WP's own final commit (charter C-011).
- [ ] No absolute checkout path appears anywhere in the corrected refusal message (NFR-002).

## Risks

- The two existing message-assertion tests need their expected-string assertions updated to the new
  per-line wording — expected, in-scope churn per FR-005 (T007 step 3); do not silently skip
  updating them and do not conflate this with WP01's Design Decision (c) pinned tests (different
  file, different code path, NOT touched here).
- Complexity ceiling: mitigated by the `_attribute_blocking_path` extraction (T006); if `ruff
  check`'s `C901` still flags `_validate_research_artifacts` after the extraction, extract further
  rather than suppressing the check (charter: no blanket `# noqa`/`# type: ignore` without a
  genuine, individually-justified rationale).
- Residual same-file merge/rebase risk with #5151's WP02: per the operator's ruling, WP02 may only
  be approved-but-not-yet-merged (not necessarily merged to `main`) when this WP starts — this risk
  is accepted and resolved by rebasing this mission's branch onto #5151 at PR time. When you
  branch/rebase for this WP, expect to see `_check_kitty_specs_contamination`-area changes already
  present once #5151's WP02 is picked up; do not touch or "reconcile" that area, it is out of scope
  for this WP.

## Reviewer Guidance

- Confirm T005's commit is provably RED against WP01's final commit (not against some earlier,
  un-WP01'd state) — check `git log` for commit order and re-run the test at the pre-T006 commit if
  needed to confirm.
- Confirm the corrected wording is exactly `f"owned by {wp_id}"` (true case) and exactly `"not
  attributable to a specific work package"` (false case) — spec.md's own literal wording, matched
  verbatim.
- Confirm the mixed-outcome test (T007) asserts per-line attribution, not merely that both phrases
  appear somewhere in the guidance text (a weak assertion that would pass even if attribution were
  scrambled between lines).
- Confirm the FR-009 truncation-branch test is genuinely new coverage (grep the file's git history /
  diff to confirm no prior test already covered `"... and N more"` before this WP).
- Confirm `owning_wp_for_path` is imported directly from `specify_cli.review.dirty_classifier` in
  `_attribute_blocking_path` — no reimplementation of the WP-directory regex anywhere in this file.
- Confirm `_validate_research_artifacts`'s complexity is ≤ 15 (`ruff check` clean, no suppression
  comments added).
- Confirm no absolute checkout path (e.g. a `/home/<user>/...` string) appears in any new guidance
  string or test fixture (NFR-002 / SK-223 precedent — this repo is public).

Implementation command:

```bash
spec-kitty agent action implement WP02 --agent claude
```
