---
work_package_id: WP05
title: intake - stdin non-UTF-8 guard (#4739)
dependencies:
- WP01
requirement_refs:
- FR-008
planning_base_branch: fix/cli-error-surface-seam
merge_target_branch: fix/cli-error-surface-seam
branch_strategy: Planning artifacts for this mission were generated on fix/cli-error-surface-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-error-surface-seam unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
phase: Phase 2 - Adoption
history:
- at: '2026-09-19T10:45:02Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/intake/scanner.py
create_intent:
- tests/specify_cli/cli/commands/test_intake_stdin_guard.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/intake/scanner.py
- src/specify_cli/cli/commands/intake.py
- tests/specify_cli/cli/commands/test_intake_stdin_guard.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – intake - stdin non-UTF-8 guard (#4739)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[No prior review cycle — this is the first pass for WP05.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

`head -c 500 /dev/urandom | spec-kitty intake -` crashes today with an unhandled
`UnicodeDecodeError` instead of the clean typed error the file-path variant of
the same intake already produces for the same bytes.

**Verified root cause**: `read_stdin_capped` (`src/specify_cli/intake/scanner.py:193-238`)
already wraps the *bytes*-branch decode at line 234 (`buf.decode("utf-8")`) in a
`try/except UnicodeDecodeError` at line 237, raising `IntakeFileUnreadableError`
cleanly. But the CLI's stdin call site (`src/specify_cli/cli/commands/intake.py`,
around line 306-308) passes `sys.stdin` — a **text** stream, not a bytes stream —
so `buf = stream.read(cap + 1)` at scanner.py:216 performs the UTF-8 decode
**itself, inside Python's text-IO layer**, before any of scanner.py's own
try/except blocks run. The decode failure happens at line 216, which is entirely
outside the guarded bytes-branch at lines 231-238. The `isinstance(buf, str)`
branch at line 226 is dead for the failure case — it never gets a `str` back
because `.read()` raised first.

**Done when**: piping non-UTF-8 bytes into `spec-kitty intake -` produces the
same clean exit-1 typed-error behavior as piping the same bytes through a file
argument — parity between the two intake paths, both routed through the WP01
hook.

## Context & Constraints

- **Dependency**: WP01 lands `kernel.guarded_read.read_guarded`, the
  `GuardedReadError` base, and the global Typer hook. WP01 also **re-parents**
  `IntakeFileUnreadableError` as a `GuardedReadError` subclass (per
  `plan.md`'s legacy-error mermaid diagram, group E3) — do not re-parent it
  again here; just confirm it already inherits from the base once WP01 lands,
  and rely on the existing hook to render it. WP05 does not need to introduce
  a new error class; `IntakeFileUnreadableError` already exists and already
  carries the right shape (`path`, `cause`).
- Reference: `kitty-specs/cli-error-surface-seam-01M2WJD2/{spec.md,plan.md,quickstart.md}`,
  `contracts/guarded-read-primitive.md`, `contracts/error-envelope.md`,
  `.kittify/charter/charter.md`.
- The fix belongs in **`read_stdin_capped`** (or its call site), not in the
  file-reading branch of `scanner.py` — do not touch the already-correct
  file-path helper that reads via `candidate.read_text(encoding="utf-8")`
  (lines ~182-190).
- Two viable fix shapes — pick whichever keeps the function simplest and under
  the complexity ceiling:
  1. Read from `sys.stdin.buffer` (bytes) at the call site in `intake.py`
     instead of `sys.stdin` (text), so `read_stdin_capped` always receives a
     bytes stream and the existing bytes-branch guard (lines 231-238) already
     covers it — **no scanner.py change needed**, only the `intake.py` call site.
  2. Keep passing `sys.stdin` but wrap the `stream.read(cap + 1)` call itself
     in a `try/except UnicodeDecodeError` inside `read_stdin_capped`, raising
     `IntakeFileUnreadableError` there too.
  Prefer option 1 if `sys.stdin.buffer` is reliably available in the test
  harness and in real terminals/pipes (it normally is on all three supported
  platforms) — it deletes a special case rather than adding one. If option 1
  breaks any existing stdin test that feeds a `io.StringIO` directly, fall
  back to option 2 and guard both the buffer path and the text path.
- **Charter constraints**: cyclomatic complexity ≤ 15; ruff + mypy clean, zero
  suppressions; ≥ 90% new-code coverage on the changed lines.
- **NFR-003** (no added read work): whichever fix shape you choose must not
  add a second read of stdin or double-buffer the payload — the existing
  cap-plus-one read strategy (reading `cap + 1` bytes to detect overflow
  without unbounded buffering) must be preserved exactly.

## Branch Strategy

- **Strategy**: coordination-bearing (`topology: coord`) — WP05 runs on its own
  lane worktree, branched from the mission coordination branch.
- **Planning base branch**: `main`
- **Merge target branch**: `fix/cli-error-surface-seam`

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.
> Use `spec-kitty implement WP05` to resolve/create the actual lane worktree.

## Subtasks & Detailed Guidance

### T017 – Red-first: `intake -` non-UTF-8 stdin crashes

- **Purpose**: Prove, through the real `spec-kitty intake -` command entry
  point, that non-UTF-8 bytes piped via stdin crash with an unhandled
  `UnicodeDecodeError` today, while the equivalent bytes via a file argument
  do not.
- **Steps**:
  1. In `tests/specify_cli/cli/commands/test_intake_stdin_guard.py`, generate
     a deterministic non-UTF-8 byte sequence (e.g. `b"\xff\xfe\x00\x01" + b"x" * 100`
     — avoid a random source so the test is reproducible; do not use
     `/dev/urandom` in the test itself, only reference it in the docstring as
     the real-world repro).
  2. Invoke the CLI via the project's Typer test harness, feeding the bytes
     as stdin (e.g. `CliRunner().invoke(app, ["intake", "-"], input=<bytes>)`
     — check how the existing intake CLI tests inject stdin, in
     `tests/specify_cli/cli/commands/test_intake*.py` or `tests/intake/`, and
     match that convention rather than inventing a new one).
  3. Mark the test `@pytest.mark.regression`, reference `#4739` in the
     docstring. Assert the CURRENT (pre-fix) behavior is an unhandled
     `UnicodeDecodeError` (or the CLI runner surfacing it as
     `result.exception`) — RED on base.
  4. Add a companion test that pipes the **same non-UTF-8 bytes** through a
     temp file argument instead of stdin, and asserts that path **already**
     produces a clean `IntakeFileUnreadableError`/exit-1 (this establishes the
     parity baseline the fix must match, and should already pass on base).
- **Files**: `tests/specify_cli/cli/commands/test_intake_stdin_guard.py` (new).
- **Parallel?**: No — must land before T018/T019 within WP05; WP05 itself runs
  in parallel with WP02/WP03/WP04/WP06/WP07.
- **Notes**: If the repo already has an `intake -` stdin test file (check
  `tests/specify_cli/cli/commands/` and `tests/intake/` first), extend it
  instead of creating a fully disjoint fixture set — but this WP's
  `create_intent` specifically names `test_intake_stdin_guard.py`, so put the
  new regression tests there even if you reuse existing fixtures/helpers by
  import.

### T018 – Guard the stdin text-stream read path

- **Purpose**: Close the crash by ensuring the UTF-8 decode of stdin content
  always happens inside a guarded boundary, matching the file path's contract.
- **Steps**:
  1. Locate the stdin call site in `src/specify_cli/cli/commands/intake.py`
     (`content = read_stdin_capped(sys.stdin, cap=cap)`, around line 306-308).
  2. Apply the chosen fix shape from Context & Constraints above:
     - **Option 1 (preferred)**: change the call site to pass
       `sys.stdin.buffer` instead of `sys.stdin`, so `read_stdin_capped`
       always operates on bytes. Verify `read_stdin_capped`'s existing type
       narrowing (`isinstance(buf, str)` vs the bytes branch) still behaves
       correctly — with a bytes stream, `buf` will always be `bytes`, so the
       `str` branch becomes dead code for this call site; confirm it is not
       relied on by another caller before deleting it (grep all callers of
       `read_stdin_capped`).
     - **Option 2 (fallback)**: in `scanner.py`, wrap the `stream.read(cap + 1)`
       call itself: `try: buf = stream.read(cap + 1) except UnicodeDecodeError
       as exc: raise IntakeFileUnreadableError(path=label, cause=exc) from exc`.
  3. Whichever shape you pick, do **not** introduce a second `read_guarded`
     invocation here for stdin — `read_guarded` is a `Path`-based file-read
     primitive (per `contracts/guarded-read-primitive.md`'s signature,
     `path: Path`); stdin is a stream, not a path, so this WP hardens
     `read_stdin_capped` directly rather than routing it through
     `read_guarded`. This is consistent with the primitive's stated
     non-goal: it guards *file* reads, and `IntakeFileUnreadableError`
     already exists as the domain error for stream failures — WP01 makes it
     a `GuardedReadError` subclass so the same hook renders it.
  4. Keep the fix minimal — do not refactor `read_stdin_capped`'s overall
     cap-detection logic, only the decode-boundary.
- **Files**: `src/specify_cli/cli/commands/intake.py`; `src/specify_cli/intake/scanner.py`
  only if Option 2 is used (or if a caller audit requires updating a type hint).
- **Parallel?**: Depends on T017 landing first; can run in parallel with other
  WPs' equivalent steps.
- **Notes**: If you pick Option 1, double check any other caller of
  `read_stdin_capped` in the codebase (`grep -rn "read_stdin_capped" src/`) to
  confirm none of them still needs the text-stream (`str`) branch before
  treating it as dead code — do not delete a branch a sibling caller depends on.

### T019 – Green: stdin parity with file-path handling

- **Purpose**: Flip the T017 regression test from red to green and prove
  parity between the stdin and file-path intake routes.
- **Steps**:
  1. Update the T017 stdin test: assert exit code 1, a clean `Error: <reason>`
     line (no traceback) for the non-`--json` path, and confirm the message
     names the offending stream/handle per `IntakeFileUnreadableError`'s
     existing shape.
  2. If `intake -` supports `--json`, add the JSON-envelope assertion per
     `contracts/error-envelope.md` (single object on stdout, `kind`:
     `"IntakeFileUnreadableError"`); if `intake -` has no `--json` mode, note
     that explicitly in the test docstring and skip that assertion rather than
     inventing a flag that doesn't exist.
  3. Add a direct parity assertion: the stdin scenario and the file-argument
     scenario (from T017's companion test) both exit 1 with an
     `IntakeFileUnreadableError`-shaped message — same error family, same
     exit code.
  4. Add a happy-path stdin regression: valid UTF-8 content piped via stdin
     is still read correctly end-to-end (guards against the fix accidentally
     breaking the normal path).
  5. Run the targeted test file plus its blast radius.
- **Files**: `tests/specify_cli/cli/commands/test_intake_stdin_guard.py`.
- **Parallel?**: No — final step of WP05's sequence.
- **Notes**: Preserve the existing `IntakeTooLargeError` behavior for the
  oversized-stdin case — do not let this fix change cap-overflow handling.

## Test Strategy

- **Mandatory**: `tests/specify_cli/cli/commands/test_intake_stdin_guard.py`
  (new) covering: non-UTF-8 stdin (red→green), non-UTF-8 file-path parity
  baseline, happy-path stdin, and cap-overflow-still-works regression.
- **Commands**:
  ```bash
  .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_intake_stdin_guard.py -v
  .venv/bin/python -m pytest tests/specify_cli/cli/commands/ tests/intake/ -v
  make test-fast
  uv run --frozen mypy -p specify_cli.intake -p specify_cli.cli
  uv run --frozen ruff check src/specify_cli/intake/scanner.py src/specify_cli/cli/commands/intake.py
  uv run --frozen ruff format --check src/specify_cli/intake/scanner.py src/specify_cli/cli/commands/intake.py
  ```
- Record the exact commands and pass/fail counts in the PR per CLAUDE.md's
  "Test policy — what you must run for a change".

## Risks & Mitigations

- **Risk**: Switching to `sys.stdin.buffer` could change behavior for a
  terminal (non-piped) invocation on some platform. **Mitigation**: this
  command already requires piped/non-interactive stdin for the `-` path (per
  existing `IntakeFileUnreadableError` for a `None` stream); verify with a
  targeted manual smoke test (`echo hi | spec-kitty intake -`) in addition to
  the automated suite.
- **Risk**: Deleting the now-dead `str` branch in `read_stdin_capped` could
  break a caller this WP didn't audit. **Mitigation**: grep all call sites
  before deleting; if any other caller needs the text path, keep both branches
  and only fix the decode-boundary (Option 2) instead.
- **Risk**: Windows text-mode stdin has different newline/encoding defaults.
  **Mitigation**: `sys.stdin.buffer` is a raw byte stream on all three
  platforms — using it sidesteps platform-specific text-mode decoding
  entirely, which is part of why Option 1 is preferred.

## Review Guidance

- Confirm the fix touches only the stdin decode boundary — the file-path
  helper (`candidate.read_text(...)` guard) is untouched.
- Confirm no second `read_guarded` call was introduced for a stream (streams
  are out of `read_guarded`'s `Path`-based contract).
- Confirm parity: identical non-UTF-8 bytes via stdin and via file both exit 1
  with the same error family and no traceback.
- Confirm the cap-overflow (`IntakeTooLargeError`) path still works unchanged.
- Confirm `mypy` and `ruff check`/`ruff format --check` pass with zero new
  suppressions.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Why this matters**: The acceptance system reads the LAST activity log entry as the current state. If entries are out of order, acceptance will fail even when the work is complete.

**Initial entry**:

- 2026-09-19T10:45:02Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task WP05 --to <status>` to change WP status.

### Optional Phase Subdirectories

For large features, organize prompts under `tasks/` to keep bundles grouped while maintaining lexical ordering.
