# Implementation Plan: Contract Scenario glossary entry and the Pack Level "tier" wording

**Branch**: `issue-6439-contract-scenario-glossary-and-pack-level` | **Date**: 2026-10-31 | **Spec**: [`spec.md`](./spec.md)
**Input**: Mission specification from `kitty-specs/contract-scenario-glossary-and-pack-level-01M68J95/spec.md`

## Summary

Add a **Contract Scenario** entry to the core glossary in `docs/context/charter.md`
(beside Charter Pack), carrying the definition, home, related terms and a
`Do NOT use when` guard. Correct the **Pack Level** entry in
`docs/context/governance.md` so a pack's level is called a *level*, not a *tier*,
and correct the same claim as restated in the **Charter Pack** entry. Pin both with
one docs-scoped test that fails on the pre-fix tree and passes after, ignoring
`kernel.pack_tiers` inside inline code spans. Regenerate the docs index for the new
heading and add one `[Unreleased]` changelog entry.

The work is prose and one test module. No `src/` code path, no contract, no schema,
no generated site artefact changes.

## Technical Context

**Language/Version**: Markdown (DocFX-flavoured, markdownlint-cli2) for the glossary; Python 3.11 for the guard test and the docs gates
**Primary Dependencies**: `pytest` (guard test), `scripts/docs/docs_index.py` (index regeneration), `scripts/docs/check_docs_freshness.py`, `scripts/docs/freshen_adr_inventory.py`
**Storage**: N/A — files on disk (`docs/context/*.md`, `docs/development/docs-retrieval-index.yaml`, `tests/docs/`)
**Testing**: red-first `pytest` module under `tests/docs/`; then the docs gates (`docs_index`, `freshen_adr_inventory --check`, `check_docs_freshness --ci`, `test_no_legacy_terminology`, `make docs-lint`)
**Target Platform**: the same Linux/macOS/Windows developer and CI surface that already runs the docs shard — nothing platform-specific is added
**Project Type**: single project (documentation + its guard tests)
**Performance Goals**: N/A — the new test parses four small markdown files; well under one second
**Constraints**: no gate skipped, weakened, allowlisted or baselined (C-002); `docs/context/` is the only authoring surface (C-001); Organization Tier and `kernel.pack_tiers` untouched (C-003)
**Scale/Scope**: two glossary pages edited, four added/modified assertions, one changelog entry, one regenerated index file

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter gate | How this mission satisfies it |
| --- | --- |
| **Single canonical authority** | `docs/context/` is the one glossary authority this mission edits; no second copy is introduced in the seed, the built-in pack or a generated file (D2 in `research.md`). |
| **Glossary & terminology adherence** | The mission exists to make two entries match the canonical terms (`level` for a pack, `layers` for the merged graph) and to define a term that is used downstream. |
| **`DIRECTIVE_024` Locality of Change** | The diff stays inside the two entries the issue names plus the one restatement of the same claim; nothing else in either page is touched. |
| **`DIRECTIVE_025` Boy Scout Rule** | The second "tier token" occurrence (Charter Pack entry) is fixed because leaving it would keep the corrected entry contradicted two entries away; this is in-scope locality, not an unrelated cleanup. |
| **`DIRECTIVE_034` test-first bug fixing / ATDD-first** | The guard test is authored and observed to fail before either entry changes; each half of the fix reds a distinct assertion when reverted. |
| **`DIRECTIVE_041` test only what guards real behaviour** | One test module, standing, guarding the exact wording contract the issue asks for — not a per-WP shape check. |
| **`NO_FULL_HEAVY_SUITES_IN_MISSION`** | Only the docs shard's own gates and the new module are run locally; no `test-full` sweep. |
| **Documentation Standards / docs freshness** | Index regenerated, inventory checked, freshness gate run to `errors=0`, changelog entry added. |
| **No gate weakening (C-002)** | No skip/xfail/allowlist/baseline. Pre-existing reds are cited, not suppressed. |
| **Attribution / commit identity** | Commits authored as the operator's noreply identity; no machine paths or personal data in commits. |

No violations; **Complexity Tracking** is empty and stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/contract-scenario-glossary-and-pack-level-01M68J95/
├── plan.md              # This file
├── research.md          # Phase 0 output (discovery D1–D7, plan-phase additions)
├── data-model.md        # Phase 1 output: the glossary-entry shape and its invariants
├── quickstart.md        # Phase 1 output: how to read and re-check the two entries
├── spec.md              # Authored specification
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — not created here)
```

`contracts/` is deliberately absent: this mission defines no interface. `meta.json`
records `"contracts": "none"` with the rationale, so strict `accept` waives it.

### Source Code (repository root)

```
docs/
├── context/
│   ├── charter.md                       # + ### Contract Scenario; Charter Pack "tier token" -> "level token"
│   └── governance.md                    # Pack Level entry: "tier" -> "level" throughout
├── development/
│   ├── docs-retrieval-index.yaml        # regenerated (new ### heading)
│   └── page-inventory.yaml              # unchanged in expectation (no new page); checked, not hand-edited
└── changelog/
    └── CHANGELOG.md                     # one [Unreleased] entry

tests/
└── docs/
    └── test_context_glossary_contract_scenario_and_pack_level.py   # new standing guard
```

**Structure Decision**: single project. The change is documentation plus the test that
guards it; it adds no module, entry point or package boundary, so no `src/` tree is
touched and no Option 2/Option 3 layout applies.

## Implementation Concern Map

### IC-01 — Add the Contract Scenario entry

- **Purpose**: make the term resolvable in core, so the downstream import carries it.
- **Relevant requirements**: FR-001, SC-001, NFR-002
- **Affected surfaces**: `docs/context/charter.md` (between `### Charter Pack` and `### Activation preset`)
- **Sequencing/depends-on**: none — this is the entry that makes the guard test meaningful
- **Risks**: the definition must stay one markdown table cell and must not read as buzzword soup; naming `contracts/charter/...` paths that live in spec-kitty-charter is intended (the entry describes a downstream contract, like Charter Pack describes consumer config), and `Related terms` must not link a page that does not exist in core (the Acceptance Scenario and Conformance Corpus entries are absent today — see `## Deferred`)

### IC-02 — Correct the pack-level wording in both entries

- **Purpose**: stop the glossary calling a pack's level a "tier", which the cited ADR rejects and the downstream domain language forbids.
- **Relevant requirements**: FR-002, FR-003, SC-002
- **Affected surfaces**: `docs/context/governance.md` (Pack Level: opening sentence, "tier token", and any other pack-level "tier"), `docs/context/charter.md` (Charter Pack: "the tier token")
- **Sequencing/depends-on**: none
- **Risks**: `kernel.pack_tiers` is a module name and must survive verbatim; the **Organization Tier** term and the *Three-layer DRG* entry's own "tier" prose are different senses and must not be swept (C-003). Every other clause of the Pack Level entry — `PACK_LEVEL_MISMATCH`, `PACK_LEVEL_MISSING`, the deprecation window shipped by #6403 — keeps its meaning.

### IC-03 — Guard, index and changelog

- **Purpose**: make the correction stick and keep the docs gates green.
- **Relevant requirements**: FR-004, SC-003, SC-004, NFR-001, NFR-003
- **Affected surfaces**: `tests/docs/test_context_glossary_contract_scenario_and_pack_level.py`, `docs/development/docs-retrieval-index.yaml`, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01 and IC-02 for the green state; the test is authored **before** them (red-first)
- **Risks**: the absence probe for "tier" must strip inline code spans or it reds on `kernel.pack_tiers`; the same test needs a positive control (the entry's required rows and the authority name are present) so it cannot pass by reading nothing; the index regeneration must not be run repo-wide in a way that races other agents' checkouts (regenerate only the index file this diff changes)

## Phase 1 design notes

- **Data model**: the entities are glossary entries and the rows they carry — see `data-model.md`. There is no persistence, no state transition and no runtime event.
- **Contracts**: none. The mission changes prose and adds a test; it exposes no interface. `meta.json` carries `"contracts": "none"` and the rationale.
- **Quickstart**: `quickstart.md` states how a reader finds the two entries and how a maintainer re-runs the four gates.
