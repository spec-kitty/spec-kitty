# Implementation Plan: Charter Activation Shard Routing (#6336)

**Branch**: `issue-6336-charter-activation-shard-routing` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/charter-activation-shard-routing-01M68ZRA/spec.md`

## Summary

Register the charter activation store (`.kittify/charter/charter.yaml`,
`.kittify/charter/activation.yaml`) and the internal-pack pin
(`packs/internal.source.yaml`) as a new NON-src router group
`charter_activation`, and fan it out to the `charter` registry module so an edit
there selects `module-tests (charter shard …)` — closing the hole through which
#6333 reached `main` green. Add `src/kernel/activation_ledger_store.py` to the
`charter` scrub group's roots (and therefore to the registry row) so the ledger's
kernel floor also runs the `tests/charter/activation/**` readers. Everything is
pinned by red-first routing tests plus the existing CI-integrity guards, none of
which is weakened.

## Technical Context

**Language/Version**: Python 3.12 (repo toolchain; `uv`-managed)
**Primary Dependencies**: no new dependencies. Touches `scripts/ci/gate_selection.py`
(existing), GitHub Actions workflow YAML, the module registry and the retirement
scrub data.
**Storage**: N/A (repository data files: `tests/release/ci_retirement_scrub.json`,
`.github/ci-module-registry.yml`, `.github/ci-consumer-census.json` read-only)
**Testing**: `pytest`; the change is a routing/selection change, so the tests drive
the production entry point `scripts.ci.gate_selection.select_gates` /
`select_modules` (the same call `.github/workflows/ci-modules.yml` makes) and assert
on the parsed router, never on a helper copy of it.
**Target Platform**: GitHub Actions (ubuntu-24.04) + local `pytest`
**Project Type**: single project (CLI + CI tooling in one repo)
**Performance Goals**: no per-PR cost for unrelated diffs — NFR-001 asserts
`select_modules` is unchanged for docs-only, the built-in pin and an unrelated src
group; a diff touching only the new globs selects exactly one module (`charter`).
**Constraints**: the new group must stay non-src (FR-004 fail-closed union
untouched); `packs/internal/**` must not be a router glob (untracked since #6451);
group globs must be live tracked paths; the `charter` filter must remain a verbatim
transcription of the scrub's `charter` roots.
**Scale/Scope**: 1 new router group, 1 new hand-authored fan-out row, 1 added scrub
root (mirrored into 1 registry row), 1 new test module (~200 lines), 1 guard
registry extension (deliberately-ungated groups), 1 changelog entry. No product
runtime code changes.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| **Single canonical authority** | The path→group map stays in `ci-router.yml`; module selection stays in `gate_selection.select_modules` (it *parses* the router, it does not re-encode it). No second routing map is introduced — the new table is a group→module fan-out, the same shape as `CLI_COMMAND_MODULE_FANOUT`. |
| **Architectural alignment / locality (DIRECTIVE_024)** | The change lands at the three places the CI-integrity guards already own (router filter, scrub/registry roots, gate-selection) and nowhere else; no new workflow file, no new module, no shard re-count. |
| **ATDD-first / red-first (C-011, DIRECTIVE_034)** | New `tests/ci/test_charter_activation_routing.py` asserts the post-fix selection first and is proven red against the pre-fix router (recorded in the PR), plus per-part revert rows. |
| **Canonical sources** | `tests/release/ci_retirement_scrub.json` is the root authority; the registry row and the router filter are updated to transcribe it verbatim in the same commit. |
| **No gate weakening (Standing Order #5 / C-001)** | No assertion is removed, skipped or xfailed; the two test-side *registries* (`_DELIBERATELY_UNGATED_FILTER_GROUPS`, the fan-out wiring pin) are extended to register the new, legitimately wired group. |
| **Campsite cleaning (DIRECTIVE_025)** | The stale comment blocks that describe the non-src fan-out shape are updated to name the new member and its reason, so the next reader does not re-derive it. |
| **Pack tiers** | No `packs/**` content edit; only the pin lockfile path is named as a trigger. |
| **NO_FULL_HEAVY_SUITES_IN_MISSION** | Local verification runs the targeted CI-integrity files only; the full architectural battery is CI's job. |

No charter violations; `Complexity Tracking` stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-activation-shard-routing-01M68ZRA/
├── spec.md
├── research.md          # discovery + Phase 0 (decisions, evidence)
├── plan.md              # this file
├── data-model.md        # Phase 1: routing entities and invariants
├── quickstart.md        # Phase 1: local reproduction/verification commands
├── traces/              # approach.md, design-decisions.md, tooling-friction.md
└── tasks/               # /spec-kitty.tasks output
```

No `contracts/`: this mission defines no external interface (it changes CI
routing data consumed in-repo), so `meta.json` records `"contracts": "none"` with a
rationale instead of an empty directory.

### Source Code (repository root)

```
.github/
├── workflows/ci-router.yml          # dorny filter group + changes.outputs row
└── ci-module-registry.yml           # charter row roots += ledger floor (verbatim from scrub)

scripts/ci/
└── gate_selection.py                # ACTIVATION_STORE_MODULE_FANOUT + select_modules loop + __all__

tests/
├── release/ci_retirement_scrub.json # charter group roots += src/kernel/activation_ledger_store.py
├── ci/test_charter_activation_routing.py        # new: red-first routing pins
└── architectural/
    ├── test_gate_selection_authority.py         # fan-out wiring pin extension
    └── test_workflow_coherence.py               # deliberately-ungated group registry

docs/changelog/CHANGELOG.md          # [Unreleased] entry (#6336)
```

**Structure Decision**: single-project repo; the mission edits the CI routing data
plane (`scripts/ci`, `.github/`), its test guards (`tests/ci`, `tests/architectural`,
`tests/release`) and the changelog. No `src/` product code changes.

## Implementation Concern Map

> Implementation concerns are not work packages; `/spec-kitty.tasks` decides the WP
> shape. Concerns here describe the architectural areas the tasks must cover.

- **IC-01 — Router group declaration and outputs wiring.** Add `charter_activation`
  to `ci-router.yml`'s dorny filter block (three literals: the two activation-store
  files and the internal pin lockfile) and to `changes.outputs` with the standard
  run-all/unmatched fold. Keep it out of the `unmatched` union (non-src) and out of
  every job `if:` (ungated by design), and register it in
  `test_workflow_coherence._DELIBERATELY_UNGATED_FILTER_GROUPS`.
- **IC-02 — Module fan-out in the single selection authority.** Add
  `ACTIVATION_STORE_MODULE_FANOUT = {"charter_activation": {"charter"}}` to
  `scripts/ci/gate_selection.py`, export it, and union it in `select_modules`
  alongside `GROUP_MODULE_FANOUT` / `DEPENDENCY_MODULE_FANOUT` /
  `CLI_COMMAND_MODULE_FANOUT`; document why it cannot be a `FANOUT_GROUPS` member
  (census scope) in the table's own comment.
- **IC-03 — Ledger floor joins the charter group.** Add
  `src/kernel/activation_ledger_store.py` to the `charter` scrub group roots in
  `tests/release/ci_retirement_scrub.json` and transcribe it into the registry's
  `charter` row (and the router's `charter` filter, which the transcription guard
  compares to the scrub verbatim). Rationale: the file is the activation ledger's
  kernel floor (`tests/charter/activation/**` are its readers) and a src file may not
  live in the non-src group.
- **IC-04 — Red-first routing pins + guard registries.** New
  `tests/ci/test_charter_activation_routing.py` covering FR-002..FR-009: the three
  activation/pin paths select `charter`; the ledger floor selects `charter` *and*
  keeps `kernel`; the ledger reader stays selected; non-src/keep-fail-closed; no
  blast radius; router/scrub/registry transcription equality; and per-part revert
  rows proving each pin reds when its part is reverted. Extend the existing fan-out
  wiring pin in `test_gate_selection_authority.py`.
- **IC-05 — Changelog.** One `[Unreleased]` entry, bold impact-first lead with
  `(#6336)`, before/after, under 1,200 characters.

## Phase 0 — Outline & Research

`research.md` already carries the discovery decisions, the reproduction table and
the rejected alternatives (see its "Decisions" section). Phase 0 adds nothing new:
there is no unknown technology, no dependency decision (so the supply-chain section
is not applicable), and no NEEDS CLARIFICATION marker remains — the three
specify-interview decisions were resolved from the issue body and the spec.

## Phase 1 — Design & Contracts

- `data-model.md`: the routing entities (router filter group, outputs row, scrub
  group row, registry row, fan-out table row, module selection) and the invariants
  the guards enforce between them.
- No `contracts/`: `meta.json` records `"contracts": "none"` with a rationale (no
  external interface; the router YAML and the scrub JSON are the in-repo data
  contracts, and they are pinned by the existing architectural guards).
- `quickstart.md`: the local commands that reproduce and verify the routing answer
  (the same `select_modules` call CI makes) and the targeted pytest files.

## Complexity Tracking

No charter violations; not filled.
