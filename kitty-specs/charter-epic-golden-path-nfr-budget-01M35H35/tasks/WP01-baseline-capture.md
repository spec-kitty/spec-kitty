---
work_package_id: WP01
title: Baseline capture at the merge-base
dependencies: []
requirement_refs:
- NFR-002
planning_base_branch: issue-4213-golden-path-nfr-budget
merge_target_branch: issue-4213-golden-path-nfr-budget
branch_strategy: Planning artifacts for this mission were generated on issue-4213-golden-path-nfr-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4213-golden-path-nfr-budget unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
history: []
agent_profile: researcher-robbie
authoritative_surface: kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/research/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/research/**
role: researcher
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – Baseline capture at the merge-base

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `researcher-robbie`
- **Role**: `researcher`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Establish an honest pre-change baseline: run the mission's three baseline pytest
commands against the merge-base of `issue-4213-golden-path-nfr-budget` and
`origin/main` (NOT against this working tree), record pass/fail counts, and
classify every failure as pre-existing before any of this mission's own WPs make
a single code change. This WP produces the durable evidence every later WP's
"no new red" claim gets compared against.

## Context

Per `plan.md`'s "Baseline method" section and the charter's `§Pre-existing Failure
Reporting Rule`, distinguishing pre-existing red from introduced red is the WHOLE
point of this WP — it is not a formality. Every later code-change WP (WP02–WP07)
and the closing WP08 depend on this WP's recorded baseline to make their own
"nothing new went red" claim credible.

**Why WP02–WP07 do not declare a hard `dependencies: [WP01]` gate despite this**:
`spec-kitty`'s execution-lane computation places every `planning_artifact` WP
into one shared canonical lane (`lane-planning`); since this WP and WP08 are
both `planning_artifact`, a hard dependency from any code-change WP onto this
WP — combined with WP08's own dependency on those same code-change WPs — would
create a lane-dependency cycle (`lane-planning` ⇄ the code lane), which
`finalize-tasks --validate-only` rejects outright. This WP's own measurement
does not technically require the rest of the working tree to be untouched
first (it runs against an isolated worktree at a fixed merge-base SHA, never
against this checkout), so the missing hard gate does not weaken correctness —
but the orchestrator should still DISPATCH this WP first, as a process/ordering
matter, so its artifact exists before WP08 needs to diff against it.

**Hard constraint — never switch branches under this checkout.** This repository
is a single checkout shared by other concurrently-running agents on other WPs and
by the orchestrator itself ("one checkout, many agents" — never `git checkout` on
this working tree to get to the merge-base commit). Use a **separate** `git
worktree` (or a separate clone) checked out at the merge-base SHA instead.

This WP is a `planning_artifact` WP: it makes no code change. Its only output is
a durable research artifact recording the baseline measurement.

### Subtask T001: Resolve the real merge-base SHA

**Purpose**: Determine the exact commit this mission's changes are being compared
against — do not assume any cached/historical SHA is still current.

**Steps**:
1. From the repository root checkout (this one, read-only for this step):
   ```bash
   git fetch origin main
   git merge-base issue-4213-golden-path-nfr-budget origin/main
   ```
2. Record the resulting SHA. `plan.md` notes the readiness session used
   `6b4164dbf` as its checkout point, but explicitly warns this may not be the
   current merge-base if `main` has advanced — **do not assume it; use the
   command's actual output.**
3. If the resolved SHA differs from `6b4164dbf`, note the discrepancy explicitly
   in the research artifact (T004) — this is expected drift, not an error.

**Files**: none changed.
**Validation**: the recorded SHA is the literal stdout of the `git merge-base`
command, not a guess or a value copied from this prompt.

### Subtask T002: Create an isolated worktree at the merge-base

**Purpose**: Get a real, isolated checkout of the merge-base commit to run tests
against, without touching this working tree's branch or HEAD.

**Steps**:
1. Create a worktree on `/home` (NOT `/tmp` — `/tmp` is tmpfs/RAM and can evict
   large checkouts or venvs under memory pressure). Use the parent directory of
   this checkout as the worktree's home — do not hardcode any operator's home
   directory or username in this mission artifact (this repo is public):
   ```bash
   git worktree add "$(dirname "$(pwd)")/4211-baseline-<sha-short>" <merge-base-sha>
   ```
2. In that worktree, build an isolated Python environment matching this repo's
   dev setup (`uv sync --frozen --all-extras`, or reuse a hand-built `.venv` if
   `make dev-setup`'s equivalent is available) — CLAUDE.md requires the hand-built
   `.venv/bin/python`, never a bare `uv run`, for these commands.
3. Confirm the worktree's `git log -1 --oneline` shows the resolved merge-base
   SHA from T001, not this branch's HEAD.

**Files**: a new worktree directory under `/home`, outside the tracked repo tree —
not a change to any tracked file in this checkout.
**Validation**: `git -C <worktree-path> rev-parse HEAD` equals the SHA from T001.

### Subtask T003: Run the three baseline commands and record raw output

**Purpose**: Execute the exact commands `plan.md`'s Baseline method section
specifies, verbatim, and capture their full output.

**Steps**:
1. From inside the merge-base worktree, run exactly these three commands (copy
   and execute them verbatim — do not paraphrase or add/remove flags; see the
   "Transcribed commands are not runnable" lesson — always run the real command,
   never a hand-retyped approximation):
   ```bash
   .venv/bin/python -m pytest tests/unit tests/status tests/cli tests/specify_cli/runtime -q -m "(fast or unit)"
   .venv/bin/python -m pytest tests/e2e -q
   .venv/bin/python -m pytest tests/performance -q -m "not performance"
   ```
2. Capture full stdout/stderr for each command, including the final summary
   line (pass/fail/skip/error counts) and every individual failure's test ID.
3. Before treating any output as final, apply CLAUDE.md's "Test-run baseline-red
   gotcha" categories 3–4 (stale-install / stale-venv false reds) — if a failure
   looks like an import error or a `spec-kitty` CLI shell-out failure, re-sync
   (`uv sync --frozen --all-extras`, `pip install -e .` in the worktree) and
   re-run before recording it as real baseline red.

**Files**: none changed (read-only test execution).
**Validation**: each command's final summary line is captured verbatim in the
research artifact (T004), with individual failing test IDs listed, not just
counts.

### Subtask T004: Classify failures and write the research artifact

**Purpose**: Turn the raw baseline run into a durable, reviewable artifact that
every later WP's "no new red" comparison cites.

**Steps**:
1. For every failing/erroring test from T003, classify it using CLAUDE.md's
   baseline-red taxonomy (pre-existing known-P0, CI-environment, stale-install,
   stale-venv) as best you can from a local run; note explicitly that a fully
   confident pre-existing-vs-introduced classification for some failures may
   require checking `origin/main`'s own CI history, and say so if you cannot be
   fully certain.
2. Write `kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/research/baseline-<YYYY-MM-DD>.md`
   containing: the resolved merge-base SHA (T001), the three exact commands run,
   full pass/fail/skip counts per command, the list of individual failing test
   IDs with your classification and reasoning for each, and an explicit statement
   that `test_charter_epic_golden_path` is expected to be `SKIPPED` (not
   pass/fail) at this baseline commit, since the skip decorator this mission
   removes (FR-001/C-004) has not been touched yet.
3. Do not touch any file outside `kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/research/`
   — this WP's `owned_files` is confined to that directory (`planning_artifact`
   ownership rule).

**Files**: `kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/research/baseline-<date>.md`
(new, ~100-200 lines).
**Validation**: the file exists, cites the real merge-base SHA and real command
output (not fabricated), and every failure is either classified or explicitly
flagged as needing the orchestrator's judgment.

### Subtask T005: Hand off the pre-existing-failure set — do not file the issue yourself

**Purpose**: Comply with the charter's `§Pre-existing Failure Reporting Rule` and
`plan.md`'s explicit instruction that the ORCHESTRATOR files any GitHub issue for
a pre-existing failure, never the WP-implementing agent.

**Steps**:
1. In the same research artifact (T004), add a clearly labeled closing section
   "Hand-off to orchestrator" listing: the exact command(s) that produced each
   pre-existing failure, the failure summary, and why you believe it is
   pre-existing rather introduced by this mission (per the classification in
   T004).
2. Do **not** open a GitHub issue yourself for any pre-existing failure found —
   that action belongs to the orchestrator, not this WP.
3. Do not skip reporting a pre-existing failure just because it is not yet filed
   upstream — record it regardless; an unfiled pre-existing failure is not
   license to omit it from this artifact.
4. Clean up the worktree created in T002 once the artifact is written
   (`git worktree remove <path>`) — leave this checkout's tree exactly as you
   found it (only the new research file, per this WP's `owned_files`).

**Files**: same research artifact as T004 (append the hand-off section).
**Validation**: the hand-off section exists, names commands + counts + evidence
per pre-existing failure, and makes no claim to have filed or being about to file
a GitHub issue.

## Definition of Done

- The real merge-base SHA is resolved via `git merge-base`, not assumed.
- All three baseline commands ran, unmodified, against an isolated worktree at
  that SHA — never against this working tree's branch.
- `kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/research/baseline-<date>.md`
  exists with full pass/fail/skip counts, individual failing test IDs, and a
  classification (or explicit "needs orchestrator judgment" flag) for each.
- The artifact explicitly notes `test_charter_epic_golden_path` is `SKIPPED`
  (not run) at the baseline commit.
- A hand-off section names every pre-existing failure with commands + evidence,
  without this WP filing any GitHub issue itself.
- Per-subtask completion is recorded via
  `spec-kitty agent tasks mark-status <Txxx> --status done` for T001–T005.
- The baseline worktree created in T002 is cleaned up.

## Risks

- **Stale-venv/stale-install false reds** (CLAUDE.md categories 3–4) could be
  misrecorded as pre-existing product defects. Mitigation: re-sync and re-run
  before finalizing any classification (T003).
- **`/tmp` eviction**: creating the baseline worktree under `/tmp` risks losing
  it mid-run under memory pressure (tmpfs). Mitigation: use `/home` as directed
  in T002.
- **Merge-base drift**: if another agent merges to `origin/main` between T001 and
  when this WP's artifact is read by WP08, the recorded SHA may no longer be the
  literal current merge-base. This is expected and does not invalidate the
  artifact — WP08 re-runs its own comparison at its own time, citing this
  baseline as the reference point, not re-deriving a fresh merge-base itself
  unless plan.md's method calls for it.

## Reviewer Guidance

Confirm the research artifact cites a real `git merge-base` output (not a
plausible-looking fabricated SHA), that the three commands match plan.md's
Baseline method verbatim, and that the hand-off section does not claim to have
filed a GitHub issue. Confirm the baseline worktree was cleaned up and no stray
files landed outside `kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/research/`.

Implementation command: `spec-kitty agent action implement WP01 --agent claude`
