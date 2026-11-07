# Work Packages: Corpus advisory suite budget you can defend

**Inputs**: Design documents from `kitty-specs/corpus-advisory-budget-01M6P49E/`
**Prerequisites**: spec.md, plan.md, research.md, reasons-canvas.md
**Governing issue**: [#7206](https://github.com/spec-kitty/spec-kitty/issues/7206)

**Organization**: Two work packages. WP01 is the red-first budget change — the cap guard extension,
the recorded headroom line, the derived cap, and the legible budget-expiry notice with its own
guard module. WP02 is the recorded rationale in the reference doc plus the per-PR changelog
fragment.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel (different files/components).
- Subtasks are reference rows; completion is recorded with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `.github/workflows/`, `tests/ci/`, `docs/`.

---

## Work Package WP01: The cap is derived from measurement, and a budget expiry is legible (Priority: P0)

**Goal**: `built-in-corpus-suite` records the measured maximum suite wall-clock above its cap, the
cap is the value the repository's #5378 formula implies (31), the cap guard enforces that derivation
for this job, and a killed suite still reaches a notice that says the run is INCOMPLETE and advisory
— with the selection semantics (marker, deselects, `continue-on-error`, trigger) untouched.
**Independent Test**: `uv run --frozen pytest tests/ci/test_nightly_timeout_headroom.py
tests/ci/test_corpus_suite_budget.py -q` — the new pack-corpus cap test fails on the current
`timeout-minutes: 20` naming the required 31, and passes after the change; the new budget-legibility
module fails on the current job (no step budget, no legible notice) and passes after.
**Prompt**: `tasks/WP01-derived-cap-and-legible-expiry.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, NFR-001, NFR-002, NFR-003, NFR-004, C-001, C-002, C-003, C-004, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

- T001 Red-first: add the `packs.yml::built-in-corpus-suite` target to
  `tests/ci/test_nightly_timeout_headroom.py` (generalize the per-file target selection without
  changing the nightly/module behaviour) and run it against the current `timeout-minutes: 20`;
  record the failure ("timeout-minutes 20 < required 31")
- T002 Red-first: write `tests/ci/test_corpus_suite_budget.py` — step budget strictly below the job
  cap, notice legibility (advisory + not-a-test-failure wording), recorded max-suite ≤ 75 % of the
  cap, and a mutation control per property — and run it red against the current job
- T003 `.github/workflows/packs.yml`: record the headroom line (`# headroom (#5378): max-suite>=19:55
  runs=55 window=2026-11-04..05 formula=ceil((max+0:30)*1.5)`) directly above the job-level
  `timeout-minutes`, with the measured decomposition and the rejected path shard in a comment
  directly above it; set `timeout-minutes: 31`
- T004 `.github/workflows/packs.yml`: give the suite step `timeout-minutes: 28` (below the job cap, so
  a killed suite still reaches the next step) and rewrite the `if: failure()` notice so it states the
  run did not finish, is advisory, and is not a test failure (#7206, #4437)
- T005 Run the guards and the lane's existing invariants unchanged:
  `tests/ci/test_nightly_timeout_headroom.py`, `tests/ci/test_corpus_suite_budget.py`,
  `tests/ci/test_corpus_blocking_home.py`, `tests/ci/test_contracts_routing.py`,
  `tests/ci/test_xdist_worker_policy.py`, `tests/architectural/test_ci_corpus_trigger_completeness.py`,
  `tests/architectural/test_no_duplicate_suite_execution.py`; plus `ruff check` and
  `ruff format --check`
- T006 Prove the selection semantics did not move: print the `git diff` of the job's pytest command
  line and of the `if:`/`continue-on-error`/`needs:` keys and record that they are unchanged in the
  WP notes and the PR body

### Implementation Notes

- The headroom comment MUST be the last non-blank line directly above the job-level
  `timeout-minutes:`; the guard's block parser is 4-space-indent and neighbour-sensitive (its own
  mutation tests cover both).
- Do not add a `paths:`/matrix shard: `tests/ci/test_corpus_blocking_home.py` requires the advisory
  lane to select a corpus test at any path, and `tests/ci/test_contracts_routing.py` requires exactly
  one pytest invocation in this job.
- The 75 % guard reads the recorded max-suite from the comment and the job cap; it is the issue's
  acceptance rule (p95 proxy: recorded worst case) made machine-checked.
- Keep `continue-on-error: true` job-level: a step-level flag would change the advisory verdict
  surface (`ci-fleet-verdict` reads the workflow-run conclusion).

### Parallel Opportunities, Dependencies, Risks

- T001/T002 are red-first and can be written in parallel; T003/T004 depend on them being red first.
- Risk: a stale notice name breaks nothing (no guard references it), but keep the suite step's name
  unchanged so log-based operators keep their search term.

---

## Work Package WP02: Record the rationale, and the per-PR changelog fragment (Priority: P1)

**Goal**: A maintainer who reads the lane's documentation finds the budget, its derivation and the
rejected alternatives; the change is recorded in a per-PR changelog fragment.
**Independent Test**: read `docs/development/reference/ci-gate-mechanics.md` next to its "Corpus
tests have one advisory owner" bullet; run
`uv run --frozen python -m scripts.docs.check_docs_freshness --ci` (errors=0) and the changelog-style
and spelling checks.
**Prompt**: `tasks/WP02-docs-and-changelog-fragment.md`
**Requirement Refs**: FR-007, SC-004, NFR-001

### Included Subtasks

- T007 `docs/development/reference/ci-gate-mechanics.md`: extend the advisory-owner bullet with the
  measured budget (p95 20.3 min of the old 20-minute cap), the derivation (`ceil((max+0:30)*1.5)` =
  31), the legible-expiry behaviour, and why sharding was rejected (naming both pinned guards)
- T008 `docs/changelog/unreleased/7206-corpus-advisory-budget.fixed.md`: impact-first entry with the
  `(#7206)` reference, before/after, under 1,200 characters; rename to `<pr>.fixed.md` once the pull
  request number exists
- T009 Run `scripts.docs.check_docs_freshness --ci`, `scripts.docs.check_changelog_style` and
  `scripts.docs.check_spelling --pass unreleased`; record the results in the PR's "Tests run"

### Implementation Notes

- Docs are indexed: prose-only edits to an existing page need no `docs_index --write`; confirm with
  the freshness check rather than trusting it.
- No new page, no ADR: the rationale belongs with the cap and in the existing reference section.

### Parallel Opportunities, Dependencies, Risks

- Depends on WP01 for the final numbers and behaviour wording.
- Risk: the fragment name must be the PR number before the flip to ready; keep the branch-slug name
  until `gh pr create` returns.
