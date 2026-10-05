# Implementation Plan: Mirror three glossary terms into the built-in pack

**Branch**: `issue-5761-glossary-pack-terms` | **Date**: 2026-10-05 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/glossary-pack-mirror-three-terms-01M45SNF/spec.md`

## Summary

Append three terms (tool-surface drift, integrating worktree, target-owned
bookkeeping) to the shipped glossary pack
`packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml` and, with
identical fields, to this project's seed `.kittify/glossaries/spec_kitty_core.yaml`.
Definitions are condensed from the canonical `docs/context/` entries (meaning
unchanged), then the pack manifest is regenerated. Grounding:
[research/code-grounding.md](research/code-grounding.md).

## Engineering Alignment

No live user in this scheduled run; the operator's stored task brief stands in
for the planning interview. Decisions taken from it and from grounding:

1. Both files are hand-edited; the terms are appended at the end of each list.
2. Status `active`, confidence `0.9`. The `docs/context/` entries say
   `candidate`, but a seed/pack `draft` term is skipped when the glossary DRG is
   built (`src/glossary/drg_builder.py` keeps only active senses), so `draft`
   would not resolve through the glossary tooling (spec SC-001).
3. "Do not use" guidance: a condensed "not this" passage in the definition,
   plus `synonyms_to_avoid` (`drift` for tool-surface drift,
   `primary-owned bookkeeping` for target-owned bookkeeping).
4. Pack text cites no issue numbers and no `src/` paths (provenance ratchet);
   each definition ends by pointing at its `docs/context/` entry, as the
   "skill" precedent does.

## Technical Context

**Language/Version**: YAML data files read by Python 3.11 (pydantic `GlossaryTerm` / `GlossarySeedTerm` schemas)
**Primary Dependencies**: ruamel.yaml loaders; `spec-kitty doctrine regenerate-graph` for the pack manifest
**Storage**: files (`packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml`, `.kittify/glossaries/spec_kitty_core.yaml`, `packs/built-in/pack-manifest.yaml`)
**Testing**: existing gates only (no new test): pack/seed parity, pack-manifest round trip, provenance ratchet, legacy terminology, glossary/doctrine/charter suites, `make test-fast`
**Target Platform**: every Spec Kitty consumer (the built-in pack ships in the wheel)
**Project Type**: single
**Performance Goals**: N/A (data change)
**Constraints**: no `docs/context/` wording change; no source code; no other terms; no `.github/ci-shard-timings.json` recapture
**Scale/Scope**: 3 terms, 2 data files, 1 regenerated manifest

## Charter Check

| Charter rule | Status |
|---|---|
| Single canonical authority | Pass: `docs/context/` stays the wording authority; pack and seed mirror it. |
| Pack tiers (built-in vs internal) | Pass: all three name consumer-visible behavior (grounding section 3). |
| Canonical sources | Pass: follows precedent `b70a344fc8` / `8fc1a85560`; manifest via `regenerate-graph`. |
| Terminology canon | Pass: Mission, "tool surface", named senses of primary/merge; no "spec-kitty merge". |
| `DIRECTIVE_048` version governance | Pass: definitions mirror the current `docs/context/` entries on `origin/main` @ `14d653bb9` and ADRs `2026-10-04-3` / `2026-10-04-4`. |
| ATDD-first | Adapted: there is no behavior to drive; the red-first check is the parity and manifest gates, which go red if only one file is edited or the manifest is stale. Recorded in the WP. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | Pass: named gate files only. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/glossary-pack-mirror-three-terms-01M45SNF/
├── spec.md
├── plan.md
├── research.md
├── research/code-grounding.md
├── data-model.md
├── quickstart.md
├── traces/
└── tasks/
```

### Source Code (repository root)

```
packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml   # +3 terms
packs/built-in/pack-manifest.yaml                                  # regenerated hashes
.kittify/glossaries/spec_kitty_core.yaml                           # +3 terms (mirror)
```

**Structure Decision**: data-only change in the two glossary files plus the generated manifest; no code tree.

## Implementation Concern Map

### IC-01 — Glossary mirror

- **Purpose**: add the three terms to the pack and the seed with identical fields, and regenerate the pack manifest.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005
- **Affected surfaces**: the three files above
- **Sequencing/depends-on**: none
- **Risks**: seed/pack string mismatch (parity gate); a cited issue number or `src/` path in pack text (provenance ratchet); a stale manifest (round-trip gate).
