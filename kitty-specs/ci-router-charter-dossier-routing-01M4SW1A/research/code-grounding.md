---
title: Code grounding — CI router does not select charter/dossier for an expected-artifacts.yaml edit
mission: ci-router-charter-dossier-routing-01M4SW1A
issue: 6125
updated: 2026-10-13
type: explanation
audience: agentic-framework-core-team
author: Stijn Dejongh (via governed agent)
---

# Code grounding (read-only)

Empirical confirmation of issue #6125 on current `main` (`e872e99`), plus a map of
every gate/guard that pins the surfaces this mission will edit. **No product code is
in scope.** Every claim below was run against this checkout, not inferred.

## 1. The two-authority router model (confirmed)

`scripts/ci/gate_selection.py` is the single importable routing authority. It parses
two hand-authored authorities straight out of `.github/workflows/ci-router.yml`:

1. the dorny `changes` **filter** block — `group -> globs[]` (path → group), and
2. the job `if: needs.changes.outputs.<group>` **gates** — group → job.

`select_modules(paths)` returns `matched_groups ∩ registry_module_names` (module
universe = `.github/ci-module-registry.yml` `modules[].module`), unioned with a
tests-dir mirror (`_modules_for_test_paths`) for `tests/**`-only diffs. `mode="full"`
or an unmatched `src/**` diff (`unmatched_src`, FR-004) forces run-all.

The module registry consumes `tests/release/ci_retirement_scrub.json` **verbatim**
(roots + cov_targets), and the router filter block is pinned to the same scrub roots —
so registry, scrub, and router filter are ONE source in three transcriptions.

## 2. The gap, confirmed empirically

Run on this checkout (`python scripts/ci/gate_selection.py` API):

```
registry module universe (20): agent, auth, charter, ci, cli, consolidation,
  core_misc, execution_context, glossary, kernel, lanes, missions, next, post_merge,
  release, review, specify_cli_runtime, status, unit, upgrade

manifest software-dev: select_modules -> []   matched_groups=['corpus'] unmatched_src=False
manifest research:     select_modules -> []   matched_groups=['corpus'] unmatched_src=False
manifest plan:         select_modules -> []   matched_groups=['corpus'] unmatched_src=False
manifest documentation:select_modules -> []   matched_groups=['corpus'] unmatched_src=False

dossier source edit (src/specify_cli/dossier/manifest.py):
  select_modules -> ALL 20 modules   matched_groups=[] unmatched_src=True

charter in registry: True | dossier in registry: False
```

Interpretation:

- A mission-manifest edit (`packs/built-in/missions/*/expected-artifacts.yaml`) matches
  only the non-module `corpus` group (`packs/**`). `unmatched_src=False` (the path is
  not under `src/`), so there is **no** fail-closed run-all. → `select_modules` returns
  **`[]`** for all four manifests: neither `tests/charter` (+`tests/charter_offering`)
  **nor** `tests/dossier` runs per-PR. This is exactly the #6125 red-main hazard.
- `dossier` is **not** a registry module. A `src/specify_cli/dossier/**` edit matches no
  group → `unmatched_src=True` → run-all (all 20 modules), yet `tests/dossier` is in no
  module's `test_dirs`, so it **still never runs per-PR** (run-all runs the module
  matrix; `tests/dossier` isn't in it). `tests/dossier` + `tests/specify_cli/dossier`
  are nightly-only (`out_of_matrix_test_dirs`, `ci-nightly.yml` shards 3/4).

Baseline: the named gate suites are green on `main`
(`tests/architectural/test_gate_selection_authority.py`,
`test_module_shard_registry.py`, `test_retirement_scrub.py`,
`test_out_of_matrix_evidence.py`, `test_ci_router_transcription_guards.py`,
`test_ci_quality_path_filters.py`, `test_ci_corpus_trigger_completeness.py`,
`tests/ci/test_ci_module_wiring.py` — exit 0).

## 3. Manifest consumers (why charter + dossier are the right modules)

`packs/built-in/missions/**/expected-artifacts.yaml` is produced by
`charter.offering.missions` (`src/charter/offering/missions/repository.py`) and consumed
by:

- the **charter** module — `src/charter/activation/{org_expected_artifacts,manifest_loader}.py`
  (covered by `tests/charter` + `tests/charter_offering`), and
- the **dossier** consumer — `src/specify_cli/dossier/manifest.py` (covered by
  `tests/dossier` + `tests/specify_cli/dossier`; `tests/dossier/fixtures/expected_artifacts_typo.yaml`
  shows the manifest-shape coupling directly).

A manifest-shape edit routinely moves assertions in `tests/dossier` and can move
assertions in `tests/charter`/`tests/charter_offering` (issue #6125, PR #5945 had three
stale `tests/dossier` pins). So the correct per-PR selection for a manifest edit is
**`charter` + `dossier`** — not `missions`, and not broader (non-goal).

## 4. Guard/gate map (what the change must satisfy)

| Surface | Guard (file::test) | Invariant |
|---|---|---|
| registry ↔ scrub bijection | `test_module_shard_registry.py::test_registry_covers_every_scrub_group_no_gaps_no_extras` | `{registry modules} == {scrub groups}` exactly |
| registry verbatim | `test_module_shard_registry.py::test_registry_consumes_scrub_verbatim_no_divergent_rescrub` | row `roots`/`cov_targets` ordered-equal the scrub group's |
| router verbatim | `test_ci_router_transcription_guards.py::test_router_src_filters_derive_from_scrub_verbatim` | for every group in `scrub ∩ router`, router filter globs **ordered-equal** scrub `roots`; `router.src_backed_groups == scrub src-backed set`; no scrub group missing from the filter block |
| changes.outputs cover | `...::test_changes_outputs_cover_every_routing_group` | `changes.outputs − {unmatched} == router.routing_groups` |
| unmatched union | `...::test_unmatched_union_covers_every_src_backed_group` | the `unmatched` loop unions exactly `router.src_backed_groups` |
| every src group gated | `test_ci_quality_path_filters.py::test_ci_router_two_authority_every_src_group_is_job_gated` | every src-backed filter group is referenced by some job `if:` |
| claim-once / out-of-matrix | `test_module_shard_registry.py::test_every_test_directory_is_claimed_once_or_recorded_out_of_matrix` + `test_registry_test_dirs_are_pairwise_non_nested` | a test dir is claimed by exactly one row **xor** recorded out-of-matrix; test_dirs pairwise non-nested |
| test_dirs exist | `...::test_declared_test_dirs_exist_and_are_directories` | each declared `test_dirs` entry is an existing dir |
| tree reachable (INV-2) | `test_gate_selection_authority.py::test_every_registry_module_test_tree_is_reachable` | each row's `test_dirs` (or `tests/{module}`) exists on disk, routes to ≥1 module, and (explicit-test_dirs rows) routes back to itself. **Uses `test_dirs`, not `roots` mirrors** — a non-`/**` root with a nonexistent mirror is harmless (cf. `ci`'s `.github/workflows/**`). |
| shard-timings measured | `test_ci_module_wiring.py::test_registry_ci_row_is_measured_not_guessed` (pattern); `test_module_length_agreement.py::test_*_agrees_with_live_collection` (strict only under `SPEC_KITTY_STRICT_SHARD_TIMINGS=1`, i.e. the scheduled `ci-shard-recapture.yml`); skew ≤20% `test_module_shard_registry.py::test_inter_shard_skew_within_twenty_percent` | `module_test_count[m] == len(module_test_durations[m])`, provenance `producer == scripts/ci/capture_shard_timings.py`; shard_count=1 trivially passes skew |
| corpus golden | `test_gate_selection_authority.py::test_corpus_only_diff_selects_zero_code_shards` | `select_gates(["packs/built-in/missions/foo.md"])` → zero code shards, not unmatched. **`foo.md` must NOT match the manifest glob** → use the file-specific glob |
| golden lane-set | `test_ci_module_wiring.py::test_golden_non_prose_pr_lane_set_is_byte_identical_to_today` (+ other `test_golden_*`) | re-derive from live `ci-router.yml`; **no committed golden fixture file** — they stay green as long as consolidation/docs/arch contexts evaluate unchanged |

Derived surfaces: **no generator reads the registry/router/scrub** (`spec-kitty regen
--check` regenerates pack/command artifacts only — unaffected). The nightly interpreter
roster `tests/architectural/_interpreter_shard_roster.py` already enumerates both dossier
dirs (shard 3 `tests/specify_cli/dossier`, shard 4 `tests/dossier`); it needs updating
**only if the dirs are moved/renamed** (they are not).

`dossier` source: `src/specify_cli/dossier/` is a real 9-module package
(`manifest.py`, `indexer.py`, `reconciler.py`, `snapshot.py`, `hasher.py`, `events.py`,
`models.py`, `rebaseline.py`, `__init__.py`). Tests: `tests/dossier/` (13 files) +
`tests/specify_cli/dossier/test_integration.py` — ~399 collected under
`-m "not performance and not stress"` (the capture selection).

## 5. Design decision + a flagged conflict with the dispatch brief

**Chosen fix (canonical): mint a real `dossier` module, and route the manifest glob
through the `charter` and `dossier` groups in all three authorities in lockstep.**

The operator brief suggested routing the manifest DATA glob via the **router filter
group only** and keeping registry/scrub `roots` **src-only** (to avoid
`_canonical_test_mirror` mapping a broad `packs/built-in/missions/**` → `tests/missions`
and polluting tests-only mirror routing).

That prescription is **infeasible under the router verbatim guard**
(`test_router_src_filters_derive_from_scrub_verbatim`): for any group present in both
the scrub `groups[]` and the router filter block, the router globs must be
**ordered-equal** to the scrub `roots`. `charter` and a `dossier` module are both scrub
groups, so their router filter globs cannot carry any glob that is not also a scrub
`root`. To make `select_modules` pick the `charter`/`dossier` **modules** for a manifest
edit, the group itself must match the path — which requires the glob in the scrub root
too. A router-only extra glob on either group reds the verbatim guard.

The honest, guard-satisfying path is therefore to add the **file-specific** glob
`packs/built-in/missions/**/expected-artifacts.yaml` to the `charter` and `dossier`
groups in **scrub roots + registry roots + router filter**, in lockstep (ordered
append). This is exactly the `ci`-group precedent (a module whose scrub/registry/router
roots include non-`src/` paths: `scripts/ci/**`, `.github/workflows/**`, whose mirror
`tests/workflows` does not exist and harms nothing).

The brief's mirror-pollution concern is **real but only bites the broad glob**
(`packs/built-in/missions/**` → `tests/missions`). The file-specific glob maps to
`_canonical_test_mirror(...) == "tests/expected-artifacts"`, a directory that does not
exist, so no real test path is ever within it and `_modules_for_test_paths` never
mis-routes. `test_corpus_only_diff_selects_zero_code_shards` uses `foo.md`, which the
file-specific glob does not match, so that golden stays green.

This deviation from the brief is recorded here and will be called out in the PR, per
"the charter wins over this prompt; flag any conflict" and "you MAY take a materially
cheaper honest path — justify in the PR."

## 6. Change surface (atomic, lockstep)

1. `tests/release/ci_retirement_scrub.json` — add a `dossier` group
   (`roots: ["src/specify_cli/dossier/**", "packs/built-in/missions/**/expected-artifacts.yaml"]`,
   `cov_targets: ["specify_cli.dossier"]`, `census_evidence`); append the manifest glob
   to the existing `charter` group's `roots`.
2. `.github/ci-module-registry.yml` — add a `dossier` module row (roots/cov_targets
   **verbatim** from scrub, `tier: standard`, measured `shard_count`,
   `test_dirs: [tests/dossier, tests/specify_cli/dossier]`); append the manifest glob to
   the `charter` row's `roots` (verbatim); remove `tests/dossier` and
   `tests/specify_cli/dossier` from `out_of_matrix_test_dirs` (claim-once).
3. `.github/workflows/ci-router.yml` — append the manifest glob to the `charter` filter
   group; add a `dossier` filter group (verbatim the scrub roots); add the `dossier`
   `changes.outputs` line; add `dossier` to the `unmatched` loop; OR
   `needs.changes.outputs.dossier == 'true'` into the heavy-battery `if:`.
4. `.github/ci-shard-timings.json` — real measured capture via
   `python scripts/ci/capture_shard_timings.py --module dossier --write`.
5. Red-first parity test (ATDD) pinning `select_modules(manifest) ⊇ {charter, dossier}`
   for all four manifests — RED on `origin/main`, GREEN after.

Non-goals (held): no router-design restructure; no selection broadening beyond
charter+dossier for manifest edits; no product-code changes; no new size/length ratchet.
