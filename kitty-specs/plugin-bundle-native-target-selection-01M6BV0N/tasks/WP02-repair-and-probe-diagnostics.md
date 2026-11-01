---
work_package_id: WP02
title: Repair and probe diagnostics
dependencies: []
requirement_refs:
- FR-004
- FR-005
- NFR-003
- C-002
- C-003
- SC-003
planning_base_branch: issue-6273-plugin-bundle-native-target-selection
merge_target_branch: issue-6273-plugin-bundle-native-target-selection
branch_strategy: Planning artifacts for this mission were generated on issue-6273-plugin-bundle-native-target-selection. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6273-plugin-bundle-native-target-selection unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Diagnostics
history:
- at: '2026-11-01T15:22:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tool_surface/providers/
create_intent:
- tests/specify_cli/tool_surface/providers/test_plugin_bundle_repair_reporting.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/tool_surface/providers/plugin_bundle.py
- src/specify_cli/tool_surface/repair.py
- src/specify_cli/cli/commands/_command_surface_doctor.py
- tests/specify_cli/tool_surface/providers/test_plugin_bundle_repair_reporting.py
- tests/specify_cli/tool_surface/integration/test_doctor_tool_surfaces_cli.py
- docs/changelog/CHANGELOG.md
- docs/guides/how-to/installation/tool-surface-upgrade-and-repair.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Repair and probe diagnostics

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status`). Address all feedback before the
work is complete, and record each change with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

Outcome: when `--fix` cannot repair a surface, the operator sees which surfaces failed and why, and
the command exits 1; a stale staged bundle reports the underlying cause instead of only the generic
"missing, drifted, or unavailable members" sentence.

- FR-004 / SC-003: forced failure → exit 1, failed ids + reasons in human output, `repair.failed`
  and `repair.findings_after` in JSON; successful repair → exit 0.
- FR-005: probe of an incomplete staged bundle carries the provider's diagnostic message.
- C-002: audit-only `ok` and OPTIONAL missing behaviour unchanged.

## Context & Constraints

- `kitty-specs/plugin-bundle-native-target-selection-01M6BV0N/spec.md`, `plan.md` (IC-02, IC-03),
  `data-model.md` (Repair outcome), `contracts/plugin-bundle-selection.md` (Diagnostics).
- `.kittify/charter/charter.md` — no gate weakening; user-visible change needs a changelog entry.
- Do not edit `bundles/*` or the projector tests (WP01 owns them); this WP starts from the repaired
  selection behaviour.
- `RepairResult.findings_after` already exists; the provider already produces it —
  `SurfaceRepairService` drops it.

## Branch Strategy

- Planning base branch: `issue-6273-plugin-bundle-native-target-selection`
- Merge target branch: `issue-6273-plugin-bundle-native-target-selection`
- Execution worktrees are allocated per computed lane from `lanes.json`; do not hand-build paths.

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first: repair failure and exit code

- **Purpose**: prove the silent success before changing anything.
- **Steps**: create `tests/specify_cli/tool_surface/providers/test_plugin_bundle_repair_reporting.py`
  with a unit test that forces a bundle repair failure (e.g. a malformed required member, or the
  existing partial-write fixture style) and asserts `RepairResult.failed` is non-empty **and**
  `findings_after` names the cause after passing through `SurfaceRepairService.repair`. Add an
  integration test in `tests/specify_cli/tool_surface/integration/test_doctor_tool_surfaces_cli.py`
  that runs `doctor tool-surfaces --fix` on a controlled project forced to fail, asserting exit 1 and
  both `repair.failed` and `repair.findings_after` in the JSON; keep the existing successful-repair
  test asserting exit 0.
- **Files**: the two test modules.
- **Parallel?**: no (must fail first).
- **Notes**: prefer the in-process `run_tool_surfaces_audit`/CliRunner harness already used by the
  integration module; do not spawn a real `init` of the whole app if avoidable.

### Subtask T007 – Probe keeps the cause

- **Purpose**: stop discarding the prepared-batch diagnostic.
- **Steps**: in `PluginBundleProvider.probe`, when `assess(...)` is incomplete, build the finding
  message from the assessment diagnostics (joins their messages) with the generic sentence as a
  fallback only when there are none. Keep the finding code/severity/state/repair hint as today.
- **Files**: `src/specify_cli/tool_surface/providers/plugin_bundle.py`
- **Parallel?**: with T008/T009 after T006.
- **Notes**: do not make an absent manifest an error (OPTIONAL policy).

### Subtask T008 – Carry `findings_after` through the repair service

- **Purpose**: make the provider's cause survive aggregation.
- **Steps**: add a findings accumulator to `_RepairTally`, extend it in `_apply` from
  `result.findings_after`, and return it from `SurfaceRepairService.repair`. `RepairResult` keeps its
  defaulted field, so all existing constructors stay valid.
- **Files**: `src/specify_cli/tool_surface/repair.py`
- **Parallel?**: with T007/T009.
- **Notes**: de-duplicate only if a provider repeats the identical finding object; otherwise keep
  one finding per failed surface (NFR-003).

### Subtask T009 – Human rendering and exit code

- **Purpose**: surface the failure to the operator.
- **Steps**: in `_print_tool_surface_human`, print a `Failed to repair: N surface(s)` block listing
  each failed id and the matching `findings_after` message. In `run_tool_surfaces_audit`, exit 1 when
  `outcome.repair is not None and outcome.repair.failed` (both JSON and human paths), otherwise keep
  `0 if outcome.report.ok else 1`.
- **Files**: `src/specify_cli/cli/commands/_command_surface_doctor.py`
- **Parallel?**: with T007/T008.
- **Notes**: `dry_run` results with `failed` should behave the same; `skipped` alone (consent) does not
  escalate beyond today's behaviour.

### Subtask T010 – Changelog and guide

- **Purpose**: user-facing change needs the [Unreleased] entry and docs.
- **Steps**: add one bold, impact-first `(#6273)` entry under `[Unreleased]` in
  `docs/changelog/CHANGELOG.md` (before/after, under 1,200 characters; root `CHANGELOG.md` is a
  symlink). Add a short paragraph to
  `docs/guides/how-to/installation/tool-surface-upgrade-and-repair.md` under the `--fix` section: a
  failed repair now prints the failed surfaces and their reasons and exits non-zero; multi-harness
  projects stage all three bundles because each bundle takes its own native agent rendering. Update the
  page `updated:` frontmatter date.
- **Files**: `docs/changelog/CHANGELOG.md`, the guide.
- **Parallel?**: after T009.
- **Notes**: no doc index change is expected (existing pages); if you add no page, skip
  `docs_index --write`.

## Test Strategy

```bash
uv run pytest tests/specify_cli/tool_surface/providers/test_plugin_bundle_repair_reporting.py \
  tests/specify_cli/tool_surface/integration/test_doctor_tool_surfaces_cli.py -q
uv run pytest tests/specify_cli/tool_surface -q
uv run mypy src/specify_cli/tool_surface/providers/plugin_bundle.py src/specify_cli/tool_surface/repair.py
uv run ruff check src/specify_cli/tool_surface/providers/plugin_bundle.py src/specify_cli/tool_surface/repair.py src/specify_cli/cli/commands/_command_surface_doctor.py
uv run python -m scripts.docs.check_docs_freshness --ci
```

Do not run a full heavy suite.

## Risks & Mitigations

- Exit-code regression for successful repairs → the existing success test stays and asserts 0.
- Message duplication → one finding per failed surface; join diagnostics once.
- Broader CLI blast radius → the change is confined to the tool-surface branch of `doctor`.

## Review Guidance

- Confirm only a failed repair escalates the exit code.
- Confirm the probe message now names the cause and that an absent manifest stays OPTIONAL.
- Confirm the changelog entry is impact-first and under the limit.

## Progress & Status

Record progress with `spec-kitty agent tasks mark-status <Txxx> --status done` and
`spec-kitty agent tasks add-history WP02 --note "..."`.
