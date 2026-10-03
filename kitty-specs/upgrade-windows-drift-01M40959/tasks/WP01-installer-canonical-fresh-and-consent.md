---
work_package_id: WP01
title: 'Command-skill installer: canonical bytes are fresh, consent is honored'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- NFR-001
- NFR-002
- C-003
- C-005
planning_base_branch: kitty/upgrade-windows-drift
merge_target_branch: kitty/upgrade-windows-drift
branch_strategy: Planning artifacts for this mission were generated on kitty/upgrade-windows-drift. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/upgrade-windows-drift unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-windows-drift-01M40959
base_commit: fc9d2a7b5a1cac97a66993b1c6c8c54e80803425
created_at: '2026-10-03T07:56:05.723435+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Command skills
history:
- at: '2026-10-03T07:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/skills/
create_intent:
- tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py
execution_mode: code_change
model: claude-sonnet-5-5-high
owned_files:
- src/specify_cli/skills/command_installer.py
- src/specify_cli/skills/manifest_store.py
- tests/specify_cli/skills/test_command_installer.py
- tests/specify_cli/skills/test_manifest_repair.py
- tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Command-skill installer: canonical bytes are fresh, consent is honored

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter (`python-pedro`, role `implementer`) and behave according to its guidance before parsing the rest of this prompt.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission upgrade-windows-drift-01M40959`) and the Activity Log below. Address every feedback item before completing.

---

## Objectives & Success Criteria

Closes **#5574** at the command-skill owner, and lands the installer half of **#5575**.

1. A command skill whose on-disk bytes equal today's canonical rendering is **fresh**, whatever hash the manifest recorded. The adoption pass that `spec-kitty upgrade` runs (`_repair_stale_command_manifest` → `manifest_store.repair_stale_manifest` → `prepare_commands(adopt_only=True)`) refreshes the recorded `content_hash` to the canonical digest. A following `spec-kitty upgrade --yes` exits 0 (spec FR-001, SC-001).
2. The installer honors explicit consent. A path the installer would otherwise mark `consent_required` ("Managed command content has drifted") is overwritten with the canonical rendering when, and only when, it is named in `inputs.consent.overwrite_paths`. WP02 wires the provider to pass that consent.
3. Ratchet: an unattended `spec-kitty upgrade --yes` leaves a genuinely edited command skill byte-identical and still exits non-zero with the drift report (spec FR-002, NFR-002, C-003).

## Context & Constraints

- Read: `kitty-specs/upgrade-windows-drift-01M40959/spec.md`, `plan.md` (IC-01, IC-02), `research.md` (D1, D2), `data-model.md` (command-skill table), `contracts/command-skill-drift.md`, `research-memo.md`.
- Charter: `.kittify/charter/charter.md` — red-first (C-011), user customization preservation, complexity ≤ 15, no new suppressions.
- **No new public CLI flag** (C-002). **Do not widen** into #702, the Codex skill-drift programme, #2527, or `doctor skills` (#5281). The strict `xfail` `test_doctor_skills_fix_converges_self_consistent_drift` in `tests/specify_cli/skills/test_crlf_skill_render_4998.py` must stay as it is. If your change makes it XPASS, stop and report; do not edit it.
- Code anchors (verify line numbers yourself):
  - `src/specify_cli/skills/command_installer.py`:
    - `install_command` ~657-713: digest at ~673, `preserve` call ~674, adopt-only early return ~676, `same`/`existing` entry reuse ~680-685.
    - `preserve` ~715-727.
    - `prepare_commands` ~865.
    - `verify` ~1098 (keep it read-only).
  - `src/specify_cli/skills/manifest_store.py` `repair_stale_manifest` ~424-462: the drifted report at ~446.
  - `src/specify_cli/cli/commands/upgrade.py` `_run_upgrade_surface_repair` ~435-485, `_surface_drift_exit_required` ~508. Read only; this WP does not edit `upgrade.py`.
  - `src/specify_cli/tool_surface/operations.py` `ApplyConsent` (~242-254) and how `apply_commands` / `recheck_commands` compare consent.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `kitty/upgrade-windows-drift`
- **Merge target branch**: `kitty/upgrade-windows-drift`

Execution worktrees are allocated per computed lane from `lanes.json`; run `spec-kitty agent action implement WP01 --agent cursor --mission upgrade-windows-drift-01M40959` and work only in the workspace it prints.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first entry-point test for #5574

- **Purpose**: prove the bug through the real CLI before changing product code (C-005, NFR-001).
- **Steps**:
  1. Create `tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py`. Model it on `test_doctrine_skill_repair_converges_via_real_upgrade_cli` in `tests/specify_cli/skills/test_crlf_skill_render_4998.py` (~517-610):
     - `CliRunner` against `specify_cli.app`.
     - `spec-kitty init --ai codex --non-interactive` inside `tmp_path/"project"` with `contextlib.chdir`.
     - Assert `Path.home().is_relative_to(tmp_path)`.
  2. Pick one installed command skill, e.g. `.agents/skills/spec-kitty.plan/SKILL.md`. Do not touch its bytes. Load the command-skill manifest with `manifest_store.load(project)`, replace that entry's `content_hash` with a different valid hex digest (e.g. `"0" * 64`, the shape an older release's render leaves), and `manifest_store.save(...)`.
  3. Run `spec-kitty upgrade --yes`. Assert:
     - `exit_code == 0`, and `"Unresolved tool-surface drift"` is not in the output;
     - the manifest entry's `content_hash` now equals `manifest_store.fingerprint_file(skill_path)`;
     - the skill bytes are unchanged.
  4. Mark the test `integration` and `slow`, like its model. Run it and **record the red output** (expected: exit 1 with the drift message) in the Activity Log before touching product code.
- **Files**: new `tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py`.
- **Notes**: if the real `init` + `upgrade` turns out to be red for an unrelated reason, report it rather than switching to a weaker unit-only proof.

### Subtask T002 – Red-first unit test at the owner

- **Purpose**: pin the classifier directly so the behavior is cheap to test.
- **Steps**: in `tests/specify_cli/skills/test_command_installer.py` (reuse its existing project fixtures), add:
  - canonical bytes on disk, manifest entry with an older hash. `prepare_commands(inputs, ("codex",), adopt_only=True)` must not produce a `consent_required` disposition for that path, and must stage a manifest entry whose `content_hash` equals the canonical digest. `apply_commands(...)` must leave the file bytes unchanged and persist the refreshed hash.
  - the same through `manifest_store.repair_stale_manifest(project, canonical_commands=list(CANONICAL_COMMANDS))`: the path is not in `result.drifted` after the change, and the manifest hash is refreshed.
- Run them red first and record that in the Activity Log.

### Subtask T003 – Canonical bytes are fresh; adopt-only refreshes the hash

- **Purpose**: the fix for #5574.
- **Steps**:
  1. In `preserve(rel, before, existing, digest)`, a regular file whose `before.sha256 == digest` is never `consent_required`. The bytes are already canonical, and only the recorded hash is old.
  2. In `install_command`:
     - The adopt-only early return currently refuses whenever `existing is not None`. Allow exactly the case `existing is not None and before.kind == "file" and before.sha256 == digest and existing.content_hash != digest`.
     - In that case, and also for a non-adopt install, the staged `ManifestEntry` must carry `content_hash=digest`. Today the `same and existing is not None` branch keeps `existing` verbatim, which would leave the old hash; use `dataclasses.replace(existing, content_hash=digest)` and keep the agents-added loop.
     - `report_kind` is consumed via `getattr(report, command.report_kind)` (~1074, ~1086), so it must name an existing `InstallReport` field (~186-199) or you must add the field in the same change. With `replace(existing, content_hash=digest)`, `existing != entry`, so the current expression yields `reused_shared`; assert that explicitly in a test.
     - Make sure no file write effect is emitted (bytes are already correct; `same` is true, so the `else` disposition "Canonical bytes retained" applies).
  3. `install_command` is near the complexity ceiling (15). Extract a small pure helper, e.g. `_adopt_decision(existing, before, digest, adopt_only) -> bool` or `_refreshed_entry(...)`, rather than growing the function. Add focused tests for the helper's branches.
  4. Expose a public, read-only helper `canonical_digest(project_root: Path, command: str) -> str | None`. It returns the SHA-256 of today's rendering for the configured command-skill agents, or `None` when the render fails or agents render differently. Reuse `_render_command_skill` and the same agent roster `prepare_commands` uses; no writes. WP02's `probe` consumes it. Add unit tests for both return shapes.
  5. In `repair_stale_manifest`, the `drifted` list (~446) must not report a path whose bytes equal the canonical rendering. Either compute the drift list after the adoption pass, or exclude paths the pass refreshed. Keep "never rewrites command bytes" true.
- **Must not change**:
  - `verify()` stays read-only and hash-versus-manifest; it becomes correct because the manifest is refreshed.
  - Unknown bytes with no manifest entry stay `preserve`.
  - Absent files are not synthesized by adopt-only.

### Subtask T004 – Honor explicit consent in the installer

- **Purpose**: the installer half of #5575; WP02 supplies the consent.
- **Steps**:
  1. In `preserve`, when `existing is not None and before.sha256 != existing.content_hash and before.sha256 != digest`, the result is currently `consent_required`. If `rel in self.inputs.consent.overwrite_paths`, do **not** preserve; fall through so the canonical bytes are written and the entry records `digest`. Confirm `self.inputs` (or the batch's equivalent) carries the `AssessmentInputs.consent`.
  2. No change is needed in `apply_commands` or `recheck_commands`:
     - `apply_commands` (~1013) already refuses when `consent != assessment.consent`, comparing the whole dataclass, `overwrite_paths` included.
     - `recheck_commands` (~915) is state-based and does not re-refuse a consented overwrite.

     Honor consent in `preserve` only, mirroring `agent_profiles.py` ~700-703.
  3. `remove_entry` (prune of an edited owned file, ~730) keeps its own `consent_required`. Out of scope; do not change it.
- **Tests** in `test_command_installer.py`:
  - edited file + `ApplyConsent(automatic=True, overwrite_paths=(rel,))` → overwritten with canonical bytes, hash recorded;
  - edited file + `ApplyConsent(automatic=True)` → `consent_required`, bytes unchanged;
  - consent naming a *different* path does not overwrite this one.

### Subtask T005 – Ratchet: unattended upgrade keeps a real edit

- **Purpose**: FR-002 / NFR-002 / C-003. Must be green before and after; it guards against T003/T004 over-reaching.
- **Steps**: in `test_upgrade_command_skill_drift.py`, add a second real-CLI test: `init --ai codex`, append `"\n<!-- local edit -->\n"` to `.agents/skills/spec-kitty.plan/SKILL.md`, capture the bytes, run `upgrade --yes`. Assert:
  - `exit_code != 0` and the output contains `doctor tool-surfaces`;
  - the file bytes are identical before and after (zero bytes rewritten);
  - the manifest hash is unchanged.
- To keep runtime down, both tests may share one module-scoped `init`, provided each test copies the project into its own directory (`shutil.copytree`) before mutating.

## Test Strategy

Run, from the lane workspace:

```bash
uv run pytest tests/specify_cli/skills/test_command_installer.py tests/specify_cli/skills/test_manifest_repair.py \
  tests/specify_cli/skills/test_manifest_store.py tests/specify_cli/skills/test_command_manifest_determinism.py \
  tests/specify_cli/skills/test_crlf_skill_render_4998.py tests/specify_cli/tool_surface/providers/test_command_skills.py \
  tests/specify_cli/tool_surface/test_drift_policy.py tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py -q
make test-fast
uv run --frozen ruff check src/specify_cli/skills tests/specify_cli/skills tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py
uv run --frozen ruff format --check --force-exclude <changed files>
uv run --frozen mypy src/specify_cli/skills/command_installer.py src/specify_cli/skills/manifest_store.py
```

Record commands and pass/fail counts in the Activity Log. Do not run `make test-full` or the whole `tests/architectural/`.

## Risks & Mitigations

- **Over-adoption**: adopt-only must refresh only when the bytes are exactly canonical. Unknown bytes, symlinks and package links keep their current dispositions; the existing symlink-loop tests (`test_command_installer_symlink_loops.py`) must stay green.
- **Shared-content conflict**: `prepare_commands` raises `shared_content_conflict` when agents render differently. Do not paper over it.
- **Complexity**: extract helpers; keep `install_command` and `preserve` ≤ 15.
- **Out of scope, by decision**: `init.py` ~1499-1506 has a second exit-1 path for the same symptom (non-interactive `init` over an existing project does not run the adoption pass). It is not part of #5574's upgrade report. Do not edit `init.py`; it is logged as a follow-up in `traces/design-decisions.md`.
- `_repair_stale_command_manifest` swallows exceptions (`upgrade.py` ~430). If adoption raises, the run falls through to exit 1, and T001 will show it. Investigate rather than mask.

## Review Guidance

- The red output of T001/T002 is recorded before the product change (commit order or Activity Log).
- T005 proves unattended upgrade wrote zero bytes to the edited file.
- No change to `upgrade.py`, `verify()` semantics, `doctor skills`, or public flags.
- mypy and ruff are clean on touched files; no new `noqa` / `type: ignore`.

## Activity Log

- 2026-10-03T07:45:00Z – system – Prompt created.
