---
title: Architecture Audience
description: 'Architecture audience catalog: the canonical internal and external persona references for Spec Kitty, split by delivery-boundary membership for journeys and reviews.'
doc_status: active
updated: '2026-03-10'
related:
- context/audience/external
- context/audience/internal
---
# Architecture Audience

This directory captures architecture-level personas for Spec Kitty.
Personas are split into two groups:

- `internal/` for contributors and system actors inside the Spec Kitty delivery boundary.
- `external/` for stakeholders outside that boundary.

Use these persona documents as the canonical audience reference for:

- actor mapping in `docs/plans/user_journey/*.md`
- trade-off validation in architecture decisions
- communication and adoption planning for architecture changes

## Audience Groups

| Group | Scope | Index |
|---|---|---|
| Internal Audience | Contributors and runtime/system actors | [internal/index.md](internal/index.md) |
| External Audience | Stakeholders outside runtime boundary, including evaluators for adoption decisions | [external/index.md](external/index.md) |

## Conventions

1. Persona links used in actor tables must point to files under `docs/context/audience/internal/` or `docs/context/audience/external/`.
2. Personas are architecture artifacts, not user-marketing profiles.
3. Keep persona behavior aligned with active ADRs and user journeys.
