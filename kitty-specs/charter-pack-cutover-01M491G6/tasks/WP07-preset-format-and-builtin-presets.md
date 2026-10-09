---
work_package_id: WP07
title: Preset format, discovery and built-in presets
dependencies:
- WP05
- WP06
requirement_refs:
- FR-002
- FR-004
- FR-019
planning_base_branch: issue-3732-charter-pack-rename
merge_target_branch: issue-3732-charter-pack-rename
branch_strategy: Planning artifacts for this mission were generated on issue-3732-charter-pack-rename. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3732-charter-pack-rename unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-pack-cutover-01M491G6
base_commit: 5fddfac375c951b9e16ffed947b4524447249e9c
created_at: '2026-10-07T12:53:23.229255+00:00'
subtasks:
- T035
- T036
- T037
- T038
- T039
- T040
phase: Phase 2 - Presets and promotion
history:
- at: '2026-10-06T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/packs/presets.py
create_intent:
- src/charter/offering/schemas/activation-preset.schema.yaml
- src/charter/offering/packs/presets.py
- packs/built-in/presets/default.yaml
- packs/built-in/presets/minimal.yaml
- tests/charter/presets/test_preset_model.py
- tests/charter/presets/test_preset_discovery.py
- tests/charter/presets/test_builtin_presets.py
- tests/charter/presets/test_preset_validation.py
- tests/charter/presets/test_preset_manifest_hashing.py
- tests/charter/presets/test_preset_scaffold.py
execution_mode: code_change
owned_files:
- src/charter/offering/schemas/activation-preset.schema.yaml
- src/charter/offering/schemas/README.md
- src/charter/offering/packs/presets.py
- packs/built-in/presets/default.yaml
- packs/built-in/presets/minimal.yaml
- tests/charter/presets/test_preset_model.py
- tests/charter/presets/test_preset_discovery.py
- tests/charter/presets/test_builtin_presets.py
- tests/charter/presets/test_preset_validation.py
- tests/charter/presets/test_preset_manifest_hashing.py
- tests/charter/presets/test_preset_scaffold.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Preset format, discovery and built-in presets

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

Activation presets become **pack data** with a documented, validated format (FR-019), discovered by the charter layer from any pack (FR-004), and the built-in pack ships `default` and `minimal` presets under `packs/built-in/presets/` (FR-002):

- `default` lists **no** artifact ids and **no** `activated_kinds`; it carries only `mission_type_activations` (the built-in mission types). Every built-in artifact is therefore effective after applying it, and it cannot drift (#5323).
- `minimal` keeps today's curated `activated_directives` / `activated_tactics` and `mission_type_activations: [software-dev]`, and **drops** `activated_kinds: [directives, tactics]` (that gate switches off six kinds the file's own comment says stay open — a defect, architecture squad B3).
- A preset is not an `ArtifactKind`, has no URN, and is hashed by the pack manifest.
- `validate_pack` validates presets (malformed file or unresolvable id is named), so `charter org validate` does now and `charter pack validate` does once WP15 creates it. The acceptance tests that invoke `charter pack validate` flip at WP15; this WP proves the behaviour with unit-level tests in its own test files and through `charter org validate`.
- `charter org init` scaffolds an example preset.

This WP does **not** apply presets (WP08), list them on the CLI (WP08), or repoint mission-type provisioning (WP09).

Done when every acceptance test in `tests/acceptance/charter_pack_cutover/` marked `pending_until("WP07")` (FR-002 preset content; FR-019 `charter org validate`, scaffold and manifest hashing) is green with the marker removed.

## Context & Constraints

- Read first: `spec.md` FR-002, FR-004, FR-019, Key Entities; `data-model.md` "Activation preset" and "Charter Pack"; `contracts/activation-preset.schema.yaml`; `research/postspec-squad-architecture.md` B3 and S4; `research/package-split-and-paths.md` §B.3 (kernel path constants) and §B.4 clause (b).
- Upstream state: WP04 put the pack model and tooling in `src/charter/offering/packs/` (`pack_manifest.py`, `builtin_manifest.py`, `pack_validator.py`, `pack_descriptor.py`, `extends.py`, `pack_assembler.py`) behind the `charter.packs` facade; WP05 put org-charter composition in `src/charter/activation/org_charter.py`; WP02 created `src/kernel/charter_pack_paths.py` with `PRESETS_DIRNAME` and `pack_presets_dir(pack_root)`; WP06 created `charter.activation.effective_set`. Verify each with `ls`/`grep` first and record any difference.
- **Path authority (FR-016 gate, WP03)**: a `"presets"` segment in a path-construction context outside `kernel/charter_pack_paths.py` fails `tests/architectural/test_charter_pack_path_authority.py`. Always use `pack_presets_dir(pack_root)`.
- **Layering**: `charter.offering` must not import `charter.activation` (`tests/architectural/test_charter_offering_does_not_import_activation.py` walks the whole AST, lazy imports included). The preset model, discovery and validation live in offering; nothing here may import `charter.activation`.
- **Kind authority**: the kinds a preset may govern are **derived**, never hand-listed (`tests/architectural/test_charter_kind_vocabulary_single_authority.py`). The JSON-schema enum in the contract is illustrative; the validator reads the authority.
- **Pack tiers (C-003)**: only consumer presets go into `packs/built-in`. Pack edits are followed by graph/manifest regeneration.
- **C-001**: `src/charter/activation/packs/default.yaml` and `minimal.yaml` still exist and are still read by `charter_pack_registry` until WP13. Do not delete or alias them here, and do not make the new presets read from them.

## Branch Strategy

- **Strategy**: lane-based; the lane for this WP is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Red-first (C-006 / C-011)

First commit: remove every `pending_until("WP07")` marker and nothing else, run them, see them red, commit.

```bash
grep -rn 'pending_until("WP07")' tests/acceptance/charter_pack_cutover/
uv run --frozen pytest tests/acceptance/charter_pack_cutover/ -q -k "<ids WP01 used for FR-002/FR-004/FR-019>"
git commit -m "test(charter): flip preset-format acceptance tests red (#3732)"
```

Do not change WP01's assertions (C-006). If an acceptance test for FR-004 needs the CLI (`charter pack list`), it belongs to WP08 and should name WP08; if WP01 named WP07 for it, raise it in the Activity Log rather than half-building the CLI here.

## Subtasks & Detailed Guidance

### Subtask T035 – Preset JSON schema (kinds derived from `ArtifactKind`)

- **Purpose**: a documented contract pack authors (and the public-packs sidecar) write against.
- **Steps**:
  1. Create `src/charter/offering/schemas/activation-preset.schema.yaml` from `contracts/activation-preset.schema.yaml`, Draft 2020-12, `additionalProperties: false`, `required: [name, description]`, `name` pattern `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`, `maxLength: 64`.
  2. Decide the governed kinds from the authority (orchestrator ruling, FI-S1): every kind with `ArtifactKind.activatable == True`, minus `skill` and `glossary_pack` (own absence contract); mission types have their own key. That gives **nine** per-kind keys: `activated_{directives,tactics,styleguides,toolguides,paradigms,procedures,agent_profiles,mission_step_contracts,anti_patterns}`, matching `contracts/activation-preset.schema.yaml`. `anti_pattern` is charter-activatable (#5409; `PackContext` reads `activated_anti_patterns`, `pack_context.py:173,277`) although it is excluded from the hand-authorable token set `CHARTER_KIND_TOKENS`, so derive from `ArtifactKind.activatable`, not from `CHARTER_KIND_TOKENS`. `template` and `asset` are not activatable. If `prepare_activation_write` / `ACTIVATION_YAML_KEYS` rejects `activated_anti_patterns`, record it for WP08, whose writer must write and remove it.
  3. `activated_kinds` items: every `ArtifactKind` plural (13; that is the universe `PackContext._read_activated_kinds` and `drg_activation` gate on).
  4. Because a static schema cannot import the authority, generate nothing at runtime from the YAML enum: the schema keeps the enum for documentation, and a test (T040) asserts the schema's per-kind `patternProperties` / `activated_kinds` enum equals the derived sets. If they drift, the test fails, not the user.
  5. Add a row to `src/charter/offering/schemas/README.md`'s table.
- **Files**: the schema, the README.
- **Parallel?**: Yes with T037.
- **Validation**: `jsonschema` validates both built-in presets (T037) against the file.

### Subtask T036 – Preset model + discovery across built-in, org chain, fetched packs

- **Purpose**: one charter-side loader (C-007: no `specify_cli` preset registry).
- **Steps**:
  1. Create `src/charter/offering/packs/presets.py` with:
     - `PRESET_GOVERNED_KINDS: tuple[ArtifactKind, ...]` derived as in T035 (from `ArtifactKind.activatable`, never hand-written), and `preset_activation_keys()` returning the nine `activated_<plural>` keys;
     - a frozen dataclass (or pydantic `BaseModel`, `extra="forbid"`) `ActivationPreset`: `name`, `description`, `activations: Mapping[str, tuple[str, ...]]` (only keys present in the file; absent ⇒ unrestricted; `[]` ⇒ none), `activated_kinds: tuple[str, ...] | None`, `mission_type_activations: tuple[str, ...] | None`, `source: Path`;
     - `PresetFormatError(ValueError)` carrying `path` and a message naming the offending field;
     - `load_preset_file(path: Path) -> ActivationPreset` — strict: rejects unknown keys (naming them; `activated_skills` / `activated_glossary_packs` get a message saying presets do not govern them), rejects `name` ≠ file stem, enforces the name grammar, list-of-unique-non-empty-strings values, and **no context-scoped activation entries** (an `activations:` list as in `org-charter.yaml` is rejected);
     - `discover_presets(pack_root: Path) -> tuple[ActivationPreset, ...]` — reads `pack_presets_dir(pack_root)` (`*.yaml`, sorted by name); a pack without the directory returns `()` (a pack without presets works, spec Edge Cases);
     - `load_preset(pack_root: Path, name: str) -> ActivationPreset` raising a typed `PresetNotFoundError` that carries the available names (WP08 renders `PRESET_NOT_FOUND` from it).
  2. Offering pack enumeration for a project (FR-004): add `OfferingPack(name: str, tier: Literal["built-in", "org", "project"], root: Path)` and `list_offering_packs(repo_root: Path) -> tuple[OfferingPack, ...]`:
     - `built-in` → `charter.offering.pack_paths.built_in_root()` (name `built-in`, matching `packs/built-in/pack.yaml` `name`);
     - each entry of `charter.offering.drg.org_pack_config.load_pack_registry(repo_root, quiet=True).packs` in declaration order → `OfferingPack(entry.name, "org", entry.effective_root(repo_root))`. A pack fetched with `spec-kitty charter fetch` is an org pack whose root is populated; there is no separate "fetched" tier. An unfetched root (directory absent) is listed, and `discover_presets` returns `()` for it;
     - `project` → `kernel.charter_pack_paths.project_pack_root(repo_root)`; the project layer ships no presets (Key Entities) — `discover_presets` is not consulted for it, or returns `()` by contract; document which.
     - Do not resolve or validate artifact ids here; that needs the whole offering and is done by the validator (T038) and the activation engine (WP08).
  3. Export the public names through the `charter.packs` facade (WP04 created `src/charter/packs.py`) as a logged follow-up edit, so `specify_cli` (WP08) imports `charter.packs`, not `charter.offering.packs.presets`. No alias names.
- **Files**: `src/charter/offering/packs/presets.py` (new); `src/charter/packs.py` (logged follow-up edit, owned by WP04).
- **Parallel?**: After T035's kind decision.
- **Notes**: keep functions ≤ 15 complexity: split field checks into small validators. Use `ruamel.yaml` safe loading (the offering already does). Read files as UTF-8.
- **Validation**: unit tests in `test_preset_model.py` and `test_preset_discovery.py` (T040).

### Subtask T037 – Built-in `presets/default.yaml` and `minimal.yaml` (fixed kind gate)

- **Purpose**: FR-002 content.
- **Steps**:
  1. `packs/built-in/presets/default.yaml`:
     ```yaml
     name: default
     description: Every built-in artifact is effective; activates the built-in mission types.
     mission_type_activations:
       - software-dev
       - documentation
       - research
       - plan
     ```
     Take the mission-type list from today's `src/charter/activation/packs/default.yaml:15-19`, and cross-check it with `charter.offering.missions.mission_type_repository.builtin_mission_type_id_set()`; if they differ, stop and record it (do not silently pick one). No `activated_*` key, no `activated_kinds`. A short header comment explaining "absent means unrestricted" is fine; do not mention the retired registry.
  2. `packs/built-in/presets/minimal.yaml`: `name: minimal`, a one-line description, `mission_type_activations: [software-dev]`, `activated_directives` (the five ids in `src/charter/activation/packs/minimal.yaml:34-39`) and `activated_tactics` (`:43-44`). **No** `activated_kinds`. Rewrite the header comment: it must not say `charter pack apply` (FR-018 forbidden token) — say `spec-kitty charter activate --preset minimal`.
  3. Check that every id in both files resolves in the built-in pack (`packs/built-in/directives/`, `packs/built-in/tactics/`).
- **Files**: the two YAML files (new).
- **Parallel?**: Yes with T035/T036.
- **Notes**: the built-in pack is not a Python package; `packs/` ships via hatch `force-include`. Run `tests/cross_cutting/packaging/test_packaging_safety.py` to confirm the new directory ships and nothing from `packs/internal` leaks.
- **Validation**: `test_builtin_presets.py` (T040).

### Subtask T038 – Validator: presets in `charter pack validate` / `charter org validate`; manifest hashes presets

- **Purpose**: FR-019's "validated by `charter pack validate` and `charter org validate` (malformed file or unresolvable id named)" and "hashed by the pack manifest".
- **Steps (validation)**:
  1. Both commands call `validate_pack(...)` (the `doctrine pack validate` handler at `src/specify_cli/cli/commands/doctrine.py:398-422` and `org validate` at `:1092-1122`, through the composing entry WP04 added in `charter.activation.org_charter`). Add preset validation **inside `validate_pack`** in `src/charter/offering/packs/pack_validator.py`, so every caller gets it and no CLI change is needed. Keep it in a new private function `_validate_presets(pack_dir, pack_ids_per_type) -> list[ValidationIssue]` (complexity ≤ 15; `validate_pack` is already long — call, don't inline).
  2. For each file under `pack_presets_dir(pack_dir)`: `load_preset_file`; a `PresetFormatError` → one `ValidationIssue(severity="error", artifact_type="preset", artifact_id=<stem>, file=<path>, message=<names the field>, category="preset_format")`.
  3. Id resolution: every id must resolve in the offering this validator can see — the built-in ids (`_load_built_in_ids_per_kind()` at `pack_validator.py:1186`; for `mission_step_contracts`, which has no built-in content dir, use `_built_in_node_urns()` at `:615`) ∪ the pack's own ids (`pack_artifact_ids_per_type`, already collected in `validate_pack`) ∪ the pack's ancestors when `parent_pack` lineage resolves locally (`resolve_pack_lineage_order` in `extends.py`/`pack_lineage.py` — check what it needs; if ancestors cannot be located from a bare directory, do not guess: resolve against built-in ∪ own and record the decision). Directive ids compare after normalisation (stem ↔ `DIRECTIVE_NNN`), reusing the existing offering normaliser rather than writing a new one. An unresolved id → error naming the preset file and the id (`category="preset_unresolved_id"`). `mission_type_activations` ids resolve against built-in ∪ pack mission types.
  4. `activated_kinds` consistency (FR-002): when present, it must include the plural of every kind the preset lists ids for; otherwise error naming the missing plurals (this is the check that would have caught the released `minimal`).
  5. `charter org validate` reaches the same code through `validate_pack`; confirm with a test, do not add a second path.
- **Steps (manifest)**:
  6. In `src/charter/offering/packs/pack_manifest.py` add an optional `presets: list[PresetEntry] | None = None` to `PackManifest` (`PresetEntry`: `name`, `path` (pack-relative POSIX), `content_hash`), serialised only when not `None` (mirror the `constituents` pop in `_serialize_manifest`), included in `manifest_hash`. Packs without presets keep byte-identical manifests, so `SCHEMA_VERSION` (`"1"`) does not need a bump; if a test proves otherwise, bump and record why.
  7. Add `enumerate_presets(pack_root) -> list[PresetEntry]` in `presets.py` (LF-normalised bytes, the single sanctioned hasher `hash_content_bytes` — WP04 moved it to offering), and call it from `builtin_manifest.build_builtin_manifest` and from the pure manifest writer WP04 extracted (`write_pack_manifest` with primitive fields), so fetched/assembled packs hash their presets too. Sorted by name for determinism.
  8. `pack_manifest.py`, `builtin_manifest.py`, `pack_validator.py` and `src/charter/packs.py` are **owned by WP04** (completed upstream). These are follow-up edits allowed by the tasks.md rule; log each in the Activity Log with a one-line rationale. Keep the edits minimal and additive.
- **Files**: `src/charter/offering/packs/presets.py`; logged edits in `pack_validator.py`, `pack_manifest.py`, `builtin_manifest.py`.
- **Parallel?**: After T036.
- **Validation**: `test_preset_validation.py`, `test_preset_manifest_hashing.py` (T040).

### Subtask T039 – `charter org init` scaffolds an example preset

- **Purpose**: FR-019 "scaffolded by `charter org init`".
- **Steps**:
  1. Put the example content in offering, not in the CLI: `presets.py` gains `EXAMPLE_PRESET_NAME = "starter"` (any grammar-valid name other than `default`/`minimal`, which would shadow nothing but confuse readers) and `render_example_preset() -> str` (valid against the schema; lists no ids, so it validates against any offering; a comment shows how to add `activated_directives`).
  2. The minimal scaffold writer `_run_minimal_scaffold` (`src/specify_cli/cli/commands/doctrine.py:1012-1035`) writes three files; make it also write `pack_presets_dir(pack_path) / f"{EXAMPLE_PRESET_NAME}.yaml"` and print the line. Update the `org_init` docstring (`:991-1001`, "three files") and `_ORG_PACK_README_STUB` (`:936-952`, "Contents" list) to mention `presets/`. `doctrine.py` is owned by WP03 (upstream; WP15 moves its handlers to `charter/` and WP16 deletes it); this is a small logged follow-up edit — keep it to those lines so WP15's move carries it.
  3. The `--template` path renders a user template; do not inject a preset there.
- **Files**: `presets.py`; logged edit in `src/specify_cli/cli/commands/doctrine.py`.
- **Parallel?**: Yes (independent of T038 once T036 exists).
- **Validation**: `test_preset_scaffold.py`: `CliRunner` invokes `charter org init <tmp>/pack`, then `charter org validate <tmp>/pack` exits 0 and the preset file exists and loads.

### Subtask T040 – Tests; regenerate pack manifest; flip FR-002/FR-019 xfails

- **Steps**:
  0. WP04 is expected to have created `tests/charter/packs/` (the home of the moved pack-tooling tests). If it does not exist, create it with an `__init__.py` like its siblings under `tests/charter/` and record that.
  1. `tests/charter/presets/test_preset_model.py`: valid file loads; each rejection (unknown key, `activated_skills`, `activated_glossary_packs`, name ≠ stem, bad grammar, >64 chars, non-list value, duplicate ids, empty string id, context-scoped `activations:` list) raises `PresetFormatError` naming the field; absent vs `[]` preserved.
  2. `test_preset_discovery.py`: pack without `presets/` → `()`; two presets sorted; `load_preset` unknown → `PresetNotFoundError` listing names; `list_offering_packs` on a tmp project with two org packs (one with presets, one without) returns built-in, both org packs in declaration order, and `project`.
  3. `test_builtin_presets.py`: both built-in presets load; `default` has no `activated_*` and no `activated_kinds` and a non-empty `mission_type_activations`; `minimal` has no `activated_kinds`; every `minimal` id resolves; both validate against the JSON schema; **kind authority**: the schema's per-kind pattern and `activated_kinds` enum equal the derived sets, and `preset_activation_keys()` equals the `activated_<plural>` of every activatable `ArtifactKind` minus `skill` and `glossary_pack` (so it contains `activated_anti_patterns`).
  4. `test_preset_validation.py`: `validate_pack` on a tmp pack with a malformed preset, an unresolvable id, an `activated_kinds` that omits a listed kind → three errors naming file and field/id; a clean pack → no preset issues; `validate_pack(packs/built-in)` reports no preset issues; `charter org validate` (CliRunner) surfaces the same error.
  5. `test_preset_manifest_hashing.py`: a pack with presets gets `presets` entries and a different `manifest_hash`; a pack without presets has no `presets` key and an unchanged hash; changing a preset byte changes its hash.
  6. Regenerate the built-in manifest and graph with the command that exists at this point in the mission (the `charter` home lands in WP15):
     ```bash
     uv run --frozen spec-kitty doctrine regenerate-graph
     uv run --frozen spec-kitty doctrine regenerate-graph --check
     ```
     Commit `packs/built-in/pack-manifest.yaml` as regenerated output (never hand-edited; `tests/architectural/test_pack_manifest_no_author_edit.py`). Log it as a regenerated shared file.
  7. Turn the WP07 acceptance tests green.

## Test Strategy

```bash
make test-fast
uv run --frozen pytest tests/acceptance/charter_pack_cutover/ -q
uv run --frozen pytest tests/charter/packs/ -q
uv run --frozen pytest tests/charter/ tests/doctrine/ -q        # src/charter/offering/** changed
uv run --frozen pytest tests/cli/test_doctrine_org_commands.py tests/cli/test_doctrine_commands.py -q
uv run --frozen pytest tests/architectural/test_charter_offering_does_not_import_activation.py tests/architectural/test_charter_kind_vocabulary_single_authority.py tests/architectural/test_pack_manifest_no_author_edit.py tests/architectural/test_charter_pack_path_authority.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_dead_modules.py tests/architectural/test_layer_rules.py -q
uv run --frozen pytest tests/cross_cutting/packaging/test_packaging_safety.py -q
uv run --frozen spec-kitty doctrine regenerate-graph --check
uv run --frozen ruff check src/charter/offering/packs/ src/charter/packs.py src/specify_cli/cli/commands/doctrine.py tests/charter/packs/
uv run --frozen ruff format --check --force-exclude <every file you touched>
uv run --frozen mypy src/charter/offering/packs/ src/charter/packs.py src/specify_cli/cli/commands/doctrine.py
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
```

If `test_charter_pack_path_authority.py` has a different name in WP03's final state, run the FR-016 gate WP03 created. Record every command and its pass/fail counts in the Activity Log.

## Commit discipline

Conventional subjects with `#3732`, e.g. `feat(charter): activation preset model and discovery (#3732)`, `feat(packs): built-in default and minimal presets (#3732)`, `feat(charter): validate and hash presets (#3732)`. First commit is the red flip. Never push to `main`.

## Risks & Mitigations

- **Offering→activation import** sneaking in through `ACTIVATION_YAML_KEYS`: derive in offering from `ArtifactKind`; never import `charter.activation` from `presets.py`.
- **Manifest churn**: regenerate, never hand-edit; packs without presets must stay byte-identical (proves the field is optional).
- **`regenerate-graph` choking on the new `presets/` directory**: if the graph builder or a layout gate treats unknown top-level dirs as artifacts, teach it that `presets/` is not an artifact kind directory (it is not an `ArtifactKind`), with a test; record the file you touched.
- **Validator id resolution too strict for org packs that extend a parent**: covered by T038 step 3's recorded decision; do not silently downgrade an unresolved id to an advisory.

## Definition of Done

- [ ] `src/charter/offering/packs/presets.py` declares `__all__` (charter `__all__` Declaration Convention, binding per C-007).

- [ ] Red-first commit; every `pending_until("WP07")` test green on the final commit.
- [ ] Schema in `src/charter/offering/schemas/`, kinds derived and pinned by a test; contract-enum deviation recorded.
- [ ] `presets.py` in offering: model, strict loader, discovery, offering-pack enumeration, example renderer, manifest enumeration; no `charter.activation` import.
- [ ] `packs/built-in/presets/{default,minimal}.yaml` as specified; `minimal` has no `activated_kinds`.
- [ ] `validate_pack` validates presets (format, ids, kind-gate consistency); `charter org validate` covered by test.
- [ ] Pack manifest hashes presets; built-in manifest regenerated and fresh.
- [ ] `charter org init` writes and validates an example preset.
- [ ] All Test Strategy commands run and recorded; ruff/format/mypy clean, no new suppressions; out-of-ownership edits logged.

## Review Guidance

- Red on base → green on final for every acceptance test that names WP07; markers removed, assertions unchanged.
- `grep -rn '"presets"' src/` returns only `kernel/charter_pack_paths.py`.
- `default.yaml` preset has exactly `name`, `description`, `mission_type_activations`.
- Try `spec-kitty doctrine pack validate` on a copy of `packs/built-in` with one preset id misspelled: the error names the file and id.
- Confirm mypy was run on touched typed sources.

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
- 2026-10-07T13:46:06Z – claude – shell_pid=10916 – python-pedro: step 0 gate repair (a07b9cdb): retired_fields SCOPE_ORG_CHARTER uses kernel ORG_CHARTER_FILENAME; pinning inventory regenerated (scripts/ci/derive_pinning_inventory.py); remediation-effectiveness table re-pinned -8 lines; ruff-format exclude: dropped 2 deleted WP10 test files + 3 WP10-neutralised migrations (ratchet clean-entry check); dead doc paths repointed (OrgPackMissingError in org_pack_loader.py; pack_assembler at charter/offering/packs). Lane venv lacked ruff module; ran uv sync --frozen --all-extras.
- 2026-10-07T13:46:08Z – claude – shell_pid=10916 – python-pedro: out-of-ownership logged edits: pack_validator.py (_validate_presets in validate_pack, categories preset_format/preset_unresolved_id/preset_kind_gate), pack_manifest.py (optional presets field, popped when None, write_pack_manifest enumerates presets), builtin_manifest.py (presets), charter/packs.py (facade exports preset functions incl. write_example_preset; constants not exported - FR-010 facade test needs module-owned objects), doctrine.py (_run_minimal_scaffold writes presets/starter.yaml; docstring/README stub), tests/charter/presets/__init__.py, dead_symbol_allowlist.yaml (pack_presets_dir REVIVED entry removed), pack-manifest.yaml regenerated (regenerate-graph). Acceptance: test_upgrade_migration._nfr001_param - pre_rc35 case unmarked (was pending WP12 but only waited for presets/default.yaml; XPASSed strict); assertions unchanged. Decisions: id resolution = built-in DRG URNs + pack's own nodes (parent_pack ancestors not locatable from a bare dir); directive ids normalised via id_normalizer; mission types resolved as mission_type URNs; project tier ships no presets (OfferingPack.ships_presets False); default mission types == builtin_mission_type_id_set().
- 2026-10-07T13:46:17Z – claude – shell_pid=10916 – python-pedro: tests run - tests/charter/presets 59+ passed; tests/charter + tests/doctrine (builtin_manifest, pack_manifest_schema, counts, charter_profile, pack_version, org_pack_augmentation, drg, pack_skills, assets) + tests/cli/test_doctrine_org_commands.py + test_charter_mission_type_commands.py + packaging safety: 4780 passed 23 skipped; acceptance charter_pack_cutover: 112 passed 1 skipped 241 xfailed, 0 failed 0 xpassed; gates (facades, kind-vocab, offering-no-activation, path authority, layer rules, dead modules/symbols, allowlist contract, manifest no-author-edit, terminology, dead src paths, remediation, ruff ratchet, pinning) green; make test-fast 2281 passed 8 skipped; ruff check . clean; regenerate-graph --check fresh; mypy no new errors (1 pre-existing no-any-return in pack_validator._plural_to_urn_kind).
