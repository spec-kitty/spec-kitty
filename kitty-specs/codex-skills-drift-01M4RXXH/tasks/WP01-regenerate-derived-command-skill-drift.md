---
work_package_id: WP01
title: Regenerate drifted DERIVED command-skill projections
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-702-codex-skills-drift
merge_target_branch: issue-702-codex-skills-drift
branch_strategy: Planning artifacts for this mission were generated on issue-702-codex-skills-drift. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-702-codex-skills-drift unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Fix
history:
- timestamp: '2026-10-12T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/skills/command_installer.py
create_intent:
- tests/specify_cli/skills/test_command_installer_derived_regeneration_702.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/skills/command_installer.py
- tests/specify_cli/skills/test_command_installer.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- spec-kitty/spec-kitty#702
---

# WP01 — Regenerate drifted DERIVED command-skill projections

## Goal

A drifted, **manifest-owned** `.agents/skills/spec-kitty.<command>/SKILL.md` must be regenerated to the canonical render during the install/upgrade/sync/init reconcile, instead of being classified `consent_required` ("Managed command content has drifted") and kept. The surface is DERIVED/IGNORED per `state/contract.py` `shared_skills_projection` — never committed, always regenerable — so cross-checkout / stale-output drift is spurious, not a user edit. Non-manifest / third-party paths under `.agents/skills/` stay untouched (installer NFR-002).

## Context / root cause

See `research/diagnosis-702.md`. The defect lives in `src/specify_cli/skills/command_installer.py::_Plan.preserve()`:

```python
if existing is not None and before.sha256 not in (existing.content_hash, digest):
    if rel in self.inputs.consent.overwrite_paths:
        return False
    self.disposition(rel, "consent_required", "Managed command content has drifted")
    return True
```

`install_command()` only ever manages `.agents/skills/spec-kitty.{command}/SKILL.md`, so this branch is always on a DERIVED/IGNORED path.

## Subtasks

- **T001** — Red-first regression `tests/specify_cli/skills/test_command_installer_derived_regeneration_702.py`, driving the real `upgrade`/`init` reconcile; witness RED on base; commit first.
- **T002** — Flip the `preserve()` drift branch to regenerate for the manifest-owned DERIVED surface; inline-cite `shared_skills_projection` + #702; commit GREEN.
- **T003** — Premise guard: `shared_skills_projection` is DERIVED/IGNORED.
- **T004** — Update superseded-policy tests in `test_command_installer.py` with #702 justification.
- **T005** — Docs + CHANGELOG `[Unreleased]` (generated/ignored policy, idempotent repair, fresh-clone).
- **T006** — Gates: regression + skills/manifest/agent-config/doctor suites + `tests/agent/` + `make test-fast`; ruff/format/mypy; terminology guard; complexity ≤ 15; non-vacuity revert proof.

## Acceptance

- FR-001/NFR-001/NFR-003: after one reconcile, a drifted projection equals the canonical render; `verify_installed_skills(project).ok` with `drifted == []`; a second reconcile changes nothing.
- FR-002/NFR-002: a non-manifest `spec-kitty.*` file and a third-party dir are byte-identical after the reconcile.
- SC-001: `spec-kitty upgrade --project` on a drifted fixture exits 0; `doctor skills --json` → `ok:true`.
- SC-002: the regression is RED pre-fix, GREEN post-fix, for codex + one more shared-root agent.
- C-001/C-002/C-003: scope held to the command-skill installer; ruff/format/mypy clean, complexity ≤ 15, no suppressions; premise guard present.
- FR-003/SC-004: docs state the generated/ignored + idempotent-repair policy.

## Out of scope

`.claude/skills/**` managed-file installer, `.claude/agents/*.md` profiles, the `.agents/` gitignore policy, the manifest schema, `remove_entry()` prune-time consent, and #5574/#5709/#5745/#1780/#1670.
