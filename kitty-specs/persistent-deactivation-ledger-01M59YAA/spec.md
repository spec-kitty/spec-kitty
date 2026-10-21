# Mission Specification: Persistent deactivation: one activation ledger

**Mission Branch**: `core-align-3-persistent-deactivation`
**Created**: 2026-10-19
**Status**: Draft
**Input**: Core side of spec-kitty-charter ADR-0013 ("Deactivation persists in one activation ledger, and nothing silently reinstalls it"), steps spec-kitty-charter #62, #63, #64, #66 and #67. #65 (projection/resolution filtering) is the Java offering's and is out of scope.

## Intent Summary

A user who deactivates a charter artifact expects it to stay gone. Today it does not:
deactivation only removes an id from the `activated_<kind>` allow-list, raises
`NoActivationRestrictionsError` when that list is absent ("absent = all"), and several
paths quietly bring the artifact back (the cascade walk, the one-time upgrade reset that
turns a default-equal list back into "absent", the interview and promotion writers).
Activation state also has several homes (`config.yaml`, the `charter.yaml` its pointer
names, `answers.selected_*`).

This mission makes one new file, `.kittify/charter/activation.yaml`, the single authority
for activation: allow state (`activated_<kind>`, three-state) and deny state
(`deactivated_<kind>`). A new upgrade migration moves the existing keys into it. Cascade
skips and reports excluded artifacts, no migration or preset can remove an exclusion, and
deactivating an artifact an org pack requires is refused with an error naming the pack.

### Operator rulings (recorded decisions)

- **Ledger authority** (`ledger_authority`): `.kittify/charter/activation.yaml` holds
  `activated_<kind>` (three-state: absent = the kind's `ArtifactKind.effective_when_absent`
  default, `[]` = fail-closed empty, list = set) and `deactivated_<kind>`. Effective set =
  allow state minus deny-list, never subtracting a required artifact. Empty deny-lists are
  omitted. Every other surface derives from the ledger or is checked against it; doctor
  reports surfaces that diverge.
- **Unmigrated projects** (`unmigrated_projects`) and **pre-ledger seam** (`pre_ledger_seam`):
  a new migration moves the keys during `spec-kitty upgrade`; there is no runtime fallback.
  The seam resolves as follows:
  - `activation.yaml` exists → it is the only source for reads and writes;
  - legacy activation keys exist (pointer `charter.yaml` or `config.yaml`) and there is no
    ledger → **amended 2026-10-20 by `mission_pivot_option_b`**: ordinary CLI **reads** stay on
    the legacy allow keys (the same answer as `main`; nothing widens, because no deny entry can
    exist there), and **deny writes** refuse with `ActiveCharterConfigError` naming
    `spec-kitty upgrade` (or `spec-kitty migrate activation-ledger`). Allow-only writes keep
    today's legacy target. The strict fail-closed read moves to the charter-contract alignment
    epic (epic child #6535: retire the legacy activation reader). **Inside the upgrade runner**, the seam keeps targeting the legacy surface so
    shipped migrations that run before the ledger migration behave byte-for-byte as today;
  - neither → the ledger (a fresh project; absent keys keep their defaults).
- **Older CLIs** (`older_cli_downgrade`): the keys move out of `charter.yaml`. The downgrade
  hazard (an older CLI then treats every kind as absent) is documented in the changelog's
  Upgrade Notes and in the new core ADR; doctor flags activation keys that reappear in
  `charter.yaml` or `config.yaml`. No unknown keys are introduced into `charter.yaml`.
- **Deny writers** (`deny_writers`): only an explicit operator choice changes a deny-list:
  `charter activate <kind> <id>` (including `--only`), a cascade with
  `--include-deactivated`, and `charter activate --preset X --force`, which clears entries
  for the ids the preset lists and reports them. Presets without `--force`, the interview,
  synthesis, seeding and every migration never touch deny keys; a denied id they list stays
  subtracted and is reported in a warning. Ids dropped by `--only` narrowing get no deny
  entry; only an id the user names in `charter deactivate` is added.
- **Conformance corpus** (`conformance_corpus`): the corpus lives in the migrated and
  ported test cases and the open-packs content. The fixed answers are written as portable,
  data-driven acceptance cases; there is no separate export script.
- **Dogfood path** (`dogfood_migration_path`, 2026-10-19): this repository moves its keys with
  `spec-kitty migrate activation-ledger` (FR-021), never with a full `spec-kitty upgrade`.
- **Mission type as a cascade source** (`mission_type_cascade_source`, 2026-10-20): FR-022,
  folded into WP07.
- **Contract document scope** (`contract_document_scope`, 2026-10-20): `activation.yaml` keeps
  core's flat shape. Packs, languages and contextActivations stay in their homes, and a future
  ACL seam maps them onto the charter contract's `ActivationConfig`. That seam is not in this
  Mission.
- **Required on read** (`required_always_active_divergence`, 2026-10-20): core keeps its
  semantics (a required id is never subtracted by deny, and is not added under an explicit allow
  list). The difference from the contract is logged as a divergence in the ADR and the
  conformance corpus (FR-024) and settled before the remote cutover. Operators see it through
  FR-023.
- **Contract rulings R2–R12** (`contract_rulings_r2_r12`, 2026-10-20), all accepted:
  - R2: a dated amendment to ADR 2026-10-16-1 (the service is authoritative after the 1.0.0 cutover);
  - R3: #6423 (declared-id activate) is folded into WP07;
  - R4: a register deny choice goes to the epic;
  - R5: unknown and stale deny entries stay inert locally and are dropped on export;
  - R6: NFR-003 is restated as "no regression against the base" (#6506);
  - R7: preset `--force` clearing exclusions is a logged divergence;
  - R8: the CLI verbs are kept. Since charter #125 answered request 4 (2026-10-20), the contract's `select` clears the named id's own exclusion and `deactivate` records it and unselects, exactly as core does. The mapping is therefore 1:1, with no composition and no divergence;
  - R9: an `appliedPresets` sidecar goes to the epic;
  - R10: only authored languages are emitted;
  - R11: stems are stored, declared ids are emitted, and unknown tokens are refused on export;
  - R12: FR-023.
- **Epic placement** (`contract_epic_ga_milestone`, 2026-10-20): the charter-contract alignment
  epic and all its children sit on the 4.0 GA milestone (#11, target date removed). That
  includes (epic child #6535: retire the legacy activation reader).
- **Mission pivot** (`mission_pivot_option_b`, 2026-10-20): Option B.
  - Kept: WP07, WP08 (migration, `migrate activation-ledger`, dogfood), WP09 (bundle, doctor),
    WP10 (gate, corpus with the divergence register), a reduced flip (WP14) and WP15 docs.
  - Canceled: the fixture sweeps WP11–WP13.
  - Moved to the epic: retiring the legacy reader.
- **Org-pack precedence** (parallel workstream): org-pack precedence becomes
  later-declared-pack-wins. This mission must not change precedence logic; it reads
  `required_*` as a union over every declared pack (walking each pack's `extends:` chain),
  which precedence does not decide.

### Out of scope

- spec-kitty-charter #65: projection and resolution filtering in the Java offering, and
  skill/command projection retirement for excluded built-ins. Core's own Python read path
  (`PackContext`, the resolver, DRG filtering, `charter context`) **is** in scope (FR-016).
- `locked` / `enforced` mutability levels (spec-kitty-charter ADR-0012): core has no such
  concept yet; FR-013 covers org `required_*` only and leaves a single refusal seam that a
  later lock check plugs into.
- Project-charter `required_directives` (the top-level charter's own list) and mission types
  / `activated_kinds`, which are not artifact kinds and get no deny-list.
- ADR-0013 Decision 7 (activation as an additive contract set on the charter API): a later
  contract-set change in spec-kitty-charter.
- Any change in the spec-kitty-charter repository (C-006).
- Moved to the charter-contract alignment epic (milestone #11) by `mission_pivot_option_b` and
  `contract_rulings_r2_r12`. Each item stays out of scope here:
  - retiring the legacy activation reader, i.e. strict fail-closed reads on an unmigrated
    project and the full test-fixture sweep (epic child #6535: retire the legacy activation reader);
  - the ACL module, `to_contract` / `from_contract`, the revision;
  - `DenyListChoice.REGISTER`;
  - the `appliedPresets` sidecar;
  - `--json` on activate and deactivate;
  - the activation block in `charter status --json`;
  - removing the `charter.yaml` bootstrap's allow-key copy and the `CharterYaml` activation fields. Both stay while the legacy reader survives; the copy runs only for a LEGACY source (C-003). Both are recorded in epic child #6535.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A deactivation sticks (Priority: P1)

A project lead runs `spec-kitty charter deactivate directive D`. D stops being in force and
stays out across later commands, upgrades, the interview and regeneration, until the lead
explicitly runs `spec-kitty charter activate directive D`.

**Why this priority**: This is the user-visible defect (#63). Without a persisted exclusion
nothing else in the mission can hold.

**Independent Test**: In a fresh project with no `activated_directives` key, deactivate D,
then run the interview promotion, preset seeding and the upgrade; D is never in the
effective directive set; `charter activate directive D` brings it back.

**Acceptance Scenarios**:

1. **Given** no `activated_directives` key, **When** the user deactivates directive D,
   **Then** the command succeeds, `deactivated_directives: [D]` is written to
   `activation.yaml`, and D is not in the effective set.
2. **Given** `activated_directives: [A, D]`, **When** the user deactivates D, **Then** D is
   removed from the allow-list and added to `deactivated_directives`.
3. **Given** D is excluded, **When** the interview promotion, org-required promotion of
   other ids, synthesis or mission-type seeding runs, **Then** D stays excluded and no
   writer re-adds it to an allow-list.
4. **Given** D is excluded and the allow-list is absent, **When** `charter activate
   directive D` runs, **Then** D leaves the deny-list and is effective again, and the
   allow-list stays absent.
5. **Given** D is excluded and `activated_directives: [A]` is present, **When**
   `charter activate directive D` runs, **Then** D leaves the deny-list and is appended to
   the allow-list.
6. **Given** D is excluded, **When** `charter context --action implement` runs, **Then** D
   is not in the served context, even when `answers.selected_directives` lists D.

---

### User Story 2 - One activation ledger (Priority: P1)

A maintainer upgrades a project. The upgrade moves every activation key out of
`charter.yaml` (and any leftover `config.yaml` copy) into `.kittify/charter/activation.yaml`.
From then on there is one file that answers "what is active here", and `spec-kitty doctor`
reports any other surface that disagrees with it.

**Why this priority**: #62. The deny-list needs one authoritative home, and the migration is
the only route by which existing projects reach it.

**Independent Test**: Seed a project with activation keys in `charter.yaml`, run the
migration, and check the keys are in `activation.yaml`, gone from `charter.yaml`, and the
effective sets are unchanged; re-run it and nothing changes.

**Acceptance Scenarios**:

1. **Given** activation keys in the `charter.yaml` the pointer names, **When** the migration
   runs, **Then** they move verbatim (three-state preserved, including `[]`) to
   `activation.yaml` and are removed from `charter.yaml`.
2. **Given** a leftover `config.yaml` copy equal to the authority, **When** the migration
   runs, **Then** the copy is removed too; **given** it disagrees, **Then** the migration
   refuses, names the key and both files, and changes nothing.
3. **Given** an already-migrated project, **When** the migration runs again, **Then** it
   reports nothing to do and writes nothing.
4. **Given** activation keys reappear in `charter.yaml` or `config.yaml` beside a ledger,
   **When** `spec-kitty doctor charter-packs` runs, **Then** it reports the divergence as an
   error, the ledger's answer wins, and the report is not healthy.
5. **Given** a deny-list entry names an artifact no pack provides, or one an org pack now
   requires, or `answers.selected_*` lists a denied id, **Then** doctor reports it as a
   warning (`answers.yaml` is provenance only, ADR 3.x/2026-07-18-1).
6. **Given** legacy activation keys and no ledger, **When** an ordinary command reads
   activation (for example `charter context`), **Then** it answers from the legacy allow keys
   exactly as `main` does; **When** a command would write a deny entry (`charter deactivate`,
   including a cascade), **Then** it refuses with an error naming `spec-kitty upgrade` and writes
   nothing (amended by `mission_pivot_option_b`; the strict fail-closed read is
   (epic child #6535: retire the legacy activation reader)); **When** `spec-kitty upgrade` runs from an rc5-era fixture through
   the whole manifest, **Then** the shipped migrations act on the legacy surface and the
   ledger migration then moves the result.

---

### User Story 3 - Cascade honours exclusions (Priority: P2)

A lead activates a mission type with `--cascade all`. A child artifact they excluded earlier
is not brought back; the output lists it as "skipped, deactivated", and flags it when the
parent `requires` it. `--include-deactivated` takes it back in and clears its exclusion.

**Why this priority**: #64. Cascade is the most common path that silently reinstalls a
deactivated artifact.

**Independent Test**: Exclude child C, cascade-activate a parent that reaches C, and assert C
stays excluded and is reported; repeat with `--include-deactivated` and assert C is active
and its exclusion cleared.

**Acceptance Scenarios**:

1. **Given** child C is excluded, **When** `charter activate mission-type X --cascade all`
   reaches C, **Then** C stays excluded, the walk does not continue through C, and the
   output names C under a "skipped, deactivated" heading beside "skipped (out of scope)"
   and lists anything reachable only through C as unreached.
2. **Given** C is reached over a `requires` edge, **Then** the report flags C as a
   requirement the parent no longer has.
3. **Given** `--include-deactivated`, **Then** C is activated and its exclusion is cleared.
4. **Given** a cascade deactivation of parent P that also removes children, **Then** only P
   gets a deny-list entry; the children are not excluded.

---

### User Story 4 - Required artifacts cannot be deactivated (Priority: P2)

A lead tries to deactivate a directive an org pack requires. The command exits non-zero,
names the requiring org pack(s), and records no exclusion. Required artifacts are never
subtracted by a stale deny-list entry.

**Why this priority**: #67. Today the org `required_*` union silently overrides the user's
intent, so a deactivation is quietly ineffective.

**Independent Test**: With an org pack requiring D, deactivate D and assert exit code,
message (pack name) and an unchanged ledger.

**Acceptance Scenarios**:

1. **Given** org pack `acme` requires directive D, **When** the user deactivates D, **Then**
   the command exits non-zero, the error names `acme` and the `required_directives` policy,
   and the ledger is byte-identical.
2. **Given** D sits in `deactivated_directives` and an org pack later requires D, **Then** D
   is effective (required wins), and doctor reports the stale deny entry.
3. **Given** a cascade deactivation reaches a required child, **Then** the child is skipped
   and the report names the requiring pack.

---

### User Story 5 - Upgrades never reset an exclusion (Priority: P2)

A maintainer upgrades. No migration and no preset removes a deny-list entry, and a gate test
proves it for every registered migration and preset.

**Why this priority**: #66. The one-time cutover reset turns default-equal allow-lists back
into "absent", which would re-enable everything if exclusions lived in the allow-list.

**Independent Test**: The gate runs every registered migration's `apply()` and every preset
application against a project holding deny-list entries and asserts each entry survives.

**Acceptance Scenarios**:

1. **Given** D is excluded, **When** `spec-kitty upgrade` runs the cutover (including its
   resets), **Then** D is still excluded.
2. **Given** any writer other than the explicit-choice paths, **When** it tries to remove
   or shrink a `deactivated_<kind>` entry through the activation write seam, **Then** the
   seam refuses (structural guard).
3. **Given** every registered migration and built-in preset, **Then** a gate proves none
   of them can remove a deny entry: statically (no migration or preset names a deny key in
   a removal) and dynamically (each is applied to a fixture on which it is applicable,
   with deny entries present, and every entry survives); the gate fails naming the
   offender.
4. **Given** `charter activate --preset X --force` where X lists denied id D, **Then** D's
   exclusion is cleared and the output names it; without `--force` D stays subtracted and
   a warning names it.
5. The migration ordering gate is green.

### Edge Cases

- Deactivating an id that is not available for the kind: refused with the existing
  unknown-id error; nothing written.
- Deactivating an already-excluded id: no-op with a warning; ledger unchanged.
- Activating an id that is not denied from an absent allow-list: the existing #4253
  materialisation is unchanged, except that the materialised set leaves out denied ids.
- `charter activate <kind> <id> --only`: clears the id's deny entry like any explicit
  activation; ids dropped by the narrowing are removed from the allow-list only.
- `[]` allow-list plus activating a denied id: the deny entry is cleared and the id is
  appended (the list becomes `[id]`).
- A kind whose absent key means "required only" (`skill`): a deny entry for a non-required
  skill is recorded; a required skill is refused like any other required artifact.
- A malformed ledger (non-mapping, non-list value, unknown key): fail closed with the
  structured `ActiveCharterConfigError`; nothing written. An unknown `deactivated_<kind>` key
  (a kind a later CLI added) is tolerated with a warning instead.
- An unreadable declared org pack, or an `extends:` cycle: deactivation and promotion refuse
  (the required floor cannot be proven; it is always read for them). The read path fails closed
  whenever a deny list is present, the only case where the floor changes the answer. An empty
  deny list cannot widen anything, so the floor is not read then. Neither path widens.
- A crash partway through the ledger migration: re-running it completes the move (legacy keys
  equal to the ledger are stripped; differing ones are refused as divergent).
- A cascade deactivation whose children sit under an absent allow-list: the children stay
  effective and the output says so ("still active: no allow-list; only P was excluded").
- `[]` allow-list plus a deny-list: effective set stays empty.
- Synthesis: the created-tactics record (`.kittify/charter/synthesized-tactics.yaml`, ADR
  2026-10-06-2 Amendment 2026-10-19) stays as is and is not an activation surface; synthesis
  never re-adds a denied tactic, even on first creation.
- The interview re-selecting a denied id: not an explicit activation; the id stays
  subtracted and the interview warns.
- Unmigrated project (legacy activation keys, no ledger; `mission_pivot_option_b`):
  - `charter deactivate`, including a cascade deactivation, refuses before any write and before the required-floor read, naming `spec-kitty upgrade` / `spec-kitty migrate activation-ledger`. It is all-or-nothing: no child is unselected either.
  - `charter activate` of an id, `--only`, `--preset X [--force]` and cascade `--include-deactivated` succeed on the legacy surface as long as the write records or changes no deny entry. A `deny_change` that clears nothing is not a deny write.
  - A `deactivated_<kind>` key found on a legacy surface (hand edit, or a pre-release build of this Mission) is never applied. Doctor reports it as an error, and the ledger migration refuses it.
  - `charter generate` keeps copying the legacy allow keys into a newly bootstrapped `charter.yaml`, so minting the pointer does not drop them (allow keys only, never deny keys). On a project with a ledger, or a fresh one, the bootstrap copies nothing (C-003).
  - **Upgrade of a keyless pre-ledger project** (no activation keys anywhere, no ledger): rc8 has nothing to move. The upgrade's final provisioning step then treats the project as fresh and writes `mission_type_activations` to the ledger, so a full upgrade never leaves a project unmigrated.
  - **`spec-kitty init` re-run on an unmigrated project**: init stops at its "Already initialized" exit (the project's `config.yaml` exists) before provisioning and before the migration-ledger seed, so it writes nothing, records nothing for `4.0.0rc8_activation_ledger`, and a later `spec-kitty upgrade` still selects it and moves the keys (WP08 finding; a fresh init never sees pre-existing legacy keys).
- A fresh project (no activation keys anywhere, no ledger) and `spec-kitty init` get the ledger on the first write.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Activation ledger file | As a maintainer, I want `.kittify/charter/activation.yaml` (git-tracked) to be the only place activation allow and deny state is read from and written to once it exists, through one seam in `charter.activation`, so that one file answers "what is active here". (#62) | High | Open | [build] | no |
| FR-002 | Ledger key vocabulary derives from ArtifactKind | As a maintainer, I want the `activated_<plural>` and `deactivated_<plural>` keys derived from the `ArtifactKind` enum (charter-activatable kinds), plus the tokenless `activated_kinds` and `mission_type_activations`, so that the kind vocabulary keeps one authority. (#62) | High | Open | [build] | no |
| FR-003 | Ledger migration | As a maintainer, I want a new idempotent upgrade migration (tracked partition, `clone_local_effect=False`, `target_version` = the current version, appended to `order_manifest.txt` after the rc7 entries) that moves every activation key from the pointer `charter.yaml`, a no-pointer legacy `config.yaml`, or a leftover `config.yaml` copy into `activation.yaml`, preserving three-state values, and re-stamps the bundle hash, so that existing projects reach the ledger. (#62) | High | Open | [build] | no |
| FR-004 | Migration refuses divergent stores | As a maintainer, I want the ledger migration to refuse, naming the key and files and changing nothing, when two legacy surfaces (or a legacy surface and an existing ledger) hold different values for the same key, including a stray `config.yaml` copy of a key the authority lacks; a re-run where a ledger exists strips legacy keys equal to it, so an interrupted migration recovers by re-running. (#62, ADR-0013 Risks) | High | Open | [build] | no |
| FR-005 | Doctor reports divergent surfaces | As a maintainer, I want `spec-kitty doctor charter-packs` to report as errors (not healthy) activation keys in `charter.yaml`/`config.yaml` beside a ledger and an unreadable activation store (malformed ledger, unreadable required floor), a `deactivated_<kind>` key on a legacy surface (it is never applied there and blocks the migration), and as warnings an unmigrated project (legacy activation keys, no ledger; names `spec-kitty upgrade`), deny entries for unknown ids, deny entries for ids an org pack now requires, unknown `deactivated_<kind>` keys, and `answers.selected_*` ids that are denied, so that drift is visible and the ledger wins. (#62) | High | Open | [build] | no |
| FR-006 | Deny-list effective set | As a project lead, I want the effective set of a kind to be its allow state (list, `[]`, or the kind's `effective_when_absent` default) minus its `deactivated_<kind>` list, never subtracting an org-required artifact, computed once in `charter.activation`, so that an exclusion holds under "absent = all". (#63) | High | Open | [build] | no |
| FR-007 | Deactivation records an exclusion | As a project lead, I want `charter deactivate <kind> <id>` to add the id to the deny-list (and remove it from a present allow-list) without raising when the allow-list is absent, so that deactivation works for every artifact kind; `NoActivationRestrictionsError` is retired. (#63) | High | Open | [build] | no |
| FR-008 | Only explicit choices clear an exclusion | As a project lead, I want only `charter activate <kind> <id>` (including `--only`), a cascade with `--include-deactivated` and `charter activate --preset X --force` to remove deny entries, with a denied id re-added to a present allow-list on activation, so that no other writer undoes my choice. (#63, ADR-0013 Decision 3) | High | Open | [build] | no |
| FR-009 | Writers skip excluded ids | As a project lead, I want the promotion writers (interview, org-required promotion, synthesis, mission-type seeding, migrations that promote), non-forced presets and absent-key materialisation never to add a denied id to an allow-list, and to name it in a warning, so that the exclusion survives them. (#63) | High | Open | [build] | no |
| FR-010 | Cascade skips and reports excluded nodes | As a project lead, I want a cascade activation walk to skip excluded artifacts, stop there (nothing reachable only through an excluded artifact is activated), and report them in a "skipped, deactivated" bucket beside `skipped_by_scope`, flagging those reached over a `requires` edge, plus an "unreached (behind a deactivated artifact)" report, so that cascade never reinstalls them silently. (#64) | High | Open | [build] | no |
| FR-011 | `--include-deactivated` opt-in | As a project lead, I want `charter activate ... --cascade ... --include-deactivated` to take excluded artifacts back in and clear their exclusions, so that I can undo exclusions in bulk on purpose. (#64) | Medium | Open | [build] | no |
| FR-012 | Cascade deactivation excludes only the named id | As a project lead, I want a cascade deactivation to add only the id I named to the deny-list, keeping the shared-reference skip (C-005) and skipping required children; children under an absent allow-list stay active and the output says so, so that children removed along with it are not excluded. (#64, ADR-0013 Decision 3) | Medium | Open | [build] | no |
| FR-013 | Refuse deactivating a required artifact | As a project lead, I want deactivating an artifact any declared org pack requires (directly or through its `extends:` chain) to exit non-zero, name the requiring pack(s) and the `required_<kind>` policy, and record nothing; the required-floor read is strict, so an unreadable or malformed declared org pack or a broken `extends:` chain refuses the deactivation rather than widening, so that the outcome is never silently ineffective. (#67) | High | Open | [build] | no |
| FR-014 | No migration or preset removes a deny entry | As a maintainer, I want the activation write seam to refuse changing a deny-list except on the explicit-choice paths, plus a gate over every registered migration and built-in preset (a static scan and classifier; every activation-touching migration run on a fixture where it applies; non-vacuous by self-mutation), so that upgrades can never re-enable an exclusion. (#66) | High | Open | [build] | no |
| FR-015 | Portable conformance cases | As a charter-service contributor, I want the fixed answers (effective set under deny, cascade skipped-deactivated report, required refusal, migration move) expressed as data-driven test cases in one table, so that they can be ported to the open-packs content and the Java offering. (spec-kitty-charter #9) | Medium | Open | [build] | no |
| FR-016 | Every core reader honours the ledger | As a project lead, I want every core read path to read activation through the ledger seam and apply the deny-list in identity space (stem, declared id and URN agree) after the `selected_*`/`required_*` unions, so that an excluded artifact is not served anywhere in core. The read paths are: `PackContext` and its consumers (resolver, DRG activation filter, compiler, action governance bundle seeds, `charter context` including `--include <kind>:<id>` selectors and rendered references, mission-step contract selection, agent-profile dispatch and listing, skills installer and catalog, consistency check, list command), and the offering-side SPDD activation probe. A read-path error fails closed: callers that today turn a `PackContext` error into an unfiltered graph let `ActiveCharterConfigError` propagate. (#62, #63) | High | Open | [build] | no |
| FR-017 | Unmigrated projects: legacy reads, refused deny writes | As a project lead, I want an ordinary command on a project with legacy activation keys and no ledger to read activation from the legacy allow keys (the same answer as `main`, nothing widened, `deactivated_<kind>` keys there never applied) and to refuse any write that would record or change a deny entry, naming `spec-kitty upgrade` and writing nothing; allow-only writes keep the legacy target. Migration code paths (every method a migration defines, registry/runner selection, `migrate ledger`, worktree upgrades; matched on the canonical root) and the `spec-kitty upgrade` command keep the legacy target until the ledger migration moves the keys, so that nothing silently widens and the shipped migrations keep their behaviour. (#62; amended 2026-10-20 by `mission_pivot_option_b`: the strict fail-closed **read** half is delivered by the charter-contract alignment epic (epic child #6535: retire the legacy activation reader)) | High | Open | [build] (read half → epic) | no |
| FR-018 | Ledger is part of the charter bundle | As a maintainer, I want `activation.yaml` to be an optional tracked member of the charter bundle and part of its content hash when present, so that a hand edit of the ledger made outside the CLI is detected as stale. Projects without a ledger keep their hash. (#62) | Medium | Open | [build] | no |
| FR-019 | `spec-kitty init` writes the ledger | As a new user, I want `spec-kitty init` to provision activation (for example `mission_type_activations`) into `activation.yaml` through the ledger seam, so that a fresh project is never "unmigrated" and `spec-kitty upgrade` stays a no-op on it. (#62) | High | Open | [build] | no |
| FR-020 | Late legacy keys are surfaced | As a maintainer, I want an ordinary command to print one warning when activation keys sit in `charter.yaml`/`config.yaml` beside a ledger (for example written by an older CLI or a merged branch), naming the keys and saying the ledger wins, so that the drift is never silent. (#62) | Medium | Open | [build] | no |
| FR-021 | Narrow ledger move command | As a maintainer, I want `spec-kitty migrate activation-ledger [--dry-run]` to run exactly the ledger migration's move (same refusals, idempotent) without the rest of the upgrade, so that a project can move or re-move its activation keys narrowly, for example this repository or after an older CLI wrote legacy keys again. (#62; operator ruling `dogfood_migration_path`) | Medium | Open | [build] | no |
| FR-022 | Mission type as a cascade source | As a project lead, I want `charter activate mission-type X --cascade <scope>` to walk the mission type's DRG node (its action-sequence `requires` steps, type-wide `scope` governance and `instantiates` templates) with the same scope, skip-and-report and stop-at-deny rules as an artifact source, instead of silently cascading nothing, so that the issue's own example works. (#64; operator ruling `mission_type_cascade_source`) | Medium | Open | [build] | no |
| FR-023 | Required ids omitted by an explicit allow list are surfaced | As a maintainer, I want `spec-kitty doctor charter-packs` to warn, and `spec-kitty charter list` to mark as "required (not in force: explicit allow list omits it)", every org-required id that an explicit `activated_<kind>` list leaves out, naming the requiring pack(s), so that the required-on-read divergence from the charter contract is visible; core's semantics do not change. (operator rulings `required_always_active_divergence`, `contract_rulings_r2_r12` R12) | Medium | Open | [build] | no |
| FR-024 | Divergence register in the conformance corpus | As a charter-service contributor, I want the FR-015 conformance table to carry a `divergences` section that records each place where core's local semantics differ from the proposed charter contract, and every case to record its ids in both spellings (stem and declared id), so that the charter harness (spec-kitty-charter #9 / #72) can map cases to contract URNs and track the divergences until the cutover. At least these entries:<br>- required-on-read;<br>- write-time floor materialisation;<br>- preset `--force` clears exclusions;<br>- unknown `deactivated_<x>` preserved;<br>- stale required deny inert;<br>- authored-vs-derived languages;<br>- id spelling;<br>- unknown token.<br>(operator rulings `required_always_active_divergence`, `contract_rulings_r2_r12`) | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No write on failure | Any refused or failed activation, deactivation or migration leaves `activation.yaml`, `charter.yaml` and `config.yaml` byte-identical (asserted by tests for every refusal path). | Reliability | High | Open |
| NFR-002 | Idempotent migration | A second run of the ledger migration on any fixture changes 0 bytes and reports nothing to do. | Reliability | High | Open |
| NFR-003 | CLI latency | `charter activate`/`deactivate`/`charter context` show no latency regression against the base. Verification: a **manual**, alternating base-vs-head measurement on this repository, with medians recorded in the PR's *Tests run* section. The automated timing tests measure only the cost of the deny list (a fixture with a deny list vs one without, on the same code), not a regression against the base; the absolute 2 s budget is tracked in #6506, which is pre-existing on `main` (operator ruling `contract_rulings_r2_r12` R6). | Performance | Medium | Open |
| NFR-004 | Quality gates | 0 new ruff, ruff-format (`--force-exclude`) and mypy findings in touched files; every new function stays at cyclomatic complexity ≤ 15; diff coverage ≥ 90 %. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Never edit a shipped migration | Fixes go in new migrations listed in `order_manifest.txt` (DIRECTIVE_044, ADR 2026-10-17-1); shipped migrations keep their behaviour through the upgrade-only legacy seam. | Technical | High | Open |
| C-002 | Layer boundaries | The ledger seam lives in `charter.activation`; `charter.offering` never imports activation; `specify_cli` reaches it only through `charter.activation.api`; the shrink-only activation boundary baseline does not grow (ADR 2026-10-16-1). | Technical | High | Open |
| C-003 | No unknown keys in charter.yaml | `deactivated_*` keys are never written to `charter.yaml` or `config.yaml`. The charter.yaml bootstrap copies activation keys only for a LEGACY (unmigrated) source and allow keys only; with a ledger, or on a fresh project, it copies nothing. Its removal moves to epic child #6535 (amended 2026-10-20, `mission_pivot_option_b`). | Technical | High | Open |
| C-004 | Kind vocabulary single authority | No hand-written kind lists; `tests/architectural/test_charter_kind_vocabulary_single_authority.py` stays green. | Technical | High | Open |
| C-005 | Precedence untouched | Org-pack precedence code (`resolve_pack_chain`, fold order) is not changed; the parallel later-declared-pack-wins work owns it. | Technical | High | Open |
| C-006 | No changes in spec-kitty-charter | The sibling repository is read-only for this mission. | Business | High | Open |
| C-007 | Shared-reference safety | Cascade deactivation keeps the C-005 rule: an artifact still referenced by another active artifact is skipped. | Technical | High | Open |
| C-008 | No aliases or shims | Retired names (e.g. `NoActivationRestrictionsError`) are removed, not aliased (ADR 2026-10-06-2 Decision 7). | Technical | Medium | Open |
| C-009 | ADR first | A new core ADR in `docs/adr/4.x/` records the ledger, supersedes ADR 3.x/2026-07-18-1 Decision 2 ("charter.yaml owns activation") and amends ADR 2026-10-03-1 (write target) and ADR 2026-10-06-2 (presets, synthesis removal), before the code lands. | Technical | High | Open |
| C-010 | Release line | Activation rework is post-GA work per ADR 2026-10-16-1 D-2; the operator brought this slice forward ahead of the cutover; target milestone "CLI 4.x stable" unless the operator says otherwise. | Business | Medium | Open |

### Key Entities

- **Activation ledger** (`.kittify/charter/activation.yaml`): flat mapping of
  `activated_kinds`, `mission_type_activations`, `activated_<plural>` (three-state) and
  `deactivated_<plural>` (omitted when empty) for every charter-activatable `ArtifactKind`.
  Glossary entry required: distinct from the Migration Ledger, the decision ledger and the
  status event log.
- **Exclusion** (deny-list entry): an artifact id the user explicitly deactivated; removed
  only by an explicit choice (FR-008).
- **Required floor**: the union of `required_<plural>` over every declared org pack, each id
  attributed to the pack(s) requiring it.
- **Skipped-deactivated report**: cascade result bucket of excluded artifacts reached by a
  walk, each with a `via_requires` flag.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In an acceptance test, a directive deactivated with no allow-list present is absent from `charter context` output after the interview, preset seeding, synthesis promotion and a full upgrade run — [build] · no-op passable: no
- **SC-002**: The ledger migration moves 100 % of activation keys from every legacy fixture shape (pointer charter.yaml, no-pointer config.yaml, leftover equal copy) with unchanged effective sets, refuses every divergent fixture, and an rc5-era fixture upgrades through the whole manifest — [build] · no-op passable: no
- **SC-003**: The FR-014 gate covers every registered migration and every built-in preset (counts asserted against the registry and the preset directory; every activation-touching migration found by the static classifier runs on a fixture where it applies; non-vacuous by a self-mutation test) — [build] · no-op passable: no
- **SC-004** (after `mission_pivot_option_b`, delivered by every WP plus the reduced flip's bounded, red-first re-seed in WP14): `make test-fast`, `tests/charter/`, `tests/charter_offering/`, the migration tests and the implicated architectural gates pass with 0 new failures against the base — [ratchet] · no-op passable: yes — positive control: the new FR acceptance tests are red on the base
