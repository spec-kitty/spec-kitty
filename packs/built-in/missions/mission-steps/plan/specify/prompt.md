---
description: Frame the problem, goals, and boundaries this plan mission exists to resolve
---
**Path reference rule:** When you mention directories or files, provide either the absolute path or a path relative to the project root (for example, `kitty-specs/<plan>/`). Never refer to a folder by name alone.

**In repos with multiple missions, always pass `--mission <handle>` to every spec-kitty command.** The `<handle>` can be the mission's `mission_id` (ULID), `mid8` (first 8 chars of the ULID), or `mission_slug`. The resolver disambiguates by `mission_id` and returns a structured `MISSION_AMBIGUOUS_SELECTOR` error on ambiguity — there is no silent fallback.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## What This Step Is — and Is Not

A `plan` mission produces a **decomposition-and-decision artifact**, not a
codebase change. The output of this step is a specification of a *problem to
be planned*: what needs deciding, who needs to agree, and what bounds the
decision. There is no code, API contract, or implementation detail in this
document — those belong to a downstream software-dev mission if and when the
plan is executed.

**Before writing anything, sanity-check the mission itself**: if the request
underneath this plan is really "build/change X in the codebase" rather than
"decide/sequence/structure X", say so and recommend a software-dev mission
instead of forcing code-shaped content through a plan-shaped artifact.

## Goal

Produce a plan specification that a stakeholder could read cold and
understand: what problem is being planned for, why it matters now, who has
to agree, and what boundaries constrain an acceptable plan.

## Visual Communication (recommended)

Apply the visual doctrine when stakeholder relationships, decision boundaries,
dependencies, or a non-trivial sequence is clearer visually. Load
`spk-practice-show-me` and add the smallest useful diagram. Keep it focused on
the planning problem; do not introduce implementation architecture.

## What to Do

1. **State the problem.** In 1-3 sentences, name the decision-shaped problem
   this plan exists to resolve — a choice to be made, a body of work to be
   sequenced, a structure to be designed. Name the trigger: a deadline, a
   recurring pain, a new constraint, an unresolved trade-off.

2. **Separate goals from non-goals.** List what a successful plan delivers.
   Then list what is explicitly out of scope — record it so it is not
   silently relitigated when the `plan` step gets underway.

3. **Name stakeholders and decision authority.** For each stakeholder,
   capture their interest and who actually has sign-off. If the same word
   means different things to different stakeholders (a bounded-context
   signal), flag it now rather than letting it surface as friction during
   decomposition.

4. **Record constraints.** Time-box, resourcing, dependencies on other
   decisions or deliverables, and any other hard boundary that bounds the
   space of acceptable plans.

5. **Define success criteria for the plan itself** — not for the eventual
   work the plan describes. A plan succeeds when it produces a decomposition
   and a set of decisions stakeholders can act on with confidence.

6. **Surface open questions.** List anything that must be answered before
   the `plan` step's decomposition can be trusted. These feed directly into
   the `research` step next.

## Deliverable

Fill in the plan specification template (`artifact_key: spec`) with the
sections above: Problem Statement, Goals & Non-Goals, Stakeholders &
Decision Owners, Constraints, Success Criteria, Open Questions, Out of
Scope.

## Success Criteria

- The problem statement is decision-shaped, not implementation-shaped.
- Every stakeholder has a named interest and decision authority.
- Constraints and non-goals are explicit, not implied.
- Open questions are concrete enough that the `research` step can act on
  them directly.
