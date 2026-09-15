# Phase 0 Research: Drupalling Dries Agent Profile

**Mission**: `drupalling-dries-profile-01M28X69`
**Date**: 2026-09-11
**Method**: direct inspection of the repository's pack, extractor, and test surfaces, plus the
distillation source. Every finding below was executed or read, not inferred.

---

## R-001 — Profile lineage is authored in Python, not in the profile YAML

**Decision**: Add one entry to `_CURATED_ARTIFACT_EDGES` in
`src/charter/offering/drg/migration/extractor.py` to mint
`agent_profile:drupalling-dries --specializes_from--> agent_profile:implementer-ivan`.

**Rationale**: The table is documented in place (`extractor.py:267-272`) as the single source of
lineage truth for built-in profiles: *"built-in profile lineage is now authored directly as DRG
`specializes_from` edges. The legacy `specializes-from` profile field has been retired (and is
rejected by the profile model), so these edges are the single source of lineage truth."* All four
peer specialists — `python-pedro`, `java-jenny`, `node-norris`, `frontend-freddy` — appear there.
Verified: the table currently holds 25 entries.

**Alternatives considered**:
- *A `specializes-from` field in the profile YAML* — rejected at load time by the profile model.
  This is not a style preference; it fails.
- *Hand-authoring the edge into `packs/built-in/agent_profile.graph.yaml`* — the fragments are
  generated; see R-002. A hand-edit reads as staleness to the gate.
- *No lineage edge at all, declaring directives directly on the profile* — would technically load,
  but violates FR-005 and breaks the inheritance property that lets one change to implementer
  discipline reach every specialist. Rejected.

**Consequence for the plan**: the mission touches `src/charter/offering/`, which per CLAUDE.md
means both `tests/charter/` and `tests/doctrine/` are in the blast radius, and the terminology
guard runs pre-push.

---

## R-002 — Graph fragments are generated and gate-checked; never hand-edit them

**Decision**: Produce `packs/built-in/*.graph.yaml` exclusively by running
`spec-kitty doctrine regenerate-graph`, and prove freshness with `--check`.

**Rationale**: The command's own help states it "regenerates into a temp directory and compares the
fragment set against the committed source, exiting non-zero when stale." Running twice on unchanged
inputs yields byte-identical fragments. A hand-edited fragment is therefore indistinguishable from a
stale one — it fails the same way.

**Note on the hand-authored overlay**: the regeneration merges an enumerable overlay
(`charter.offering.drg.migration.hand_authored_overlay`) carrying `in_tension_with` /
`reconciles_tension` / `rejects` edges and the `anti_pattern` **nodes**, because the extractor has
no frontmatter mechanism that could mint them. This mission adds none of those edge kinds, so the
overlay is not touched — but it is the reason `anti_pattern` nodes exist without source files, and
it corroborates R-004.

**Alternatives considered**: hand-editing fragments for speed — rejected; it goes red.

---

## R-003 — Two commands, two different packs: a verified trap

**Decision**: All regeneration and verification in the implementation lane must run against the
**repository's** source and pack, in a synced dev environment — never via a globally installed
`spec-kitty`.

**Evidence (executed during this research)**:

```
$ spec-kitty doctrine regenerate-graph --check
DRG graph is fresh:
/Users/nicolas/.local/pipx/venvs/spec-kitty-cli/lib/python3.14/site-packages/packs/built-in
```

The globally installed (pipx) CLI reported "fresh" — for **its own bundled pack inside the pipx
venv**, not for `/Users/nicolas/Projects/spec-kitty/packs/built-in`. An implementer who runs the
bare command will get a confident green that says nothing about their changes.

**Second half of the trap**: running the repository's own code in this checkout currently fails —

```
$ PYTHONPATH=src python3 -m specify_cli doctrine regenerate-graph --check
ModuleNotFoundError: No module named 'spec_kitty_events.diary'
```

This is the stale/absent dev-environment case the repository's own testing guidance warns about: a
`ModuleNotFoundError` for a declared, pinned package means the environment was never synced, not
that anything regressed. There is no `.venv` in this checkout.

**Consequence**: the first task of IC-1 is `make dev-setup` (or `uv sync --frozen --all-extras`),
then establishing the *repository* pack's freshness baseline. Until that runs, the baseline is
**unverified** — this document does not claim the repo pack is fresh, only that the pipx pack is,
which is irrelevant.

**Alternatives considered**: assuming the baseline is clean because the global command said so —
rejected; that is precisely the false green this finding exists to prevent.

---

## R-004 — Drupal anti-patterns belong in the styleguide, not the `anti_pattern` channel

**Decision**: Carry all 14 of the source guide's "Never Do This" entries into
`drupal-conventions.styleguide.yaml` as `patterns:` entries with `description`, `bad_example`, and
`good_example`.

**Rationale**: Two independent observations agree.
1. The `anti_pattern` channel holds 13 nodes with `edges: []`, no body directory, and labels that
   are cross-cutting architecture/DDD concepts — *Anemic Domain Model*, *Big Ball of Mud*,
   *Big-Bang Rewrite*, *Feature Envy*, *Global Data*. There is nowhere to put content: the nodes
   carry a label and tags only.
2. `python-conventions.styleguide.yaml` already carries its stack anti-patterns — *Nested
   Conditional Logic*, *Untyped Public Functions*, *String Path Manipulation*, *Cleanup In Test
   Body* — as `patterns:` entries with paired bad/good examples. That is the established home for
   stack-level "don't do this".

Drupal idioms such as "never use `\Drupal::` static calls in services" are stack conventions, not
architectural archetypes. SC-003 is satisfied: 14 of 14 carried, none omitted.

**Alternatives considered**:
- *Add 14 nodes to `anti_pattern.graph.yaml`* — they would be label-only, with the actual guidance
  nowhere, and would dilute a channel whose current membership is deliberately architectural.
- *Split anti-patterns into a third styleguide* — rejected; they are the inverse face of the
  conventions they violate and belong beside them.

---

## R-005 — The inherited directive and tactic set

**Decision**: Declare on the profile — `directive-references`: 010, 024, 025, 030, 034, 051;
`tactic-references`: `dependency-hygiene`, `tdd-red-green-refactor`, `supply-chain-install-safety`,
`bug-fixing-checklist`.

**Rationale**: Derived from the intersection of the three implementer specialists' existing graph
edges, read directly from `packs/built-in/agent_profile.graph.yaml`:

| Edge | java-jenny | python-pedro | node-norris |
|------|:---:|:---:|:---:|
| `specializes_from: implementer-ivan` | ✅ | ✅ | ✅ |
| requires DIRECTIVE_010 / 024 / 025 / 030 / 034 / 051 | ✅ | ✅ | ✅ |
| suggests DIRECTIVE_041, DISCIPLINED_REFACTORING | ✅ | ✅ | ✅ |
| requires `tactic:dependency-hygiene` | ✅ | ✅ | ✅ |
| requires `tactic:tdd-red-green-refactor` | ✅ | ✅ | ✅ |
| requires `tactic:supply-chain-install-safety` | ❌ | ❌ | ✅ |

`supply-chain-install-safety` is taken from the Node precedent rather than the Java one because
Drupal projects install from Packagist via Composer **and** from npm for theming assets — the same
two-registry exposure that earned Node Norris the edge.

The extractor reads `directive-references` and `tactic-references` from the profile YAML
(`extractor.py:634,646`), so these edges are minted automatically. Only lineage (R-001) needs the
curated table.

**Alternatives considered**: copying Java Jenny's set verbatim — would omit
`supply-chain-install-safety`, understating the npm exposure the JS-gate decision (R-006) creates.

---

## R-006 — Resolving the JS-gate / FR-004 tension

**Decision**: Dries's self-review protocol includes `npm run test` and `npm run test:a11y`
alongside the PHP gates, and **both** profiles state a verification-versus-authorship distinction:
Dries *verifies* the Drupal-native theming JavaScript it authored; Frontend Freddy remains the
*author* for generic browser component work.

**Rationale**: The operator chose to include the JS gates (decision
`01M28YDXBXHFGHFV3PT9DH5HND`) after FR-004 had already sharpened the Dries/Freddy line. Taken
naively these conflict: a profile that runs another profile's test suite has effectively claimed
its territory. Separating the two scopes resolves it without weakening either — running a test
proves nothing about who should have written the code, and a profile that writes
`Drupal.behaviors` and then declines to run the JS suite is failing its own gate.

This is recorded as **contested and changed**, not accepted silently: the boundary text FR-004
requires is now strictly larger than what the spec described, and IC-7 must carry the distinction
into both profiles.

**Alternatives considered**:
- *PHP gates only* — the cleaner boundary, and the recommendation; not what the operator chose.
- *Include JS gates and say nothing* — rejected. It would leave two shipped profiles making
  quietly incompatible claims, which is the exact failure FR-004 exists to prevent.

---

## R-007 — Tooling commands come from the source; no levels invented

**Decision**: The toolguide names `vendor/bin/phpcs --standard=Drupal`, `vendor/bin/phpstan
analyse`, `vendor/bin/drupal-check`, `composer audit`, `vendor/bin/phpunit`, `drush cr`,
`drush updatedb`, plus `npm run test` / `npm run test:a11y` per R-006 — with **no** invented
PHPStan level, coverage percentage, or threshold.

**Rationale**: NFR-006 forbids invented claims. The source guide's *Code Quality Tools* and *Before
Submitting Code* sections name these commands exactly and specify no analysis level. Asserting
"PHPStan level 5" would be a fabrication dressed as guidance.

**Alternatives considered**: recommending a level from general Drupal community practice —
rejected under NFR-006. The toolguide instead says to use the level the consumer project
configures.

**Deliberately not included**: a mutation-testing guide. Python ships `PYTHON_MUTATION_TOOLS.md`
and TypeScript ships its own, but the source guide contains no mutation-testing content, and Java
ships none either. Inventing an Infection/PHP guide would violate NFR-006.

---

## R-008 — Environment-agnostic command form

**Decision**: Write commands bare (`composer`, `drush`, `vendor/bin/phpunit`) with one explicit
adaptation note stating that containerized setups prefix them (`ddev drush cr`, `lando composer
audit`).

**Rationale**: C-004 and the operator's decision (`01M28YDW8F49V927NNPWMWCBVJ`'s sibling,
`01M28XMB432H0PPSHG8J3V4VG5`). The source is the Vanilla variant, so bare commands are faithful to
it; the note prevents a false gate failure for the large population of Drupal developers using DDEV
or Lando.

**Alternatives considered**: dual-listing every command in both forms — rejected as noise that
doubles the guide's length for no added information.

---

## Supply-chain and adversarial-evidence record

**Dependency decisions made**: none. This mission adds, upgrades, and removes zero packages in
every ecosystem (C-006). The Composer and npm commands appearing in delivered artifacts are
*content describing consumer projects*; nothing is installed into this repository.

**Adversarial squad challenge pass**: **not triggered** — no security-impacting dependency decision
was taken. Recorded explicitly so a later reviewer sees a determination rather than an omission.

**Contested findings and disposition** (per `contracts/adversarial-evidence-contract.md` shape):

| Finding | Raised during | Disposition |
|---------|--------------|-------------|
| JS gates contradict the FR-004 boundary | Plan interrogation | **changed** — R-006 adds the verification/authorship distinction to both profiles |
| Anti-patterns have no content-bearing home in the `anti_pattern` channel | Phase 0 | **changed** — R-004 routes them to the styleguide, following the `python-conventions` precedent |
| A global `spec-kitty` reports a graph baseline for the wrong pack | Phase 0 | **changed** — R-003 makes a synced repo environment a prerequisite of IC-1 |
| Repository pack freshness baseline is unverified in this checkout | Phase 0 | **deferred_with_rationale** — cannot be established without a synced dev environment; assigned as the first task of IC-1 rather than assumed |

No contested finding was dropped.
