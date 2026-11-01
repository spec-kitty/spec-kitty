---
title: 'Tutorial: Governed Charter Workflow End-to-End'
description: A guided tour connecting charter setup, doctrine synthesis, a governed mission run, and the retrospective loop into one journey.
doc_status: active
updated: '2026-08-11'
audience:
- profile: external/project-owner
  guidance_text: Written for the Project Owner reader.
type: tutorial
related:
- context/charter-overview
- guides/how-to/governance/setup-governance
- guides/how-to/governance/run-governed-mission
- guides/how-to/governance/use-retrospective-learning
---
# Tutorial: Governed Charter Workflow End-to-End

> **Background**: If you're new to Charter, read [How Charter Works](../../context/charter-overview.md) first.

![Governed charter workflow - Mission Kitty splash](../../assets/images/charter-governed-workflow-mission-kitty.png)

_Stylized splash — the seal and stage board are decorative. Setup, governed run, and retrospective steps are in the linked how-tos below._

## What you'll build

By the end of this tutorial, you will have a project with Charter governance fully configured,
doctrine synthesized into a valid bundle, and at least one governed mission action run. This page
does not repeat the step-by-step commands for each stage — each stage already has its own
authoritative how-to. Instead, it connects them in the order you'll actually use them, so you
understand the complete operator flow: from a blank git repository to agents receiving consistent,
policy-backed context on every action.

> [!TIP]
> This page is a tour. Stage commands live in the linked how-tos: [setup governance](../how-to/governance/setup-governance.md), [run a governed mission](../how-to/governance/run-governed-mission.md), [retrospective learning](../how-to/governance/use-retrospective-learning.md).

---

## Stage 1: Set up governance

Initialize the project scaffold, run the Charter interview, generate the charter bundle, validate
it, and synthesize doctrine. This is the complete interview-to-generation flow, covered start to
finish in one place:

**→ [How to Set Up Project Governance](../how-to/governance/setup-governance.md)**

Work through that guide's Steps 1–4 before continuing. When `spec-kitty charter status` shows no
drift after synthesis, your governance is active and you're ready for Stage 2.

## Stage 2: Run a governed mission action

With governance set up and doctrine synthesized, create a mission (see
[Create a Specification](../how-to/missions/create-specification.md) if you don't have one yet — `spec-kitty
specify` returns a full `mission_slug`, which is what `spec-kitty next --mission` expects, not
just the short name) and drive it with `spec-kitty next`. Charter context is injected into every
mission-action prompt automatically — that's what "governed" means. The full command reference
(query mode vs. `--result`, reading the JSON output, composed steps, blocked decisions) lives in
its own guide:

**→ [How to Run a Governed Mission](../how-to/governance/run-governed-mission.md)**

## Stage 3: The retrospective record and summary

When a mission completes, Spec Kitty automatically authors a `retrospective.yaml` for that mission
under `.kittify/missions/<mission_id>/` — no configuration needed by default. Configuring
retrospective policy (blocking completion on a failed retrospective, opting out, applying
proposals back into governance) is its own operator workflow:

**→ [How to Use Retrospective Learning](../how-to/governance/use-retrospective-learning.md)**

---

## What's next

You've completed the full Charter governance loop. Here is where to go from here:

- [How to Set Up Project Governance](../how-to/governance/setup-governance.md) — the interview-to-generation how-to (Stage 1 above)
- [How to Synthesize and Maintain Doctrine](../how-to/governance/synthesize-doctrine.md) — partial resynthesis, provenance, recovery from stale bundles
- [How to Run a Governed Mission](../how-to/governance/run-governed-mission.md) — composed steps, prompt resolution, blocked decisions
- [How to Use Retrospective Learning](../how-to/governance/use-retrospective-learning.md) — preview and apply synthesis proposals
- [Troubleshooting Charter Failures](../how-to/governance/troubleshoot-charter.md) — fixes if any stage above fails
- [How Charter Works](../../context/charter-overview.md) — deeper conceptual background: synthesis, the DRG, and the bundle

---

## See also

- [How to Set Up Project Governance](../how-to/governance/setup-governance.md)
- [How to Synthesize and Maintain Doctrine](../how-to/governance/synthesize-doctrine.md)
- [How to Run a Governed Mission](../how-to/governance/run-governed-mission.md)
- [How Charter Works: Synthesis, DRG, and the Bundle](../../context/charter-overview.md)
