---
work_package_id: WP03
title: Arbiter override classification narrowed
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
planning_base_branch: issue-5196-rework-is-not-an-override
merge_target_branch: issue-5196-rework-is-not-an-override
branch_strategy: Planning artifacts for this mission were generated on issue-5196-rework-is-not-an-override. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5196-rework-is-not-an-override unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-rework-is-not-an-override-01M3MQV6
base_commit: 59502db6825305687ecd04cc4262a05cdca0c52c
created_at: '2026-09-28T20:35:53.944603+00:00'
subtasks:
- T012
- T013
- T014
- T015
- T016
phase: Phase 2 - Honest review history
history:
- at: '2026-09-28T20:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/review/
create_intent:
- tests/specify_cli/cli/commands/agent/test_rework_override_classification.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/review/arbiter.py
- tests/specify_cli/review/test_arbiter.py
- tests/review/test_arbiter.py
- tests/specify_cli/cli/commands/agent/test_rework_override_classification.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Arbiter override classification narrowed

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⛔ HARD RULE — no heavy full suites during the mission

During implement and **every WP review** (by you AND every implementer/reviewer subagent you dispatch), NEVER run full or heavy suites:
- no whole `tests/architectural/`, no e2e or full-integration suites, no performance/stress/timing suites;
- no `make test-full`, no whole-repo pytest.

Per WP, run only:
- the test files covering the files the WP touches;
- the owning module's fast tier;
- the specific NAMED architectural gate files the change implicates.

Leave the broad sweeps to the END of the mission (closeout, and only the targeted set listed below) or to CI. This is the internal-pack directive NO_FULL_HEAVY_SUITES_IN_MISSION.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete.

---

## Objectives & Success Criteria

`_is_arbiter_override` (`src/specify_cli/review/arbiter.py:337-370`) mis-classifies in both directions today:

- **Over-match (#5196)**: any forced move out of `planned` to `for_review`/`claimed`/`approved` after a `for_review → planned` rejection is recorded as an arbiter override. Every forced rework resubmission therefore shows `rejected → overridden`.
- **Under-match**: condition 4 requires `latest.from_lane == for_review`. A genuine forced `planned → approved` after an `in_review → planned` rejection is **not** recorded.

Target, per `contracts/arbiter-override-classification.md` (normative; decision moment `01M3MQXYAFEYE62RA5513KKNX6`): an override is recorded iff `force`, `old == planned`, `target ∈ {approved, done}`, and the latest event is a rejection (`→ planned` from `for_review|in_review` with a non-`None` `review_ref`).

- **FR-004**: a forced rework to `claimed`, `in_progress` or `for_review` after a rejection lights **no** probe.
- **FR-005**: a forced `planned → approved` after an `in_review` rejection lights **all five** probes. The `for_review` source is already pinned by the WP01 ratchet.

## Context & Constraints

- Read: `spec.md` (US2, US3), `plan.md`, `research.md` R-04, R-07, and `contracts/arbiter-override-classification.md` with its truth-table deltas.
- **Consumers are unchanged** and must keep working: `arbiter_persist_signal` (`tasks_transition_core.py:~766-780`), `Emit.arbiter_forward` (`~857`), `_run_arbiter_override` (`tasks_move_task.py:~3640-3708`), and the approved-cycle suppression in `tasks_verdict_persistence.py:~810-842`. **Do not edit those files**; WP02 owns `tasks_transition_core.py` and `tasks_move_task.py`.
- **Compat surface**: `_detect_arbiter_override` (`tasks_move_task.py:3620`) is re-exported via `tasks.py:410` and pinned by `test_tasks_compat_surface.py`. Keep `_is_arbiter_override(feature_dir, wp_id, old_lane, target_lane, force)`'s name and signature.
- `read_events` returns lane transitions only (`status/store.py:~736`), so with the WP in `planned` the latest transition into `planned` **is** the latest event. The rejection lookup is a private helper in `arbiter.py`.
- `approved → planned` (a reopen) is **deliberately excluded** from the rejection sources, as on the base.
- `planned → done` is gated by `_guard_done_ancestry` (it needs `--done-override-reason`). Cover `done` in the pure unit table and use `approved` for the real-CLI tests.

## Branch Strategy

- **Strategy**: lanes (populated by finalize-tasks)
- **Planning base branch**: `issue-5196-rework-is-not-an-override`
- **Merge target branch**: `issue-5196-rework-is-not-an-override`

Worktrees are allocated per computed lane from `lanes.json`. Start with `spec-kitty agent action implement WP03 --agent <you>`. This WP runs in parallel with WP02 in a separate lane.

## Subtasks & Detailed Guidance

### Subtask T012 – Tidy-first: characterize + pure split (behaviour-preserving)

- **Purpose**: Standing Order #2. Pin today's truth table, then split the predicate without changing behaviour.
- **Steps**:
  1. In `tests/specify_cli/review/test_arbiter.py`, add a parametrized characterization table for the **current** semantics. Cover:
     - force on/off;
     - old lane planned / non-planned;
     - targets `for_review`, `claimed`, `in_progress`, `approved`, `done`;
     - latest event of each of these shapes: a `for_review → planned` rejection, an `in_review → planned` rejection, a rollback without `review_ref`, a non-rejection.
  2. Extract a pure `is_arbiter_override_history(events: Sequence[StatusEvent], wp_id: str, old_lane: str, target_lane: str, force: bool) -> bool` in `arbiter.py`, carrying the **old** semantics.
  3. Make `_is_arbiter_override` a thin shell: `read_events` once, then delegate. Hoist the lazy imports if there is no import cycle.
  4. Run the table: it must be green before and after.
  5. Commit: `refactor(arbiter): split override predicate into a pure history check (tidy-first)`.
- If the pure name would trip `test_no_dead_symbols.py` (a public name with no caller in `src/`), the shell calling it satisfies the gate. Keep it out of `__all__` unless the module declares one; follow the module's convention.

### Subtask T013 – RED: classification acceptance through the real CLI (commit before the fix)

- **File**: `tests/specify_cli/cli/commands/agent/test_rework_override_classification.py` (new). Import `build_mission`, `drive_to_for_review`, `reject`, `move`, `override_probes`, `IMPLEMENTER`, `REVIEWER` from `_rework_loop_harness` (WP01).
- **Tests** (`@pytest.mark.regression` plus the directory's markers; docstring cites #5196):
  - (a) FR-004, for each target in `{for_review, claimed}`: drive to `for_review`, reject via `for_review_to_planned` (with `allow_force=True` if needed on the base), then the IMPLEMENTER moves `planned → target` **with `--force`** (the legacy habit). Assert exit 0 and all five probes False. For `for_review`, also mark subtasks done or monkeypatch readiness per the harness.
  - (b) FR-005: drive to `for_review`, reject via `in_review_to_planned`, then force `planned → approved` with `--note "arbiter: …"`. Assert exit 0 and all five probes True.
  - (c) The same as (b) for the `for_review_to_planned` source, as a sanity row. It is already green (WP01 ratchet); keep it here only if it adds a distinct assertion, otherwise skip it.
- Run on the base and paste the red summary into the Activity Log: (a) red via the `Arbiter override recorded` marker, (b) red via no probe lit.
- Commit this file alone: `test(arbiter): red-first rework-vs-override classification (#5196)`.

### Subtask T014 – Narrow the classification + re-pin stale pins

- Change `is_arbiter_override_history`:
  - targets `{APPROVED, DONE}`;
  - rejection = the latest event has `to_lane == PLANNED`, `from_lane ∈ {FOR_REVIEW, IN_REVIEW}`, and `review_ref is not None`;
  - `approved → planned` is excluded.
- Rewrite the docstring of `_is_arbiter_override` (`arbiter.py:344-350`) to state the new rule and cite the decision moment.
- **Re-pin stale unit pins with rationale** (§4 of the standing orders: the scenario is still valid but the expected value moved):
  - `tests/specify_cli/review/test_arbiter.py:~115` (target `for_review` → now False)
  - `tests/specify_cli/review/test_arbiter.py:~126` (target `claimed` → now False)
  - `tests/review/test_arbiter.py:~187` (check its target; re-pin if it is a rework-shaped target)

  Add a one-line comment citing #5196 on each re-pinned assertion. Keep the `approved`-target tests as they are.
- **Vacuity trap (binding)**: these existing "returns False" tests use target `for_review`. That target is always False after the change, so they would stop testing their named condition:
  - `tests/specify_cli/review/test_arbiter.py:~60, ~71, ~93, ~103, ~148, ~160`
  - `tests/review/test_arbiter.py:~216, ~237, ~601, ~631`

  **Re-target each to `approved`**, so each still fails for its own named reason (no force / wrong old lane / non-rejection / no review_ref / other WP …). `tests/review/test_arbiter.py:~187` (target `for_review`, expects True) flips to False and needs the #5196 comment.
- Update the T012 characterization table to the new truth table. Do this in the same commit as the behaviour change, with the deltas matching the contract table exactly.

### Subtask T015 – Approved-cycle suppression + `done` coverage

- **Purpose**: `tasks_verdict_persistence.py:~842` suppresses the approved review-cycle write when `is_arbiter_override` is true. After the change that suppression also fires for the in_review source, and no longer fires for forced rework (which targets non-approval lanes anyway).
- **Add to the T013 file**: after (b), assert the review-cycle artifacts are consistent with a genuine override. That means no synthesized `approved` review-cycle record for the overridden cycle, matching what the for_review-source genuine override produces on the base. Pin it exactly: `review_cycle_files == ["review-cycle-1.md"]` for **both** sources. The probe shows the base writes `review-cycle-2.md` for the in_review source, which is the defect.
- **Unit**: add a `done` row (forced `planned → done` after a rejection → True) to the pure table.

### Subtask T016 – Green-up, un-mark, gates

- Remove `@pytest.mark.regression` once green; keep the focused tests.
- Run:

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_rework_override_classification.py tests/specify_cli/cli/commands/agent/test_rework_guard_ratchets.py tests/specify_cli/review/test_arbiter.py tests/review/test_arbiter.py tests/review/test_arbiter_coord_root.py tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_observability.py -q
uv run --frozen pytest tests/specify_cli/review/ tests/review/ -q -m "fast or unit"      # owning module fast tier
uv run --frozen pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_verdict_vocab_single_source.py tests/architectural/test_untrusted_path_containment.py -q
uv run --frozen ruff check src/specify_cli/review/arbiter.py <test files> && uv run --frozen ruff format --check <same>
uv run --frozen mypy src/specify_cli/review/arbiter.py
```

- Also run the tests that exercise arbiter consumers: `grep -rl "is_arbiter_override\|arbiter_forward\|_run_arbiter_override" tests/ --include=*.py`. Exclude `tests/integration/**` from edits; running an individual integration file that covers the arbiter is fine.

## Risks & Mitigations

- A behaviour change for anyone who used a forced `claimed`/`for_review` as an "arbiter" action. This is intended (decision moment), and the CHANGELOG entry at closeout will state it.
- Blind probe: (a) is only meaningful because WP01's T003 proves the probes see a real override on the same fixture shape.

## Review Guidance

- Verify the tidy-first commit is behaviour-preserving (the characterization table passes unchanged across the split).
- Verify the RED commit precedes the behaviour change, with red output in the Activity Log.
- Verify the final truth table equals the contract table, and the re-pins carry a #5196 rationale.
- Verify no edits outside `owned_files`, especially not `tasks_transition_core.py` / `tasks_move_task.py` (WP02).
- Reviewer ≠ implementer. Respect the HARD RULE.

## Hardening (post-tasks squad — binding)

- **RED proof**: on the base, (a) must fail on `cli_marker is True` (the forced rework prints "Arbiter override recorded") and (b) on "not all probes lit", **with exit code 0 in both**. A red for any other reason is not a valid RED. Paste the evidence into the Activity Log.
- "Arbiter override recorded" prints only without `--json`, so do not pass `--json` on the moves you probe.

## Activity Log

- 2026-09-28T20:30:00Z – system – Prompt created.
