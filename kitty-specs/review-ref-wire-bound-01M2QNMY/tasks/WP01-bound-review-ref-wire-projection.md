---
work_package_id: WP01
title: Bound legacy-prose review_ref at the WPStatusChanged wire projection
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
- C-005
planning_base_branch: issue-3954-review-ref-wire-bound
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on issue-3954-review-ref-wire-bound. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-review-ref-wire-bound-01M2QNMY
base_commit: c0538f83650cdc5e323a5d31a734119329c4143c
created_at: '2026-09-17T12:59:11.472042+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Implementation
history:
- at: '2026-09-17T12:45:00Z'
  actor: system
  action: Prompt generated for review-ref-wire-bound mission
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/specify_cli/cli/commands/agent/test_move_task_review_ref_broadcast.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/status/zeitgeist_bridge.py
- tests/status/test_zeitgeist_moment_handler.py
- tests/specify_cli/cli/commands/agent/test_move_task_review_ref_broadcast.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Bound legacy-prose review_ref at the WPStatusChanged wire projection

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (role: implementer) via the profile-load skill before proceeding.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## Objectives & Success Criteria

Fix F-46 (#3954): a `WPStatusChanged` moment carrying a legacy-prose `review_ref` >240 UTF-8 bytes is dropped whole; make it broadcast bounded instead.

Done when:
- A prose `review_ref` is collapsed to one line and truncated to ≤240 UTF-8 bytes with a trailing `…` (codepoint-safe, byte-identical to the codec's `_truncate_utf8`), the moment is offered **exactly once**, and the full note is still in `status.events.jsonl`.
- A **pointer-shaped** `review_ref` rides the wire verbatim (never truncated).
- The bound is applied to **all four transition families**: approval, completion, rejection/rework, direct emission.
- A truncation logs at **INFO**; the change is marked interim (`# SUNSET: remove when #4327 lands`, `refs #3954`).
- The #4318 stale docstring is corrected.
- All 8 ATDD cases (T1–T8) pass; `ruff`/`mypy` clean.

## Context & Constraints

- Charter: `.kittify/charter/charter.md`. Plan: `kitty-specs/review-ref-wire-bound-01M2QNMY/plan.md`. Spec: `.../spec.md`. Helper contract (authoritative I/O table + invariants): `.../contracts/review_ref_bound.md`. Research: `.../research.md`.
- **Change site**: `src/specify_cli/status/zeitgeist_bridge.py` → `_broadcast_status_transition` (~L169), where `review_ref` is read from `metadata.review_ref`. Apply the bound there, before `_broadcast_moment`/`to_zeitgeist_attrs`.
- **HARD boundaries (C-002/C-003)**: do NOT edit the events package (`spec_kitty_events`), `tasks_move_task.py`, or `emit.py`. One helper in the bridge only — no duplication (whack-a-field risk vs #4336).
- **KISS (C-005)**: minimal, pointer-biased structural classifier — NO regex sentence/em-dash detector (that got #4319 closed).
- Events pin stays `>=9,<10` (C-001). Byte bound = UTF-8 **bytes**, not chars (NFR-001).
- **Order matters**: collapse whitespace (`" ".join(value.split())`) BEFORE the byte check and BEFORE the codec's printable guard.

## Branch Strategy

- **Strategy**: single_branch (stay on `issue-3954-review-ref-wire-bound`)
- **Planning base branch**: main
- **Merge target branch**: main

## Subtasks & Detailed Guidance

### Subtask T001 [P] – RED-first e2e regression tests (T1–T4)

- **Purpose**: Prove F-46 across the four transition families through the pre-existing entry points, RED before the fix.
- **File (create)**: `tests/specify_cli/cli/commands/agent/test_move_task_review_ref_broadcast.py`
- **Cases**:
  - **T1** `move-task --to approved --note <>240B multi-line prose containing a real newline>` → capture the ACTUAL offered attr value via the `OfferRecorder` and assert `len(offered_review_ref.encode("utf-8")) <= 240`, single-line (no `\n`), ends with `…`; AND read the full multi-line note back from `status.events.jsonl` byte-for-byte. Do NOT make log-presence the pass condition (fakeable); the INFO log is an additional assertion, not the proof. The note MUST contain a real newline (the 9.1.6 codec rejects control chars on ENCODE, so whitespace-collapse must precede the codec — this case proves ordering). (SHOULD-FIX S2, NIT N2)
  - **T2** a GENUINE multi-hop `move-task` command that emits more than one status event → assert `offers == number_of_emitted_events` (NOT `== 1`). (SHOULD-FIX S2)
  - **T3** `move-task --to doing --note <long>` (rejection/rework, the review_ref-required edge) → bounded broadcast, one offer.
  - **T4** `emit_status_transition` with prose ref + clock-derived `at=` → bounded broadcast.
- **Mark**: `@pytest.mark.regression`, docstring/comment `#3954`. Use valid FSM fixtures. Black-box (assert stdout/exit/offer-count/persisted log), not internals.
- **Notes**: reuse the existing `OfferRecorder.moment_offers()` recorder (`tests/status/test_zeitgeist_moment_handler.py` ~L87/L109) for offer capture/counting; realistic (production-shaped) ids and note lengths.

### Subtask T002 [P] – RED-first seam-unit safety tests (T5–T8)

- **File (extend)**: `tests/status/test_zeitgeist_moment_handler.py`
- **Cases**:
  - **T5** over-bound **pointer** (a path with spaces, >240B) rides verbatim; if the codec still rejects it, the drop is loud (a logged warning names `review_ref`) — never a silently corrupted broadcast.
  - **T5b (accepted-degradation edge, SHOULD-FIX S1)** a single-line **prose** note >240B that contains `/` is (correctly, under the KISS classifier) classified as a pointer and therefore NOT truncated → the codec drops it; assert the drop is LOUD (logged warning naming `review_ref`), never silently corrupted. This pins the "fail toward loud pointer-drop" invariant and documents the classifier's one known liability. Do NOT reopen the #4319 regex debate — this degradation is ratified (C-005).
  - **T6** codepoint boundary — a multi-byte char at the 240-byte cut is never split; `…` budget honored. **Pin byte-identity to the codec's `_truncate_utf8`** (budget 237, `errors="ignore"`, value returned unchanged when ≤240 bytes). (NIT N1)
  - **T7** exactly-one-offer single-hop.
  - **T8** an over-bound **non-review_ref** attr is untouched → existing codec fail-closed behavior unchanged.
- **Mark**: `@pytest.mark.regression`, `#3954`.

### Subtask T003 – Implement the bound helper + wire it in

- **File**: `src/specify_cli/status/zeitgeist_bridge.py`
- **Steps**: add `_bound_wire_review_ref(value: str | None) -> str | None` per `contracts/review_ref_bound.md` (None/empty → unchanged; pointer → verbatim; prose → collapse → ≤240B else 237-byte codepoint-safe prefix + `…` + INFO log). Apply it where `review_ref` enters the `StatusTransitionPayload` in `_broadcast_status_transition`. Add `# SUNSET: remove when #4327 lands` + `refs #3954`.
- **Turns T001/T002 GREEN.**

### Subtask T004 – #4318 docstring campsite

- Correct `_first_non_printable_attr`'s stale docstring (it names the 8.2.0 pin and claims the codec has no printability check; 9.1.6 has `_reject_control_characters`). Reference #4318.

### Subtask T005 – Verify

- Run the blast radius (see Test Strategy) GREEN; `ruff check .` (or scoped), `ruff format --check`, `mypy` clean.
- Relocate any purely-transitional repro out of `@regression` (durable seam-unit + e2e stay as guards); keep the F-46 repro as the issue-pinned guard.
- **Completeness gate (NIT N4)**: confirm the NEW e2e file `tests/specify_cli/cli/commands/agent/test_move_task_review_ref_broadcast.py` is discovered by CI — i.e. it is picked up by the per-module test matrix / coverage-breadth baseline (shard maps), not just a local `pytest` run. A new test file that is not in the shard map is invisible to CI.
- Note (NIT N3): `action-review-claim` (workflow_executor.py:1696) is a short semantic pointer that the structural classifier treats as prose — harmless (well under 240 bytes, never truncated in practice); no action, recorded so a reviewer doesn't flag it.

## Test Strategy

- **Blast radius** (record commands + counts): the two owned test files, plus `tests/status/` (owning subsystem), plus `make test-fast` baseline.
  - `.venv/bin/python -m pytest tests/status/test_zeitgeist_moment_handler.py tests/specify_cli/cli/commands/agent/test_move_task_review_ref_broadcast.py -q`
  - `.venv/bin/python -m pytest tests/status/ -q`
  - `make test-fast`
- Typecheck: `.venv/bin/python -m mypy -p specify_cli` (or the configured command). A passing test runner does not replace compiler diagnostics.

## Risks & Mitigations

- Codepoint split → codepoint-safe truncation, T6 guard.
- Classifier over/under-reach → pointer-biased + loud pointer-drop fallback; T5/T8.
- Double-offer → T7 + existing `recorder.moment_offers()` assertions.

## Review Guidance

- Confirm: bound applied before `to_zeitgeist_attrs`; only `review_ref` transformed; no edits outside the one source file + two test files; pointers verbatim; full local note preserved; exactly one offer; INFO log; SUNSET marker; #4318 fixed; ruff+mypy clean.

## Activity Log

- 2026-09-17T12:45:00Z – system – Prompt created.
