# Post-tasks squad: fold decisions

Orchestrator decisions on the three post-tasks reports (`posttasks-squad-{nonvacuity,architecture,fidelity}.md`). Each line names the finding(s) it resolves. Owner-visible names are listed separately at the end for veto.

## Ordering and dependencies (tasks.md + WP frontmatter)

| Change | Resolves |
|---|---|
| WP06 depends on WP05, WP10, WP17 | NV-B5, AR-B2 (normalizer `[]` neutralised before FR-015 upgrade row) |
| WP09 depends on WP07, WP08, WP10 | NV-B4, AR-B2, AR-S1 (WP10 edits WP09's test) |
| WP12 depends on WP07, WP08, WP09, WP11 | AR-S1 (WP09 edits `upgrade.py`), AR-S9 |
| WP14 depends on WP12, WP13 | AR-S1 (WP13 edits `org_pack_config.py`) |
| WP19 depends on WP14, WP16, WP17, WP18 | AR-S1 (skill prose) |
| WP17 prompt: delete every "wait for WP11 / owners of later files" instruction; WP17 runs after WP05 and before everything that uses its names | AR-B3, FI-S6 |

## Test assignment (WP01 flip map; C-006 means fix it now)

| Test | New owner | Resolves |
|---|---|---|
| `test_fr010_charter_pack_id_in_project_state` | WP11 | NV-B2, AR-B2 |
| every test that invokes `charter pack validate` (FR-019 validate row, `test_us3_4_accompanies_field_rejected`) | WP15; WP07 and WP13 keep unit-level tests in their own owned test files | NV-B3, AR-B2 |
| FR-003 init-vs-preset comparison | WP09 (now depends on WP08) | NV-B4 |
| installed-skill removal through `spec-kitty upgrade` (FR-008 / FR-012 skills row) | WP18 | NV-B6, AR-S7 |
| new: `test_fr010_retired_identifiers_absent[r1|r2|r3r4|prose]` — AST/token scan of a closed per-subsystem identifier list taken from the occurrence map and WP19–WP22 rename tables (e.g. `DoctrineService`, `BaseDoctrineRepository`, `doctrine_root`, `MissingDoctrinePackError`, `OrgDoctrineSource`, `DoctrineCatalog`, `DoctrineSelectionConfig`, `_doctrine_paths`, `doctrine_service_builder`, `action_doctrine_bundle`, `doctrine_service_factory`, `doctrine_synthesizer`), scoped to that subsystem's directories, with a planted-identifier self-test and a scanned-file floor | WP19, WP20, WP21, WP22 respectively | NV-B1, FI-S7 |

## WP01 helper and test semantics

- `pending_until(wp)` is `pytest.mark.xfail(strict=True, reason=f"pending {wp}")` with **no** `raises=` restriction: any exception counts as the expected failure at base. | NV-B7
- A test that already passes at base is **not** pending: it ships unmarked as a regression guard and is excluded from red-first evidence (list them in WP01's prompt: FR-011 exempt invocations, `--preset` + positional exit 2, the FR-012 user-path-not-rewritten test, US2-7 lane consolidate). NFR-003 latency gets a precondition assertion that the command succeeded (exit 0 + expected output) before timing, so a fast failure cannot pass. | NV-B8
- Windows move case (`windows_ci`): exempt from red-first evidence; recorded as such in WP01 and WP11. | NV-S13
- Traceability test: the closed id list includes FR-012 inventory rows (by item name), edge cases (by title), OD-1..OD-10 and both DM ids. | NV-S7
- Add the coverage NV-S6 lists: `--json` shapes per contracts/cli.md, `DEFAULT_PRESET_MISSING`, OD-6 "preset name not persisted", FR-013 retirements, FR-019 malformed-file cases, `PackContext.from_config` totality on a legacy fixture. | NV-S6
- NFR-002 rows check every exemption structure in each named gate (including `TICKETED_BASELINE`, `_LAZY_BASELINE_ALLOWLIST`), not one per gate. | NV-S9
- FR-005 scan exempts the preset loader reading `presets/default.yaml` (it forbids `charter.activation.default_pack`, `charter_pack_registry`, `BUILTIN_PACKS` and `src/charter/activation/packs/`). | NV-S5

## Golden "before" sets (NFR-001) — spec NFR-001 is amended accordingly

- The measuring helper applies `activated_kinds` (mirrors `drg_activation.py:423`). | NV-golden-S1
- "Before" records each kind as either `ALL_BUILTIN` (unrestricted) or an explicit id set, plus project/org ids; the comparison expands `ALL_BUILTIN` against the inventory at comparison time, so built-in drift during the mission cannot break equality. | NV-golden-S2
- The helper's source digest is pinned in the golden header; WPs never edit it (a needed change is a WP01 follow-up with a regenerated golden, logged). | NV-golden-S3
- Expected relation per fixture class (spec NFR-001 amended): non-stale → equal; stale snapshot lists / stale kind gate → before with those kinds expanded to `ALL_BUILTIN`; `minimal_equal` → per-kind lists equal, kinds previously excluded by `[directives, tactics]` become `ALL_BUILTIN`; `normalizer_empty_lists` → reset kinds become `ALL_BUILTIN`; `pre_rc35` → every kind `ALL_BUILTIN` plus the `default` preset mission types. | NV-B9

## Package split

- WP04's `charter.packs` facade exports only offering-side functions; the two org-charter-composing entry points are added to the facade by WP05 when `org_charter` lands in `charter.activation` (the facade module is not under `charter/offering/`, so importing `charter.activation` there is legal). | AR-B1

## Upgrade robustness

- The cutover migration's structural predicate (legacy root present, legacy keys present, `doctrine_pack_id` present) re-selects it even when `metadata.yaml` records it applied; the `[]`/snapshot/kind-gate resets run only on the first application (recorded). WP10 implements selection, WP11 the split predicate. | AR-B4
- The WP14 CLI-root gate exempts git merge drivers and hook entry points (`merge-driver-*`, live-work and session-start hooks) in addition to `upgrade`, `init`, `--version`, `--help`. | AR-S3
- WP11 drops the `ci-router.yml` `.kittify/doctrine/**` path filter deferred by WP03. | FI-S8

## Removal completeness

- WP14 T070 deletes every temporary legacy symbol WP02/WP03 introduce: `resolve_project_pack_read_root`, `LEGACY_PROJECT_PACK_DIRNAME`, their call sites, the preflight runner dual prefix, the `service.py` legacy comparison, the manifest `_is_legacy_artifact_prefix`, the `test_*_legacy_root_read_fallback` tests, the path-gate legacy exemption and the two path-gate allowlist entries assigned to WP14. | FI-B1, AR-S2

## FR-018 / WP25

- WP25's exemption list equals spec FR-018 exactly (historical roots, cutover modules and helpers, legacy predicate module, tombstone files, changelog headline rule); no escalation for what the spec already exempts. The scanned-file floor is a literal recorded in WP01 at base, not derived from the gate's own scope function. | FI-S2, AR-S4, NV-S10, NV-S11

## Contracts and messaging

- Preset-governed kinds include `anti_patterns` (charter-activatable per `ArtifactKind`, #5409); templates/assets are not activatable; skill and glossary_pack excluded. Contract schema and WP07 updated. | FI-S1
- `contracts/cli.md` gains: `charter pack path <pack> --preset`, flag-combination exit-2 rules, `--json` shapes for `activate`, `pack list`, `pack path`, `doctor tool-surfaces --kind charter-skill`, error text format `Error (<CODE>): <message>`. `contracts/upgrade-migration.md` gains the `migration_reports.charter_pack_cutover` keys. | FI-S9, FI-S10
- WP24 changelog Before/After adds: `--kind doctrine-skill` → `charter-skill`, `doctrine_skill` → `charter_skill`, `charter pack list --json` shape, state surface `project_doctrine_graph` → `project_pack_graph`, manifest `generated_by`. | FI-S3
- The public-packs sidecar PR (OD-2) is a WP24 subtask: draft the PR description and the descriptor/org-charter changes; the orchestrator opens it after merge. | FI-coverage
- WP18 retires 13 names (the 12 plus `spec-kitty-constitution-doctrine`); counts updated in WP18 and WP12. | FI-S4

## Housekeeping

- Version: the cutover migration targets `4.0.0rc6` (current), no bump; fix WP10's rc7 mention. | AR-S6
- Generated files are unowned: remove `docs/api/cli-commands.md` and any other generated output from WP16's (and others') `owned_files`. | AR-S1, AR-nit
- Every prompt's "Do This First" adds: after WP18 lands, load profiles with `spk-charter-profile-load` (the `/ad-hoc-profile-load` alias is deleted). | FI-nit
- WP06 uses `ActiveCharterManager` (WP17 ran first). | AR-nit
- Stale "runs in parallel" statements and wrong owner attributions corrected against the final graph. | AR-nit
- WP01, WP20, WP22 stay single WPs (owner ruling for WP01; WP20/WP22 are mechanical) but each prompt adds explicit commit checkpoints per subtask so a session can stop and resume. | AR-S8

## New consumer-visible names — approved by the owner (Stijn Dejongh, 2026-10-06)

CLI: `charter activate --pack/--preset`, `charter pack list|path <pack> [--preset]|validate|assemble|regenerate-graph|asset`, `charter consistency-check`, `doctor charter-packs`, `doctor tool-surfaces --kind charter-skill`. Error codes: `ACTIVE_CHARTER_CONFIG_INVALID`, `LEGACY_CHARTER_STATE`, `DEFAULT_PRESET_MISSING`, `PRESET_NOT_FOUND`, `PACK_NOT_FOUND`, `PRESET_ID_UNRESOLVED`, `PRESET_WOULD_OVERWRITE`, `PRESET_INVALID`, `RESYNTHESIS_FAILED` (both approved 2026-10-07, WP08 review), `RETIRED_PACK_FIELD`. Keys/files: `charter_pack_id`, org-charter `schema_version: 2`, `presets/<name>.yaml`, `presets:` in `pack-manifest.yaml`, `presets/starter.yaml` scaffold, state surface `project_pack_graph`, `charter_skill`. Python: `charter.packs`, `ActiveCharterManager`, `ActiveCharterConfigError`, `CharterOfferingService`, `ActiveCharterService`, `BaseArtifactRepository`, `MissingCharterPackError`, `OrgCharterPackSource`. Kept with "doctrine": pytest marker `doctrine`, doc pages `create-an-org-doctrine-pack.md`, `org-doctrine-layer.md`, `doctrine-kinds.md` (published URLs; renaming needs a redirect, which C-001 forbids), schema `$id` URLs under `/schemas/doctrine/`, persisted key `propose_doctrine_changes`.

## Owner ruling 2026-10-07 — edited copies of retired skills (US4, WP18 review)

Option A: when the cutover keeps an edited installed copy of a retired skill, it also drops that copy's skills-manifest entry, so the copy becomes user-owned. It is reported once ("Kept edited skill copy") and never makes a later `spec-kitty upgrade` exit non-zero or print the "delete it and run upgrade again" advice.

## Owner ratification 2026-10-08 — WP20 public names

Ratified (WP20 review): `OfferingCatalog`, `load_offering_catalog`, `resolve_offering_root`, `GovernanceCharterConfig`, `build_active_charter_service`, modules `active_charter_service_builder`, `action_governance_bundle`, `_project_root_candidates`, JSON key `missing_from_offering` (`charter consistency-check --json`), keyword `charter_service=` on `compile_charter` and related functions.

## Orchestrator rulings 2026-10-08 (WP22)

- WP01 fixture follow-up (logged): `docs/development/docs-retrieval-index.yaml` joins the prose slice's `exclude_patterns` in `tests/fixtures/charter_pack_cutover/retired_identifiers.yaml`. It is generated from every docs page, including the FR-018 historical roots the prose slice already exempts at source; the removed-command gate exempts it for the same reason. The assertion is unchanged.
- `docs/api/batch-api-contract.md` `doctrine_mode` (SaaS wire-payload example): the payload contract is authored upstream (spec-kitty/saas; client-repo inversion ADR 2026-09-06-1) and the CLI-side producer was removed by WP14. WP25 decides: if the doc still describes a live upstream contract, keep the key with a narrow, reasoned FR-018 exemption naming the file; if the section only documents the removed CLI producer, delete or mark it historical. No rename of an upstream-owned wire key from this repo.
- (WP24) WP01 fixture follow-up (logged, commit 41ac0dbe on lane-x): `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml` joins the prose slice's exemptions in `tests/fixtures/charter_pack_cutover/retired_identifiers.yaml`. FR-013 requires deprecated-term redirect entries that spell the retired terms; same reason `docs/context/charter.md` is already exempt. WP25's FR-018 gate needs the same file-level exemption (plus the glossary seed's deprecated entries).
- Public-packs sidecar PR draft persisted at research/sidecar-public-packs-pr-draft.md; the orchestrator opens it after the mission PR merges.
