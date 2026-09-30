---
title: Recommended directory structure
description: Raw proposal dump from a 2026-02-17 repo-architecture-coaching brainstorm session, preserved as input to the architecture-discovery initiative.
doc_status: deprecated
updated: '2026-09-30'
---
2026-02-17:13:18

Mode: repo architecture coaching
Confidence: high
Scope: practical folder structure + rules of engagement (stable vs initiatives)

You’re aiming for two things that often get mixed:

1. **Stable architecture reference** (what the system *is*)
2. **Active design work** (what the system *might become*)

C4’s “zoom-in” framing is a great backbone for (1).
For (2), you want an “initiatives” lane that’s intentionally volatile.

Here’s a structure that works well in real repos, stays C4-aligned, and keeps initiatives from polluting the stable narrative.

---

## Recommended directory structure

```text
architecture/
  README.md

  01_context/
    README.md
    system-context.md
    system-context.puml
    stakeholders.md

  02_containers/
    README.md
    containers.md
    containers.puml
    runtime-topology.md

  03_components/
    README.md
    components.md
    components.puml
    component-index.md

  04_code/
    README.md
    key-modules.md
    cross-cutting-concerns.md
    adr-links.md

  adr/
    README.md
    0001-*.md

  initiatives/
    README.md
    2026-02-adhoc-specialists/
      README.md
      user-journeys/
        uj-adhoc-specialist-session.md
        uj-formalization-session-end.md
        uj-formalized-approach-to-mission.md
      dialectics/
        dialectic-structured-vs-adhoc.md
      notes/
        meeting-notes.md
      proposals/
        proposal.md
      decisions/
        adr-drafts.md

  archive/
    initiatives/
    deprecated/
```

### Why this works

* `01_…04_…` is the stable C4 “zoom-in” spine.
* `adr/` is stable decision record-keeping, separate from narrative docs.
* `initiatives/` is explicitly “in flight” and can contain UJs, dialectics, experiments, prototypes.
* `archive/` gives you a way to retire initiatives without deleting history.

---

## Rules that keep the separation real

### Stable architecture rules (C4 spine)

Stable docs should:

* describe current reality
* link to code where applicable
* avoid speculative language
* only change when the system changes

If you want future direction, link out to an initiative.

### Initiative rules

Initiative docs are allowed to be:

* exploratory
* contradictory (dialectics!)
* full of options
* time-bound

But they should always answer:

* what problem we’re exploring
* what success looks like
* what artefacts were produced
* what decisions were made (and where they landed)

---

## How to cross-link without contaminating

In stable docs, add a small “Active Initiatives” section (one line per item):

```md
## Active Initiatives
- Ad-hoc specialist interaction + formalization chain (see `architecture/initiatives/2026-02-adhoc-specialists/`)
```

In initiatives, always include:

* “current architecture touchpoints” (which C4 docs/components it impacts)
* “migration path” (if it lands, where it will be reflected in stable C4)

---

## Naming and numbering guidance

* The numeric prefixes (`01_`, `02_`) keep files navigable in GitHub.
* C4 levels are clearly signposted without forcing you into the official tooling.
* Initiative folders should be time-stamped or issue-numbered:

  * `2026-02-adhoc-specialists`
  * `SK-123-adhoc-specialists`

Pick one and stick to it.

---

## A very practical README for `architecture/`

In `docs/architecture/README.md`, clarify the contract:

* “If you want to understand how the system works today, read 01–04.”
* “If you want to see what we’re currently exploring, check initiatives.”
* “If you want binding decisions, check adr.”

That’s what makes this structure usable for contributors.

---

## One sharp warning

If you put “future direction” into the C4 spine, it will rot fast and confuse everyone.
Keep speculative thinking in `initiatives/` until it becomes real, then migrate it into the spine + ADR.

That migration step is part of the discipline.

---

If you want, I can draft the `docs/architecture/README.md` and `architecture/initiatives/README.md` texts so the separation is explicit and contributors don’t accidentally blur the boundary.
