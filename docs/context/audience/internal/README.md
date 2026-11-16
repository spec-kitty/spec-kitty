---
title: Internal Audience Personas
description: 'Index of the internal-audience personas: contributors and system actors inside the Spec Kitty delivery boundary, their concerns, and the pages to write for them.'
doc_status: active
kind: Hub
updated: '2026-11-13T00:00:00Z'
audience:
- profile: internal/maintainer
  guidance_text: Keep this index in step with the profiles it lists.
- profile: internal/ai-collaboration-agent
  guidance_text: Use this index to pick the reader a page is written for.
related:
- context/audience/internal/ai-collaboration-agent
- context/audience/internal/lead-developer
- context/audience/internal/maintainer
- context/audience/internal/project-codebase
- context/audience/internal/spec-kitty-cli-runtime
- context/audience/internal/system-architect
---
# Internal Audience Personas

These personas represent contributors and system actors inside the Spec Kitty delivery
boundary. The three `human` personas and the `llm` AI Collaboration Agent are readers:
people and agents read the pages written for them. The two `system` personas, the CLI
runtime and the project codebase, are actors whose behavior a page must match; no page
names either as its reader today.

## Index

| Persona | Type | Primary Concern | Name it for |
|---|---|---|---|
| [System Architect](system-architect.md) | `human` | Coherent boundaries and explicit trade-offs | Architecture pages, ADR-backed explanations and glossary pages about boundaries |
| [Lead Developer](lead-developer.md) | `human` | Practical implementation guidance and maintainability | Development how-tos, configuration and reference pages contributors work from |
| [Maintainer](maintainer.md) | `human` | Sustainable governance and predictable operations | Governance, charter, release and CI pages |
| [AI Collaboration Agent](ai-collaboration-agent.md) | `llm` | Clear constraints, deterministic instructions, traceable outputs | Pages agents follow while working: command contracts, terminology and footgun disambiguations |
| [Spec Kitty CLI Runtime](spec-kitty-cli-runtime.md) | `system` | Deterministic orchestration and policy enforcement | Rarely the reader; use it when a page specifies behavior the runtime must enforce |
| [Project Codebase](project-codebase.md) | `system` | Structural consistency and low-friction evolution | Rarely the reader; use it when a page records constraints the code must keep |
