---
title: External Audience Personas
description: 'Index of the external-audience personas: stakeholders outside the Spec Kitty delivery boundary, with their actor type, primary concern, and the pages to write for them.'
doc_status: active
kind: Hub
updated: '2026-11-16T00:00:00Z'
audience:
- profile: internal/maintainer
  guidance_text: Keep this index in step with the profiles it lists.
- profile: internal/ai-collaboration-agent
  guidance_text: Use this index to pick the reader a page is written for.
related:
- context/audience/external/architect-evaluator
- context/audience/external/practitioner
- context/audience/external/product-manager-evaluator
- context/audience/external/project-owner
- context/audience/external/tech-lead-evaluator
---
# External Audience Personas

These personas represent stakeholders outside the Spec Kitty delivery boundary: people
who decide whether to adopt Spec Kitty, who own the outcome a Mission delivers, or who
run the CLI day to day.

## Index

| Persona | Type | Primary Concern | Name it for |
|---|---|---|---|
| [Practitioner](practitioner.md) | `human` | Running Missions with the CLI day to day, and recovering when a command refuses | Tutorials and task how-tos: installing, running a Mission, reviewing, consolidating, recovering |
| [Project Owner](project-owner.md) | `human` | Fast onboarding and clear governance defaults | Getting-started pages and the governance defaults an owner sets or approves |
| [External Tech Lead Evaluator](tech-lead-evaluator.md) | `human` | Adoption fit for engineering delivery workflows and quality gates | Workflow how-tos and pages that explain the Mission lifecycle, review and branch handling |
| [External Architect Evaluator](architect-evaluator.md) | `human` | Long-term architecture governance fitness and boundary clarity | Architecture overviews, ADR summaries and boundary explanations |
| [External Product Manager Evaluator](product-manager-evaluator.md) | `human` | Intent-to-delivery alignment and decision accountability | Pages about specs, checkpoints and how intent is carried into delivery |

Tutorials and task how-tos should name `external/practitioner`: it is the reader who
installs Spec Kitty and runs Missions (operator ruling 2026-11-16). Retargeting the
existing guide pages is tracked in #7523.
