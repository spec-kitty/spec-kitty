---
title: Mission Types
description: 'The four Mission types Spec Kitty ships today, their purpose, phases, and how to choose one.'
doc_status: active
kind: Explanation
updated: '2026-11-13T00:00:00Z'
audience:
- profile: external/tech-lead-evaluator
  guidance_text: Read this to see which kinds of work Spec Kitty structures as a Mission and what each type produces.
- profile: internal/lead-developer
  guidance_text: Read this to choose the mission type before you run /spec-kitty.specify.
related:
- context/ops-vs-missions
---
# Mission Types

A [Mission](ops-vs-missions.md) is the canonical spec-to-consolidate workflow unit.
Every mission is an instance of one **mission type**, which shapes the phases
it moves through, the artifacts it produces, and the agent instructions used
along the way. As of this writing there are exactly four mission types, each
defined by its own `mission.yaml` under `src/specify_cli/missions/` (the built-in pack
carries an identical copy under `packs/built-in/missions/<type>/`, beside the
`mission-runtime.yaml` step DAG):
`software-dev`, `research`, `documentation`, and `plan`. There is no fifth type
— if you're choosing, pick from this list.

## How to choose

| Your situation | Mission type |
|---|---|
| You're building or changing software: a feature, a fix, a refactor, with tests | **software-dev** |
| You need to systematically investigate a question and produce evidence-backed findings | **research** |
| You're creating or overhauling user-facing or contributor documentation | **documentation** |
| You need a goal-oriented plan/strategy document, not code or docs, with room to iterate | **plan** |

If your task doesn't need a spec, a review gate, or multi-session tracking at
all, you may not need a Mission — see [Ops vs. Missions](ops-vs-missions.md)
for the Op alternative.

---

## software-dev

**Purpose**: "Build high-quality software with structured workflows and
test-driven development." Enforces Library-First, CLI Interface, and
Test-First principles; tests are written before code.

**Phases** (`discovery` → `specify` → `plan` → `tasks` → `analyze` → `implement` →
`review` → `accept`, per the mission's runtime step DAG in `mission-runtime.yaml`):

1. Discovery & Research
2. Specification
3. Implementation Planning
4. Tasks
5. Analysis (cross-artifact consistency, recorded as an analysis report)
6. Implementation
7. Code Review
8. Acceptance

The `mission.yaml` workflow description frames the same arc as research → design →
implement → test → review. Required artifacts: `spec.md`, `plan.md`,
`tasks.md`; source code lands under `src/`.

**Best for**: any code change — new features, bug fixes, refactors — where
tests, an implementation plan, and code review matter.

---

## research

**Purpose**: "Conduct systematic research with structured methodology and
evidence synthesis." Enforces research integrity and methodological rigor: all
sources must be documented, findings must trace back to evidence, and at least
3 sources must be documented before synthesis can begin.

**Phases** (`scoping` → `methodology` → `gathering` → `synthesis` → `output` →
`accept`, per the mission's runtime step DAG):

1. Research Scoping
2. Methodology Design
3. Source Gathering
4. Findings Synthesis
5. Publication Output
6. Acceptance

Required artifacts: `spec.md` (research question/scope), `plan.md`
(methodology), `tasks.md`, `findings.md` (synthesized findings). The mission
also expects `research/source-register.csv` documenting sources with citations, URLs,
and access dates; the gathering step needs at least three `source_documented`
events, and publication is gated on approval.

**Best for**: systematic literature reviews, empirical investigations, or any
question that needs a defensible, cited evidence trail rather than a single
freeform answer.

---

## documentation

**Purpose**: "Create and maintain high-quality software documentation
following Write the Docs and Divio principles." Drives documentation as code,
using the Divio four-type system (tutorial, how-to, reference, explanation)
and supporting three iteration modes: `initial` (from scratch), `gap_filling`
(audit existing docs and fill gaps), and `mission_specific` (document one
component; `feature_specific` is accepted as a legacy input alias).

**Phases** (declared under `workflow.phases`; the runtime step DAG follows the
same arc and adds a final acceptance step):

1. Discover — identify documentation needs and target audience
2. Audit — analyze existing documentation and identify gaps
3. Design — plan documentation structure and Divio types
4. Generate — create documentation from templates and generators
5. Validate — check quality, accessibility, and completeness
6. Publish — deploy documentation and notify stakeholders

Required artifacts: `spec.md`, `plan.md`, `tasks.md`, `gap-analysis.md`.
Supports generator integration (JSDoc, Sphinx, rustdoc) for API reference
docs.

**Best for**: standing up documentation from nothing, auditing and closing
gaps in existing docs, or documenting one specific component in depth.

---

## plan

**Purpose**: "Goal-oriented planning with iterative refinement." Designed
for planning artifacts (strategy, structured plans) rather than code or
end-user docs, where iteration is expected: a review can send a draft back
for another pass instead of forcing linear progress.

**Phases** (`specify` → `research` → `plan` → `review`, per the mission's
runtime step DAG):

1. Specify — define the goals
2. Research & Analysis
3. Draft Plan
4. Review & Approval

Required artifacts: `spec.md`, `plan.md`; optional `research.md` and a `data/`
directory. Unlike the other three types, this mission type's approval gate is
plan approval rather than a code-review or publication gate.

**Best for**: producing a goal-oriented plan or strategy document where you
expect to iterate — research findings can send you back to restructuring, and
review can send a draft back for another pass — before anything is
implemented.

---

## Verifying this list yourself

This page is generated from reading each mission type's own definition
directly, not from memory:

```bash
ls -d src/specify_cli/missions/*/ | grep -v __pycache__
# src/specify_cli/missions/documentation/  plan/  research/  software-dev/
cat src/specify_cli/missions/<type>/mission.yaml
```

If a fifth mission type directory appears in that listing that isn't described
above, this page is stale — file a docs gap rather than guessing at its
purpose.

For the distinction between starting a Mission and using a lightweight Op
instead, see [Ops vs. Missions](ops-vs-missions.md).
