---
work_package_id: WP04
title: Recapture charter Shard Timings (Phase 2a, NFR-004)
dependencies:
- WP03
requirement_refs:
- FR-006
- NFR-004
- C-002
- C-003
planning_base_branch: issue-4865-ci-nightly-wallclock-budget
merge_target_branch: issue-4865-ci-nightly-wallclock-budget
branch_strategy: Planning artifacts for this mission were generated on issue-4865-ci-nightly-wallclock-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4865-ci-nightly-wallclock-budget unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-nightly-wallclock-budget-01M34HNZ
base_commit: e864b4563a21c6635a8bd81b542011034fe90b7c
created_at: '2026-09-22T17:49:11.310033+00:00'
subtasks:
- T020
- T021
- T022
- T023
phase: Phase 2 - Recapture & Re-Derive
history:
- at: '2026-09-22T14:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- .github/ci-shard-timings.json
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Recapture charter Shard Timings

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
Use language identifiers in code blocks: ````bash`, ````json`

---

## Objectives & Success Criteria

Run the ONE sanctioned producer — `scripts/ci/capture_shard_timings.py --module charter --write`
— as its own explicit, budgeted step (~110 minutes serial wall-clock, this morning's 5 `charter`
shards already summed to ~110 min combined). This is NFR-004's requirement made concrete: the
recapture must never be silently folded into "edit a YAML number."

Success = `.github/ci-shard-timings.json`'s `module_capture_provenance["charter"]` is populated
(not `None`), matching the shape of the existing `auth` reference record, with `exit_code == 0`
(SC-005).

## Context & Constraints

- `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/spec.md` — FR-006, NFR-004, C-002, C-003,
  User Story 2's AC1, "The vacuous-gate finding" section (WHY this recapture matters: `charter`'s
  current timings come from an old ad-hoc bulk `-n auto --dist loadfile` run that measures only
  pytest's call phase, missing fixture-setup cost — producing near-uniform ~0.098s-mean durations
  that make the LPT skew computation return ~0% skew for ANY `shard_count` from 1 to 4211).
- `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/plan.md` — "Generated-artifact discipline"
  section (the exact verification steps below), Phasing § Phase 2 step 2a.
- **C-002 (binding, do not deviate)**: the `charter` recapture MUST use `scripts/ci/
  capture_shard_timings.py --module charter --write`. The manual wall-clock÷target heuristic used
  for `agent`/`upgrade` in commit `349b73fc0` is EXPLICITLY REJECTED as a precedent for this
  mission.
- **C-003 (binding scope boundary)**: only `charter` is recaptured. 13 other stale modules
  (`agent`, `cli`, `core_misc`, `execution_context`, `glossary`, `kernel`, `lanes`, `missions`,
  `next`, `post_merge`, `release`, `review`, `upgrade`) are explicitly OUT OF SCOPE — do not
  recapture them, even opportunistically. No follow-up GitHub issue is filed for that broader gap
  (project standing rule); it is already recorded in `tracer-design-decisions.md` for the
  orchestrator to ledger at mission exit.
- `scripts/ci/capture_shard_timings.py` is READ and RUN only in this mission — never edited.

## Branch Strategy

- **Strategy**: `single_branch`.
- **Planning base branch**: `issue-4865-ci-nightly-wallclock-budget`
- **Merge target branch**: `issue-4865-ci-nightly-wallclock-budget`

> Populated automatically by `spec-kitty agent mission tasks`. Do NOT change manually.

## Subtasks & Detailed Guidance

### Subtask T020 – Run the recapture

- **Purpose**: FR-006/NFR-004 — the fixture-aware, purpose-built measurement this mission's P2
  half exists to obtain.
- **Steps**:
  1. From the repo root: `scripts/ci/capture_shard_timings.py --module charter --write`
  2. Budget ~110 minutes of serial wall-clock — do not interrupt or background this in a way that
     risks a partial/incomplete capture. If your execution environment has a shorter default
     timeout than 110 minutes, run this as an explicitly long-running/backgrounded step and poll
     for completion rather than truncating it.
- **Files**: `.github/ci-shard-timings.json` (written by the script, not hand-edited).
- **Parallel?**: No.
- **Notes**: This is this mission's single largest wall-clock cost item — treat interruption risk
  seriously; a truncated run is not a partial success to build on.

### Subtask T021 – Confirm the provenance record

- **Purpose**: SC-005 — prove the capture actually happened via the purpose-built tool, not just
  that the command exited.
- **Steps**:
  1. Inspect `.github/ci-shard-timings.json`'s `module_capture_provenance["charter"]`.
  2. Confirm it is populated (not `None`) with: `run_id`, `command`, `captured_at`, `test_dirs`,
     `selection`, `unique_tests_measured`, `exit_code`, `producer` — matching the shape of the
     existing `auth` entry (the reference example named in spec.md's AC1).
  3. Confirm `exit_code == 0`.
- **Files**: `.github/ci-shard-timings.json` (read/verify only).
- **Parallel?**: No — depends on T020.

### Subtask T022 – [Conditional] Pre-existing failure during capture

- **Purpose**: The charter's binding Pre-existing Failure Reporting Rule applies here too — a
  non-zero `exit_code` means the capture run itself hit a test failure or error.
- **Steps** (only if T021 shows `exit_code != 0`, or the capture surfaces a test failure/error):
  1. **Dedup check**: first check whether WP01's Activity Log already recorded an issue for a
     related failure — file a new issue only if this capture's failure is genuinely distinct from
     anything WP01 already reported, to avoid a duplicate filing.
  2. File a GitHub issue (command run, failure summary, why judged pre-existing) BEFORE treating
     it as accepted baseline or proceeding to WP05.
  3. Do not proceed to T023 until this is resolved or explicitly accepted by the operator.
- **Files**: None (issue filing only).
- **Parallel?**: No.

### Subtask T023 – Commit the regenerated timings file

- **Purpose**: `.github/ci-shard-timings.json` is a generated artifact; commit the recapture
  result as its own step, separate from WP05's registry-row edit that consumes it.
- **Steps**: Stage `.github/ci-shard-timings.json`, commit with a message like `chore(ci):
  recapture charter shard timings via capture_shard_timings.py`.
- **Files**: `.github/ci-shard-timings.json`
- **Parallel?**: No — depends on T021 (and T022 if triggered).

## Red-first / revert discipline (concrete, for this WP)

**RED** for this WP: `exit_code != 0` in the capture's provenance record, or
`module_capture_provenance["charter"]` remaining `None` after T020 completes. **GREEN**: the
populated, `auth`-shaped provenance record (matching the reference shape T021 checks against) with
`exit_code == 0`. T021 is the check that observes this directly; T022's conditional issue-filing
(after its dedup check against WP01's Activity Log) is this WP's escalate/revert discipline should
RED occur — do not proceed to T023/WP05 until it resolves.

## Test Strategy

- No pytest suite is written by this WP — the deliverable IS the recapture command and its
  provenance verification.
- Downstream WP06's `test_charter_shard_skew_sensitivity.py` and WP05/WP06's re-runs of
  `test_module_shard_registry.py` are what consume and validate this WP's output.

## Risks & Mitigations

- **Risk**: an interrupted/partial capture reported as complete. **Mitigation**: T021's explicit
  `exit_code == 0` check plus shape comparison against `auth`'s reference record.
- **Risk**: scope creep into recapturing another stale module "since the tool is already running."
  **Mitigation**: C-003 is restated explicitly above; only `--module charter` is in scope.

## Review Guidance

- Confirm `module_capture_provenance["charter"]` is genuinely populated (not a hand-edited stub)
  — cross-check `producer` names `capture_shard_timings.py`, not a manual entry.
- Confirm no other module's `module_capture_provenance` entry changed in this diff (only
  `charter`'s should differ from the pre-mission state).
- Confirm this WP's commit does NOT also touch `.github/ci-module-registry.yml` — that edit
  belongs to WP05.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

**Initial entry**:

- 2026-09-22T14:15:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task WP04 --to
<status>` to change WP status.
- 2026-09-22T18:15:35Z – claude – shell_pid=2269967 – T020 recapture ran successfully (exit_code 0, 18m59s real elapsed vs the plan's ~110min budgeted estimate; 6144 passed/12 skipped/20 deselected). T021 verified independently: module_capture_provenance[charter] populated, auth-shaped (run_id/command/captured_at/test_dirs/selection/unique_tests_measured/exit_code/producer), exit_code=0; module_test_count[charter] 4211->6156 now matches the consumer's own collect-only count (6156, reproduced via pytest tests/charter tests/doctrine -m "not performance and not stress" --collect-only -q); duration sum 410.755s->1134.188s; sub-2ms share 77.3%->36.3% (no longer near-uniform). T022 conditional check evaluated and NOT triggered (exit_code==0, no pre-existing failure) -- marked done per the done/pending-has-no-skipped gap; this mark asserts only that the conditional was checked and found not-applicable, not that any remediation or issue-filing occurred. T023 committed .github/ci-shard-timings.json only, commit 66e5255dc on issue-4865-ci-nightly-wallclock-budget; .github/ci-module-registry.yml untouched (WP05's scope); lane branch kitty/mission-ci-nightly-wallclock-budget-01M34HNZ-lane-b tip unchanged at d1e7d5177. Durability limit (see tracer-tooling-friction.md 2026-09-22 ROOT CAUSE entry, not restated here): this recapture makes charter's length match the consumer's collection right now (6156==6156) but installs no ongoing check -- the next test added under tests/charter or tests/doctrine will silently re-desync the length and return charter to the uniform-weight fallback, with every existing gate still green. Relevant to FR-008/NFR-003/SC-006 and WP06's non-vacuity test.
