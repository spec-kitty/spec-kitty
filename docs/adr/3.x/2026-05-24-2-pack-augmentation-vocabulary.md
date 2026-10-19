---
title: 'ADR: Pack Augmentation Vocabulary — `overrides` and `enhances` as Declarative
  Fields'
description: 'Adds mutually exclusive overrides and enhances fields to five doctrine artifact kinds, making full replacement versus field-level augmentation a declared intent.'
status: Accepted
date: '2026-05-24'
---

- [`2026-05-24-1-charter-freshness-ux-contract.md`](2026-05-24-1-charter-freshness-ux-contract.md) (sibling — surfaces `overrides` / `enhances` in the freshness banners and preflight checks)
- [`2026-05-24-3-shipped-to-built-in-cutover.md`](2026-05-24-3-shipped-to-built-in-cutover.md) (sibling — renames the `shipped` layer this vocabulary augments)

## Context

ADR `2026-05-16-1` ratified that the doctrine layer merge is **field-level**
(`{**shipped.model_dump(), **project_data}`), not artifact-level full
replacement. Under that model, a pack-side artifact that shares an ID with a
built-in artifact silently augments the built-in by field merge — and the
runtime currently emits a generic same-ID-collision *advisory* asking the pack
author to disambiguate.

Two structural gaps remain:

1. **Intent is not declarable.** A pack author cannot say "I mean to fully
   replace this built-in" versus "I mean to add a few fields to it." The
   collision advisory therefore cannot tell intentional augmentation from an
   accidental ID clash; it fires equally in both cases, producing churn for
   intentional pack design.
2. **`extra="forbid"` blocks the most natural fix.** Every doctrine model
   carries `model_config = ConfigDict(frozen=True, extra="forbid", ...)` so
   pack YAMLs that declare an *unknown* augmentation field (e.g. `enhances:
   <id>`) get rejected at the Pydantic boundary before the loader ever sees
   the relation.

Issue #1291 surfaced this when a pack author tried to encode "enhance
built-in `<id>`" as a free-form field and was rejected by `extra_forbidden`.
Wording the validator output as a collision *also* did not reflect the
field-merge semantics that `2026-05-16-1` ratified — the runtime *does*
combine these artifacts; it just lacked the vocabulary to call it that.

## Decision

Add two **first-class, optional declarative fields** to five doctrine artifact
kinds (`Tactic`, `Styleguide`, `Paradigm`, `Procedure`, `AgentProfile`):

- `overrides: <id> | None` — declares full replacement of the built-in
  artifact with this ID.
- `enhances: <id> | None` — declares augmentation of the built-in artifact
  with this ID via field-merge (the existing `2026-05-16-1` semantics).

A cross-field validator (`_augmentation_intent_is_exclusive`, `@model_validator(mode="after")`)
on every artifact kind raises a structured `ValidationError` if both fields
are set on the same artifact; setting neither remains the default and
preserves backward compatibility.

WP06 (a downstream WP in this mission) consumes these fields to auto-emit
`OVERRIDES` / `ENHANCES` edges in the doctrine reference graph and to
**suppress** the same-ID-collision advisory when either field is set —
because the pack author has declared intent.

### Vocabulary canon

- `enhances` (canonical) — synonyms-to-avoid: `augments`, `extends`.
- `overrides` (canonical) — synonyms-to-avoid: `replaces`, `supersedes`.

Both terms are added to `.kittify/glossaries/spec_kitty_core.yaml` per
DIR-032 (project glossary as the source of truth for vocabulary).

## Alternatives Considered

### Alternative A — Drop `extra="forbid"` on doctrine models

**Rejected.** `extra="forbid"` is the principal defense against typo'd field
names in pack YAMLs (e.g. `enhanced_by:` instead of `enhances:`). Loosening
it would degrade the validation surface for every pack author to fix a single
intent-declaration use case. The cost-benefit is wrong.

### Alternative B — Magic precedence rules (no declaration needed)

**Rejected.** "Same ID + extra fields ⇒ enhances; same ID + same fields ⇒
overrides" is implicit, fragile, and hostile to review. Pack authors and
reviewers would need to memorize precedence rules instead of reading a
declarative statement at the top of the artifact. Implicit intent also makes
the DRG edge type (`ENHANCES` vs `OVERRIDES`) unstable across refactors.

### Alternative C — `relation:` enum field with values `overrides`/`enhances`

**Rejected.** A single `relation:` field couples the *kind* of relation to a
*target ID* through positional convention, and a future relation type would
force breaking changes to the field shape. Two narrowly-typed optional
fields, each `string | None`, keep each relation independently evolvable and
make the mutually-exclusive validator trivially expressible.

## Consequences

### Positive

- Pack authors can declare augmentation intent in one line per artifact.
- The same-ID collision advisory (WP06) can suppress correctly on intentional
  augmentation, eliminating churn.
- DRG edge emission (WP06) becomes deterministic from the artifact source —
  no separate `drg/fragment.yaml` entry required for `OVERRIDES` / `ENHANCES`
  edges.
- The field-merge semantics ratified in `2026-05-16-1` are now *namable* in
  the doctrine vocabulary; reviewers and downstream tooling share one term.

### Negative / cost

- Five symmetric model changes plus five matching schema YAML changes are
  required; the cross-cutting fixture surface is large (NFR-004 forces a
  zero-regression sweep across the full doctrine test suite).
- Pack-validator advisory wording (WP06) must be updated in lockstep — the
  vocabulary canon is not useful if downstream messages still say
  "augments".

### Neutral

- Both fields default to `None`; existing fixtures that omit them are
  unaffected. The added schema properties are not `required`.
- `extra="forbid"` is preserved on all five models — only the known-field
  set widens.

### Forward chain

- **WP06** (this mission): adds `Relation.OVERRIDES` and `Relation.ENHANCES`
  to the DRG enum, auto-emits edges from these fields in
  `org_pack_loader.py`, and rewords the collision advisory to suppress when
  either field is set.
- **WP07+** (future): pack-validator hard error path for
  `enhances: <unknown-id>` / `overrides: <unknown-id>` (target must exist as
  a built-in).

## Compliance

This ADR is binding on every change that touches:

- `src/doctrine/{tactics,styleguides,paradigms,procedures,agent_profiles}/models*.py`
- `src/doctrine/schemas/*.schema.yaml`
- `src/doctrine/drg/models.py` (the `Relation` enum, via WP06)
- `.kittify/glossaries/spec_kitty_core.yaml` entries for `enhances` /
  `overrides`

Any new doctrine artifact kind added in the future SHOULD inherit the same
two declarative fields and the same `_augmentation_intent_is_exclusive`
validator unless an explicit deviation is documented in a successor ADR.

## Amendment 2026-10-19: owner-declared mutability levels (spec-kitty-charter ADR-0012)

**Deciders:** Stijn Dejongh (operator), 2026-10-19. Requested by `spec-kitty-charter`
[ADR-0012](https://github.com/spec-kitty/spec-kitty-charter/blob/main/docs/adr/0012-pack-mutability-policy.md) (the owning pack declares a mutability level per artifact: `open`, `extendable` or
`locked`), recorded in [spec-kitty-charter#88](https://github.com/spec-kitty/spec-kitty-charter/pull/88).
The record above is unchanged; this note bounds it.

> Amendment 2026-10-19: a field-level merge (2026-05-16-1) or a declared `overrides` /
> `enhances` relation (2026-05-24-2) applies only where the owning pack's level permits the
> operation (spec-kitty-charter ADR-0012); otherwise the merge refuses with
> `governance_policy_violation`.

**Migration, confirmed by the operator on 2026-10-19:** the built-in pack ships its own policy
file whose kind defaults are `extendable`, and every URN that a released
`replaceable-builtins.yaml` sanctions today is listed in it as `open`. Until the policy
enforcement lands (`spec-kitty-charter` #58, after the org-precedence defect
`spec-kitty-charter` #87 is fixed), current behavior is unchanged.
