---
work_package_id: WP08
title: Final integration validation and tracer close-out
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
- WP06
- WP07
requirement_refs:
- NFR-002
- C-005
- FR-004
- C-003
- SC-003
- SC-004
- SC-005
planning_base_branch: issue-4213-golden-path-nfr-budget
merge_target_branch: issue-4213-golden-path-nfr-budget
branch_strategy: Planning artifacts for this mission were generated on issue-4213-golden-path-nfr-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4213-golden-path-nfr-budget unless the human explicitly redirects the landing branch.
subtasks:
- T026
- T027
- T028
- T029
history: []
agent_profile: debugger-debbie
authoritative_surface: kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/tracer-approach.md
- kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/tracer-design-decisions.md
- kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/tracer-tooling-friction.md
role: investigator
tags: []
tracker_refs: []
---

# Work Package Prompt: WP08 – Final integration validation and tracer close-out

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `debugger-debbie`
- **Role**: `investigator`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Re-run the golden-path test locally to confirm it now passes within its 120s
budget; re-run the full blast-radius baseline commands and diff the result
against WP01's recorded baseline (confirming no new red was introduced by
WP02–WP07); and update the three tracer files. This WP does **NOT** touch
`plan.md`'s "Actions Evidence Log" section and does **NOT** push to a remote or
read real GitHub Actions CI numbers — those are explicitly the orchestrator's
PR-stage responsibility, not WP-agent work.

## Context

This is the mission's closing WP, depending on WP01 (baseline artifact,
needed by T027 to diff against) and every other implementation WP
(WP02–WP07). It exists to give the orchestrator a trustworthy local signal
before opening the PR — it is NOT the mission's actual closure mechanism.
Closure per NFR-002/SC-003/Ruling 2 requires a REAL GitHub Actions `tests (e2e)`
run at ≤110s, which only exists once a PR is opened and CI runs on it — an
event this WP cannot cause or fabricate.

**Ownership split — state this explicitly, do not let it be assumed**: per
`plan.md`'s "Actions evidence path" section, sk-review's accept gate (not this
WP, not any WP-implementing agent) must positively confirm the PR's
`## Actions Evidence Log` section exists and cites a real run URL plus a
measured-seconds number before treating NFR-002/SC-003 as closed. This WP's own
local re-run is necessary evidence that the mission is READY for that real
Actions measurement — it is not a substitute for it, and nothing in this WP's
own output should be read by a later agent as if it were that real measurement.

### Subtask T026: Re-run the golden path test locally, confirm it passes in budget

**Purpose**: Confirm the fixture redesign (WP03) + freshness pre-check (WP04) +
lazy imports (WP05) together bring the golden path back under its 120s budget,
locally, as the first checkpoint before the real Actions measurement.

**Steps**:
1. Run:
   ```bash
   .venv/bin/python -m pytest tests/e2e/test_charter_epic_golden_path.py::test_charter_epic_golden_path -q
   ```
   with the real `@pytest.mark.timeout(120)` active (do not disable the
   timeout plugin — the whole point is observing the real, current budget
   behavior).
2. Record the measured local wall-clock time. Per NFR-002's own rationale, a
   local pass is necessary but explicitly NOT sufficient evidence of closure —
   state this limitation directly in your notes rather than implying a local
   pass alone satisfies SC-003.
3. If the test is still RED at this point (over budget or failing for any
   other reason), this is a genuine mission-level problem, not something to
   quietly work around in this WP — STOP and report the failure with full
   detail (which lever's expected savings did not materialize, what the actual
   measured time was) rather than declaring success. Do not touch any WP02–WP07
   `owned_files` to attempt a fix yourself; this WP's own `owned_files` is
   confined to the tracer files.

**Files**: none changed (read-only verification).
**Validation**: the test passes locally within its 120s timeout, with the
measured time recorded and explicitly caveated as "local, not the Actions
measurement SC-003 requires."

### Subtask T027: Re-run the full blast-radius baseline and diff against WP01

**Purpose**: Confirm WP02–WP07's combined changes introduced no new red beyond
what WP01 already recorded as pre-existing.

**Steps**:
1. Read WP01's recorded baseline artifact
   (`kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/research/baseline-<date>.md`).
2. Run the exact same three baseline commands from `plan.md`'s Baseline method,
   this time against the current state of THIS working tree (the mission's own
   branch, with all of WP02–WP07's changes applied):
   ```bash
   .venv/bin/python -m pytest tests/unit tests/status tests/cli tests/specify_cli/runtime -q -m "(fast or unit)"
   .venv/bin/python -m pytest tests/e2e -q
   .venv/bin/python -m pytest tests/performance -q -m "not performance"
   ```
3. Diff this run's pass/fail/skip counts and individual failing test IDs
   against WP01's recorded baseline. Classify:
   - Any failure present in BOTH WP01's baseline and this run: still
     pre-existing, unchanged — expected, not this mission's problem to fix.
   - Any failure present in this run but NOT in WP01's baseline: a NEW
     regression introduced by this mission's own changes — this blocks
     declaring the mission ready; report it in full (which command, which
     test, full failure output) rather than silently accepting it.
   - `test_charter_epic_golden_path` specifically: expected to have FLIPPED
     from `SKIPPED` (WP01's baseline) to `PASSED` (this run) — this is the
     intended outcome, not a regression.
4. Apply CLAUDE.md's baseline-red gotcha categories before concluding any new
   failure is real (stale-venv/stale-install false reds) — re-sync and re-run
   before finalizing a "new regression" classification.
5. **SC-005/C-003 mechanical check (added per post-tasks analysis, findings
   B2/C3): count the golden path's real subprocess CLI call sites, do not rely
   on "the e2e suite stayed green" alone.** SC-005 ("all 12 subprocess CLI
   invocations remain real subprocess calls against the real, source-tree
   `spec-kitty` CLI... not converted to in-process/library-level calls —
   verifies C-003 was honored, not just declared") requires an actual count,
   not an inference from a passing test. Do this by static inspection (grep or
   a short AST walk, whichever is faster to get right):
   - In `tests/e2e/test_charter_epic_golden_path.py`, count every call site
     that invokes the `run_cli` fixture's `_run_cli` helper (`tests/conftest.py:1318-1338`)
     inside the test body — confirm the count is still 12 (per C-003's own
     text) and that none of the twelve call expressions were replaced by a
     direct, in-process `specify_cli` function/module call.
   - In `tests/e2e/conftest.py`'s `fresh_e2e_project` fixture, confirm its own
     `spec-kitty init` call still goes through `run_cli_subprocess`
     (`tests/test_isolation_helpers.py:93-124`) — the same check WP03 already
     performs for its own narrower scope (see `tasks/WP03-fixture-redesign.md`),
     re-confirmed here at the whole-mission integration level.
   - Record the exact count and the grep/AST command used in this WP's tracer
     entry (T028) — a bare "tests/e2e passed" statement does not satisfy this
     check; the count itself must be stated.

**Files**: none changed (read-only verification).
**Validation**: a clear, evidence-backed statement exists of exactly which
failures (if any) are new relative to WP01's baseline, with no failure silently
dropped from consideration, AND a stated, real count of subprocess call sites
confirming SC-005/C-003 was mechanically verified, not just declared.

### Subtask T028: Update the three tracer files

**Purpose**: Close out the mission's tracer-file discipline (charter Standing
Order #3) with a final assessment pass, and record the PR-shape assessment the
orchestrator's dispatch requires.

**Steps**:
1. Append a closing entry to `tracer-approach.md` summarizing how the
   implementation phase went relative to the plan: which levers delivered
   roughly the expected savings, which did not, and why (if known).
2. Append a closing entry to `tracer-design-decisions.md` recording any
   implementation-time decisions WP02–WP07 made that were left open by
   `plan.md` (e.g. WP04's exact stamp filename/format choice, WP04's
   `__init__.py` touch-or-not decision, WP07's exact `--durations` value) —
   cite which WP made each decision and why.
3. **In `tracer-design-decisions.md`, add a new dated subsection specifically
   for the PR-shape assessment** the orchestrator's dispatch requires: state
   plan.md's existing, binding "ONE PR for the whole mission" decision (do not
   reopen or re-litigate it), then assess — given the actual WP decomposition
   this mission used — whether that one PR is reviewable in a single sitting.
   Give a rough diff-size estimate (files touched across WP02–WP07, rough
   line-count order of magnitude, drawn from each WP's actual `git diff
   --stat`) and a verdict: reviewable-as-is, or a recommendation (not a
   unilateral action) that the operator consider a split, and along which
   lines if so. This is a recommendation FOR THE OPERATOR — do not act on it
   by actually splitting the PR yourself. **This same subsection also serves
   FR-004** (one PR closes both #4213 and #4211): state plainly, in prose the
   orchestrator can lift near-verbatim into the PR description, the shared
   root cause (budget overrun, not a hang — per spec.md's Evidence section) so
   a reviewer does not need to re-derive which framing was correct. This WP
   prepares that language; it does not open the PR or write `Closes #4213`/
   `Closes #4211` anywhere itself — that remains the orchestrator's PR-stage
   action per the ownership split in T029 below.
4. Append a closing entry to `tracer-tooling-friction.md` for any tooling
   friction encountered during implementation (e.g. any CLI command that
   behaved unexpectedly, any doctrine drift discovered) — if none was
   encountered, state that explicitly rather than leaving the file's
   implementation-phase section silently blank.
5. Do **not** touch `plan.md`'s "Actions Evidence Log" section — that section
   is explicitly the orchestrator's own responsibility once a real GitHub
   Actions run exists, per `plan.md`'s own text. Do not fabricate or
   pre-populate it.

**Files**: `tracer-approach.md`, `tracer-design-decisions.md`,
`tracer-tooling-friction.md` (each appended, not rewritten — preserve all
existing content).
**Validation**: all three files have a new, dated closing entry; the
PR-shape assessment subsection exists in `tracer-design-decisions.md` with a
real diff-size estimate and an explicit reviewable-as-is-or-split verdict
stated as a recommendation, not an action taken.

### Subtask T029: State the ownership split explicitly, hand off to the orchestrator

**Purpose**: Prevent a downstream agent from assuming this WP's local
validation IS the mission's closure evidence, or from self-authorizing a push
or a real CI read that belongs to the orchestrator.

**Steps**:
1. In `tracer-approach.md`'s closing entry (T028), add an explicit statement:
   this WP's local re-run (T026, T027) is readiness evidence for opening the
   PR, not the NFR-002/SC-003 closure evidence itself; the real ≤110s Actions
   measurement, the PR's `Closes #4213`/`Closes #4211` description (FR-004/
   SC-004), and the `## Actions Evidence Log` section in `plan.md` are all
   explicitly out of this WP's scope and belong to the orchestrator's PR-stage
   work.
2. If T027 found any new regression, state it prominently and do not soften
   the finding — per the charter's "never trust a green check... verify
   against live code" throughline, a real regression found here must reach
   the orchestrator clearly, not be buried in a passing-sounding summary.
3. If T026's golden path measurement suggests the mission may not clear the
   real Actions ≤110s bar (e.g. local time is uncomfortably close to 110s
   given the historical ~12-32s local-to-CI gap NFR-002 cites), flag this risk
   explicitly rather than implying confidence the local number does not
   support.

**Files**: same tracer files as T028 (part of the same closing entries).
**Validation**: the hand-off is explicit and unambiguous about what this WP
did and did not verify.

## Definition of Done

- The golden path test passes locally within its 120s budget, with the
  measured time recorded and explicitly caveated as not the required Actions
  measurement.
- A full diff of the current blast-radius run against WP01's recorded baseline
  exists, with every new-vs-pre-existing failure explicitly classified — no
  failure silently dropped.
- The SC-005/C-003 subprocess-call-site count (T027 step 5) is recorded with
  its exact count and the command used — not inferred from a passing test
  suite alone.
- All three tracer files have new, dated closing entries.
- `tracer-design-decisions.md` contains the PR-shape assessment subsection
  with a real diff-size estimate and an explicit verdict, framed as a
  recommendation to the operator.
- `plan.md`'s "Actions Evidence Log" section is untouched.
- No push to any remote occurred, and no real GitHub Actions run was read or
  fabricated by this WP.
- Per-subtask completion is recorded via
  `spec-kitty agent tasks mark-status <Txxx> --status done` for T026–T029.

## Risks

- **Declaring success prematurely**: the strongest risk in this WP is treating
  a passing local run as if it settles NFR-002/SC-003 — it does not, and this
  WP's own text must not imply otherwise anywhere it is read.
- **Silently dropping a found regression**: per C-005 (this WP's own
  requirement_refs), silent success is forbidden mission-wide; this applies
  doubly to this closing WP, whose entire purpose is to surface exactly this
  kind of finding, not paper over it.
- **Overstepping into PR-stage work**: do not open a PR, push a branch, or
  read/cite real CI numbers from this WP — those are out of scope by explicit
  instruction, not merely by convention.

## Reviewer Guidance

Confirm the local golden-path pass is genuinely observed (not assumed), confirm
the baseline diff accounts for every failure with no silent drops, confirm the
PR-shape assessment gives a real diff-size estimate rather than a vague
qualitative statement, and confirm `plan.md`'s Actions Evidence Log section and
any push/CI-read activity are absent from this WP's diff.

Implementation command: `spec-kitty agent action implement WP08 --agent claude`
