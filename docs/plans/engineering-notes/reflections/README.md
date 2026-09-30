---
title: Engineering notes — Reflections
description: 'Landing page for the reflections engineering notes: quick dated notes on process inaccuracies and ad-hoc findings, not architectural decisions or doctrine.'
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/engineering-notes/reflections/2026-05-24-drg-profile-routing-missed-first-pass.md
---
# Engineering notes — Reflections

This directory holds **quick, dated notes about process inaccuracies, idiosyncratic mismatches, and ad-hoc findings** that surface during day-to-day work on Spec Kitty itself or in projects that adopt Spec Kitty.

It is intentionally **not** a place for architectural decisions (those go to `docs/adr/3.x/`), nor for charter doctrine (that goes to `.kittify/doctrine/`), nor for mission specs (those live under `kitty-specs/`).

## What belongs here

- Times a tool, skill, or runtime behaved in a way that did not match the operator's mental model.
- Cases where a default produced a sensibly-functional-but-suboptimal output that needed a second pass to correct.
- Workarounds discovered in passing that aren't yet codified into a skill or tactic.
- Observations about how Spec Kitty's own status commit surfaces interact with the project's protected-branch / pre-commit / CI configuration.
- Friction or surprise notes from dogfooding the toolchain.

## Difference from `finding/` and `architectural-review/`

Loose rules of thumb:
- **`reflections/`** (this dir): the orchestrator's own failure modes during a mission. "I should have done X earlier."
- **`finding/`**: the system's failure modes during a mission. "When the operator does X, the CLI does Y, but only after Z."
- **`architectural-review/`**: deep-dive code/structure audits done by architect-profile agents. "Module X and Y duplicate the same concept under different names."

## What does NOT belong here

- **Architectural decisions.** Use ADRs.
- **Doctrine changes.** Use the charter / doctrine packs.
- **Mission specs.** Use `kitty-specs/`.
- **Bug fixes ready to commit.** Open a GitHub issue and fix in code.
- **User-facing documentation.** Use `docs/` (other subdirectories).
- **Long-form retrospectives.** Use `retrospective-facilitator` agent profile output, not this directory.

## File format

One file per reflection. Filename: `YYYY-MM-DD-short-kebab-slug.md`. The first line is an H1 title; the second line is a single-sentence summary; everything below that is free-form notes (suggested structure: *what happened* → *what should have happened* → *why the gap* → *follow-up*).

Notes here are **not load-bearing**. Curators may distill recurring themes into ADRs, doctrine, or skills — at which point the corresponding reflection can be archived or deleted with a note saying which artifact absorbed it.

## Index

(append as new reflections land)

- [2026-05-24 — DRG profile routing not applied on first tasks generation](2026-05-24-drg-profile-routing-missed-first-pass.md)
