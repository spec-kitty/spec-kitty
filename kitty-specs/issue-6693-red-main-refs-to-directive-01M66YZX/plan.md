# Implementation Plan: Repoint the red-main references to the RED_MAIN_RELEASE_DISCIPLINE directive

**Branch**: `issue-6693-red-main-refs-to-directive` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/issue-6693-red-main-refs-to-directive-01M66YZX/spec.md`
**Input**: Mission specification from `kitty-specs/issue-6693-red-main-refs-to-directive-01M66YZX/spec.md`

**Note**: This plan is filled in by hand for a `change_mode: bulk_edit` mission whose
upstream doctrine change already landed (open-packs#74, pin `72cb7dbc`).

## Summary

Vendor both charter packs forward to `spec-kitty-open-packs@72cb7dbc` (the merge
commit of open-packs#74, which turns the built-in `red-main-release-discipline`
procedure into the `RED_MAIN_RELEASE_DISCIPLINE` directive and the internal
`spec-kitty-red-main-policy` procedure into the `SPEC_KITTY_RED_MAIN_POLICY`
directive), then repoint every live core reference that still names the retired
procedure id: the curated `DIRECTIVE_030` edge, five tests, the
`minimal_org_pack_2` fixture, and this repository's own activation ledger and
charter prose. Add one guard test so the next upstream re-kinding fails here
instead of emitting a warning nobody reads. No fetched pack file is edited.

## Technical Context

**Language/Version**: Python 3.11+ (repo floor), typed `mypy --strict`; YAML artefacts (charter packs, activation ledger, compiled catalog)
**Primary Dependencies**: `typer` CLI, `ruamel.yaml`, `pytest`; pack content fetched from `spec-kitty-open-packs` via `scripts/sync_packs.py`
**Storage**: files — `packs/<pack>.source.yaml` pin lockfiles, fetched `packs/built-in/` + `packs/internal/` trees (untracked), `.kittify/charter/activation.yaml` ledger, `.kittify/charter/charter.yaml` compiled catalog
**Testing**: `pytest`; targeted files only during mission work (NO_FULL_HEAVY_SUITES_IN_MISSION). Red evidence already captured at the bumped pin: `tests/charter_offering/drg/test_single_owner_edges.py`, `tests/charter_offering/drg/migration/test_extractor_projection.py`, `tests/charter_offering/test_testing_doctrine_single_owner.py`, `tests/integration/test_org_pack_chain_delivery.py` (6 failing tests), plus a new ledger-resolution guard.
**Target Platform**: Linux/macOS developer machines and CI; POSIX paths only
**Project Type**: single project (CLI + charter runtime library under `src/`)
**Performance Goals**: N/A — build-time data, no runtime path changes; the new guard test must stay in the fast tier (no network, reads the already-synced trees)
**Constraints**: fetched pack content is never edited; pin bumps use `spec-kitty charter pack vendor` + `make sync-packs`; no gate may be skipped, xfailed or weakened; historical records keep their wording (C-002)
**Scale/Scope**: 2 pin lockfiles, 1 curated-edge tuple, 5 test files, 1 fixture fragment, 4 regenerated/repointed charter surfaces, 1 charter prose file, 1 changelog entry, 1 new test

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — the doctrine change is authored upstream in `spec-kitty-open-packs` and reaches core only through the pin; core keeps one live reference per surface. ✔
- **Pack-tier boundary** — no doctrine is added: built-in stays consumer doctrine, internal stays in-house doctrine. The mission edits neither tree. ✔
- **Template Source Location (AGENTS.md)** — edit the source (open-packs), bump the pin here; do not edit `packs/**` in core. ✔ (the mission's only `packs/` changes are the two `*.source.yaml` pins)
- **ATDD / red-first (DIRECTIVE_034)** — the six failures were observed at the bumped pin before any fix, through the tests' own entry points. ✔
- **Bulk-edit gate (DIRECTIVE_035)** — `change_mode: bulk_edit`; `occurrence_map.yaml` classifies all eight categories, four preserved-history exceptions and the two pin lockfiles. ✔
- **Test discipline (DIRECTIVE_041)** — one new test, guarding a standing invariant (every ledger id resolves) with a positive control on the same fixture; no test is added to restate what an existing gate already proves. ✔
- **Documentation sync (DIRECTIVE_037)** — the changelog entry names the directive, the before/after and the consumer action; `charter.md`'s two pointers follow the artifact. ✔
- **Git discipline (DIRECTIVE_045)** — draft PR first, operator merges, no push to `main`. ✔

## Project Structure

### Documentation (this mission)

```
kitty-specs/issue-6693-red-main-refs-to-directive-01M66YZX/
├── plan.md              # This file
├── research.md          # Phase 0 output (discovery findings, D1-D6)
├── occurrence_map.yaml  # bulk-edit classification (DIRECTIVE_035)
├── spec.md              # Mission specification
├── traces/              # approach.md, design-decisions.md, tooling-friction.md
└── tasks/               # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
packs/
├── built-in.source.yaml        # pin lockfile -> open-packs 72cb7dbc
└── internal.source.yaml        # pin lockfile -> open-packs 72cb7dbc

src/charter/offering/drg/migration/
└── extractor.py                # _CURATED_ARTIFACT_EDGES: DIRECTIVE_030 -> directive:RED_MAIN_RELEASE_DISCIPLINE

tests/
├── charter_offering/
│   ├── drg/test_single_owner_edges.py            # test-first-bug-fixing -> directive requires
│   ├── drg/migration/test_extractor_projection.py # ledger commentary + curated-edge projection
│   ├── test_testing_doctrine_single_owner.py      # reference set of test-first-bug-fixing
│   ├── fixtures/minimal_org_pack_2/drg/fragment.yaml
│   └── test_red_main_ledger_resolution.py         # NEW guard (FR-005)
└── integration/test_org_pack_chain_delivery.py    # internal-pack refines edges

.kittify/charter/
├── activation.yaml             # procedure -> directive, stale deny entry removed
├── charter.yaml                # compiled catalog (regenerated by the CLI)
├── synthesis-manifest.yaml     # bundle hash (regenerated by the CLI)
├── charter.md                  # standing-order pointers
└── ../charter-packs/graph.yaml # project DRG layer (regenerated by the CLI)

docs/changelog/CHANGELOG.md     # [Unreleased] entry
```

**Structure Decision**: single project. Every path above is an existing surface;
the mission adds exactly one source file (the guard test) and no module.

## Complexity Tracking

*No charter violations to justify.*

## Implementation Concern Map

### IC-01 — Vendor the pin and repoint the curated DRG edge

- **Purpose**: move both packs to `72cb7dbc` and stop the curated `DIRECTIVE_030`
  edge from minting an orphan `procedure:red-main-release-discipline` node, so the
  regenerated graph equals the shipped one again.
- **Relevant requirements**: FR-001, FR-002, NFR-001, NFR-003, C-001, C-003
- **Affected surfaces**: `packs/built-in.source.yaml`, `packs/internal.source.yaml`,
  `src/charter/offering/drg/migration/extractor.py`
- **Sequencing/depends-on**: none (first — every other concern is validated
  against the bumped pin)
- **Risks**: the pin must be the #74 merge commit, not open-packs `main` tip
  (unrelated breaking migration); the curated edge's comment block must explain
  the kind change or the next reader will "fix" it back.

### IC-02 — Repoint the five tests and the org-pack fixture

- **Purpose**: make every test assertion and fixture edge name what the packs
  now ship, keeping the same checks (no assertion weakened).
- **Relevant requirements**: FR-003, NFR-002, C-002
- **Affected surfaces**: `tests/charter_offering/drg/test_single_owner_edges.py`,
  `tests/charter_offering/drg/migration/test_extractor_projection.py`,
  `tests/charter_offering/test_testing_doctrine_single_owner.py`,
  `tests/integration/test_org_pack_chain_delivery.py`,
  `tests/charter_offering/fixtures/minimal_org_pack_2/drg/fragment.yaml`
- **Sequencing/depends-on**: IC-01
- **Risks**: `test_extractor_projection.py` carries ledger commentary about the
  retired procedure; the *counts* it pins (node/edge totals) must be updated only
  if the shipped graph actually changes them — verify, do not assume.

### IC-03 — Repoint this repository's charter and add the ledger guard

- **Purpose**: replace the activated procedure with the activated directive,
  drop the stale deny entry the doctor names, refresh the charter prose pointers,
  and add a fast guard that every activation-ledger id resolves against the
  fetched packs.
- **Relevant requirements**: FR-004, FR-005, FR-006, SC-002
- **Affected surfaces**: `.kittify/charter/activation.yaml`,
  `.kittify/charter/charter.yaml`, `.kittify/charter/synthesis-manifest.yaml`,
  `.kittify/charter-packs/graph.yaml`, `.kittify/charter/charter.md`,
  new `tests/charter_offering/test_red_main_ledger_resolution.py`,
  `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01
- **Risks**: the ledger writes must go through
  `spec-kitty charter deactivate` / `activate` (generate the compiled surfaces;
  never hand-edit `charter.yaml`), and the stale `deactivated_procedures` entry
  must be removed by hand afterwards because the doctor's own remedy says so.
  The guard test must use a shared fixture for the positive and negative cases
  (acceptance-criteria-non-vacuity) and must not depend on the network.

## Phase 0: Outline & Research

Research lives in `research.md` (discovery findings D1–D6). No dependency is
added, upgraded or removed, so the supply-chain section of the plan step is a
no-op; that is stated here rather than left silent.

## Phase 1: Design & Contracts

No new interface, contract or data model. The only new code is a test module.
Contracts changed: none (the charter pack *interface* is the pin lockfile, whose
schema is unchanged — only its values move).

## Key rules for implementation

- Run `spec-kitty charter pack vendor --pack <built-in|internal> --ref 72cb7dbcba69efa608327be9921d915f435d1565`
  from a `uv run --frozen` checkout; then `make sync-packs`.
- Never hand-edit anything under `packs/built-in/` or `packs/internal/`.
- Never hand-edit `.kittify/charter/charter.yaml` or `synthesis-manifest.yaml`;
  regenerate them through the CLI's ledger seam.
- Do not run a full heavy suite; run the named files.
