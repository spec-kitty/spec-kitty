---
title: 'ADR: spec-kitty-internal Is One Public Org Pack, Consumed via the Org Tier, Never Force-Shipped'
description: 'The internal maintainer pack is one public artifact (open-packs catalog #16), consumed as an org-tier pack and kept out of the core wheel — not secret, just not shipped.'
status: Accepted
date: '2026-08-16'
related:
- docs/adr/3.x/2026-08-16-2-open-packs-is-source-of-truth-for-built-in-doctrine.md
- docs/adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md
- docs/adr/3.x/2026-05-24-2-pack-augmentation-vocabulary.md
---

# spec-kitty-internal Is One Public Org Pack, Consumed via the Org Tier, Never Force-Shipped

**Filename:** `2026-08-16-3-spec-kitty-internal-is-a-public-org-pack-not-force-shipped.md`

**Status:** Accepted

**Date:** 2026-08-16

**Deciders:** Maintainer

**Technical Story:** Internal doctrine-pack initiative. The open-packs catalog proposal already scopes `spec-kitty-internal` as base pack #16 (public, "so contributors and downstream teams can adopt or study it"), grounded in core #2196. A repo-local `packs/internal/` first step was built on branch `feat/internal-pack`.

---

## Context and Problem Statement

Spec Kitty wants an **internal** doctrine pack + org charter that governs how the
core team works on the project itself (PR-landing, tracker processing, keeping main
honest, the internal glossary), stated as "**not shipped to our consumers**" — yet
also "**built in the open**" as "an example for our user-base." Read literally these
pull in opposite directions: private vs. public.

Separately, the open-packs catalog already scopes a pack for exactly this slot —
`spec-kitty-internal` (base pack #16), framed as **public and studyable**. Building a
second, private pack would **duplicate** #16 and its `org-charter.yaml`, and force a
policy for what is secret vs. public.

We must decide whether `spk-internal` is a distinct private artifact or the same
public pack #16, and what "not shipped to consumers" actually constrains.

## Decision Drivers

* Avoid duplicating catalog pack #16 and its charter.
* Reconcile "build in the open" with "not shipped to consumers".
* Keep the public built-in product context clean — maintainer doctrine must not flood
  every consumer's LLM session.
* Reuse the already-built org-tier consumption path (no new plumbing).

## Considered Options

* **A — Distinct private pack:** a maintainer-only pack that never appears in the public
  catalog.
* **B — One public org pack, not force-shipped (chosen):** `spk-internal` **is** catalog
  pack #16 — authored in the open in open-packs (studyable), consumed by SK-Inc projects
  as an **org-tier** pack via `.kittify/config.yaml`, and **never force-included** in the
  core consumer wheel. "Not shipped" == not in the wheel; **not** == secret.
* **C — Ship it like built-in:** force-include the internal pack in the wheel alongside
  `packs/built-in/`.

## Decision Outcome

**Chosen option: "B — One public org pack, not force-shipped."** There is one artifact,
not two: the open-packs catalog pack #16 `spec-kitty-internal`. It is developed publicly
(anyone may study or adopt it), and SK-Inc projects consume it as an **org-tier** pack —
the merged org-pack loader, `subdir:` support, and `${ENV}`/`~` indirection already make
this a config entry, not new code. It is deliberately **excluded from the core wheel**:
`pyproject.toml`'s `force-include` and sdist globs are scoped to `packs/built-in/` so a
consumer's default install never inherits maintainer doctrine, keeping their context clean.
This precisely reconciles "built in the open" (public source) with "not shipped to
consumers" (absent from the distributed artifact).

The repo-local `packs/internal/` created as the first step is a **transitional staging
location** inside the core repo; its permanent home is the open-packs catalog (per the
companion ADR `2026-08-16-2`, which makes open-packs the source of truth for pack content).

Option A is rejected (duplicates #16, needs a secrecy policy for no real benefit — the
content is not sensitive, only context-noisy). Option C is rejected (pollutes every
consumer's default context with maintainer-only doctrine — the exact problem the pack
system exists to solve).

### Consequences

#### Positive

* One artifact, one `org-charter.yaml`; no duplication.
* Consumers keep a clean default context; SK-Inc projects opt in explicitly.
* Reuses the org tier — a config entry, not new plumbing.
* The pack is public and studyable, serving as the worked example for the user base.

#### Negative

* "Not shipped" is enforced only by the packaging-scope guard; a future whole-tree
  `force-include` regression would re-leak it. Mitigated by
  `tests/cross_cutting/packaging/test_packaging_safety.py` (tightened to `packs/built-in/`
  with an explicit "internal must not ship" assertion).
* SK-Inc projects must each register the org pack (via `.kittify/config.yaml`, or a seeded
  `spec-kitty init` default) — there is no auto-broadcast to "all projects" today.

#### Neutral

* The internal pack's content overlaps maintainer doctrine already in built-in; the pack
  **references** those via DRG edges rather than re-authoring them.

### Confirmation

Success = (1) exactly one `spec-kitty-internal` pack exists (open-packs #16); (2) it never
appears in a released wheel (guard test green; a real wheel build shows 0 `packs/internal/`
files while `packs/built-in/` ships fully — verified for the first-step scaffold); (3)
SK-Inc projects load it as a healthy org layer (`doctor doctrine` reports it with resolved
edges, no dangling/collisions — verified for the first-step scaffold).

## Pros and Cons of the Options

### A — Distinct private pack

**Pros:** Clean secrecy story.
**Cons:** Duplicates #16 + its charter; needs a private-vs-public policy; no real benefit
since the content is not sensitive.

### B — One public org pack, not force-shipped

**Pros:** No duplication; clean consumer context; reuses org tier; public/studyable.
**Cons:** Non-shipment relies on a packaging guard; no auto-broadcast to all SK-Inc projects.

### C — Ship it like built-in

**Pros:** Auto-present everywhere.
**Cons:** Floods every consumer's context with maintainer-only doctrine — defeats the pack
system's purpose.

## More Information

* First step: `packs/internal/` scaffold on branch `feat/internal-pack` (glossary_pack +
  `landing-contributor-prs` procedure + `drg/fragment.yaml` + `org-charter.yaml`), packaging
  scoped to `packs/built-in`, guard test tightened.
* Companion decision (source of truth + re-vendor): `2026-08-16-2-open-packs-is-source-of-truth-for-built-in-doctrine.md`.
* Catalog: `spec-kitty-open-packs/docs/packs/catalog-proposal.md` (pack #16).

## Amendment (2026-10-19 — cross-reference, #6451)

No decision change. `packs/internal/` is now pinned and fetched like `packs/built-in/`: its
source lives in `spec-kitty-open-packs` (`packs/internal`), core holds only
`packs/internal.source.yaml`, and `make sync-packs` places the tree. It is still never
shipped: the wheel and sdist exclude it and `tests/cross_cutting/packaging/test_packaging_safety.py`
is extended to cover the fetched tree and the `source.yaml` pins. See the 2026-10-19 amendment to
`2026-08-16-2-open-packs-is-source-of-truth-for-built-in-doctrine.md`.
