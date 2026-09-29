---
work_package_id: WP01
title: Review - dead-code gate not applicable + pytest pre-check warning
dependencies: []
requirement_refs:
- C-002
- C-003
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-004
planning_base_branch: issue-5283-tech-agnostic-language-fallback
merge_target_branch: issue-5283-tech-agnostic-language-fallback
branch_strategy: Planning artifacts for this mission were generated on issue-5283-tech-agnostic-language-fallback. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5283-tech-agnostic-language-fallback unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-tech-agnostic-language-fallback-01M3NP53
base_commit: a2060146a75be1a4f614a859d5a86433924f4a3d
created_at: '2026-09-29T05:11:38.640682+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
phase: Phase 1 - Review gate (lane A)
history:
- at: '2026-09-29T06:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/review/
create_intent:
- tests/specify_cli/cli/commands/review/test_dead_code_not_applicable.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/cli/commands/review/_dead_code.py
- src/specify_cli/cli/commands/review/__init__.py
- src/specify_cli/cli/commands/review/_report.py
- src/specify_cli/cli/commands/review/_diagnostics.py
- src/specify_cli/cli/commands/review/ERROR_CODES.md
- tests/specify_cli/cli/commands/review/test_dead_code_baseline.py
- tests/specify_cli/cli/commands/review/test_dead_code_baseline_git.py
- tests/specify_cli/cli/commands/review/test_diagnostic_codes_documented.py
- tests/specify_cli/cli/commands/review/test_dead_code_not_applicable.py
- tests/specify_cli/cli/commands/review/baselines/issue_2987_red_first.md
- tests/specify_cli/cli/commands/test_review.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP01 – Review - dead-code gate not applicable + pytest pre-check warning

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (canonical: `spk-doctrine-profile-load`) to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Reviewers load `reviewer-renata` (reviewer ≠ implementer).

---

## ⛔ HARD RULE — NO_FULL_HEAVY_SUITES_IN_MISSION (verbatim, binding for implementer AND reviewer)

During implement and every WP review, you must NEVER run full or heavy suites:
- no whole `tests/architectural/`, no e2e or full-integration suites, no performance/stress/timing suites;
- no `make test-full`, no whole-repo pytest.

Per WP, run only:
- the test files covering the files the WP touches;
- the owning module's fast tier;
- the specific NAMED architectural gate files the change implicates.

Leave broad sweeps to the END of the mission (closeout) or to CI.

---

## ⚠️ Post-tasks squad corrections (BINDING — supersede any conflicting guidance further below)

- T001 case list: Zig/Go-only (use TWO `.zig` files + one `.go` so the de-duplicated `.go, .zig` string is exercised at CLI level) is RED; mixed, Python-only and undeterminable cases are GREEN controls. Lightweight AND post-merge modes are both mandatory (seed `baseline_merge_commit` so lightweight runs).
- Assert **exactly one** `dead_code_not_applicable` finding (count == 1) in both modes; assert `.py` absence on the finding's `unsupported_extensions` field (not on all of stdout — stdout legitimately mentions `tests/test_x.py`).
- "Never 0 unreferenced": assert on **stdout** (that text is console-only, `_dead_code.py:378`) for the Zig case, paired with a clean Python-only GREEN control whose stdout DOES contain `0 unreferenced public symbols`.
- Formatter: assert the written report **body** contains the rendered `MISSION_REVIEW_DEAD_CODE_NOT_APPLICABLE` line (the record alone is insufficient — without a formatter the line silently disappears).
- Missing-pytest case: use a clean **Python-only** mission (so rc 0 depends only on the pre-check fix), and assert the gate records exist in the written report.
- Add a GREEN control: an empty change set (git diff reports no changed files) behaves exactly as today.
- T008 neutrality scope: ban `.py`, `src/`, `pytest`, `python` in `_NOT_APPLICABLE_REMEDIATION` and the Zig-only console block, allowing exactly the phrases "only analyzes Python sources" and "test-only Python paths".
- Half-by-half is ENFORCED by the reviewer (not just logged): revert (a) the skip mapping in `review/__init__.py` → acceptance red; (b) `_NOT_APPLICABLE_REMEDIATION` → neutrality red; (c) the formatter in `_report.py` → report-body assertion red.
- `tests/specify_cli/compat/test_review_migration.py` does not exist — ignore that reference. Name the new module distinctly from the existing Gate-4 `test_zero_reference_not_applicable.py` (the planned `test_dead_code_not_applicable.py` is fine; do not touch the Gate-4 file).
- **Red→green proof (reviewer, mandatory):** re-run the new tests after `git checkout <base> -- src/specify_cli/cli/commands/review/_dead_code.py src/specify_cli/cli/commands/review/__init__.py src/specify_cli/cli/commands/review/_report.py src/specify_cli/cli/commands/review/_diagnostics.py` (then `git checkout HEAD -- src/specify_cli/cli/commands/review/_dead_code.py src/specify_cli/cli/commands/review/__init__.py src/specify_cli/cli/commands/review/_report.py src/specify_cli/cli/commands/review/_diagnostics.py`): they must be RED for the intended reason (an assertion, never an ImportError/collection error) and GREEN again at the tip. Base = the planning base branch.
- **Red-first labelling:** in the red-first commit, every test is labelled in its docstring either `RED (pins the fix)` or `GREEN control (pins unchanged behaviour)`. Controls may pass on the base; only RED tests must fail. New names that do not exist on the base are imported function-locally (or referenced as literals) so the base can still collect the module.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks and use language identifiers in code blocks.

---

## Objectives & Success Criteria

Closes #5283 and the operator-approved pytest pre-check fold. When `spec-kitty review` (lightweight or post-merge) runs on a mission whose changed files contain nothing the Python-only dead-code scan supports:

- the dead-code gate is recorded with result **`skip`** in the review report;
- exactly one finding of type **`dead_code_not_applicable`** with diagnostic code **`MISSION_REVIEW_DEAD_CODE_NOT_APPLICABLE`** is recorded and rendered (console + report), naming the unsupported extensions (sorted, de-duplicated; `(no extension)` for bare files) and, separately, how many test-only Python paths were excluded — `.py` is **never** listed as unsupported;
- remediation text is tech-agnostic: extend the local charter with tech-specific review guidance and your own analyzer/test command — no Python file/layout/tool advice;
- verdict is exactly `pass_with_notes`, exit code 0, and the report never says "0 unreferenced".

Unchanged (must stay green, positive controls): a Python-only change set shows no note and still reports unreferenced symbols; a mixed set still scans the Python subset; git unavailable / git diff failure / unreadable source / empty corpus stay `DEAD_CODE_UNDETERMINABLE` + `fail`; `LEGACY_MISSION_DEAD_CODE_SKIP` keeps recording `pass`.

Also: a missing pytest in the CLI's interpreter no longer exits before the gates run — it prints a warning carrying `MISSION_REVIEW_TEST_EXTRA_MISSING`, keeps the stdout JSON diagnostic line (add `"severity": "warning"`), then the review continues and writes its report.

## Context & Constraints

- Charter (binding): `.kittify/charter/charter.md` — ATDD/red-first (C-011): the failing test is committed as its own commit BEFORE the fix; reviewer verifies red on the planning base and green at the WP tip.
- Mission docs: `kitty-specs/tech-agnostic-language-fallback-01M3NP53/{spec.md,plan.md,research.md,data-model.md,contracts/cli-outputs.md,quickstart.md}`; tracer files under `traces/` — append a dated 1–3 sentence entry for any tooling friction, approach change, or design decision you make.
- Operator policy (#2330 decision): Spec Kitty doctrine is tech-agnostic; default implementation profile `implementer-ivan`; unknown languages → advise extending the local charter; NEVER fix by adding languages one by one; NEVER suggest Python files/layouts/tools to a non-Python project.
- Sibling-owned, do NOT edit: `src/specify_cli/consolidation/**`, `tests/integration/**`, golden/snapshot fixtures (`tests/specify_cli/skills/__snapshots__/**`, `tests/cli/__snapshots__/**`, `tests/consolidation/merge_driver_goldens/**`, `tests/contract/snapshots/**`), doctor/decision surfaces, `review/arbiter.py`, move-task override, built-in software-dev guidelines (#5202).
- Code quality: `ruff check`, `ruff format --check`, `mypy` (strict) clean on touched files; cyclomatic complexity ≤15; no new `# noqa`/`# type: ignore`; every new branch/helper gets a focused test in the same commit; modules under `src/charter/**` keep `__all__` and every exported name needs a caller in `src/` (dead-symbol gate).
- Terminology canon: Mission, never "feature", in any new prose/identifier.
- In a lane worktree always run tools via `uv run --frozen ...` or the worktree's own interpreter so the LANE `src/` is imported (bare `python`/`pytest` may import the primary checkout).

### Grounded seams (verified on main f13a799c)

- `_dead_code.py:83-111` `_discover_changed_symbols`: supported = `.py` and (`src/` prefix or no `test` in path) (`:97-98`); today returns `_Discovery(changed_paths, (), "changed source set contains no supported Python files")` → rendered by `_append_undeterminable` (`:159-176`).
- `_dead_code.py:301` `scan_dead_code` returns None; `review/__init__.py:212-236` `_run_dead_code_gate` records gate fail when any finding was appended (`:234`); `_record_gate` typed `Literal["pass","fail"]` (`:181-186`); `GateRecord.result` already allows `"skip"` (`_report.py:41`).
- `_report.py:19-30` `_HARD_FAILURE_FINDING_TYPES` includes `dead_code_undeterminable` → verdict `fail`; any other finding → `pass_with_notes` (`:127`); `_format_finding_line` returns None for unknown types (`:97`, `:162-164`) → the line silently disappears from the report.
- pytest pre-check: `review/__init__.py:393-397` (`assert_pytest_available` → `_fail_missing_test_extra` → `typer.Exit(1)`); no review gate imports or runs pytest (lane check, dead-code string scan, BLE001 audit, issue matrix); env-skew compares typer/click only and returns nothing without `uv.lock`.
- Diagnostics enum `_diagnostics.py:34`; documented-codes gate `test_diagnostic_codes_documented.py:75` hardcodes 15.
- Deliberately-pinned: `test_dead_code_baseline_git.py:95-110` `test_unsupported_non_python_change_is_undeterminable` (docs `.md` change; #2987 FR-015/016; listed in `baselines/issue_2987_red_first.md:40`); `test_review.py:330` and `:364` (TEST_EXTRA_MISSING exit + JSON).
- CLI fixture template: `test_dead_code_baseline_git.py:257-340` `test_real_post_merge_cli_uses_git_as_only_path_executable` (git repo + `.kittify/config.yaml` + `meta.json` with `baseline_merge_commit` + one WP `done` in `status.events.jsonl`).

## Branch Strategy

- **Strategy**: lanes (no coordination branch)
- **Planning base branch**: issue-5283-tech-agnostic-language-fallback
- **Merge target branch**: issue-5283-tech-agnostic-language-fallback

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; prepare yours with `spec-kitty agent action implement WP01 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first CLI acceptance tests (commit alone, RED)

- **Purpose**: Pin the user-observable behaviour through the pre-existing entry point before any fix (NFR-004).
- **Steps**:
  1. Create `tests/specify_cli/cli/commands/review/test_dead_code_not_applicable.py`, reusing the real-git fixture pattern of `test_real_post_merge_cli_uses_git_as_only_path_executable` (copy the minimal helpers or import shared fixtures from `_dead_code_fixtures.py` if present; do not edit goldens).
  2. Cases (each through the real `spec-kitty review` typer app, both `--mode lightweight` where a baseline exists and `--mode post-merge`):
     - **Zig/Go only**: committed `src/main.zig` + `cmd/app/main.go` after the baseline → assert rc 0; stdout contains `not applicable` and `MISSION_REVIEW_DEAD_CODE_NOT_APPLICABLE`; names `.go, .zig`; does NOT contain `DEAD_CODE_UNDETERMINABLE`; written report has dead-code gate `result: skip`, a finding `dead_code_not_applicable`, `verdict: pass_with_notes`, and not `0 unreferenced`.
     - **Mixed**: Zig + `scripts/gen.py` defining `def DeliberatelyUnreferenced(): ...` → the symbol is still reported; the non-Python remainder is noted as not applicable; verdict `pass_with_notes`.
     - **Python-only positive control**: only a `.py` with an unreferenced public def → no not-applicable text.
     - **Tests-only / docs-only**: `tests/test_x.py` + `README.md` → not applicable; message mentions excluded test-only Python paths separately; `.py` NOT listed among unsupported extensions; `.md` listed.
     - **Missing pytest**: patch `assert_pytest_available` to raise `TestExtraMissing` → rc 0 for an otherwise clean Zig mission, stderr/stdout carries `MISSION_REVIEW_TEST_EXTRA_MISSING`, the report IS written, stdout JSON line includes `"severity": "warning"`. Control: no patch → no warning.
  3. Run it: every case must FAIL on the current code for the right reason (undeterminable/rc 1 or exit before gates). Commit: `test(review): red-first not-applicable dead-code acceptance (#5283)`.
- **Files**: new test module (~220 lines).
- **Notes**: Realistic data — real ULID-shaped `mission_id`, real git commits.

### Subtask T002 – Discovery outcome carries not-applicable detail

- **Purpose**: Let the caller distinguish scanned / undeterminable / not-applicable without string-matching reasons.
- **Steps**:
  1. Extend `_Discovery` (or add a small frozen dataclass) with an explicit outcome discriminator (e.g. `Literal["scan","undeterminable","not_applicable"]`) plus `unsupported_extensions: tuple[str, ...]` and `excluded_test_paths: int`.
  2. In `_discover_changed_symbols`, when `changed_paths` is non-empty and `supported_paths` is empty, return the not-applicable outcome; compute extensions via `PurePosixPath(p).suffix.lower()` for non-`.py` paths (`(no extension)` when empty); count `.py` paths excluded by the test filter.
  3. For a mixed set, the scan outcome also carries the non-Python remainder's extensions so the console can note them.
  4. Keep git-unavailable / git-diff-failure / empty-diff behaviour byte-identical.
  5. Extract a helper (e.g. `_summarize_unsupported(changed_paths, supported_paths)`) to keep complexity ≤15; unit-test it directly in `test_dead_code_baseline.py` (sorting, de-dup, no-extension, `.py` never listed).
- **Files**: `_dead_code.py`, `test_dead_code_baseline.py`.

### Subtask T003 – Finding, code, remediation, formatter

- **Steps**:
  1. `_diagnostics.py`: add `DEAD_CODE_NOT_APPLICABLE = "MISSION_REVIEW_DEAD_CODE_NOT_APPLICABLE"` next to `DEAD_CODE_UNDETERMINABLE`.
  2. `_dead_code.py`: module constant `_NOT_APPLICABLE_REMEDIATION` — tech-agnostic, e.g. "The dead-code scan only analyzes Python sources. For other languages, add tech-specific review guidance and your own analyzer or test command to your local charter (see 'Extend your charter for an unsupported language')." Never mention `.py`, `src/`, `pytest`, or creating files.
  3. `_append_not_applicable(...)`: prints `⚠  Dead-code scan: not applicable (<code>)`, reason, remediation; appends `{"type": "dead_code_not_applicable", "diagnostic_code": ..., "unsupported_extensions": "...", "excluded_test_paths": "N", "reason": ..., "remediation": ...}` (all str values — findings are `dict[str, str]`).
  4. `_report.py`: add a formatter so the finding renders one readable line in the report; do NOT add the type to `_HARD_FAILURE_FINDING_TYPES`.
  5. Mixed set: print a one-line ⚠ note for the non-Python remainder (no finding needed beyond what the scan produces — decide and document; the acceptance test asserts the note text).

### Subtask T004 – Tri-state gate recording

- **Steps**: widen `_record_gate(...)` to `Literal["pass","fail","skip"]`; make `scan_dead_code` return the outcome; in `_run_dead_code_gate` record `skip` for not-applicable, keep `fail` when any other dead-code finding was appended, `pass` otherwise (legacy skip path stays `pass`). Keep `scan_dead_code` complexity ≤15. Unit test the mapping.

### Subtask T005 – pytest pre-check → warning

- **Steps**: replace `_fail_missing_test_extra` with a warning helper (keep the name if tests import it, or rename and update tests): print `[yellow]Warning:[/yellow] MISSION_REVIEW_TEST_EXTRA_MISSING: ...` worded as a Spec Kitty installation note (the review runs no Python tests; the extra only matters for local CI-parity runs of Spec Kitty itself) + the existing remediation string; write the JSON line with `"severity": "warning"`; continue. Re-pin `test_review.py:330/:364`: stub mission resolution so the bare repo does not exit later for an unrelated reason; assert warning + code + remediation + that review proceeded. Also run `tests/specify_cli/cli/commands/test_test_env_check.py` and `tests/specify_cli/compat/test_review_migration.py` (if present) — adjust only if they assert the exit.

### Subtask T006 – Re-pin deliberately-pinned tests

- **Steps**: rename/re-pin `test_unsupported_non_python_change_is_undeterminable` → `test_unsupported_non_python_change_is_not_applicable` asserting not-applicable naming `.md`, gate `skip`, no false "0 unreferenced" (keeps #2987 FR-015 "never a false clean zero"); add a dated note to `baselines/issue_2987_red_first.md` recording the rename and why (this mission, #5283); bump the enum count 15→16 in `test_diagnostic_codes_documented.py:75`.

### Subtask T007 – ERROR_CODES.md

- **Steps**: add a `## DEAD_CODE_NOT_APPLICABLE` section (Code, When it fires, JSON stability, Severity: non-failing/`pass_with_notes`, Remediation — tech-agnostic, Body example) matching the house format of neighbouring sections; remove "a change set with no supported Python files" from the UNDETERMINABLE "when it fires" list (keep git/unreadable/empty-corpus); mark `TEST_EXTRA_MISSING` as a warning (review continues) and drop the claim that it "prevents the dead-code scan and BLE001 audit from running". The documented-codes gate must pass.

### Subtask T008 – Neutrality + half-by-half proof

- **Steps**: a parametrized test asserting the not-applicable remediation and console text contain none of: `.py`, `src/`, `pytest`, `python` (case-insensitive) except the fixed phrase "only analyzes Python sources" (assert that exact allowance explicitly), and contain "local charter". Record in the Activity Log the half-by-half proof: (a) revert the skip mapping only → acceptance test red; (b) revert the remediation text only → neutrality test red.

## Test Strategy

Run (targeted only):
- `uv run --frozen pytest tests/specify_cli/cli/commands/review/ tests/specify_cli/cli/commands/test_review.py tests/specify_cli/cli/commands/test_review_git_baseline.py tests/specify_cli/cli/commands/test_test_env_check.py -q`
- `uv run --frozen ruff check <touched files>`; `uv run --frozen ruff format --check <touched files>`; `uv run --frozen mypy src/specify_cli/cli/commands/review/`
- Baseline before you start (from the post-plan squad): the review dir + test_review.py + two charter files = 129 passed. Record before/after counts in the Activity Log.

## Risks & Mitigations

- Recording `skip` from the finding list instead of the scan outcome would mis-record a Python mission with dead code → decide from the returned outcome.
- `LEGACY_MISSION_DEAD_CODE_SKIP` must keep `pass`.
- A too-broad not-applicable branch could hide genuine undeterminable cases — keep the git/read/empty-corpus paths untouched and covered.

## Definition of Done

- [ ] T001 red commit precedes all fix commits; all T001 cases green at the tip.
- [ ] Gate `skip`, finding `dead_code_not_applicable`, verdict `pass_with_notes`, rc 0 for Zig/Go-only (both modes).
- [ ] Python-only, mixed, and undeterminable controls unchanged.
- [ ] pytest pre-check warns and review continues; JSON line has `severity: warning`.
- [ ] ERROR_CODES.md updated; documented-codes gate green (16).
- [ ] Neutrality test + half-by-half proof recorded.
- [ ] ruff/format/mypy clean; complexity ≤15; targeted tests green with counts recorded.

## Review Guidance

Reviewer (`reviewer-renata`, not the implementer): verify red→green (check out the planning base product files and re-run T001 → must fail); verify no hard-failure type was added; verify `.py` never appears as unsupported; verify the remediation is tech-agnostic; verify the legacy and undeterminable paths are untouched; run only the targeted commands above (HARD RULE).

## Activity Log

> Append entries at the END, oldest first: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>` (UTC now: `date -u "+%Y-%m-%dT%H:%M:%SZ"`).

- 2026-09-29T06:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status; record subtasks with `spec-kitty agent tasks mark-status <Txxx> --status done`.
