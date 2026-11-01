---
work_package_id: WP01
title: Target-native agent selection
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- C-001
- NFR-001
- NFR-002
- SC-001
- SC-002
- SC-004
planning_base_branch: issue-6273-plugin-bundle-native-target-selection
merge_target_branch: issue-6273-plugin-bundle-native-target-selection
branch_strategy: Planning artifacts for this mission were generated on issue-6273-plugin-bundle-native-target-selection. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6273-plugin-bundle-native-target-selection unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Selection
history:
- at: '2026-11-01T15:22:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tool_surface/bundles/
create_intent:
- tests/specify_cli/tool_surface/bundles/test_projection_selection.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/tool_surface/bundles/projection.py
- src/specify_cli/tool_surface/bundles/claude.py
- src/specify_cli/tool_surface/bundles/copilot.py
- src/specify_cli/tool_surface/bundles/vscode.py
- tests/specify_cli/tool_surface/bundles/test_projection_selection.py
- tests/specify_cli/tool_surface/providers/test_plugin_bundle.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Target-native agent selection

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status`). Address all feedback before the
work is complete, and record each change with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

Outcome: a plugin bundle carries exactly one agent rendering per member, chosen by the distribution
target's own ordered accept-list, so a Claude+Codex project stages all three bundles and a genuine
same-family conflict still fails closed.

- FR-001: Claude bundle selects `claude`; Copilot/VS Code bundles select `copilot`/`vscode`; Codex
  `.toml` is never a candidate for a Markdown member.
- FR-002: two accepted sources of the same rank with different bytes still produce
  `Conflicting prepared bundle member: <member>` and write nothing.
- FR-003: single-harness projects keep staging through the Markdown-family fallback.
- SC-001/SC-002: the issue reproduction stages the three manifests and reports `missing: 0`; the
  pre-fix state (`missing: 3`) is the negative control.

## Context & Constraints

- `kitty-specs/plugin-bundle-native-target-selection-01M6BV0N/spec.md`
- `kitty-specs/plugin-bundle-native-target-selection-01M6BV0N/plan.md` (IC-01)
- `kitty-specs/plugin-bundle-native-target-selection-01M6BV0N/data-model.md`
- `kitty-specs/plugin-bundle-native-target-selection-01M6BV0N/contracts/plugin-bundle-selection.md`
- `kitty-specs/plugin-bundle-native-target-selection-01M6BV0N/research.md` (root cause and evidence)
- `.kittify/charter/charter.md` — locality of change, single canonical authority, no gate weakening.
- Do **not** touch `providers/plugin_bundle.py`, `repair.py` or the CLI (WP02 owns them), and do not
  change manifest payloads, layout tables or non-agent aggregation.

## Branch Strategy

- Planning base branch: `issue-6273-plugin-bundle-native-target-selection`
- Merge target branch: `issue-6273-plugin-bundle-native-target-selection`
- Execution worktrees are allocated per computed lane from `lanes.json`; do not hand-build paths.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first: issue reproduction through the real entry point

- **Purpose**: prove the defect before the fix, on the fixture the issue describes.
- **Steps**: in `tests/specify_cli/tool_surface/providers/test_plugin_bundle.py`, add a test that
  builds a project configured with `claude,codex,copilot` (reuse the `canonical_bundle_tree` fixture
  or initialize a tiny one), runs the pre-existing repair path (`PluginBundleProvider().repair(...)`
  or `run_tool_surfaces(..., fix=True)`), and asserts today's failing expectation: the assessment is
  complete, `dist/spec-kitty-plugins/{claude_code_plugin,copilot_skill_package,vscode_extension}`
  exist, and an immediate re-audit has `missing == 0`. Run it and confirm it fails for the collision.
- **Files**: `tests/specify_cli/tool_surface/providers/test_plugin_bundle.py`
- **Parallel?**: no (must fail first).
- **Notes**: capture the failure message in the commit body: `Conflicting prepared bundle member:
  agents/<id>.md`.

### Subtask T002 – Red-first: selection unit tests

- **Purpose**: pin the selection contract independently of the CLI.
- **Steps**: create `tests/specify_cli/tool_surface/bundles/test_projection_selection.py` with
  `_support`-style plans covering:
  1. claude `.claude/agents/<id>.md` + codex `.codex/agents/<id>.toml` → Claude bundle entry has only
     the `.claude` source; Copilot/VS Code bundles likewise never include the `.toml`.
  2. copilot `.github/agents/<id>.agent.md` + claude `.claude/agents/<id>.md` with differing bytes →
     Copilot bundle picks the copilot source (native), Claude bundle picks the claude source.
  3. claude-only project → Copilot and VS Code bundles still get an agent member from the Markdown
     fallback.
  4. two `claude`-family sources for the same member with different bytes → `supplied_entries` still
     raises `Conflicting prepared bundle member`.
- **Files**: new test module.
- **Parallel?**: no.
- **Notes**: use `bundle_entries_for_plans` directly for the selection assertions and
  `supplied_entries` for the conflict assertion.

### Subtask T003 – Add ordered `profile_tool_keys` to the projectors

- **Purpose**: make the accepted family explicit and testable on the owner of each target.
- **Steps**: add a class attribute (e.g. `profile_tool_keys: tuple[str, ...]`) to
  `ClaudeCodeBundleProjector` (`("claude", "copilot", "vscode")`), `CopilotBundleProjector`
  (`("copilot", "vscode", "claude")`) and inherit/override in `VsCodeBundleProjector`
  (`("vscode", "copilot", "claude")`). Pass it from each `entries()` into
  `bundle_entries_for_plans`. Document the list in the module docstring or attribute comment.
- **Files**: `claude.py`, `copilot.py`, `vscode.py`.
- **Parallel?**: with T004 (same change, one commit each is fine).
- **Notes**: keep the tuples ordered — index is the preference rank.

### Subtask T004 – Rank-aware member merge

- **Purpose**: implement the selection in the one merge loop.
- **Steps**: extend `bundle_entries_for_plans` with `profile_tool_keys: Sequence[str] | None = None`.
  For `ToolSurfaceKind.AGENT_PROFILE` instances:
  - resolve `rank = profile_tool_keys.index(instance.owner)`; skip the instance when absent;
  - remember the chosen rank per `bundle_relative_path`; a lower rank replaces the prior entry, a
    higher rank is skipped, an equal rank merges as today (sources/claims/logical_owners union).
  Non-agent kinds keep today's unconditional merge. Keep the function deterministic (sorted keys).
- **Files**: `src/specify_cli/tool_surface/bundles/projection.py`
- **Parallel?**: with T003.
- **Notes**: do not read any file during selection; ranking must happen before `files_for_entries`.

### Subtask T005 – Re-pin the multi-harness provider contract test

- **Purpose**: the old test pins the defect; replace it with the corrected contract without losing
  the safety guarantee.
- **Steps**: rewrite `test_canonical_multi_harness_profile_conflict_is_read_only` (claude,codex,vibe
  canonical tree) to assert the assessment is complete and stages the three bundles, and keep a
  genuine-conflict test that uses two same-family differing sources and asserts `complete is False`,
  `apply(...).outcome == "precondition_changed"`, and a `snapshot`-verified no-write result.
- **Files**: `tests/specify_cli/tool_surface/providers/test_plugin_bundle.py`
- **Parallel?**: no.
- **Notes**: the no-write assertion is the value; do not delete it, move it to the new conflict test.

## Test Strategy

```bash
uv run pytest tests/specify_cli/tool_surface/bundles tests/specify_cli/tool_surface/providers/test_plugin_bundle.py -q
uv run mypy src/specify_cli/tool_surface/bundles tests/specify_cli/tool_surface/bundles/test_projection_selection.py
uv run ruff check src/specify_cli/tool_surface/bundles tests/specify_cli/tool_surface/bundles/test_projection_selection.py
```

Red-first order: land T001+T002 failing, then T003+T004, then T005. Do not run a full heavy suite.

## Risks & Mitigations

- Guard weakening → the equal-rank differing-bytes test is the paired control.
- Double-selection tables → the accept-list lives only on the projector; the merge helper consumes it.
- Fallback confusion → single-harness cases are explicit unit tests.

## Review Guidance

- Confirm each target's accept-list matches the contract table in
  `contracts/plugin-bundle-selection.md`.
- Confirm no non-agent behaviour changed and no file is read for a dropped source.
- Confirm the genuine conflict still refuses with no writes.

## Progress & Status

Record progress with `spec-kitty agent tasks mark-status <Txxx> --status done` and
`spec-kitty agent tasks add-history WP01 --note "..."`.
