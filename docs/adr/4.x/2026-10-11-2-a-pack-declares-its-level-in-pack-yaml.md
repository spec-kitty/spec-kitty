---
title: 'ADR: a Charter Pack declares its level in pack.yaml'
description: 'Every Charter Pack declares its level (built-in, org or project) in pack.yaml; loading refuses a pack whose declared level disagrees with where it is configured.'
status: Accepted
date: '2026-10-11'
related:
- docs/adr/3.x/2026-08-16-1-pack-metadata-manifest-unification.md
- docs/adr/3.x/2026-08-16-2-open-packs-is-source-of-truth-for-built-in-doctrine.md
- docs/adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md
---

**Status:** Accepted

**Date:** 2026-10-11

**Deciders:** Stijn Dejongh (owner; ruled on the model and the vocabulary on 2026-10-11).

**Technical Story:** the layout question on
[spec-kitty-open-packs#32](https://github.com/spec-kitty/spec-kitty-open-packs/pull/32)
(seeding the built-in pack into open-packs for [#3504](https://github.com/spec-kitty/spec-kitty/issues/3504)).
Related: [#5961](https://github.com/spec-kitty/spec-kitty/issues/5961) and
[#5992](https://github.com/spec-kitty/spec-kitty/issues/5992) (pack-tier spelling), [#6048](https://github.com/spec-kitty/spec-kitty/issues/6048) (implementation),
[#6046](https://github.com/spec-kitty/spec-kitty/issues/6046) (`requires_core`, another `pack.yaml` field).

## Context and Problem Statement

A Charter Pack's level is never declared. It is inferred from how the pack was wired in:

* the built-in pack is the directory `resolve_pack_root("built-in")` finds;
* an org pack is a directory listed under `charter_packs.org.packs` in `.kittify/config.yaml`;
* a project pack is the directory under `.kittify/charter-packs/`.

Only the built-in pack has a `pack.yaml` (`PackDescriptor`: `pack_id`, `pack_version`,
`parent_pack`, `name`). Org packs such as `qa` are recognised by the files they hold
(`org-charter.yaml`, `drg/fragment.yaml`). The validator infers what to expect from those files.

That inference broke as soon as packs started living outside the repository that uses them.
Seeding the built-in pack into `spec-kitty-open-packs` (#32) showed it:

* placed under `packs/`, the built-in pack was registered as an org pack by that repository's CI;
* `doctor charter-packs` then failed, because it had no `drg/fragment.yaml`;
* it also shadowed the CLI's own built-in layer.

Nothing in the pack said what it was, so nothing could refuse the mistake.

The level names themselves have no single owner either. Code spells the built-in level both
`"built-in"` and `"builtin"` (#5961, #5992), and about 93 source files carry the layer literals.

## Decision Drivers

* A pack must say what it is, so a wrong placement is refused by name rather than discovered
  by a downstream failure.
* Reuse the vocabulary the product already speaks (config keys, glossary, paths). Do not add
  a third one.
* One authority for the level names, which #5961 needs anyway.
* Avoid terms that already mean something else: "root pack" already means a pack with no
  `parent_pack`.

## Considered Options

* **Field name:** `pack_level`, `pack_tier`, `layer`.
* **Values:** `built-in` / `org` / `project` (A); `core` / `org` / `project` (B);
  `base` / `organization` / `project` (C); `root` / `organisational` / `repository`
  (the first proposal).

## Decision Outcome

**Chosen: `pack_level` with values `built-in`, `org` and `project`.**

1. **Every Charter Pack has a `pack.yaml`, and it declares `pack_level`.** It is a required
   field of `PackDescriptor` and must be one of `built-in`, `org` or `project`. `pack_id`,
   `pack_version`, `parent_pack` and `name` are unchanged.
2. **The level names have one authority.** A single enum in `charter.offering.packs` owns the
   three values. Every layer literal, including the `"builtin"` spelling (#5961, #5992),
   derives from it.
3. **Loading refuses a mismatch.** A pack whose declared `pack_level` disagrees with where it
   was configured is refused with `PACK_LEVEL_MISMATCH`, naming the file, the declared level
   and the configured one. A `pack.yaml` without the field is refused with
   `PACK_LEVEL_MISSING`, after the migration window described below.
4. **The validator branches on the declared level**, not on the files it finds. For example,
   `drg/fragment.yaml` and `org-charter.yaml` are expected of `org` packs, and the sharded
   `*.graph.yaml` plus a generated `pack-manifest.yaml` of the `built-in` pack.
5. **Migration.** An upgrade migration writes `pack.yaml` (minting a `pack_id`) with
   `pack_level: project` for an existing project pack. For one release, an org pack without a
   `pack.yaml` loads with a deprecation warning that names the file to add. After that it is
   refused.

Rejected:

* **`root` / `organisational` / `repository`.** "root pack" already means a pack with no
  `parent_pack`. `organisational` fails the US-spelling docs gate and disagrees with the
  config key `org`. `repository` clashes with `project` and with "repository root checkout".
* **`pack_tier` and `layer`.** "Tier" is overloaded (model tiers, tiered rigour). `layer` is
  overloaded by the architectural layer rules.
* **Values B and C.** Both rename what config, paths and the glossary already say.

### Consequences

#### Positive

* A mis-placed pack is refused at load with a named code. The open-packs layout question is
  settled: `built-in/` can live at `packs/built-in/`, and open-packs CI registers only packs
  that declare `org`.
* #5961 gets its single owner for the tier spelling.
* The validator's expectations become explicit per level.

#### Negative

* Every org and project pack must gain a `pack.yaml`. That needs a migration for consumer
  project packs and a deprecation window for org packs.
* This is a `PackDescriptor` schema change. Bundle it with `requires_core` (#6046) so pack
  authors meet one schema bump, not two.
* The open-packs layout fix waits for a core release that ships the field.

### Confirmation

* `charter pack validate` refuses a pack without `pack_level` once the window closes, and
  refuses one whose level disagrees with its configured position.
* An architectural test pins that every layer literal in `src/` derives from the single enum.
* In open-packs, the built-in pack moves to `packs/built-in/` with `pack_level: built-in`, and
  `validate-packs.sh` registers only `pack_level: org` packs.
