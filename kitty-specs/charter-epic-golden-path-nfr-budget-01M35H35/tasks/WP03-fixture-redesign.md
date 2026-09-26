---
work_package_id: WP03
title: 'Lever A: fresh_e2e_project fixture redesign'
dependencies:
- WP02
requirement_refs:
- FR-002
- C-006
- C-003
- SC-005
planning_base_branch: issue-4213-golden-path-nfr-budget
merge_target_branch: issue-4213-golden-path-nfr-budget
branch_strategy: Planning artifacts for this mission were generated on issue-4213-golden-path-nfr-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4213-golden-path-nfr-budget unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-epic-golden-path-nfr-budget-01M35H35
base_commit: 4c99dc103113fcb4ddf5fb55ffb63f169d7ac6a2
created_at: '2026-09-23T11:27:53.156339+00:00'
subtasks:
- T009
- T010
- T011
history: []
agent_profile: python-pedro
authoritative_surface: tests/e2e/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/e2e/conftest.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP03 – Lever A: fresh_e2e_project fixture redesign

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Redesign `fresh_e2e_project` (`tests/e2e/conftest.py`) per `data-model.md`'s exact
before/after shape: replace the two `git config` subprocess calls with a direct
write into the freshly-created project's `.git/config`, and add the two explicit
C-006 precondition assertions immediately before the `spec-kitty init` call. Do
NOT touch the `spec-kitty init` call itself (C-003 — it stays a real subprocess
invocation of the source-tree CLI, unchanged in shape/args).

## Context

This is lever A (FR-002) from `plan.md`. Its dominant expected savings actually
come "for free" from WP04's lever-C fix (the fixture's own `spec-kitty init` call
goes through the same `main_callback()` → `ensure_global_agent_commands()` path
every other golden-path call does) — this WP's own scope is narrower: the
secondary, fixture-local git-config batching change, plus making C-006's
precondition an explicit, executable assertion instead of an implicit ordering
guarantee.

**Read `data-model.md`'s "`fresh_e2e_project` fixture — before/after shape"
section before writing any code** — it gives the exact target shape this WP must
produce, including the precise comment text expected around the `spec-kitty init`
call.

**C-003 binds this fixture's `spec-kitty init` call too**, not only the golden
path's 12 test-body invocations (see spec.md C-003's explicit "This applies the
same lever-B rejection to every CLI invocation the golden path makes, fixture-
setup and test-body alike" clause). Do not convert this call to an in-process/
library call under any circumstance.

**This WP is one of SC-005's contributing owners (added per post-tasks
analysis, finding B2).** SC-005 ("all 12 subprocess CLI invocations remain real
subprocess calls... verifies C-003 was honored, not just declared") spans every
CLI call the golden path makes, including this fixture's own `spec-kitty init`
call — this WP's own Definition-of-Done bullet ("The `spec-kitty init` call
itself is byte-for-byte unchanged in shape/args") is this WP's concrete
contribution to that mission-wide guarantee. The mechanical, whole-golden-path
count/assertion that verifies SC-005 across ALL 12 calls (not just this
fixture's one) lives in WP08 (see `tasks/WP08-final-integration-validation.md`,
which WP08 also cites in its own `requirement_refs` alongside this WP) — this WP
does not itself need to add a new count assertion, since its own scope only
ever touches one of the twelve/thirteen call sites and that one call's shape is
already verified unchanged by this WP's existing Definition of Done.

### Subtask T009: Replace the two `git config` subprocess calls with a direct `.git/config` write

**Purpose**: Cut 2 of the fixture's 5 subprocess spawns to 0, per FR-002(b) /
`data-model.md`'s target shape.

**Steps**:
1. In `tests/e2e/conftest.py`'s `fresh_e2e_project` fixture, after the
   `git init -b main` subprocess call and before the `spec-kitty init` call,
   remove the two `subprocess.run(["git", "config", "user.email", ...])` and
   `subprocess.run(["git", "config", "user.name", ...])` calls.
2. Replace them with a direct append into `project / ".git" / "config"`, adding
   (or extending, if a `[user]` section-like block does not already exist from
   `git init`) a `[user]` section with `email = fresh-e2e@example.com` and
   `name = Fresh E2E Test` — matching the exact values the two removed
   `git config` calls previously set. Use plain text file writing (INI-shaped
   append); do not invent a new config-writing dependency.
3. Confirm this produces the SAME observable git config state as before: run
   `git -C <project> config user.email` / `git -C <project> config user.name`
   after the fixture runs (in a scratch test, or via the golden path test
   itself once it is green) and confirm both return the expected values.

**Files**: `tests/e2e/conftest.py` (~10-15 line net change inside
`fresh_e2e_project`).
**Validation**: `git config user.email`/`user.name` resolve correctly against
the fixture's project directory after only the direct-write path (no `git
config` subprocess call remains for these two values); no commit is made by this
write (it only edits `.git/config`, a plain-text file, not a git object).

### Subtask T010: Add explicit, executable C-006 precondition assertions

**Purpose**: Turn C-006's currently-implicit "init always sees a zero-commit,
no-`.kittify` repo" guarantee into a real, executable assertion that would fail
loudly if a future edit to this fixture's ordering broke it.

**Steps**:
1. Immediately before the `spec-kitty init` call (`run_cli_subprocess(project,
   "init", ...)`), add two assertions:
   ```python
   assert not (project / ".kittify").exists(), "C-006: no .kittify content before init"
   ```
   and a zero-commit check — `data-model.md` gives two equivalent forms; pick
   one, per plan.md's own note that "the exact assertion form is an
   implementation-time choice, but it must be a real, executable assertion
   inside the fixture, not a comment": either
   ```python
   result = subprocess.run(
       ["git", "rev-list", "--count", "HEAD"],
       cwd=project, capture_output=True, text=True,
   )
   assert result.returncode != 0, "C-006: zero-commit repo before init"
   ```
   or
   ```python
   assert not (project / ".git" / "refs" / "heads" / "main").exists(), (
       "C-006: zero-commit repo before init"
   )
   ```
2. Do not change the ORDER of operations: `git init` (now the fixture's only
   remaining `git`-subprocess call before `init`) still runs first, the direct
   `.git/config` write (T009) happens between `git init` and `spec-kitty init`,
   and neither creates a commit or `.kittify` content.
3. Confirm the existing precondition assertion at
   `tests/e2e/test_charter_epic_golden_path.py:485`
   (`assert not doctrine_path.exists()`) still passes unmodified — this WP does
   not touch that test file (WP02 owns it and has already landed its own
   narrow change).

**Files**: `tests/e2e/conftest.py` (same fixture, ~4-6 new lines).
**Validation**: both new assertions execute (not merely documented) immediately
before the `spec-kitty init` call; a deliberate local experiment (e.g.
temporarily reordering the fixture to commit before `init`, then reverting)
should make one of these assertions fail — confirm this once, then revert, as
proof the assertions are load-bearing, not vacuous.

### Subtask T011: Verify fixture isolation and run the affected test surface

**Purpose**: Confirm this WP's changes did not leak new shared state into any
other `tests/e2e/` fixture or test, and that the fixture's own contract still
holds.

**Steps**:
1. Run the fixture's single consumer:
   ```bash
   .venv/bin/python -m pytest tests/e2e/test_charter_epic_golden_path.py -q
   ```
   Expect this to still be RED at this point (WP04/WP05 have not landed yet) —
   that is expected; what matters here is that it fails for the SAME budget
   reason as WP02's red-first evidence, not a NEW failure mode introduced by
   this WP's own changes (e.g. a broken git-config write or a tripped C-006
   assertion would be a new, WP03-introduced failure — distinguish these).
2. Run the broader `tests/e2e/` directory to confirm no other test in that
   directory gained or lost state as a result of this fixture change (per
   Acceptance Scenario 4):
   ```bash
   .venv/bin/python -m pytest tests/e2e -q
   ```
3. Confirm `fresh_e2e_project` remains `tmp_path`-scoped with no new
   session-scoped fixture, template, or shared cache introduced by this change.

**Files**: none further changed (verification only).
**Validation**: the only observed difference in `tests/e2e`'s overall pass/fail
pattern relative to WP01's baseline is the (expected, already-recorded) golden
path failure — no other test in the directory newly fails.

## Definition of Done

- The two `git config` subprocess calls are replaced by a direct `.git/config`
  write producing the identical observable git config state.
- Two explicit, executable C-006 assertions exist immediately before the
  `spec-kitty init` call and were proven load-bearing (not vacuous) per T010.
- The `spec-kitty init` call itself is byte-for-byte unchanged in shape/args
  (C-003 preserved).
- `tests/e2e` as a whole shows no NEW failure beyond the already-expected,
  already-recorded golden-path red from WP02.
- Per-subtask completion is recorded via
  `spec-kitty agent tasks mark-status <Txxx> --status done` for T009–T011.

## Risks

- **Silently weakening C-003 by "cleaning up" the `spec-kitty init` call**: do
  not touch that call's args/shape under any framing — only the two `git config`
  calls and the new assertions are in scope.
- **INI-write correctness**: a malformed `.git/config` write (wrong section
  header, wrong key syntax) could silently produce a *different* git identity
  than before, which would only surface later as a confusing commit-authorship
  bug. T009's verification step exists specifically to catch this before it
  ships.
- **New fixture-sharing mechanism temptation**: do not introduce a session-
  scoped template or clone source "while you're in here" — `data-model.md`
  explicitly requires this WP change nothing about *what* is shared, only *how
  expensively* the fixture builds its own project.

## Reviewer Guidance

Confirm the diff matches `data-model.md`'s target shape closely (comment text
included), confirm both C-006 assertions are real, executable code (not
comments), confirm the `spec-kitty init` call itself has zero diff, and confirm
the reviewer independently ran `tests/e2e -q` and saw no failure beyond the
already-known golden-path red.

Implementation command: `spec-kitty agent action implement WP03 --agent claude`
