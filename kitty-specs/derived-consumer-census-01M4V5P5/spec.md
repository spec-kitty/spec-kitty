# Mission Specification: Durable derived consumer census for CI fan-out

**Mission Branch**: `issue-6173-derived-consumer-census`
**Created**: 2026-10-13
**Status**: Draft
**Input**: Issue #6173 (task C of #6166) — replace the hand-maintained CI fan-out lists with a derived consumer census so a new unrouted test consumer reds a gate instead of reddening `main` later.

## Context

CI selects which per-PR test modules to run by **routing** (placement / consumer
sense) a changed `src/**` or `packs/**` path to the modules whose tests consume
it. Paths consumed *indirectly* — a test that reads a mission-step `prompt.md`
through the runtime resolver without naming it, or imports
`cli/commands/lifecycle.py` from another module's test tree — are fanned out by
**hand-maintained** lists: `GROUP_MODULE_FANOUT` in `scripts/ci/gate_selection.py`
and the non-src router groups in `.github/workflows/ci-router.yml`. Those lists
drift: the next unrouted consumer reaches `main` before anyone edits the list
(three such regressions on 2026-10-13 — #6153/#6156/#6161). The durable fix is a
**derived consumer census** that is the single authority for "module M consumes
path P", from which the fan-out is derived and against which a red-first gate
fires when a consumer is unrouted.

Grounding: `research/code-grounding.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Census the consumers a grep misses (Priority: P1)

A maintainer runs one committed, regenerable census script that reports, for
every test module, the `src/**` and `packs/**` paths its tests consume — both by
static import/file-read analysis and by capturing runtime-resolved reads a grep
census misses (the `tests/next` prompt case, where the module resolves the pack
prompt through the CLI and never names its path).

**Why this priority**: The census is the data every other slice derives from;
without the runtime-capture half it would miss exactly the consumer class
(#6156) that made this mission necessary.

**Independent Test**: Run the census script; assert its artifact records
`tests/next → packs/built-in/missions/mission-steps/software-dev/research/prompt.md`
(runtime-resolved), `tests/agent → .../cli/commands/lifecycle.py` (static import),
and `tests/dossier → .../expected-artifacts.yaml` (static read).

**Acceptance Scenarios**:

1. **Given** the committed census artifact, **When** the census script is
   re-run on the current tree, **Then** it reproduces the artifact byte-for-byte
   (deterministic, regenerable).
2. **Given** a module whose tests resolve a pack prompt only at runtime,
   **When** the census runs, **Then** that pack path appears under that module
   with `runtime` provenance (a pure static grep would omit it).

### User Story 2 - Red the gate when a consumer is unrouted (Priority: P1)

A maintainer adds a new test that consumes a `src/**` or `packs/**` path its
module would not be selected for under the current router+registry. An
architectural gate reds in that PR — rather than letting the gap reach `main`
and surface on an unrelated PR.

**Why this priority**: This is the behaviour #6173 exists to deliver — closing
the defect class by construction instead of by hand-editing a list after a
regression.

**Independent Test**: Plant a synthetic census entry for a path that matches no
routing group; assert the gate's checker reports a violation. Confirm the three
historical pins are satisfied (green) now and would red against a router with the
corresponding globs stripped.

**Acceptance Scenarios**:

1. **Given** the census and the current router+registry, **When** the gate runs,
   **Then** every census `(module, path)` routes to that module via
   `select_modules` and the gate is green.
2. **Given** a planted census consumer whose path matches no routing group,
   **When** the gate runs, **Then** the gate reds naming the module and the
   unrouted path.
3. **Given** the three historical paths (`prompt.md`, `lifecycle.py`,
   `expected-artifacts.yaml`), **When** the router globs that route them are
   stripped, **Then** the gate reds for each (red-first provenance).

### User Story 3 - Derive the fan-out and record the cost (Priority: P2)

The hand-maintained module sets in `GROUP_MODULE_FANOUT` are derived from the
census (no longer hand-curated), the derived routing's selected-shard cost delta
is measured on recent merged PR diffs, and the `charter` 7-shard long pole on a
`mission_pack_content` edit is either shrunk by within-module file selection or
carved to a named follow-up.

**Why this priority**: Deriving the module sets removes the drift source; the
cost measurement and within-module selection are the "also enables" of #6173 and
the operator-accepted trade-off from #6174.

**Independent Test**: Assert the derived `GROUP_MODULE_FANOUT` equals the known
sets the existing authority gate pins; run the cost tool over the last N merged
PR diffs and read the recorded delta.

**Acceptance Scenarios**:

1. **Given** the committed census, **When** `GROUP_MODULE_FANOUT` is loaded,
   **Then** its module sets are those derived from the census (the existing
   `test_group_module_fanout_is_wired` pins stay green).
2. **Given** recent merged PR diffs, **When** the cost tool runs, **Then** it
   reports the selected-shard count per diff and the delta vs. the pre-census
   routing, recorded in the PR.

### Edge Cases

- A module consumes a path matching **no** router group → the gate reds (the
  whole point); the remedy is a new router glob (hand-authored, transcription-
  pinned), never a silent list edit.
- A consumed path is already covered by the base src-routing or the tests-only
  mirror → no fan-out entry needed; the census must not fabricate a redundant one.
- #6164 removes a module row / router group under the mission → the census and
  gate read `_registry_module_names()` / `load_router()` at runtime, so a removed
  module flows through without a hardcoded list to edit.
- The runtime capture must be deterministic and offline (no network, no flakiness)
  so the committed artifact is reproducible in CI and locally.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Census script over test modules | As a maintainer, I want a script that reports, per test module, the `src/**`+`packs/**` paths its tests consume, so the fan-out has a derived source. | High | Open | [build] | no |
| FR-002 | Static consumer detection | As a maintainer, I want imports, file reads and path string-literals in each module's `test_dirs` detected, so statically-named consumers are captured. | High | Open | [build] | no |
| FR-003 | Runtime read-capture | As a maintainer, I want resolver-driven opens of `src/**`/`packs/**` captured and attributed to the consuming module, so a grep-invisible consumer (the `tests/next` prompt case) is captured. | High | Open | [build] | no — paired with the `tests/next` positive control (the path is absent from a static-only census) |
| FR-004 | Committed, regenerable census artifact | As a maintainer, I want the census emitted to a committed artifact that re-runs reproduce, so the gate reads a deterministic SSOT. | High | Open | [build] | no |
| FR-005 | Red-first routing gate | As a maintainer, I want an architectural test that reds when a census consumer's path would not select its module under the current router+registry, so an unrouted consumer reds a PR instead of `main`. | High | Open | [build] | no — paired with the planted-unrouted-consumer positive control (FR-006) |
| FR-006 | Planted-consumer non-vacuity | As a maintainer, I want the gate proven to red on a planted unrouted consumer, so the gate is not vacuously green. | High | Open | [build] | no |
| FR-007 | Reproduce the three historical pins | As a maintainer, I want the census+gate to reproduce `prompt.md → next`, `lifecycle.py → agent`, `expected-artifacts.yaml → dossier`, so the known regressions are guarded. | High | Open | [ratchet] | no — each pin reds against a router with its routing glob stripped |
| FR-008 | Derive `GROUP_MODULE_FANOUT` from the census | As a maintainer, I want the hand-maintained module sets derived from the census, so they cannot drift from the real consumers. | High | Open | [build] | no |
| FR-009 | Cost-delta measurement on recent PRs | As a maintainer, I want the derived routing's selected-shard count measured on recent merged PR diffs and recorded, so the CI-cost impact is known. | Medium | Open | [build] | no |
| FR-010 | Charter within-module selection or carved follow-up | As a maintainer, I want the `charter` 7-shard cost on a `mission_pack_content` edit shrunk by within-module file selection, or carved to a named follow-up if too large for this PR. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No loosened gate | No existing architectural/lockstep gate is weakened or deleted; the three-way lockstep (router/registry/scrub) and `test_group_module_fanout_is_wired` stay green and non-vacuous. | Reliability | High | Open |
| NFR-002 | Module-set agnostic | The census/gate derive the module universe from `_registry_module_names()` and `load_router()` at runtime; no hardcoded module list, so a #6164 module-set change flows through automatically. | Maintainability | High | Open |
| NFR-003 | Deterministic & offline census | The census script is deterministic and network-free; a re-run on an unchanged tree reproduces the committed artifact exactly. | Reliability | High | Open |
| NFR-004 | Bounded census runtime | The runtime-capture phase runs a bounded, representative set of resolver paths (not the full ~17k-test suite); it completes in CI/local budget (target < 2 min). | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No src behaviour change | No `src/**` product-code behaviour changes; CI-infrastructure + tests only. | Technical | High | Open |
| C-002 | No size/length ratchet gate | Do not add a size/length ratchet gate (operator ruling). | Technical | High | Open |
| C-003 | No scrub/registry row for fan-out groups | The non-src fan-out groups keep the #6131 precedent: router filter + outputs + derived fan-out only; no scrub or registry row added for them. | Technical | High | Open |
| C-004 | Router globs stay hand-authored | The dorny filter globs stay literal YAML (GitHub Actions requirement), transcription-pinned; the census verifies they cover all consumers but does not generate them. | Technical | Medium | Open |

### Key Entities

- **Consumer census**: a committed artifact mapping each test module → the set
  of `src/**`/`packs/**` path patterns its tests consume, each tagged with
  provenance (`static-import` / `static-read` / `runtime`).
- **Fan-out derivation**: the function mapping each non-src router group → the
  modules the census shows consume a path matching that group's globs (and that
  the base src-routing does not already select).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The census reproduces the three historical pins (`prompt.md → next`, `lifecycle.py → agent`, `expected-artifacts.yaml → dossier`). — [ratchet] · no-op passable: no (each reds against a router with its glob stripped)
- **SC-002**: A planted unrouted consumer reds the new gate. — [build] · no-op passable: no
- **SC-003**: The hand-maintained fan-out module sets are replaced by (derived from) the census without loosening any lockstep gate (`test_group_module_fanout_is_wired` and the transcription lockstep stay green). — [build] · no-op passable: no
- **SC-004**: The derived-routing selected-shard cost delta is measured on recent merged PR diffs and recorded in the PR. — [build] · no-op passable: no
