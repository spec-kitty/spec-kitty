---
affected_files: []
cycle_number: 1
mission_slug: charter-pack-cutover-01M491G6
reproduction_command:
reviewed_at: '2026-10-07T15:21:38Z'
reviewer_agent: claude
wp_id: WP08
---

# WP08 review feedback, cycle 1 (reviewer: architect-alphonso)

Verdict: **changes requested**. The design is sound: the engine is in `charter.activation`, there is one writer, and the FR-001 decisions (customised-key rule, a preset without `mission_type_activations` leaves the key untouched) match the spec text and the WP01 tests. Red-first is genuine: at 8ff685f7 there are 15 red tests. They fail for the right reasons: `No such option: --preset` (exit 2), the old `pack list` row shape, and `pack path built-in` exiting 1. Two blocking defects and one contract gap remain.

## Blocking

**Issue 1: a regression you introduced in `activate.py`'s own test file (red on the branch, green on the base).**
`tests/specify_cli/test_charter_activate_cli.py::TestRegistration::test_dead_subapp_exports_removed` asserts `activate_mod.__all__ == ["activate_cmd", "run_full_synthesize"]`. Adding `render_coded_error` to `__all__` breaks it. It passes at 8ff685f7. This test file covers `activate.py` and is part of the blast radius, but your Activity Log does not list it as run. Fix one of two ways: update the assertion (a logged out-of-ownership edit), or move the shared renderer to a module that both `activate.py` and `pack.py` import, such as a small `charter/_coded_errors.py` CLI helper, so that `activate.__all__` stays unchanged. Then run `tests/specify_cli/test_charter_activate_cli.py`. Note: `TestDeactivate::test_none_state_exits_1_with_guidance` in that file is already red at the base. It is not yours to fix.

**Issue 2: per-id resolution does not fail closed the way the effective-set seam does (T041 step 3: "never apply a preset you could not check").**
`_Roots.of` and `_available_mission_types` use `resolve_org_root_chain`, which calls `resolve_existing_org_roots`. That chain silently drops a declared org pack whose root is missing. The seam's `_declared_org_roots` uses `load_pack_registry(strict=True)` and refuses when a declared root is not a directory. Reproduction: a project whose `config.yaml` declares org pack `ghost` with `local_path: org-packs/ghost` (absent).
- `resolve_effective_sets(root, ["activated_directives", "activated_tactics"])` returns `resolved=False` with "declared org pack root ... is not a directory".
- `spec-kitty charter activate --preset minimal --json` exits 0 and writes `activated_directives`/`activated_tactics`.

Consequence: the org union (`_org_required`) is also computed without that pack's `required_<kind>`. A listed key is then frozen without the missing org's required ids. That is the governance hazard the fail-closed rule exists to prevent.

Fix: keep per-id lookup (it is fine for NFR-003). Before resolving ids or computing the union, run the same fail-closed precondition the seam runs once per plan: strict registry read plus "every declared root is a directory". Do not copy it; expose or reuse the seam's check. Raise `PresetIdUnresolvedError` with the reason in `reasons`, and write nothing. Apply it whenever the preset lists a per-kind key or `activated_kinds`, or when org policies feed the union. A preset that lists nothing (`default`) may still pass. Add an engine test and a CLI test for the missing-root case: exit 1, `PRESET_ID_UNRESOLVED`, file bytes unchanged.

Apart from this, the per-id lookup is equivalent to the seam or stricter:
- it reads the same layers (built-in, every org root, project);
- directive `DIRECTIVE_NNN` spellings are accepted through `resolve_config_id`, as the WP intends;
- anti-patterns are checked against the merged DRG, which the seam cannot resolve at all (it has no `activated_anti_patterns` token);
- mission types go through the roster plus `validate_activatable_mission_type`.

## Should fix (contract)

**Issue 3: a `--json --resynthesize` failure emits no JSON.**
In `_activate_preset`, `recompile_or_notify` runs inside `console.capture()`. When `run_full_synthesize` exits non-zero, for example because interview answers are missing (`generate` then exits 1), the command exits 1 with empty stdout and empty stderr. The preset write has already happened. contracts/cli.md says: "A failure under `--json` emits `json_error(code, message)` and exits 1." Reproduction: a fresh git project with only `mission_type_activations`, then `charter activate --preset minimal --resynthesize --json`, gives exit=1 and no output. Fix: catch the post-write failure in JSON mode. Emit `json_error` with a message that says the preset was applied and the resynthesis failed (or add a field to the success payload, whichever the owner prefers), and test it. Also, the "Catalog not recompiled" notice is swallowed under `--json`. Consider adding a `catalog_recompiled: false` signal, or record it as accepted.

## PRESET_APPLY_FAILED (owner decision; this is my recommendation)

The blanket `except (PresetFormatError, ValueError, DRGLoadError)` lumps three different conditions together under one code that is not in the contract. Recommendation per case:
- **DRG load failure while checking anti-pattern ids** → map to the existing `PRESET_ID_UNRESOLVED`, with the reason in `reasons`. The ids cannot be checked, and T041 step 3 already says this case fails as unresolved. This needs no new code.
- **Unreadable or invalid activation target** (a flow-style root that cannot preserve a deletion, an unparseable target) → map to the existing `ACTIVE_CHARTER_CONFIG_INVALID`, which `validate_pack_config` already raises for the same file a moment earlier. `precondition_changed` (a concurrent edit) is a race, not invalid config. Either keep it uncoded with a re-run hint or fold it into the same code. Do not let a bare `ValueError` catch hide programming errors (for example the "both written and removed" or "unknown key" guards). Narrow the catch.
- **Malformed preset file** (`PresetFormatError`) → no existing code fits: `PRESET_NOT_FOUND` would be wrong, and `RETIRED_PACK_FIELD` covers only retired fields. **Keep a new code, but call it `PRESET_INVALID`**. `PRESET_APPLY_FAILED` misleads on `charter pack list` and `charter pack path`, which apply nothing. Add it to contracts/errors.md and to the FR-017 changelog list.

## Minor (non-blocking)

- `_check_mission_types` overwrites `reasons[MISSION_TYPE_ACTIVATIONS_KEY]` for each failing mission type, so only the last one is reported. Accumulate them instead.
- The campsite `repo_root.resolve()` in `resolve_write_root_or_exit` is correct. It is covered indirectly: reverting it turns 7 tests red in `test_presets.py` and `test_activate_preset.py` under `-n0`. Add one focused test for the positional activate/deactivate path: two tmp repos in one process, `chdir`, default `--repo-root`.

## Verified OK

- The customised-key rule and the omitted-`mission_type_activations` rule match FR-001 verbatim. Comparing as sets is a reasonable refinement.
- `activated_anti_patterns` is added at the `ACTIVATION_YAML_KEYS` authority and derived from `ArtifactKind`. `charter_yaml_io._activation_keys` follows it, and `test_activation_vocabulary_setequal` passes.
- The subclasses and `GOVERNED_KEYS` that were left out of `__all__` are not dead code: each is raised or used inside the module, and the CLI catches the base class.
- Removing the WP09 marker from `test_fr003_init_without_activation_equals_default_preset` is legitimate, not vacuous. The test asserts exit 0 for `--preset default`, equality with a plain `init`, and a non-empty mission-type control. A strict xfail that XPASSes would turn the suite red. WP09's two other FR-003 tests remain pending. Tell the WP09 owner.
- Exit-2 flag rules, including an explicit `--pack built-in`; the `--json` shapes; the four contract codes with no write; one `apply_yaml_write` per application; `pack apply` unchanged; no aliases or hidden commands (C-001).
- ruff check and format (with `--force-exclude`) are clean, C901 ≤ 15, and mypy reports only the 2 `no-any-return` errors that already exist at the base.

## Commands run (lane, `uv run --frozen`)

- Red-first at 8ff685f7 (lane venv, `PYTHONPATH` set to the checkout): 15 failed, 5 passed, 9 xfailed.
- `pytest tests/acceptance/charter_pack_cutover -q -n 4 --dist loadfile`: 128 passed, 1 skipped, 225 xfailed, 0 failed, 0 xpassed.
- `pytest -m timing -n0 test_preset_cli_timing.py test_gates_latency_messaging.py::test_nfr003_preset_and_pack_list_latency`: 2 passed.
- WP08 unit and CLI tests plus `test_charter_yaml_io`, `test_pack_manager`, `test_activation_vocabulary_setequal`, `tests/specify_cli/test_charter_activate_cli.py` (`-n 4`): 306 passed, 2 failed. The 2 failures are Issue 1 and one that is already red at the base.
- Architectural gates (`json_contract_enumeration`, `completion_manifest_freshness`, `docs_cli_reference_parity`, `charter_no_specify_cli_import`, `no_dead_symbols`, `no_legacy_terminology`, `charter_kind_vocabulary_single_authority`): 286 passed.
