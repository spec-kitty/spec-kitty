---
work_package_id: WP10
title: Include, selection block, presets and charter list identity
dependencies:
- WP02
- WP09
requirement_refs:
- FR-007
- FR-017
planning_base_branch: issue-6404-charter-governance-resolution-work
merge_target_branch: issue-6404-charter-governance-resolution-work
branch_strategy: Planning artifacts for this mission were generated on issue-6404-charter-governance-resolution-work. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6404-charter-governance-resolution-work unless the human explicitly redirects the landing branch.
subtasks:
- T043
- T044
- T045
- T046
phase: Phase 2 - Identity surfaces
history:
- at: '2026-10-18T17:40:00Z'
  actor: claude-code/opus
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/context_renderers/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/activation/context_renderers/template_include.py
- src/charter/activation/context_renderers/selection_block.py
- src/charter/activation/preset_application.py
- src/specify_cli/cli/commands/charter/list_cmd.py
- tests/charter/test_context_include.py
- tests/charter/test_context_include_activation.py
- tests/charter/test_context_selection_render.py
- tests/charter/presets/test_preset_validation.py
- tests/specify_cli/cli/commands/charter/test_charter_list_commands.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP10 – Include, selection block, presets and charter list identity

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt. Then load action doctrine: `spec-kitty charter context --action implement --mission-type software-dev --no-mark-loaded`.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission charter-governance-resolution-01M57Z77`). Address every feedback item; record progress with `spec-kitty agent tasks add-history <WPID> --note "..."`.

---

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `issue-6404-charter-governance-resolution-work`
- **Merge target branch**: `issue-6404-charter-governance-resolution-work`

Execution worktrees are allocated per computed lane from `lanes.json`. Start with:

```bash
spec-kitty agent action implement <WPID> --agent claude --mission charter-governance-resolution-01M57Z77
```

Never construct a workspace path by hand.

## Shared Rules (every WP)

- **Red first** (ADR 2026-07-17-1): write the issue-pinned failing test(s) for the WP's acceptance scenarios and commit them on their own *before* the fix commit (`test: red repro for #NNNN ...`). After the fix, keep them as focused tests (not left marked `regression`).
- **Non-vacuity**: every absence/refusal assertion is paired with a positive control on the same fixture (tactic `acceptance-criteria-non-vacuity`).
- **Quality gates** (NFR-001): `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check --force-exclude <changed files>`, `uv run --frozen mypy --strict <changed src files>`; cyclomatic complexity ≤ 15; no new `# noqa` / `# type: ignore`.
- **Tests**: run the WP's own test files plus the owning subsystem directory (`tests/charter/` and, for `src/charter/offering/**`, `tests/charter_offering/`). Subsystem sweeps are large (`tests/charter/` ≈ 3,900 tests): always run them with `-n auto --dist loadfile` (pytest-xdist is installed), never `--dist load`. Do not run `make test-full` or the whole `tests/architectural/` directory; run only the named gate files.
- **Terminology**: "Mission", never the retired term. Run `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q` when touching prose or `src/charter/offering/`.
- **Commits**: conventional types (`fix`, `feat`, `test`, `refactor`, `docs`); end every commit message with the session attribution lines given to you.
- Diagnostic wording for unknown selected ids is fixed Mission-wide (WP02 defines the constant `UNKNOWN_SELECTION_DIAGNOSTIC` in `resolver.py`): `"Unknown selected {kind} '{token}' dropped: not found in built-in, org packs (charter_packs.org.packs) or .kittify/charter-packs/; see 'spec-kitty charter list'."`
- Stay inside `owned_files`; a small out-of-map edit is acceptable only with a one-line rationale in the commit message and `add-history` note.

## Objectives & Success Criteria

Route the rendering and listing surfaces through the identity index: `--include` accepts declared ids and stems for every kind (FR-017), the selection block attributes org sources by declared id, preset application compares declared ids, and `charter list` shows activated stem ≠ id artifacts as activated (FR-007).

Done when, with WP02's fixture org pack:
- `charter context --include directive:QA_003` and `--include directive:qa-003-no-fake-green` both render `Directive QA_003`; likewise `tactic:qa-seven` / `tactic:qa-tactic-seven`; an unknown include still errors (control);
- the selection block attributes `QA_003` to its org pack when selected by stem or id;
- a preset whose org-required non-directive id is a declared id counts it as present;
- `charter list` shows `qa-tactic-seven (qa-seven)` as activated, not available; `charter list --json` rows gain `declared_id` (contract change: update `tests/specify_cli/cli/commands/charter/test_charter_list_commands.py:308` which asserts the exact key set; note it for the changelog).

Requirement refs: FR-007, FR-017.

## Context & Constraints

- Depends on WP02 (index + fixture) and WP09 (owns `context.py`; this WP adds the `identity=` keyword at the include-renderer call site `context.py:459` — an out-of-map edit made after WP09 lands; record it).
- `src/charter/activation/context_renderers/template_include.py`: `_render_offering_artifact_include` :229, `_render_catalog_kind_include_selector` :386; :139 `directive_id = normalize_directive_id(identifier)`; :298 generic `repo.get(identifier)`. `context.py` imports them at :64-65 and calls the selector at :459.
- `src/charter/activation/context_renderers/selection_block.py`: :163-164 `lookup_id = normalize_id(artifact_id)`; :254 `normalize_id=normalize_directive_id`; `_collect_org_source_map` :389; `_merge` :459.
- `src/charter/activation/preset_application.py`: `_id_key` :286-292 (directive normaliser only); `_Roots` :317-327 owns a `ResolutionPass`; `_union` :456-474. `_org_required` :440-453 unchanged.
- `src/specify_cli/cli/commands/charter/list_cmd.py`: :149, :287, :297 compare `AvailableArtifact.artifact_id` (stem, `pack_manager.py:1019`) with the activated set. Import `IdentityIndex` from `charter.activation.api` only (C-002; baseline `tests/architectural/charter_activation_boundary_baseline.yaml`).

## Subtasks & Detailed Guidance

### Subtask T043 – Red tests

- `tests/charter/test_context_include.py` (and `test_context_include_activation.py` if needed): both spellings resolve for directive and tactic; unknown control.
- `tests/charter/test_context_selection_render.py`: org source attributed for a stem ≠ id selection.
- `tests/charter/presets/test_preset_validation.py`: org-required non-directive declared id counted as present.
- `tests/specify_cli/cli/commands/charter/test_charter_list_commands.py`: activated org tactic with stem ≠ id listed as activated; JSON `declared_id`.
Commit red: `test: red repro for #6406 render and list surfaces`.

### Subtask T044 – `--include` and selection block

- `template_include`: `identity.declared_id(kind, identifier)` first, normaliser fallback for directives; pass the index from `build_charter_context_include`.
- `selection_block`: index-backed `normalize_id` for every kind; `_collect_org_source_map` compares declared ids.

### Subtask T045 – Preset application and `charter list`

- `preset_application._id_key` → `identity.declared_id(kind, id) or id`; build the index from `_Roots`.
- `list_cmd`: activated when `stem in activated or identity.declared_id(kind, stem) in activated`; text shows `stem (declared_id)` when they differ; JSON rows gain `declared_id`.

### Subtask T046 – Verify

## Test Strategy

```bash
uv run --frozen pytest tests/charter/test_context_include.py tests/charter/test_context_include_activation.py tests/charter/test_context_selection_render.py tests/charter/presets/ tests/specify_cli/cli/commands/charter/test_charter_list_commands.py tests/charter/test_default_in_force_snapshot.py -q
uv run --frozen pytest tests/charter/ tests/specify_cli/cli/commands/charter/ -q -n auto --dist loadfile
uv run --frozen pytest tests/architectural/test_runtime_charter_activation_boundary.py tests/architectural/test_json_contract_enumeration.py -q
uv run --frozen mypy --strict <changed src files>
```

## Risks & Mitigations

- `charter list --json` key-set change is a contract change → changelog.

## Review Guidance

- `git grep -n normalize_directive_id src/charter/activation/context_renderers/ src/charter/activation/preset_application.py` shows only the documented fallback.
- `list_cmd` imports only from `charter.activation.api`.
