---
work_package_id: "WP09"
title: "Provisioning reads the `default` preset"
subtasks: ["T046", "T047", "T048", "T049"]
dependencies: ["WP07", "WP08", "WP10"]
requirement_refs: ["FR-003", "FR-005"]
task_type: "implement"
phase: "Phase 2 - Presets and promotion"
execution_mode: "code_change"
owned_files:
  - "src/charter/activation/compiler.py"
  - "src/specify_cli/provisioning/default_charter.py"
  - "src/specify_cli/provisioning/__init__.py"
  - "src/specify_cli/cli/commands/init.py"
  - "tests/charter/activation/test_default_preset_provisioning.py"
  - "tests/charter/test_mission_type_activations_seed_read_parity.py"
  - "tests/charter/test_compiler_charter_yaml.py"
  - "tests/specify_cli/cli/commands/test_init_provisioning.py"
  - "tests/specify_cli/cli/commands/test_init_default_preset_positive_control.py"
  - "tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py"
authoritative_surface: "src/specify_cli/provisioning/"
create_intent:
  - "tests/charter/activation/test_default_preset_provisioning.py"
  - "tests/specify_cli/cli/commands/test_init_default_preset_positive_control.py"
agent_profile: "python-pedro"
role: "implementer"
agent: "claude"
history:
  - at: "2026-10-06T19:30:00Z"
    actor: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP09 – Provisioning reads the `default` preset

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

After WP18 lands, the `/ad-hoc-profile-load` skill is deleted: load profiles with `spk-charter-profile-load` instead (use whichever exists in your checkout).

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

FR-003: skipping charter activation during `spec-kitty init` leaves the project exactly as `--preset default` would. `init`, `charter generate` and the upgrade provisioning read the mission types from the **built-in pack's `default` preset** (`packs/built-in/presets/default.yaml`, WP07), and fail closed when it is missing. FR-005 (this WP's share): no reader of `src/charter/activation/packs/default.yaml` remains in mission-type provisioning, and `charter.activation.default_pack` has no caller left, so it is deleted here; only `charter_pack_registry` (deleted by WP13) and the rc35 migration body (neutralised by WP10) may still name `default.yaml`.

- New error `DefaultPresetMissingError`, code `DEFAULT_PRESET_MISSING`, replaces `DefaultCharterPackMissingError` (no alias, C-001; data-model "Renamed identities"; contracts/errors.md).
- FR-003's positive control passes: a copied built-in pack whose `default` preset lists a different mission-type set makes `spec-kitty init` write that set (spec FR-003 "No-op passable?" column).

Done when every acceptance test marked `pending_until("WP09")` (FR-003, including the positive control) is green with the marker removed.

## Context & Constraints

- Read first: `spec.md` FR-003, FR-005, FR-002; `data-model.md` "Activation preset" (built-in presets) and "Renamed identities"; `contracts/errors.md` (`DEFAULT_PRESET_MISSING`); `research/postspec-squad-architecture.md` §A rows 6–8 (the consumers this WP repoints); `research/postspec-squad-testability.md` §B row FR-003 (positive control through the CLI, not the provisioner function).
- Upstream state: WP07 created `charter.offering.packs.presets` (`load_preset`, `PresetNotFoundError`, `PresetFormatError`, `ActivationPreset.mission_type_activations`) exported via `charter.packs`, and the preset file `packs/built-in/presets/default.yaml`. WP06 already deleted `load_default_pack_activation_ids` from `src/charter/activation/default_pack.py`; only `load_default_mission_type_activations` (and its private helpers) remain there. Verify with `grep -n "^def " src/charter/activation/default_pack.py`.
- The built-in pack root is `charter.offering.pack_paths.built_in_root()` (honours `SPEC_KITTY_PACKS_ROOT`, which is how the positive control points `init` at a copied pack). Preset file path via WP02's `kernel.charter_pack_paths.pack_presets_dir(root)` — never a literal `"presets"` join (FR-016 gate).
- Semantics that stay exactly as today: provisioning is **additive and idempotent** — it writes `mission_type_activations` only when the key is absent; an authored `[]` or any present list is left byte-for-byte (`default_charter.py:22-40` design notes; `compiler.py:652-688`). Only the **source** of the list changes.
- `charter_pack_registry` (`merge_pack_into_config`, `resolve_builtin_pack_path`) is deleted by WP13; this WP removes provisioning's dependency on it so WP13 is a pure deletion.
- C-001: no alias for `DefaultCharterPackMissingError`, no wrapper keeping `load_default_mission_type_activations` alive.

## Branch Strategy

- **Strategy**: lane-based; the lane for this WP is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Red-first (C-006 / C-011)

```bash
grep -rn 'pending_until("WP09")' tests/acceptance/charter_pack_cutover/
# remove only those markers; run; confirm red (init still copies default.yaml, so the positive control fails)
git commit -m "test(charter): flip default-preset provisioning acceptance tests red (#3732)"
```

Do not edit WP01's assertions (C-006).

## Subtasks & Detailed Guidance

### Subtask T046 – Mission-type provisioning reads the `default` preset (`init`, `charter generate`, upgrade)

- **Purpose**: one seed source for all three provisioners: the built-in `default` preset.
- **Steps**:
  1. Add the single seed-read, fail-closed, in charter (C-007): `default_preset_mission_types() -> list[str]` in `src/charter/activation/compiler.py`, next to `prepare_mission_type_activations` (owned here). `specify_cli` reaches it through `charter.activation.compiler`, as it already does for `provision_mission_type_activations`. Do not put it in WP07's `presets.py` (offering): it raises the fail-closed provisioning error and belongs with the provisioner. It:
     - loads `load_preset(built_in_root(), "default")`;
     - raises `DefaultPresetMissingError` when the preset file is absent (`PresetNotFoundError`), unreadable or malformed (`PresetFormatError`), or declares no / an empty `mission_type_activations` (an empty list in the **shipped** preset is a broken install, exactly the rule `load_default_mission_type_activations` documents today, `default_pack.py:114-140`);
     - returns the list verbatim (no catalog intersection, no re-scan — keep the "copy, not re-scan" rule from `default_charter.py:24-30`).
  2. `charter generate` and upgrade: in `src/charter/activation/compiler.py`, `prepare_mission_type_activations` (`:618-647`) — replace `load_default_mission_type_activations()` with the new reader, and replace the precondition inputs `seed = _default_pack_yaml_path(None)` (`:632-633`) with the preset file path (`pack_presets_dir(built_in_root()) / "default.yaml"`, via the kernel helper), so the prepared-write CAS still observes the real seed file. Delete the module-level `from charter.activation.default_pack import load_default_mission_type_activations` (`:38`) and the lazy `_default_pack_yaml_path` import (`:620`). Update the docstrings at `:652-688` (they name `src/charter/activation/packs/default.yaml`).
  3. `init`: `src/specify_cli/provisioning/default_charter.py` — `_load_default_pack_activations` (`:87-124`) becomes a call to the new reader; delete `_DEFAULT_PACK_NAME`, the `resolve_builtin_pack_path` / `merge_pack_into_config` imports (`:51-54`) and the registry-based path resolution. Replace `merge_pack_into_config(config_data, {key: list}, force=False)` (`:166-170`) with the equivalent explicit additive write: if `mission_type_activations` is absent, set it and dump; else return `False` without touching the file. Rewrite the module docstring (`:1-40`): the surface is the built-in `default` preset; drop the rc35/registry narrative.
  4. The upgrade path (`src/specify_cli/cli/commands/upgrade.py:445-506`, `_provision_mission_type_activations_for_upgrade` or similarly named) calls `provision_mission_type_activations` and catches `CharterPackConfigError`, returning `exc.body`. Make it also catch `DefaultPresetMissingError` the same way (T047). `upgrade.py` is owned by WP12, which runs after you (WP12 depends on WP09): keep the edit to that `except` clause and the docstring lines `:466-483` that name `default_pack`; log it as a follow-up edit with rationale.
  5. `src/specify_cli/upgrade/assessment.py:127` and the two skill installers (`skills/installer.py:371`, `skills/command_installer.py:835`) consume `prepare_mission_type_activations`; they need no change, but run their tests (they compare prepared writes, which now observe the preset file).
- **Files**: `compiler.py`, `default_charter.py`; logged edit in `upgrade.py`.
- **Parallel?**: No; T047 defines the error it raises.
- **Validation**: `grep -rn "default_pack\|charter_pack_registry" src/charter/activation/compiler.py src/specify_cli/provisioning/` returns nothing.

### Subtask T047 – `DefaultPresetMissingError` / `DEFAULT_PRESET_MISSING` replaces `DefaultCharterPackMissingError`

- **Purpose**: one fail-closed error, one stable code, for all three provisioners.
- **Steps**:
  1. Define `DefaultPresetMissingError` once, where `charter` can raise it and `specify_cli` can catch it: subclass `kernel.errors.KittyInternalConsistencyError` with `code = "DEFAULT_PRESET_MISSING"` and a `body` naming the preset path and the remedy ("reinstall spec-kitty"). Put it beside the reader from T046 (charter). Do not subclass `CharterPackConfigError` (that type is renamed by WP17 and means "invalid active charter", not "broken install").
  2. Delete `DefaultCharterPackMissingError` from `src/specify_cli/provisioning/default_charter.py` (`:76-84`) and from `src/specify_cli/provisioning/__init__.py` (`:17,22` exports; keep `__all__` honest). Re-export nothing.
  3. `src/specify_cli/cli/commands/init.py:48-49,1402-1415`: import and catch `DefaultPresetMissingError`; print `Error (DEFAULT_PRESET_MISSING): <body>` and exit 1 (same flow as today). Update the comment block at `:1402-1410` ("shipped default charter pack" → "the built-in pack's `default` preset"; this phrase is also an FR-018 forbidden token).
  4. `charter generate` (`src/specify_cli/cli/commands/charter/generate.py:495-502`) calls `provision_mission_type_activations(repo_root)`. Check how its outer handler (`:616-635`) renders a `KittyInternalConsistencyError`; if it does not surface the code, add the narrowest handling that prints `DEFAULT_PRESET_MISSING` and exits 1 — `generate.py` is not owned by this WP; log the edit. Update its comment at `:499` ("built-in set from default.yaml").
- **Files**: `default_charter.py`, `provisioning/__init__.py`, `init.py`; logged edits in `generate.py`, `upgrade.py`.
- **Parallel?**: With T046.
- **Validation**: `grep -rn "DefaultCharterPackMissingError" src/ tests/` returns nothing.

### Subtask T048 – Repoint remaining `default.yaml` readers from the research inventory

- **Purpose**: after this WP, `charter.activation.default_pack` has no caller and is deleted; no runtime reader of `src/charter/activation/packs/default.yaml` remains except `charter_pack_registry` (WP13) and the rc35 migration (WP10 neutralises it).
- **Steps**:
  1. Inventory first (record the output in the Activity Log):
     ```bash
     grep -rn "default_pack\|packs/default.yaml\|default\.yaml\|load_default_mission_type_activations" src/ tests/ --include=*.py
     ```
     Expected live readers at this point: `compiler.py` (T046), `default_charter.py` (T046), tests `tests/charter/test_mission_type_activations_seed_read_parity.py:40-121`, `tests/charter/test_compiler_charter_yaml.py:35-201`, `tests/charter/test_mission_type_activation_emit.py` (WP06 pointed it at `load_default_mission_type_activations`), `tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py:418-428` (monkeypatches `charter.activation.compiler.load_default_mission_type_activations`).
  2. Repoint each test to the new reader / the `default` preset; `test_mission_type_activation_emit.py` is owned by WP06 (completed upstream) — a mechanical rename follow-up, log it. The seed/read parity test keeps its purpose (init and generate seed the same list) with the preset as the source; its "missing / broken / empty pack" cases become "missing / malformed / empty `default` preset" cases raising `DefaultPresetMissingError`, built by pointing `SPEC_KITTY_PACKS_ROOT` at a tmp copy of the built-in pack.
  3. Delete `src/charter/activation/default_pack.py` once `grep -rn "charter.activation.default_pack\|from charter.activation import default_pack" src/ tests/` is empty (`tests/architectural/test_no_dead_modules.py` and `test_no_dead_symbols.py` would otherwise flag it). The file is owned by WP06 (completed upstream); deleting a module whose last caller this WP repointed is a follow-up allowed by the tasks.md rule — log it. Note for WP13: T066's "delete `default_pack`" is then already done; WP13 only verifies it.
  4. Docstring-only mentions in files this WP does not own (`charter/activation/schemas.py:368,378`, `charter/activation/charter_yaml_io.py:439`, `upgrade/migrations/m_3_2_0rc35_activate_builtin_mission_types.py:40-46`, `m_3_2_6_retire_rtk_search_tooling.py:5`, `m_4_0_0rc5_retire_single_owner_doctrine_ids.py:28`): leave them; list them in the Activity Log for the prose/rename WPs (the FR-018 gate in WP25 forces them). Do not edit frozen migration bodies here.
  5. `src/specify_cli/provisioning/__init__.py:9` docstring names `default.yaml`: fix it (owned).
- **Files**: tests in `owned_files`; logged deletion of `default_pack.py`; logged edit in `test_mission_type_activation_emit.py`.
- **Parallel?**: After T046/T047.

### Subtask T049 – Tests with the positive control; flip FR-003 xfails

- **Steps**:
  1. `tests/charter/activation/test_default_preset_provisioning.py` (new): the reader returns the preset's list; missing preset file, malformed YAML, preset without the key, preset with `[]` → `DefaultPresetMissingError` with code `DEFAULT_PRESET_MISSING` (each via a tmp copy of `packs/built-in` and `SPEC_KITTY_PACKS_ROOT`); `prepare_mission_type_activations` on a project lacking the key prepares the preset's list and observes the preset file as an input; present key / authored `[]` untouched.
  2. `tests/specify_cli/cli/commands/test_init_default_preset_positive_control.py` (new): **through the `spec-kitty init` CLI**, not the provisioner function (testability squad, FR-003 row): copy `packs/built-in` to tmp, rewrite its `presets/default.yaml` `mission_type_activations` to a different valid set (for example `[software-dev, research]`), point `SPEC_KITTY_PACKS_ROOT` at it, run `init` non-interactively into a fresh dir (copy the invocation style of existing init CLI tests; skip agent setup flags as they do), assert `.kittify/config.yaml` carries exactly that set. Same test with the untouched copy asserts the shipped list (the negative half). Third case: remove the preset file → exit 1, output contains `DEFAULT_PRESET_MISSING`, no `mission_type_activations` written.
  3. FR-003 equivalence: on a freshly `init`-ed project (agents skipped), read the activation state; apply the `default` preset's governed-key rules (no per-kind keys, no `activated_kinds`, the preset's mission types) and assert equality — "init equals `--preset default`". WP08 is upstream (WP09 depends on it): also run `charter activate --preset default` on the same project and assert 0 bytes change. The acceptance test `test_fr003_init_without_activation_equals_default_preset` drives the same comparison through the CLI.
  4. Update `tests/specify_cli/cli/commands/test_init_provisioning.py` (`:46-47,148-166`: `DefaultCharterPackMissingError` → `DefaultPresetMissingError`; monkeypatches of the registry path → `SPEC_KITTY_PACKS_ROOT` copies). Note: WP10 (upstream; WP09 depends on it) has already deleted the rc35 identity test in this file (`test_rc35_default_charter_pack_migration_identity_and_idempotence_unchanged`, `:320-349`) because it turned that migration into a recorded no-op; do not re-add or rewrite it.
  5. Update `tests/charter/test_compiler_charter_yaml.py` and `tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py` (`:418-428` monkeypatch target) to the new reader.
  6. Remove `pending_until("WP09")` markers (red-first commit) and turn them green.

## Test Strategy

```bash
make test-fast
uv run --frozen pytest tests/acceptance/charter_pack_cutover/ -q
uv run --frozen pytest tests/charter/activation/test_default_preset_provisioning.py tests/charter/test_mission_type_activations_seed_read_parity.py tests/charter/test_compiler_charter_yaml.py tests/charter/test_mission_type_activation_emit.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/test_init_provisioning.py tests/specify_cli/cli/commands/test_init_default_preset_positive_control.py tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py -q
uv run --frozen pytest tests/specify_cli/upgrade/ tests/specify_cli/skills/ -q     # assessment + installer consumers of prepare_mission_type_activations
uv run --frozen pytest tests/charter/ -q
uv run --frozen pytest tests/architectural/test_no_dead_modules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_charter_no_specify_cli_import.py tests/architectural/test_layer_rules.py tests/architectural/test_charter_pack_path_authority.py -q
uv run --frozen ruff check src/charter/activation/compiler.py src/specify_cli/provisioning/ src/specify_cli/cli/commands/init.py src/specify_cli/cli/commands/upgrade.py src/specify_cli/cli/commands/charter/generate.py tests/charter/ tests/specify_cli/cli/commands/
uv run --frozen ruff format --check --force-exclude <every file you touched>
uv run --frozen mypy src/charter/activation/compiler.py src/specify_cli/provisioning/ src/specify_cli/cli/commands/init.py
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
```

If `tests/specify_cli/skills/` does not exist under that name, run the test files that `grep -rln prepare_mission_type_activations tests/` returns. `src/charter/offering/**` is untouched unless you put the reader in the facade; if you do, add `tests/doctrine/`. Record commands and counts in the Activity Log.

## Commit discipline

Conventional subjects with `#3732`: `refactor(charter): mission types seeded from the default preset (#3732)`, `refactor(provisioning): DefaultPresetMissingError replaces DefaultCharterPackMissingError (#3732)`, `refactor(charter): delete default_pack (#3732)`. First commit is the red flip. Never push to `main`.

## Risks & Mitigations

- **Prepared-write CAS input drift**: `prepare_mission_type_activations` records its seed file as an observed input; the skill installers compare prepared writes (`installer.py:371`). Point the observation at the preset file in the same commit as the source switch.
- **`SPEC_KITTY_PACKS_ROOT` in tests leaking**: use `monkeypatch.setenv`, never `os.environ` directly.

## Definition of Done

- [ ] Red-first commit; every `pending_until("WP09")` test green, positive control included.
- [ ] `init`, `charter generate`, upgrade provisioning read the built-in `default` preset; fail closed with `DEFAULT_PRESET_MISSING`.
- [ ] `DefaultCharterPackMissingError` gone everywhere; no alias.
- [ ] `charter.activation.default_pack` deleted; provisioning imports nothing from `charter_pack_registry`.
- [ ] Inventory grep recorded; remaining docstring mentions listed for later WPs.
- [ ] All Test Strategy commands run and recorded; ruff/format/mypy clean, no new suppressions; out-of-ownership edits logged.

## Review Guidance

- Red on base → green on final for every acceptance test naming WP09; markers removed, assertions unchanged.
- Run the positive control by hand: copied pack with a different mission-type set → `init` writes that set.
- `grep -rn "default_pack\|DefaultCharterPackMissing" src/ tests/` is empty.
- Confirm the "additive, never overwrites an authored list" behaviour is unchanged (existing tests still pass).
- Confirm mypy ran on touched typed sources.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Initial entry**:

- 2026-10-06T19:30:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
