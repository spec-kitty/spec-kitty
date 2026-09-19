---
work_package_id: WP06
title: specify --json contract + non-ASCII name reject (#4720)
dependencies:
- WP01
requirement_refs:
- FR-009
- FR-010
planning_base_branch: fix/cli-error-surface-seam
merge_target_branch: fix/cli-error-surface-seam
branch_strategy: Planning artifacts for this mission were generated on fix/cli-error-surface-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-error-surface-seam unless the human explicitly redirects the landing branch.
subtasks:
- T020
- T021
- T022
- T023
phase: Phase 2 - Adoption
history:
- at: '2026-09-19T10:45:02Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/lifecycle.py
create_intent:
- tests/specify_cli/cli/commands/test_specify_json_nonascii.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/cli/commands/lifecycle.py
- tests/specify_cli/cli/commands/test_specify_json_nonascii.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – specify --json contract + non-ASCII name reject (#4720)

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

*[No prior review cycle — this is the first pass for WP06.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

`spec-kitty specify <name> --json` currently produces three distinct wrong
shapes depending on the input's script, none of which satisfy the machine
`--json` contract:

1. **`日本語`** (non-Latin script) — `_slugify_feature_input`
   (`src/specify_cli/cli/commands/lifecycle.py:121-126`) strips every
   character (the regex `[^a-z0-9]+` matches none of them as letters/digits),
   leaving an empty slug, which raises `typer.BadParameter("Feature name
   cannot be empty.")`. Typer intercepts `BadParameter` **before** any error
   hook runs, forcing a Rich usage panel on **stderr**, exit **2**, and
   **empty stdout** — violating the `--json` contract (a JSON consumer gets
   nothing on stdout and a non-standard exit code for what should be a
   domain-level rejection, not a usage error).
2. **`Ünïcödé`** (accented Latin) — the regex silently strips diacritics and
   accepts the result, producing slug `n-c-d` (from the surviving ASCII
   fragments) with **no error at all** — a silent identity-mangling accept.
3. **`auth日本`** (mixed ASCII + non-Latin) — silently accepted and slugified
   down to `auth`, dropping the non-ASCII suffix without any indication to
   the caller that characters were discarded.

**Done when**: all three scenarios are explicitly rejected — never silently
truncated or accepted — as a single `NonAsciiNameError` (`GuardedReadError`
subclass) that the WP01 global hook renders as a JSON object on stdout at
exit **1** under `--json` (and a clean `Error: <reason>` line on stderr,
exit 1, without `--json`) — and Typer's usage-error path (exit 2) is no
longer reachable for this validation. No mission directory, branch, slug, or
`meta.json` identifier is ever written for a rejected name (NFR-005).

## Context & Constraints

- **Dependency**: WP01 lands `kernel.guarded_read.read_guarded`, the
  `GuardedReadError` base, and the global Typer hook. WP06 does **not** use
  `read_guarded` itself — per `contracts/guarded-read-primitive.md`'s
  Non-goals section, the primitive is not a validator for operator input
  strings; a name-slug rejection is not a file read. WP06 instead raises a
  domain error **directly**, which the same hook still renders (per
  `quickstart.md`'s "Validating operator input (not a file read)" section).
- Reference: `kitty-specs/cli-error-surface-seam-01M2WJD2/{spec.md,plan.md,quickstart.md}`,
  `contracts/error-envelope.md`, `.kittify/charter/charter.md`, and decision
  `01M2WJE53KMFBGEJX8JMFT71EE` (non-ASCII rejected explicitly, never silently
  truncated; routes through the presentation hook, not the read primitive —
  cited in spec.md FR-010).
- **Current code** (`src/specify_cli/cli/commands/lifecycle.py`):
  ```python
  def _slugify_feature_input(value: str) -> str:
      """Normalize a free-form feature name to kebab-case slug text."""
      slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
      if not slug:
          raise typer.BadParameter("Feature name cannot be empty.")
      return slug
  ```
  This function is called from `specify(...)` at line ~149
  (`slug = _slugify_feature_input(mission)`), before `_enforce_initialized`'s
  JSON-aware error path even gets a chance — note `_enforce_initialized`
  already demonstrates the correct pattern for a JSON-aware error at lines
  95-118 (build the envelope, print, `raise typer.Exit(code=1)`), and there is
  a **sibling** function `_require_mission_or_exit` (line ~191-204) whose
  docstring already says *"do not use `typer.BadParameter` here — its Rich
  error-panel rendering is dropped by [json output]"* — i.e. this exact
  BadParameter footgun has already been diagnosed and worked around once in
  this file for a different command; WP06 applies the same lesson to
  `_slugify_feature_input`.
- **Two distinct failure classes to preserve as distinct messages** (per the
  Body brief): keep "no name given" (whitespace-only input, e.g. `"   "`) as
  a **different** message from "no usable ASCII characters in `<value>`"
  (e.g. `日本語`) — do not collapse them into one generic string; a caller
  debugging automation needs to tell "you passed nothing" from "you passed
  non-ASCII" apart.
- **Explicit-reject, never-truncate rule**: `Ünïcödé` and `auth日本` must now
  **fail** the same way `日本語` does (an explicit `NonAsciiNameError`) —
  do not special-case "still has some surviving ASCII" as an accept path.
  The whole point of decision `01M2WJE53KMFBGEJX8JMFT71EE` is that **any**
  non-ASCII character in the name is a hard reject, named in the error.
- **Terminology canon**: keep any new user-facing string in Mission-canon
  language (`Mission`, not `feature`) wherever the string is user-facing —
  note the *variable* name `mission`/`_slugify_feature_input` is existing
  code and out of scope for a rename in this WP (do not do an unrelated
  terminology sweep here); only touch strings/identifiers this WP's fix
  actually needs to introduce or change.
- **Charter constraints**: cyclomatic complexity ≤ 15; ruff + mypy clean, zero
  suppressions; ≥ 90% new-code coverage on the changed lines; no gate-silencing
  `# noqa`/`# type: ignore`.

## Branch Strategy

- **Strategy**: coordination-bearing (`topology: coord`) — WP06 runs on its own
  lane worktree, branched from the mission coordination branch.
- **Planning base branch**: `main`
- **Merge target branch**: `fix/cli-error-surface-seam`

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.
> Use `spec-kitty implement WP06` to resolve/create the actual lane worktree.

## Subtasks & Detailed Guidance

### T020 – Red-first: 3 `--json` failure shapes for `specify`

- **Purpose**: Prove, through the real `spec-kitty specify <name> --json`
  command entry point, that each of the three inputs produces a
  contract-violating shape today.
- **Steps**:
  1. In `tests/specify_cli/cli/commands/test_specify_json_nonascii.py`, set up
     an initialized project fixture (`assert_initialized` must pass — reuse
     whatever fixture the existing `specify` command tests use; check
     `tests/specify_cli/cli/commands/test_lifecycle*.py` or equivalent for the
     established pattern rather than inventing a new init fixture).
  2. Scenario A — `日本語`: invoke `spec-kitty specify 日本語 --json` and
     assert the CURRENT (pre-fix) behavior: exit code **2**, **empty**
     stdout, and a Rich usage panel on stderr (or at minimum: stdout does not
     parse as JSON and exit code is 2, not 1) — RED on base.
  3. Scenario B — `Ünïcödé`: invoke `spec-kitty specify Ünïcödé --json` and
     assert the CURRENT behavior: exit code 0 (or whatever "success" looks
     like today) with a silently mangled slug (`n-c-d` or similar) — i.e. no
     rejection at all — RED on base (the test asserts the wrong-but-current
     silent-accept, proving the defect).
  4. Scenario C — `auth日本`: same pattern — assert silent accept, slug
     truncated to `auth`, no error — RED on base.
  5. Mark all three `@pytest.mark.regression`, reference `#4720` in the
     docstring.
- **Files**: `tests/specify_cli/cli/commands/test_specify_json_nonascii.py` (new).
- **Parallel?**: No — must land before T021/T022/T023 within WP06; WP06 runs
  in parallel with WP02/WP03/WP04/WP05/WP07.
- **Notes**: Use exact byte-for-byte string literals (`"日本語"`, `"Ünïcödé"`,
  `"auth日本"`) as given in this prompt/spec — do not substitute equivalent
  but different code points; the spec pins these exact examples for
  reproducibility and for the NFR-005 accented-Latin + non-Latin-script
  regression coverage requirement.

### T021 – `NonAsciiNameError` + replace `typer.BadParameter`

- **Purpose**: Stop `_slugify_feature_input` from raising a Typer usage
  error; raise a hook-owned domain error instead, and make the rejection
  explicit for every non-ASCII input (not just the all-non-ASCII case).
- **Steps**:
  1. Define `class NonAsciiNameError(GuardedReadError)` in
     `src/specify_cli/cli/commands/lifecycle.py` (or the module's existing
     domain-errors surface if `specify_cli.cli` has one — check for an
     `errors.py` under `src/specify_cli/cli/` first).
  2. Rewrite `_slugify_feature_input` to:
     - First check for the whitespace-only / empty-input case (preserve this
       as its own distinct message, e.g. "no name given" — do not change
       this existing user-facing behavior's wording unnecessarily, only its
       raise mechanism if it currently also uses `BadParameter`).
     - Then explicitly test whether `value` (after `.strip()`) contains any
       non-ASCII character — e.g. `if not value.strip().isascii():` — and if
       so, raise `NonAsciiNameError(path=value, reason=f"name {value!r} has
       no usable ASCII characters")` (or a closer variant distinguishing
       "some ASCII survives but characters would be silently dropped" from
       "zero usable ASCII characters remain" if you judge the two deserve
       different reasons — but both must reject, never accept).
     - Only run the existing `re.sub(r"[^a-z0-9]+", "-", ...)` slugify logic
       on an already-ASCII-validated string, so a surviving-ASCII case like
       `auth日本` never reaches the silent-truncate path.
  3. Remove the `typer.BadParameter` import/usage from this function
     entirely — confirm no other code path in `lifecycle.py` still needs it
     for `_slugify_feature_input` specifically (other functions in the file
     may still legitimately use `BadParameter` for genuine Typer usage
     errors — do not touch those).
  4. Ensure **no side effect** (no directory creation, no git branch, no
     `meta.json` write) happens before this validation runs — check the call
     order in `specify(...)`: `_slugify_feature_input` must be called (and
     able to raise) before any mission-scaffolding write. If any write
     currently happens first, reorder so validation is strictly first.
- **Files**: `src/specify_cli/cli/commands/lifecycle.py`.
- **Parallel?**: Depends on T020 landing first; can run in parallel with
  other WPs' equivalent steps.
- **Notes**: Keep the function's cyclomatic complexity low — extract a small
  `_reject_if_non_ascii(value: str) -> None` helper if the combined checks
  push `_slugify_feature_input` toward the complexity ceiling.

### T022 – Route the name-validation error through the hook as JSON

- **Purpose**: Ensure `specify --json` presents `NonAsciiNameError` as a
  single JSON object on stdout at exit 1, consistent with every other
  `specify --json` error path in this file (compare `_enforce_initialized`'s
  existing JSON-envelope pattern at lines 95-118).
- **Steps**:
  1. Confirm the WP01 global hook is registered on the top-level app before
     `specify(...)` runs — WP06 is a hard dependent of WP01, so this should
     already be true; do not add a **second**, command-local try/except
     around `_slugify_feature_input`'s call site to hand-roll JSON — that
     would violate "the command does not try/except for presentation" (C-002,
     single authority) and would risk a shape divergent from
     `contracts/error-envelope.md`.
  2. If `specify(...)`'s existing structure calls
     `_slugify_feature_input(mission)` in a context where an in-function
     try/except already exists for a different purpose (check the code around
     line 149), make sure `NonAsciiNameError` is allowed to propagate past
     it uncaught — narrow any existing except clause if it is currently too
     broad and would inadvertently swallow the new error.
  3. Verify the JSON object's `path` field carries the offending name value
     (per `contracts/error-envelope.md`'s note: `NonAsciiNameError` carries
     the offending name as `path` or a dedicated field — pick `path` for
     consistency with every other error in this mission, since the contract
     says "always a stable machine field" and `path` is the field every
     other `GuardedReadError` subclass already uses).
- **Files**: `src/specify_cli/cli/commands/lifecycle.py`.
- **Parallel?**: Can be done alongside T021 as part of the same refactor;
  sequenced before T023's green pass.
- **Notes**: This subtask is mostly verification/wiring — if T021 is
  implemented correctly (error raised directly, no local catch), T022 may
  require no additional code changes beyond a targeted audit. Do not invent
  a parallel presentation path.

### T023 – Green: 3 scenarios + NFR-005 no-write + identifier-safety regression

- **Purpose**: Flip the T020 regression tests to assert the correct
  post-fix behavior, and add the negative NFR-005 assertion plus the
  identifier-safety regression matrix.
- **Steps**:
  1. Update all three T020 scenarios (`日本語`, `Ünïcödé`, `auth日本`) to
     assert: exit code **1** (not 2, not 0), a single parseable JSON object
     on stdout (`json.loads(result.stdout)` succeeds) shaped per
     `contracts/error-envelope.md` (`error`, `kind: "NonAsciiNameError"`,
     `path: <original value>`), and **nothing else** on stdout.
  2. Add the non-`--json` variant for at least one scenario: a clean
     `Error: <reason>` line on stderr, exit 1, no traceback.
  3. Add the NFR-005 **negative assertion**: for each of the three rejected
     names, assert that **no** mission directory was created under
     `kitty-specs/`, no git branch was created, no `meta.json` was written,
     and no slug/identifier from the rejected name appears anywhere on disk
     after the command returns non-zero. This is the actual data-loss guard
     the spec calls out — do not skip it as "implied by exit 1".
  4. Add the identifier-safety regression matrix explicitly required by the
     spec: **at least one accented-Latin example** (`Ünïcödé` satisfies this)
     and **at least one non-Latin-script example** (`日本語` or `auth日本`
     satisfies this) — confirm both are present and both reject.
  5. Add a happy-path regression: a valid ASCII name (e.g. `auth-refactor`)
     still slugifies and proceeds exactly as before — guards against the
     fix over-rejecting valid input.
  6. Confirm the "no name given" (whitespace-only) message is still distinct
     from the new "no usable ASCII characters in `<value>`" message — add an
     explicit assertion the two strings differ.
  7. Run the targeted test file plus its blast radius.
- **Files**: `tests/specify_cli/cli/commands/test_specify_json_nonascii.py`.
- **Parallel?**: No — final step of WP06's sequence.
- **Notes**: If the existing `specify` test suite (elsewhere in the repo)
  has any test asserting the OLD silent-truncate or old `BadParameter`/exit-2
  behavior for a non-ASCII name, that test is now stale and must be
  updated/removed as part of this WP's blast radius — search for it
  (`grep -rn "BadParameter\|Feature name cannot be empty" tests/`) before
  declaring green.

## Test Strategy

- **Mandatory**: `tests/specify_cli/cli/commands/test_specify_json_nonascii.py`
  (new) covering the 3 rejection scenarios × {`--json`, no `--json`}, the
  NFR-005 no-write negative assertion, the identifier-safety matrix
  (accented-Latin + non-Latin-script), the distinct-message assertion, and
  the ASCII happy-path regression.
- **Commands**:
  ```bash
  .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_specify_json_nonascii.py -v
  .venv/bin/python -m pytest tests/specify_cli/cli/commands/ -v
  make test-fast
  uv run --frozen mypy -p specify_cli.cli
  uv run --frozen ruff check src/specify_cli/cli/commands/lifecycle.py
  uv run --frozen ruff format --check src/specify_cli/cli/commands/lifecycle.py
  pytest tests/architectural/test_no_legacy_terminology.py  # touching user-facing prose
  ```
- Record the exact commands and pass/fail counts in the PR per CLAUDE.md's
  "Test policy — what you must run for a change".

## Risks & Mitigations

- **Risk**: Widening the ASCII check could reject a legitimate ASCII name
  that merely contains unusual-but-valid punctuation. **Mitigation**: the
  ASCII check (`str.isascii()`) only tests code-point range, not character
  class — punctuation/digits/letters within ASCII all still pass; only
  genuinely non-ASCII code points are rejected, so no valid ASCII name is
  newly rejected.
- **Risk**: Some other command or test elsewhere in the codebase may depend
  on the old silent-slugify behavior (e.g. a fixture using an accented name
  expecting a mangled-but-accepted slug). **Mitigation**: grep for non-ASCII
  literals in existing `specify`-adjacent tests before declaring the change
  complete; update any that assumed the old silent behavior.
- **Risk**: Reordering validation ahead of any existing side effect could
  change behavior for an unrelated valid-input path. **Mitigation**: the
  ASCII/empty check is a pure string predicate with no side effects itself —
  moving it earlier only ever *prevents* writes, never *adds* new ones; the
  happy-path regression (T023 step 5) catches any accidental behavior change.

## Review Guidance

- Confirm all three named scenarios (`日本語`, `Ünïcödé`, `auth日本`) reject
  explicitly — none silently truncate or accept.
- Confirm `typer.BadParameter` is gone from `_slugify_feature_input` and the
  rejection routes through `NonAsciiNameError` → the WP01 hook, not a
  command-local try/except.
- Confirm the JSON envelope matches `contracts/error-envelope.md` exactly
  and exit code is 1 (not 2) for this validation failure.
- Confirm the NFR-005 negative assertion (no mission dir/branch/meta.json
  write on reject) is present and passing.
- Confirm the "no name given" and "no usable ASCII characters" messages
  remain distinguishable.
- Confirm no unrelated `feature`→`Mission` terminology sweep leaked into this
  diff beyond what this WP's new strings require.
- Confirm `mypy` and `ruff check`/`ruff format --check` pass with zero new
  suppressions, and `test_no_legacy_terminology.py` is green.

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

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task WP06 --to <status>` to change WP status.

### Optional Phase Subdirectories

For large features, organize prompts under `tasks/` to keep bundles grouped while maintaining lexical ordering.
