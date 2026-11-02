---
work_package_id: WP01
title: One definition, conforming payload, refusing doors (#6955)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-008
- FR-009
- SC-001
- SC-002
- SC-003
- SC-004
- SC-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
- C-006
planning_base_branch: issue-6955-wire-valid-approved-reopen
merge_target_branch: issue-6955-wire-valid-approved-reopen
branch_strategy: Planning artifacts for this mission were generated on issue-6955-wire-valid-approved-reopen. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6955-wire-valid-approved-reopen unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-wire-valid-approved-reopen-01M6EJW0
base_commit: e66c896c5306be8f79f3b8b17eb5c2c23f57a064
created_at: '2026-11-02T16:58:37.785045+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - The rule
history:
- at: '2026-11-02T17:00:00Z'
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
- src/specify_cli/cli/commands/agent/tasks_transition_core.py
- tests/status/test_forced_rewind_requires_review_ref.py
- tests/status/test_transitions.py
- tests/status/fsm_parity_baseline.jsonl
- tests/specify_cli/cli/commands/agent/test_move_task_feedback_file_edges.py
- tests/integration/test_owned_reopen_feedback.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6955'
---
# Work Package Prompt: WP01 – One definition, conforming payload, refusing doors (#6955)

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

Close #6955 at its root: the emitted forced `approved -> in_progress` rewind must be a
payload the pinned `spec_kitty_events` contract accepts, and no write door may append a
pointerless rewind on the contract's "Review-Ref-Gated Rewind Family".

Done when:

1. the owned-checkout `move-task WP01 --to in_progress` repro on an approved WP with **no**
   `--review-feedback-file` records `force: true` and `review_ref: "force-override"`, and
   that exact payload validates against the pinned contract (pre-fix: `None`, invalid);
2. `agent status emit WP01 --to in_progress --force --reason "<why>"` on a WP in
   `approved` (and in `in_review`) exits non-zero naming `review_ref`, with
   `status.events.jsonl` and `status.json` byte-identical; the same request with
   `--review-ref force-override` appends one row and validates clean;
3. a supplied `--review-feedback-file` still wins: the row is `force: false` and cites the
   file (the #6845 arm, unchanged);
4. no second literal edge set exists anywhere.

## Context & Constraints

- Spec FR-001..FR-006, FR-008, FR-009, SC-001..SC-005, NFR-001..NFR-003, C-001..C-004,
  C-006. Plan §"Implementation Concern Map". Research R1..R6. Contract
  `contracts/review-ref-gated-rewind.md` C-RRR-1..C-RRR-5. Data model tables.
- **Do not touch the wire contract.** `spec-kitty-events` is a pinned dependency; the
  payload conforms to it (`C-001`). Do not edit `pyproject.toml`, the pin files or anything
  under `services/`.
- **Do not change force policy.** The forced arm stays forced, the evidence arm stays
  force-free (`C-002`). Do not add or remove a guard; the writer's existing
  force-insurmountable branch already refuses with `review_ref_required_message`.
- **The evidence arm is part of this WP** (research R7): the approved reopen must accept a
  supplied `--review-feedback-file` again and record it as `review_ref`, force-free. That is
  `_feedback_edge_recordable` gaining `_is_approved_reopen`, nothing else.
- **The sentinel fill already exists.** `build_transition_plan` fills `force-override` when
  `emit_force and requires_review_ref(old, target)` and no pointer was supplied. Widening
  the set is what makes it apply to the approved reopen — do not add an edge-specific
  branch.
- **One definition only.** `REVIEW_REF_REQUIRED_EDGES` in `status/wp_state.py` is the single
  source; the emitter, the writer and the auditor keep reading it (`C-004`).
- **Never widen to `* -> planned`.** The review-rejection family keeps its own rule,
  optional `review_ref`, and message (`C-006`).
- Do not rewrite, correct or back-fill any `status.events.jsonl` bytes (`C-003`).
- `src/specify_cli/status/` must not import `specify_cli.coordination`
  (`tests/architectural/test_status_module_boundary.py`).

## Branch Strategy

- **Planning base branch**: `main`
- **Merge target branch**: `main`

Implement with `spec-kitty agent action implement WP01 --agent pi --mission wire-valid-approved-reopen-01M6EJW0`.

## Subtasks & Detailed Guidance

### T001 – Red-first: the owned-checkout repro asserts the sentinel and wire validity (own commit, must be red)

Extend `tests/integration/test_owned_reopen_feedback.py`'s
`test_owned_approved_reopen_feedback_contract`. For `kind == "absent"` (today it asserts
`force is True` and `review_ref is None`), assert instead:

- `event.force is True` (the FR-015 forced arm is untouched);
- `event.review_ref == "force-override"` (**this is the red assertion**);
- rebuild the recorded row as `spec_kitty_events.status.StatusTransitionPayload` from the
  event's own fields and assert `validate_transition(payload).valid is True` (also red
  pre-fix — this is the issue's exact complaint, not a proxy for it).

Keep the `missing` / `directory` kinds as they are. The `provided` and `empty` kinds are
**already red on the merge base** (research R7): `_feedback_edge_recordable` (#6699) treats
the approved reopen as non-recordable and refuses the flag before the file is read, so the
#6845 arm is broken. Tighten them instead of relaxing them — `provided` must record
`force is False` and `review_ref == str(feedback.resolve())`; `empty` must be refused with
the *empty-file* message (`Review feedback file is empty: ...`), not the
"writes no review cycle" message. Both assertions are red today and both must be green
after T003; they are the restore half of the compound fix (the sentinel is the other half).
Run the suite and keep the red output. Commit:
`test(6955): pin the approved reopen's two conforming arms (red)`.

### T002 – Red-first: pointerless gated rewinds are refused at the door (own commit, must be red)

In `tests/status/test_forced_rewind_requires_review_ref.py`, reuse the existing fixture
harness (`repo_in_review`, `_invoke`, `_digest`, `_rows`, `_assert_validate_clean`, the
autouse fan-out monkeypatch). Generalise the fixture so the WP can be seeded to `in_review`
and `approved` through the same `agent status emit` hops (approval needs a review artefact
or `--force` — pick the cheapest legal route and say which in the test docstring), then add:

- `test_pointerless_gated_rewind_is_refused_before_append` parametrised over `in_review` and
  `approved`: pointerless forced `--to in_progress` → `exit_code != 0`, log and snapshot
  SHA-256 unchanged, `review_ref` and `--review-ref` in the JSON `error`, no `event_id`;
- `test_pointer_carrying_gated_rewind_still_appends` on the **same** fixtures: the same
  request plus `--review-ref force-override` → exit 0, exactly one row, `review_ref`
  preserved, `validate` exits 0 (the same-fixture positive control the non-vacuity tactic
  requires);
- `test_whitespace_only_review_ref_is_refused_on_the_gated_family`: `--review-ref "   "` is
  treated as absent on the added edges.

Commit: `test(6955): pin the pointerless gated rewind refusal (red)`.

### T003 – Widen the one definition (own commit)

In `src/specify_cli/status/wp_state.py`:

- add `(Lane.IN_REVIEW, Lane.IN_PROGRESS)` and `(Lane.APPROVED, Lane.IN_PROGRESS)` to
  `REVIEW_REF_REQUIRED_EDGES`;
- rewrite its comment/docstring to name the owning authority: the pinned
  `spec_kitty_events` "Review-Ref-Gated Rewind Family" (three `-> in_progress` edges,
  requirement holds whether the event is forced or not), and say the arrangement is
  deliberately the whole family so the writer, the auditor and the emitter cannot drift.

In `src/specify_cli/status/validate.py`, update the module/function prose that says the set
is "today: `for_review -> in_progress`" so it names the family (no logic change — it
already calls `requires_review_ref`).

In `src/specify_cli/cli/commands/agent/tasks_transition_core.py`:

- update the #6514 comment above the sentinel fill: it now covers the whole family, and cite
  #6955 for the approved reopen. No behavioural branch is added there;
- restore the evidence arm (research R7): `_feedback_edge_recordable` must also return `True`
  for the approved reopen (`_is_approved_reopen(old, target)`), because that edge *does*
  record the supplied file as the event's `review_ref`. Reuse the canonical predicate — no
  second edge list — and extend `_feedback_file_no_effect_message`'s recordable-family list
  with the approved reopen so the refusal text stays truthful. The #6699 test matrix lists
  `for_review -> in_progress` as non-recordable and never claims this edge, so the restore
  contradicts no existing pin; add the approved reopen to
  `test_guard_leaves_recordable_edges_alone` and to the recordable half of
  `tests/specify_cli/cli/commands/agent/test_move_task_feedback_file_edges.py`.

Commit: `fix(6955): conform the approved reopen and restore its evidence arm`.

### T004 – Emitter pin and the family ratchet (own commit)

In `tests/status/test_forced_rewind_requires_review_ref.py`:

- `test_build_transition_plan_fills_the_sentinel_for_the_approved_reopen`: call the
  production planner with `old_lane="approved"`, `target_lane="in_progress"`,
  `force=False`, `review_feedback_pointer=None`; assert `emit_force is True` and
  `emit_review_ref == "force-override"`, and that the same plan with a supplied pointer
  keeps the pointer and `emit_force is False`.
- `test_local_edge_set_equals_the_pinned_contract_family`: enumerate
  `REVIEW_REF_REQUIRED_EDGES` and assert it equals the three pairs; for each, build a
  pointerless forced `StatusTransitionPayload` with the **real** pinned
  `spec_kitty_events.status.validate_transition` and assert it is invalid, and that the
  `force-override`-carrying twin is valid. This is the ratchet that stops the local set and
  the dependency from re-splitting, and it fails if someone "fixes" the test by editing the
  set to a narrower or wider one (`FR-009`).

Commit: `test(6955): ratchet the local family to the pinned contract`.

### T005 – Writer pins and the unchanged-edge matrix (own commit)

In `tests/specify_cli/status/test_wp_state.py` (or the existing force-free contract module):

- `approved`/`in_review` + `check_transition(IN_PROGRESS, GuardContext(force=True,
  actor=..., reason=...))` → `(False, message)` containing `review_ref` and
  `--review-ref`;
- the same with `review_ref="force-override"` → `(True, None)`;
- the same with `review_ref="   "` → `(False, message)`;
- `migration:backfill` actor → `(True, None)` (the #5446 exemption, `FR-008`);
- force-free `approved -> in_progress` with a review_ref still passes its own guard
  (`test_approved_to_in_progress_requires_review_ref` must stay green).

Add an explicit matrix pin for `NFR-003`: iterate every `(from_lane, to_lane)` pair over the
canonical lanes, compute `check_transition` with a forced actor+reason and no review_ref on
the current tree versus a hard-coded expectation table, and assert exactly the three family
pairs are refused. Prefer an expectation table that a reviewer can read over a snapshot
file; no golden regeneration.

Commit: `test(6955): pin the writer's gated-family refusal and the unchanged matrix`.

### T006 – Auditor pins (own commit)

In `tests/status/test_validate.py`:

- a hand-built `approved -> in_progress` row with `review_ref: null` produces the existing
  `... without review_ref` finding shape (and one for `in_review`);
- the same row with `review_ref: "force-override"` produces no such finding;
- a `migration:backfill`-actor row without a pointer still produces the finding (the
  auditor reports, the writer exempts — `FR-008`);
- an `approved -> in_progress` row that is **force-free with a pointer** stays clean.

Commit: `test(6955): pin the auditor's family verdict`.

## Test commands

```bash
uv run pytest -q tests/status/test_forced_rewind_requires_review_ref.py
uv run pytest -q tests/status/test_validate.py tests/specify_cli/status/test_wp_state.py
uv run pytest -q tests/integration/test_owned_reopen_feedback.py
uv run pytest -q tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py tests/status/test_transitions.py
uv run pytest -q tests/architectural/test_status_module_boundary.py
```

## Definition of Done

- T001 and T002 committed red before T003; the final tree is green.
- The emitted repro payload validates against the pinned contract, and no door appends a
  pointerless gated rewind.
- No second edge-set literal; the wire contract and the pin files are untouched.
- The evidence arm (#6845) and every non-family forced edge are unchanged.
- Diff coverage on changed lines ≥ 90%.
