---
title: 'ADR: charter offering, active charter and activation presets'
description: 'A Charter Pack bundles charter components with activation presets applied by charter activate; the doctrine names are cut over with no aliases or shims.'
status: Accepted
date: '2026-10-06'
updated: '2026-10-06'
---

**Status:** Accepted

**Date:** 2026-10-06

**Deciders:** Stijn Dejongh (repository owner).

**Technical Story:** [#3732](https://github.com/spec-kitty/spec-kitty/issues/3732) (rename doctrine packs to charter packs), with [#5323](https://github.com/spec-kitty/spec-kitty/issues/5323) and [#4400](https://github.com/spec-kitty/spec-kitty/issues/4400).

**Reader:** a maintainer or agent executing the #3732 rename, or changing pack loading, charter activation, the `charter` / `doctrine` CLI groups, or the shipped `spk-*` skills.

---

## Context and Problem Statement

PR #3791 settled two words for the rename of "doctrine pack": **Charter Pack** for the offered collection, and **Pack Default Charter** for the older meaning of "charter pack". Classifying every occurrence at `b327f5bb` showed that this was not enough to rename safely:

- **"charter pack" has three meanings in the code, not two.** The config key `charter_packs.org.packs` and the directory `.kittify/charter-packs/` already mean the offered collection. `spec-kitty charter pack list|path|apply`, `src/charter/activation/packs/{default,minimal}.yaml` and the `3.2.0rc35_default_charter_pack` migration mean a ready-made activation set. `CharterPackManager`, `CharterPackConfigError` and the error code `CHARTER_PACK_CONFIG_INVALID` mean a project's own activation state. The contract had no word for the third meaning.
- **The CLI name was taken twice over.** Retiring `spec-kitty doctrine` sends `doctrine pack validate|assemble` to `charter pack`, which already holds the activation-set commands.
- **The "default charter pack" is a drifted copy.** `default.yaml` says it lists every built-in artifact id; it lists about 200, and at `b327f5bb` it missed 91 shipped artifacts across seven kinds (matching each file by YAML `id` or filename stem; a stricter match finds about 100). Nothing regenerates it or compares it to `packs/built-in/`. The rc35 upgrade migration and `charter pack apply default` write it into `.kittify/config.yaml`, where a present `activated_<kind>` key is an allowlist, so those projects silently lose every newer built-in ([#5323](https://github.com/spec-kitty/spec-kitty/issues/5323)). Three activation-promotion callers narrow an absent key with the same file ([#4400](https://github.com/spec-kitty/spec-kitty/issues/4400)).
- **The presets are not part of any pack.** They are registered in a hard-coded `BUILTIN_PACKS` map in `specify_cli` and live outside `packs/built-in/`; the pack descriptor does not know them. Packs are going to ship from the spec-kitty public-packs sidecar repository, where a code-registered preset cannot exist.
- **The `spk-doctrine-*` skill family mixes two things.** Four skills are charter governance (charter, glossary, profile loading, the REASONS canvas); three are working practices unrelated to the charter (bulk-edit classification, semantic compression, show-me visuals). An older `spec-kitty-*` name layer still ships beside them and often holds the real content.
- **Earlier renames left compatibility layers with no end date.** The `spec-kitty doctrine` group, the `doctrine.*` config keys and the `.kittify/doctrine/` read root each warn once and keep working, with no removal milestone, so in practice they are permanent.

`docs/context/charter.md` cites ADR `2026-08-22-2` (§74, §76–77) for the earlier definitions, but that ADR is not in the repository. This ADR therefore states the vocabulary in full rather than amending it.

## Decision

### 1. The model: charter offering and active charter

The charter has two sides, matching the existing package split `src/charter/offering/` and `src/charter/activation/`:

| Term | Meaning | Replaces |
|---|---|---|
| **Charter offering** | Everything that is *offered* to a project: the Charter Packs it can draw from. | "doctrine" as the name of the offer-side tier |
| **Charter Pack** | A distributable bundle of interconnected charter components (artifacts and their DRG edges) together with a set of **activation presets**. An org pack may also enforce activations (`required_<kind>` in `org-charter.yaml`). | "doctrine pack" |
| **Activation preset** | A named set of activations that a Charter Pack ships, applied to a project by activating it. | "Pack Default Charter", and the old meaning of "charter pack" |
| **Active charter** | What a project has activated: its `activated_<kind>` keys and `mission_type_activations`. | the third meaning of "charter pack" (`CharterPackManager`, `CHARTER_PACK_CONFIG_INVALID`) |
| **Charter Bundle** | Unchanged: the materialised `.kittify/charter/` tree. | — |

"Active" and "inactive" still describe a single artefact's state ("an active directive"). The glossary guard that "active" never describes bundle state is amended: **active charter** names the project's activated set as a whole.

### 2. Applying a preset is an activation

```
spec-kitty charter activate --pack <pack> --preset <preset>
```

`--pack` defaults to `built-in`. The built-in pack ships two presets:

- **`default`**: every built-in artifact, plus the built-in mission types. It is expressed as *no per-kind restriction* (the per-kind keys stay absent, which already means "all built-ins"), never as a list of ids, so it cannot drift from the shipped inventory.
- **`minimal`**: the curated small baseline (today's `minimal.yaml`).

Skipping charter activation during `spec-kitty init` is the same as `charter activate --pack built-in --preset default`. Today's fresh `init` already behaves this way for artifact kinds: it writes only `mission_type_activations` and leaves the per-kind keys absent. It reads that mission-type list from `src/charter/activation/packs/default.yaml` and fails closed when the file is missing (`provision_default_mission_type_activations`, `DefaultCharterPackMissingError`); that read moves with the preset, to the built-in pack's `default` preset.

### 3. Presets are pack data

A preset lives inside its pack, next to the pack's components, and is discovered from the pack, for the built-in pack and for any fetched or org pack alike. There is no code registry of presets. `src/charter/activation/packs/` and `BUILTIN_PACKS` are removed. The pack descriptor field `accompanies_doctrine_pack`, which described a separate pack accompanying a doctrine pack, is retired: a pack carries its own presets.

### 4. The CLI

| Before | After |
|---|---|
| `charter pack apply <name>` | `charter activate --pack <pack> --preset <preset>` |
| `charter pack list` (presets only) | `charter pack list`: packs and the presets each one ships |
| `charter pack path <name>` | `charter pack path <pack>` |
| `doctrine pack validate`, `doctrine pack assemble` | `charter pack validate`, `charter pack assemble` |
| `charter pack consistency-check` | a top-level `charter` subcommand; it checks the active charter, not a pack |
| `doctrine regenerate-graph`, `doctrine asset` | a home under `spec-kitty charter` |
| `doctrine mission-type list` | already replaced by `charter mission-type list --include-inactive`; removed with the group |
| `spec-kitty doctrine` group | removed once its last command has moved |

`charter pack` holds operations on Charter Packs (the offering). Activation operations, presets included, stay on `charter activate` and `charter deactivate`.

### 5. Skills

| Before | After |
|---|---|
| `spk-doctrine-charter` | `spk-charter-governance` |
| `spk-doctrine-glossary` | `spk-charter-glossary` |
| `spk-doctrine-profile-load` | `spk-charter-profile-load` |
| `spk-doctrine-spdd-reasons` | `spk-charter-spdd-reasons` |
| `spk-doctrine-bulk-edit` | `spk-practice-bulk-edit` |
| `spk-doctrine-semantic-compression` | `spk-practice-semantic-compression` |
| `spk-doctrine-show-me` | `spk-practice-show-me` |

`spk-practice-*` is a new family for working practices that apply in any mission. The older `spec-kitty-*` skills (`spec-kitty-charter-doctrine`, `spec-kitty-glossary-context`, `spec-kitty-bulk-edit-classification`, `spec-kitty-spdd-reasons`, `ad-hoc-profile-load`, and the rest of that layer) are folded into the `spk-*` skill they back and deleted. Each skill ends with one name.

### 6. Names that stay

- The **`doctrine-daphne`** agent profile keeps its id and name. It is a known persona already in use; "doctrine" there is part of a name, not the retired tier.
- **"Doctrine" as the governance content itself** (the substance of a directive or tactic) stays where it is written as content.
- `DIRECTIVE_039` (named for a person) and every historical record (`kitty-specs/`, released changelog sections, ADRs, dated reports, the archive) are unchanged.

### 7. Full cutover: no aliases, no shims

Earlier renames kept the old names working for backwards compatibility. The result is a mixed bag of naming and code structures: agents and human contributors meet two names for one thing, and users' harnesses contradict themselves because one surface uses the old name while another uses the new one. This rename therefore does not repeat that approach. The old names are removed, not deprecated:

- No alias commands, alias skills or redirecting stubs. An old command name fails as an unknown command.
- The existing compatibility layers are removed: the deprecated `spec-kitty doctrine` group (after its commands move), the read-side fallbacks for the `doctrine.org.packs` and `governance.doctrine.*` config keys, and the `.kittify/doctrine/` read-root fallback.
- **Persisted project state is rewritten once, not shimmed** (confirmed by the deciders: a one-time migration is not a compatibility layer). An upgrade migration rewrites legacy config keys and moves `.kittify/doctrine/` to `.kittify/charter-packs/` during `spec-kitty upgrade`. The same migration replaces a project's `activated_<kind>` lists that equal the drifted `default.yaml` contents with the `default` preset's meaning (key absent), so projects stop losing newer built-ins. After the migration there is no read-side compatibility. A project that has not been upgraded gets an error naming `spec-kitty upgrade`.

## Consequences

**Good:**

- One meaning per word on every surface: CLI, config, code, skills, docs.
- The `default` preset cannot drift, because it lists nothing.
- Presets work for packs fetched from the public-packs sidecar repository, not only for the built-in one.
- Fixes #5323 and #4400 by construction instead of by re-listing ids.
- Removes four permanent compatibility layers instead of adding more.

**Bad:**

- A breaking release for anyone who scripts `charter pack apply`, `spec-kitty doctrine …` or a renamed skill. The changelog carries a Before/After table, and the generated agent command and skill copies are regenerated in the same change.
- A project that skips `spec-kitty upgrade` stops at the first command, with an error naming the fix.

**Neutral:**

- The `src/specify_cli/doctrine/` module path and internal `Doctrine*` identifiers are renamed as internal refactors under the same occurrence map; they are not consumer contracts.

## Execution

The rename runs as the #3732 governed mission. Its occurrence map is the classification ledger from the 2026-10-06 run (posted on #3732); this ADR is the naming contract the map binds to.
