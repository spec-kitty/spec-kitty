---
title: 'Agent Profiles'
description: Catalog of the 18 built-in agent profiles Spec Kitty ships, with identity, routing, and role for each.
doc_status: active
updated: '2026-10-08'
type: reference
audience: docs/context/audience/internal/lead-developer.md
related:
- docs/api/agent_profiles/architect-alphonso.md
- docs/api/agent_profiles/curator-carla.md
- docs/api/agent_profiles/debugger-debbie.md
- docs/api/agent_profiles/designer-dagmar.md
- docs/api/agent_profiles/doctrine-daphne.md
- docs/api/agent_profiles/frontend-freddy.md
- docs/api/agent_profiles/generic-agent.md
- docs/api/agent_profiles/human-in-charge.md
- docs/api/agent_profiles/implementer-ivan.md
- docs/api/agent_profiles/java-jenny.md
- docs/api/agent_profiles/node-norris.md
- docs/api/agent_profiles/paula-patterns.md
- docs/api/agent_profiles/planner-priti.md
- docs/api/agent_profiles/python-pedro.md
- docs/api/agent_profiles/randy-reducer.md
- docs/api/agent_profiles/researcher-robbie.md
- docs/api/agent_profiles/retrospective-facilitator.md
- docs/api/agent_profiles/reviewer-renata.md
- docs/api/index.md
- docs/context/identity.md
---
# Agent Profiles

This page catalogs the 18 built-in agent profiles shipped in
`packs/built-in/agent_profiles/`. A profile governs identity, routing,
and boundaries for a work package: the runtime assigns profiles to work
packages automatically, and you can also load one on demand for an
interactive session with the [`spk-charter-profile-load`
skill](../skills/spk-charter-profile-load.md). Two entries — `generic-agent`
and `human-in-charge` — are structurally different from the other 16; see
their own pages for what that means.

| Profile ID | Name | Roles | Routing Priority | Purpose |
|---|---|---|---|---|
| [architect-alphonso](architect-alphonso.md) | Architect Alphonso | architect | 50 | Designs and validates system architectures for scalability, maintainability, and correctness. |
| [curator-carla](curator-carla.md) | Curator Carla | curator | 40 | Maintains knowledge base, charter offering layers, and documentation consistency. |
| [debugger-debbie](debugger-debbie.md) | Debugger Debbie | investigator, reviewer | 60 | Investigates recurring or stubborn bugs via a five-paradigm parallel debugging swarm. |
| [designer-dagmar](designer-dagmar.md) | Designer Dagmar | designer | 50 | Creates accessible, consistent UX/UI designs and interaction specifications. |
| [doctrine-daphne](doctrine-daphne.md) | Doctrine Daphne | curator, onboarding-guide | 48 | Onboards externally-built agents into validated Charter Pack artifacts. |
| [frontend-freddy](frontend-freddy.md) | Frontend Freddy | implementer | 80 | Implements browser-side components, layouts, and accessible frontend code. |
| [generic-agent](generic-agent.md) | Generic Agent | implementer | 10 | Executes work packages under baseline governance (— default fallback). |
| [human-in-charge](human-in-charge.md) | Human in Charge | human-in-charge | 100 | Marks a work package for direct human execution (— sentinel, not a persona). |
| [implementer-ivan](implementer-ivan.md) | Implementer Ivan | implementer | 50 | Implements features, fixes bugs, and writes tests to specification. |
| [java-jenny](java-jenny.md) | Java Jenny | implementer | 80 | Delivers idiomatic, tested Java code under ATDD/TDD and the Maven quality gate. |
| [node-norris](node-norris.md) | Node Norris | implementer | 80 | Implements Node.js HTTP APIs and server-side services with async discipline. |
| [paula-patterns](paula-patterns.md) | Paula Patterns | architecture-scout, architect, reviewer | 65 | Reviews recurring architecture failures via five-scout dispatch and synthesis. |
| [planner-priti](planner-priti.md) | Planner Priti | planner | 50 | Decomposes missions into sequenced, dependency-mapped work packages. |
| [python-pedro](python-pedro.md) | Python Pedro | implementer | 80 | Delivers idiomatic, type-safe Python under TDD and the pytest/ruff/mypy gate. |
| [randy-reducer](randy-reducer.md) | Randy Reducer | implementer, refactorer, reviewer | 70 | Performs behavior-preserving semantic compression of implementation size. |
| [researcher-robbie](researcher-robbie.md) | Researcher Robbie | researcher | 40 | Investigates unknowns and synthesizes research to inform decisions. |
| [retrospective-facilitator](retrospective-facilitator.md) | Retrospective Facilitator | facilitator | 60 | Facilitates structured mission retrospectives at mission terminus. |
| [reviewer-renata](reviewer-renata.md) | Reviewer Renata | reviewer | 50 | Evaluates code and designs for correctness, quality, security, and standards. |
