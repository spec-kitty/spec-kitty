---
work_package_id: WP05
title: Gate wiring — canceled-content axis and mixed-lane refusal
dependencies:
- WP02
- WP04
- WP07
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-003
- C-003
planning_base_branch: issue-5046-mixed-lane-authorship
merge_target_branch: issue-5046-mixed-lane-authorship
branch_strategy: Planning artifacts for this mission were generated on issue-5046-mixed-lane-authorship. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5046-mixed-lane-authorship unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mixed-lane-authorship-soundness-01M3M7Y0
base_commit: c04d2db37ab7446a9258599f0c340a5a90aeefcf
created_at: '2026-09-28T18:36:46.863188+00:00'
subtasks:
- T022
- T023
- T024
- T025
- T026
- T027
phase: Phase 3 - Gate (#5046)
history:
- at: '2026-09-28T15:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/consolidation/reconciliation.py
- tests/consolidation/test_reconciliation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Gate wiring: canceled-content axis and mixed-lane refusal

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (role `implementer`, agent `claude`) before reading further.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. All feedback items are your TODO list.

---

## Objectives & Success Criteria

Close #5046 in `src/specify_cli/consolidation/reconciliation.py` with the smallest wiring on top of WP04:
- WP02's RED repros (`tests/terminus/test_repro_5046.py`) turn GREEN with the specified verdict text; WP02 controls and `tests/terminus/test_repro_5018.py` stay GREEN.
- Every row of the contract verdict table (`contracts/attribution-and-verdicts.md` C3) has a unit test.
- `approved`, `authored_shas`, `authored_patch_ids`, `authored_blobs`, `authored_deletions`, `multi_lane_paths`, `excluded_shas`, `excluded_patch_ids` are **byte-identical** to today for every input (no issue 5018-class regression surface) — pin with a test.

## Context & Constraints

- Plan D-3 (steps 1, 2, 5) and D-4; research R-8, R-9 (R2, R4), R-10 (B2, B6).
- Claim builder: `build_approved_wp_set` (`reconciliation.py:925-1004`); verifier: `MergeOutcomeVerifier.verify` (`:415-487`), `_refusal_reason` (`:489`), squash axis (`:558-705`); result types `Divergence` (`:149-206`), `VerifyResult` (`:208-246`). Every test constructs `ApprovedWpCommitSet` by keyword, so a new defaulted field is safe.
- Bookkeeping: extract the body of `MergeOutcomeVerifier._is_bookkeeping_path(path, claim)` into a module-level `_is_bookkeeping(path, mission_slug, planning_prefix)`; the staticmethod delegates; pass `functools.partial(_is_bookkeeping, mission_slug=..., planning_prefix=...)` to WP04 (the claim does not exist yet inside `build_approved_wp_set`).
- REFUSE restores the target via WP07 (dependency) — WP02's T008 `target restored` assertion needs both WP05 and WP07.
- Mixed lane (B2): `_lane_is_approved(lane, work_packages)` **and** `any(wp in excluded_canceled_wp_ids for wp in lane.wp_ids)` — `excluded_canceled_wp_ids` is the existing parameter fed by `acceptably_canceled_wp_ids` (`consolidation/done_bookkeeping.py:42`). Do not re-derive "canceled" from the snapshot.
- Entered implementation: from the same events list WP04 consumes (any transition into `claimed`/`in_progress` for that WP).
- Read events once: `from specify_cli.status import read_events` on `feature_dir` **iff any mixed lane exists** (decided from `lanes.json` + snapshot + `excluded_canceled_wp_ids`, no events needed); `StoreError` → refusal `events_unreadable` (NFR-002). No mixed lane → events are not read (non-mixed missions byte-identical).
- Keep `verify()` ≤ complexity 15: add `_canceled_content_divergence(target_ref, claim) -> tuple[list[CanceledPathState], str | None]` (FAIL entries, REFUSE reason).

## Branch Strategy

- **Planning base / merge target**: `issue-5046-mixed-lane-authorship`. Workspace from `spec-kitty agent action implement WP05 --agent claude`; it must contain WP02 and WP04.

## Subtasks & Detailed Guidance

### Subtask T022 – Mixed-lane refusal in the claim

- After the snapshot and the existing `_unresolvable_approved_lane_branches` check, for each mixed lane and each canceled WP there that entered implementation, call WP04's resolver. Any `Unattributable` → return `_refusal_claim(...)` (existing helper, `:1017`) with a reason built as: `"mixed lane <lane>: canceled <WP> cannot be attributed — <detail>. Recovery: revert <WP>'s commits on the lane branch through a surviving WP's governed work (so its paths are superseded), then re-run spec-kitty consolidate."` The phrase **`no commit attribution`** must appear for the `no_stamp` reason (WP02 T008 asserts it).
- Refusals take precedence over FAIL by construction (claim refusal returns first in `verify`).

### Subtask T023 – `canceled_content` on the claim

- New field `canceled_content: frozenset[CanceledPathState] = frozenset()` on `ApprovedWpCommitSet` with a comment in the file's existing style (why it exists, why `excluded_*` is not reused: SHA reachability false-FAILs a superseded canceled commit under merge and squash destroys SHAs; hand-built claims leave it empty → byte-identical behaviour).
- Populate from all `Attributed` outcomes. Pass the verifier's bookkeeping predicate to WP04 (a module-level function or a static method reference — do not duplicate the denylist).

### Subtask T024 – Verifier step (every strategy)

- In `verify()`, after `_refusal_reason` and the vacuous-manifest check, **before** the `verify_reachability` branch: compute `canceled_fail, canceled_refuse = self._canceled_content_divergence(target_ref, claim)`. If `canceled_refuse` → return `VerifyResult.refused(canceled_refuse)`.
- Per entry, with T = target state of P (`blob_id_at(target_ref, P)` or `None` if absent) and W = window-base state (`claim.excluded_window_base`; if `None` while entries exist → REFUSE with `_REFUSE_WINDOW_BASE_UNRESOLVED`):
  - `T == canceled_state and W != canceled_state` → FAIL entry;
  - `T == canceled_state and W == canceled_state` → FAIL entry if `pre_state_by_survivor` (approved work undone — SC-007), else nothing (the target already had it — R4);
  - `T == pre_state or T == W` → nothing;
  - else → REFUSE `"canceled <WP>'s change to '<path>' was merged with an independent change; the gate cannot prove it is absent"` (+ same recovery sentence).
  - `GitProbeError` → REFUSE.
- FAIL entries must be merged into whatever the strategy branch returns: simplest is to compute them first and, after the strategy result, if the strategy result is PASS and entries exist → `VerifyResult.failed(Divergence(canceled_content=...))`; if the strategy result is FAIL → a new `Divergence` combining both (use `dataclasses.replace`). A strategy REFUSE stays REFUSE.

### Subtask T025 – `Divergence.canceled_content` + rendering

- Field `canceled_content: tuple[CanceledPathState, ...] = ()`; `describe()` renders per entry:
  - modify/add: `file '<path>' carries canceled <WP>'s change (lane <lane>) on the target — canceled work would ship; revert <WP>'s change to '<path>' on the lane through a surviving WP's governed work, then re-run spec-kitty consolidate`
  - deletion (`canceled_state is None`): `file '<path>' was deleted by canceled <WP> (lane <lane>) and that deletion is on the target — approved content would be lost; …same recovery…`
  WP02 asserts the substring `carries canceled WP02's change` for add/modify — for deletions assert on `deleted by canceled WP02` (update WP02's expectation via review feedback if its delete assertion used the other wording; coordinate in the activity log).
- Update the `Divergence` docstring.

- **Rendering contract with WP02 (binding, from WP02 review cycle 2):** WP02's tests extract the verdict block (text after `Reconciliation FAILED` / `Reconciliation refused (fail-closed)`), split it on `;`, and match clause by clause. Each divergence clause MUST name its path in single quotes (`'<path>'`) together with its wording (`carries canceled WP02's change` for add/modify, `deleted by canceled WP02` for deletions) in the SAME `;`-separated clause, and the REFUSE reason must contain `no commit attribution`, the lane id and `re-run spec-kitty consolidate` (backticks are stripped by the tests). Do not introduce `;` inside a single clause.

### Subtask T026 – Docstring correction + complexity

- `_collect_excluded` docstring (`:1160-1166`) currently states that "a canceled WP's own work" is never subtracted — that is the #5046 hole written as a guarantee. Correct it and point to the `canceled_content` axis.
- Run `uv run --frozen ruff check --select C901 src/specify_cli/consolidation/reconciliation.py`.

### Subtask T027 – Tests

In `tests/consolidation/test_reconciliation.py` (git-backed, same style as the existing tests there):
- one **parametrized table test** per contract C3 row: never-implemented canceled → unchanged; unattributable (each reason, **including `events_unreadable` via a corrupted `status.events.jsonl`**: mixed lane → REFUSE, non-mixed lane → unchanged) → REFUSE with the reason text; resolved + no unsuperseded content → PASS; target carries canceled state → FAIL; survivor-undone (W == canceled, `pre_state_by_survivor`) → FAIL; target already carried it (W == canceled, inherited pre-state) → no finding; merged-with-independent-change → REFUSE.
- message tests: every FAIL and every REFUSE reason's rendered text names the lane, the WP, a path or the missing evidence, and contains `re-run spec-kitty consolidate` (NFR-003).
- each under both `verify_reachability=True` and `False` (strategy independence, C-003), and one rebase-shaped claim.
- precedence: unattributable + unsuperseded both present → REFUSE.
- byte-identical pin: for a representative set of inputs, the pre-existing claim fields equal those computed by the unmodified collectors (call the collectors directly and compare).
- then run WP02's files and `test_repro_5018.py`.

## Test Strategy

```bash
uv run --frozen pytest tests/consolidation/test_reconciliation.py tests/consolidation/test_reconciliation_divergent.py tests/consolidation/test_wp_attribution.py tests/consolidation/test_executor_terminus_integrity.py tests/consolidation/test_merge_canceled_wp.py tests/consolidation/test_done_bookkeeping_seam.py -q
PWHEADLESS=1 uv run --frozen pytest tests/terminus/test_repro_5046.py tests/terminus/test_repro_5046_controls.py tests/terminus/test_repro_5018.py tests/terminus/test_repro_5022.py -q
uv run --frozen pytest tests/architectural/test_merge_pipeline_ratchets.py tests/architectural/test_status_module_boundary.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_read_side_bypass.py -q
uv run --frozen ruff check src/specify_cli/consolidation tests/consolidation && uv run --frozen ruff format --check src/specify_cli/consolidation tests/consolidation
uv run --frozen mypy src/specify_cli/consolidation/reconciliation.py src/specify_cli/consolidation/wp_attribution.py
```
Also run, file by file, every test file found by `grep -rlE "ApprovedWpCommitSet|build_approved_wp_set|run_terminus" tests` (SC-004 ratchet) and record the list with pass counts in the activity log.

## Risks & Mitigations

- False FAIL on superseded content (issue 5018 class): WP02 controls + `test_repro_5018` are the net — they must stay green.
- Reading events for non-mixed missions would change behaviour on unreadable logs — only read when needed.

## Review Guidance

- Reviewer confirms WP02's repro file is GREEN now and was RED at WP02's head (red→green).
- Confirm the byte-identical pin exists and is non-vacuous (it would fail if a collector changed).
- Confirm REFUSE vs FAIL wording distinct and recovery sentence present.

## Activity Log

- 2026-09-28T15:40:00Z – system – Prompt created.
