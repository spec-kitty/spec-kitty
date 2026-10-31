---
work_package_id: WP01
title: Legacy agent list resolves to the observed set
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6501-legacy-agent-list-no-widening
merge_target_branch: issue-6501-legacy-agent-list-no-widening
branch_strategy: Planning artifacts for this mission were generated on issue-6501-legacy-agent-list-no-widening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6501-legacy-agent-list-no-widening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-legacy-agent-list-no-widening-01M68J84
base_commit: d396a8df5319f9fb09fec3e3f23ffc8936783bf7
created_at: '2026-10-31T08:51:53.255484+00:00'
subtasks:
- T001
- T002
- T003
- T004
history:
- at: '2026-10-31T08:55:00Z'
  actor: claude
  action: created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/agent_utils/
create_intent:
- tests/agent/test_agent_config_migration.py
execution_mode: code_change
owned_files:
- src/specify_cli/agent_utils/directories.py
- tests/agent/test_agent_config_migration.py
role: implementer
tags: []
tracker_refs:
- '6501'
---

# WP01 — Legacy agent list resolves to the observed set

## ⚡ Do This First: Load Agent Profile

Load **`python-pedro`** (implementer) with the `/spk-charter-profile-load` skill before reading
anything else. The review runs under `reviewer-renata`.

## Objective

`get_agent_dirs_for_project()` returns the whole `AGENT_DIRS` registry when `.kittify/config.yaml`
states no `available` list. Narrow that branch to the agents whose project surface already exists,
and make the read say what it did. Spec: FR-001..FR-004, C-001..C-003.

Current code (`src/specify_cli/agent_utils/directories.py`):

```python
config = load_agent_config(project_path)
if not config.available:
    return [] if config.explicit_agent_list else list(AGENT_DIRS)
return [(root, subdir) for root, subdir in AGENT_DIRS if AGENT_DIR_TO_KEY.get(root) in config.available]
```

`AGENT_DIRS` entries are `(agent_root, subdir)`; the project surface is
`project_path / agent_root / subdir` (`.claude/commands`, `.github/prompts`, ...).

## Branch Strategy

Planning base and merge target: `issue-6501-legacy-agent-list-no-widening`. Worktree per the lane in
`lanes.json`.

```bash
spec-kitty agent action implement WP01 --agent claude --mission legacy-agent-list-no-widening-01M68J84
```

## Subtasks

### T001 — Red-first: the no-config-file shape

**File**: `tests/agent/test_agent_config_migration.py`.

Replace `test_fallback_to_all_agents_when_no_config` with a test that builds `.kittify/` (no
`config.yaml`), creates one agent surface (`.claude/commands/`), and asserts
`get_agent_dirs_for_project(tmp_path) == [(".claude", "commands")]`. Add the reverse control on the
same fixture: create `.cursor/commands/` too and assert both are returned, so the assertion cannot
pass by returning a constant. It must fail on the current code (12 entries) — run it and paste the
failure into the WP log before touching `src/`.

### T002 — Red-first: the no-agents-section shape

**File**: `tests/agent/test_agent_config_migration.py`.

Replace `test_agents_section_without_available_key_keeps_legacy_fallback`: `config.yaml` holding
`vcs:\n  type: git\n` (no `agents` section) and a `.opencode/command/` directory returns exactly
`[(".opencode", "command")]`. Also cover the third shape, an `agents:` section with only
`auto_commit` and a `.gemini/commands/` directory → `[(".gemini", "commands")]`. Both must be red on
`main` for the same reason as T001.

### T003 — The fix

**File**: `src/specify_cli/agent_utils/directories.py`.

- Keep the stated-list branch exactly as it is (`[]` for explicit empty, filter by
  `config.available` otherwise) — C-003.
- For the no-list branch: return the `AGENT_DIRS` entries whose `project_path / root / subdir`
  `is_dir()`. Empty when nothing is present (FR-003). No `$HOME`, no global command dir, no writes
  (NFR-001).
- Log `logger.warning` once per read, one line, naming `.kittify/config.yaml`, the `agents.available`
  key, the remedy (`spec-kitty agent config` — reuse the wording style of `CONFIG_ERROR_REMEDY` in
  `core/agent_config.py`) and the observed agents / "none found" (FR-002, NFR-002). Do not raise
  (C-001).
- Update the docstring's bullet list: the no-list case is the observed set, not "every agent", and
  say why (legacy projects must not gain surfaces they never had; the ADR's upgrade requirement).
- Reuse `AGENT_DIRS` / `AGENT_DIR_TO_KEY`; do not add a new registry (C-002).

### T004 — Green, plus the consumer proof

- `uv run pytest tests/agent/test_agent_config_migration.py tests/agent/test_agent_config_unit.py -q`.
- `uv run pytest tests/cli/commands/test_doctor_slash_commands.py tests/upgrade -q -k "agent or doctor"`
  — the doctor audit and the migration suite read this helper; fix any expectation that was pinned to
  the widening, never by skipping the test.
- Prove the user-visible outcome once by hand: a temp project with only `.claude/commands/` and no
  `agents` section yields one entry from the helper, and `doctor`'s slash-command audit reports
  nothing for the other 11 agents.
