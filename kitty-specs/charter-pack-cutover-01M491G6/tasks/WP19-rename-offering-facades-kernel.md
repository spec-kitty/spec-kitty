---
work_package_id: WP19
title: Identifier rename R1 — offering, facades, kernel
dependencies:
- WP14
- WP16
- WP17
- WP18
requirement_refs:
- FR-010
planning_base_branch: issue-3732-charter-pack-rename
merge_target_branch: issue-3732-charter-pack-rename
branch_strategy: Planning artifacts for this mission were generated on issue-3732-charter-pack-rename. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3732-charter-pack-rename unless the human explicitly redirects the landing branch.
subtasks:
- T092
- T093
- T094
phase: Phase 5 - Names
history:
- at: '2026-10-06T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: lexical-larry
authoritative_surface: src/charter/offering/
create_intent: []
execution_mode: code_change
owned_files:
- src/charter/README.md
- src/charter/assets.py
- src/charter/glossary_packs.py
- src/charter/mission_steps.py
- src/charter/missions.py
- src/charter/model_routing.py
- src/charter/offering/README.md
- src/charter/offering/__init__.py
- src/charter/offering/agent_profiles/README.md
- src/charter/offering/agent_profiles/diagnostics.py
- src/charter/offering/agent_profiles/profile.py
- src/charter/offering/agent_profiles/repository.py
- src/charter/offering/api.py
- src/charter/offering/assets/models.py
- src/charter/offering/assets/repository.py
- src/charter/offering/base.py
- src/charter/offering/directives/README.md
- src/charter/offering/directives/models.py
- src/charter/offering/directives/repository.py
- src/charter/offering/discovery_recursion.py
- src/charter/offering/drg/README.md
- src/charter/offering/drg/__init__.py
- src/charter/offering/drg/loader.py
- src/charter/offering/drg/migration/__init__.py
- src/charter/offering/drg/migration/extractor.py
- src/charter/offering/drg/migration/id_normalizer.py
- src/charter/offering/drg/models.py
- src/charter/offering/drg/org_pack_loader.py
- src/charter/offering/drg/query.py
- src/charter/offering/drg/reachability.py
- src/charter/offering/glossary_packs/__init__.py
- src/charter/offering/glossary_packs/repository.py
- src/charter/offering/missions/action_index.py
- src/charter/offering/missions/expected_artifact_manifest.py
- src/charter/offering/missions/glossary_hook.py
- src/charter/offering/missions/mission_step_repository.py
- src/charter/offering/missions/models.py
- src/charter/offering/missions/repository.py
- src/charter/offering/missions/step_contracts.py
- src/charter/offering/missions/step_offer_seam.py
- src/charter/offering/missions/step_projection.py
- src/charter/offering/model_task_routing/evaluator.py
- src/charter/offering/model_task_routing/loader.py
- src/charter/offering/pack_paths.py
- src/charter/offering/pack_skills/repository.py
- src/charter/offering/paradigms/README.md
- src/charter/offering/paradigms/models.py
- src/charter/offering/paradigms/repository.py
- src/charter/offering/procedures/models.py
- src/charter/offering/procedures/repository.py
- src/charter/offering/procedures/validation.py
- src/charter/offering/provenance.py
- src/charter/offering/resolver.py
- src/charter/offering/schemas/directive.schema.yaml
- src/charter/offering/schemas/import-candidate.schema.yaml
- src/charter/offering/schemas/mission.schema.yaml
- src/charter/offering/schemas/model-to-task_type.schema.yaml
- src/charter/offering/schemas/occurrence-map.schema.yaml
- src/charter/offering/schemas/paradigm.schema.yaml
- src/charter/offering/schemas/procedure.schema.yaml
- src/charter/offering/schemas/skill.schema.yaml
- src/charter/offering/schemas/styleguide.schema.yaml
- src/charter/offering/schemas/tactic.schema.yaml
- src/charter/offering/schemas/toolguide.schema.yaml
- src/charter/offering/shared/__init__.py
- src/charter/offering/shared/errors.py
- src/charter/offering/shared/exceptions.py
- src/charter/offering/shared/schema_utils.py
- src/charter/offering/spdd_reasons/__init__.py
- src/charter/offering/spdd_reasons/template_renderer.py
- src/charter/offering/styleguides/repository.py
- src/charter/offering/tactics/README.md
- src/charter/offering/tactics/repository.py
- src/charter/offering/template_catalog.py
- src/charter/offering/templates/README.md
- src/charter/offering/templates/agent-onboarding/decomposition-table-template.md
- src/charter/offering/templates/agent-onboarding/onboarded-artifact-set-template.md
- src/charter/offering/templates/agent-onboarding/source-agent-dossier-template.md
- src/charter/offering/templates/architecture/c4-container-mermaid-template.md
- src/charter/offering/templates/architecture/stakeholder-persona-template.md
- src/charter/offering/templates/architecture/user-journey-template.md
- src/charter/offering/templates/diagrams/plantuml/themes/plantuml-theme-bluegray-conversation-template.md
- src/charter/offering/toolguides/models.py
- src/charter/offering/toolguides/repository.py
- src/charter/offering/versioning.py
- src/charter/pack_paths.py
- src/charter/primitives.py
- src/charter/profiles.py
- src/charter/provenance.py
- src/charter/repository_protocol.py
- src/charter/resolution.py
- src/charter/spdd_reasons.py
- src/charter/template_catalog.py
- src/charter/versioning.py
- src/kernel/__init__.py
- src/kernel/errors.py
- src/kernel/glossary_runner.py
- src/kernel/glossary_types.py
- src/kernel/paths.py
- src/kernel/pyproject.toml
- src/kernel/schema_utils.py
- src/kernel/sibling_paths.py
- tests/architectural/_sole_door_scan.py
- tests/charter/test_activate_resolves_no_answers_edit.py
- tests/charter/test_builder_overlay_seam.py
- tests/charter/test_catalog_completeness_4785.py
- tests/charter/test_charter_whole_kind_invariants.py
- tests/charter/test_compiler_scope_filtered_placeholder.py
- tests/charter/test_context.py
- tests/charter/test_context_selection_render.py
- tests/charter/test_context_service_seams.py
- tests/charter/test_doctrine_service_lineage_accessor.py
- tests/charter/test_doctrine_service_unfiltered_mode.py
- tests/charter/test_mission_type_profile_override.py
- tests/charter/test_mission_type_profiles.py
- tests/charter/test_model_task_routing_resolves.py
- tests/charter/test_profile_channel_delivery.py
- tests/charter/test_repository_protocol.py
- tests/consolidation/test_profile_charter_e2e.py
- tests/docs/test_doc_status_durable.py
- tests/docs/test_docs_structural_lint.py
- tests/docs/test_touched_set_gates.py
- tests/integration/test_pack_enhances_partial_fields.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP19 – Identifier rename R1 — offering, facades, kernel

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `lexical-larry`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

(After WP18 the skill is `spk-charter-profile-load`. Also load `spk-practice-bulk-edit` / the bulk-edit skill: this WP is an occurrence-classified bulk edit.)

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

FR-010, slice R1 of `research/package-split-and-paths.md` §C: rename the **retired-tier** sense of "doctrine" in the offering package (`src/charter/offering/**`), the `charter` facade modules and `kernel`, with no aliases (C-001). R1 lands first because downstream names hang off it (R2 = WP20, R3/R4 = WP21).

Done means:

- Every R1 identifier in the table below is renamed at its definition **and at every call site in the repository** (including `charter.activation`, `specify_cli`, `runtime`, tests), in the same commit as the definition, so the tree imports at every commit.
- No `X = Y` alias, no re-export of an old name from any facade, no `__getattr__` shim (C-001).
- Docstrings, comments and README prose in owned files use the charter vocabulary **where the word means the retired tier**; content-sense "doctrine" is kept (T094 rules).
- WP01 acceptance test `test_fr010_retired_identifiers_absent[r1]` (marked `pending_until("WP19")`: the closed R1 identifier list, scanned over `src/charter/offering/**`, `src/kernel/**` and the charter facades) goes red → green.

### R1 rename table (proposed; record the final choice)

| Before | After | Where defined |
|---|---|---|
| `charter.offering.service.DoctrineService` (raw, unfiltered aggregation over the offering's repositories) | `CharterOfferingService` | `src/charter/offering/service.py:23`; exported by `src/charter/offering/__init__.py:5,10` |
| `BaseDoctrineRepository` | `BaseArtifactRepository` | `src/charter/offering/base.py`; exported by `offering/__init__.py:4,9`; subclassed in 13 files |
| `DoctrineLayerCollisionWarning` | `ArtifactLayerCollisionWarning` | `src/charter/offering/base.py:49`; re-exported by `src/charter/drg.py:75,126` |
| `DoctrineArtifactLoadError` | `ArtifactLoadError` | `src/charter/offering/shared/exceptions.py`; `shared/__init__.py` |
| `DoctrineResolutionCycleError` | `ArtifactResolutionCycleError` | same |
| `doctrine_package_dir()` | `offering_package_dir()` | `src/charter/offering/pack_paths.py:244` (`__all__` l.89) |
| `_is_doctrine_package_root` | `_is_offering_package_root` | `src/charter/offering/drg/migration/extractor.py:80` |
| `doctrine_root` parameter/local meaning "the `charter.offering` package root" | `offering_root` | `extractor.py` (37 tokens: `extract_artifact_edges`, `extract_action_edges`, `generate_graph`, `extract_mission_type_edges`, …), `drg/migration/hand_authored_overlay.py:2197-2221` |
| module alias `_doctrine_service_module` (`import charter.offering.service as …`) | `_offering_service_module` | importers in activation (rename at call sites) |

**Homonym decision (record it).** Two classes are called `DoctrineService` today: the raw one above and the activation-aware wrapper `charter.activation.resolver.DoctrineService` (`resolver.py:170`, "Activation-aware wrapper around `charter.offering.service.DoctrineService`"). Callers already disambiguate them with local aliases (`as RawDoctrineService` / `as ActivationAwareDoctrineService`, e.g. `cli/commands/_doctrine_collect.py:239-240`, `charter/activation/compiler.py:1091-1092`). The proposal gives them distinct, meaning-bearing names:

- raw offering aggregation → **`CharterOfferingService`** (this WP);
- activation-aware wrapper (filters by the project's active charter) → **`ActiveCharterService`** (WP20).

They pair with WP17's `ActiveCharterManager`. If you choose differently, record the final names and the reason in the Activity Log and in your first rename commit message, and tell WP20 through the Activity Log, since WP20 must use the matching wrapper name. Local aliases at call sites (`RawDoctrineService`) are removed: import the distinct names directly.

Names that are **not** R1: `bundle.DOCTRINE_DIR` (`src/charter/bundle.py:66`) is retired for the kernel constant by WP02/WP03 (FR-016); `LegacyOrgPackDoctrineKeyWarning` / `_warn_legacy_org_pack_doctrine_key_once` (`offering/drg/org_pack_config.py`) were deleted by WP14 (FR-011); `kernel/doctrine_root.py` was replaced by WP02. If any survives, report it; do not rename a thing that should be gone.

## Context & Constraints

- Read: `.kittify/charter/charter.md`; `spec.md` FR-010, C-001, C-002, C-004, Domain Language table; `occurrence_map.yaml` (categories: `code_symbols`, `import_paths` rename; `user_facing_strings` **manual_review**; exceptions: C-004 names, historical records, mission-slug citations in comments `src/**` `comments:mission-slug` keep); `research/package-split-and-paths.md` §C (sizing, R1 scope, most-frequent names).
- Dependencies: WP14 (shims gone) and WP17 (three names) are done. The package split (WP04/WP05) is done, so `src/charter/offering/packs/**` exists; it is **not** in this WP's owned files (WP04/WP05/WP07/WP13 own it) — rename R1 symbols there as logged follow-ups.
- **No parallel lane**: every WP02–WP18 is upstream of this WP (directly or through WP14, WP16 and WP18). R1 call sites in files they own (`src/charter/offering/artifact_kinds.py`, `drg/merge.py`, `drg/validator.py`, `agent_profiles/operating_procedures.py`, `drg/override_policy.py` carry WP15 remediation strings; `shared/scoping.py`, `drg/migration/hand_authored_overlay.py`, `schemas/agent-profile.schema.yaml` are WP16's; skill prose is WP18's) are logged follow-up edits.
- **Do not edit WP01's `tests/acceptance/charter_pack_cutover/_effective_set.py`** (its digest is pinned in the golden header). If a rename breaks its imports, stop and ask the orchestrator for the WP01 follow-up (fixed helper, regenerated golden, logged).
- **Files you will edit but do not own** (call sites; log each in the Activity Log): `src/charter/offering/service.py` (WP02 owns it for its `.kittify` read-site change; it holds the `DoctrineService` definition you rename — WP02 is upstream and done), `src/kernel/README.md` (WP02), `src/charter/offering/schemas/README.md` (WP07), tests `tests/architectural/test_charter_facades_reexport_doctrine.py` and `test_charter_sole_door_agent_profile_repository.py` (WP04), `tests/charter/test_answers_inert_and_org_union.py`, `tests/integration/test_org_pack_artifact_lifecycle.py`, `tests/specify_cli/test_provenance_integration.py` (WP05), `tests/charter/synthesizer/**` (WP03 glob, e.g. `test_context_reflects_synthesis.py`), `tests/architectural/test_charter_sole_door_doctrine_service.py` (WP21 owns it under a glob and renames it later; update the R1 class names it pins as a one-line edit and log it), `src/charter/drg.py` (WP04 facade: `DoctrineLayerCollisionWarning` export l.75,126), `src/charter/bundle.py` (WP02/WP03), `src/charter/offering/drg/{project_scan,override_policy,org_pack_config}.py`, `src/charter/offering/yaml_utils.py`, `src/charter/offering/packs/**`, the WP15/WP16/WP17 offering files named above, every `src/charter/activation/**` importer (WP20 renames its own identifiers later; you only change R1 names there), `src/specify_cli/**` and `src/runtime/**` importers (`charter_runtime/freshness/computer.py`, `charter_runtime/lint/checks/org_layer.py`, `cli/commands/_doctrine_{asset,collect,health}.py` or their WP15/WP21 successors), skill prose quoting `DoctrineService` in `src/charter/offering/skills/**` (WP18), and test files under `tests/doctrine/**` (WP23 moves that directory later; WP23 runs strictly after this WP).
- Keep **test file names** unchanged here; rename identifiers inside them. File renames of tests are WP23 (T106), which also owns the `pyproject.toml` format-exclude entries that list test paths.
- No `__init__.py` re-export may keep an old name. `src/charter/offering/__init__.py` exports change in place.
- Code style: ruff + mypy clean; `ruff format --check --force-exclude`; complexity ≤ 15; no new suppressions.

## Branch Strategy

- **Strategy**: lane per `lanes.json` (filled by finalize)
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Red-first commit (C-006 / C-011)

```bash
rg -n 'pending_until\("WP19"\)' tests/acceptance/charter_pack_cutover/
```

This is WP01 T008's `test_fr010_retired_identifiers_absent[r1]`: an AST/token scan of `src/charter/offering/**`, `src/kernel/**` and the charter facades for the closed R1 identifier list in `tests/fixtures/charter_pack_cutover/retired_identifiers.yaml` (for example `DoctrineService`, `BaseDoctrineRepository`, `doctrine_root`), with a planted-identifier self-test and a scanned-file floor. Remove only the markers, run them, confirm red, commit `test(acceptance): unmark WP19 FR-010 R1 tests (red) (#3732)`.

## Subtasks & Detailed Guidance

### Subtask T092 – R1 rename: offering, facades, kernel identifiers

- **Purpose**: rename the retired-tier identifiers of the offering layer.
- **Steps**:
  1. Re-measure at your base (counts drift after WP02–WP17):
     ```bash
     python - <<'PY'
     import io, tokenize, collections, pathlib
     c = collections.Counter()
     for root in ("src/charter/offering", "src/kernel"):
         for p in pathlib.Path(root).rglob("*.py"):
             for t in tokenize.generate_tokens(io.StringIO(p.read_text()).readline):
                 if t.type == tokenize.NAME and "doctrine" in t.string.lower():
                     c[(str(p), t.string)] += 1
     for (p, n), k in sorted(c.items()): print(k, n, p)
     PY
     ```
     Record the before-count in the Activity Log (research baseline: `charter/offering` 19 files / 81 tokens, `kernel/doctrine_root.py` 11 — the latter should now be gone).
  2. Rename one symbol family per commit, definition plus all call sites, using exact-word replacement scoped to Python files, then fix stragglers by hand:
     - `DoctrineService` (offering) → `CharterOfferingService`: `from charter.offering.service import DoctrineService` (and `as RawDoctrineService`) everywhere; `from charter.offering import DoctrineService`; type annotations `_doctrine_service_module.DoctrineService`. **Do not** touch `charter.activation.resolver.DoctrineService` (WP20) — check each hit's import origin before replacing. `mypy` will tell you if you crossed them.
     - `BaseDoctrineRepository` → `BaseArtifactRepository` (13 subclass files in `offering/*/repository.py`, `missions/step_contracts.py`, `pack_skills/repository.py`, `activation/mission_type_profile_repository.py:72` (follow-up), `src/charter/repository_protocol.py:13` docstring).
     - Warning and error classes (`base.py`, `shared/exceptions.py`, `shared/__init__.py`, `charter/drg.py` facade). Search for `filterwarnings` / `pytest.warns(DoctrineLayerCollisionWarning` in tests.
     - `doctrine_package_dir` → `offering_package_dir` (`pack_paths.py:54,57,89,244`; importer `extractor.py:37,84`).
     - `doctrine_root` → `offering_root` **only where it means the `charter.offering` package root** (extractor docstring l.1789: "Path to `src/charter/offering/`"; `hand_authored_overlay.py`). Keyword callers (`generate_graph(doctrine_root=…)`) in `src/specify_cli` regenerate-graph code and tests must follow.
  3. `src/charter/offering/__init__.py`: export the new names only; module docstring "Public doctrine package exports." → "Public charter offering exports.".
  4. Facade gates: `tests/architectural/test_charter_facades_reexport_doctrine.py:103` pins `("DoctrineLayerCollisionWarning", "charter.offering.base")`; update to the new name (keep the file name: gate-file renames are WP21/R4). Check `tests/architectural/test_doctrine_public_surface.py` and `test_charter_sole_door_doctrine_service.py` / `_sole_door_scan.py` for pinned class names and update.
  5. `tests/architectural/dead_symbol_allowlist.yaml` keys symbols by name: rename entries for renamed symbols (follow-up; count unchanged).
- **Files**: owned offering/kernel/facade files; call sites as listed in Context.
- **Parallel?**: Families are independent; commit each separately.
- **Notes**: string-based references break silently: `monkeypatch.setattr("charter.offering.service.DoctrineService", …)`, `mock.patch("…DoctrineService")`, `importlib.import_module` + `getattr(…, "DoctrineService")`, dotted names in YAML allowlists. Grep for the bare string, not just the identifier: `rg -n "DoctrineService|BaseDoctrineRepository|DoctrineLayerCollisionWarning|DoctrineArtifactLoadError|DoctrineResolutionCycleError|doctrine_package_dir" src tests scripts`.
- **Validation**: [ ] `uv run python -c "import charter.offering, charter.drg, charter.activation"`; [ ] `uv run mypy src/charter src/kernel` clean; [ ] the before-count step now shows no R1 identifier.

### Subtask T093 – R1 tests follow

- **Purpose**: tests import and assert the new names; no test keeps an old name alive.
- **Steps**:
  1. Owned tests (frontmatter) import R1 names: update imports, annotations, patch strings and assertion messages. Notable: `tests/charter/test_doctrine_service_lineage_accessor.py`, `test_doctrine_service_unfiltered_mode.py` (file names stay; rename test functions/fixtures whose names describe the retired tier, e.g. `test_doctrine_service_*` → `test_offering_service_*`), `tests/charter/test_repository_protocol.py`, `tests/docs/test_docs_structural_lint.py:56,869-873`, `tests/docs/test_touched_set_gates.py:60`, `tests/docs/test_doc_status_durable.py:72`, `tests/integration/test_org_pack_artifact_lifecycle.py`, `test_pack_enhances_partial_fields.py`, the sole-door gates.
  2. Not owned but importing R1 names (logged follow-ups): every file under `tests/doctrine/**` (`rg -l "BaseDoctrineRepository|charter\.offering\.service|DoctrineLayerCollisionWarning|DoctrineArtifactLoadError|DoctrineResolutionCycleError|doctrine_package_dir" tests/doctrine` — about 40), `tests/specify_cli/cli/commands/test_doctor_doctrine_collisions.py`, `tests/specify_cli/test_doctor_doctrine.py`, `tests/specify_cli/cli/commands/test_doctrine_collect.py` (or the WP15 successors), WP17-owned tests that also touch R1 names.
  3. Do not delete tests to make the rename pass; a test that only asserted an alias existed is the exception (there should be none).
- **Files**: owned tests; follow-ups listed.
- **Parallel?**: Alongside T092 (same commits).
- **Validation**: [ ] `uv run pytest tests/charter/ tests/doctrine/ -q` green; [ ] `rg -n "DoctrineService" tests | rg -v "resolver"` returns only WP20-scope (activation wrapper) hits.

### Subtask T094 – R1 docstrings/prose (tier sense only)

- **Purpose**: living prose in the offering, facades and kernel stops naming the retired tier (feeds FR-018), while content-sense "doctrine" survives.
- **Classification rule** (occurrence map `user_facing_strings: manual_review`; record one line per non-obvious judgment in the Activity Log):
  - **Tier sense → rename**: the offer-side layer or its package (`the doctrine package`, `kernel <- doctrine <- charter`, `doctrine layer`, "Doctrine Catalog", "Doctrine Artifact Catalog", "doctrine pack", "project doctrine", `.kittify/doctrine`, "the doctrine root", "src/doctrine"). Replacements: "charter offering" / `charter.offering` (package), "Charter Pack", "project layer" (`.kittify/charter-packs/`), "offering root". Examples: `src/kernel/__init__.py:4,8` (`kernel <- doctrine` → `kernel <- charter`), `src/kernel/schema_utils.py:4-25,39,52,78`, `src/kernel/glossary_runner.py:6,21,31,33`, `src/kernel/glossary_types.py:3,6`, `src/kernel/errors.py:3`, `src/kernel/sibling_paths.py:9`, `src/kernel/paths.py:253,459`, `src/kernel/pyproject.toml:8-10,37` (the dormant `spec-kitty-doctrine` wheel note: historical fact, keep the wheel name but reword the layering), `src/charter/drg.py:1-7` (follow-up), `src/charter/offering/README.md` ("# Doctrine", "The **doctrine** package is a standalone catalog…"), `src/charter/README.md:4`, `offering/service.py:1` "Doctrine service for lazy access to all doctrine repositories", `offering/shared/exceptions.py:1`.
  - **Content sense → keep**: "doctrine" meaning governance content itself — "doctrine alignment" (`templates/architecture/user-journey-template.md:23,234`), "apply doctrine", "doctrine artifacts" where it means the directives/tactics/… themselves rather than the tier (judge each; when the sentence is about the *catalog* or *layer*, it is tier sense), `DIRECTIVE_039`, `doctrine-daphne` (C-004), `018-doctrine-versioning-requirement` (exception).
  - **Always keep**: mission-slug citations in comments (e.g. `doctrine-consumer-surface-missions-extraction-01KZ6G6H`, `kernel/paths.py:111,173`); ADR file names and titles (`docs/adr/...doctrine-layer-merge-semantics.md` cited in `base.py:53`); schema `$id` URLs (`https://spec-kitty.dev/schemas/doctrine/...`, generated by `scripts/generate_schemas.py:107`) — persisted identifiers; record that they were kept.
- **Steps**:
  1. `rg -n -i "doctrine" <owned files>`; classify each hit; edit tier-sense hits.
  2. Generated schemas (`src/charter/offering/schemas/*.schema.yaml`) come from `scripts/generate_schemas.py` (WP16 owns the generator): if a description needs changing, change it in the generator (follow-up, WP16 done by then) and regenerate; never hand-edit generated schema text. Most schema descriptions ("Minimal schema for doctrine paradigms") are content sense: keep.
  3. Templates under `src/charter/offering/templates/**`: classify; "Doctrine Artifact Catalog" (`c4-container-mermaid-template.md:22,43`) is tier sense → "Charter offering"; "Doctrine alignment" is content sense.
  4. After edits: `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`.
- **Files**: owned prose files.
- **Parallel?**: After T092 (names in prose must match the code).
- **Validation**: [ ] every remaining `doctrine` hit in owned files is classified in the Activity Log summary (counts per class are enough for obvious ones).

## Test Strategy

```bash
make test-fast
uv run pytest tests/acceptance/charter_pack_cutover/ -q                 # WP19-marked tests at least
uv run pytest tests/charter/ tests/doctrine/ -q                         # owning subsystems of src/charter/offering/**
uv run pytest tests/kernel/ tests/docs/ tests/integration/test_org_pack_artifact_lifecycle.py \
              tests/integration/test_pack_enhances_partial_fields.py tests/consolidation/test_profile_charter_e2e.py \
              tests/specify_cli/test_provenance_integration.py -q
uv run pytest tests/architectural/test_charter_facades_reexport_doctrine.py \
              tests/architectural/test_doctrine_public_surface.py \
              tests/architectural/test_charter_sole_door_doctrine_service.py \
              tests/architectural/test_charter_sole_door_agent_profile_repository.py \
              tests/architectural/test_charter_offering_does_not_import_activation.py \
              tests/architectural/test_kernel_no_doctrine_import.py \
              tests/architectural/test_layer_rules.py \
              tests/architectural/test_no_dead_symbols.py \
              tests/architectural/test_dead_symbol_allowlist_loader.py \
              tests/architectural/test_doctrine_census.py \
              tests/architectural/test_runtime_charter_doctrine_boundary.py \
              tests/architectural/test_no_legacy_terminology.py -q
uv run spec-kitty charter pack regenerate-graph --check                  # extractor rename must not change the graph
uv run ruff check src tests scripts
uv run ruff format --check --force-exclude <touched .py files>
uv run mypy src/charter src/kernel
```

Never bare `tests/architectural/` or `make test-full`.

## Risks & Mitigations

- **Crossing the homonyms**: replacing the activation wrapper's name by mistake. Mitigation: replace by import origin, run mypy after each family.
- **String references** (patch targets, YAML allowlists) survive a symbol rename silently: grep bare strings.
- **Content-sense prose renamed**: reviewer samples the Activity Log classification; when in doubt keep and record.
- **Graph regeneration drift**: `regenerate-graph --check` must stay green (a parameter rename must not change output).
- **Ownership**: no WP runs in parallel with this one (see Context); every edit outside `owned_files` is a logged follow-up.

## Review Guidance

- Red-on-base → green-on-final for the WP19 acceptance tests.
- R1 table names are gone from `src/` and `tests/` (except the activation wrapper, WP20); no aliases in `__init__.py`, `charter/drg.py` or anywhere (`rg -n "DoctrineService\s*=|as DoctrineService|BaseDoctrineRepository\s*="`).
- Homonym names recorded; WP20 told the wrapper name.
- Prose classification recorded; mission slugs, ADR names, schema `$id`s and C-004 names kept.
- Follow-up edits outside owned files logged with the owner's status.
- mypy over `src/charter` and `src/kernel` clean; format check run with `--force-exclude`.

## Definition of Done

- [ ] Red-first commit, then green.
- [ ] R1 identifiers renamed with all call sites; no aliases.
- [ ] Owned tests updated; follow-up tests updated and logged.
- [ ] Tier-sense prose renamed; classification log in the Activity Log.
- [ ] Commands above run and recorded; terminology gate green.

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
- 2026-10-08T09:20:00Z – claude (lexical-larry) – WP19 started on lane-s at 9f282f47. Before-count (tokenize NAME tokens containing "doctrine" over src/charter/offering, src/kernel, src/charter/*.py): 91 tokens / 20 files (kernel/doctrine_root.py is gone, WP02). R1 identifiers found: BaseDoctrineRepository x13 files, DoctrineService (offering), DoctrineLayerCollisionWarning, DoctrineArtifactLoadError, DoctrineResolutionCycleError, doctrine_package_dir, _is_doctrine_package_root, doctrine_root (extractor 37+, hand_authored_overlay 4, charter/bundle.py 13). bundle.DOCTRINE_DIR, LegacyOrgPackDoctrineKeyWarning, _warn_legacy_org_pack_doctrine_key_once, kernel/doctrine_root.py: none survive.
- 2026-10-08T09:40:00Z – claude – Step 0 (separate commits, red -> green): 13a581c9 census orphans (red: test_no_reached_file_is_orphaned, pack_asset.py -> charter.offering.service, pack_tooling.py -> charter.offering.drg.migration.hand_authored_overlay; fix: two pair-specific ORPHAN_REACHED_EXCEPTIONS entries, ticket #3732, because the owner list is the frozen 01KZPDSR WP05 record and these files are the git-mv successors of WP05-owned _doctrine_asset.py / doctrine.py; green: census file 0 failed). 93b05c0d ruff format-exclude ratchet (red: 4 already-formatted entries charter/pack.py, test_mission_type_activations_seed_read_parity.py, test_pack_id_identity.py, test_charter_pack_builtin.py; removed from pyproject.toml; green 6 passed). d946ce72 pinning inventory regenerated with scripts/ci/derive_pinning_inventory.py (red: reproducibility; line drift only; green 5 passed). 77ed0dc0 kind_vocabulary.py PROJECT_KIND_DIRS comment names the `spec-kitty charter new` scaffolder (WP15 carry-over; out-of-ownership, comment only).
- 2026-10-08T10:05:00Z – claude – Red-first de8d1da4: removed the WP19 entry from _SLICE_PENDING in tests/acceptance/charter_pack_cutover/test_package_split.py (map falls back to no mark). test_fr010_retired_identifiers_absent[r1] RED: 26 findings over 20 files; r2/r3r4/prose stay xfail.
- 2026-10-08T10:40:00Z – claude – Homonym decision (for WP20): raw offering aggregation `charter.offering.service.DoctrineService` -> `CharterOfferingService` (this WP, f78d406d). The activation-aware wrapper `charter.activation.resolver.DoctrineService` is untouched and WP20 must rename it `ActiveCharterService` (pairs with WP17's ActiveCharterManager). Renamed by import origin only; local aliases RawDoctrineService/_RawDoctrineService/InnerDoctrineService removed (distinct name imported directly); `_doctrine_service_module` -> `_offering_service_module`. Sole-door gate test_charter_sole_door_doctrine_service.py: RAW qualname, candidate names {CharterOfferingService, DoctrineService, _build_doctrine_service}, locality-exclusion token substrings and the planted bypass follow (WP20 must drop "DoctrineService" from the candidate set and rename WRAPPER_DOCTRINE_SERVICE_QUALNAME when it renames the wrapper).
- 2026-10-08T11:00:00Z – claude – a50962ec BaseDoctrineRepository -> BaseArtifactRepository (68 occurrences / 37 files). 55c077b1 DoctrineLayerCollisionWarning -> ArtifactLayerCollisionWarning (56/17), DoctrineArtifactLoadError -> ArtifactLoadError (10/3), DoctrineResolutionCycleError -> ArtifactResolutionCycleError (11/3); warning text "Doctrine override:" -> "Artifact override:" together with its only parser (_doctrine_collect.py collision regex).
- 2026-10-08T11:30:00Z – claude – a722927f doctrine_package_dir -> offering_package_dir (14/4), _is_doctrine_package_root -> _is_offering_package_root (5/1), doctrine_root -> pack_root in extractor.py (43), hand_authored_overlay.py (5), charter/bundle.py (14). NAME CHOICE differs from the proposed offering_root: the extractor/overlay parameter carries the built-in pack root (packs/built-in; the offering package dir is one legacy caller shape, detected by _is_offering_package_root), and bundle.py's local is the project pack root (.kittify/charter-packs), so pack_root states what is passed. Stale docstring "Path to src/charter/offering/" corrected. No keyword callers exist. regenerate-graph --check fresh.
- 2026-10-08T12:10:00Z – claude – T094 bf551a0d prose. Classification over owned src files (lines containing "doctrine"): 473 at base -> 201 now. Renamed (tier sense, ~190 lines): layering chains (kernel <- doctrine <- charter -> kernel <- charter.offering <- charter), "runtime -> charter -> doctrine boundary" -> "... -> charter.offering boundary" and "reach doctrine artifacts" -> "reach charter offering artifacts" in 13 facades, "doctrine package/layer/pack/tiers" -> charter offering / offering layer / Charter Pack(s) / Charter Pack tiers, old module paths (doctrine/api.py, doctrine.discovery_recursion, doctrine.drg.models, doctrine/__init__.py, doctrine/resolver.py) -> charter.offering.*, `doctrine regenerate-graph` -> `charter pack regenerate-graph`, `doctor doctrine` -> `doctor charter-packs`, .kittify/doctrine project paths in living descriptions -> .kittify/charter-packs (step_contracts.py; follow-ups artifact_kinds.py, drg/merge.py), READMEs (src/charter/README.md relationship section; offering README "# Doctrine" -> "# Charter offering"), C4 template "Doctrine Artifact Catalog" -> "Charter Offering", SPDD/REASONS "doctrine pack" -> "Charter Pack". Kept: mission-slug citations 64, tests/doctrine paths 25, C-004 (doctrine-daphne) 4, schema $id 11 (persisted ids), ADR paths 3, doc-path links 2, spec-kitty-doctrine wheel name 6, R2/R3 identifier 1; content sense 60 (DRG = Doctrine Reference Graph; doctrine artifacts/references/kinds as governance content; step_offer_seam "doctrine advisory offers"; "Doctrine alignment"; error message "Cycle detected in doctrine artifact references"; generated schema descriptions "Minimal schema for doctrine paradigms"); historical 6 (kernel/pyproject.toml S5 note, "formerly src/doctrine", step_contracts relocation note, missions/repository.py src/doctrine path note); quoted headings/link text of living docs owned by WP22 7; runtime origin labels doctrine/<mission>/... 9 (allowlisted in charter_pack_path_allowlist.yaml for the FR-018 vocabulary work, coupled with activation template_resolver._tier_to_origin); id_normalizer.py wrapper reference 1 (WP20).
- 2026-10-08T12:15:00Z – claude – Out-of-ownership edits (all mechanical R1 call sites or Step 0, logged): src/charter/offering/service.py (WP02; class definition), src/charter/drg.py (WP04 facade export), src/charter/bundle.py (WP02/WP03; local), src/charter/offering/packs/pack_validator.py, artifact_kinds.py (WP15), drg/merge.py (WP15, prose), drg/migration/hand_authored_overlay.py (WP16), src/charter/offering/skills/spk-charter-governance/references/charter-governance-workflow.md (WP18; dotted raw-service name only), src/charter/activation/{_activation_render,action_doctrine_bundle,compiler,context,context_json,context_renderers/template_include,doctrine_service_builder,resolver,kind_vocabulary,mission_type_profile_repository,_catalog_miss,selection_block,mission_type_profiles,org_expected_artifacts}.py (R1 names only), src/specify_cli/cli/commands/{_doctrine_collect,_doctrine_health,charter/pack_asset}.py, src/specify_cli/charter_runtime/lint/checks/org_layer.py, pyproject.toml (Step 0 ratchet), tests/release/pinning_rule_inventory.json (regenerated), tests/architectural/{test_doctrine_census,test_charter_sole_door_doctrine_service,_sole_door_scan,test_charter_sole_door_agent_profile_repository,test_runtime_charter_doctrine_boundary,test_charter_facades_reexport_doctrine}.py, tests/doctrine/** (~40 files), tests/specify_cli/** (doctor/collect/asset/provenance), tests/charter/** (non-owned: synthesizer, answers_inert, etc.), tests/fixtures/mission_type_canonical/.../governance-profile.yaml (comment). WP01's _effective_set.py not touched.
- 2026-10-08T13:30:00Z – claude – c9f7b777: six test files' prose that meant the raw service now says CharterOfferingService (wrapper mentions left for WP20). Additional follow-up file: src/charter/offering/missions/mission_type_repository.py (BaseArtifactRepository prose). Validation (standalone clone): acceptance 306 passed / 1 skipped / 47 xfailed / 0 failed / 0 xpassed; tests/charter+tests/doctrine+tests/kernel 8355 passed / 38 skipped; importers (tests/specify_cli/cli/commands, charter_runtime, doctor/provenance/factory, tests/docs, 3 integration files, consolidation e2e, pinning) 7617 passed / 6 failed — all 6 not WP19: 4 test_upgrade_command (env SPEC_KITTY_NO_UPGRADE_CHECK/NO_NAG set in this container; 58/58 pass with them unset), test_no_new_dangling_module_doc_pointer (docs/migrations/charter-pack-cutover.md pointer from ea922f6d, pre-existing at base; runbook is FR-017 work), test_init_fails_closed_when_the_default_preset_is_missing (passes alone; load flake); 20 gate files 602 passed; make test-fast 2281 passed / 8 skipped; ruff check . clean; ruff format --check . 3435 formatted; mypy src/charter src/kernel 17 errors = 17 at base (identical set, none new); regenerate-graph --check fresh. Subtasks T092-T094 marked done; WP19 moved to for_review.

## Carry-over from WP15 review

- Comment at `src/charter/activation/kind_vocabulary.py:~64` still names `specify_cli.cli.commands.doctrine`'s `new` (now `charter new` in `charter/authoring.py`).
- Known slow tests (not a regression): `test_org_cascade_chain::TestNoOrgPackRegression::*` and `test_charter_activate_commands_cascade_output::TestCascadeOutputAbsence::*` take ~95–115 s each; under heavy `-n` on a loaded box they can hit `pytest.ini` timeout=240. Run them with `-n 4 --dist loadfile` or alone.

## Step 0 — gates red at WP16's base (separate commits, red → green, logged)

- `tests/architectural/test_doctrine_census.py::test_no_reached_file_is_orphaned`: WP15's new `src/specify_cli/cli/commands/charter/pack_asset.py` and `pack_tooling.py` have no census owner/disposition. Add the correct census entries (same mechanism as the other charter command modules); no blanket exemption.
- `tests/architectural/test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_still_genuinely_reformats`: four `[tool.ruff.format].exclude` entries are already formatted — remove them from the exclude list (the ratchet only shrinks).
- `tests/release/test_pinning_inventory_fresh.py`: regenerate with `scripts/ci/derive_pinning_inventory.py` (line drift in `test_workflow_coherence.py`).
- `tests/cli/test_doctrine_*` / `tests/specify_cli/cli/commands/test_doctrine_*` file names: leave for WP21/WP23 per ownership unless your owned_files cover them.
