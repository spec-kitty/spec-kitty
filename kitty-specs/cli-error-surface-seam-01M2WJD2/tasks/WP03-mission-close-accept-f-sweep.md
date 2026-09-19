---
work_package_id: WP03
title: mission close + accept invalid --mission guard + -f sweep (#4724)
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-006
planning_base_branch: fix/cli-error-surface-seam
merge_target_branch: fix/cli-error-surface-seam
branch_strategy: Planning artifacts for this mission were generated on fix/cli-error-surface-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-error-surface-seam unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
phase: Phase 2 - Adoption
history:
- at: '2026-09-19T10:45:02Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/mission_type.py
create_intent:
- tests/specify_cli/cli/commands/test_mission_close_guard.py
- tests/specify_cli/cli/commands/test_accept_guard.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/cli/commands/mission_type.py
- src/specify_cli/cli/commands/accept.py
- src/specify_cli/cli/commands/agent/status.py
- tests/specify_cli/cli/commands/test_mission_close_guard.py
- tests/specify_cli/cli/commands/test_accept_guard.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – `mission close` + `accept` invalid `--mission` guard + `-f` sweep (#4724)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## 🔴 BINDING SQUAD AMENDMENTS (post-tasks fold — read before implementing)

These override any conflicting guidance below.

1. **`accept`'s crash site is `accept.py:206` — a direct `assert_safe_path_segment(mission_slug)`** (imported at `accept.py:28`), NOT `resolve_owned_mission`. It is a bare call with no surrounding try/except, so once `UnsafePathSegmentError` is a `GuardedReadError` subclass (WP01), it propagates to the global hook → clean exit 1. T011: confirm `accept.py:206` reaches the hook; do not add a local handler.
2. **`mission close`'s resolver call is `close_cmd` (~`mission_type.py:571`)** — same pattern: let the (now-subclassed) `UnsafePathSegmentError` propagate to the hook.
3. **`-f` sweep — exactly 4 sites, all confirmed `-f`=`--mission`**: `mission_type.py:139`, `mission_type.py:506`, `agent/status.py:850`, `agent/status.py:1052`. Do NOT touch the legitimate `-f`/`--force` at `auth.py:50`, `charter/sync.py:75`, `charter/generate.py:268`.
4. **Depends on WP01** (frontmatter corrected). Branch topology `coord`, base `fix/cli-error-surface-seam` (per `lanes.json`) — ignore any "single branch" prose.

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Two related defects under #4724:

1. `spec-kitty mission close --mission '<unsafe value>'` and `spec-kitty accept
   --mission '<unsafe value>'` both crash today with an `UnsafePathSegmentError`
   traceback instead of a clean typed error. `accept` was **confirmed crashing
   live on 2026-09-19** (exit 1, raw traceback) — it is not a documentation
   exemplar, it is a real, currently-broken command.
2. `mission close`'s `--mission` option carries a `-f` short alias that reads as
   "force" and collides with the destructive `--discard` path:
   `mission close -f --discard` binds `--discard`'s value onto `-f`/`--mission`
   instead of behaving as expected, and the resulting bad `--mission` value then
   crashes via defect (1). The same `-f`=`--mission` alias exists on 3 other sites
   beyond `mission close` (`mission_type.py:139`, `agent/status.py:850`,
   `agent/status.py:1052`) and must be swept as one campsite class (FR-006), not
   fixed only at the one reported site.

**Done when**:
- `mission close --mission 'bad seg!'` → exit 1, clean "not a safe path segment" /
  "mission not found" error via the hook, zero traceback frames.
- `accept --mission 'bad seg!'` → the same, exit 1, zero traceback frames.
- `mission close -f --discard` no longer crashes from the `-f`/`--discard`
  collision (the `-f` alias is gone, so `-f` is no longer interpretable as
  `--mission` at all).
- `mission close --help`, `mission_type.py:139`'s command's `--help`, and both
  `agent/status.py` commands' `--help` show **no** `-f` alias for `--mission`.
- Neither command's own bespoke crash-handling (if any) survives — both let
  `UnsafePathSegmentError` (now a `GuardedReadError` subclass per WP01) propagate
  to the global hook.

## Context & Constraints

**Depends on WP01.** `UnsafePathSegmentError` must already be re-parented as a
`GuardedReadError` subclass and the global hook must already be registered before
you start — you are a pure consumer here, adding no new error type.

- Follow `quickstart.md`'s pattern: the command does not try/except for
  presentation; letting the (now-subclassed) domain error propagate to the global
  hook is the fix. Do not add a second, command-local emitter.
- **`mission close`**: `close_cmd` (`src/specify_cli/cli/commands/
  mission_type.py:503`) calls `resolve_feature_dir_for_mission(repo_root,
  mission_slug)` at `~mission_type.py:571`; that resolver is what raises
  `UnsafePathSegmentError` on an unsafe value via
  `assert_safe_path_segment`/`UnsafePathSegmentError` in
  `src/specify_cli/core/paths.py:42`. Remove any local
  try/except around that call in `close_cmd` that currently converts it into
  something other than a clean propagate-to-hook path (check for one — if
  `close_cmd` has no such try/except today, the "removal" is simply confirming
  none needs adding, and the fix is entirely upstream in the hook from WP01).
- **`accept`**: verify live where `accept.py` resolves its `--mission` value (it
  imports from `specify_cli.core.owned_mission` — `resolve_owned_mission` and
  related helpers per the file's imports) and confirm the same
  `UnsafePathSegmentError` (or an equivalent unsafe-segment path) is what
  currently crashes it. `accept.py` is explicitly *not* an exemplar in
  `spec.md`'s Assumptions — it is a second, independently-confirmed crash site
  the single hook fixes for free; still add its own dedicated regression test
  (do not assume WP01's hook fixing it structurally means it needs no test here).
- **`-f` sweep — the 4 sites** (verified against the live source, all currently
  `typer.Option("--mission", "-f", ...)`):
  - `src/specify_cli/cli/commands/mission_type.py:139`
  - `src/specify_cli/cli/commands/mission_type.py:506` (`close_cmd`)
  - `src/specify_cli/cli/commands/agent/status.py:850`
  - `src/specify_cli/cli/commands/agent/status.py:1052`
  Remove `"-f"` from all four `typer.Option(...)` calls, leaving `--mission` as
  the only spelling. Do not introduce a replacement short alias unless the
  existing option definition already documents one as intentional elsewhere in
  the same file — if in doubt, remove without replacing (FR-006 says "removed,"
  not "replaced").
- Charter constraints: complexity ≤ 15, ruff + mypy clean with zero new
  suppressions, ≥ 90% new-code coverage, `--mission` terminology only (this WP is
  itself part of enforcing that canon — do not reintroduce `-f` or `--feature`
  anywhere).
- Cite decision D4 (`research.md`): handled domain errors on these two commands
  go to exit **1** via the hook — this is a **deliberate exit-code decision**, not
  an omission; do not "fix" it to exit 2, and do not touch `next`'s already-clean
  exit 2 (out of scope, called out as a future consistency follow-up in the PR,
  not folded into this WP).

## Branch Strategy

- **Strategy**: Single branch — all WPs land directly on the mission branch.
- **Planning base branch**: `fix/cli-error-surface-seam`
- **Merge target branch**: `fix/cli-error-surface-seam` (a PR later targets `main`)

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T010 – Red-first: invalid `--mission` crashes both commands; `-f --discard` footgun

- **Purpose**: pin both defects with issue-referenced regressions BEFORE the fix
  (C-003).
- **Steps**: In `tests/specify_cli/cli/commands/test_mission_close_guard.py`,
  write an `@pytest.mark.regression` test that runs the real `mission close
  --mission 'bad seg!'` CLI command (via the CLI test runner) against a scratch
  repo and asserts it currently raises/crashes with an `UnsafePathSegmentError`
  traceback (RED on the base — confirm before writing the fix). Also add a test
  for the `mission close -f --discard` footgun: confirm that today `-f` binds to
  `--mission` and the resulting malformed invocation crashes (rather than behaving
  as an operator would expect). In `tests/specify_cli/cli/commands/
  test_accept_guard.py`, write the equivalent red-first regression for `accept
  --mission 'bad seg!'` — reproduce the live 2026-09-19 crash exactly (exit 1, raw
  traceback) before fixing it. Reference #4724 in both test files.
- **Files**: `tests/specify_cli/cli/commands/test_mission_close_guard.py` (new),
  `tests/specify_cli/cli/commands/test_accept_guard.py` (new).
- **Parallel?**: Yes — independent of WP02, WP04–WP07 (distinct owned files).
- **Notes**: Use a scratch/temp project fixture, not a real mission in this repo's
  own `kitty-specs/` — never invoke `mission close`/`accept` against this
  repository's own live missions from a test.

### Subtask T011 – Route both commands through the hook

- **Purpose**: FR-005 — close the crash by letting the (now-subclassed) domain
  error reach the global hook; remove any local duplicate handling.
- **Steps**: In `close_cmd` (`mission_type.py`), confirm the call to
  `resolve_feature_dir_for_mission(repo_root, mission_slug)` at `~:571` has no
  local try/except that currently converts `UnsafePathSegmentError` into a
  different (non-hook) presentation — if one exists, remove it so the error
  propagates naturally to the WP01 global hook. In `accept.py`, do the same for
  whatever resolver call currently raises the unsafe-segment error on a bad
  `--mission` value — trace it from the live crash (reproduce it locally first:
  `spec-kitty accept --mission 'bad seg!'` in a scratch project) to find the exact
  call site, then remove/avoid any local handling that isn't the hook.
- **Files**: `src/specify_cli/cli/commands/mission_type.py`,
  `src/specify_cli/cli/commands/accept.py`.
- **Parallel?**: Yes.
- **Notes**: If neither command has any local try/except today (the crash is
  simply an unhandled propagation), this subtask may require zero production
  code changes in one or both files — the fix is entirely the WP01 hook now
  being registered. Confirm and document this in your Activity Log rather than
  adding a no-op try/except just to have "done something."

### Subtask T012 – Remove the `-f` short alias from `--mission` at all 4 sites

- **Purpose**: FR-006 — the UX footgun sweep, not limited to `mission close`.
- **Steps**: Edit each of the 4 `typer.Option("--mission", "-f", ...)` call sites
  to drop `"-f"`, leaving `typer.Option("--mission", ...)`:
  `mission_type.py:139`, `mission_type.py:506` (`close_cmd`),
  `agent/status.py:850`, `agent/status.py:1052`. Grep once more after editing
  (`grep -n '"-f"' src/specify_cli/cli/commands/mission_type.py
  src/specify_cli/cli/commands/agent/status.py`) to confirm no fifth site was
  missed and that removing `-f` didn't leave a dangling reference elsewhere (e.g.
  a docstring or help string mentioning `-f`).
- **Files**: `src/specify_cli/cli/commands/mission_type.py`,
  `src/specify_cli/cli/commands/agent/status.py`.
- **Parallel?**: Yes.
- **Notes**: This is a pure UX/flag removal — it does not change `--mission`'s
  long-form behavior at all, only removes the short alias. Keep the diff minimal
  (charter locality/smallest-diff).

### Subtask T013 – Green: exit 1 both commands; `--help` shows no `-f`

- **Purpose**: prove both fixes and lock the UX contract.
- **Steps**: Flip T010's regressions to assert the new behavior: `mission close
  --mission 'bad seg!'` and `accept --mission 'bad seg!'` both exit 1 with a clean
  actionable message and zero traceback frames. Add an assertion that `mission
  close --help` output contains no `-f` token associated with `--mission` (parse
  the help text or use Typer's introspection to confirm the option has no short
  name). Add the equivalent `--help` assertion for the other 3 sites'
  commands. Re-verify `mission close -f --discard` no longer silently
  misbinds — since `-f` is removed entirely, this should now surface as either a
  normal "no such option: -f" Typer usage error (exit 2, unchanged per D4) or a
  clean handling of `--discard` alone; assert whichever is correct given the
  actual command signature after the option removal.
- **Files**: `tests/specify_cli/cli/commands/test_mission_close_guard.py`,
  `tests/specify_cli/cli/commands/test_accept_guard.py`.
- **Parallel?**: Yes.
- **Notes**: Also re-run `tests/specify_cli/test_error_backcompat.py` (WP01) to
  confirm this WP's consumption of `UnsafePathSegmentError` didn't require any
  further subclassing change.

## Test Strategy

- `tests/specify_cli/cli/commands/test_mission_close_guard.py` and
  `tests/specify_cli/cli/commands/test_accept_guard.py` — the full red-then-green
  suites from T010/T013, run through the real Typer CLI entry points against
  scratch project fixtures.
- Run `make test-fast` plus targeted existing tests for
  `mission_type.py`/`accept.py`/`agent/status.py` (mirror the source tree or
  `grep -rl "close_cmd\|resolve_feature_dir_for_mission" tests/ --include="*.py"`)
  to confirm nothing pre-existing regressed from the `-f` removal.
- Typecheck the three owned source files with the project's configured mypy
  invocation.
- `ruff check .` and `ruff format --check .` (whole-repo) before handing off.

## Risks & Mitigations

- **`-f` removal breaking an existing test or doc that asserts `-f` works**: grep
  `tests/` and `docs/` for `-f` in the context of `--mission`/`mission close`
  before finalizing; update any stale reference (docs are out of this WP's
  `owned_files`, so file a note rather than editing docs outside scope if you find
  one).
- **`accept.py`'s crash site turning out to be a different error type** than
  `UnsafePathSegmentError` on closer inspection: reproduce the live crash first
  (T010) and read the actual traceback before assuming the error type — do not
  guess from the plan's exemplar list alone.
- **Over-broadening the exit-code fix**: do not touch `next`'s exit 2 behavior —
  D4 explicitly scopes this WP to the two crashing commands only.

## Review Guidance

- Reproduce `accept --mission 'bad seg!'` on the pre-fix tree (or trust the
  Activity Log's documented red run) to confirm this was a genuine live crash,
  not a hypothetical.
- Confirm `mission close --help` and the 3 sibling commands' `--help` show no
  `-f` for `--mission`.
- Confirm neither command's fix introduces a second, hook-bypassing presentation
  path.
- Confirm exit code 1 (not 2) for both handled domain errors, per D4.
- If typed sources changed, confirm the implementer ran the configured mypy check
  in addition to pytest and that mypy diagnostics passed.

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

**Example (correct chronological order)**:

```
- 2026-01-12T10:00:00Z – system – Prompt created
- 2026-01-12T10:30:00Z – claude – Started implementation
- 2026-01-12T11:00:00Z – codex – Implementation complete, ready for review
- 2026-01-12T11:30:00Z – claude – Review passed, all tests passing  ← LATEST (at bottom)
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

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

### Optional Phase Subdirectories

For large features, organize prompts under `tasks/` to keep bundles grouped while maintaining lexical ordering.
