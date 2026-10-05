---
title: 'ADR: org packs ship their own built-in override sanction'
description: 'An org pack lists the built-ins it replaces in a pack-root replaceable-builtins.yaml; doctor doctrine honours it for that pack only, and the consumer can revoke it.'
status: Accepted
date: '2026-10-05'
updated: '2026-10-05'
---

**Status:** Accepted

**Date:** 2026-10-05

**Deciders:** Stijn Dejongh (repository owner).

**Technical Story:** [#5767](https://github.com/spec-kitty/spec-kitty/issues/5767), Mission `pack-shipped-builtin-override-sanction-01M45WB7`.

**Reader:** a maintainer changing `spec-kitty doctor doctrine`, org-pack validation or assembly, or the work for [#2216](https://github.com/spec-kitty/spec-kitty/issues/2216) and [#2594](https://github.com/spec-kitty/spec-kitty/issues/2594).

---

## Context and Problem Statement

The three-layer DRG merge lets an org node replace a built-in node of the same kind in place. Whether a given repository accepts that replacement is a governance decision, made by `charter.offering.drg.override_policy` from one file in the consumer repository, `.kittify/doctrine/replaceable-builtins.yaml` (see [the doctrine layer merge ADR](../3.x/2026-05-16-1-doctrine-layer-merge-semantics.md) and Mission `doctrine-governance-fidelity-01KW42KY`, where the check is fail-closed, NFR-004). An override that the file does not list makes `spec-kitty doctor doctrine` exit 1.

The sanction lived only in the consumer repository. An org pack that wanted to replace built-ins could ship a template at `templates/setup/replaceable-builtins.yaml`, and the consumer was expected to copy it. Nothing read that template. The copy drifted: when upstream promoted an org-authored artifact into the built-in set, the pack's same-id artifact became an override of a built-in. Every consumer whose copied file predated the promotion then failed `doctor doctrine` with exit 1, although the consumer had changed nothing ([#5767](https://github.com/spec-kitty/spec-kitty/issues/5767)).

## Decision

An org pack ships its sanction in a `replaceable-builtins.yaml` at its **pack root**: the resolved root of the pack, including any configured `subdir`. The file uses the same entry grammar as the consumer file, `replaceable_builtins: [{urn, reason}]`. `doctor doctrine` reads it in place; nothing is copied into the consumer repository.

All sanction semantics (parse, scope, union, revoke, decision table) live in `charter.offering.drg.override_policy`. One loader, `load_effective_override_policy`, combines the consumer file, every pack's file and the revocations, and feeds both `doctor doctrine` and the built-in-override architectural gate, so the two cannot adjudicate differently. The verdict predicates stay free of I/O.

Rules:

1. **Scoped to the contributing pack.** A pack entry sanctions an override only when the surviving node was contributed by that same pack. The pack is identified by the registry name in the consumer's configuration, taken from the loaded fragments, never by a name the pack declares. Pack B cannot sanction pack A's override.
2. **Unioned with the consumer file, which is checked first.** A valid consumer entry sanctions the override and is reported as the source.
3. **A directive needs a reason.** A built-in directive override is sanctioned only by an entry with a non-empty reason, whichever source supplies it.
4. **Revocable.** The consumer file gains an optional `revoked_pack_sanctions` list whose entries are `{urn}` or `{pack}`, each with an optional reason. A revocation withdraws only what packs delivered; an entry in the consumer's own `replaceable_builtins` still sanctions.
5. **Fail closed and isolated.** An override that nobody sanctions still exits 1. A pack file that is malformed, unreadable, not a regular file, or resolves outside the pack root voids only that pack's sanctions and makes the report unhealthy with an error naming the pack and the file. Every loaded pack's file is checked, whether or not the pack overrides anything. A `revoked_pack_sanctions` key in a pack file is an error, because that key is consumer-only.
6. **Visible.** The report lists every sanctioned override with its source and reason, on green runs too.

### Decision table

For one surviving org override of built-in `U`, contributed by pack `P`. "Valid" means the entry lists `U` and, for a directive, carries a non-empty reason.

| Consumer allowlist | Pack `P` sanction | Consumer revokes `U` or `P` | Verdict | Reported source or finding |
|---|---|---|---|---|
| valid | any | any | sanctioned | consumer |
| absent or invalid | valid | no | sanctioned | pack `P` |
| absent or invalid | valid | yes | unsanctioned | pack sanction revoked by the consumer `replaceable-builtins.yaml` |
| absent | absent | not applicable | unsanctioned | not on the consumer file or pack `P`'s `replaceable-builtins.yaml` |
| absent or not listing `U` | lists `U`, directive, empty reason | no | unsanctioned | directive override requires a non-empty reason (pack `P`) |
| lists `U`, directive, empty reason | absent or invalid | no | unsanctioned | directive override requires a non-empty reason |

A revocation is reported in preference to a reason finding when the pack would otherwise have sanctioned `U`. Revoking a URN the pack never sanctioned changes nothing, and a revocation that names another pack does not affect `P`.

### Report shape

`doctor doctrine --json` gains three additive keys under `profile_health.org_drg`, each present only when non-empty: `sanctioned_overrides` (`urn`, `kind`, `pack`, `source`, `reason`), `pack_sanction_errors`, and, on each `unsanctioned_overrides` entry, an optional `legacy_template`. Every sanction error is also appended to `errors`, which drives exit 1. The frozen top-level `profile_health` key set is unchanged. With no org packs configured the output is byte-identical to before.

Two checks are new and deliberate. A malformed consumer allowlist is now reported as an error that names the file, and is treated as empty. A `revoked_pack_sanctions` entry that names a pack that is not configured (exact, case-sensitive match) is an error, so a typo can never leave a sanction in force that the operator believes revoked. Both make `doctor doctrine` unhealthy even when no org override exists.

### Authoring tools

- `spec-kitty doctrine pack validate` parses the pack-root file with the same parser. A malformed file, or a directive entry without a reason, is an error; an entry the pack does not override is an advisory (category `pack_sanction`).
- `spec-kitty doctrine pack assemble` writes the union of its inputs' sanction files to the assembled pack root. Two inputs that give the same URN different reasons are a conflict (artifact type `replaceable_builtins`); `--force` keeps the last pack's reason.

## Considered Options

1. **Read the pack's file in place (chosen).** No copy exists, so nothing drifts, and scoping per pack is possible because provenance is `org:<registry name>`.
2. **Fetch installs the file into the consumer repository.** Rejected. The copy drifts on the next promotion, scoping is lost, `doctrine fetch` would mutate consumer governance, it never runs for local-path packs, and it has no lifecycle.
3. **A per-node `replaces:` marker.** Rejected. The marker is absent at the moment of promotion, and it would widen a strict node schema.
4. **A key in `org-charter.yaml`.** Rejected. `OrgCharterPolicy` refuses unknown keys, so a new key would break every CLI already shipped, pack assembly rebuilds `org-charter.yaml` from four keys only, and the sanction logic must live in `charter.offering`, which cannot import that model.

## Consequences

- A pack author moves the sanction to the pack root once. A consumer who refreshes the pack stays green across later built-in promotions, with no edit in the consumer repository.
- **Legacy template hint (transitional).** A template at `templates/setup/replaceable-builtins.yaml` is never a sanction. For an unsanctioned override whose own pack lists the URN there, `doctor doctrine` still exits 1 and prints the pack-author move and the exact `{urn, reason}` entry to append to the consumer file. The one exception is a directive whose template entry has no reason: the hint then says a reason is required instead of printing an entry. It never prints a whole-file copy command, because a copy would overwrite consumer entries and revocations, bypass scoping and drift again. A malformed template yields no hint and no error. The probe is removed with #2594.
- **API sources.** A pack fetched through an API source does not carry pack-root files, so it delivers no sanction and the consumer file still governs.
- **Integrity.** The sanction file has the integrity of the pack's other files. Git and https fetches hash the whole tree at fetch time; local-path packs carry no integrity check. It is not recorded in the pack-manifest constituents, whose model refuses entries that are not artifact kinds, and `doctor doctrine` does not verify it.
- **Bounded I/O.** `doctor doctrine` reads at most one sanction file per configured pack, plus at most one legacy template per unsanctioned override.
- **Compatibility.** A CLI that predates this change ignores both the pack-root file and the `revoked_pack_sanctions` key, with no new errors or warnings.
- **Unchanged.** DRG merge behavior, and the intentional exemption of project-tier overrides (`doctrine-governance-fidelity-01KW42KY`, FR-012). When several packs override one built-in, the last pack's node survives and only that node is adjudicated, against its own pack's sanction.

### Absorption by #2594

Delegated governance in [#2594](https://github.com/spec-kitty/spec-kitty/issues/2594) can absorb this design without new concepts. The pack sanction becomes the pack's declared overlay intent, and the revocation becomes consumer narrowing of a delegated sanction, the consumer-side counterpart of `governed` and `locked`. The entry grammar `{urn, reason}` is the only governance concept introduced here.

### Follow-ups, not in scope

- Make `OrgCharterPolicy` tolerant of unknown keys when the schema version is newer, as groundwork for #2594.
- Edges that a losing org pack contributes at a built-in URN, and edge-form `overrides` and `enhances` relations that target a built-in, are not adjudicated. Tracked in [#5769](https://github.com/spec-kitty/spec-kitty/issues/5769) and [#5770](https://github.com/spec-kitty/spec-kitty/issues/5770).
- Updating the external org packs to move their template to the pack root is outside this repository.
