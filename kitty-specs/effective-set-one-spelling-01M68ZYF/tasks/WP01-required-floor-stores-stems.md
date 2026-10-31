---
work_package_id: WP01
title: The required-only floor stores stems
dependencies: []
requirement_refs:
- FR-001
- FR-004
- FR-005
- NFR-001
- SC-001
planning_base_branch: issue-6435-effective-set-one-spelling
merge_target_branch: issue-6435-effective-set-one-spelling
branch_strategy: Planning artifacts for this mission were generated on issue-6435-effective-set-one-spelling. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6435-effective-set-one-spelling unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - The live defect
history:
- at: '2026-10-31T12:48:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/specify_cli/cli/commands/charter/test_activate_required_key_stems_6435.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/pack_manager.py
- tests/specify_cli/cli/commands/charter/test_activate_required_key_stems_6435.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The required-only floor stores stems

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Fix the live half of #6435: `ActiveCharterManager.activate` materialises an absent
**required-only** activation key (`skill`) from the raw org `required_<kind>`
**declared ids**, so the written activation list holds a declared id beside a
file stem. Route that floor through the identity authority and prove it through
the production CLI.

Red-first. The test in T001 must fail on the pre-fix code for the right reason
(the list contains `acme-skill-id`), not because the fixture is wrong.

## Context

- Issue: spec-kitty/spec-kitty#6435 — "Charter effective-set union mixes declared IDs and activation stems".
- The union itself is already stem-only (`a8dd1812a6`, #6527 local slice); see
  `kitty-specs/effective-set-one-spelling-01M68ZYF/research.md` (D1-D4) for the
  grounding evidence and the exact CLI reproduction.
- Contract: every activation writer stores the artifact's **activation stem** (the
  file name) — `IdentityIndex.stored_spelling`; a declared id whose file name
  another layer uses for a different id raises `ActivationIdCollisionError`
  (Decision `file_name_collision`).
- `charter.activation.org_charter.org_required_stems(repo_root, kind_plural, warnings)`
  is the existing authority for "org-required ids, as activation stems": it maps
  declared ids through `IdentityIndex.stored_spelling`, so it both raises the
  collision refusal and returns stems. `_narrow_inputs` (the `--only` path) already
  uses it; the plain `activate` path does not.

### The code to change

`src/charter/activation/pack_manager.py`:

```python
def _refuse_required_collisions(repo_root: Path, kind: str) -> None:      # ~line 503
    ...
    org_required_stems(repo_root, ArtifactKind.from_operator_token(kind).plural, [])

def _preservation_ids(...):                                              # ~line 518
    if data.get(yaml_key) is not None:
        return _Preservation([], [], True)
    _refuse_required_collisions(repo_root, kind)
    if when_absent != "all":
        in_force = PackContext.from_config(repo_root).allow_for(ArtifactKind.from_plural(...))
        return _Preservation(sorted(str(item) for item in in_force or ()), [], True)
```

`PackContext.allow_for(...)` for an absent required-only key is
`frozenset(read_org_required_ids(repo_root, kind))` — declared ids, raw.

### The fix

In the `when_absent != "all"` branch, compute the floor once through
`org_required_stems(repo_root, kind.plural, [])` and return those stems. That one
call also performs the collision refusal, so `_refuse_required_collisions` can be
deleted (it has exactly one caller, this branch).

Rules:

- Pass an empty warnings list (`[]`), exactly as `_refuse_required_collisions`
  does today: the user-visible `activate` output must not gain warnings
  (existing tests assert the exact warning set).
- Do not change the `_Preservation` shape, the `in_force=True` flag, or the
  `when_absent == "all"` branch below it.
- Delete `_refuse_required_collisions` only if it becomes unreferenced; keep the
  module import-clean (`ruff`), and update the docstrings that name it.
- No new artifact scan and no extra `IdentityIndex.build` on this path
  (NFR-001): the call replaces one that already ran.

## Branch Strategy

- Planning / base branch: `issue-6435-effective-set-one-spelling`
- Final merge target: `issue-6435-effective-set-one-spelling`
- Execution worktrees are allocated per computed lane from `lanes.json`; do not
  hand-build a worktree path.

## Subtasks

### T001 — red test (production entry point)

Create `tests/specify_cli/cli/commands/charter/test_activate_required_key_stems_6435.py`.

Fixture: a git-initialised temp project whose org pack is declared in
`.kittify/config.yaml` (`charter_packs.org.packs`), holding

```
packs/acme/skills/acme-skill-file.skill.yaml   -> id: acme-skill-id
packs/acme/skills/other-skill-file.skill.yaml  -> id: other-skill-id
packs/acme/org-charter.yaml                    -> required_skills: [acme-skill-id]
```

and **no** `activated_skills` key. Drive the CLI exactly as an operator does:

```python
runner.invoke(charter_app, ["activate", "--repo-root", str(root), "--no-compile", "skill", "other-skill-file"])
```

Assert the written `activated_skills` list equals, as a set,
`{"acme-skill-file", "other-skill-file"}` and that `"acme-skill-id"` is not in it.
Include the positive control on the same fixture: the required artifact **is**
materialised (the list is non-empty and holds its stem), so the assertion cannot
pass by materialising nothing.

Skill file shape used by the Fixture in `test_stored_spelling_6527.py`:
`schema_version: "1.0"\nid: <id>\nname: <n>\nsummary: <s>\nbody: <b>\n`.

### T002 — collision ratchet

On the same fixture family, add the `file_name_collision` case: a second org layer
that ships a file with the same name as the required artifact's stem but a
different declared id, so the required id has no single stem. Assert `activate`
exits non-zero with `ActivationIdCollisionError` in the output and that the
activation list is unchanged (nothing written). Keep the non-colliding
materialisation assertion in T001 as this case's positive control.

### T003 — the fix

As described in **The fix** above.

### T004 — targeted validation

```
uv run --frozen pytest tests/specify_cli/cli/commands/charter/test_activate_required_key_stems_6435.py -q
uv run --frozen pytest tests/charter/activation/test_stored_spelling_6527.py tests/specify_cli/cli/commands/charter/test_activate_only_6408.py -q
uv run --frozen pytest tests/charter/activation/test_pack_manager.py -q   # if present
uv run --frozen ruff check src/charter/activation/pack_manager.py tests/specify_cli/cli/commands/charter/test_activate_required_key_stems_6435.py
uv run --frozen mypy src/charter/activation/pack_manager.py
```

Plus the specific architectural gates for the touched packages that exist (name
them; do not run the whole `tests/architectural/` directory —
`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Definition of Done

- T001 red before T003, green after; the failure message names `acme-skill-id`.
- T002 pins the collision refusal and writes nothing.
- No user-visible warning change; no new scan (NFR-001).
- The touched suites and the named architectural gates pass; `ruff` and `mypy`
  clean on the touched files.
- PR-ready diff: one test module (new), one source file (small diff).

## Risks

- Required-floor consumers in `pack_context` are read-only readers of the config;
  they accept either spelling. If a test asserts a declared id is written, it is
  masking this defect — re-pin it to the stem and say so in the PR.

## Reviewer guidance

- Confirm the test drives `charter activate` (not `_preservation_ids` directly).
- Confirm the collision case writes nothing.
- Confirm no `PackContext.allow_for` braces remain on the required branch and that
  the `"all"` branch is untouched.
