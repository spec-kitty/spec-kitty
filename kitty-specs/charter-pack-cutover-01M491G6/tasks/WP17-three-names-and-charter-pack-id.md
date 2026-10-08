---
work_package_id: "WP17"
title: "Three meanings, three names; `charter_pack_id`"
subtasks: ["T083", "T084", "T085", "T086", "T087"]
dependencies: ["WP05"]
requirement_refs: ["FR-009", "FR-010"]
task_type: "implement"
phase: "Phase 5 - Names"
execution_mode: "code_change"
owned_files:
  - "src/charter/offering/packs/retired_fields.py"
  - "tests/charter/test_retired_pack_fields.py"
  - "src/charter/activation/pack_context.py"
  - "src/charter/activation/activations.py"
  - "src/charter/activation/consistency_check.py"
  - "src/charter/activation/scope.py"
  - "src/charter/activation/context_renderers/template_include.py"
  - "src/charter/activation/ERROR_CODES.md"
  - "src/charter/offering/spdd_reasons/activation.py"
  - "src/charter/offering/missions/mission_type_repository.py"
  - "src/runtime/next/decision.py"
  - "src/runtime/next/prompt_builder.py"
  - "src/specify_cli/charter_activate.py"
  - "src/specify_cli/cli/commands/agent/mission_create.py"
  - "src/specify_cli/cli/commands/agent/tasks_status_cmd.py"
  - "src/specify_cli/cli/commands/charter/deactivate.py"
  - "src/specify_cli/core/mission_creation.py"
  - "src/specify_cli/core/mission_creation_scaffold.py"
  - "src/specify_cli/tool_surface/enums.py"
  - "src/specify_cli/tool_surface/bundles/claude.py"
  - "src/specify_cli/tool_surface/bundles/copilot.py"
  - "src/specify_cli/tool_surface/bundles/projection.py"
  - "src/specify_cli/tool_surface/providers/managed_skills.py"
  - "src/specify_cli/skills/installer.py"
  - "src/specify_cli/skills/command_installer.py"
  - "src/specify_cli/upgrade/assessment.py"
  - "src/specify_cli/.contextive/execution.yml"
  - "docs/context/execution.md"
  - "docs/configuration/yaml-libraries.md"
  - "docs/api/orchestrator-api.md"
  - "tests/_factories/__init__.py"
  - "tests/architectural/test_json_contract_enumeration.py"
  - "tests/charter/test_activation_authority.py"
  - "tests/charter/test_activations.py"
  - "tests/charter/test_charter_scope_config_reader.py"
  - "tests/charter/test_charter_yaml_model.py"
  - "tests/charter/test_cli_boundary_config_mapping.py"
  - "tests/charter/test_context_activation_render.py"
  - "tests/charter/test_context_include.py"
  - "tests/charter/test_context_org_governance.py"
  - "tests/charter/test_context_render_seams.py"
  - "tests/charter/test_issue_5409_anti_pattern_activation.py"
  - "tests/charter/test_mission_type_activation_gating.py"
  - "tests/charter/test_org_activations_reach_context.py"
  - "tests/charter/test_org_activations_resolution.py"
  - "tests/charter/test_org_scan_dirs_activation_regression.py"
  - "tests/charter/test_pack_context.py"
  - "tests/charter/test_pack_context_charter_yaml.py"
  - "tests/charter/test_schemas_selection.py"
  - "tests/charter/test_tension_cascade_exclusion.py"
  - "tests/cli/test_mission_type_malformed_yaml_cli_boundary.py"
  - "tests/core/golden/mission_create_refusals.json"
  - "tests/core/test_mission_create_activation_gate.py"
  - "tests/core/test_mission_creation_decomposition.py"
  - "tests/core/test_mission_creation_owned_charter.py"
  - "tests/integration/test_user_doctrine_artifact_lifecycle.py"
  - "tests/next/test_cli_boundary_scope_config_4600.py"
  - "tests/specify_cli/cli/commands/agent/test_mission_create.py"
  - "tests/specify_cli/cli/commands/agent/test_mission_create_json_remediation.py"
  - "tests/specify_cli/cli/commands/charter/test_charter_activate_commands_cascade_flags.py"
  - "tests/specify_cli/cli/commands/charter/test_charter_activate_commands_cascade_output.py"
  - "tests/specify_cli/cli/commands/charter/test_charter_activate_commands_core.py"
  - "tests/specify_cli/cli/commands/charter/test_charter_deactivate_commands.py"
  - "tests/specify_cli/cli/commands/charter/test_charter_list_commands.py"
  - "tests/specify_cli/skills/test_crlf_skill_render_4998.py"
  - "tests/specify_cli/skills/test_installer.py"
  - "tests/specify_cli/test_charter_activate_cli.py"
  - "tests/specify_cli/test_requirement_mapping.py"
  - "tests/specify_cli/tool_surface/bundles/_support.py"
  - "tests/specify_cli/tool_surface/bundles/test_claude.py"
  - "tests/specify_cli/tool_surface/integration/test_doctor_tool_surfaces_cli.py"
  - "tests/specify_cli/tool_surface/integration/test_migration_compat.py"
  - "tests/specify_cli/tool_surface/providers/test_managed_skills.py"
  - "tests/specify_cli/tool_surface/providers/test_plugin_bundle.py"
  - "tests/specify_cli/tool_surface/test_docs.py"
  - "tests/specify_cli/tool_surface/test_registry.py"
authoritative_surface: "src/charter/activation/"
create_intent:
  - "src/charter/offering/packs/retired_fields.py"
  - "tests/charter/test_retired_pack_fields.py"
agent_profile: "python-pedro"
role: "implementer"
agent: "claude"
history:
  - at: "2026-10-06T19:30:00Z"
    actor: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP17 – Three meanings, three names; `charter_pack_id`

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

(If WP18 has already landed, the skill is named `spk-charter-profile-load`.)

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

The code stops using one word for three things (FR-009, ADR 2026-10-06-1 §1). The renames are fixed by `data-model.md` "Renamed identities" and `contracts/errors.md`:

| Before | After |
|---|---|
| `CharterPackManager` | `ActiveCharterManager` |
| `CharterPackConfigError` | `ActiveCharterConfigError` |
| `CHARTER_PACK_CONFIG_INVALID` | `ACTIVE_CHARTER_CONFIG_INVALID` |
| `doctrine_pack_id` (activation entries, OD-1) | `charter_pack_id` |
| `ToolSurfaceKind.DOCTRINE_SKILL = "doctrine_skill"` | `ToolSurfaceKind.CHARTER_SKILL = "charter_skill"` |

Done means:

- No re-export alias, no `X = Y` binding, no pydantic alias or `populate_by_name` for any old name (C-001). `rg -nw "CharterPackManager|CharterPackConfigError|CHARTER_PACK_CONFIG_INVALID|DOCTRINE_SKILL|doctrine_skill" src tests docs packs` (excluding historical roots and the cutover migration module) is empty.
- The JSON code string has **one** source: `charter/mission_type.py`'s hard-coded literal (today l.143) reads `exc.code`.
- Golden `tests/core/golden/mission_create_refusals.json` carries the new code; `src/charter/activation/ERROR_CODES.md` documents `ACTIVE_CHARTER_CONFIG_INVALID`.
- `ActivationEntry.charter_pack_id` replaces `doctrine_pack_id`; the org-charter `schema_version` is bumped; an `org-charter.yaml` (or project `charter.yaml`) activation entry that still carries `doctrine_pack_id` is rejected with `RETIRED_PACK_FIELD`, naming the field and its replacement (OD-1, `contracts/errors.md`).
- The WP01 acceptance tests marked `pending_until("WP17")` (FR-009, including the `doctor tool-surfaces --kind charter-skill --json` shape, and `test_us3_4_doctrine_pack_id_rejected_in_org_charter`) go from red to green. `test_fr010_charter_pack_id_in_project_state` is **not** yours: it needs WP11's migration, which runs after you.

`DefaultCharterPackMissingError` → `DefaultPresetMissingError` is **WP09's** (T047), not this WP's.

## Context & Constraints

- Read: `.kittify/charter/charter.md`; `spec.md` FR-009, FR-010, OD-1, C-001, FR-018 forbidden-token list; `data-model.md` "Renamed identities"; `contracts/errors.md`; `research/runtime-seams.md` §6 (every emitter, catcher, test and golden with file:line); `occurrence_map.yaml` (`code_symbols`, `serialized_keys`, `logs_telemetry` all `rename`).
- **Upstream**: WP05 moved org charter composition to `src/charter/activation/org_charter.py` (from `src/specify_cli/doctrine/org_charter.py`) and pack lineage to `src/charter/offering/packs/pack_lineage.py`. WP11 runs **after** you (it depends on WP17): it writes `charter_pack_id` into project `charter.yaml`, which your model must already accept. Do not wait for it.
- **Ownership.** You run after WP05 and before every WP that uses your names. The files listed under "Files you will touch but do not own" are owned by upstream WPs (WP02–WP05) or by downstream WPs (WP06 onward) that cannot run in parallel with you (tasks.md rule): edit them, rename only, and log each. Do not wait for their owners. The one WP that can run beside you is WP10: never edit a file WP10 owns (the `m_*` migrations listed in its frontmatter); if one carries an old name, record it in the Activity Log.
- **This WP creates** `src/charter/offering/packs/retired_fields.py` (WP17 now runs right after WP05, before WP11 and WP13): `RETIRED_PACK_FIELD = "RETIRED_PACK_FIELD"` (the code string's only source); `@dataclass(frozen=True) class RetiredField: file: str; field: str; replacement: str`; `RETIRED_PACK_FIELDS` with the one entry `RetiredField(file="org-charter.yaml", field="doctrine_pack_id", replacement="charter_pack_id")` (WP13 later adds `accompanies_doctrine_pack` as a one-line addition); `class RetiredPackFieldError(ValueError)` with `code`, `file`, `field`, `replacement` and the message `<path>: field '<field>' was removed. <replacement>. See docs/migrations/charter-pack-cutover.md.`; and `reject_retired_fields(raw, *, file, path)`. It lives in `charter.offering.packs` (no import of `charter.activation`). Tests in `tests/charter/test_retired_pack_fields.py` (data-driven: a planted second entry is rejected the same way; positive control: an unrelated unknown field still fails with pydantic's generic error).
- **Ordering**: this WP runs early (after WP05), so the files it renames in have not yet been changed by WP06–WP16; those WPs build on the new names. Line numbers below were measured before those WPs and will still hold.
- C-001: no aliases. Validation diagnostics that name a replacement are allowed (that is what `RETIRED_PACK_FIELD` is).
- Code style: ruff + mypy clean; `ruff format --check --force-exclude`; complexity ≤ 15; no new suppressions.

### Files you will touch but do not own (mechanical follow-ups; log each in the Activity Log)

Owned by upstream or sibling WPs; edit only the renamed token and its docstring mention:

- `CharterPackManager` definition `src/charter/activation/pack_manager.py:701` (and `__all__` l.116) — WP02/WP06. Users: `src/charter/activation/activation_engine.py:5` (WP06), `src/charter/activation/mission_type_profiles.py:1010` (WP14), `src/specify_cli/cli/commands/charter/activate.py:51,226,287,888` (WP08), `src/charter/activation/layer_roots.py` (moved by WP02 from `cli/commands/charter/_layer_roots.py:46`).
- `CharterPackConfigError` catchers: `src/charter/activation/compiler.py:680` (WP09), `src/specify_cli/cli/commands/charter/activate.py:50,103-111,851` (WP08), `src/specify_cli/cli/commands/charter/mission_type.py:33,138-143` (WP15), `src/specify_cli/cli/commands/upgrade.py:499-1072` (WP12), `src/specify_cli/provisioning/default_charter.py:51,119` (WP09), `src/specify_cli/analysis_inputs.py:146,155` (WP14), `src/specify_cli/charter_runtime/lint/checks/org_layer.py` (WP05), `src/specify_cli/tool_surface/providers/agent_profiles.py:30,116,196` (WP02).
- `doctrine_pack_id`: `src/charter/activation/org_charter.py` (WP05; formerly `specify_cli/doctrine/org_charter.py:179,677`), `src/charter/offering/packs/pack_lineage.py` (WP04; formerly `:210`), `docs/context/charter.md` (WP24's glossary file: only replace the field spelling).
- `src/specify_cli/cli/commands/charter/list_cmd.py:17,197,331-341` (WP02), `src/specify_cli/cli/commands/charter/synthesize.py:688` (WP03; comment naming the old code).
- Tests owned elsewhere: `tests/agent/cli/commands/test_charter_synthesize_cli.py:456` (WP03), `tests/charter/test_activation_engine_charter_yaml.py:154` (WP06), `tests/charter/test_compiler_charter_yaml.py:276` (WP09), `tests/charter/test_mission_type_activations_seed_read_parity.py` (WP09), `tests/charter/test_skill_activation.py` (WP06), `tests/cli/commands/test_charter_rendering.py` (WP05), `tests/specify_cli/cli/commands/charter/test_resynthesize_and_hotpath.py` (WP03/WP06), `tests/charter/test_pack_manager.py`, `tests/charter/test_pack_manager_catalog.py`, `tests/charter/test_activation_preserves_effective_4253.py`, `tests/charter/test_mission_type_path_layout_ssot.py`, `tests/specify_cli/cli/commands/charter/test_org_cascade_chain.py`, `tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py`, `tests/architectural/dead_symbol_allowlist.yaml`, `tests/architectural/charter_path_literal_allowlist.yaml`, `tests/doctrine/test_activation_parity_guard.py` (WP23 later moves `tests/doctrine/`).

## Branch Strategy

- **Strategy**: lane per `lanes.json` (filled by finalize)
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Red-first commit (C-006 / C-011)

First commit: remove the `pending_until("WP17")` markers from the WP01 acceptance tests (rename cases written by WP01 T008: FR-009 class/code names, `charter_pack_id`, `CHARTER_SKILL`; any FR-010 case that names `doctrine_pack_id`):

```bash
rg -n 'pending_until\("WP17"\)' tests/acceptance/charter_pack_cutover/
```

Run them; confirm red. Commit `test(acceptance): unmark WP17 FR-009 tests (red) (#3732)`. Do not change assertions (C-006).

## Subtasks & Detailed Guidance

### Subtask T083 – `ActiveCharterManager`, `ActiveCharterConfigError`

- **Purpose**: name the project's activation configuration as the **active charter**, not a pack (ADR §1).
- **Steps**:
  1. `src/charter/activation/pack_context.py:63-67`: rename the class to `ActiveCharterConfigError`; update its docstring ("Raised when the active charter configuration (`.kittify/config.yaml` or the pointed `charter.yaml`) has an invalid shape."); `__all__` (l.40). The code string changes in T084.
  2. Rename every raiser: `pack_context.py:294-300` `_config_error`; `pack_manager.py:651,659` (follow-up); `consistency_check.py:309,337,341,343`; `scope.py:265`; `src/specify_cli/core/mission_creation_scaffold.py:142`. (`default_pack.py:150` is deleted by WP09.)
  3. Rename every catcher (research §6 list): `src/runtime/next/decision.py:28,711`, `prompt_builder.py:27,518`; `cli/commands/agent/mission_create.py:492,542`; `cli/commands/charter/deactivate.py:41,295`; `list_cmd.py` (l.331-341 comments); `agent/tasks_status_cmd.py:972,1125` (comments); `core/mission_creation.py:554` (docstring); `charter/activation/context_renderers/template_include.py`; `charter/offering/spdd_reasons/activation.py`; `src/charter/activation/consistency_check.py:26,1582`; plus the not-owned follow-ups listed above.
  4. `CharterPackManager` → `ActiveCharterManager`: definition `pack_manager.py:701` (follow-up), users `consistency_check.py:27,371,1579`, `deactivate.py:42,114,158,301`, `list_cmd.py:17,197`; docstrings in `mission_type_repository.py:455`, `spdd_reasons/activation.py:98`, `src/specify_cli/charter_activate.py:10`.
  5. Rename locals that carry the old meaning where touched (`pack_manager` variables holding an `ActiveCharterManager` → `charter_manager`), but do not widen into unrelated renames (that is WP19–WP21).
  6. `rg -nw "CharterPackManager|CharterPackConfigError" src docs` → only historical roots remain (`docs/changelog/CHANGELOG.md:1765,2938` are released sections; leave them).
- **Files**: owned src files above; follow-ups listed.
- **Parallel?**: T086 is independent and can be done first.
- **Notes**: mypy catches missed imports; run it on every touched module. `tests/_factories/__init__.py:21` imports the class for fixtures: update it in the same commit or collection breaks widely.
- **Validation**: [ ] `uv run mypy` on touched modules clean; [ ] `uv run pytest tests/charter/test_pack_context.py tests/charter/test_pack_context_charter_yaml.py -q` green after T084.

### Subtask T084 – `ACTIVE_CHARTER_CONFIG_INVALID`; golden; `ERROR_CODES.md`

- **Purpose**: the JSON error code follows the class (FR-009), with one literal in the codebase.
- **Steps**:
  1. `pack_context.py`: `super().__init__("ACTIVE_CHARTER_CONFIG_INVALID", body)`. Hoist the literal to a module constant (e.g. `ACTIVE_CHARTER_CONFIG_INVALID = "ACTIVE_CHARTER_CONFIG_INVALID"`, exported) only if a second reader needs it; otherwise readers use `exc.code`.
  2. `src/specify_cli/cli/commands/charter/mission_type.py:138-143` (`mission_type_error_boundary`): replace `code = "CHARTER_PACK_CONFIG_INVALID"` with `code = exc.code` (follow-up in a WP15-owned file; log it).
  3. `cli/commands/charter/activate.py:106` (`render_pack_config_error`) calls the code a "stable diagnostic code": update the docstring/message to the new code (follow-up, WP08 file).
  4. Golden `tests/core/golden/mission_create_refusals.json:598-601` (`malformed_config_invalid_yaml`): `"exc_type": "ActiveCharterConfigError"`, `"message": "ACTIVE_CHARTER_CONFIG_INVALID"`. Regenerate through the golden's own updater if one exists (`rg -n mission_create_refusals tests/core`), else edit by hand; then run its test.
  5. Code-string asserts (research §6): `tests/charter/test_pack_context.py:468,481,489`, `test_pack_context_charter_yaml.py:206,216,226,235,351`, `test_activation_engine_charter_yaml.py:154`, `test_compiler_charter_yaml.py:276`, `test_context_include.py:304`, `tests/core/test_mission_create_activation_gate.py:56,60,73`, `tests/next/test_cli_boundary_scope_config_4600.py:55`, `tests/specify_cli/cli/commands/agent/test_mission_create_json_remediation.py:1,6,82,87,89`, `tests/specify_cli/cli/commands/charter/test_charter_list_commands.py:421,423`, `tests/specify_cli/test_charter_activate_cli.py:10,322,331`, `tests/agent/cli/commands/test_charter_synthesize_cli.py:456`, and `tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py:215` (follow-up, WP09).
  6. `src/charter/activation/ERROR_CODES.md`: today it is a hand mirror of the `CharterEncodingDiagnostic` StrEnum (header note, NFR-008 section count). Add a separate top-level part, e.g. `# Activation configuration codes` with a `## ACTIVE_CHARTER_CONFIG_INVALID` section (when it fires, JSON stability, remediation: fix the YAML shape in `.kittify/config.yaml` / `charter.yaml`, `spec-kitty charter list --json` to confirm, payload shape unchanged). Adjust the header so the StrEnum-mirror rule clearly scopes to the encoding part. Check no test counts all `##` sections of this file: `rg -n "activation/ERROR_CODES" tests` (none today).
  7. `docs/api/orchestrator-api.md:343` (pass-through upstream code) and `docs/configuration/yaml-libraries.md`: new names.
  8. Leave `docs/changelog/CHANGELOG.md` alone: the Before/After row is WP24's (FR-017). Note in the Activity Log the exact Before/After pairs for WP24 (class names, code, `doctrine_pack_id`, `doctrine_skill`, the `--kind doctrine-skill` token).
- **Files**: `pack_context.py`, `ERROR_CODES.md`, golden, tests, docs listed.
- **Parallel?**: After T083.
- **Validation**: [ ] `rg -n "CHARTER_PACK_CONFIG_INVALID" src tests docs -g '!docs/changelog/**'` empty; [ ] `uv run pytest tests/core/ -q -k "refusal or activation_gate or creation"` green.

### Subtask T085 – `charter_pack_id` in models, schemas, org-charter `schema_version` bump, validator message

- **Purpose**: OD-1 — the activation entry names the Charter Pack it draws from.
- **Steps**:
  1. `src/charter/activation/activations.py:217`: `ActivationEntry.doctrine_pack_id: str` → `charter_pack_id: str`; keep `model_config = ConfigDict(extra="forbid")`; update the module docstring (l.6), the YAML example (l.202), the identity-tuple docs (l.274) and the accessor at l.290. No pydantic `alias`, no `populate_by_name`.
  2. Retired-field rejection: add a `model_validator(mode="before")` on `ActivationEntry` that, when the raw mapping contains `doctrine_pack_id`, raises the `RETIRED_PACK_FIELD` error from `retired_fields.py` naming file context where available, the field `doctrine_pack_id` and the replacement `charter_pack_id` (data-model.md "Charter Pack"; `contracts/errors.md`). This runs for both the project `charter.yaml` (`GovernanceConfig.activations`) and org packs (`OrgCharterPolicy.activations`). Keep the validator small; put the message construction in a helper you test directly.
  3. `src/charter/activation/org_charter.py` (WP05's moved module; follow-up): `OrgCharterPolicy.schema_version` default `1` → `2` with a docstring line: "2 (#3732): activation entries use `charter_pack_id`; `doctrine_pack_id` is rejected." Decide and record whether a file that declares `schema_version: 1` and **no** activations still validates (recommended: yes — the version documents the format; the field-level rejection is what enforces OD-1; only a `doctrine_pack_id` key fails). Update the identity-tuple docstrings (old l.179, l.677). `charter org init` scaffolding (WP15/WP07 home) should emit `schema_version: 2`: check `rg -n "schema_version" src/specify_cli/cli/commands/charter` and follow up.
  4. Validator message: `charter pack validate` / `charter org validate` (the validator moved by WP04 to `src/charter/offering/packs/pack_validator.py`, org-charter leg via `charter.activation.org_charter.validate_org_charter_file`, WP04 A.3 #4) must surface `RETIRED_PACK_FIELD` for `doctrine_pack_id` as a named issue, not a generic pydantic "extra field" error. Add the mapping in the validator so WP13 can reuse it for `accompanies_doctrine_pack` (follow-up in the WP04/WP05 module; log it).
  5. `src/charter/offering/packs/pack_lineage.py` docstring (old l.210) and `docs/context/charter.md` field spelling: follow-ups.
  6. Persisted state: WP11's migration (after you) rewrites project `charter.yaml`; your model must accept `charter_pack_id` before that. Packs in this repository: `packs/internal/org-charter.yaml` has no activations and no `schema_version` today; bump it only if the validator requires the new version (record either way). `rg -n doctrine_pack_id packs` must stay empty.
  7. Tests: `tests/charter/test_activations.py`, `test_charter_yaml_model.py`, `test_context_activation_render.py`, `test_context_org_governance.py`, `test_context_render_seams.py`, `test_issue_5409_anti_pattern_activation.py`, `test_org_activations_reach_context.py`, `test_org_activations_resolution.py`, `test_schemas_selection.py`, `tests/cli/commands/test_charter_rendering.py`, `tests/integration/test_user_doctrine_artifact_lifecycle.py`: rename the key in fixtures. Add focused tests: (a) an entry with `charter_pack_id` validates; (b) an entry with `doctrine_pack_id` fails with `RETIRED_PACK_FIELD` naming both names, for the project model and for `OrgCharterPolicy`; (c) `charter org validate` on a pack whose `org-charter.yaml` carries `doctrine_pack_id` exits non-zero and prints the field and its replacement (US3 scenario 4).
- **Files**: `activations.py`, tests above; follow-ups `org_charter.py`, validator, lineage, glossary spelling.
- **Parallel?**: Independent of T083/T084.
- **Notes**: the activation identity tuple `(activation_context, charter_pack_id, artifact_id, artifact_kind)` is used for dedup in the cross-pack merge; rename the tuple field everywhere so ordering and equality are unchanged (byte-identical merge output).
- **Validation**: [ ] `rg -nw doctrine_pack_id src tests packs docs -g '!docs/adr/**' -g '!docs/archive/**' -g '!docs/plans/**'` shows only the retired-field validator, its tests and the cutover migration module.

### Subtask T086 – `ToolSurfaceKind.CHARTER_SKILL`

- **Purpose**: the managed-skill surface kind stops saying "doctrine" (occurrence map C15, `logs_telemetry: rename`).
- **Steps**:
  1. `src/specify_cli/tool_surface/enums.py:22`: `CHARTER_SKILL = "charter_skill"`; delete the old member (no alias member).
  2. Users: `tool_surface/bundles/claude.py:75,85`, `bundles/copilot.py:40,49`, `bundles/projection.py:202,227`, `providers/managed_skills.py:221,261,763` (surface id f-string), `upgrade/assessment.py:138,151`.
  3. `providers/managed_skills.py:751` `doctrine_skill_entries` → `charter_skill_entries`; `:790` operator `--kind` token `"doctrine-skill"` → `"charter-skill"` (CLI token change: record it for WP24's Before/After).
  4. `skills/installer.py:590` surface-id f-string `.doctrine_skill.` → `.charter_skill.`; `skills/command_installer.py:505-547` prose "doctrine skills"/"doctrine-skill provider" → "charter skills"/"charter-skill provider".
  5. Are surface ids persisted? Check `rg -n "doctrine_skill|charter_skill" src/specify_cli/skills/manifest*.py src/specify_cli/skills/data/` and the `.kittify/skills-manifest.json` writer. If ids are persisted and compared across runs, a stale id must not make `doctor tool-surfaces` report drift forever: either confirm the manifest stores paths, not surface ids (expected), or record the finding and raise it with the orchestrator (the cutover migration, WP11/WP12, would own any rewrite). Do not add a compat reader.
  6. Prose: `src/specify_cli/.contextive/execution.yml:51` and `docs/context/execution.md` (member list).
  7. Tests: `tests/specify_cli/tool_surface/integration/test_migration_compat.py:137-149` freezes `EXPECTED_SURFACE_KINDS` as an "additive-only contract (FR-042/NFR-005)". This rename deliberately breaks that contract under FR-009/#3732: replace `"doctrine_skill"` with `"charter_skill"` and extend the comment ("renamed by #3732, listed in the changelog Before/After; no alias, C-001"). Update `tests/specify_cli/tool_surface/{test_registry,test_docs}.py`, `providers/{test_managed_skills,test_plugin_bundle}.py`, `bundles/{_support,test_claude}.py`, `integration/test_doctor_tool_surfaces_cli.py`, `tests/specify_cli/skills/{test_installer,test_crlf_skill_render_4998}.py`.
- **Files**: tool-surface and skills modules above.
- **Parallel?**: Yes ([P] in tasks.md): independent of T083–T085.
- **Validation**: [ ] `uv run pytest tests/specify_cli/tool_surface/ tests/specify_cli/skills/ -q` green; [ ] `uv run spec-kitty doctor tool-surfaces --kind charter-skill --json` runs (in a temp project) and `--kind doctrine-skill` is rejected.

### Subtask T087 – Tests; flip FR-009 xfails

- **Purpose**: close the WP against its acceptance tests and leave no old name behind.
- **Steps**:
  1. Run the WP17 acceptance tests: green.
  2. Final sweep (excluding historical roots and the cutover migration module):
     ```bash
     rg -nw "CharterPackManager|CharterPackConfigError|CHARTER_PACK_CONFIG_INVALID|DOCTRINE_SKILL|doctrine_skill|doctrine_skill_entries|doctrine_pack_id" \
        src tests docs packs -g '!docs/adr/**' -g '!docs/archive/**' -g '!docs/plans/**' -g '!docs/reports/**' -g '!docs/changelog/**' \
        -g '!src/specify_cli/upgrade/migrations/m_*charter_pack_cutover*.py'
     ```
     Allowed hits: the retired-field validator and its tests (they must spell `doctrine_pack_id`). Record them in the Activity Log for WP25's FR-018 allowlist review (the allowlist closes empty except C-004 names, so these must be inside the cutover migration module or expressed so the gate can see them as the validator's own literal: coordinate with WP25 via the Activity Log; do not add an allowlist here).
  3. `tests/architectural/test_json_contract_enumeration.py:318` names the class: update. Run the dead-symbol gate (`tests/architectural/test_no_dead_symbols.py`) since renamed public names may be keyed in `dead_symbol_allowlist.yaml` (follow-up edit, log).
  4. Commit `refactor(charter)!: active charter names, charter_pack_id, CHARTER_SKILL (#3732)`.
- **Validation**: [ ] `rg -n 'pending_until\("WP17"\)' tests` empty.

## Test Strategy

```bash
make test-fast
uv run pytest tests/acceptance/charter_pack_cutover/ -q    # at least the WP17-marked tests
uv run pytest tests/charter/ tests/doctrine/ -q            # src/charter/offering/** touched (spdd_reasons, mission_type_repository)
uv run pytest tests/core/ tests/next/ tests/specify_cli/tool_surface/ tests/specify_cli/skills/ \
              tests/specify_cli/cli/commands/charter/ tests/specify_cli/cli/commands/agent/ \
              tests/specify_cli/test_charter_activate_cli.py tests/cli/commands/test_charter_rendering.py \
              tests/integration/test_user_doctrine_artifact_lifecycle.py -q
uv run pytest tests/architectural/test_json_contract_enumeration.py \
              tests/architectural/test_no_dead_symbols.py \
              tests/architectural/test_dead_symbol_allowlist_loader.py \
              tests/architectural/test_charter_offering_does_not_import_activation.py \
              tests/architectural/test_layer_rules.py \
              tests/architectural/test_no_legacy_terminology.py -q
uv run ruff check src tests
uv run ruff format --check --force-exclude <touched .py files>
uv run mypy <touched src modules>
```

Never bare `tests/architectural/` or `make test-full`.

## Risks & Mitigations

- **Missed catcher silently changes behaviour** (an `except CharterPackConfigError` left behind would fail import, not behaviour; but a string comparison against the old code would silently stop matching). Mitigation: grep for the code string as well as the class.
- **Golden drift**: run the golden's test, not just the grep.
- **Persisted surface ids**: T086 step 5 investigates before changing behaviour.
- **Files owned by later WPs** (`pack_manager.py`, `activate.py`, `upgrade.py`, `mission_type.py`): their owners run after you, so edit them (rename only) and log each; do not wait (see Context).

## Review Guidance

- Red-on-base → green-on-final for the WP17 acceptance tests.
- No alias anywhere: grep `= CharterPack`, `alias=`, `populate_by_name`, `DOCTRINE_SKILL =`.
- `mission_type.py` reads `exc.code`; exactly one spelling of the new code string in `src/`.
- Golden updated and its test green; `ERROR_CODES.md` has the new section with remediation.
- `doctrine_pack_id` rejected with `RETIRED_PACK_FIELD` naming `charter_pack_id`, for both project and org entries; `schema_version` bump recorded with its decision.
- Every follow-up edit outside `owned_files` logged with the owning WP's status at the time.
- mypy and format checks ran on touched sources.

## Definition of Done

- [ ] Red-first commit, then green.
- [ ] Five renames complete per the table; no aliases.
- [ ] Single source for the JSON code; golden and `ERROR_CODES.md` updated.
- [ ] Retired-field rejection for `doctrine_pack_id` with tests; org-charter schema version bumped.
- [ ] Before/After pairs recorded in the Activity Log for WP24.
- [ ] Commands above run and recorded; ruff/format/mypy clean; terminology gate green.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END**
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (`date -u "+%Y-%m-%dT%H:%M:%SZ"`)

**Initial entry**:

- 2026-10-06T19:30:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
