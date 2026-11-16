---
title: Architecture Audience
description: 'Audience catalog: the eleven internal and external reader profiles a Spec Kitty doc page names in its audience frontmatter, and how to choose one.'
doc_status: active
kind: Hub
updated: '2026-11-16T00:00:00Z'
audience:
- profile: internal/maintainer
  guidance_text: Keep the catalog and its conventions current.
- profile: internal/ai-collaboration-agent
  guidance_text: Pick the reader for a page from this catalog before drafting it.
related:
- context/audience/external
- context/audience/internal
---
# Architecture Audience

This directory holds the reader profiles for Spec Kitty documentation. A doc page names
the reader it is written for by choosing one of these profiles. The field is required on
every page a change touches; pages no change has touched since may still name none. The
profiles are split into two groups:

- `internal/` for contributors and system actors inside the Spec Kitty delivery boundary.
- `external/` for stakeholders outside that boundary.

## Naming a page's reader

A page names its reader in its `audience:` frontmatter. Each entry names a profile by its
path under this directory, without `.md`, and says in one line what that reader uses the
page for:

```yaml
audience:
- profile: internal/lead-developer
  guidance_text: Written for contributors who configure a project.
```

`scripts/docs/audience_resolver.py` checks that every `internal/...` or `external/...`
profile names a page in this directory. Choose from this catalog rather than inventing a
reader: directive 047 (Audience-Oriented Writing) asks every page to name its reader, and
directive 042 (Common Docs) and the `common-docs` styleguide point that field at the
profiles in this directory. The `writing-audience-catalog` tactic covers a different
library, the general writing personas in the built-in pack's `assets/audiences/`.

As a house convention (not a doctrine rule), name one primary reader and add a second
entry only when the page serves two readers.

## Audience Groups

| Group | Scope | Index |
|---|---|---|
| Internal Audience | Contributors and runtime/system actors | [Internal audience personas](internal/README.md) |
| External Audience | Stakeholders outside the delivery boundary, including evaluators deciding on adoption | [External audience personas](external/README.md) |

| Profile | Name it when the page is for |
|---|---|
| [`external/practitioner`](external/practitioner.md) | someone who installs the CLI and runs Missions day to day (tutorials and task how-tos) |
| [`external/project-owner`](external/project-owner.md) | someone who sets project intent and approves scope |
| [`external/tech-lead-evaluator`](external/tech-lead-evaluator.md) | an engineering lead judging whether the workflow fits their team |
| [`external/architect-evaluator`](external/architect-evaluator.md) | an architect judging governance and boundary fitness |
| [`external/product-manager-evaluator`](external/product-manager-evaluator.md) | a product manager judging how intent reaches delivery |
| [`internal/system-architect`](internal/system-architect.md) | a contributor who designs boundaries and writes ADRs |
| [`internal/lead-developer`](internal/lead-developer.md) | a contributor who implements and configures |
| [`internal/maintainer`](internal/maintainer.md) | a contributor who keeps governance, CI and releases running |
| [`internal/ai-collaboration-agent`](internal/ai-collaboration-agent.md) | an agent that follows the page while working |
| [`internal/spec-kitty-cli-runtime`](internal/spec-kitty-cli-runtime.md) | the runtime behavior a page specifies (rare) |
| [`internal/project-codebase`](internal/project-codebase.md) | the constraints the code must keep (rare) |

## Conventions

1. Persona links used in actor tables must point to files under `docs/context/audience/internal/` or `docs/context/audience/external/`.
2. Personas are architecture artifacts, not user-marketing profiles.
3. Keep persona behavior aligned with active ADRs and the current CLI.
4. Adding or removing a profile needs an operator ruling; propose it rather than editing the catalog.
