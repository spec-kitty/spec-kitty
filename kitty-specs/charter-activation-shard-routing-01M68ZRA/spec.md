# Mission Specification: Charter Activation Shard Routing

**Mission Branch**: `issue-6336-charter-activation-shard-routing`
**Created**: 2026-10-31
**Status**: Draft
**Closes**: #6336 (follow-up to #6333 / #6334; refs #6798, #6801, #6816, #5927)
**Input**: Act as the implementation sub-agent for issue #6336 — "CI hardening: charter shard should trigger on activation-store / internal-pack edits".

## Purpose

An edit to the charter activation store (`.kittify/charter/charter.yaml`,
`.kittify/charter/activation.yaml`) or to the internal-pack pin
(`packs/internal.source.yaml`) changes what the charter module's config-parity
tests assert, but today it selects **no CI module at all**: `select_modules`
returns an empty set, so `module-tests (charter shard …)` never runs. That is how
#6333 reached `main` green and then reddened every later PR, which is tested as
merged.

`#6334` deliberately did not close the hole. Appending the activation store to the
router's `charter` filter group fails
`tests/architectural/test_ci_router_transcription_guards.py::test_router_src_filters_derive_from_scrub_verbatim`:
a router group's globs must be a **verbatim transcription** of that group's roots
in `tests/release/ci_retirement_scrub.json`, and the `charter` group is the charter
*source* subsystem (`src/charter/**`, `src/specify_cli/charter_runtime/**`), not a
free-form CI-trigger list. The activation store is non-src doctrine state.

This mission registers the activation store and the internal-pack pin as their own
NON-src router group and wires it to the charter module, so an activation-store or
internal-pack edit runs the charter shard on a PR and on a push to `main`. It also
routes `src/kernel/activation_ledger_store.py` (the ledger's kernel-side floor,
exercised by `tests/charter/activation/**`) to the charter shard, as #6336's
2026-10-20 follow-up comment requests.

## Confirmed reproduction on current `main` (35318ef51c)

```
select_modules(['.kittify/charter/charter.yaml'])         -> frozenset()
select_modules(['.kittify/charter/activation.yaml'])      -> frozenset()
select_modules(['packs/internal.source.yaml'])            -> frozenset()
select_modules(['src/kernel/activation_ledger_store.py']) -> {core_misc, kernel, unit}   # charter absent
select_modules(['src/charter/activation/activation_ledger.py']) -> {charter}            # already covered
```

## User Scenarios & Testing

### Primary actors

- **Maintainer / CI pipeline** — needs the charter module shard to run for every
  change that can alter what its config-parity tests assert, so `main` cannot go
  green on a parity-breaking activation edit and then red every later PR.
- **PR author** — must not pay for the charter shard on diffs that cannot affect it
  (a docs-only diff or an unrelated src group still selects exactly what it did).

### Scenario A — activation-store edit runs the charter shard (P1)

1. **Trigger:** a PR or push to `main` changes `.kittify/charter/charter.yaml` or
   `.kittify/charter/activation.yaml`.
2. **Today:** the diff matches only the non-src `corpus` group; `select_modules`
   selects zero modules, so the charter shard (the parity tests that read the
   activation store) never runs.
3. **Desired outcome:** the diff matches the new non-src `charter_activation`
   router group, which fans out to the `charter` registry module, so
   `module-tests (charter shard …)` runs on both the PR and the push to `main`.
4. **Invariants that must hold:** the new group is non-src, so it never joins the
   FR-004 fail-closed `unmatched` union; an unmapped `src/**` change still forces
   run-all; the `charter` scrub group's *scope* stays the charter source subsystem.

### Scenario B — internal-pack pin bump runs the charter shard (P1)

1. **Trigger:** a pin bump of `packs/internal.source.yaml` (`spec-kitty charter pack
   vendor --pack internal --ref <sha>`).
2. **Today:** the bump matches only `corpus` (and the `packs.yml` internal lanes);
   `tests/charter_offering/**`, which reads `packs/internal`, is not selected.
3. **Desired outcome:** the bump also selects the `charter` module, so the
   charter-offering tests that read the internal pack run before merge.
4. **Not a valid trigger:** `packs/internal/**` itself — the tree is untracked in
   core since #6451, so a glob on it matches no tracked path (and the
   dead-glob guard would red). The pin lockfile is the live in-repo signal.

### Scenario C — kernel ledger floor edit runs the charter shard (P2)

1. **Trigger:** a PR changes `src/kernel/activation_ledger_store.py`.
2. **Today:** it selects `kernel`, `core_misc` and `unit`; the `charter` module
   (whose `tests/charter/activation/**` readers are the ones that exercise the
   ledger floor) is not selected.
3. **Desired outcome:** the file also selects `charter`, while the pre-existing
   `kernel`/`core_misc`/`unit` selection is untouched.
4. **Regression pin:** `src/charter/activation/activation_ledger.py` already
   selects `charter` (via `src/charter/**`); the mission keeps that true and pins it.

### Scenario D — no routing blast radius (P2)

1. **Trigger:** a docs-only diff, an unrelated src group, or the built-in pin.
2. **Desired outcome:** the module selection is exactly what it was before this
   mission; the new group selects no module unless one of its own globs matched,
   and adds no registry row, no shard and no test-dir claim.

### Edge cases

- A diff that touches both the activation store and an unrelated src group selects
  the union (`charter` plus the other group's modules) — never a narrowed set.
- A diff that touches an unmapped `src/**` path still forces run-all, even when it
  also touches the activation store (the non-src group cannot mask the catch-all).
- `packs/internal.source.yaml` also matches the `corpus` group; multi-group
  matches are additive (the router already encodes overlapping ownership).
- The new group's globs must all match a tracked path, or the dead-glob guard
  (`test_every_restored_filter_glob_is_live`) reds.
- The `corpus` group continues to match `.kittify/charter/**`; the new group is
  additive, not a move, so corpus-marked corpus tests are unaffected.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Non-src `charter_activation` router group | As a maintainer, I want one named router group for the activation store and the internal-pack pin so a path-routed change has a group to match instead of falling into no module. | High | Open | [build] | no — the group must be declared in the dorny filter block and in `changes.outputs`; a no-op leaves neither. |
| FR-002 | Activation-store edits select the charter module | As a maintainer, I want `.kittify/charter/charter.yaml` and `.kittify/charter/activation.yaml` edits to select the `charter` registry module so its parity tests run before merge and on `main`. | High | Open | [build] | no — today `select_modules` returns ∅ for both paths. |
| FR-003 | Internal-pack pin selects the charter module | As a maintainer, I want a `packs/internal.source.yaml` bump to select `charter` so `tests/charter_offering/**` (which reads `packs/internal`) runs for the pin change. | High | Open | [build] | no — today the pin selects zero modules. |
| FR-004 | Kernel ledger floor selects the charter module | As a maintainer, I want `src/kernel/activation_ledger_store.py` to also select `charter` so the `tests/charter/activation/**` readers run when the store's floor changes. | Medium | Open | [build] | no — today it selects `{core_misc, kernel, unit}` only. |
| FR-005 | Activation ledger reader stays selected | As a maintainer, I want `src/charter/activation/activation_ledger.py` pinned as selecting `charter`, so a future routing change cannot drop it. | Medium | Open | [ratchet] | no — the pin asserts a non-empty `charter` selection on a path whose group could be re-scoped. |
| FR-006 | Non-src, fail-closed intact | As a maintainer, I want the new group to stay out of the FR-004 `unmatched` union so an unmapped `src/**` change still forces run-all and is never masked. | High | Open | [ratchet] | no — the pin asserts run-all on an unmapped src path *while* the activation store also changed. |
| FR-007 | No routing blast radius | As a CI owner, I want the new group to add exactly the `charter` module and no registry row, shard or test-dir claim, so unrelated diffs keep their current selection. | High | Open | [ratchet] | no — the pin asserts docs-only selects zero modules and unrelated src groups select exactly their own. |
| FR-008 | Charter group transcription stays verbatim | As a maintainer, I want the router's `charter` filter to remain the verbatim transcription of the scrub's `charter` group, with the ledger floor added to that group's roots in *both* the scrub and the registry, so the transcription guards stay green. | High | Open | [build] | no — the transcription guard compares globs to roots; a one-sided edit reds it, and the selection pin reds without the root. |
| FR-009 | Red-first routing pins | As a reviewer, I want a test module that fails on pre-fix `main` for FR-002/FR-003/FR-004 and is non-vacuous (glob stripped → selection drops), so the fix cannot regress silently. | High | Open | [build] | no — each assertion names a module the current router does not select. |

### Non-Functional Requirements

| ID | Requirement | Threshold / Measure | Category | Priority | Status |
|----|-------------|---------------------|----------|----------|--------|
| NFR-001 | No added shard cost for unrelated diffs | `select_modules` for a docs-only path, for `packs/built-in.source.yaml` and for `src/specify_cli/review/**` returns exactly the pre-change set (assertion-compared, not eyeballed). | Performance | High | Open |
| NFR-002 | CI-integrity gates stay green | All of: `test_ci_router_transcription_guards.py`, `test_gate_selection_authority.py`, `test_module_shard_registry.py`, `test_same_tier_uniqueness.py`, `test_workflow_coherence.py`, `test_retirement_scrub.py`, `test_ci_integrity_oracle_nonvacuous.py`, `test_consumer_census_routing.py`, `tests/ci/test_fanout_derivation.py` pass with no skip, xfail or allowlist widening. | Reliability | High | Open |
| NFR-003 | Single-module fan-out | The new group fans out to exactly one registry module (`charter`); a diff touching only its globs selects `{charter}` and no other module. | Performance | Medium | Open |
| NFR-004 | Local reproduction | The routing claim is reproducible locally through the pre-existing entry point (`python -c "from scripts.ci.gate_selection import select_modules; …"`), the same call `ci-modules.yml` makes. | Testability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No gate weakening | No CI gate, guard, allowlist or assertion may be deleted, skipped, xfailed or broadened to make this pass; guard *registries* (deliberately-ungated groups, joins) may be extended only to register the new, legitimately-wired group. | Technical | High | Open |
| C-002 | Do not re-scope the `charter` scrub group to non-src paths | The activation store must not be appended to the `charter` filter group (that is exactly what #6334 refused); the new group carries it. | Technical | High | Open |
| C-003 | The pin lockfile is the internal-pack trigger | `packs/internal/**` is untracked since #6451 and must not be used as a router glob; `packs/internal.source.yaml` is. | Technical | High | Open |
| C-004 | No pack content or packaging change | `packs/built-in/**` and `packs/internal/**` are fetched trees; this mission edits neither, and touches no packaging include/exclude. | Technical | High | Open |
| C-005 | Delivery protocol | Work lands on `issue-6336-charter-activation-shard-routing`; the PR is opened as a draft and flipped only when green; the operator merges. Never push `main`, never arm auto-merge. | Business | High | Open |
| C-006 | Changelog | A user-facing CI-behaviour change gets an `[Unreleased]` entry in `docs/changelog/CHANGELOG.md` with a bold impact-first lead and `(#6336)`. | Business | Medium | Open |

### Key Entities

- **Router routing group** — an entry in `ci-router.yml`'s dorny `changes` filter
  block (authority 1: path → group) plus its `changes.outputs` row; groups whose
  job `if:` gates are authority 2.
- **Gate-selection authority** — `scripts/ci/gate_selection.py`; parses the two
  router authorities and answers `select_gates` / `select_modules` for a diff.
- **Module registry row** — `.github/ci-module-registry.yml` `modules[]`; the
  `module-tests` matrix's unit. Rows are verbatim from the scrub.
- **Retirement scrub** — `tests/release/ci_retirement_scrub.json`; the single data
  source for group roots (`groups[]`) and the router-only non-src group copy
  (`non_src_router_groups[]`).
- **Activation store** — `.kittify/charter/charter.yaml` (the charter read
  authority) and `.kittify/charter/activation.yaml` (ADR `2026-10-19-1`, the single
  authority for charter activation).
- **Internal-pack pin** — `packs/internal.source.yaml`, the in-repo signal that the
  fetched internal doctrine pack changed (#6451).

## Success Criteria

- **SC-001**: `select_modules(['.kittify/charter/charter.yaml'])`, `(['.kittify/charter/activation.yaml'])` and `(['packs/internal.source.yaml'])` each contain `charter`. — [build] · no-op passable: no
- **SC-002**: `select_modules(['src/kernel/activation_ledger_store.py'])` contains both `charter` and `kernel`. — [build] · no-op passable: no
- **SC-003**: Every CI-integrity gate named in NFR-002 passes, and neither `test_ci_router_transcription_guards.py` nor `test_gate_selection_authority.py` loses an assertion. — [ratchet] · no-op passable: no
- **SC-004**: An unmapped `src/**` path alongside an activation-store path still yields `unmatched_src is True` and run-all; a docs-only diff still selects zero modules. — [ratchet] · no-op passable: no
- **SC-005**: The registry's module set, `shard_count` values and `test_dirs` claims are unchanged (still the same 20 modules; the charter row keeps `shard_count: 7` and its two test dirs). — [ratchet] · no-op passable: no

## Assumptions

- The consumer census (`.github/ci-consumer-census.json`) records only resolved
  `src/**` imports and `packs/built-in/missions/**` runtime reads, so a `.kittify/**`
  or pin-lockfile group derives an **empty** census set; the new fan-out therefore
  cannot be a `GROUP_MODULE_FANOUT`/`FANOUT_GROUPS` member without breaking
  `tests/ci/test_fanout_derivation.py`'s non-vacuity rule. It follows the
  `CLI_COMMAND_MODULE_FANOUT` precedent: a hand-authored non-census fan-out table
  consumed by the same `select_modules` entry point.
- `tests/charter/**` and `tests/charter_offering/**` (the charter module's two test
  dirs) are the readers that exercise the activation store, the ledger floor and the
  internal pack; hence `charter` is the module set.
- `packs/internal.source.yaml` is tracked; `packs/internal/**` is not (#6451).

## Out of Scope

- Wiring the activation store into the heavy architectural battery or the always-on
  fast gates (they are unaffected by a non-src group; a separate issue if wanted).
- Extending the consumer census to `.kittify/**`/pin paths (follow-up material, not
  needed to close #6336).
- Any change to the charter module's test dirs, shard count, tiers or the module
  matrix shape.
- Editing pack content or the pins themselves.
