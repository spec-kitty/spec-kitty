---
affected_files: []
cycle_number: 1
mission_slug: charter-cli-typed-errors-json-01M5ZC9Z
reproduction_command:
reviewed_at: '2026-10-27T21:16:28Z'
reviewer_agent: claude
wp_id: WP01
---

# WP01 review feedback (cycle 1) — reviewer-renata

Verdict: changes requested. The core work is sound. These were checked and pass:

- Commit sequence. The golden test passes on `6e56ee72` with the pre-refactor source, 10/10. The refactor `61f9fa03` changes no test. At `6d78e622` the JSON tests are red: 21 failed, 12 passed.
- Text output on success paths is byte-identical (golden).
- Every `--json` run produces exactly one JSON document, including the `--resynthesize`, malformed `charter_packs`, mission-type and skill cases I probed by hand.
- Exit codes are the same with and without `--json`, and nothing is written on refusal.
- The codes match `contracts/cli-json.md`, with no contract codes and no `revision` field.
- ruff, ruff format and `mypy --strict` are clean, every function is at complexity 15 or below, nothing under `src/charter/` changed, and there are no new suppressions.

Two items block approval.

## Blocking

**1. Step-removal warnings are dropped from the `--json` payload (FR-005, spec US2 AS1).**
Activating a mission type in text mode prints `⚠ Step '<id>' removed by mission-type override. Affected missions: …` (FR-008 of the earlier mission). With `--json`, `_emit_step_removal_warnings` prints into `console.capture()` and the output is discarded, so a warning the operator sees never reaches the machine payload. That breaks FR-005 ("the entries that changed and the warnings") and makes `--json` silently less informative than the text output, which is the drift this mission is meant to prevent.
Fix:
- Split `_emit_step_removal_warnings` into a collector that returns the `StepRemovalWarning`s, or the warning strings, and a text renderer that still prints at the same point in preflight, so the golden stays byte-identical.
- Carry the strings in `ActivationChangeReport.warnings` (or a dedicated tuple that `all_warnings()` includes). Use one string per removed step that names the affected missions.
- Add a test, for example by monkeypatching `find_removed_steps` / `scan_inflight_missions` the way `tests/cli/test_charter_activate_warning.py` does. It must assert that the warning appears in `payload["warnings"]` and that the text output is unchanged.

**2. The refactor left production helpers that only tests call (dead code; checklist item 1).**
- `deactivate.py::_cascade_child` is no longer called from `src/`. The command path uses `_cascade_child_entry` plus `_render_cascade_entry`. Its only caller is `tests/specify_cli/cli/commands/charter/test_activate_clears_exclusion.py::_child`.
- `activate.py::_required_note` is no longer called from `src/`. Its only callers are a docstring and `tests/.../test_activate_include_deactivated.py:252`. Production now duplicates its `ref.required_by if ref.via_requires else ()` rule inline in `_deactivated_skip_entries`, so the unit test pins a copy production never runs. In particular, the suggests-only case with `via_requires=False` is untested on the live path.

Your cleanup commit `52b98747` removed the other orphaned wrappers but missed these two.
Fix:
- Delete `_cascade_child` and point the `_child` test helper at `_cascade_child_entry` + `_render_cascade_entry`. Its assertions on text and `record_exclusion` still hold.
- For `_required_note`, either have `_deactivated_skip_entries` call a live helper that keeps the `via_requires` rule, for example `_required_by(ref) -> tuple[str, ...]`, and retarget the test to it, or delete it and add an equivalent assertion against the live helper.

Both tests sit outside `owned_files`, so record that ownership-map leeway in `add-history`.

## Non-blocking (please consider; not required for approval)

- **N1.** In no-cascade mode, `referenced_not_cascaded` leaves out the kind-filtered node (`Not cascaded: asset/a-asset …`). It also merges "deactivated" and "not activated" references with no distinguishing field, so a line the text prints has no JSON counterpart. This is defensible under data-model's `list[ArtifactRef]` type, but write it down in the documentation WP (WP03) or `contracts/cli-json.md`, and consider a follow-up issue.
- **N2.** The text marker `(deactivated; nothing behind it was walked)` on a `skipped_out_of_scope` entry is not serialized. `CascadeEntry.deactivated` exists but `to_json` drops it. Same situation as N1: allowed by the data model, but worth documenting.
- **N3.** The red fixture for `ACTIVE_CHARTER_CONFIG_INVALID` changed in the implementation commit, from a broken charter pointer to an unparseable ledger. That is acceptable and was explained. Consider also pinning the `validate_pack_config` shape refusal (`charter_packs: [1, 2]` in `.kittify/config.yaml`), which I checked by hand and which produces the correct envelope.
- **N4.** A failed pack-skill projection maps to `ACTIVATION_FAILED`. That is acceptable: it adds no new code and keeps exit 1. List this cause in the contract table's ACTIVATION_FAILED row, and `RESYNTHESIS_FAILED` for positional `--json`, so tooling authors know these codes exist.
- **N5.** The edit to `test_activate_preset.py` (dropping the positional `--json` usage-error case) is necessary because of FR-005. That is acceptable.
- **N6.** The import order in `activate.py` changed: `from collections.abc import Callable` moved below a first-party import. ruff passes, but revert it while you are in the file.
