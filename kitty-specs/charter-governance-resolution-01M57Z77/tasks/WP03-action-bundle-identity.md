---
work_package_id: WP03
title: Action bundle and DRG activation filter identity
dependencies:
- WP02
- WP09
requirement_refs:
- FR-007
- FR-008
- NFR-003
planning_base_branch: issue-6404-charter-governance-resolution-work
merge_target_branch: issue-6404-charter-governance-resolution-work
branch_strategy: Planning artifacts for this mission were generated on issue-6404-charter-governance-resolution-work. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6404-charter-governance-resolution-work unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-governance-resolution-01M57Z77
base_commit: 35362c3ccd122fa746a8216592dfd28d8169dac5
created_at: '2026-10-18T23:37:39.084141+00:00'
subtasks:
- T012
- T013
- T016
phase: Phase 2 - Identity surfaces
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
- tests/charter/test_action_governance_bundle_activation.py
- tests/charter/test_drg_activation_gate.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Action bundle and DRG activation filter identity

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

Route action-context delivery through the identity index: the action governance bundle and the DRG activation filter resolve activated, org-required and selected tokens (stem or declared id) to declared ids (#6406, FR-007, FR-008). `--include`, selection block, presets and `charter list` are WP10.

Done when, with the WP02 fixture org pack:
- action context (`charter context --action implement --mission-type software-dev --json`) delivers `QA_003` and the org tactic `qa-seven` whether the activation lists hold stems or declared ids;
- org-required ids declared as declared ids are delivered;
- the NFR-004 snapshot still passes.

Requirement refs: FR-007, FR-008, NFR-003.

## Context & Constraints

- Depends on WP02 (index, fixture builder `tests/charter/org_pack_identity_support.py`) and WP09 (owns `context.py`; this WP adds the `identity=` keyword at the `_load_action_governance_bundle` call sites in `context.py` — an out-of-map edit made after WP09 lands; record it).
- `src/charter/activation/action_governance_bundle.py`: `_ActionGovernanceBundle` :110 (carries `service`, `merged`, `roots` — add `identity`); `_resolve_action_bundle` / `_load_action_governance_bundle` :183/:251; :337-343 `project_directives = {_normalize_directive_id(d) for d in _catalog_default_or_activated(...)}`; :341 and :373 normaliser use for activated and org-required directives; `selected_tactics` / `selected_paradigms` :349-358, :378-379 carry raw stems (miss stem ≠ id graph nodes in `_classify_artifact_urns`).
- `src/charter/activation/drg_activation.py`: :331-333 `urns.add(resolve_artifact_urn(kind_enum, stem, ...))` with `except UnknownArtifactIdError: continue`; `_resolve_activated_urns_by_kind` :338-360; `filter_graph_by_activation(graph, pack_context)` :433.


## Subtasks & Detailed Guidance

### Subtask T012 – Red tests

- `tests/charter/test_action_governance_bundle_activation.py`: stem-token list and declared-id-token list for org tactics (`qa-tactic-seven` / `qa-seven`) both deliver `tactic:qa-seven`; org-required declared id delivered; built-in positive control.
- `tests/charter/test_drg_activation_gate.py`: a declared-id token for a non-directive kind keeps its node through `filter_graph_by_activation`.
Commit red: `test: red repro for #6406 action bundle identity`.

### Subtask T013 – Action bundle and activation filter

- Store the index on the bundle (build once in `_load_action_governance_bundle` if not passed; `context.py` passes the one built per invocation). Map every activated and org-required token through `identity.activation_id(kind, t, warnings)` and selected tokens through `identity.selection_id(...) or t` before seeding; keep catalog-default behaviour for absent keys (C-007).
- `filter_graph_by_activation(graph, pack_context, *, identity=None)`: resolve tokens through the index (fallback to `resolve_artifact_urn` for anything the index misses); `_resolve_activated_urns_by_kind` uses the shared index.

### Subtask T016 – Verify

- Snapshot test passes unchanged; run the suites below.

## Test Strategy

```bash
uv run --frozen pytest tests/charter/test_action_governance_bundle_activation.py tests/charter/test_drg_activation_gate.py tests/charter/test_action_bundle_delivery.py tests/charter_offering/test_owner_delivery.py tests/charter/test_default_in_force_snapshot.py -q
uv run --frozen pytest tests/charter/ tests/charter_offering/ tests/specify_cli/cli/commands/charter/ -q -n auto --dist loadfile
uv run --frozen pytest tests/architectural/test_runtime_charter_activation_boundary.py -q
uv run --frozen mypy --strict <changed src files>
```

## Risks & Mitigations

- Bundle seeding change could alter NFR-004 → snapshot test.

## Review Guidance

- `git grep -n normalize_directive_id src/charter/activation/action_governance_bundle.py src/charter/activation/drg_activation.py` returns nothing.
