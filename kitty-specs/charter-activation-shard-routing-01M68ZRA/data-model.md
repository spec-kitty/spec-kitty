# Data Model — Charter Activation Shard Routing (#6336)

This mission has no runtime data model: it changes the CI routing/selection data
plane. The entities below are the data artifacts the change touches and the
invariants the existing architectural guards enforce between them. Every invariant
below is already guarded; the mission must keep all of them true while adding one
row to each of three of them.

## Entities

### E1 — Router filter group (`ci-router.yml`, dorny `changes` block)

Authority 1 of the router's two authorities: `group -> globs[]`.

| Field | Meaning | Constraint |
| --- | --- | --- |
| `group` | Routing-group name | unique within the block; lowercase snake_case |
| `globs[]` | Repository-relative glob(s) | must match ≥1 tracked path (dead-glob guard); a group's globs == its scrub `groups[].roots` verbatim for every scrub group |
| src-backed? | at least one `src/`-prefixed glob | src-backed groups are job-gated and join the FR-004 `unmatched` union; non-src groups do neither |

**New row**: `charter_activation` → `.kittify/charter/charter.yaml`,
`.kittify/charter/activation.yaml`, `packs/internal.source.yaml`. Non-src (no
`src/` glob) by construction.

### E2 — `changes.outputs` row (`ci-router.yml`)

One output per routing group, fold shape
`(inputs.mode == 'full' || steps.unmatched.outputs.unmatched == 'true') && 'true' || steps.filter.outputs.<group>`.
**Invariant**: the outputs block (minus `unmatched`) equals the set of filter
routing groups (`test_changes_outputs_cover_every_routing_group`).

### E3 — Retirement-scrub group row (`tests/release/ci_retirement_scrub.json` `groups[]`)

The single data source for a module's roots, cov targets and census evidence; the
module registry consumes `groups[]` rows verbatim.

| Field | Meaning | Constraint |
| --- | --- | --- |
| `group` | equals the module-registry `module` name | registry covers every scrub group, no gaps, no extras |
| `roots[]` | the group's path globs | each must be live on disk; the router filter transcribes them verbatim |
| `cov_targets[]` | dotted coverage subjects | must resolve to live src; dotted form only |

**Change**: `charter.roots` gains `src/kernel/activation_ledger_store.py`.

### E4 — Module registry row (`.github/ci-module-registry.yml` `modules[]`)

The `module-tests` matrix unit: `module`, `roots` (verbatim from E3), `cov_targets`,
`tier`, `shard_count`, optional explicit `test_dirs`.

**Change**: the `charter` row's `roots` gains the same single file. `test_dirs`
(`tests/charter`, `tests/charter_offering`), `tier` and `shard_count: 7` are
unchanged; no new row is added.

### E5 — Module fan-out row (`scripts/ci/gate_selection.py`)

A hand-authored `group -> frozenset[module]` map consulted by `select_modules` when
the group matched. Three existing tables: `GROUP_MODULE_FANOUT` (census-backed),
`DEPENDENCY_MODULE_FANOUT` (derived), `CLI_COMMAND_MODULE_FANOUT` (non-census).

| Constraint | Why |
| --- | --- |
| keys must be router filter groups | `test_group_module_fanout_is_wired` |
| targets must be registry module names | same |
| members of `FANOUT_GROUPS` must each derive ≥1 module from the consumer census | `tests/ci/test_fanout_derivation.py::test_derivation_is_non_vacuous` |

**New row**: `ACTIVATION_STORE_MODULE_FANOUT = {"charter_activation": {"charter"}}`,
kept out of `FANOUT_GROUPS` for the same documented reason as
`CLI_COMMAND_MODULE_FANOUT`: the census records only resolved `src/**` imports and
`packs/built-in/missions/**` runtime reads, so a `.kittify`/pin group derives an
empty set.

### E6 — Module selection (the answer)

`select_modules(changed_paths) -> frozenset[module]` = (matched groups ∩ registry
modules) ∪ fan-out targets of matched groups ∪ test-path owners, or **all** modules
when `mode == "full"` or the FR-004 catch-all tripped.

## Invariants that must hold after the change

| ID | Invariant | Guard |
| --- | --- | --- |
| I1 | Router filter globs == scrub roots, verbatim and in order, for every scrub group | `test_ci_router_transcription_guards.py::test_router_src_filters_derive_from_scrub_verbatim` |
| I2 | `changes.outputs` == router routing groups | `::test_changes_outputs_cover_every_routing_group` |
| I3 | The `unmatched` union == the src-backed groups | `::test_unmatched_union_covers_every_src_backed_group` |
| I4 | Every src-backed group is referenced by a job `if:` | `test_ci_quality_path_filters.py::test_ci_router_two_authority_every_src_group_is_job_gated` |
| I5 | Every filter group is job-gated or registered as deliberately ungated | `test_workflow_coherence.py::unconsumed_filter_groups` |
| I6 | Every filter glob matches ≥1 tracked path | `test_workflow_coherence.py::test_every_restored_filter_glob_is_live` |
| I7 | Registry rows == scrub rows, verbatim | `test_module_shard_registry.py::test_registry_consumes_scrub_verbatim_no_divergent_rescrub` |
| I8 | Registry covers every scrub group, no extras; test dirs claimed once | `test_module_shard_registry.py` (coverage + claim guards) |
| I9 | Heavy battery `if:` == src-backed groups ∪ `HEAVY_BATTERY_NON_SRC_GROUPS` | `test_ci_integrity_oracle_nonvacuous.py` |
| I10 | Every `FANOUT_GROUPS` member derives ≥1 census module | `tests/ci/test_fanout_derivation.py` |
| I11 | Fan-out keys are filter groups; targets are registry modules | `test_gate_selection_authority.py::test_group_module_fanout_is_wired` |
| I12 | An unmapped `src/**` change forces run-all; docs-only selects zero modules | `test_gate_selection_authority.py` fail-closed pins |
| I13 | No census pack consumer is unrouted | `test_consumer_census_routing.py` |

## State / selection transitions

```
changed paths ──► _match_groups (router filters, probe excluded)
                    │
                    ├─ matched ⊇ {charter_activation} ──► + fan-out {charter}
                    ├─ matched ∩ src_backed_groups == ∅ and any src/** ──► run-all
                    └─ tests/** only ──► registry test-path owners (mirror)

select_modules = matched∩modules ∪ fan-out(matched) ∪ test-path owners, or all modules on run-all
```

There is no persisted state and no lifecycle transition; the "state" is the
changed-path set, which is per-run.
