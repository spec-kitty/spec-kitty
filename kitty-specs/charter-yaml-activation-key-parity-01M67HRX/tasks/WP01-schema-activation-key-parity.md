---
work_package_id: WP01
title: Schema/authority parity for the charter.yaml activation keys
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6556-charter-yaml-activation-key-parity
merge_target_branch: issue-6556-charter-yaml-activation-key-parity
branch_strategy: Planning artifacts for this mission were generated on issue-6556-charter-yaml-activation-key-parity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6556-charter-yaml-activation-key-parity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-yaml-activation-key-parity-01M67HRX
base_commit: c7fcf3f64083cc34cd204dbb8886447964e04a1e
created_at: '2026-10-30T23:26:30.252562+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T008
phase: Phase 1 - Red-first fix
history:
- at: '2026-10-30T23:22:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/schemas.py
- tests/charter/test_charter_yaml_model.py
- tests/charter/test_activation_vocabulary_setequal.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Schema/authority parity for the charter.yaml activation keys

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

- `CharterYaml` accepts every key in `charter.activation.pack_manager.ACTIVATION_YAML_KEYS`
  as a flat root field (13/13 today), so a legitimate `charter.yaml` written by the activation
  writer validates (FR-001, SC-001).
- `CharterYaml` declares no activation-shaped field outside the authority — in particular no
  `activated_assets` (FR-002, C-001).
- A guard test fails, naming the keys, if the authority and the model's activation-shaped
  fields differ in either direction (FR-003, SC-002).
- A regression proves the writer→`charter.yaml`→model path end to end for the three keys that
  fail today (FR-004, SC-003).
- Strictness is untouched: `extra="forbid"`, `frozen=True`, the nested-`activation:`
  rejection and the three-state `None`/`[]`/non-empty semantics all still hold, with the
  pre-existing assertions unmodified (NFR-002, C-003).

## Context & Constraints

- Issue: `spec-kitty/spec-kitty#6556`. Mission spec:
  `kitty-specs/charter-yaml-activation-key-parity-01M67HRX/spec.md`; plan and design
  decisions: `plan.md` D1–D4; grounding, reproduction transcript and the import-cycle
  evidence: `research.md` R1–R7.
- The single vocabulary authority is `ACTIVATION_YAML_KEYS` in
  `src/charter/activation/pack_manager.py`. It is derived from `ArtifactKind`, so it grows on
  its own; the model's field list is static, which is why it drifted.
- **Only `src/charter/activation/schemas.py` may change under `src/`** (NFR-003). No writer,
  serializer, ledger or migration edit.
- Do **not** add `activated_assets`: `ArtifactKind.ASSET.activatable is False` and
  `prepare_activation_write(root, {"activated_assets": [...]})` raises
  `ValueError: Unknown activation ledger key(s): ['activated_assets']` (C-001).
- No module-level import from `schemas.py` into `pack_manager` — `pack_manager`'s own import
  chain loads `schemas`, so it would be a circular import (research.md R5). Both test files
  already use a function-scoped import for the authority; keep that idiom.
- Do not run full heavy suites (NO_FULL_HEAVY_SUITES_IN_MISSION). Targeted files only:
  `tests/charter/test_charter_yaml_model.py`,
  `tests/charter/test_activation_vocabulary_setequal.py`.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on main; completed changes must merge back into main. Execution happens in the lane worktree `finalize-tasks` computes; never build a workspace path by hand.
- **Planning base branch**: main
- **Merge target branch**: main

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first: writer → charter.yaml → model regression

- **Purpose**: prove the defect through the pre-existing entry point before touching the
  model. This is the failing test that justifies the fix (DIRECTIVE_034).
- **Steps**:
  1. In `tests/charter/test_charter_yaml_model.py`, add a test that builds a legacy
     (unmigrated) fixture project in `tmp_path`:
     - `.kittify/charter/charter.yaml` — a sound document (copy the shape the file's existing
       helpers build: `schema_version`, `governance`, `directives`, `catalog`, `metadata`),
     - `.kittify/config.yaml` — the `charter:` pointer to that file **plus one already-present
       legacy activation key** (for example `activated_directives: [DIRECTIVE_001]`), and no
       `.kittify/charter/activation.yaml`, so `resolve_ledger_source` answers `LEGACY`.
  2. For each of `activated_skills`, `activated_glossary_packs`, `activated_anti_patterns`:
     `apply_yaml_write(prepare_activation_write(root, {key: ["some-id"]}))`, then
     `CharterYaml.model_validate(dict(load_charter_yaml(root / ".kittify/charter/charter.yaml")))`.
  3. Assert the key is on disk **and** the document validates.
  4. Run it and record the failing output (three `extra_forbidden` failures) in your progress
     note: `spec-kitty agent tasks add-history WP01 --note "red: ..."`.
- **Files**: `tests/charter/test_charter_yaml_model.py`; imports from
  `charter.activation.charter_yaml_io` (`load_charter_yaml`, `apply_yaml_write`) and
  `charter.activation.pack_manager` (`prepare_activation_write`).
- **Parallel?**: No — this is the red gate for T003.
- **Notes**: build the fixture per test (or per parametrized case) so no case inherits a
  sibling's written key. If the writer refuses a key, that is a genuine finding — stop and
  report it rather than adjusting the key list.

### Subtask T002 – Red-first: parametrize the flat-root field test over the authority

- **Purpose**: replace the hard-coded ten-name parametrization (a second mirror of the
  vocabulary) with the authority, so "the model accepts every legal key" becomes a
  behavioural assertion.
- **Steps**:
  1. In `tests/charter/test_charter_yaml_model.py`, change
     `test_activation_field_is_flat_root_attribute`'s `parametrize` list to
     `tuple(ACTIVATION_YAML_KEYS)` via a module-level helper with a function-scoped import:
     `from charter.activation.pack_manager import ACTIVATION_YAML_KEYS`.
  2. Run it; record the three failing ids (`activated_glossary_packs`, `activated_skills`,
     `activated_anti_patterns`) in a progress note.
- **Files**: `tests/charter/test_charter_yaml_model.py`.
- **Parallel?**: Can be done with T001.
- **Notes**: do not drop the `mission_type_activations` / `activated_kinds` coverage — they
  are in the authority, so the parametrization keeps them.

### Subtask T003 – Declare the three missing fields

- **Purpose**: the fix. Make the model agree with the writer.
- **Steps**:
  1. In `src/charter/activation/schemas.py`, add to `CharterYaml` beside the existing
     activation fields, in authority order (the tuple order is
     `… activated_mission_step_contracts, activated_glossary_packs, activated_skills,
     mission_type_activations, activated_anti_patterns`):

     ```python
     activated_glossary_packs: list[str] | None = None
     activated_skills: list[str] | None = None
     activated_anti_patterns: list[str] | None = None
     ```
  2. Correct the class docstring: it says "the ten `activated_*` / `mission_type_activations`
     fields below"; state that the field names mirror the single authority
     `charter.activation.pack_manager.ACTIVATION_YAML_KEYS` and that
     `tests/charter/test_activation_vocabulary_setequal.py` pins the equality, so a new
     activatable kind fails the gate until the model declares it. Mention explicitly that
     `ACTIVATION_YAML_KEYS` is imported lazily in the test (not at module scope here) because
     `pack_manager` already imports this module.
  3. Keep every other field, the `model_config`, the `schema_version` pattern and the
     three-state semantics untouched (NFR-002, C-003).
- **Files**: `src/charter/activation/schemas.py`.
- **Parallel?**: No.
- **Notes**: `_OPTIONAL_EMPTY_OMIT_KEYS` and the serializers are key-driven; do not add the
  new names there unless a test proves they are emitted when empty (they must not be).

### Subtask T004 – Both-directions parity gate + the `activated_assets` case

- **Purpose**: the anti-drift guard, so this defect class cannot come back (FR-003, C-001).
- **Steps**:
  1. In `tests/charter/test_activation_vocabulary_setequal.py`, add
     `test_charter_yaml_activation_fields_set_equal_to_authority`:
     - build the model's set as every declared field whose name starts with `activated_` or
       is `mission_type_activations` (from `CharterYaml.model_fields`),
     - compare with `frozenset(ACTIVATION_YAML_KEYS)` using a message that names
       `missing` and `stray` explicitly, so a future maintainer is told what to add or drop.
  2. Add `test_charter_yaml_has_no_activated_assets_field` asserting
     `"activated_assets" not in CharterYaml.model_fields` with a comment citing
     `ArtifactKind.ASSET.activatable` and the writer's refusal.
  3. Update the module docstring's list of "hand-restated copies" to name the model as the
     fourth surface now guarded.
- **Files**: `tests/charter/test_activation_vocabulary_setequal.py`.
- **Parallel?**: No — needs T003's fields to pass.
- **Notes**: the expectation must come from the authority, never from a literal list; a
  literal would recreate the mirror this gate exists to prevent. Add a short non-vacuity
  demonstration (a local `set` mutation or a planted-name assertion) only if it stays
  readable — do not build a second AST gate for this.

### Subtask T005 – Keep strictness, prove it

- **Purpose**: "accepts the authority" must not decay into "accepts anything `activated_*`".
- **Steps**:
  1. Add a case to `tests/charter/test_charter_yaml_model.py` showing an unknown key such as
     `activated_not_a_kind` is still rejected with `extra_forbidden`.
  2. Confirm the pre-existing strictness tests (`test_rejects_nested_activation_mapping`, the
     three-state cases, the `schema_version` pattern cases) pass **unmodified** — do not edit
     their assertions.
- **Files**: `tests/charter/test_charter_yaml_model.py`.
- **Parallel?**: No.
- **Notes**: if a strictness test needs an edit to pass, that is a design failure — stop and
  report instead.

### Subtask T008 – Every legal key at once

- **Purpose**: cover the spec's "a charter that carries every legal activation key at once"
  edge case, so acceptance is proven at set level and not only key by key.
- **Steps**:
  1. In `tests/charter/test_charter_yaml_model.py`, build one document from a valid catalog and
     set every name in `ACTIVATION_YAML_KEYS` to `["some-id"]` (a loop over the authority; do
     not hand-list the names).
  2. Assert `CharterYaml.model_validate(doc)` succeeds and that each attribute reads back the
     list (or that `model_dump()` carries each key).
- **Files**: `tests/charter/test_charter_yaml_model.py`.
- **Parallel?**: Can follow T003.
- **Notes**: this is the combination case; a per-key pass with a set-level failure here means
  the field block is incomplete.

## Test Strategy

- Commands (from the lane worktree, venv ready):
  - `uv run pytest tests/charter/test_charter_yaml_model.py tests/charter/test_activation_vocabulary_setequal.py -q`
  - `uv run pytest tests/charter -q` (the wider charter slice, still targeted, not a heavy suite)
  - `uv run ruff check src/charter/activation/schemas.py tests/charter/test_charter_yaml_model.py tests/charter/test_activation_vocabulary_setequal.py`
  - `uv run mypy src/charter/activation/schemas.py` (or the repository's configured invocation) —
    typed sources changed, so compiler diagnostics are part of the gate.
- Red proof to record before T003: the T001/T002 failures, verbatim enough to show
  `extra_forbidden` naming the key.

## Risks & Mitigations

- **Circular import** if the authority is imported at module scope in `schemas.py` → keep the
  import function-scoped inside tests; if you need it in `src/`, use the existing
  `functools.lru_cache` lazy-accessor idiom (`charter_yaml_io._allow_activation_keys`).
- **Loosening `extra`** to silence the error → forbidden; T005 pins it.
- **A tautological parity test** (expectation read from the model itself) → derive the
  expectation from `ACTIVATION_YAML_KEYS` only.
- **Fixture leakage** between parametrized cases → build the project directory per case.

## Review Guidance

- Confirm the red run was captured before the fix (progress history shows it).
- Confirm `git diff src/` touches only `src/charter/activation/schemas.py`.
- Confirm the parity test would fail on `main`: mentally add/remove a key and check the
  assertion message names it.
- Confirm no pre-existing assertion in `test_charter_yaml_model.py`'s strictness tests changed.

## Progress & Status

Progress, history, and status live in the status event log (`status.events.jsonl`) — never
in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
