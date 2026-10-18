---
work_package_id: WP03
title: 'Identity surfaces: action bundle, activation filter, include, selection block, presets, charter list'
dependencies:
- WP02
requirement_refs:
- FR-007
- FR-008
- FR-017
- NFR-003
subtasks:
- T012
- T013
- T014
- T015
- T016
phase: Phase 2 - Identity surfaces
agent: claude
history:
- at: '2026-10-18T17:40:00Z'
  actor: claude-code/opus
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/action_governance_bundle.py
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/activation/action_governance_bundle.py
- src/charter/activation/drg_activation.py
- src/charter/activation/context_renderers/template_include.py
- src/charter/activation/context_renderers/selection_block.py
- src/charter/activation/preset_application.py
- src/specify_cli/cli/commands/charter/list_cmd.py
- tests/charter/test_action_governance_bundle_activation.py
- tests/charter/test_drg_activation_gate.py
- tests/charter/test_context_include.py
- tests/charter/test_context_selection_render.py
- tests/charter/presets/test_preset_validation.py
- tests/specify_cli/cli/commands/charter/test_charter_list_commands.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP03 – Identity surfaces: action bundle, activation filter, include, selection block, presets, charter list

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
- **Tests**: run the WP's own test files plus the owning subsystem directory (`tests/charter/` and, for `src/charter/offering/**`, `tests/charter_offering/`). Do not run `make test-full` or the whole `tests/architectural/` directory; run only the named gate files.
- **Terminology**: "Mission", never the retired term. Run `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q` when touching prose or `src/charter/offering/`.
- **Commits**: conventional types (`fix`, `feat`, `test`, `refactor`, `docs`); end every commit message with the session attribution lines given to you.
- Stay inside `owned_files`; a small out-of-map edit is acceptable only with a one-line rationale in the commit message and `add-history` note.

## Objectives & Success Criteria

Route the remaining identity surfaces through the identity index so action context, `--include`, the selection block, preset application, the DRG activation filter and `charter list` all agree on declared ids (#6406, FR-007, FR-017).

Done when, with the WP02 fixture org pack:
- action context (`charter context --action implement --mission-type software-dev --json`) delivers `QA_003` and the org tactic `qa-seven` whether the activation lists hold stems or declared ids;
- org-required ids declared as declared ids are delivered;
- `charter context --include directive:QA_003` and `--include directive:qa-003-no-fake-green` both render `Directive QA_003`; likewise `--include tactic:qa-seven` / `tactic:qa-tactic-seven`;
- `charter list` shows an activated org tactic with stem ≠ id as activated (not available), with its declared id alongside the stem;
- the NFR-004 snapshot still passes.

Requirement refs: FR-007, FR-008, FR-017, NFR-003.

## Context & Constraints

- Depends on WP02 (index threaded from `context.py`; fixture builder `tests/charter/org_pack_identity_support.py`).
- `src/charter/activation/action_governance_bundle.py`: `_ActionGovernanceBundle` :110 (carries `service`, `merged`, `roots` — add `identity`); `_resolve_action_bundle` / `_load_action_governance_bundle` :183/:251; :337-343 `project_directives = {_normalize_directive_id(d) for d in _catalog_default_or_activated(...)}`; :341 and :373 normaliser use for activated and org-required directives; `selected_tactics` / `selected_paradigms` :349-358, :378-379 carry raw stems (miss stem ≠ id graph nodes in `_classify_artifact_urns`).
- `src/charter/activation/drg_activation.py`: :331-333 `urns.add(resolve_artifact_urn(kind_enum, stem, ...))` with `except UnknownArtifactIdError: continue`; `_resolve_activated_urns_by_kind` :338-360; `filter_graph_by_activation(graph, pack_context)` :433.
- `src/charter/activation/context_renderers/template_include.py`: :139 `directive_id = normalize_directive_id(identifier)`; :298 generic `repo.get(identifier)`; called from `context.py` `_render_catalog_kind_include_selector` (:386) and `_render_offering_artifact_include` (:229).
- `src/charter/activation/context_renderers/selection_block.py`: :163-164 `lookup_id = normalize_id(artifact_id)`; :254 `normalize_id=normalize_directive_id`; :476-519 `_merge` / `_collect_org_source_map` compare raw `selected_*` against org-required membership.
- `src/charter/activation/preset_application.py`: `_id_key` :286-292 (directive normaliser only); `_Roots` :317-327 owns a `ResolutionPass`; `_union` :456-474 writes org-required declared ids verbatim. `_org_required` :440-453 unchanged.
- `src/specify_cli/cli/commands/charter/list_cmd.py`: :149, :287, :297 compare `AvailableArtifact.artifact_id` (stem, `pack_manager.py:1019`) with the activated set. Import `IdentityIndex` from `charter.activation.api` only (C-002; baseline `tests/architectural/charter_activation_boundary_baseline.yaml`).
- Out-of-map: `context.py` (owned by WP02) — if the include renderers need the index passed, add the keyword at the two call sites with a one-line rationale.

## Subtasks & Detailed Guidance

### Subtask T012 – Red tests

- `tests/charter/test_action_governance_bundle_activation.py`: stem-token list and declared-id-token list for org tactics (`qa-tactic-seven` / `qa-seven`) both deliver `tactic:qa-seven`; org-required declared id delivered; built-in positive control.
- `tests/charter/test_drg_activation_gate.py`: a declared-id token for a non-directive kind keeps its node through `filter_graph_by_activation`.
- `tests/charter/test_context_include.py`: both spellings for directive and tactic resolve.
- `tests/charter/test_context_selection_render.py`: org source attributed for a stem ≠ id selection.
- `tests/charter/presets/test_preset_validation.py`: org-required non-directive declared id counted as present.
- `tests/specify_cli/cli/commands/charter/test_charter_list_commands.py`: activated org tactic with stem ≠ id listed as activated.
Commit red: `test: red repro for #6406 identity surfaces`.

### Subtask T013 – Action bundle and activation filter

- Store the index on the bundle (build once in `_load_action_governance_bundle` if not passed). Map every activated, org-required and selected token through `identity.declared_id(kind, t) or t` before seeding; keep catalog-default behaviour for absent keys (C-007).
- `filter_graph_by_activation(graph, pack_context, *, identity=None)`: resolve tokens through the index (fallback to `resolve_artifact_urn` for anything the index misses); `_resolve_activated_urns_by_kind` uses the shared index.

### Subtask T014 – `--include` and selection block

- `template_include`: `identity.declared_id(kind, identifier)`, falling back to the normaliser for directives; pass the index from `build_charter_context_include`.
- `selection_block`: index-backed `normalize_id` for every kind; `_collect_org_source_map` compares declared ids.

### Subtask T015 – Preset application and `charter list`

- `preset_application._id_key` → `identity.declared_id(kind, id) or id`; build the index from `_Roots`.
- `list_cmd`: activated when `stem in activated or identity.declared_id(kind, stem) in activated`; render the declared id next to the stem when they differ (e.g. `qa-tactic-seven (qa-seven)`); JSON rows gain `declared_id`.

### Subtask T016 – Verify

- Snapshot test passes unchanged; run the suites below.

## Test Strategy

```bash
uv run --frozen pytest tests/charter/test_action_governance_bundle_activation.py tests/charter/test_drg_activation_gate.py tests/charter/test_context_include.py tests/charter/test_context_include_activation.py tests/charter/test_context_selection_render.py tests/charter/presets/ tests/specify_cli/cli/commands/charter/test_charter_list_commands.py tests/charter/test_default_in_force_snapshot.py -q
uv run --frozen pytest tests/charter/ tests/charter_offering/ tests/specify_cli/cli/commands/charter/ -q -p no:randomly
uv run --frozen pytest tests/architectural/test_runtime_charter_activation_boundary.py -q
uv run --frozen mypy --strict <changed src files>
```

## Risks & Mitigations

- `charter list --json` row shape change → additive key only; check `tests/architectural/test_json_contract_enumeration.py` still passes.
- Bundle seeding change could alter NFR-004 → snapshot test.

## Review Guidance

- No remaining `_normalize_directive_id` call outside the index fallback in the touched modules (`git grep normalize_directive_id src/charter/activation`).
- `list_cmd` imports only from `charter.activation.api`.
