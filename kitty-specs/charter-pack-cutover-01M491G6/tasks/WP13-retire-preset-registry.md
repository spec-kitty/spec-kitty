---
work_package_id: "WP13"
title: "Retire the preset registry and the descriptor field"
subtasks: ["T066", "T067", "T068", "T069"]
dependencies: ["WP08", "WP09", "WP12"]
requirement_refs: ["FR-005", "C-001"]
task_type: "implement"
phase: "Phase 4 - Removal (no aliases, no shims)"
execution_mode: "code_change"
owned_files:
  - "src/specify_cli/charter_pack_registry.py"
  - "src/charter/activation/packs/**"
  - "packs/built-in/pack.yaml"
  - "tests/specify_cli/test_charter_pack_registry.py"
  - "tests/specify_cli/cli/commands/charter/test_apply_compile_bridge.py"
  - "tests/specify_cli/cli/commands/charter/test_charter_pack_apply_removed.py"
  - "tests/charter/test_retired_accompanies_doctrine_pack.py"
authoritative_surface: "src/specify_cli/charter_pack_registry.py"
create_intent:
  - "tests/specify_cli/cli/commands/charter/test_charter_pack_apply_removed.py"
  - "tests/charter/test_retired_accompanies_doctrine_pack.py"
agent_profile: "python-pedro"
role: "implementer"
agent: "claude"
history:
  - at: "2026-10-06T19:30:00Z"
    actor: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP13 – Retire the preset registry and the descriptor field

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

Presets now have one home (`packs/built-in/presets/`, WP07) and one application path (`charter activate --preset`, WP08); provisioning reads the `default` preset (WP09); the migration has frozen the old lists (WP12). This WP deletes everything that made the old "charter pack = preset" model work, with no alias:

- `src/specify_cli/charter_pack_registry.py` (`BUILTIN_PACKS`, `load_pack_yaml`, `merge_pack_into_config`, `resolve_builtin_pack_path`, `UnknownPackError`), `src/charter/activation/packs/` (`__init__.py`, `default.yaml`, `minimal.yaml`), `src/charter/activation/default_pack.py`: deleted.
- `spec-kitty charter pack apply` deleted; the spelling exits 2 through Typer's unknown-command path (contracts/cli.md).
- `accompanies_doctrine_pack` removed from the descriptor model, from `packs/built-in/pack.yaml` and from lineage code; a `pack.yaml` that still carries it is rejected with code `RETIRED_PACK_FIELD`, naming the field and what to do (OD-2; contracts/errors.md).
- No reader of the old `default.yaml` remains in `src/` (FR-005's 11 consumers are repointed by WP06/WP09 or retired here).
- Every WP01 acceptance test marked `pending_until("WP13")` (FR-005) is green.

## Context & Constraints

- `spec.md` FR-005, C-001, C-008 ("FR-012 (snapshots, run-first ordering, rc35 no-op) before FR-005"); US3 scenario 4; OD-2.
- `contracts/cli.md` (command map: `charter pack apply` → `charter activate --preset`), `contracts/errors.md` (`RETIRED_PACK_FIELD`: payload file, field, replacement).
- `data-model.md` "Charter Pack (offer side)": descriptor row.
- `research/runtime-seams.md` §1.4–1.5 (rc35 and `m_unify_charter_activation` no longer import the deleted modules after WP10/WP06; confirm).
- Upstream: WP04 moved `pack_descriptor.py` / `pack_lineage.py` / `pack_validator.py` / `pack_manifest.py` to `src/charter/offering/packs/` (confirm paths); WP06 deleted `merge_defaults` / `_load_default_pack` and repointed promotion; WP07 created `packs/built-in/presets/{default,minimal}.yaml` (it may already have moved or deleted `src/charter/activation/packs/minimal.yaml`: check `git log --follow`); WP08 rewrote `charter pack list/path` in `src/specify_cli/cli/commands/charter/pack.py`; WP09 repointed `provisioning/default_charter.py` and `compiler.provision_mission_type_activations`; WP10 neutralised `m_3_2_0rc35_default_charter_pack`.

Constraints:

- **C-001**: no re-export, no stub module, no hidden command, no "did you mean" hint. Deleted things are deleted.
- **Files owned by upstream WPs**: `src/specify_cli/cli/commands/charter/pack.py` (WP08), `src/charter/offering/packs/pack_descriptor.py`, `pack_lineage.py`, `pack_validator.py` (WP04 moves), `pyproject.toml` and the census/roster files (WP05). Edits there are logged follow-ups (tasks.md rule): one line each in the Activity Log with the rationale.
- **Neighbours (none in a parallel lane)**: WP15 (downstream) also edits `charter/pack.py` (it moves `consistency-check` out). WP17 (upstream) created the retired-field table with its `doctrine_pack_id` entry; you add one row (T068). WP14 runs after you. Keep your edits minimal; log them.
- Code style: ruff + mypy clean, complexity ≤ 15, no suppressions without rationale.
- Commit often (`refactor(charter)!: delete the built-in preset registry (#3732)`), never push to `main`.

## Branch Strategy

- **Strategy**: lane-based; the lane is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`

> Populated automatically by `spec-kitty agent mission finalize-tasks`. Do not change manually.

## Red-first (C-006 / C-011)

First commit: remove the `pending_until("WP13")` strict-xfail markers in `tests/acceptance/charter_pack_cutover/` (`grep -rn 'pending_until("WP13")' tests/acceptance/charter_pack_cutover/`): per WP01's flip map, in `test_cli_surface.py`: all `test_fr005_*` except `test_fr005_merge_defaults_removed` (WP06), and the FR-007 row for `charter pack apply` (exits 2). `test_us3_4_accompanies_field_rejected` invokes `charter pack validate`, which exists only from WP15, so it flips at WP15; you prove the rejection with unit-level tests in your own `tests/charter/test_retired_accompanies_doctrine_pack.py` (T069). Run them, paste the red output into the Activity Log, change no assertion.

## Subtasks & Detailed Guidance

### Subtask T066 – Delete `charter_pack_registry`, `src/charter/activation/packs/`, `default_pack`

- **Purpose**: one home for presets (FR-005).
- **Steps**:
  1. Inventory first and paste it into the Activity Log:
     ```bash
     git grep -n -e charter_pack_registry -e BUILTIN_PACKS -e 'activation.default_pack' -e 'activation import default_pack' -e 'activation/packs' -e 'activation.packs' -e load_default_pack -e merge_pack_into_config -e resolve_builtin_pack_path -- src tests pyproject.toml .github scripts
     ```
     At planning time the hits were: `provisioning/default_charter.py` (9), `cli/commands/charter/pack.py` (5), `m_3_2_0rc35_default_charter_pack.py` (5), `compiler.py` (4), `m_unify_charter_activation.py` (3), `org_charter.py` (2), `cli/commands/upgrade.py` (2), `_resynthesis_preflight.py`, `provisioning/__init__.py`, migrations rtk/rc5/rc35-activate (docstrings), plus tests. Most `src` hits should already be gone (WP06/WP09/WP10). Any remaining **code** reader is a gap from those WPs: repoint it to the `default` preset loader (WP07) or the effective-set seam (WP06) and log which WP should have covered it; docstring mentions are repointed or dropped.
  2. Delete `src/specify_cli/charter_pack_registry.py` and `src/charter/activation/packs/` (whatever WP07 left). `src/charter/activation/default_pack.py` is WP06/WP09's module (WP09 removes its last function and the module): confirm it is gone; if WP09 left it, delete it as a logged follow-up.
  3. Clean every roster that names them (logged follow-ups): `pyproject.toml` ruff-format exclude entry `src/specify_cli/charter_pack_registry.py` (around `:463`); `tests/architectural/_interpreter_shard_roster.py:340` and `.github/workflows/ci-nightly.yml:774` (the test path `tests/specify_cli/test_charter_pack_registry.py`); `.github/ci-foreign-coverage-baseline.json` (`specify_cli.charter_pack_registry` at `:63`, `charter.activation.packs` at `:84` and in `_provenance.notes` at `:12`: shrink-only baseline, so lowering a count is allowed, raising is not); `tests/release/coverage_breadth_baseline.json` (`:219`, `:1555`); `tests/architectural/test_src_reachability_guard.py:91` (`"charter.activation.packs"`); `tests/architectural/test_no_dead_modules.py` and `tests/architectural/charter_path_literal_allowlist.yaml` if they list the deleted files.
  4. Confirm packaging no longer needs the data package: `uv run --frozen pytest tests/cross_cutting/packaging/test_packaging_safety.py -q`.
- **Files**: the deleted modules; roster files (follow-ups).
- **Parallel?**: no; first.
- **Notes**: if the rc35 migration module still imports the registry at module level, discovery of **every** migration breaks (`MigrationDiscoveryError`, runtime-seams §1.1). Run `uv run --frozen pytest tests/upgrade/test_auto_discovery.py -q` right after the delete.

### Subtask T067 – Delete `charter pack apply`

- **Purpose**: `charter activate --preset` is the only way to apply a preset (FR-001/FR-005).
- **Steps**:
  1. In `src/specify_cli/cli/commands/charter/pack.py`, delete `apply_cmd` (`@charter_pack_app.command("apply")`, around `:279`) and every helper only it uses: `_resolve_pack_path_or_exit`, `_compile_bundle_after_merge`, `_compile_failure_exit`, `_apply_compile_bridge` (around `:102-260`) unless WP08's `list`/`path` or `charter activate --preset --compile` still calls them (grep before deleting; if WP08 reuses one, leave it).
  2. Delete the registry imports at the top of `pack.py` (`:20-26`).
  3. Remove remediation strings in `src/` that tell operators to run `charter pack apply` (for example `org_pack_config.py` warning text "or run `spec-kitty charter pack apply`", around `:117-121`). `org_pack_config.py` is owned by WP14, which runs after you (WP14 depends on WP13): edit the string here as a logged follow-up; WP14 deletes that whole warning later. Replace any other with `spec-kitty charter activate --preset <name>`.
  4. Tests: delete `tests/specify_cli/cli/commands/charter/test_apply_compile_bridge.py`; delete the `apply` tests in `tests/specify_cli/cli/commands/charter/test_charter_pack_builtin.py` (the `_apply` helper and every `test_apply_*` / `test_applied_*` function, around `:122-260`; WP08 owns that file for `list`/`path`, so this is a logged follow-up). Do not port them to `--preset`: WP08 owns preset-application tests.
  5. Create `tests/specify_cli/cli/commands/charter/test_charter_pack_apply_removed.py`: `spec-kitty charter pack apply default` exits 2 with Typer's "No such command" path; `charter pack --help` does not list `apply`; positive control in the same file: `charter activate --preset minimal` on a fresh fixture exits 0.
- **Files**: `charter/pack.py` (follow-up), the test files above.
- **Parallel?**: yes, beside T068.

### Subtask T068 – Retire `accompanies_doctrine_pack`; `RETIRED_PACK_FIELD` rejection

- **Purpose**: OD-2: reject, never tolerate, and name the fix.
- **Steps**:
  1. Extend `src/charter/offering/packs/retired_fields.py` (created by WP17 with the `doctrine_pack_id` entry; logged follow-up edit — WP17 is upstream). Its shape:
     - `RETIRED_PACK_FIELD = "RETIRED_PACK_FIELD"` (the code string's only source).
     - `@dataclass(frozen=True) class RetiredField: file: str; field: str; replacement: str`.
     - `RETIRED_PACK_FIELDS: tuple[RetiredField, ...]`: WP17 created it with `RetiredField(file="org-charter.yaml", field="doctrine_pack_id", replacement="charter_pack_id")`; add `RetiredField(file="pack.yaml", field="accompanies_doctrine_pack", replacement="delete the field; presets ship inside the pack (presets/<name>.yaml)")` (a one-line addition).
     - `class RetiredPackFieldError(ValueError)` with `code = RETIRED_PACK_FIELD`, attributes `file`, `field`, `replacement`, and a message: `<path>: field '<field>' was removed. <replacement>. See docs/migrations/charter-pack-cutover.md.`
     - `reject_retired_fields(raw: Mapping[str, Any], *, file: str, path: Path | None) -> None`.
     It lives in `charter.offering.packs` because the descriptor model is there (C-007; no import of `charter.activation`: `tests/architectural/test_charter_offering_does_not_import_activation.py`).
  2. Descriptor (`src/charter/offering/packs/pack_descriptor.py` after WP04; field around `:62`, docstring `:39`, model `extra="forbid"` at `:48`): delete the field and its docstring lines; add a `model_validator(mode="before")` that calls `reject_retired_fields(data, file="pack.yaml", ...)` **before** pydantic's generic extra-field error, so the operator sees `RETIRED_PACK_FIELD` and not "extra fields not permitted". Make sure the error survives pydantic wrapping (pydantic converts a `ValueError` raised in a validator into a `ValidationError`); if the loader catches `ValidationError`, unwrap the cause or raise from the loader before `model_validate`. Pick the place that keeps a single code path and test it through the real loader.
  3. Lineage (`src/charter/offering/packs/pack_lineage.py`, after WP04): delete the `accompanies` resolution (`resolve_…` around `:200-240`) and `UnresolvedDoctrinePackError` (`:99-115`), plus their callers (`grep -rn accompanies src/`). No replacement concept.
  4. Validator (`pack_validator.py`) and `charter org validate`: a descriptor with the field is a validation finding with code `RETIRED_PACK_FIELD` naming file and field (US3 scenario 4). Reuse the same error, do not re-spell the message.
  5. `packs/built-in/pack.yaml:12` `accompanies_doctrine_pack: null`: delete the line, then regenerate the pack manifest with `spec-kitty doctrine regenerate-graph` (WP15, which creates the `charter pack` home, runs after you); never hand-edit `pack-manifest.yaml` (`tests/architectural/test_pack_manifest_no_author_edit.py`). The manifest is a generated file other WPs also regenerate; log the regeneration.
  6. Any other pack in the repo or test fixtures with the field: `git grep -n accompanies_doctrine_pack -- packs tests src`; fixtures that test the old lineage are deleted with that test; fixtures that merely carried `null` drop the line.
- **Files**: `retired_fields.py`, descriptor/lineage/validator (follow-ups), `packs/built-in/pack.yaml`, `tests/charter/test_retired_pack_fields.py`.
- **Parallel?**: yes.
- **Notes**: the public-packs sidecar PR (OD-2) is out of this WP's code scope; WP24 drafts it (a WP24 subtask) and the orchestrator opens it after merge.

### Subtask T069 – Tests; flip FR-005 xfails

- **Steps**:
  1. Delete tests of deleted code: `tests/specify_cli/test_charter_pack_registry.py`; registry/`default_pack` uses in `tests/charter/test_compiler_charter_yaml.py`, `test_mission_type_activations_seed_read_parity.py`, `test_mission_type_activation_emit.py`, `test_activation_preserves_effective_4253.py`, `tests/specify_cli/cli/commands/test_init_provisioning.py`, `tests/specify_cli/upgrade/test_unify_charter_activation_migration.py`, `tests/doctrine/test_activation_squad_lenses.py`, `test_squad_procedure_single_owner.py`, `test_owner_delivery.py`, `test_retirement_table_consistency.py`, `test_retired_ids_absent.py`, `tests/doctrine/test_pack_lineage.py` / `test_pack_id_identity.py` (or their WP04 destinations). For each: if the test guards behaviour that still exists (for example "retired ids absent from the default list"), retarget it to the `default`/`minimal` preset or the frozen snapshot module; if it tests the deleted mechanism, delete it. Record each decision (file, kept/retargeted/deleted, reason) in the Activity Log. Most should already be handled by WP06/WP09; touch only what remains.
  2. `tests/charter/test_retired_accompanies_doctrine_pack.py` (yours; `test_retired_pack_fields.py` is WP17's): descriptor with the field → `RetiredPackFieldError` with code, file, field, replacement; descriptor without it loads; validator reports the finding; the error message names the runbook; the table lookup is data-driven (a planted second `RetiredField` is rejected the same way).
  3. Positive controls next to every negative assertion (C-006): an unrelated unknown field still fails with pydantic's generic error, proving the retired-field check is specific.
  4. Run the WP13 acceptance tests: green.

## Test Strategy

```bash
make test-fast
uv run --frozen pytest tests/charter/test_retired_pack_fields.py tests/charter/test_retired_accompanies_doctrine_pack.py tests/specify_cli/cli/commands/charter/test_charter_pack_apply_removed.py tests/specify_cli/cli/commands/charter/test_charter_pack_builtin.py -q
uv run --frozen pytest tests/acceptance/charter_pack_cutover/ -q
uv run --frozen pytest tests/charter/ tests/doctrine/ -q            # src/charter/offering/** changed
uv run --frozen pytest tests/specify_cli/cli/commands/charter/ tests/specify_cli/upgrade/ tests/upgrade/test_auto_discovery.py tests/specify_cli/cli/commands/test_init_provisioning.py -q
uv run --frozen pytest tests/cross_cutting/packaging/test_packaging_safety.py -q
uv run --frozen pytest tests/architectural/test_src_reachability_guard.py tests/architectural/test_no_dead_modules.py tests/architectural/test_pack_manifest_no_author_edit.py tests/architectural/test_charter_offering_does_not_import_activation.py tests/architectural/test_doctrine_census.py tests/architectural/test_completion_manifest_freshness.py tests/architectural/test_docs_cli_reference_parity.py tests/architectural/test_ruff_format_enforcement.py -q
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen mypy src/charter/offering/packs/ src/specify_cli/cli/commands/charter/pack.py
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
```

Add any other provisioning tests found with `grep -rl default_charter tests/`. Removing a command changes the completion manifest and the CLI reference: regenerate with `uv run --frozen python -m specify_cli.completion --regenerate` and `uv run --frozen python scripts/docs/build_cli_reference.py` (both generated files; log the regeneration). Never bare `tests/architectural/` or `make test-full`.

## Risks & Mitigations

- **Discovery-wide ImportError** if an old migration still imports a deleted module: run auto-discovery tests immediately after T066.
- **Pydantic swallows the retired-field code**: test through the real loader, not the model alone.
- **Tests deleted that guarded live behaviour**: retarget instead; every decision recorded.
- **Merge conflict with WP15 on `charter/pack.py`**: small, separate hunks; rebase before review.

## Definition of Done

- [ ] First commit removed only the WP13 markers; red output logged.
- [ ] Registry, `activation/packs/`, `default_pack` deleted; no `src` reader of the old `default.yaml`; no stub or alias.
- [ ] `charter pack apply` exits 2; completion manifest and CLI reference regenerated.
- [ ] `accompanies_doctrine_pack` gone from model, lineage, built-in `pack.yaml`; `RETIRED_PACK_FIELD` raised with file, field, replacement; manifest regenerated.
- [ ] Rosters, baselines and allowlists cleaned (each logged).
- [ ] All Test Strategy commands pass; mypy/ruff clean.

## Review Guidance

- Red-on-base → green-on-final for every `pending_until("WP13")` test.
- `git grep` the inventory command from T066: zero code hits in `src/`.
- Check no compatibility path: no module named like the deleted ones, no hidden `apply`.
- Check the retired-field error is raised from one place and carries the code from `retired_fields.py`.
- Check the test-deletion log: each deleted test tested deleted code.
- Confirm mypy/ruff were run.

## Activity Log

> Entries in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-06T19:30:00Z – system – Prompt created.
