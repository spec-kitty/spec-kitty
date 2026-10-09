---
work_package_id: WP15
title: Charter homes for every doctrine command
dependencies:
- WP05
- WP08
- WP13
- WP14
requirement_refs:
- FR-006
- SC-004
planning_base_branch: issue-3732-charter-pack-rename
merge_target_branch: issue-3732-charter-pack-rename
branch_strategy: Planning artifacts for this mission were generated on issue-3732-charter-pack-rename. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3732-charter-pack-rename unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-pack-cutover-01M491G6
base_commit: e3921ae28c164f809681f7ff2d6d1c1b160398dc
created_at: '2026-10-08T03:16:57.448919+00:00'
subtasks:
- T075
- T076
- T077
- T078
- T079
phase: Phase 4 - Removal (no aliases, no shims)
history:
- at: '2026-10-06T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- src/specify_cli/cli/commands/charter/authoring.py
- src/specify_cli/cli/commands/charter/org.py
- src/specify_cli/cli/commands/charter/pack_tooling.py
- src/specify_cli/cli/commands/charter/pack_asset.py
- src/specify_cli/cli/commands/charter/consistency_check.py
- tests/specify_cli/cli/commands/charter/test_charter_pack_tooling.py
- tests/specify_cli/cli/commands/charter/test_charter_pack_asset.py
- tests/specify_cli/cli/commands/charter/test_charter_consistency_check.py
- tests/specify_cli/cli/commands/test_doctor_charter_packs.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/charter/_app.py
- src/specify_cli/cli/commands/charter/authoring.py
- src/specify_cli/cli/commands/charter/org.py
- src/specify_cli/cli/commands/charter/pack_tooling.py
- src/specify_cli/cli/commands/charter/pack_asset.py
- src/specify_cli/cli/commands/charter/consistency_check.py
- src/specify_cli/cli/commands/charter/mission_type.py
- src/specify_cli/cli/commands/_doctrine_asset.py
- src/specify_cli/cli/commands/doctor.py
- src/specify_cli/cli/commands/_cutover_doctor.py
- .github/workflows/packs.yml
- Makefile
- packs/internal/README.md
- packs/internal/assets/test-quality-scan.py
- packs/internal/procedures/executive-debrief-generation.procedure.yaml
- packs/internal/procedures/test-suite-quality-assessment.procedure.yaml
- packs/internal/skills/report-debrief.skill.md
- packs/internal/toolguides/TEST_QUALITY_TRIAGE.md
- packs/internal/toolguides/test-quality-triage.toolguide.yaml
- tests/specify_cli/cli/commands/charter/test_charter_pack_tooling.py
- tests/specify_cli/cli/commands/charter/test_charter_pack_asset.py
- tests/specify_cli/cli/commands/charter/test_charter_consistency_check.py
- tests/specify_cli/cli/commands/test_doctor_charter_packs.py
- tests/specify_cli/cli/commands/test_doctor_doctrine_collisions.py
- tests/specify_cli/cli/commands/test_doctor_doctrine_integrity.py
- tests/specify_cli/cli/commands/test_doctor_doctrine_org_layer.py
- tests/specify_cli/cli/commands/test_doctor_doctrine_selections.py
- tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py
- tests/specify_cli/test_doctor_doctrine.py
- tests/cli/test_doctor_doctrine_selections_snapshot.py
- tests/architectural/test_doctrine_regenerate_graph_roundtrip.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP15 – Charter homes for every doctrine command

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

After WP18 lands, the `/ad-hoc-profile-load` skill is deleted: load profiles with `spk-charter-profile-load` instead (use whichever exists in your checkout).

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile list` and pick the best match for `task_type: implement` on `src/specify_cli/cli/commands/charter/`.

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

Every `spec-kitty doctrine` leaf gets a named `charter` home (FR-006 table), `doctor doctrine` becomes `doctor charter-packs`, `charter pack consistency-check` becomes `charter consistency-check` (OD-8), and every in-repo caller moves in the same WP. The `doctrine` group itself stays registered until WP16 deletes it; in this WP it re-registers the **same handler objects** imported from their new charter homes.

| Old leaf | New home | Handler today |
|---|---|---|
| `doctrine fetch` / `new` / `validate` | `charter fetch` / `new` / `validate` (already registered) | `doctrine.py:132,653,841` → move to `charter/authoring.py` |
| `doctrine org init` / `org validate` | `charter org init` / `org validate` (already registered) | `doctrine.py:956,1092` (`org_app`) → move to `charter/org.py` |
| `doctrine pack validate` / `pack assemble` | `charter pack validate` / `pack assemble` | `doctrine.py:398,428` → `charter/pack_tooling.py` |
| `doctrine regenerate-graph [--check]` | `charter pack regenerate-graph [--check]` | `doctrine.py:251` (+ `_doctrine_root` `:222`, `_read_graph_source` `:347`, `_emit_regen_result` `:365`) → `charter/pack_tooling.py` |
| `doctrine asset list` / `asset path` | `charter pack asset list` / `asset path` | `_doctrine_asset.py:125,158` → `charter/pack_asset.py` |
| `doctrine mission-type list` | `charter mission-type list --include-inactive` (exists, `charter/mission_type.py:195`) | help text only |
| `charter pack consistency-check` | `charter consistency-check` | `charter/pack.py:37` → `charter/consistency_check.py` |
| `doctor doctrine [--json]` | `doctor charter-packs [--json]` (JSON keys unchanged) | `doctor.py:1077` |

Done means: each replacement exits with the old spelling's recorded exit code (`cli_before.json`; `doctor` exits 1 on the fixture because its org pack is not fetched) on the same fixture as the old spelling with the same key output (SC-004's first half); `doctor doctrine` and `charter pack consistency-check` exit 2 (renamed here, no alias); the `doctrine` group's old spellings exit 2 with WP16; `.github/workflows/packs.yml`, `Makefile`, the pack-manifest `generated_by` line, `AGENTS.md` (CLAUDE.md is a symlink to it), `packs/internal/**` and remediation strings name the new spellings; the #4836 guidance gate stays green; every WP01 test marked `pending_until("WP15")` (FR-006) is green.

## Context & Constraints

- `spec.md` FR-006, FR-007 (next WP), OD-3, OD-8, US3, SC-004, C-001, C-003.
- `contracts/cli.md` command map.
- `research/runtime-seams.md` §4: the 11 leaves with file:line, the in-repo caller inventory (CI, Makefile, manifest, CLAUDE.md, `packs/internal` 9 files, `packs/built-in` hits, `src` remediation strings, living docs, tests), the `doctor doctrine` JSON key inventory and the rename recommendation.
- Upstream: WP05 moved pack tooling to `charter.offering.packs` and adapters to `specify_cli.charter_packs` (the moved handlers import from there; confirm paths); WP07 made `charter pack validate`'s validator also check `presets/`; WP08 rewrote `charter pack list` and `charter pack path <pack>` in `charter/pack.py`.
- The #4836 gate `tests/architectural/test_no_deprecated_doctrine_command_in_guidance.py` computes the migrated set from the two Typer apps: a `doctrine` command counts as migrated exactly when the `charter` app registers the **same handler object**. Once `pack validate`, `pack assemble`, `regenerate-graph` and `asset` are registered on both apps with the same function, every shipped-guidance citation of their `doctrine` spelling (skills, both packs, living docs, `src` string literals; not docstrings/comments) fails the gate. That is the mechanism that forces T078; do not weaken the gate (WP16 rewrites it).

Constraints:

- **C-001**: no alias. The doctrine group keeps working only because WP16 has not deleted it yet; do not add new hidden spellings.
- **C-003**: `packs/internal` stays internal; editing either pack trips the pack-manifest regen gate: regenerate with the **new** command after the edit.
- **Files you edit but do not own** (each edit logged in the Activity Log with a one-line rationale):
  - upstream-owned: `src/specify_cli/cli/commands/doctrine.py` (WP03 upstream; WP16 deletes it next: you remove the moved bodies and import the handlers), `src/specify_cli/cli/commands/charter/pack.py` (WP08; you remove `consistency-check`; WP13, upstream, already deleted `apply` there), `src/charter/offering/packs/builtin_manifest.py` (`GENERATED_BY`, WP04's move), remediation strings in `src/charter/**` (`activation/kind_vocabulary.py:480,662`, `activation/activation_engine.py:102`, `offering/drg/merge.py:843`).
  - downstream-owned, edited early because the #4836 gate turns red the moment you register the moved handlers on both apps (command spellings only, nothing else in those files): `src/specify_cli/cli/commands/_profile_health_render.py` (WP21), `src/specify_cli/cli/commands/mission_type.py` and `regen.py` (WP16), `packs/built-in/tactics/common-docs-write.tactic.yaml`, `common-docs-find.tactic.yaml` (WP16/WP22), `packs/built-in/procedures/onboard-external-agent-to-pack.procedure.yaml` (WP22), `AGENTS.md` (WP22; FR-006 names CLAUDE.md as a WP15 caller), the living docs listed in T078 step 7 (WP16/WP22), and `docs/context/charter.md` (WP24). WP16's prompt plans some of the same command-spelling edits; when WP16 runs it finds them done.
  - `src/specify_cli/cli/commands/_doctrine_collect.py` belongs to WP14 in this phase: do not edit it (its hits are docstrings).
- Generated files you regenerate (not hand-edit; no WP owns them): `packs/built-in/pack-manifest.yaml`, `src/specify_cli/_completion_manifest.json`, `docs/api/cli-commands.md`, `docs/development/docs-retrieval-index.yaml`. Log each regeneration.
- `docs/migrations/doctrine-local-overlay-to-org-layer.md` is historical (occurrence map `do_not_change`; WP24 adds a banner). `packs/built-in/agent_profiles/doctrine-daphne.agent.yaml:114` names `spec-kitty doctrine regenerate-graph` but the file is `do_not_change` (C-004): do not edit it; record it for WP22/WP25 (an instruction inside a C-004 file still names a removed command).
- Code style: ruff + mypy clean, complexity ≤ 15, constants for repeated help strings, no unexplained suppressions.
- Commit often (`feat(charter): charter pack regenerate-graph home (#3732)`), never push to `main`. Change the CI workflow in the same commit as the command it calls.

## Branch Strategy

- **Strategy**: lane-based; the lane is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`

> Populated automatically by `spec-kitty agent mission finalize-tasks`. Do not change manually.

## Red-first (C-006 / C-011)

First commit: remove the `pending_until("WP15")` strict-xfail markers in `tests/acceptance/charter_pack_cutover/` (`grep -rn 'pending_until("WP15")' tests/acceptance/charter_pack_cutover/`): each FR-006 replacement runs on the shared fixture with the recorded exit code and key output, `doctor charter-packs --json` keys equal the old `doctor doctrine --json` keys, in-repo callers use the new spellings. WP01's flip map (`test_cli_surface.py`): the FR-006 rows not yet built (`pack validate/assemble/regenerate-graph/asset`, `consistency-check`, `doctor charter-packs`), `test_fr006_in_repo_callers_use_charter_spellings`, and the FR-007 rows for `doctor doctrine` and `charter pack consistency-check` (both old spellings must exit 2 after this WP: no alias). Also every acceptance test that invokes `charter pack validate` (it exists only from this WP): `test_fr019_validate_names_malformed_file_and_unresolved_id`, `test_fr019_malformed_preset_cases[*]` (`test_presets.py`) and `test_us3_4_accompanies_field_rejected` (`test_cli_surface.py`); WP07 and WP13 proved the same validator behaviour with unit-level tests. Run, paste red output, change no assertion. Leave the `doctrine` group rows of `test_fr007_old_spelling_exits_2` marked (WP16).

## Subtasks & Detailed Guidance

### Subtask T075 – Move shared handlers out of `doctrine.py` into `charter/`

- **Purpose**: the handlers live where the command lives; `doctrine.py` becomes a thin registrar that WP16 can delete in one step.
- **Steps**:
  1. Create `src/specify_cli/cli/commands/charter/authoring.py` with `fetch` (`doctrine.py:132-220`), `new` and its helpers (`:589-760`: `_artifact_filename`, `_stub_template`, `_resolve_scaffoldable_kind`, `_resolve_scaffold_root`), `validate` and its helpers (`:762-955`). Move, do not copy (`git mv` is not possible for a partial file: cut and paste, keep the bodies byte-identical except imports, so review can diff them).
  2. Create `src/specify_cli/cli/commands/charter/org.py` with `org_app` and `org_init`, `_run_minimal_scaffold`, `_run_template_render`, `org_validate` (`:108-113`, `:956-1140`).
  3. In `doctrine.py`, delete the moved bodies and import the handler functions and `org_app` from the new modules, registering them on the doctrine apps exactly as before (same objects). Keep the deprecation callback until WP16.
  4. `charter/_app.py` (`:27`, `:73-78`): import `fetch`, `new`, `validate`, `org_app` from the new modules; drop the `doctrine` import. Remove the stale comment "Authoring commands share handlers … with the legacy group" or rephrase it.
  5. Repoint every other importer: `git grep -n "commands.doctrine import\|commands import doctrine\|from specify_cli.cli.commands.doctrine" -- src tests`. Test patch strings (`mock.patch("specify_cli.cli.commands.doctrine.<name>")`) must follow the moved names; otherwise the patch silently targets nothing. For each, check the test still exercises what it says.
- **Files**: `authoring.py`, `org.py`, `doctrine.py`, `_app.py`.
- **Parallel?**: first.

### Subtask T076 – `charter pack validate/assemble/regenerate-graph/asset` homes

- **Steps**:
  1. Create `charter/pack_tooling.py` with `pack_validate` (`doctrine.py:398-427`), `pack_assemble` (`:428-588`), `regenerate_graph` (`:251-346`) and its helpers `_doctrine_root` (rename to `_built_in_pack_root`; it routes through `charter.pack_paths.built_in_root`), `_read_graph_source`, `_emit_regen_result`. Help strings and `--check` semantics unchanged.
  2. Move `src/specify_cli/cli/commands/_doctrine_asset.py` to `charter/pack_asset.py` (`git mv`, then edit): module docstring says `spec-kitty charter pack asset`; the `asset_app` Typer stays; `asset path`'s argument help (`:163`) names `charter pack asset list`.
  3. Register on `charter_pack_app` from `charter/_app.py` (not from `pack.py`, which WP08 owns): `charter_pack_app.command("validate")(pack_validate)`, `.command("assemble")(pack_assemble)`, `.command("regenerate-graph")(regenerate_graph)`, `.add_typer(asset_app, name="asset")`. In `doctrine.py`, register the same functions on `pack_app` / `app` / `asset` so the group still works until WP16.
  4. `charter pack validate` also validates `presets/` (WP07) and reports `RETIRED_PACK_FIELD` (WP13, upstream): the acceptance tests above flip here; it is the same validator call.
  5. `doctrine mission-type list` → `charter mission-type list --include-inactive`: update the help/docstring references in `charter/mission_type.py` (`:8`, `:203-218`) and `cli/commands/mission_type.py:1695` so they no longer call the doctrine spelling "canonical replacement for …" in a way that instructs it; keep one sentence saying it replaced the removed command only if useful.
- **Files**: `pack_tooling.py`, `pack_asset.py`, `_doctrine_asset.py` (moved), `_app.py`, `doctrine.py`, `charter/mission_type.py`, `mission_type.py`.

### Subtask T077 – `charter consistency-check`; `doctor charter-packs`

- **Steps**:
  1. Create `charter/consistency_check.py` with `consistency_check_cmd` moved from `charter/pack.py:37-68` (flags unchanged: `--json`, hidden `--repo-root`). Register as `charter_app.command("consistency-check")` in `_app.py`; delete it from `pack.py` (logged follow-up on WP08's file). Human output says "Active charter is coherent." instead of "Charter pack is coherent." (three meanings, ADR §1). Update `charter/activate.py:393`'s docstring reference.
  2. `doctor.py:1073-1180`: `@app.command(name="charter-packs")`, function `charter_packs_check`, docstring and section comment updated; the docstring's `.kittify/doctrine/` mentions follow FR-016 (`.kittify/charter-packs/`). JSON payload keys unchanged (`_profile_health_render.py:222-233`; keys listed in research §4).
  3. `_profile_health_render.py`: human strings only: `:257` "No org doctrine configured." → "No org charter packs configured."; `:291` "(run spec-kitty doctor doctrine --json …)" → `doctor charter-packs`; docstrings naming the command (`:1`, `:103`, `:168`, `:216`, `:243`, `:268`, `:296`, `:304`). `_doctor_shared.py` and `_doctrine_health.py` docstrings: update if they name the command (`_doctrine_health.py` is unowned; logged).
  4. `_cutover_doctor.py`: replace its `doctor doctrine` mention (find with grep).
  5. Remediation strings that instruct an operator to run `spec-kitty doctor doctrine` (logged follow-ups): `charter/activation/kind_vocabulary.py:480,662`, `charter/activation/activation_engine.py:102`, `charter/offering/drg/merge.py:843`. Docstring mentions elsewhere are WP19–WP21 prose; leave them.
- **Files**: `consistency_check.py`, `_app.py`, `pack.py` (follow-up), `doctor.py`, `_profile_health_render.py`, `_cutover_doctor.py`.

### Subtask T078 – In-repo callers: `packs.yml`, `Makefile`, `generated_by`, AGENTS.md, `packs/internal`, remediation strings

- **Steps**:
  1. `.github/workflows/packs.yml:225` `uv run --frozen spec-kitty doctrine regenerate-graph --check` → `spec-kitty charter pack regenerate-graph --check`; `:229` remediation; `:22`, `:213` prose. Keep job ids and check names unchanged (branch protection keys on them).
  2. `Makefile:47` comment → `spec-kitty charter pack asset path test-quality-scan`.
  3. `GENERATED_BY` (`builtin_manifest.py:48` before WP04; now under `src/charter/offering/packs/`) → `"spec-kitty charter pack regenerate-graph"`, then regenerate the manifest with the new command; never hand-edit `packs/built-in/pack-manifest.yaml:1377` (`test_pack_manifest_no_author_edit.py`).
  4. `AGENTS.md:49` "run `spec-kitty doctrine regenerate-graph`" and `:648` "`spec-kitty doctor doctrine --json`" → new spellings. `:49` also says "(legacy fallback `doctrine.org.packs`)": that fallback is removed by WP14; drop the parenthesis. Leave other prose to WP22.
  5. `packs/internal/**` (9 sites, research §4): `README.md:83`; `assets/test-quality-scan.py:35,39,40`; `procedures/executive-debrief-generation.procedure.yaml:47`; `procedures/test-suite-quality-assessment.procedure.yaml:47`; `skills/report-debrief.skill.md:16`; `toolguides/TEST_QUALITY_TRIAGE.md:36`; `toolguides/test-quality-triage.toolguide.yaml:15,21` → `spec-kitty charter pack asset path …`.
  6. `packs/built-in` command citations: `tactics/common-docs-write.tactic.yaml:54,60`, `tactics/common-docs-find.tactic.yaml:27,49` (`charter pack regenerate-graph`), `procedures/onboard-external-agent-to-pack.procedure.yaml:30,234,238` (`doctor charter-packs`). Command spellings only; tier-sense prose is WP22. Then regenerate the built-in pack manifest/graph.
  7. Living docs with command spellings (then refresh the generated `docs/development/docs-retrieval-index.yaml` with `python scripts/docs/docs_index.py --write`; never hand-edit it): `docs/guides/how-to/governance/create-an-org-doctrine-pack.md`, `docs/architecture/org-doctrine-layer.md`, `docs/architecture/doctrine-kinds.md`, `docs/development/how-to/create-a-doctrine-artifact.md`, `docs/development/how-to/create-a-pack-skill.md`, `docs/development/reference/ci-gate-mechanics.md`, and the one citation in `docs/context/charter.md` (logged follow-up). Command spellings only; no file renames (WP22).
  8. `src/specify_cli/cli/commands/regen.py:17` and any other `src` string literal the #4836 gate flags.
  9. Run the inventory and the gate until both are clean:
     ```bash
     git grep -nE "spec-kitty doctrine (regenerate-graph|pack|asset|mission-type)|doctrine regenerate-graph|doctrine asset (list|path)|doctor doctrine|charter pack consistency-check" -- docs src packs .github Makefile AGENTS.md ':!docs/adr' ':!docs/reports' ':!docs/plans' ':!docs/archive' ':!docs/changelog'
     uv run --frozen pytest tests/architectural/test_no_deprecated_doctrine_command_in_guidance.py -q
     ```
     Remaining hits must each be a docstring/comment (WP19–WP22), the historical runbook, the `doctrine-daphne` profile (C-004, recorded), or `doctrine.py` itself (WP16). List them in the Activity Log.
- **Files**: as listed; regenerated manifests.

### Subtask T079 – Tests; regenerate completion manifest and pack manifest; flip FR-006 xfails

- **Steps**:
  1. New tests, each with a positive control on the same fixture:
     - `tests/specify_cli/cli/commands/charter/test_charter_pack_tooling.py`: `charter pack validate <dir>` (valid pack exit 0; broken pack non-zero naming the file; pack with a malformed preset named), `charter pack assemble` (same flags as before), `charter pack regenerate-graph --check` exit 0 on the repo, exit 1 on a planted stale fragment in a temp copy.
     - `test_charter_pack_asset.py`: `asset list --json` shape equals the old command's; `asset path <id>` resolves; unknown id exits non-zero naming the id.
     - `test_charter_consistency_check.py`: coherent and incoherent fixtures; `--json` shape unchanged; `charter pack consistency-check` is no longer registered under `pack` (exit 2).
     - `tests/specify_cli/cli/commands/test_doctor_charter_packs.py`: JSON keys equal the recorded set (research §4); exit 1 when unhealthy; human "No org charter packs configured."
     - Handler identity: `charter` and `doctrine` apps register the same function objects (so WP16 deletes only registration).
  2. Repoint existing tests that invoke `doctor doctrine` to `doctor charter-packs` (invocation string only, keep their subject): the owned files in the frontmatter, plus as logged follow-ups `tests/architectural/test_builtin_override_policy.py`, `test_json_contract_enumeration.py`, `test_override_policy_parity.py`, `tests/charter/test_reject_not_drop_cli.py`, `tests/doctrine/test_pack_relocation_doctor_gate.py`, `tests/doctrine/test_doctrine_health_glossary_pack.py`, `tests/integration/test_org_pack_subdir_e2e.py`, `tests/specify_cli/cli/commands/test_doctor_operating_procedures.py`, `test_doctor_override_diagnostics.py`, `test_doctrine_hard_fail_surfacing.py`, `tests/specify_cli/cli/commands/charter/test_status_org_layer_completeness.py`, `tests/specify_cli/test_provenance_integration.py`, `tests/specify_cli/tool_surface/test_projection_org_visibility.py` (verify each with `git grep -n "doctor.*doctrine\|\"doctrine\"\]" <file>`; some hits are unrelated dict keys). Tests of `charter pack consistency-check`: `tests/charter/test_consistency_check.py`, `test_cascade.py`, `tests/doctrine/test_activation_parity_guard.py`, `tests/architectural/test_json_contract_enumeration.py`. `tests/architectural/test_doctrine_regenerate_graph_roundtrip.py`: invoke `charter pack regenerate-graph --check` (it shells out: `pip install -e .` first, stale-install gotcha). WP14 (upstream) already converted fixtures in some of the same `test_doctor_*` files: keep its changes.
  3. Regenerate: `uv run --frozen python -m specify_cli.completion --regenerate`; `uv run --frozen python scripts/docs/build_cli_reference.py` (updates `docs/api/cli-commands.md`); `uv run --frozen spec-kitty charter pack regenerate-graph` (pack manifest). Commit the regenerated files with a `chore(generated)` subject.
  4. Run the WP15 acceptance tests: green.

## Test Strategy

```bash
make test-fast
uv run --frozen pytest tests/specify_cli/cli/commands/charter/test_charter_pack_tooling.py tests/specify_cli/cli/commands/charter/test_charter_pack_asset.py tests/specify_cli/cli/commands/charter/test_charter_consistency_check.py tests/specify_cli/cli/commands/test_doctor_charter_packs.py -q
uv run --frozen pytest tests/acceptance/charter_pack_cutover/ -q
uv run --frozen pytest tests/specify_cli/cli/commands/ tests/cli/ tests/charter/ tests/doctrine/ -q     # src/charter/** strings touched
uv run --frozen pytest tests/specify_cli/test_doctor_doctrine.py tests/specify_cli/test_provenance_integration.py tests/integration/test_org_pack_subdir_e2e.py -q
uv run --frozen pip install -e . && uv run --frozen pytest tests/architectural/test_doctrine_regenerate_graph_roundtrip.py -q
uv run --frozen pytest tests/architectural/test_no_deprecated_doctrine_command_in_guidance.py tests/architectural/test_docs_cli_reference_parity.py tests/architectural/test_completion_manifest_freshness.py tests/architectural/test_pack_manifest_no_author_edit.py tests/architectural/test_lifted_cli_doctrine_retirement.py tests/architectural/test_lifted_cli_doctrine_charter_cr02_compat.py tests/architectural/test_json_contract_enumeration.py tests/architectural/test_builtin_override_policy.py tests/architectural/test_override_policy_parity.py tests/architectural/test_ruff_format_enforcement.py -q
uv run --frozen pytest tests/cross_cutting/packaging/test_packaging_safety.py -q
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen mypy src/specify_cli/cli/commands/charter/ src/specify_cli/cli/commands/doctrine.py src/specify_cli/cli/commands/doctor.py src/specify_cli/cli/commands/_profile_health_render.py
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
```

Also run `spec-kitty charter pack regenerate-graph --check` and `make test-quality-scan SCAN_ARGS="--paths tests/status"` once by hand and paste the exit codes. Never bare `tests/architectural/` or `make test-full`.

## Risks & Mitigations

- **CI calls a command that does not exist yet**: the workflow edit lands in the same commit as the command.
- **Mock patch strings target moved names**: grep every `patch("specify_cli.cli.commands.doctrine` and repoint; an unpatched mock passes silently.
- **#4836 gate goes red on guidance you did not expect**: it is the inventory; fix the citation, never allowlist it.
- **Shared files with WP13/WP14** (both upstream, not parallel): small hunks; WP18 may run beside you: never edit a file it owns.
- **Required-check names change**: keep CI job ids and names.

## Definition of Done

- [ ] First commit removed only the WP15 markers; red output logged.
- [ ] Every FR-006 home exists and passes on the shared fixture; the doctrine group re-registers the same handler objects.
- [ ] `charter consistency-check` and `doctor charter-packs` exist; old `charter pack consistency-check` gone; JSON keys unchanged.
- [ ] `packs.yml`, `Makefile`, `generated_by`, `AGENTS.md`, `packs/internal`, built-in command citations, living-doc command spellings and remediation strings updated; inventory grep residue listed.
- [ ] Completion manifest, CLI reference and pack manifest regenerated, not hand-edited.
- [ ] All Test Strategy commands pass; mypy/ruff clean; follow-up edits logged.

## Review Guidance

- Red-on-base → green-on-final for every `pending_until("WP15")` test.
- Diff the moved handler bodies against `doctrine.py` at base: imports aside, identical.
- Run each new command and its old spelling on the same fixture; compare exit codes and JSON.
- Check `packs.yml` and the manifest `generated_by` name the new command, and the manifest was regenerated.
- Check the #4836 gate, docs parity and completion freshness gates are green without new allowlist entries.
- Confirm mypy/ruff were run.

## Activity Log

> Entries in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-06T19:30:00Z – system – Prompt created.
- 2026-10-08T12:00:00Z – claude (implementer-ivan) – Red-first (5e56ed66): removed every `pending_until("WP15")` marker in tests/acceptance/charter_pack_cutover/ (test_cli_surface.py Leaf rows + _FR006/_FR007 WP15 entries, test_fr006_in_repo_callers_use_charter_spellings, test_us3_4_accompanies_field_rejected; test_presets.py test_fr019_validate_names_malformed_file_and_unresolved_id + test_fr019_malformed_preset_cases[*]). No assertion changed. Base run: 17 failed, 269 passed, 1 skipped, 67 xfailed (the 17 = 7 FR-006 homes, in-repo callers, FR-007 doctor + consistency_check, US3-4, FR-019 validate + 5 malformed-preset cases). doctrine-group FR-007 rows stay WP16-marked.
- 2026-10-08T12:30:00Z – claude – T075/T076/T077/T078 (b37cd22b): handlers moved out of doctrine.py into charter/authoring.py (fetch/new/validate), charter/org.py (org_app), charter/pack_tooling.py (pack_validate/pack_assemble/regenerate_graph; `_doctrine_root` -> `_built_in_pack_root`), charter/pack_asset.py (git mv of _doctrine_asset.py), charter/consistency_check.py (from charter/pack.py). Bodies unchanged except: imports, ruff format of the new files (doctrine.py was format-excluded), `_NEW_KIND_HELP` hoisted (mypy name-defined on the inline generator in a default arg), regen stale message names `charter pack regenerate-graph`, consistency-check prints "Active charter is coherent." and its help reads "Check the active charter for coherence against the offering (FR-011).", `charter new` docstring names `charter validate`. doctrine.py is a thin registrar re-registering the same objects (deprecation callback kept). doctor doctrine -> doctor charter-packs (charter_packs_check; docstring `.kittify/charter-packs/`), JSON keys unchanged.
- Out-of-ownership edits (mechanical, logged):
  - src/specify_cli/cli/commands/doctrine.py (WP03/WP16): moved bodies removed, handlers imported and re-registered; docstring and deprecation notice name the charter homes.
  - src/specify_cli/cli/commands/charter/pack.py (WP08): consistency-check removed (moved), unused ProjectContext import dropped.
  - src/specify_cli/cli/commands/charter/activate.py: docstring reference to `charter consistency-check`.
  - src/charter/offering/packs/builtin_manifest.py: GENERATED_BY = "spec-kitty charter pack regenerate-graph"; packs/built-in/pack-manifest.yaml regenerated with the new command.
  - src/charter/activation/cascade.py: _NO_CASCADE_HINT names `charter consistency-check` (remediation string; tests/charter/test_cascade.py assertion flipped accordingly).
  - src/charter/activation/kind_vocabulary.py (x2), activation_engine.py, offering/drg/merge.py: remediation strings name `doctor charter-packs`.
  - src/specify_cli/cli/commands/_profile_health_render.py (WP21): "No org charter packs configured.", "(run spec-kitty doctor charter-packs --json …)", docstrings.
  - src/specify_cli/cli/commands/_doctrine_health.py (unowned): docstrings name `doctor charter-packs`.
  - src/specify_cli/cli/commands/mission_type.py, regen.py (WP16): command spellings in docstrings.
  - packs/built-in tactics common-docs-write/common-docs-find, procedure onboard-external-agent-to-pack (WP16/WP22): command spellings only.
  - AGENTS.md + CLAUDE.md (WP22; identical blobs, not a symlink in this checkout): `charter pack regenerate-graph`, `doctor charter-packs --json`, dropped "(legacy fallback `doctrine.org.packs`)".
  - Living docs (WP16/WP22/WP24), command spellings only: create-an-org-doctrine-pack.md, org-doctrine-layer.md, doctrine-kinds.md, create-a-doctrine-artifact.md, create-a-pack-skill.md, ci-gate-mechanics.md, docs/context/charter.md.
  - Tests repointed (invocation strings / moved module paths / failure-message remediation text): test_builtin_override_policy, test_json_contract_enumeration (charter spellings added beside the still-registered doctrine ones; doctor/consistency-check renamed), test_override_policy_parity, test_doctrine_census (comment), test_no_config_key_spelled_as_module_path (docstring), test_charter_sole_door_doctrine_service / test_no_dead_cli_paths / test_runtime_charter_doctrine_boundary (pack_asset.py path), test_doctrine_regenerate_graph_roundtrip (`charter pack regenerate-graph --check`), test_pack_manifest_no_author_edit (message), tests/charter/{test_reject_not_drop_cli,test_activation_engine,test_cascade,test_project_registration,packs/test_pack_validator}, tests/doctrine/{test_activation_parity_guard,test_builtin_manifest,test_doctrine_health_glossary_pack,test_pack_relocation_doctor_gate,test_inline_ref_rejection,pack_skills/test_health,agent_profiles/*,drg/test_extractor_asset,drg/test_kind_mapping_totality,drg/test_regen_roundtrip,drg/test_org_drg_bridge,drg/test_tiered_standards_non_orphan,drg/migration/test_extractor,drg/migration/test_path_ref_resolver}, tests/integration/test_org_pack_subdir_e2e, tests/specify_cli/{test_doctor_doctrine,test_provenance_integration,charter_packs/test_snapshot}, tests/specify_cli/cli/commands/{test_doctor_*,test_doctrine_hard_fail_surfacing,test_doctrine_asset,test_doctor_json_not_in_project,test_cli_boundary_json_seam,charter/test_status_org_layer_completeness}, tests/cli/test_doctor_doctrine_selections_snapshot.
- Generated (regenerated, not hand-edited): packs/built-in/pack-manifest.yaml (`spec-kitty charter pack regenerate-graph`), src/specify_cli/_completion_manifest.json (`python -m specify_cli.completion --regenerate`), docs/api/cli-commands.md (`python -m scripts.docs.build_cli_reference`), docs/development/docs-retrieval-index.yaml (`python -m scripts.docs.docs_index --write`).
- Inventory grep residue (each a docstring/comment, the historical runbook, the C-004 daphne profile, or doctrine.py): docs/migrations/doctrine-local-overlay-to-org-layer.md (historical, WP24 banner); packs/built-in/agent_profiles/doctrine-daphne.agent.yaml:114 (C-004, record for WP22/WP25); docstrings in src/charter/activation/{action_grain,drg_activation}.py, src/charter/offering/{agent_profiles/operating_procedures,artifact_kinds,drg/merge(:809),drg/override_policy,drg/validator,packs/pack_validator,drg/migration/hand_authored_overlay}.py, src/specify_cli/charter_packs/snapshot.py, src/specify_cli/cli/commands/_doctrine_collect.py (WP14-owned in this phase), charter/_status_collectors.py; doctor.py comment naming the former spelling.

## Carry-over from WP13

`validate_pack` already emits the `RETIRED_PACK_FIELD` finding for `accompanies_doctrine_pack` (scope `pack.yaml`); hook `charter pack validate` into it so `test_us3_4_accompanies_field_rejected` flips. WP13's hunks in `charter/pack.py` were deletions only.
- From WP14: the `doctor doctrine` help docstring (`src/specify_cli/cli/commands/doctor.py:~1094,1100`, mirrored in `_completion_manifest.json` — regenerate, never hand-edit) still names `.kittify/doctrine`.
- Local test environment (from WP14): lane worktrees resolve the project root to the main checkout, which still tracks `.kittify/doctrine` until the lanes merge, so in-process CLI tests there fail with `LEGACY_CHARTER_STATE`. Run CLI-heavy targeted tests in a standalone clone of your lane branch (`git clone --branch <lane> /home/user/spec-kitty <scratch>`; `uv sync --frozen --all-extras`). CI is unaffected.
