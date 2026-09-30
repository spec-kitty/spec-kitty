---
title: WP & Op Schema Model — Formalising Work-Package and Op Records
description: 'Idea + grounding to formalise WP files and the Op record via code-owned models/schemas; the model is ~60-70% already shipped, so the win is a narrow hash/field-eviction fix.'
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
---
# WP & Op Schema Model

> **Status update (2026-09-30).** Parked idea, written against the 3.2.x milestone. The 3.x line has closed and 3.3.x was retired, so any "deferred to 3.3.x" routing below needs re-triage. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

| Field | Value |
|---|---|
| Date | 2026-07-16 |
| Stage | Idea — pending research grounding |
| Author | Operator (via Spec Kitty session `SK_DESIGN`) |
| Branch | `design/wp-op-schema-model` (isolated worktree) |
| Grounds against | model-first doctrine schema precedent, degodding roadmap, mission-type→doctrine migration, Op record schema v2 |
| Related | [model-first-schema-generation.md](model-first-schema-generation.md), `src/specify_cli/invocation/record.py`, `src/specify_cli/core/wps_manifest.py`, `src/specify_cli/task_metadata_validation.py` |

> **This is an idea note, not a decision.** It captures intent verbatim from the
> originating session and frames the research questions. It is deliberately
> unresolved on trade-offs; the accompanying research squad grounds it against
> the code as-is, the roadmap/vision, and the existing ADRs before any
> spec/plan work is contemplated.

---

## The itch

Recent and in-flight roadmap movement — **degodding** (god-module decomposition),
**`specify_cli` cleanup**, and **moving mission-type configuration into doctrine** —
has surfaced that the current representation of **Work-Package (WP) files** is
lacklustre. Today a WP is a **markdown file with a YAML frontmatter block**
(`kitty-specs/<mission>/tasks/WP##.md`): structured metadata up top, free-prose
body below.

Observed pain points with that format:

1. **Hash / content-address mismatch churn.** Minor, semantically-inert edits
   (e.g. flipping a task to complete) shift content and trip
   hashcode-mismatch warnings/errors. The content-address machinery treats the
   whole file as one opaque blob, so bookkeeping mutations are indistinguishable
   from substantive ones.
2. **Context sizing / retrieval friction.** The prose-heavy body is expensive to
   load and hard to slice; there is no clean way to pull "just the scope" or
   "just the acceptance criteria" without parsing free text.
3. **Inconsistencies.** Free-form bodies drift in structure across missions;
   there is no enforced shape, so downstream tooling parses defensively.
4. **Duplicated information.** The same facts live in **both** the frontmatter
   metadata **and** the body prose (title, anchors, requirement refs, scope
   headings), and the two can diverge.

## The idea

With WP **prompt templates** shifting into **doctrine elements** (the
mission-type→doctrine migration), this is an opportune moment to revamp the WP
representation into a **formal schema format**:

- A **code-owned logical model** (Pydantic, matching the existing model-first
  doctrine-schema pattern) is the **single source of truth** for a WP's shape.
- A **schema** + **schema checks** validate WP records — no hand-authored,
  drift-prone structure.
- These models live inside the code logic and are used to **create, update, and
  process** WP records (not re-parsed ad hoc at each call site).
- On disk, records still **render to markdown** for human readability and
  dashboard display — but the **authoritative representation is structured**
  (YAML / model), and the markdown is a **derived view**, not the source.

The distinction that unblocks the hash-churn problem: separate **semantic
content** (scope, requirements, acceptance) from **mutable bookkeeping** (lane,
task-complete flags, history) so a status flip does not perturb the
content-addressed identity of the semantic record.

## Extension: Op records should carry "why & what", not just "something was done"

The same logical-model + schema approach applies to the **Op run-type** (ad-hoc
dispatch / `profile-invocation`). Today an Op record
(`src/specify_cli/invocation/record.py`, schema v2) captures the **facts of an
invocation** — `request_text`, `action`, `mode_of_work`, `outcome`, `closed_by`
— i.e. *that* something was dispatched and *how* it closed. It does **not**
persist a structured account of the **why and what** — the scope the Op set for
itself, the intent, the change surface, the reasoning. It stores that something
was done, not what was undertaken and to what end.

This is **incongruent with Spec Kitty's core vision** (specifications ahead of
implementation; traceability from intent to artefact) and it **blurs the line
between `ad-hoc` and `op`**: if an Op leaves no more trace of intent than a raw
ad-hoc action, the governance overhead buys little.

Applying the **same schema model** to Op scope would let an Op carry a
lightweight, structured **intent + scope + outcome** record — a "small WP for a
non-mission action" — restoring the traceability that distinguishes a governed
Op from an ungoverned ad-hoc edit.

## Why now (timing)

- **WP templates → doctrine.** The prompt templates that shape WP files are
  being lifted into doctrine artefacts; changing the *representation* at the
  same moment avoids a second disruptive migration later.
- **Degodding / `specify_cli` cleanup.** Numerous call sites parse WP frontmatter
  and bodies today (`wps_manifest.py`, `task_metadata_validation.py`,
  `status/*`, `dependency_parser.py`, …). A single code-owned model is exactly
  the kind of consolidation the degodding roadmap favours (one authority, ports
  over scattered parsing).
- **Precedent exists.** [Model-first schema generation](model-first-schema-generation.md)
  already made **Pydantic models the single source of truth for all 10 doctrine
  YAML schemas**, with `scripts/generate_schemas.py --check` as a drift gate.
  This idea extends that proven pattern from *doctrine* artefacts to *execution*
  (WP) and *op* artefacts.

## Explicitly out of scope for the idea (for the squad to confirm/deny)

- A specific migration mechanism or backwards-compat window.
- Whether markdown remains round-trippable or becomes strictly one-way (derived).
- The exact content-address boundary (what counts as semantic vs bookkeeping).
- Any commitment to a version number or milestone.

## Research questions to ground this

1. **Code as-is.** Where and how are WP files created, mutated, hashed, and
   parsed today? Enumerate the call sites and the current content-address /
   hash-mismatch machinery. What does the frontmatter↔body duplication actually
   cost? How does the Op record (schema v2) store intent today, and what is
   genuinely missing vs. the WP shape?
2. **Roadmap / vision alignment.** Does this fit the degodding, `specify_cli`
   cleanup, and mission-type→doctrine directions — or does it collide with
   in-flight work (e.g. runtime/state overhaul #1619, infra-logic separation
   #2173, doctrine extensibility)? Is now genuinely the right seam?
3. **ADR / precedent.** Which existing ADRs bind here (doctrine-layer merge
   semantics, shared-package boundary, model-first schema generation, status
   append-only event model)? Does the append-only status event log already solve
   the "bookkeeping churn" half, meaning the WP file only needs to shed its
   mutable fields rather than adopt a new store?
4. **Feasibility & risk.** Is a structured-authoritative / markdown-derived split
   realistic given human-editing workflows and the many agents that read WP
   files? What breaks? What is the smallest first slice that de-risks the rest?

---

# Research Synthesis (2026-07-16)

A three-lens research squad grounded the idea against the code as-is
(architect-alphonso), the roadmap/vision + ADRs (researcher-robbie), and
architectural feasibility / whack-a-field risk (paula-patterns). **All three
converged independently.** Verbatim reports are archived alongside this note;
the synthesis:

## What the idea gets right (confirmed)

- **The parse-surface sprawl is real and worse than stated.** There are
  **5 distinct frontmatter parsers** (`frontmatter.py:327`,
  `template/renderer.py:23`, `task_utils/support.py:191` regex-scraper,
  `manifest.py:68`, `doc_analysis/gap_analysis.py:83`) and **2 typed WP models**
  (`status/wp_metadata.py:183` `WPMetadata`; `task_utils/support.py:269`
  `WorkPackage`, a raw-string regex scraper), across **~49 consumer modules**.
  Consolidation onto one model is a genuine degodding-shaped win.
- **The hash-churn pain is confirmed exactly.** The mission **dossier** hashes
  the **whole WP file as opaque bytes** (`dossier/hasher.py:14`), feeds every
  `wp*.md` into a parity hash (`dossier/indexer.py:242`,
  `dossier/snapshot.py`), so *any* inert edit — a subtask checkbox flip, a
  `history` append — trips drift. Sync's `body_upload.py:52,116,121`
  whole-file-hashes the same files (`content_hash_mismatch` guard).
- **The Op intent/scope gap is real.** `OpStartedEvent`/`OpCompletedEvent`
  (`invocation/record.py:39,65`) persist `request_text` + `action` + `outcome`
  but no structured **scope / change-surface / reasoning / done-criteria**.
  Governance context is stored as a *hash*, not readable content. A contract
  already exists to extend: `contracts/op-record-events.md`.
- **The model-first machinery is proven and reusable.** `scripts/generate_schemas.py`
  (10 doctrine schemas, `--check` drift gate) can register `WPMetadata` / the Op
  models mechanically cheaply.

## What the idea gets wrong / over-scopes (the decisive findings)

1. **The "code-owned model" is ~60–70% already shipped.** `WPMetadata` is
   *already* a frozen Pydantic v2 model, `extra="forbid"`, ~40 typed fields, and
   *already the read authority* for 23 modules. The idea proposes building what
   largely exists. It needs **electing** (make `WP_FIELD_ORDER` and
   `WorkPackageEntry` *derive* from `WPMetadata`), not inventing.
2. **"Bookkeeping churn needs a new store" is half-false.** Lane/review status
   was *already evicted* from the file into the append-only `status.events.jsonl`
   model (`frontmatter.py:47-49` comment; `status/reducer.py`); the residual
   lane-in-frontmatter code is stamped **MIGRATION-ONLY**
   (`task_metadata_validation.py:82,181`). The bookkeeping/semantic split the
   idea calls its key unblock **is already the shipped architecture** for the
   fields that churned most. Only `history` + `shell_pid`/`shell_pid_created_at`
   + prose-body edits still perturb the hash.
3. **The WP *body* cannot be one-way-derived.** The body IS the agent's work
   order and is authored by humans *and* agents; the dashboard renders it
   verbatim and even reads the card title from a body regex in preference to
   frontmatter (`dashboard/scanner.py:895,950,976`). Only the **index**
   (`tasks.md`) is safely derived — and *that already is*, generated one-way
   from `wps.yaml` (`core/wps_manifest.py:170,184`). "Markdown becomes a derived
   view" is undercut on contact unless it splits *index* from *prompt body*.
4. **The structured-authoritative precedent already exists and stalled.**
   `wps.yaml` (code-owned Pydantic + YAML + generated markdown) reached only
   **5 of 278 missions**. The blocker was never the model — it was authority
   migration and human/agent editing workflow. Any future "YAML authoritative"
   push must first answer *why `wps.yaml` didn't win*.
5. **Whack-a-field risk.** Dropping a new `WPRecord` "single source of truth"
   next to the existing three field lists (`frontmatter.py:49`,
   `wps_manifest.py:16`, `wp_metadata.py:197` — which already drift, held in sync
   by a hand-maintained comment tax) makes **four** authorities, not one. The
   prerequisite is unifying the existing three *first*.

## Prior art — this ground is largely already owned

- **#2093 / #2400 (WP-metadata authority split)** — *already adjudicated*
  (REWORK-staged). It decided the semantic-vs-bookkeeping split **the opposite
  way on authority**: static design-intent **stays frontmatter-canonical**;
  dynamic runtime state (`agent`/`shell_pid`/`history`/reviews) retires to the
  event log. This must be **reconciled with, not re-litigated**.
- **ADR 2026-06-11-1 + epic #1804 (Op as first-class artifact)** — owns the Op
  record shape and its enrichment, C-005 **no-parallel-primitive**. An Op
  intent/scope field belongs here as a field extension; a separate
  "small-WP-for-an-Op" primitive would re-open the exact divergence the ADR
  closes. Must also respect `MinimalViableTrailPolicy` (`record.py:128`) — scope
  is **opt-in Tier-2**, not mandatory.
- **ADR 2026-06-06-1 + `wps.yaml`** — already a structured, `extra="forbid"`
  machine-readable WP manifest. **ADR 2026-06-07-1 / status event model** — lane
  already event-owned. The "no code-owned model exists" premise is only half
  true.

## Sequencing — this is a downstream consumer, not a peer of the current wave

The 3.2.x milestone posture is explicitly **"no new shadow paths / adopt don't
build."** This idea is a *consumer* of #1868 (seam-binding), #2173 (ports),
#1797 (degod), and #2468's keystone #2467 — it belongs **behind** them, ideally
expressed *as* a #2173-style port over WP/Op parsing. Critically, **#1619
(runtime/state overhaul) is actively re-cutting the WP/Mission/MissionRun
aggregate model** (its domain dialectic is unsettled — refutations at the
consolidation gate); formalising a WP logical model now front-runs a domain map
mid-revision.

## Disposition — **document, narrow, re-parent. Not "spec now."**

The instinct (code-owned models + model-first schemas) is the house style and
on-direction, but the note as written is deflated: its two headline
justifications are already owned, one decided the opposite way on authority.
Recommended path, smallest-blast-radius first:

| # | Slice | Owner / parent | Risk |
|---|-------|----------------|------|
| **0** | **Tidy-first:** unify the 3 field lists — make `WP_FIELD_ORDER` + `WorkPackageEntry` derive from `WPMetadata`; register `WPMetadata` in `generate_schemas.py`. Pure debt, no behaviour change. | degod / #1797 lineage | low |
| **1** | **Semantic-only content-address:** hash a normalized `WPMetadata` projection (drop `history`/`shell_pid*`, normalize body) instead of raw bytes in `dossier/{hasher,indexer}.py` + `sync/body_upload.py`. **Kills the hash-churn pain with no authority migration, no markdown rewrite.** Highest signal. | dossier / sync | low–med |
| **2** | Retire the `WorkPackage` regex scraper (`task_utils/support.py:269`) onto `WPMetadata`. | degod | low |
| **3** | **Independent:** add an *optional* structured `scope`/`intent` field to `OpStartedEvent`, respecting `MinimalViableTrailPolicy`. Do **not** bundle with WP work. | ADR 2026-06-11-1 / **#1804** | low |
| **X** | Full "YAML authoritative, markdown-body derived." | **Deferred** — needs `wps.yaml` post-mortem + #1619 aggregate boundaries settled + #2093/#2400 reconciliation. | high |

**Reconcile-before-spec, in priority order:** (1) #2093/#2400 authority
decision; (2) ADR 2026-06-11-1 / #1804 for the Op half; (3) #1619 aggregate
model; (4) #1868/#2173/#1797/#2468 sequencing.

Slices 0–3 are legitimate, low-risk, and mostly filable as reconciliation items
under existing epics rather than a new construction mission. Slice X is the only
part matching the note's original ambition, and it is explicitly **not now**.

## Related open tracker tickets

A three-lens tracker sweep (2026-07-16) mapped the open issues across all four
elements — see [wp-op-schema-related-tickets.md](wp-op-schema-related-tickets.md).
Key result: the idea's headline ambitions are **already filed** — **#1676** (P0,
deterministic structured authoring) and **#424/#425** (JSON-canonical planning
artifacts, markdown-derived) are the Slice-X architecture; **#2093/#2400** already
adjudicated the WP-metadata authority split. The template-move timing is owned by
the **#2652** arc (#2658 templates-as-config, #2659 template discovery) + **#2677**
(DRG edges → WP templates/assets). Only two elements are **unticketed**: the
semantic-only content-hash fix, and an optional Op scope/intent field (which
attaches to #2400 / ADR 2026-06-11-1, not a new epic — the #1804 Ops layer is
closed/shipped). Disposition therefore firms up to **reconcile-and-attach**, not
a new mission.
