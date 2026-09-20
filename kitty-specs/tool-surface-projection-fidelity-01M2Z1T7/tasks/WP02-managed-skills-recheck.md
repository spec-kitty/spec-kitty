---
work_package_id: WP02
title: 'Seam B: managed-skills recheck host-awareness + manifest determinism'
dependencies: []
requirement_refs:
- FR-005
- FR-006
- FR-007
- FR-008
- NFR-001
- NFR-003
planning_base_branch: fix/tool-surface-projection-fidelity
merge_target_branch: fix/tool-surface-projection-fidelity
branch_strategy: Planning artifacts for this mission were generated on fix/tool-surface-projection-fidelity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/tool-surface-projection-fidelity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-tool-surface-projection-fidelity-01M2Z1T7
base_commit: fe44602aefdfdcdb266c120f11529ee8020950f5
created_at: '2026-09-20T10:01:41.186271+00:00'
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 1 - Managed-skills completion re-check
history:
- at: '2026-09-20T06:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tool_surface/providers/
create_intent:
- tests/specify_cli/tool_surface/providers/test_managed_skills_host_aware.py
- tests/specify_cli/skills/test_command_manifest_determinism.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/tool_surface/providers/managed_skills.py
- src/specify_cli/skills/command_installer.py
- src/specify_cli/skills/installer.py
- tests/specify_cli/skills/test_installer.py
- tests/specify_cli/tool_surface/providers/test_managed_skills_host_aware.py
- tests/specify_cli/skills/test_command_manifest_determinism.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Seam B: managed-skills recheck host-awareness + manifest determinism

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (implementer) before parsing the rest of this prompt.

---

## Objectives & Success Criteria

Make `spec-kitty upgrade` converge in ONE invocation on Windows and stop reporting phantom `--dry-run` repairs, without weakening POSIX correctness.

Done when:
- `_recheck_command_completion` treats a freshly-created directory whose only divergence from the plan is a POSIX `mode` the host can't represent (Windows) as satisfied — so `upgrade` converges in one pass (FR-005/006, NFR-001).
- `upgrade --dry-run` reports zero repairs once converged under the Windows condition (FR-007, #4777).
- Command-skills manifest content is deterministic: `installed_at` is excluded from the recheck comparison hash so a cross-invocation wall-clock diff never drives phantom drift (FR-008, #4134).
- POSIX correctness preserved: on a POSIX host a genuinely wrong mode still refuses (NFR-003).

## Context & Constraints (post-plan brownfield squad — READ)

- **Relax ONLY `managed_skills.py:179`** (the observed-vs-planned-`0o755` directory-effect comparison, the #4776 abort). Do NOT touch `:195`/`:199`/`:308` — those are observed-vs-observed same-host and over-broadening masks a real parent swap.
- **Host gate**: use `kernel.paths.is_windows()` **called through the module attribute** (so tests monkeypatch `kernel.paths.is_windows`; never fake `os.name` — it flips pathlib and crashes pytest). Scope the relaxation to **directory-kind** effects diverging only by `mode`. `skills/command_installer.py:63` already imports `kernel.paths`. No existing `os.name`/platform guard exists in these packages — this is the first; keep it routed through `is_windows()`.
- **#4134 seam**: the COMMAND manifest is `command_installer.py:514` (`self.time = now_utc_iso()`) / `:610` (`installed_at = existing.installed_at if existing else self.time`) + `manifest_store`. Exclude `installed_at` from the recheck **comparison hash** (mirror `managed_skills.py:702 _expected_entries` which already uses `installed_at=""`). **Do NOT** null/zero the stored value (breaks the preserved-timestamp contract `tests/specify_cli/skills/test_manifest.py:313-321`) and **do NOT** touch `skills/manifest.py:_retain_entry_times` (that's the doctrine manifest — wrong seam).
- Keep the `[mode]` 0o700-on-POSIX tests green (`test_managed_skills.py:1371/1409`) — they are the NFR-003 tripwire; a blanket mode-skip flips them red.

## Subtasks

### T007 [P] — Red: Windows single-pass convergence
New test `tests/specify_cli/tool_surface/providers/test_managed_skills_host_aware.py` (declare `pytestmark`): monkeypatch `kernel.paths.is_windows`→True and force the freshly-created `.agents/skills` observed mode ≠ 0o755; assert one `apply_composition`/`upgrade` pass converges (doctrine skills applied), no `Completed command output changed` raise. RED before T008.

### T008 [P] — Host-aware :179 comparison
In `managed_skills.py:_recheck_command_completion`, gate the `:179` directory-effect mode comparison on `kernel.paths.is_windows()` (module attr): when Windows and the effect is a directory whose only divergence is `mode`, treat it as satisfied. Leave file effects and `:195`/`:199`/`:308` unchanged.

### T009 [P] — Red+green: idempotent second run + no phantom dry-run
Assert a second `upgrade` under the Windows condition reports zero changes (NFR-001) and `upgrade --dry-run` reports zero repairs (#4777/FR-007).

### T010 [P] — #4134: exclude installed_at from comparison hash
Make the recheck/probe comparison ignore `installed_at` for command-manifest entries (mirror `_expected_entries` `installed_at=""`), so a cross-invocation wall-clock diff doesn't fail the recheck. Keep the stored `installed_at` real.

### T011 [P] — Red+green: cross-invocation installed_at stability
Test that assessing an unchanged command skill across two separate installer invocations (fresh clock each) does not produce a phantom drift / recheck failure.

### T012 [P] — POSIX guard (NFR-003)
Add a test: a genuinely wrong SKILL.md **file** mode on a POSIX host still refuses (the Windows gate must be directory-scoped and host-gated, never relaxing file modes or POSIX). Confirm `test_managed_skills.py:1371/1409` (0o700 dir, POSIX) stay green.

## Branch Strategy
- Planning base / merge target: `fix/tool-surface-projection-fidelity` (final PR → `main`). Own lane; worktree per `lanes.json`.

## Definition of Done
- T007–T012 green; `[mode]` 0o700 POSIX tests green; ruff/mypy clean; only owned files; no touch to `:195`/`:199`/`:308` or `manifest.py`; `is_windows()` routed through the module attribute.

## Reviewer guidance
- Confirm ONLY `:179` relaxed and gated on `is_windows()` (module attr), dir-scoped. Confirm #4134 fix excludes `installed_at` from the hash, not from storage. Confirm POSIX wrong-mode still refuses (NFR-003). Confirm no over-broadening to `:195`/`:199`/`:308`.
