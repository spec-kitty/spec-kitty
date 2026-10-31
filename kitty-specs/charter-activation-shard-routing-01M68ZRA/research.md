# Discovery / Research — charter-activation-shard-routing (#6336)

Discovery step for a `software-dev` mission (no research-mission templates).
Everything below was gathered on current `main` (`35318ef51c`) before planning.

## Issue grounding

- **Issue**: spec-kitty/spec-kitty#6336, `priority:P2`, `domain:ci`, open,
  unassigned at claim time. Follow-up to #6333 (PR #6334 fixed the parity test
  itself but deliberately did not widen the trigger).
- **Two maintainer amendments in the thread supersede parts of the body**:
  1. 2026-10-19 (`stijn-dejongh`, from #6480/#6483): once #6451 landed,
     `packs/internal/` is untracked and a `packs/internal/**` root matches no PR
     diff; the live trigger is the pin lockfile `packs/internal.source.yaml`.
     `packs/internal/**` must not be used as a router glob.
  2. 2026-10-20: add `.kittify/charter/activation.yaml`,
     `src/kernel/activation_ledger_store.py` and
     `src/charter/activation/activation_ledger.py` to the charter shard triggers.
- Nothing in `git log -S`/the changelog closes this; #6798/#6801/#6816/#5927 are
  the related CI-routing precedents cited by the task brief (router
  two-authority, group fan-out, and shard-selection classes).

## Reproduction (through the production entry point)

`scripts/ci/gate_selection.py` is the single gate-selection authority;
`ci-modules.yml` calls `select_modules(changed_files)` to build the module
matrix. On `main`:

| changed path | matched groups | selected modules |
| --- | --- | --- |
| `.kittify/charter/charter.yaml` | `corpus` | ∅ |
| `.kittify/charter/activation.yaml` | `corpus` | ∅ |
| `packs/internal.source.yaml` | `corpus` | ∅ |
| `src/kernel/activation_ledger_store.py` | `core_misc`, `kernel`, `unit` | `{core_misc, kernel, unit}` |
| `src/charter/activation/activation_ledger.py` | `charter` | `{charter}` |

So a parity-breaking activation-store edit selects **no** module shard (the #6333
hole), and the ledger's kernel floor does not run the `tests/charter/activation/**`
readers that exercise it.

## Why the obvious fix is refused

`tests/architectural/test_ci_router_transcription_guards.py::
test_router_src_filters_derive_from_scrub_verbatim` pins each router filter
group's globs to the group's roots in `tests/release/ci_retirement_scrub.json`
**verbatim** (ordered). The `charter` group is `src/charter/**` +
`src/specify_cli/charter_runtime/**` — the charter *source* subsystem. Appending
`.kittify/charter/charter.yaml` / `packs/internal/**` there reds that guard,
which is exactly why #6334 left this open. The scrub's own note for `ci` (#4386)
records the same reasoning.

## Decisions

1. **New NON-src router group `charter_activation`** carrying
   `.kittify/charter/charter.yaml`, `.kittify/charter/activation.yaml`,
   `packs/internal.source.yaml`, transcribed verbatim into the router filter
   block with a `changes.outputs` row. Non-src keeps it out of the FR-004
   fail-closed `unmatched` union (contract Invariant 2), so it can never mask an
   unmapped `src/**` change. It gates no router job by design; the module matrix
   is its per-PR executor (the `mission_manifest` / `cli_cmd_*` shape).
2. **Fan out to the `charter` module** through a hand-authored, non-census table
   in `gate_selection.py` (proposed name `ACTIVATION_STORE_MODULE_FANOUT`), the
   `CLI_COMMAND_MODULE_FANOUT` precedent. It cannot join
   `GROUP_MODULE_FANOUT`/`FANOUT_GROUPS`: `derive_group_module_fanout` reads the
   committed consumer census, which records only resolved `src/**` imports and
   `packs/built-in/missions/**` runtime reads, so a `.kittify`/pin group derives
   an empty set and `tests/ci/test_fanout_derivation.py` requires every
   `FANOUT_GROUPS` member to derive ≥1 module.
3. **`src/kernel/activation_ledger_store.py` reaches the charter shard by adding
   the file verbatim to the `charter` scrub group roots** (and, because the
   registry consumes scrub rows verbatim, to the registry's `charter` row). A src
   file in the new non-src group would drag that group into the fail-closed
   `unmatched` union and the "every src-backed group is job-gated" guard.
   Overlapping src ownership is already the scrub's documented shape
   (`core_misc`/`unit`/`execution_context` each own `src/specify_cli/status/**`).
4. **`src/charter/activation/activation_ledger.py` needs no new routing** (it is
   under `src/charter/**`); it gets a regression pin instead.
5. **Register the new group where the guards require it**: the router filter
   block + `changes.outputs`, `test_workflow_coherence.
   _DELIBERATELY_UNGATED_FILTER_GROUPS`, and the fan-out wiring pin in
   `test_gate_selection_authority.py`. No guard assertion is removed or weakened.

## Evidence

- `scripts/ci/gate_selection.py` — `select_gates`/`select_modules`,
  `GROUP_MODULE_FANOUT`, `CLI_COMMAND_MODULE_FANOUT`, `DEPENDENCY_MODULE_FANOUT`,
  `PROBE_GROUPS`, `src_backed_groups`, `unmatched` semantics.
- `.github/workflows/ci-router.yml` — the dorny filter block, the `changes.outputs`
  rows, the `unmatched` step, `architectural-heavy`'s `if:`.
- `.github/workflows/ci-modules.yml` — `select_modules(changed_files)` builds the
  `module-tests` matrix; `module-tests (charter shard i/7)` is the shard this
  issue is about.
- `.github/ci-module-registry.yml` — 20 module rows; `charter` roots
  `src/charter/**` + `src/specify_cli/charter_runtime/**`, `test_dirs`
  `tests/charter`, `tests/charter_offering`, `shard_count: 7`.
- `tests/release/ci_retirement_scrub.json` — `groups[]` (registry-consumed) vs
  `non_src_router_groups[]` (documentation copy, read by nothing).
- Readers of the activation store / ledger floor: `tests/charter/activation/**`,
  `tests/charter/conformance/test_activation_ledger_conformance.py`,
  `tests/charter_offering/**` (internal pack), `src/kernel/activation_ledger_store.py`
  (path authority, ADR `2026-10-19-1`).
- `packs/internal.source.yaml` is tracked; `packs/internal/**` is not (#6451);
  `.github/workflows/packs.yml` already treats the pin as the internal trigger.

## Open questions for plan

- Exact placement/name of the new fan-out table in `gate_selection.py` and
  whether `select_modules`'s loop should stay a single tuple-unpacked chain
  (minimal diff) — plan decides.
- Whether the new router group should also gate `architectural-heavy`; decision:
  **no** for this mission (it would require editing
  `HEAVY_BATTERY_NON_SRC_GROUPS` and two exact-set guards for a non-CI-integrity
  reason, widening blast radius). Recorded in Out of Scope with the follow-up
  rationale.
- Whether `docs/` needs more than the changelog entry: the router group registry
  is code/test-owned, so plan checks for a doc that lists routing groups.
