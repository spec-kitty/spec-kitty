# WP12 review feedback, cycle 1 (reviewer-renata)

Verdict: **changes requested.** One architectural gate is red because of WP12, and one test-design defect will break at WP18. Everything else is sound:

- **Snapshot fidelity.** I regenerated the snapshot module independently from `research/default-yaml-snapshots.yaml` (sha256 `a007f1ef…`). Every `default` and `minimal` key has exactly the same distinct sets: agent_profiles 15/16/18, directives 19, mission_step_contracts 17, paradigms 8, procedures 13, styleguides 8/9, tactics 97/95/94, toolguides 10/9/12, minimal directives 5, minimal tactics 2/1. Both kind gates are equal. No minimal set overlaps a default set. `DIRECTIVE_ID_TO_STEM` covers all 19 numbered stems.
- **Frozen skill hashes.** They match the live sources (`test_frozen_hashes_match_the_shipped_sources`, 12 params).
- **Resets.** They run only on the first application, are tested on both paths, and go through the single writer. The `{}` path for an emptied file is tested. The warnings name the file and the key.
- **This repo (11e427d0).** The rule was applied correctly. `activated_paradigms` set-equals the released default 8 list, and the spec FR-012 row "Stale activation lists" plus the NFR-001 relation "stale → ALL_BUILTIN" prescribe exactly this reset. The other six lists are customised supersets and were kept. `mission_type_activations` is untouched. The effective-set change (6 more paradigms) is called out in the commit.
- **a7e1311f (skip skills the catalog still ships).** This is correct. It defers to WP18's source deletion, and after WP18 every name is live. `test_fr012_installed_removed_skills` (WP18) is the end-to-end proof.
- **Dry-run parity re-point.** It is end to end and not vacuous: it has a control, and the implementer showed a red result with the summary helper stubbed.
- **Out-of-ownership edits.** All are logged. The `test_retired_ids_absent` exemption is by file and matches the FR-018 historical-root rule for `_charter_pack_cutover_*` helpers.
- **Red-first.** cdb20674 showed 51 failed.

## Blocking

1. **`tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported` is red because of WP12.** It is green on base 8811a06e (37 passed) and red on HEAD. Seven public symbols have no `src/` caller:
   - `_charter_pack_cutover_resets::ResetAction`, `ResetOutcome`
   - `_charter_pack_cutover_skills::REMOVED_SKILL_NAMES`, `SHIPPED_SKILL_HASHES`, `SkillCopy`, `find_removed_skill_copies`
   - `_charter_pack_cutover_snapshots::DIRECTIVE_ID_TO_STEM`

   Fix them in the gate's order of preference. Drop each one from `__all__`; it stays an unexported module name that tests can still import. Underscore-privatise any that are not in `__all__`. Do not add allowlist entries. WP11 got the same finding in its cycle 1.

## Should fix (in this cycle, cheap)

2. **`tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_skills.py` breaks when WP18 deletes the skill sources.** `_install()` (13 call sites) does `shutil.copytree(SKILL_SOURCES / name, …)`. Only the hash-parity test is `skipif`-guarded. After WP18 every removal and keep test errors with `FileNotFoundError`, and `_FrozenTreeHashProver` loses all its coverage. WP18 does not own this file.

   Make the removal and keep tests independent of the live sources. For example, monkeypatch `SHIPPED_SKILL_HASHES` (or the prover's hash map) with a small synthetic tree whose hashes the fixture computes. Keep only the one source-parity test `skipif`-guarded.

## Non-blocking (log or fix if cheap)

3. **Unreachable branch in `_absent_meaning`.** Its `except KeyError` fallback cannot be reached: `activated_kinds` is classified earlier, and `mission_type_activations` is excluded. Every other `ACTIVATION_YAML_KEYS` entry resolves through `ArtifactKind.from_plural`. Remove the fallback, or test it.
4. **Weaker dry-run parity comparison.** The re-pointed `test_fr012_dry_run_parity` compares only the change categories. Kept-for-review, minimal and skills-kept warnings are no longer compared between the dry run and the real run. This is acceptable under the orchestrator ruling. Consider one extra assertion that the `Would keep …` warning count matches.

## Commands run (lane-l HEAD eacd4ee6)

| Command | Result |
|---|---|
| `pytest tests/specify_cli/upgrade/migrations -k charter_pack_cutover -n 4` | 184 passed |
| `pytest tests/acceptance/charter_pack_cutover -n 4 --dist loadfile` | 207 passed, 1 skipped, 146 xfailed, 0 failed, 0 xpassed |
| `pytest tests/specify_cli/skills tests/compat/test_dry_run_parity.py -n 4` | 644 passed, 1 xfailed |
| Gate files: migration_chain_integrity, no_dead_modules, no_dead_symbols, charter_pack_path_authority, mutation_ownership_routing, overwrite_ownership_routing, no_legacy_terminology, ruff_format_enforcement, plus `tests/doctrine/test_retired_ids_absent.py` and `tests/charter/test_config_stem_parity.py` | 303 passed, **1 failed** (no_dead_symbols; green at base, 37 passed) |
| `ruff check`, `ruff check --select C901`, `ruff format --check --force-exclude` on touched files | clean |
| `mypy` on touched sources | 3 errors, all present identically at base (compiler.py:620, preset_application.py:418, `BaseMigration` Any); none in the new modules |
