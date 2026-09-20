---
work_package_id: WP01
title: 'Seam A: session-presence repair applicability (gemini/llxprt)'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-009
- NFR-002
planning_base_branch: fix/tool-surface-projection-fidelity
merge_target_branch: fix/tool-surface-projection-fidelity
branch_strategy: Planning artifacts for this mission were generated on fix/tool-surface-projection-fidelity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/tool-surface-projection-fidelity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-tool-surface-projection-fidelity-01M2Z1T7
base_commit: cfb0ebd68154eabee881848c47ad546d98f94aea
created_at: '2026-09-20T10:00:23.221215+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Session-presence applicability
history:
- at: '2026-09-20T06:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/session_presence/
create_intent:
- tests/specify_cli/session_presence/test_registry_can_write.py
- tests/specify_cli/tool_surface/providers/test_session_presence_root_context_repair.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/session_presence/writers/registry.py
- tests/specify_cli/session_presence/test_registry_can_write.py
- tests/specify_cli/tool_surface/providers/test_session_presence_root_context_repair.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Seam A: session-presence repair applicability

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (implementer) before parsing the rest of this prompt.

---

## Objectives & Success Criteria

Make `doctor tool-surfaces --fix` and `upgrade` refresh a stale **root-level orientation file** (`GEMINI.md`, `LLXPRT.md`) regardless of whether the harness command dir (`.gemini/`, `.llxprt/`) exists.

Done when:
- The gemini and llxprt registry writers are writable at the repo root (a stale block is repaired, not silently skipped) — FR-001/002/003.
- A selected, detected-stale surface is `repaired` (or `failed` on a real write error), never dispositioned `not_applicable` with exit 0 — FR-004/009.
- detect-applicable == repair-applicable for every supported writer — NFR-002.

## Context & Constraints (post-plan brownfield squad — READ)

- **Surgical fix**: drop `check_dir` from the gemini (`:42`) and llxprt (`:43`) rows in `src/specify_cli/session_presence/writers/registry.py`. With no `check_dir`, `MarkdownRulesWriter.can_write` falls back to the file's real parent (repo root, always present) — matching `AgentsMdWriter`. **Do NOT modify `writers/markdown_rules.py::can_write` (:134-138)** — cursor/windsurf/kiro depend on the check_dir gate (`tests/specify_cli/session_presence/test_agents_md_writer.py:214-256`).
- **Safety**: `can_write` is a redundant 3rd gate — config membership (`tool in configured`, `providers/session_presence.py:232`) + `configured_tools` (`tool_surface/repair.py:472-486`, `plan.py:58`) already guard, so this cannot open an unconfigured-write path.
- **FR-004/009 resolve structurally** here: once gemini/llxprt are `applicable`, a stale surface flows to `repaired` (or `failed` via `_apply_prepared:334`); the legitimately-unselected `not_applicable` path (`_prepare:227/238`, `tool not in configured`) is untouched. The cursor/windsurf/kiro sibling silent-skip is OUT of scope.
- Do NOT touch the staleness comparator (`_orientation_version_is_stale:690-707`) — that's the deferred split-brain.

## Subtasks

### T001 [P] — Red: registry can_write gemini AND llxprt
New test `tests/specify_cli/session_presence/test_registry_can_write.py` (declare `pytestmark`): assert `get_writer("gemini").can_write(tmp_path) is True` and `get_writer("llxprt").can_write(tmp_path) is True` with NO harness dir present. RED before T002. Use the registry instances (not inline writers — `test_agents_md_writer.py:258` already covers the inline case).

### T002 [P] — Drop check_dir from gemini + llxprt rows
In `session_presence/writers/registry.py:42-43`, remove `check_dir=".gemini"` / `check_dir=".llxprt"` from those two `MarkdownRulesWriter(...)` rows only. Leave every other row (copilot/cursor/windsurf/kiro) untouched.

### T003 [P] — Red+green: repair-path regression
New test `tests/specify_cli/tool_surface/providers/test_session_presence_root_context_repair.py`: seed a STALE `GEMINI.md` + no `.gemini/`, drive `SessionPresenceProvider.repair()` (configured gemini), assert the surface lands in `RepairResult.repaired` (not `.skipped`). Add the llxprt case. RED before T002.

### T004 [P] — NFR-002 parity table test
Table test over `WRITER_REGISTRY`: for each `MarkdownRulesWriter`, the disk state that makes `probe` return STALE/MISSING is the same state that makes `_prepare` mark it `applicable` (detect==repair). Anchor: detect `session_presence.py:599-601/629-631` vs repair `:232-236`.

### T005 [P] — Migration backfill test
Assert a configured-gemini project with `.gemini/` absent now backfills `GEMINI.md` (behavior change vs today's `detect()==False`). Covers `manager.install/update` + `upgrade/migrations/m_3_3_0_session_presence_all_harnesses.py:73` paths (idempotent writes).

### T006 [P] — Keep the cursor contract green
Confirm `tests/specify_cli/session_presence/test_markdown_rules_writer.py:207-216` (cursor, `TestAppendModeFalse`) and `test_agents_md_writer.py:214-256` (cursor check_dir) stay GREEN — they must NOT change. If they go red, you touched the generic `can_write` body — revert and re-scope to the registry rows.

## Branch Strategy
- Planning base / merge target: `fix/tool-surface-projection-fidelity` (final PR → `main`). Worktree per lane from `lanes.json`.

## Definition of Done
- T001–T006 green; cursor contracts green; ruff/mypy clean; only owned files changed; no `packs/` edits; no change to `markdown_rules.py` `can_write` body or the staleness comparator.

## Reviewer guidance
- Confirm the fix is the registry-row `check_dir` drop, NOT a `can_write` body change. Confirm gemini AND llxprt both covered. Confirm the NFR-002 parity test genuinely exercises detect vs repair. Confirm no scope drift into the staleness split-brain or the cursor/windsurf/kiro sibling.
