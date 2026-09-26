---
work_package_id: WP04
title: 'Lever C primary: agent-commands freshness pre-check'
dependencies:
- WP02
requirement_refs:
- FR-003
planning_base_branch: issue-4213-golden-path-nfr-budget
merge_target_branch: issue-4213-golden-path-nfr-budget
branch_strategy: Planning artifacts for this mission were generated on issue-4213-golden-path-nfr-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4213-golden-path-nfr-budget unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-epic-golden-path-nfr-budget-01M35H35
base_commit: 4c99dc103113fcb4ddf5fb55ffb63f169d7ac6a2
created_at: '2026-09-23T11:48:57.245477+00:00'
subtasks:
- T012
- T013
- T014
- T015
- T016
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/runtime/agent_commands.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/runtime/agent_commands.py
- src/specify_cli/__init__.py
- pyproject.toml
- docs/changelog/CHANGELOG.md
- tests/specify_cli/runtime/**
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP04 – Lever C primary: agent-commands freshness pre-check

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ CHOKEPOINT

`src/specify_cli/runtime/agent_commands.py` is the global agent-command install
machinery every spec-kitty workspace uses — including the very orchestrator and
worker agents running this mission. Any subtle behavior change here can degrade
`spec-kitty` invocations for every concurrently-running mission on this machine.
Read `data-model.md`'s "Agent-commands freshness stamp" section in full before
writing any code, and re-read `plan.md`'s "Reflexivity" section, which analyzes
exactly this risk and explains why the chosen mechanism is safe.

## Objective

Add a freshness pre-check to `assess_global_agent_commands()`
(`src/specify_cli/runtime/agent_commands.py`) that skips the redundant,
currently-unconditional re-render of all 13 agents' command templates when
nothing has changed — implementing the exact four-condition read/write contract
`data-model.md` specifies — and prove it red-first: T012's original three
named staleness tests (a/b/c), mandated by operator Ruling 6's binding
condition, plus T015's additional `agent_keys` staleness test, sourced from
`plan.md`'s Diff-cover >=90% completeness requirement (not itself a Ruling-6
item) — four tests total, each proven to fail against a naive stub before the
real fix makes them pass.

## Context

Per operator Ruling 6 (`reviews/plan.ruling.md`), this is lever C's **primary**
mechanism (the Typer command-surface trim in WP05 is secondary/complementary).
Profiling in `plan.md`'s Research found this one call chain
(`ensure_global_agent_commands` → `_render_agent_commands` → `render_command_template`
→ `render_template_text` → `ruamel.yaml` `load`) consumes ~55-65% of a bare
`spec-kitty init` invocation's wall-clock cost, on a warm cache, with **zero**
short-circuit today.

**Binding condition (Ruling 6, non-negotiable)**: the freshness check must be
proven red-first not to cause silent staleness. Write and run each staleness
test FIRST against a deliberately naive/broken stub of the check — confirm it
fails there — before writing the real implementation that makes it pass. A test
that was never observed to fail is not proof of anything; do not skip this step
even under time pressure.

**SK-243 — read before touching `AssetPreparation` construction.** Per
`data-model.md`'s SK-243 interaction analysis and `SPEC-KITTY-LEDGER.md` § SK-243,
the stamp read AND the `_all_global_agent_commands_healthy()` destination-health
check MUST both run entirely BEFORE any `AssetPreparation("slash_commands", ...)`
object is constructed. This is what makes the fast (stamp-match) path
structurally immune to SK-243's spurious `RuntimeError: Global asset input
changed` failure mode — not luck, not timing, but the literal ordering of the
check relative to `AssetPreparation` construction. Get this ordering wrong and
you reintroduce SK-243 exposure on the very path this WP is supposed to make
faster and safer.

### Subtask T012: Write the three red-first staleness tests against a naive stub

**Purpose**: Satisfy Ruling 6's binding condition — prove each test is
non-vacuous BEFORE the real fix exists.

**Steps**:
1. In `tests/specify_cli/runtime/` (extend `test_agent_commands.py` or
   `test_agent_commands_routing.py` — check which already covers
   `assess_global_agent_commands`/`ensure_global_agent_commands` via
   `grep -rl assess_global_agent_commands tests/`), write three tests matching
   `plan.md`'s "Red-first staleness tests for the freshness check" subsection
   exactly:
   - **(a) Template-change staleness test.** Mutate a command template's source
     content under `_get_command_templates_dir()`'s tree (or the
     `template_source_signature` input) without changing `cli_version` or
     `agent_keys`, then call `assess_global_agent_commands()`/
     `ensure_global_agent_commands()` again. It must detect the change and
     re-render.
   - **(b) Version-change staleness test.** Monkeypatch `_get_cli_version()`/
     `__version__` to a different value than the stored stamp, with no template
     content change, then call the same entry point again. It must detect the
     version mismatch and re-render.
   - **(c) Destination-health staleness test.** With a stamp that matches on all
     three source-side fields, delete/corrupt/hand-edit one rendered destination
     command file, then call the same entry point again. It must detect the
     destination-health miss and re-render/repair — this is exactly
     PLAN-ARCH-001's named failure mode (a stamp-only short-circuit that ignores
     destination drift).
2. Before implementing the real fix (T013), temporarily stub a NAIVE freshness
   check (one that always short-circuits, or whose comparison omits the
   relevant field per each test's own "what it catches" description in
   `plan.md`) and run all three tests against it. **Confirm each one fails** —
   record this observation (a screenshot-equivalent: paste the actual red
   pytest output into your WP notes/commit message). This is the proof-of-
   non-vacuousness Ruling 6 requires.
3. Remove the naive stub once each test's red state is confirmed and proceed to
   T013's real implementation.

**Files**: `tests/specify_cli/runtime/test_agent_commands.py` (or the correct
existing test module — confirm via grep first), new tests added, ~80-150 lines
total for the three tests plus fixtures/helpers.
**Validation**: each of the three tests is observed RED against the naive stub
before any real implementation exists; this observation is recorded, not just
asserted.

### Subtask T013: Implement the four-condition freshness stamp read/write contract

**Purpose**: Make the three tests from T012 pass via the real mechanism
`data-model.md` specifies.

**Steps**:
1. In `assess_global_agent_commands()` (`src/specify_cli/runtime/agent_commands.py`),
   before any `_render_agent_commands()` call, add a stamp read comparing the
   CURRENT `(cli_version, template_source_signature, agent_keys)` triple against
   a stored stamp under `home / "cache"` (the same cache root
   `AssetPreparation` already uses — see `asset_preparation.py:165-178`).
2. Implement the three dispositions exactly as `data-model.md` specifies:
   - **Match** (all three source-side fields equal AND
     `_all_global_agent_commands_healthy()` — `agent_commands.py:296-305`,
     currently zero-caller — reports every configured destination healthy):
     short-circuit. Return the prior "healthy" assessment WITHOUT calling
     `_render_agent_commands` and WITHOUT constructing an
     `AssetPreparation("slash_commands", ...)` object at all. **This ordering is
     the SK-243 immunity property — get it right.**
   - **Miss, stamp-side** (stamp absent, or any of the three source-side fields
     differs): fall through to today's render-then-diff behavior, then write a
     fresh stamp only after a full, successful render-and-apply cycle completes
     (never speculatively, never on a partial/failed run).
   - **Miss, destination-health-side** (stamp matches but
     `_all_global_agent_commands_healthy()` fails): also falls through to
     render-then-diff and re-stamps — implement this as its own distinct branch
     from the stamp-side miss, since it is reached only through the fourth
     condition.
3. Implement the **Unreadable/malformed** disposition: a narrowly-scoped catch
   around the stamp READ only (parse errors, not render/write errors) that
   treats a corrupt, legacy-shaped, or torn-write stamp identically to absent —
   never let this propagate as an unhandled exception. If you reuse the
   existing `_VERSION_FILENAME` (`agent-commands.lock`) path, note that every
   existing installation's on-disk stamp is GUARANTEED to hit this disposition
   on the very first post-upgrade read (its current content is plain
   version-string bytes, not the new stamp shape) — this is not an edge case,
   it is the first-run case for every real user.
4. Choose the stamp's exact filename/format (reuse `_VERSION_FILENAME` or
   introduce a new file — `data-model.md` leaves this as your implementation
   choice) and document the choice in a short code comment.
5. Reuse or coordinate with `AssetPreparation`'s existing lock-file mechanism
   for the stamp write so two concurrent `spec-kitty` invocations on the same
   machine cannot race a torn stamp write.
6. Re-run the three T012 tests against this real implementation — confirm all
   three now PASS.

**Files**: `src/specify_cli/runtime/agent_commands.py` (~60-120 new lines: the
freshness-check helper(s), the stamp read/write functions, the branch
restructuring inside `assess_global_agent_commands()`).
**Validation**: all three T012 tests pass; the stamp-match path's own code
provably never constructs an `AssetPreparation` object (verify by reading the
code path, not just by the tests passing — the tests prove behavior, this check
proves the *mechanism* that produces the SK-243 immunity).

### Subtask T014: Decide on and handle the `__init__.py` call-site question

**Purpose**: `plan.md` states no `main_callback()` call-site change is required
if the freshness check stays internal to `assess_global_agent_commands()` — but
also permits one, confined to lines ~145-152, "if the plan's implementer finds a
call-site change is cleaner." Resolve this explicitly.

**Steps**:
1. **Prefer keeping the fix entirely internal to `agent_commands.py`** — this
   avoids touching `__init__.py` at all, which is the lower-risk, smaller-diff
   path (per the charter's smallest-viable-diff-first reconciliation order).
2. If, after implementing T013, you find a call-site change to `main_callback()`
   in `src/specify_cli/__init__.py` genuinely necessary or clearly cleaner,
   confine it strictly to the existing block at lines ~145-152 (the
   `ensure_global_agent_commands()` call site, guarded by
   `_is_doctor_skills_invocation`) — do not add new argv-sniffing fast-path
   logic here; the fix belongs inside the callee.
3. **If, and only if, `__init__.py` is touched**: this checkout's CLAUDE.md
   states "Any changes to `__init__.py` require a version bump in
   `pyproject.toml` and a `CHANGELOG.md` entry." In that same commit:
   - Bump the version in `pyproject.toml` (currently `4.0.0rc5`) — choose the
     next appropriate pre-release/patch increment per this repo's existing
     versioning convention (check recent `CHANGELOG.md`/git history for the
     pattern rather than guessing a scheme).
   - Add an entry under the CHANGELOG's existing `## [Unreleased] - 4.0.0rc5`
     section (see `docs/changelog/CHANGELOG.md` for the current format)
     describing the `__init__.py` change.
   - If `__init__.py` is NOT touched, do not bump the version or touch the
     CHANGELOG — those two files remain outside this WP's actual diff even
     though they are listed in `owned_files` as a conditional allowance.
4. **Open-PR overlap check (performed 2026-09-23):**
   `gh pr list --repo spec-kitty/spec-kitty --state open --limit 100 --json
   number,title,files` shows 9 open PRs. Of those, 6 touch
   `docs/changelog/CHANGELOG.md` (#4953, #4950, #4947, #4942, #4938, #4936) and
   2 touch `pyproject.toml` (#4953, #4936) — both files this WP conditionally
   owns, and only if this subtask's `__init__.py` call-site change fires. No
   other open PR touches `agent_commands.py`, `__init__.py`, or any other file
   this WP owns. This is an expected trivial append/version-bump conflict on
   those two files, not a functional clash: whoever lands this WP, if the
   conditional path is taken, should rebase and re-append the CHANGELOG entry
   / re-bump the version rather than force a functional merge on those two
   files. Re-run the `gh pr list` query at landing time — these numbers will
   have shifted.

**Files**: `src/specify_cli/__init__.py` (conditional, ~0-10 lines),
`pyproject.toml` (conditional, 1 line), `docs/changelog/CHANGELOG.md`
(conditional, a few lines) — all three touched ONLY if the call-site change is
made; otherwise none of the three change.
**Validation**: if `__init__.py`'s diff is non-empty, `pyproject.toml`'s version
line and a matching `CHANGELOG.md` entry are both present in the same commit; if
`__init__.py`'s diff is empty, neither of the other two files changed either.

### Subtask T015: Extend unit test coverage for the four dispositions

**Purpose**: Satisfy `plan.md`'s Diff-cover ≥90% section, which requires each of
the four dispositions (Match / Miss-stamp-side / Miss-destination-health-side /
Unreadable-malformed) to be exercised as its own distinct test, not folded into
a two-branch approximation.

**Steps**:
1. Beyond the three T012 staleness tests (which cover Miss-stamp-side (a, b)
   and Miss-destination-health-side (c)), add or extend targeted unit tests
   for:
   - **Match**: a genuinely fresh, matching stamp with a healthy destination
     short-circuits with zero renders and zero `AssetPreparation` construction.
   - **Unreadable/malformed**: a corrupt/legacy-shaped stamp file degrades
     gracefully to the render-then-diff path and is overwritten with a correctly
     -shaped stamp afterward, without raising.
   - **agent_keys staleness (Miss, stamp-side, the third source-side field)**:
     `plan.md`'s Approach and Diff-cover sections name three source-side stamp
     fields — `cli_version`, `template_source_signature`, and `agent_keys` —
     but T012's (a) and (b) tests only exercise the first two. Add a dedicated
     test: with `cli_version` and `template_source_signature` held constant,
     vary the resolved agent-key set (e.g. add or remove a configured agent),
     then call `assess_global_agent_commands()`/`ensure_global_agent_commands()`
     again. Use the same naive-stub-first red-first structure T012 used for
     (a)/(b): write it against a deliberately naive stamp comparison that omits
     `agent_keys` from the match condition, confirm it fails, then confirm it
     passes against the real four-condition contract. This closes the gap
     where `agent_keys` had no dedicated, non-vacuous coverage of its own.
2. Run `grep -rl assess_global_agent_commands tests/` again to confirm you are
   extending the existing test module(s), not creating a parallel/duplicate one.

**Files**: same test module(s) as T012, extended (~55-100 more lines).
**Validation**: all four dispositions have their own passing test; all three
named source-side stamp fields (`cli_version`/`template_source_signature`/
`agent_keys`) have dedicated, non-vacuous coverage, not just two of them;
running `.venv/bin/python -m pytest tests/specify_cli/runtime -q` is green.

### Subtask T016: Run the targeted blast radius for this WP

**Purpose**: Confirm this chokepoint change does not regress anything using
`assess_global_agent_commands`/`ensure_global_agent_commands` elsewhere.

**Steps**:
1. Run every test file `grep -rl "assess_global_agent_commands\|ensure_global_agent_commands" tests/ --include="*.py"` returns (this WP's dispatch already found: `tests/architectural/test_cli_placeholder_output.py`,
   `tests/runtime/test_check_assets_membership_tolerance.py`,
   `tests/runtime/test_bootstrap_unit.py`, `tests/runtime/test_generic_asset_scope.py`,
   `tests/runtime/test_upgrade_preview_bootstrap.py`,
   `tests/specify_cli/cli/test_no_visible_feature_alias.py`,
   `tests/specify_cli/cli/commands/test_doctor_slash_commands.py`,
   `tests/specify_cli/cli/commands/test_short_help_flag.py`,
   `tests/specify_cli/runtime/test_agent_commands_routing.py`,
   `tests/specify_cli/runtime/test_agent_commands.py` — re-run the grep yourself
   in case it has drifted).
2. Run `make test-fast`'s baseline directories plus `tests/specify_cli/runtime`.
3. Re-run the `cProfile`-based measurement `plan.md`'s Research section used
   (isolated `HOME`, warm global asset cache, `spec-kitty init --ai codex
   --non-interactive`) before/after this WP's diff, and confirm the freshness
   check's short-circuit measurably reduces `ensure_global_agent_commands`'s
   cumulative time on a warm cache — per `plan.md`'s FR-003 red-first row, this
   re-verifies the profiling claim against the actual implementation, not just
   this plan's own scratch measurement.

**Files**: none further changed (verification only).
**Validation**: every test in the grep'd list passes; the re-profiled
measurement shows a real, attributable reduction on a warm cache.

## Definition of Done

- All four staleness tests — T012's Ruling-6-mandated three (a/b/c) plus
  T015's additional `agent_keys` staleness test (sourced from plan.md's
  Diff-cover >=90% requirement, not itself a Ruling-6 item) — were observed
  RED against a naive stub before the real implementation, then observed
  GREEN against the real four-condition contract.
- The stamp-match short-circuit path never constructs an
  `AssetPreparation("slash_commands", ...)` object — verified by reading the
  code, not only by tests passing (this is the SK-243 immunity property).
- All four dispositions (Match / Miss-stamp / Miss-destination-health /
  Unreadable-malformed) have their own passing, distinct test coverage.
- `__init__.py` is either untouched, OR touched with a matching
  `pyproject.toml` version bump and `CHANGELOG.md` entry in the same commit —
  never one without the other two.
- The grep'd blast-radius test list and `tests/specify_cli/runtime` are green.
- A before/after profiling comparison shows a measurable, attributable
  reduction in `ensure_global_agent_commands`'s cost on a warm cache.
- Per-subtask completion is recorded via
  `spec-kitty agent tasks mark-status <Txxx> --status done` for T012–T016.

## Risks

- **Reintroducing SK-243 exposure**: getting the stamp-read-before-
  `AssetPreparation`-construction ordering wrong silently reintroduces the exact
  ledger-tracked failure mode this WP's analysis explicitly rules out. This is
  the single highest-severity risk in this WP; verify the ordering by reading
  the code path, not by assuming the tests would catch it (SK-243 is a
  concurrency race — a single-process unit test will not reliably reproduce it).
- **Malformed-stamp crash regression**: per `data-model.md`'s cited precedent
  (`AssetPreparation.__init__`'s `ValueError` on malformed inventory), an
  un-caught parse error on the stamp read would crash `main_callback()` for
  every `spec-kitty` invocation on the machine until manually fixed — strictly
  worse than today's "always slow" baseline. T013's narrowly-scoped read-only
  catch is the guard; do not widen it to swallow render/write errors too.
  Chokepoint file — treat with matching care.
- **Silent staleness (the whole point of Ruling 6)**: a freshness check that
  short-circuits when it should not is a worse defect than the performance
  problem this mission fixes, because it fails silently. This is why T012 must
  be genuinely red-first, not a plausible-looking test that was never actually
  observed failing.

## Reviewer Guidance

This is the mission's chokepoint WP — give it the most scrutiny. Confirm: (1)
all four staleness tests' (T012's Ruling-6-mandated a/b/c plus T015's
additional `agent_keys` test, sourced from plan.md's Diff-cover requirement,
not Ruling 6) red-before-green history is documented, not just claimed; (2)
the stamp-match path's code has no reachable
`AssetPreparation(...)` construction; (3) the `__init__.py`/`pyproject.toml`/
`CHANGELOG.md` trio is all-or-nothing; (4) the malformed-stamp catch is scoped
to the read only; (5) the profiling re-measurement is real, not inferred from
plan.md's own numbers.

Implementation command: `spec-kitty agent action implement WP04 --agent claude`
