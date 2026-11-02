# Quickstart: reproduce and verify the approved-reopen fix

## 1. See the defect on the merge base (pre-fix)

```sh
uv run python - <<'PY'
from specify_cli.cli.commands.agent.tasks_transition_core import build_transition_plan
from spec_kitty_events.status import validate_transition, StatusTransitionPayload, Lane, ExecutionMode

plan = build_transition_plan(
    old_lane="approved", target_lane="in_progress", force=False,
    review_feedback_pointer=None, arb_review_ref=None, note_text=None,
)
print(plan.emit_force, plan.emit_review_ref)   # True None   <- wire-invalid
p = StatusTransitionPayload(
    mission_slug="m", wp_id="W", from_lane=Lane.APPROVED, to_lane=Lane.IN_PROGRESS,
    actor="cli", force=plan.emit_force, reason=plan.emit_reason,
    execution_mode=ExecutionMode("direct_repo"), review_ref=plan.emit_review_ref, evidence=None,
)
print(validate_transition(p).valid)            # False
PY
```

## 2. Verify the fix

```sh
# The sentinel now cites the operator rewind on the forced arm.
uv run python - <<'PY'
from specify_cli.cli.commands.agent.tasks_transition_core import build_transition_plan
plan = build_transition_plan(
    old_lane="approved", target_lane="in_progress", force=False,
    review_feedback_pointer=None, arb_review_ref=None, note_text=None,
)
assert plan.emit_force is True and plan.emit_review_ref == "force-override", plan
print("conforming:", plan)
PY

# The targeted suites that own the behaviour.
uv run pytest -q tests/status/test_forced_rewind_requires_review_ref.py
uv run pytest -q tests/specify_cli/status/test_wp_state.py tests/status/test_validate.py
uv run pytest -q tests/integration/test_owned_reopen_feedback.py
```

## 3. Drive the reported repro through the real CLI

The git-backed owned-checkout fixture is the reproduction harness:

```sh
uv run pytest -q "tests/integration/test_owned_reopen_feedback.py::test_owned_approved_reopen_feedback_contract" -k absent -vv
```

It walks a WP to `approved` through the real command, then runs
`move-task WP01 --to in_progress` with no feedback file and asserts the recorded row is
`force: true` / `review_ref: "force-override"` and that the same row validates against the
pinned contract.

## 4. Check a door refuses before appending

```sh
uv run pytest -q tests/status/test_forced_rewind_requires_review_ref.py -k "refused_before_append or pointer_carrying"
```

The refusal case asserts the log and snapshot SHA-256 are unchanged; the paired
pointer-carrying case on the same fixture asserts one row lands and `status validate` is
clean.

## What must NOT change

- `uv run pytest -q tests/integration/test_owned_reopen_feedback.py -k "provided or empty or missing"`
  — the #6845 evidence arm (force-free + file pointer; empty/missing refused).
- Every forced edge outside the family: `tests/status/test_transition*.py`,
  `tests/specify_cli/status/test_wp_state.py -k forced`.
