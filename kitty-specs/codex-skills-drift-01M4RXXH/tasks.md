---
description: "Work package task list for mission codex-skills-drift"
---

# Work Packages: Codex `.agents/skills` manifest-drift idempotency

**Inputs**: Design documents from `/kitty-specs/codex-skills-drift-01M4RXXH/`
**Prerequisites**: plan.md (required), spec.md (user stories), research/diagnosis-702.md

**Tests**: Required — this is a correctness fix of a DERIVED-surface disposition; the deliverable is a red-first regression driving the real upgrade/init reconcile, plus the fix and updated policy tests.

**Organization**: One work package (`WP01`). Fine-grained subtasks (`Txxx`) roll up into it.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `src/`, `tests/`. This mission touches `src/specify_cli/skills/command_installer.py`, `tests/specify_cli/skills/`, and docs/CHANGELOG.

---

## Work Package WP01: Regenerate drifted DERIVED command-skill projections (Priority: P1) 🎯 MVP

**Goal**: Make a drifted, manifest-owned `.agents/skills/spec-kitty.<command>/SKILL.md` regenerate to the canonical render on the install/upgrade/sync/init reconcile — instead of landing in `consent_required` and being kept as a phantom user edit — while non-manifest / third-party paths stay untouched. Proven red-first through the real entry point.
**Independent Test**: `.venv/bin/python -m pytest tests/specify_cli/skills/test_command_installer_derived_regeneration_702.py` — RED on the base (drift kept), GREEN on the final commit; reverting the `preserve()` change re-reds it. Plus `spec-kitty upgrade --project` on a drifted fixture exits 0 with `doctor skills --json` `ok:true`.
**Prompt**: `/tasks/WP01-regenerate-derived-command-skill-drift.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

T001 Add the red-first regression test `tests/specify_cli/skills/test_command_installer_derived_regeneration_702.py`: scaffold a codex (+ one more shared-root agent, e.g. opencode is slash-command so use vibe/pi/letta) project via the real installer/init, mutate a manifest-owned `spec-kitty.<cmd>/SKILL.md` so its bytes differ from both the recorded hash and the render, drive the reconcile through the real `upgrade`/`init` path with automatic (non-overwrite) consent, assert the file is regenerated to the canonical render, `verify_installed_skills(...).ok` is True with 0 drift, and a second run makes no change. Add a positive-control assertion that a non-manifest `spec-kitty.*` path and a third-party dir are preserved. Witness RED on the base. Commit FIRST.
T002 Fix `src/specify_cli/skills/command_installer.py::_Plan.preserve()`: for a manifest-owned (`existing is not None`) drift (`before.sha256 not in (content_hash, digest)`) on this DERIVED/IGNORED surface, return `False` (regenerate to the canonical render) instead of emitting `consent_required`. Inline-cite the `shared_skills_projection` state-contract surface and #702. Leave the `existing is None` (non-manifest) branch untouched. Commit the GREEN fix.
T003 Add a guard test pinning the premise — `state/contract.py` `shared_skills_projection` is `authority=DERIVED`, `git_class=IGNORED` — so the regenerate decision cannot silently lose its justification (C-003).
T004 Update the tests that pinned the superseded consent-on-drift policy (`tests/specify_cli/skills/test_command_installer.py`: `test_wp04_drift_and_unknown_preserved_while_gap_repaired` and the `_prepare` drift cases asserting `consent_required` without overwrite consent) to assert the new regenerate behaviour, with docstring/comment justification citing #702 and the state contract. Keep the `existing is None` preserve cases unchanged.
T005 Document the policy (FR-003/SC-004): state in the Codex / agent-skills docs that `.agents/skills` is generated/git-ignored and regenerated idempotently by init/upgrade/sync; remove/avoid any guidance to `git add .agents/skills` as normal content; add a `[Unreleased]` CHANGELOG entry (`#702`, impact-first).
T006 Run the gates: the new regression + the updated installer/verifier/manifest suites + `tests/agent/` agent-config/doctor tests (covering `.claude`/`.codex`/`.opencode`) + `make test-fast`; `ruff check`, `ruff format --check --force-exclude` and mypy on changed files; terminology guard if prose/charter touched; confirm complexity ≤ 15 and non-vacuity (revert → RED).

### Implementation Notes

- `install_command()` hardcodes `rel = ".agents/skills/spec-kitty.{command}/SKILL.md"`, so `preserve()`'s drift branch only ever sees this DERIVED surface — regenerating is safe and correct here.
- Do NOT touch the `.claude/skills/**` managed-file installer (`skills/installer.py`) or `.claude/agents/*.md` profiles — out of scope (C-001).
- The clean version-upgrade re-render (on-disk == recorded hash, ≠ new render) already falls through this branch; verify the regression fixture distinguishes genuine drift from that case so the change is non-vacuous.
- `.codex`/`.opencode` are slash-command directories for different agents; the shared-root command-skill agents are codex/vibe/pi/letta (all `.agents/skills/`). Exercise codex plus one more shared-root agent for multi-agent coverage.

### Parallel Opportunities

- T001 (test) and T005 (docs) author different files, but T001 must land before T002 (red-first ordering).

### Dependencies

- None (starting and only package).

### Risks & Mitigations

- Over-broadening to user content → keep the `existing is None` branch untouched; assert preservation in T001 (FR-002/NFR-002).
- Regressing the version-upgrade re-render → fixture distinguishes genuine drift (T001); existing version-bump tests stay green.
- Losing the DERIVED justification later → premise guard (T003).

---

## Dependency & Execution Summary

- **WP01** — no dependencies; single sequential package on `issue-702-codex-skills-drift` (single_branch topology). Red → green → docs.
