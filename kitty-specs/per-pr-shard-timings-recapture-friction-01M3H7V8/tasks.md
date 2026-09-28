# Tasks: Per-PR charter shard-timings recapture friction

**Input**: `kitty-specs/per-pr-shard-timings-recapture-friction-01M3H7V8/plan.md` (PASSED, HEAD `a117695b5`),
`kitty-specs/per-pr-shard-timings-recapture-friction-01M3H7V8/spec.md` (PASSED),
`reviews/spec.ruling.md` (rulings 1 & 2), `reviews/plan.ruling.md` (rulings 1 & 2 + the standing
extra-round rule).
**Branch**: `issue-5189-per-pr-shard-timings-recapture-friction` (target == planning branch; this is
a `SINGLE_BRANCH`-shaped mission, one PR at the end).

This mission decomposes plan.md's four Implementation Concerns (IC-01..IC-04) into **3 work
packages**. IC-04 (the docs supersession note) is folded into WP03 as a small addendum rather than
given its own WP — see "IC-04 disposition" below.

---

## PR shape recommendation

**ONE PR for the whole mission.** Per plan.md's own file list (one edited test file, one new
script + its unit-test file, one new workflow file, plus a one-line docs addendum), the total diff
is small (**amended 2026-09-28**: a purely additive test-only edit — no behavioural change, since
PR #5240 already merged the demotion mechanism ahead of this mission — adding ~8 new tests plus
one verification subtask in one existing file (fix round 2 restored FR-004's agreeing-case fixture
pair, T003b/T004b); one new ~150-250-line script; one matching
~280-320-line unit-test file — 11 fixtures, estimated from WP02's own fixture list, see WP02's
section below for the derivation; one new ~70-100-line workflow YAML — now two jobs, the recapture
job plus the new strict-mode job (T020); a 1-2 line docs edit) and is reviewable in one sitting on
`main`. This matches spec-kitty's own default (one PR per mission); nothing here argues for a
split. This is an explicit judgment call, stated per the dispatch's instruction, not a silent
default.

---

## Open-PR write-scope check (re-verified live 2026-09-27 by the orchestrator before dispatch)

`gh pr list --repo spec-kitty/spec-kitty --state open --json number,files` showed 9 open PRs at
dispatch time. Two touch paths in this mission's blast radius:

- **#5224** (`pr/consolidate-canonical-terminology`) touches `.github/ci-shard-timings.json`,
  `.github/workflows/ci-router.yml`, `scripts/ci/aggregate_source.py`,
  `scripts/ci/coverage_guard_lib.py`.
- **#5244** (`issue-4951-ci-nightly-interpreter-matrix-timeout`) touches
  `.github/workflows/ci-nightly.yml`, `tests/ci/test_interpreter_matrix_env_pinning.py`,
  `tests/ci/test_nightly_exit_code_honesty.py`.

This mission's own file list is: `tests/architectural/test_module_length_agreement.py` (edit),
`scripts/ci/recapture_charter_shard_timings.py` (new), `tests/ci/test_recapture_charter_shard_timings.py`
(new), `.github/workflows/ci-charter-shard-recapture.yml` (new), and (WP03's folded-in IC-04
addendum) `docs/development/reference/known-friction-points.md` (edit).

**No exact filename collides** with either #5224's or #5244's file list. **Directory-sharing
only** (not a merge conflict, not blocking): #5224 shares `scripts/ci/` (different file:
`recapture_charter_shard_timings.py` vs. `aggregate_source.py`/`coverage_guard_lib.py`) and
`.github/workflows/` (different file: `ci-charter-shard-recapture.yml` vs. `ci-router.yml`);
#5244 shares `tests/ci/` (different file: `test_recapture_charter_shard_timings.py` vs.
`test_interpreter_matrix_env_pinning.py`/`test_nightly_exit_code_honesty.py`) and
`.github/workflows/` (different file, as above). **No lane write-scope adjustment is needed** —
none of this mission's three code WPs (below) touch a file either PR also touches.

Separately: the earlier-flagged hazard on `.github/ci-shard-timings.json` (#5175/#5177) is
**resolved** — #5177 is MERGED, #5175 is CLOSED (unmerged) — per plan.md item (g). No stale PR
numbers to chase.

---

## Chokepoints

- **IC-03 depends on IC-02** (ordering dependency, not a shared-CI-gate chokepoint in the
  write-scope sense): the new workflow file (WP03) calls the script WP02 creates
  (`scripts/ci/recapture_charter_shard_timings.py`). WP03 cannot be implemented (its `run:` step
  has nothing to invoke) before WP02 lands. This is captured as `dependencies: ["WP02"]` in WP03's
  frontmatter.
- **No seam applies** (plan.md item (i)): no WP in this mission touches the migration chain, the
  runtime-state schema, the event contract, or a shared CI gate serializing the whole repo. All
  three WPs' diffs are confined to `tests/architectural/**`, `scripts/ci/**`, `tests/ci/**`,
  `.github/workflows/**`, and one `docs/**` file — none of which participate in the enforced
  `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli` import-direction chain.
- **No parallel-WP file overlap**: WP01, WP02, and WP03 own disjoint file sets (see each WP's
  `owned_files` below) — verified again in the "Lanes / write-scope cross-check" section after
  `finalize-tasks` runs.

---

## Campsite-clean: no WP needed

Plan.md item (e) inspected both files this mission's design depends on
(`tests/architectural/test_module_length_agreement.py`, which WP01 edits, and
`scripts/ci/capture_shard_timings.py`, which stays **unmodified**) and concluded **"none needed"**
for both, with concrete reasons: `test_module_length_agreement.py` has no dead code, stale
comments, or complexity/duplication issue, and its existing session-scoped-fixture / pure-helper /
self-mutation-test idiom is exactly the shape WP01's own addition should match (no tidy-first
commit needed — the change is additive, in the file's own established idiom).
`capture_shard_timings.py` likewise has no debt, and — per plan.md's "mechanism-vs-ordinary-failure
design problem" analysis — requires **zero edits**: its existing write-before-return-decision
control flow is exactly what WP02's wrapper depends on. **No campsite-clean WP is added to this
mission**, per plan.md item (e)'s own reasoning, restated here so a reviewer does not wonder why
one is missing.

---

## IC-04 disposition (docs supersession note)

Plan.md marks IC-04 (a supersession note in `docs/development/reference/known-friction-points.md`
about PR #5190's already-merged bullet) as **optional, a judgment call at implementation time**.
This tasks.md folds it into **WP03** as a small addendum (T018) rather than giving it its own WP:
the edit is a 1-2 line prose addition to an existing doc file, has no dependency of its own, and
does not warrant separate worktree/lane overhead. It is **not dropped** — spec.md's Reflexivity
section explicitly asks for the PR to note the supersession, so WP03 delivers it directly rather
than leaving it to the PR body alone.

---

## FR / NFR / Constraint / Ruling traceability

Every FR in spec.md, every NFR, every Constraint, and every operator ruling point that carries a
code-facing consequence is mapped below to a concrete WP task with a concrete test (or, for
FR-009/FR-010/NFR-001, a concrete inspection point plan.md itself designates as "no-op passable:
yes" / verified by code-shape inspection, not a dedicated fixture). Four operator rulings —
PLAN-FRESH2-003 through PLAN-FRESH2-006 — are resolved entirely in plan.md's own prose (the TOCTOU
sequencing paragraph, the fixture-tested/code-shape-inspection split, and the accepted-residual-cost
paragraph) with no separate code-landing WP task required, and are therefore intentionally absent
from this table rather than missing coverage.

| Requirement / ruling point | WP | Task(s) | How it is verified |
|---|---|---|---|
| FR-001 (demote to non-blocking; amended: already merged by #5240, WP01 verifies + adds red-first tests) | WP01 | T002 (verify), T003, T005 | T002 confirms `_report_drift`/`_strict_mode` merged behavior; `test_charter_disagreement_emits_shard_timings_drift_warning` (T003) and its strict-mode counterpart (T005) exercise the production function directly |
| FR-002 (charter stays out of `_MISMATCH_ALLOWLIST`) | WP01 | T002, T008 | T002 confirms the unchanged hard `assert "charter" not in _MISMATCH_ALLOWLIST` in the merged test body; diff review in T008 confirms it stays unedited |
| FR-003 (amended: 3 untouched allowlist-ratchet tests + 19-entry allowlist byte-identical; demotion covers both live-collection gates) | WP01 | T004 (cross-module gate), T008 (diff review) | `test_non_allowlisted_disagreement_emits_shard_timings_drift_warning` (T004) exercises the cross-module gate directly; T008's diff review confirms the three allowlist-ratchet tests and the allowlist itself are byte-identical |
| FR-004 (visible drift + infra-break still fails; amended: extended to both gates; fix round 2 restored the agreeing-case fixture) | WP01 | T002, T003, T003b, T004, T004b, T005, T006 | T002 confirms the merged warn/strict-fail mechanism; T003/T004 prove the disagree-warns case for each gate; T003b/T004b (`test_charter_agreement_emits_no_shard_timings_drift_warning`, `test_non_allowlisted_agreement_emits_no_shard_timings_drift_warning`) prove FR-004's third mandatory fixture — the AGREEING case emits zero `ShardTimingsDriftWarning` (via `recwarn`) and each production gate function returns normally; T005 proves the strict-fail case for each gate; T006 (`test_load_timings_fails_loudly_when_artefact_missing`, `test_load_registry_fails_loudly_when_artefact_missing`) proves infra-break |
| FR-005 (named secret, truthy check, fail-loud before anything else) | WP02 | T012, T014 (fixture 5) | `main()`'s first action is the truthy secret check; fixture 5's two sub-cases (empty-string, fully-unset) both assert the capture-wrapper AND the open-PR-check callables are never invoked |
| FR-006 (no PR when no drift) | WP02 | T010, T014 (fixtures 3, 6) | `has_drift(N, N)` is `False`; `has_drift(N, M)` is `True` and triggers the push callable |
| FR-007 (skip if a recapture PR is already open) | WP02 | T011, T013, T014 (fixtures 1, 2), T015 (fixture 7) | open-PR matcher returns the PR number only for the fixed head branch; fixture 2 proves an unrelated PR on a different head is never matched; fixture 7 (TOCTOU re-check) proves a PR appearing between the initial check and the push still aborts the push |
| FR-008 (mechanism failure aborts; ordinary test failure does not) | WP02 | T009, T014 (fixture 4), T015 (fixtures 8, 9, 10) | `run_capture_or_die` catches `(Exception, SystemExit)`, re-raises `KeyboardInterrupt`; fixtures 4/8/9 prove mechanism-crash aborts before commit/push/PR-open; fixture 10 proves an ordinary non-zero `pytest_exit_code` (no exception) proceeds to the drift check |
| FR-009 (charter-only scope, no `--module` flag) | WP02 | T009, T013 | `MODULE = "charter"` module-level constant; script exposes no `--module` CLI flag at all |
| FR-010 (bot identity + fixed PR body/commit text) | WP02 | T013 | fixed commit author `spec-kitty-ci-bot <ci-bot@users.noreply.github.com>`, fixed commit message `chore(ci): automated charter shard-timings recapture`, fixed PR title/body template (verbatim in plan.md item (d)) |
| NFR-001 (gate protects shard balance, not correctness) | WP01, WP03 | T002 (code shape, read-and-confirm), T019 (PR-body statement) | `module-tests.yml`'s uniform-weight fallback verified by inspection (plan.md item (d)); WP03's PR-body note states this explicitly |
| NFR-002 (recapture job: 30-minute timeout budget, measured runtime recorded post-dispatch; amended: strict-mode job T020 gets its own 10-minute budget) | WP03 | T016, T019, T020 | recapture job `timeout-minutes: 30` (T019 flags for revisit post-dispatch); strict-mode job `timeout-minutes: 10` (T020, evidence: ~36s measured live-collection of all 21 modules) |
| NFR-003 (no credential leakage) | WP02 | T012, T013 | secret value never interpolated into commit/PR/log text; only the secret's **name** appears in error paths |
| C-001 (charter-only *recapture* scope; the demotion's own scope is broader — see FR-003) | WP01, WP02 | T004 (synthetic-only, never a real non-charter module), T009 | WP01's T004 fixture uses only synthetic in-memory data, never a real registry module; WP02 hardcodes `MODULE = "charter"` for the recapture script |
| C-002 (no allowlist-mutation feature) | WP01 | T002, T008 | no code is added anywhere that edits `_MISMATCH_ALLOWLIST` / `_BASELINE_ALLOWLIST_COUNT`; T002/T008 confirm this by reading and diff review |
| C-003 (`main` is PR-only) | WP02, WP03 | T013, T016 | the script never pushes to `main`; the workflow's checkout token is the dedicated PAT, never `GITHUB_TOKEN`, and the push target is always the fixed recapture branch |
| C-004 (no silent `GITHUB_TOKEN` fallback) | WP02 | T012, T014 (fixture 5) | the truthy check never falls back to `GH_TOKEN`/`GITHUB_TOKEN`; fixture 5 proves the loud-failure path |
| C-005 (no absolute local paths / credentials in committed artifacts) | WP01, WP02, WP03 | (all) | reviewer/self-check: `grep -rn "/home/" <touched files>` before each WP is marked done |
| C-006 (concurrency-guarded) | WP03 | T016 | `concurrency: {group: ci-charter-shard-recapture, cancel-in-progress: false}` — static group, per plan.md item (b)'s rationale (a topic-branch rehearsal dispatch and a `main` cron run both push to the same fixed branch) |
| Ruling: fixed head branch `ci/recapture-charter-shard-timings`, skip-if-open (not force-update) | WP02 | T011, T013 | the `gh pr list --head ci/recapture-charter-shard-timings --base main` query already restricts candidates by BOTH head and base at the CLI level; `find_open_recapture_pr`'s own `headRefName == ci/recapture-charter-shard-timings` check is then a defense-in-depth re-check of the (already-filtered) results, not the primary filter — this is also what makes the pure function unit-testable via injected fixtures 1/2 (T014), which construct JSON payloads independent of what any real `gh` call would return; when found, the job writes one job-summary line and performs no push/force-push/comment/open. **Pointer (TASKS-FRESH2-001):** `plan.md`'s "Open-PR check (verbatim)" bullet and its TOCTOU-paragraph restatement of the same `gh pr list` command still show the pre-fix `--json number` field list; both are superseded by WP02.md's T011 section, which specifies `--json number,headRefName` and is authoritative for implementation. |
| Ruling: FR-010 carries no identity-matching coupling to FR-007 | WP02 | T013 | commit/PR template text is independent of the branch-based open-PR check; no cross-requirement coupling in the code |
| Plan ruling: fixture proving an ordinary failing test does not abort commit/PR (PLAN-FRESH2-001) | WP02 | T015 (fixture 10) | `test_ordinary_failure_continues_to_drift_check` (or equivalently named) |
| Plan ruling: static concurrency group, real rationale (PLAN-FRESH2-002) | WP03 | T016 | concurrency group is static, not `${{ github.ref }}`-suffixed — WP03's task text states the rehearsal-vs-`main` rationale verbatim |
| Plan ruling: TOCTOU re-check fixture (fixture 7) | WP02 | T015 | `test_toctou_recheck_aborts_push` |
| Plan ruling: truthy secret check, both empty-string and fully-unset sub-cases (PLAN-FRESH4-001) | WP02 | T014 (fixture 5) | both sub-cases fail loudly before any recapture/open-PR call |
| Plan ruling: NFR-002 satisfied by post-dispatch PR-body update (PLAN-FRESH4-002) | WP03 | T019 | stated explicitly as a PR-body note (T019 step 2) — WP03 has no separate "Definition of Done" section; the note lives in T019's own Subtasks & Detailed Guidance text |
| Amendment ruling point 2 (absorb #5240 rather than reimplement) | WP01 | T002 | documented read-and-confirm verification pass, recorded in the Activity Log, before any new test is written |
| Amendment ruling point 4 (strict-mode home for the exact-count invariant, in WP03's own workflow) | WP03 | T020 | new, independent job in `ci-charter-shard-recapture.yml`, no `needs:` to the recapture job, `SPEC_KITTY_STRICT_SHARD_TIMINGS=1`, `timeout-minutes: 10` |
| Amendment ruling point 5 (allowlist-ratchet interplay: charter-only recapture can never trip `test_allowlisted_modules_still_genuinely_mismatch`) | WP01 | T002 | stated in plan.md item (a2)'s allowlist-ratchet paragraph and WP01's Objectives section; verified by the unconditional `assert "charter" not in _MISMATCH_ALLOWLIST"` T002 confirms is unchanged |
| Amendment ruling point 6 (optional `mypy` `no-any-return` fix, admissible campsite debt) | WP01 | T007 | explicitly optional, non-gating subtask; a distinct, behaviour-preserving commit if the implementer chooses to do it |

---

## Subtask Index

| ID | Description | WP | Parallel |
|----|---|----|----|
| T001 | Capture RED-FIRST baseline: `.venv/bin/python -m pytest tests/architectural/test_module_length_agreement.py -q` on current HEAD, before any edit | WP01 | [P] |
| T002 | Verify #5240's merged `ShardTimingsDriftWarning`/`_report_drift`/`_strict_mode` mechanism satisfies FR-001/FR-002/FR-004 for `charter` (read-and-confirm, no code edit) | WP01 | [P] |
| T003 | Add `test_charter_disagreement_emits_shard_timings_drift_warning` | WP01 | [P] |
| T003b | Add `test_charter_agreement_emits_no_shard_timings_drift_warning` (FR-004's agreeing-case fixture; fix round 2) | WP01 | [P] |
| T004 | Add `test_non_allowlisted_disagreement_emits_shard_timings_drift_warning` | WP01 | [P] |
| T004b | Add `test_non_allowlisted_agreement_emits_no_shard_timings_drift_warning` (cross-module agreeing-case fixture; fix round 2) | WP01 | [P] |
| T005 | Add strict-mode tests (`SPEC_KITTY_STRICT_SHARD_TIMINGS=1`) for both production gate functions | WP01 | [P] |
| T006 | Add `test_load_timings_fails_loudly_when_artefact_missing` + `test_load_registry_fails_loudly_when_artefact_missing` | WP01 | [P] |
| T007 | (Optional, non-gating) Fix `mypy` `no-any-return` in `_resolve_test_dirs` | WP01 | [P] |
| T008 | Post-edit targeted test run + diff review confirming FR-002/FR-003/SC-006 untouched | WP01 | [P] |
| T009 | Implement `CaptureOutcome` dataclass + `run_capture_or_die()` | WP02 | [P] |
| T010 | Implement `has_drift(before_length, after_length) -> bool` | WP02 | [P] |
| T011 | Implement the open-PR matching function (`gh pr list` parsing, fixed-branch match) | WP02 | [P] |
| T012 | Implement the secret truthy-check (fail-loud, no `GITHUB_TOKEN` fallback) | WP02 | [P] |
| T013 | Implement `main()`'s orchestration sequence (secret check -> open-PR check -> capture -> re-check -> drift -> commit/push/PR-open) | WP02 | [P] |
| T014 | Unit tests for fixtures 1-6 (skip-if-open, unrelated-PR-not-matched, no-drift-no-PR, capture-failure-no-commit, missing-secret-loud-failure x2, drift-triggers-push) | WP02 | [P] |
| T015 | Unit tests for fixtures 7-11 (toctou-recheck-aborts-push, mechanism-crash-via-systemexit, post-write-logging-failure-fails-closed, ordinary-failure-continues, snapshot-before-overwrite) | WP02 | [P] |
| T016 | Author `.github/workflows/ci-charter-shard-recapture.yml` | WP03 | |
| T017 | Verify workflow shape against plan.md item (b)'s verbatim decisions (checklist, no code) | WP03 | |
| T018 | Add docs supersession note to `docs/development/reference/known-friction-points.md` (IC-04) | WP03 | |
| T019 | `make ci-parity` check + PR-body notes (gate-selection prediction, NFR-002 budget-revisit flag) | WP03 | |
| T020 | Add the strict-mode job (`SPEC_KITTY_STRICT_SHARD_TIMINGS=1`) to `ci-charter-shard-recapture.yml`, independent of the recapture job (amendment ruling point 4) | WP03 | [P] |

---

## Work Package WP01 — Demote the per-PR charter length assertion

**File**: `tasks/WP01-demote-charter-length-assertion.md`
**Priority**: P1 (User Stories 1, 3) | **Dependencies**: none | **Parallel with**: WP02
**Requirements**: FR-001, FR-002, FR-003, FR-004; C-001, C-002, C-005; NFR-001 (code-shape half)

Subtasks: T001, T002, T003, T003b, T004, T004b, T005, T006, T007, T008 (10 subtasks; T007 is
optional/non-gating).

**Amended 2026-09-28 (operator ruling, `reviews/amendment.ruling.md`)**: after this design's
original `ready` verdict, `main` was found to already carry PR #5240, which merged the demotion
mechanism this WP originally specified as a `_charter_disposition`/`pytest.xfail` design — that
design is dead. WP01's job is now "absorb #5240": verify the merged
`ShardTimingsDriftWarning`/`_report_drift`/`_strict_mode` mechanism (T002), and add the red-first
tests #5240 itself leaves unmet (T003-T006), with an optional, non-gating campsite-debt fix (T007).
The subtask count was originally kept at 8 (same IDs, new content) by this amendment pass.

**Further amended 2026-09-28 (fix round 2, fresh-sweep finding AMENDMENT-FRESH-002)**: a fresh-eyes
sweep found that T003-T006 covered only the disagreeing, strict-mode, and infra-break dispositions
— FR-004's third mandatory fixture (the agreeing case) and User Story 3 Acceptance Scenario 2 had
no test, dropped when the pre-amendment `_charter_disposition` design (which had
`test_charter_disposition_is_none_on_agreement`) was replaced. Added T003b and T004b, one per
production gate function, each constructing an agreeing (`committed == collected`) fixture and
asserting via `recwarn` that zero `ShardTimingsDriftWarning` instances are recorded and the
function returns normally. WP01's subtask count is now **10** (T001, T002, T003, T003b, T004, T004b,
T005, T006, T007, T008); `dependencies`, `owned_files`, and `create_intent` remain unchanged — only
the `subtasks` frontmatter list grew.

This is reconciled against
`packs/built-in/missions/mission-steps/software-dev/tasks/guidelines.md`'s subtask-granularity
guidance: "Aim for 3–7 subtasks per WP and 200–500 lines per WP prompt. Prefer splitting an
oversized WP over padding a small one." (Note on denominator, mirroring WP02's own clarification
below: that guideline's "lines per WP prompt" wording literally means the `tasks/WPnn-*.md` prompt
document's own length — WP01's actual committed prompt file is 565 lines (`wc -l`, re-measured after
fix round 2's T003b/T004b addition), now above the 200-500 range as literally written — but
tasks.md's "estimated lines" figures for all three WPs have consistently tracked the underlying
*implementation* diff size instead, so that is the reading reconciled here, matching WP02's
denominator clarification.) WP01's subtask count (10) is three over the 3-7 guideline as literally
written. WP01 is kept at 10 subtasks — not merged down to 7, not split into two WPs — because T003
and T004 each pin one of the two now-demoted production gate functions' DISAGREEING-case fixture
(T003: `test_charter_is_not_allowlisted_and_agrees`; T004: the cross-module
`test_non_allowlisted_modules_agree_with_live_collection`), T003b and T004b each pin the same two
functions' complementary AGREEING-case fixture (FR-004's third mandatory fixture, restored in fix
round 2 after a fresh-sweep review found it dropped), and T005/T006 each cover a further distinct
disposition (strict-mode hard-fail; infra-break). Merging any of these into one subtask would
satisfy the count guideline but blur the pass/fail signal — a reviewer could confirm only that a
merged subtask as a whole passed, not that each disposition independently landed and stays correct.
Splitting into two WPs is rejected too: every one of the 10 subtasks operates on the single file
`tests/architectural/test_module_length_agreement.py` against the same already-merged mechanism, so
a second WP would either duplicate ownership of that file or carve an artificial boundary with no
real design seam behind it. Three subtasks over the guideline's aim-for ceiling, spent on keeping
each disposition (disagree/agree for both gates, strict-fail, infra-break) independently
falsifiable, is judged the smaller cost than either blurring the pass/fail signal or fragmenting
review across an artificial second WP.

Owns `tests/architectural/test_module_length_agreement.py` only. This is the **first and only** WP
to touch this file, so it carries the mandatory RED-FIRST baseline (T001) before its own edit — that
baseline now captures the post-#5240 state (see T001's amended Notes).

---

## Work Package WP02 — Recapture decision-logic script

**File**: `tasks/WP02-recapture-decision-script.md`
**Priority**: P1 (User Story 2) | **Dependencies**: none | **Parallel with**: WP01
**Requirements**: FR-005, FR-006, FR-007, FR-008, FR-009, FR-010; C-001, C-003, C-004, C-005,
C-006; NFR-003

Subtasks: T009, T010, T011, T012, T013, T014, T015 (7 subtasks). Revised line estimate, derived
from the actual artifacts rather than an assumed round number: the script itself is ~150-250 lines
(per the "PR shape recommendation" section above); the accompanying 11-fixture test file
(`tests/ci/test_recapture_charter_shard_timings.py`) is separately estimated at ~280-320 lines —
derived from the fixture list itself (T014's 6 fixtures, one with two required sub-cases, plus
T015's 5 fixtures = ~12 actual test functions), each needing setup for one or more injected fake
callables (`capture_main`, `find_open_recapture_pr`, a "would-push" spy) plus multi-line
assertions, shared imports/constants, fixture 5's two sub-cases, and fixture 11's multi-step
mutate-then-reread sequence — pushing several fixtures well past this repo's own
`tests/ci/test_stale_running_sweep.py` precedent (206 lines / 14 test functions, ~15 lines/test on
average, mostly single-assertion tests with no fake-injection setup). Combined, WP02's realistic
total is **~430-570 estimated lines** (script + test file), replacing the previously-stated flat
"~500-600," which was an unsubstantiated round number not derived from either file.

This combined figure is reconciled against
`packs/built-in/missions/mission-steps/software-dev/tasks/guidelines.md`'s subtask-granularity
guidance: "Aim for 3–7 subtasks per WP and 200–500 lines per WP prompt. Prefer splitting an
oversized WP over padding a small one." (Note on denominator: that guideline's "lines per WP
prompt" wording literally means the `tasks/WPnn-*.md` prompt document's own length — WP02's
actual committed prompt file is 448 lines (`wc -l`, freshly re-measured after this round's T011
supersession-note addition), within the 200-500
range as literally written — but
tasks.md's "estimated lines" figures for all three WPs have consistently tracked the underlying
*implementation* diff size instead, so that is the reading reconciled here, since implementation
size is what actually bears on a split-or-keep decision.) WP02's subtask count (7) is within the
3-7 guideline. Its implementation-line estimate (~430-570) sits within the 200-500 guideline at
the low end and above it at the high end. WP02 is kept as **ONE WP** despite that: every one of
the 11 fixtures exercises the same small set of pure functions (`has_drift`,
`find_open_recapture_pr`, `run_capture_or_die`, and `main()`'s orchestration sequence) —
splitting along fixture lines would force a reviewer to hold the same handful of functions' full
behavioral contract open across two separate diffs, fragmenting a review surface that is
inherently one cohesive unit. That is a real cost the guideline's "prefer splitting" default does
not price in for this specific shape (many fixtures over few functions, not many concerns over
many functions).

Owns `scripts/ci/recapture_charter_shard_timings.py` (new) and
`tests/ci/test_recapture_charter_shard_timings.py` (new). Both files are new — `create_intent`
covers both.

---

## Work Package WP03 — Scheduled workflow wiring + docs supersession note

**File**: `tasks/WP03-scheduled-workflow-wiring.md`
**Priority**: P1 (User Story 2, workflow half) / P2 (docs note) | **Dependencies**: WP02
**Requirements**: NFR-002, C-003, C-005, C-006 (workflow-file half); IC-04 (docs note)

Subtasks: T016, T017, T018, T019, T020 (5 subtasks, ~200-280 estimated lines for T016-T019; T020
adds one small, independent job to the same workflow file — see plan.md item (a2)).

**Amended 2026-09-28 (operator ruling, `reviews/amendment.ruling.md`, point 4)**: added T020, a
second, independent job in the SAME `ci-charter-shard-recapture.yml` file running the architectural
length-agreement gates under `SPEC_KITTY_STRICT_SHARD_TIMINGS=1` — the exact-count invariant's real,
scheduled, hard-failing home. This does **not** change `create_intent`/`owned_files` below (still
one workflow file plus the docs file) — only the `subtasks` list grew by one entry.

Owns `.github/workflows/ci-charter-shard-recapture.yml` (new) and
`docs/development/reference/known-friction-points.md` (edit, existing file — no `create_intent`
needed for it).

---

## Baseline discipline reminder (plan.md item (f))

**Per `NO_FULL_HEAVY_SUITES_IN_MISSION` (binding, CLAUDE.md + charter):** every test invocation in
this mission's WPs targets specific named files —
`tests/architectural/test_module_length_agreement.py` and, once WP02 creates it,
`tests/ci/test_recapture_charter_shard_timings.py` — never a bare `tests/architectural/` or
`tests/ci/` directory sweep, and never `make test-full`. WP01's T001 is the mandatory RED-FIRST
baseline for the one pre-existing file this mission edits; if that baseline surfaces any
pre-existing red, **T001's own task text (in `tasks/WP01-*.md`) directs the implementer to report it
to the orchestrator, not to fix it or file a GitHub issue** — filing an issue for a pre-existing
red is explicitly an ORCHESTRATOR action per plan.md item (f), never a WP task.

---

## Next steps

**Amendment note (2026-09-28)**: this design was amended per operator ruling
(`reviews/amendment.ruling.md`) to absorb PR #5240 (already merged to `main`, ahead of this
mission) and add a strict-mode CI job (WP03's new T020). WP01's and WP03's `subtasks` lists changed
(WP01: same 8 IDs, new content; WP03: grew from 4 to 5 IDs), but every WP's `dependencies`,
`owned_files`, and `create_intent` are **unchanged** from before this amendment — the
dependency/ownership graph `finalize-tasks` computes `lanes.json` from has not moved. This
amendment therefore does not, by itself, require a `finalize-tasks` re-run; the orchestrator should
still make that call explicitly rather than inferring it silently from this note.

**Fix round 2 note (2026-09-28, AMENDMENT-FRESH-002)**: WP01's `subtasks` list grew further, from 8
IDs to 10 (added T003b, T004b — the FR-004 agreeing-case fixtures), to close a fresh-sweep finding.
As with the amendment note above, `dependencies`, `owned_files`, and `create_intent` are still
unchanged, so this does not by itself require a `finalize-tasks` re-run — the orchestrator should
still make that call explicitly, and this note names it explicitly rather than leaving it implicit.

**Status as of this commit**: `finalize-tasks` has already run successfully — the committed
`lanes.json` (`computed_at: '2026-09-27T22:06:42+00:00'`, `computed_from:
'dependency_graph+ownership'`) landed in the same commit as this tasks.md and all three
`tasks/WP*.md` files. All three WP files' `requirement_refs` frontmatter fields are already
populated, and are richer than the `map-requirements --batch` payload below would have produced —
e.g. WP01 already carries `C-001`/`C-002`/`NFR-001`, WP02 already carries
`C-001`/`C-003`/`C-004`/`C-006`, WP03 already carries `C-003`/`C-005`/`C-006`, none of which the
batch payload below lists.

The only genuinely pending next step is:

1. `/spec-kitty.analyze` (mandatory gate before any WP implementation claim).

**Historical note — already executed; do not re-run unless a WP file changes:**

- `spec-kitty agent mission finalize-tasks --validate-only --mission per-pr-shard-timings-recapture-friction-01M3H7V8 --json` — superseded by the real `finalize-tasks` run below.
- `spec-kitty agent tasks map-requirements --batch '{"WP01":["FR-001","FR-002","FR-003","FR-004"],"WP02":["FR-005","FR-006","FR-007","FR-008","FR-009","FR-010"],"WP03":["NFR-002"]}' --mission per-pr-shard-timings-recapture-friction-01M3H7V8 --json` — superseded; the frontmatter already on disk is richer than this payload (see above).
- `spec-kitty agent mission finalize-tasks --mission per-pr-shard-timings-recapture-friction-01M3H7V8 --json` — already run; see the committed `lanes.json`.
