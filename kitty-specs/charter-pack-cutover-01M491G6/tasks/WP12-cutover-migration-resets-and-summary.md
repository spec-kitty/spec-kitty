---
work_package_id: "WP12"
title: "Cutover migration II — stale lists, resets, skills, summary"
subtasks: ["T061", "T062", "T063", "T064", "T065"]
dependencies: ["WP07", "WP08", "WP09", "WP11"]
requirement_refs: ["FR-012", "NFR-001", "NFR-004", "SC-002"]
task_type: "implement"
phase: "Phase 3 - Upgrade migration"
execution_mode: "code_change"
owned_files:
  - "src/specify_cli/upgrade/migrations/_charter_pack_cutover_snapshots.py"
  - "src/specify_cli/upgrade/migrations/_charter_pack_cutover_resets.py"
  - "src/specify_cli/upgrade/migrations/_charter_pack_cutover_skills.py"
  - "src/specify_cli/cli/commands/upgrade.py"
  - "tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_snapshots.py"
  - "tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_resets.py"
  - "tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_skills.py"
  - "tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_summary.py"
  - ".kittify/charter/charter.yaml"
authoritative_surface: "src/specify_cli/upgrade/migrations/_charter_pack_cutover_"
create_intent:
  - "src/specify_cli/upgrade/migrations/_charter_pack_cutover_snapshots.py"
  - "src/specify_cli/upgrade/migrations/_charter_pack_cutover_resets.py"
  - "src/specify_cli/upgrade/migrations/_charter_pack_cutover_skills.py"
  - "tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_snapshots.py"
  - "tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_resets.py"
  - "tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_skills.py"
  - "tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_summary.py"
agent_profile: "python-pedro"
role: "implementer"
agent: "claude"
history:
  - at: "2026-10-06T19:30:00Z"
    actor: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP12 – Cutover migration II — stale lists, resets, skills, summary

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

After WP18 lands, the `/ad-hoc-profile-load` skill is deleted: load profiles with `spk-charter-profile-load` instead (use whichever exists in your checkout).

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile list` and pick the best match for `task_type: implement`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete.
- **Report progress** in the Activity Log as you address each item.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

Finish the FR-012 migration that WP11 started: the activation-list rows, the installed-skill row and the upgrade summary, then prove the whole migration against NFR-001 (nothing effective is lost), NFR-004 (idempotence) and SC-002.

Done means:

- The frozen snapshots of every released `default.yaml` / `minimal.yaml` live in a migration-private data module, derived from `research/default-yaml-snapshots.yaml`, and never read a live file.
- Per key, a list set-equal (order-insensitive, id-normalised) to a `default` snapshot is reset to absent; `activated_kinds` equal to the 8-kind snapshot is reset; `activated_kinds == [directives, tactics]` is reset **and reported** (DM-01M497F0NAQARAK3JZFVWF1SD0); every per-artifact `activated_<kind>: []` is reset **and reported** with the file and key to set back to `[]` (DM-01M497EW60HNWWJQCXDFA99R0H); customised and `minimal`-equal lists are kept and reported.
- Removed skill directories in configured agent skill roots are removed when manifested or hash-equal to a shipped copy; edited copies are kept and reported.
- `spec-kitty upgrade` (human and `--json`, real and `--dry-run`) shows moved / rewritten / reset / kept-for-review lines.
- Every remaining WP01 test marked `pending_until("WP12")` (FR-012 rows, NFR-001, NFR-004, SC-002, US2 scenarios 2, 3, 4, 6 and any other tagged WP12) is green.

## Context & Constraints

- `spec.md`: FR-012 inventory rows "Stale activation lists", "Stale kind gate", "Released `minimal` kind gate", "Normalizer empty lists", "Installed skills", "Customised lists, `minimal`-equal lists"; the comparison rule under the table; Edge Cases (stale list plus one id; list equal to `minimal`; deliberate `[]`; lists mixing default ids with others); NFR-001, NFR-004, SC-002.
- Decisions: `decisions/DM-01M497EW60HNWWJQCXDFA99R0H.md` (reset **every** per-artifact `[]` and name each with how to switch the kind off again), `decisions/DM-01M497F0NAQARAK3JZFVWF1SD0.md` (remove `activated_kinds: [directives, tactics]` and report).
- `research/default-yaml-snapshots.md` (method, per-key distinct-list tables, rewrite rules, id normalisation, gaps G1–G6) and `research/default-yaml-snapshots.yaml` (1,080 lines; the data).
- `research/runtime-seams.md` §1.5 (normalizer conflict), §5 (skill retirement: project roots are manifest-based; the hash-matched step for unmanifested copies).
- `contracts/upgrade-migration.md` steps 6–8 and the `MigrationResult` mapping.
- WP11's module docstrings: `m_4_0_0rc6_charter_pack_cutover.py` (step order) and `_charter_pack_cutover_report.py` (`CutoverReport` fields and dict shape). Read them first; use the report categories WP11 created (`reset`, `kept_for_review`, `matches_minimal`, `skills_removed`, `skills_kept`).
- Upstream: WP07 (presets exist in `packs/built-in/presets/`, `minimal` fixed), WP10 (normalizer and rc35 migrations neutralised: after this WP nothing writes `[]` or stale lists again), WP11 (module, report, move, keys).

Constraints:

- **No live-file reads for comparison.** The snapshots are frozen data; `src/charter/activation/packs/default.yaml` is deleted by WP13 after you. Do not import `default_pack`, `charter_pack_registry` or the preset loader for the comparison.
- **`mission_type_activations` is never reset** (absent means fail closed at use; `data-model.md` "Active charter").
- **C-001**: no compatibility layer; the migration is the only legacy-aware code.
- Wiring your steps into WP11's `apply()`/`detect()` is a short edit in a file owned by WP11 (completed upstream): allowed by the tasks.md follow-up rule; log it with a one-line rationale.
- `src/specify_cli/cli/commands/upgrade.py` is yours; WP17 (exception renames) and WP09 (provisioning `except` clause and docstring) edited it before you, both upstream. Keep your edit to one rendering helper plus its call.
- Code style: ruff + mypy clean, complexity ≤ 15, no unexplained suppressions, constants for repeated literals.
- Commit often (`feat(upgrade): reset stale default activation lists (#3732)`), never push to `main`.

## Branch Strategy

- **Strategy**: lane-based; the lane is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`

> Populated automatically by `spec-kitty agent mission finalize-tasks`. Do not change manually.

## Red-first (C-006 / C-011)

First commit: remove the `pending_until("WP12")` strict-xfail markers from the WP01 acceptance tests in `tests/acceptance/charter_pack_cutover/` (`grep -rn 'pending_until("WP12")' tests/acceptance/charter_pack_cutover/`): the remaining FR-012 rows, the NFR-001 golden comparisons, NFR-004 idempotence, SC-002 and the US2 scenarios tagged WP12 (WP01's plan: in `test_upgrade_migration.py`, the stale/kept/minimal/`[]`/dry-run FR-012 tests, all `test_nfr001_*`, `test_nfr004_*`, `test_us2_6_*`). Not yours: `test_fr012_installed_removed_skills` flips at WP18 (it runs through `spec-kitty upgrade`, whose finalizer reinstalls the skills until WP18 deletes their sources), and `test_us2_7_*` is unmarked (it passes at base; a regression guard that must stay green). WP01 keeps its own copy of the snapshot data in `tests/fixtures/charter_pack_cutover/default_yaml_snapshots.yaml`, independent of your T061 module: never make the tests read your module or vice versa. Run them, paste the red output into the Activity Log, change no assertion. The NFR-001 "before" sets are frozen JSON from WP01 (with generator and base SHA); never regenerate them.

## Subtasks & Detailed Guidance

### Subtask T061 – Frozen snapshot data module from `research/default-yaml-snapshots.yaml`

- **Purpose**: the comparand for "stale", frozen as code because the source file disappears in WP13 (research B2/S6).
- **Steps**:
  1. Create `src/specify_cli/upgrade/migrations/_charter_pack_cutover_snapshots.py` (underscore: not auto-discovered, `migrations/__init__.py:46-51` imports only `m_*` and `base`). Content, all immutable:
     - `DEFAULT_SNAPSHOTS: Mapping[str, tuple[frozenset[str], ...]]`: per key (`activated_directives`, `activated_tactics`, `activated_styleguides`, `activated_toolguides`, `activated_paradigms`, `activated_procedures`, `activated_agent_profiles`, `activated_mission_step_contracts`), every distinct id set from both `form: original` and `form: post_rewrite` entries. Expected distinct counts per key (research table): directives 1, paradigms 1, procedures 1, mission_step_contracts 1, agent_profiles 3, styleguides 2, toolguides 3, tactics 3 (97, 95 and the unshipped post-rc5 94-list).
     - `DEFAULT_KIND_GATE: frozenset[str]` = the 8 kinds; `MINIMAL_KIND_GATE = frozenset({"directives", "tactics"})`.
     - `MINIMAL_SNAPSHOTS`: `activated_directives` (5 stems), `activated_tactics` (both variants). `mission_type_activations` snapshots are **not** needed (never reset).
     - `DIRECTIVE_ID_TO_STEM: Mapping[str, str]`: `DIRECTIVE_NNN` → numbered stem for every directive id in any snapshot (research "Id normalisation": all 32 numbered built-ins have `id: DIRECTIVE_<NNN>` equal to the stem's prefix; embed the 19 that appear in snapshots).
     - `normalise_id(kind_key, raw) -> str`: for directives, map `DIRECTIVE_NNN` via the table, and fold an UPPER_SNAKE unnumbered id to its kebab stem (`USE_C4_MODEL_TECHNIQUES` → `use-c4-model-techniques`); other kinds return `raw` unchanged.
     - Module docstring: source (PyPI wheels, 174 releases, sha256-verified, 2026-10-06), comparison rule, and "do not edit by hand; regenerate from the research YAML".
  2. Generate the literals with a throwaway script in your scratchpad that reads the research YAML with `yaml.safe_load` and prints sorted tuples. Do not commit the script; paste its command and output digest (sha256 of the generated module body) into the Activity Log.
  3. Before WP13 deletes them, check by hand that today's `src/charter/activation/packs/default.yaml` and `minimal.yaml` match the 4.0.0rc5 snapshot on every key (research: "set-equal to 4.0.0rc5"). If they differ, a new snapshot is needed: add it and record why. Do **not** encode that check as a test (the files are deleted by WP13).
- **Files**: `_charter_pack_cutover_snapshots.py`, `tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_snapshots.py`.
- **Tests**: distinct-count table per key; list sizes (directives 19, paradigms 8, procedures 13, mission_step_contracts 17, agent_profiles 15/16/18, styleguides 8/9, toolguides 10/9/12, tactics 97/95/94); the 94-list equals the 95-list minus `supply-chain-install-safety`; `normalise_id` round trips; no `minimal` set equals a `default` set for the same key (research overlap check).
- **Parallel?**: yes, first.

### Subtask T062 – Stale-list, kind-gate and `[]` resets with per-key report lines

- **Purpose**: upgraded projects regain built-ins added after their list was written (SC-002), without touching customisations.
- **Steps**:
  1. Create `_charter_pack_cutover_resets.py` with `plan_resets(project_path) -> list[ResetAction]` (pure, no writes) and `apply_resets(project_path, actions, dry_run) -> CutoverReport fragment`.
  2. **Surfaces**: the resolved activation store (`charter.yaml` when `config.yaml` carries the `charter:` pointer, else `config.yaml`; resolve the pointer the same way as `charter.activation.pack_manager.resolve_activation_write_target`, `pack_manager.py:618`, lazy import) **and** the other file when it also carries activation keys (a leftover `config.yaml` mirror, research G3 and the finalize-fold timing gap). Malformed YAML raises `MigrationStateUnreadableError`.
  3. **Per key, in this order** (keys from `ACTIVATION_YAML_KEYS`, `pack_manager.py:175`, lazy import; or the WP17-renamed home):
     - `activated_kinds`: set equals `DEFAULT_KIND_GATE` → reset, `reset` line; equals `MINIMAL_KIND_GATE` → reset, `reset` line **and** a `warnings` line naming the file and saying the `minimal` gate was a defect (DM-…F0NA); anything else → keep, `kept_for_review`.
     - per-artifact key `== []` → reset, `reset` line **and** a `warnings` line: `<file>: <key> was [] (nothing active); it is now absent (every <kind> available). To switch the kind off again, set <key>: [] in <file>.` If a CLI command exists that writes an empty list for a kind, name it too (check `charter deactivate` and WP08's preset surface; record what you found). This covers `activated_skills` and `activated_glossary_packs` (DM ruling: every per-artifact key).
     - normalised set equal to any `DEFAULT_SNAPSHOTS[key]` entry → reset, `reset` line ("matched released default list").
     - normalised set equal to a `MINIMAL_SNAPSHOTS[key]` entry → keep, `matches_minimal` line ("matches preset minimal").
     - any other present list → keep, `kept_for_review` line ("customised; not changed").
     - `mission_type_activations` → never touched, never reported.
  4. **Write**: remove keys only; never add one. WP08 is upstream and added key removal to the single writer: use `prepare_activation_write(repo_root, {}, remove=…)` → `apply_yaml_write` (lazy import) for both targets, and assert untouched lines are byte-identical.
  5. **First application only** (orchestrator decision, AR-B4): the `[]`, stale-list and kind-gate resets run only on the cutover's first application. WP11 records it; when WP10's selection re-runs the migration on its structural predicate (legacy root, legacy keys, `doctrine_pack_id`), skip this step, so a deliberate post-cutover `activated_<kind>: []` (which your own warning tells users to set) is never reset again. Test both paths.
  5. Wire into WP11's `apply()` at contract step 6 and into `detect()` (a reset or a reportable `[]` makes `detect()` true; a kept customised list alone does **not**, otherwise `detect()` never turns false: NFR-004).
- **Files**: `_charter_pack_cutover_resets.py`, `test_charter_pack_cutover_resets.py`, the WP11 module (wiring, logged).
- **Tests**: one per row and edge case: each released `default` list per key (original and post-rewrite, including the 94-tactics list and a post-rtk 9-toolguides list); a list in a pointed `charter.yaml` and a leftover config mirror; `DIRECTIVE_NNN` ids; near-miss (snapshot minus one id, plus one id) kept; minimal-equal kept and reported; 8-kind gate reset; `[directives, tactics]` reset + warning; `[]` per key reset + warning text naming file and key; `mission_type_activations: []` untouched; second apply byte-identical and `detect()` False.
- **Parallel?**: after T061.

### Subtask T063 – Installed-skill removal (manifested and hash-matched; edited copies kept)

- **Purpose**: project skill roots stop carrying names FR-008 removes; edited copies survive (research §5 decision c).
- **Steps**:
  1. Create `_charter_pack_cutover_skills.py` with `REMOVED_SKILL_NAMES`: `spk-doctrine-charter`, `spk-doctrine-glossary`, `spk-doctrine-profile-load`, `spk-doctrine-spdd-reasons`, `spk-doctrine-bulk-edit`, `spk-doctrine-semantic-compression`, `spk-doctrine-show-me`, `spec-kitty-charter-doctrine`, `spec-kitty-glossary-context`, `spec-kitty-bulk-edit-classification`, `spec-kitty-spdd-reasons`, `ad-hoc-profile-load` (FR-008, occurrence map moves), plus `spec-kitty-constitution-doctrine` (13 names; orchestrator ruling FI-S4; WP10 leaves that directory alone and WP18 retires the name; it has no shipped source here, so only a manifested copy is removed and an unmanifested one is kept and reported). WP18 later adds the same names to `RETIRED_CANONICAL_SKILL_NAMES` (`skills/retired.py`) for user-global roots; do not edit `retired.py` here.
  2. `SHIPPED_SKILL_HASHES: Mapping[str, Mapping[str, str]]`: per removed skill, relative file path → sha256 of every file under `src/charter/offering/skills/<name>/` **as of this WP** (the sources still exist; WP18 deletes them). Installed copies are byte copies of the source (`skills/installer.py:_project_skill_file`, `atomic_write(dest, content)`). Generate with a scratch script; record its digest. Older released copies are not covered: an unmanifested old copy is kept and reported (the safe direction); record this limitation in the docstring.
  3. Roots: for each configured agent (`load_agent_config(project_path)`; CLAUDE.md "Agent Management"), each project skill root from `AGENT_SKILL_CONFIG[agent]["skill_roots"]` (`core/config.py`, see `skills/paths.py:16`). Deduplicate (`.agents/skills` is shared by codex, vibe, pi, letta). Skip roots that do not exist; never `mkdir`.
  4. For each `<root>/<removed name>/` present: prove ownership with `AnyProver([ManifestProver(), _FrozenTreeHashProver(...)])` (`asset_preservation/provers.py:73,221`; write the tree prover in this module: proven when every file hashes to a frozen value for that skill and the tree has no extra files). Remove with `guard_destructive_removal(..., is_tree=True, dry_run=dry_run)` (`asset_preservation/guard.py:148`). Verify what the guard does with an unproven tree: the spec requires the edited copy to stay **in place** (kept and reported, path in `preserved_paths`). If the guard archives-and-removes when `backup_parent` is passed, do not pass it.
  5. The removal must satisfy `tests/architectural/test_mutation_ownership_routing.py` (no raw `rmtree`/`unlink` in migration modules; shrink-only allowlist; a new routed module may need adding to the gate's pinned routed-module set, a logged test edit). Never add an allowlist entry.
  6. When a manifested copy is removed, drop its entries from `.kittify/skills-manifest.json` through the manifest store (`skills/manifest.py` load/write helpers around `:144-240`) so no orphan entry remains (US4).
  7. Wire into WP11's `apply()` at contract step 7 and into `detect()` (a removed name present in a root makes `detect()` true; after a run that kept an edited copy, `detect()` must still turn false, so exclude copies recorded as kept: compare against the frozen hashes rather than presence alone).
- **Files**: `_charter_pack_cutover_skills.py`, `test_charter_pack_cutover_skills.py`, WP11 module wiring (logged).
- **Notes**: until WP18 lands, the upgrade finalizer's surface repair would reinstall these skills from the catalog; test the migration step directly, not through a full `spec-kitty upgrade`. The acceptance test `test_fr012_installed_removed_skills` and US4's end-to-end skills scenario belong to WP18.
- **Parallel?**: yes, beside T062.

### Subtask T064 – Upgrade summary rendering; dry-run parity

- **Purpose**: the operator sees what moved, what changed and what to review (FR-012 "Results … go to the migration result and the upgrade summary").
- **Steps**:
  1. JSON: confirm `migration_reports["charter_pack_cutover"]` carries WP11's report dict (`cli/commands/upgrade.py:834-848` decodes `changes_made[0]`). Add a test.
  2. Human: today `_render_outcome_tail` (`upgrade.py:~925-958`) prints warnings, errors and manual-review paths but no per-migration changes. Add one helper, for example `_print_migration_summaries(outcome)`, that prints, for each migration whose `changes_made[0]` decodes to a dict with a `summary_lines` (or the WP11 field names) list, a header and the lines, before the Warnings section. Keep it generic (no cutover-specific import into `upgrade.py`) and ≤ 15 complexity.
  3. Dry run: lines prefixed `Would …`; `tests/compat/test_dry_run_parity.py` stays green; the plan table already lists the cutover first (WP10 ordering).
  4. Make sure kept-for-review, minimal-equal, `[]`-reset and edited-skill lines also land in `warnings` so `manual_review_required` turns on and the existing auto-commit suppression (`upgrade.py:1871-1873`) applies.
- **Files**: `src/specify_cli/cli/commands/upgrade.py`, `test_charter_pack_cutover_summary.py`.
- **Tests**: CliRunner `spec-kitty upgrade --dry-run` and real run on a legacy fixture: human output contains each category; `--json` has the report; dry run writes nothing (tree hash).

### Subtask T065 – NFR-001 / NFR-004 / pre-rc35 green; flip remaining FR-012 xfails

- **Purpose**: prove the whole migration on WP01's fixtures and golden sets.
- **Steps**:
  1. Run the WP01 upgrade acceptance tests you un-marked. For each NFR-001 fixture (spec NFR-001 list: legacy keys only; single-pack legacy form; `organisation_packs`; legacy directory only; stale lists per snapshot including post-rc5; stale lists in a pointed `charter.yaml`; near-miss; customised; `minimal`-equal; `governance.doctrine:` in `charter.yaml`; two org packs; mixed stale and custom kinds; pre-rc35; synthesized artifacts with provenance; project pack skills): after ⊇ golden before, with the expected relation per fixture class of spec NFR-001 (WP01's `EXPECTED_RELATION`; `ALL_BUILTIN` expanded against the built-in inventory at comparison time): non-stale equal; stale kinds expanded to `ALL_BUILTIN`; `minimal`-equal lists equal with the formerly gated-out kinds `ALL_BUILTIN`; normalizer `[]` kinds `ALL_BUILTIN`; pre-rc35 every kind `ALL_BUILTIN` plus the `default` preset's mission types. Never edit WP01's `_effective_set.py`.
  2. NFR-004: first `spec-kitty upgrade` changes something; second changes 0 bytes over `.kittify/`, `.gitignore` and agent dirs; `detect()` False.
  3. Pre-rc35 one-shot (US2-6): 0 migration errors, effective set equals the `default` preset's. If it fails because an older migration still writes `[]` or stale lists, that is WP10's neutralisation: record and escalate rather than patching WP10's files.
  4. US2-7 (open lane worktree in `approved`, then consolidate) is an unmarked WP01 regression guard: it must stay green. The migration never touches integrating worktrees (`runner.py:81-112`); do not widen `_is_bookkeeping`.
  5. Re-run the migration on **this repository** (as in WP11/T059, direct `apply()`, dry run first). Expected: `.kittify/charter/charter.yaml` lines `activated_mission_step_contracts: []` and `activated_glossary_packs: []` (around `:2085-2086`) are removed (owner ruling); every other `activated_*` list in that file is compared and, if not a snapshot match, kept and reported. Paste the report. This **changes this repository's effective set** (all mission-step contracts and glossary packs become available): call it out in the Activity Log and the PR body so the operator can set them back to `[]` if wanted.
- **Files**: `.kittify/charter/charter.yaml`.

## Test Strategy

```bash
make test-fast
uv run --frozen pytest tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_snapshots.py tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_resets.py tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_skills.py tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_summary.py -q
uv run --frozen pytest tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_keys.py tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_paths.py -q   # WP11's, must stay green
uv run --frozen pytest tests/acceptance/charter_pack_cutover/ -q
uv run --frozen pytest tests/specify_cli/upgrade/ tests/upgrade/ tests/compat/test_dry_run_parity.py -q
uv run --frozen pytest tests/specify_cli/skills/ tests/specify_cli/asset_preservation/ -q
uv run --frozen pytest tests/architectural/test_migration_chain_integrity.py tests/architectural/test_no_dead_modules.py tests/architectural/test_charter_pack_path_authority.py tests/architectural/test_ruff_format_enforcement.py tests/architectural/test_mutation_ownership_routing.py tests/architectural/test_overwrite_ownership_routing.py -q
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen mypy src/specify_cli/upgrade/migrations/_charter_pack_cutover_snapshots.py src/specify_cli/upgrade/migrations/_charter_pack_cutover_resets.py src/specify_cli/upgrade/migrations/_charter_pack_cutover_skills.py src/specify_cli/upgrade/migrations/m_4_0_0rc6_charter_pack_cutover.py src/specify_cli/cli/commands/upgrade.py
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
```

NFR-001/NFR-004 tests may carry slow markers; run them explicitly by path. Never bare `tests/architectural/` or `make test-full`.

## Risks & Mitigations

- **Over-reset** (a customised list wrongly matched): per-key exact set equality after normalisation only; near-miss tests both directions.
- **`detect()` never false** because kept lists or kept skills count as "needed": only actionable items make `detect()` true.
- **`charter.yaml` churn**: line-level key removal; byte-compare untouched lines.
- **Skills reinstalled by the finalizer before WP18**: test the step directly; leave the end-to-end check to WP18.
- **This repo's effective set changes**: owner-ruled; reported, not hidden.

## Definition of Done

- [ ] First commit removed only the WP12 markers; red output in the Activity Log.
- [ ] Snapshot module generated from research data (digest logged); counts and sizes tested.
- [ ] Reset rules per row with report lines; `mission_type_activations` untouched; second run 0 bytes.
- [ ] Skill removal: manifested and hash-matched removed, edited kept in place and reported, no orphan manifest entries.
- [ ] Human and JSON upgrade summary, dry-run parity.
- [ ] NFR-001, NFR-004, SC-002, pre-rc35 acceptance tests green.
- [ ] Repo re-run recorded; effective-set change called out.
- [ ] mypy, ruff check, ruff format (`--force-exclude`) clean; complexity ≤ 15; follow-up edits logged.

## Review Guidance

- Red-on-base → green-on-final for every test that carried `pending_until("WP12")`.
- Spot-check the snapshot module against `research/default-yaml-snapshots.yaml` (pick two keys, compare id lists).
- Check that no comparison reads a live `default.yaml`/preset and that `mission_type_activations` is never touched.
- Check the `[]` warning text names the file and the key and says how to restore "none".
- Check edited skill copies stay in place (not archived away) and appear in `preserved_paths`.
- Check the `upgrade.py` edit is generic and small.
- Confirm mypy/ruff were run.

## Activity Log

> Entries in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-06T19:30:00Z – system – Prompt created.
