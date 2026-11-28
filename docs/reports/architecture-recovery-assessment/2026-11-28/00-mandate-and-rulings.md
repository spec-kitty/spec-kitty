---
doc_status: draft
updated: '2026-11-28'
---

# Mandate and rulings

A recovery-oriented architectural assessment and design exercise for the Spec Kitty ecosystem, commissioned by its human architect on 2026-11-28. It follows the Wayfinder reconnaissance (`docs/reports/wayfinder-reconnaissance/2026-11-28/`) and reuses its findings. No production implementation or remediation is authorised.

Guiding principle of the architect: tidy first, even if inconvenient; but establish what deserves to remain before investing in tidying it.

## What the architect wants to know

1. How problematic the current architecture actually is.
2. Which mechanisms introduce unnecessary complexity.
3. Which capabilities are genuinely needed.
4. What a simpler, coherent architecture could look like.
5. What prevents moving towards it.
6. How to transition incrementally while the product keeps working.

## The class of problem

Structural dependency compliance is not architectural coherence. The concerns are: duplicated domain logic, responsibilities and intent; competing mechanisms for the same problem; special cases that bypass established abstractions and extension mechanisms; accidental complexity out of proportion to the problem; mechanisms that no longer justify their existence. The architect's example: mission types are configurable through Charter packs, while mission-specific conditionals are hardcoded in the CLI.

## Rulings

R1 to R13 were given on approval of the approach; R14 to R20 with the authorisation to dispatch, the same day. Dispatch was authorised with no production implementation or remediation.

| # | Ruling |
|---|---|
| R1 | Recorded decisions, approved changes and implementation choices are evidence, not deliberate intent beyond challenge. ADRs may be challenged. |
| R2 | Who caused the present state, human or agent, and a complete causal history are out of scope. History is used only where it informs a present decision or a migration constraint. |
| R3 | Necessity before implementation quality. No capability, abstraction or mechanism is assumed to deserve to survive. Recommendations are not limited to improving what exists. |
| R4 | Mechanisms in scope: worktrees, lanes, mission-type configuration, Mission and work-package lifecycle, Charter integration, event handling, execution coordination, and (approved addition) consolidation with its approval-evidence rules, and upgrade migrations with compatibility shims. |
| R5 | Needs come from documented needs and user journeys. Usage inside Spec Kitty's own repositories is heavily skewed to the software-dev mission type and must not be over-fitted. The two leading questions are: does the code need this complexity, and is this a remnant of an older design that was not fully extracted. |
| R6 | The ability to upgrade from an older version is not a hard blocker where it actively prevents the new shape. |
| R7 | Nothing existing is a fixed constraint: not the status event log format, not the existing Missions under `kitty-specs/`, not the orchestrator API, not the list of supported agents. The event log is moving to the events system and the charter to the charter system. The target is the best possible 4.0 release; historical usage and storage do not stop it. |
| R8 | Principles to preserve: Human in Charge, responsible delegation, explicit responsibility ownership, independent evolvability, governed Mission coordination. They may be challenged where applying them introduces unjustified complexity. |
| R9 | Evidence in proportion to risk, cost and reversibility. A plausible direction with representative evidence may justify a reversible experiment. Irreversible changes, persistent-data migrations and public-contract changes need stronger assurance. Exhaustive enumeration is not required where representative evidence makes a pattern credible. |
| R10 | A credible, actionable simplification proposal with stated uncertainties is preferred to an exhaustive investigation that leaves no decision possible. Look for complexity to delete, not only to reorganise. |
| R11 | Wayfinder stays prospective. Its scope follows from the needs found here and does not constrain this work. |
| R12 | Independent architectural perspectives and challenge are kept. The experimental apparatus of the reconnaissance (pre-registration, blind replication, mutations, seeded reproduction, prediction packet) is not repeated. The reconnaissance findings are freely reusable. |
| R13 | Storage: additive only, on the research branch, in this folder. No pull request unless asked. |
| R14 | The necessity of a capability and the necessity of its present implementation are separate questions. Four leading questions: does the need require the present complexity; is the mechanism a remnant of an older design never fully extracted or retired; are several generations of solutions operating at once; could the capability be kept through a substantially simpler mechanism. |
| R15 | Low use of a mission type, topology or capability inside Spec Kitty's own repositories is not sufficient evidence that it is unnecessary. Historical usage is supplementary evidence only. Counts from the code are indicators for where to look, not evidence of unnecessary complexity. |
| R16 | Existing user data and capabilities are not disposable. For every breaking change: the consequences, viable migration strategies, affected consumers and costs, presented as a trade-off for the architect. Not every historical version needs a supported migration path; where upgrade support obstructs a coherent 4.0, name the trade-off and consider discontinuing the compatibility mechanism. |
| R17 | Four things are kept apart: the intended target architecture, the current implementation, the transitional architecture needed to move between them, and legacy arrangements that can be retired. A temporary migration mechanism does not become a permanent requirement by default; each needs a stated end. |
| R18 | Look for substantial deletion, consolidation and simplification, not a redistribution of the present implementation over cleaner boundaries. Ask whether lanes, worktrees, consolidation and topology management are independently necessary, or whether their complexity comes from interactions between abstractions that could be removed together. Replacement of a subsystem is an acceptable recommendation where repair is worse. Both the delete-first and the consolidate-in-place perspectives are approved. |
| R19 | Wayfinder's requirements derive from the problems and remediation decisions found here. Its purpose is to help preserve architectural coherence and support deliberate evolution, not to preserve the existing architecture. |
| R20 | The outside observer has received the consolidated findings of the reconnaissance and has given an assessment. The prospective prediction control of the reconnaissance is abandoned due to disclosure. No retrospective predictions are reconstructed. |

## Vehicle

One Mission of the built-in `plan` type (`kitty-specs/architecture-recovery-assessment-01M8HPDM/`), advanced with `spec-kitty next`. A probe in a disposable clone showed that this type runs specify, research, plan, review to `done` with documented commands, its guards asking only for the step artefacts. Specialist work runs as profile-loaded subagents inside the Mission's steps. The Mission's `research.md` and `plan.md` index the documents in this folder.

## Deliverables

| # | Deliverable | File |
|---|---|---|
| 1 | Current capability and responsibility map | `01-capability-and-responsibility-map.md` |
| 2 | Essential versus accidental complexity | `02-essential-vs-accidental-complexity.md` |
| 3 | Catalogue of semantic duplication and competing mechanisms | `03-duplication-and-competing-mechanisms.md` |
| 4 | Candidate simplified architecture, with alternatives | `04-candidate-architecture.md` |
| 5 | Obstruction map | `05-obstruction-map.md` |
| 6 | Capability dispositions | `06-capability-dispositions.md` |
| 7 | Incremental remediation roadmap | `07-remediation-roadmap.md` |
| 8 | Architectural constraints and acceptance scenarios | `08-constraints-and-acceptance-scenarios.md` |
| 9 | Outstanding decisions for the architect | `09-open-decisions.md` |

Working material: `needs/`, `mechanisms/`, `duplication/`, `candidates/`, `challenge/`, `dispatch/` (the briefs), and `report/`.
