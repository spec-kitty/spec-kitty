---
work_package_id: WP04
title: Permanent regression battery
dependencies:
- WP03
requirement_refs:
- NFR-001
- NFR-007
planning_base_branch: issue-4334-sonar-reuse-shard-coverage
merge_target_branch: issue-4334-sonar-reuse-shard-coverage
branch_strategy: Planning artifacts for this mission were generated on issue-4334-sonar-reuse-shard-coverage. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4334-sonar-reuse-shard-coverage unless the human explicitly redirects the landing branch.
subtasks:
- T018
- T019
- T020
- T021
- T022
history:
- date: '2026-09-14'
  note: Created by /spec-kitty.tasks; must land BEFORE the retirement (WP06).
agent_profile: reviewer-renata
authoritative_surface: tests/architectural/test_no_duplicate_suite_execution.py
create_intent:
- tests/architectural/test_no_duplicate_suite_execution.py
execution_mode: code_change
owned_files:
- tests/architectural/test_no_duplicate_suite_execution.py
- tests/_arch_shard_map.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

```
/ad-hoc-profile-load reviewer-renata
```

Apply the resolved initialization, boundaries, directives and tactics, and state which you applied.
`governance unresolved` is a known pre-existing repository condition — reconstruct from
`.kittify/charter/charter.md` and say so. Retry the `Global asset input changed` race.

*(A reviewer profile is assigned deliberately: this work package's entire job is to think like an
adversary trying to sneak the defect back in.)*

## Objective

Build a **permanent, in-tree fault-injection battery** that fails on every way the duplicate
measurement could return, and on removal of either declaration that keeps the report advisory.

## Why "a mutation that is reverted" is not good enough

A one-off mutate-and-revert demonstration is self-reported, leaves nothing in the tree, and cannot
protect anything after the pull request closes. This repository already has a better pattern in the
very area you are working in: a synthetic-workflow fixture asserting a **pure relation** flags exactly
the injected violation. Use that shape.

The battery's value is entirely in whether it catches evasions a motivated implementer would actually
reach for. Assume the future regressor is competent and does not want to be caught.

## Subtasks

### T018 — Battery scaffold with a non-vacuity floor

**Steps**:
1. Create `tests/architectural/test_no_duplicate_suite_execution.py`.
2. Express the property as a **pure relation** over a parsed workflow model — the set of
   change-triggered jobs that execute the suite must equal exactly the matrix.
3. Add the **non-vacuity floor**: assert the rule's workflow set is non-empty. Without this, a future
   change that narrows the scanned set makes the whole battery silently vacuous.
4. Enumerate `.github/workflows/*.yml` from the **directory**, not from a closed literal list — a
   closed list cannot see a net-new file, which is mutation 4.
5. Declare the file's `pytestmark` and register it in the shard map if that is not inherited.

**Validation**: passes on the current tree.

### T019 — Mutations 1-3, proven RED against the live tree

**This is the subtask that must happen before the retirement.** The retiring step is still present,
so each mutation can be demonstrated against reality rather than a fixture.

**Steps**: assert the rule reds for each of:
1. **Canonical** — the retiring step in its current form.
2. **Inlined** — the same selection written as a direct suite invocation with no shared-target
   reference. Defeats a literal-string rule.
3. **Indirection** — the same work behind a shell wrapper, an invoked script, or a composite action.
   Defeats both of the above.

Apply at least one mutation to a **copy of the real workflow file**, not only to a hand-written
snippet — a battery fed exclusively synthetic fixtures reproduces the blindness it exists to close.

**Validation**: three demonstrated reds, captured in the pull-request evidence.

### T020 — Mutation 4: a net-new workflow file

**Steps**: assert the rule reds when the duplicate appears in a **new** workflow file that no closed
candidate list mentions. This is what forces the directory enumeration from T018 to be real.

**Validation**: red, and the reason is the new file — not an unrelated parse error.

### T021 — Mutations 5-6: removal of the advisory declarations

**Steps**: assert the rule reds when either is removed from the reporting job:
5. the job-level non-blocking declaration;
6. the same-origin conjunct in the execution condition.

**Context**: today the non-blocking declaration's removal reds **nothing** — the string appears in the
test tree only inside prose rationales, never as a live assertion. The same-origin conjunct is the
mission's principal security-relevant change (a platform-enforced guarantee becomes a
condition-enforced one), so its silent removal must be impossible.

**Note on ordering**: the reporting job exists from WP05. Write these two as fixture-driven
assertions over a synthetic workflow carrying the declarations, so this WP is self-contained and
green; WP05's own acceptance then exercises them against the real job.

**Validation**: two demonstrated reds.

### T022 — Characterise the live tree (non-vacuity against reality)

**⚠️ Read carefully — this is NOT "assert the tree is clean" yet.**

At this point in the mission the duplicate **still exists** (it is retired in WP06). That is
deliberate: it is what lets T019 prove mutation 1 against live source. So an "unmutated tree is
clean" assertion would be **wrong here** and would force the implementer to either fake it or retire
the step out of order.

**Steps**:
1. Assert the rule, run against the **real** workflow tree, detects exactly the known duplicate —
   named explicitly. This is the characterisation that proves the rule is non-vacuous *against
   reality*, not merely against fixtures.
2. Leave a clearly-marked seam (a single constant or a well-named assertion) that WP06 flips to the
   clean-tree form once the duplicate is retired. WP06 co-owns this file for exactly that flip.

**Why this matters**: a battery that only ever inspects fixtures can pass forever while the live tree
violates the property — which is precisely the failure mode observed in the neighbouring gate before
this mission. Characterising the live violation now, and flipping it at retirement, proves the rule
saw reality at both ends.

**Validation**: the assertion passes *because* it correctly detects the still-present duplicate. If it
passes by finding nothing, the rule is blind and T019 is meaningless.

## Branch Strategy

- **Planning base branch**: `issue-4334-sonar-reuse-shard-coverage`
- **Final merge target**: `issue-4334-sonar-reuse-shard-coverage`
- Worktrees are allocated per computed lane from `lanes.json`; `spec-kitty implement WP04` resolves it.

**Test scope (operator ruling):** run **targeted tests only** — your own new tests plus the specific gate files your diff touches (locate them with `grep -rl "<symbol>" tests/ --include="*.py"`). **Do not run the full `tests/architectural/` battery** — it is heavy, has been observed killing dispatched agent processes, and belongs to CI. Record the exact commands and counts in your handoff; "targeted tests pass, full arch suite deferred to CI" is the honest statement.

## Definition of Done

- [ ] Six mutations, each **demonstrated red**, with output captured in the pull-request evidence
- [ ] At least one mutation applied to a copy of a real workflow file, not only a synthetic snippet
- [ ] Non-vacuity floor asserts the scanned set is non-empty
- [ ] Workflow enumeration reads the directory; a net-new file is caught
- [ ] The live tree is **characterised** (rule detects the still-present duplicate), with a marked seam for WP06 to flip
- [ ] File registered in the shard map; targeted tests pass (your new battery module + the shard-map gate); full arch suite deferred to CI
- [ ] `ruff check .` and `ruff format --check .` clean

## Reviewer Guidance

- **Try to beat it.** Write a seventh evasion and check the battery catches it. If you can get the
  duplicate past the rule in under ten minutes, the battery is not done.
- **Check T022 characterises rather than claims clean.** At this point the duplicate still exists; an "all clean" assertion here is either wrong or faked.
- **Check mutation 1 was proven against the live tree**, not a fixture. That is the whole reason this
  WP is sequenced before the retirement — if it was demonstrated on a synthetic snippet, the sequencing
  bought nothing and should be challenged.
- **Check the enumeration is a directory read.** A closed list silently exempts net-new files.
- **Reviewer ≠ implementer** (C-007).
