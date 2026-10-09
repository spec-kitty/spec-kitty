# Post-tasks adversarial review: anti-laziness / non-vacuity

Reviewer: reviewer-renata, using tactic `acceptance-criteria-non-vacuity`. Read-only, except for this file.
Base: branch `issue-3732-charter-pack-rename`, HEAD `051d5a55`.
Read: `spec.md`, `plan.md`, `tasks.md`, `data-model.md`, `contracts/*`, `occurrence_map.yaml`, `decisions/DM-*`, `research/postspec-squad-testability.md` and all 25 `tasks/WP*.md`. I also checked the code at HEAD where a finding depends on it.

Line numbers refer to the files at HEAD. `WP01:<n>` means `tasks/WP01-acceptance-suite.md` line `<n>`.

**Counts: 9 BLOCKER, 17 SHOULD-FIX, 7 NIT.**

---

## A. BLOCKERS

### B1. FR-010 identifier renames (R1–R4) have no acceptance test; WP19, WP20 and WP22 have nothing to flip
- **Evidence.**
  - The WP01 flip map (`WP01:105-128`) gives nothing to WP19, WP20 or WP22.
  - FR-010 coverage is limited to these tests:
    - the package split tests (WP04/WP05);
    - `test_fr010_no_src_module_named_for_retired_tier`, which checks path segments only (WP21);
    - `test_fr010_tests_doctrine_directory_renamed` (WP23);
    - `test_fr010_charter_pack_id_in_project_state`.
  - Even so, `WP19:193,240-243` and `WP20:193,246-249` require "WP01 acceptance tests marked `pending_until("WP19"/"WP20")` … go red → green". They cite, as examples, tests that do not exist: "the R1 names no longer importable", "no `DoctrineService` anywhere", "`doctrine_service_builder` not importable".
  - The FR-018 closed token list (`spec.md:181`) does not include `DoctrineService`, `doctrine_service_builder`, `DoctrineCatalog`, `BaseDoctrineRepository`, `DoctrineSelectionConfig`, `doctrine_root` or any other R1/R2 identifier. No gate therefore catches a skipped rename.
- **Consequence.** WP19, WP20 and WP22 can each meet their Definition of Done (DoD) with zero renames. Their red-first step is an empty grep.
- **Fix in `WP01-acceptance-suite.md` T008.** Freeze the R1/R2/R3/R4 rename tables (WP19:197-207, WP20:197-217, WP21's table) into `tests/fixtures/charter_pack_cutover/rename_tables.yaml`, with old name, new name, defining module and slice. Then add these tests to `test_package_split.py`:
  - `test_fr010_r1_identifiers_renamed`, pending WP19;
  - `test_fr010_r2_identifiers_renamed`, pending WP20, with the three module paths not importable;
  - `test_fr010_r3_r4_identifiers_renamed`, pending WP21.

  Each test AST-scans `src/` for every "old" name: no definition, no import binding, no attribute access. It also imports every "new" name as the positive control. It has a planted-positive check on a tmp module.
- **Fix for WP22.** Add `test_fr010_living_prose_tokens[packs|docs|AGENTS.md]`, pending WP22. It runs the FR-018 token list over `packs/` and living `docs/` only.
- **Fix in `tasks.md`.** Add the new rows to the flip map.

### B2. `test_fr010_charter_pack_id_in_project_state` is assigned to WP17, but the behaviour arrives in WP11, which depends on WP17
- **Evidence.**
  - `WP01:123` assigns the test to WP17. `WP01:293` defines it as "after upgrade of `doctrine_pack_id_activations`, `charter.yaml` uses `charter_pack_id`".
  - The rewrite is WP11 T057. WP11 depends on WP17 (`WP11` frontmatter `dependencies: ["WP03","WP10","WP17"]`), so WP17 cannot turn the test green.
  - `WP17:164` says "WP11 (T057) migrates project `charter.yaml` … Confirm both are done before starting". That precondition cannot hold.
  - `WP11:173` asserts the reverse order ("WP17 … which depends on this WP").
  - The test also duplicates `test_fr012_doctrine_pack_id_renamed` (WP11).
- **Fix.**
  - `WP01:123,293`: retag `test_fr010_charter_pack_id_in_project_state` as `pending_until("WP11")`, or delete it as a duplicate of `test_fr012_doctrine_pack_id_renamed`.
  - Give WP17 the model-level half instead: a `charter.yaml` hand-written with `charter_pack_id` loads through `charter list --json`, and the same file with `doctrine_pack_id` fails with `RETIRED_PACK_FIELD`.
  - `WP17:164`: drop "WP11 … confirm done".
  - `WP11:173`: fix the stated order.

### B3. Two tests are assigned to WPs that run before `charter pack validate` exists
- **Evidence.**
  - `test_fr019_validate_names_malformed_file_and_unresolved_id` (`WP01:219`, WP07) and `test_us3_4_accompanies_field_rejected` (`WP01:263`, WP13) both invoke `charter pack validate <dir>`.
  - That command is created by WP15 T076. WP07 depends on WP05 and WP06; WP13 depends on WP08, WP09 and WP12. Neither depends on WP15, and WP15 depends on WP13.
  - WP07 knows the command is missing: its own review step uses `spec-kitty doctrine pack validate` (`WP07:275`). Yet its objective says "`charter pack validate` … validate presets" (`WP07:87`).
- **Fix in `WP01-acceptance-suite.md`.** Choose one:
  - (a) Keep the CLI tests and retag both to `pending_until("WP15")`. Add WP-local `validate_pack(...)`-level tests (the shared validator entry) pending WP07 and WP13 respectively, plus `charter org validate` rows, which exist at base, for the CLI half.
  - (b) Make both tests parametrised over the spelling that exists at the time (`doctrine pack validate` before WP15, `charter pack validate` after it). Option (a) is cleaner and keeps C-001.
- **Fix in WP07.** Correct objective line 87.

### B4. `test_fr003_init_without_activation_equals_default_preset` (WP09) needs `charter activate --preset` (WP08), and WP09 does not depend on WP08
- **Evidence.**
  - `WP01:216` compares `init` with "what `--preset default` writes on a second fresh project".
  - WP09 depends on WP07 only. tasks.md:492 runs WP09 beside WP08.
  - WP09 admits the gap: "If WP08 has landed in your lane base, also run `charter activate --preset default` …; if not, the acceptance suite covers it" (`WP09:159`). The acceptance suite is exactly the test that cannot pass.
- **Fix.** Choose one:
  - (a) Rewrite the test (`WP01:216`) to derive the expected state from the preset file through the test's own reader: no `activated_*`, no `activated_kinds`, and `mission_type_activations` equal to the preset's list. Then add a separate `test_fr003_init_equals_activate_default` pending WP08 or later.
  - (b) Add WP08 to WP09's dependencies (`tasks.md:276`, WP09 frontmatter).

### B5. The FR-015 "upgrade" caller row (WP06) cannot go green before WP10 neutralises the normalizer
- **Evidence.**
  - `WP01:278` drives `m_unify_charter_activation` through `spec-kitty upgrade` on a fixture "stamped below 3.2.6rc1 with `answers.yaml` selections" and with every key absent.
  - In the same run, `m_3_2_x_normalize_activation_absence` (`TARGET_VERSION = "3.2.6rc1"`, `src/specify_cli/upgrade/migrations/m_3_2_x_normalize_activation_absence.py:125`) writes `[]` for every absent per-artifact key. Its bare-config deferral (`:278-290`) does not apply when an answers-only promotion is pending, which is exactly this fixture.
  - The effective set therefore narrows whatever the seam does. Only WP10 T051 neutralises the normalizer, and WP06 depends on WP05 and WP17, not WP10.
  - `WP06:174` assumes "run-first ordering (WP10/WP11) means this migration now sees canonical state". That holds only if WP10 is upstream.
- **Fix.** Choose one:
  - Add WP10 to WP06's dependencies (`tasks.md:243`, `tasks.md:461`, WP06 frontmatter). WP10 depends only on WP01, so this costs no parallelism beyond WP10 itself.
  - Retag that one parametrised row `pytest.param(..., marks=pending_until("WP10"))`. This is weaker: the row would then prove nothing about WP06's seam.

### B6. `test_fr012_installed_removed_skills` (WP12) runs through `spec-kitty upgrade`, but the removed names are still shipped skills until WP18
- **Evidence.**
  - `WP01:240` and the flip map (`WP01:117`) give it to WP12.
  - WP12 itself says: "until WP18 lands, the upgrade finalizer's surface repair would reinstall these skills from the catalog; test the migration step directly, not through a full `spec-kitty upgrade`" (`WP12:166`).
  - WP18 depends on WP12, so the reinstall happens on every WP12 run. The CLI test cannot go green there.
  - "new names installed" also needs the WP18 sources.
- **Fix in `WP01:117,240`.** Retag the test `pending_until("WP18")`, next to `test_fr008_upgrade_installs_new_and_removes_old`. WP12 keeps its unit-level `test_charter_pack_cutover_skills.py`. Also record in the Activity Log template that WP12's `REMOVED_SKILL_NAMES` and WP18's retired list must be the same constant (see S15).

### B7. The strict `raises=(AssertionError, ImportError)` turns many specified tests into FAILED rather than XFAILED at base, so WP01's own DoD cannot be met
- **Evidence.**
  - `pending_until` restricts `raises` (`WP01:141`). Several test bodies, as specified, raise something else at base:
    - Reading `packs/built-in/presets/{default,minimal}.yaml` (`WP01:207,214`) and the `default` preset in `test_us2_6_*` (`WP01:243`) raises `FileNotFoundError`.
    - `ToolSurfaceKind.CHARTER_SKILL.value` (`WP01:292`) raises `AttributeError`.
    - The NFR-002 rows read gate attributes that later WPs delete or rename (`WP01:307`), which raises `AttributeError`.
    - Gate modules are loaded with `spec_from_file_location` on a file that does not exist yet (`WP01:306,309,313`). `exec_module` raises `FileNotFoundError`, not `ImportError`. T009's checklist claims "a missing gate is an `ImportError` xfail" (`WP01:313`), which is false.
    - JSON key lookups on error output raise `KeyError`.
  - Each of these is FAILED, against the DoD at `WP01:82,361` ("0 failed").
  - The implementer will then either widen `raises` (losing the harness-error protection) or quietly restructure the tests.
- **Fix in `WP01-acceptance-suite.md` T001.** Add `_support` helpers that turn "behaviour absent" into `AssertionError` with a message naming the missing behaviour, and require tests to use them:
  - `require_file(path)`
  - `require_attr(obj, name)`
  - `load_module_by_path(path)`, which asserts the path exists first and then imports
  - `require_key(mapping, key)`

  Keep `raises=(AssertionError, ImportError)`. Then add a T010 self-test that runs the suite at base in a subprocess and asserts 0 failed. At WP01 time this is simply the WP01 DoD run.

### B8. Several tests pass at base without the behaviour (XPASS, so strict-fail at WP01), and they are vacuous as specified
Each test below needs a same-fixture positive control that is red at base.
- **`test_fr011_exempt_invocations` (`WP01:265`, WP14).** `upgrade`, `init`, `--version` and `--help` all run on a legacy fixture at base, because there is no gate yet.
  - Fix: in the same test, on the same fixture copy, assert that one non-exempt command (`charter list`) exits 1 with `LEGACY_CHARTER_STATE`.
- **`test_fr001_preset_with_positional_kind_exits_2` (`WP01:213`, WP08).** `--preset` is an unknown option at base, so the command already exits 2.
  - Fix: assert the usage error names the mutual exclusion, not "No such option". Also assert that `--preset minimal` alone exits 0 on the same fixture.
- **`test_nfr003_preset_and_pack_list_latency` (`WP01:308`, WP08).** A command that fails fast at base is also fast, and `charter pack list` already exists.
  - Fix: assert `exit_code == 0` for every timed run. Assert the `pack list` output contains both org packs and that `activate --preset` wrote the keys, before comparing medians.
- **`test_us2_7_lane_in_approved_consolidates_after_root_upgrade` (`WP01:243`, WP12).** At base the upgrade moves nothing and `consolidate` succeeds anyway.
  - Fix: assert first that the root upgrade produced `.kittify/charter-packs/` and a commit that moves `.kittify/doctrine/**`. Assert that the merged lane carries that commit. Only then assert that `consolidate` exits 0 with no `LANE_MOVED_AFTER_APPROVAL`.
- **`test_fr012_user_path_values_untouched` (`WP01:237`, WP11).** It passes at base if the fixture's value sits under a canonical key.
  - Fix in `WP01:176`: build `user_path_value_with_doctrine` with the legacy key (`doctrine.org.local_path: packs/doctrine-foo`). Assert that the canonical key is present and its value byte-identical.
- **`test_fr012_near_miss_and_customised_kept_and_reported` and `test_fr015_unresolvable_set_*`.** The "kept" and "absent" halves already hold at base. Only the "reported" half is red.
  - Fix: require the report or warning assertion explicitly, in the same test (see also S9).

### B9. NFR-001's expected relation is undefined for several fixtures, and as written the test fails on them
- **Evidence.**
  - `WP01:241` encodes "non-stale fixtures `after == before`; stale fixtures `after == before ∪ builtin_inventory()`". "Stale" is never defined per fixture.
  - These NFR-001 fixtures grow legitimately without being stale lists:
    - `minimal_equal`: the kind gate is removed (DM-01M497F0…), so the six gated kinds open up.
    - `normalizer_empty_lists`: `[]` becomes absent (DM-01M497EW…).
    - `pre_rc35`: "equals the `default` preset's" (US2-6).
    - the stale 8-kind gate inside `stale_*`.
  - Strict equality fails on these. The only sanctioned escape is `WP01:200`: "drop it from `NFR001_FIXTURES`". Dropping the fixture removes the very cases the owner ruled on.
- **Fix in `WP01-acceptance-suite.md` T002/T003/T005.**
  - Add `EXPECTED_RELATION: dict[str, Relation]` to `legacy_fixtures.py`. It is closed: one entry per `NFR001_FIXTURES` name, and the test asserts the key sets are equal. Each entry is `EQUAL`, or `GROWS(kinds=…)` meaning `after[k] == before[k] ∪ builtin_now[k]` for the listed kinds and equality elsewhere.
  - Derive each entry from the FR-012 inventory row it exercises, cited in a comment.
  - Replace the "drop it" escape at `WP01:200` with "stop and escalate to the orchestrator". Assert `set(NFR001_FIXTURES) ⊇` the spec NFR-001 list (`spec.md:191`), as named builders.

---

## B. SHOULD-FIX

### S1. The effective-set helper cannot see `activated_kinds`, so the golden "before" does not measure the kind gate (NFR-001 soundness)
- **Evidence.**
  - `_effective_set.py` takes the mapping keys of `build_activation_aware_doctrine_service` (`WP01:186`).
  - The activation-aware resolver does not apply the kind gate. `PackContext.activated_kinds` is consumed only by `charter/activation/drg_activation.py:423`, and a grep over `src/` finds no other consumer.
  - The `[directives, tactics]` gate and the stale 8-kind gate are therefore invisible in both "before" and "after". The NFR-001 superset or equality says nothing about the two DM-ruled resets.
- **Fix in `WP01:186`.** The spec's definition ("one helper over the activation-aware service …") is incomplete here. The helper must also apply `PackContext.from_config(repo).activated_kinds`: a kind outside the gate gets an empty set. Then add a generator-time positive control in `test_golden_before.py`: in `minimal_equal`'s golden, every gated-out kind is empty, and in `legacy_keys_only` it is not. Record the spec gap for the orchestrator. The NFR-001 text should name `activated_kinds`.

### S2. Golden sets for absent-key fixtures embed the base built-in inventory, so `after == before` breaks on any built-in change between base and closeout
- **Evidence.** Most NFR-001 fixtures leave keys absent: `legacy_keys_only`, `legacy_directory_only`, `two_org_packs`, `governance_doctrine_in_charter_yaml` and others. Their "before" set is "every built-in artifact at base". A rebase onto `main` that adds or removes one built-in artifact makes `after == before` red, and that has nothing to do with the cutover.
- **Fix in `WP01` T003/T005.**
  - Freeze `builtin_at_base` per kind in `golden_before/_meta.json`.
  - For kinds whose key is absent in the fixture, assert `after[k] == (before[k] − builtin_at_base[k]) ∪ builtin_now[k]`. For listed kinds, assert strict equality. Only built-in ids are allowed to vary.
  - Also assert `before[k] − builtin_at_base[k] ⊆ after[k]`, so no org or project artifact is ever lost.

### S3. `_effective_set.py`, the measurement instrument, is not digest-pinned, and later WPs are told to edit it
- **Evidence.** Only the generator file is pinned (`WP01:195`). WP19 and WP20 must "update its imports mechanically" (`WP01:186`). A semantic edit to the helper could align "after" with "before" by construction.
- **Fix in `WP01` T003.** Pin a digest of `_effective_set.py`'s AST with `Import` and `ImportFrom` nodes stripped and names normalised through a frozen rename table, so only import and rename churn is allowed. Cross-check with the golden `charter_list` rows in every NFR-001 assertion. `WP01:241` says "`charter list --json` agrees"; make that a hard assertion per kind, not advisory.

### S4. SC-004 recorded outputs can be vacuous, and some recorded key lines conflict with renames other WPs are told to make
- **Evidence.**
  - Nothing requires the recorded `exit_code == 0` or a non-empty `key_lines` (`WP01:191`). A leaf recorded as failing at base (for example `doctrine fetch` without a source) would make the "replacement matches" test vacuous.
  - Unmarked rows (`charter new`, `WP01:257`) record a path under `.kittify/doctrine/`. WP03 deliberately changes that output (`WP03` T017 step 6), so WP03 would turn an unmarked WP01 test red.
  - WP15 changes "Charter pack is coherent." to "Active charter is coherent." (`WP15:174`) and "No org doctrine configured." to "No org charter packs configured."
- **Fix in `WP01` T003/T006.**
  - In `test_golden_before.py`, assert every recorded leaf has `exit_code == 0` and at least one key line.
  - Prefer `--json` key sets for `key_patterns` wherever the leaf supports `--json`.
  - Normalise the project-pack root (`.kittify/doctrine` and `.kittify/charter-packs` both become `<project-pack-root>`).
  - Exclude, with a comment, the human strings that FR-009 or FR-006 rename on purpose.

### S5. `test_fr005_no_default_yaml_reader_outside_migration_data` will flag the legitimate preset reader
- **Evidence.** The scan is a text scan for `default.yaml` (`WP01:262`). WP09 T046 builds `pack_presets_dir(built_in_root()) / "default.yaml"` (`WP09:118`). WP13 would then face a test it cannot pass without editing WP09's code or "interpreting" the test.
- **Fix in `WP01:262`.** Scan for the retired surfaces: the path segment `activation/packs`, the module `charter.activation.default_pack`, `charter_pack_registry` and `merge_pack_into_config`. Keep a planted-positive control: a tmp module that imports `charter.activation.default_pack` is flagged, and one that reads `presets/default.yaml` is not.

### S6. Spec items with no WP01 test (C-006 says "every FR")
Add a test, with a positive control, for each item below. Owner WP in brackets.
- **FR-001 [WP08]:**
  - `--json` payload shape `{"pack","preset","written","removed","target_file"}` (`contracts/cli.md:346`).
  - A preset without `mission_type_activations` leaves the key byte-identical (FR-001 text).
  - `activated_skills` and `activated_glossary_packs` are untouched. The fixture must carry both.
  - Write target = pointed `charter.yaml` when the `charter:` pointer exists.
  - `PRESET_ID_UNRESOLVED` (Edge Case "Preset id resolution"; nothing written) and `PACK_NOT_FOUND`.
  - The flag rules WP08 delegates to "the acceptance tests" (`WP08` T041 steps 4-5, T042 step 2). The tests are silent on them, so the open points get decided ad hoc.
  - `--compile`/`--resynthesize` carry over (at least `--no-compile` accepted).
- **FR-003 [WP09]:** missing `default` preset gives `init` exit 1 with `DEFAULT_PRESET_MISSING` and no `mission_type_activations` written (spec: "fail-closed when the preset is missing").
- **FR-011 [WP14]:** `PackContext.from_config` stays total on a legacy-only config: no raise, empty org registry.
- **OD-6 [WP08]:** the applied preset's name is **not** persisted. Assert the whole `config.yaml`/`charter.yaml` key set gains nothing beyond the governed keys. `active_charter()` reads only governed keys, so it cannot see this.
- **FR-013 [WP24]:**
  - Doctrine Pack, Doctrine Pack ID, Doctrine Catalog and Charter Selection are retired or redirected.
  - The `charter` entry's "Do NOT use when" is rewritten.
  - The "active" guard is amended.

  `WP01:295` tests only the definitions and the ADR citation.
- **FR-017 / Edge Case "saved script" [WP24]:** the runbook names the replacement for each `contracts/cli.md` row, parsed. Today `WP01:310` checks only existence and `spec-kitty upgrade`.
- **FR-019 [WP07]:** each malformed case is named:
  - name grammar violation;
  - `name` ≠ stem;
  - `activated_kinds` omits a listed kind;
  - context-scoped `activations:` list;
  - `activated_skills` key.

  Also: the schema's kind enum equals the `ArtifactKind`-derived set. Today `WP01:219` covers only "unknown key" and "unknown id".
- **FR-008 [WP18]:** a pre-2.1.2 fixture upgrades with 0 errors after the skill sources are deleted ("historical skill migrations that read deleted sources neutralised"). No current fixture is older than 3.2.0rc30.
- **OD-1 [WP17]:** an `org-charter.yaml` scaffolded by `charter org init` carries `schema_version: 2`.

### S7. The traceability closed list omits FR-012 inventory rows, edge cases, ODs, DMs and constraints
- **Evidence.** `REQUIRED_IDS` (`WP01:321`) holds only FR, NFR, SC and US ids. FR-012 inventory coverage is a "comment table" (`WP01:251`), which is not machine-checked. Edge cases (`spec.md:114-126`), OD-1..OD-9, both DMs and C-001/C-004/C-007 have no id at all.
- **Fix in `WP01` T010.**
  - Parse the inventory table rows as `INV-01..INV-18` and the edge-case bullets as `EC-01..EC-13` from `spec.md`.
  - Add `OD-1..OD-9` (OD-10 is process) and `DM-01M497EW60HNWWJQCXDFA99R0H` and `DM-01M497F0NAQARAK3JZFVWF1SD0` as literal ids.
  - Extend the `covers` regex to accept them and add them to `REQUIRED_IDS`.
  - Optional: assert that each `pending_until("WPnn")` test's `covers` ids appear in WPnn's `requirement_refs`. This cheap check would have caught B2 and B3.

### S8. The FR-015 fail-closed test can be satisfied by a crash
- **Evidence.** `WP01:279` breaks the org pack with a dangling `local_path`. At base and later, that hard-fails before any promotion (`tests/integration/test_org_pack_missing_path_hard_fails.py`). "Key stays absent, output names it" is then true for the wrong reason.
- **Fix in `WP01:279`.** Use an unresolvable effective set that the CLI tolerates: a malformed artifact in org pack #2 that makes the service build raise, or `charter_packs.org.packs` naming an unfetched pack. Assert:
  - exit 0, or the documented warning exit;
  - a warning naming the key and the reason;
  - a different, resolvable key promoted in the same run, as the partial-success control.

### S9. The NFR-002 rows check one exemption structure per gate; the others can absorb violations
- **Evidence.**
  - `WP01:307` checks census `EXEMPT_MANAGEMENT_SURFACE` and boundary `_EXEMPT_SUBPACKAGE` only.
  - The census gate also has `TICKETED_BASELINE`, `DISPOSITION` and `ORPHAN_REACHED_EXCEPTIONS` (`tests/architectural/test_doctrine_census.py:102,116,183`).
  - The boundary gate has `_LAZY_BASELINE_ALLOWLIST` and `_LAUNDERING_BASELINE` (`test_runtime_charter_doctrine_boundary.py:113,155`).
  - The guidance gate has `_EXCLUDED_PREFIXES` (`test_no_deprecated_doctrine_command_in_guidance.py:47`), which WP16 widens (`WP16:197`).
  - Checking "`_EXEMPT_SUBPACKAGE` gone" by attribute absence is passed by renaming the attribute.
- **Fix in `WP01` T009.**
  - Freeze each gate's exemption structures and sizes at base in `tests/fixtures/charter_pack_cutover/nfr002_base.json`.
  - The rows assert every structure is empty, or no larger than at base and containing no `doctrine`-package path.
  - The guidance gate's exclusion prefixes must be ⊆ the spec's historical roots plus the cutover module.
  - Add one mutation check per gate: plant a violation in a tmp copy and the gate's scan function reports it.

### S10. The FR-018 floor and token list must come from WP01, not from the gate under test
- **Evidence.**
  - WP25 computes `_FILE_FLOOR` "by applying the gate's own scope function" to the base tree (`WP25:112`). A narrow scope gives a narrow floor, which is circular.
  - The spec says the floor is "recorded at base" (`spec.md:151`), yet WP01 records none.
  - `test_fr018_planted_token_detected` (`WP01:309`) does not say where its token list comes from. If it imports the gate's tuple, a token missing from that tuple is never planted.
- **Fix in `WP01` T009.**
  - Hard-code the spec's closed token list in `_requirements.py`, checked against `spec.md:181` by parsing.
  - Hard-code the living-roots list from `spec.md:185`.
  - At base, count tracked text files per living root (`git ls-files` over the spec roots minus the spec historical roots) into `fr018_floor.json` with the base SHA.
  - The test asserts the gate's scanned set ⊇ every root, its count ≥ the floor minus the files the mission deleted, and its tuple == the WP01 list.

### S11. WP25 escalates registries that the spec already exempts by name
- **Evidence.** `WP25:117` says the closed lists "do not cover" `retired.py`, the `RETIRED_PACK_FIELD` validator, the predicate module, older skill migrations and `metadata.py`, and orders "stop and escalate". The spec does exempt them:
  - `spec.md:182`: the cutover modules, `_charter_pack_cutover_*` helpers and the legacy-state predicate module, by file;
  - `spec.md:183`: the tombstone files `retired.py`, `retired_fields.py`, `metadata.py` and every pre-existing `m_*.py`.

  WP25's historical-root step (`WP25` T111 step 3) omits these as well.
- **Fix in `WP25-vocabulary-gate-and-closeout.md` T111 steps 3 and 5.** Copy the spec's tombstone and helper by-file exemptions verbatim, each with its reason. Keep "escalate" only for hits outside those files. WP01's `test_fr018_*` should assert the gate's exemption set equals that spec list (from S10).

### S12. NFR-004's non-vacuity control is satisfied by an unrelated restamp
- **Evidence.** "First upgrade changes `tree_digest`" (`WP01:242`) is met by the `metadata.yaml` version restamp on any fixture. On non-legacy NFR-001 fixtures (`customised_lists`, `two_org_packs` with canonical keys), the cutover migration has nothing to do.
- **Fix in `WP01:242`.** For fixtures that hold legacy state, assert the migration's report (`migration_reports["charter_pack_cutover"]`, `--json`) has at least one moved/rewritten/reset line on run 1. For the others, assert `detect()` is False before run 1 and say so in `EXPECTED_RELATION` (B9).

### S13. The Windows edge case is verified only by a test that never runs in any WP's local loop
- **Evidence.**
  - `test_fr012_windows_locked_file_refuses` is `windows_ci` (`WP01:238`), and `tests/conftest.py:343` auto-skips it off win32. WP11 therefore cannot show it red-first.
  - The suite's "no skip" rule (`WP01:150`) is contradicted.
  - WP11 adds a POSIX simulation only at unit level (`WP11` T058 note).
- **Fix in `WP01` T005.** Add a POSIX twin through the CLI: monkeypatch the move primitive WP11 will route through (`specify_cli.asset_preservation` copy/guard), or `os.replace`, to raise `PermissionError` for one path. Assert exit ≠ 0, the path named, already-moved files listed, and a clean finish on re-run. Keep the `windows_ci` case as the native check.

### S14. The exception set of `test_fr010_no_src_module_named_for_retired_tier` is undefined
- **Evidence.**
  - `WP01:293` says "except the kept migration ids listed in the occurrence map". `occurrence_map.yaml:82-85` exempts only the `migration_id` *field* of `m_*.py`, not file names. An implementer may exempt `src/specify_cli/upgrade/migrations/**` wholesale.
  - `spec-kitty-charter-doctrine/references/doctrine-artifact-structure.md` may legitimately be kept by WP18 (`WP18` T088 step 2: "rename … only if tier sense"), and it would fail the test.
- **Fix in `WP01:293`.** Use a closed literal exception set: `src/specify_cli/upgrade/migrations/m_2_1_2_fix_charter_doctrine_skill.py` and `src/specify_cli/upgrade/migrations/m_4_0_0rc5_retire_single_owner_doctrine_ids.py`. Any addition needs an owner ruling. Tell WP18 to rename the reference file.

### S15. The removed-skill list is defined twice and the copies already disagree
- **Evidence.**
  - WP12 hard-codes `REMOVED_SKILL_NAMES` with 12 names (`WP12` T063 step 1).
  - WP18 adds 12 names plus `spec-kitty-constitution-doctrine` to `RETIRED_CANONICAL_SKILL_NAMES` (`WP18` objectives).
  - WP18's review asks for "exactly the twelve" (`WP18:323`).
- **Fix.**
  - WP01 adds `test_fr008_migration_and_retired_lists_agree` (pending WP18). It asserts the migration's removal set equals `RETIRED_CANONICAL_SKILL_NAMES` ∩ FR-008 names, plus `spec-kitty-constitution-doctrine` handled per the WP10 note.
  - WP18 line 323: say "the twelve FR-008 names plus `spec-kitty-constitution-doctrine`".

### S16. WP10 edits a WP09-owned file in a parallel lane
- **Evidence.** `WP10:96` deletes a test in `tests/specify_cli/cli/commands/test_init_provisioning.py` (owned by WP09, "parallel lane"). tasks.md:11 forbids exactly this ("Never edit a file owned by a WP that can run in a parallel lane").
- **Fix.** Move that deletion to WP09 (WP09 can delete the rc35 identity test because WP10's neutralisation makes it obsolete), or make WP10 a dependency of WP09. The same check applies to WP09 and WP10 both touching `upgrade.py`-adjacent tests.

### S17. "Drop the fixture" and "stop and raise" clauses let a WP finish with an acceptance test silently out of scope
- **Evidence.**
  - `WP01:200` ("drop it from `NFR001_FIXTURES`").
  - `WP01:130` ("keep the closest WP … record the mismatch").
  - `WP21:197` ("If a WP21 test passes immediately, stop … ask the reviewer").
  - WP08's open points ("implement the recommendation, record it").
- **Fix.** Fix the known mismatches now (B2–B6, B8). Replace "record and continue" with "the WP cannot be approved while a mismatch is open" in each WP's Review Guidance (WP01, WP08, WP21).

---

## C. NITs

- **N1.** `WP04:131` says tasks.md lists WP04 as depending on WP02 only and asks the orchestrator to add WP03. The frontmatter and tasks.md:216 already include WP03. Delete the paragraph.
- **N2.** `WP10:100,221` say the cutover `target_version` is `4.0.0rc7`, while WP11 uses `m_4_0_0rc6_…` / `4.0.0rc6`. Pick one.
- **N3.** `WP25:155` says `test_lifted_cli_doctrine_charter_cr02_compat.py` is "deleted (WP14)". WP16 deletes it (`WP16` T082 step 3; flip map `WP01:120`).
- **N4.** `WP01:197` Test 2 uses cwd-relative `Path("src/kernel/doctrine_root.py")` and omits the `specify_cli.doctrine` condition the predicate checks. Anchor it to the repo root and mirror all three conditions.
- **N5.** `WP01:296` (FR-014): deleting every pin passes. Require the `Deleted pins (FR-014)` section to list each pin from the base inventory, frozen at WP01, either re-asserted or deleted, so the count is checked.
- **N6.** `WP01:214`: "`default` lists the built-in mission types". Compare against `builtin_mission_type_id_set()` read at test time, not a literal.
- **N7.** `WP01:310` checks `.kittify/doctrine/` and `accompanies_doctrine_pack` by literal. Derive the config-key and directory rows from the spec FR-012 inventory table, so the changelog check grows with the spec.

---

## D. Golden "before" generator (NFR-001) verdict

The generator's structure is sound:
- refusal after cutover;
- base SHA plus ancestry check;
- generator digest;
- fixtures built under `tmp_path`;
- the frozen synthesized tree;
- cross-check data from `charter list --json`.

It does **not** yet measure the effective set as NFR-001 defines it, for three reasons:
1. The kind gate is invisible (S1).
2. The per-fixture expected relation is undefined (B9).
3. The built-in inventory is baked into "before" (S2).

The measuring helper is also unpinned (S3), and the fixture list can shrink through the "drop it" clause (B9/S17).

With S1–S3 and B9 applied, the comparison becomes:
- per kind;
- gate-aware;
- invariant to built-in inventory drift;
- unable to lose an org or project artifact.

That is what NFR-001 and SC-002 require.

## E. Red-first feasibility summary

| WP | Can its WP01 tests be red on base and green at the WP? |
|---|---|
| WP02, WP03, WP04, WP05, WP10, WP15, WP16, WP23, WP24 | Yes, once B7's helpers are used. |
| WP06 | No for the upgrade row (B5). |
| WP07 | No for `test_fr019_validate…` (B3). |
| WP08 | Positional-kind and latency tests XPASS (B8). |
| WP09 | No for the `init`-vs-preset equivalence (B4). |
| WP11 | User-path test XPASS (B8). Windows test is skipped locally (S13). |
| WP12 | No for the installed-skills row (B6). US2-7 XPASS (B8). NFR-001 rows fail as specified (B9). |
| WP13 | No for `test_us3_4_accompanies_field_rejected` (B3). |
| WP14 | Exempt-invocations test XPASS (B8). |
| WP17 | No for `test_fr010_charter_pack_id_in_project_state` (B2). |
| WP18 | Yes (gains B6's test). |
| WP19, WP20, WP22 | Nothing to flip (B1). |
| WP21 | Yes, but path-only (B1, S14). |
| WP25 | Yes, but the floor is circular (S10). |
