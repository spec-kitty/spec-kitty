# WP01 review feedback, cycle 1 (architect-alphonso, reviewer role)

**Verdict: changes requested.** The suite is mostly strong. Traceability is complete: a planted removal of an EC, INV, OD, DM, US or NFR id is named, and spec drift is detected. The golden data is sound: `ALL_BUILTIN` symbolic form, `activated_kinds` applied, digests pinned, and `src/` plus `packs/` byte-identical between `fcf7a827` and `b9c2365a`. ruff, format, mypy and the terminology/corpus/collection gates are clean.

Under C-006, though, five tests encode the wrong behaviour or are vacuous. Each one would block or mislead a later WP, so they must be fixed now, before WP02 or WP10 start flipping markers.

## Evidence

- `uv run --frozen pytest tests/acceptance/charter_pack_cutover -q --durations=15`: **82 passed, 1 skipped (`windows_ci` auto-skip), 244 xfailed, 0 failed, 0 xpassed in 476.7 s (8m02s wall).**
- `--runxfail` on 25 sampled tests. Red for the right reason: FR-001 minimal, FR-015 interview/upgrade_unify, FR-012 org_packs/rc35/near-miss, NFR-001 stale_d5, NFR-004, FR-011 pack_context/shims/[charter], FR-007 fetch, FR-016 synthesize/state-contract, FR-009 json code, FR-019 org validate, US3-4 org-charter, FR-008 upgrade, FR-010 r1/r2/r3r4/prose. The exceptions are listed below.

## Required changes (blocking)

1. **`test_promotion.py:63-74` (`org_charter_union` row of `test_fr015_promotion_preserves_effective_set`) uses the wrong entry point and is red for the wrong reason.**
   - The org-charter union (`apply_org_charter_to_interview` → `_promote_org_required_to_config`) is reached only from `charter interview` (`src/specify_cli/cli/commands/charter/interview.py:205-207`), never from `charter generate`.
   - The row runs `charter interview --defaults` **before** writing `org-charter.yaml`, then runs `charter generate --from-interview --force`. With `--runxfail` it fails on the control "the caller promoted the directive key", because only `mission_type_activations` is written.
   - WP06 cannot turn it green without adding the union to `generate`, which is out of scope.
   - Fix: write `org-charter.yaml` (with `required_directives`/`required_tactics`) first, then drive `charter interview --defaults` as the union caller. I probed this at base: the union promotes `activated_directives`/`activated_tactics` and narrows the set (20 directives and 26 tactics lost), which is the correct #4400 red.
   - Keep it distinct from the `interview` row: the union row has no `--selected-*`, and the interview row has no org-charter required lists.

2. **`test_promotion.py:99, 125, 134-137` (`resynthesize` row) is vacuous for the caller it claims to cover.**
   - `_resynthesis_preflight.preflight_resynthesis` still seeds from `load_default_pack_activation_ids()` at base, yet the row passes. Two reasons:
     - the preflight only validates, so it writes nothing the effective-set check could see;
     - `_assert_caller_ran` accepts any exit code when "Activated:" is printed, and the comment admits that synthesis then fails.
   - So reverting WP06's preflight change would not turn this row red, which breaks the "one row per caller" rule in the WP prompt (T007 validation).
   - Fix: make the row observe the preflight. Use a fixture where seeding from the narrow default list makes the preflight refuse or resolve differently, for example a cascade or project-layer reference to the pack-2 id≠stem artifact, or a CLI-visible preflight report. Pend it on WP06, and assert the command's exit code.
   - If no CLI-observable effect exists, say so in a docstring, cover the preflight seam behaviourally in a WP06-owned acceptance test, and stop claiming the unmarked row covers it.

3. **`legacy_fixtures.py:554-564` / `test_upgrade_migration.py:551` (`test_us2_7_lane_in_approved_consolidates_after_root_upgrade`) is vacuous.**
   - The `build_lane_project` docstring says "with a legacy project layer committed on the target before the lanes are cut". The code only calls `build_older_version_lanes_project(...)`, which commits no `.kittify/doctrine/`, no legacy keys and no stale lists.
   - The root upgrade therefore never produces a cutover commit, before or after the cutover. The test can never exercise US2-7's "the lane's bookkeeping-only upgrade commit is not refused".
   - Fix:
     - Commit a legacy project layer (and/or legacy keys) on the target before lanes are cut, as the docstring says.
     - Add a positive control that the root upgrade changed `.kittify/` (non-empty `git status` / the cutover report `moved` non-empty).
     - Since that control cannot hold at base, mark the test `pending_until("WP11", …)`. If you keep it unmarked, show that the control holds at base and log why.

4. **`test_rename_skills_glossary.py:202-212` (`test_fr013_retired_terms_redirected`) cannot be satisfied together with FR-018.**
   - The test requires each retired term to be either a non-canonical `### <term>` section in `docs/context/charter.md` or a `| <term> |` row in `docs/context/historical-terms.md`. Both files are FR-018 living surfaces with no exemption in spec FR-018. For `Doctrine Pack` and `Doctrine Pack ID`, both routes spell the forbidden token `doctrine pack`, so `test_fr018_vocabulary_gate_zero_findings_over_floor` (WP25) goes red. The historical-terms route also trips the WP22 `prose` slice (`doctrine catalog`, `charter selection`).
   - Spec FR-013 says "retire or redirect". The spec-compatible route, which the WP24 prompt (l.83-86, l.220) already plans, is to remove the entries from `charter.md` and mark the terms `status: deprecated` in the exempt seed (`.kittify/glossaries/spec_kitty_core.yaml`) and pack (`packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml`). The test currently fails that route.
   - Fix: accept "absent from `charter.md` (no section) **and** `status: deprecated` with a replacement naming the new term in both the seed and the pack". Drop the `historical-terms.md` alternative, or keep it only for the two terms that are not FR-018 tokens and that the prose slice excludes. Keep the existing controls.

5. **`test_cli_surface.py:211-236` (`test_fr007_old_spelling_exits_2[doctor]`) contradicts `test_fr006_charter_home_matches_recorded_output[doctor]`. WP15 cannot satisfy both.**
   - `cli_before.json` records `doctor doctrine --json` exit **1** on `build_doctrine_command_fixture`, because the configured org pack is not fetched. I confirmed this with `--runxfail`.
   - The FR-006 row correctly requires the recorded exit code (SC-004). The FR-007 row's control requires `doctor charter-packs --json` to exit **0** on the same fresh fixture.
   - Fix: for rows whose recorded exit code is not 0, the FR-007 control should assert the recorded exit code and that "No such command" is absent. Alternatively, build a healthy fixture for that row.
   - Orchestrator note (not this WP's file): WP15 prompt l.113, "each replacement exits 0", should read "with the recorded exit code".

6. **`test_presets.py:417` (`test_fr019_malformed_preset_cases[name_grammar]`) does not isolate the grammar check.**
   - The file stem is `name-grammar` and the body name is `Bad_Name`, so the case is also a name≠stem violation. A validator that only checks name==stem passes it.
   - Fix: make the file stem equal the bad name, for example `presets/Bad_Name.yaml` with `name: Bad_Name`, so only the grammar rule can reject it.

7. **`test_cli_surface.py:330-349` (`test_fr011_legacy_project_fails_naming_upgrade`) covers registered groups only.**
   - The prompt (T006) asks to derive the parameters from `registered_groups` **and** `registered_commands`. Today, top-level commands such as `accept`, `consolidate`, `dispatch`, `merge`, `plan`, `specify`, `tasks`, `review`, `research` and `materialize` are not covered (only `next` and `implement WP01` are, through `HOT_PATHS`).
   - Fix: add the non-exempt `registered_commands`. Exclude `merge-driver-*`, `session-*`, `commit-guard-hook`, `upgrade`, `init` and the hidden `__force_multi_command_mode__`, so a new top-level command is gated automatically.

## Non-blocking (fix if cheap, otherwise log)

- `test_upgrade_migration.py:523` NFR-004: the "first upgrade changed something" control is satisfied by the metadata version stamp alone (fixtures are stamped rc5 and the CLI is rc6). For fixtures the cutover applies to, also assert that the cutover id is in the first run's applied migrations.
- `test_cli_surface.py:416` (`test_fr011_shims_removed`): the control `"def charter_list" in src_text or "charter" in src_text` is trivially true. Replace it with a known symbol that must exist.
- `test_rename_skills_glossary.py:73`: the `(0, 1)` exit tolerance is defensible, since the base finalizer exits 1 on an edited managed copy. On exit 1, assert that the reason is the kept edited copy, not just that `spk-doctrine-show-me` appears in the output. US4-1's orphan check could also cover `.kittify/command-skills-manifest.json`.
- `test_gates_latency_messaging.py` NFR-002 rows: spec NFR-002 names `test_lifted_cli_doctrine_retirement`, but no row checks its exemption structures (the cr02 row only uses it as a control).
- FR-017 changelog check: names are matched verbatim from the contract's Before column, including `spec-kitty tracker … --doctrine-mode` with a Unicode ellipsis. This is fragile. Consider normalising, or note it for WP24.
- **Runtime**: the suite takes 8 min. Most of it is per-test fixture building (git init, commit) plus CLI upgrades across 244 xfails. Each `BUILDERS[name]` result is deterministic, so a session-scoped template per fixture name (build once, then `shutil.copytree` into `tmp_path` per test) would keep per-test isolation and remove most of the build cost. The 33 s resynthesize row is the largest single item.

## On the reported contradictions with later WP prompts

- **WP03 `.gitignore`**: the test (`test_project_pack_root.py`, `.kittify/charter-packs` present, no `.kittify/doctrine`) agrees with WP03's own clause (c) and the spec's "same rules" inventory row. The WP03 "recommended: ignore nothing" line is the inconsistent one, and the orchestrator should align it. No test change is needed.
- **WP06 union row**: the test is wrong (item 1).
- **WP15 exit 1**: the FR-006 test is right and the FR-007 doctor control is wrong (item 5). WP15 prompt l.113 also needs the wording fix.
- **WP18 exit 1**: the test's tolerance is acceptable (see non-blocking). Neither the spec nor WP18 requires exit 0.

## Checklist

Dead code N/A (tests only) · synthetic fixture FAIL (items 2, 3) · silent empty return PASS · FR coverage FAIL (items 1, 2, 4) · frozen surface PASS (no `src/`/`packs/` change; two justified edits outside owned trees: the corpus registry entry and the deferred-bucket registry line) · locked decision PASS · shared-file ownership PASS · production fragility N/A.
