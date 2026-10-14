# Implementation Plan: Durable derived consumer census for CI fan-out

**Branch**: `issue-6173-derived-consumer-census` | **Date**: 2026-10-13 | **Spec**: `spec.md`
**Input**: Mission specification from `kitty-specs/derived-consumer-census-01M4V5P5/spec.md`

## Summary

Replace the hand-maintained CI fan-out lists (`GROUP_MODULE_FANOUT` in
`scripts/ci/gate_selection.py` + the non-src router groups' module sets) with a
**derived consumer census**: a committed, regenerable artifact mapping each test
module → the `src/**`/`packs/**` path patterns its tests consume (static import/
read/string-literal scan **plus** runtime read-capture of resolver-driven opens).
From that census, `GROUP_MODULE_FANOUT`'s module sets are derived; the router
*globs* stay hand-authored (GitHub Actions requires literal YAML, transcription-
pinned) but are verified by a new red-first architectural gate that reds when a
census consumer's path would not select its module under the current
router+registry. The three historical pins are reproduced; a planted unrouted
consumer reds the gate; the derived routing's selected-shard cost delta is
measured on recent merged PR diffs; and the `charter` 7-shard long pole is either
shrunk by within-module file selection or carved to a named follow-up.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: stdlib `ast`, `pathlib`, `sys.addaudithook` (runtime
capture); existing `scripts.ci.gate_selection` (`load_router`,
`_registry_module_names`, `select_modules`, `GROUP_MODULE_FANOUT`); `yaml`/`json`
for artifact I/O. No new third-party dependency.
**Storage**: a committed census artifact (JSON) under `.github/` (beside
`ci-module-registry.yml` / `ci-shard-timings.json`, the CI-data home) or
`scripts/ci/` — decided in IC-1. Deterministic, sorted keys.
**Testing**: pytest; the new gate lives under `tests/architectural/` (its only
per-PR home is the heavy battery, like the other routing-authority gates); the
census script's unit tests live under `tests/ci/` (the `ci` module). `make
test-fast` + `tests/ci` + the specific named routing lockstep gate files + the
new gate's module (per CLAUDE.md test policy + `NO_FULL_HEAVY_SUITES_IN_MISSION`).
**Target Platform**: CI (GitHub Actions Linux) + local dev; the census must run
offline and deterministically.
**Project Type**: single (CI-infrastructure tooling in `scripts/ci/` + tests).
**Performance Goals**: census regeneration < 2 min (NFR-004); the gate is a
static read of the committed artifact (no test execution, battery-fast).
**Constraints**: no `src/**` behaviour change (C-001); no size/length ratchet
gate (C-002); no scrub/registry row for the non-src fan-out groups (C-003);
router globs stay hand-authored (C-004); module-set agnostic / #6164-robust
(NFR-002); no loosened gate (NFR-001).
**Scale/Scope**: 21 registry modules; ~177 tracked `packs/built-in/missions`
files; the four non-src fan-out groups; ~15 test_dirs on the aggregate rows.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** (DIRECTIVE_044): the census becomes the ONE
  source for "module consumes path"; the fan-out module sets derive from it
  rather than being a second hand-curated map. PASS (reconciles, does not add a
  rival authority — the router globs stay the one path→group source, the
  registry the one module inventory).
- **Architectural gate discipline** (DIRECTIVE_043, Standing Order #5): the new
  gate is a non-vacuous call-site gate (concrete census floor + a
  planted-consumer self-mutation positive control). It starts empty-allowlist
  (no baseline entry — there is no allowlist). PASS.
- **ATDD-first** (C-011): the gate's red-first provenance is proven — the three
  pins red against a router with their globs stripped, and the planted consumer
  reds the gate. The gate is committed before the derivation flips
  `GROUP_MODULE_FANOUT`. PASS.
- **Canonical sources** (DIRECTIVE_044): reuse `gate_selection.load_router` /
  `_registry_module_names` / `select_modules`; do not re-derive routing. PASS.
- **No full heavy suites in mission work** (`NO_FULL_HEAVY_SUITES_IN_MISSION`):
  run the SPECIFIC named architectural gate files, never the bare
  `tests/architectural/` sweep. PASS (recorded in tasks' validation).
- **Terminology**: "routing" is always qualified (placement/consumer sense);
  "Mission" canon respected. PASS.
- **Git/workflow** (DIRECTIVE_045): draft PR first, operator merges. PASS.

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/derived-consumer-census-01M4V5P5/
├── spec.md
├── plan.md                 # this file
├── research/
│   └── code-grounding.md   # committed first (read-only grounding)
├── data-model.md           # census artifact schema (Phase 1)
├── analysis/               # cost-delta measurement record (Phase 1/impl)
└── tasks/                  # WP files (/spec-kitty.tasks)
```

### Source Code (repository root)

```
scripts/ci/
├── gate_selection.py            # MODIFIED: GROUP_MODULE_FANOUT derived from the census
├── consumer_census.py           # NEW: build/load the census (static + runtime capture)
└── consumer_census_cost.py      # NEW: selected-shard cost-delta over recent PR diffs

.github/
└── ci-consumer-census.json      # NEW: committed, regenerable census artifact

tests/
├── architectural/
│   └── test_consumer_census_routing.py   # NEW: red-first routing gate (+ 3 pins + planted consumer)
└── ci/
    ├── test_consumer_census.py           # NEW: census-builder unit tests (determinism, runtime capture)
    └── test_consumer_census_cost.py      # NEW: cost tool unit tests
```

**Structure Decision**: single-project CI-infrastructure tooling. The census
builder + cost tool live in `scripts/ci/` (the `ci` module, test_dirs
`tests/ci`). The routing gate lives in `tests/architectural/` because its only
per-PR home is the heavy battery, matching `test_gate_selection_authority.py` /
`test_ci_router_transcription_guards.py`. The committed artifact lives in
`.github/` beside the registry and shard timings (confirmed in IC-1).

## Complexity Tracking

*No Charter Check violations — section intentionally empty.*

## Implementation Concern Map

> Concerns are NOT work packages; `/spec-kitty.tasks` translates them into WPs.

- **IC-1 — Census model & artifact.** The schema (module → list of
  `{path_or_glob, provenance}` with provenance in `{static-import, static-read,
  static-literal, runtime}`), the artifact location (`.github/ci-consumer-census.json`),
  determinism (sorted, stable), and the `load_census()` reader. The module
  universe and path→module attribution reuse the registry (`test_dirs` +
  canonical mirror) and `load_router`, so a #6164 module-set change flows through.
  (FR-001, FR-004, NFR-002, NFR-003.)
- **IC-2 — Static consumer detection.** AST + text scan over each module's
  `test_dirs`: imports of `src/**` modules, `Path(...)`/`read_text`/`open`
  arguments and string-literals naming `src/**` or `packs/**` paths, resolved to
  repo-relative paths/globs and attributed to the owning module(s). (FR-002.)
- **IC-3 — Runtime read-capture.** A bounded, offline harness that exercises the
  resolver-driven codepaths (the prompt/template/manifest resolution the
  `tests/next`/`tests/runtime`/`tests/charter_offering` consumers trigger) under
  an `open`/`is_file` audit hook, recording `src/**`/`packs/**` opens attributed
  to the triggering module. Canonical validation: `tests/next` resolves
  `packs/.../mission-steps/software-dev/research/prompt.md`. (FR-003, NFR-004.)
- **IC-4 — Red-first routing gate.** `test_consumer_census_routing.py`: for each
  census `(module, path)`, assert `select_modules([path])` ⊇ `{module}`; red on a
  planted unrouted consumer (positive control); reproduce the three pins and prove
  each reds against a router with its glob stripped (red-first). (FR-005, FR-006,
  FR-007, NFR-001.)
- **IC-5 — Derived fan-out.** Replace the hardcoded `GROUP_MODULE_FANOUT` dict
  with a loader that derives each non-src group's module set from the census
  (paths matching the group's router globs → consuming modules not already base-
  selected). The existing `test_group_module_fanout_is_wired` pins stay green as a
  cross-check. No scrub/registry row added (C-003); router globs untouched (C-004).
  (FR-008, NFR-001.)
- **IC-6 — Cost delta + within-module selection.** `consumer_census_cost.py`
  measures the selected-shard count per recent merged PR diff and the delta vs.
  pre-census routing; recorded in `analysis/` and the PR. Within-module file
  selection for `charter` (`tests/charter_offering/missions/*` +
  `test_*prompt*`) lands if tractable, else a named follow-up issue. (FR-009, FR-010.)

## Phase 0 — Research

Done in `research/code-grounding.md` (committed): the mechanism verbatim, the
runtime-resolution trace, the lockstep gates, the cost picture, the #6164
collision, churn. Open question resolved there: derive the module sets, keep the
router globs hand-authored + census-verified.

## Phase 1 — Design

- `data-model.md`: the census artifact JSON schema + provenance vocabulary +
  determinism contract.
- Confirm the derivation breaks no circularity: the gate checks census→routing
  via `select_modules` against the **router globs** (independent authority for
  path→group), so deriving the fan-out from the census does not make the gate
  check itself vacuously; an unrouted path (matching no group) still reds.

## Risks

- **Circularity** — if the gate checked the census against a fan-out derived from
  the same census, it would be vacuously green. Mitigation: the gate's authority
  is the router *globs* (path→group), not the derived module sets; a census path
  matching no group reds regardless of derivation. (Validated by the planted
  consumer.)
- **Runtime capture flakiness** — audit-hook capture must be deterministic and
  offline. Mitigation: a fixed, enumerated set of resolver invocations; sorted
  output; a unit test asserting reproducibility (NFR-003).
- **#6164 lockstep churn** — shared files (`gate_selection.py`, maybe the
  registry) may conflict on rebase. Mitigation: keep the diff confined to the
  census mechanism; re-run the lockstep gates on rebase; never take/revert #6164's
  module rows.
- **Charter 7-shard cost** — within-module selection is the only lever; if it is
  too large for this PR it is carved to a follow-up, not half-built (FR-010).
