---
work_package_id: WP02
title: Cascade-source surfaces share one index
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-006
- NFR-004
planning_base_branch: issue-6433-charter-identity-single-authority
merge_target_branch: issue-6433-charter-identity-single-authority
branch_strategy: Planning artifacts for this mission were generated on issue-6433-charter-identity-single-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6433-charter-identity-single-authority unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - Cascade surfaces
history:
- at: '2026-10-30T12:55:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- tests/specify_cli/cli/commands/charter/test_cascade_identity_6433.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/charter/activate.py
- src/specify_cli/cli/commands/charter/deactivate.py
- src/specify_cli/cli/commands/charter/_resynthesis_preflight.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Cascade-source surfaces share one index

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (`spec-kitty agent profile show python-pedro`) before parsing the rest of this prompt.

## Objectives & Success Criteria

- `charter activate <kind> <token> --cascade all` produces the same cascade report for a file stem, a `<kind>:<id>` URN and a normalised directive id (`24`).
- `charter deactivate <kind> <token> --cascade all` produces the same shared-artifact skip report for the same three spellings.
- `--resynthesize` resolves its cascade source through the index.
- One index is built per command, never per token.

## Context & Constraints

- Read: `spec.md` (FR-004..FR-006), `research.md` §3.2, §3.3 for the exact red outputs.
- `_source_urn` returning `None` is the documented "no DRG node" contract for a genuinely unknown token; keep it, and keep the command's silent-no-cascade behaviour for that case.
- `deactivate._active_urns` loops over every active token: build the index once and pass it into the inner helper.
- Do not touch compile, the consistency check or the DRG filter — those are already routed (#6457, #6749; C-005).

## Branch Strategy

- **Strategy**: single branch on `issue-6433-charter-identity-single-authority`.
- **Planning base branch**: `issue-6433-charter-identity-single-authority`
- **Merge target branch**: `issue-6433-charter-identity-single-authority`

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first CLI tests

- **Purpose**: prove the loss through the shipped command before fixing it.
- **Steps**: create `tests/specify_cli/cli/commands/charter/test_cascade_identity_6433.py`. Fixture: `tmp_path` project, `.kittify/config.yaml` = `{}`, `seed_activation_ledger(root, mission_type_activations=["software-dev"])` (and the directive seed for deactivate), run with `["--repo-root", str(root), "--no-compile"]`. Assert for `activate ... --cascade all`: the stem run prints `Cascade-activated: directive/reconcile-change-scope-tensions`, and so do the `directive:DIRECTIVE_024` and `24` runs (red today), with identical ledger contents. Same shape for `deactivate ... --cascade all`: the stem run prints the `Skipped (shared artifact): directive:RECONCILE_CHANGE_SCOPE_TENSIONS` line, and so do the other two.
- **Files**: `tests/specify_cli/cli/commands/charter/test_cascade_identity_6433.py`.
- **Parallel?**: no.
- **Notes**: assert the positive control (stem) on the same fixture in the same test, so the test cannot pass vacuously.

### Subtask T007 – `activate._source_urn`

- **Purpose**: the cascade and the referenced-but-not-cascaded warning must both survive a non-stem spelling.
- **Steps**: build one `IdentityIndex.from_roots(offering_root=resolve_offering_root(), org_roots=org_roots, layer_roots=layer_roots)` and resolve `declared_id`; return `f"{kind}:{declared}"` or `None`.
- **Files**: `src/specify_cli/cli/commands/charter/activate.py`.
- **Notes**: the mission-type branch stays first, untouched.

### Subtask T008 – `deactivate._source_urn` and `_active_urns`

- **Purpose**: the deactivation target and the shared-reference safety set.
- **Steps**: same index resolution in both; hoist the index build above the `urns_of` loop.
- **Files**: `src/specify_cli/cli/commands/charter/deactivate.py`.
- **Parallel?**: yes.
- **Notes**: `urn in graph_urns` filtering and the deny subtraction stay as they are.

### Subtask T009 – `_resynthesis_preflight._cascade_source`

- **Purpose**: the resynthesis preflight walks the same node the write will.
- **Steps**: resolve through the index; an unknown token keeps raising (the preflight is fail-closed).
- **Files**: `src/specify_cli/cli/commands/charter/_resynthesis_preflight.py`.
- **Parallel?**: yes.
- **Notes**: use `unknown_artifact_id_error(...)` for the refusal so the message names the searched layers.

## Test Strategy

```bash
uv run pytest tests/specify_cli/cli/commands/charter/test_cascade_identity_6433.py -q
uv run pytest tests/specify_cli/cli/commands/charter/test_charter_activate_commands_cascade_output.py \
  tests/specify_cli/cli/commands/charter/test_activate_include_deactivated.py \
  tests/specify_cli/cli/commands/charter/test_activate_declared_id_identity.py \
  tests/specify_cli/cli/commands/charter/test_charter_deactivate_commands.py -q
uv run ruff check src/specify_cli/cli/commands/charter/{activate,deactivate,_resynthesis_preflight}.py
uv run mypy src/specify_cli/cli/commands/charter/{activate,deactivate,_resynthesis_preflight}.py
```

## Risks & Mitigations

- Output drift in existing cascade tests: they assert rendered lines, so keep the render path untouched; only the source resolution changes.
- Scan regression in `_active_urns`: one index per command, proven by the T001 scan-count test pattern.

## Review Guidance

- Confirm each CLI site builds at most one index per command.
- Confirm the unknown-token path is unchanged (no new exception where the command used to no-op).
- Confirm the red tests fail on `main` and pass on this branch.
