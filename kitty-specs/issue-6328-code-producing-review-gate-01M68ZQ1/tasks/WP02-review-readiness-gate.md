---
work_package_id: WP02
title: The review-readiness prerequisite keyed on the capability
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
- FR-008
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6328-code-producing-review-gate
merge_target_branch: issue-6328-code-producing-review-gate
branch_strategy: Planning artifacts for this mission were generated on issue-6328-code-producing-review-gate. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6328-code-producing-review-gate unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
- T013
phase: Phase 1 - Foundation
history:
- at: '2026-10-31T12:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_ready_for_review_code_producing_gate.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/tasks_parsing_validation.py
- tests/specify_cli/cli/commands/agent/test_ready_for_review_code_producing_gate.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – The review-readiness prerequisite keyed on the capability

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission issue-6328-code-producing-review-gate-01M68ZQ1`) and address every item before handing back.

## Objectives & Success Criteria

This is the actual defect fix (`#6328`). The review-readiness pre-flight must apply
its worktree-state prerequisite — the one that includes "an implementation commit
exists on the lane" — to **any** mission type whose `code_producing` capability is
true, instead of to the `software-dev` family name.

Done means:

- The literal guard is gone: `git grep -n 'MISSION_TYPE_SOFTWARE_DEV' -- src/specify_cli/cli/commands/agent/tasks_parsing_validation.py` returns nothing, and the import is dropped (SC-002).
- A custom mission type declaring `code_producing: true`, with a work package and no lane commit, is refused by the pre-existing `_validate_ready_for_review` entry point with the existing implementation-commit guidance (FR-006 / SC-001).
- The same fixture with a commit on the lane passes (same-fixture positive control).
- `research`, `documentation`, `plan` and a custom `code_producing: false` type keep bypassing the block (FR-007); `software-dev` keeps failing when it should (C-002 / SC-003).
- `--force` still short-circuits before the capability is consulted (C-003).
- `src/specify_cli/lanes/for_review_gate.py` and the `single_branch` gates are byte-unchanged (FR-008 / C-001 / SC-004).

## Context

**Spec**: `kitty-specs/issue-6328-code-producing-review-gate-01M68ZQ1/spec.md` — the Problem statement, the Scope boundary, and FR-006..FR-008.
**Plan**: plan.md § "Design / D2", "D3" and the IC-02 concern.
**Depends on**: WP01. `charter.activation.api.code_producing_for` must exist before you
start; if it does not, stop and report rather than stubbing it.

### The exact site

`src/specify_cli/cli/commands/agent/tasks_parsing_validation.py`, inside
`_validate_ready_for_review`, today reads:

```python
    # Check 2: For software-dev missions, check worktree for implementation commits
    if mission_type == MISSION_TYPE_SOFTWARE_DEV:
        worktree_result = _validate_worktree_state(
            repo_root=repo_root,
            ...
        )
        if worktree_result is not None:
            return worktree_result
```

`MISSION_TYPE_SOFTWARE_DEV` comes from `specify_cli.core.constants` and is imported
near the top of the file (line ~55). Check 1
(`_validate_research_artifacts`) above it is unaffected and applies to all mission
types. `force` short-circuits at the top of the function.

### The consumer idiom to copy

`src/specify_cli/cli/commands/agent/mission_check_prerequisites.py`, function
`_requires_substantive_spec` (around line 432). Read it. Copy its three defining
choices verbatim, adapting only the accessor name:

1. Import **inside** the function from `charter.activation.api` — never
   `charter.activation.mission_type_profiles`. The architectural boundary gate
   forbids the internal reach.
2. Bind the result to a `bool`-annotated local before returning, with the same
   comment: under the narrow mypy check `specify_cli.*` runs with
   `follow_imports = "skip"`, so a name imported from the skipped `charter.*` seam
   resolves as `Any` and a bare `return` reads as "Returning Any from function
   declared to return bool". Do not add a `# type: ignore`.
3. Do not invent a fallback — the accessor already carries the built-in fallback and
   never raises.

## Detailed guidance per subtask

### T007 — Red first, through the pre-existing entry point

Create
`tests/specify_cli/cli/commands/agent/test_ready_for_review_code_producing_gate.py`.
Call the **real** `_validate_ready_for_review` (import it from
`specify_cli.cli.commands.agent.tasks_parsing_validation`), injecting the
collaborators by keyword exactly as the existing neighbours do — see
`tests/integration/test_coord_loop_depgraph.py` around line 320 for the minimal
injection set and `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py`
for richer fixtures.

The case that must fail before T008: a custom mission type resolving
`code_producing = True`, a worktree with no commit beyond the check branch, and the
assertion that the pre-flight returns `(False, guidance)` where the guidance mentions
the missing implementation commits.

Practical route for the mission type: put the type in `meta.json`'s `mission_type`
and make `code_producing_for` resolve `True` for it. Two honest options, use the
first that works:

- **Preferred**: a real layered org pack declaring `code_producing: true`, as in
  WP01's test, so the whole chain is production code. Patch `existing_mission_types`
  and `PackContext.from_config` the same way WP01 does.
- **Fallback**: `unittest.mock.patch` on
  `charter.activation.api.code_producing_for` for the consumer test, while WP01's
  suite proves the resolver. If you take this route, say so plainly in the hand-off:
  the consumer test then proves *wiring*, not resolution, and that split must be
  visible to the reviewer.

Either way, the fixture repository must be a real git repo with a worktree
(`tmp_path` + `git init`) — the checks shell out to git. Reuse the git fixture
helpers already in `tests/specify_cli/cli/commands/agent/` rather than writing new
ones.

### T008 — The swap

Add a module-local helper beside `_validate_ready_for_review` (not a new public
symbol; do not add it to `__all__`):

```python
def _is_code_producing(repo_root: Path, mission_type: str) -> bool:
    """Whether *mission_type* produces committed code (capability, not family name)."""
    from charter.activation.api import code_producing_for  # boundary: public seam only

    produces_code: bool = code_producing_for(repo_root, mission_type)
    return produces_code
```

and change the guard to `if _is_code_producing(main_repo_root, mission_type):`.
Pass `main_repo_root`, not `repo_root`: that is the value the surrounding function
already resolved for the primary partition, and the charter config lives there.

Update the `# Check 2:` comment to say the check is capability-keyed. Remove
`MISSION_TYPE_SOFTWARE_DEV` from the module's imports **only if** nothing else in the
file uses it (`git grep -n MISSION_TYPE_SOFTWARE_DEV -- src/specify_cli/cli/commands/agent/tasks_parsing_validation.py`
must be empty afterwards). Do not delete the constant from `core/constants.py`; other
modules use it.

### T009 — Positive control on the same fixture

Same repo, same injected collaborators, one commit on the lane branch beyond the
check branch → the pre-flight passes. This is what makes T007 non-vacuous: without
it, "always refuse" would pass.

### T010 — Built-in parity ratchet (SC-003)

Parametrise over the four built-ins on a fixture with **no** lane commit:

| mission type | expected |
| --- | --- |
| `software-dev` | blocked (unchanged) |
| `research` | not applied |
| `documentation` | not applied |
| `plan` | not applied |

Plus a custom type declaring `code_producing: false` → not applied. Add a short
comment naming this as the SC-003 parity ratchet so a future reader knows it is a
regression pin, not redundant coverage.

### T011 — `--force`

`_validate_ready_for_review(..., force=True, ...)` returns `(True, [])` and never
consults the capability. Assert it with collaborators that would raise if called
(pass a `code_producing_for` patch that raises, or inject minimal lambdas and assert
the verdict).

### T012 — Neighbour suites

Run, and fix nothing outside `owned_files` (report instead):

```bash
uv run pytest tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py -q
uv run pytest tests/integration/test_coord_loop_depgraph.py -q
uv run pytest tests/agent/ tests/tasks/ tests/review/ -q
```

`tests/integration/test_coord_loop_depgraph.py:333` asserts the research-type bypass
with the comment "worktree check is gated on MISSION_TYPE_SOFTWARE_DEV". That test
must stay green **without being edited**. If it fails, your capability resolution is
resolving `research` to `True` — fix the resolution, not the test.

### T013 — The empty-diff proof (SC-004)

```bash
git diff --stat origin/main -- \
  src/specify_cli/lanes/for_review_gate.py \
  src/specify_cli/lanes/consolidation.py
```

must be empty. Record the command and its (empty) output in the hand-off so the PR
body can cite it. This is a hand-off artefact, not a test — do not add a pytest that
shells out to `git diff` to assert it.

## Out of scope — do not do these

- Do **not** modify `src/specify_cli/lanes/for_review_gate.py`,
  `src/specify_cli/lanes/consolidation.py`, or any `SINGLE_BRANCH_*` gate. They are
  the `#6715`/`#5939` evidence gates and this mission's whole point is to not touch
  them.
- Do **not** extend the gate to check *what* the commit touched, add an
  `owned_files` requirement, or change the guidance text. The issue is about *which
  mission types* the existing prerequisite applies to.
- Do **not** add a required parameter to `_validate_ready_for_review` (C-003) — its
  collaborator set is a live monkeypatch contract across the suite.
- Do **not** edit the changelog; that is WP03.
- Do **not** re-key the runtime `software-dev` comparisons in `src/runtime/next/`.

## Test strategy

```bash
uv run pytest tests/specify_cli/cli/commands/agent/test_ready_for_review_code_producing_gate.py -v
uv run pytest tests/charter/test_code_producing_capability.py -q     # WP01, still green
uv run pytest tests/specify_cli/cli/commands/agent/ -q
uv run pytest tests/integration/test_coord_loop_depgraph.py -q
uv run ruff check src/specify_cli/cli/commands/agent tests/specify_cli/cli/commands/agent
uv run ruff format --check src/specify_cli/cli/commands/agent tests/specify_cli/cli/commands/agent
uv run mypy src/specify_cli/cli/commands/agent/tasks_parsing_validation.py
```

## Definition of Done

- [ ] T007's test was observed red before T008 and green after; both runs captured
      in the hand-off.
- [ ] No `MISSION_TYPE_SOFTWARE_DEV` comparison or import remains in
      `tasks_parsing_validation.py`.
- [ ] The capability is reached only through `charter.activation.api`, with the
      `bool`-annotated local bind and no `# type: ignore`.
- [ ] `_validate_ready_for_review`'s signature is unchanged.
- [ ] `tests/integration/test_coord_loop_depgraph.py` passes **unedited**.
- [ ] The `#6715`/`#5939` empty-diff proof is captured in the hand-off.
- [ ] `ruff check`, `ruff format --check` clean on the touched paths.

## Risks & reviewer guidance

- **Over-reach is the main danger.** The tempting "improvement" is to also make the
  gate inspect `owned_files` or the commit message. Do not: that is a different,
  already-owned layer (`#6715`), and widening the pre-flight here would change
  `software-dev` behaviour, which C-002 forbids.
- **Passing `repo_root` instead of `main_repo_root`** would resolve the charter
  against a worktree and could silently fail over to the built-in map in every
  non-primary checkout. Reviewer: check the argument.
- **The research bypass test is the canary.** If it goes red, resolution is wrong.
- **A refused pre-flight must still fail closed.** If the resolver ever raises, the
  accessor returns the built-in default; do not add a second `try/except` in the
  consumer that could turn a refusal into a pass.
