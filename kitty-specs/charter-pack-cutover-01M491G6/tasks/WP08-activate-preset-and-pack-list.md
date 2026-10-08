---
work_package_id: "WP08"
title: "`charter activate --preset` and `charter pack list/path`"
subtasks: ["T041", "T042", "T043", "T044", "T045"]
dependencies: ["WP06", "WP07"]
requirement_refs: ["FR-001", "FR-004", "NFR-003", "SC-001"]
task_type: "implement"
phase: "Phase 2 - Presets and promotion"
execution_mode: "code_change"
owned_files:
  - "src/charter/activation/preset_application.py"
  - "src/charter/activation/charter_yaml_io.py"
  - "src/specify_cli/cli/commands/charter/activate.py"
  - "src/specify_cli/cli/commands/charter/pack.py"
  - "tests/charter/activation/test_preset_application.py"
  - "tests/charter/activation/test_activation_key_removal.py"
  - "tests/specify_cli/cli/commands/charter/test_activate_preset.py"
  - "tests/specify_cli/cli/commands/charter/test_charter_pack_list_path.py"
  - "tests/specify_cli/cli/commands/charter/test_preset_cli_timing.py"
  - "tests/specify_cli/cli/commands/charter/test_charter_pack_builtin.py"
authoritative_surface: "src/charter/activation/preset_application.py"
create_intent:
  - "src/charter/activation/preset_application.py"
  - "tests/charter/activation/test_preset_application.py"
  - "tests/charter/activation/test_activation_key_removal.py"
  - "tests/specify_cli/cli/commands/charter/test_activate_preset.py"
  - "tests/specify_cli/cli/commands/charter/test_charter_pack_list_path.py"
  - "tests/specify_cli/cli/commands/charter/test_preset_cli_timing.py"
agent_profile: "python-pedro"
role: "implementer"
agent: "claude"
history:
  - at: "2026-10-06T19:30:00Z"
    actor: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP08 – `charter activate --preset` and `charter pack list/path`

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

- `spec-kitty charter activate [--pack <pack>] --preset <preset> [--force] [--compile|--no-compile] [--resynthesize] [--json]` applies a pack's preset with **replace semantics** (FR-001): every governed key is written as listed or removed when the preset leaves it unrestricted, the org's `required_<kind>` is unioned in, a change to a customised key is refused without `--force` (OD-6, with a per-key diff), and the whole change is **one atomic write** to the resolved activation target. `--pack` defaults to `built-in`.
- `spec-kitty charter pack list [--json]` lists one row per pack (built-in, each org pack, `project`) with the presets it ships (FR-004; US3 AS-3). `spec-kitty charter pack path <pack> [--preset <preset>]` prints the pack root or the preset file.
- New stable error codes `PRESET_NOT_FOUND`, `PACK_NOT_FOUND`, `PRESET_ID_UNRESOLVED`, `PRESET_WOULD_OVERWRITE` (contracts/errors.md).
- NFR-003: `charter activate --preset <name>` and `charter pack list` take ≤ 1.5× `charter list` on the same fixture (built-in + two org packs), median of 5 in-process runs, under the `timing` marker.
- SC-001: switching `minimal` ↔ `default` is one command each; `charter list --json` matches the preset in 100% of fixture runs; after `--preset default` every per-kind key and `activated_kinds` is absent.

Not in scope: deleting `charter pack apply` and `charter_pack_registry` (WP13); moving `consistency-check` (WP15).

Done when every acceptance test marked `pending_until("WP08")` (FR-001, FR-004 CLI half, NFR-003, SC-001, US1 AS-1..AS-5, US3 AS-3) is green with the marker removed.

## Context & Constraints

- Read first: `spec.md` FR-001, FR-004, NFR-003, SC-001, US1, US3 AS-3, OD-6; `data-model.md` "Applying a preset (FR-001) — state transition" and "Active charter"; `contracts/cli.md` (command map and the `--preset` outcome table); `contracts/errors.md`; `research/postspec-squad-architecture.md` B2.
- Upstream state: WP07's `charter.offering.packs.presets` (`ActivationPreset`, `load_preset`, `PresetNotFoundError`, `list_offering_packs`, `OfferingPack`, `discover_presets`, `preset_activation_keys()`) exported through the `charter.packs` facade; WP06's `charter.activation.effective_set.resolve_effective_set(repo_root, kind)`; WP05's `charter.activation.org_charter.load_org_charter_policies(repo_root)` and `REQUIRED_KIND_FIELDS`; WP02's `charter.activation.layer_roots`. Verify the names before coding and record differences.
- **C-007**: the application engine lives in `charter.activation` (`preset_application.py`); the CLI is a thin adapter. No `specify_cli` preset registry, no `charter` → `specify_cli` import.
- **C-001**: no alias for `charter pack apply`; the `apply` command keeps working unchanged until WP13 deletes it. `--preset` is a new option of the existing `activate` command, not a new command.
- **One write path**: activation writes go through `charter.activation.pack_manager.prepare_activation_write` → `charter_yaml_io.apply_yaml_write` (the INV-9 single writer). Today that path can only set keys; it cannot remove one (`prepare_activation_write` at `pack_manager.py:663-683` and `prepare_charter_yaml_section` at `charter_yaml_io.py:612-632` only assign). Replace semantics needs removal; add it there (T041), not a second writer.
- Complexity ≤ 15 per function; `activate_cmd` (`activate.py:796-936`) is already long — the preset branch must be a separate function called early, not more inline branches.

## Branch Strategy

- **Strategy**: lane-based; the lane for this WP is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Red-first (C-006 / C-011)

```bash
grep -rn 'pending_until("WP08")' tests/acceptance/charter_pack_cutover/
# remove only those markers, run them, confirm red, then:
git commit -m "test(charter): flip preset activation and pack list acceptance tests red (#3732)"
```

`test_fr001_preset_with_positional_kind_exits_2` is unmarked (it passes at base, where `--preset` is an unknown option): it is a regression guard, not red-first evidence. `test_nfr003_preset_and_pack_list_latency` asserts every timed command succeeded before it compares medians, so it is red at base.

The acceptance tests are the arbiter of the two open semantic points below (customised-key rule, preset that omits `mission_type_activations`). Do not edit their assertions (C-006); if they contradict the spec, stop and record it.

## Subtasks & Detailed Guidance

### Subtask T041 – Preset application engine (replace semantics, org union, diff, atomic write)

- **Purpose**: the FR-001 write path, pure enough to unit-test without the CLI.
- **Steps**:
  1. **Key removal in the single writer.** In `src/charter/activation/charter_yaml_io.py`, give `prepare_charter_yaml_section` (`:612`) a keyword `remove: Iterable[str] = ()` honoured only for `section == "activation"` (validate the names with `_validate_section`'s activation-key check; a non-activation section with `remove` is a `ValueError`); delete those keys from the document before rendering. In `src/charter/activation/pack_manager.py`, give `prepare_activation_write(repo_root, values, *, remove=())` (`:663`) the same keyword for both targets (config branch: `data.pop(key, None)`; charter branch: pass `remove=` through). `pack_manager.py` is owned by WP06 (completed upstream): a follow-up edit allowed by the tasks.md rule — log it. Update the `update_charter_yaml_section` docstring (`charter_yaml_io.py:635-670`) and the module docstring lines naming the deleted `pack_manager.merge_defaults` (`:4`, `:639`, `:659`; WP06 deleted it).
  2. Create `src/charter/activation/preset_application.py` with:
     - `GOVERNED_KEYS`: `preset_activation_keys()` (WP07; the nine `activated_<plural>` keys, `activated_anti_patterns` included) + `"activated_kinds"` + `"mission_type_activations"`. The single writer must accept and remove `activated_anti_patterns`; if `prepare_activation_write` rejects it today, extend the accepted key set at its authority (not a second list), and add it to `test_activation_key_removal.py`. `activated_skills` and `activated_glossary_packs` are never read or written by this module (they have their own absence contract).
     - `PresetPlan` (frozen dataclass): `pack`, `preset`, `target_file: Path`, `written: dict[str, list[str]]`, `removed: list[str]`, `changes: dict[str, tuple[object, object]]` (key → (before, after), `None` meaning absent), `customised_changes: tuple[str, ...]`.
     - `plan_preset_application(repo_root, pack_name, preset_name) -> PresetPlan` — pure read: resolve the pack (`list_offering_packs`; unknown → `PackNotFoundError` carrying the available pack names), load the preset (`PresetNotFoundError` carrying the pack's preset names; the `project` pack ships none), resolve ids (step 3), compute the target state (step 4), diff against the current state read with `resolve_activation_write_target(repo_root)`.
     - `apply_preset_plan(repo_root, plan) -> None` — one `prepare_activation_write(repo_root, written, remove=removed)` then `apply_yaml_write(...)`; nothing else writes. If `written` and `removed` are both empty, no write at all (idempotent re-apply changes 0 bytes).
  3. **Id resolution against the whole offering** (spec Edge Cases): for each listed per-kind key, `resolve_effective_set(repo_root, kind)` gives the offering's ids (built-in, every org pack, project layer). Compare after directive normalisation (stem ↔ `DIRECTIVE_NNN`; reuse `charter.activation.kind_vocabulary`'s normaliser, do not write a new one). Any id not found → `PresetIdUnresolvedError` naming the preset file and every unresolved id. If the seam reports `resolved=False`, fail the same way with its reason (never apply a preset you could not check). `mission_type_activations` ids are checked with the same rule the positional path uses: `activate.py:216-222` (`_validate_mission_type_activatable`) delegates to `charter.activation.mission_type_profiles.validate_activatable_mission_type(id, repo_root=...)`; call that charter function directly, not the CLI helper.
  4. **Target state** for each governed key:
     - preset lists the key → that list, then the org's `required_<plural>` ids not already in it (`load_org_charter_policies(repo_root)`, `getattr(policy, f"required_{plural}")`, first-seen order), for kinds in `REQUIRED_KIND_FIELDS`;
     - preset leaves a per-kind key or `activated_kinds` unrestricted → **absent** (removed). An absent key already admits every org-required id, so no union is needed;
     - `activated_kinds` listed → the list plus the plural of every kind for which the org requires ids and which is missing from it (record this rule in the module docstring);
     - `mission_type_activations` omitted by the preset → **open point**: FR-001 literally says "removed", but an absent `mission_type_activations` fails closed at mission create (data-model "Active charter"). Both built-in presets declare it, so the built-in path is unaffected. Recommended: a preset that omits it leaves the key untouched (not governed by that preset). Implement what the WP01 acceptance tests require; if they are silent, implement the recommendation, record the decision in the Activity Log, and flag it in the review hand-off.
  5. **"Would change a customised key" (OD-6)** — **open point**: data-model says "diff := governed keys whose value would change; refuse without `--force`", but US1 AS-1 applies `--preset minimal` to a *fresh* project without `--force`, and a fresh project already carries `mission_type_activations` (seeded by `init`) that `minimal` changes. A rule consistent with AS-1, AS-2 (`minimal` → `default` needs `--force`) and AS-5 is: a key is **customised** when it is present and its value differs from what the built-in `default` preset would leave (per-kind keys and `activated_kinds`: absent; `mission_type_activations`: the `default` preset's list). Refuse without `--force` when any customised key would change. Let the acceptance tests decide; record which rule you implemented.
  6. Errors are typed classes in `preset_application.py` (or WP07's `presets.py` for the lookup errors) each with a stable `code` attribute: `PACK_NOT_FOUND`, `PRESET_NOT_FOUND`, `PRESET_ID_UNRESOLVED`, `PRESET_WOULD_OVERWRITE` (the last carries the per-key diff). Derive from one small base so the CLI renders them in one place.
- **Files**: `preset_application.py` (new), `charter_yaml_io.py`; logged follow-up edit in `pack_manager.py`.
- **Parallel?**: No; T042–T044 consume it.
- **Validation**: `tests/charter/activation/test_preset_application.py` and `test_activation_key_removal.py` (T045).

### Subtask T042 – `charter activate --pack/--preset` wiring and flag rules

- **Purpose**: the CLI surface of FR-001 (contracts/cli.md).
- **Steps**:
  1. In `src/specify_cli/cli/commands/charter/activate.py`, `activate_cmd` (`:796-936`): add options `--preset` (str | None), `--pack` (str, default `"built-in"`), `--force` (bool), `--json` (bool). Keep `--compile/--no-compile` (default `True`, as today) and `--resynthesize/--no-resynthesize`.
  2. Flag rules (usage errors exit **2**, raised as `typer.BadParameter`/`click.UsageError` so they go through Click's usage path, before any I/O):
     - `--preset` with positional `KIND`/`ARTIFACT_ID` → exit 2;
     - `--cascade` with `--preset` → exit 2 (presets do not cascade);
     - `--pack`, `--force` or `--json` without `--preset` → exit 2 (they mean nothing on the positional path; the positional path has no JSON output today).
     - These rules, the `--json` shapes and the `Error (<CODE>): <message>` text format are binding in `contracts/cli.md`; do not deviate from it.
     - Detect "user passed `--pack`" without comparing to the default string (use `ctx.get_parameter_source("pack")`), so `--pack built-in` alone is still an error.
  3. Put the preset flow in its own function, e.g. `_activate_preset(repo_root, pack, preset, *, force, json_output, compile_catalog, resynthesize) -> None`, called right after the `ctx.invoked_subcommand` guard. Order inside it: `resolve_write_root_or_exit(repo_root)` (worktree fail-closed, as the positional path does) → `validate_pack_config(repo_root)` (fail closed on invalid config) → `plan_preset_application` → refuse/print diff without `--force` → `apply_preset_plan` → `recompile_or_notify(repo_root, resynthesize=..., compile_catalog=...)` exactly as the positional path finishes (`:930-935`). Do not call `reproject_pack_skills` (presets never govern skills).
  4. `--resynthesize`: the positional path runs `preflight_resynthesis(repo_root, kind, artifact_id, ...)` before writing. For a preset, run the equivalent read-only check over the preset's resulting state before the write if the preflight module can express it; if not without a new abstraction, document that `--resynthesize` performs the post-write resynthesis only and record it.
  5. Output: text mode prints one line per written/removed key and the target file; `--json` prints exactly `{"pack", "preset", "written": {...}, "removed": [...], "target_file"}` (contracts/cli.md) via `console.emit_json` / `json_error(code, message)` from `specify_cli.cli.json_contract` for failures (exit 1).
  6. Update `activate_cmd`'s help/docstring to show both forms. Help text feeds `src/specify_cli/_completion_manifest.json` (freshness gate); regenerate it with `uv run --frozen python -m specify_cli.completion --regenerate` (regenerated shared file — log it).
- **Files**: `activate.py`.
- **Parallel?**: After T041.
- **Validation**: `test_activate_preset.py` (T045).

### Subtask T043 – `charter pack list` (packs + presets, `project` row) and `charter pack path <pack>`

- **Purpose**: FR-004 listing, FR-006's "`charter pack path <pack>` takes a pack name".
- **Steps**:
  1. In `src/specify_cli/cli/commands/charter/pack.py`, rewrite `list_cmd` (`:69-100`) on `charter.packs.list_offering_packs(repo_root)` + `discover_presets(pack.root)`: one row per pack — `name`, `tier`, `root`, `presets` (`[{"name", "description", "path"}]`); the `project` row has `presets: []`. Add a hidden `--repo-root` option (default `Path(".")`) like the other charter commands. Text mode: a Rich table (pack, tier, presets comma-joined or "—"). `--json`: `{"packs": [...]}` (keep the result total: exit 0 even with zero org packs; outside a project it lists `built-in` and, when `.kittify/` is absent, no `project` row — decide and document).
  2. Rewrite `path_cmd` (`:262-276`): argument `pack` (pack name, help text "Pack name (built-in, an org pack name, or project)"), option `--preset <name>`; prints the pack root or the preset file (`--json`: `{"pack", "path"}` plus `"preset"` when given). Unknown pack → `PACK_NOT_FOUND`, unknown preset → `PRESET_NOT_FOUND`, both exit 1, both list the valid names.
  3. `list` and `path` no longer import `specify_cli.charter_pack_registry`; only `apply_cmd` still does until WP13. Remove the now-unused helpers if only list/path used them (`_resolve_pack_path_or_exit` is also used by `apply_cmd`, so it stays until WP13).
  4. Update the module docstring (`:1-8`): it describes the retired registry as the home of list/path.
- **Files**: `pack.py`.
- **Parallel?**: Yes with T042 once T041 exists.
- **Validation**: `test_charter_pack_list_path.py` (T045).

### Subtask T044 – Error codes `PRESET_NOT_FOUND`, `PACK_NOT_FOUND`, `PRESET_ID_UNRESOLVED`, `PRESET_WOULD_OVERWRITE`

- **Purpose**: stable machine contract (contracts/errors.md); FR-017 lists them in the changelog later (WP24).
- **Steps**:
  1. One rendering helper in `activate.py` (and reused by `pack.py`) maps the typed errors to `(code, message)`; text mode prints `Error (<CODE>): <message>`; JSON mode emits `json_error(code, message)` plus the payload the contract names (pack/preset/ids/diff).
  2. Messages: `PACK_NOT_FOUND` names the pack and lists available packs; `PRESET_NOT_FOUND` names the pack and lists its presets (US1 AS-4); `PRESET_ID_UNRESOLVED` names the preset file and each id; `PRESET_WOULD_OVERWRITE` prints the per-key diff (before → after, "absent" spelled out) and says `--force` applies it.
  3. Exit code 1 and **no write** for all four (assert file bytes unchanged in tests).
  4. `tests/architectural/test_json_contract_enumeration.py` registers every `--json` command with its probe args (`:150-215`) and total-result evidence (`:219-228`): add `charter activate` (preset probe, e.g. `("--preset", "missing")` → 1 outside a project, or whatever the harness expects), update `charter pack path` args (`("missing",)` still exits 1) and the `charter pack list` evidence line (it is no longer a "fixed built-in pack catalog"). Shared gate file — logged edit. Leave the `charter pack apply` row for WP13.
- **Files**: `activate.py`, `pack.py`; logged edit in `tests/architectural/test_json_contract_enumeration.py`.
- **Parallel?**: With T042/T043.

### Subtask T045 – Tests incl. NFR-003 timing; flip FR-001/FR-004 xfails

- **Steps**:
  1. `tests/charter/activation/test_activation_key_removal.py`: `prepare_charter_yaml_section(..., remove=[...])` drops keys and preserves every other byte of the document; `remove` on a non-activation section raises; `prepare_activation_write(remove=...)` on both a `config.yaml` target and a pointer `charter.yaml` target.
  2. `tests/charter/activation/test_preset_application.py`: on tmp projects (config target and pointer target): `minimal` on an empty project writes exactly its keys; `default` after `minimal` removes every per-kind key and `activated_kinds` and writes the mission types; org `required_directives` unioned into a listed key and not written into an unrestricted one; unresolved id → error, file unchanged; unknown pack/preset → typed errors with available names; customised key + no force → `PRESET_WOULD_OVERWRITE` with diff, file unchanged; force → applied; re-apply → 0 bytes changed; `activated_skills` / `activated_glossary_packs` untouched in every case; exactly one `apply_yaml_write` per application (spy).
  3. `tests/specify_cli/cli/commands/charter/test_activate_preset.py` (CliRunner on `charter_app`, real git repo where `recompile_or_notify` needs one — copy the fixture style of `test_charter_activate_commands_core.py`): every row of contracts/cli.md's outcome table (0/1/1/1/1/2); `--json` payload shape; usage errors exit 2 and write nothing; SC-001 round trip `minimal` → `default --force` → `minimal --force`, reading back `charter list --json` each time; US1 AS-2 drift case: copy `packs/built-in` to a tmp dir, add one directive, point `SPEC_KITTY_PACKS_ROOT` at the copy, apply `--preset default`, assert the new directive is effective (`PackContext.from_config`).
  4. `tests/specify_cli/cli/commands/charter/test_charter_pack_list_path.py`: fixture with built-in + org pack A (with `presets/`) + org pack B (without) → list shows A's presets, B with none, `project` with none (US3 AS-3; B is the negative control); `path` for each pack, `--preset`, unknown pack/preset.
  5. `tests/specify_cli/cli/commands/charter/test_preset_cli_timing.py`, `pytestmark = [pytest.mark.timing]`: same fixture (built-in + two org packs), in-process `CliRunner`, median of 5 runs each for `charter list`, `charter activate --preset minimal --force --no-compile`, `charter pack list`; assert each ≤ 1.5 × `charter list`'s median (NFR-003). Run it serially: `-m timing -n0`.
  6. `tests/specify_cli/cli/commands/charter/test_charter_pack_builtin.py`: update the `list`/`path` tests (`:57-120`) to the new output (pack rows; `path built-in`; `path built-in --preset minimal`). Leave the `apply` tests (`:134-300`) for WP13 to delete.
  7. Remove the `pending_until("WP08")` markers (red-first commit) and turn them green.
- **Notes**: if the timing gate fails, profile first (`resolve_effective_set` builds the doctrine service; the `default` preset lists no ids, so it should not need it — resolve ids only for listed keys). Tune the code, never the 1.5× budget (`docs/development/testing/testing-flakiness.md`).

## Test Strategy

```bash
make test-fast
uv run --frozen pytest tests/acceptance/charter_pack_cutover/ -q
uv run --frozen pytest tests/charter/activation/test_preset_application.py tests/charter/activation/test_activation_key_removal.py tests/charter/test_charter_yaml_io.py tests/charter/test_pack_manager.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/charter/ -q
uv run --frozen pytest -m timing -n0 tests/specify_cli/cli/commands/charter/test_preset_cli_timing.py -q
uv run --frozen pytest tests/charter/ -q
uv run --frozen pytest tests/architectural/test_json_contract_enumeration.py tests/architectural/test_completion_manifest_freshness.py tests/architectural/test_docs_cli_reference_parity.py tests/architectural/test_charter_no_specify_cli_import.py tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_symbols.py -q
uv run --frozen ruff check src/charter/activation/ src/specify_cli/cli/commands/charter/ tests/charter/activation/ tests/specify_cli/cli/commands/charter/
uv run --frozen ruff format --check --force-exclude <every file you touched>
uv run --frozen mypy src/charter/activation/preset_application.py src/charter/activation/charter_yaml_io.py src/charter/activation/pack_manager.py src/specify_cli/cli/commands/charter/activate.py src/specify_cli/cli/commands/charter/pack.py
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
```

This WP does not change `src/charter/offering/**`; if it ends up doing so, add `tests/doctrine/`. Record every command with pass/fail counts in the Activity Log.

## Commit discipline

Conventional subjects with `#3732`: `feat(charter): activation-key removal in the single writer (#3732)`, `feat(charter): preset application engine (#3732)`, `feat(cli): charter activate --preset (#3732)`, `feat(cli): charter pack list/path over the offering (#3732)`. First commit is the red flip. Never push to `main`.

## Risks & Mitigations

- **Second writer**: any `yaml.dump` in the preset path is a defect; the spy test in T045 step 2 guards it.
- **Partial write**: compute the whole plan first, then one prepared write; a refused or failed plan writes nothing.
- **Latency**: building the doctrine service per kind is the likely cost; resolve only listed kinds, once each.
- **Semantic open points** (T041 steps 4–5): decided by WP01's tests; otherwise implement the recommendation, record it, flag it for review.

## Definition of Done

- [ ] Red-first commit; every `pending_until("WP08")` test green.
- [ ] Removal supported in `prepare_charter_yaml_section` / `prepare_activation_write`; no second writer.
- [ ] `charter activate --preset` with replace semantics, org union, OD-6 refusal + diff, one atomic write, flag rules (exit 2), `--json` payload per contract.
- [ ] `charter pack list` lists built-in, every org pack and `project` with presets; `charter pack path <pack> [--preset]`.
- [ ] Four error codes, exit 1, no write.
- [ ] NFR-003 timing test passes under `-m timing -n0`.
- [ ] Completion manifest regenerated; JSON-contract gate updated; out-of-ownership edits logged.
- [ ] ruff, format, mypy clean, no new suppressions; all commands recorded.

## Review Guidance

- Red on base → green on final for every acceptance test naming WP08; markers removed, assertions untouched.
- Apply `--preset default --force` to a project carrying `minimal`: `git diff` shows only removed/written governed keys; `activated_skills` untouched; second run shows no diff.
- Confirm the two recorded decisions (customised-key rule, preset without `mission_type_activations`) match the acceptance tests and the spec text; raise any mismatch.
- Confirm `charter pack apply` still behaves exactly as before (WP13 removes it).
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
