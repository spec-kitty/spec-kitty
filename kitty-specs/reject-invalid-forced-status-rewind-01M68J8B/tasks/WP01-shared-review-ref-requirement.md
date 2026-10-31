---
work_package_id: WP01
title: One requirement, enforced before the append (#6514)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-005
- FR-006
- SC-001
- SC-002
- SC-003
- SC-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-003
planning_base_branch: issue-6514-reject-invalid-forced-status-rewind
merge_target_branch: issue-6514-reject-invalid-forced-status-rewind
branch_strategy: Planning artifacts for this mission were generated on issue-6514-reject-invalid-forced-status-rewind. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6514-reject-invalid-forced-status-rewind unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-reject-invalid-forced-status-rewind-01M68J8B
base_commit: de1af6c7ef505850b7f3325be5c29739403a5097
created_at: '2026-10-31T08:51:26.344941+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - The rule
history:
- at: '2026-10-31T08:55:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/wp_state.py
create_intent:
- tests/status/test_forced_rewind_requires_review_ref.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/wp_state.py
- src/specify_cli/status/validate.py
- src/specify_cli/status/work_package_lifecycle.py
- src/specify_cli/cli/commands/agent/tasks_transition_core.py
- tests/status/test_forced_rewind_requires_review_ref.py
- tests/status/test_transitions.py
- tests/status/fsm_parity_baseline.jsonl
- tests/status/test_work_package_lifecycle.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6514'
---
# Work Package Prompt: WP01 – One requirement, enforced before the append (#6514)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` via `spec-kitty agent tasks status`; address every item; record with
`spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

Close #6514 at its root: the fact "an event on `for_review → in_progress` must carry a
`review_ref`" gets **one** owning definition, the write path enforces it before any
append, and the auditor reads that same definition instead of restating it.

Done when, on one fixture mission carrying a WP in `for_review`:

1. `agent status emit WP01 --to in_progress --actor codex --force --reason "<why>"`
   exits non-zero, and **both** `status.events.jsonl` and `status.json` are byte-identical
   afterwards (same SHA-256);
2. `agent status validate --mission <slug>` exits 0 right after that refusal;
3. re-running the same command **with** `--review-ref <ref>` exits 0, appends exactly one
   row, and validates clean — the positive control on the same fixture;
4. the same forced rewind with `--review-ref "   "` (whitespace only) is refused.

## Context & Constraints

- Spec FR-001..FR-003, FR-005, FR-006, SC-001/002/003/006, NFR-001..NFR-003, C-001, C-003.
  Plan §"Engineering Alignment". Research §2..§5. Contract
  `contracts/forced-rewind-refusal.md` C-1..C-5. Data model: `REVIEW_REF_REQUIRED_EDGES`,
  `requires_review_ref`, the one requirement expression.
- **The edge is force-only.** `ForReviewState.allowed_targets()` is
  `{in_review, blocked, canceled}`; `for_review → in_progress` has no structural edge, so
  only `ctx.force` admits it. **Do not add the edge** — that would widen the lane graph.
- **Never put the check in `guard_for`.** `wp_state.py` states the rule at
  `InProgressState.guard_for`: *"guards must NOT consult `ctx.force`"*, and force bypasses
  guards entirely, so a guard-only requirement is dead on the only path this edge has.
- **Preserve the force-free message.** A force-free attempt must keep returning
  `Illegal transition: for_review -> in_progress` from the structural check, in the same
  order as today (contract C-5). Return from the structural branch before evaluating the
  new requirement.
- **One definition only.** `validate.py` already imports from `wp_state`
  (`wp_state_for`), so the predicate belongs in `wp_state.py`; adding a second inline copy
  in `validate.py` is the review finding this WP must not produce.
- **No auto-filled sentinel.** Do not manufacture `review_ref` on refusal. `move-task`
  supplies `force-override` as its own deliberate choice; a generic door inventing a
  pointer is out of scope (research D-1).
- Do not touch `in_review → in_progress` (research D-6) and do not touch any
  `status.events.jsonl` bytes (C-002).
- `src/specify_cli/status/` must not import `specify_cli.coordination`
  (`tests/architectural/test_status_module_boundary.py`).

## Branch Strategy

- **Planning base branch**: `main`
- **Merge target branch**: `main`

Implement with `spec-kitty agent action implement WP01 --agent pi --mission reject-invalid-forced-status-rewind-01M68J8B`.

## Subtasks & Detailed Guidance

### T001 – Red-first CLI acceptance test (own commit, must be red)

New `tests/status/test_forced_rewind_requires_review_ref.py`. Follow the existing harness in
`tests/status/test_agent_status_emit_cli.py`: `CliRunner`, `tests.status.conftest.seed_wp_to_planned`,
`patch("specify_cli.cli.commands.agent.status.locate_project_root")` and
`patch("specify_cli.cli.commands.agent.status._find_mission_slug")`, and the module's
`_disable_emit_side_effects` fan-out monkeypatch. Seed `planned → claimed → in_progress →
for_review` through the same `emit` command (the `for_review` hop needs
`--subtasks-complete --implementation-evidence-present`).

One shared fixture, then:

- `test_invalid_forced_rewind_is_refused_before_append`: capture
  `hashlib.sha256` of `status.events.jsonl` **and** `status.json`, run the pointerless
  forced rewind, assert `exit_code != 0`, assert both digests are unchanged, and assert the
  `--json` payload has no `event_id` and its `error` contains `review_ref` and
  `--review-ref` (NFR-003).
- `test_validation_passes_after_the_refusal`: on the same fixture, run
  `app ["validate", "--mission", ...]` → exit 0.
- `test_pointer_carrying_forced_rewind_still_appends`: same fixture, same request plus
  `--review-ref "review-cycle://WP01/1"` → exit 0, exactly one row appended, that row's
  `review_ref` preserved, and `validate` exits 0.
- `test_whitespace_only_review_ref_is_treated_as_absent`: `--review-ref "   "` → refused,
  nothing appended.

Commit with the message `test(6514): pin the forced for_review rewind refusal (red)` and
record the red output. Non-vacuity: the pointer-carrying test is the same-fixture positive
control for the refusal assertions.

### T002 – `REVIEW_REF_REQUIRED_EDGES` + `requires_review_ref()` (own commit)

In `src/specify_cli/status/wp_state.py`, next to the other shared message constants:

```python
#: Edges whose persisted events the schema validator refuses without a
#: ``review_ref`` (#6514). Force may bridge a missing edge; it may not produce
#: an event this tool's own auditor calls malformed.
REVIEW_REF_REQUIRED_EDGES: frozenset[tuple[Lane, Lane]] = frozenset(
    {(Lane.FOR_REVIEW, Lane.IN_PROGRESS)}
)


def requires_review_ref(from_lane: Lane | str, to_lane: Lane | str) -> bool:
    """True when an event on this edge must carry a ``review_ref``. ..."""
```

Coerce with `Lane(...)`-tolerant comparison or compare resolved values; state in the
docstring that it is a membership test only and that whitespace handling belongs to the
requirement check. Export it the way the module exports its other helpers (check
`src/specify_cli/status/__init__.py` — add it only if the auditor needs the re-export;
`validate.py` may import it from `.wp_state` directly).

### T003 – `check_transition` enforcement (own commit)

Add the message constant, e.g.

```
_REVIEW_REF_REQUIRED = (
    "Transition {source} -> {target} requires review_ref: a forced rewind out of review "
    "must cite the review feedback it is rewinding (pass `--review-ref <ref>`)."
)
```

Restructure `WPState.check_transition` to this order, keeping every existing message:

1. `target == Lane.GENESIS` → unchanged refusal.
2. No structural edge **and** not forced → unchanged `Illegal transition: ...` (this is
   what keeps contract C-5 true).
3. `requires_review_ref(self.lane, target)` and `not (ctx.review_ref or "").strip()` →
   `(False, message)`.
4. `ctx.force` → `_check_force(ctx)` (actor + reason), unchanged.
5. Otherwise `self.guard_for(target, ctx)`, unchanged.

Then add a unit pin in the same file's test module (T005) that a forced attempt on the edge
returns the new message, and that `can_transition_to(IN_PROGRESS, ctx)` still returns
`False` (its contract says force is not consulted there —
`tests/status/test_wp_state_force_free_contract.py::test_t013_for_review_has_no_backward_edge`).

Commit: `fix(6514): refuse a forced for_review rewind that carries no review_ref`.

### T004 – `validate_event_schema` reads the shared predicate (own commit)

In `src/specify_cli/status/validate.py`, replace the inline

```python
if event.get("from_lane") == Lane.FOR_REVIEW and event.get("to_lane") == Lane.IN_PROGRESS and not event.get("review_ref"):
```

with a call to `requires_review_ref(...)` plus the same `strip()` test, keeping the
finding text **byte-identical** (`Event {event_id}: for_review->in_progress without
review_ref`) — existing tests and operators match on it. Guard the call against
non-canonical / unhashable lane values the same way `_edge_is_legal` does (a `ValueError`
from `Lane(...)` must not escape the auditor; schema findings already cover a bad lane).

Update the `validate_event_schema` docstring's check list to say the rule is the shared
`wp_state.REVIEW_REF_REQUIRED_EDGES` definition.

Commit: `refactor(6514): the auditor reads the one review_ref requirement definition`.

### T005 – Unit pins (own commit, or folded into T003 where it reads naturally)

In `tests/status/test_forced_rewind_requires_review_ref.py` (unit half) or
`tests/status/test_wp_state_force_free_contract.py`:

- `requires_review_ref(FOR_REVIEW, IN_PROGRESS) is True`; a sample of the other edges
  (`IN_REVIEW → IN_PROGRESS`, `FOR_REVIEW → PLANNED`, `DONE → IN_PROGRESS`) is `False`.
- `wp_state_for("for_review").check_transition(Lane.IN_PROGRESS, GuardContext(force=True,
  actor="codex", reason="why"))` → `(False, message)` with `review_ref` and
  `--review-ref` in it.
- The same with `review_ref="force-override"` → `(True, None)`.
- The same with `review_ref="   "` → `(False, message)`.
- Force-free: `check_transition(Lane.IN_PROGRESS, GuardContext(actor="codex", reason="why"))`
  still returns the `Illegal transition: for_review -> in_progress` text.
- `validate_event_schema` on a hand-built event dict on the edge: no `review_ref` → the
  historical finding; with `review_ref` → no finding.

Commit: `test(6514): pin the review_ref requirement on the edge and in the auditor`.

## Test commands

```bash
uv run pytest -q tests/status/test_forced_rewind_requires_review_ref.py
uv run pytest -q tests/status/test_validate.py tests/status/test_wp_state_force_free_contract.py \
  tests/status/test_agent_status_emit_cli.py tests/status/test_transition_pipeline.py
uv run pytest -q tests/architectural/test_status_module_boundary.py
```

## Definition of Done

- T001 committed red before T002; the final tree is green.
- No new copy of the requirement rule anywhere.
- `status.events.jsonl` / `status.json` byte-identical across a refusal.
- Diff coverage on changed lines ≥ 90%.
