---
work_package_id: WP01
title: Phase 0 Baseline + Campsite-Clean — Remove Dead fail-fast Key (Commit A)
dependencies: []
requirement_refs:
- NFR-006
planning_base_branch: issue-4865-ci-nightly-wallclock-budget
merge_target_branch: issue-4865-ci-nightly-wallclock-budget
branch_strategy: Planning artifacts for this mission were generated on issue-4865-ci-nightly-wallclock-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4865-ci-nightly-wallclock-budget unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-nightly-wallclock-budget-01M34HNZ
base_commit: e864b4563a21c6635a8bd81b542011034fe90b7c
created_at: '2026-09-22T15:46:19.324213+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 0/1 - Baseline + Campsite-Clean
history:
- at: '2026-09-22T14:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
- at: '2026-09-22T14:15:00Z'
  actor: system
  action: "Merged former standalone WP01 (Phase 0 baseline) into this WP to satisfy spec-kitty's lane-computation constraint: a planning_artifact WP cannot sit both upstream and downstream of a code lane in one mission without producing a LANE_DEPENDENCY_CYCLE (all planning_artifact WPs collapse into one canonical lane-planning). Baseline recording therefore lands in this WP's own Activity Log, not a kitty-specs/ file edit — see tracer-tooling-friction.md's dated entry."
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-nightly.yml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Phase 0 Baseline + Campsite-Clean (Commit A)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: (unset — select per `spec-kitty agent profile list` if not pre-assigned)

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log.
- **You must address all feedback** before your work is complete.

---

## Review Feedback

*None yet.*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````yaml`, ````bash`

---

## Objectives & Success Criteria

This WP does TWO things, in order, as the mission's opening WP:

1. **Phase 0 — scoped baseline** (T001-T003): establish the mission's real pre-change baseline —
   not issue #3284's stale, closed "23 known-red" figure — by running the scoped
   `tests/architectural/` command plan.md names, BEFORE any functional edit lands, and filing a
   GitHub issue first if a pre-existing failure surfaces (charter's binding Pre-existing Failure
   Reporting Rule, SC-008's sanctioned exception to "no follow-up issues").
2. **Campsite-clean (Commit A)** (T004-T006): remove the inert `strategy: { fail-fast: false }`
   key (no `matrix:` exists under the job, so the key has no effect) from the EXISTING single
   `performance-and-e2e` job, as a distinct, behavior-preserving commit that precedes the
   functional split (WP02) — per charter Standing Order #2 and plan.md's Campsite-clean decision
   (PLAN-GOV-001).

**Why these two are one WP, not two** (a deliberate, documented adaptation — see the WP-level
history note in this file's frontmatter and `tracer-tooling-friction.md`'s dated entry): running
`spec-kitty agent mission finalize-tasks --validate-only` against an EARLIER 8-WP split (a
standalone Phase-0-baseline WP, `execution_mode: planning_artifact`, sequenced first) produced a
hard `LANE_DEPENDENCY_CYCLE` — spec-kitty's lane-computation collapses ALL `planning_artifact`
WPs into one canonical `lane-planning`, and that lane cannot legitimately sit both upstream of a
code lane (as the standalone baseline WP did, feeding WP02) AND downstream of the same code lane
(as the mission's closing PR-assembly WP legitimately must, per NFR-006's evidence-consolidation
requirement) without the lane graph becoming cyclic. The closing PR-assembly WP's downstream
position is the one Standing Order/NFR genuinely requires; the baseline's UPSTREAM planning
position was the one that could be folded into an adjacent code WP without losing anything
(baseline recording only needs a durable per-WP record, which the Activity Log already provides
— it does not need a `kitty-specs/` file edit). Folding baseline into this WP's opening subtasks
resolves the cycle without weakening either constraint.

Success = (a) a dated Activity Log entry stating the exact baseline command + pass/fail counts
(+ issue URL if filed), recorded BEFORE T004 begins, and (b) a commit that changes EXACTLY the two
`strategy: { fail-fast: false }` lines and nothing else — the job still exists, still runs
`performance`/`e2e`/`stress` serially, still has `timeout-minutes: 60`.

## Context & Constraints

- `.kittify/charter/charter.md` — Pre-existing Failure Reporting Rule (bottom of the charter);
  Standing Order #2 ("Campsite cleaning & incremental debt paydown... a distinct preceding
  step... behavior-preserving").
- `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/spec.md` — Correction #2 (reject #3284 as
  baseline), SC-008.
- `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/plan.md` — "Baseline honesty" section (the
  exact baseline command), "Campsite-clean decision" section (an earlier plan draft folded the
  `fail-fast` removal into the functional commit and was corrected — "the charter text does not
  carve out a churn-based exception to Standing Order #2's distinct-preceding-commit
  requirement"; do not repeat that mistake by folding the `fail-fast` removal into WP02's
  functional commit).
- `CLAUDE.md`'s "Test-run baseline-red gotcha" applies to T001: rule out categories 2-4
  (CI-environment config, stale install, stale venv — specifically re-run `uv sync --frozen
  --all-extras` and retry) before treating a failure as real.
- The current job body (`.github/workflows/ci-nightly.yml`): `performance-and-e2e:` header,
  `timeout-minutes: 60`, then `strategy:\n      fail-fast: false`, then `env:`, then `steps:` —
  re-read the live file directly rather than trusting a specific line number, since no prior WP
  has edited it yet.
- `.github/*.yml` is outside `ruff`'s domain — no Python formatter gate applies to the campsite-
  clean edit.

## Branch Strategy

- **Strategy**: `single_branch` — this mission has no lane split; planning artifacts and every
  WP's implementation land directly on the mission's target branch.
- **Planning base branch**: `issue-4865-ci-nightly-wallclock-budget`
- **Merge target branch**: `issue-4865-ci-nightly-wallclock-budget`

> These fields are populated automatically by `spec-kitty agent mission tasks`. Do NOT change
> them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Run the scoped baseline pytest command

- **Purpose**: Get the real, current pass/fail counts for the two architectural test files this
  mission's own diff will touch or read, on this branch's HEAD, before any change lands.
- **Steps**:
  1. Confirm you are on `issue-4865-ci-nightly-wallclock-budget` with a clean working tree
     (`git status`).
  2. Run exactly: `uv run --frozen pytest tests/architectural/test_module_shard_registry.py
     tests/architectural/test_performance_marker_guard.py -q`
  3. Record the full pass/fail/error counts from the output verbatim (do not paraphrase — copy
     the summary line) in this WP's Activity Log (below).
- **Files**: None edited; reads test files only.
- **Parallel?**: No — this is the mission's first executed step.
- **Notes**: If the command errors on collection (e.g. `ModuleNotFoundError`), first re-run `uv
  sync --frozen --all-extras` and retry once before treating it as a real failure (CLAUDE.md
  category-4 stale-venv gotcha).

### Subtask T002 – [Conditional] File a pre-existing-failure GitHub issue

- **Purpose**: The charter's binding Pre-existing Failure Reporting Rule requires a filed issue
  BEFORE any pre-existing failure is treated as accepted baseline context — the one sanctioned
  exception to this project's "no follow-up issues" rule for this mission (SC-008).
- **Steps** (only if T001 showed any failure):
  1. Confirm the failure is pre-existing (nothing has been touched yet at this point, so any
     failure observed here is by definition pre-existing to this mission — but rule out CLAUDE.md
     categories 2-4 first).
  2. `unset GITHUB_TOKEN && gh issue create` with: the exact command run (from T001), the failure
     summary (test name(s), error text), and why it is judged pre-existing.
  3. Record the issue URL for use in the Activity Log.
- **Files**: None.
- **Parallel?**: No.
- **Notes**: Skip entirely if T001 shows 100% pass — do not manufacture a finding. **Scope/dedup**:
  this WP's baseline covers only the two named architectural test files
  (`test_module_shard_registry.py`, `test_performance_marker_guard.py`) — a distinct command
  surface from WP04's later `capture_shard_timings.py` recapture run, so no dedup check against a
  later WP04-filed issue applies here (see WP04's own T022 for its side of this scope note).

### Subtask T003 – Record the baseline in this WP's Activity Log

- **Purpose**: Standing Order #3 (mission tracer files / durable evidence) applies to this
  mission's evidence trail broadly — this WP's own Activity Log IS that durable record for the
  baseline step (the mission's dedicated `tracer-approach.md` consolidation happens later, in
  WP07, which pulls this entry forward per NFR-006 — see WP07's prompt).
- **Steps**:
  1. Append an Activity Log entry (see format below) stating: the exact command run, the
     pass/fail counts observed, and — if T002 ran — the filed issue URL and a one-line summary of
     why it is judged pre-existing.
- **Files**: None (Activity Log entries in this WP's own prompt file are not a declared
  `owned_files` surface — they are the standard per-WP status/progress mechanism).
- **Parallel?**: No.

### Subtask T004 – Remove the dead `fail-fast` key

- **Purpose**: Close real, domain-matched debt (an inert config key) before the functional split
  (WP02) touches the same job.
- **Steps**:
  1. **Red-first check (do this BEFORE editing anything)**: grep/read
     `.github/workflows/ci-nightly.yml`'s `performance-and-e2e` job body and confirm no `matrix:`
     key exists anywhere under it — `matrix:` is the only thing `fail-fast` governs. If a
     `matrix:` key IS found, STOP: the key would not be inert, do not remove it — escalate instead
     (see this file's "Red-first / revert discipline" section below).
  2. Open `.github/workflows/ci-nightly.yml`, locate the `performance-and-e2e:` job.
  3. Remove the two lines: `    strategy:` and `      fail-fast: false` (confirm indentation
     matches — these are the lines directly following `timeout-minutes: 60`).
  4. Do NOT touch any other line in this job or elsewhere in the file.
- **Files**: `.github/workflows/ci-nightly.yml`
- **Parallel?**: No — depends on T001-T003 (baseline must be recorded before any functional/
  cleanup edit lands).

### Subtask T005 – Confirm the diff is scoped to exactly two lines

- **Purpose**: Standing Order #2 requires this commit be strictly behavior-preserving — any
  additional change here is scope creep into WP02's territory.
- **Steps**:
  1. Run `git diff .github/workflows/ci-nightly.yml`.
  2. Confirm the diff shows ONLY the two removed `strategy:`/`fail-fast: false` lines (as `-`
     lines), with no other addition or removal.
  3. Confirm the job still exists under the name `performance-and-e2e`, still has
     `timeout-minutes: 60`, and its `steps:` still run all three suites (`performance`, `e2e`,
     `stress`) serially.
- **Files**: `.github/workflows/ci-nightly.yml` (read/verify only in this subtask).
- **Parallel?**: No.
- **Notes**: If the diff shows anything beyond the two lines, revert and redo T004 — do not
  rationalize an extra change as "while I'm here."

### Subtask T006 – Commit as `chore(ci)`

- **Purpose**: A clean, single-purpose Conventional Commit, distinct from and preceding WP02's
  `feat(ci)` commit. (No commit is made for T001-T003 — baseline recording is Activity-Log-only,
  not a repo file change.)
- **Steps**:
  1. Stage only `.github/workflows/ci-nightly.yml`.
  2. Commit with a message like: `chore(ci): remove inert fail-fast key from
     performance-and-e2e (no matrix strategy)` — body may reference that `fail-fast` has no effect
     without a `strategy.matrix:`, confirmed by direct inspection.
  3. Confirm commitlint (if run locally/in a pre-commit hook) accepts the message shape.
- **Files**: `.github/workflows/ci-nightly.yml`
- **Parallel?**: No.

## Red-first / revert discipline (concrete, for this WP)

**RED for this WP's campsite-clean claim**: T004's grep-confirm step finds a `matrix:` key
present anywhere under the `performance-and-e2e` job body alongside `strategy: { fail-fast:
false }` — a `matrix:` block is exactly what `fail-fast` governs, so its presence would mean the
key is NOT inert, and removing it would be a real behavior change, not a campsite-clean. Finding
one is this WP's own falsification signal: STOP and escalate rather than proceeding to remove the
key. **GREEN**: no `matrix:` key is found (the current, directly-inspectable state of the file),
confirming the key genuinely has no effect and T004's removal is safe. This mirrors WP02/WP06's
red-first sections in stating a concrete falsification condition, distinguishing this WP's
campsite-clean half (T004-T006) from its baseline-recording half (T001-T003, which records a fact
rather than asserting a red/green claim).

## Test Strategy

- T001's scoped baseline command IS this WP's primary test deliverable:
  `uv run --frozen pytest tests/architectural/test_module_shard_registry.py
  tests/architectural/test_performance_marker_guard.py -q`
- No pytest applies to T004-T006 (a pure YAML edit with no Python surface touched) — verification
  there is structural (T005's `git diff` scope check).

## Risks & Mitigations

- **Risk**: mistaking a stale-venv false red for a genuine pre-existing failure and filing a
  spurious issue. **Mitigation**: re-run `uv sync --frozen --all-extras` and retry before
  concluding (CLAUDE.md category 4).
- **Risk**: treating the campsite-clean removal as "trivial, just fold it into the next commit."
  **Mitigation**: T006 makes the separate commit the explicit deliverable; do not begin WP02's
  edits until this commit exists on the branch.

## Review Guidance

- Confirm the Activity Log carries the EXACT baseline command and EXACT counts (not a
  paraphrase), recorded before T004's edit.
- Confirm `git show <T006-commit>` touches only the two `fail-fast` lines.
- Confirm the commit history shows this `chore(ci)` commit strictly before WP02's `feat(ci)`
  commit.
- If a pre-existing-failure issue was filed, confirm the issue's URL appears in the Activity Log
  and the issue body includes the command, failure summary, and pre-existing rationale.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-09-22T14:15:00Z – system – Prompt created.
- 2026-09-22T15:49:05Z – claude-sonnet-5 – T001 baseline: ran exactly `uv run
  --frozen pytest tests/architectural/test_module_shard_registry.py
  tests/architectural/test_performance_marker_guard.py -q` from the primary
  checkout (`/home/jeroennouws/dev/SK-missions/4865`, branch
  `issue-4865-ci-nightly-wallclock-budget`, HEAD `e864b4563` — the same
  commit the lane worktree's `base_commit` was pinned to). Verbatim summary
  line: `28 passed in 36.71s`. 0 failed, 0 errors — 100% pass, no
  pre-existing failure surfaced. T002 (file a pre-existing-failure GitHub
  issue) is therefore SKIPPED per the subtask's own instruction ("Skip
  entirely if T001 shows 100% pass — do not manufacture a finding"); no
  issue filed for this baseline. Category-4 stale-venv gotcha ruled out
  before trusting the result: the `uv run --frozen` invocation itself
  rebuilt/reinstalled the local `spec-kitty-cli` editable package
  (`Building spec-kitty-cli ... Uninstalled 1 package ... Installed 1
  package`), and `.venv/bin/spec-kitty --version` was re-checked afterward
  (`spec-kitty-cli version 4.0.0rc5`, unchanged) to confirm the venv
  remained healthy and was not left in a broken state by that rebuild.
- 2026-09-22T15:58:52Z – claude-sonnet-5 – Supplementary baseline gate:
  `make test-fast` (`env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 uv run
  --frozen pytest tests/unit tests/status tests/cli
  tests/specify_cli/runtime tests/architectural/test_no_retired_subsystems.py
  -m "(fast or unit) and not slow and not e2e and not integration and not
  regression and not distribution and not live_adapter and not stress and
  not windows_ci and not platform_darwin" -n auto --dist loadfile -p
  no:cacheprovider -q`) run from the primary checkout, same HEAD. Verbatim
  summary line: `1941 passed, 5 skipped, 5 warnings in 222.31s (0:03:42)`,
  exit code 0. No failures — no additional pre-existing-failure issue
  needed. **Correction to T004-T006's original landing**: T004-T006's
  campsite-clean commit was first made on the lane worktree branch
  (`kitty/mission-ci-nightly-wallclock-budget-01M34HNZ-lane-a`, commit
  `d1e7d5177`) that `agent action implement` silently provisioned (see
  `tracer-tooling-friction.md`'s dated entry on the `lanes.json`/`meta.json`
  `single_branch` topology divergence) — NOT on this WP's own
  `merge_target_branch` (`issue-4865-ci-nightly-wallclock-budget`), so the
  branch pushed to `origin` did not carry it. Caught and corrected on
  operator instruction: the identical 2-line removal was re-applied and
  re-committed directly on `issue-4865-ci-nightly-wallclock-budget`
  (commit `3fb1c8bb7`), independently red-first-checked again (no `matrix:`
  key between `performance-and-e2e:` and the next job). That commit is what
  is now pushed to `origin/issue-4865-ci-nightly-wallclock-budget`. Full
  detail in `tracer-tooling-friction.md`'s second addendum, including the
  now-duplicated commit on the lane branch that a future lane-consolidation
  step will need to reconcile (content-identical, so expected to be a
  no-op/already-applied hunk).

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task WP01 --to
<status>` to change WP status.
