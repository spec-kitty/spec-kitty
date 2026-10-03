---
work_package_id: WP02
title: 'Command-skill repair: the explicit repair replaces a real edit'
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- NFR-001
- C-002
- C-003
- C-005
planning_base_branch: kitty/upgrade-windows-drift
merge_target_branch: kitty/upgrade-windows-drift
branch_strategy: Planning artifacts for this mission were generated on kitty/upgrade-windows-drift. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/upgrade-windows-drift unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-windows-drift-01M40959
base_commit: a7f354c1358cce35c85abb26956a886df3c4a49e
created_at: '2026-10-03T08:33:09.559667+00:00'
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 1 - Command skills
history:
- at: '2026-10-03T07:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tool_surface/providers/
create_intent:
- tests/specify_cli/cli/commands/test_doctor_command_skill_repair_consent.py
execution_mode: code_change
model: claude-sonnet-5-5-high
owned_files:
- src/specify_cli/tool_surface/providers/command_skills.py
- tests/specify_cli/tool_surface/providers/test_command_skills.py
- tests/specify_cli/cli/commands/test_doctor_command_skill_repair_consent.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Command-skill repair: the explicit repair replaces a real edit

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (role `implementer`) and behave according to its guidance before parsing the rest of this prompt.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission upgrade-windows-drift-01M40959`) and the Activity Log below. Address every feedback item before completing.

---

## Objectives & Success Criteria

Closes **#5575**.

1. `spec-kitty doctor tool-surfaces --fix` (and `--kind command-skill --fix`) replaces a genuinely edited command skill with the canonical rendering and records its digest. A second run reports no finding for it (FR-003, SC-002). This matches what the same command already does for agent profiles.
2. The drift finding a command skill produces names the repair the operator can run: `spec-kitty doctor tool-surfaces --fix`.
3. Unattended paths never overwrite a real edit. Only statuses in `STATE_DRIFTED`, handed to `CommandSkillsProvider.repair` by an explicit repair, populate consent (FR-002, C-003). An interactive upgrade "yes" (drift-policy Rule 3) reaches the same `repair`. After this WP, its `drifted_overwritten` record is true.
4. No new public flag (C-002).

## Context & Constraints

- **Depends on WP01**, which makes `CommandInstaller.preserve` honor `inputs.consent.overwrite_paths`. Start from the lane workspace that `implement` gives you; it includes WP01's work.
- Read: `spec.md`, `plan.md` (IC-02), `research.md` (D2), `data-model.md`, `contracts/command-skill-drift.md`.
- Prior art: `AgentProfilesProvider.repair` (`src/specify_cli/tool_surface/providers/agent_profiles.py` ~444-495) builds:

  ```python
  ApplyConsent(
      automatic=True,
      overwrite_paths=tuple(sorted(rel for drifted statuses)),
  )
  ```

  It assesses with that consent, then calls `self.apply(assessment, consent)`, and reports `consent_required` dispositions as failures.
- Anchors in `src/specify_cli/tool_surface/providers/command_skills.py`:
  - `probe` ~216-259: the drift finding is built at ~245-258 with `make_finding(MANAGED_FILE_DRIFT, SEVERITY_WARNING, ...)`.
  - `repair` ~364-392: today `ApplyConsent(automatic=True)` only.
- Unattended safety: `src/specify_cli/tool_surface/repair.py` `_apply_auto_repairs` (~401) passes only missing and stale statuses. `_classify_drifted` (~380) sends drifted statuses to repair only on Rule 5 (`repair_drift=True`, which no caller sets) or an interactive "yes". Do not change `repair.py`.
- Out of scope: `doctor skills --fix` and `_command_surface_doctor._repair_refusal` (#5281); #702; #2527.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `kitty/upgrade-windows-drift`
- **Merge target branch**: `kitty/upgrade-windows-drift`

Run `spec-kitty agent action implement WP02 --agent cursor --mission upgrade-windows-drift-01M40959` and work only in the workspace it prints.

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first entry-point test for #5575

- **Purpose**: prove the bug through the real CLI first (C-005, NFR-001).
- **Steps**:
  1. Create `tests/specify_cli/cli/commands/test_doctor_command_skill_repair_consent.py`, reusing the harness style of `tests/specify_cli/skills/test_crlf_skill_render_4998.py`:
     - `_make_project(tmp_path, agents=["codex"])`. If that helper is private to the module, write a local equivalent or use a real `init`, whichever is reliable for `doctor tool-surfaces`.
     - The test at ~722 (`test_command_skill_repair_converges_via_tool_surfaces_fix`) already drives `doctor_app ["tool-surfaces", "--kind", "command-skill", "--fix", "--json"]`.
  2. Seed a **real edit**:
     - install the canonical rendering for one command (`render(template, "codex", version, repo_root=None).to_skill_md()`, as in `_seed_self_consistent_command_skill_drift`);
     - record its hash in the manifest;
     - then append a local edit to the file without updating the manifest.

     The file's hash now differs from both the recorded and the canonical hash.
  3. Assert the audit (`doctor tool-surfaces --kind command-skill --json`, no `--fix`) reports the drift finding and exits 1, with the file unchanged.
  4. Run `--fix --json`. Assert:
     - `exit_code == 0` and `payload["ok"] is True`;
     - the file equals the canonical rendering;
     - the manifest hash equals its fingerprint;
     - a second `--fix --json` has `payload["findings"] == []` and an empty `repair.repaired`.
  5. Run it red and record the output in the Activity Log (expected today: the write is refused as `consent_required`, so the file is unchanged and the result is not ok).

### Subtask T007 – Pass drifted paths as consent

- **Steps**:
  1. In `CommandSkillsProvider.repair`, compute `overwrite_paths`: the sorted project-relative POSIX paths of the statuses whose `state == STATE_DRIFTED` (`s.instance.path.relative_to(project_root).as_posix()`).
  2. Build `consent = ApplyConsent(automatic=True, overwrite_paths=overwrite_paths)`, use it in the `AssessmentInputs`, and pass the **same** object to `self.apply(assessment, consent)`.
  3. Keep the existing `unresolved` handling. After WP01, a consented path no longer yields `consent_required`, so it lands in `eligible` and `repaired`.
  4. Keep `dry_run` truthful: a consented drifted path is reported as repairable in a dry run.
- **Tests** in `tests/specify_cli/tool_surface/providers/test_command_skills.py`:
  - a drifted status is repaired, and the file equals canonical;
  - a mixed batch (one missing, one drifted) repairs both;
  - a present status is untouched;
  - the dry run reports without writing.

### Subtask T008 – Actionable drift guidance

- **Steps**: change the drift finding message in `probe` (~252) so it names the repair, for example `f"Command skill drifted from manifest hash: {path}; run 'spec-kitty doctor tool-surfaces --fix' to restore it"`. Set the structured `repair_command=` field on the finding, as the agent-profile twin does (`agent_profiles.py` ~439 uses `repair_command=_REPAIR_HINT`). Reuse or mirror that constant. Prose in the message is optional. If the same string appears three or more times, hoist it to a module constant (Sonar S1192).
- `make_finding` already accepts `repair_command` (`tool_surface/findings.py` ~103); using it is mandatory.
- **Tests**: assert the finding carries the repair command. No test pins the old command-skill message text, so do not edit `test_findings.py`.

### Subtask T008 (part 2) – Probe: canonical bytes are present (spec US1 acceptance 1.2)

- **Purpose**: `expand` sets `file_hash` from the manifest entry, so `probe` reports canonical-bytes-with-old-hash as DRIFTED in a read-only `doctor tool-surfaces` audit. Only `upgrade` runs the adoption pass. The audit must report it present.
- **Steps**: in `probe`, just before emitting `MANAGED_FILE_DRIFT` when `on_disk != instance.file_hash`:
  - if `command_installer.canonical_digest(project_root, command) == on_disk` (WP01 helper; derive `command` from `rel`), return `SurfaceStatus(instance, STATE_PRESENT)`;
  - if the helper returns `None`, keep today's drift finding (fail toward reporting).
- **Tests**:
  - red-first: audit `doctor tool-surfaces --kind command-skill --json` on canonical bytes with an old manifest hash. Today it reports drift and exits 1; after the change, no finding and exit 0.
  - plus a unit test in `test_command_skills.py`. A real edit must still be DRIFTED.

### Subtask T009 – Guard the unattended path

- **Purpose**: pin C-003 at the seam this WP widened.
- **Steps**:
  - Add a test that runs `run_surface_repair(project, interactive=False, repair_drift=False)` on a project with one drifted command skill. Assert the path is in `summary.drifted_reported`, not in `drifted_overwritten`, and the bytes are unchanged.
  - Add a test that `CommandSkillsProvider.repair` with only missing or stale statuses passes empty `overwrite_paths`. Spy on `command_installer.prepare_commands` or `apply_commands` with `monkeypatch` to capture the consent.
  - Put both in `test_command_skills.py`.

## Test Strategy

```bash
uv run pytest tests/specify_cli/tool_surface/providers/test_command_skills.py \
  tests/specify_cli/tool_surface/test_drift_policy.py tests/specify_cli/tool_surface/test_repair.py \
  tests/specify_cli/tool_surface/test_findings.py tests/specify_cli/skills/test_crlf_skill_render_4998.py \
  tests/specify_cli/skills/test_command_installer.py tests/specify_cli/cli/commands/test_tool_surfaces_fail_closed.py \
  tests/specify_cli/cli/commands/test_doctor_command_skill_repair_consent.py -q
make test-fast
uv run --frozen ruff check src/specify_cli/tool_surface/providers/command_skills.py tests/specify_cli/tool_surface tests/specify_cli/cli/commands/test_doctor_command_skill_repair_consent.py
uv run --frozen ruff format --check --force-exclude <changed files>
uv run --frozen mypy src/specify_cli/tool_surface/providers/command_skills.py
```

Record commands and counts in the Activity Log. Never `make test-full` or the whole `tests/architectural/`.

## Risks & Mitigations

- **Consent leaking to unattended runs**: `overwrite_paths` is derived only from `STATE_DRIFTED` statuses inside `repair`. T009 pins it.
- **Message-text pins**: changing the finding text may break assertions elsewhere. Search for `drifted from manifest hash` in `tests/` before changing it.
- **Strict xfail #5281** in `test_crlf_skill_render_4998.py` must stay xfail. If it XPASSes, stop and report.

## Review Guidance

- The red output of T006 is recorded before the product change.
- Consent mirrors `AgentProfilesProvider.repair`; no new flag; `repair.py` is unchanged.
- The guidance names `spec-kitty doctor tool-surfaces --fix`.
- mypy and ruff are clean; no new suppressions.

## Activity Log

- 2026-10-03T07:45:00Z – system – Prompt created.
