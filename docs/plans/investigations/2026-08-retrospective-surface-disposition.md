---
title: 'Retrospective-learning surface: disposition and sequencing'
description: 'Planner disposition for the retrospect-surface blind spot (#1239/#2267/#3072): milestone the two orphans now, then mint one lightweight epic on the dual-schema reconciliation.'
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/3-2-x-milestone-roadmap.md
- docs/architecture/status-model.md
- docs/plans/index.md
---

# Retrospective-learning surface: disposition and sequencing

> **Status update (2026-09-30).** The two orphans are now milestoned: #2267 on *CLI 4.x stable* and #3072 on *Product backlog*, not 3.2.x as proposed below (the 3.x line closed with 3.2.7). The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

**Scope:** a draft investigation on the distil-then-retire working surface —
**not** a canonical ADR. It records a planner disposition decision (roadmap-line vs
de-scope vs fold vs minimal-fix) plus sequencing for the retrospective-learning
blind spot. The one genuinely architectural call inside it — which record contract
becomes canonical — is deferred to architect review and, when settled, belongs in
an ADR under `docs/adr/3.x/`. This document retires once that ADR and the owning
epic exist. Evidence base: `work/bug-triage-research/blindspot-retrospect.md` and
`categorization-findings.md` §4.

## Problem

The retrospective-learning surface (`src/specify_cli/retrospective/`, 16 modules +
runtime hooks + the `spk-gate-retrospective` skill) carries three open defects with
**no owning epic**: #1239, #2267, #3072. It is the product of four source
missions plus a perf spike — substantial prior investment, and a `deprecation.py`
that actively migrates config **forward**, so the surface is *maintained, not
winding down*.

**Corrected framing (milestone vs epic).** The aggregate `categorization-findings.md`
§4 called this "no roadmap home." The tracker is more precise: the surface is
homeless on the **epic** axis, not uniformly on the **milestone** axis.

| Bug | Milestone | State |
|---|---|---|
| #1239 | **3.2.x** | P1; pulled onto the critical path by the 2026-07-04 operator ruling (`3-2-x-milestone-roadmap.md:386`). |
| #3164 | **3.2.x** | P1, reliability — **fixed via #2717 (commit `87b37246c`), closed.** |
| #2267 | **None** | milestone-hygiene drift. |
| #3072 | **None** | milestone-hygiene drift. |

So of the three still-open defects one (#1239) is a loose P1 line on 3.2.x with **no
owning epic**, and two (#2267, #3072) are §3.1 milestone drift. This is an
**ownership gap, not a scheduling gap** — the distinction that drives the decision
below.

## Evidence

**The load-bearing fact is a dual top-level record schema** in
`retrospective/schema.py`: a Pydantic `RetrospectiveRecord` (**`schema.py:380`**,
`schema_version:"1"`, `extra="forbid"`) sitting beside a dataclass
`GenRetrospectiveRecord` (**`schema.py:581`**, `schema_version:1` int). Two
independently-authored contracts, one per source mission, **never reconciled by an
ADR**. Every consumer is written as "try Pydantic, except → try Gen." That
split-brain is the parent defect.

- **#1239** (P1, 3.2.x) — `create` writes the **Gen** shape; `synthesize`'s
  `read_record` uses Pydantic `extra=forbid` and rejects every Gen field; `summary`
  then counts the record malformed. Fallback readers were bolted on, but
  `src/specify_cli/cli/commands/agent_retrospect.py:540` still warns *"proposal
  application not available for generator-shape proposals yet"* — the payoff path
  (apply learnings to doctrine) is **dead for exactly the shape `create` writes**.
  Root: the dual schema.
- **#3164** — **Resolved by #2717 (commit `87b37246c`) and now closed; no longer a
  member of this epic.** The discovery-source mismatch is fixed: `summary`'s
  `iter_mission_instance_dirs` (`summary.py:300`) now anchors on `kitty-specs/*` and
  **excludes** `.kittify/missions/`, so it no longer picks up template/`__pycache__`
  dirs as pseudo-missions.
- **#3072** (P2, None) — `generator.py:_TRACE_ENTRY_RE:89` only matches bold-lead
  list items, but shipped tracer doctrine (`mission-tracer-files.procedure.yaml`,
  #2203) tells authors to write **prose** → a doctrine-conformant tracer yields zero
  findings. Two-package root: parser **and** the doctrine procedure.
- **#2267** (None) — `generator.py:_detect_force_overrides:453` counts any forced
  transition as a guard-bypass and does not exclude
  `_is_review_rejection_event:362`, so the state-machine-*required* `--force` on an
  `in_review→planned` rejection is mislabeled and rejection cycles are
  double-counted. Sibling of #1734.

**Blast-radius fact (bounds the urgency).** The completion **gate**
(`retrospective/gate.py:is_completion_allowed`) is **event-driven** against
`status.events.jsonl`, *schema-independent*. A schema-broken record does **not**
block `done`; `spk-gate-retrospective` runs post-merge without blocking completed
work. Net: the three bugs **nullify the analytics/learning output but do not block
delivery** — high value-erosion, low delivery-risk. The gate sits on the critical
path; the record/learning flow is an adjacent post-merge analytics layer, and all
three defects live in that second layer.

## Options considered

Compressed from the brief, with the planner verdict on each.

- **(a) New owning epic "Retrospective-learning surface reliability."** — *Accept, in
  lightweight form.* Three defects share one structural root and are cohesive; it
  gives #1239 an epic home and reflects the four-mission investment. The
  "adds a goal to a ~95%-mapped roadmap" objection is real, which is why the epic is
  scoped tight (see Decision), not a broad program.
- **(b) Fold under #3148 (closeout follow-through).** — *Reject.* #3148's charter is
  *issue-parking for homeless follow-ups*, not *subsystem repair*. Folding a
  three-defect subsystem with an architectural root under it is the force-fit
  anti-pattern #3148 itself warns against; it would need an explicit charter
  amendment to be honest, at which point you have re-created an epic under the wrong
  name.
- **(c) De-scope / deprecate.** — *Reject (strongly).* The gate is critical-path and
  event-driven — you cannot cleanly remove the surface without redesigning `done`.
  `deprecation.py` shows forward-migration, four missions + skill + profile +
  synthesizer are sunk value, and the operator already milestoned two defects as P1
  = an explicit *"fix"* signal, not *"kill."*
- **(d) Fix-4-bugs-only + milestone the two orphans.** — *Accept the milestone half,
  reject the fix-only half.* Milestoning #2267/#3072 is a zero-cost hygiene win.
  But stopping there leaves #1239's dual-schema reconciliation — an architectural
  decision — unowned, which invites whack-a-field: the next retrospect defect
  re-orphans and the "try Pydantic except Gen" tax stays.

## Decision

**Hybrid (d)-milestone + (a)-lite epic.** Concretely:

1. **Immediately milestone #2267 and #3072 to 3.2.x** (zero-code hygiene; stops the
   burn-count leak — these are exactly the §3.1 milestone-drift class the aggregate
   flagged).
2. **Mint one lightweight owning epic** spined on the **#1239 dual-schema
   reconciliation** as its root-cause line, with **#3072 and #2267 as members**.
   This converts three orphan symptom-lines into one owned root-cause line.

**Architectural justification (for architect review).** The remaining symptoms are
downstream of a single unmade architecture decision: *which record contract is
canonical.* #3072 (tracer parser) and #2267 (force classifier) are leaf defects;
#1239 is the seam. Point-patching the leaves without naming a canonical contract is
the "point-patch a shared seam" mistake — every consumer keeps its
`try-Pydantic-except-Gen` branch and the dead proposal-application path
(`src/specify_cli/cli/commands/agent_retrospect.py:540`) stays dead. The
reconciliation is a real ADR-shaped choice — **pick one canonical
`RetrospectiveRecord`, or sanction a single adapter at a named boundary** — and it
needs a home that a symptom ticket cannot provide. That is the whole reason for an
epic rather than three milestone lines. The disposition does **not** choose the
contract here (that is the architect's call and the epic's first deliverable, now
answered in [Architect recommendation](#architect-recommendation)); it asserts only
that the decision must be *owned* before the leaves are touched. With #3164 resolved,
the ADR gates exactly one leaf (#1239's read/create/synthesize path); #3072 and #2267
are parallelizable from step 1.

Why *lightweight*: the surface is post-merge analytics, not delivery-critical
(event-driven gate). The epic buys ownership and an ADR home, not a large program;
its first increment should be scoped to *trustworthy records + summary*, with
proposal-application deferred pending the operator input below.

## Architect recommendation

> **Operator-accepted (2026-08-16).** The recommendation below is adopted as the
> decision; the epic's first-deliverable ADR ratifies it rather than re-opening it.

The record-contract choice this disposition deferred to architect review has been
made (architect-alphonso, 2026-08-15):

**Adopt the Pydantic `RetrospectiveRecord` (`schema.py:380`) as the single canonical
*persisted* contract; demote `GenRetrospectiveRecord` to an internal
generator-scratch type that is never persisted; sanction exactly one adapter at the
generator→persist seam.**

The real decision is *which layer is allowed to have two shapes.* The on-disk
`retrospective.yaml` contract — and every reader of it — must be single. Pydantic
wins because:

- It is **already the reader contract** (`read_record` / `synthesize` consume it),
  so canonicalising it leaves the readers untouched and moves the single adapter to
  the **write** side, where there is exactly one producer — one adapter instead of N
  `try-Pydantic-except-Gen` branches.
- `extra="forbid"` gives the **fail-closed** posture the charter expects.
- The nested `mission: MissionIdentity` shape is DDD-cleaner.

The generator may keep `GenRetrospectiveRecord` internally, but must adapt to the
canonical shape **before** persistence, at one named seam.

The ADR's real work is the **field mapping** (Gen flat identity → Pydantic nested
`MissionIdentity`) plus **`schema_version` unification** (string `"1"` wins;
read-time migration for int-tagged `1` records). Canonicalising also un-deads the
proposal-application path (`src/specify_cli/cli/commands/agent_retrospect.py:540`).

**Rejected as an end-state:** two persisted contracts behind a single `load()`
adapter. Acceptable only as a one-release migration bridge — as a permanent design it
perpetuates two wire formats, double-adds every field, and re-opens version-tag
divergence.

## Recommended tracker actions

- **Milestone → 3.2.x:** #2267, #3072 (hygiene; do this first, independent of the
  epic).
- **Mint epic** — proposed title **"Retrospective-learning surface reliability"**;
  scope: *reconcile the dual record schema and restore trustworthy
  create→synthesize→summary output.* Members: **#1239 (root), #3072, #2267.**
- **First epic deliverable = an ADR** on record-contract ownership (canonical
  contract vs sanctioned adapter). Do not start the leaf fixes before it lands.
- **Do not fold under #3148** — cross-link only, with a note that closeout
  follow-through and subsystem repair are distinct charters.
- **#2342 perf verdict** — file it into this epic (it currently has no home).
- Leave #1239 on its existing 3.2.x milestone; the epic is the *epic* axis, not a
  milestone change. (#3164 is already closed — fixed via #2717.)

## Sequencing

1. **Now, zero-code:** milestone #2267 + #3072 → 3.2.x; mint the epic; parent all
   three (#1239, #3072, #2267). (No dependencies.)
2. **Gate item — ADR on the canonical record contract (#1239 root).** Blocks the
   record-shape-touching fixes below. Owner: architect. (The architect's answer is
   in [Architect recommendation](#architect-recommendation); the ADR ratifies it.)
3. **#3072 (parser + tracer procedure)** and **#2267 (force classifier)** — leaf
   fixes, **independent of the schema decision and of each other**; parallelizable
   any time after step 1. #3072 must touch *both* the parser regex and
   `mission-tracer-files.procedure.yaml` in one change (two-package root) or it
   re-opens.
4. **Proposal-application path** (the dead
   `src/specify_cli/cli/commands/agent_retrospect.py:540` warning) — gated on the
   operator input below; scheduled only if synthesize output is actually consumed.

## Open questions for the operator

- **Record-contract choice — answered.** The "which record contract is canonical"
  question this disposition deferred to architect review now has an answer: adopt the
  Pydantic `RetrospectiveRecord` as the single persisted contract, with one write-side
  adapter (see [Architect recommendation](#architect-recommendation)). The ADR in
  Sequencing step 2 ratifies it — no further operator input needed on the mechanism.
- **Does the operator actually consume the `synthesize → doctrine-mutation`
  output?** *Recommended default: assume yes* (forward-migrating `deprecation.py` +
  the skill deployed across all agent dirs signal intent) **but** scope the epic's
  **first** increment to *trustworthy records/summary only* and defer
  proposal-application (step 4) as a fast-follow. If the answer is **no**, narrow the
  epic permanently to records/summary and close the proposal-application path rather
  than fixing it. Flagging rather than silently resolving: this changes epic scope,
  so it is the operator's call.
- **Epic weight.** Recommended default: keep it lightweight (one ADR + three fixes).
  Confirm this is not over-weight for a non-blocking analytics surface, or conversely
  that the operator wants the full synthesize payoff restored.
