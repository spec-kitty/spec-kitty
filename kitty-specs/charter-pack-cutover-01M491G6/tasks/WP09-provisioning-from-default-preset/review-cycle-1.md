---
affected_files: []
cycle_number: 1
mission_slug: charter-pack-cutover-01M491G6
reproduction_command:
reviewed_at: '2026-10-07T17:25:56Z'
reviewer_agent: claude
wp_id: WP09
---

# WP09 review feedback, cycle 1

Reviewer: architect-alphonso (claude). Reviewed lane `charter-pack-cutover-01M491G6-lane-i` at 71c34ce2.

Verdict: **changes requested.** One blocking defect. Everything else checks out (see the end of this file).

## BLOCKER 1: `spec-kitty upgrade` crashes with a traceback when the `default` preset is missing (it used to print an error and exit 1)

contracts/errors.md says `DEFAULT_PRESET_MISSING` covers "init / charter generate / upgrade provisioning", and T046 step 4 / T047 asks for upgrade to report it the same way. You handled it only in `_provision_missing_mission_type_activations` (`upgrade.py:498-506`). A real upgrade reaches that function only when `prepared is None` (`_finalizer_step_provision`, `upgrade.py:1014`).

The live path is different. It is `_prepare_finalizer_repairs` (`upgrade.py:1036-1046`) and the dry-run preview `_supporting_repair_preview` (`upgrade.py:1058-1075`). Both call `prepare_upgrade_repairs`, which calls `prepare_mission_type_activations`, which calls `default_preset_mission_types`.

- Both handlers catch only `(OSError, ValueError, AgentConfigError, ActiveCharterConfigError)`.
- The old seed-read raised `ActiveCharterConfigError`, so those handlers caught it.
- The new `DefaultPresetMissingError` subclasses `KittyInternalConsistencyError` and not `ActiveCharterConfigError`, so it escapes both handlers.

Reproduction:

1. Run `spec-kitty init p --ai claude --non-interactive`.
2. Remove `mission_type_activations` from `.kittify/config.yaml`.
3. Copy `packs/built-in` to `$S/packs/built-in`, delete `presets/default.yaml` from the copy, and set `SPEC_KITTY_PACKS_ROOT=$S/packs`.
4. Run `spec-kitty upgrade --yes`, then `spec-kitty upgrade --dry-run --yes`.

Results:

- **WP09 head:** both commands print a Rich traceback ending in `DefaultPresetMissingError: DEFAULT_PRESET_MISSING` and exit 1. The body (preset path plus "reinstall spec-kitty") is never printed.
- **Base (`b1390ad8^`, with `src/charter/activation/packs/default.yaml` removed):** a clean `✗ ... does not declare a non-empty 'mission_type_activations' list ... reinstall spec-kitty` line and exit 1.

So the change regresses upgrade and breaks the contract. The `--plan-json` path (`upgrade.py:~1506`, `except Exception` gives `str(exc)`) does not crash, but its message is only `DEFAULT_PRESET_MISSING`, with no body or path.

Required fix (smallest, inside `upgrade.py`; log it as a WP12-owned edit like the existing one):

- Add `DefaultPresetMissingError` to both except tuples (`_prepare_finalizer_repairs`, `_supporting_repair_preview`).
- Make `_preparation_error_text` render it as `Error (DEFAULT_PRESET_MISSING): <body>`, the same text as the fallback path, init and generate.
- Prefer passing `exc.body` (or the rendered text) in the `--plan-json` `assessment_failed` diagnostic message too.

Add a test that drives `spec-kitty upgrade` (and `--dry-run`) through the CLI with a broken `SPEC_KITTY_PACKS_ROOT` copy and a project that lacks the key. The test must check exit 1, that the output contains `Error (DEFAULT_PRESET_MISSING):` and the preset path, that there is no `Traceback`, and that `config.yaml` is unchanged. The current upgrade test (`test_upgrade_provisions_mission_type_activations.py:418-437`) covers only the `prepared is None` helper, which is why this was missed.

## Non-blocking notes (no action required for approval)

1. **The open question about `preset_application._default_values` (WP08).** When the preset is missing, it treats every present key as customised. This does **not** contradict the contract. errors.md limits `DEFAULT_PRESET_MISSING` to init, charter generate and upgrade provisioning, and `charter activate --preset` is not in that list. The fallback is also fail-safe: it can only cause more `PRESET_WOULD_OVERWRITE` refusals and never a silent overwrite. Recommendation for WP12 or a later cleanup: have `_default_values` use `default_preset_mission_types()`, or at least share `_DEFAULT_PRESET_NAME`/`_default_preset_path` with `compiler.py`. There are now two readers of the built-in default preset (one for provisioning, one for the customisation baseline), and each declares its own name constant.
2. **`provisioning/__init__.py`.** The change is a docstring edit plus one removal from `__all__` in a subpackage. The CLAUDE.md version-bump rule targets the package `__init__.py`, and the mission rule is a changelog entry under Unreleased with no bump until closeout. Nothing is needed now. **WP24:** the CHANGELOG Before/After must list `DefaultCharterPackMissingError` → `DefaultPresetMissingError` / `DEFAULT_PRESET_MISSING` (FR-017).
3. Remaining docstring mentions of `packs/default.yaml` (schemas.py, charter_yaml_io.py, migrations, charter_pack_registry) are correctly left alone and listed for WP13 and WP25.

## Verified OK

- **Step 0a:** fixing the test, not the message, is correct. WP06 T0xx step 5 / FR-015 explicitly replaces the looping "Run `spec-kitty upgrade`" remedy and says "Update any test asserting the old text".
- **Step 0b:** the tests, renames and comment removal are fine.
- **Red-first at 42b17ca7:** both FR-003 tests fail for the right reasons. One gets `exit=0` instead of 1 because nothing fails closed. The other gets `['software-dev','documentation','research','plan'] != ['software-dev']` because the old pack drives init.
- **Single seed-read:** `default_preset_mission_types` in `compiler.py` is the only provisioning reader. `default_pack.py` is deleted. There is no alias of `DefaultCharterPackMissingError` (C-001). Provisioning imports nothing from `charter_pack_registry`. The CAS input now observes the preset file.
- **init and charter generate (text and `--json`):** both render `DEFAULT_PRESET_MISSING` and exit 1. The `generate.py` helper extraction keeps C901 clean.
- **mypy** on the touched sources: 8 errors at head vs 9 at base, all pre-existing (stubs, untouched lines).
- **ruff check and format** (`--force-exclude`) are clean.
