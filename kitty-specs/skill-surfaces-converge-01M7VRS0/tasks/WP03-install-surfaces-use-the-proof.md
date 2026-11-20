---
work_package_id: WP03
title: Install surfaces use the proof
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-004
- FR-011
- FR-012
- NFR-002
- SC-001
planning_base_branch: issue-7700-skill-surfaces-converge
merge_target_branch: issue-7700-skill-surfaces-converge
branch_strategy: Planning artifacts for this mission were generated on issue-7700-skill-surfaces-converge. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7700-skill-surfaces-converge unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-skill-surfaces-converge-01M7VRS0
base_commit: a6987ab06abdbd129fdbedb60b520606ebdfadb0
created_at: '2026-11-20T09:00:40.551316+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
- T016
- T017
phase: Phase 2 - Behaviour
history:
- at: '2026-11-20T07:00:00Z'
  actor: claude::planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/runtime/agent_skills.py
create_intent:
- tests/specify_cli/runtime/test_global_skills_historical_proof.py
- tests/specify_cli/skills/test_project_skills_historical_proof.py
- docs/changelog/unreleased/7700.fixed.md
- docs/changelog/unreleased/2527.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/runtime/agent_skills.py
- src/specify_cli/skills/installer.py
- tests/specify_cli/runtime/test_global_skills_historical_proof.py
- tests/specify_cli/skills/test_project_skills_historical_proof.py
- docs/changelog/unreleased/7700.fixed.md
- docs/changelog/unreleased/2527.fixed.md
- src/specify_cli/runtime/asset_preparation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Install surfaces use the proof

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

- User-global skill sync (`assess_global_agent_skills`): an existing destination file whose sha256 is a historical render of the same `<skill>/<rel>` is refreshed (`canonical_predecessor=True`).
- `agent-skills.lock` is not written as current while any **canonical** skill destination (a path under `<root>/<canonical skill>/`) has a `preserve`/`consent_required` disposition (#7700 ruling b).
- Retired skill dirs in a global root: files proven by the historical list are retired; anything else stays and is preserved (reported by WP04).
- Project installer (`skills/installer.py`): a managed or unmanaged file whose bytes are a historical render of its path is replaced like canonical-predecessor content (with the existing backup), not `consent_required` (#2527, reproduced on `a053b674`, research R-4).
- One classifier, `kept_global_skill_files(assessment) -> tuple[KeptSkillFile, ...]`, classifies the assessment's dispositions into `stale_canonical` / `edited_retired` (custom skills excluded). WP04 consumes it.
- Startup sync, `upgrade` and `doctor --fix` reach the same verdict because they all call these two assessors (FR-011): add one test that runs the startup path and the tool-surfaces fix path on the same fixture and compares outcomes.

## Context & Constraints

- Plan IC-02, IC-03 (classifier only); spec FR-001, FR-002, FR-004, FR-011, FR-012.
- WP01 provides `specify_cli.skills.historical_renders.is_historical_render`; WP02 provides `retire(..., proven=...)` and the anchor-stable inventory.
- Never prove by name. Symlinks/directories never proven by bytes. A digest of another path never proves this one.

## Branch Strategy

Populated by finalize-tasks. Planning base and merge target: `issue-7700-skill-surfaces-converge` via the Mission branch `kitty/mission-skill-surfaces-converge-01M7VRS0`.

```bash
spec-kitty agent action implement WP03 --agent claude --mission skill-surfaces-converge-01M7VRS0
```

## Subtasks & Detailed Guidance

### Subtask T011 – Red tests

`tests/specify_cli/runtime/test_global_skills_historical_proof.py` (isolated HOME; use the real built-in catalog; seed `~/.claude/skills/<skill>/...` with the bytes of an older blob read via a hard-coded fixture copied into the test as bytes, or from the JSON's known digest + a committed tiny fixture file; do not call git in tests):
1. byte-equal historical render, no inventory → refresh effect for that path; `agent-skills.lock` effect present.
2. non-matching bytes → preserved, file untouched after apply, **no** `agent-skills.lock` effect.
3. edited copy of a retired skill → preserved; unedited (historical bytes) retired copy → removal effect.
4. a user's own custom skill dir (non-canonical, non-retired) → preserved but does NOT block the stamp.
5. FR-011 agreement: same fixture through `ensure_global_agent_skills()` and through `run_tool_surfaces(..., fix=True)` gives the same final bytes.
`tests/specify_cli/skills/test_project_skills_historical_proof.py`:
6. #2527 shape: init a project's managed skills (or call `assess_project_skills` on a minimal project), replace one managed file with a historical render while the manifest records today's hash; the assessment writes it (no `consent_required`) and backs up the old bytes; a non-historical edit stays `consent_required`.

### Subtask T012 – Global sync proof

- In `_prepare_skill_tree`, before `prepared.asset(target, data, mode)`: if the target is a regular file and `is_historical_render(skill_name, rel, observed_sha256)`, pass `canonical_predecessor=True`. Get `rel` = target relative to the skill's destination dir (thread a `relative` prefix through recursion). Observe the target with `role="destination_probe"`.

### Subtask T013 – Stamp

- After building, compute `kept_canonical = any(d.state in {"preserve","consent_required"} and <path is under a canonical skill destination>)`; pass `version_path=None` to `finish()` when true. Keep `selection` semantics.

### Subtask T014 – Retired dirs

- Replace `prepared.retire(existing)` for retired names with `prepared.retire(existing, proven=<closure over skill name and rel>)`.

### Subtask T015 – Project installer

- In `_prepare_project_skills`'s loop compute `historical = before.kind == "file" and is_historical_render(skill, rel, before.sha256)` from the expected entry (`wanted`) skill/source file; treat it like `canonical` for `_preserve_project_path` purposes but still back up (the existing backup branch runs when `not canonical`). Keep complexity <= 15: extract a helper.

### Subtask T016 – Classifier

- `KeptSkillFile(path: Path, kind: Literal["stale_canonical","edited_retired"], reason: str)`; derive from dispositions + root; export in `__all__` if the module has one.

### Subtask T017 – Changelog

- `7700.fixed.md` (#7700, #5983 retire half) and `2527.fixed.md`, Before/After style.

## Test Strategy

```bash
uv run --frozen pytest -q tests/specify_cli/runtime/test_global_skills_historical_proof.py tests/specify_cli/skills/test_project_skills_historical_proof.py tests/specify_cli/runtime/ tests/specify_cli/skills/ tests/runtime/
make test-fast
```

## Risks & Mitigations

- Existing tests may assert the stamp is written while a custom skill is preserved: keep custom skills out of the stamp rule.
- Backup on project replace: reuse the existing branch; never replace without backup.

## Review Guidance

- Byte-for-byte assertion that every unproven file is unchanged after apply (NFR-002).
