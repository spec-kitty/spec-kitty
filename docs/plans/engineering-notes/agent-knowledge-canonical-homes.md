---
title: 'Agent knowledge: canonical homes for rules, practices, reference, and learned facts'
description: "Where durable agent knowledge belongs — charter, doctrine, Common Docs, and the orphaned .kittify/memory store — and how to stop a per-agent memory duplicating the repo."
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/engineering-notes/index.md
- docs/context/orchestration.md
- src/charter/offering/skills/spec-kitty-charter-doctrine/references/doctrine-artifact-structure.md
---
# Agent knowledge: canonical homes for rules, practices, reference, and learned facts

**Origin (2026-07-22):** a profile-loaded research pass (researcher-robbie) investigating why a
per-agent "memory" store (a harness's per-user `memory/*.md` + index) keeps duplicating content
already tracked in the repo and repeatedly hits a size ceiling. This note is the durable record of
the finding and the recommended canonical solution, so a maintainer or agent does not re-derive it.

## The problem

An AI harness's per-user memory (learned facts: mission status, past fixes, code structure, gotchas)
is **not in the repo**, **not shared with the maintainer team**, and **Claude-specific**. It grows
without bound because it duplicates facts that already have a canonical git-backed home — mission
status lives in `status.events.jsonl`, code structure lives in the code, past fixes live in git and
ADRs. The size ceiling is a symptom of duplication, not of insufficient memory.

## The four kinds of agent knowledge already have canonical homes

The architecture already separates knowledge by kind; the per-user store's failure is conflating all
four into one un-shared bucket.

| Kind | Canonical home | How an agent reads it | Team-shared + harness-neutral |
|------|----------------|-----------------------|-------------------------------|
| **Rules** (what must/must-not be true) | charter (`.kittify/charter/charter.yaml`) | `spec-kitty charter context --action <name> --json` | ✅ git-tracked |
| **How-to-work** (practices, gotchas, techniques) | **doctrine** (directives / tactics / styleguides / toolguides / paradigms), DRG-scoped | `charter context --json` + `DoctrineService`; profile-load skills | ✅ |
| **Reference** (explanatory prose) | Common Docs (`docs/`) + generated page-inventory | today: ad-hoc file reads — **no query API** | ✅ git, but no retrieval surface |
| **Learned facts** (mission status, decisions, gotchas) | **`.kittify/memory/`** (git-tracked, worktree-shared) | flat-file reads | ✅ |

**Load-bearing insight:** a per-user memory collapses all four rows into one Claude-only store. The
fix is not a better memory system — it is to route each kind to its existing canonical home and stop
copying repo-tracked facts into a per-agent duplicate.

## The `.kittify/memory/` verdict: live infrastructure, orphaned from its cargo

`.kittify/memory/` is not folklore. Lineage:

- Forked GitHub spec-kit kept the constitution at `memory/constitution.md`; commit `d71a6a0d9`
  ("Move memory/ to .kittify/") relocated it under `.kittify/`.
- The `constitution → charter` rename (`src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py`,
  epic #390) moved the **payload** to `.kittify/charter/charter.md` — but left the directory behind.
- The directory is **still git-tracked and still worktree-broadcast**: `src/specify_cli/core/worktree.py`
  symlinks each worktree's `.kittify/memory` to the main repo's (file-copy fallback on Windows) and
  excludes it from the worktree's git, so every Mission branch shares one `.kittify/memory`.
  `src/charter/offering/templates/AGENTS.md` still documents it as a single source of truth for project
  principles — and the `worktree.py` rationale comment still says "share the same charter", which is
  now stale (the charter moved to `.kittify/charter/`).
- It today holds an **uncurated grab-bag** (a session tooling record, an architect-review artifact,
  a toolguide) — "infrastructure that outlived its cargo." This is the team-shared, harness-neutral,
  git-backed learned-facts store the problem needs; it simply lost its curator.

## Retrieval-endpoint feasibility (the Common Docs gap)

A hosted REST/GraphQL doc/doctrine/DRG API does **not** exist, but the substrate is ~60-70% built:

- **Doctrine / charter / glossary retrieval is effectively already an endpoint** — `charter context
  --action --json`, `DoctrineService`, `doctrine.drg.query.resolve_context`, and
  `spec-kitty glossary … --json` deliver pre-generated, action-scoped, token-budgeted, freshness-gated
  retrieval. For the *how-to-work* half, no new build is needed.
- **Common Docs retrieval is the real gap (~40% exists).** The metadata spine is done — validated
  per-page frontmatter + a generated, CI-drift-gated page-inventory
  (`scripts/docs/inventory_lockfile.py` → `docs/development/page-inventory.yaml`) — but there is
  **no title / heading-anchor / body index and no query surface**. The glossary
  (`src/glossary/store.py`, `spec-kitty glossary … --json`) is the proven queryable-index model to
  mirror. A loopback dashboard already serves `GET /api/charter` and `/api/glossary-terms`
  (`src/specify_cli/dashboard/server.py`), and the dossier `DossierAPIHandler`
  (`src/specify_cli/dossier/api.py`) was written "in anticipation of a future FastAPI port (T033)".

## Recommendation: a two-move convention plus one incremental build

1. **Facts → `.kittify/memory/`.** Rehabilitate the orphaned directory as the curated, git-backed,
   harness-neutral team-memory store with a light convention (an index + per-topic notes; no PII;
   de-duplicated against the repo's single-sources-of-truth). A per-agent memory then shrinks to
   *pointers into it*, killing the size ceiling. Correct the stale `worktree.py` / `AGENTS.md`
   "charter" references. Near-zero new infrastructure — already shared and wired.
2. **Practices → doctrine.** Anything an agent should "just know before working here" that is a
   *practice* becomes a **toolguide / tactic** (precedent: `toolguides/built-in/EFFICIENT_LOCAL_TOOLING.md`),
   instantly served action-scoped by `charter context --json`. The retrieval endpoint already exists
   for this half.
3. **Reference retrieval → a `spec-kitty docs query --json` CLI over a generated index** (the missing
   Common Docs half). Extend the page-inventory generator to also emit title + heading-anchor +
   short-abstract, and expose a glossary-shaped query command; defer any REST/GraphQL server (the
   dossier FastAPI port remains the later HTTP option). Reuses proven substrate rather than a
   green-field service.

**Net:** don't build a new memory system — stop duplicating into a per-user one, route each kind to
its existing canonical home, and add one modest CLI build to close the Common Docs retrieval gap.

## Key evidence paths

`src/specify_cli/core/worktree.py`, `src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py`,
`src/charter/offering/templates/AGENTS.md`, `.kittify/memory/`, `src/charter/activation/context.py`,
`src/charter/offering/service.py`, `src/charter/offering/drg/query.py`, `scripts/docs/inventory_lockfile.py`,
`docs/development/page-inventory.yaml`, `src/glossary/store.py`,
`src/specify_cli/dossier/api.py`, `src/specify_cli/dashboard/server.py`.
