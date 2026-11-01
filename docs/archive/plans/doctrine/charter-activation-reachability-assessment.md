---
title: 'Charter Activation vs DRG Reachability: Which Path Actually Reaches an Agent'
description: Why 185 charter-activated doctrine artefacts never surface at the action-context boundary, the three parallel activation vocabularies behind it, and the recommended fix ordering.
doc_status: deprecated
updated: '2026-07-28'
type: explanation
related:
- docs/plans/doctrine/layered-doctrine-resolution-design.md
- docs/archive/plans/doctrine/doctrine-artifact-selection-preflight.md
- docs/development/how-to/review-gates.md
- docs/adr/3.x/2026-07-26-1-drg-edges-are-the-canonical-relationship-authority.md
---
# Charter Activation vs DRG Reachability

> **Retired (deprecated).** Shipped as the landing pass for PR #3007 (#3009); superseded by the delivery-reachability wiring table. Preserved as a historical record.

**Origin.** Written during the landing pass for PR #3007 (mission
`doctrine-silence-guards-01KYFV7Q`), in response to an operator question:
*"I would expect directives, and paradigms especially, to be activated directly
from the charter — any element of the doctrine/DRG can be referenced there to be
activated. Which path is actually being followed?"*

The short answer: **the operator's expectation is the correct design intent, it is
half-implemented, and the half that is missing is the half agents actually read.**

Issue [#3009](https://github.com/Priivacy-ai/spec-kitty/issues/3009) frames the
problem as nine activated artefacts being DRG orphans. That framing is true but
too narrow — and acting only on it would produce a fix that does not fix the
symptom. This document records why.

---

## 1. What was measured

All figures re-derived on the PR #3007 tip rebased onto `e97fc6ab9`, this
repository, `2026-07-28`.

`.kittify/config.yaml` activation counts:

| key | count |
|---|---|
| `activated_tactics` | 110 |
| `activated_directives` | 25 |
| `activated_procedures` | 18 |
| `activated_styleguides` | 12 |
| `activated_toolguides` | 12 |
| `activated_paradigms` | 8 |
| **total** | **185** |

What the action-context boundary renders — the surface an agent consumes at a
step boundary, invoked with the correct grain:

```
$ spec-kitty charter context --action implement --mission-type software-dev --json

Governance:
  - Template set: software-dev-default
  - Paradigms: (none)
  - Tools: git, mypy, pytest, ruff, spec-kitty
Directive IDs:
  - DIR-001 … DIR-013
Tactic IDs:
  - (none)

references_count            : 0
directives (action-scoped)  : 0
```

**185 activated artefacts; zero of them appear.** The thirteen `DIR-0NN` entries
are not the activated doctrine directives (`DIRECTIVE_001`, `DIRECTIVE_035`, …) —
they are bullet lines scraped from the charter prose, with titles like
`**Cross-platform:** Linux, macOS, Windows 10+`. The 25 activated doctrine
directives are absent, as are all 110 tactics and all 8 paradigms.

This is not the typeless-grain defect of #883: the run above passes
`--mission-type software-dev` explicitly and the result is identical to the
typeless run.

## 2. Why — three parallel activation vocabularies

Activation is not one mechanism. It is three, with different storage, different
writers, and different readers.

| # | Vocabulary | Stored in | Written by | Read by |
|---|---|---|---|---|
| **V1** | `activated_<kind>` | `.kittify/config.yaml` | `charter activate` / `deactivate` | `charter.resolver` (as a *filter*), `charter.compiler._resolve_config_activated_roots` (as compile *roots*) |
| **V2** | `selected_<kind>` | `.kittify/charter/interview/answers.yaml` | the charter interview | `charter.compiler` charter-body render (`Selected Doctrine`) |
| **V3** | `selected_<kind>` | `.kittify/charter/charter.yaml` | charter compile | assorted consumers |

In this repository today:

- **V1** holds 185 artefacts.
- **V2** holds 110 tactics and 25 directives but `selected_paradigms: []`.
- **V3** holds `selected_*: []` for **every kind** — all eight lists empty.

The compact view that `charter context --action` renders takes its paradigm line
from the **V2** interview answers (`compiler.py:1282`,
`', '.join(interview.selected_paradigms) or '(none)'`) — which is empty — and its
tactic list from a `tactic_ids` argument that the action-context caller passes as
`()` (`context.py:2814-2817`, `render_compact_view(..., tactic_ids=tactic_ids or ())`).

So the `(none)` values are literally correct for the vocabulary being consulted.
The activated set is simply not the vocabulary that surface reads.

## 3. What activation *does* do today

Activation is **not** wholly inert, and it is important not to overstate this.
Two paths honour V1 correctly:

- **On-demand fetch works.** `spec-kitty charter context --include tactic:acceptance-test-first`
  returns the full artefact — purpose, steps, references. An agent that knows an
  id can always reach it.
- **Compile-time root seeding works.** `charter.compiler._resolve_config_activated_roots`
  seeds tactics, styleguides, toolguides, procedures and agent profiles as direct
  roots, explicitly *"so an artefact activated directly in `config.activated_*`
  resolves in the compiled set even when no selected directive's transitive
  closure reaches it"* (compiler.py:70-77). That docstring is the design intent
  the operator described, stated in the code.

What is missing is the third path: **the action-scoped context boundary does not
consult V1 at all.** Activation influences what is *compiled* and what can be
*fetched*, but not what is *offered* at the moment an agent starts an action.

## 4. Why this reframes #3009

Issue #3009's remedy 2 says each of the nine orphans needs *"either an inbound edge from
whatever should reach it, or an explicit 'reachable by direct activation only, by
design' note."*

Both branches are currently unsound as stated:

- **The edge branch fixes traversal, not the symptom.** Adding an inbound
  `requires` edge makes an artefact reachable by cascade and by DRG traversal from
  whatever it is attached to. It does **not** make it appear in
  `charter context --action`, because that surface renders from V2/V3, not from a
  DRG walk over V1. Wiring all nine and re-running the command yields the same
  `(none)`.
- **The direct-activation branch presumes a capability that is absent.**
  "Reachable by direct activation only" is only an acceptable disposition if
  direct activation actually surfaces the artefact somewhere an agent looks. Today
  it surfaces only under `--include`, which requires already knowing the id.

This is the mission's own thesis one level up the stack. `doctrine-silence-guards`
was built on the finding that *"resolves" was operationalised as id-lookup rather
than reachability*. Charter activation currently operationalises *"activated"* as
**membership in a filter list** rather than **presence in the context an agent
receives** — the same substitution, at the layer above the one the mission fixed.

## 5. Recommendation

Ordered by leverage, not by cost.

### R1 — Make activation an entry vector into action context (the real fix)

The action-context builder should seed its directive/tactic/paradigm lists from
the **V1 activated set**, intersected with the action grain, rather than from the
V2 interview answers. Concretely: the `directive_ids` / `tactic_ids` the
action-context caller currently passes as `()` should be populated from
`resolve_config_activated_roots`, which already exists and already does the
resolution correctly.

This makes the operator's stated expectation true: *anything referenced in the
charter is activated, and activation means an agent sees it.* It also makes the
orphan question far less load-bearing, because direct activation becomes a
first-class entry vector rather than a dead end.

**Caveat to size before doing it:** 110 activated tactics is far more than an
action boundary should emit verbatim. R1 needs a grain filter (by action, by
mission type) or a two-tier render (ids at the boundary, bodies on `--include`).
The compact view already has that shape — it emits *ids*, not bodies — so the
cost is mostly in choosing the grain, not in the plumbing.

### R2 — Collapse the three vocabularies to one

V2 and V3 are both `selected_*` and both currently empty or partial, while V1 is
the one the CLI writes. Three vocabularies for one concept is the condition that
produced this defect; it will produce another. V1 (`config.activated_*`) is the
right survivor — it is what `charter activate` writes and what the compiler
already treats as authoritative roots. V2 should become an *input* to V1 at
interview time, not a parallel store consulted at render time.

This is an ADR-level change, not a fold. It should be decided before **B2**,
which migrates 400+ inline `references:` into authored edges and will otherwise
encode the ambiguity into the edge set.

### R3 — Adopt #3009 remedy 1 now (cheap, and correct regardless of R1/R2)

Replace `_EXPECTED_ORPHAN_COUNT: int` with a named `frozenset` of intentional
orphans and assert set equality. A golden count cannot distinguish *"32
known-acceptable orphans"* from *"32 unexamined orphans"*; a named set makes each
one carry a justification and makes a new one name itself in the failure. This is
independent of the activation question and should land immediately.

### R4 — Triage the nine, with the disposition vocabulary fixed

With R1 pending, the honest dispositions are:

- **remove** — the artefact should not ship;
- **wire** — it has a genuine structural relationship that is simply unauthored;
- **direct-activation-only** — legitimate, *conditional on R1 landing*; until then
  record it as a known gap rather than as an accepted design.

Operator rulings taken 2026-07-28:

| artefact | disposition |
|---|---|
| `toolguide:rtk-search-tooling` | **remove** — RTK will not be pushed to the userbase; it is difficult to set up correctly and can significantly affect test execution |
| the other eight | **wire** — oversights, not design |

### R5 — Measure reachability, not incidence

Issue #3009's third point stands and is the most important thing to do before B2. The
pinned orphan metric counts *incidence* (nodes touching no edge, currently 30).
The operationally meaningful numbers are worse and unpinned:

| measure | count |
|---|---|
| incident to no edge (currently pinned) | 30 |
| zero **inbound** edges — unreachable by any traversal | 80 |
| unreachable from any `action` node | 144 of 311 (46%) |

Fifty nodes have outbound edges only: non-orphan by the pinned metric,
unreachable in fact. B2 moves all three numbers at once; entering it with the
wrong metric pinned is the trap.

## 6. What this means for PR #3007

Nothing in section 5 is a defect *introduced* by #3007 — every item predates it.
The mission's own WP09 explicitly logged the incidence-vs-traversability gap and
declined to change it mid-mission, which was the right call.

R3 and R4 are folded into the PR because they are small, bounded, and use the
structures the mission just built. **R1 and R2 are not** — they change what an
agent receives at every action boundary in every consumer project, which is a
mission with its own spec and its own blast-radius analysis, not a landing fold.

They are, however, the difference between a doctrine layer that is *declared* and
one that is *in force*.
