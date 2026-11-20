---
work_package_id: WP03
title: meta.json path-conventions waiver and history field
dependencies: []
requirement_refs:
- FR-010
- C-006
- NFR-003
planning_base_branch: issue-7566-path-conventions-per-type
merge_target_branch: issue-7566-path-conventions-per-type
branch_strategy: Planning artifacts for this mission were generated on issue-7566-path-conventions-per-type. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7566-path-conventions-per-type unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-path-conventions-per-type-01M7VRQM
base_commit: 44fbe9ab575496d046b7f587a56e7d9419345f49
created_at: '2026-11-20T06:58:29.855568+00:00'
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 1 - Foundation
history:
- at: '2026-11-20T07:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/paths.py
create_intent:
- tests/core/test_path_conventions_waiver_reader.py
- tests/specify_cli/test_record_acceptance_path_conventions_waiver.py
execution_mode: code_change
owned_files:
- src/specify_cli/core/paths.py
- src/specify_cli/mission_metadata.py
- tests/core/test_path_conventions_waiver_reader.py
- tests/specify_cli/test_record_acceptance_path_conventions_waiver.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – meta.json path-conventions waiver and history field

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Record status moves as `claude::python-pedro` (no model name).

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log; address all feedback before completion.

## Markdown Formatting

Wrap HTML/XML tags in backticks; use language identifiers in code blocks.

## Objectives & Success Criteria

- `read_path_conventions_waiver_from_meta(primary_meta_dir)` is the one reader for the per-Mission waiver: `"path_conventions": "waived"` plus a non-blank string `"path_conventions_rationale"` (FR-010).
- The #5298 contracts waiver and the new waiver share one generalized implementation. `tests/core/test_contracts_waiver_reader.py` and `tests/specify_cli/acceptance/test_accept_contracts_waiver.py` pass **unmodified** (behaviour-preserving campsite step).
- `record_acceptance(..., path_conventions_waiver_reason="...")` writes `"path_conventions_waived": {"reason": "..."}` on the history entry. Without it, the entry shape is unchanged (FR-009 storage half).

## Context & Constraints

- Spec FR-009, FR-010, C-006. Contract: `contracts/accept-waiver-contract.md`. Data model: `data-model.md`.
- Existing reader: `src/specify_cli/core/paths.py` (`ContractsWaiver`, `_malformed_contracts_waiver`, `read_contracts_waiver_from_meta`, around line 750). ADR `docs/adr/4.x/2026-10-04-1-mission-contracts-waiver-in-meta-json.md`.
- `record_acceptance` lives in `src/specify_cli/mission_metadata.py` (~line 1075). `lenient` (#7356) is the pattern to mirror.
- `MissionMetaOptional` (same module) records optional meta fields; add `path_conventions` and `path_conventions_rationale` beside `contracts` and `contracts_rationale`.

## Branch Strategy

- **Planning base branch**: `issue-7566-path-conventions-per-type`
- **Merge target branch**: `issue-7566-path-conventions-per-type`
- Implement with `spec-kitty agent action implement WP03 --agent claude --mission path-conventions-per-type-01M7VRQM`.

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first waiver reader tests

Create `tests/core/test_path_conventions_waiver_reader.py` (mirror `tests/core/test_contracts_waiver_reader.py`):
- absent field → `waived False`, no warning;
- well-formed → `waived True`, the stripped rationale;
- the value `"Waived"`, `True`, `None` or `"none"` → not waived, and the warning names the value and the expected `"waived"`;
- rationale missing, blank or non-string → not waived, and the warning names `path_conventions_rationale`;
- a corrupt `meta.json` → `MissionMetaReadError` propagates;
- the warning text says path conventions stay in force.

Create `tests/specify_cli/test_record_acceptance_path_conventions_waiver.py`:
- with a reason → the last history entry has `path_conventions_waived == {"reason": "why"}` (stripped);
- without one → the key is absent (shape unchanged);
- together with `lenient=True` → both keys are present.

Confirm red.

### Subtask T007 – Generalize the waiver reader

- Introduce a private frozen spec (`_MetaWaiverSpec(field, value, rationale_field, requirement)`) and one private reader `_read_meta_waiver(primary_meta_dir, spec) -> ContractsWaiver`. Rename nothing public. Keep `ContractsWaiver` as the verdict type, and add `PathConventionsWaiver = ContractsWaiver` only if it reads better; otherwise document that the verdict type is shared.
- `_malformed_contracts_waiver`'s text must stay byte-identical for contracts. Parameterize `requirement` (`"The contracts/ requirement"` vs `"Path conventions"`) so the sentence reads naturally:
  - contracts: `meta.json 'contracts' waiver ignored: <problem>. The contracts/ requirement stays in force; declare "contracts": "none" with a non-empty 'contracts_rationale' to waive it.`
  - path: `meta.json 'path_conventions' waiver ignored: <problem>. Path conventions stay in force; declare "path_conventions": "waived" with a non-empty 'path_conventions_rationale' to waive them.`

  Check the exact contracts wording against the current source before parameterizing. A pinned test will catch drift.
- `read_contracts_waiver_from_meta` and the new `read_path_conventions_waiver_from_meta` become thin wrappers. Export the new one in `__all__` if the module has one.

### Subtask T008 – Metadata fields and history recording

- `MissionMetaOptional`: add `path_conventions: str` and `path_conventions_rationale: str`, with comments citing #7566.
- `record_acceptance(..., path_conventions_waiver_reason: str | None = None)`: when a non-blank reason is given, set `entry["path_conventions_waived"] = {"reason": reason.strip()}`. Update the docstring.

### Subtask T009 – Verify

```bash
uv run --frozen pytest -q tests/core/test_path_conventions_waiver_reader.py tests/core/test_contracts_waiver_reader.py tests/specify_cli/acceptance/test_accept_contracts_waiver.py tests/specify_cli/test_record_acceptance_path_conventions_waiver.py tests/specify_cli/test_feature_metadata.py
uv run --frozen ruff check <touched files>; uv run --frozen ruff format --check --force-exclude <touched files>; uv run --frozen mypy src/specify_cli/core/paths.py src/specify_cli/mission_metadata.py
```

## Test Strategy

Unit tests on the reader and the recorder; the existing contracts tests are the behaviour-preservation control.

## Risks & Mitigations

- `mission_metadata` meta validation (`write_meta(validate=...)`) may reject unknown keys. Confirm the new optional keys validate.

## Review Guidance

- Contracts waiver text unchanged byte for byte.
- No new reader of `meta.json` outside `core/paths.py` (single authority).

## Progress & Status

`spec-kitty agent tasks mark-status T006 T007 T008 T009 --status done --mission path-conventions-per-type-01M7VRQM`.
