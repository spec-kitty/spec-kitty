# Post-spec adversarial review: architecture and feasibility

Mission: `charter-pack-cutover-01M491G6`. Spec at `01476e16`, ADR `2026-10-06-1`. Reviewer: architect-alphonso profile, read-only.

Line numbers refer to branch `issue-3732-charter-pack-rename` as checked out.

---

## A. Seams: who consumes `default.yaml` today

There are 11 live consumers, through 3 loaders plus 2 private readers:

| # | Consumer | Reads | What breaks under "default lists no ids" / file moved |
|---|---|---|---|
| 1 | `charter/activation/default_pack.py:88` `load_default_pack_activation_ids` | per-kind lists | Returns `{}`. Every caller then promotes a bare list (see B1). |
| 2 | `specify_cli/doctrine/org_charter.py:406` org-required union | (1) | #4400 narrowing |
| 3 | `specify_cli/upgrade/migrations/m_unify_charter_activation.py:115,280` | (1) | #4400 narrowing |
| 4 | `specify_cli/cli/commands/charter/interview.py:127` (via `load_default_pack_ids` from the migration module) | (1) | #4400 narrowing |
| 5 | **`specify_cli/cli/commands/charter/_resynthesis_preflight.py:37`** (not named in FR-015) | (1) | When a key is absent, the preflight builds the future set as `{identifier}` only (`:44`), so the resynthesis preflight checks a narrowed set. |
| 6 | `charter/activation/default_pack.py:114` `load_default_mission_type_activations` (fail-closed) | mission types | It must read the new preset. A preset that is absent or empty must still raise. |
| 7 | `charter/activation/compiler.py:634,647` `provision_mission_type_activations` (`charter generate`, `upgrade.py:498-502`) | (6) | Repoint |
| 8 | `specify_cli/provisioning/default_charter.py:52,87-152` (`init`; `DefaultCharterPackMissingError`) via `charter_pack_registry.resolve_builtin_pack_path` | (6) + registry | The registry is removed by FR-005, so this needs a new resolver. |
| 9 | `charter/activation/pack_manager.py:552,685,1123` `_load_default_pack` / `merge_defaults` | per-kind lists, own reader | It writes `[]` for every absent key, which is total narrowing. No src caller, but tests use it (`tests/charter/test_activation_engine_charter_yaml.py:297`). It must be deleted, not left in place. |
| 10 | `specify_cli/charter_pack_registry.py:97-175` + `cli/commands/charter/pack.py:20,81` (`pack list/path/apply`) | both files | removed by FR-005 |
| 11 | `specify_cli/upgrade/migrations/m_3_2_0rc35_default_charter_pack.py:71-77,152-157` | own hard-coded path | Once the file is gone, `apply` returns `success=False`, so **every upgrade from a pre-rc35 project fails**. |

Docstring-only references: `schemas.py:368,378`, `charter_yaml_io.py:439`, `activation_engine.py:54,304`, `m_3_2_6_*`, `m_4_0_0rc5_*`, `m_3_2_0rc35_activate_builtin_mission_types.py:40-46` (that one also has its own hard-coded roster).

Deactivation planning (`activation_engine.py:106-135`, `NoActivationRestrictionsError`) still says to seed the default pack with `spec-kitty upgrade`. Once `default` means "absent", that remedy loops: after an upgrade the key is still absent.

---

## Findings

### B1: blocker. FR-015 does not say what happens when the effective set cannot be resolved

**Where:** spec FR-015, US5.

**Evidence:**
- `promote_activations` materialises `default_ids.get(yaml_key, ())` (`activation_engine.py:566-573`). An empty value writes a bare restrictive list (`_plan_promotion`, `:492-494`).
- The #4399 seam is two private helpers in `pack_manager.py`:
  - `_effective_ids_for_kind` (`:454-511`) returns `()` on any failure ("Diagnostics must never turn an activation into a failure", `:478-482`). It also always returns `()` for `directive` (`:488-494`) and for `mission-type`.
  - `_chain_complete_available` (`:408-443`) needs the CLI's `layer_roots`, which come from `specify_cli/cli/commands/charter/_layer_roots.py`.
- Reusing that seam as-is for promotion re-creates #4400 whenever building the service fails, for example at upgrade time on a half-migrated tree.

**Proposed spec change:**
- FR-015 adds: "Promotion of an absent key fails closed. If the effective set for that kind cannot be resolved or is empty while artifacts of the kind ship, the key is left absent and the caller reports it. It never writes a bare list."
- `promote_activations` makes the default set required for every absent key (no `default_ids or {}`).
- Name one public seam, for example `charter.activation.effective_ids_for_absent_key(repo_root, kind)`. It must cover directives, which means moving org-chain root resolution below `specify_cli` (see L1).
- Add `_resynthesis_preflight.py` as a fourth caller. Delete `merge_defaults` and `_load_default_pack`.

### B2: blocker. The semantics of applying a preset are undefined, and today's merge cannot express `default`

**Where:** FR-001, US1 AS-2.

**Evidence:**
- `merge_pack_into_config` (`charter_pack_registry.py:151-175`) is additive: a present key is skipped unless `--force`.
- `default` means "keys absent". So `--preset default` after `--preset minimal` must **delete** keys (`activated_directives`, `activated_tactics`, `activated_kinds`). No current code path deletes activation keys.
- Today's `apply` also has `--force`, `--compile` and `--json` (`pack.py:280-300`). `charter activate` already takes positional `kind id` plus `--cascade`, `--resynthesize` and `--compile` (`activate.py:797-820`).

**Proposed spec change:** add an FR, or extend FR-001, that defines:
- **Replace semantics.** Applying a preset sets every activation key the preset governs: listed keys are written, unlisted keys are removed. This includes `activated_kinds` and `mission_type_activations`. It excludes `activated_skills` and `activated_glossary_packs`, which have their own absence contract (`charter_pack_registry.py:44-66`).
- **Customised keys.** What happens to a key the operator customised: refuse unless `--force`, or show a diff and confirm.
- **Flags.** `--preset` is mutually exclusive with positional `kind id`. `--compile`, `--resynthesize` and `--json` carry over.
- **Write target.** One atomic write through `resolve_activation_write_target`, either `charter.yaml` or `config.yaml`.

### B3: blocker. Stale `activated_kinds` is not in FR-012's reset

**Where:** FR-012, NFR-001, US2 AS-2.

**Evidence:**
- `default.yaml:5-13` lists 8 kinds. rc35 wrote it into projects (`m_3_2_0rc35_default_charter_pack.py:123`).
- An absent `activated_kinds` means every `ArtifactKind` (`pack_context.py:84,610-617`).
- A present list is enforced as a kind gate in DRG filtering (`drg_activation.py:420-424`). Upgraded projects therefore filter out `anti_pattern`, `glossary_pack`, `skill`, `template` and `asset` nodes. That is a #5323-class loss that FR-012 as written leaves in place.
- The same gate means `minimal.yaml:24-26` (`activated_kinds: [directives, tactics]`) turns off styleguides, toolguides, paradigms, procedures, agent_profiles and mission_step_contracts at the DRG level. Its own comment (`:17-22`) says those kinds "fall back to admit all built-ins". This appears to be a latent defect that ships into the new preset unless the preset content is audited.

**Proposed spec change:**
- FR-012 resets `activated_kinds` when it equals the stale 8-kind list.
- FR-002 says that `default` writes no `activated_kinds`.
- FR-002 adds a check that each preset's `activated_kinds` agrees with its own per-kind keys, and fixes `minimal` (drop `activated_kinds`, or list every kind).

### B4: blocker. "Equals the stale `default.yaml`" has no single comparand

**Where:** FR-012, the stale-list edge case, SC-002.

**Evidence:**
- Projects took rc35 at different releases.
- Later migrations rewrote ids inside those lists:
  - `m_3_2_6_retire_rtk_search_tooling`
  - `m_4_0_0rc5_retire_single_owner_doctrine_ids`, which includes moves and successors (`:22-45`)
- A project that took rc35 early therefore holds a list that differs from today's file. Comparing only against today's file classifies most real stale projects as "customised", and they keep losing newer built-ins. That fails SC-002's intent.
- FR-005 also deletes the file the migration needs to compare against.

**Proposed spec change:**
- FR-012 compares each key separately against a frozen set of snapshots. There is one snapshot per released `default.yaml`, after the later retirement rewrites have been applied. The snapshots are stored as migration-private data.
- The snapshots are captured before FR-005 deletes the file.
- Plan research enumerates the released versions from the PyPI wheels, because the local history is squashed (`git log --follow` shows 1 commit).

### B5: blocker. Migration ordering deadlocks once the shims are gone

**Where:** FR-011, FR-012, US2 AS-5.

**Evidence:**
- The runner orders migrations by `target_version` (`upgrade/runner.py:297-340`).
- The new migration would target ≥ 4.0.0rc7, so on a legacy project these run first, against shim-less readers:
  - `m_unify_charter_activation` (3.2.6rc1). It promotes through the effective-set seam, which builds the doctrine service and reads org packs and `.kittify/doctrine`.
  - `m_unify_charter_activation_finalize`. It calls `apply_legacy_governance_selection_key_compat` (`:231,247`), which FR-011 deletes.
  - `m_4_0_0rc5_retire_single_owner_doctrine_ids`. Its org-resolvable skip goes through `resolve_existing_org_roots` (`_retired_activation.py:348-352`). With the legacy key unread it finds no org packs and retires ids the project can still use (`tracker-organisation-workflow`).
- US2 AS-5 ("any charter command fails naming `spec-kitty upgrade`") becomes self-referential if those readers raise during the upgrade.

**Proposed spec change:** FR-012 states that the cutover migration runs **before** every other pending migration. Options: a runner pre-phase, or migrations whose target precedes 3.2.0. Alternatively, FR-011 copies the legacy-aware readers into a migration-private helper that the older migrations use, and no runtime code imports it. Add a fixture: a pre-rc35 legacy project upgraded to HEAD in one run.

### B6: blocker. The `.kittify/doctrine` move is a write-side cutover of about 60 files, not "remove a read fallback"

**Where:** FR-011, FR-016, US2 AS-1.

**Evidence:**
- Only **one** call site uses the dual-root reader: `synthesizer/reconcile.py:612` → `kernel/doctrine_root.py:76`. Its own docstring says "M3 performs the actual on-disk data move and flips write call sites over" (`:7-9`), and that has not happened.
- The rest of the code hard-codes `.kittify/doctrine`: 124 lines in 63 files. Examples:
  - writers: `synthesizer/project_drg.py:460`, `resynthesize_pipeline.py:370,453,482`
  - layer-root discovery: `charter/_layer_roots.py:21`, `skills/catalog.py:60`, `review/gate_bindings.py:74`, `mission_type_profile_repository.py:52`, `offering/drg/project_scan.py:73,200`
  - the runtime layer: `runtime/next/runtime_bridge_composition.py:286`
- Also affected:
  - the state contract `specify_cli/state/contract.py:594` (`project_doctrine_graph`, `.kittify/doctrine/graph.yaml`)
  - this repository's `.gitignore:103-111`
- The spec does not say whether `.kittify/charter-packs/` is **one** pack root (flat, which is what the kernel code implies) or a directory of packs. It also does not say whether the project layer gets a `pack.yaml` or presets.

**Proposed spec change:**
- Make FR-016 "every reader and writer of the project pack root goes through one kernel constant/resolver (no `"doctrine"` path segment in src)".
- Gate it with an AST test in the style of `test_charter_path_literal_authority.py`.
- List the state contract and `.gitignore`.
- Settle the root layout in the spec.
- Raise the FR-016 priority to High, because FR-011 and FR-012 depend on it.

### B7: blocker. Renamed skills linger in user-global skill roots

**Where:** FR-008, US4 AS-1.

**Evidence:**
- Canonical skills are installed into user-global roots (`runtime/agent_skills.py:1,195-205`).
- An existing directory that is not in the canonical set is **preserved** as an "Unproven custom skill". Only names in `RETIRED_CANONICAL_SKILL_NAMES` (`skills/retired.py:9-16`) are retired.
- Without adding the 7 `spk-doctrine-*` names and every deleted `spec-kitty-*` / `ad-hoc-profile-load` name, users keep the old copies forever, and US4 AS-1 fails.
- This happens outside the project, so the project upgrade migration cannot fix it.
- Historical migrations also read deleted skill sources by name:
  - `m_2_1_2_fix_glossary_context_skill.py:22,70-80` reads `charter.offering/skills/spec-kitty-glossary-context/SKILL.md`
  - same pattern in `m_2_1_2_fix_*`, `m_2_1_2_install_*`
  - `m_3_1_1_charter_rename.py:412-413`

**Proposed spec change:**
- FR-008 adds every removed skill name to `RETIRED_CANONICAL_SKILL_NAMES`.
- Add a check that the global bootstrap retires them.
- Neutralise or rebase the `m_2_1_2_*` skill migrations that read deleted sources.
- Regenerate `.kittify/command-skills-manifest.json` if any command skill references the old names.

### S1: should-fix. FR-008 is narrower than the ADR

ADR §5 folds "the rest of that layer" of the `spec-kitty-*` skills. On disk there are 16 `spec-kitty-*` directories plus `ad-hoc-profile-load`, `spec-kitty` and `adversarial-squad` (`src/charter/offering/skills/`). FR-008 folds only "charter" skills.

**Proposed spec change:** state the exact list, or record a deviation from the ADR.

### S2: should-fix. FR-007 relocation scope

`doctrine.py` (1209 lines) hosts `fetch`, `new`, `validate`, `org init|validate`, `mission-type list`, `asset` and `pack *`. `charter/_app.py:27,77-80` imports `fetch`, `new`, `org_app` and `validate` **from** `doctrine.py`.

Removing the group therefore means moving those handlers into a charter module. FR-006 does not list `fetch`, `new`, `validate` or `org`.

Two external surfaces also call the old command:
- CI: `.github/workflows/packs.yml:225,229` (`spec-kitty doctrine regenerate-graph --check`)
- the generated manifest: `packs/built-in/pack-manifest.yaml:1377` (`generated_by: spec-kitty doctrine regenerate-graph`)

Guidance text also names the old commands:
- `packs/internal/**`, for example `toolguides/test-quality-triage.toolguide.yaml:21`
- `dispatch.py:88` and `pack.py:98`, which say `charter pack apply minimal`
- `org_pack_config.py:123`

**Proposed spec change:** list them in FR-006 and FR-007, and require the CI workflow to change in the same work package.

### S3: should-fix. Hidden machine contracts

**Error code:**
- `CHARTER_PACK_CONFIG_INVALID` is emitted in `--json` output (`charter/mission_type.py:143`) and is documented as a "stable diagnostic code" (`activate.py:106`).
- It is pinned in `tests/core/golden/mission_create_refusals.json:600-601` (mission create JSON).
- `orchestrator_api` does not reference it.

**Proposed spec change:** FR-009 lists every renamed JSON code in the changelog Before/After, and checks the SaaS consumers.

**Descriptor field:**
- `PackDescriptor` is `extra="forbid"` (`pack_descriptor.py:48`). `packs/built-in/pack.yaml:12` carries `accompanies_doctrine_pack: null`.
- Removing the field (FR-005) makes **every org or fetched pack that still carries it fail validation**: the public-packs sidecar, consumer org packs, and cached snapshots. The project upgrade does not rewrite those.

**Proposed spec change:** add a pack-side remediation, for example `charter pack validate` naming the field to remove, plus a sidecar PR. Alternatively, explicitly accept the break.

**Third legacy key:**
- There is a third legacy config key, `organisation_packs` (`org_pack_config.py:456-488`, 12 references). It is missing from FR-011 and FR-012.

### S4: should-fix. Presets have no schema or pack membership

FR-002 and FR-004 say "presets dir" but define no preset file schema. They also do not say whether presets are manifest constituents (hashing, `regenerate-graph --check`), validated by `pack_validator`, or need a kind in the `ArtifactKind` single authority (`test_charter_kind_vocabulary_single_authority.py`).

**Proposed spec change:** add a Key Entity schema for presets, and say that they are hashed by the pack manifest but are not an `ArtifactKind`.

### S5: should-fix. NFR-002 contradicts C-004

NFR-002 asks for "0 exemptions beyond historical roots", but C-004 and the Domain Language line keep `doctrine-daphne`, `DIRECTIVE_039` and "doctrine as content". A lexical gate cannot tell those apart.

**Proposed spec change:** allow a named, shrink-only allowlist for C-004 ids and content-sense occurrences.

### S6: should-fix. Renaming `src/specify_cli/doctrine/` (FR-010)

The rename touches:
- 99 src/test files
- 20 `pyproject.toml` lines (ruff format-exclude ratchet, mypy overrides)
- the boundary and census exemptions:
  - `test_runtime_charter_doctrine_boundary.py:31`
  - `test_doctrine_census.py:80,377-380` (it asserts the directory exists)
- `_owned_checkout_scan.py:100`
- `test_egress_consent_boundary.py:575-580`
- `test_mutation_ownership_routing.py:131,296-328`
- `test_destructive_op_routing.py:179`
- `test_no_dead_modules.py:463`
- `_gate_coverage.py:2263`
- `_interpreter_shard_roster.py:331`

Renamed files also drop out of the ruff format-exclude list, so they get reformatted.

**Proposed spec change:** name the target package. Treat this as a dedicated work package that moves the census and boundary exemptions atomically, with test files that mirror the move.

### L1: should-fix. Layering

- **Constants.** FR-016's constants must live in `kernel`, the only floor shared by charter, runtime and specify_cli (rename `kernel/doctrine_root.py`). `runtime_bridge_composition.py:286` is in `runtime`.
- **Promotion seam.** The FR-015 seam cannot sit in `charter` while it depends on `specify_cli/.../_layer_roots.py` (`test_charter_no_specify_cli_import.py`). Either move org-root-chain resolution into `charter` (it already uses `charter.offering.drg.org_pack_config.resolve_org_roots`) or keep the seam in `specify_cli`.
- **Preset loading.** Do not add a `specify_cli` preset registry. Preset discovery belongs in charter (the built-in root via `resolve_doctrine_root`, org roots via `org_pack_config`). The interview currently imports from a migration module (`interview.py:72`); FR-015 should end that.

### N1: nit

- `charter validate` (artifact files) and the new `charter pack validate` sit side by side. The help text needs to tell them apart.
- `charter check` overlaps `charter lint` and `charter bundle validate`.

---

## Dependencies and proposed work-package order

Hard edges, written "X before Y":

| Before | After | Why |
|---|---|---|
| FR-016 (kernel constants + all R/W sites) | FR-012, FR-011 | B6 |
| FR-012 snapshots captured | FR-005 deletes `default.yaml` | B4 |
| rc35 migration neutralised | FR-005 | consumer row 11 in section A |
| FR-012 migration + runner ordering | FR-011 shim removal | B5 |
| FR-015 effective-set seam | FR-002 (stated in the spec) and FR-005 | B1 |
| FR-006 homes (incl. fetch/new/validate/org, CI workflow, regen `generated_by`) | FR-007 group removal | S2 |
| FR-008 skill rename + retired-name registry | the vocabulary gate (NFR-002) | B7 |
| FR-009/FR-010 code renames | FR-013 glossary, then the docs sweep | — |

**Proposed sequence:**

| WP | Content | Requirements |
|---|---|---|
| WP01 | acceptance tests, strict xfail | C-006 |
| WP02 | kernel pack-path constants + write/read cutover of ~63 files + state contract | FR-016 |
| WP03 | effective-set seam, fail-closed promotion, 4 callers, delete `merge_defaults` | FR-015 |
| WP04 | preset schema + built-in `default`/`minimal` presets in `packs/built-in/presets/` + preset loader in charter + init/generate/upgrade mission-type provisioning repoint | FR-002, FR-003 |
| WP05 | `charter activate --pack/--preset` (replace semantics) + `charter pack list/path` over all packs | FR-001, FR-004 |
| WP06 | cutover migration + frozen snapshots + runner pre-ordering + rc35 neutralisation + this repository's config | FR-012 |
| WP07 | remove registry, `packs/` dir, `pack apply`, descriptor field + sidecar note | FR-005 |
| WP08 | move CLI homes + CI workflow + manifest `generated_by` | FR-006 |
| WP09 | remove the doctrine group | FR-007 |
| WP10 | remove the shims (legacy keys incl. `organisation_packs`, `.kittify/doctrine`, governance key) | FR-011 |
| WP11 | `CharterPackManager` / `CharterPackConfigError` / code rename + golden + JSON consumers | FR-009 |
| WP12 | `specify_cli/doctrine` package rename + census/boundary exemptions | FR-010a |
| WP13–WP15 | `Doctrine*` identifiers and prose in src (2,937 lines across 419 files; `DoctrineService` alone 198 references in 125 files), packs, docs | FR-010b |
| WP16 | skills rename/fold + retired registry + regen | FR-008 |
| WP17 | glossary + ADR citations | FR-013 |
| WP18 | reachability pins | FR-014 |
| WP19 | vocabulary gate (NFR-002) + changelog Before/After | — |

## Size

About 18–20 work packages. Under-sized FRs:

| FR | Under-sizing | Evidence |
|---|---|---|
| FR-010 | about 6–10× | One FR for 419 src files, 840 test files and 68 built-in pack files mentioning "doctrine". Each occurrence needs a content-sense vs tier-sense judgement. |
| FR-011 / FR-016 | about 5× | Framed as removing fallbacks, but the work is a full write-side move (B6). |
| FR-012 | about 3× | Snapshot archaeology, runner ordering, 5+ fixtures, `activated_kinds` (B3–B5). |
| FR-008 | about 2× | Global retirement and the old migrations (B7, S1). |
| FR-001 | — | Hides a new replace-semantics write path (B2). |
