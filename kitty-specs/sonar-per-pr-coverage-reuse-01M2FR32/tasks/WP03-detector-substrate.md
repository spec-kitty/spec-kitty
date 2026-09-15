---
work_package_id: WP03
title: Teach the gate model to see indirect suite invocations
dependencies: []
requirement_refs:
- NFR-007
- FR-010
planning_base_branch: issue-4334-sonar-reuse-shard-coverage
merge_target_branch: issue-4334-sonar-reuse-shard-coverage
branch_strategy: Planning artifacts for this mission were generated on issue-4334-sonar-reuse-shard-coverage. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4334-sonar-reuse-shard-coverage unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-sonar-per-pr-coverage-reuse-01M2FR32
base_commit: 576801bc0249171bb037e4ccdc5ccbe66c186ba7
created_at: '2026-09-14T14:39:53.592040+00:00'
subtasks:
- T013
- T014
- T015
- T016
- T017
history:
- date: '2026-09-14'
  note: Created by /spec-kitty.tasks; sequenced BEFORE the retirement so the battery is provable against live source.
agent_profile: python-pedro
authoritative_surface: tests/architectural/_gate_coverage.py
create_intent: []
execution_mode: code_change
owned_files:
- tests/architectural/_gate_coverage.py
- tests/architectural/test_suite_jobs_gate_blocking.py
- tests/architectural/test_workflow_coherence.py
- tests/_arch_shard_map.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

```
/ad-hoc-profile-load python-pedro
```

Apply the resolved initialization, boundaries, directives and tactics, and state which you applied.
`governance unresolved` from `spec-kitty charter context` is a known pre-existing condition —
reconstruct from `.kittify/charter/charter.md` and say so. Retry the `Global asset input changed` race.

## Objective

The duplicate-detection substrate is **documented as structurally blind** to the retiring step's
invocation form. Close that blindness now, while the step still exists, so WP04's battery can be
proven against reality instead of a fixture.

## Why the sequencing matters

`tests/architectural/_gate_coverage.py` carries this in its own source:

> the non-blocking `sonarcloud` reporter … reaches pytest only through `make test-fast` — no
> directly-anchored pytest command, so it is **not (and cannot be) collected as a gate here**

And `tests/architectural/test_suite_jobs_gate_blocking.py` asserts that the workflow carrying that
step has **no** suite-running jobs — a test that **passes right now, with a ~22-minute duplicate
suite execution present in the file**.

Any regression rule built on this substrate inherits that blindness and is vacuous by construction.
Fixing the substrate **before** the retirement means WP04 can demonstrate its strongest mutation
("reintroduce the retiring step") red against **live source**. After the retirement, only a synthetic
fixture would remain — reproducing exactly the blindness being closed.

## Subtasks

### T013 — Red-first: prove the model cannot see the indirect invocation

**Steps**:
1. Add a test asserting the workflow model resolves a `run:` step that reaches the suite through a
   make target to a suite invocation.
2. Confirm it is RED on the current tree. Capture the output.

**Validation**: red, for the documented reason — not for a typo.

### T014 — Resolve `run:` steps transitively

**Purpose**: make T013 green without hardcoding.

**Steps**:
1. Extend the model's detection so a step reaching the suite through a make target, or through an
   invoked script, is recognised — not only a directly-anchored command.
2. Resolve the make target by **reading the Makefile**, not by matching the literal string
   `make test-fast`. A literal match is defeated by a rename; the mission's own battery will test
   exactly that evasion.
3. Keep the existing directly-anchored detection working.

**Validation**: T013 passes; existing gate tests still pass.

### T015 — Reconcile the workflow allowlist with widened detection

**Purpose**: widening detection pulls a workflow into a set-equality invariant. That cascade is the
point, but it must be landed deliberately.

**Steps**:
1. The model holds a closed list of workflows considered suite runners, and a live invariant asserts
   the discovered set equals it. Widening detection will make the discovered set grow.
2. Update the list, and check the coherence model that consumes it.
3. Re-run the surrounding architectural battery.

**Validation**: targeted re-run of the cascade you touched — `test_suite_jobs_gate_blocking.py`, `test_workflow_coherence.py`, and whatever `grep -rl "_gate_coverage" tests/ --include="*.py"` returns.

### T016 — Rewrite the non-blocking rationale truthfully

**Purpose**: the recorded rationale asserts the job "invokes the suite through `make test-fast`, so
the anchored derivation never flags it". After T014, that is no longer why. A justification that
describes something untrue is exactly what C-005 forbids.

**Steps**:
1. Rewrite the rationale to describe what is now actually detected and why the job remains
   non-blocking.
2. Do **not** delete the entry — its subject still exists at this point in the mission. (WP06 will
   revisit it when the job is retired.)

**Validation**: the rationale-non-emptiness guard passes, and the text is true.

### T017 — Register any new architectural test file in the shard map

**Purpose**: a new architectural test file that is not registered reds a shard-map completeness gate.

**Steps**: if T013 added a new file, append it to the appropriate shard tuple and recompute the test
count the map records.

**Validation**: the shard-map completeness gate passes.

## Branch Strategy

- **Planning base branch**: `issue-4334-sonar-reuse-shard-coverage`
- **Final merge target**: `issue-4334-sonar-reuse-shard-coverage`
- Worktrees are allocated per computed lane from `lanes.json`; `spec-kitty implement WP03` resolves
  the path.

**Test scope (operator ruling):** run **targeted tests only** — your own new tests plus the specific gate files your diff touches (locate them with `grep -rl "<symbol>" tests/ --include="*.py"`). **Do not run the full `tests/architectural/` battery** — it is heavy, has been observed killing dispatched agent processes, and belongs to CI. Record the exact commands and counts in your handoff; "targeted tests pass, full arch suite deferred to CI" is the honest statement.

## Definition of Done

- [ ] T013 was RED before T014, GREEN after — both outputs captured
- [ ] Detection resolves indirection by **reading the Makefile**, not by matching a literal
- [ ] The discovered-set invariant and the coherence model are reconciled
- [ ] The non-blocking rationale describes what is actually detected
- [ ] Any new test file is registered in the shard map
- [ ] Targeted tests pass (the gates you edited + the cascade files you identified); full arch suite deferred to CI; `ruff check` and `ruff format --check` clean on changed files

## Reviewer Guidance

- **The key question**: after this WP, does the model see the duplicate suite execution that is
  *still present in the tree*? If the answer is "it will once the job moves", the substrate is still
  blind and WP04 will be vacuous.
- **Check the make-target resolution reads the Makefile.** A literal-string match is defeated by a
  rename, and WP04's battery includes that exact mutation.
- **Reviewer ≠ implementer** (C-007).
