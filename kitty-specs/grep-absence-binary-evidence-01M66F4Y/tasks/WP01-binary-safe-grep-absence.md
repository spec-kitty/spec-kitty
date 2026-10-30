---
work_package_id: WP01
title: Binary-safe grep_absence verdict and named evidence
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- C-002
planning_base_branch: issue-6761-grep-absence-binary-evidence
merge_target_branch: issue-6761-grep-absence-binary-evidence
branch_strategy: Planning artifacts for this mission were generated on issue-6761-grep-absence-binary-evidence. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6761-grep-absence-binary-evidence unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-grep-absence-binary-evidence-01M66F4Y
base_commit: e09f1b06e0521bd53a5cd3b10b810f36831aa7f7
created_at: '2026-10-30T13:20:01.668211+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Defect fix
history:
- at: '2026-10-30T00:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/acceptance/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/acceptance/matrix.py
- tests/specify_cli/acceptance/test_negative_invariant_authoring.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Binary-safe grep_absence verdict and named evidence

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
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

`src/specify_cli/acceptance/matrix.py::_check_grep_absence` must:

1. Judge **text only**: add `-I` (skip binary files) to the grep invocation, so a stale `.pyc` under `__pycache__/` holding the pattern cannot keep a removed string "present" (FR-001, issue #6761).
2. Never record an empty match list on a non-absent verdict: when grep exits 0 with empty stdout, fall back to stderr (which GNU grep ≥ 3.5 uses for `binary file matches`) so the evidence names what grep saw (FR-002).
3. Keep the text-match behaviour intact: a pattern in a tracked text file still yields `still_present` with the first matching lines in the evidence (FR-003, positive control).

Success criteria SC-001..SC-003 in `kitty-specs/grep-absence-binary-evidence-01M66F4Y/spec.md`.

## Context & Constraints

- Defect: spec-kitty/spec-kitty#6761. Grounding repro (GNU grep 3.11): a `.pyc` containing the pattern, tracked `.py` clean → `grep -r --exclude=acceptance-matrix.json --exclude-dir=.git -- <pat> .` exits 0 with **empty stdout** and `binary file matches` on stderr; the matcher records `still_present` with evidence `grep found matches: `.
- Entry point: the `acceptance_verdict` CLI command (`spec-kitty agent acceptance-verdict --negative-invariant ... --execute`) → `enforce_negative_invariants` → `_check_invariant` → `_check_grep_absence`. Tests must drive this path, not call the private helper alone (non-vacuity: production path).
- Existing tests that own this contract live in `tests/specify_cli/acceptance/test_negative_invariant_authoring.py` (`TestNegativeInvariantRegisterAndExecute`: confirmed-absent and still-present cases with `_init_flat_mission` fixture repos). Extend that module; do not create a parallel test file.
- Constraints: no CLI/schema change (NFR-001); still one `grep` subprocess (NFR-002); #2743 and #5464 are out of scope (C-001); keep the 5-line match-list cap and the 500-char error-detail cap.
- Charter: `.kittify/charter/charter.md`; plan: `kitty-specs/grep-absence-binary-evidence-01M66F4Y/plan.md`.

## Branch Strategy

- **Strategy**: populated automatically by `spec-kitty agent mission finalize-tasks`.
- **Planning base branch**: `issue-6761-grep-absence-binary-evidence`
- **Merge target branch**: `main`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Do NOT change them manually.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first stale-`.pyc` regression test

- **Purpose**: Prove the defect through the production entry point before the fix exists (C-002, DIRECTIVE_034).
- **Steps**: In `tests/specify_cli/acceptance/test_negative_invariant_authoring.py`, add a test class/method following the existing `_init_flat_mission` pattern. Inside the fixture repo: write `legacy_mod.py` containing `STALE_PYC_TOKEN_<random>` ; run `compileall`/`py_compile` so `__pycache__/legacy_mod.cpython-*.pyc` holds the token; then rewrite `legacy_mod.py` without the token; commit. Register and execute a `grep_absence` negative invariant for that token via `acceptance_verdict(..., execute=True)`; assert `result == "confirmed_absent"`.
- **Files**: `tests/specify_cli/acceptance/test_negative_invariant_authoring.py`.
- **Parallel?**: No.
- **Notes**: The test MUST fail on current `main` (run it and capture the red). Use a token unlikely to collide with repo content. The `.pyc` must not be git-tracked (gitignored `__pycache__` is the whole point) — do not `git add` it.

### Subtask T002 – Same-fixture positive control

- **Purpose**: Non-vacuity — prove the probe can still see a text match after `-I` lands.
- **Steps**: On the same fixture style, keep a token in a tracked **text** file (e.g. `notes.md`) and assert `still_present` with evidence naming that file. Keep the existing `test_execute_records_still_present_when_pattern_matches` green.
- **Files**: same test module.
- **Parallel?**: No.

### Subtask T003 – Evidence fallback test

- **Purpose**: FR-002 — exit 0 with empty stdout must not yield an empty match list.
- **Steps**: Drive the matcher into the exit-0/empty-stdout state (e.g. monkeypatch `subprocess.run` used by the module to return `returncode=0`, `stdout=""`, `stderr="grep: ./x.pyc: binary file matches"`, or construct the binary-only fixture) and assert the recorded evidence contains that stderr content. Keep truncation discipline.
- **Files**: same test module.
- **Parallel?**: No.
- **Notes**: A monkeypatch at the `specify_cli.acceptance.matrix.subprocess.run` seam is acceptable for this half of the compound fix (the stderr path is otherwise unreproducible once `-I` lands); the entry-point path is still exercised end-to-end by T001/T002.

### Subtask T004 – Fix `_check_grep_absence`

- **Purpose**: FR-001 + FR-002.
- **Steps**: In `src/specify_cli/acceptance/matrix.py::_check_grep_absence`: add `"-I"` to the grep argv (next to `-r`); in the `returncode == 0` branch, when `result.stdout.strip()` is empty, build the match list from `result.stderr` (first 5 non-empty lines) so evidence reads e.g. `grep found matches (stderr): grep: ./__pycache__/x.pyc: binary file matches` — or an equivalent wording that names what grep saw. Do not change the exit-1 (`confirmed_absent`) or error (exit ≥ 2) branches beyond what the fallback requires.
- **Files**: `src/specify_cli/acceptance/matrix.py`.
- **Parallel?**: No.
- **Notes**: Half-by-half proof: reverting only `-I` must redden T001; reverting only the stderr fallback must redden T003.

### Subtask T005 – Verify and record

- **Purpose**: Green suite and clean checks.
- **Steps**: Run `uv run pytest tests/specify_cli/acceptance/test_negative_invariant_authoring.py tests/specify_cli/acceptance/test_acceptance_verdict_command.py -q` plus the repo's lint (`ruff`) and type (`mypy` per project config) on the touched files. Record T001–T005 done via `spec-kitty agent tasks mark-status`.
- **Parallel?**: No.

## Test Strategy (include only when tests are required)

- Tests live in `tests/specify_cli/acceptance/test_negative_invariant_authoring.py` (the module that owns the `acceptance-verdict` contract).
- Command: `uv run pytest tests/specify_cli/acceptance/test_negative_invariant_authoring.py -q` (fixture-repo based; no network).
- Compiler/typecheck: run the project's configured typecheck on touched files, matching CI.

## Risks & Mitigations

- Weakening the text search → T002 positive control.
- BSD grep differences → `-I` is portable; CI is GNU grep.
- Vacuous compound fix → T001/T003 prove each half.
- Fixture flakiness from real `compileall` → deterministic in-repo Python, no network.

## Review Guidance

- Check the red-first ordering (red tests committed before the fix, or the same commit shows test + fix with the red evidence recorded in the WP history).
- Check `-I` placement and that the exit-1 branch is untouched.
- Check evidence wording names the matched source (file path from grep output).

## Progress & Status

Progress, history, and status all live in the status event log (`status.events.jsonl`) — never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
