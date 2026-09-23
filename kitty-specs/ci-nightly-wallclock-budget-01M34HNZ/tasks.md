---
description: "Work package task list for CI Nightly Wall-Clock Budget (issues #4865, #4864)"
---

# Work Packages: CI Nightly Wall-Clock Budget

**Inputs**: `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/spec.md`,
`kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/plan.md` (both authoritative, committed, not
edited by this file).
**Prerequisites**: plan.md (present), spec.md (present). No `research.md`, `data-model.md`,
`contracts/`, or `quickstart.md` — plan.md's own "Project Structure" section states none apply to
this CI/YAML-and-test-file mission.

**Tests**: Included — the mission's central P2 deliverable (FR-008/NFR-003/SC-006) is a mandatory
new committed test (`tests/architectural/test_charter_shard_skew_sensitivity.py`), and the P1 half
carries a required edit to an existing architectural test file (FR-010). Explicit request per
plan.md's Red-first / revert discipline section.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). This mission
has `topology: single_branch` (`meta.json`) — one continuous lane, no `lanes.json` expected by
design, no parallel worktree split. (A `lanes.json` file did subsequently appear on disk as a
`finalize-tasks` tooling side effect unrelated to this mission's actual execution model — see
`tracer-tooling-friction.md`'s 2026-09-22 dated entry, "`finalize-tasks` (real run) writes a
`lanes.json` for a `single_branch`-topology mission...", for the full writeup; this prose describes
the mission's designed topology, not that file's incidental presence.) Every WP below is therefore
a strictly sequential link in one dependency chain, not an independently-schedulable unit; see
"Dependency & Execution Summary" for why.

**Prompt Files**: Each work package references a matching prompt file in `/tasks/` under this
mission directory.

## A note on this decomposition's shape (7 WPs, not 8)

An earlier draft of this decomposition used 8 WPs, with the Phase 0 baseline as its own leading
`execution_mode: planning_artifact` WP (feeding into WP02's campsite-clean) and PR-assembly/
evidence-recording as a trailing `planning_artifact` WP (fed by the code WPs). Running
`spec-kitty agent mission finalize-tasks --validate-only --json` against that 8-WP shape failed
with `LANE_DEPENDENCY_CYCLE`: spec-kitty's lane-computation algorithm collapses **every**
`planning_artifact` WP in a mission into one canonical `lane-planning` lane
(`src/specify_cli/lanes/compute.py`, `PLANNING_LANE_ID`), and that single lane cannot legitimately
sit both upstream of a code lane (as the baseline WP did) and downstream of the same code lane (as
the closing evidence WP legitimately must) without the lane dependency graph becoming cyclic. The
closing evidence WP's downstream position is genuinely required (NFR-006 — durable, consolidated
evidence, gathered only once the code WPs' own evidence exists); the baseline WP's upstream
position was the one that could be folded into an adjacent code WP's opening subtasks without
losing anything (a baseline record only needs to be durable, and a WP's own Activity Log already
provides that — it does not require a `kitty-specs/` file edit). This decomposition therefore
folds the Phase 0 baseline into **WP01** as its opening subtasks (T001-T003), ahead of WP01's own
campsite-clean commit (T004-T006), and keeps the PR-assembly/evidence WP as the sole
`planning_artifact` WP, positioned last (**WP07**). See
`tracer-tooling-friction.md`'s dated entry for the full defect writeup and the exact error
reproduced.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components). **Only
  WP02's T010/T011 carry `[P]`** — both are non-mutating verification commands over the same
  T009-edited file with no ordering dependency on each other; this is the one genuine intra-WP
  parallel pair this mission's decomposition found (see "Dependency & Execution Summary"). Every
  other subtask below is sequential — see "Dependency & Execution Summary" for the chokepoint
  reasoning (both Phase 1 and Phase 2 touch `.github/`, and each phase's own steps are causally
  ordered: a dispatch's real duration must exist before a timeout can be re-derived from it; a
  recapture must exist before a shard_count can be re-derived from it; a derived shard_count must
  exist before its non-vacuity can be asserted).
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks
  mark-status <Txxx> --status done`.

## Path Conventions

CI-workflow YAML mission, not a `src/`-code mission. Real touched-file set (from plan.md
"Project Structure"):
- `.github/workflows/ci-nightly.yml` — job split, timeout sizing, `needs:` update.
- `.github/ci-module-registry.yml` — `charter` row only.
- `.github/ci-shard-timings.json` — generated; regenerated only via `scripts/ci/capture_shard_timings.py`.
- `tests/architectural/test_performance_marker_guard.py` — three hardcoded job-name tests updated.
- `tests/architectural/test_charter_shard_skew_sensitivity.py` — NEW, mandatory non-vacuity test.

---

## Work Package WP01: Phase 0 Baseline + Campsite-Clean (Commit A) (Priority: P0/P1)

**Goal**: (a) Establish the mission's real pre-change baseline by running the scoped
`tests/architectural/` command plan.md names, before any functional edit lands, filing a GitHub
issue first if a pre-existing failure surfaces; then (b) remove the inert `strategy: { fail-fast:
false }` key from the EXISTING single `performance-and-e2e` job, as a distinct, behavior-
preserving commit that precedes the functional split — per charter Standing Order #2 and plan.md's
Campsite-clean decision (PLAN-GOV-001). No other change in the campsite-clean commit.
**Independent Test**: This WP's own Activity Log carries a dated baseline entry (exact command +
pass/fail counts) recorded before its `git diff` shows any edit; that `git diff` against the
parent commit then shows only the two removed `fail-fast` lines, with the job otherwise unchanged
(same three suites, same `timeout-minutes: 60`).
**Prompt**: `/tasks/WP01-baseline-and-campsite-clean.md`
**Requirement Refs**: NFR-006, SC-008 (spec-kitty's tasks-parsing regex only recognizes
FR-/NFR-/C- prefixed ids — SC- ids are not machine-parsed; NFR-006 is this WP's closest FR/NFR/C
anchor for its baseline-recording deliverable, SC-008 is kept for human traceability. See
`tracer-tooling-friction.md`.)

### Included Subtasks

T001 Run `uv run --frozen pytest tests/architectural/test_module_shard_registry.py tests/architectural/test_performance_marker_guard.py -q` on the current branch HEAD (before any mission edit) and record the exact pass/fail counts.
T002 [conditional] If any failure surfaces: apply the charter's binding Pre-existing Failure Reporting Rule — file a GitHub issue (command run, failure summary, why judged pre-existing, e.g. confirmed still red on the merge-base with `upstream/main`) BEFORE treating it as accepted baseline. Record the issue URL. Scope/dedup note: this WP's baseline covers only the two named architectural test files (`test_module_shard_registry.py`, `test_performance_marker_guard.py`) — a distinct command surface from WP04's later `capture_shard_timings.py` recapture run, so no dedup check against a WP04-filed issue applies here.
T003 Record the baseline (command, counts, issue URL if any) in this WP's own Activity Log.
T004 Before removing anything, grep-confirm no `matrix:` key exists anywhere under the
`performance-and-e2e` job body (the only thing `fail-fast` governs) — if one is found, STOP and
escalate instead of removing the key (this WP's red-first falsification check; see the WP prompt's
"Red-first / revert discipline" section). Otherwise, remove `.github/workflows/ci-nightly.yml`'s
`strategy: { fail-fast: false }` key (the two lines directly under `performance-and-e2e`'s
`timeout-minutes: 60`) — no other line touched.
T005 Confirm via `git diff` that only those two lines changed; confirm the job still exists,
still runs `performance`/`e2e`/`stress` serially, still has `timeout-minutes: 60`.
T006 Commit as a `chore(ci)`-scoped Conventional Commit (e.g. `chore(ci): remove inert fail-fast
key from performance-and-e2e (no matrix strategy)`).

### Implementation Notes

- Do not cite issue #3284 for T001/T002 — it is CLOSED and explicitly rejected as this mission's
  baseline (spec.md Correction #2).
- The campsite-clean commit (T004-T006) is a distinct, PRECEDING commit within this same WP — do
  not fold it into WP02's functional split commit. An earlier plan.md draft folded this in and was
  corrected per PLAN-GOV-001; do not repeat that mistake.
- `.github/*.yml` is outside `ruff`'s domain — no Python formatter gate applies to T004's edit.
- T001-T003 produce NO commit (baseline recording is Activity-Log-only); T004-T006 produce exactly
  one `chore(ci)` commit.

### Parallel Opportunities

- None — this is the mission's root WP; every other WP is downstream of it.

### Dependencies

- None (root WP).

### Risks & Mitigations

- Risk: mistaking a stale-venv false red (CLAUDE.md category 4) for a real pre-existing failure.
  Mitigation: re-run `uv sync --frozen --all-extras` and retry before filing the issue.
- Risk: scope creep into touching other parts of the job body during the campsite-clean edit.
  Mitigation: T005's `git diff` check is the enforcement — reject the commit if it shows any line
  beyond the two `fail-fast` lines.

---

## Work Package WP02: Split `performance-and-e2e` into Three Jobs (Commit B, FR-001-FR-005, FR-010) (Priority: P1) 🎯 MVP

**Goal**: Replace the (now campsite-clean) single `performance-and-e2e` job with three independent
jobs — `performance` (timeout 35), `e2e` (timeout 40), `stress` (timeout 90 — Stage A, a
deliberately generous MEASUREMENT-ONLY value, not final) — each keeping the existing
checkout/uv-sync/suite-step/upload-artifact/fail-loud-terminal-step shape and the exit-0/exit-5-
skip/fail-loud convention; update `nightly-summary`'s `needs:` list and echoed report step to
name all three; update the three `test_performance_marker_guard.py` tests that hardcode
`"performance-and-e2e"` (FR-010) to the new job names.
**Independent Test**: `grep` inside any one new job's `steps:` finds exactly one `uv run --frozen
pytest -m` marker selection (never more than one suite per job); `uv run --frozen pytest
tests/architectural/test_performance_marker_guard.py -q` passes all five tests (the two
pull_request-trigger-detection tests unchanged in behavior, plus the three updated tests now
passing against the new job names).
**Prompt**: `/tasks/WP02-split-performance-e2e-stress.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-010, NFR-001, NFR-005, C-001, C-005

### Included Subtasks

T007 Replace the single `performance-and-e2e` job with three jobs (`performance` timeout 35, `e2e`
timeout 40, `stress` timeout 90 Stage A) in `.github/workflows/ci-nightly.yml`, each preserving
`env:` (`SPEC_KITTY_RUN_PERFORMANCE`/`PWHEADLESS` only where the suite needs it), checkout, `uv
sync --frozen --all-extras`, its own `-m <marker>` suite step, artifact upload, and the terminal
`if: always()` fail-loud step (exit 0 and exit 5 both non-failing).
T008 Update `nightly-summary`'s `needs:` list (currently `[performance-and-e2e,
interpreter-matrix, full-module-matrix]`) to `[performance, e2e, stress, interpreter-matrix,
full-module-matrix]`, and its echoed report step to print a result line for each of the three.
T009 Update `tests/architectural/test_performance_marker_guard.py`'s three hardcoded-job-name
tests (`test_nightly_suite_steps_are_fail_loud`,
`test_nightly_fail_loud_step_treats_marker_empty_exit_5_as_non_failing`,
`test_nightly_workflow_houses_performance_and_interpreter_jobs`) to iterate/assert against
`performance`, `e2e`, `stress` instead of the literal `"performance-and-e2e"`. Leave
`"interpreter-matrix"` unchanged where shared.
T010 [P] Run `uv run ruff format --check tests/architectural/test_performance_marker_guard.py`.
T011 [P] Run `uv run --frozen pytest tests/architectural/test_performance_marker_guard.py -q` and
confirm all five tests pass — specifically confirm
`test_nightly_workflow_never_triggers_on_pull_request` and
`test_no_pull_request_workflow_selects_performance_or_interpreter_jobs` still pass with zero new
violations (C-001/FR-005's actual falsification mechanism for this WP).
T012 Commit as a `feat(ci)`-scoped Conventional Commit covering FR-001-FR-005/FR-010 together
(one functional commit; the guard-test edit is folded in per plan.md's explicit reasoning — it is
the only diff-cover-measurable Python edit paired with this behavior change).

### Implementation Notes

- Stage A's `stress` timeout of 90 is NOT the shipped value — WP03 unconditionally re-derives it
  from real dispatch data. Do not "tune" it here; use 90 exactly, per plan.md's "Real evidence
  used to size the new budgets."
- `performance` (35) and `e2e` (40) ARE the shipped values — both are derived from real,
  completed step durations already pulled via `gh run view 35683539593 --json jobs`
  (`performance` 23m41s, `e2e` 24m44s; plan.md table).
- FR-010's edit is in-scope maintenance of a stale literal, not evidence of a `pull_request`-
  trigger regression (spec.md AC4). Do not treat T009's expected test-file diff as a red flag.

### Red-first / revert discipline (per plan.md, stated concretely for this WP)

A pytest RED is structurally impossible for a live GitHub-Actions job-topology claim — a pytest
process parses YAML, it cannot observe a live Actions run's job list. The falsification mechanism
for THIS WP's claim (three independent jobs actually exist and report independently) is WP03's
pre-merge `workflow_dispatch`, using the ALREADY-CITED run `35683539593` (2026-09-22, one blended
`performance-and-e2e` verdict, `cancelled`) as the "red" baseline — no fresh revert-and-redispatch
cycle is needed, that run already IS the red state. The post-split dispatch in WP03 is the
"green." What THIS WP's own pytest run (T011) DOES prove, and is real: no `pull_request` trigger
was introduced by the split (C-001/FR-005), which a pytest process genuinely CAN observe.

### Parallel Opportunities

- T010/T011 are `[P]` relative to each other — both are non-mutating verification commands over
  the same T009-edited file with no ordering dependency between them; both depend only on T009.
  T007/T008 (same file) and T009 (dependent test) remain sequential by construction.

### Dependencies

- WP01 (functional split builds on the campsite-clean job body; performing it before Commit A
  would carry the dead key forward into all three new jobs — and the mission's baseline must be
  recorded before any functional edit).

### Risks & Mitigations

- Risk: `nightly-summary`'s `needs:` update silently drops one of the three names.
  Mitigation: T011's guard-test run plus WP03's dispatch both independently observe all three
  job names.
- Risk: a suite-step's `SPEC_KITTY_RUN_PERFORMANCE=1` env var is dropped from the `performance`
  job specifically during the split (only that job needs it). Mitigation: T007 explicit callout.

---

## Work Package WP03: Pre-Merge Dispatch Evidence + Unconditional Stress-Timeout Re-Derivation (Stage A/B) (Priority: P1)

**Goal**: Dispatch `ci-nightly.yml` on this branch (`mode: full`) to get the first live evidence
that the split actually produces three independent job verdicts and that `stress` can complete
under Stage A's generous 90-minute ceiling; then UNCONDITIONALLY re-derive `stress`'s tightened,
FINAL production `timeout-minutes` (Stage B) from its real completed duration, following the
bounded `90 -> 150 -> 300` widen-retry ladder if Stage A itself truncates.
**Independent Test**: A recorded dispatch run URL shows `performance`/`e2e`/`stress` as three
independent job conclusions (none blended), `stress`'s conclusion is `success`/`failure` (never
`cancelled`), and `out/reports/xunit-nightly-stress.xml` exists in its artifact; `ci-nightly.yml`'s
`stress` job now carries a `timeout-minutes` value re-derived from that real completed duration
(differing from both `60` and Stage A's `90` unless the re-derivation genuinely lands there).
**Prompt**: `/tasks/WP03-dispatch-evidence-stage-b.md`
**Requirement Refs**: FR-002, FR-009, NFR-001, NFR-002, NFR-006, C-001

### Included Subtasks

T013 Dispatch: `gh workflow run ci-nightly.yml --ref issue-4865-ci-nightly-wallclock-budget -f
mode=full`. Capture the run URL.
T014 Once the run completes, capture each of `performance`/`e2e`/`stress`'s job conclusions,
`stress`'s actual COMPLETED job duration (not just its conclusion — Stage B re-derives from this
number), and confirm `out/reports/xunit-nightly-stress.xml` exists in the `stress` job's uploaded
artifact (not assumed from a bare "success").
T015 [conditional — only if T014's `stress` conclusion is `cancelled`/truncated inside the 90-
minute Stage A ceiling] Re-dispatch with `stress`'s `timeout-minutes` widened to 150 (widen
attempt 1, its own small `chore(ci)` commit to `ci-nightly.yml`); if still truncated, widen to 300
(widen attempt 2, final ceiling — at most two widen attempts total, staying under GitHub Actions'
360-minute per-job ceiling for hosted runners). Record each widen dispatch's own run URL and job
conclusion.
T016 [conditional — only if T015's final 300-minute ceiling is ALSO exceeded] This is a genuine
test-suite hang/deadlock, not a sizing problem: do not widen further. Apply the charter's
Pre-existing Failure Reporting Rule (file the issue) using plan.md's specific confirmation-method
caveat for this case (the standard `upstream/main` pre-existing confirmation does not transfer,
since `stress` is never isolated long enough to hang or complete on `upstream/main` today —
describe it honestly as "a suite that could not be shown to complete within a generous, newly-
isolated budget" and escalate to the operator instead of continuing the ladder).
T017 Unconditionally (regardless of whether Stage A's 90 minutes happened to be sufficient in
T014): re-derive `stress`'s tightened FINAL production `timeout-minutes` from the real completed
duration captured in T014 (or the widen attempt that succeeded), using the same ~1.5x-headroom
method already used for `performance`/`e2e`. Edit `ci-nightly.yml`'s `stress` job with the
derived value.
T018 Commit the Stage B re-derivation as its own `fix(ci)` commit, SEPARATE from WP02's Commit B
and from any widen-retry commit from T015.
T019 Confirm (re-run) `tests/architectural/test_performance_marker_guard.py`'s two
pull_request-trigger-detection tests still pass against the final `stress` timeout value — the
timeout number itself is outside what those tests check, but this closes the loop that no
trigger-shape regression crept in across T015/T017's edits.

### Implementation Notes

- T016's escalation is a STOP condition, not a subtask that "completes" T017-T019 — if T016
  triggers, this WP's remaining subtasks (T017-T019) do not proceed until the operator resolves
  the escalation.
- Record every dispatch this WP performs (T013, and each of T015's widen attempts if any) — WP07
  consolidates all of them into the PR description per NFR-006; this WP's own job is to make sure
  each one's run URL + duration + conclusion is captured in this WP's own Activity Log as it
  happens (do not defer capturing it to "later," it will not be recoverable from the dispatch
  UI indefinitely).

### Parallel Opportunities

- None — T017 (Stage B re-derivation) causally depends on T014's (or T015's) real completed
  duration; it cannot be computed before that duration exists.

### Dependencies

- WP02 (the three-job split must exist before it can be dispatched and observed).

### Risks & Mitigations

- Risk: treating Stage A's 90-minute success as license to skip Stage B ("it worked, ship it").
  Mitigation: T017 is explicitly unconditional per plan.md — Stage A's 90 is never itself the
  shipped value.
- Risk: losing track of which of possibly three dispatches (90/150/300) actually produced the
  duration Stage B used. Mitigation: T014/T015 both require recording the duration inline, not
  after the fact.

---

## Work Package WP04: Recapture `charter` Shard Timings (Phase 2a, NFR-004) (Priority: P2)

**Goal**: Run the one sanctioned producer, `scripts/ci/capture_shard_timings.py --module charter
--write`, as its own explicit, budgeted step (~110 minutes serial wall-clock) — never folded into
"edit a YAML number" — and confirm the recapture succeeded before any downstream re-derivation
work begins.
**Independent Test**: `.github/ci-shard-timings.json`'s `module_capture_provenance["charter"]` is
populated (not `None`), matching the shape of the existing `auth` reference record, with
`exit_code == 0`.
**Prompt**: `/tasks/WP04-recapture-charter-timings.md`
**Requirement Refs**: FR-006, NFR-004, C-002, C-003, SC-005

### Included Subtasks

T020 Run `scripts/ci/capture_shard_timings.py --module charter --write` from the repo root (budget
~110 minutes serial execution — this is its own step, per NFR-004, not silently absorbed into
WP05's registry edit).
T021 Confirm `module_capture_provenance["charter"]` is populated (`run_id`, `command`,
`captured_at`, `test_dirs`, `selection`, `unique_tests_measured`, `exit_code`, `producer`) and
`exit_code == 0`, matching the shape of the existing `auth` record (SC-005).
T022 [conditional] If `exit_code != 0`, or if the capture run itself surfaces a test failure/error:
first check whether WP01's Activity Log already recorded an issue for a related failure — file a
new issue only if this capture's failure is genuinely distinct, to avoid a duplicate filing.
Otherwise apply the charter's Pre-existing Failure Reporting Rule (file the GitHub issue, command
run, failure summary, why pre-existing) before treating it as accepted baseline or proceeding to
WP05.
T023 Commit the regenerated `.github/ci-shard-timings.json` as its own commit (e.g. `chore(ci):
recapture charter shard timings via capture_shard_timings.py`).

### Implementation Notes

- `scripts/ci/capture_shard_timings.py` is READ and RUN only — never edited (C-002; plan.md
  Seam/layering).
- Only `charter` is recaptured. The other 13 stale modules (`agent`, `cli`, `core_misc`,
  `execution_context`, `glossary`, `kernel`, `lanes`, `missions`, `next`, `post_merge`, `release`,
  `review`, `upgrade`) are explicitly OUT OF SCOPE (C-003) — do not recapture them "while the tool
  is warm." No follow-up issue is filed for that broader gap per the project's standing rule; it
  is recorded in `tracer-design-decisions.md` already and ledgered by the orchestrator at mission
  exit.

### Parallel Opportunities

- None — this is the mission's cost chokepoint; see "Dependency & Execution Summary."

### Dependencies

- WP03 (Phase 1's full evidence cycle — including the dispatch, not merely the code split — must
  land first; plan.md's own reasoning is that the cheaper Phase 1 evidence cycle should de-risk
  the branch before the ~110-minute Phase 2 cost is paid. This is a genuine chokepoint: both
  phases touch `.github/`, and Phase 2's registry edit is only meaningful once Phase 1's dispatch
  evidence exists and this recapture completes).

### Risks & Mitigations

- Risk: an agent times out or is interrupted mid-capture (110 minutes is long for a single tool
  call). Mitigation: run via a backgroundable/non-interactive invocation; do not treat an
  incomplete capture as a partial success — re-run to completion.

---

## Work Package WP05: Re-Derive `charter`'s `shard_count` (Phase 2b, FR-007/SC-007) (Priority: P2)

**Goal**: Using the recaptured, fixture-aware `module_test_durations["charter"]` from WP04, derive
`charter`'s `shard_count` via the EXISTING `test_inter_shard_skew_within_twenty_percent` gate's own
`_lpt_bin_pack`/`_skew_of` method (read-only; not the rejected `349b73fc0` wall-clock÷target
heuristic), and edit `.github/ci-module-registry.yml`'s `charter` row with the derived value plus
a derivation-basis comment.
**Independent Test**: The `charter` row's `shard_count` and its comment are traceable to a genuine
LPT-derived computation from the recaptured data (not the prior `5` left unchanged by default, and
not a wall-clock÷target guess) — traceable via T024's full candidate-trace Activity Log entry,
independently reproducible by a reviewer.
**Prompt**: `/tasks/WP05-rederive-charter-shard-count.md`
**Requirement Refs**: FR-007, C-002, C-004, SC-007

### Included Subtasks

T024 Compute `charter`'s LPT-derived `shard_count` by feeding the recaptured
`module_test_durations["charter"]` through `tests/architectural/test_module_shard_registry.py`'s
`_lpt_bin_pack`/`_skew_of` helpers (import/consume only — that file is NOT edited by this WP),
mirroring the method already correctly used for `auth` et al. Record the FULL derivation trace in
this WP's Activity Log — every candidate `shard_count` tried and its computed skew, not only the
final chosen value — so a reviewer can independently reproduce the identical result; this trace IS
this WP's own falsification mechanism, distinct from WP06's non-vacuity test (see WP05's prompt
Test Strategy).
T025 Edit `.github/ci-module-registry.yml`'s `charter` row `shard_count` (currently `5`, line
~151) to the derived value, and add a derivation-basis comment analogous to the existing
`agent`/`upgrade` rows' comment style — but stating the genuine LPT derivation basis, not their
rejected heuristic's framing. Touch ONLY the `charter` row (C-004 — locality of change; the four
disposition-ledger comments elsewhere in this file and the
`tests/e2e/test_worktree_owned_root_concurrency.py:377` comment are explicitly OUT of this diff).
T026 Re-check PR #4886's status: `gh pr view 4886`. Confirm it still only touches
`.github/ci-module-registry.yml`'s unrelated `core_misc` row (per plan.md's "Known collision — PR
#4886" section — reference that resolution approach, do not re-derive it). If #4886 has merged
first, re-apply this WP's `charter`-row-only diff on top of the updated upstream file and
hand-verify via `git diff` that only the `charter` row changed before proceeding.
T027 Commit as a `fix(ci)`-scoped Conventional Commit touching only the `charter` row (e.g.
`fix(ci): re-derive charter shard_count from recaptured timings`).

### Implementation Notes

- The outcome (shard_count higher, lower, or unchanged at 5) is ALL acceptable per spec.md's Edge
  Cases — what matters is that it is genuinely LPT-derived from the recaptured data, not chosen to
  match the old value.
- A clean merge with PR #4886 is NOT assumed (spec.md Edge Cases; plan.md "Known collision").

### Parallel Opportunities

- None.

### Dependencies

- WP04 (the recaptured `module_test_durations["charter"]` this WP derives from must exist first —
  re-deriving from stale/near-uniform pre-recapture data would repeat the exact defect this
  mission closes).

### Risks & Mitigations

- Risk: silently reusing the `agent`/`upgrade` rows' wall-clock÷target heuristic "for consistency
  with their comment style." Mitigation: T024 explicitly restricts the derivation method to the
  LPT helpers; the heuristic is C-002-rejected as a precedent for this mission.
- Risk: PR #4886 merges mid-WP and the registry file conflicts. Mitigation: T026's explicit
  re-check-and-reapply step.

---

## Work Package WP06: Non-Vacuity Spot-Check + Mandatory Committed Test (Phase 2c/2d, PLAN-VERIFY-001/002) (Priority: P2)

**Goal**: Prove `test_inter_shard_skew_within_twenty_percent` can now actually fail for `charter`
— first via a documented ad-hoc spot-check (skew at the derived `shard_count` vs. skew at a
pre-declared, collision-free deliberately-wrong `shard_count`), then via a durable, CI-re-runnable
committed test, `tests/architectural/test_charter_shard_skew_sensitivity.py` (NEW), which
plan.md elevates from spec.md's "optional" framing to a MANDATORY plan-level requirement
(PLAN-VERIFY-002) per charter Standing Order #5 ("a gate-unmask cannot self-validate").
**Independent Test**: The new test passes locally against the real recaptured data, asserting
`charter`'s recomputed skew at its derived `shard_count` is non-zero and above a concrete floor;
`test_module_shard_registry.py` itself still passes unmodified.
**Prompt**: `/tasks/WP06-non-vacuity-spot-check-and-test.md`
**Requirement Refs**: FR-008, NFR-003, SC-006, C-005

### Included Subtasks

T028 Run the documented ad-hoc spot-check (not committed — a supplementary illustration alongside
the committed test in T029): import `_lpt_bin_pack`/`_skew_of` and the recaptured
`module_test_durations["charter"]`, compute (a) skew at `charter`'s genuinely LPT-derived
`shard_count` from WP05 (expect: <=20%, passing) and (b) skew at the PRE-DECLARED, collision-free
deliberately-wrong `shard_count` — `max(2, derived_shard_count // 2)` for every
`derived_shard_count >= 3`, or `derived_shard_count * 2` when `derived_shard_count == 2` (the one
case where the plain `// 2` form degenerates to a no-op; also excludes `shard_count == 1`, which
`_skew_of` always reports as exactly `0.0`, and excludes any value within 1 of
`len(module_test_durations["charter"])`). Expect: >0%, plausibly >20%. Record both commands and
both numeric outputs verbatim.
T029 Write `tests/architectural/test_charter_shard_skew_sensitivity.py` (NEW — does not exist
before this WP), importing `_lpt_bin_pack`/`_skew_of` from `test_module_shard_registry.py` (that
file stays read-only) plus the recaptured `module_test_durations["charter"]`, asserting `charter`'s
own recomputed skew at its derived `shard_count` is non-zero and above a concrete floor (e.g.
`>1%`, tightened once the real recaptured number from T028 is known).
T030 Run `uv run ruff format --check tests/architectural/test_charter_shard_skew_sensitivity.py`.
T031 Run `uv run --frozen pytest tests/architectural/test_charter_shard_skew_sensitivity.py -q`
and confirm it passes (GREEN) against the real recaptured data.
T032 Run `uv run --frozen pytest tests/architectural/test_module_shard_registry.py -q` and confirm
the gate itself still passes post-recapture (its aggregate `checked_multi_shard >= 1` condition is
not, by itself, proof `charter` specifically became non-vacuous — that is what T028/T029 prove).
T033 Commit the new test file as `test(ci): add charter shard skew non-vacuity test`.

### Red-first / revert discipline (concrete, for this WP)

**RED before this WP**: `tests/architectural/test_charter_shard_skew_sensitivity.py` does not
exist before T029 — there is no test to run, and if one existed against the PRE-recapture data it
would assert nothing meaningful (the near-uniform ~0.098s-mean durations make every `shard_count`
from 1 to 4211 report ~0% skew, so any non-vacuity assertion would be vacuously true or would
never have been written honestly in the first place). **GREEN after**: T031's run asserts a real,
non-zero, `shard_count`-sensitive skew against the recaptured data from WP04. This is the genuine
pytest-RED-then-GREEN story for this WP — unlike WP02/WP03's live-topology claims, this WP's
central claim IS pytest-observable.

### Implementation Notes

- `test_module_shard_registry.py` is consumed (imported from), never edited — this WP does not
  change the gate, it proves the gate is no longer vacuous for `charter`.
- The wrong-`shard_count` rule in T028 is PRE-DECLARED in plan.md BEFORE any real skew number was
  known — do not adjust it post-hoc to produce a convenient result.

### Parallel Opportunities

- None — T029 depends on T028's derivation groundwork; T031/T032 depend on T029/T030.

### Dependencies

- WP05 (this WP asserts against `charter`'s derived `shard_count`, which WP05 computes and writes
  to the registry row — deriving it independently a second time here risks a second, possibly
  divergent, computation).

### Risks & Mitigations

- Risk: the concrete floor in T029's assertion (`>1%`) turns out too tight or too loose once the
  real recaptured skew is known. Mitigation: T028's spot-check runs FIRST and reports the real
  number, so T029's floor is calibrated against real data, not guessed blind.

---

## Work Package WP07: PR Assembly & Evidence Recording (Phase 3, NFR-006) (Priority: P1)

**Goal**: Gather a follow-up `workflow_dispatch` for User Story 2's AC4 (`full-module-matrix`'s
`charter` shards, post-recapture), consolidate every prior WP's evidence (every dispatch run URL +
job conclusions, the widen-retry commit hash(es) if any, the SC-006 spot-check command+output, the
new test's pass result, the Phase 0 baseline, any filed pre-existing-failure issue URLs, and the
scoped test commands run) into a durable record, and assemble/open the PR.
**Independent Test**: `tracer-approach.md` carries a consolidated "Evidence Summary" section
covering every item NFR-006 requires; the PR description (or the dedicated review-evidence
location it points to) is durable, not a verbal claim.
**Prompt**: `/tasks/WP07-pr-assembly-evidence.md`
**Requirement Refs**: FR-009, NFR-006, SC-001, SC-002, SC-003, SC-004, SC-005, SC-006, SC-007, SC-008, C-006, C-007

### Included Subtasks

T034 Using the same or a follow-up `workflow_dispatch` (`mode: full`) run after WP05's registry
edit has landed, inspect `full-module-matrix`'s `charter` shards for per-shard wall-clock
(visible in the run's job list) — satisfies User Story 2's AC4. Compare against the pre-fix
27m20s/27m41s/17m37s/21m13s/16m22s spread; record whether the long pole is no worse than before
and, ideally, more balanced.
T035 Assemble a consolidated "Evidence Summary" appended to `tracer-approach.md`: every dispatch
run's URL + conclusions (WP01's baseline, WP03's Stage A dispatch, any widen attempts, this WP's
follow-up dispatch), `stress`'s two-stage sizing narrative (Stage A `90` measurement-only, Stage
B's derived final value + its commit hash), any widen-retry commit hash(es), WP06's spot-check
command+output and the new test's pass result, any filed pre-existing-failure issue URL(s), and
the scoped test commands run (per CLAUDE.md §6 Test policy).
T036 In the same evidence assembly, note plan.md's "Blast radius" finding verbatim (unverified-
but-likely-low-risk external consumers of the literal `performance-and-e2e` job name in
`team-kitty-missions`/`muster-missions`, not directly searchable from this checkout) and PR
#4886's collision-handling note (reference plan.md's "Known collision" section, do not
re-derive), plus C-006/C-007 gate awareness (diff-cover has nothing to score for the YAML/JSON
files in this diff; `sonar-pr` is reported, not required).
T039 [Detect-and-escalate, read-only] Immediately before pushing/opening the PR: re-run `gh pr view
4886` and re-confirm via `git diff` (against current `main`) that `.github/ci-module-registry.yml`'s
`charter` row is the only row this mission's branch has touched relative to upstream. WP07 does
not own this file (its `owned_files` is `tracer-approach.md` only; WP05 exclusively owns
`.github/ci-module-registry.yml`) — if #4886 has merged in the interim AND the registry has
genuinely diverged, this subtask HALTS WP07 and reports the divergence (what changed, since when,
the `git diff` evidence) to the orchestrator/operator, who dispatches a fresh fix as separate work.
No WP is reopened, no `move-task --force`, no terminal-lane transition, and no cross-WP ownership
change of any kind — WP07's role ends at detection and escalation.
T037 Push the branch (if not already pushed) and open the PR targeting `main` per the charter's
Programme PR Workflow (`git checkout -b issue-<n>-<slug>` is not needed here — this mission
already IS on its `issue-4865-ci-nightly-wallclock-budget` branch per meta.json's
`single_branch` topology), using the T035/T036 evidence as the PR body content. Do not merge —
the operator/fleet owns that step.
T038 Confirm the final commit history reads as clean, single-purpose Conventional Commits (per
this mission's own campsite-clean/functional/re-derivation split across WP01-WP06) before
requesting review.

### Implementation Notes

- This WP does NOT merge the PR — implementers never merge (charter, Agent Operating Discipline /
  Git & workflow discipline #7).
- If the mission scaffold's auto-commit (`2c9f9ef38`, spec.md Correction #8) is still present in
  history at this point, handling it is this WP's PR-prep concern per plan.md — not an earlier
  WP's.
- This is the mission's sole `execution_mode: planning_artifact` WP, deliberately positioned last
  (downstream of every code WP) — see "A note on this decomposition's shape" above for why.

### Parallel Opportunities

- None — this WP is the mission's closing synthesis; it depends on every prior WP's evidence.

### Dependencies

- WP03 (Phase 1 dispatch evidence)
- WP05 (registry re-derivation, needed before the follow-up dispatch in T034 is meaningful)
- WP06 (spot-check + test evidence)

### Risks & Mitigations

- Risk: assembling the PR description from memory instead of each WP's actual recorded Activity
  Log / evidence, producing a "confident summary" the charter's Standing Orders throughline
  specifically warns against. Mitigation: T035 explicitly sources every item from a prior WP's
  own recorded evidence, not from re-deriving or re-estimating any of it.

---

## Dependency & Execution Summary

**Chain (fully linear — no parallel-safe WPs)**:

```
WP01 (baseline + campsite-clean, Commit A)
  -> WP02 (functional split, Commit B)
    -> WP03 (dispatch evidence + Stage A/B re-derivation)
      -> WP04 (charter recapture, ~110 min)
        -> WP05 (charter shard_count re-derivation)
          -> WP06 (spot-check + non-vacuity test)
            -> WP07 (PR assembly + evidence)
```

**Why none of these WPs are marked parallel-safe.** This mission has `topology: single_branch`
(`meta.json`) — a single continuous lane, not a lanes/multi-worktree split — so there is no
concurrent-agent scenario to protect against in the first place. But even setting topology aside,
the WPs are genuinely causally ordered, not merely sequenced for convenience:

- **Standing Order #2 ordering**: WP01's campsite-clean sub-scope must precede WP02's functional
  split — an opening campsite-clean is a distinct, behavior-preserving step that precedes the
  functional change, per the charter's "Reconciling change-scope tensions" section.
- **Evidence-before-cost chokepoint (the mission's central sequencing constraint)**: Both Phase 1
  (WP01-WP03) and Phase 2 (WP04-WP06) touch `.github/` — WP01/WP02/WP03 edit
  `.github/workflows/ci-nightly.yml`; WP04/WP05 edit `.github/ci-shard-timings.json` and
  `.github/ci-module-registry.yml`. This is not incidental — it serialises the mission's own
  commits regardless of how the WPs are drawn, because **WP04's registry-feeding recapture is
  only meaningful once WP03's dispatch evidence exists** (there is no point re-deriving a
  shard_count from fresh timings while the job-split half of the mission is still unproven) **and
  because Phase 1's cheaper evidence cycle (a `workflow_dispatch`, minutes) is deliberately paid
  before Phase 2's expensive one (~110 minutes serial, NFR-004) to de-risk the branch first** —
  plan.md's own stated reasoning for the phase order. You cannot commit Phase 2's registry edit
  concurrently with Phase 1's workflow edit in any meaningful sense.
- **Data-before-derivation chokepoints within Phase 2**: WP05 cannot derive `shard_count` before
  WP04's recapture exists (deriving from stale near-uniform data would repeat the exact defect
  #4864 exists to fix); WP06 cannot assert non-vacuity of a `shard_count` WP05 has not yet
  computed.
- **Evidence-before-assembly**: WP07 needs every prior WP's recorded evidence to assemble a
  truthful PR description, not a summary written from the assembler's expectations.

**A note on subtask-level parallelism** (considered separately from the WP/topology-level analysis
above). The absence of any parallel-safe WP does not mean no subtask-level independence exists
within a WP — that question was checked separately. WP02's T010 (`ruff format --check`) and T011
(the guard-test pytest run) are the one genuine case found: both are non-mutating verification
commands over the same T009-edited file with no ordering dependency on each other, so both carry
`[P]`. No other subtask pair in this mission's decomposition was found to be independent this way.

**PR-touching-`.github/ci-module-registry.yml` collision (open PR #4886) — two-checkpoint
design.** WP05 is the SOLE WP that edits the `charter` row — the only WP whose frontmatter
declares `.github/ci-module-registry.yml` in `owned_files`/`authoritative_surface`. WP07 never
edits this file directly and never reopens WP05. PR #4886 (open) also touches this file, but only
its unrelated, distant `core_misc` row (`test_dirs` addition) — low collision risk, but a clean
merge is **not assumed**. The two checkpoints guard the window between WP05's commit and the
eventual push, and they are deliberately asymmetric in what each is allowed to do: (1) **WP05's
own T026**, mid-mission, checks the collision status and, if #4886 has already merged by then,
re-applies the `charter`-row diff itself as part of WP05's own commit — WP05 can still edit at
this point, because it has not yet closed; (2) **WP07's T039**, pre-push, read-only (`gh pr view`
+ `git diff` only, no file edit, ever) and detect-and-escalate only — it re-checks immediately
before push/PR-open, the highest-risk moment, since a large window can elapse between WP05 closing
and WP07's actual push per plan.md's worst-case wall-clock accounting, but by the time T039 runs
WP05 is realistically `done` (a terminal lane in this mission's WP state machine) and nothing
reopens it. If T039 finds #4886 merged AND the registry genuinely diverged since WP05's check, it
HALTS WP07 and reports the divergence (the `git diff` evidence, what changed, since when) to the
orchestrator/operator, who dispatches a fresh fix as separate work — never a `move-task --force`,
a terminal-lane transition, or an in-WP repair of any kind. (plan.md's "Known collision — PR
#4886" section states the resolution approach; WP05's T026 references it directly rather than
re-deriving it.)

**A structural note on `execution_mode` placement (tooling-driven, see "A note on this
decomposition's shape" above).** `WP07` is the mission's only `execution_mode: planning_artifact`
WP, and it is deliberately the LAST WP in the chain. spec-kitty's lane-computation collapses every
`planning_artifact` WP into one canonical lane, which cannot sit both upstream and downstream of
the same code lane without a `LANE_DEPENDENCY_CYCLE` — so this mission's only durable-evidence
file-edit (`tracer-approach.md`) happens at the end, and the Phase-0-baseline's evidence (which
would otherwise need a similar file edit at the START) is instead recorded in WP01's own Activity
Log rather than a `kitty-specs/` file, avoiding the conflict entirely.

## PR-shape judgment: ONE PR for the whole mission (not a per-WP split)

This mission stays with spec-kitty's default mission shape — **one PR** — not tk's
one-PR-per-WP rule. `meta.json` declares `"topology": "single_branch"` with no `lanes.json`
expected by design (see the Organization section above and `tracer-tooling-friction.md`'s dated
entry for why a `lanes.json` file nonetheless exists on disk as an unrelated tooling side effect),
and plan.md's own Phasing section states this explicitly ("One PR (spec-kitty's default mission
shape... this mission has no `lanes.json`/WP split)"). Restated and affirmed here as a real
decision, not boilerplate: even after this WP decomposition, the mission's real file surface stays
small and concentrated — exactly two workflow/registry YAML files, one generated JSON artifact
regenerated by its one sanctioned producer, one existing test file with a bounded 3-test edit, and
one new, narrowly-scoped test file. No `src/**` production code is touched. A reviewer reading the
final diff in one sitting is reading: a two-line dead-key removal, a job-topology restructuring
that is mechanically comparable line-for-line against the old single job, a timeout-value change,
a registry row plus a comment, and two test files. The mission's real cost driver — the ~650-
minute worst-case cumulative wall-clock plan.md flags (Stage A/B widen ladder + the ~110-minute
recapture) — is dispatch-WAIT time, not diff volume, and does not make the diff itself harder to
review; it makes the mission take longer to reach a reviewable state, which is a scheduling
concern, not a reviewability concern. **Recommendation: keep the single-PR shape.** If a future
reviewer disagrees once the real diff is in hand (e.g., if the widen-retry ladder's contingency
commits turn out to add material width), splitting by phase (Phase 1 PR, Phase 2 PR) is
mechanically straightforward given the WP boundaries above, since WP03 and WP06 are natural phase
boundaries — but that is not this decomposition's recommendation.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP02 |
| FR-002 | WP02, WP03 |
| FR-003 | WP02 |
| FR-004 | WP02 |
| FR-005 | WP02 |
| FR-006 | WP04 |
| FR-007 | WP05 |
| FR-008 | WP06 |
| FR-009 | WP03, WP07 |
| FR-010 | WP02 |
| NFR-001 | WP02, WP03 |
| NFR-002 | WP03 |
| NFR-003 | WP06 |
| NFR-004 | WP04 |
| NFR-005 | WP02 |
| NFR-006 | WP01, WP03, WP07 |
| C-001 | WP02, WP03 |
| C-002 | WP04, WP05 |
| C-003 | WP04 |
| C-004 | WP05 |
| C-005 | WP02, WP06 |
| C-006 | WP07 |
| C-007 | WP07 |
| SC-001 | WP03, WP07 |
| SC-002 | WP03, WP07 |
| SC-003 | WP02, WP07 |
| SC-004 | WP02, WP07 |
| SC-005 | WP04, WP07 |
| SC-006 | WP06, WP07 |
| SC-007 | WP05, WP07 |
| SC-008 | WP01, WP07 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Run scoped baseline pytest command | WP01 | P0 | No |
| T002 | [conditional] File pre-existing-failure issue | WP01 | P0 | No |
| T003 | Record baseline entry in Activity Log | WP01 | P0 | No |
| T004 | Remove dead fail-fast key | WP01 | P1 | No |
| T005 | Confirm git diff scoped to 2 lines | WP01 | P1 | No |
| T006 | Commit chore(ci) campsite-clean | WP01 | P1 | No |
| T007 | Split into three jobs (perf/e2e/stress) | WP02 | P1 | No |
| T008 | Update nightly-summary needs: list | WP02 | P1 | No |
| T009 | Update 3 hardcoded-job-name tests (FR-010) | WP02 | P1 | No |
| T010 | ruff format --check on edited test file | WP02 | P1 | Yes (with T011) |
| T011 | Run guard tests, confirm 5/5 pass | WP02 | P1 | Yes (with T010) |
| T012 | Commit feat(ci) functional split | WP02 | P1 | No |
| T013 | Dispatch ci-nightly.yml mode=full | WP03 | P1 | No |
| T014 | Capture 3 job conclusions + stress duration + xunit | WP03 | P1 | No |
| T015 | [conditional] Widen-retry ladder 150/300 | WP03 | P1 | No |
| T016 | [conditional] Escalate genuine hang/deadlock | WP03 | P1 | No |
| T017 | Unconditional Stage B stress re-derivation | WP03 | P1 | No |
| T018 | Commit fix(ci) Stage B re-derivation | WP03 | P1 | No |
| T019 | Re-confirm pull_request-trigger tests still pass | WP03 | P1 | No |
| T020 | Run capture_shard_timings.py --module charter --write | WP04 | P2 | No |
| T021 | Confirm provenance populated, exit_code == 0 | WP04 | P2 | No |
| T022 | [conditional] File pre-existing-failure issue | WP04 | P2 | No |
| T023 | Commit regenerated ci-shard-timings.json | WP04 | P2 | No |
| T024 | Compute LPT-derived shard_count for charter | WP05 | P2 | No |
| T025 | Edit registry charter row + derivation comment | WP05 | P2 | No |
| T026 | Re-check PR #4886 collision status | WP05 | P2 | No |
| T027 | Commit fix(ci) registry re-derivation | WP05 | P2 | No |
| T028 | Spot-check skew at derived vs. wrong shard_count | WP06 | P2 | No |
| T029 | Write test_charter_shard_skew_sensitivity.py (NEW) | WP06 | P2 | No |
| T030 | ruff format --check on new test file | WP06 | P2 | No |
| T031 | Run new test, confirm GREEN | WP06 | P2 | No |
| T032 | Confirm test_module_shard_registry.py still passes | WP06 | P2 | No |
| T033 | Commit test(ci) non-vacuity test | WP06 | P2 | No |
| T034 | Follow-up dispatch for charter shard evidence (AC4) | WP07 | P1 | No |
| T035 | Assemble consolidated Evidence Summary | WP07 | P1 | No |
| T036 | Note blast-radius + PR #4886 + gate awareness | WP07 | P1 | No |
| T039 | Re-check PR #4886 immediately before push/PR open (detect-and-escalate; HALTs + reports to operator) | WP07 | P1 | No |
| T037 | Open PR targeting main with assembled evidence | WP07 | P1 | No |
| T038 | Confirm clean, single-purpose commit history | WP07 | P1 | No |
