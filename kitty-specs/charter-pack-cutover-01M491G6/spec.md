# Mission Specification: Charter offering, activation presets and the doctrine-to-charter cutover

**Mission Branch**: `issue-3732-charter-pack-rename`
**Created**: 2026-10-06
**Status**: Draft (post-spec squad folded; owner decisions OD-1..OD-10 ruled 2026-10-06)
**Input**: Issue #3732 (rename doctrine packs to charter packs), bound by ADR `docs/adr/4.x/2026-10-06-2-charter-offering-active-charter-and-activation-presets.md` (owner ruling, 2026-10-06); absorbs #4400, #5323, #5826, the legacy-key half of #4573 and the pack-path half of #5825. Requirement set confirmed by the owner in brief-intake mode on 2026-10-06; revised after the post-spec adversarial squad (architecture, testability, consumer impact).

## Bulk edit declaration

This mission renames the retired **doctrine pack** vocabulary to the **charter** vocabulary across the codebase, CLI, configuration, skills and documentation. Per-category rules (code symbols, import paths, filesystem paths, serialized keys, CLI commands, user-facing strings, tests and fixtures, logs and telemetry) are captured in `occurrence_map.yaml`, produced during plan from the classification ledger posted on #3732 and re-measured at the mission base. Unlike a default bulk edit, CLI commands and serialized keys **are** renamed: the owner ruled a full cutover with no compatibility layer, and the upgrade migration (FR-012) is the consumer-protection mechanism.

## Domain Language

| Canonical term | Meaning | Replaces / do not use |
|---|---|---|
| **Charter offering** | Everything offered to a project: the Charter Packs it can draw from, plus the project layer. | "doctrine" as the name of the offer-side tier; "Doctrine Catalog" |
| **Charter Pack** | A distributable bundle of interconnected charter components (artifacts and their DRG edges) with a set of activation presets; an org pack may also enforce activations (`required_<kind>`). | "doctrine pack" |
| **Activation preset** | A named set of activations a Charter Pack ships, applied to a project by activating it. Not an Activation Registry entry (a context-scoped activation). | "Pack Default Charter", "default charter pack", the old meaning of "charter pack" |
| **Active charter** | What a project has activated: its per-kind activation keys and mission-type activations. | the third meaning of "charter pack" (the project's activation state); "Charter Selection" |
| **Project layer** | The project's own charter components under `.kittify/charter-packs/`. Part of the offering; it ships no presets. | "project doctrine", `.kittify/doctrine/` |
| **Charter Bundle** | Unchanged: the materialised `.kittify/charter/` tree. | — |

"Active" / "inactive" still describe a single artefact's state; **active charter** names the project's activated set as a whole (the glossary guard is amended accordingly, ADR §1). "Doctrine" stays only where it means the governance content itself, in historical records, in `DIRECTIVE_039`, and in the `doctrine-daphne` profile name.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Apply a curated starting point from a pack (Priority: P1)

An operator setting up governance for a project wants a small, legible baseline instead of every built-in artifact. They run `spec-kitty charter activate --preset minimal` (the built-in pack is the default pack) and the project's active charter becomes the curated baseline. An operator whose organisation publishes its own Charter Pack runs `spec-kitty charter activate --pack <org-pack> --preset <name>` the same way.

**Why this priority**: presets are the user-facing heart of the new model, and the old path (`charter pack apply`) is removed by this mission.

**Independent Test**: in a fresh project, apply `--preset minimal`, then `--preset default`, then an org pack's preset; read the active charter back with `spec-kitty charter list --json` after each.

**Acceptance Scenarios**:

1. **Given** a fresh project, **When** the operator runs `spec-kitty charter activate --preset minimal`, **Then** every activation key the preset governs is written exactly as the preset declares and `spec-kitty charter list --json` reports that active charter.
2. **Given** a project with the `minimal` preset active, **When** the operator runs `spec-kitty charter activate --preset default --force`, **Then** every per-kind activation key and `activated_kinds` is absent, and every built-in artifact is effective, including one added to a copied built-in pack after the preset was written.
3. **Given** an org pack that ships a preset listing both built-in and org ids, **When** the operator activates it with `--pack <org-pack> --preset <name>`, **Then** the active charter matches that preset, unioned with the org's `required_<kind>`.
4. **Given** any project, **When** the operator runs `spec-kitty charter activate --preset does-not-exist`, **Then** the command fails, names the pack and lists its presets, and changes nothing.
5. **Given** a project with a customised activation list that the preset would change, **When** the operator applies a preset without `--force`, **Then** the command refuses, prints the per-key difference, and changes nothing (OD-6).

---

### User Story 2 - Upgrade an existing project without losing anything (Priority: P1)

An operator upgrades a project created under the old vocabulary: config uses legacy keys (`doctrine.org.*`, `organisation_packs`, `governance.doctrine.*`), project components live in `.kittify/doctrine/`, activation entries carry `doctrine_pack_id`, and the per-kind activation keys may hold a stale `default.yaml` list. They run `spec-kitty upgrade` once and keep working.

**Why this priority**: the cutover removes every read-side fallback, so the migration is the only thing standing between existing users and a broken project.

**Independent Test**: build fixture projects in each legacy shape; compare the effective set after `spec-kitty upgrade` with a golden "before" set frozen at the mission base (NFR-001).

**Acceptance Scenarios**:

1. **Given** a legacy project, **When** `spec-kitty upgrade` runs, **Then** the config keys use the canonical names, project components live in `.kittify/charter-packs/`, `.kittify/doctrine/` does not exist, and the effective set equals the golden "before" set.
2. **Given** a project whose `activated_<kind>` list equals a frozen released `default.yaml` snapshot for that kind, **When** the upgrade runs, **Then** that key becomes absent and the newer built-in artifacts are effective again.
3. **Given** a project with a customised activation list (including a stale list plus one id), **When** the upgrade runs, **Then** that list is left exactly as it was and the upgrade summary names it for review.
4. **Given** an already-upgraded project, **When** `spec-kitty upgrade` runs again, **Then** 0 bytes change.
5. **Given** a legacy project that has not been upgraded, **When** any command except `upgrade`, `init`, `--version`, `--help`, git merge drivers and hook entry points runs, **Then** it fails with an error naming `spec-kitty upgrade` and the migration runbook.
6. **Given** a project older than the rc35 default-pack migration, **When** `spec-kitty upgrade` runs to the cutover version in one go, **Then** it completes with 0 migration errors and the effective set equals the `default` preset's.
7. **Given** a mission with an open lane worktree in `approved`, **When** the repository root is upgraded, **Then** a later `spec-kitty consolidate` of that mission succeeds and the lane's bookkeeping-only upgrade commit is not refused as a post-approval change.

---

### User Story 3 - One command surface for pack authors (Priority: P2)

A pack author validates and assembles their Charter Pack with `spec-kitty charter pack validate` and `spec-kitty charter pack assemble`, regenerates the graph with the `charter` home of `regenerate-graph`, and checks the project's active charter with the top-level `charter` consistency check. No step uses the `spec-kitty doctrine` group, which no longer exists.

**Why this priority**: today pack authors must use the deprecated group and see its banner on every call.

**Independent Test**: run every former `spec-kitty doctrine` leaf command (enumerated in FR-006) through its `charter` replacement on the same fixture; run each old spelling and see it fail as unknown.

**Acceptance Scenarios**:

1. **Given** a pack directory, **When** the author runs `spec-kitty charter pack validate <dir>`, **Then** it validates as `doctrine pack validate` did, plus the pack's presets.
2. **Given** any former `spec-kitty doctrine <command>`, **When** it is run, **Then** it exits with the unknown-command path (exit 2); the replacement exits 0 on the same fixture.
3. **Given** a project with the built-in pack, an org pack with presets and an org pack without, **When** the operator runs `spec-kitty charter pack list`, **Then** it shows each pack with the presets it ships, and the project layer with none.
4. **Given** a pack whose `pack.yaml` still carries `accompanies_doctrine_pack`, or whose `org-charter.yaml` activation entries carry `doctrine_pack_id`, **When** it is validated or loaded, **Then** it is rejected with an error naming the field and its replacement (OD-1, OD-2).

---

### User Story 4 - Agents read one vocabulary (Priority: P2)

An agent working in a consumer project loads skills and reads docs. Every skill name, command, config key and path it meets uses the charter vocabulary; none contradicts another.

**Why this priority**: mixed names are the problem the owner named; agents and harnesses then contradict themselves.

**Independent Test**: upgrade a fixture project with installed agent directories and a user-global skill root; list the skills; run the vocabulary gate.

**Acceptance Scenarios**:

1. **Given** a freshly upgraded project with `.claude` and `.agents` installed, and a user-global skill root holding the old skills, **When** skills are listed, **Then** `spk-charter-*` and `spk-practice-*` are present, no removed skill name remains in either root, and the skill manifests have no orphan entries.
2. **Given** the shipped skills, packs and living docs, **When** the vocabulary gate (FR-018) runs, **Then** no forbidden token remains outside the closed historical-root list.

---

### User Story 5 - Promotion keeps what was effective (Priority: P1)

The charter interview, the org-charter union, the unify-activation upgrade step and the resynthesis preflight each materialise or reason about an absent activation key. They use exactly what was effective at that moment, never a narrower list.

**Why this priority**: once the `default` preset lists nothing, these callers would otherwise seed from an empty set (#4400).

**Independent Test**: for each caller, through its CLI entry point, start from an absent key with two org packs present (one artifact's `id:` differs from its file stem) and compare the effective set before and after.

**Acceptance Scenarios**:

1. **Given** an absent activation key and two declared org packs, **When** each caller promotes the key, **Then** every artifact effective before is still effective after.
2. **Given** an absent key whose effective set cannot be resolved, **When** a caller would promote it, **Then** the key stays absent and the caller reports it; no bare list is written.

---

### Edge Cases

- **Both project roots present** (`.kittify/doctrine/` and `.kittify/charter-packs/`): the migration moves every file whose path is free in the target; if any path exists in both with different content, it refuses, lists the colliding paths, and moves nothing.
- **Canonical and legacy config keys both present**: the canonical value wins; the legacy key is removed and named in the upgrade summary.
- **Preset id resolution**: preset ids resolve against the whole offering (built-in, org and project layers); an id that resolves nowhere fails activation, names the id, and writes nothing.
- **Pack without presets** (for example one fetched from the public-packs repository): the pack works; it offers no presets.
- **Stale list plus one customisation**: not equal to any snapshot, so it is kept and named in the upgrade summary.
- **List equal to the `minimal` preset**: per-kind lists kept and reported as "matches preset minimal"; its `activated_kinds: [directives, tactics]` gate is removed and reported.
- **Deliberate `[]` for a kind**: reset to absent like the normalizer's `[]` (the two cannot be told apart); the upgrade summary names the kind, the file and the key to set back to `[]` to restore "none".
- **Lists mixing default ids with other ids** (written by interview, org-charter or answers promotion): match no snapshot; kept and reported as customised.
- **Saved script calling `spec-kitty doctrine fetch`**: fails as an unknown command (OD-3); the changelog Before/After and the runbook name the replacement.
- **Uncommitted edits in moved or rewritten files**: the migration carries the working-tree content over (plain filesystem move; the operator commits the result) and lists the moved paths.
- **Windows**: the directory move tolerates a target that does not yet exist and refuses with a named path when a file is locked; covered by a `windows_ci` case.
- **User-chosen path values containing "doctrine"** (for example `local_path: packs/doctrine-foo`): never rewritten; the rename covers vocabulary keys only.
- **Lane worktrees created before the upgrade**: an unmigrated worktree hits the FR-011 error, whose text names the remedy (upgrade the repository root, then merge the target branch into the lane; never rebase, because a rebase loses the approval stamp).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Activate a preset | As an operator, I want `spec-kitty charter activate --pack <pack> --preset <preset>` (`--pack` defaults to `built-in`) to apply a pack's activation preset with **replace semantics**: every key the preset governs (each `activated_<kind>` of a charter-activatable kind except `activated_skills` and `activated_glossary_packs`, as derived from `ArtifactKind`; plus `activated_kinds`, and `mission_type_activations` when the preset lists it) is written as listed or removed when the preset leaves it unrestricted, in one atomic write to the resolved activation write target; the org's `required_<kind>` is unioned in; a governed key that would change is refused without `--force` (OD-6) when its current value differs both from the preset's value and from what the built-in `default` preset leaves (so applying a preset to a freshly initialised project needs no `--force`); a preset that does not list `mission_type_activations` leaves that key untouched (an absent key fails mission creation closed); `--preset` is mutually exclusive with positional `kind id`; `--compile`, `--resynthesize` and `--json` carry over. | High | Open | [build] | no |
| FR-002 | Built-in presets as pack data | As an operator, I want the built-in pack to ship `default` and `minimal` presets as pack data under `packs/built-in/presets/`, where `default` lists no artifact ids and no `activated_kinds` (every built-in artifact is effective) plus the built-in mission types, and each preset's `activated_kinds` is consistent with its own per-kind keys (fixing `minimal`, which today disables six kinds its comment says stay open), so that the default can never drift. | High | Open | [build] | no |
| FR-003 | Init equals the default preset | As an operator, I want skipping charter activation during `spec-kitty init` to leave the project exactly as `--preset default` would, with `init`, `charter generate` and the upgrade provisioning reading the mission types from the built-in pack's `default` preset (fail-closed when the preset is missing), so that both paths agree. | High | Open | [ratchet] | yes — positive control: a copied built-in pack whose `default` preset lists a different mission-type set makes `spec-kitty init` write that set |
| FR-004 | Presets from any pack | As a pack author, I want presets discovered by the charter layer from any pack (built-in, org, fetched) and listed by `spec-kitty charter pack list`, so that my pack can ship its own starting points. | High | Open | [build] | no |
| FR-005 | Retire the preset registry | As a maintainer, I want `BUILTIN_PACKS` / `charter_pack_registry`, `src/charter/activation/packs/`, `charter.activation.default_pack`, `pack_manager.merge_defaults` / `_load_default_pack`, `charter pack apply` and the `accompanies_doctrine_pack` descriptor field removed, with every former reader of `default.yaml` (inventory in plan research: 11 live consumers) repointed to the `default` preset, the effective set, or retired, so that presets have one home. Lands only after FR-012 has frozen its snapshots and neutralised the rc35 migration. | Medium | Open | [build] | no |
| FR-006 | Charter homes for every doctrine command | As a pack author, I want each `spec-kitty doctrine` leaf to have a named `charter` home: `fetch`, `new`, `validate`, `org init`, `org validate` (already shared handlers, moved out of `doctrine.py`); `pack validate`, `pack assemble` → `charter pack validate/assemble`; `regenerate-graph [--check]` → `charter pack regenerate-graph [--check]`; `asset list/path` → `charter pack asset list/path`; `mission-type list` → `charter mission-type list --include-inactive`; `charter pack consistency-check` → `charter consistency-check` (OD-8); `charter pack path <pack>` takes a pack name; `spec-kitty doctor doctrine` → `spec-kitty doctor charter-packs` (JSON keys unchanged; they carry no "doctrine"). In-repo callers move in the same work package: `.github/workflows/packs.yml`, `Makefile`, the pack manifest `generated_by` line, CLAUDE.md, `packs/internal/**` and remediation strings. | High | Open | [build] | no |
| FR-007 | Remove the doctrine command group | As an operator, I want `spec-kitty doctrine` removed so that only one command surface exists; old spellings fail through the unknown-command path (OD-3). | High | Open | [build] | no |
| FR-008 | Skill families | As an agent, I want the charter-governance skills named `spk-charter-{governance,glossary,profile-load,spdd-reasons}` and the practice skills `spk-practice-{bulk-edit,semantic-compression,show-me}`, the older skills that back them (`spec-kitty-charter-doctrine`, `spec-kitty-glossary-context`, `spec-kitty-bulk-edit-classification`, `spec-kitty-spdd-reasons`, `ad-hoc-profile-load`; wider scope per OD-7) folded in and deleted, every removed name (plus `spec-kitty-constitution-doctrine`, whose historical rename migration is neutralised) added to `RETIRED_CANONICAL_SKILL_NAMES` so project and user-global roots drop them, historical skill migrations that read deleted sources neutralised, and generated agent copies and manifests regenerated. `doctrine-daphne` is unchanged. | High | Open | [build] | no |
| FR-009 | Three meanings, three names | As a maintainer, I want the code to separate Charter Pack, activation preset and active charter, renaming `CharterPackManager`, `CharterPackConfigError` and the JSON error code `CHARTER_PACK_CONFIG_INVALID` (golden `mission_create_refusals.json` updated, listed in the changelog Before/After), with no re-export alias. | Medium | Open | [build] | no |
| FR-010 | Rename retired-tier wording | As an agent or contributor, I want retired-tier "doctrine" wording in living code, packs and docs renamed per the occurrence map, including the `src/specify_cli/doctrine/` package, split by meaning (OD-9): pack model and tooling to `charter.offering.packs`, org charter composition to `charter.activation`, fetching and scaffolding adapters to `specify_cli.charter_packs`, with its architectural census/boundary exemptions removed (not moved) and `pyproject.toml` entries updated atomically, and `doctrine_pack_id` per OD-1. | High | Open | [build] | no |
| FR-011 | Remove read-side shims | As a maintainer, I want the `doctrine.org.*`, `organisation_packs` (OD-4), `governance.doctrine.*` and `.kittify/doctrine/` read fallbacks, the tracker `doctrine` ownership key, `--doctrine-mode` flag and `doctrine_mode` JSON output (CR-03; canonical `ownership`), `apply_legacy_governance_selection_key_compat`, `LegacyDoctrineRootWarning` and `LegacyTrackerOwnershipKeyWarning` removed, with one detection seam at the CLI root that fails every command except `upgrade`, `init`, `--version`, `--help`, git merge drivers and hook entry points on an unmigrated project, naming `spec-kitty upgrade` and the runbook. `PackContext.from_config` stays total. | High | Open | [build] | no |
| FR-012 | One upgrade migration | As an operator, I want one idempotent upgrade migration that runs **before every other pending migration** and rewrites the inventory below, so that my project keeps working after the cutover. The rc35 default-pack migration becomes a recorded no-op. Results (moved, rewritten, reset, kept-for-review) go to the migration result and the upgrade summary. | High | Open | [build] | no |
| FR-013 | Glossary and citations | As a reader, I want `docs/context/charter.md` to define charter offering, Charter Pack, activation preset, active charter, project layer and Charter Bundle; retire or redirect Doctrine Pack, Doctrine Pack ID, Doctrine Catalog and Charter Selection; rewrite the `charter` entry's "Do NOT use when"; amend the "active" guard (ADR §1); and repoint every citation of the missing ADR 2026-08-22-2, so that the terms have one canonical definition. | Medium | Open | [build] | no |
| FR-014 | Reachability pins | As a maintainer, I want the stale `test_reachability.py` pins re-asserted against the new default preset, or deleted with each deletion listed and its reason recorded (#5323 item 2). | Low | Open | [build] | no |
| FR-015 | Promotion seeds from the effective set | As an operator, I want the interview, org-charter union, unify-activation migration and resynthesis preflight to resolve an absent key through one public effective-set seam (covering directives, both org packs of a two-pack chain, and ids that differ from file stems) instead of `default.yaml`, and promotion of an absent key to fail closed (key left absent and reported) when the set cannot be resolved, landing before FR-002 (#4400). | High | Open | [build] | no |
| FR-016 | Project pack root, read and write | As a maintainer, I want every reader **and writer** of the project layer (synthesizer, project DRG, project scan, layer-root discovery, skills catalog, review gate bindings, mission-type profiles, runtime bridge, state contract) to resolve `.kittify/charter-packs/` and the pack-relative paths (`drg/fragment.yaml`, `org-charter.yaml`, `presets/`) through one `kernel` constant module, so that `charter synthesize` writes to the new root and no `"doctrine"` path segment is joined to `.kittify` in `src/` (path half of #5825). | High | Open | [build] | no |
| FR-017 | Messaging | As an operator or pack author, I want a changelog Before/After (commands, skills, config keys, directories, descriptor field, JSON codes), a runbook `docs/migrations/charter-pack-cutover.md` (operators, pack authors, saved scripts), the two superseded runbooks marked historical, and the FR-011 error naming the runbook, so that every removed name has a stated replacement. | High | Open | [build] | no |
| FR-018 | Vocabulary gate | As a maintainer, I want an architectural gate that forbids the retired tokens (closed list, below) on living surfaces outside the closed historical-root list, with a scanned-file floor recorded at base, a planted-token self-test per token, and an allowlist that closes empty except the named C-004 identifiers, so that the cutover cannot regress. | High | Open | [build] | no |
| FR-019 | Preset format | As a pack author, I want a documented preset schema (`presets/<name>.yaml`; name grammar; per-kind `activated_<kind>` keys where absent means unrestricted and `[]` means none; `activated_kinds`; `mission_type_activations`; no context-scoped entries), hashed by the pack manifest but not an `ArtifactKind`, validated by `charter pack validate` and `charter org validate` (malformed file or unresolvable id named), and scaffolded by `charter org init`, so that sidecar packs have a contract to write against. | High | Open | [build] | no |

#### FR-012 migration inventory

| Item | Old form | New form | Action |
|---|---|---|---|
| Org packs list | `doctrine.org.packs[]` | `charter_packs.org.packs[]` | rename |
| Single-pack legacy form | `doctrine.org.{local_path,subdir,source_type,url,ref}` (auto-named `default`) | one `charter_packs.org.packs[]` entry with an explicit name (not `default`, which collides with the preset) | rewrite |
| Flat org list | `organisation_packs[]` | `charter_packs.org.packs[]` | rewrite (OD-4) |
| Governance selection | `governance.doctrine.*` in `config.yaml` **and** `charter.yaml`; standalone legacy `governance.yaml` | `governance.charter.*` | rename |
| Tracker ownership | `tracker:` block `doctrine` key (CR-03) | `ownership` | rename |
| Interview answers | `.kittify/charter/interview/answers.yaml` top-level `doctrine:` | canonical key | rename |
| Activation entry key | `doctrine_pack_id` in `charter.yaml` activations | per OD-1 | rename / keep |
| Project layer | `.kittify/doctrine/**` (all subdirectories, `graph.yaml`) | `.kittify/charter-packs/**` | move (collision rule in Edge Cases) |
| Synthesis manifest | `.kittify/charter/synthesis-manifest.yaml` `artifacts[].path` prefix | new prefix | rewrite path |
| Provenance sidecars | `.kittify/charter/provenance/*` keyed to old paths | new paths | rewrite path |
| Pack-skill manifest | `.kittify/skills-manifest.json` `source_ref` under the old root | new root | rewrite path |
| Ignore rules | `.gitignore` patterns for `.kittify/doctrine/**` and their negations | same rules for `.kittify/charter-packs/**` | rewrite |
| Stale activation lists | `activated_<kind>` equal to a frozen released `default.yaml` snapshot for that kind (both before and after the rc5 and rtk retirement rewrites), in `config.yaml` or the pointed `charter.yaml` | key absent | reset |
| Stale kind gate | `activated_kinds` equal to a frozen snapshot's 8-kind list | key absent | reset |
| Released `minimal` kind gate | `activated_kinds` equal to `[directives, tactics]` (every released `minimal.yaml`) | key absent | reset + report (DM-01M497F0NAQARAK3JZFVWF1SD0) |
| Normalizer empty lists | per-artifact `activated_<kind>: []` (written by the 3.2.6 `normalize_activation_absence` migration; indistinguishable from a deliberate `[]`) | key absent | reset + report, naming the file and key to set back to `[]` to switch the kind off again (DM-01M497EW60HNWWJQCXDFA99R0H) |
| Installed skills | removed skill names in configured agent directories (via `get_agent_dirs_for_project`) and command-skill manifests | new names | remove + reinstall |
| Customised lists, `minimal`-equal lists | — | unchanged | report |

Comparison rule for "stale": per key (snapshot data: `research/default-yaml-snapshots.yaml`, 174 releases scanned; original and post-rtk/rc5-rewrite forms), order-insensitive set equality after id normalisation (directive stem and `DIRECTIVE_NNN` compare equal), against the frozen snapshot set embedded in the migration (released versions enumerated from the published wheels during plan research, captured before FR-005 deletes the file).

#### FR-018 closed lists

- **Forbidden tokens**: `doctrine pack`, `spk-doctrine-`, `spec-kitty doctrine`, `doctrine.org.packs`, `organisation_packs`, `.kittify/doctrine`, `accompanies_doctrine_pack`, `CharterPackManager`, `CharterPackConfigError`, `CHARTER_PACK_CONFIG_INVALID`, `charter pack apply`, `Pack Default Charter`, `default charter pack`, `BUILTIN_PACKS`, `specify_cli.doctrine`, `doctor doctrine`, `--doctrine-mode`, `doctrine_mode`, `doctrine_skill`, every removed skill id, and `doctrine_pack_id` if OD-1 renames it.
- **Historical roots**: other missions' `kitty-specs/`, `docs/adr/**`, released changelog sections (section-aware, not whole-file), `docs/reports/**`, archive roots, `docs/plans/**`, `.kittify/evidence/**`, `.kittify/migrations/**`, the shared `FORBIDDEN_SCAN_ROOTS`, the cutover migration modules (`m_*charter_pack_cutover*.py` and its `_charter_pack_cutover_*` helpers) and the legacy-state predicate module, by file.
- **Tombstone files** (their job is to name retired things; exempt by file, each with its reason in the gate): `src/specify_cli/skills/retired.py` (`RETIRED_CANONICAL_SKILL_NAMES`), `src/charter/offering/packs/retired_fields.py`, `src/specify_cli/upgrade/metadata.py`, and every pre-existing `src/specify_cli/upgrade/migrations/m_*.py` module (historical migrations; their `migration_id`s are recorded in consumer projects).
- **Changelog Before/After**: in the Unreleased section, only entries whose bold headline starts `Charter pack cutover:` may spell retired tokens (FR-017 needs them); released sections are historical.
- **Living surfaces in scope**: `src/`, `packs/`, `docs/` (outside the historical roots), shipped skills, `.github/workflows/`, `Makefile`, `CLAUDE.md`, and the generated agent copies in this repository. Consumer-generated `.kittify/charter/` prose is out of scope (refreshed by `charter generate`, not rewritten).

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Effective set preserved | For every legacy fixture (legacy keys only; single-pack legacy form; `organisation_packs`; legacy directory only; stale lists per snapshot including a post-rc5-rewritten one; stale lists in a pointed `charter.yaml`; near-miss stale list; customised lists; `minimal`-equal lists; `governance.doctrine:` in `charter.yaml`; two org packs; mixed stale and custom kinds; pre-rc35 project; synthesized artifacts with provenance; project pack skills), the effective set after `spec-kitty upgrade` (one helper over the activation-aware service, directives, mission types and in-force skills that also applies `activated_kinds`, cross-checked with `charter list --json`; the helper's source digest is pinned in the golden header) is a superset of a golden "before" set generated at the mission base and frozen with its generator and base SHA. "Before" records each kind either as `ALL_BUILTIN` (unrestricted) or as an explicit id set, plus the project and org ids; the comparison expands `ALL_BUILTIN` against the built-in inventory at comparison time, so built-in drift during the mission cannot break equality. Expected relation per fixture class: non-stale fixtures → equal; stale snapshot lists or a stale kind gate → before with those kinds expanded to `ALL_BUILTIN`; `minimal`-equal lists → per-kind lists equal, and the kinds previously excluded by `[directives, tactics]` become `ALL_BUILTIN`; normalizer `[]` lists → the reset kinds become `ALL_BUILTIN`; pre-rc35 → every kind `ALL_BUILTIN` plus the `default` preset's mission types. 0 artifacts lost. | Reliability | High | Open |
| NFR-002 | Gates close empty | `test_doctrine_census`, `test_lifted_cli_doctrine_retirement`, `test_no_deprecated_doctrine_command_in_guidance`, `test_no_dead_doctrine_paths`, the kind-vocabulary single authority and the FR-016/FR-018 gates close with empty allowlists (FR-018 excepted only for the C-004 identifiers); `test_lifted_cli_doctrine_charter_cr02_compat` is deleted with the shim it tests. | Maintainability | High | Open |
| NFR-003 | CLI latency | `charter activate --preset <name>` and `charter pack list`, measured in-process under the `timing` marker as a median of 5 runs, take no more than 1.5× `charter list` on the same fixture (built-in pack plus two org packs). | Performance | Medium | Open |
| NFR-004 | Upgrade idempotence | On every NFR-001 fixture, the first `spec-kitty upgrade` changes something, and a second changes 0 bytes (tree hash over `.kittify/`, `.gitignore` and the agent directories) with the migration's `detect()` false. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No compatibility layer | No alias commands, alias skills, re-export aliases, redirect stubs or read-side fallbacks; a one-time upgrade migration and validation diagnostics that name a replacement are allowed (owner ruling, ADR 2026-10-06-1 §7). | Business | High | Open |
| C-002 | Historical records immutable | `kitty-specs/` of other missions, released changelog sections, ADRs, dated reports and the archive keep their wording. | Business | High | Open |
| C-003 | Pack tiers | `packs/built-in` ships to consumers and `packs/internal` does not; nothing maintainer-only moves into `packs/built-in`. Pack edits are followed by `charter pack regenerate-graph`. | Technical | High | Open |
| C-004 | Names kept | The `doctrine-daphne` profile id and name, `DIRECTIVE_039`, and "doctrine" as governance content are unchanged. | Business | Medium | Open |
| C-005 | Out of scope | The Walk-B half of #4573, the built-in/builtin tier spelling (#5825), #5823, #5824, and compatibility residue unrelated to the doctrine vocabulary (for example the `charter sync` no-op; OD-5) are not part of this mission. | Business | Medium | Open |
| C-006 | Acceptance tests first | WP01 turns every FR (and the NFRs with a measurable check) into acceptance tests before any implementation WP starts. Tests for behaviour not yet built are committed as strict `xfail` naming the WP that turns them green. Every later WP takes its done-condition from those tests and flips its own `xfail`s; it does not redefine the acceptance criteria (owner ruling, 2026-10-06). The NFR-001 golden "before" sets are generated in WP01, at the base. | Process | High | Open |
| C-007 | Layering | Path constants live in `kernel`; preset discovery, the effective-set seam, layer-root/org-chain resolution, the pack model and tooling, and org charter composition live in `charter` (no `specify_cli` preset registry, no `charter` → `specify_cli` import); the interview stops importing from a migration module. | Technical | High | Open |
| C-008 | Ordering | FR-015 before FR-002; FR-016 before FR-011/FR-012; FR-012 (snapshots, run-first ordering, rc35 no-op) before FR-005 and FR-011; FR-006 before FR-007; FR-008 before FR-018. | Technical | High | Open |

### Key Entities

- **Charter Pack**: a pack directory with artifacts, DRG edges, a descriptor (`pack.yaml`), optional enforced activations (org packs, `org-charter.yaml`) and an optional `presets/` directory.
- **Activation preset**: `presets/<name>.yaml` in a pack (FR-019): per-kind `activated_<kind>` keys (absent = unrestricted, list = allowlist), optional `activated_kinds`, optional `mission_type_activations`; ids resolve against the whole offering.
- **Active charter**: the project's per-kind activation keys, `activated_kinds` and mission-type activations, in `config.yaml` or the pointed `charter.yaml`.
- **Project layer**: one flat root, `.kittify/charter-packs/`, holding the project's own components; part of the offering, listed by `charter pack list` as `project`, ships no presets.
- **Legacy project state**: everything in the FR-012 inventory, rewritten once by the upgrade migration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator switches a project between the `minimal` and `default` presets with one command each, and `charter list --json` matches the preset in 100% of fixture runs; after `--preset default` every per-kind key is absent — [build] · no-op passable: no
- **SC-002**: After `spec-kitty upgrade` on each NFR-001 fixture, 0 artifacts of the golden "before" set are lost, and stale fixtures gain exactly the upgrading CLI's built-in inventory — [build] · no-op passable: no
- **SC-003**: The FR-018 gate finds 0 forbidden tokens on living surfaces, over at least the base-recorded file floor — [build] · no-op passable: no
- **SC-004**: Each former `spec-kitty doctrine` leaf command listed in FR-006 runs through its `charter` home on the same fixture with the recorded exit code and key output, and each old spelling exits 2 — [build] · no-op passable: no
- **SC-005**: The changelog Before/After lists every removed command, skill, config key, directory, descriptor field and JSON code, and the runbook exists — [build] · no-op passable: no

## Owner decisions (ruled 2026-10-06)

Stijn Dejongh accepted every recommended default except OD-9, where he accepted the split below after reviewing the package contents. Recorded in ADR 2026-10-06-1 (Amendment 2026-10-06) and on #3732.

| ID | Question | Ruling |
|---|---|---|
| OD-1 | `doctrine_pack_id` (persisted in project `charter.yaml` and every org pack's `org-charter.yaml`, strictly validated): rename or keep? | Rename to `charter_pack_id`; the migration rewrites project state; org packs get an `org-charter.yaml` schema-version bump and a validation error naming the field. |
| OD-2 | Third-party `pack.yaml` still carrying `accompanies_doctrine_pack`: reject or tolerate? | Reject with a validation error naming the field to delete; send the public-packs sidecar a PR. |
| OD-3 | Removed `spec-kitty doctrine`: bare unknown-command error, or a one-line root hint naming the runbook (not a registered command, does no work)? | Bare unknown-command error; the changelog and runbook carry the message. |
| OD-4 | Remove the `organisation_packs` legacy key too? | Yes; migrate it in FR-012. |
| OD-5 | Compatibility residue unrelated to doctrine vocabulary (`charter sync` no-op): in scope? | Out of scope; follow-up #5828. |
| OD-6 | Applying a preset over customised lists: refuse without `--force` (with a diff), and record the applied preset name? | Refuse without `--force`, print the diff; do not persist the preset name. |
| OD-7 | Fold scope for `spec-kitty-*` skills: ADR §5 says the whole layer (13 `spec-kitty-*` directories plus `spec-kitty`, `ad-hoc-profile-load` and `adversarial-squad`), FR-008 says only the five that back the renamed skills. | The five here; the rest of the layer as a follow-up mission (#5830); ADR deviation recorded (amendment ruling 7). |
| OD-8 | Name for the moved `consistency-check`. | `spec-kitty charter consistency-check` (avoids a clash with `validate`, `lint`, `bundle validate`). |
| OD-9 | Target for `src/specify_cli/doctrine/` (all code, ~7,600 lines; 52 imports from `charter`, 3 back into `specify_cli`). | **Ruled: split by meaning, not renamed.** Pack model and tooling (descriptor, manifest, built-in manifest, lineage, validator, assembler) → `src/charter/offering/packs/`; org charter composition (`org_charter`, `org_charter_loader`, `config`) → `src/charter/activation/`; fetch and scaffold adapters (`sources/`, `snapshot`, `template_render/`) → `src/specify_cli/charter_packs/`. The boundary exemption for the old package is deleted. |
| OD-10 | One mission and one PR (about 19 work packages), or split? | One: a no-shim cutover cannot ship half. |

## Assumptions

- The built-in pack stays bundled with the CLI; other packs, including those from the public-packs sidecar repository, arrive through `spec-kitty charter fetch`.
- `spec-kitty upgrade` is the only supported path from a pre-cutover project.
- The migration uses a plain filesystem move (not `git mv`); the operator commits the result.
- The occurrence map is derived from the 2026-10-06 classification ledger (measured at `b327f5bb`) and re-derived at the mission base before implementation.
