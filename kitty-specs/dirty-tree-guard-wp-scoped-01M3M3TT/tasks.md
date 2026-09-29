# Tasks: Dirty-Tree Guard Is WP-Scoped

**Input**: `spec.md`, `plan.md` from `kitty-specs/dirty-tree-guard-wp-scoped-01M3M3TT/`
**Mission**: `dirty-tree-guard-wp-scoped-01M3M3TT` (GitHub issue `spec-kitty/spec-kitty#5007`)
**Branch**: `issue-5007-dirty-tree-guard-wp-scoped` (planning_base_branch = merge_target_branch =
current branch; public PR target is `main`)

## Shape of this breakdown

plan.md's Implementation Concern Map names exactly **two** implementation concerns (IC-01, IC-02),
with an explicit `depends-on` edge between them (IC-02 "calls `owning_wp_for_path`, which IC-01
introduces"). This tasks phase maps IC-01 → **WP01** and IC-02 → **WP02** one-to-one, WP02 depending
on WP01. No further split and no merge:

- **No further split** — spec C-003 fixes the blast radius at 2 source files + 3 test files (5
  files total). Splitting either IC into multiple WPs over a 1–2-file surface would be padding, not
  decomposition — there is no independently-shippable sub-concern inside either IC.
- **No merge into one WP** — IC-01 and IC-02 are genuinely sequenced (plan.md's own
  "Sequencing/depends-on" note for IC-02: "IC-01 (calls `owning_wp_for_path`, which IC-01
  introduces)") and each opens with its own separate RED-first commit per charter ATDD-first
  (C-011) / plan.md Validation Strategy steps 1 and 3. Charter Standing Order #2 ("no campsite-clean
  WP") is honored the same way plan.md's own Charter Check states it: "No campsite-clean commit is
  planned; a grab-bag would violate Locality of Change for no gain" — neither WP is a grab-bag; each
  is exactly one plan.md IC.

**No campsite-clean WP** is created, per plan.md's Charter Check section quoted above.

## Known, accepted cross-mission file overlap — read before claiming WP02

This section's #5151 file-overlap hold is the *narrowest* compatibility concern in this mission —
spec.md's Compatibility & Reflexivity section makes a broader claim: `dirty_classifier.py` is shared
`move-task` guard infrastructure every currently-running mission depends on, not only #5151. See
WP01's Objective section for that general claim and its proof obligation
(`test_no_previously_benign_path_becomes_blocking`).

Sibling mission `lane-history-safe-handoff-5151-01M3JR6R` (issue #5151), its own WP02 ("Preserve
refused edits with exact-path guidance"), has `owned_files` = `src/specify_cli/cli/commands/agent/tasks_parsing_validation.py`,
`tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py`,
`tests/specify_cli/cli/commands/agent/test_tasks.py` — the **same file set** this mission's WP02
(IC-02) touches, editing a **different function** (`_check_kitty_specs_contamination` and
neighbours — a lane-history-provenance refusal — not `_validate_research_artifacts`, the
WP-directory-ownership refusal this mission fixes). As of this tasks phase, #5151's WP02 is only
just created (lane: `planned`) — it has not started implementation.

This overlap is **known and accepted**, per spec.md Clarifications Q1 and Constraint C-002. An
earlier draft of plan.md's Design Decision (b) had chosen a bar **stricter** than spec.md's own
minimum ("merged to `main`"), but that tightening was never authorized by the operator. On
2026-09-28 the operator ruled (binding, "operator ruling"):

> "Implement for this mission may start once sibling mission
> lane-history-safe-handoff-5151-01M3JR6R's WP02 is approved (reviewed/approved on its own branch);
> this mission builds off main and rebases onto #5151 at PR time; the residual same-file risk is
> accepted as a small conflict in a different function."

plan.md's Design Decision (b) has been corrected to reflect this; spec.md's C-002/Clarifications Q1
"landed-or-approved" bar governs directly.

**Pre-implement precondition (binding on both WPs, chokepoint is this mission's WP02, which shares
the file set):** before either WP01 or WP02 is claimed for implementation, confirm sibling mission
#5151's WP02 has **landed or been reviewed/approved on its own branch** using one of plan.md's three
concrete verification methods (Design Decision (b)):

1. `spec-kitty agent tasks status --mission lane-history-safe-handoff-5151-01M3JR6R --json` and
   confirm WP02's lane is `approved`, `done`, or otherwise landed on `main`; or
2. once WP02's PR exists, `gh pr view <PR#> --json state,mergedAt,reviewDecision` and confirm
   `state == "MERGED"` or `reviewDecision == "APPROVED"`; or
3. `git log main --oneline -- src/specify_cli/cli/commands/agent/tasks_parsing_validation.py` and
   confirm a commit plausibly matching WP02's described change
   (`_check_kitty_specs_contamination` and neighbours) is present on `main`.

If none of these confirms WP02 has landed or been reviewed/approved, **hold implementation and
re-check later** — this is a self-enforced orchestrator/operator discipline (spec-kitty has no
cross-mission dependency gate that blocks `implement`/`move-task` automatically on another mission's
WP status). WP01 has no file overlap with #5151's WP02, but since WP02 (this mission) depends on
WP01 and both WPs together form one PR (see PR Shape below), the practical effect is: do not start
*this mission's implement phase at all* until the precondition above is confirmed.

**Superseded (operator ruling 2026-09-28, later same day):** the operator lifted this
implement-phase hold outright. Implementation on this mission proceeds now, off `main`, without
waiting for sibling mission `lane-history-safe-handoff-5151-01M3JR6R`'s WP02 to land or be
reviewed/approved — the "pre-implement precondition" above (and its three verification methods) is
retained as history, not as a current gate. The two missions' PRs are independent; whichever merges
second rebases onto the first, and the residual same-file risk is accepted as a small, localized
conflict in a different function. See spec.md's C-002 (superseding update) and Clarifications Q1 for
the authoritative current record.

## Gate set (plan.md is authoritative — do not restate the stale doctrine table)

plan.md's "Gate Statement" section is authoritative for this mission and explicitly supersedes the
stale table in `design-pipeline.md §2a` and `review-overlay.md`'s plan `verify` lens (orchestrator
ruling, confirmed 2026-09-23). Read plan.md's Gate Statement directly rather than re-deriving a gate
list here; the short version: `ruff check .` + `ruff format --check .` (always-on), the
architectural-heavy CI battery DOES trigger on this diff's paths (CI-owned, never run
`tests/architectural/` locally per `NO_FULL_HEAVY_SUITES_IN_MISSION`), the routed `tests-cli` job
fires (touches `src/specify_cli/cli/**`), per-module shards `review` and `execution_context` fire,
`diff-cover ≥90%` applies to the new/changed lines. NOT enforced: commitlint, markdownlint, Bandit,
pip-audit, mypy (no CI job), any "kernel/mission-loader 90%" floor, SonarCloud quality gate
(informational only). `packs.yml` does not apply — no `packs/` path is touched.

## Test commands — targeted only, never a full/heavy suite

Per charter `NO_FULL_HEAVY_SUITES_IN_MISSION` and plan.md's Baseline section, every test command
below is `.venv/bin/python -m pytest <targeted files>` only — never a bare `tests/architectural/`,
never `make test-full`, never a full `tests/cli/` or `tests/specify_cli/` sweep.

**Targeted baseline, already re-confirmed during planning (plan.md Baseline section):**

```
.venv/bin/python -m pytest tests/review/test_dirty_classifier.py tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py tests/specify_cli/acceptance/test_accept_dirty_kitty_ops.py -q
```

→ **77 passed, 0 failed, 0 errors** (equals `main@af847be71`; re-confirmed 1.57s, no pre-existing
reds — per charter's Pre-existing Failure Reporting Rule, N/A here since baseline is fully green).

Per spec FR-009, the blocking-lines truncation (`"... and N more"`) branch in
`_validate_research_artifacts` currently has **no test coverage** — this mission (WP02) **adds**
that coverage; it is new coverage, not part of the 77-test baseline.

**Full targeted implementation test surface** (plan.md Validation Strategy):

- `tests/review/test_dirty_classifier.py` (WP01 owns; edited)
- `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py` (WP02 owns; edited)
- `tests/specify_cli/cli/commands/agent/test_tasks.py` (WP01 owns; edited — ATDD, public `move-task`
  route)
- `tests/specify_cli/acceptance/test_accept_dirty_kitty_ops.py` — **run only, not edited**;
  confirms the `_is_benign` kitty-ops-orphan counter-contracts stay green unmodified
- `tests/cli/test_move_task_planned_guard.py` — **run only, not edited** (added per plan.md review
  finding PLAN-VERIFY-001: `tasks_move_task.py` imports directly from this mission's edited
  `tasks_parsing_validation.py`, so this file is in the blast radius even though it is not itself
  edited)
- Owning-module fast tiers: `tests/review/` (module `review`) and
  `tests/mission_runtime tests/runtime tests/specify_cli/cli/commands/agent` (aggregate module
  `execution_context`'s registered `test_dirs`)
- `ruff check .` / `ruff format --check .` for changed files

## PR shape

**One PR for the whole mission** (plan.md Design Decision (e)) — the charter/AGENTS.md default
("Issue branch first... opened as a pull request targeting `main`"), and the 5-file blast radius is
small enough to review in one sitting once both WPs land. Reconciled against the WPs' own
per-subtask line estimates (WP01 T001 ~80-150, T002 ~40-60, T003 ~150-200; WP02 T005 ~25-35, T006
~25-40, T007 ~60-90): the combined estimated diff size is approximately 380-575 lines across the
final PR, mostly test code, which is still small enough to review in one sitting alongside the
5-file count. No per-WP PR split is proposed.

---

## Work Packages

### WP01 — WP-scoped ownership attribution mechanism (IC-01)

**Priority**: P1 (both stories it backs, User Story 1 and User Story 3, are P1/P2 in spec.md;
every other WP in this mission depends on it)
**Independent test**: `tests/review/test_dirty_classifier.py`'s new unit tests plus the new
`tests/specify_cli/cli/commands/agent/test_tasks.py` ATDD case reproduce all three concretely
reported occurrences RED on `main`, GREEN once `owning_wp_for_path` + the `classify_dirty_paths`
integration land.
**Requirement refs**: FR-001, FR-002, FR-003, FR-004, FR-006, FR-007, FR-008, FR-009 (partial — the
ATDD reproduction half; the truncation-branch half of FR-009 is WP02's), SC-001, SC-002, SC-003;
C-001; NFR-001, NFR-002.
**Owned files**:
- `src/specify_cli/review/dirty_classifier.py`
- `tests/review/test_dirty_classifier.py`
- `tests/specify_cli/cli/commands/agent/test_tasks.py`

**Dependencies**: none within this mission. **Superseded (operator ruling 2026-09-28, later same
day):** this previously noted a mission-level implement-phase hold (see "Pre-implement precondition"
above) applying to the whole mission, both WPs; the operator has since lifted that hold outright —
see the "Superseded" note under "Known, accepted cross-mission file overlap" above and spec.md's
C-002 (superseding update).

**Included subtasks**: T001, T002, T003, T004 (see Subtask Index)

**Implementation sketch**:
1. RED-first: add the failing acceptance test in `test_tasks.py` reproducing all three occurrences
   through the public `move-task` entry point (T001).
2. Add `owning_wp_for_path(path, mission_slug) -> str | None` to `dirty_classifier.py`; tighten
   `_is_review_handoff_survivor_path`'s `wp_task_pattern` (`.+` → `[^/]+`, PLAN-ARCH-001 companion
   fix); wire the new helper into `classify_dirty_paths` as a second step after the existing
   `_is_benign` check (T002).
3. Add direct unit coverage in `test_dirty_classifier.py` for FR-001/002/003/004/007/008, the two
   PLAN-ARCH-001 nested-`.md` regression tests, and the no-new-blocking compatibility regression
   test (T003).
4. Confirm GREEN: T001's ATDD test now passes; run the full targeted surface named above (T004).

**Parallel opportunities**: none — this is a single, tightly sequenced WP (RED test → mechanism →
unit coverage → confirm green) on a 1-source-file + 2-test-file surface; the subtasks are not
independently parallelizable.

**Risks** (plan.md IC-01 risk list, carried verbatim in substance):
- The combined regex must not over-match a bare flat non-`.md` file directly in `tasks/` (not
  inside a WP subdirectory) as WP-owned — covered by an explicit negative-control test.
- **(resolved by adversarial plan review, PLAN-ARCH-001)**: the pre-existing `wp_task_pattern` in
  `_is_review_handoff_survivor_path` over-matched nested `.md` paths across WP-directory and
  mission boundaries, short-circuiting `_is_benign` to `True` before `owning_wp_for_path` was ever
  consulted — silently defeating spec.md AC3 and FR-008 for a nested-`.md` shape. Fixed by
  tightening the pattern in the same commit that introduces `owning_wp_for_path`; covered by
  `test_own_directory_nested_md_file_still_blocks` and
  `test_cross_mission_nested_md_file_still_blocks`.

---

### WP02 — Honest per-path refusal attribution (IC-02)

**Priority**: P1 (User Story 2 is P1 in spec.md)
**Independent test**: a blocking refusal's guidance text is asserted for content — never a
hardcoded `"owned by {wp_id}"` when `{wp_id}` is not the true owner; a mixed-outcome refusal (one
line the moving WP's own residue, one line unattributable) carries per-line attribution, not one
shared header.
**Requirement refs**: FR-005, FR-009 (the truncation-branch coverage half), SC-004; NFR-002.
**Owned files**:
- `src/specify_cli/cli/commands/agent/tasks_parsing_validation.py`
- `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py`

**Dependencies**: WP01 (calls `owning_wp_for_path`, which WP01 introduces — plan.md IC-02
"Sequencing/depends-on"). This WP shares its file set with sibling mission #5151's WP02, and was
previously described as the chokepoint work package gated by the mission-level pre-implement
precondition above. **Superseded (operator ruling 2026-09-28, later same day):** that hold was
lifted outright; see the "Superseded" note under "Known, accepted cross-mission file overlap" above
and spec.md's C-002 (superseding update).

**Included subtasks**: T005, T006, T007, T008 (see Subtask Index)

**Implementation sketch**:
1. RED-first: add the failing test in `test_tasks_parsing_validation.py` pinning the corrected
   FR-005 wording against WP01's already-landed final state (T005).
2. Extract `_attribute_blocking_path(path, wp_id, mission_slug) -> str` and rewrite
   `_validate_research_artifacts`'s guidance construction to call it per blocking line, replacing
   the single hardcoded `"owned by {wp_id}"` header (T006).
3. Add unit coverage: the mixed-outcome per-line case (User Story 2 AC3), the FR-009
   truncation-branch test (construct >5 blocking paths), and update the two existing
   wording-assertion tests to the new per-line phrasing (T007).
4. Confirm GREEN: run the full targeted surface plus the owning module's fast tier and the two
   run-only files (T008).

**Parallel opportunities**: none — same reasoning as WP01 (single sequenced RED → implement →
unit-coverage → confirm-green chain on a 2-file surface).

**Risks** (plan.md IC-02 risk list):
- The two existing message-assertion tests
  (`test_validate_research_artifacts_blocks_research_commit_format`,
  `test_validate_research_artifacts_benign_only_passes_with_note`) need their expected-string
  assertions updated to the new per-line wording — expected, in-scope churn per FR-005 (distinct
  from WP01's Design Decision (c) wp_id-blind pins, which live in a different file/code path and
  are NOT touched).
- Complexity ceiling: adding per-path attribution to the guidance-construction loop risks pushing
  `_validate_research_artifacts` past the charter's mccabe ceiling of 15 — mitigated by extracting
  `_attribute_blocking_path` as its own small, independently-testable helper (plan.md
  Compatibility/Risks section).

---

## Subtask Index (reference table — not a tracking surface)

Completion is event-sourced via `spec-kitty agent tasks mark-status <Txxx> --status done`; this
table is a reference list only, per the tasks-authoring convention (`prompt.md`'s "Subtask Index vs.
reference rows" distinction) — the `Parallel` column names parallelism, not status.

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | RED-first ATDD test in `test_tasks.py` via public `move-task`, reproducing #5151 ask 3 (non-`.md` cross-WP file), #5159 item 4 (cross-WP `review-cycle` directory), kentonium3's Friction 2 (wholly-untracked `review-cycle-N.md`) — RED on `main`/pre-fix product code | WP01 | no |
| T002 | Add `owning_wp_for_path`; tighten `wp_task_pattern` (PLAN-ARCH-001); wire into `classify_dirty_paths` | WP01 | no |
| T003 | Unit coverage in `test_dirty_classifier.py`: FR-001/002/003/004/007/008, two PLAN-ARCH-001 nested-`.md` regression tests, no-new-blocking compatibility regression test | WP01 | no |
| T004 | Confirm GREEN: T001 passes; run full WP01 targeted surface + counter-contract file | WP01 | no |
| T005 | RED-first test in `test_tasks_parsing_validation.py` pinning corrected FR-005 wording, against WP01's final state | WP02 | no |
| T006 | Extract `_attribute_blocking_path`; rewrite `_validate_research_artifacts` guidance construction to per-line attribution | WP02 | no |
| T007 | Unit coverage: mixed-outcome per-line case (SC-004), FR-009 truncation-branch test, update two existing wording-assertion tests | WP02 | no |
| T008 | Confirm GREEN: run full WP02 targeted surface + owning module fast tier + run-only files + ruff | WP02 | no |

## Next steps

1. `spec-kitty agent tasks map-requirements` to register `requirement_refs` per WP.
2. `spec-kitty agent mission finalize-tasks --validate-only` then `finalize-tasks` (commits
   automatically).
3. ~~Confirm the mission-level pre-implement precondition (sibling #5151 WP02 landed or
   reviewed/approved on its own branch) before claiming WP01 or WP02.~~ **Superseded (operator
   ruling 2026-09-28, later same day):** this precondition was lifted outright; do not hold
   implementation on it. See spec.md's C-002 (superseding update) and Clarifications Q1.
4. `/spec-kitty.analyze` (required gate before any WP implementation).
