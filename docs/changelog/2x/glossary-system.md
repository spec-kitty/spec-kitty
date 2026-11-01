---
title: 2.x Glossary System
description: Historical Spec Kitty 2.x archive page for 2.x Glossary System; use Spec Kitty 3.2 docs for current Charter-era workflows.
doc_status: deprecated
updated: '2026-06-03T00:00:00Z'
related:
- docs/context/index.md
kind: Changelog
---
> Archive notice: This page documents historical Spec Kitty behavior and is not the current 3.2 workflow. Start with [Spec Kitty 3.2](../../context/index.md) for current docs.

# 2.x Glossary System

The glossary keeps terminology consistent across all mission artifacts. Every term that matters to your project -- from framework concepts like "lane" and "work package" to domain-specific jargon like "deployment" -- lives in the glossary with a precise definition, a scope, and a status. When the runtime detects a term used inconsistently in an artifact, it can flag or block generation until you resolve the inconsistency.

In 2.x the glossary is a living system: terms are added, curated, promoted, and deprecated over the lifecycle of a project. The system is designed so that agents and humans share the same vocabulary.

## Glossary Structure

2.x glossary content is organized by context domain:

1. `glossary/README.md` -- overview and conventions
2. `docs/context/*.md` -- domain-specific term files

Current domains include execution, orchestration, governance, identity, doctrine, dossier, lexical, system-events, and technology-foundations.

## The 4 Scopes

Terms are organized into four scopes. When the same surface form exists in multiple scopes, the narrowest scope wins:

| Precedence | Scope | Use For |
|:---:|---|---|
| 0 (highest) | `mission_local` | Feature-specific jargon (e.g., "widget" = a specific UI component in this feature) |
| 1 | `team_domain` | Team or organization conventions (e.g., "sprint" = a 2-week iteration) |
| 2 | `audience_domain` | Industry or domain standards (e.g., "deployment" in DevOps) |
| 3 (lowest) | `spec_kitty_core` | Framework terms like "lane", "work package", "mission" |

If `deployment` is defined in both `team_domain` and `audience_domain`, the `team_domain` definition takes precedence during conflict resolution.

## Term Lifecycle

Every term follows a three-state lifecycle:

```
draft  -->  active  -->  deprecated
  ^                          |
  +--------------------------+
         (re-draft)
```

- **draft** -- newly added or auto-extracted, not yet reviewed by a human
- **active** -- promoted by a human, used in conflict resolution
- **deprecated** -- retired from active resolution but preserved in event history

New terms are added as `draft`. Promotion to `active` is controlled by Human-in-Charge governance. Deprecated terms are excluded from conflict resolution but remain in the glossary for audit purposes.

## Strictness Modes

The glossary runtime supports three enforcement levels:

| Mode | Behavior |
|------|----------|
| `off` | Glossary checks are disabled entirely |
| `medium` | Only HIGH severity conflicts block generation |
| `max` | Any unresolved conflict blocks generation |

Strictness is configured per-project in `.kittify/config.yaml` or via the charter interview. The default is `medium`.

## Conflict Resolution

When the same surface form is defined differently in two scopes, or when an artifact uses a term inconsistently with the glossary, the system records a **conflict**. Conflicts have an ID, a description of the inconsistency, and a resolution status.

Resolving a conflict is a human decision: you choose which definition wins, or you update the artifact to match the glossary. Once resolved, the conflict is closed and excluded from future checks.

## CLI Commands

| Command | Purpose |
|---------|---------|
| `spec-kitty glossary list` | List all terms across all scopes |
| `spec-kitty glossary list --scope <scope>` | Filter terms by scope |
| `spec-kitty glossary list --status <status>` | Filter terms by status (draft, active, deprecated) |
| `spec-kitty glossary list --json` | Machine-readable JSON output |
| `spec-kitty glossary conflicts` | Show all conflict history |
| `spec-kitty glossary conflicts --unresolved` | Show only unresolved conflicts |
| `spec-kitty glossary resolve <conflict-id>` | Resolve a conflict interactively |

## Runtime Integration

Glossary checks are integrated into mission primitive execution via:

1. `src/doctrine/missions/glossary_hook.py` -- hook that runs during artifact generation
2. `src/doctrine/missions/primitives.py` -- primitive execution with glossary context
3. Compatibility import path: `src/specify_cli/missions/glossary_hook.py`

Hook behavior is metadata/config driven with enabled-by-default semantics.

Doctrine artifacts for glossary curation:

1. `src/doctrine/tactics/glossary-curation-interview.tactic.yaml`
2. `src/doctrine/styleguides/writing/kitty-glossary-writing.styleguide.yaml`

## Validation Coverage

1. Link/anchor integrity for context docs: `tests/doctrine/test_glossary_link_integrity.py`
2. Glossary hook behavior: `tests/doctrine/missions/test_glossary_hook.py`
3. Primitive context strictness/enablement behavior: `tests/doctrine/missions/test_primitives.py`

---

## Learn More

- **Step-by-step management**: [How to Manage the Glossary](../../guides/how-to/governance/manage-glossary.md) -- listing terms, resolving conflicts, editing seed files, configuring strictness
- **Spec-driven development**: [Spec-Driven Development Explained](../../architecture/spec-driven-development.md) -- how the glossary fits into the broader specification workflow
- **CLI reference**: [CLI Commands Reference](../../api/cli-commands.md) -- complete `glossary` subcommand details
