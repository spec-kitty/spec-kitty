---
work_package_id: WP01
title: Historical-render proof source
dependencies: []
requirement_refs:
- C-001
- FR-001
- NFR-001
planning_base_branch: issue-7700-skill-surfaces-converge
merge_target_branch: issue-7700-skill-surfaces-converge
branch_strategy: Planning artifacts for this mission were generated on issue-7700-skill-surfaces-converge. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7700-skill-surfaces-converge unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-skill-surfaces-converge-01M7VRS0
base_commit: 4493063989eaccca10467177437126b14df7402e
created_at: '2026-11-20T06:41:39.221935+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundation
history:
- at: '2026-11-20T07:00:00Z'
  actor: claude::planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/skills/
create_intent:
- scripts/skills/build_historical_skill_digests.py
- scripts/skills/__init__.py
- src/specify_cli/skills/historical_renders.py
- src/specify_cli/skills/data/historical_skill_renders.json
- tests/specify_cli/skills/test_historical_renders.py
execution_mode: code_change
owned_files:
- scripts/skills/build_historical_skill_digests.py
- scripts/skills/__init__.py
- src/specify_cli/skills/historical_renders.py
- src/specify_cli/skills/data/historical_skill_renders.json
- tests/specify_cli/skills/test_historical_renders.py
- RELEASE_CHECKLIST.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Historical-render proof source

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Record status moves as `claude::python-pedro` (no model name).

---

## Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission skill-surfaces-converge-01M7VRS0`). Address every item before handing back.

## Objectives & Success Criteria

- A committed generator turns git history into a frozen JSON list of every skill render Spec Kitty shipped, keyed by `<skill>/<relative path>` (operator ruling Q1=A).
- A reader answers `is_historical_render(skill, relative_path, sha256)` from that JSON, memoized, failing closed.
- A test fails when any current render (raw, and for `SKILL.md` the shared and native projection) is missing, so a PR that edits a shipped skill must re-run the generator.
- `RELEASE_CHECKLIST.md` has a step: run the generator, expect no diff.

## Context & Constraints

- Spec FR-001, C-001, NFR-001; plan IC-01; research R-1, R-2; data-model `HistoricalRenderList`.
- Source roots: `src/doctrine/skills/` (historical) and `src/charter/offering/skills/` (current). Both are flattened to `<skill>/<rel>` keys.
- Projection: `specify_cli.skills.skill_frontmatter.project_skill_bytes(data, shared=..., skill_name=...)`.
- Package data ships through the existing wheel artifact glob `src/specify_cli/**/*.json`.

## Branch Strategy

Populated by finalize-tasks. Planning base and merge target: `issue-7700-skill-surfaces-converge` via the Mission branch `kitty/mission-skill-surfaces-converge-01M7VRS0`; the execution workspace is allocated per computed lane from `lanes.json`:

```bash
spec-kitty agent action implement WP01 --agent claude --mission skill-surfaces-converge-01M7VRS0
```

## Subtasks & Detailed Guidance

### Subtask T001 – Red tests

- **Purpose**: pin the reader contract and completeness before code exists.
- **File**: `tests/specify_cli/skills/test_historical_renders.py`.
- **Tests**:
  1. `test_known_historical_blob_is_proven_for_its_path`: the sha256 of the bytes of `spk-run-implement-review/SKILL.md` at `dd83e5b6f` (hard-code the digest; compute it once with `git show dd83e5b6f:src/doctrine/skills/spk-run-implement-review/SKILL.md | sha256sum`) is proven for `("spk-run-implement-review", "SKILL.md")`.
  2. `test_digest_is_not_proven_for_another_path`: same digest for `("spk-run-next", "SKILL.md")` → False.
  3. `test_every_current_render_is_listed`: for every file under the current built-in skill catalog, the raw digest is listed; for `SKILL.md` also both projections. Failure message names the generator command.
  4. `test_reader_fails_closed_on_missing_or_malformed_data` (monkeypatch the data path to a missing file and to a bad JSON): returns False, never raises.
  5. `test_generator_union_never_drops_a_digest`: unit-test the generator's pure merge function: existing ∪ new, sorted, deduped.
- Commit the tests alone (red) before T002–T004.

### Subtask T002 – Generator

- **File**: `scripts/skills/build_historical_skill_digests.py` (+ empty `scripts/skills/__init__.py` if needed to import in tests; check how `tests/ci/` imports `scripts.ci.*`).
- Steps: `git log --format=%H -- <roots>`; for each commit `git ls-tree -r <commit> -- <roots>`; map each blob path to `<skill>/<rel>`; read each distinct blob once (`git cat-file --batch`) ; digest raw bytes; for `SKILL.md` also both projections. Add the working tree's current files the same way. Load the existing JSON, union, write sorted (`json.dumps(..., sort_keys=True, indent=1)` + newline). Pure helpers: `merge_renders(existing, new)`, `digests_for(rel, data, skill)`.
- `--check` flag: exit 1 if the file would change (used by the release step).
- Keep functions under complexity 15.

### Subtask T003 – Generate and commit the JSON

- Run the generator in a full-history clone (`git fetch --unshallow` if needed). Commit the JSON in its own commit so reviewers can skim it.

### Subtask T004 – Reader

- **File**: `src/specify_cli/skills/historical_renders.py`, `__all__` declared.
- API: `is_historical_render(skill_name: str, relative_path: str, sha256: str | None) -> bool`; `historical_render_digests(skill_name, relative_path) -> frozenset[str]`.
- Load via `importlib.resources.files("specify_cli.skills.data")`; memoize with `functools.cache`; validate shape (schema_version 1, dict of str → list of 64-hex); on any error log once at debug and return empty.
- Normalize `relative_path` to POSIX.

### Subtask T005 – RELEASE_CHECKLIST step

- Add one short step near other pre-release checks: `uv run --frozen python -m scripts.skills.build_historical_skill_digests --check` in a full-history clone; a diff means a skill changed without regenerating.

## Test Strategy

```bash
uv run --frozen pytest -q tests/specify_cli/skills/test_historical_renders.py
uv run --frozen ruff check <files>; uv run --frozen ruff format --check --force-exclude <files>; uv run --frozen mypy <files>
```

## Risks & Mitigations

- Data size (~1–2k digests): fine as one JSON; reader memoizes.
- A skill edited later without regeneration: T001 test 3 fails in that PR.

## Review Guidance

- Red→green evidence for T001; the JSON is generated (spot-check two #7700 blobs); reader never raises.
