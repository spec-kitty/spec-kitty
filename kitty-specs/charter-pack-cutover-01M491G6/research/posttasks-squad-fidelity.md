# Post-tasks squad: scope fidelity and consumer impact

**Lens**: scope fidelity and consumer impact (profile `doctrine-daphne`, curator role).
**Base**: branch `issue-3732-charter-pack-rename`, HEAD `051d5a55`.
**Read**: ADR `docs/adr/4.x/2026-10-06-1-…` (with the 2026-10-06 amendment), `spec.md`, `occurrence_map.yaml`, `plan.md`, `data-model.md`, `contracts/{cli,errors,upgrade-migration}.md`, `contracts/activation-preset.schema.yaml`, `tasks.md`, `tasks/WP01`–`WP25`.
**Read-only**: nothing was edited except this file.

## Summary

| Severity | Count |
|---|---|
| BLOCKER | 1 |
| SHOULD-FIX | 10 |
| NIT | 13 |

Every ADR decision, every amendment ruling except one part of ruling 2, every FR, NFR and C, and every occurrence-map category, exception and move has at least one owning subtask. I found no breach of C-002 (historical records) and no breach of C-003 (pack tiers). The issues are:

- One temporary read fallback that no work package removes (C-001), the BLOCKER.
- One requirement that a prompt narrowed: presets do not govern `activated_anti_patterns`, though FR-001 and SC-001 say they should.
- Changelog gaps.
- About 60 new consumer-visible names chosen by prompt writers, listed at the end for the owner's veto.

---

## 1. Coverage table

### 1a. ADR decisions and amendment rulings

| Item | Delivered by | Note |
|---|---|---|
| §1 model (offering / Charter Pack / preset / active charter / Bundle) | WP17 T083–T084 (names), WP24 T107 (glossary) | |
| §1 "active" guard amended | WP24 T107 step 1 | |
| §2 `charter activate --pack --preset`, `--pack` default `built-in` | WP08 T041–T042 | |
| §2 `default` = no per-kind restriction, `minimal` curated | WP07 T037 | anti_patterns gap, see S1 |
| §2 init skip = `--preset default`; mission types from `default` preset | WP09 T046–T047 | |
| §3 presets are pack data, discovered from any pack | WP07 T036, WP08 T043 | |
| §3 `src/charter/activation/packs/` and `BUILTIN_PACKS` removed | WP13 T066 | |
| §3 `accompanies_doctrine_pack` retired | WP13 T068 | |
| §4 CLI table (every row) | WP08 (list/path), WP13 (apply), WP15 (homes, consistency-check, doctor), WP16 (group) | |
| §5 skills (seven renames) | WP18 T088–T089 | |
| §6 names kept | WP16 T081 note, WP22 rule table, WP21 keep list | |
| §7 no aliases, shims removed | WP14, WP16 | B1: interim fallback has no remover |
| §7 one-time migration; resets stale lists; error names `spec-kitty upgrade` | WP10–WP12, WP14 T072 | |
| Amendment 1 `doctrine_pack_id` → `charter_pack_id`, schema bump, validation names field | WP11 T057, WP17 T085 | |
| Amendment 2 reject `accompanies_doctrine_pack` | WP13 T068 | **The "sidecar repository receives a PR" part has no owner (S5)** |
| Amendment 3 bare unknown-command error | WP16 T080 | |
| Amendment 4 `organisation_packs` removed and migrated | WP11 T056, WP14 T070 | |
| Amendment 5 unrelated residue out of scope | not touched (correct) | |
| Amendment 6 refuse without `--force`, print diff, do not persist the preset name | WP08 T041 step 5, T044 | Not persisting the name is implicit (only governed keys are written). Fine. |
| Amendment 7 fold only the five backing skills | WP18 | WP10/WP18 add a 13th retired name (S4) |
| Amendment 8 `charter consistency-check` | WP15 T077 | |
| Amendment 9 package split by meaning; layer roots into charter; exemption deleted | WP02 T012, WP04, WP05 T028 | |
| Amendment 10 one mission, one PR | tasks.md (25 WPs, one branch) | |

### 1b. Functional requirements

| FR | WPs / subtasks |
|---|---|
| FR-001 | WP08 T041–T045 (WP01 T004 tests) |
| FR-002 | WP07 T037, T040 |
| FR-003 | WP09 T046–T049 |
| FR-004 | WP07 T036 (discovery), WP08 T043 (CLI) |
| FR-005 | WP06 T033 (`merge_defaults`), WP09 T048 (`default_pack`), WP13 T066–T068 |
| FR-006 | WP15 T075–T079; WP08 T043 (`pack path <pack>`) |
| FR-007 | WP16 T080–T082 |
| FR-008 | WP18 T088–T091; WP12 T063 (installed copies); WP10 T051/T053 (migrations reading deleted skills) |
| FR-009 | WP17 T083–T087 |
| FR-010 | WP04, WP05 (split); WP17 T085 (`charter_pack_id`); WP19–WP21 (identifiers); WP22 (prose); WP23 (tests dir) |
| FR-011 | WP14 T070–T074 (gap B1) |
| FR-012 | WP10 (ordering, neutralisation), WP11 (keys, root, paths), WP12 (resets, skills, summary) |
| FR-013 | WP24 T107 |
| FR-014 | WP25 T112 |
| FR-015 | WP06 T030–T034 |
| FR-016 | WP02 T011–T015, WP03 T016–T020 |
| FR-017 | WP24 T108–T109; WP14 T072 (error names the runbook) |
| FR-018 | WP25 T111 (gap S2) |
| FR-019 | WP07 T035–T040 |

Every row of the FR-012 inventory maps to a step: org packs, single-pack form and `organisation_packs` (WP11 T056); governance in config.yaml, charter.yaml and governance.yaml (T056 steps 2–4); tracker (T056); answers (T056 step 5); `doctrine_pack_id` (T057); project layer (T058); synthesis manifest, provenance, skills manifest and `.gitignore` (T058 step 3); stale lists, kind gates, `minimal` gate and `[]` (WP12 T062); installed skills (WP12 T063); customised and minimal-equal lists (T062).

### 1c. NFRs and constraints

| Item | WPs |
|---|---|
| NFR-001 | WP01 T002–T003 (golden sets), WP12 T065 |
| NFR-002 | WP05 T028, WP16 T081–T082, WP25 T113 |
| NFR-003 | WP08 T045 step 5 |
| NFR-004 | WP12 T065 |
| C-001 | every removal WP; gaps B1, S8 |
| C-002 | respected everywhere (§3 below) |
| C-003 | respected (§4 below) |
| C-004 | WP16 T081 (daphne line 114 only), WP21 keep list, WP22 table |
| C-005 | nothing in scope touches `charter sync`, #5823–#5825 |
| C-006 | WP01 plus a red-first section in every WP |
| C-007 | WP02 T012, WP04–WP06, WP07 T036, WP08 T041 |
| C-008 | dependency graph checked: WP06→WP07; WP03→WP11, WP12→WP14; WP12→WP13, WP12→WP14; WP15→WP16; WP18→WP22→WP25. All edges are present. |

### 1d. Occurrence map

| Entry | Delivered by |
|---|---|
| `code_symbols` | WP17, WP19, WP20, WP21 |
| `import_paths` | WP04, WP05, WP20 T096, WP21 T098 |
| `filesystem_paths` | WP02, WP03, WP11 T058, WP13 T066, WP18 |
| `serialized_keys` | WP11 (migration), WP14 (readers), WP17 (`charter_pack_id`), WP13 (descriptor) |
| `cli_commands` | WP08, WP13, WP15, WP16, WP14 T071 (tracker) |
| `user_facing_strings` (manual_review) | WP19 T094, WP20 T097, WP22 (classification table) |
| `tests_fixtures` | every WP; WP16 deletes the cr02 compat tests; WP23 |
| `logs_telemetry` | WP14 (`doctrine_mode`), WP17 T086 (`doctrine_skill`), WP15 T078 (`generated_by`), WP17 T084 (code). The map says these are "listed in the changelog Before/After"; two are missing (S3). |
| Exceptions: daphne id and name, 039, 018 | honoured (WP16, WP22) |
| Exceptions: historical roots | honoured |
| Exceptions: `migration_id`, `metadata.py`, cutover module | honoured (WP10, WP21 T099 step 2) |
| Exceptions: mission-slug comments | honoured (WP19 T094) |
| Moves: `specify_cli.doctrine` → three homes | WP04 T023, WP05 T026–T028. `config.py` is folded into `org_charter.py`, not created as `charter/activation/config.py`; this is consistent with OD-9 and research A.2 (N12). |
| Moves: presets | WP07 T037 (create), WP13 T066 (delete old) |
| Moves: skills | WP18 T088 |

---

## 2. Findings

### BLOCKER

**B1 — The interim project-root read fallback and the legacy-prefix predicate have no remover (C-001, FR-011).**

- **Evidence.**
  - WP02 T011 step 2 (`WP02:148`) creates `LEGACY_PROJECT_PACK_DIRNAME` and `resolve_project_pack_read_root`, and keeps `LegacyDoctrineRootWarning` in `kernel/charter_pack_paths.py`.
  - WP02 T013 and T014 (`WP02:182-206`) route about 25 read sites through `resolve_project_pack_read_root(..., quiet=True)`. They add a dual legacy/canonical prefix in `charter_runtime/preflight/runner.py` `_DIRTY_SCOPE_PATHS` (`:203`) and a legacy comparison in `offering/service.py:48` (`:188`).
  - WP03 adds the manifest legacy-prefix predicate `_is_legacy_artifact_prefix` (`WP03:109,134`), "deleted by WP14". It also adds `test_*_legacy_root_read_fallback` tests "deleted by WP14" (`WP03:191`).
  - WP03's FR-016 gate exempts the legacy segment in the authority file "until WP14" (`WP03:174`).
  - WP14 T070 step 3 (`WP14:124`) looks for the fallback under its **pre-WP02** name: `git grep -n resolve_doctrine_read_root`. It states "the only caller was `reconcile.py:612`".
  - `grep` across WP04–WP25 for `resolve_project_pack_read_root|LEGACY_PROJECT_PACK_DIRNAME|_is_legacy_artifact_prefix|legacy_root_read_fallback` returns nothing.
- **Risk.** The `.kittify/doctrine/` read fallback, the manifest's legacy-prefix acceptance and the dual dirty-scope prefix can survive the cutover. The FR-018 gate does not catch a bare `"doctrine"` constant. `test_fr011_shims_removed` checks only the warning class.
- **Fix.** Rewrite WP14 T070 step 3 to name everything WP02 and WP03 created:
  - delete `LEGACY_PROJECT_PACK_DIRNAME`, `resolve_project_pack_read_root` and `LegacyDoctrineRootWarning`;
  - repoint every `resolve_project_pack_read_root(..., quiet=True)` call site (list the WP02 B.1 sites) to `project_pack_root`;
  - drop the legacy half of `_DIRTY_SCOPE_PATHS` and of `service.py:48`;
  - delete `_is_legacy_artifact_prefix` and the `test_*_legacy_root_read_fallback` tests;
  - remove the legacy-segment authority exemption from `test_charter_pack_path_authority.py`.

  Add an acceptance row in `test_fr011_shims_removed` for `resolve_project_pack_read_root` and `LEGACY_PROJECT_PACK_DIRNAME`. That needs a WP01 test change, so raise it before WP01 lands.

### SHOULD-FIX

**S1 — Presets do not govern `activated_anti_patterns`, contrary to FR-001 and SC-001.**

- **What the requirements say.** FR-001 (`spec.md:134`) governs "each `activated_<kind>` of a charter-activatable kind except `activated_skills` and `activated_glossary_packs`, as derived from `ArtifactKind`".
- **What the code holds.** `ArtifactKind.activatable` includes `anti_pattern`, and `PackContext` reads `activated_anti_patterns` (`src/charter/activation/pack_context.py:173,277,701`). `ACTIVATION_YAML_KEYS` does not include it (measured).
- **What WP07 does.**
  - T035 step 2 (`WP07:132`) derives the governed set from `CHARTER_KIND_TOKENS` and excludes anti_patterns. It records the deviation in the Activity Log only.
  - It also claims that the contract enum lists `anti_patterns, templates, assets`. That is false: `contracts/activation-preset.schema.yaml:21,27` lists eight kinds.
  - T035 step 3 sets `activated_kinds` to 13 plurals, while the contract says 8.
- **Effect.** A project that carries `activated_anti_patterns` keeps it after `--preset default`. This breaks SC-001 ("every per-kind key absent") and US1-2.
- **Fix.** Get an owner ruling before WP07 starts. Either:
  - (a) govern `activated_anti_patterns` (make it writable and removable in WP08's writer; add it to the preset schema and to the WP12 `[]` reset), or
  - (b) amend FR-001 and SC-001 to say "activation keys in `ACTIVATION_YAML_KEYS`" and state that `activated_anti_patterns` is out of scope.

  Correct the false contract claim in WP07, and align the `activated_kinds` enum between WP07 and the contract.

**S2 — WP25's historical-root list leaves out the spec's tombstone files and predicate module.**

- **What the spec says.** `spec.md:182-183` lists these as closed exemptions:
  - the legacy-state predicate module;
  - the `_charter_pack_cutover_*` helpers;
  - **Tombstone files**: `skills/retired.py`, `offering/packs/retired_fields.py`, `upgrade/metadata.py`, and every pre-existing `m_*.py`.
- **What WP25 does.**
  - T111 step 3 (`WP25`, "Historical roots") exempts only `m_*_charter_pack_cutover.py` and possibly the snapshot module.
  - T111 step 5 says these registries are "not covered by the spec's closed lists" and tells the implementer to stop and escalate.
- **Effect.** As written, the gate goes red on `retired.py` (the `spk-doctrine-` prefix) and on older migrations (`spec-kitty-glossary-context` in `m_2_1_2_*`). The last work package would stall on a question the spec already answers.
- **Fix.** Copy the spec's "Historical roots" and "Tombstone files" bullets verbatim into T111 step 3, including `src/specify_cli/migration/legacy_charter_layout.py` and `_charter_pack_cutover_report.py`, `_snapshots.py`, `_resets.py` and `_skills.py`. Delete the escalation sentence for those files.

**S3 — The WP24 changelog Before/After misses renamed names that other WPs change (FR-017, occurrence map `logs_telemetry`).** The table in §5 has the full cross-check. Missing:

- `spec-kitty doctor tool-surfaces --kind doctrine-skill` → `--kind charter-skill` (WP17 T086 step 3, `WP17:255`). It is also absent from `contracts/cli.md`, so `test_fr017_*` cannot catch it.
- The `ToolSurfaceKind` value and surface-id segment `doctrine_skill` → `charter_skill` (WP17 T086). The occurrence map line 41 says it is "listed in the changelog Before/After".
- The `charter pack list --json` row shape changes from preset rows to `{name, tier, root, presets[]}` rows (WP08 T043). This is a breaking change to an existing JSON contract, and WP24 lists it only under Added.
- The state-contract surface name `project_doctrine_graph` → `project_pack_graph` (WP03 T018 step 1). `doctor` prints state surfaces (`cli/commands/doctor.py:339`).
- The pack-manifest `generated_by` value (WP15 T078 step 3; occurrence map C12 says "listed in the changelog").
- `spec-kitty-constitution-doctrine` retirement, if S4 is kept.

Fix: add these rows to `contracts/cli.md` and `contracts/errors.md` (or a new "output/telemetry" table) and to WP24 T108 step 2.

**S4 — Scope creep: a 13th retired skill name.**

- **Where.** WP10 T053 step 1 (`WP10:174`) and WP18 (`WP18:180`) add `spec-kitty-constitution-doctrine` to `RETIRED_CANONICAL_SKILL_NAMES`. Neither FR-008 nor ruling 7 asks for this.
- **Contradictions.**
  - WP18's own review checklist says "Retired list contains exactly the twelve" (`WP18:323`).
  - WP12 `REMOVED_SKILL_NAMES` has twelve names (`WP12:158`).
- **Consumer impact.** User-global copies of that skill are deleted on the next CLI run.
- **Fix.** Get an owner veto or approval. If approved, add the name to FR-008, the WP12 list, the WP24 changelog and the WP25 token list. If vetoed, drop WP18 line 180 and keep WP10's "leave the directory alone".

**S5 — Ruling 2's "the public-packs sidecar repository receives a PR" has no owner.**

- WP13 T068 note (`WP13:149`) says this is out of the WP's code scope and to "record it for WP24's runbook".
- WP24 T109 does not mention it.
- **Fix.** Give it an owner: a closeout step in WP25 or WP24 that opens or links the sidecar PR (or a tracking issue), recorded in the PR body.

**S6 — WP17 contradicts the dependency graph.**

- `WP17:164`: "WP11 (T057) migrates … Confirm both are done before starting". `WP17:242`: "WP11's migration already rewrote project `charter.yaml`". But tasks.md and WP11's frontmatter make WP11 depend on WP17.
- `WP17:165,175-179` tells the implementer to confirm that owning WPs (WP06, WP08, WP09, WP12, WP14, WP15) are `done` before editing their files. All of them are downstream of WP17, so the condition can never be met.
- Taken literally, the prompt deadlocks.
- **Fix.** Delete the "confirm WP11 done" sentences. State that the files are owned by downstream WPs that cannot run in parallel (the tasks.md rule), so edits are allowed and logged.

**S7 — `MissingDoctrinePackError` and `OrgDoctrineSource` have no rename owner.**

- WP05 (`WP05:152`, T027 step 5) defers both to "WP19–WP21". Neither the WP20 R2 table nor WP21 names them.
- `MissingDoctrinePackError` is a public exception in `org_charter.__all__` that surfaces to operators.
- Neither name is an FR-018 token, so nothing would catch a miss.
- **Fix.** Add both to the WP20 table (`MissingDoctrinePackError` → for example `MissingCharterPackError`) and the WP21 R3 list (`OrgDoctrineSource` → `OrgCharterPackSource`). Record the new names for the owner's veto.

**S8 — Nobody removes the `.kittify/doctrine/**` path filter in `ci-router.yml`.**

- WP03 T018 step 3 (`WP03:164`) keeps the old filter "until WP11 T059 … then WP11 drops it".
- WP11 neither owns `.github/workflows/ci-router.yml` nor mentions it.
- The leftover filter is a forbidden FR-018 token on a living surface, so the WP25 gate would trip on it.
- **Fix.** Add a step to WP11 T059: drop `'.kittify/doctrine/**'` from `ci-router.yml` as a logged follow-up.

**S9 — WP08 invents consumer-visible CLI behaviour and JSON that the contract does not state.** The prompt writer chose all of the following:

- `--pack`, `--force` or `--json` without `--preset` exits 2.
- `--cascade` with `--preset` exits 2.
- The `charter pack list --json` shape: `{"packs":[{"name","tier","root","presets":[{"name","description","path"}]}]}` with tier values `built-in|org|project`.
- The `charter pack path --json` shape: `{"pack","path","preset"}`.
- The text error format `Error (<CODE>): <message>`.

The sources are `WP08:144-151,161-162,173`. `contracts/cli.md` names only `--preset` with a positional argument → 2, and the `activate` JSON.

**Fix.** Move these into `contracts/cli.md` (owner veto), so WP01's tests and WP24's runbook bind to them.

**S10 — WP07 invents consumer-visible pack-format names.**

- The example preset `starter` (`presets/starter.yaml`, scaffolded by `charter org init`).
- A new `presets:` key in `pack-manifest.yaml`, with `PresetEntry` `name`, `path` and `content_hash`.
- Validator issue categories `preset_format` and `preset_unresolved_id`, with `artifact_type: "preset"`.

The sources are `WP07:194,205`. None of these is in `data-model.md` or the contracts. **Fix.** Add them to `data-model.md` "Charter Pack" and `contracts/activation-preset.schema.yaml` for the owner's veto. The `presets:` manifest key also belongs in the WP24 "Pack authors" runbook section.

### NIT

- **N1 — The profile-load boilerplate names a skill that WP18 deletes.** Every WP header says "Use the `/ad-hoc-profile-load` skill". After WP18 that skill is deleted; only WP16, WP17 and WP19 carry a parenthetical. WP18 fixes the source template (`WP18:249`), but WP19–WP25 as generated still name it. Add the parenthetical to WP20–WP25, or regenerate those prompts after WP18.
- **N2 — Version mismatch.** WP10 says the cutover `target_version = "4.0.0rc7"` (`WP10:100`). WP11 uses `m_4_0_0rc6_…` and `4.0.0rc6`, which matches `pyproject.toml`. Align them.
- **N3 — Stale escalation in WP11.** WP11 T055 step 5 (`WP11:138`) tells the implementer to escalate the "stamped above the cutover version" wedge. WP10 T050 step 3 already implements version-independent selection. Drop it.
- **N4 — Stale start condition in WP04.** WP04 (`WP04:131`) says "tasks.md lists WP04 as depending on WP02 only". Both tasks.md and the frontmatter already list WP02 and WP03.
- **N5 — Old class name in WP06.** WP06 uses `CharterPackManager` throughout (T030, T033). WP17 renames it first, so use `ActiveCharterManager`.
- **N6 — WP08 calls two settled points "open".** WP08 T041 steps 4–5 treat the `mission_type_activations` omission and the customised-key rule as open, and say "FR-001 literally says 'removed'". FR-001 (`spec.md:134`) states both rules, and the recommendations match it. Cite the spec instead.
- **N7 — Wrong lane caution in WP19.** WP19 (`WP19:222`) says "WP08, WP09, WP13, WP15 and WP16 are not upstream". All are upstream through WP14 and WP16.
- **N8 — Wrong owner in WP25.** WP25 T113 says the cr02 compat gate was "deleted (WP14)". WP16 deletes it.
- **N9 — Misread occurrence-map entry for `doctrine-daphne.agent.yaml`.** WP15 (`:131`), WP16 (`:185`) and WP22 (T101) call the whole file `do_not_change` and "record a deviation". The map pins only `profile-id` and `name`, and says the rest follows the categories. Both WP16 and WP22 plan the same line-114 edit. Keep WP16's edit and drop the "deviation" language.
- **N10 — Retired-tier names kept by prompt choice, for the owner to acknowledge.**
  - The `doctrine` pytest marker (WP23 T106 step 4).
  - Doc page slugs `create-an-org-doctrine-pack.md`, `org-doctrine-layer.md` and `doctrine-kinds.md` (WP22: "do not rename doc page files").
  - Schema `$id` URLs `…/schemas/doctrine/…` (WP19 T094).
  - The `pytest.ini:87` corpus glob `.kittify/{…,doctrine}/**`, which no WP updates.
- **N11 — Casing of the glossary term.** The glossary term is **Charter Pack**. User strings in the prompts write "org charter packs" (WP15 T077 step 3), "internal charter pack" (WP22 `:330`) and "charter pack content" (WP05 T027). Pick one rule: lowercase in running prose is fine if the glossary says so, but record it in WP24.
- **N12 — Moves deviation.** The occurrence map moves `config.py` to `src/charter/activation`; WP05 folds it into `org_charter.py`. This is consistent with OD-9; note it in the map.
- **N13 — Changelog writers.**
  - WP14 (`WP14:94`) asks for a CHANGELOG Unreleased line for the gate. WP24 owns the changelog and FR-018's prefix rule. Defer the line to WP24.
  - WP24 T109 changes `doc_status` and `updated` frontmatter on the superseded runbooks, while the map says "banner only". This is acceptable, but say so in the map.

---

## 3. C-001, C-002, C-003 sweeps

**C-001 (no alias).** I checked every prompt for alias commands, hidden groups, re-exports, read fallbacks, warning stubs and redirect pages.

- Temporary layers that do get removed: the WP02/WP03 fallbacks (they do not; see B1), WP15's interim double registration (WP16 removes it), and WP08's "`apply` keeps working until WP13" (WP13 removes it).
- WP22 explicitly refuses redirect stubs for doc slugs.
- WP17 forbids pydantic `alias` and `populate_by_name`.
- WP13 and WP17 retired-field messages name a replacement, which C-001 allows.
- No hint or "did you mean" text was found (WP16 forbids it).
- Remaining items: B1 and S8.

**C-002 / C-004 (historical records and kept names).** No prompt edits another mission's `kitty-specs`, `docs/adr`, `docs/plans`, `docs/reports`, `.kittify/evidence`, `.kittify/migrations`, a released changelog section, or the archive.

- WP24 adds banners to the two superseded runbooks, which the occurrence map permits.
- WP24 also rewords existing **Unreleased** entries (#4836, #5538). Unreleased is not historical.
- `migration_id`s, migration class and module names, and `upgrade/metadata.py` are kept (WP10, WP21 T099).
- C-004 names are kept. WP16 changes only daphne line 114, a stale command, which the map's reason text allows.

**C-003 (pack tiers).** Nothing maintainer-only moves into `packs/built-in`; the only additions there are the consumer presets (WP07) and consumer prose and glossary entries (WP22, WP24). `packs/internal` receives only in-place command and prose fixes (WP15, WP22). Consumer guidance (the runbook) lives in `docs/migrations/`, not only in `packs/internal`. Every pack-editing WP regenerates the manifest. No findings.

## 4. Terminology

- "Mission" is used throughout. No "feature" appears in any prompt, apart from `plan.md:40` quoting the rule.
- The glossary nouns are consistent across prompts:
  - charter offering (WP19 `CharterOfferingService`, `offering_root`);
  - Charter Pack (WP21 `CharterPackHealthReport`, `charter_pack_synthesizer`);
  - activation preset;
  - active charter (WP17 `ActiveCharterManager`, WP20 `ActiveCharterService`);
  - project layer (WP21 `_fresh_project_layer`, WP22 table);
  - Charter Bundle (WP20 explicitly avoids `charter bundle` for the action bundle).
- "Charter Selection" is avoided (WP20 `GovernanceCharterConfig`).
- Only casing nits remain (N11).

## 5. Consumer messaging cross-check (WP24 T108 against what other WPs change)

| Changed by | Name | In WP24 list? |
|---|---|---|
| WP16 | `spec-kitty doctrine` group and 11 leaves | yes |
| WP13 | `charter pack apply` | yes |
| WP08 | `charter pack path <preset>` → `<pack> [--preset]` | yes |
| WP08 | `charter pack list --json` row shape | **no** (Added only) — S3 |
| WP08 | new usage-error rules on `charter activate` | no (new behaviour) — S9 |
| WP15 | `charter pack consistency-check` → `charter consistency-check` | yes |
| WP15 | `doctor doctrine` → `doctor charter-packs` | yes |
| WP15 | manifest `generated_by` | **no** — S3 |
| WP14 | tracker `--doctrine-mode`, `doctrine_mode` key | yes |
| WP17 | `doctor tool-surfaces --kind doctrine-skill` → `charter-skill` | **no** — S3 |
| WP17 | `ToolSurfaceKind` `doctrine_skill` → `charter_skill`, surface ids | **no** — S3 |
| WP17 | `CHARTER_PACK_CONFIG_INVALID` → `ACTIVE_CHARTER_CONFIG_INVALID` | yes |
| WP17 | `doctrine_pack_id` → `charter_pack_id`; org-charter `schema_version` 2 | yes |
| WP17 | Python `CharterPackManager` / `CharterPackConfigError` | not in Breaking (Python API; ADR treats it as internal); suggest one Internal line |
| WP18 | the 12 skill names | yes |
| WP10/WP18 | `spec-kitty-constitution-doctrine` retired | **no** — S4 |
| WP11 | config keys (`doctrine.org.*`, single-pack, `organisation_packs`, `governance.doctrine.*`, tracker `doctrine`, answers `doctrine:`) | yes |
| WP11 | `.kittify/doctrine/` → `.kittify/charter-packs/`; `.gitignore` rules | yes (Upgrade Notes) |
| WP13 | `accompanies_doctrine_pack` → `RETIRED_PACK_FIELD` | yes |
| WP07 | `src/charter/activation/packs/` → `packs/built-in/presets/` | yes |
| WP07 | manifest `presets:` key; `starter` scaffold | no (new; S10, Added) |
| WP09/WP08/WP14 | new codes `DEFAULT_PRESET_MISSING`, `PRESET_*`, `PACK_NOT_FOUND`, `LEGACY_CHARTER_STATE` | yes |
| WP03 | state surface `project_doctrine_graph` → `project_pack_graph` | **no** — S3 |
| WP11/WP12 | `upgrade --json` `migration_reports.charter_pack_cutover` payload | no (new; suggest Added) |
| WP15 | human strings "Active charter is coherent." / "No org charter packs configured." | no (minor; optional) |

The runbook (WP24 T109) covers operators, missions in flight (merge, never rebase), pack authors (field deletion, `charter_pack_id`, schema bump, presets) and saved scripts (the full command map). It inherits the S3 gaps through the "full command map from `contracts/cli.md`".

---

## 6. New consumer-visible names introduced by the prompts (owner veto list)

These are names not fixed in the ADR or spec, chosen by prompt writers, or fixed in the contracts and data model without an explicit owner ruling.

**CLI flags, tokens and behaviour**

- `charter pack path <pack> --preset <name>` (contract)
- `charter pack list` hidden `--repo-root` (WP08)
- `--pack`, `--force` or `--json` without `--preset` exits 2; `--cascade` with `--preset` exits 2 (WP08)
- `doctor tool-surfaces --kind charter-skill` (WP17)
- `tracker … --ownership-mode` as the stated replacement (already exists)

**JSON keys and values**

- `charter activate --json` returns `{pack, preset, written, removed, target_file}` (contract)
- `charter pack list --json` returns `{packs:[{name, tier, root, presets:[{name, description, path}]}]}` with `tier` ∈ `built-in|org|project` (WP08, WP07)
- `charter pack path --json` returns `{pack, path, preset}` (WP08)
- `ToolSurfaceKind` value `charter_skill` and surface-id segment `.charter_skill.` (WP17)
- `upgrade --json` `migration_reports.charter_pack_cutover` keys `moved`, `rewritten`, `reset`, `kept_for_review`, `matches_minimal`, `skills_removed`, `skills_kept`, `errors` (WP11)
- Validator issues `category: preset_format | preset_unresolved_id`, `artifact_type: preset` (WP07)
- State surface `project_pack_graph` (WP03)

**Error codes and messages**

- `ACTIVE_CHARTER_CONFIG_INVALID`, `LEGACY_CHARTER_STATE`, `DEFAULT_PRESET_MISSING`, `PRESET_NOT_FOUND`, `PACK_NOT_FOUND`, `PRESET_ID_UNRESOLVED`, `PRESET_WOULD_OVERWRITE`, `RETIRED_PACK_FIELD` (contracts)
- Text format `Error (<CODE>): <message>` (WP08, WP09)
- `LEGACY_CHARTER_STATE` finding names `legacy_project_root`, `unreadable_config`, … in the message (WP11/WP14)
- `RetiredPackFieldError` message `<path>: field '<field>' was removed. <replacement>. See docs/migrations/charter-pack-cutover.md.` (WP17)
- Human strings "Active charter is coherent." and "No org charter packs configured." (WP15); the new deactivate remedy text (WP06 T031 step 5); the resynthesis "Cannot resolve the effective … set" (WP06)

**Config, persisted keys and files**

- `charter_pack_id`; org-charter `schema_version: 2` (WP17)
- Answers key `charter:` (WP11)
- Auto-derived single-pack name (slug of the `local_path` basename, fallback `org`) (WP11)
- `presets/<name>.yaml`; built-in `default` and `minimal`; scaffolded `presets/starter.yaml` (WP07)
- `pack-manifest.yaml` `presets:` entries `{name, path, content_hash}` (WP07)
- `.kittify/charter-packs/`; manifest `generated_by: spec-kitty charter pack regenerate-graph`
- Runbook `docs/migrations/charter-pack-cutover.md`
- Retired skill `spec-kitty-constitution-doctrine` (WP10/WP18)

**Skill names**: `spk-charter-{governance, glossary, profile-load, spdd-reasons}`, `spk-practice-{bulk-edit, semantic-compression, show-me}` (ADR), plus the new family word `practice` in `spk-meta-skill-authoring` (WP18).

**Python facade and module exports**

- WP04/WP07: `charter.packs` facade with `validate_pack_with_org_charter`, `assemble_pack_with_org_charter`, `write_pack_manifest`, `pack_document_dict`, `ActivationPreset`, `PresetFormatError`, `PresetNotFoundError`, `OfferingPack`, `list_offering_packs`, `discover_presets`, `load_preset`, `load_preset_file`, `preset_activation_keys`, `PRESET_GOVERNED_KINDS`, `enumerate_presets`, `render_example_preset`, `EXAMPLE_PRESET_NAME`.
- WP04: `charter.drg` gains `CORE_KIND_PLURALS` and `resolve_relative_path_within_root`.
- WP04/WP05: `charter.offering.packs.{hashing, extends}`; `validate_org_charter_file`, `merge_org_charter_files`.
- WP06/WP08: `charter.activation.effective_set` (`EffectiveSet`, `resolve_effective_set`); `PromotionOutcome`; `charter.activation.preset_application` (`PresetPlan`, `plan_preset_application`, `apply_preset_plan`, `PackNotFoundError`, `PresetIdUnresolvedError`).
- WP02: `charter.activation.layer_roots`; `kernel.charter_pack_paths` (`PROJECT_PACK_DIRNAME`, `PROJECT_PACK_ROOT`, `project_pack_root`, `project_pack_path`, `pack_drg_fragment`, `pack_org_charter`, `pack_presets_dir`, …).
- WP13/WP17: `charter.offering.packs.retired_fields` (`RetiredField`, `RetiredPackFieldError`, `reject_retired_fields`, `RETIRED_PACK_FIELDS`).
- WP09: `DefaultPresetMissingError`, `default_preset_mission_types`.
- WP14: `require_canonical_governance`; `specify_cli.migration.legacy_charter_gate`.
- WP11: `specify_cli.migration.legacy_charter_layout`.
- WP17: `ActiveCharterManager`, `ActiveCharterConfigError`, `ToolSurfaceKind.CHARTER_SKILL`.
- WP19: `CharterOfferingService`, `BaseArtifactRepository`, `ArtifactLayerCollisionWarning`, `ArtifactLoadError`, `ArtifactResolutionCycleError`, `offering_package_dir`, parameter `offering_root`.
- WP20: `ActiveCharterService`, `build_active_charter_service`, module `active_charter_service_builder`, module `action_governance_bundle`, `_project_root_candidates`, `OfferingCatalog`, `load_offering_catalog`, `resolve_offering_root`, `GovernanceCharterConfig` (re-exported by `charter`), `pack_kind_subdir`.
- WP21: `CharterPackHealthReport`; packages `specify_cli.charter_pack_synthesizer` and `specify_cli.charter_packs`; `<noun>_service_factory`.
- S7 proposal: `MissingCharterPackError`, `OrgCharterPackSource` (not yet chosen).

**Contributor-facing (not shipped)**: `tests/charter_offering/` (WP23); renamed gate files (WP21 T099 step 3); `tests/charter/presets/`, `tests/charter/packs/`.

**Retired-tier names kept by prompt choice (acknowledge)**: the pytest marker `doctrine`; doc slugs `create-an-org-doctrine-pack.md`, `org-doctrine-layer.md`, `doctrine-kinds.md`; schema `$id` `…/schemas/doctrine/…`; the persisted key `propose_doctrine_changes`; `doctrine_snapshot` (conditional, WP20).
