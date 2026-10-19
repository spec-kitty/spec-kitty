---
title: 'ADR: Doctrine Layer Merge Semantics — Field-Level Merge with Collision Warnings'
description: 'Doctrine layers combine by field-level overlay with explicit collision warnings, preserving partial project overrides instead of replacing whole artifacts.'
status: Accepted
date: '2026-05-16'
---

## Context

`layered-doctrine-org-layer-01KRNPEE` shipped with a documented contradiction
between specification and implementation that no per-WP reviewer flagged:

- **`spec.md` FR-003** stated: *"the higher layer fully replaces the lower
  layer's artifact (full-replace semantics). Partial field merging is not
  applied across layers."*
- **`data-model.md`** stated: *"Higher layer fully replaces lower layer on
  artifact ID collision. No field-level merging across layers."*
- **`tasks/WP02-base-repository-org-layer.md`** "Key invariant to preserve"
  stated the OPPOSITE: *"The existing `_merge()` (field-level merge) is used
  within the project override step for artifacts whose ID exists in shipped
  (project fields override shipped fields). The same field-level merge is used
  for org overrides of shipped."*
- **`src/doctrine/base.py::_merge`** ships the field-level merge:
  `{**shipped.model_dump(), **project_data}` — a project override that omits
  a field inherits the lower layer's value for that field.

WP02's implementer correctly preserved the pre-2.x project-overlay behaviour
(field-merge has been in place since well before the org layer was added) and
followed WP02's "Key invariant to preserve" note. The contradiction with
`spec.md` and `data-model.md` was not raised in any per-WP review and only
surfaced in post-merge mission review.

### What's actually at stake

Two distinct user-facing semantics could legitimately be called "the higher
layer wins":

1. **Artifact-level full replace.** When a higher layer declares an artifact ID,
   the lower layer's artifact for that ID is discarded entirely; the higher
   layer's YAML must contain every field that downstream consumers need.
   Overrides are self-contained.

2. **Field-level replace (the actual behaviour).** When a higher layer declares
   an artifact ID, fields present in the higher layer's YAML replace the
   same-named fields in the lower layer; fields absent from the higher layer
   fall through to the lower layer's value. Overrides may be partial.

Both share the same "no two artifacts with the same ID coexist across layers
in the resolved view" guarantee. They differ in what an override YAML must
contain and how surprising a partial override is.

### Options

- **(A) Make code match literal spec.** Rewrite `_merge` to
  `type(shipped).model_validate(project_data)`. Project overlays in any
  deployed project that uses partial overrides start failing pydantic
  validation. The existing test `test_org_overrides_shipped_field_merge`
  needs revision. Real, observable regression with no operator-facing
  benefit beyond doctrinal purity.
- **(B) Make spec match code, no other change.** Reword FR-003 and
  `data-model.md` to describe field-merge. Zero code change. Risk: operators
  who override an artifact may not realise a higher-layer file silently
  shadowed a lower-layer artifact — the merge is invisible until someone
  reads the resulting `provenance`.
- **(C) Field-merge **with explicit collision warnings**.** Same as (B) but
  the loader emits a `UserWarning` whenever an override collision occurs,
  so operators are explicitly notified that an org or project artifact
  shadowed a builtin artifact (and which fields it replaced).

## Decision

Adopt **Option C: field-level merge with explicit collision warnings**.

Operators retain the convenience of partial overrides (which the project
overlay layer has supported throughout 2.x). Spec and code are reconciled.
The previously-invisible "top layer wins" semantics become surfaceable.

The decision rests on five facts:

1. **Pre-existing behaviour.** `_merge` has performed field-level merge in
   every spec-kitty release that supported a project doctrine overlay.
   Changing it now would silently break any deployed project with partial
   `.kittify/doctrine/` overrides, with no operator-facing benefit.
2. **WP02 explicitly preserved this invariant.** The "Key invariant to
   preserve" note in `WP02-base-repository-org-layer.md` ratified field-merge
   for the new org layer. The contradiction is in the spec's wording, not in
   delivery intent.
3. **Operator ergonomics.** Override files are short and focused on what
   changes. Requiring full artifacts in every override file would inflate
   YAML and make overrides harder to maintain.
4. **The user's mission-review feedback explicitly asked for collision
   visibility, not behaviour change.** *"The user should be explicitly warned
   about these collisions and the 'top level will win' behaviour."*
5. **No information is destroyed.** Field-merge never drops fields the
   operator did not explicitly target; the merge is non-destructive at the
   field grain. The risk is solely about operator surprise, which collision
   warnings address directly.

## Consequences

### Specification updates (required, normative)

- **`spec.md` FR-003** is reworded:

  > When the same artifact ID appears in multiple layers, the higher layer
  > takes ownership of the resolved artifact (its `provenance` becomes that
  > layer). Field-level merge applies: fields present in the higher layer's
  > YAML replace the same-named fields in the lower layer; fields absent
  > from the higher layer fall through to the lower layer's value. No two
  > artifacts with the same ID coexist across layers — the higher layer's
  > identity wins. The resolver emits an operator-visible collision warning
  > each time a higher layer shadows a lower-layer artifact, with the
  > artifact ID, the source and target layers, and the count of replaced
  > fields.

- **`data-model.md`** "Merge precedence" paragraph is reworded to align.

### Code changes (required, normative)

- `BaseDoctrineRepository._apply_org_overrides` and
  `_apply_project_overrides` emit a `UserWarning` of the shape:

      Doctrine override: <artifact_id> from <higher_layer> shadowed
      <lower_layer> (<N> field(s) replaced; <M> field(s) inherited).

  The warning is emitted exactly once per collision, at load time, with
  `stacklevel=3` so the warning surfaces in the caller's frame.

- `AgentProfileRepository._load_org_profiles_from_dir` and the analogous
  project-merge path in the same module emit the equivalent warning for
  profile collisions.

- The warnings are categorised under a new
  `doctrine.base.DoctrineLayerCollisionWarning` subclass of `UserWarning`
  so operators can filter them via standard `warnings` machinery if
  they intentionally maintain heavy overrides.

### CLI-layer surfacing (operator UX)

- `spec-kitty doctor doctrine` adds a "Collisions" section that lists every
  override collision detected at load time, grouped by pack, so operators
  can audit their override footprint without parsing log noise. (No new
  command; extension of the existing WP07 command.)

### Migration story

- Zero migration burden for operators: existing overlays continue to work
  unchanged. The only new artifact in operator experience is the warning
  stream and the doctor section.

- Existing tests for project-overlay field-merge behaviour (e.g.,
  `tests/doctrine/test_base_org_layer.py::test_org_overrides_shipped_field_merge`)
  remain valid. New tests are added for warning emission.

## Alternatives considered

- **Per-artifact opt-in `_layering: full-replace` strategy.** Adds
  per-artifact API surface, documentation burden, and more code paths for
  a use case nobody has requested. Rejected on YAGNI grounds; can be
  added later if operator demand emerges.

- **Strict `--strict-overrides` CLI flag that promotes warnings to
  errors.** Tempting for CI lint purposes, but cleanly orthogonal to
  the warning emission itself. Captured as a follow-up consideration,
  not part of this ADR.

## Verification

- Reword FR-003 in `spec.md`.
- Reword the merge precedence paragraph in `data-model.md`.
- Implement the `DoctrineLayerCollisionWarning` emission in `base.py` and
  `agent_profiles/repository.py`.
- Add unit tests asserting the warning is emitted for org-over-shipped,
  project-over-shipped, and project-over-org collisions, with the
  expected field-count payload.
- Extend `spec-kitty doctor doctrine` to surface collision counts.
- Update `docs/explanation/org-doctrine-layer.md` (the WP08 explanation
  doc) with a section on collision semantics + warnings.

All verification is local to the doctrine package and its tests; no cross-repo
or downstream-mission impact.

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
