---
work_package_id: WP06
title: Verify-side retired-orphan detection
dependencies: []
requirement_refs:
- FR-006
planning_base_branch: issue-7700-skill-surfaces-converge
merge_target_branch: issue-7700-skill-surfaces-converge
branch_strategy: Planning artifacts for this mission were generated on issue-7700-skill-surfaces-converge. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7700-skill-surfaces-converge unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-skill-surfaces-converge-01M7VRS0
base_commit: 3579bd533ea5904528d91073baddcda730a09d54
created_at: '2026-11-20T06:56:48.680775+00:00'
subtasks:
- T028
- T029
- T030
- T031
phase: Phase 2 - Behaviour
history:
- at: '2026-11-20T07:00:00Z'
  actor: claude::planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/skills/verifier.py
create_intent:
- tests/specify_cli/skills/test_verify_retired_orphan.py
- docs/changelog/unreleased/2460.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/skills/verifier.py
- src/specify_cli/tool_surface/providers/managed_skills.py
- tests/specify_cli/skills/test_verify_retired_orphan.py
- docs/changelog/unreleased/2460.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Verify-side retired-orphan detection

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Record status moves as `claude::python-pedro` (no model name).

---

## Review Feedback

Check `review_ref` in the event log. Address every item before handing back.

## Objectives & Success Criteria

- `verify_installed_skills` reports a manifest entry whose skill is absent from a **non-empty** registry and whose file is present, as `VerifyResult.retired`; `ok` is False while any exists (#2460 contract widening, accepted by the brief).
- `ManagedSkillsProvider._delegate_repair` runs the repair for retired entries; `repair_skills` drains them through `assess_project_skills(retire=True)` (its existing retirement path) and the manifest entry leaves.
- An edited retired file (hash differs) keeps today's behaviour (drift → consent rules), never deleted without proof.
- `m_2_1_1` migration's `detect` inherits the widened `ok` (document in the changelog; no migration edit — DIRECTIVE_044, never edit a shipped migration).

## Context & Constraints

- Plan IC-04 (#2460 half); research R-5.
- Registry empty ⇒ no retired reporting (a missing package must never look like retirement; mirrors `_retirable_paths(catalog_empty=...)`).

## Branch Strategy

Populated by finalize-tasks. Planning base and merge target: `issue-7700-skill-surfaces-converge` via the Mission branch `kitty/mission-skill-surfaces-converge-01M7VRS0`.

```bash
spec-kitty agent action implement WP06 --agent claude --mission skill-surfaces-converge-01M7VRS0
```

## Subtasks & Detailed Guidance

### Subtask T028 – Red test

`tests/specify_cli/skills/test_verify_retired_orphan.py`:
1. project with a manifest entry for a retired skill (e.g. `spk-team-sync`, copy mode) whose file matches the recorded hash → `verify_installed_skills(...).ok is False` and the entry is in `.retired`.
2. `ManagedSkillsProvider().repair(...)` (or `doctor tool-surfaces --kind charter-skill --fix`) removes the file and the manifest entry.
3. edited retired file → not deleted.
4. positive control: a clean project → `ok` True, nothing in `retired`.

### Subtask T029 – `VerifyResult.retired`

- Add field + include in `ok` and `total_issues`; populate when `registry` is non-empty and `registry.get_skill(entry.skill_name) is None` and the file is a regular file matching `entry.content_hash`.
- Perf: `registry.get_skill` rescans per call (#2460 item 2): build one `{name: skill}` dict per verify.

### Subtask T030 – Repair

- `repair_skills`: include retired entries in `requested`; `_delegate_repair` count check: retired removals count as repaired. If `RepairResult` id mapping makes `repaired != len(ids)` ambiguous, compute ids for retired entries explicitly.

### Subtask T031 – Changelog

- `2460.fixed.md`.

## Test Strategy

```bash
uv run --frozen pytest -q tests/specify_cli/skills/test_verify_retired_orphan.py tests/specify_cli/skills/ tests/specify_cli/tool_surface/
```

## Review Guidance

- Non-empty-registry guard present; edited retired file never removed.
