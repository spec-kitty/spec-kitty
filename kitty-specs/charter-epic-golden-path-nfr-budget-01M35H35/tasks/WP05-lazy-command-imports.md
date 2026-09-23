---
work_package_id: WP05
title: 'Lever C secondary: lazy command-module imports'
dependencies:
- WP02
requirement_refs:
- FR-003
planning_base_branch: issue-4213-golden-path-nfr-budget
merge_target_branch: issue-4213-golden-path-nfr-budget
branch_strategy: Planning artifacts for this mission were generated on issue-4213-golden-path-nfr-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4213-golden-path-nfr-budget unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-epic-golden-path-nfr-budget-01M35H35
base_commit: 4c99dc103113fcb4ddf5fb55ffb63f169d7ac6a2
created_at: '2026-09-23T11:27:09.838180+00:00'
subtasks:
- T017
- T018
- T019
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/__init__.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/__init__.py
- tests/specify_cli/cli/**
- tests/cli/**
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP05 – Lever C secondary: lazy command-module imports

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Generalize the existing `_is_next_fast_path`/`_is_live_work_hook_fast_path`
argv-sniffing idiom in `register_commands()`
(`src/specify_cli/cli/commands/__init__.py`) into a lazy command-lookup table, so
a single-leaf-command invocation only imports the one module tree its invoked
command actually needs, instead of unconditionally importing all ~40 command
modules on every non-fast-pathed invocation. This is the literal PR #4417-
deferred item FR-003 names.

## Context

Per `plan.md`'s Lever C section, this is the **secondary, complementary** trim —
lever C's primary mechanism is WP04's freshness pre-check, which dominates the
measured cost. This WP is independent of WP04 (different file, no shared
runtime dependency between the two changes) and may run in parallel with it,
though both declare a hard dependency on WP02 (red-first anchor) only. WP01
(baseline capture) has no hard WP-dependency gate on it from this WP or from
WP02/WP03/WP04/WP07 — it measures an isolated worktree at the merge-base and does
not touch this working tree — but the orchestrator should still dispatch it
early/first as a process matter, per `plan.md`'s Baseline method. (WP08, the
mission's closing WP, is the one exception: it does carry a hard dependency on
WP01, because its T027 subtask needs WP01's baseline artifact to exist and be
committed before WP08 can diff against it — see
`tasks/WP08-final-integration-validation.md`.)

`register_commands()` (`src/specify_cli/cli/commands/__init__.py:181-257`
approximately — verify current line numbers) already implements exactly this
pattern for two commands: `_is_next_fast_path` short-circuits to import only
`next_cmd` when argv indicates a `next` invocation, and
`_is_live_work_hook_fast_path` does the same for `live-work hook`. This WP
generalizes that SAME idiom to cover the remaining ~40 command modules via a
lookup table keyed by the invoked subcommand name, rather than inventing a new
pattern.

**Typer contract preservation**: neither this WP nor WP04 may change any
command's `--help` text, argument surface, JSON envelope shape, or exit-code
contract. The lazy-import trim changes *when* a module is imported, never *what*
it registers once imported — the same `app.command()`/`app.add_typer()` calls
must still run, just deferred behind the lazy lookup.

### Subtask T017: Build the lazy command-lookup table

**Purpose**: Replace the ~40 unconditional `from . import <module>` imports
inside `register_commands()`'s eager (non-fast-path) branch with a lookup keyed
by the invoked subcommand name.

**Steps**:
1. Read the full current body of `register_commands()` in
   `src/specify_cli/cli/commands/__init__.py` and enumerate every
   `from . import <module> as <alias>` + registration call
   (`app.command()(...)` / `app.add_typer(...)`) pair currently made
   unconditionally.
2. Build a lookup structure mapping the invoked top-level subcommand name (the
   first non-flag `sys.argv` token, same detection style as
   `_is_next_fast_path`/`_is_live_work_hook_fast_path`) to the specific
   `from . import ...` + registration call needed for that command. Some
   commands may map many-to-one (a single module backing multiple registered
   names) — preserve the existing module-to-command mapping exactly, just defer
   *when* each import/registration executes.
3. Keep the existing `_is_next_fast_path`/`_is_live_work_hook_fast_path` special
   cases as they are (they already return early) — this WP generalizes the
   REMAINING eager branch, not those two already-fast-pathed cases.
4. Handle multi-command invocations correctly (e.g. `--help` at the top level,
   which must enumerate every command's help text, or any invocation whose argv
   does not cleanly resolve to exactly one known leaf command) — these cases
   must still import everything needed to produce correct output; do not break
   `spec-kitty --help` or any command-group listing.
5. Preserve `make_leaf_commands_mission_agnostic(app)` and
   `_apply_short_help_options(app)` calls at the correct point relative to the
   now-lazy registration — these must still run against whatever commands were
   actually registered for the current invocation.

**Files**: `src/specify_cli/cli/commands/__init__.py` (~80-150 line
restructuring inside `register_commands()`; net line count may shrink since the
~40 import statements collapse into a lookup table plus a resolution function).
**Validation**: `spec-kitty --help` still lists every command; a single leaf
command (e.g. `spec-kitty charter generate --help`) still works identically to
before.

### Subtask T018: Add a targeted test proving the import deferral itself

**Purpose**: Prove the lazy-import mechanism actually defers import (not merely
that commands still work, which the existing CLI-contract suite already covers
as a side effect).

**Steps**:
1. Add a new test (in `tests/specify_cli/cli/` — check for an existing
   `register_commands`-focused test file first, or create one if none exists)
   that asserts a specific command module is NOT present in `sys.modules` (or
   an equivalent import-tracking mechanism) until its command name appears in
   the simulated `argv`.
2. Model this test's structure on the existing `#4409`/`#4417` precedent's own
   self-mutation-testable style (`tests/performance/test_cli_startup_budget_4409.py`)
   if a similar assertion pattern exists there for imports — reuse the idiom
   rather than inventing a new testing style.
3. Confirm this test would FAIL against the pre-fix eager-import version (a
   quick sanity check: temporarily revert T017's change locally, confirm the
   new test fails, then restore T017's change) — this is the same
   proof-of-non-vacuousness discipline the mission applies elsewhere, even
   though this specific test is not one of Ruling 6's named staleness tests.

**Files**: `tests/specify_cli/cli/test_lazy_command_imports.py` (new, or an
existing file extended — confirm via search first), ~40-80 lines.
**Validation**: the test passes against the real T017 implementation and was
confirmed to fail against the pre-fix eager-import behavior.

### Subtask T019: Run the full CLI-contract test suite

**Purpose**: Confirm no command's registration, help text, or behavior regressed
as a side effect of deferring its import.

**Steps**:
1. Run:
   ```bash
   .venv/bin/python -m pytest tests/specify_cli/cli -q
   .venv/bin/python -m pytest tests/cli -q
   ```
2. Pay particular attention to any test that invokes `spec-kitty --help` or
   enumerates the full command tree — these are the cases most likely to
   surface an incomplete lazy-lookup mapping.
3. Cross-check against WP04's blast radius: since both WPs touch the same
   overall CLI startup path, confirm there is no unexpected interaction (run
   the golden path test once more here too — it is still expected RED until
   WP04 also lands, which is fine, but its FAILURE MODE should be the same
   budget-related one, not a new crash from this WP's own change).

**Files**: none further changed (verification only).
**Validation**: `tests/specify_cli/cli` and `tests/cli` are fully green; the
golden path test's failure mode (if still red at this point) is unchanged from
WP02's original red-first evidence, not a new error type.

## Definition of Done

- `register_commands()`'s eager, unconditional `from . import <module>` block
  is replaced by a lazy lookup keyed by the invoked subcommand, generalizing the
  existing `_is_next_fast_path`/`_is_live_work_hook_fast_path` idiom.
- `spec-kitty --help` and every individual leaf command still work identically
  (same registered commands, same help text, same JSON envelopes, same exit
  codes).
- A new, proven-non-vacuous test confirms a command module is not imported
  until its command name appears in argv.
- `tests/specify_cli/cli` and `tests/cli` are fully green.
- Per-subtask completion is recorded via
  `spec-kitty agent tasks mark-status <Txxx> --status done` for T017–T019.

## Risks

- **Incomplete lookup table**: missing even one of the ~40 modules from the
  lazy-lookup mapping would silently break that one command. Enumerate the
  FULL current list from the real source file (T017 step 1) rather than
  working from `plan.md`'s illustrative examples alone.
- **`--help`/multi-command edge cases**: the top-level `--help` invocation and
  any command-group listing must still see every registered command — a naive
  "only import the one matched command" implementation could break these.
  T017 step 4 exists specifically to guard this.
- **Interaction with WP04**: both WPs touch CLI startup cost; keep this WP's
  diff strictly confined to `register_commands()`'s import/registration
  mechanics — do not touch `agent_commands.py` or `main_callback()`, which are
  WP04's exclusive `owned_files`.

## Reviewer Guidance

Confirm the full ~40-module list from the actual source is accounted for in the
lazy lookup (not just the illustrative subset in this prompt), confirm
`spec-kitty --help` output is byte-identical before/after, and confirm the new
import-deferral test was genuinely observed failing against the pre-fix
behavior before this WP's fix made it pass.

Implementation command: `spec-kitty agent action implement WP05 --agent claude`
