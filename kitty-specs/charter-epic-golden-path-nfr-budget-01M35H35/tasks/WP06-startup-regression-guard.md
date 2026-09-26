---
work_package_id: WP06
title: FR-005 startup regression guard (two-tier)
dependencies:
- WP04
- WP05
requirement_refs:
- FR-005
- NFR-001
- C-002
- SC-002
planning_base_branch: issue-4213-golden-path-nfr-budget
merge_target_branch: issue-4213-golden-path-nfr-budget
branch_strategy: Planning artifacts for this mission were generated on issue-4213-golden-path-nfr-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4213-golden-path-nfr-budget unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-epic-golden-path-nfr-budget-01M35H35
base_commit: 4c99dc103113fcb4ddf5fb55ffb63f169d7ac6a2
created_at: '2026-09-23T14:14:28.146498+00:00'
subtasks:
- T020
- T021
- T022
- T023
history: []
agent_profile: python-pedro
authoritative_surface: tests/performance/
create_intent:
- tests/performance/test_cli_startup_agent_commands_freshness.py
execution_mode: code_change
model: ''
owned_files:
- tests/performance/test_cli_startup_agent_commands_freshness.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP06 – FR-005 startup regression guard (two-tier)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Create a new file, `tests/performance/test_cli_startup_agent_commands_freshness.py`,
implementing FR-005's two-tier regression guard for lever C: a structural,
always-on, deterministic check (fast per-PR tier) that catches a future
reintroduction of the pre-fix eager-render/eager-import pattern, plus a
wall-clock check scoped strictly to the nightly `performance`-marked lane. This
WP depends on BOTH WP04 and WP05 landing first, since its structural checks
assert the real shape of both fixes.

## Context

Model this file directly on the existing `#4409`/`#4417` precedent,
`tests/performance/test_cli_startup_budget_4409.py` — read that file in full
before writing anything here, per the charter's canonical-sources rule (follow
the established pattern, do not invent a new one).

**Do NOT touch `tests/performance/test_cli_startup_budget_4409.py` itself** —
it is read-only precedent for this WP. This is a new file only.

**Explicitly ruled out** (per `plan.md` and Ruling 4): no hard wall-clock
assertion inside `tests/unit/` or any fast per-PR shard. The structural half
must be deterministic and marker-free (or `fast`/`unit`-marked, matching the
existing precedent); the wall-clock half must carry the `performance` marker
and nothing else may assert real elapsed time outside that marker.

**This WP is SC-002's own delivery point and is bound by C-002 (both added per
post-tasks analysis, findings B2/C3).** SC-002 ("a startup-time regression
guard for the lever-C portion exists... a structural check... plus a wall-clock
check, scoped to the `performance`-marked nightly lane only, never asserted as
a hard wall-clock threshold inside a fast unit-test shard") is this WP's entire
objective, delivered by exactly the two-tier structure below — cite SC-002 by
name in this WP's own completion notes as the criterion being satisfied, not
only FR-005. C-002 (no cadence move for `test_charter_epic_golden_path` itself)
bounds this WP indirectly: the wall-clock half's marker discipline (T022/T023)
exists specifically so this NEW guard test never migrates real wall-clock
assertion into the per-PR fast tier the way C-002 forbids for the golden path
test — the same cadence discipline applies here by the same reasoning, even
though C-002's literal text names the golden path test, not this WP's own new
file.

### Subtask T020: Structural check #1 — freshness-check-before-render shape

**Purpose**: Assert `assess_global_agent_commands()` (or whichever function
ends up owning the render call after WP04) contains a freshness-check code path
reachable BEFORE its first call to `_render_agent_commands` — a structural,
non-vacuous shape check, not a source hash.

**Steps**:
1. Mirror `test_jsonschema_stays_out_of_module_scope`'s AST-based approach from
   `tests/performance/test_cli_startup_budget_4409.py` — parse the function body
   of `assess_global_agent_commands()` (via the `ast` module) and assert the
   `_render_agent_commands` call site is reachable only after an early-return
   branch exists earlier in the function body.
2. Write this check to survive cosmetic refactors (renamed local variables,
   reordered unrelated statements) while still FAILING if the early-return
   branch is deleted — prove this by temporarily reverting WP04's fix locally,
   confirming this test fails, then restoring the fix (the same
   self-mutation-testable discipline `#4409` itself uses).

**Files**: `tests/performance/test_cli_startup_agent_commands_freshness.py`
(new, ~40-70 lines for this check).
**Validation**: the test passes against WP04's real implementation and was
confirmed to fail when WP04's early-return branch is temporarily removed.

### Subtask T021: Structural check #2 — lazy-import shape in `register_commands()`

**Purpose**: Directly re-assert WP05's lazy-import shape, mirroring `#4409`'s
own second guard pattern.

**Steps**:
1. Assert `register_commands()` (`src/specify_cli/cli/commands/__init__.py`)
   contains no top-level `from . import <command_module>` statement inside the
   eager (non-fast-path) branch OUTSIDE the lazy-lookup table's own
   module-name-to-import mapping WP05 introduces.
2. Use the same AST-based, structural (not source-hash) approach as T020 — the
   check should assert the SHAPE of the lazy-import mechanism, not the literal
   text.
3. Prove non-vacuousness the same way: temporarily revert WP05's lazy-import
   change locally, confirm this test fails, then restore it.

**Files**: same file as T020, ~40-70 more lines.
**Validation**: the test passes against WP05's real implementation and was
confirmed to fail against the pre-fix eager-import shape.

### Subtask T022: Wall-clock check — nightly `performance`-marked only

**Purpose**: A real subprocess timing test, modeled on
`test_help_stays_inside_its_startup_budget`
(`tests/performance/test_cli_startup_budget_4409.py:133-149` — verify current
line numbers), but timing a REAL leaf-command invocation instead of `--help`.

**Steps**:
1. **Do not time `--help`.** Per `plan.md`'s own finding: click's eager
   `--help` option exits BEFORE `main_callback`'s body runs, so it never pays
   the `ensure_global_agent_commands()` cost this guard exists to catch —
   timing `--help` would make this check vacuous against exactly the
   regression it is supposed to detect.
2. Time a cheap, side-effect-light leaf command instead — e.g. `spec-kitty
   context show --json` or an equivalent low-cost leaf command that still
   passes through `main_callback()`'s full non-fast-pathed path (confirm your
   chosen command is NOT one of the `next`/`live-work hook`/`doctor
   skills`-fast-pathed commands, or it would not exercise the code path either).
3. Mark this test `@pytest.mark.performance` (matching the existing
   `performance`-marker convention this repo already enforces via
   `tests/architectural/test_performance_marker_guard.py`).
4. Set a budget generous enough to absorb CI contention (mirror
   `_HELP_BUDGET_SECONDS`'s stated design intent from the `#4409` precedent —
   read its rationale comment and apply the same reasoning to this new budget
   value) while tight enough to catch a full-render regression.

**Files**: same file, ~40-60 more lines.
**Validation**: the test is correctly `performance`-marked; running
`.venv/bin/python -m pytest tests/performance -q -m "not performance"`
(the mission's own baseline-method command) does NOT collect/run this test;
running it explicitly with `-m performance` does.

### Subtask T023: Confirm marker scoping end-to-end

**Purpose**: Prove the two-tier split is real, not just labeled correctly.

**Steps**:
1. Run:
   ```bash
   .venv/bin/python -m pytest tests/performance -q -m "not performance"
   ```
   Confirm T020's and T021's structural checks RUN and PASS here (they are
   NOT `performance`-marked), and T022's wall-clock check is DESELECTED
   (excluded by the marker filter).
2. Run:
   ```bash
   .venv/bin/python -m pytest tests/performance -q -m "performance"
   ```
   Confirm T022 runs here and T020/T021 are deselected.
3. Confirm via `tests/architectural/test_performance_marker_guard.py`'s own
   assertion (read it) that no `pull_request`-triggered workflow selects
   `-m performance` — this WP's new wall-clock test must not accidentally
   become a per-PR blocker.

**Files**: none further changed (verification only).
**Validation**: both marker-filtered runs above show exactly the expected
split — structural tests in the fast tier, wall-clock test excluded from it
and only running under the explicit `performance` marker.

## Definition of Done

- Two structural checks exist (freshness-check-before-render shape;
  lazy-import shape), both AST-based and both proven to fail against a
  temporarily-reverted version of WP04/WP05's respective fixes.
- One wall-clock check exists, times a real non-fast-pathed leaf command (never
  `--help`), and carries the `performance` marker exclusively.
- `tests/performance -q -m "not performance"` runs the structural checks and
  skips the wall-clock check; `tests/performance -q -m "performance"` does the
  reverse.
- `tests/performance/test_cli_startup_budget_4409.py` is untouched.
- Per-subtask completion is recorded via
  `spec-kitty agent tasks mark-status <Txxx> --status done` for T020–T023.

## Risks

- **Vacuous structural checks**: an AST assertion that always passes (e.g.
  checking for ANY early-return anywhere in the function, not specifically
  gating the render call) would not actually catch a regression. The
  revert-and-confirm-red step in T020/T021 is the guard against this.
- **Timing `--help` by mistake**: would make the wall-clock check silently
  vacuous against the exact regression this WP exists to catch — re-read
  `plan.md`'s explicit warning about this before choosing the timed command.
- **Marker misconfiguration**: an incorrectly marked wall-clock test could
  either leak into the per-PR fast tier (violating Ruling 4/C-002's cadence
  constraints) or never run at all. T023 exists specifically to prove the
  split is real.

## Reviewer Guidance

Confirm both structural checks were genuinely observed failing against a
reverted fix before this WP's own commit (ask for the evidence, do not take
"it should fail" on faith), confirm the wall-clock check times a real leaf
command and not `--help`, and confirm the marker-filtered pytest runs in T023
show the expected split.

Implementation command: `spec-kitty agent action implement WP06 --agent claude`
