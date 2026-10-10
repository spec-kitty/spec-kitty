---
work_package_id: WP05
title: Implement command-template verification reference (#5989)
dependencies: []
requirement_refs:
- FR-007
planning_base_branch: fix/nightly-suites-green-rework
merge_target_branch: fix/nightly-suites-green-rework
branch_strategy: Planning artifacts for this mission were generated on fix/nightly-suites-green-rework. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/nightly-suites-green-rework unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-suites-green-rework-01M4J5EN
base_commit: 237405165a0a6c5f4067c96c158c79e2ec0e9526
created_at: '2026-10-10T06:17:29.194868+00:00'
subtasks:
- T015
- T016
- T017
phase: Phase 2 - Source template drift
history:
- at: '2026-10-10T05:45:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: packs/built-in/missions/mission-steps/software-dev/implement/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- packs/built-in/missions/mission-steps/software-dev/implement/prompt.md
- tests/specify_cli/upgrade/test_occurrence_classification.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Implement command-template verification reference (#5989)

## ⚡ Do This First: Load Agent Profile
Use `/spk-charter-profile-load` to load `python-pedro` (implementer, claude).

## Objectives & Success Criteria

`TestImplementTemplateContent::test_verification_checks_template_dirs` (nightly `interpreter-3.13-shard-3`, #5989) asserts the implement command-template contains the literal `src/specify_cli/missions/*/command-templates/`. The test reads the **SOURCE** template `packs/built-in/missions/mission-steps/software-dev/implement/prompt.md` (`IMPLEMENT_TEMPLATE_PATH`, test lines 29-38); that string is currently absent — the bulk-edit/occurrence-classification verification guidance was dropped during the doctrine-to-charter rework.

Done when: the template's verification guidance and the test agree on the canonical `command-templates` path (FR-007).

## Context & Constraints
- **C-004**: edit the SOURCE template under `packs/built-in/`, NEVER an agent copy under `.claude/` etc.
- **Classify first (SO#4)**: decide whether the verification instruction legitimately belongs in the implement template (restore it in the SOURCE) or whether the template intentionally moved it elsewhere (then realign the test to the canonical location). Prefer restoring real, useful verification guidance; only move the assertion if the guidance genuinely belongs on another surface. Record the judgment in the Activity Log.

## Subtasks
- **T015** — Red-first: confirm the test is red because `src/specify_cli/missions/*/command-templates/` is absent from `implement/prompt.md`; read the surrounding occurrence-classification verification context (test module docstring lines 25-28) to understand what the guidance is for.
- **T016** — Restore the verification reference in the SOURCE `implement/prompt.md` (bulk-edit safety / template-dirs verification), matching the string the test and the occurrence classifier expect — OR, if the guidance belongs elsewhere, realign the test's expected location with a one-line rationale.
- **T017** — Verify the test green; confirm no agent copy was edited (only the SOURCE).

## Branch Strategy
Planning base / merge target: `fix/nightly-suites-green-rework`. Lane from `lanes.json`.

## Validation
```bash
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -q \
  "tests/specify_cli/upgrade/test_occurrence_classification.py"
```

## Definition of Done
Test green; SOURCE template edited (not an agent copy); classification judgment recorded; `ruff` clean on the test if touched.

## Reviewer Guidance (opus)
Confirm the SOURCE (not a generated copy) was edited, the restored guidance is genuine (not a string stuffed only to pass), and the classify-restore-vs-realign judgment is sound.
