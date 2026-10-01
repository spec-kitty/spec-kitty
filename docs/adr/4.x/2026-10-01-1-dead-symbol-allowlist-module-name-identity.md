---
title: 'ADR: dead-symbol allowlist identity is (module, name)'
description: 'Accepted: dead-symbol allowlist entries are keyed (module, name) in a schema-checked YAML file; body hashes are computed at runtime only and never persisted.'
status: Accepted
date: '2026-10-01'
updated: '2026-10-01'
---

**Status:** Accepted

**Date:** 2026-10-01

**Deciders:** Stijn Dejongh (owner), through the operator rulings recorded in
`kitty-specs/test-suite-remediation-01M3SSDW/decisions/` (Decision Moments
`DM-01M3SSRY`, which put the re-key in scope, and `DM-01M3SVDP`, which withdrew
the census gate) and the plan rulings R2, RK-4 and RK-6 of that Mission.

**Technical Story:** [#5346](https://github.com/spec-kitty/spec-kitty/issues/5346)
under [#5353](https://github.com/spec-kitty/spec-kitty/issues/5353), Mission
`test-suite-remediation-01M3SSDW`.

---

## Context and Problem Statement

`tests/architectural/test_no_dead_symbols.py` fails when a name in a module's
`__all__` has no non-test caller. Documented exceptions are held in an
allowlist. Before this ADR, each allowlist entry was a `SymbolKey` literal
inside the 4,800-line gate file, keyed on a **persisted content hash**:

- D-1 of Mission `relocation-hardened-dead-code-scanners-01KX958P` chose a
  location-free content tier, `(bare_name, body_hash)`, so that a pure move
  would keep its key. A module_path tier, `(bare_name, module_path, body_hash)`,
  was escalated only for live same-name, same-hash collisions (18 entries).
- Mission `frozen-baseline-toll-reduction-01M0A42D` (FR-001/FR-002) added a
  fail-closed refresh helper, `_refresh_dead_symbol_hashes.py`, that rewrote a
  stale `body_hash` literal in the gate file.
- [#3552](https://github.com/spec-kitty/spec-kitty/issues/3552) (FR-006/FR-007)
  added a required `source_module=` provenance field and guards that red when
  that module stops declaring the name.

The hash made every body edit an allowlist edit. Since the `source_module`
backfill on 2026-08-18, 41 of 78 commits that touched the allowlist carried a
body-edit re-pin: 57 re-pinned entries in total. In 25 of those commits the
re-pin was the only allowlist change. None of the sampled re-pins changed a
rationale; they re-pinned mechanically. The hash was not even formatter-stable:
`2641f6b181` re-pinned `DeclaredCommandScopeSource` because `ruff format` joined
a three-line call onto one line.

The benefit D-1 bought, relocation-proof identity, was already gone in
practice. The #3552 provenance guard forced a `source_module=` edit on every
move: the `merge` → `consolidate` package rename (`f5c15f9f88`) edited 28
entries, and the charter-activation split (`e72f8b8a0b`) edited 26.

## Decision Drivers

- A behaviour-neutral body edit must cost zero allowlist edits (SC-003).
- The gate must not weaken: a new dead symbol still reds, and a stale entry is
  still reported (C-007 canon; `architectural-gate-non-vacuity`).
- Exemption data lives apart from gate logic, under one authority per gate
  (single canonical authority; DIRECTIVE_044).
- Every mutable architectural allowlist is capped in `_baselines.yaml`
  (Charter Burn-down Policy (a)); the dead-symbol allowlist had no cap.

## Considered Options

1. **`(module, name)`, where `module` is the `__all__`-declaring module (chosen).**
2. `(module_path, qualname)`: the same key in practice, because the gate only
   covers module-level names. Rejected as a name: "qualname" promises nested
   coverage the gate lacks.
3. `(bare_name, source_module)` plus a stored advisory hash for rename hints.
   Rejected: a stored hash nothing enforces rots and invites "just refresh it".
4. Keep `(bare_name, body_hash)` and run the refresh helper automatically.
   Rejected: its output is still a test-source edit, so it fails SC-003; the
   helper existed since `01M0A42D` and the 57 re-pins happened anyway.

## Decision Outcome

Chosen option 1, because it is the only option whose key a body edit cannot
change (SC-003): `module` and `name` are both structural facts about where a
name is declared, never a function of its content, unlike option 3's stored
hash or option 4's `body_hash`.

- **Identity.** An allowlist entry is `DeadSymbolKey(module, name)`. `module` is
  the dotted module whose `__all__` declares the name; `name` is the bare
  module-level name. An `__all__` is a set, so the key is unique per location
  by construction.
- **Location.** The data lives in `tests/architectural/dead_symbol_allowlist.yaml`
  and is read by one loader, `tests/architectural/_dead_symbol_allowlist.py`
  (`load_allowlist`, `ALLOWLIST`). The loader enforces rules L1–L10 at import:
  exact top-level keys, no duplicate mapping keys, `schema_version: 1`, only
  allowed record keys (so `line:`, `body_hash:` and the retired provenance field
  are refused), non-empty rationales, declared categories with an `issue` where
  `requires_issue` is true, whole-file `(module, name)` uniqueness, no tombstone
  categories, and identifier-shaped `module` and `name` values.
- **Categories.** Category ids are the former `_CATEGORY_*` constant names,
  lower-cased with the leading underscore dropped (`category_*`, ruling RK-4).
  `requires_issue` is `false` for every category today.
- **The #470 widened list** is folded into the same file, as the
  `widened_grandfathered_470` section (91 entries), so the gate has one
  exemption authority.
- **Body hashes are never persisted.** The gate still computes one at runtime,
  for two jobs only: the keyability precondition (an allowlisted name must bind
  a real definition, alias or facade entry, or the entry is INVALID) and
  condition (1) of the re-export auto-exempt (a live same-name collision is
  never auto-exempt).
- **Stale verdicts.** Each entry that no longer earns its place gets exactly one
  verdict, first match wins: INVALID (declared but un-keyable), GONE (no longer
  in that module's `__all__`; a move gets a "probably moved to `X`; update
  `module:`" hint), REVIVED (it has a caller again), SUPERSEDED (a structural
  auto-exempt now covers it) and MOOT (the module is star-imported, so the entry
  exempts nothing).
- **Retired.** `_refresh_dead_symbol_hashes.py` and its tests are deleted, and
  so is `SymbolKey.source_module` with its guards.
- **Size ratchet.** `tests/architectural/_baselines.yaml` gains the section
  `test_no_dead_symbols` with two shrink-only leaves: `allowlist_entries: 293` and
  `widened_grandfathered_470: 91` (ruling RK-6). The count lives only there,
  never in the YAML data. The exact `len(_REQUIRED_TOP_LEVEL_KEYS) == 15` pin in
  `test_ratchet_baselines.py` became the floor `>= 16`.

The migration was lossless. The 294 `SymbolKey` literals collapsed to 293
entries: a duplicate `check_push_safety` literal inside one category had been
silently deduplicated by the frozenset. Nine empty tombstone categories were
dropped. The parity check compared the migrated YAML rows with the pre-migration
set: 293 = 293 entries, 91 = 91 widened entries, 0 category mismatches, and the
same digest on both sides
(`c86703f3d8904b128cfb823e043915971298eb892995ad708bb2ea35707607a1`).

Non-vacuity is kept by a corpus floor (at least 3,500 `__all__` names across at
least 600 modules, so a walker that silently scans a fraction of `src/` reds),
by the M1–M13 mutation battery in `test_no_dead_symbols.py`,
`test_dead_symbol_allowlist_contract.py` and
`test_dead_symbol_allowlist_loader.py`, and by
`test_p1_planted_regression`, which still catches a planted dead symbol.

### Consequences

#### Positive

- A body edit to an allowlisted symbol costs zero allowlist edits (SC-003).
- Persisted collision escalation is gone, and with it the 18 module_path-tier
  entries: a byte-identical rogue sibling in another module has a different
  key. The runtime collision check survives as condition (1) of the
  re-export auto-exempt (above) -- a live same-name collision is still never
  auto-exempt -- it is only the persisted two-tier key that is retired.
- Duplicates within one category are now detectable (loader rule L8); the
  frozenset union used to hide them.
- The gate file stops co-changing with `src/` for data reasons, so its history
  records logic changes.
- Charter Burn-down Policy (a) is honoured: the allowlist is capped.

#### Negative

- A move or rename costs one YAML edit: the old entry is reported GONE, with a
  "probably moved to" hint for a move, and the new location is a fresh
  offender. This is the same cost as before, now explicit and hinted.
- The bite tests that encoded the old contract are retired or inverted:
  `bite_b`, the body-edit arm of `bite_g`, and the relocation arm of `bite_j`.
  M1, M7 and M8 cover the new contract.
- `SymbolKey.source_module` and its G1–G6 guards are deleted.
- MOOT is stricter than the old behaviour, where an entry for a star-imported
  module lingered silently. The live tree has no star-imported targets, so
  this caused no red on landing.

#### Neutral

- The gate file keeps its name, marker and asserts; it stays in the C-007
  enforcement canon.

### Confirmation

- `tests/architectural/test_no_dead_symbols.py`,
  `test_dead_symbol_allowlist_contract.py` and
  `test_dead_symbol_allowlist_loader.py` are green on the live tree.
- `tests/architectural/test_ratchet_baselines.py` enforces the two
  `test_no_dead_symbols` leaves.
- The gate's guidance for contributors is in
  [CI and Architectural Gate Mechanics](../../development/reference/ci-gate-mechanics.md)
  and [Add an exemption to an architectural gate](../../development/how-to/add-architectural-gate-exemption.md).

## Supersession

This ADR **partially supersedes**:

- **D-1 of Mission `relocation-hardened-dead-code-scanners-01KX958P`**, for the
  persisted identity only. The runtime content key, collision classification
  and keyability check remain in `tests/architectural/_symbol_key.py`.
- **Mission `frozen-baseline-toll-reduction-01M0A42D` FR-001/FR-002**: the
  refresh helper is retired.
- **Mission `frozen-baseline-toll-reduction-01M0A42D` FR-005**: its guarantee
  that an inert `test_no_dead_symbols` baselines key cannot re-enter is subsumed
  by the ratchet table's row-to-leaf bijection. The section now exists again as
  an enforced ratchet.
- **#3552 FR-006/FR-007**: the `source_module` field and its guards are deleted.

The superseded Mission artefacts are immutable and are not edited.

## Non-goals

- Changing the caller detectors (`from`-imports, module-attribute access,
  `getattr` strings, facade dictionaries, dynamic accessors).
- Changing the #470 widened scope or its stale semantics.
- Removing condition (1) of the re-export auto-exempt; that is a follow-up.
- Renaming `test_no_dead_symbols.py`, which stays in the C-007 canon.
- Adding a census gate (C-008).

## Links

- Related: [ADR 2026-09-14-1, census-floor ratchets: per-ratchet adjudication](../3.x/2026-09-14-1-census-floor-ratchet-adjudication.md).
  It is the precedent for adjudicating a toll ratchet on its own merits, and the
  reason this Mission adds no census gate.
- Research: `kitty-specs/test-suite-remediation-01M3SSDW/research/dead-symbol-rekey.md`.
- Contract: `kitty-specs/test-suite-remediation-01M3SSDW/contracts/dead-symbol-allowlist.md`.
