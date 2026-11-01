---
title: 'ADR: A Mission-Halting Instrument Is Worth Its Cost — It Runs Before the Mission, and Its Verdict Is Acted On'
description: 'Records why a pre-mission ablation instrument that nothing consumed and nothing sequenced was worth its cost: it fired at |P| = 5, and the mission halted.'
status: Accepted
date: '2026-08-07'
doc_status: active
kind: ADR
updated: '2026-08-07T00:00:00Z'
---

## Context and Problem Statement

Mission `isolated-home-pin-convergence-01KZCTWC` set out to converge 28 test fixtures onto one
`SPEC_KITTY_HOME` owner. Its own first work package was not convergence work at all: it was an
instrument (`scripts/mutants/ablate_home_pin_3121.py`) built to answer the question the mission's
premise rested on — *do these 28 modules actually depend on the pin they all restate?*

That instrument was expensive. It required an externally provisioned venv on the pinned pytest, a
`pytest_fixture_setup` hookwrapper, three measurement arms, a positive control, a repeated and
interleaved re-run, and a published set. None of it edited a single line the mission was chartered
to change. Two structural properties of the mission made it look, at planning time, like overhead
that could be deferred or parallelised:

1. **Nothing consumed it.** Before spec amendment A14, no success criterion in the specification
   referenced the pre-convergence ablation at all. SC-001 through SC-011 are each defined over the
   *converged* tree or over source. An implementer who never wrote the instrument satisfied every
   gate the mission had.
2. **Nothing sequenced it.** The ~320-line manifest guard (IC-02) was originally scheduled to run
   *in parallel* with the instrument (IC-01).

The instrument then fired. `|P| = 5` — five behaviour-class members pass with the pin removed and
keep passing under a repeated, interleaved re-run — which is the mission's own halt trigger. The
operator signed off on halt-and-re-scope on 2026-08-07.

This ADR records why an instrument with that property is worth building, and what has to be true
about it for the verdict to survive contact with a mission that wants to proceed.

### What the instrument actually caught

It is worth being concrete, because the cheap version of this instrument would have reported
green and the mission would have run.

* **A broken hookwrapper reds a population as *setup errors*.** Recorded as ordinary non-passes,
  that yields `P = ∅` and greenlights the mission — the direction that also makes the three most
  expensive obligations in the work package vacuous. The instrument therefore carries `error` in
  its outcome vocabulary as a distinct kind, and any `error` voids the run. Measured: **0 errors
  across 526 nodes**.
* **A class-defined fixture has a class-qualified `baseid`.** The first arm-1 run bound **27 of 28**
  sites and ablated `test_identity_value_faults_3030.py` on **zero** of its 6 nodes, while still
  reporting a clean `35 failed`. The zero-ablation refusal (FR-011) cannot catch this — 27 sites did
  fire. Only the expected-versus-observed site comparison did.
* **The measurement is parallelism-dependent.** Under `-n0` arm 1 gives 491 pass / 35 fail and
  `|P1| = 15`; under `-n auto --dist loadfile` it gives 498 pass / 28 fail and `|P1| = 16`. That is
  not an instrument defect — it is the phenomenon under measurement showing up directly, because
  fewer tests share a worker home.

## Decision Drivers

* An instrument whose only consumer is the mission it can stop has no natural advocate. If nothing
  in the specification depends on it, it is the first thing dropped under schedule pressure.
* Sunk cost is an argument. Work completed before a gate's verdict exists becomes the reason to
  discount that verdict.
* A threshold chosen after the measurement is a threshold chosen to clear it.
* A verdict that can be argued with will be argued with, because the party reading it is the party
  the mission's remaining work belongs to.

## Decision Outcome

**An instrument that can halt its own mission is worth its cost; it runs before any surface the
mission would edit *and before any artifact that would argue for the mission*; its trigger and
consequence are fixed in the spec before the measurement; and its verdict is acted on rather than
argued with.**

The four clauses are separable and each earns its place.

### 1. Worth its cost

The instrument's cost is bounded and paid once. The cost it avoids is a mission that converges 28
fixtures onto an owner that five of them provably do not need, and then discovers it — if ever — in
the post-convergence discriminating red, after every adoption edit has landed.

The asymmetry is what settles it. Over-measurement biases toward *keeping* a member, which is the
safe direction. Under-measurement biases toward deletion, which is not.

### 2. Before any surface the mission would edit, and before any artifact that would argue for it

The first half is obvious: measure the tree before you change it, or the "before" half is
unobtainable.

The second half is the one that had to be learned. The manifest guard was originally scheduled to
run in parallel with the instrument. **A built guard is the strongest argument anyone will ever have
for not acting on its own gate's verdict.** Arriving at the halt with 320 lines of finished,
reviewed, working guard already in the tree changes what the halt costs to obey — and it changes it
in exactly the direction that makes obeying it less likely. The dependency edge from the guard to
the instrument is therefore not a technical dependency. It is a *rhetorical* one, and it is binding
for the same reason.

The generalisation: **anything that would function as an argument for the mission is downstream of
the gate**, whether or not it is downstream in the build graph.

### 3. Trigger and consequence fixed in the spec, before the measurement

The gate as first drafted said *"if a **material fraction** pass"* and *"**a large pass-rate** is a
STOP-and-re-spec signal"*. Neither is a trigger. There is no threshold, no expression of the verdict
as a set, no named decision-maker, and no ceremony.

The replacement fixes all four *before* anything ran:

* the verdict is a **set** `P`, published per member and keyed `(file, qualified_name)` — not a rate,
  not a count;
* the trigger is `|P| ≥ 5`, and **5 is derived from a figure the specification already committed
  to**: §0.6 refused a deletion prize of 4 of 28 as not worth its risk, so 5 is the smallest prize
  strictly larger than the one the mission had already declined. The threshold cannot be re-tuned at
  implementation time without visibly moving §0.6 too;
* the consequence is named — halt, pending explicit operator sign-off — in the same ceremony the
  specification already prescribed for reversing a recorded decision;
* the evidence shape is fixed: recorded raw output at a stated path, per-member pytest **node-ID**
  outcome sets, exact invocations including `-p`/`-n`/`--dist`, and enough for a reviewer to re-run
  and reproduce the same set. Without that clause the cheapest green *without running anything* is a
  desk-produced table asserting `P = ∅`.

### 4. Acted on rather than argued with

Two things make this operational rather than aspirational.

**Report on the measurement least favourable to halting.** Where the measurement was ambiguous, the
reading that made the halt *harder* was taken as authoritative. `-n0` is more red, therefore yields
the smaller `P1` (15 versus 16), therefore is the least likely of the two to trigger. Partition B
was excluded from `P` by construction even though including it could only raise `|P|`. The halt is
reported on the arm that argues against it, and it still fires.

**A lane state is not a halt.** Verified in this tree by AST, not transcription:
`src/specify_cli/status/wp_state.py:517` defines `BlockedState`; `:528` returns
`frozenset({Lane.IN_PROGRESS, Lane.CANCELED})`; and the class overrides no `guard_for`, so it
inherits the base hook at `:139` whose entire body is `return True, None` and whose own comment reads
*"the default is unguarded"*. So `blocked → in_progress` requires **no actor, no reason, no
`review_ref`, no force and no operator**, and `blocked → in_progress → for_review → approved`
delivers exactly the `approved` state every downstream work package gates on.

A halt therefore has to be recorded somewhere the state machine cannot walk past: an append-only
comment on the tracker issue, which any subsequent resumption must cite by URL. The unguarded edge
itself is filed as a tooling gap rather than worked around.

## Consequences

### Positive

* The mission stopped on evidence rather than on exhaustion, and the record shows a mission that
  worked rather than one that was rescued.
* The prize is now measured rather than assumed: the adopting set moves from 27 of 28 (96.4%) to
  24 of 28 (85.7%), and all three departing members are zero-decoration fixtures — the cheapest
  edits the mission had.
* The instrument is a reusable artifact. It is `-p`-loaded against an unmodified tree with zero
  source edits, so it can be re-run by any reviewer at the recorded pre-convergence SHA.

### Negative / accepted trade-offs

* The instrument is a real cost paid up front, and in the halting case it is the *only* work the
  mission ships. That is the trade this ADR accepts, not one it denies.
* Fixing the trigger before the measurement means committing to a number that later evidence might
  argue was wrong. That is the point; the alternative is a number chosen to clear.
* The rhetorical dependency edge (clause 2) serialises work that could have run in parallel, and it
  costs wall-clock time on every mission where the gate turns out to pass.

### Neutral

* The threshold's derivation is mission-local. `N = 5` is not a framework constant; it is anchored
  to a prize *this* specification had already refused. Another mission's instrument must derive its
  own trigger from its own committed figures.
* Nothing here says the halted mission was wrong to be proposed. The gate answered a question that
  was genuinely open, and "the premise does not hold for 5 of 28" is a result, not a failure.

### Confirmation — and what this ADR does not prove

The confirming signal already exists: the instrument fired, the trigger was met on the arm least
favourable to firing, and the mission halted with the operator's sign-off rather than proceeding.

What this ADR does **not** establish:

* It does not prove that a cheaper instrument would have missed the result. It proves that two
  specific cheap versions — one that folds `error` into non-pass, and one that does not compare
  expected against observed ablation sites — would each have reported the opposite result.
* It does not settle whether the five members should be *deleted*. That is a separate decision on
  separate evidence, and three of the five carry a scope caveat on the breadth of their arm-2 green.
* It does not generalise the instrument's mechanism. What generalises is the four-clause property,
  not the hookwrapper.

## Alternatives considered

**Run the instrument after the convergence.** Rejected: the "before" half of the comparison is
unobtainable once the adoption edits land, and an instrument that can only confirm is not a gate.

**Express the gate as a coverage rate.** Rejected on the mission's own constraint against counted
definitions of done. A rate does not move when a fixture *body* changes, and a member-level decision
cannot be read off a percentage. The verdict is a published set for the same reason the manifest is.

**Let the lane state carry the halt.** Rejected on the measured FSM behaviour above. `blocked` is a
label, not a gate.

**Let the implementer adjudicate the trigger.** Rejected. The party holding the mission's remaining
work is the wrong party to decide whether that work proceeds. The consequence names an operator, and
the record has to exist outside the machinery the implementer drives.

## More Information

* Mission record and full evidence:
  `kitty-specs/isolated-home-pin-convergence-01KZCTWC/evidence/ablation/` — `VERDICT.md`, `HALT.md`,
  `P.json`, `TABLES.md`, `REPRODUCTION.md`, `RESIDUALS.md`, `anchor.md`.
* Specification: `kitty-specs/isolated-home-pin-convergence-01KZCTWC/spec.md`, criterion SC-012 and
  amendments A14, A17, A18, A19, A20, A21.
* Instrument: `scripts/mutants/ablate_home_pin_3121.py`.
* The FSM surface this ADR measures: `src/specify_cli/status/wp_state.py`.
* Tracker: [#3121](https://github.com/Priivacy-ai/spec-kitty/issues/3121).
