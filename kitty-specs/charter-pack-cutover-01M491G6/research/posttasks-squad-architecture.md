# Post-tasks squad: architecture, sequencing and intermediate-state soundness

Lens: architect-alphonso. Mission `charter-pack-cutover-01M491G6`, branch `issue-3732-charter-pack-rename`, HEAD `051d5a55`. Read-only review of `spec.md`, `plan.md`, `research.md`, `research/runtime-seams.md`, `research/package-split-and-paths.md`, `tasks.md`, `contracts/*.md` and all 25 WP prompts, checked against the code at HEAD. No `.codegraph/` index; evidence is grep/read.

Counts: **4 BLOCKER**, **9 SHOULD-FIX**, **11 NIT**.

## Method

- Parsed every WP frontmatter (`dependencies`, `owned_files`) and computed the transitive closure. 29 WP pairs can run in parallel lanes:
  WP10 with WP02–WP09 and WP17; WP06/WP07 with WP11; WP08 with WP09, WP11, WP12, WP14, WP18; WP09 with WP11, WP12, WP14, WP18; WP13 with WP14 and WP18; WP18 with WP14, WP15, WP16, WP19, WP20, WP21; WP23 with WP24.
- `owned_files` are pairwise disjoint across all 25 WPs (no glob overlap). Every parallel-lane conflict below therefore comes from the "mechanical edits outside owned_files" sections and the in-prompt follow-up lists.
- For each acceptance test in the WP01 flip map I checked that the WP it names, plus that WP's ancestors, actually build the CLI surface or the code the test drives.

---

## BLOCKER

### B1. WP04's `charter.packs` facade imports `specify_cli` (C-007 violation; `test_charter_no_specify_cli_import.py` goes red)

- **Where**: `tasks/WP04-package-split-pack-tooling.md` T022 step 1 (L195–197), T024 step 1 (L219), and "How this WP executes the table" (L172).
- **Finding**:
  - WP04 puts the composing entries `validate_pack_with_org_charter` and `assemble_pack_with_org_charter` into `src/specify_cli/doctrine/org_charter.py`, because `org_charter` only moves to `charter.activation` in WP05.
  - T024 then says to fill `src/charter/packs.py` with "at least `validate_pack_with_org_charter`, `assemble_pack_with_org_charter`".
  - That is a `charter` → `specify_cli` import. `tests/architectural/test_charter_no_specify_cli_import.py:40-60` walks the full AST of every file under `src/charter/**`, so `src/charter/packs.py` fails it, and C-007 forbids the import.
- **Root cause**: the tasks split reversed research A.6, running step 4 (validator/assembler, WP04) before step 3 (org_charter move, WP05). A.6 orders them 3 before 4 for exactly this reason.
- **Fix** (either):
  - (a) In WP04, the CLI (`cli/commands/doctrine.py`, `_doctrine_collect.py`) imports the composing entries directly from `specify_cli.doctrine.org_charter` (specify_cli → specify_cli is legal). `charter.packs` exports them only after WP05 has moved them to `charter.activation.org_charter`, which WP05 then owns.
  - (b) Move A.6 step 3 into WP04 ahead of step 4.
  - With either fix, rewrite T024 step 1 and WP05 T026 accordingly.

### B2. Acceptance tests tagged for a WP that cannot turn them green (hidden coupling with a non-ancestor)

C-006 forbids later WPs from editing these assertions, so the WP01 flip map has to be corrected before WP01 starts. Each row below is an unattainable done-condition.

| Test (WP01 flip map) | Tagged | Needs | Why that WP cannot get there |
|---|---|---|---|
| `test_fr019_validate_names_malformed_file_and_unresolved_id` (WP01 T004, L219; flip map L112: "all `test_fr019_*`" → WP07) | WP07 | `spec-kitty charter pack validate`, created by WP15 T076 | WP15 depends on WP08 → WP07. At HEAD `charter pack` has only `consistency-check`, `list`, `path`, `apply` (`cli/commands/charter/pack.py:37,69,262,279`). |
| `test_us3_4_accompanies_field_rejected` (T006 L263; flip map L118 → WP13) | WP13 | `charter pack validate` (WP15) | WP15 depends on WP13. |
| `test_fr003_init_without_activation_equals_default_preset` (T004 L216; flip map L114 → WP09) | WP09 | `charter activate --preset default` (WP08) | WP09 depends only on WP07, and WP08 ∥ WP09. WP09 T049 step 3 ("if WP08 has landed… if not, the acceptance suite covers it") is circular. |
| `test_fr010_charter_pack_id_in_project_state` (T008 L293: "after upgrade of `doctrine_pack_id_activations`"; flip map L123 → WP17) | WP17 | the WP11 migration rewriting `doctrine_pack_id` | WP11 depends on WP17. WP11 T057 notes even suggest re-tagging in the opposite direction (WP11 → WP17). |
| `test_fr015_promotion_preserves_effective_set[upgrade]` (T007 L278: a fixture stamped below 3.2.6rc1, driven by `spec-kitty upgrade`; flip map L111 → WP06) | WP06 | the normalizer neutralised (WP10) | `m_3_2_x_normalize_activation_absence` (same `3.2.6rc1` target, registered before `m_unify_charter_activation` by filename) writes `[]` for every absent per-artifact key (module docstring L1–13; `_should_defer_bare_config_write` L280–299 does not defer when unify promotion is pending). Unify then appends onto `[]`, so the effective set narrows and `after ⊇ before` fails. WP10 is not an ancestor of WP06. |

- **Fix**:
  - Re-tag the FR-019 `charter pack validate` row and US3-4 (accompanies) to WP15, or drive them through `charter org validate` (which exists at base).
  - Make WP09 depend on WP08, or re-tag the FR-003 equality row to WP13.
  - Re-tag `test_fr010_charter_pack_id_in_project_state` to WP11.
  - Add WP10 to WP06's dependencies (WP10 has no other dependency, so it can land early), or re-tag the upgrade row to WP12.

### B3. WP17 instructs a wait on its own dependent (deadlock)

- **Where**: `tasks/WP17-three-names-and-charter-pack-id.md` L164 ("WP11 (T057) migrates project `charter.yaml`… Confirm both are done before starting") and T085 step 6 ("WP11's migration already rewrote project `charter.yaml`").
- **Finding**:
  - `tasks.md` WP11 has dependencies WP03, WP10 and **WP17**. An implementer following the prompt waits forever.
  - L167 of the same prompt correctly says WP17 "runs early (after WP05)", so the prompt contradicts itself.
- **Fix**: delete the WP11 precondition and the T085 step 6 claim. Say instead: "WP11 runs after you. It writes `charter_pack_id`, which your model must already accept."

### B4. Upgrade-path wedge: once the cutover is recorded as applied, `spec-kitty upgrade` cannot clear a legacy layout that the FR-011 gate still refuses

- **Where**:
  - `src/specify_cli/upgrade/runner.py:314-321`: `_apply_migration` skips any migration that `metadata.has_migration(id)` reports, before running `detect()`.
  - WP10 T050 step 3: a `runs_first` migration is selected "whenever its `detect()` is true **and it is not recorded as applied**".
  - WP14 T072: the gate checks the main root and the current checkout.
  - `.kittify/metadata.yaml` is tracked (`git ls-files .kittify/metadata.yaml`).
- **Finding**:
  - In a team, operator A upgrades and commits. Teammate B pulls.
  - Git deletes the tracked `.kittify/doctrine/**` files but leaves any untracked or ignored files there. In this repository, `.gitignore:97-114` ignores everything under `.kittify/doctrine/` except five subdirectories, so `skills/`, `mission_types/` and similar stay behind.
  - The directory therefore still exists. Every command on B's machine exits `LEGACY_CHARTER_STATE` and names `spec-kitty upgrade`.
  - B runs `spec-kitty upgrade`. `metadata.yaml` (pulled from A) records `charter_pack_cutover` as success, so the runner skips the migration and the gate still fires: a permanent wedge.
  - The same happens when a merge reintroduces a legacy file. Research §1.2 explicitly wanted `detect()` to be content-driven for this case, but the runner's record check defeats it.
- **Fix**:
  - For the `runs_first` cutover migration, let `get_applicable` and `_apply_migration` re-run it whenever the **structural** predicate `detect_legacy_charter_layout()` is true, regardless of the recorded result. It is idempotent under NFR-004.
  - Restrict that re-run trigger to the structural findings. Do not include WP12's `[]`, stale-list or skill checks. Otherwise a deliberate post-cutover `activated_<kind>: []`, which WP12's own warning tells users to set, would be reset again.
  - Add a WP10/WP11 test: the migration is recorded as success, `.kittify/doctrine/x.md` is planted, `spec-kitty upgrade` moves it, and the gate then passes.
  - Make the FR-011 message name the manual remedy as well.

---

## SHOULD-FIX

### S1. Parallel-lane ownership violations (tasks.md: "Never edit a file owned by a WP that can run in a parallel lane")

| Editing WP | File | Owner (parallel) | Evidence |
|---|---|---|---|
| WP09 | `src/specify_cli/cli/commands/upgrade.py` (`except` clause, docstring) | WP12 (WP09 ∥ WP12) | WP09 T046 step 4, T047 step 4 |
| WP10 | `tests/specify_cli/cli/commands/test_init_provisioning.py` (deletes the rc35 test) | WP09 (WP09 ∥ WP10) | WP10 L96; WP09 T049 step 4 ("expect that small hunk") |
| WP13 | `src/charter/offering/drg/org_pack_config.py` remediation string | WP14 (WP13 ∥ WP14) | WP13 T067 step 3 ("if WP14 already landed skip it") |
| WP18 | `docs/api/cli-commands.md` | WP16 (WP16 ∥ WP18) | WP18 T089 step 5, T090 step 5 |
| WP19, WP20 | skill prose in `src/charter/offering/skills/**` | WP18 (∥ both) | WP19 Context L223; WP20 Context follow-up list |
| WP21 | `tests/architectural/test_docs_cli_reference_parity.py` | WP18 (WP18 ∥ WP21) | WP21 T099 step 3 ("gates owned upstream…") |

- **Fix** (smallest set of edges):
  - Make WP19 depend on WP18. This removes four violations, and WP22/WP23 already wait for both.
  - Make WP09 depend on WP10. WP10 is early and small.
  - Move WP09's `upgrade.py` edit into WP12, or make WP12 depend on WP09.
  - Have WP13 skip `org_pack_config.py` unconditionally; WP14 deletes that warning anyway.

### S2. WP14 is scoped against stale names and misses its own inherited debts (end state red or FR-011 incomplete)

- **Where**: `tasks/WP14-remove-shims-and-legacy-gate.md` T070 step 3 and the Review grep.
- **Finding**: WP14 searches for `resolve_doctrine_read_root` and `LegacyDoctrineRootWarning` and says "the only caller was `reconcile.py:612`". WP02 T011 renamed the function to `resolve_project_pack_read_root` (in `kernel/charter_pack_paths.py`) and called it with `quiet=True` from about 25 read sites (WP02 T013/T014; WP03 T016–T017). WP14 also never mentions the following items that earlier WPs assigned to it:
  - WP03's `_is_legacy_artifact_prefix` in `synthesizer/manifest.py`, which WP03 says WP14 deletes;
  - WP03's `test_*_legacy_root_read_fallback` tests, which turn red once the fallback goes (WP03 T020 step 1);
  - the FR-016 gate's kernel legacy-segment exemption and the test that "fails once WP14 deletes `LEGACY_PROJECT_PACK_DIRNAME`" (WP03 T019);
  - the dual dirty-scope prefix in `charter_runtime/preflight/runner.py` (WP02 T014);
  - the legacy half of `charter/offering/service.py:48` (WP02 T013);
  - the two FR-016 allowlist entries owned by WP14: `kind_vocabulary.py:297` and `_doctrine_paths.py:32` (WP03 T019).
- **Fix**: add an inventory step to T070 that lists all of these, with `git grep -n "LEGACY_PROJECT_PACK_DIRNAME\|resolve_project_pack_read_root\|_is_legacy_artifact_prefix\|legacy_root_read_fallback"` as the check.

### S3. The FR-011 gate breaks git merge drivers inside an unmigrated checkout

- **Where**:
  - `src/specify_cli/lanes/consolidation.py:66-136` registers `spec-kitty merge-driver-{event-log,meta,traces,acceptance-matrix,issue-matrix,review-cycle,decision-index}`. Git runs these with cwd set to the worktree being merged.
  - The commit-guard hook falls back to the `spec-kitty` CLI (`policy/hook_installer.py:52-55`).
  - WP14 T072 gates every command except `upgrade` and `init`, and checks the current checkout.
- **Finding**:
  - The documented remedy for pre-upgrade lanes is to merge the upgraded target into the lane (research §2; spec Edge Cases).
  - That merge runs a merge driver inside a checkout that still holds `.kittify/doctrine/`. The driver exits 1, so the merge is left conflicted or fails.
- **Fix**:
  - Exempt the `merge-driver-*` subcommands and the hook-fallback subcommand in `legacy_charter_gate.EXEMPT_COMMANDS`. These are git plumbing, not project commands.
  - Add a test that runs a merge-driver invocation in a legacy checkout and expects exit 0.

### S4. WP25's exemption list is narrower than spec FR-018, so the gate is red, or escalates, on files the spec already exempts

- **Where**: `tasks/WP25-vocabulary-gate-and-closeout.md` T111 steps 3 and 5. Compare spec.md L182–183.
- **Finding**:
  - The spec exempts the following by file:
    - the cutover helpers (`_charter_pack_cutover_*`);
    - the legacy-state predicate module;
    - the tombstones: `skills/retired.py`, `offering/packs/retired_fields.py`, `upgrade/metadata.py`, and every pre-existing `migrations/m_*.py`.
  - WP25 lists only `m_*_charter_pack_cutover.py` plus the snapshot module, and tells the implementer to "stop and escalate" for `retired.py`, `retired_fields.py` and `metadata.py`. It does so because it believes "the spec's closed lists do not cover them".
  - WP12's `_charter_pack_cutover_skills.py` holds all twelve removed skill ids, so the gate fails on it.
- **Fix**: copy the spec's historical-root and tombstone bullets into T111 verbatim, and drop the escalation step for those files.

### S5. WP18 calls a command that may not exist yet

- **Where**: WP18 T090 step 3 and the Test Strategy use `spec-kitty charter pack regenerate-graph [--check]`, which is WP15's home.
- **Finding**: WP18 depends only on WP12 and can run before WP15. tasks.md's generated-files rule already says to use `spec-kitty doctrine regenerate-graph` before WP15.
- **Fix**: add the fallback spelling. The S1 edge WP19 → WP18 does not cover this; WP18 → WP15 would, at a parallelism cost.

### S6. The version rule is stated three ways

- **Where**:
  - tasks.md L15: "no WP bumps `pyproject.toml`'s version".
  - research `runtime-seams.md` §1.3: "`4.0.0rc7`, bumped in the same mission".
  - WP10 Risks: "WP11 adds `4.0.0rc7` with its version bump".
  - WP11 T055 step 4: `target_version` = the current version, file `m_4_0_0rc6_…`.
  - WP14 asks the orchestrator whether the version bump lands in WP14.
- **Finding**: the chain terminal is currently `4.0.0rc5` (`get_all()[-1]`). With `pyproject.toml` at `4.0.0rc6`, an rc6 target satisfies `test_migration_chain_does_not_exceed_current_project_version`.
- **Fix**: rule "rc6, no bump" once, then fix WP10's Risks line and WP14's question.

### S7. `test_fr012_installed_removed_skills` cannot pass through a full `spec-kitty upgrade` before WP18

- **Where**: WP01 T005 L240 (through the CLI); flip map L117 tags it WP12. WP12 T063 note: "until WP18 lands, the upgrade finalizer's surface repair would reinstall these skills".
- **Finding**: the finalizer (`upgrade/assessment.py:121-139`) reinstalls every skill the catalog still ships.
- **Fix**: re-tag the test to WP18, or pin its assertion to the migration report lines only. The test must also verify on disk only after WP18.

### S8. Oversized work packages

- **Finding**:
  - **WP01**: 10 subtasks covering about 16 fixture builders, a golden generator, about 60 acceptance tests and the traceability test. That is more than one session.
  - **WP20**: R2, about 42 src files and 550 tokens plus 86 owned test files. Research §C itself says to split R2 into R2a (catalog and service builder) and R2b (synthesizer and context) above about 30 files.
  - **WP22**: 155 owned files, all `manual_review` prose.
- **Fix**:
  - Split WP01 into scaffold, fixtures and golden data (T001–T003, T010) and the per-FR tests (T004–T009). Tag the second half to run before any implementation WP.
  - Split WP20 as research recommends.
  - Split WP22 into packs prose (T101, T103) and docs prose (T102, T104).

### S9. WP12's write path depends on whether WP08, a parallel lane, has merged

- **Where**: WP12 T062 step 4: "prefer a delete-capable writer if WP08's preset engine added one … otherwise line-level edit".
- **Finding**: WP08 ∥ WP12, so the implementation depends on merge timing.
- **Fix**: make WP12 depend on WP08 and use `prepare_activation_write(remove=…)`, or always use the line-level edit.

---

## NIT

1. **Stale "parallel" statements** contradict the dependency graph:
   - WP14 L97 says "WP15 may run beside you" and "WP17 may rename … in parallel". WP15 descends from WP14, and WP17 is an ancestor of WP14.
   - WP15 L127 and T079 say WP13 and WP14 run in parallel. Both are ancestors of WP15.
   - WP19 L222 and WP20 Context say WP08, WP09, WP13, WP15 and WP16 are "not upstream". All are upstream through WP16 and WP14.
   - WP22 L268 and WP23 L247, L258 each say the other runs in parallel. WP23 depends on WP22.
2. **Wrong owner attributions**:
   - WP05 L159 says WP10 owns `m_unify_charter_activation.py`; it is WP06.
   - WP07 T039 says `doctrine.py` is owned by WP15/WP16; it is WP03.
   - WP17 T083 says `default_pack.py` is deleted by WP13; it is WP09.
   - WP18 T089 says `synthesize.py` is WP17's; it is WP03's.
   - WP20 says `synthesizer/errors.py` is WP18's (it is WP03's) and `test_charter_pack_builtin.py` is WP13's (it is WP08's).
   - WP25 T113 says `test_lifted_cli_doctrine_charter_cr02_compat.py` is deleted by WP14; it is deleted by WP16.
3. **WP06 uses an old class name**: T030 calls `CharterPackManager().list_available`, but WP06 runs after WP17 renamed the class to `ActiveCharterManager`.
4. **Generated files listed as owned**: tasks.md L17 lists `docs/api/cli-commands.md` and `docs/development/docs-retrieval-index.yaml` as ownerless generated files. WP16 owns and hand-edits the first, and WP15 owns the second. Rule once.
5. **`doctrine-daphne.agent.yaml:114`**: WP15 says not to edit it (C-004 / `do_not_change`), while WP16 and WP22 both edit it. The owner should rule once (C-004 covers the id and name, not the stale command line) and occurrence_map should be updated.
6. **WP11 still escalates a case WP10 already handles**: WP11 T055 step 5 and Risks treat "stamped above target → not selected" as an open escalation. WP10 T050 step 3 already implements version-independent selection; align the text (and see B4).
7. **WP16 lists already-moved files**: T082 step 4 lists `tests/specify_cli/doctrine/test_config.py` and `test_pack_validator.py`, which WP04 and WP05 already moved.
8. **WP09 and C-008**: WP09 deletes `charter.activation.default_pack` (its share of FR-005) without depending on WP10 or WP12. This literally breaches C-008 ("FR-012 … before FR-005") but is harmless: the snapshots come from the research YAML, and `default.yaml` and the registry stay until WP13. Record the deviation.
9. **Shared files edited by parallel lanes** (legal, but likely to conflict):
   - `tests/architectural/charter_path_literal_allowlist.yaml` (WP10 ∥ WP17, plus WP13);
   - `tests/architectural/dead_symbol_allowlist.yaml` (WP13 ∥ WP14);
   - `pyproject.toml` excludes;
   - `tests/doctrine/**` (WP18 ∥ WP19, WP20 and WP21);
   - the `CharterPackManager` comment in `m_3_2_0rc35_default_charter_pack.py:58`, which WP17's sweep edits while WP10 deletes the body.
10. **`ci-router.yml` filter left behind**: WP03 T018 defers removing the `'.kittify/doctrine/**'` filter from `.github/workflows/ci-router.yml` to WP11, but WP11 never mentions `ci-router.yml`. WP25's FR-018 gate (which scans `.github/workflows/`) would catch it late. Add it to WP11 T059.
11. **Dogfooding hazard**: this mission's own coordination worktree keeps `.kittify/doctrine/` (research §2). Once the WP14 code is the installed CLI, any `spec-kitty` run with cwd in that checkout, or in a lane cut before WP11, is refused. Add a note to WP14 and WP11 T059: run status commands from the repository root, or upgrade and merge the coordination checkout.

---

## Checked and found sound

- **Ordering**: C-008 ordering holds in the graph:
  - FR-015 → FR-002 (WP06 → WP07);
  - FR-016 → FR-011/FR-012 (WP02/WP03 → WP11 → WP14);
  - FR-012 → FR-005 (WP12 → WP13; see NIT 8 for WP09);
  - FR-006 → FR-007 (WP15 → WP16);
  - FR-008 → FR-018 (WP18 → WP25).
- **Older migrations still import and run**:
  - `m_3_2_0rc35_default_charter_pack`'s module-level registry import (`:49`) is removed by WP10 before WP13 deletes the registry.
  - `m_unify_charter_activation`'s module-level `default_pack` import (`:59`) is removed by WP06 before WP09 deletes the module. Its module-level `resolve_doctrine_root` import (`:58`) is repointed by WP20.
  - The finalize migration's lazy `apply_legacy_governance_selection_key_compat` is removed by WP10 before WP14 deletes the function.
  - `m_2_1_2_fix_glossary_context_skill` is stubbed by WP10 before WP18 deletes the skill.
  - The only migrations naming removed skills are that one, `m_3_1_1_charter_rename` and `m_3_2_0rc35_kittify_profile_handoff`; all three are covered.
  - The `"doctrine"` path joins in the seven `m_2_1_2_*` / `m_3_2_0rc*` migrations are read fallbacks only.
- **The CLI-root gate does not block the upgrade itself**: `main_callback` returns early on `upgrade_intent` (`specify_cli/__init__.py:128-131`), `upgrade` is exempt, and the finalizer runs in-process after the migrations (`cli/commands/upgrade.py:1864-1889`). B4 and S3 are the residual gaps.
- **This repository's `.kittify` state is migrated before the shims go**: WP11 T059 moves the 14 tracked files, and WP12 T065 resets `activated_mission_step_contracts: []` and `activated_glossary_packs: []` (`charter.yaml:2085-2086`). Both come before WP14. Neither `.kittify/charter/charter.yaml` nor `packs/internal/org-charter.yaml` carries `doctrine_pack_id`, so WP17's rejection breaks nothing here before WP11.
- **Golden "before" generator**: its refusal stays consistent through the chain. WP02 deletes `kernel/doctrine_root.py` before WP05 deletes `specify_cli.doctrine`, so the T003 control test (`is_pre_cutover_tree()[0] == (doctrine_root.py exists and default.yaml exists)`) holds at every merge point.
- **Layering**: apart from B1, the prompts respect kernel ← charter ← specify_cli and the offering → activation ban:
  - `presets.py` and `retired_fields.py` are in offering and import only offering and kernel;
  - `effective_set`, `preset_application`, `default_preset_mission_types` and `org_charter` are in activation;
  - `legacy_charter_layout` and `legacy_charter_gate` import no `charter.*`.
