# Implementation Plan: Glossary — activation ledger and active charter

**Branch**: `kitty/mission-glossary-activation-ledger-01M68JH9` | **Date**: 2026-10-31 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/glossary-activation-ledger-01M68JH9/spec.md`

## Summary

Add an `activation ledger` term and refresh the `active charter` definition in the
Spec Kitty core glossary so both name `.kittify/charter/activation.yaml` as the
single activation authority (ADR `2026-10-19-1`), as #6496 already does in
`docs/context/charter.md`. The term data lives in two byte-identical copies: the
project seed `.kittify/glossaries/spec_kitty_core.yaml` (checked in here, drives
the published glossary page) and the built-in glossary pack (authored in
`spec-kitty-open-packs`, fetched here through a pin). The pack is changed
upstream and the core pin is bumped; the seed mirrors it. Two module docstrings
gain a pointer to their glossary entry, one stale guide line is corrected, and
the docs gates are re-run. No behavioural code changes.

## Technical Context

**Language/Version**: Python 3.12 (repository runtime); YAML glossary data
**Primary Dependencies**: none added — `ruamel.yaml` (existing) parses the seed and pack; `spec-kitty` CLI for pack vendoring
**Storage**: `.kittify/charter/activation.yaml` (the subject), `.kittify/glossaries/spec_kitty_core.yaml` (seed), `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml` (fetched pack), `packs/built-in.source.yaml` (pin lockfile)
**Testing**: pytest targeted — a focused glossary regression in `tests/glossary/`, plus the standing `tests/architectural/test_glossary_pack_parity.py` and `tests/architectural/test_no_legacy_terminology.py`
**Target Platform**: repository/docs toolchain (Linux CI), no runtime target change
**Project Type**: single project (source + docs + tests)
**Performance Goals**: N/A — data and documentation only; no hot path touched
**Constraints**: pack content changes upstream only (C-001); no behavioural code change (C-002); seed ↔ pack byte parity stays enforced (NFR-001); docs freshness errors=0 (NFR-003)
**Scale/Scope**: 2 glossary terms, 1 pin bump, 2 docstring pointers, 1 guide line, 1 changelog entry, 1 focused test

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — the change makes the glossary point at the one
  authority (`activation ledger`) instead of repeating a stale location. It does
  not add a second activation surface.
- **Terminology adherence** — the definitions use `docs/context/charter.md` and
  ADR `2026-10-19-1` wording; "active charter" keeps the ADR `2026-10-06-1` §1
  guard (the `.kittify/charter/` tree is never called "active").
- **Team Kitty / tier rule** — the term ships to every consumer, so it belongs in
  the built-in pack, not the internal pack.
- **ATDD-first / red-first** — the focused test is observed failing before the
  data changes; the parity test is the second, standing half of the proof.
- **Canonical sources** — `docs/context/charter.md` and the ADR are the sources;
  no older mission copy is used as a template.
- **Change-scope tension** — smallest viable diff: only the two terms, the pin,
  two docstring pointers, one stale guide line and one changelog entry. No
  glossary sweep, no unrelated prose edits.

## Project Structure

### Documentation (this mission)

```
kitty-specs/glossary-activation-ledger-01M68JH9/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 findings
├── reasons-canvas.md    # SPDD canvas
├── spec.md              # Mission specification
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

No `data-model.md`, `quickstart.md` or `contracts/` are produced: the mission
adds glossary data and documentation, defines no interface and changes no data
model. `meta.json` records `"contracts": "none"` with a rationale.

### Source Code (repository root)

```
.kittify/glossaries/spec_kitty_core.yaml        # seed: both term entries
packs/built-in.source.yaml                     # pin bump to the open-packs commit
docs/guides/how-to/governance/troubleshoot-charter.md  # stale location line
docs/changelog/CHANGELOG.md                    # [Unreleased] entry
src/charter/activation/activation_ledger.py    # module docstring pointer
src/charter/activation/resolver.py             # ActiveCharterService docstring pointer
tests/glossary/test_activation_ledger_terms.py # focused regression
tests/architectural/test_glossary_pack_parity.py  # standing parity (unchanged)
```

**Structure Decision**: single-project layout; the change is confined to the
glossary data files, two documentation surfaces, two docstrings and one test.
`packs/built-in/` is fetched and is not edited or committed here (C-001).

## Implementation Concern Map

- **IC-01 — Term definitions (seed + upstream pack).** The exact prose for
  `activation ledger` and the refreshed `active charter`, matching
  `docs/context/charter.md` and the issue's proposed substance. Authored once,
  then mirrored with the correct key order for each file.
- **IC-02 — Pack re-vendor.** Author the pack change in `spec-kitty-open-packs`,
  then `spec-kitty charter pack vendor --pack built-in --ref <commit>` in core to
  write the new commit/digest, and `make sync-packs`.
- **IC-03 — Pointers and truth.** `docs/context/charter.md#activation-ledger` and
  `#active-charter` links in the two module docstrings; the one stale
  `troubleshoot-charter.md` sentence; the `[Unreleased]` changelog entry.
- **IC-04 — Proof.** One focused glossary test (red before, green after); the
  standing parity test at the new pin; the named docs gates at errors=0.

## Phase 0: Outline & Research

`research.md` already carries the discovery decisions (D1–D8), evidence and open
questions; Phase 0 extends it with the final wording decision and the pin/re-vendor
order. No unresolved `NEEDS CLARIFICATION` remains: the wording source is
`docs/context/charter.md`, the upstream repository is `spec-kitty-open-packs`, and
the re-pin command is `spec-kitty charter pack vendor`.

## Phase 1: Design & Contracts

No data model or external contract changes. The glossary terms are data with a
fixed schema (`surface`, `definition`, `confidence`, `status`); the pack schema is
already validated by `GlossaryTerm`. Design output is the final definition text
and the file/key-order mapping between seed and pack, recorded in `tasks.md`.
