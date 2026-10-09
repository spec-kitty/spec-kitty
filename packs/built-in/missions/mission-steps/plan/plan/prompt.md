---
description: Decompose the problem, sequence the work, and decide the trade-offs
---
**Path reference rule:** When you mention directories or files, provide either the absolute path or a path relative to the project root (for example, `kitty-specs/<plan>/`). Never refer to a folder by name alone.

**In repos with multiple missions, always pass `--mission <handle>` to every spec-kitty command.** The `<handle>` can be the mission's `mission_id` (ULID), `mid8` (first 8 chars of the ULID), or `mission_slug`. The resolver disambiguates by `mission_id` and returns a structured `MISSION_AMBIGUOUS_SELECTOR` error on ambiguity — there is no silent fallback.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## What This Step Is

This is the decomposition-and-decision core of the plan mission. Working
from the specification and the research findings, you break the problem
into tractable sub-problems, scope and sequence them, and record the
trade-off decisions that resolve the material choices. **There is no code,
API, or implementation-detail section in this artifact** — a plan is a
structure and a set of decisions, not a build.

## What to Do

1. **Decompose the problem.** Apply Problem Decomposition: break the
   problem into smaller, independently tractable sub-problems before
   selecting or committing to a single approach. Premature convergence on
   one solution hides the parts of the problem it does not actually
   address. Group related sub-problems into clusters; where a cluster
   diverges in vocabulary or ownership from another (per the `research`
   step's bounded-context findings), keep the clusters decoupled rather
   than force-merging them.

2. **Scope with MoSCoW.** For the sub-problems and clusters identified,
   sort into Must (without it the plan fails its purpose), Should
   (important, painful to omit, but not fatal), Could (desirable, included
   only if room remains), and Won't-this-cut (explicitly deferred, recorded
   so it is not silently relitigated). Name the constraint forcing the
   trade-off — usually the time-box or resourcing limit from the
   specification.

3. **Sequence with Eisenhower Prioritisation.** Rate each Must/Should
   sub-problem by importance (does it move the plan's goal meaningfully
   forward?) and urgency (is there a real, near-term consequence to
   delaying it?). Order the sequence so genuinely urgent-and-important work
   leads, and distinguish real urgency from manufactured urgency.

4. **Draft a decision for every material trade-off.** Apply the ADR
   Drafting Workflow: for each trade-off surfaced during decomposition,
   write Context (problem, drivers, constraints), Decision (chosen option,
   ≤120 words), Rationale (why it wins), Alternatives (rejected options,
   one-sentence rejection reason each), and Consequences (accepted
   trade-offs, positive and negative). A decision without recorded
   alternatives is not traceable — do not skip them.

5. **Capture decisions where they are made, not after the fact.** Apply
   Traceable Decisions / Decision Marker Capture discipline: as soon as a
   choice is made during decomposition, record it immediately with its
   rationale — do not defer decision capture to a final write-up pass,
   where context and alternatives are more likely to be lost or
   reconstructed inaccurately.

6. **Premortem the plan.** Apply Premortem Risk Identification: assume the
   plan has already failed, and work backward — generate a wide list of
   failure scenarios (technical, social, resourcing, timing) without
   self-censoring, rate each by impact and likelihood, then carry the
   highest-impact and most-likely risks forward with a mitigation or an
   explicitly accepted risk.

7. **Define the handoff.** State what happens after this plan is approved —
   for example, spinning off one software-dev mission per Must sub-problem,
   or routing a specific decision back to a stakeholder for final sign-off.

## Visual Communication (recommended)

Apply the visual doctrine when decomposition, dependencies, sequencing,
decision paths, or handoffs are clearer visually. Load `spk-practice-show-me`
and add the smallest useful diagram. Prefer Mermaid inline; use PlantUML only
when its richer layout or DSL materially helps. Keep tables and decisions
authoritative, and skip diagrams that merely decorate the plan.

## Deliverable

Fill in the plan template (`artifact_key: plan`) with: Problem
Decomposition, Scope (MoSCoW), Sequencing & Prioritisation, Decisions (one
ADR-style entry per material trade-off), Risks (Premortem), Handoff, and
any Open Questions Carried Forward.

## Success Criteria

- Every sub-problem in the decomposition table has a cluster and explicit
  dependencies.
- The MoSCoW scope names the forcing constraint, not just the buckets.
- Every material trade-off has a decision entry with rejected alternatives
  and consequences — no undocumented decisions.
- The premortem risk table names at least the top risks by impact and
  likelihood, each with a mitigation or an explicit accepted-risk note.
