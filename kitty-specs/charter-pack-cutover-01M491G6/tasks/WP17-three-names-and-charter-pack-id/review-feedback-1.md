# WP17 review feedback, cycle 1 (reviewer-renata)

Verdict: **changes requested**. One blocking finding (1); the other two are small and should go in the same pass.

## What is fine (no action)

- Five renames are complete. There are no aliases, no `populate_by_name` and no `X = Y` bindings. The only `.py` literal of `ACTIVE_CHARTER_CONFIG_INVALID` is `pack_context.py:71`, and `mission_type.py:143` reads `exc.code`. The golden and `ERROR_CODES.md` are updated.
- `retired_fields.py` imports nothing from `charter.activation`. The `ActivationEntry` before-validator fires ahead of pydantic's extra-field error. The positive control (an unrelated unknown field gets the generic error) holds.
- Orchestrator ruling (1) holds exactly: a strict chain with versions {1,2} folds to 2, and {1,3}, {2,3} raise. Both halves are tested in `tests/charter/activation/test_org_charter.py`.
- `doctrine_skill` / `charter_skill` surface ids are never persisted. The skills manifest stores paths, `Effect.id` excludes `surface_ids`, and `status.py` `"kind"` goes only to stdout JSON.
- The dead-symbol allowlist category is justified and names WP13 as the drain owner. Out-of-ownership edits are rename-only, except `org_charter.py` and the `doctrine.py` org-init stub. Both are logged and legitimate.
- Verification (lane-q HEAD): acceptance suite 97 passed / 1 skipped / 255 xfailed, 0 failed, 0 xpassed. The 4 WP17 tests pass. Charter, tool_surface, skills, core, next and the named architectural gates: 3791 + 3945 passed. `ruff check .` and format checks are clean. mypy shows no new errors against the base.

## 1. (Blocking) `RETIRED_PACK_FIELD` is not raised on **loading**. A third-party org pack with `doctrine_pack_id` is silently dropped.

Contract:

- spec US3 scenario 4: "When it is validated **or loaded**, Then it is rejected with an error naming the field and its replacement".
- `contracts/errors.md`: `RETIRED_PACK_FIELD` fires on "pack validation **and loading**", with payload file, field and replacement.

Only the validation leg (`validate_org_charter_file`) meets it. On loading:

- **Org packs (fail-open).** `load_org_charter_policy` re-raises a plain pydantic `ValidationError` with no code and no file path. Three callers swallow it with `except Exception: continue`:
  - `_build_pack_set` (`org_charter.py` ~l.455)
  - the registry loop in `load_org_charter_policies` (~l.703-712)
  - `org_charter_loader.py:55-58`

  The pack's whole policy then disappears with no signal: `required_directives`, governance policies and activations. Probe: a pack declaring `required_directives: [DIRECTIVE_001]` plus one `doctrine_pack_id` activation gives `_build_pack_set(...) == {}`. The clean control pack loads. WP11 rewrites only the project `charter.yaml`, so every third-party org pack with activations hits this after upgrade. Governance enforcement is silently lost, which is the opposite of fail-closed.
- **Project `charter.yaml`.** `load_governance_config` raises a raw `ValidationError`. Its message says `activation entry: field 'doctrine_pack_id' was removed...`: it names no file path and carries no `RETIRED_PACK_FIELD` code.

Fix (one code path; WP13 T068 step 2 asks for the same pattern for `pack.yaml`):

- In `load_org_charter_policy`, catch `ValidationError`. If `retired_field_errors(exc)` is non-empty, raise the first error relocated with `.at(charter_path)`, so it carries the code, the file path, the field and the replacement.
- Let the swallowing loaders re-raise `RetiredPackFieldError`, as they already do for `OrgPackEnvVarUnsetError`/`OrgPackSubdirEscapeError` (FR-003 fail-closed).
- Do the same relocation in `load_governance_config` for the project `charter.yaml` path.
- Make sure the CLI surfaces the code and exits non-zero instead of printing a traceback.

Tests must go through the real loaders:

- `load_org_charter_policies` with a pack context, and the registry path. Assert `RetiredPackFieldError` with code, path, field and replacement, and assert the pack is not silently dropped.
- `load_governance_config` in a `git init` tmp repo.
- One CLI-level check that a loading command prints `RETIRED_PACK_FIELD` and exits non-zero.

## 2. The retired-field table's `file` column does not hold for `org-charter.yaml` top-level fields

The `org-charter.yaml` row is enforced only inside `ActivationEntry`, which is also applied to project `charter.yaml` entries. It is never checked at the `org-charter.yaml` top level. Probe: a planted `RetiredField(file="org-charter.yaml", field="planted_top", ...)` gets pydantic's generic "Extra inputs are not permitted" at the top level. So the module comment "Adding a row is the whole change for a new one" is false for that file.

The planted-row test (`test_planted_second_entry_is_rejected_the_same_way`) calls `reject_retired_fields` directly with `file="pack.yaml"`, and nothing in `src` calls that yet. Fix one of two ways:

- add a top-level before-validator on `OrgCharterPolicy` that calls `reject_retired_fields(data, file="org-charter.yaml", ...)`, or
- key the activation-entry row on a distinct token (e.g. `file="activation entry"`) and document it.

Then make the planted-row test go through a real loader or model (e.g. a planted row rejected by `OrgCharterPolicy` / `ActivationEntry` validation).

## 3. (Nit) Old names in test function names

`tests/specify_cli/tool_surface/providers/test_managed_skills.py:708` `test_managed_skills_provider_can_handle_doctrine_skill` and `:769` `test_doctrine_skill_entries_helper` still spell `doctrine_skill`. The word-boundary sweep misses them, but the FR-018 substring gate (WP25) will not. Rename both to `charter_skill`.
