---
work_package_id: WP01
title: Mission-scoped dirt predicate
dependencies: []
requirement_refs:
- FR-001
- NFR-001
- NFR-002
- C-004
planning_base_branch: fix/7545-cli-owns-its-commits
merge_target_branch: fix/7545-cli-owns-its-commits
branch_strategy: Planning artifacts for this mission were generated on fix/7545-cli-owns-its-commits. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7545-cli-owns-its-commits unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Enabler
history:
- at: '2026-11-11T16:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/coordination/mission_dirt.py
create_intent:
- src/specify_cli/coordination/mission_dirt.py
- tests/coordination/test_mission_dirt.py
execution_mode: code_change
owned_files:
- src/specify_cli/coordination/mission_dirt.py
- src/specify_cli/coordination/coherence.py
- tests/coordination/test_mission_dirt.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Mission-scoped dirt predicate

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter
(`implementer-ivan`, role `implementer`) before reading the rest of this prompt.

---

## Objectives & Success Criteria

- A new module `src/specify_cli/coordination/mission_dirt.py` answers "whose dirt is this
  path?" for a gate: this Mission's own (`OWN`), another Mission's (`OTHER_MISSION`), or
  outside every Mission (`OUTSIDE`). See `data-model.md`.
- `coherence._is_other_mission_path` is rebuilt on it and returns exactly what it returned
  before, for every input (the destructive guards depend on it).
- No git call, no file-system read, no filename list (C-004, NFR-001).

## Context & Constraints

- Grounding: `research/code-grounding.md` §2 and §4. In particular, the private rule in
  `coherence.py:551` returns `False` for a collapsed `kitty-specs/<other>/` entry
  (`len(after) < 2`). That is correct for the destructive guard, which lists with
  `--untracked-files=all`, but wrong for a gate that lists in the repository-default mode.
  The new classification treats the collapsed entry as that Mission's. The coherence wrapper
  keeps its old answer.
- `test_exemption_registry_ratchet.py` scans `coherence.py` for module-level frozensets,
  tuples and regexes of filenames. Add none; the predicate reads path segments.
- `__all__` must list the public names (repository convention for new modules).

## Branch Strategy

- **Strategy**: single_branch, direct in the repository root checkout
- **Planning base branch**: fix/7545-cli-owns-its-commits
- **Merge target branch**: fix/7545-cli-owns-its-commits

## Subtasks & Detailed Guidance

### Subtask T001 – `mission_dirt` module

- **Purpose**: the single owner of Mission-scoped dirt classification.
- **Steps**:
  1. `class DirtScope(StrEnum)`: `OWN`, `OTHER_MISSION`, `OUTSIDE`.
  2. `def classify_dirt(path: str | PurePath, *, own_dir_names: Collection[str]) -> DirtScope`:
     normalise with `kernel.paths.to_posix`; split into parts; find the `kitty-specs` segment
     (constant `KITTY_SPECS_DIR` from `specify_cli.core.constants`, where `coherence` takes it).
     If it is absent, return `OUTSIDE`. If nothing follows it (`kitty-specs/`), return
     `OUTSIDE`, because a collapsed parent may hide this Mission's own files and must stay
     visible. Otherwise the next segment is the Mission directory name: `OWN` if it is in
     `own_dir_names`, else `OTHER_MISSION`. Paths like `kitty-specs/README.md`, a single file
     directly under `kitty-specs/`, are `OUTSIDE`. Distinguish them by trailing slash or by
     depth: a file has exactly one segment after `kitty-specs` and no trailing `/`.
  3. Derived status views: `.kittify/derived/<mission>/...` belong to that Mission.
     `coherence._derived_view_mission_dir` already parses this; it is a regex in `coherence`.
     Import it function-locally only if it costs no layering. Otherwise keep derived views
     `OUTSIDE` here and leave the derived leg inside the coherence wrapper (T003).
  4. `@dataclass(frozen=True) class MissionDirt: own, other_mission, outside: tuple[str, ...]`.
  5. `def partition_mission_dirt(paths: Iterable[str], *, own_dir_names: Collection[str]) -> MissionDirt`,
     which keeps the input order.
- **Files**: `src/specify_cli/coordination/mission_dirt.py` (new, about 90 lines).

### Subtask T002 – Unit tests

- **Purpose**: pin every scope (FR-001 is `no-op passable: no`).
- **Cases** in `tests/coordination/test_mission_dirt.py` (mark `fast`):
  - own file, own collapsed dir `kitty-specs/m/`, alias dir name;
  - other Mission's file and its collapsed dir `kitty-specs/other/`;
  - `src/a.py`, `.kittify/evidence/01ABC/x`, `kitty-ops/lifecycle/x.json` → OUTSIDE;
  - `kitty-specs/`, `kitty-specs/README.md` → OUTSIDE;
  - a Windows-style `kitty-specs\\other\\a.md` → OTHER_MISSION;
  - `partition_mission_dirt` keeps order and splits correctly.

### Subtask T003 – Rebuild `_is_other_mission_path`

- **Purpose**: one rule, two consumers (single canonical authority).
- **Steps**: inside `coherence._is_other_mission_path`, keep the derived-view leg. For the
  `kitty-specs` leg, call `classify_dirt(...) is DirtScope.OTHER_MISSION`, but keep the
  `len(after) < 2 → False` behaviour for collapsed entries. The simplest faithful form is to
  return `False` when the path is a bare Mission directory entry, then delegate. Add a
  parametrised test to `test_mission_dirt.py` that asserts the coherence wrapper's answers for
  the old cases, including the collapsed entry staying `False`.
- **Files**: `src/specify_cli/coordination/coherence.py`.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/coordination/test_mission_dirt.py tests/coordination/ -q
.venv/bin/python -m pytest tests/architectural/test_exemption_registry_ratchet.py tests/architectural/test_layer_rules.py -q
.venv/bin/ruff check src/specify_cli/coordination/mission_dirt.py src/specify_cli/coordination/coherence.py
.venv/bin/mypy src/specify_cli/coordination/mission_dirt.py
```

## Risks & Mitigations

- Changing `_is_other_mission_path` semantics would change what the destructive guards may
  discard. Mitigation: the T003 pin test, plus `tests/coordination/` green.

## Review Guidance

- Verify there is no filename list and no git or file-system I/O in the new module.
- Verify the wrapper's answers are unchanged, including the collapsed entry.
