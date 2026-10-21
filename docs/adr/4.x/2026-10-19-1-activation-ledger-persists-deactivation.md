---
title: 'ADR: one activation ledger persists deactivation, and nothing silently reinstalls it'
description: 'Activation state moves to one git-tracked file, .kittify/charter/activation.yaml, with a persistent deny-list so a deactivated charter artifact stays deactivated.'
status: Accepted
date: '2026-10-19'
updated: '2026-10-21'
---

# One activation ledger persists deactivation, and nothing silently reinstalls it

**Status:** Accepted (2026-10-19); amended 2026-10-20 (see the amendment at the end).

**Date:** 2026-10-19

**Deciders:** Stijn Dejongh (operator).

**Technical Story:** the core side of spec-kitty-charter ADR-0013 ("Deactivation persists in one
activation ledger, and nothing silently reinstalls it"), steps
[#62](https://github.com/spec-kitty/spec-kitty-charter/issues/62),
[#63](https://github.com/spec-kitty/spec-kitty-charter/issues/63),
[#64](https://github.com/spec-kitty/spec-kitty-charter/issues/64),
[#66](https://github.com/spec-kitty/spec-kitty-charter/issues/66) and
[#67](https://github.com/spec-kitty/spec-kitty-charter/issues/67). Step
[#65](https://github.com/spec-kitty/spec-kitty-charter/issues/65) (projection and resolution
filtering in the Java offering) belongs to the Java offering and is not decided here. Mission:
[spec](../../../kitty-specs/persistent-deactivation-ledger-01M59YAA/spec.md),
[plan](../../../kitty-specs/persistent-deactivation-ledger-01M59YAA/plan.md).

**Reader:** a core maintainer who reads, writes or migrates charter activation state, or who
reviews a change to the activation seam.

**Supersedes / amends:** supersedes **Decision 2 only** ("`charter.yaml` OWNS activation") of
[ADR 2026-07-18-1](../3.x/2026-07-18-1-charter-yaml-authoring-authority-and-extractor-retirement.md);
amends [ADR 2026-10-03-1](2026-10-03-1-charter-read-write-service-strangler.md) (the activation
write target) and
[ADR 2026-10-06-2](2026-10-06-2-charter-offering-active-charter-and-activation-presets.md)
(presets, synthesis). Related: [ADR 2026-10-17-1](2026-10-17-1-explicit-migration-ledger.md) (the
Migration Ledger, a different ledger), [ADR 2026-10-16-1](2026-10-16-1-extract-charter-offering-first-activation-rework-post-ga.md)
(activation rework is post-GA work; the operator brought this slice forward, constraint C-010).

---

## Context and Problem Statement

A user who runs `spec-kitty charter deactivate directive D` expects D to stay gone. Today it does
not, for four reasons.

1. **Deactivation only edits an allow-list.** It removes the id from `activated_<kind>`. When that
   key is absent (which means "every artifact is in force"), there is nothing to remove from, and
   the command raises `NoActivationRestrictionsError`.
2. **Several paths quietly bring the artifact back.** The cascade walk activates every artifact it
   reaches. The one-time rc6 cutover reset turns a list equal to the default back into "absent".
   The interview and promotion writers append ids they select or that an org pack requires.
3. **Activation state has several homes.** `.kittify/config.yaml`, the `charter.yaml` its pointer
   names, and `answers.selected_*` all carry some of it, and the read and write paths each pick one.
4. **A required artifact can be "deactivated" with no effect.** The org `required_<kind>` union
   overrides the user's intent without saying so.

An allow-list cannot hold an exclusion under "absent = all": the exclusion has to be stored as its
own fact. That needs one authoritative home, and a way to reach it for projects that already exist.

## Decision Drivers

- A deactivation must survive every later command, upgrade, interview and regeneration, until the
  user explicitly activates the artifact again.
- One file must answer "what is active here", and doctor must report any surface that disagrees.
- No runtime fallback to legacy surfaces: ambiguity is resolved by migration, not by guessing.
- Shipped migrations must behave byte-for-byte as before (DIRECTIVE_044, constraint C-001).
- The activation layer is being extracted into its own repository, so layering must hold
  (`charter.offering` never imports activation; `specify_cli` reaches it through
  `charter.activation.api`).

## Considered Options

- **A. Store exclusions inside the allow-list.** Rejected: under "absent = all" there is no list to
  remove from, and every writer that rebuilds a list can re-add the id.
- **B. A separate deny file beside the existing surfaces.** Rejected: a third home for activation
  state, with the same drift problem.
- **C. One activation ledger holding allow and deny state, with a migration into it.** Chosen.

## Decision Outcome

**Chosen option: C**, recorded as the seven decisions below.

### Decision 1: one ledger

`.kittify/charter/activation.yaml` (git-tracked) is the single authority for activation. It is a
flat mapping, and every key is optional:

| Key | Absent means | `[]` means |
|---|---|---|
| `activated_kinds` | every kind | no kind |
| `mission_type_activations` | none in force | none |
| `activated_<plural>` | the kind's `ArtifactKind.effective_when_absent` default (`"all"`, or `"required"` for `skill`) | nothing (fail-closed empty) |
| `deactivated_<plural>` | no exclusion | treated as absent, never written |

An empty `deactivated_<plural>` is omitted from the file. The key set derives from
`ArtifactKind.activatable`, never from a hand-written list (constraint C-004). An unknown
non-deny key fails closed with `ActiveCharterConfigError`. An unknown `deactivated_<x>` key (a
kind a later CLI added) is preserved, ignored by readers and reported by doctor as a warning.
`deactivated_*` keys never appear in `charter.yaml` or `config.yaml` (C-003).

The ledger is an optional tracked member of the charter bundle and an optional member of its
content hash, so an edit made outside the CLI reads as stale, and a project without a ledger keeps
its hash. Every successful ledger write restamps the bundle hash.

Every other surface derives from the ledger or is checked against it. `answers.selected_*` stays
provenance only (ADR 2026-07-18-1); a denied id listed there produces a doctor warning, not a
different answer.

### Decision 2: the effective-set algebra

For a kind *k*, with `Avail(k)` the artifacts available across the built-in, org-chain and project
layers, `R(k)` the required floor (Decision 6) and `D(k)` the ledger's deny-list:

```
D*(k)   = resolve_deny(D(k)) − R(k)            effective deny, in identity space
base(k) = S                          if the allow state is the list S
        = ∅                          if the allow state is []
        = Avail(k)                   if absent and effective_when_absent = "all"
        = R(k) (+ built-in defaults) if absent and effective_when_absent = "required"
E(k)    = base(k) − D*(k)                       the effective set
Sel(k)  = (selected_<k> ∪ R(k)) − D*(k)         the governance selection overlay
```

**Identity space.** A deny entry is a stem, but an allow entry may be a declared id (for example
`PROC_CANVAS_REVIEW` for stem `canvas-review`), and a DRG node is a URN. `resolve_deny` expands
each entry into all three spellings (`DenySet`: stems, declared ids, URNs), and membership is
tested against any of them. Without this, a stem in the deny-list would fail to subtract the
declared id in the allow-list.

The effective set is computed once, in `charter.activation`. Core readers reach it through the
`PackContext.admits` and `effective_ids` accessors, and a gate forbids raw `activated_<plural>`
membership checks outside the seam. Required artifacts are never subtracted: a stale deny entry
for a required id is inert and doctor reports it.

### Decision 3: source resolution

One resolver in the kernel (`kernel.activation_ledger_store.resolve_activation_source`) decides
where activation is read from and written to. The kernel never raises an activation-domain error;
it returns the source and the raw data, and each caller keeps its own error text.

| Ledger file | Upgrade scope | Legacy keys | Result |
|---|---|---|---|
| exists | any | none | the ledger |
| exists | any | present | the ledger; the stray keys are reported (below) |
| absent | inside | any | legacy surface, byte-for-byte as before the ledger |
| absent | outside | present | fail closed: `ActiveCharterConfigError` naming `spec-kitty upgrade` |
| absent | outside | none | the ledger (a fresh project; the first write creates the file) |

"Upgrade scope" is a kernel `ContextVar` that matches the resolved and the canonical root. It is
entered by `BaseMigration` for every public project-path method a subclass defines, by
`MigrationRegistry.get_applicable`, by the `MigrationRunner` selection points, by
`spec-kitty migrate ledger` and by the `spec-kitty upgrade` command body. That keeps shipped
migrations that write through the seam before the ledger migration unchanged (C-001).

**Stray legacy keys beside a ledger.** An ordinary command prints one warning per process naming
the keys and saying the ledger wins; `spec-kitty doctor charter-packs` reports them as an error
(`LEGACY_KEYS_PRESENT`) from the resolver's data, without going through a raising read.

**`spec-kitty init` writes the ledger** (provisioning `mission_type_activations`), so a fresh
project is never "unmigrated" and the upgrade stays a no-op on it.

### Decision 4: only explicit choices change a deny-list

Four paths, and no others, may add to or remove from a `deactivated_<plural>` list:

| Path | Effect on the deny-list |
|---|---|
| `charter deactivate <kind> <id>` | adds the id |
| `charter activate <kind> <id>` (including `--only`) | removes the id |
| `charter activate ... --cascade ... --include-deactivated` | removes the ids the walk reaches |
| `charter activate --preset X --force` | removes the ids the preset lists, and reports them |

Presets without `--force`, the interview, org-required promotion, synthesis, mission-type seeding
and every migration never touch deny keys. A denied id they list stays subtracted and is named in
a warning. Ids dropped by `--only` narrowing get no deny entry; only an id the user names in
`charter deactivate` is added.

The guard is structural. The ledger write takes a `deny_change` keyword (`DenyListChoice`:
`activate`, `deactivate`, `cascade-include-deactivated`, `preset-force`). A write that changes a
deny-list (compared as normalised sets, so absent, `[]` and `null` are equal) without one raises
`DenyListWriteRefused` and writes nothing. A gate over every registered migration and built-in
preset proves none removes a deny entry: a static scan, plus a dynamic run of each
activation-touching migration on a fixture where it applies, made non-vacuous by a self-mutation
test.

### Decision 5: the cascade stops at a denied node

Operator ruling `cascade_walk_through_denied`. A cascade activation walk skips a denied node,
reports it, and **does not expand it**: nothing reachable only through a denied node is activated.
A node that is also reachable over a path that avoids every denied node is still reached.
`--include-deactivated` restores the full walk, activates the denied nodes and clears their
exclusions.

The result gains two buckets beside `skipped_by_scope`: **skipped, deactivated** (each entry says
whether it was reached over a `REQUIRES` edge and from which parents) and **unreached** (reachable
only behind a denied node). Every node of the full walk lands in exactly one bucket, and scope is
decided before deny.

A cascade *deactivation* records only the id the user named; children removed with it lose their
allow-list entry but get no deny entry (the shared-reference skip, C-007, is unchanged). Under an
absent allow-list the children stay active, and the output says so ("still active: no allow-list;
only P was excluded").

### Decision 6: a required artifact cannot be deactivated

`charter deactivate` on an id that any declared org pack requires exits non-zero, names the
requiring pack and the `required_<kind>` policy, and records nothing. The required floor is the
**union of `required_<plural>` over every declared org pack and each pack's `extends:` chain**,
read by one iterator. Precedence never decides whether an id is required, so the org-pack
precedence work in the parallel workstream is untouched (C-005).

The read is strict. An unreadable or malformed declared pack, an `extends:` cycle or a dangling
base raises `ActiveCharterConfigError`; it never widens the answer. The floor is always read for
deactivation and promotion, and on reads only when a deny-list is non-empty (the only case where
the floor changes the answer). One refusal seam, `check_deactivation_permitted`, raises
`RequiredArtifactDeactivationError`, a `DeactivationRefused` subtype that a later `locked`
mutability level can join. `NoActivationRestrictionsError` is deleted, with no alias (C-008).

### Decision 7: the migration

A new migration, `4.0.0rc8_activation_ledger` (tracked partition, `clone_local_effect = False`,
listed in `order_manifest.txt` after the rc7 entries), moves every activation key from the pointer
`charter.yaml`, a no-pointer legacy `config.yaml`, or a leftover `config.yaml` copy into the
ledger, preserving three-state values including `[]`.

- **Refuses divergence**, naming the key and both files and changing nothing, when two surfaces
  disagree on a key. This includes a stray `config.yaml` copy of a key the authoritative
  `charter.yaml` lacks (operator ruling `stray_config_copy`). A legacy `deactivated_*` key is also
  refused, because no legacy surface can hold one.
- **Re-runnable after a crash.** The order is ledger write, strip `charter.yaml`, strip
  `config.yaml`, restamp the bundle hash. A re-run with a ledger present strips legacy keys equal
  to it, so an interruption at any point is recovered by running again.
- **Idempotent.** A second run changes zero bytes.

**Dogfood path** (operator ruling `dogfood_migration_path`). A full `spec-kitty upgrade` on this
repository has no populated migration ledger and would select the whole manifest, so the
repository could not move its own keys narrowly. `spec-kitty migrate activation-ledger
[--dry-run] [--json]` runs only this migration's planner and apply, with the same refusals, and is
how this repository, and any project an older CLI wrote legacy keys into again, gets its ledger.

**A second, narrow writer of the Migration Ledger.** ADR 2026-10-17-1 names `spec-kitty upgrade`
as the Migration Ledger's only writer. `migrate activation-ledger` becomes a second one. It
appends the `4.0.0rc8_activation_ledger` success row only when `.kittify/migration-ledger.jsonl`
already exists, and builds the row through the ledger module's own record builder. The reason is a
narrow re-run path for one cheap, idempotent move: where no migration ledger exists, the command
moves the keys and reports `not_recorded`, so it never adopts the ledger for a project that has
not chosen to.

### Consequences

#### Positive

- A deactivation holds under "absent = all", across the interview, presets, synthesis, cascade and
  upgrades.
- One file answers "what is active here"; doctor reports every divergent surface.
- Deactivating a required artifact fails loudly instead of being silently ineffective.

#### Negative

- **Downgrade hazard** (operator ruling `older_cli_downgrade`). The activation keys leave
  `charter.yaml`. An older CLI reads no `activated_<kind>` keys there, so it treats every kind as
  absent, which means **everything is in force**. A project moved to the ledger and then opened
  with an older CLI silently widens its activation, and a deactivation made under the new CLI is
  ignored. We accept this and mitigate it: the changelog's Upgrade Notes and this ADR state it,
  and doctor flags activation keys that reappear in `charter.yaml` or `config.yaml`. No unknown
  keys are added to `charter.yaml`.
- A merged branch or an older CLI can write legacy keys after the ledger exists. They are ignored
  (the ledger wins), warned about once per process, and reported by doctor as an error. A
  reconcile command that merges them is deferred.
- **SPDD probe residual (decision D-07).** The offering-side SPDD activation probe reads through
  the kernel resolver and applies `allow and not deny`, but **applies no org required floor**,
  because the floor lives in activation and `charter.offering` must not import it (C-002). A
  stale deny entry for an org-required id can therefore make the probe read the artifact as
  inactive while the resolver-served context, which applies the floor, serves it. The resolver
  path is the authority, and doctor warns on the stale entry (`DENY_REQUIRED_ID`). We accept the
  residual rather than replicate the org scan in the offering.
- Fail-open callers (`gate_bindings`, the mission-step contract executor, preflight) now let
  `ActiveCharterConfigError` propagate instead of serving an unfiltered graph.

#### Neutral

- The selection overlay gains requirements inherited through `extends:`, because the floor that
  is subtracted from deny and the floor that is unioned into `selected_*` must be the same set.
  This is a behaviour alignment, announced in the changelog.
- The `deny_change` guard is a plain keyword, not a minted token; the static gate gives the
  structural protection.

### Confirmation

Portable, data-driven acceptance cases (`activation-ledger-conformance/1`) pin the fixed answers:
the effective set under deny, identity-space matching, the cascade report, the required refusal
and the migration move. Per operator ruling `conformance_corpus`, the cases live in the ported test cases and are meant to port to the open-packs content and the Java offering; there is no separate export script. The FR-014 gate covers every registered migration and built-in preset. A
dogfood run of `spec-kitty migrate activation-ledger` on this repository moves its own keys.

## Revisit Triggers

- `locked` / `enforced` mutability levels (spec-kitty-charter ADR-0012) land in core: they join
  the refusal seam of Decision 6.
- The Java offering's filtering (#65) ships: re-check that the SPDD probe residual still holds.
- Users hit stray legacy keys in practice: build the deferred reconcile command.

## Out of Scope

- spec-kitty-charter ADR-0013 Decision 7 (activation as an additive contract set on the charter
  API): a later contract-set change in spec-kitty-charter.
- Changes in the spec-kitty-charter repository (C-006); this ADR only cites it.
- Project-charter `required_directives`, mission types and `activated_kinds`, which are not
  artifact kinds and get no deny-list.

## More Information

- Source ADR: spec-kitty-charter ADR-0013, and issues
  [#62](https://github.com/spec-kitty/spec-kitty-charter/issues/62),
  [#63](https://github.com/spec-kitty/spec-kitty-charter/issues/63),
  [#64](https://github.com/spec-kitty/spec-kitty-charter/issues/64),
  [#66](https://github.com/spec-kitty/spec-kitty-charter/issues/66),
  [#67](https://github.com/spec-kitty/spec-kitty-charter/issues/67).
- Mission artifacts: [spec](../../../kitty-specs/persistent-deactivation-ledger-01M59YAA/spec.md),
  [plan](../../../kitty-specs/persistent-deactivation-ledger-01M59YAA/plan.md),
  [research](../../../kitty-specs/persistent-deactivation-ledger-01M59YAA/research.md),
  [data model](../../../kitty-specs/persistent-deactivation-ledger-01M59YAA/data-model.md).
- Glossary: [Activation ledger](../../context/charter.md#activation-ledger),
  [Exclusion](../../context/charter.md#exclusion),
  [Effective deny](../../context/charter.md#effective-deny),
  [Required floor](../../context/charter.md#required-floor).

## Amendment 2026-10-20: the reduced flip (Option B) and the charter-contract rulings

Operator rulings of 2026-10-20, recorded as Mission decisions, after the charter-contract
impact assessment ([Activation Ledger and the Charter Contract](../../architecture/activation-ledger-and-charter-contract.md)).
Decisions 1, 2, 4, 5 and 6 stand. This amendment changes Decision 3 for unmigrated projects,
records the contract rulings and the residuals, and corrects one detail of Decision 7.

### `mission_pivot_option_b`: the reduced flip

The ledger flip shipped reduced; the work packages that would have swept every test fixture
onto the ledger were canceled.

- **Reads on an unmigrated project stay on the legacy allow keys.** The Decision 3 row
  "absent | outside | present → fail closed" is superseded: such a project resolves to the
  legacy surface, flagged `unmigrated`, and its `activated_<kind>`, `activated_kinds` and
  `mission_type_activations` are read as before. A `deactivated_<kind>` key found there is
  never applied: each command warns once, doctor reports `LEGACY_DENY_KEY` (an error), and the
  migration refuses it. A legacy save leaves a hand-written deny key it does not change where
  it is.
- **Deny writes on an unmigrated project refuse**, before any write and before the
  required-floor read, naming `spec-kitty upgrade` and `spec-kitty migrate activation-ledger`
  (`refuse_unmigrated_deny_write`). A cascade deactivation is refused as a whole. A
  `mission-type` deactivation records no deny entry and keeps the legacy target. Allow-only
  writes (`activate`, `--only`, presets, a cascade that clears nothing) still succeed on the
  legacy surface.
- **No ledger is created beside legacy keys.** Only the migration creates it there; a new
  ledger beside them would strand the keys and widen the project to "absent = all".
  `spec-kitty init` and a fresh project write the ledger. A dangling `charter:` pointer stays
  legacy, as on `main`.
- **There is one mode.** `SPEC_KITTY_ACTIVATION_STRICT` and the tolerant/strict split are
  deleted, and a gate asserts no reference remains.
- **Moved to the alignment epic** (epic child #6535, retire the legacy activation reader): the
  strict fail-closed read of an unmigrated project, the full fixture sweep, removal of the
  `charter.yaml` bootstrap allow-key copy (kept until then, copying allow keys only and only
  when the source is legacy) and removal of the `CharterYaml` activation fields (kept so
  unmigrated `charter.yaml` files keep validating).

### `contract_document_scope`

`activation.yaml` does not hold the charter contract's full `ActivationConfig`. Packs,
languages and context activations stay in their current homes, and a future anti-corruption
layer maps those homes onto the contract's schema. Content alignment matters, not shape.

### `required_always_active_divergence`

Core keeps its semantics: a required artifact is never subtracted by a deny, and is not added
under an explicit allow list that omits it. The difference from the charter service (required
and locked are always active on read) is logged as a divergence and settled before the remote
cutover. Doctor and `charter list` report such an omission (`REQUIRED_OMITTED_BY_ALLOW_LIST`,
`required_not_in_force`), per R12.

### `contract_rulings_r2_r12`

- **R2.** ADR [2026-10-16-1](2026-10-16-1-extract-charter-offering-first-activation-rework-post-ga.md)
  gains a dated amendment: after the 1.0.0 remote cutover the charter service is
  authoritative and core's file is the mapped local copy.
- **R3.** `charter activate` accepts a declared id (#6423), folded into the cascade and activate
  work; the allow list keeps one stem spelling per artifact.
- **R4.** A deny choice for a whole-document register is deferred to the alignment epic.
- **R5.** Unknown and stale deny entries stay inert in core and are dropped on export.
- **R6.** NFR-003 is restated as no regression against the base; repository-scale latency is
  #6506.
- **R7.** `--preset X --force` clearing exclusions is logged as a divergence (the contract has no
  force, and a preset never removes a deny entry).
- **R8.** Core keeps its CLI verbs. They now map 1:1: spec-kitty-charter
  [#125](https://github.com/spec-kitty/spec-kitty-charter/issues/125) answered core's request 4,
  so the contract's `select` clears the named id's own exclusion and `deactivate` records the
  exclusion and unselects. That is aligned, not a divergence, and needs no adapter composition.
- **R9.** An `appliedPresets` sidecar belongs to the alignment epic.
- **R10.** Export emits authored languages only.
- **R11.** Core stores stems, emits declared ids, and refuses unknown tokens on export.
- **R12.** Doctor and `charter list` warn about a required id that an explicit allow list omits.

### `contract_epic_ga_milestone`

Switching to the charter surface is a 4.0 deliverable: the alignment epic and all its children
go on the GA milestone (#11), whose target date is removed. This supersedes the post-GA timing
of ADR 2026-10-16-1 for the activation rework.

### `mission_type_cascade_source`

A mission type is a cascade source: `charter activate mission-type X --cascade` walks the
mission type's references with the same scope, skip and stop-at-deny rules (Decision 5). It was
folded into the cascade work package; the decision record's "a new WP" wording is superseded.

### Replies to spec-kitty-charter ADR-0020 "Requests to core"

- **Item 1** (stop the flat file rejecting the document): answered "mapped at the seam". Under
  `contract_document_scope` the file never holds contract keys, so the ledger keeps its
  unknown-key refusal.
- **The id-spelling request:** answered by R3 and R11.
- **The amendment to ADR 2026-10-16-1:** R2.
- **Select and deactivate (request 4):** aligned 1:1 (R8, spec-kitty-charter #125).

### The divergence register

Every divergence that is not aligned, ruled or open, is data: the `divergences:` section of
[`tests/charter/conformance/activation_ledger_cases.yaml`](../../../tests/charter/conformance/activation_ledger_cases.yaml),
each naming its conformance cases. Aligned rows (Activate, Deactivate) are not divergences and
live only in the
[divergence register](../../architecture/activation-ledger-and-charter-contract.md#divergence-register)
of the architecture page, which also carries each ruling's status.

### Decision 7, corrected

The apply order is the ledger write, then each legacy file's strip, authority first. The
synthesis manifest is stamped with the bundle's post-strip hash just *before* the `charter.yaml`
strip, not as a last step, so a run that stops between the two writes still has legacy keys on
disk and the re-run finishes the move. A lagging manifest stamp alone is not this migration's
business. A malformed or changed-meanwhile project fails the narrow command with
`ACTIVATION_LEDGER_MIGRATION_FAILED`.

### Residuals

- The legacy `.kittify/profiles` overlay still serves a denied agent-profile id. It is outside the
  activation model (C-002, FR-007).
- A hand-edited deny entry spelled as a declared id is not matched by the shipped
  `m_unify_charter_activation` promotion, which compares raw spellings. Shipped migrations are not
  edited (DIRECTIVE_044).
- The SPDD probe residual (decision D-07) is unchanged.
- The project-intent rename (#6443) renames the legacy `mission-type-scope-directive` in the
  allow lists only. A deny entry recorded for the old id between a skipped or refused rename and its
  later run goes stale, and the renamed directive is back in force. Operator ruling 2026-10-21:
  document it and follow up in #6565; FR-014 stays absolute (no migration-reachable deny change).
