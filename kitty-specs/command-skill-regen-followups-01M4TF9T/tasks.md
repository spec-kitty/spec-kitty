---
description: "Work package task list for mission command-skill-regen-followups"
---

# Work Packages: Command-skill regeneration follow-ups (#6155)

**Inputs**: Design documents from `/kitty-specs/command-skill-regen-followups-01M4TF9T/`
**Prerequisites**: plan.md (required), spec.md (user stories), research/code-grounding.md
**Hold**: Implementation is held until PR #6113 (closes #702) merges to `main`; this WP extends #6113's `preserve()` change.

**Tests**: Required — items 2 and 3 are behaviour corrections proven RED-first through the real reconcile/provider/prune entry points (revert → RED), mirroring #6113's red-first style; item 1 is tested through the human and `--json` output.

**Organization**: One work package (`WP01`) — the three items are tightly coupled in two methods of one module (`command_installer.py`) plus reporting threaded through existing renderers (single_branch topology, one lane). Fine-grained subtasks (`Txxx`) roll up into it.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `src/`, `tests/`. This mission touches `src/specify_cli/skills/command_installer.py`, the upgrade/init/agent-config reporting surfaces, `src/specify_cli/tool_surface/{providers/command_skills.py,repair.py}`, their tests, and `docs/changelog/CHANGELOG.md`. It READS `src/specify_cli/state/contract.py`.

---

## Work Package WP01: Command-skill regeneration follow-ups (Priority: P1) 🎯 MVP

**Goal**: Deliver #6155's three follow-ups on the DERIVED/git-IGNORED command-skill surface: (1) name each regenerated projection path once in human + `--json` `surface_repair` output without changing the exit code or outcome kind; (2) gate `preserve()`'s regenerate on the runtime DERIVED/IGNORED read of `shared_skills_projection`, else fall through to the consent branch (reviving `overwrite_paths`); (3) prune a retired command's drifted manifest-owned projection and its manifest entry in `remove_entry()` on the same gate, still refusing a directory and never touching an unowned path. Non-manifest / third-party paths stay untouched throughout.
**Independent Test**: `.venv/bin/python -m pytest tests/specify_cli/skills/test_command_installer_derived_regeneration_702.py tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py tests/specify_cli/cli/commands/test_doctor_skills.py` — the item-2 (non-DERIVED fall-through) and item-3 (retired prune) assertions are RED on the merged-#6113 base and GREEN on the final commit (revert the fix → RED); the item-1 `surface_repair["regenerated"]` + human-notice assertions name each path once; in-sync and recorded-hash-equal projections stay silent; `spec-kitty upgrade --yes` exit code and outcome kind are unchanged.
**Prompt**: `/tasks/WP01-command-skill-regeneration-followups.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, NFR-003, NFR-004, C-001, C-002, C-003, SC-001, SC-002, SC-003, SC-004, SC-005

### Included Subtasks

T001 [P] Red-first (item 2): add a unit test that monkeypatches the `shared_skills_projection` contract entry to a non-ignored (or non-derived) class and drives a drifted, manifest-owned projection through `preserve()` / the real reconcile without overwrite consent, asserting it is kept as `consent_required` (pre-#6113 behaviour). Witness RED on the merged-#6113 base (the regenerate is currently unconditional). Also assert that under the REAL DERIVED/IGNORED class the drifted projection is still regenerated, and that with `overwrite_paths` consent on the fall-through path it IS overwritten (FR-003). Commit FIRST.

T002 [P] Red-first (item 3): add a test where a retired command's drifted, manifest-owned projection is reconciled through the real prune entry point (`prune_stale` / `remove`), asserting the file and its manifest entry are removed, an unowned (non-manifest) file at a `spec-kitty.*` path is preserved, and a directory at the projection path is still refused. Witness RED on the base (currently `consent_required`, kept). Commit FIRST.

T003 Reporting tests (item 1): assert through `spec-kitty upgrade --yes` (human and `--json`) and the provider/install call that each regenerated path is named exactly once (e.g. `surface_repair["regenerated"]` for `--json`, the per-path human line), that an in-sync projection and one equal to the recorded manifest hash produce NO line, and that the process exit code and `outcome` kind are unchanged versus the pre-change run on the same fixture. These are RED on the base (regenerate is silent) and GREEN after T006.

T004 Fix (item 2): in `src/specify_cli/skills/command_installer.py::_CommandBatch.preserve()`, read `shared_skills_projection` from `specify_cli.state.contract.STATE_SURFACES` (cached once per `_CommandBatch`) and gate the regenerate (`return False`) on `authority is DERIVED and git_class is IGNORED`; otherwise fall through to the existing consent branch (`overwrite_paths` → `consent_required`). Revive the `overwrite_paths` check on the non-adopt path. Rewrite the inline DERIVED/IGNORED comment to describe the runtime gate, and update the provider comment in `src/specify_cli/tool_surface/providers/command_skills.py` (near the `overwrite_paths` construction) to match. Inline-cite #6155. Commit GREEN (T001 passes).

T005 Fix (item 3): split `_CommandBatch.remove_entry()`'s top guard — keep refusing `before.kind == "directory"`, but for a drifted manifest-owned file (`before.kind == "file" and before.sha256 != entry.content_hash`) under the same DERIVED/IGNORED gate (reuse T004's helper), proceed to the existing delete/prune path (effect → absent, empty-parent cleanup, `manifest.remove_path`) instead of `consent_required`. Leave the directory refusal and the manifest-entry-only iteration untouched. Commit GREEN (T002 passes).

T006 Fix (item 1): record the regenerated `rel` in `preserve()`'s drift branch (strictly where it returns False to regenerate — not the in-sync or recorded-hash-equal paths); surface it via a new `InstallReport.regenerated` field (new `report_kind="regenerated"`) for the `install()`-based legs (`init.py`, `agent/config.py` print one per-path notice), and via a new `DriftPolicySummary.regenerated` bucket for the upgrade leg (`upgrade.py:_apply_prepared_surface_repairs` routes the regenerated subset; `_surface_repair_payload` adds `"regenerated"`; `repair.py:render_surface_summary_lines` emits the per-path human line). Route everything through the owned `surface_repair` summary so `test_upgrade_outcome_single_rendering.py` stays green; do NOT build output in a presentation function. Commit GREEN (T003 passes).

T007 [P] Docs (item 1/2/3): add a `[Unreleased]` CHANGELOG entry (impact-first, `#6155`) stating the regenerated-path notice, the runtime-gated regeneration, and the retired-projection prune; verify `docs/api/upgrade-lifecycle.md` (touched by #6113) still reads true and extend only if needed.

T008 Gates: run the new/updated regression + `tests/specify_cli/skills/` + `tests/specify_cli/tool_surface/providers/test_command_skills.py` + `tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py` + `tests/specify_cli/cli/commands/test_doctor_skills.py` + the #702 regression file + `make test-fast`; the named architectural gates `tests/architectural/test_no_legacy_terminology.py` and `tests/architectural/test_upgrade_outcome_single_rendering.py` (individually, never the bare directory); `ruff check`, `ruff format --check --force-exclude` and mypy on changed files; confirm complexity ≤ 15 and non-vacuity (revert the item-2/3 fix → RED). Record exact commands + pass/fail counts for the PR.

### Implementation Notes

- `install_command()` hardcodes `rel = ".agents/skills/spec-kitty.{command}/SKILL.md"`, so `preserve()`'s drift branch and `remove_entry()` only ever see this DERIVED surface; the gate is correct and safe here.
- Three install surfaces route through `command_installer.install()` → `InstallReport` (init.py:~155, agent/config.py:~188 via `_register_skill_agent`/`sync_agents`, `_command_surface_doctor.py:~329`); `upgrade` goes through `prepare_commands(..., prune=True)` + the provider, surfaced via `DriftPolicySummary`.
- Do NOT touch the `existing is None` (non-manifest) branch, the `.claude/skills/**` managed-file installer, `.claude/agents/*.md` profiles, or any other managed surface (C-001; ADR 2026-10-04-3 Decision 5 unchanged). The unresolved-drift exit code (#5745) is out of scope.
- The recorded-hash-equal version-bump re-render already falls through `preserve()` and must stay silent (no regenerated line); the regression fixture distinguishes genuine drift from that case.
- Verify final EDIT line numbers against the MERGED #6113 base (they shift with the merge) before editing.

### Parallel Opportunities

- T001, T002 (red-first tests) and T007 (docs) author different files. T001/T002/T003 must land before their paired fixes (T004/T005/T006) — red-first ordering within the single lane.

### Dependencies

- External: PR #6113 must be merged to `main` first (HOLD). Internal: none (starting and only package); T004 supplies the gate helper that T005 reuses.

### Risks & Mitigations

- Over-broadening to user content → keep `existing is None` untouched; `remove_entry` iterates manifest entries only; pin preservation controls (T001/T002).
- Outcome-contract regression (item 1) → route through the owned `surface_repair` summary; keep `test_upgrade_outcome_single_rendering.py` green (T006/T008).
- Double-reporting on init → the direct install leg regenerates first; assert exactly-once (T003).
- Runtime read diverging from the premise guard → read the same fields the guard asserts; keep the guard (T004).
- Merge-conflict against #6113 → concentrated in `command_installer.py:~734-781`; rebase on the merged base before editing.

---

## Dependency & Execution Summary

- **WP01** — no internal dependencies; single sequential package on `issue-6155-command-skill-regeneration-followups` (single_branch topology). External HOLD on #6113 merging. Red (T001–T003) → green (T004–T006) → docs (T007) → gates (T008).
