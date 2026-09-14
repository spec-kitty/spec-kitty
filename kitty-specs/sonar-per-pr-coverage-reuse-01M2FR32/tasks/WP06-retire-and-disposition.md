---
work_package_id: WP06
title: Retire the duplicate, execute dispositions, move the documents
dependencies:
- WP05
requirement_refs:
- FR-001
- FR-003
- FR-009
- FR-010
- FR-015
- NFR-001
planning_base_branch: issue-4334-sonar-reuse-shard-coverage
merge_target_branch: issue-4334-sonar-reuse-shard-coverage
branch_strategy: Planning artifacts for this mission were generated on issue-4334-sonar-reuse-shard-coverage. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4334-sonar-reuse-shard-coverage unless the human explicitly redirects the landing branch.
subtasks:
- T028
- T029
- T030
- T031
- T032
history:
- date: '2026-09-14'
  note: Created by /spec-kitty.tasks. Must land AFTER the battery (WP04) so mutation 1 was provable against live source.
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/ci-quality.yml
create_intent:
- scripts/ci/derive_pinning_inventory.py
- tests/architectural/test_no_duplicate_suite_execution.py
- tests/release/pinning_rule_inventory.json
- tests/release/test_pinning_inventory_fresh.py
execution_mode: code_change
owned_files:
- .github/workflows/ci-quality.yml
- tests/release/test_sonar_workflow.py
- tests/architectural/test_no_duplicate_suite_execution.py
- tests/release/test_release_ci_ownership.py
- scripts/ci/derive_pinning_inventory.py
- tests/release/pinning_rule_inventory.json
- tests/release/test_pinning_inventory_fresh.py
- docs/convergence/interim-ci-producer.md
- docs/development/reference/coverage-signals.md
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

```
/ad-hoc-profile-load implementer-ivan
```

Apply the resolved initialization, boundaries, directives and tactics, and state which you applied.
`governance unresolved` is a known pre-existing condition — reconstruct from
`.kittify/charter/charter.md` and say so. Retry the `Global asset input changed` race.

## Objective

Remove the duplicate-measurement job — realising the mission's cost saving — and relocate, rewrite or
deliberately retire **every** rule that pinned the old arrangement, via a **derived** inventory.

## The failure mode this work package exists to prevent

> A rule that goes **red** when the topology changes is found by CI.
> A rule that goes **greener by deletion** is found by nobody.

This mission's own first inventory was roughly **4× understated** and contained **four false
positives** (synthetic tests and docstring prose mistaken for real dependencies). That is why T028
comes before T029: derive the inventory mechanically *before* you start deleting things, or you will
delete something nobody notices.

Read `contracts/gate-disposition-contract.md` in full first.

## Subtasks

### T028 — Commit the derivation, its artefact, and a freshness gate

**Purpose**: "derived mechanically" with no script and no output is unverifiable prose. A transcribed
markdown table is observationally identical to a derived one.

**Steps**:
1. Write `scripts/ci/derive_pinning_inventory.py`: enumerate every automated rule referencing the
   retiring job's name, its host workflow, or the retiring step's invocation, across the whole test
   tree. Classify each by **assertion form** — exact-string, set-equality, path-anchored lookup,
   derived-relation, or docstring/synthetic — because form predicts what relocation does to it.
2. Emit `tests/release/pinning_rule_inventory.json`, each entry carrying its form and a disposition
   field.
3. Add `tests/release/test_pinning_inventory_fresh.py` re-running the derivation and diffing against
   the committed artefact, so staleness is caught.

**Validation**: re-running the script reproduces the committed artefact byte-for-byte.

### T029 — Retire the duplicate-measurement job

**Steps**:
1. Remove the reporting job and its suite-executing step from `.github/workflows/ci-quality.yml`.
2. **Flip WP04's characterisation seam to the clean-tree form.** WP04 asserted the rule detects the
   still-present duplicate; now that it is gone, that assertion must become "the live tree is clean".
   This is the co-owned seam and the reason WP06 shares that file.
3. Confirm the rest of the battery still passes — the six mutations are unaffected by the retirement.

**Validation**: the workflow no longer executes the suite; the battery's clean-tree assertion holds.

### T029b — Correct two accuracy overstatements in the battery module (added after WP04's cycle-2 review)

You co-own `tests/architectural/test_no_duplicate_suite_execution.py` for the flip seam. While you
are in that file, fix two things its own reviewer flagged — both are cases of an artifact reading as
**stronger than it is**, which is precisely the defect class this mission exists to close:

1. **The module docstring's "What remains open" list omits the command-indirection residue.** The
   header calls that surface "closed by construction"; it is closed only for **unprefixed**
   references to workflow-declared names. `true; ${{ matrix.cmd }}` and `echo x && $CMD` both escape,
   because the guard's regexes are `^`-anchored to the logical line. `indirect_command_form`'s own
   docstring is accurate — the truth is one function away — but the module header overstates.
   Add the residue to the disclosed list and soften the header to match what is actually closed.
   Cross-reference **#4367**, which tracks the underlying fix.
2. **A `mypy --strict` error at `test_no_duplicate_suite_execution.py:298`** — `data.get("on", data.get(True))`
   trips the `.get()` overload, because YAML parses a bare `on:` key as the boolean `True`. Present
   verbatim in WP04's final commit and pre-existing to WP05's diff. You co-own this file, so fix it
   here (a narrow cast or an explicit two-step lookup — do **not** add a blanket `type: ignore`).
   Context worth knowing: **no CI workflow runs mypy at all** (`grep -rn mypy .github/workflows/*.yml`
   is empty), so this is a charter code-review-checklist expectation, not a live gate — fix it
   properly or report why not, but do not treat a green CI as evidence it is fine.
3. **`tests/_arch_shard_map.py` records "24 tests"** for that module; it now has **41**. Update the
   count. (If the shard map is outside your `owned_files`, report it rather than editing — say so in
   your handoff and I will place it.)

**Validation**: the disclosed-gaps list matches what the guards actually refuse; the shard-map count
matches `grep -c "^def test_"`.

### T030 — Execute every disposition

For each entry in the derived inventory, apply exactly one disposition **with a recorded reason**:

- **relocate** — the property still matters and still has a subject. Default for anti-drift
  guarantees. The cross-surface action-pin parity guard is the clearest case: its second operand is
  resolved from the retiring host, so it must be re-pointed, **never dropped**.
- **rewrite** — the property matters but its expression no longer can. The pull-request-only
  assertion is the load-bearing case: it pins an **exact string** that is *unsatisfiable* under the
  new trigger, so a verbatim port would pass over a job that never runs. Re-express it in the new
  trigger's vocabulary, asserting **each conjunct individually**.
- **retire-as-moot** — the subject genuinely ceased to exist. Permitted, and **recorded with the
  reason**. The non-blocking allowlist entry is a candidate once its subject leaves the scanned file.

Also update the exact-job-set equality that names the retiring job.

**Prohibited**: deleting a rule with no disposition; leaving a justification describing something no
longer true; weakening an assertion to make it pass.

**Validation**: every inventory entry has a disposition and a reason; the full
`tests/architectural/` and `tests/release/` batteries pass.

### T031 — Move the governance documents in lockstep

**Steps**:
1. Update the pipeline job-inventory document — it already understates the job count and must reflect
   the new topology.
2. Correct the coverage-signals reference page, which is factually wrong today (tracked as **#4011**).
3. If either page is new to the docs index, remember this repo requires **triple registration** —
   the curated index, the page inventory, and the retrieval index — or the docs gates red.

**Validation**: the docs freshness and terminology gates pass.

### T032 — Issue-matrix verdicts and the post-integration observation

**Steps**:
1. Record a verdict for every issue the spec names: **#4334** (this mission), **#4350**
   (Automatic Analysis precondition), **#4351** (dormant test file), **#825**, **#4248**, **#4011**.
   Deferred items need a real handle — all six exist, so nothing may be fabricated.
2. Record the **post-integration observation** the declared limit requires: after this lands, the
   first run of the reporting job is observed and its run id recorded. Until #4350 is cleared the
   observation will show the publication refusal — **record that honestly**; it is the declared state,
   not a failure of this mission.

**Validation**: issue-matrix verdicts complete; the observation is recorded with a run id or an
explicit "not yet observed, blocked on #4350".

## Branch Strategy

- **Planning base branch**: `issue-4334-sonar-reuse-shard-coverage`
- **Final merge target**: `issue-4334-sonar-reuse-shard-coverage`
- Worktrees are allocated per computed lane from `lanes.json`; `spec-kitty implement WP06` resolves it.

**Test scope (operator ruling):** run **targeted tests only** — your own new tests plus the specific gate files your diff touches (locate them with `grep -rl "<symbol>" tests/ --include="*.py"`). **Do not run the full `tests/architectural/` battery** — it is heavy, has been observed killing dispatched agent processes, and belongs to CI. Record the exact commands and counts in your handoff; "targeted tests pass, full arch suite deferred to CI" is the honest statement.

## Definition of Done

- [ ] Derivation script committed; artefact reproducible; freshness gate present
- [ ] The duplicate-measurement job is gone and the suite runs once per change
- [ ] WP04's characterisation seam is flipped to the clean-tree assertion
- [ ] The battery module's disclosed-gaps list and header match what is actually closed (T029b)
- [ ] The shard-map test count is correct, or the discrepancy is reported as out-of-ownership
- [ ] Every inventory entry carries a disposition **and a reason**
- [ ] The pull-request-only assertion is **rewritten per-conjunct**, not ported verbatim
- [ ] The action-pin parity guard is **relocated**, not dropped
- [ ] Both documents updated; docs gates pass
- [ ] Issue-matrix verdicts recorded for all six issues, none fabricated
- [ ] Post-integration observation recorded honestly
- [ ] Targeted tests pass: the gate files named in your derived inventory plus `test_sonar_workflow.py` and `test_release_ci_ownership.py`; full arch/release suites deferred to CI; `ruff check` and `ruff format --check` clean on changed files

## Reviewer Guidance

- **Diff the deletions first.** Every removed assertion must map to an inventory entry with a
  *retire-as-moot* disposition and a reason. An unexplained deletion is this work package's
  characteristic failure.
- **Check the re-expressed condition asserts conjuncts individually.** A whole-string assertion means
  a future edit dropping the same-origin clause passes silently.
- **Verify the inventory was derived**, by re-running the script yourself and diffing.
- **Do not accept a green pipeline as evidence the report works.** It cannot, until #4350 clears. The
  honest claim is "the suite runs once and the report is wired"; anything stronger is overclaiming.
- **Reviewer ≠ implementer** (C-007).
