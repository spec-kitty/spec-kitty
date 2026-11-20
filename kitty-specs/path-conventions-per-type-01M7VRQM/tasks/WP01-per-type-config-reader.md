---
work_package_id: WP01
title: Per-type configuration reader
dependencies: []
requirement_refs:
- FR-001
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-005
planning_base_branch: issue-7566-path-conventions-per-type
merge_target_branch: issue-7566-path-conventions-per-type
branch_strategy: Planning artifacts for this mission were generated on issue-7566-path-conventions-per-type. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7566-path-conventions-per-type unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-path-conventions-per-type-01M7VRQM
base_commit: 81d080e15eb54a3dd19eef12944f76f7ba5ffbde
created_at: '2026-11-20T06:53:23.293258+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundation
history:
- at: '2026-11-20T07:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/config/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/config/path_conventions.py
- tests/specify_cli/config/test_path_conventions_reader.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Per-type configuration reader

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Record status moves as `claude::python-pedro` (no model name).

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission path-conventions-per-type-01M7VRQM`).
- Address all feedback before the work is complete.

## Markdown Formatting

Wrap HTML/XML tags in backticks; use language identifiers in code blocks.

## Objectives & Success Criteria

- `load_project_path_conventions(repo_root)` accepts a mapping value keyed by a mission-type id (a **per-type section**) beside the existing flat string values.
- Every malformed per-type shape raises `PathConventionsConfigError` (FR-003, FR-004).
- The flat form is unchanged: every existing test in `tests/specify_cli/config/test_path_conventions_reader.py` passes **unmodified** (FR-005, NFR-002).
- The mission-type roster is consulted only when at least one per-type section exists (NFR-001).

## Context & Constraints

- Spec: `kitty-specs/path-conventions-per-type-01M7VRQM/spec.md` (FR-001, FR-003, FR-004, FR-005, NFR-001, NFR-002, C-005).
- Design: `research.md` R-1 and R-2; `contracts/config-schema.md`; `data-model.md`.
- Current reader: `src/specify_cli/config/path_conventions.py`. Keep `ARTIFACT_ROUTED_KEYS`, `_SECTION` and the existing error wording for the flat form byte-identical.
- Operator ruling Q3: valid ids are the **layered roster** (built-in → org → project). Reuse `specify_cli.cli.commands.charter.mission_type.resolve_layered_roster(repo_root)` through a **lazy** import (no third copy of the `(mission_types_dirs, PackContext)` construction, DIRECTIVE_044).
- C-005: read only the `project.path_conventions` subkey.
- Complexity ≤ 15 per function (ruff C901 / Sonar S3776). Extract helpers.

## Branch Strategy

- **Planning base branch**: `issue-7566-path-conventions-per-type` (planning artifacts on `kitty/mission-path-conventions-per-type-01M7VRQM`)
- **Merge target branch**: `issue-7566-path-conventions-per-type`
- Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty agent action implement WP01 --agent claude --mission path-conventions-per-type-01M7VRQM`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first reader tests

**Purpose**: pin every new behaviour before the code exists (ATDD-first).

Add tests to `tests/specify_cli/config/test_path_conventions_reader.py` (append; do not edit the existing tests). Use the existing `_write_config` style helper in that file. Inject the roster through the new keyword `mission_type_ids=lambda: frozenset({"software-dev", "documentation", "plan", "research", "docs-audit"})` so the tests never touch packs.

Cases (each its own test):
1. `{"software-dev": {"workspace": "packs/"}}` → `result == {}` (no flat keys) and `result.per_type == {"software-dev": {"workspace": "packs/"}}`.
2. Flat plus per-type: `{"workspace": "apps/", "software-dev": {"workspace": "packs/"}}` → `result.for_mission_type("software-dev") == {"workspace": "packs/"}`, `result.for_mission_type("documentation") == {"workspace": "apps/"}`, `result.for_mission_type(None) == {"workspace": "apps/"}`.
3. Per-type merges key by key: flat `tests: t/` and per-type `workspace: packs/` → software-dev gets both.
4. An org id in the injected roster (`docs-audit`) is accepted.
5. Unknown type id `{"softwre-dev": {"workspace": "x/"}}` → raises, and the message contains `'softwre-dev'` and a known id.
6. Unknown key in a section `{"software-dev": {"workspce": "x/"}}` → raises, naming `software-dev.workspce`.
7. Non-string value in a section (`1`, `None`, a list) → raises.
8. Blank value in a section (`""`, `"   "`) → raises.
9. Absolute value in a section → raises. A `..` value → raises.
10. `deliverables` inside a section → `pytest.warns(UserWarning)` and the key is absent from `per_type["software-dev"]`.
11. A section value that is a list or a scalar under a non-path key (`{"software-dev": ["src/"]}`) → raises.
12. Roster is not consulted for a flat-only config: pass `mission_type_ids=` a callable that raises `AssertionError`; flat-only config loads fine.
13. A roster callable that raises (e.g. `RuntimeError("bad pack")`) while a per-type section exists → `PathConventionsConfigError` whose message contains `bad pack`.
14. Whitespace trimming applies inside sections (`"  packs/ "` → `"packs/"`).
15. Default roster (no injection): monkeypatch `specify_cli.cli.commands.charter.mission_type.resolve_layered_roster` to return `{"software-dev": object()}` and check a `software-dev` section loads. This proves the production path uses the layered seam.

Run them and confirm they fail (red) for the right reason before writing code.

### Subtask T002 – `ProjectPathConventions` value object

```python
class ProjectPathConventions(dict[str, str]):
    """Flat overrides (the mapping content) plus per-mission-type sections."""

    def __init__(self, flat: Mapping[str, str] | None = None, per_type: Mapping[str, Mapping[str, str]] | None = None) -> None: ...
    @property
    def per_type(self) -> Mapping[str, Mapping[str, str]]: ...  # read-only view (MappingProxyType of copies)
    def for_mission_type(self, mission_type: str | None) -> dict[str, str]:
        """``{**flat, **per_type.get(mission_type, {})}``; flat only when ``mission_type`` is None/unknown."""
```

- A dict subclass, so `== {...}` comparisons of the flat content hold (R-1).
- Add `ProjectPathConventions` to `__all__`; keep `load_project_path_conventions` exported. The function's return annotation becomes `ProjectPathConventions`.

### Subtask T003 – Parse and validate per-type sections

Refactor the loop into helpers so the complexity stays low:
- `_validated_value(label: str, value: object) -> str` holds the existing string, blank, absolute and `..` checks. `label` is `key` for flat and `f"{type_id}.{key}"` for a section. Keep the flat error messages byte-identical: `f"{_SECTION}.{label} must ..."`.
- `_validated_section(type_id: str, section: object) -> dict[str, str]`: the section must be a `dict` (else raise `f"{_SECTION}.{type_id} must be a mapping of path-convention key to directory, got {type}"`). Inner keys must be in `VALID_PATH_KEYS` (else raise naming `type_id.key` and the known keys). `deliverables` → warn (same wording, with `type_id.` prefixed in the label) and skip.
- Dispatch per top-level entry: if `isinstance(value, dict)` → per-type candidate (collect it; validate its id afterwards). Otherwise the existing flat path (an unknown key keeps today's "Unknown path-convention key" error, so `{"softwre-dev": "x/"}` still reads as a typo'd path key).

### Subtask T004 – Roster validation

- `load_project_path_conventions(repo_root, *, mission_type_ids: Callable[[], Collection[str]] | None = None)`.
- Only when at least one per-type candidate exists, call the roster provider once. Default provider: lazily import `resolve_layered_roster` from `specify_cli.cli.commands.charter.mission_type` and return `frozenset(roster)` for `repo_root`.
- Wrap the provider call: on any `Exception` (not `BaseException`), raise `PathConventionsConfigError(f"{_SECTION}: could not read the mission-type roster to validate per-type sections: {exc}")` from it.
- An unknown id raises `f"Unknown mission type {type_id!r} in {_SECTION}. Known mission types: {sorted(ids)}."`.
- Update the module docstring: describe the per-type form, the precedence (per-type > flat > default; the merge itself happens at the seam) and the roster rule.

### Subtask T005 – Verify

```bash
uv run --frozen pytest -q tests/specify_cli/config/test_path_conventions_reader.py tests/specify_cli/acceptance/test_path_conventions_all_types.py tests/specify_cli/acceptance/test_acceptance_support.py
uv run --frozen ruff check src/specify_cli/config/path_conventions.py tests/specify_cli/config/test_path_conventions_reader.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/config/path_conventions.py tests/specify_cli/config/test_path_conventions_reader.py
uv run --frozen mypy src/specify_cli/config/path_conventions.py
```

## Test Strategy

Red-first unit tests through the public reader. The existing tests are the FR-005 positive control and must stay unedited.

## Risks & Mitigations

- **A dict subclass surprises a consumer that copies with `dict(x)`**: `dict(x)` keeps only the flat part, which is the intended behaviour for the existing caller until WP02 switches it to `for_mission_type`.
- **An import cycle through the CLI module**: the import is lazy, inside the default provider only.

## Review Guidance

- Flat error strings are byte-identical (diff the messages).
- No roster read on a flat-only or empty config (test 12).
- No test in the existing file was edited.

## Progress & Status

Track with `spec-kitty agent tasks mark-status T001 ... --status done --mission path-conventions-per-type-01M7VRQM`.
