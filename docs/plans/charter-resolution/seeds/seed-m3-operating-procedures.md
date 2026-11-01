---
title: Mission Seed M3 - Operating-Procedures Validate, Triage, Data-Drive
description: 'Specify-intake seed for the mission closing #2994/#3352: validate operating-procedures references, triage fictional entries, then data-drive profile-to-procedure edges.'
doc_status: active
updated: '2026-08-19T00:00:00Z'
kind: Planning
---

# Mission Seed — M3: Operating-Procedures Validate → Triage → Data-Drive

> **Status:** seed (not yet a mission). Feed this to `/spec-kitty.specify` in a fresh session.
> **Part of:** charter-resolution program (see `../program-brief.md`).
> **Closes:** #2994, #3352, and the operating-procedures channel of #3488.
> **Effort:** L. **Depends on:** M1 (single-authority resolution parity) landed — needs the validated node universe. Independent of M2.

## Problem

`collaboration.operating-procedures` on an agent profile is a schema-validated `list[str]`, but its **values are never checked against real doctrine nodes**: measured across 16 built-in profiles, **36 of 50** declarations name no node (8 name a wrong-kind node; only 6 name a real procedure node). Because the edge-extractor ignores the field entirely, the real `agent_profile → procedure` edges are hand-pinned one profile at a time in `_CURATED_ARTIFACT_EDGES`. So authored procedure references are silently inert, and #3352 (data-drive those edges) cannot be done by blind emission because it would mint 36 dangling edges → `assert_valid` failure.

## Fix approach (hard internal order — do NOT reorder)

1. **Validate loud (first).** Add a load-time validator: every `operating-procedures` entry must resolve to a real doctrine node. Converts the 36 silent fictional refs into loud failures. Cheap, high-value, independent. (Empty-allowlist gate precedent: WP09.)
2. **Triage the 36.** Author / repoint / delete each fictional entry (per-artefact review). Decide the field's direction (project into edges vs retire/rename).
3. **Data-drive (last).** Teach the extractor to emit `agent_profile --requires--> procedure` from the field, **guarded to targets that resolve to an existing node**; retire the hand-pinned `_CURATED_ARTIFACT_EDGES` entries sourced from operating-procedures. Also complete the still-unwired RECONCILE third trigger edge (`tactic:change-apply-smallest-viable-diff`).

## Open operator decisions (resolve at this mission's discovery)

- **Wire vs deprecate:** should `operating-procedures` become a first-class edge source, or be deprecated/renamed in favour of DRG edges? (Either way, ship the dead-entry diagnostic.)
- **Triage dispositions:** the 36 fictional refs need per-entry author/repoint/delete calls — likely a review artifact, not a single decision.

## Scope

- **In:** the operating-procedures validator, the 36-entry triage, the data-driven extractor emission, retiring the related hand-pins.
- **Out:** the broader kind-complete cascade (#2829, that is M5); delivery/render of procedures to the agent (that is M4's `procedures[]`/step-description work).

## Key seams (from the investigation)

- `doctrine/agent_profiles/profile.py` (`CollaborationContract.operating_procedures`)
- `doctrine/drg/migration/extractor.py` (`extract_artifact_edges`; the hand-pin at ~:463)
- `_CURATED_ARTIFACT_EDGES` (the per-profile hand-pins to retire)
- validator precedent: the WP09 empty-allowlist gate

## Risk

Data-driving before triage mints 36 dangling edges and fails `assert_valid`. The order above is load-bearing.
