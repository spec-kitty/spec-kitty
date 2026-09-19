---
work_package_id: WP04
title: agent release prep pyproject guard, 3 modes (#4637)
dependencies:
- WP01
requirement_refs:
- FR-007
planning_base_branch: fix/cli-error-surface-seam
merge_target_branch: fix/cli-error-surface-seam
branch_strategy: Planning artifacts for this mission were generated on fix/cli-error-surface-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-error-surface-seam unless the human explicitly redirects the landing branch.
subtasks:
- T014
- T015
- T016
phase: Phase 2 - Adoption
history:
- at: '2026-09-19T10:45:02Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/release/payload.py
create_intent:
- tests/release/test_release_prep_guard.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/release/payload.py
- src/specify_cli/cli/commands/agent/release.py
- tests/release/test_release_prep_guard.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – agent release prep pyproject guard, 3 modes (#4637)

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

*[No prior review cycle — this is the first pass for WP04.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

`spec-kitty agent release prep --channel <alpha|beta|stable>` (and its `--json`
variant) currently crashes with a raw Python traceback for **three** distinct
`pyproject.toml` failure modes instead of the clean typed error FR-007 requires:

1. **Missing `pyproject.toml`** — `_read_current_version` (`src/specify_cli/release/payload.py:62-75`)
   opens `pyproject_path` unconditionally at line 70; a missing file raises
   `FileNotFoundError` straight through `build_release_prep_payload` → the `prep`
   command (`src/specify_cli/cli/commands/agent/release.py:100-120`) → Typer's
   default traceback renderer.
2. **`pyproject.toml` present but `[project].version` absent** — `data["project"]["version"]`
   at line 72 raises `KeyError` (missing `[project]` table too) — same crash path.
3. **Malformed/unparseable TOML** — `tomllib.load(fh)` at line 71 raises
   `tomllib.TOMLDecodeError` on invalid syntax — same crash path.

**Done when**: all three modes raise a single typed `ReleasePyprojectError`
(`GuardedReadError` subclass, landed by WP01) that the WP01 global Typer hook
renders as a clean `Error: <reason>` line at exit 1 without `--json`, and as a
single `{"error", "kind", "path"}` JSON object on stdout at exit 1 with `--json`
— never a traceback, never mixed prose + JSON on stdout.

## Context & Constraints

- **Dependency**: WP01 must be merged/available first — it lands `kernel.guarded_read.read_guarded`,
  the `GuardedReadError` base, and the global Typer hook this WP adopts. Do not
  reimplement any of that here; import it.
- Reference: `kitty-specs/cli-error-surface-seam-01M2WJD2/{spec.md,plan.md,quickstart.md}`,
  `kitty-specs/cli-error-surface-seam-01M2WJD2/contracts/guarded-read-primitive.md`,
  `kitty-specs/cli-error-surface-seam-01M2WJD2/contracts/error-envelope.md`,
  `.kittify/charter/charter.md`.
- **Contract**: `read_guarded(path, parse, *, errors=(...), error_cls=..., mode=...)`
  reads once, applies `parse`, and on any of `(OSError, UnicodeDecodeError, *errors)`
  raised by the read or by `parse`, raises `error_cls(path=str(path), reason=<message>)`.
  Anything not in the declared tuple propagates as a real bug (traceback) — do not
  widen the exception tuple beyond the three modes in scope.
- **The hook owns presentation.** `agent release.py`'s `prep` command must **not**
  grow a try/except around `build_release_prep_payload` for this error class — it
  raises `ReleasePyprojectError`, the WP01 hook renders it. This is the pattern in
  `quickstart.md` §"Reading a state/config/input file in a command".
- **Charter constraints**: cyclomatic complexity ≤ 15 (ruff `C901` / Sonar `S3776`);
  ruff + mypy clean, zero suppressions — no `# noqa`/`# type: ignore` to make this
  pass; ≥ 90% new-code coverage on `payload.py`'s changed lines; new kernel/domain
  symbols declare `__all__` with at least one real caller (no dead exports).
- `payload.py` currently declares `_read_current_version` return type contract via
  a docstring listing `FileNotFoundError`/`KeyError` — that docstring is now wrong
  and must be updated to describe `ReleasePyprojectError` instead.

## Branch Strategy

- **Strategy**: coordination-bearing (`topology: coord`) — WP04 runs on its own
  lane worktree, branched from the mission coordination branch.
- **Planning base branch**: `main` (mission `meta.json` `target_branch`
  resolves through `fix/cli-error-surface-seam`)
- **Merge target branch**: `fix/cli-error-surface-seam`

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.
> Use `spec-kitty implement WP04` to resolve/create the actual lane worktree —
> do not hand-construct a `.worktrees/...` path.

## Subtasks & Detailed Guidance

### T014 – Red-first: release prep crashes for 3 pyproject modes

- **Purpose**: Prove, through the real `spec-kitty agent release prep` command
  entry point (not by calling `_read_current_version` directly), that all three
  modes crash with an unhandled Python exception on the current base branch.
- **Steps**:
  1. In `tests/release/test_release_prep_guard.py`, build a temp repo root
     fixture per scenario using `tmp_path` (a real filesystem, not a mock).
  2. Scenario A — missing file: create `tmp_path` with no `pyproject.toml` at all.
  3. Scenario B — missing version: write a `pyproject.toml` with `[project]`
     but no `version` key (and a variant with no `[project]` table at all).
  4. Scenario C — malformed TOML: write a `pyproject.toml` with unbalanced
     brackets / invalid TOML syntax.
  5. For each scenario, invoke the Typer CLI via `CliRunner` (or the project's
     existing CLI test harness) calling `spec-kitty agent release prep --channel
     alpha --repo-root <tmp_path>`, both without and with `--json`.
  6. Mark each test `@pytest.mark.regression` and reference `#4637` in the
     docstring/comment. Assert the CURRENT (pre-fix) behavior is an unhandled
     exception (`result.exception is not None` and its type is
     `FileNotFoundError`/`KeyError`/`tomllib.TOMLDecodeError` respectively) —
     this is the RED state on `main`/base.
- **Files**: `tests/release/test_release_prep_guard.py` (new).
- **Parallel?**: No — T014 must land before T015/T016 in the same PR sequence
  (red before green), though all of WP04 can run in parallel with WP02/WP03/WP05–WP07.
- **Notes**: Do not skip Scenario B's "no `[project]` table" sub-case — the
  plan explicitly calls out `KeyError`/`TypeError` as the caller-supplied
  exception tuple for this mode; both shapes must be covered.

### T015 – `ReleasePyprojectError` + guard the version read (3 modes)

- **Purpose**: Close all three crash modes behind one typed error via the
  WP01 primitive, per `contracts/guarded-read-primitive.md`.
- **Steps**:
  1. Define `class ReleasePyprojectError(GuardedReadError)` — colocate it in
     `src/specify_cli/release/payload.py` (or the module's existing errors
     surface if the codebase has one; check for a `release/errors.py` first
     and prefer consolidating there if it exists, otherwise define in `payload.py`
     next to `_read_current_version`).
  2. Rewrite `_read_current_version` to route through `read_guarded`:
     ```python
     from kernel.guarded_read import read_guarded

     def _parse_version(fh_bytes: bytes) -> str:
         data = tomllib.loads(fh_bytes.decode("utf-8"))
         version = data["project"]["version"]
         if not isinstance(version, str):
             raise TypeError(f"Expected version to be a string, got {type(version)!r}")
         return version

     def _read_current_version(repo_root: Path) -> str:
         pyproject_path = repo_root / "pyproject.toml"
         return read_guarded(
             pyproject_path,
             _parse_version,
             errors=(tomllib.TOMLDecodeError, KeyError, TypeError),
             error_cls=ReleasePyprojectError,
             mode="bytes",
         )
     ```
     Adjust the `parse` signature to match the primitive's actual `mode="bytes"`
     contract as landed by WP01 (bytes in, `T` out) — `read_guarded` already
     covers the missing-file case via its always-on `OSError` branch, so no
     separate `FileNotFoundError` handling is needed here.
  3. Write an actionable `reason` message per mode in `ReleasePyprojectError`
     (or let the primitive's default message stand if WP01's default is already
     actionable — verify against `contracts/error-envelope.md`'s example shape).
  4. `agent/release.py`'s `prep` command (line ~100) needs **no new try/except**
     — confirm the WP01 hook is already registered on the top-level app (it
     should be, since WP01 is a hard dependency) and that this command reaches
     it undecorated.
- **Files**: `src/specify_cli/release/payload.py`; possibly
  `src/specify_cli/cli/commands/agent/release.py` only if the command currently
  wraps `build_release_prep_payload` in a local try/except that needs removing.
- **Parallel?**: Depends on T014 landing first (red-first discipline); can run
  in parallel with all other WPs' T0xx-equivalent steps.
- **Notes**: Keep `kernel/guarded_read.py` untouched — WP04 is a **consumer**
  of the primitive, not its owner. If the primitive's exact signature landed
  by WP01 differs from `contracts/guarded-read-primitive.md`'s indicative
  signature, follow the merged WP01 code, not this prompt's illustration.

### T016 – Green: exit 1 typed error + `--json` object

- **Purpose**: Flip the T014 regression tests from red to green and add the
  `--json` machine-contract assertions from `contracts/error-envelope.md`.
- **Steps**:
  1. Update the T014 tests: each of the 3 scenarios now asserts exit code 1
     (not an unhandled exception), a clean `Error: <reason>` line on stderr for
     the non-`--json` invocation, and — for `--json` — exactly one parseable
     JSON object on stdout with `{"error": ..., "kind": "ReleasePyprojectError",
     "path": "<pyproject.toml path>"}`, and nothing else on stdout.
  2. Add an explicit assertion that stdout under `--json` contains no non-JSON
     prose (NFR-002 / INV-1) — `json.loads(result.stdout)` must not raise.
  3. Add a happy-path regression: a well-formed `pyproject.toml` still returns
     the correct version string end-to-end (guards against a `read_guarded`
     adoption bug silently changing the happy path).
  4. Run the targeted test file plus its blast radius per CLAUDE.md's test
     policy: `tests/release/`, `tests/cli/`, and (since `kernel/errors.py`
     changed under WP01, not here) confirm no `tests/architectural/` change is
     needed for WP04 itself.
- **Files**: `tests/release/test_release_prep_guard.py`.
- **Parallel?**: No — final step of WP04's sequence.
- **Notes**: Do not weaken NFR-003 — `read_guarded` must not add a second file
  open beyond the single guarded read; do not additionally `pyproject_path.exists()`
  probe before calling `read_guarded` (that would be a redundant stat/open).

## Test Strategy

- **Mandatory**: `tests/release/test_release_prep_guard.py` (new, this WP's
  `create_intent`) covering all 3 modes × {no `--json`, `--json`} = 6 core cases,
  plus the happy-path regression.
- **Commands**:
  ```bash
  .venv/bin/python -m pytest tests/release/test_release_prep_guard.py -v
  .venv/bin/python -m pytest tests/release/ -v          # owning subsystem
  make test-fast                                        # shared baseline
  uv run --frozen mypy -p specify_cli.release
  uv run --frozen ruff check src/specify_cli/release/ src/specify_cli/cli/commands/agent/release.py
  uv run --frozen ruff format --check src/specify_cli/release/ src/specify_cli/cli/commands/agent/release.py
  ```
- **Fixtures**: use `tmp_path` for each scenario's repo root; do not depend on
  the real repo's own `pyproject.toml`.
- Record the exact commands and pass/fail counts in the PR per CLAUDE.md's
  "Test policy — what you must run for a change".

## Risks & Mitigations

- **Risk**: `read_guarded`'s exact `mode="bytes"` vs `mode="text"` handling for
  TOML (which requires bytes for `tomllib.load`) may not match this prompt's
  illustration once WP01 lands. **Mitigation**: adapt to WP01's actual merged
  signature; do not block on this prompt's exact code sample.
- **Risk**: Widening the `errors=(...)` tuple too far could mask a genuine bug
  (e.g. catching bare `Exception`). **Mitigation**: keep the tuple to exactly
  `(tomllib.TOMLDecodeError, KeyError, TypeError)` — `OSError` is already always
  covered by the primitive.
- **Risk**: `agent/release.py` may have an existing local error-formatting path
  for other `prep` failures that could accidentally intercept `ReleasePyprojectError`
  first. **Mitigation**: audit `agent/release.py` for any bare `except Exception`
  around the `build_release_prep_payload` call and remove it if present — the
  hook is the single presentation authority (C-002).

## Review Guidance

- Confirm `_read_current_version` no longer directly raises `FileNotFoundError`/
  `KeyError`/`tomllib.TOMLDecodeError` to its caller — all three now surface as
  `ReleasePyprojectError` via `read_guarded`.
- Confirm the `prep` command has **no** new try/except for presentation —
  the domain error propagates to the WP01 hook.
- Confirm the `--json` object matches `contracts/error-envelope.md` exactly:
  `error`/`kind`/`path` keys, single object, nothing else on stdout.
- Confirm the happy path (valid pyproject) is unchanged and still covered.
- Confirm `mypy -p specify_cli.release` and `ruff check`/`ruff format --check`
  pass with zero suppressions added.

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

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task WP04 --to <status>` to change WP status.

### Optional Phase Subdirectories

For large features, organize prompts under `tasks/` to keep bundles grouped while maintaining lexical ordering.
