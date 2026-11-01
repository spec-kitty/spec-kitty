---
title: 'ADR: Mission-Type Roster Layering Is the Availability Slice, Not the Kind-Promotion Slice'
description: 'Adds a layered, pack-aware mission-type lookup and a flat org/project roster layout. Availability slice only: mission-type is not promoted to an ArtifactKind.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-08-13'
---

## Context and Problem Statement

Mission `up-mission-type-seam-01KZY1JB` gives the mission-type roster a **layered lookup** so a
non-built-in mission type declared in an org-tier doctrine pack resolves through `mission
create`, `charter activate`, and action-sequence projection end-to-end — not merely "loads
without crashing." `MissionTypeRepository.default()` (`src/doctrine/missions/mission_type_repository.py:48-50`,
a `@classmethod` decorated with `@functools.cache`, keyed on `cls` only) stays built-in-only and
unchanged; a new, separate, pack-aware factory is added alongside it.

That work sits immediately downstream of a live sequencing decision recorded in
[`docs/adr/3.x/2026-08-05-1-mission-type-availability-before-kind-promotion.md`](./2026-08-05-1-mission-type-availability-before-kind-promotion.md),
which deliberately decoupled two independent mission-type threads and sequenced the
charter-activation-driven **availability** thread ahead of the **mission-type-as-`ArtifactKind`**
promotion thread (issue [#2468](https://github.com/Priivacy-ai/spec-kitty/issues/2468), blocked
on the keystone pack-split [#2467](https://github.com/Priivacy-ai/spec-kitty/issues/2467)). That
ADR is explicit that the promotion thread "reverses a deliberate, tested 'no silent fallback'
contract (R-009/CL-1, FR-032, pinned by `tests/doctrine/test_org_pack_augmentation.py`) and must
carry its own decision record; it must not be smuggled into an availability slice." It also
explicitly parks the org-pack mission-type directory **layout** (nested vs. flat) as an
undecided sub-decision belonging to the promotion slice: "This ADR does not bind it."

This mission's roster-layering work is exactly the availability/resolution slice that
sequencing ADR anticipated. The risk this ADR closes is conflation risk, not implementation
risk: a future reader auditing either ADR must be able to tell, without re-deriving it from the
diff, that this mission (1) does not do the promotion work, (2) is not a silent reversal of the
"no silent fallback" contract the promotion thread must reckon with, and (3) makes its own,
narrower, self-contained call on the one layout sub-decision the sequencing ADR left open for a
directory shape this mission actually needs today (the org/project roster location), without
pretending to settle the promotion thread's broader nested-vs-flat question for `#2468`.

## Decision Drivers

* **No silent contract reversal.** The sequencing ADR requires the promotion thread (`#2468`) to
  carry its own decision record rather than be smuggled into an availability slice; symmetrically,
  this availability slice must not be misread as doing that thread's work by omission.
* **Honor a parked decision instead of silently resolving it.** The sequencing ADR left
  nested-vs-flat mission-type layout open *for the promotion slice*. This mission needs an
  org/project roster layout *now*, for a narrower purpose (where does a layered lookup scan for
  non-built-in mission-type YAML), and must record that choice explicitly rather than let a
  directory decision made here be mistaken for having settled the promotion thread's question.
* **`ArtifactKind` / `CHARTER_KIND_TOKENS` boundary stays untouched.** Confirmed live (see below):
  the enum has no `MISSION_TYPE` member, and the exception that keeps `"mission-type"` out of the
  charter-activatable `ArtifactKind` vocabulary still exists and is unchanged by this mission
  (spec C-002/C-003).
* **Correctness over convenience in the seam's own shape (CL-001).** The layered lookup must not
  be built by making the existing built-in-only `default()` project-dependent, even though that
  would look like the smaller diff — see "Seam Shape" below.

## Decision

### (a) This mission does not promote mission-type to a first-class `ArtifactKind`

Confirmed live at this HEAD: `src/doctrine/artifact_kinds.py:124-143` defines
`class ArtifactKind(StrEnum)` with twelve members (`DIRECTIVE`, `TACTIC`, `STYLEGUIDE`,
`TOOLGUIDE`, `PARADIGM`, `PROCEDURE`, `AGENT_PROFILE`, `MISSION_STEP_CONTRACT`, `TEMPLATE`,
`ASSET`, `GLOSSARY_PACK`, `ANTI_PATTERN`) — **no `MISSION_TYPE` member exists today.**
`MissionTypeNotAnArtifactKind` is defined at `src/doctrine/artifact_kinds.py:40` and is
re-exported by `src/charter/kind_vocabulary.py` (import at line 51, `__all__` entry at line 78).
Its purpose, per the module's own kind-normalization contract, is to keep the operator-facing
token `"mission-type"` out of the charter-activatable `ArtifactKind` vocabulary while it remains
a `CHARTER_KIND_TOKENS` member — i.e. mission types are activatable but are deliberately **not**
a doctrine artifact kind. This mission does not add a `MISSION_TYPE` enum member, does not touch
`MissionTypeNotAnArtifactKind`, and does not widen `ALLOWED_MISSION_TYPES`
(`src/charter/activations.py:95`, an import-time-constrained frozenset — spec C-003). Promoting
mission-type to a first-class `ArtifactKind` is the separate, larger, currently-unstarted
upstream effort tracked by the sequencing ADR: issue
[#2468](https://github.com/Priivacy-ai/spec-kitty/issues/2468), blocked on the keystone pack-split
[#2467](https://github.com/Priivacy-ai/spec-kitty/issues/2467).

### (b) Relation to the sequencing ADR's "no silent contract reversal" driver

[`docs/adr/3.x/2026-08-05-1-mission-type-availability-before-kind-promotion.md`](./2026-08-05-1-mission-type-availability-before-kind-promotion.md)
names `#2468`'s promotion as reversing a deliberate, tested "no silent fallback" contract
(R-009/CL-1, FR-032, pinned by `tests/doctrine/test_org_pack_augmentation.py`) and requires that
reversal to carry its own decision record rather than be smuggled into an availability slice.

**This mission is that availability/resolution slice, and states plainly that it is not the
contract-reversing type-promotion slice.** Concretely: this mission adds a layered lookup +
`PackContext` projection + CLI-surface fixes for a mission type that has already been *activated*
(charter-eligible) — it never widens what can be *activated* in the first place (C-003, above).
It touches no code path guarded by `tests/doctrine/test_org_pack_augmentation.py`, adds no
`ArtifactKind` member, and leaves `MissionTypeNotAnArtifactKind` and `CHARTER_KIND_TOKENS`
unchanged. A future reader auditing either ADR should read this section and the sequencing ADR's
"No silent contract reversal" driver together as confirming, not conflicting: the sequencing ADR
sequenced this slice first *because* it does not touch the contract the promotion slice must
reckon with; this ADR confirms that the slice landed as scoped.

### (c) The flat org-pack layout (CL-005) — its own short decision record

The sequencing ADR's "Explicitly out of scope" section names the **nested-vs-flat mission-type
path** as an open sub-decision it deliberately parks for the `#2468` promotion slice: "This ADR
does not bind it." This mission needs an org/project mission-type roster location for its own,
narrower purpose (where the new layered lookup scans for non-built-in mission-type definitions),
so it makes and records that call here, distinct from (a) and (b) above and without claiming to
settle the promotion slice's broader question.

**Decision: the layout is flat.**

* **Org layer**: `<pack_root>/mission_types/*.yaml`. This matches the sibling `mission-steps/`
  convention already used at the org/project pack tier — confirmed live at
  `src/doctrine/missions/mission_step_repository.py:411`, whose docstring states the pattern
  `{pack_root}/mission-steps/{mission_type_id}/{step_id}/step.yaml`.
* **Project layer**: `.kittify/missions/mission_types/*.yaml`, scanned **non-recursively**.

**Rejected alternative**: `.kittify/doctrine/mission_types/`. That directory shape, scanned
recursively, would descend into a per-type subdirectory (e.g.
`.kittify/doctrine/mission_types/<type>/governance-profile.yaml`) and mint a bogus available
mission type literally named `governance-profile`. This is a real trap in the live scanning code,
not a hypothetical one: `CharterPackManager.list_available_detailed`
(`src/charter/pack_manager.py:756`) uses `scan_dir.rglob(glob)` universally for every
charter-activatable kind (the `rglob` call itself is at `src/charter/pack_manager.py:809`), so
any subdirectory content matching the glob resolves as a top-level available artifact id.

This mission's flat CL-005 shape **structurally avoids** the trap rather than fixing the
underlying `rglob` behavior — `.kittify/missions/mission_types/` holds only flat `*.yaml` files
with no per-type subdirectory, so `rglob("*.yaml")` and a hypothetical non-recursive `glob` are
behaviorally identical there. Changing `list_available_detailed` from `rglob` to `glob` would be
an unrelated, broader-blast-radius change affecting every other charter-activatable kind that
scans through the same method, and is explicitly out of scope for this mission (tracked as
follow-up scope in WP05's own work-package prompt,
`kitty-specs/up-mission-type-seam-01KZY1JB/tasks/WP05-activate-layer-scan.md`).

## Seam Shape Backing These Decisions: CL-001's Rejected Alternatives

The layered lookup itself (the mechanism (a)/(b)/(c) above describe as "the availability slice")
was not the only shape considered. Recording the rejected alternatives here, not just the chosen
shape, is part of what makes this a decision record rather than a design summary:

* **Option (a) — make `MissionTypeRepository.default()` itself project-dependent**, by threading
  a `PackContext` into the existing, process-wide, `cls`-keyed `@functools.cache`. **Rejected**:
  a project-dependent value behind a project-blind cache is a correctness bug — the first project
  resolved in a process would poison the cache for every later one resolved in that same process.
  `default()` (`src/doctrine/missions/mission_type_repository.py:48-50`) therefore stays
  built-in-only and untouched; the new lookup is a **separate, module-level**
  `@functools.cache`-wrapped factory keyed on `(mission_types_dirs, pack_context)`, never a
  classmethod cache.
* **Option (b) — move the `action_sequence` projection out of
  `src/doctrine/missions/mission_type_repository.py` into the charter layer.** **Rejected,
  measured, not guessed**: doing so would remove the only producer of the `action_sequence` slot
  from the one directory tree (`src/doctrine/` + `packs/built-in/`) that
  `tests/architectural/test_no_inert_schema_slots.py`'s producer-scan walks, which reds the one
  live assertion in that architectural gate — `test_live_tree_has_no_new_inert_slots`'s
  `assert new == []` (`tests/architectural/test_no_inert_schema_slots.py:62-75`, confirmed live at
  this HEAD).

The new lookup instead imports the existing structural `_PackContextLike` `Protocol`
(`src/doctrine/missions/mission_step_repository.py:41-61`, confirmed live) from its sibling
module in the same package (`doctrine.missions`) — an intra-package import, not a new
cross-layer one; `doctrine` still never imports `charter`. This is why the mechanism qualifies as
"availability/resolution," per (b) above: it is additive plumbing inside the existing
built-in/org/project layering, not a change to what counts as a doctrine artifact kind.

## Consequences

**Positive**

* A future reader of either this ADR or the sequencing ADR can resolve, from either document
  alone, whether a given piece of mission-type work is the availability slice or the promotion
  slice — the conflation risk this ADR exists to close.
* The one org-pack layout question this mission actually needs answered (org/project roster
  location) is decided and recorded, without overreaching into the promotion slice's broader
  nested-vs-flat question, which stays open for `#2468` to answer when it is scoped.
* The rejected `MissionTypeRepository.default()` project-dependent-cache option is on record, so a
  future contributor tempted by the smaller-looking diff can see why it was rejected instead of
  rediscovering the cache-poisoning bug by shipping it.

**Negative / accepted trade-offs**

* This ADR does not resolve the promotion slice's own nested-vs-flat decision for `#2468` — that
  remains genuinely open, and `#2468`'s own future ADR must still make that call for the doctrine
  artifact-kind path, independent of the roster-layout call made here.
* The `rglob`-vs-`glob` behavior in `CharterPackManager.list_available_detailed` is not fixed by
  this mission; it is neutralized only for the flat directories this mission introduces. A future
  per-type-subdirectory addition to a different charter-activatable kind under a recursively
  scanned root would still hit the same class of trap.

**Neutral**

* `MissionTypeRepository.default()` and its `cls`-keyed cache are unchanged; all built-in
  mission-type resolution behavior is unaffected by this mission.

## References

* Sequencing ADR this relates to:
  [`docs/adr/3.x/2026-08-05-1-mission-type-availability-before-kind-promotion.md`](./2026-08-05-1-mission-type-availability-before-kind-promotion.md)
* Promotion thread (deferred, separate ADR required): issue
  [#2468](https://github.com/Priivacy-ai/spec-kitty/issues/2468) ("mission-type as a first-class
  `ArtifactKind`"), blocked on keystone issue
  [#2467](https://github.com/Priivacy-ai/spec-kitty/issues/2467) (pack-split).
* Mission spec (binding decision records CL-001, CL-002, CL-005; constraints C-002, C-003):
  `kitty-specs/up-mission-type-seam-01KZY1JB/spec.md`
* Mission plan (Implementation Concern Map preamble stating WP01's required contents):
  `kitty-specs/up-mission-type-seam-01KZY1JB/plan.md`
* Follow-up scope for the underlying `rglob`/`glob` behavior:
  `kitty-specs/up-mission-type-seam-01KZY1JB/tasks/WP05-activate-layer-scan.md`
