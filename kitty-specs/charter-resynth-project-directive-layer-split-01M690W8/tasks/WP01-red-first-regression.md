---
work_package_id: WP01
title: Red-first regression and the additive-only positive control
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6768-charter-resynth-project-directive
merge_target_branch: issue-6768-charter-resynth-project-directive
branch_strategy: Planning artifacts for this mission were generated on issue-6768-charter-resynth-project-directive. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6768-charter-resynth-project-directive unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-resynth-project-directive-layer-split-01M690W8
base_commit: 96dd5627f7b4046836a98326ba351e9934c598a4
created_at: '2026-10-31T13:08:28.135885+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Proof
history:
- at: '2026-10-31T13:10:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/charter/synthesizer/
create_intent:
- tests/charter/synthesizer/test_project_directive_layer_split_6768.py
execution_mode: code_change
model: ''
owned_files:
- tests/charter/synthesizer/test_project_directive_layer_split_6768.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6768'
---

# Work Package Prompt: WP01 – Red-first regression and the additive-only positive control

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: check the `review_ref` field in the event log
  (`spec-kitty agent tasks status`). Address every item, then record what changed with
  `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

Write the executable proof for [#6768](https://github.com/spec-kitty/spec-kitty) **before** the
fix exists, and watch it fail for the reported reason.

The defect: `charter resynthesize --topic directive:PROJECT_007` refuses an activated,
project-authored project directive with the FR-020 / EC-6 additive-only violation, because
`SynthesisRequest.drg_snapshot` lists the project's own activated directives and is handed to
the emitter as the *built-in* layer.

Your module must establish, on one shared fixture:

1. the refusal reproduces today (red until WP02), through the real CLI;
2. a genuine built-in URN still refuses after the fix (the positive control that keeps the fix
   from becoming a gate bypass);
3. the request will carry two distinguishable layers once WP02 lands (red until WP02);
4. the pre-fix fallback path is pinned (`None` built-in layer ⇒ reference snapshot);
5. project references still resolve, and an undeclared URN still fails closed.

Do not implement the fix. WP02 owns `src/`.

## Context

Read first:

- `kitty-specs/charter-resynth-project-directive-layer-split-01M690W8/spec.md` (Problem
  Statement, FR-001…FR-003)
- `kitty-specs/charter-resynth-project-directive-layer-split-01M690W8/research.md`
  (Decision 1: the reproduction; Decision 2: the two jobs of the snapshot)
- `kitty-specs/charter-resynth-project-directive-layer-split-01M690W8/data-model.md`
  (the field, the fallback rule, the consumer matrix)
- `tests/charter/synthesizer/test_resynthesis_after_activation_6510.py` — reuse its fixture
  shape (`_build_template`, `_invoke`, module-scoped template + `charter_cwd_isolation`). Do
  not import its private helpers if that couples the two modules too tightly for your taste;
  copying the ~60-line fixture builder into your module is acceptable and keeps this file
  self-contained.
- `tests/_support/charter_cwd.py` (`CHARTER_FIND_REPO_ROOT`, `charter_cwd_isolation`) and
  `tests/_factories/activation_ledger.py` (`seed_activation_ledger`).

## Subtasks

### T001 — Module skeleton and the defect fixture

Build a module-scoped "synthesized once" template project the way
`test_resynthesis_after_activation_6510.py` does: `charter generate --from-interview`, one
minimal generated body per target, one `charter synthesize`, one commit. Then add, per test:

- an authored `.kittify/charter-packs/directive/007-local-guardrail.directive.yaml` with
  `id: PROJECT_007`;
- `charter activate directive 007-local-guardrail --no-compile` (this registers it as
  `adapter_id: project-direct-write` — deliberately **not** synthesis ownership, which is the
  state the issue reports);
- `.kittify/charter/generated/tactics/how-we-apply-project-007.tactic.yaml`.

Note: `charter activate` on a directive makes synthesis expect the companion tactic, so author
it or the run fails on a missing artifact instead of on the collision.

### T002 — The reported refusal (red)

`test_resynthesize_activated_project_authored_directive_succeeds`:

```python
result = _invoke("resynthesize", "--topic", "directive:PROJECT_007", "--json")
assert "colliding_urn" not in result.output, result.output
assert result.exit_code == 0, result.output
```

On the un-fixed tree this must fail with `colliding_urn='directive:PROJECT_007'` in the output.
Mark the test `@pytest.mark.p0_repro(issue=6768)` while #6768 is open; WP02 removes the marker
and keeps the test as the regression. Capture that exact error text in your WP history (T007) as
the red proof.

### T003 — The positive control (green before and after)

`test_built_in_urn_still_refuses_and_project_urn_does_not`, on the real shipped graph:

```python
from charter.offering.drg.loader import load_built_in_graph
from charter.activation.synthesizer.project_drg import emit_project_layer
from charter.activation.synthesizer.errors import ProjectDRGValidationError
```

Emit a one-target overlay whose URN is a shipped built-in node URN and assert
`ProjectDRGValidationError` is raised with `colliding_urn` set; then emit a one-target overlay
whose URN is `directive:PROJECT_007` and assert it does **not** raise. Same fixture, same
graph — so the probe demonstrably can see the difference.

### T004 — The two layers are distinguishable in the request (red)

`test_request_carries_a_built_in_layer_without_project_directives`:

```python
request, _ = _build_synthesis_request(project, "generated")
built_in = frozenset(n["urn"] for n in request.built_in_drg_snapshot["nodes"])
reference = frozenset(n["urn"] for n in request.drg_snapshot["nodes"])
assert "directive:PROJECT_007" not in built_in
assert "directive:PROJECT_007" in reference
```

Before WP02 the attribute does not exist (AttributeError) — that is the red for FR-004. After
WP02, `built_in` must hold real shipped built-in URNs (assert at least one known built-in
directive URN is present, so the assertion is not satisfied by an empty list).

### T005 — The fallback rules (red)

Two cases in `src/charter/activation/synthesizer/request.py`:

- `built_in_snapshot(request)` returns `request.drg_snapshot` when
  `request.built_in_drg_snapshot is None` (construct a minimal `SynthesisRequest` for this).
- `_build_synthesis_request` leaves the field `None` when `load_built_in_graph` raises
  `DRGLoadError` (monkeypatch the loader seam the builder imports) — the run must not fail
  with an unrelated loader error.

### T006 — The reference-universe pair (green before and after)

- `test_companion_tactic_reference_resolves`: the authored tactic resynthesizes (exit 0) and
  its `directive:PROJECT_007` source reference is accepted.
- `test_undeclared_source_urn_still_fails_closed`: on the same snapshot, `build_targets` with
  an explicit `source_urns=("directive:PROJECT_999",)` raises `ProjectDRGValidationError`
  naming it. This is the paired negative control that keeps T006's first half non-vacuous.

### T007 — Record the red run and the design facts

Append to the mission tracer files with
`spec-kitty agent tracer-append --mission <slug> --category approach|design-decisions --entry "<text>"`,
and add a WP history note with the command you ran and the exact refusal line.

## Definition of Done

- The module exists at
  `tests/charter/synthesizer/test_project_directive_layer_split_6768.py` and is the only file
  you change.
- Run `uv run pytest tests/charter/synthesizer/test_project_directive_layer_split_6768.py -q`
  and record, in the WP history, which tests are red on the un-fixed tree and why (the exact
  error), and that the controls (T003, T006) pass.
- No test asserts on the `PROJECT_` id prefix as a mechanism (C-001).
- Tests are not skipped or xfailed. The T002 repro carries `@pytest.mark.p0_repro(issue=6768)`
  while the bug is open (charter, P0 repro convention); WP02 removes the marker and keeps the
  test as a regression test.

## Risks

- The fixture build costs ~35 s per module (module-scoped template keeps it to once). Do not
  build it per test.
- `charter activate` writes activation state; use the test factory/CLI as the existing tests
  do and keep the template immutable per test (copy it).

## Reviewer Guidance

- Confirm the red actually reproduces the reported refusal, not a fixture setup error.
- Confirm the positive control uses the *real* shipped graph and the same fixture.
- Confirm the fallback cases would fail if WP02 removed the `None` fallback.
