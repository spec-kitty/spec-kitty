---
work_package_id: WP01
title: Upgrade plans a missing tool folder once
dependencies: []
requirement_refs:
- FR-001
- FR-002
- C-001
- NFR-001
- SC-001
- NFR-002
- NFR-003
planning_base_branch: ccr-11788f1f-qu75jg
merge_target_branch: ccr-11788f1f-qu75jg
branch_strategy: Planning artifacts for this mission were generated on ccr-11788f1f-qu75jg. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into ccr-11788f1f-qu75jg unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-skill-surface-upgrade-integrity-01M482Z3
base_commit: 613a401c6902c0f89054c6b6705c9b77b96736f5
created_at: '2026-10-06T08:09:01.140313+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Upgrade surface planning
history:
- at: '2026-10-06T08:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tool_surface/
create_intent:
- tests/upgrade/test_upgrade_absent_tool_folder_4275.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/tool_surface/operations.py
- src/specify_cli/tool_surface/providers/managed_skills.py
- tests/specify_cli/tool_surface/test_operations.py
- tests/specify_cli/tool_surface/providers/test_managed_skills.py
- tests/upgrade/test_upgrade_absent_tool_folder_4275.py
- tests/specify_cli/skills/test_crlf_skill_render_4998.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Upgrade plans a missing tool folder once

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission skill-surface-upgrade-integrity-01M482Z3`). Address every feedback item before completing.

---

## Objectives & Success Criteria

- FR-001: `spec-kitty upgrade --project --yes` exits 0 in a project with `claude` configured and no `.claude/`, and recreates `.claude/` with profiles, commands and skills (#4275).
- FR-002: a genuine conflict (differing mode, phase, action, or content) at one destination still raises, and the message names the destination, both owners and the differing field(s).
- C-001: one merge authority — `coalesce_effects`. The narrower local merge in `managed_skills.py:125-140` delegates to it (or is removed in its favour).
- NFR-001: T001's regression test is RED on the planning base and GREEN at the final commit.

## Context & Constraints

- Spec: `kitty-specs/skill-surface-upgrade-integrity-01M482Z3/spec.md`; plan IC-01; data-model "Surface effect"; research R-1.
- Root cause (live repro): `coalesce_effects` (`src/specify_cli/tool_surface/operations.py:176-189`) keys effects by `destination` and raises `ValueError("Owner effect conflict at …")` when `(owner, phase, action, before, after)` differs. Two producers emit an identical `create absent -> directory 0o755` for `<repo>/.claude`:
  - `managed_skills` — `src/specify_cli/skills/installer.py:611` ("Create managed-skill parent")
  - `agent_profiles` — `src/specify_cli/tool_surface/providers/agent_profiles.py:766-775` (`prepare_parents`, walks every absent ancestor)
  Only `owner` differs.
- Do NOT "fix" by making `prepare_parents` stop emitting parents: apply-time `mkdir` (`agent_profiles.py:817`) would then fail — a vacuous fix.
- Charter: ATDD/red-first through the pre-existing entry point; complexity ≤15; no `# noqa`/`# type: ignore`.
- Repro work only in a temp directory (`tmp_path`), never in the repository root checkout.

## Branch Strategy

- **Strategy**: (populated by finalize-tasks)
- **Planning base branch**: `ccr-11788f1f-qu75jg`
- **Merge target branch**: `ccr-11788f1f-qu75jg`

Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty agent action implement WP01 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first repro through `upgrade`

- **Purpose**: Pin #4275 user-observably before changing code.
- **Steps**:
  1. Create `tests/upgrade/test_upgrade_absent_tool_folder_4275.py`. Mark `@pytest.mark.regression`. Use the real `init` + `upgrade --yes` pattern from `tests/specify_cli/skills/test_crlf_skill_render_4998.py:515ff` (`test_failed_upgrade_recoverable.py` has only metadata stubs; hand-built fixtures behave differently).
  2. Kittify a temp project with `claude` AND one Agent Skills tool (codex) configured (covers `.claude` and `.agents/skills`, SC-001); delete `.claude/`; invoke the project upgrade path with `--yes`.
  3. Assert exit code 0 and that `.claude/` exists with at least the skills and agents subfolders the finalizer produces.
  4. Run it on the planning base and record the RED output (`Owner effect conflict at …/.claude`) in the Activity Log. Commit the test alone first.
- **Notes**: Prefer the cheapest real entry point that reaches `prepare_upgrade_repairs` (`upgrade/assessment.py:121`); if the full CLI is too slow, a test calling `prepare_upgrade_repairs` on the kittified tree is acceptable as long as it uses the real providers.

### Subtask T002 – Merge rule in `coalesce_effects`

- **Purpose**: FR-001.
- **Steps**:
  1. Read `operations.py:150-200` fully, including how `logical_owners`, `surface_ids` and `ownership` are concatenated after the equality check (lines ~185-189).
  2. Introduce a small pure predicate, e.g. `_is_shared_directory_create(previous, effect) -> bool`: true iff both `action == "create"`, `before` is the absent state, `phase` equal, and `after` equal (kind directory + mode). Owner may differ.
  3. In the coalescer: if tuples match exactly → existing path. Else if the predicate holds → merge (union `logical_owners`, `surface_ids`, `ownership`, preserving order and de-duplicating); keep a deterministic primary `owner` (the lexicographically lowest). Else → raise (T003).
  4. Keep the function ≤15 complexity; extract helpers.
- **Files**: `src/specify_cli/tool_surface/operations.py`.

### Subtask T003 – Actionable conflict message

- **Purpose**: FR-002.
- **Steps**: build the message from a helper that lists differing field names among `owner, phase, action, before, after`: `Owner effect conflict at <dest>: <owner_a> vs <owner_b> (differs in: phase, after)`. Keep `ValueError` type (callers may catch it; grep `Owner effect conflict` in `src/` and `tests/` and update any exact-string assertions).

### Subtask T004 – Delegate managed_skills merge

- **Purpose**: C-001 single authority.
- **Steps**: inspect `tool_surface/providers/managed_skills.py:125-140`. If its merge is exactly the shared-directory-create case, replace it with a call into the coalescer (or the shared predicate exported from `operations.py`), keeping its `Unsupported shared skill effect` refusal for anything else only if still reachable. Its existing tests in `tests/specify_cli/tool_surface/providers/test_managed_skills.py` must stay green.

### Subtask T005 – Focused unit tests

- **Steps** (in `tests/specify_cli/tool_surface/test_operations.py`):
  - two owners, identical absent→dir create → one effect, both owners in `logical_owners`/`ownership`.
  - differing mode → raises; message names both owners and `after`.
  - differing phase → raises.
  - file write vs file write with different content → raises (regression guard).
  - three effects on `.agents/skills` from two Agent Skills tools (codex + vibe or pi) → merge.
- Invert `tests/specify_cli/tool_surface/providers/test_managed_skills.py:1264-1268` (`test_shared_parent_composition_cold_real_owners`, `parents=False` expects `Owner effect conflict`) to assert the merge keeps both owners.
- Update the stale docstring workaround in `tests/specify_cli/skills/test_crlf_skill_render_4998.py:521-524`.
- Leave `tests/upgrade/test_upgrade_outcome_kind.py:48` (fake string only).
- Note: `skills/installer.py:614` also calls `coalesce_effects` for directory parents; it inherits the new rule with no edit (third call site, same authority).
- After T002 lands, convert T001 per ADR 2026-07-17-1: keep it as a focused test, drop the `regression` marker.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/specify_cli/tool_surface/ tests/upgrade/test_upgrade_absent_tool_folder_4275.py -q
.venv/bin/python -m pytest tests/specify_cli/tool_surface/providers/test_managed_skills.py -q
make test-fast
.venv/bin/ruff check src/specify_cli/tool_surface && .venv/bin/ruff format --check --force-exclude <changed files>
.venv/bin/mypy src/specify_cli/tool_surface/operations.py src/specify_cli/tool_surface/providers/managed_skills.py
```

## Risks & Mitigations

- Over-broad merge masks a real conflict → strict predicate + negative tests.
- Order-dependent primary owner → deterministic sort.

## Review Guidance

- Verify T001 was RED on the planning base (Activity Log) and GREEN now.
- Confirm no second merge authority remains.
- Confirm mypy + ruff clean and complexity ≤15.

## Activity Log

- 2026-10-06T08:10:00Z – system – Prompt created.
