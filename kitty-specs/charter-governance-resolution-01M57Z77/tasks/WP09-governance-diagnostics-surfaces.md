---
work_package_id: WP09
title: Governance diagnostics on compact, JSON, CLI, doctor and prompt surfaces
dependencies:
- WP02
requirement_refs:
- FR-010
- FR-011
- NFR-003
subtasks:
- T039
- T040
- T041
- T042
phase: Phase 2 - Identity surfaces
agent: claude
history:
- at: '2026-10-18T17:40:00Z'
  actor: claude-code/opus
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/compact.py
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/activation/compact.py
- src/charter/activation/context_json.py
- src/charter/activation/context_contract.py
- src/charter/activation/context.py
- src/specify_cli/cli/commands/charter/context.py
- src/specify_cli/runtime/doctor.py
- src/runtime/next/prompt_builder.py
- tests/charter/test_compact.py
- tests/charter/test_charter_context_directives_source.py
- tests/charter/test_context_schema_version_ledger.py
- tests/charter/test_procedures_json_array.py
- tests/charter/test_glossary_json_reference.py
- tests/specify_cli/cli/commands/test_charter_org_directive_identity.py
- tests/runtime/test_doctor_unit.py
- tests/agent/test_workflow_charter_context.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP09 – Governance diagnostics on compact, JSON, CLI, doctor and prompt surfaces

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

Make the unknown-selection diagnostics from WP02 visible on every governance surface and pass them through to `charter context --json` (#6407, FR-010).

Done when, with WP02's fixture org pack and `selected_directives: [QA_003, NOPE_999]`:
- compact `charter context` text shows the `NOPE_999` diagnostic line and the full directive list (no "governance unresolved");
- `charter context --action plan --mission-type software-dev --json --no-mark-loaded` exits 0 and has a top-level `diagnostics` list containing the `NOPE_999` text, and directive entries include `{"id": "QA_003", ...}` with its org source; `diagnostics == []` on a clean fixture (positive control);
- `context_schema_version` is `1.4.0`, with a ledger entry;
- `spec-kitty doctor` (governance check) reports a warning naming `NOPE_999` instead of a green "Resolved governance";
- the runtime prompt builder's legacy governance block shows a diagnostics line.

Requirement refs: FR-010, FR-011, NFR-003.

## Context & Constraints

- Depends on WP02 (`GovernanceResolution.diagnostics` populated; `UNKNOWN_SELECTION_DIAGNOSTIC`; fixture `tests/charter/org_pack_identity_support.py`).
- `src/charter/activation/compact.py:311-338` `_resolve_governance_summary` (catches `GovernanceResolutionError` :320-324; diagnostics rendered :267-268, merged :337).
- `src/charter/activation/context_json.py:135-170` `_load_project_directives_with_source` swallows errors (:155-159); `_project_directive_entries_with_source` :230 returns `(entries, directives_source)`.
- `src/charter/activation/context.py`: `build_charter_context` :151, `build_charter_context_include` :360, `build_charter_context_json` :468 (payload :520-538).
- `src/charter/activation/context_contract.py`: `CONTEXT_SCHEMA_VERSION` :40 (1.3.0), `CONTEXT_CONTRACT_TOP_LEVEL_KEYS` :82-100.
- **CLI rebuilds the JSON**: `src/specify_cli/cli/commands/charter/context.py:158-192` prints a fixed key list from the builder payload, so a new key never reaches the CLI unless added there. Add `diagnostics`. (`directives_source` is also missing there today; leave it unless trivially additive — record the choice.)
- `src/specify_cli/runtime/doctor.py:138-180` `check_governance_resolution` (green "Resolved governance" :172); `src/runtime/next/prompt_builder.py:533-545` `_legacy_governance_context`.
- Schema-version pins outside the ledger: `tests/charter/test_procedures_json_array.py:129-131`, `tests/charter/test_glossary_json_reference.py:166-167`.
- Build the identity index once per entry point in `context.py` and pass it to `resolve_project_governance` (NFR-003); WP03/WP10 add the bundle/include keyword wiring.

## Subtasks & Detailed Guidance

### Subtask T039 – Red tests

- `tests/charter/test_compact.py`: compact text has the `NOPE_999` diagnostic and the directive list, plus `QA_003` shown (not the guessed id).
- `tests/specify_cli/cli/commands/test_charter_org_directive_identity.py` and `tests/charter/test_charter_context_directives_source.py`: CLI JSON as described (exit 0, `diagnostics`, `QA_003` entry with org source); clean-fixture control.
- Doctor and prompt builder tests (find with `grep -rln check_governance_resolution tests/` and `grep -rln _legacy_governance_context tests/`; e.g. `tests/runtime/test_doctor_unit.py`, `tests/next/test_prompt_builder_unit.py`).
Commit red: `test: red repro for #6407 diagnostics surfaces`.

### Subtask T040 – Compact, JSON builder, contract, CLI pass-through

- `compact`: unknown ids arrive in `resolution.diagnostics`; keep the `except GovernanceResolutionError` for genuine failures (template set).
- `context_json`: return the resolution's diagnostics with the entries; `context.py` payload gains top-level `"diagnostics": [...]` (always present).
- `context_contract.py`: add `"diagnostics"` to `CONTEXT_CONTRACT_TOP_LEVEL_KEYS`; bump `CONTEXT_SCHEMA_VERSION` to `1.4.0`; ledger entry in `tests/charter/test_context_schema_version_ledger.py`; update the two other pins.
- CLI `charter context --json`: add `"diagnostics": structured.get("diagnostics", [])`.

### Subtask T041 – Doctor and prompt builder

- `check_governance_resolution`: when `resolution.diagnostics` contains unknown-selection entries, return a warning-level check listing them (keep the existing pass message otherwise).
- `_legacy_governance_context`: append `Diagnostics: ...` when present.

### Subtask T042 – Verify

- Snapshot test passes unchanged; suites below.

## Test Strategy

```bash
uv run --frozen pytest tests/charter/test_compact.py tests/charter/test_charter_context_directives_source.py tests/charter/test_context_schema_version_ledger.py tests/charter/test_procedures_json_array.py tests/charter/test_glossary_json_reference.py tests/specify_cli/cli/commands/test_charter_org_directive_identity.py tests/charter/test_default_in_force_snapshot.py -q
uv run --frozen pytest tests/charter/ tests/runtime/ tests/next/ -q -n auto --dist loadfile
uv run --frozen pytest tests/architectural/test_json_contract_enumeration.py -q
uv run --frozen mypy --strict src/charter/activation/compact.py src/charter/activation/context_json.py src/charter/activation/context_contract.py src/charter/activation/context.py src/specify_cli/cli/commands/charter/context.py src/specify_cli/runtime/doctor.py src/runtime/next/prompt_builder.py
```

## Risks & Mitigations

- `runtime` → `charter` boundary: `prompt_builder.py` already imports `resolve_project_governance`; add no new charter imports (check `tests/architectural/test_runtime_charter_activation_boundary.py`).
- Schema bump is additive; changelog notes it.

## Review Guidance

- `diagnostics` present in builder payload **and** CLI output.
- Doctor no longer reports green for a typo'd selection.
