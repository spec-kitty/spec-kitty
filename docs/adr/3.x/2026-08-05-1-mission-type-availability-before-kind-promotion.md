---
title: 'ADR: Sequence Charter-Activation-Driven Mission-Type Availability Ahead of Mission-Type-as-ArtifactKind; Land It With Mission-Tree Resolution Unification as One Slice'
description: 'Sequences charter-activation-driven mission-type availability ahead of mission-type-as-ArtifactKind, landed with mission-tree resolution unification as one slice.'
status: Accepted
date: '2026-08-05'
doc_status: active
kind: ADR
updated: '2026-08-05T00:00:00Z'
---

## Context and Problem Statement

The end-state the epic [#2466](https://github.com/Priivacy-ai/spec-kitty/issues/2466)
("Doctrine/Charter extensibility & pack ecosystem") calls **fully doctrine-provided,
charter-loaded mission types** — a single canonical mission-type source where a type is
*offered* iff the charter activation set says so, and `software-dev` is an ordinary peer
doctrine type with no filesystem-position-implies-availability logic anywhere — has been
**repeatedly deferred across successive missions**. [PR #3204](https://github.com/Priivacy-ai/spec-kitty/pull/3204)
(mission `doctrine-consumer-surface-missions-extraction`, closes
[#3091](https://github.com/Priivacy-ai/spec-kitty/issues/3091)) is the latest instance: it
landed the *physical* relocation of built-in mission data to `packs/built-in/missions/`
and deferred everything else by explicit spec constraint (C-002).

This ADR records **why** the deferral keeps happening and the sequencing decision that
breaks it, so the next slice is scoped correctly rather than re-bundling the whole endgame
and deferring again.

The end-state decomposes into three technically independent pieces that prior scoping
treated as one:

| Piece | Nature | Status | Real blocker |
|---|---|---|---|
| Relocate mission data → `packs/built-in/missions/` | file move | **done** (#3204) | — |
| **Availability from the charter activation set** — [#2652](https://github.com/Priivacy-ai/spec-kitty/issues/2652) chain, delete `specify_cli/missions/` | runtime behaviour | deferred | [#2657](https://github.com/Priivacy-ai/spec-kitty/issues/2657) provisioned default charter (unstarted) |
| **`mission-type` as a first-class `ArtifactKind`** — [#2468](https://github.com/Priivacy-ai/spec-kitty/issues/2468) | type system | deferred | [#2467](https://github.com/Priivacy-ai/spec-kitty/issues/2467) keystone pack-split (L, high blast radius, unstarted) |

The deferral is **structural, not effort-related**: the visible "move mission types" work
is a leaf sitting on two unstarted foundations (#2467 and #2657). Every run that scopes the
leaf reaches one of these foundations, finds it absent, and defers the *whole* chunk rather
than claiming a foundation.

Two facts change the calculus and make the deferral fixable now:

1. The type-system piece (#2468) genuinely needs the keystone pack-split (#2467), *and*
   #3204 introduced a new sub-decision under it (the mission-type content lives **nested** at
   `packs/built-in/missions/mission_types/`, but every other built-in kind resolves through
   the **flat** `doctrine.pack_paths.built_in_dir(kind)` convention). That piece is
   legitimately large and blocked.
2. The availability piece (#2652 chain) does **not** need the keystone. Its first child
   #2658 (templates-as-config) is already **closed**. The chain is now
   `#2658 ✅ → #2659 → #2660 → #2661`, and #2659 is blocked by exactly **one** unstarted
   issue: #2657. The behaviour the user actually named — "charter-loaded mission types" —
   is delivered by this chain, independent of the artifact-kind promotion.

Separately, #3204 left its own resolution debt as [#3210](https://github.com/Priivacy-ai/spec-kitty/issues/3210):
two parallel `get_package_asset_root` implementations (`src/kernel/paths.py` and
`src/specify_cli/runtime/home.py`) with `_find_relocated_missions_ancestor` byte-duplicated,
a false "re-exported by" docstring, and `default_missions_root()` ignoring
`SPEC_KITTY_PACKS_ROOT` (an env split-brain where directives/styleguides honour the
override but missions silently do not). Nothing mis-resolves today, but this is *exactly*
the kind of two-door mission-tree ambiguity that would confuse the availability rework built
on top of it.

## Decision Drivers

* **Break the deferral by claiming a foundation, not the leaf.** As long as the work is
  scoped as "relocate mission types," it re-derives its blockers and defers. The scope must
  name a foundation issue as its headline.
* **Separability of the two halves.** "Charter-loaded availability" (#2652/#2657) and
  "mission-type as a doctrine kind" (#2468/#2467) are independent. Only the second needs the
  keystone. Prior scoping conflated them and inherited the keystone's weight unnecessarily.
* **Deliver the behaviour the user named, on the shortest unblocked path.** The user's phrase
  maps to activation-driven availability, which is one unstarted issue (#2657) away — not the
  L-sized keystone.
* **Resolve the resolution seam before building on it.** #3210 is a precondition for trusting
  a single mission-tree door; the availability rework (#2659) resolves availability *through*
  that door. Landing them together avoids repointing the same readers twice.
* **No silent contract reversal.** #2468 reverses a deliberate, tested "no silent fallback"
  contract (R-009/CL-1, FR-032, pinned by `tests/doctrine/test_org_pack_augmentation.py`) and
  must carry its own decision record; it must not be smuggled into an availability slice.

## Decision

**Decouple the two mission-type threads and sequence the charter-activation-driven
availability thread first.**

1. **The next slice is the resolution + availability foundation**, bundling **#2657
   (provisioned default charter)** and **#3210 (mission-tree resolution unification)** into a
   single mission:
   - **#3210** collapses the two-door `get_package_asset_root` into one authority, removes the
     duplicated `_find_relocated_missions_ancestor`, corrects the false re-export docstring,
     and makes `default_missions_root()` honour `SPEC_KITTY_PACKS_ROOT` — so there is *one*
     resolution door with consistent env-relocation semantics.
   - **#2657** retires the implicit "all four built-in types" fallback
     (`src/charter/mission_type_profiles.py:388-395` and the analogous `charter.pack_context`
     fallback) so the provisioned default charter (`src/charter/packs/default.yaml`, migration
     `m_3_2_0rc35_default_charter_pack`) is the single authority for the activation set, with
     fail-closed provisioning for both legacy-migration and fresh-init projects.
   - These two are bundled because they are the *foundation the availability chain stands on*:
     #2659 resolves availability through the mission-tree door (#3210) using the activation set
     as the single authority (#2657). Landing them together repoints the mission-tree readers
     exactly once.
2. **#2659 → #2660 → #2661** (the remainder of the #2652 chain, delivering
   activation-driven enumeration and the deletion of `specify_cli/missions/`) follow as
   sequenced slices once this foundation is in, **without** waiting on the keystone.
3. **#2468 (mission-type as `ArtifactKind`) stays parked behind #2467 (keystone pack-split)**
   and is *not* part of this or the immediately following slices. The runtime "charter-loaded"
   behaviour does not depend on it.

## Consequences

**Positive**
- The behaviour the user named ships on the shortest unblocked path: after this slice, only
  #2659–#2661 (already sequenced, no new foundations) stand between here and a single
  activation-driven availability authority.
- The repeated-deferral pattern is closed at its cause: a foundation issue (#2657) is the
  headline, so a run cannot reach it, find it missing, and defer.
- #3204's own resolution debt is retired as part of the seam the availability work builds on,
  rather than accreting as a separate never-scheduled cleanup.
- #3183 (the `UnknownMissionTypeError` activated-vs-available vocabulary collision) is
  resolved by #2657 making "activated" the single authority, rather than being inherited.

**Negative / accepted trade-offs**
- The type-system unification (#2468) remains deferred, so `mission-type` continues to be
  admitted via the `_ORG_DRG_KIND_ALIASES["mission_types"]` side channel and
  `MissionTypeNotAnArtifactKind` stays raised until the keystone (#2467) lands. This is
  intentional: it is the larger, keystone-blocked half and carries a tested-contract reversal
  that needs its own decision record.
- Bundling #2657 (charter activation semantics) with #3210 (kernel/path resolution) crosses
  two layers in one mission. Accepted because both converge on the single question "how is a
  mission type resolved and offered," and splitting them would repoint the same mission-tree
  readers twice.

**Explicitly out of scope (deferred, not decided here)**
- The **nested-vs-flat** mission-type path decision (#2468: flatten `mission_types/` to a
  top-level pack dir to fit the `built_in_dir` convention, vs. teach `built_in_dir` a nested
  `missions/` mission-tier exception). It belongs to the #2468 promotion and should get its own
  short decision record when that slice is scoped. This ADR does **not** bind it.
- The kernel↔doctrine **schema** coupling follow-up flagged by #3204.

## References

- Epic: [#2466](https://github.com/Priivacy-ai/spec-kitty/issues/2466)
- Availability thread: [#2652](https://github.com/Priivacy-ai/spec-kitty/issues/2652)
  (chain), [#2657](https://github.com/Priivacy-ai/spec-kitty/issues/2657),
  [#2659](https://github.com/Priivacy-ai/spec-kitty/issues/2659)
- Resolution unification: [#3210](https://github.com/Priivacy-ai/spec-kitty/issues/3210)
- Type-promotion thread (deferred): [#2468](https://github.com/Priivacy-ai/spec-kitty/issues/2468),
  [#2467](https://github.com/Priivacy-ai/spec-kitty/issues/2467)
- Landed relocation: [PR #3204](https://github.com/Priivacy-ai/spec-kitty/pull/3204),
  [#3091](https://github.com/Priivacy-ai/spec-kitty/issues/3091)
- Coherence ADR this refines:
  [2026-07-15-1-doctrine-offers-charter-activates-runtime-consumes.md](./2026-07-15-1-doctrine-offers-charter-activates-runtime-consumes.md)
- Wheel-cutover assessment (downstream consumer of a settled mission home):
  [2026-08-02-1-charter-wheel-assessment.md](./2026-08-02-1-charter-wheel-assessment.md)

## Addendum (2026-08-05) — #3210 resolver shape sharpened after the post-plan review

The post-plan review squad on mission `resolution-activation-foundation-01KZ9FKG` showed the original
"one resolution door via a thin re-export" framing was incomplete: `packs/built-in/missions` is
resolved by **two** functions with disjoint caller bases — `kernel.paths.get_package_asset_root` (the
door) and `doctrine.missions.repository.default_missions_root` — and only the latter was being made
`SPEC_KITTY_PACKS_ROOT`-aware. Re-pointing `home.py` at the kernel door would have left the door and
its ~7 consumers env-blind, i.e. the split-brain would move, not die.

**Operator decision (2026-08-05): unify the resolver. The `built-in` pack — missions included — is
installed/available from the default- or env-supplied pack root ("PACKS_HOME" = `SPEC_KITTY_PACKS_ROOT`).**
The mission-tree is `<built-in-pack-root>/missions`, resolved through one primitive:

- The **kernel** floor owns a `SPEC_KITTY_PACKS_ROOT`-aware built-in-pack-root resolver (kernel reading
  an env var is layer-legal; it does not import doctrine). `kernel.sibling_paths.resolve_installed_sibling`
  already exists as the env-agnostic algorithm; the env read moves to a kernel entry point.
- `doctrine.pack_paths._resolve_built_in` delegates to it (retiring the duplicate `SPEC_KITTY_PACKS_ROOT`
  read at `pack_paths.py:204`).
- `doctrine.missions.repository.default_missions_root()` becomes `built_in_root() / "missions"` — so it
  inherits PACKS_ROOT-awareness by construction (the FR-003 fix by unification, not a bolt-on).
- The kernel door resolves the same `<built-in-pack-root>/missions`, so door consumers honor PACKS_ROOT
  uniformly. `home.py`'s `specify_cli/missions`/`dev_root` legacy fallbacks are intentionally dropped —
  fail-closed, not fall-through.
- `SPEC_KITTY_TEMPLATE_ROOT` retains its distinct role as the asset-copy/template override (it is used
  across `template/manager.py`, `asset_generator.py`, `init.py`, `bootstrap.py`, and upgrade migrations);
  precedence: `SPEC_KITTY_PACKS_ROOT` governs pack-root *location* and wins when both are set. A
  door-caller census confirms TEMPLATE_ROOT semantics are preserved for the copy path.

This also subsumes the sibling-pattern-literal duplication (three drifting `packs/built-in/missions`
constants collapse onto the kernel primitive + the existing `missions` leaf name). The mission's spec,
plan, and contracts are revised accordingly; `_find_relocated_missions_ancestor` is **logically**
duplicated (not byte-identical — the "byte-duplicated" wording earlier in this ADR is loose; the code
uses a constant in kernel and an inline literal in home.py).

## Addendum (2026-08-07) — DR-1 silent-parity behaviour superseded: misconfigured `SPEC_KITTY_PACKS_ROOT` now warns loudly

The 2026-08-05 addendum above records DR-1 (mission `resolution-activation-foundation-01KZ9FKG`,
`post-plan-review-findings.md`): unify the built-in pack resolver behind one kernel-floor primitive,
`kernel.paths.get_built_in_pack_root`. One consequence of that unification, carried over unchanged from
the pre-collapse resolver for behaviour-parity, was that a **set-but-unresolvable**
`SPEC_KITTY_PACKS_ROOT` — the value is present, but `<value>/built-in` does not exist as a directory —
resolved *silently* to the installed/ancestor-walk sibling. The override lost the race, but nothing told
the operator it had.

**Operator decision (2026-08-07): this silent parity is superseded.** It is cleaner to inform an
operator of a misconfigured environment than to silently load a possibly-unrelated doctrine/charter pack
on their machine. Resolution stays **fail-open** — a broken override must not hard-break every command —
but the fallback is now **loud**: `get_built_in_pack_root` emits a `UserWarning` naming the misconfigured
`SPEC_KITTY_PACKS_ROOT` value and the `built-in` path it failed to resolve, before falling through to the
ancestor-walk-resolved installed sibling. This is a narrow amendment to DR-1's fallback framing, not a
reversal of DR-1 itself: there is still exactly one resolution primitive, and it still does not raise on
the override — only the silence is removed. See `src/kernel/paths.py::get_built_in_pack_root` and its
regression coverage in `tests/kernel/test_paths.py`.
