---
work_package_id: WP01
title: The RunScope type and its call sites
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-005
- SC-001
- SC-002
- SC-004
planning_base_branch: issue-6728-reconcile-run-scope
merge_target_branch: issue-6728-reconcile-run-scope
branch_strategy: Planning artifacts for this mission were generated on issue-6728-reconcile-run-scope. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6728-reconcile-run-scope unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-reconcile-run-scope-01M66YH3
base_commit: 0a1ef8b64c7120eb85dc749407ad5194b8b5b7a8
created_at: '2026-10-30T17:52:47.399565+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - The run-scope type and its call sites
history:
- at: '{{TIMESTAMP}}'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/synthesizer/reconcile.py
- src/charter/activation/synthesizer/resynthesize_pipeline.py
- tests/charter/synthesizer/test_synthesize_reconcile.py
- tests/charter/synthesizer/test_styleguide_reach_only.py
- tests/charter/synthesizer/test_project_intent_directive.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6728'
---

# Work Package Prompt: WP01 – The RunScope type and its call sites

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (`python-pedro`) before parsing the rest of this prompt, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Replace the `Ellipsis` sentinel that #6456 left in the legacy-edge reconciler with a typed,
named run scope, with no behaviour change. Done when:

- `src/charter/activation/synthesizer/reconcile.py` defines `RunScope` (`FULL`, `TOPIC_SCOPED`)
  next to `SynthesizeMode`, and the enum owns the derivation
  `dead_edge_filter(regenerated_urns) -> Collection[str] | None`.
- `_is_legacy_applies` and `legacy_applies_edges` take a **required keyword-only**
  `run_scope: RunScope`; `dead_edge_regenerated_urns` and the `from types import EllipsisType`
  import are gone, and no signature in the module defaults to `...`.
- `merge_project_overlay` keeps its exported `topic_scoped: bool = False` keyword and converts it
  to the enum in exactly one place; `_graph_delta` passes `RunScope.FULL`.
- `resynthesize_pipeline._validation_callback` passes `RunScope.TOPIC_SCOPED` (the behaviour the
  `...` default gave it); the seven test call sites state their scope explicitly.
- The new test section fails on the pre-fix tree (RED) and passes after the change (GREEN); the
  untouched `tests/charter/synthesizer/` suite is green before **and** after, with no existing
  assertion relaxed to keep it green.
- `ruff check`, `ruff format --check` and `mypy` (repo config) are clean on the touched files;
  `_is_legacy_applies` loses its sentinel ternary (complexity does not grow).

Requirements: FR-001…FR-007, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, C-005, SC-001, SC-002, SC-004.

## Context & Constraints

- **The defect is a shape, not a wrong answer.** Today
  `dead_filter = regenerated_urns if dead_edge_regenerated_urns is ... else dead_edge_regenerated_urns`
  means the public surface advertises three states (set / `None` / `...`) while callers pass two.
  Nothing in this WP may change *which* edges are stripped or reported.
- **The complete caller census** is in `research.md` D-1 and `plan.md` "Call-site map". Do not look
  for further callers beyond `grep -rn "legacy_applies_edges\|_is_legacy_applies" src tests`;
  there are none, and inventing a compatibility shim for a non-existent caller is out of scope.
- **The two real runs** (#6456): a full run passes the regenerated set for the `applies` rule and
  **no** dead-edge filter (`None`); a topic-scoped run passes the regenerated set for both. The
  `applies` rule is scope-independent — do not route the scope into that branch (FR-005).
- **`merge_project_overlay`'s boolean stays.** It is exported (`__all__`), used by
  `tests/charter/test_project_registration.py` and by the pipeline, and it is not the sentinel this
  issue is about. Changing it would widen a P3 typing change into a public-signature change of an
  unrelated function (C-001).
- **`_is_dead_mission_type_edge(edge, regenerated_urns: Collection[str] | None = None)`** is the
  primitive the scope feeds; leave its signature alone (spec "Out of Scope").
- `RunScope` goes into `__all__` (charter `__all__` convention, C-007); `reconcile.py` itself calls
  it, so `tests/architectural/test_no_dead_symbols.py` stays satisfied.
- Do not add a dependency, a new module, or a third scope. `run_scope` gets **no default** — a
  default re-introduces "the scope you did not say", which is the defect (C-005).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated by `finalize-tasks`. Execution worktrees are allocated per lane from `lanes.json`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first: the scope does not exist yet

- **Purpose**: witness the defect before naming it. The defect is a missing type, so the red is an
  import error plus the behaviour assertions that will guard the new API.
- **Steps**: open `tests/charter/synthesizer/test_synthesize_reconcile.py` and add a section header
  comment `# #6728 -- explicit run scope` near the existing `#6543` section, then add:

  ```python
  def test_reconcile_legacy_edge_signatures_carry_no_ellipsis_sentinel() -> None:
      """#6728: the run scope is a parameter, not a magic literal."""
      import inspect

      from charter.activation.synthesizer.reconcile import (
          _is_legacy_applies,
          legacy_applies_edges,
      )

      for func in (_is_legacy_applies, legacy_applies_edges):
          params = inspect.signature(func).parameters
          assert "dead_edge_regenerated_urns" not in params
          scope = params["run_scope"]
          assert scope.kind is inspect.Parameter.KEYWORD_ONLY
          assert scope.default is inspect.Parameter.empty
          assert all(p.default is not Ellipsis for p in params.values())
          assert not any("Ellipsis" in str(p.annotation) for p in params.values())
  ```

  Run it and capture the RED (`ImportError: cannot import name 'RunScope'` for the scope tests
  below, and `KeyError: 'run_scope'` here). Do **not** weaken the assertions to make the red
  disappear.
- **Files**: `tests/charter/synthesizer/test_synthesize_reconcile.py`.
- **Validation**: RED on the pre-fix tree for the documented reason; the failure text is quoted in
  the commit message or the mission's `traces/approach.md`.

### Subtask T002 – Add `RunScope` (the type owns the meaning)

- **Purpose**: the enum is the single place a run scope's meaning is defined (C-002, C-003).
- **Steps**: in `reconcile.py`, after `SynthesizeMode`, add:

  ```python
  class RunScope(enum.Enum):
      """How much of the project overlay a reconcile run re-emits (#6728).

      ``FULL`` re-emits every artifact, so the dead project-intent
      ``requires --> mission_type:*`` edge (#6443) is stripped wherever it sits.
      ``TOPIC_SCOPED`` re-emits only the targeted artifacts, so that edge is
      stripped only where its owner was regenerated.
      """

      FULL = "full"
      TOPIC_SCOPED = "topic-scoped"

      def dead_edge_filter(self, regenerated_urns: Collection[str] | None) -> Collection[str] | None:
          """The URN set the dead-edge check filters on, or ``None`` for no filter."""
          return regenerated_urns if self is RunScope.TOPIC_SCOPED else None
  ```

  Add `"RunScope"` to `__all__` (alphabetical position: after `"REACH_ONLY_KINDS"`, before
  `"SynthesizeMode"`). `Collection` is already imported under `TYPE_CHECKING`; the annotation is a
  string under `from __future__ import annotations`, so no runtime import is needed — verify with
  `mypy`, do not add a runtime `collections.abc` import just to be safe.
- **Files**: `src/charter/activation/synthesizer/reconcile.py`.
- **Validation**: `uv run mypy src/charter/activation/synthesizer/reconcile.py` clean (or the
  repository's own mypy invocation if it differs — check `pyproject.toml`).

### Subtask T003 – Rewire the two legacy-edge functions

- **Purpose**: the load-bearing change.
- **Steps**:
  - `_is_legacy_applies(edge, synthesized_urns, regenerated_urns=None, *, run_scope: RunScope)`:
    replace the `dead_filter = ...` ternary with
    `if _is_dead_mission_type_edge(edge, run_scope.dead_edge_filter(regenerated_urns)): return True`,
    keep the `applies` return expression **byte-identical**, and rewrite the docstring: name the
    two scopes and say the `applies` rule is scope-independent (#6456). Drop the sentence about
    ``...`` meaning the same set as `regenerated_urns`.
  - `legacy_applies_edges(existing_overlay, synthesized_urns, regenerated_urns=None, *, run_scope: RunScope)`:
    forward `run_scope=run_scope`; extend the one-line docstring with the scope.
  - Delete `from types import EllipsisType`.
- **Files**: `src/charter/activation/synthesizer/reconcile.py`.
- **Validation**: `grep -n "Ellipsis" src/charter/activation/synthesizer/reconcile.py` → no output.

### Subtask T004 – Rewire the two internal call sites

- **Purpose**: keep the exported boolean and the delta path on the enum, with one conversion.
- **Steps**:
  - In `merge_project_overlay`, replace
    `dead_edge_regenerated_urns=updated_urns if topic_scoped else None` with
    `run_scope=RunScope.TOPIC_SCOPED if topic_scoped else RunScope.FULL`, and add one docstring
    sentence: "`topic_scoped` is the boolean spelling of :class:`RunScope` and is converted here,
    once."
  - In `_graph_delta`, both calls (`legacy_applies_edges(...)` and `_is_legacy_applies(...)`)
    pass `run_scope=RunScope.FULL` in place of `dead_edge_regenerated_urns=None`.
- **Files**: `src/charter/activation/synthesizer/reconcile.py`.
- **Validation**: `grep -n "RunScope\\." src/charter/activation/synthesizer/reconcile.py` shows the
  mapping once (`merge_project_overlay`) plus `RunScope.FULL` in `_graph_delta` and the member
  definition — no second boolean→enum conversion anywhere in `src/`.

### Subtask T005 – Name the scope at the remaining call sites

- **Purpose**: nothing relies on a default any more.
- **Steps**:
  - `src/charter/activation/synthesizer/resynthesize_pipeline.py` (~line 389): pass
    `run_scope=RunScope.TOPIC_SCOPED` to `_legacy_applies_edges(...)` (it merges with
    `topic_scoped=True` two statements later — the two must agree), and extend the `#6404` comment
    by one clause naming the scope. Add `RunScope` to the existing `from .reconcile import ...`
    block.
  - `tests/charter/synthesizer/test_project_intent_directive.py` (2 calls),
    `tests/charter/synthesizer/test_styleguide_reach_only.py` (3 calls): add
    `run_scope=RunScope.TOPIC_SCOPED` — the behaviour the `...` default had. Import the enum in
    each module.
  - `tests/charter/synthesizer/test_synthesize_reconcile.py` (2 calls in the #6404 section): same.
  - **Do not** change any assertion in these tests; the calls' results must stay identical
    (NFR-001). If a result *does* change, you have changed behaviour: stop and re-read the
    call-site map.
- **Files**: `src/charter/activation/synthesizer/resynthesize_pipeline.py`, the three test modules.
- **Validation**: `uv run pytest tests/charter/synthesizer/ tests/charter/test_project_registration.py -q`
  green, with the same pass count as before your change plus the new tests.

### Subtask T006 – Pin the two scopes and the invariants

- **Purpose**: make sentinel-semantics drift a test failure, not a review miss (SC-002, FR-003,
  FR-004, FR-005). Use **one shared fixture** so each scope test names its partner (the
  half-by-half rule in tactic `acceptance-criteria-non-vacuity`).
- **Steps**: in the new section add a module-level helper that builds the fixture and the tests
  below. Suggested shape (adapt names to the file's existing helpers):

  ```python
  def _scope_fixture() -> tuple[DRGGraph, DRGGraph, set[str], DRGEdge, DRGEdge]:
      """regenerated + untargeted legacy ``applies`` edges, a dead edge on a
      regenerated and on an untouched PROJECT_* directive."""
  ```

  Tests:
  1. `test_full_scope_strips_the_dead_edge_of_an_untouched_directive` — `RunScope.FULL` returns the
     dead edge (FR-003).
  2. `test_topic_scoped_scope_keeps_the_dead_edge_of_an_untouched_directive` — `RunScope.TOPIC_SCOPED`
     returns nothing for it (FR-004). Its partner is test 1 on the same fixture.
  3. `test_both_scopes_strip_the_dead_edge_of_a_regenerated_directive` — parametrised over
     `RunScope` (both members), same fixture (FR-003/FR-004 positive control).
  4. `test_run_scope_does_not_change_which_legacy_applies_edges_are_stripped` — parametrised over
     `RunScope`, `regenerated_urns={regen}` and `None`; assert the `applies` sources stripped are
     identical under both members and that the hand-authored styleguide is never among them
     (FR-005).
  5. `test_merge_project_overlay_scopes_match_the_explicit_run_scope` — for `topic_scoped in
     (False, True)`, the surviving edge sets equal what
     `legacy_applies_edges(..., run_scope=RunScope.TOPIC_SCOPED if topic_scoped else RunScope.FULL)`
     classifies as stripped on that fixture (SC-002, FR-006).
- **Files**: `tests/charter/synthesizer/test_synthesize_reconcile.py`.
- **Validation**: RED before T002–T005, GREEN after. Then **mutate locally and watch it fail**: flip
  `RunScope.TOPIC_SCOPED`/`FULL` inside `dead_edge_filter` and confirm tests 1–2 and 5 go red;
  revert. Record the mutation result in the WP history/`traces/approach.md`.

### Subtask T007 – Targeted verification

- **Purpose**: prove the change is clean without a full suite sweep (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
- **Steps**: run and record exact commands and counts:
  - `uv run pytest tests/charter/synthesizer/ tests/charter/test_project_registration.py -q`
  - `uv run pytest tests/charter/synthesizer/test_synthesize_reconcile.py -q -k "run_scope or dead_edge or legacy"`
  - `uv run ruff check src/charter/activation/synthesizer/reconcile.py src/charter/activation/synthesizer/resynthesize_pipeline.py tests/charter/synthesizer/`
  - `uv run ruff format --check` on the same paths
  - `uv run mypy src/charter/activation/synthesizer/reconcile.py src/charter/activation/synthesizer/resynthesize_pipeline.py`
- **Files**: none (verification only).
- **Validation**: all green; counts quoted in the commit message and the PR's `## Tests run`.

## Test Strategy

Red-first (charter ATDD-First Discipline, `test-first-bug-fixing`). RED at T001, GREEN after T002–T005,
then the mutation check at T006 as the non-vacuity proof. Only the owning suites run here;
`tests/charter/test_project_registration.py` covers the `merge_project_overlay` callers, and the
architectural gates are WP02's. Never run `tests/architectural/` wholesale, `make test-full`, or any
e2e/performance sweep.

## Definition of Done

- T001–T007 complete and recorded; the RED and the GREEN are both quoted in the commit history.
- `grep -c Ellipsis src/charter/activation/synthesizer/reconcile.py` → 0.
- All six call sites name their scope; no default `run_scope` exists; one bool→enum conversion.
- The existing `tests/charter/synthesizer/` assertions are unedited (only call sites gained a
  keyword argument).
- ruff + ruff format + mypy clean on the touched files; complexity of `_is_legacy_applies` ≤ its
  pre-change value.
- No new dependency, module, `# noqa`, or `type: ignore`.

## Risks & Reviewer Guidance

- **Reviewer**: check the `applies` return expression is unchanged (a scope wired into it is a
  silent #6456 regression that tests 4 and 5 should catch). Check the pipeline's two statements
  agree (`run_scope=RunScope.TOPIC_SCOPED` with `topic_scoped=True`). Check `EllipsisType` is gone
  from the import line, not just the annotations. Check the enum's `dead_edge_filter` is the only
  place the scope becomes a filter set.
- **Risk**: a `regenerated_urns=None` topic-scoped call degenerates to the full-run behaviour (that
  is correct and pre-existing — spec edge case 1); do not "fix" it into an empty set.
- **Risk**: mypy may complain that `Collection` is only imported under `TYPE_CHECKING`; the module
  uses postponed annotations, so this is fine — do not add a runtime import.
