---
work_package_id: WP04
title: Integration verification and mission tracer close-out
dependencies:
- WP02
- WP03
requirement_refs:
- FR-001
- C-001
- C-007
planning_base_branch: fix/reconcile-flake-family-4882
merge_target_branch: fix/reconcile-flake-family-4882
branch_strategy: Planning artifacts for this mission were generated on fix/reconcile-flake-family-4882. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/reconcile-flake-family-4882 unless the human explicitly redirects the landing branch.
subtasks:
- T016
- T017
- T018
- T019
history: []
agent_profile: python-pedro
authoritative_surface: kitty-specs/reconcile-flake-family-01M34HR7/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/reconcile-flake-family-01M34HR7/tracer-tooling-friction.md
- kitty-specs/reconcile-flake-family-01M34HR7/tracer-approach.md
- kitty-specs/reconcile-flake-family-01M34HR7/tracer-design-decisions.md
role: implementer
tags: []
tracker_refs: []
---

# WP04: Integration verification and mission tracer close-out

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ Pre-merge verification scope note (state this explicitly, do not silently assume it)

**This mission's own PR cannot exercise its own fix through the real trigger path.** All
three affected workflows (`ci-fleet-verdict.yml`, `ci-aggregate.yml`) fire on `workflow_run`,
which always executes the copy of the workflow file — and every script it references — that
lives on the repository's default branch (`main`) at trigger time, never the triggering PR's
own branch copy (spec.md Decision 2 / C-001). **A green PR for this mission is therefore NOT
evidence that the race is closed.** The only pre-merge verification available is the unit
tests this mission adds (WP01/WP02/WP03) run directly against mocked racy evidence
sequences — which is exactly what this WP's full-suite re-run (T016) confirms. Confirmation
that the real race is closed is a POST-MERGE observation (spec.md SC-004: 20 consecutive
`main`-head CI cycles or 5 calendar days, whichever comes first, zero same-SHA reconcile
flaps across all three job shapes) — it is explicitly NOT a condition this WP or this
mission's PR must satisfy to be considered done.

## Objective

Close out the mission: run the full baseline-plus-new test suite across all three job
shapes (SC-001/SC-002/SC-003) to confirm WP01–WP03 compose correctly, then append the
closing entries to the three mission tracer files. **This WP introduces no new functional
code and carries no test of its own** — charter C-011's per-WP failing-first-commit
requirement does not apply to it (see plan.md's Constitution Check C-011 row and
"Deviations, Blockers, and Judgment Calls for Reviewers" item 6: FR-009's cross-invocation
isolation test — originally WP04's only test content — was moved into WP02's own red-first
commit sequence in a prior plan-review round, specifically so WP04 would carry zero new-code
test obligations and therefore not need a red-first anchor it structurally could not have).

## Context

Depends on BOTH WP02 and WP03 — this WP's full-suite re-run needs all three functional WPs'
code present (WP01 transitively, via WP02/WP03's imports) to be meaningful. Read
`kitty-specs/reconcile-flake-family-01M34HR7/plan.md`'s "Parallel Work Analysis" section and
its "Deviations, Blockers, and Judgment Calls for Reviewers" item 6 in full before starting.
Also re-read spec.md's Success Criteria (SC-001 through SC-004) — this WP is where
SC-001/SC-002/SC-003 are actually confirmed; SC-004 is explicitly out of this WP's (and this
mission's) scope, being a post-merge observation window, not something to attempt here.

`owned_files` for this WP is confined ENTIRELY to
`kitty-specs/reconcile-flake-family-01M34HR7/tracer-*.md` — do not edit any `scripts/ci/**`,
`tests/ci/**`, or `.github/workflows/**` file in this WP even if you notice something you
would like to fix; that would be WP02's or WP03's scope, and this WP's `planning_artifact`
staged-ownership classification depends on `owned_files` staying confined to
`kitty-specs/`/`docs/` paths. If the full-suite re-run in T016 surfaces a genuine defect in
WP01–WP03's work, record it in the tracer files and flag it to the orchestrator rather than
silently fixing it here.

**C-007 (no SPEC-KITTY-LEDGER.md entry) — confirm at close-out, do not silently drop it.**
spec.md's C-007 row records that the mission orchestration workspace's
`SPEC-KITTY-LEDGER.md` (outside this checkout) was grepped for "reconcile", "fleet.verdict",
"fleet_main", and "reconcile_shards" with no relevant hits at spec time. As part of T017,
re-confirm this finding still holds — if the operator's copy of the ledger now has an entry
for this defect family, note the drift in `tracer-tooling-friction.md` rather than silently
ignoring it; if it still has none, record that confirmation explicitly rather than leaving
C-007 as a name-only requirement ref.

## Subtask T016: Full baseline-plus-new-tests re-run (SC-001/SC-002/SC-003)

**Purpose**: Confirm the merged WP01+WP02+WP03 diff, as a whole, satisfies SC-001 (unit test
coverage exists across all required surfaces), SC-002 (both safety invariants hold under
simulated instability), and SC-003 (the pre-existing baseline suite for these modules still
passes in full, with the new tests added alongside — no pre-existing test broken or deleted).

**Steps**:
1. Run the exact SC-003 baseline command:
   `.venv/bin/python -m pytest tests/ci/test_fleet_verdict.py tests/ci/test_fleet_main.py
   tests/ci/test_reconcile_shards.py -q` and confirm it passes in full. The recorded baseline
   (spec.md SC-003) is 98 passed / 0 failed as of 2026-09-22 for these three files alone;
   confirm your count is at least that, plus every new test WP01–WP03 added to
   `test_fleet_verdict.py`/`test_fleet_main.py` (WP02 added tests to two of these three
   files; `test_reconcile_shards.py` itself is unmodified, per WP03's proof that
   `reconcile_shards.py` has zero diff).
2. Run the full new-surface suite together:
   `.venv/bin/python -m pytest tests/ci/test_fleet_verdict.py tests/ci/test_fleet_main.py
   tests/ci/test_reconcile_shards.py tests/ci/test_reconcile_retry.py
   tests/ci/test_wait_for_artifacts.py -q` and confirm everything passes with no
   cross-file interaction failures (this is the actual proof that WP01/WP02/WP03 compose —
   run together, not just individually per-WP).
3. Spot-check SC-002's two safety invariants directly against the test names/assertions
   you now have available: (a) confirm at least one test in `test_fleet_verdict.py` and one
   in `test_fleet_main.py` proves "never publish from a stale/first snapshot when the two
   disagree" under retry; (b) confirm the composing test in `test_wait_for_artifacts.py`
   (WP03's T014) proves `reconcile_shards.py::main()` still fails closed when the poller's
   budget is exhausted. If either is missing or unconvincing, record it as a finding in
   `tracer-tooling-friction.md` (T017) rather than silently patching another WP's test file.
4. Note the known, pre-existing, explicitly-out-of-scope environment gap: 34 failures in
   `tests/ci/test_aggregate_source.py` (`ModuleNotFoundError: No module named 'coverage'`)
   are unrelated to this mission (spec.md SC-003's own parenthetical) — if you see them, do
   not attribute them to this mission's diff or attempt to fix them; confirm via
   `.venv/bin/python -m pytest tests/ci/test_aggregate_source.py -q` on the merge-base (or
   note that the failure signature matches the documented `ModuleNotFoundError: coverage`
   pattern) before dismissing them, per CLAUDE.md's baseline-red gotcha.
5. Run `uv run --frozen ruff check .` and `uv run --frozen ruff format --check .` scoped at
   minimum to `scripts/ci/**` and `tests/ci/**` (C-005, hard-enforced), and
   `uv run --frozen ruff check --select TID251 .` for the whole diff.
6. Record every command you ran and its exact pass/fail counts — this is the evidentiary
   record `tracer-approach.md`/the mission's eventual PR body will cite.

**Files**: none — verification only (no code edited in this subtask).

**Validation**: All commands above green (excluding the documented, out-of-scope
`test_aggregate_source.py` environment gap), with exact counts recorded for the PR.

## Subtask T017: Append `tracer-tooling-friction.md`

**Purpose**: Record any spec-kitty tooling friction encountered across WP01–WP04, per
charter Standing Order #3 (mission tracer files: seed at planning, append during
implementation, assess at close).

**Steps**:
1. Read the existing seeded content in
   `kitty-specs/reconcile-flake-family-01M34HR7/tracer-tooling-friction.md` (already present
   from the plan phase — append, do not overwrite).
2. Append an entry for any command that errored, gave a misleading diagnostic, or required a
   workaround during WP01–WP04's implementation (gathered from your own T016 run and from
   whatever WP01/WP02/WP03 implementers reported, if that information is available to you —
   if it is not directly available, note that this WP's own T016 run is the only friction
   source you can directly attest to, and record what you actually observed).
3. If T016 surfaced any finding you did NOT fix (per Context's instruction not to edit
   `scripts/ci/**`/`tests/ci/**` from this WP), record it here explicitly, with enough detail
   that the orchestrator can route it to the right WP or a follow-up.
4. Re-confirm C-007 (per Context's "C-007" note above): check whether the operator's copy of
   `SPEC-KITTY-LEDGER.md` now has an entry for this defect family. Append one line either way
   — "still no ledger entry, confirmed at close-out" or, if one now exists, the drift noted
   explicitly (do not silently ignore it).
5. If nothing new surfaced, append a short, honest entry saying so — do not fabricate
   friction to fill the section, and do not skip the append.

**Files**: `kitty-specs/reconcile-flake-family-01M34HR7/tracer-tooling-friction.md` (append).

**Validation**: File still contains its original seeded content plus your new entry/entries;
`/home/` does not appear anywhere in the file (public-repo hygiene — use repo-relative paths
only).

## Subtask T018: Append `tracer-approach.md`

**Purpose**: Record the final, as-implemented approach summary, per Standing Order #3.

**Steps**:
1. Read the existing seeded content in
   `kitty-specs/reconcile-flake-family-01M34HR7/tracer-approach.md`.
2. Append a closing summary: the four-WP shape as actually implemented (WP01 shared
   primitive → WP02 fleet-verdict/fleet-main retry-then-skip → WP03 ci-aggregate polling →
   WP04 this integration/verification close-out), the exact T016 verification commands and
   results, and explicit confirmation that the pre-merge verification scope note at the top
   of this WP prompt (C-001/Decision 2 — this mission's own PR cannot exercise the fix
   through its real `workflow_run` trigger path) was honored: no rehearsal/replay path and no
   split-off observability mission were added (both were explicitly rejected alternatives in
   spec.md Decision 2 — confirm neither crept in anywhere across WP01–WP03's diffs).
3. Restate the PR-shape recommendation from plan.md's "PR Shape (§2a.6)" section: plan.md's
   own assessment is that ONE PR for this whole mission is realistic and appropriate
   (~250–350 lines across 2 new small modules, 2 modified functions, one workflow
   re-sequencing, plus tests). Confirm or revise this recommendation based on the ACTUAL
   diff size now that WP01–WP03 are implemented — if the real diff is materially larger or
   more review-heavy than plan.md's estimate, say so explicitly here and flag it for the
   orchestrator/operator to decide on a split; do not decide unilaterally to split it
   yourself (per plan.md's own instruction on this point).

**Files**: `kitty-specs/reconcile-flake-family-01M34HR7/tracer-approach.md` (append).

**Validation**: File contains a clear, accurate closing summary; PR-shape recommendation is
explicit (confirm one-PR default, or explicitly flag a split concern) rather than left
implicit.

## Subtask T019: Append `tracer-design-decisions.md`

**Purpose**: Close out the design-decisions tracer with any implement-phase judgment calls
not already captured in plan.md, per Standing Order #3.

**Steps**:
1. Read the existing seeded content in
   `kitty-specs/reconcile-flake-family-01M34HR7/tracer-design-decisions.md` (plan.md's own
   text references "entry 1" — the FR-008 generalization to a single shared primitive — and
   "entry 2" — the selected-only polling scope decision — as already living in this file from
   the plan phase; do not duplicate them, append what's new).
2. Append any WP01–WP03-implement-phase judgment call not already recorded at plan time —
   e.g., the exact sleep-indexing convention WP01 chose for `retry_with_backoff`, the exact
   `_attempt()` decomposition shape WP02 used to hit the complexity-15 target in both files,
   or any artifact-response-shape assumption WP03 had to resolve when integrating with the
   real `GitHub`/`GitHubCLI` `pages()` boundary. If you do not have direct visibility into
   WP01–WP03's implementation decisions beyond what their own WP prompt files and the code
   diff show, read the actual merged code and infer/record the decisions from it rather than
   leaving this section thin.
3. Confirm the mission's Gate Statement (plan.md) held as verified: `ruff check .`/`ruff
   format --check .` (hard), TID251 import-linter (hard), `clean-install-verification`
   (hard, unaffected — no new dependency), `ci-modules.yml`'s `ci` shard over `tests/ci/`
   (hard, verified in T016), diff-cover ≥90% (does not apply, C-008), `sonar-pr`
   (advisory/non-blocking). Record this confirmation explicitly.

**Files**: `kitty-specs/reconcile-flake-family-01M34HR7/tracer-design-decisions.md` (append).

**Validation**: File contains a complete closing record; no `/home/` absolute paths anywhere
in the file.

## Definition of Done

- The full SC-003 baseline (`test_fleet_verdict.py` + `test_fleet_main.py` +
  `test_reconcile_shards.py`) passes with counts at or above the recorded 98-passed baseline
  plus every new test WP01–WP03 added.
- The combined new-surface suite (adding `test_reconcile_retry.py` +
  `test_wait_for_artifacts.py`) passes together, proving WP01/WP02/WP03 compose (SC-001).
- SC-002's two safety invariants are confirmed present and convincing in the test suite (or
  a gap is explicitly recorded in `tracer-tooling-friction.md`, not silently patched).
- All three tracer files (`tracer-tooling-friction.md`, `tracer-approach.md`,
  `tracer-design-decisions.md`) are appended with closing entries — none left as pure
  plan-phase seed content with no implementation-phase record.
- This WP's own diff touches ONLY the three tracer files — no `scripts/ci/**`,
  `tests/ci/**`, or `.github/workflows/**` file.
- `ruff check .` / `ruff format --check .` confirmed clean across the whole mission diff
  (re-verified here, not just trusted from earlier WPs).
- The pre-merge verification scope note (top of this file) is explicitly restated in
  `tracer-approach.md`, not merely implied.
- C-007 is re-confirmed at close-out in `tracer-tooling-friction.md` — either "still no
  `SPEC-KITTY-LEDGER.md` entry" or an explicit note of drift if one now exists — not left as
  a name-only entry in `requirement_refs`.
- The PR-shape recommendation (one PR, per plan.md's default) is explicitly confirmed or
  explicitly flagged for a split, in `tracer-approach.md`.
- No `/home/<user>/...` absolute path appears in any file this WP writes.

## Risks

- **Scope-creep risk**: discovering a real defect in WP01–WP03's work during T016 and being
  tempted to fix it directly from this WP. Don't — this WP's `owned_files` are confined to
  the three tracer files precisely so its `planning_artifact` staged-ownership classification
  holds; route any real finding back to the appropriate WP or flag it to the orchestrator.
- **Silent-scope-satisfaction risk on SC-004**: do not attempt to simulate or fabricate the
  post-merge observation window here. SC-004 is genuinely out of scope for this WP and this
  mission's PR — say so plainly rather than gesturing at "future work" language the spec's
  Decision 2 explicitly forbids (no rehearsal/replay path, no split-off observability
  mission, not even as a footnote).

## Reviewer Guidance

Confirm this WP's diff is confined to the three tracer files only. Confirm the T016 full-suite
counts are recorded with exact numbers, not vague claims of "all green." Confirm the
pre-merge verification scope note is restated in `tracer-approach.md` in the reviewer's own
words are unnecessary — literal restatement is fine, but it must be present, not assumed.
Confirm the PR-shape recommendation is explicit and matches the actual, now-known diff size
rather than merely repeating plan.md's estimate without checking it against reality.

Run: `spec-kitty agent action implement WP04 --agent claude`
