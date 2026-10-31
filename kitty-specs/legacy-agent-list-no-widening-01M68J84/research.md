# Research — legacy agent list no widening (#6501)

## Decisions

1. **Narrow the read; do not refuse it.** `get_agent_dirs_for_project()` is called by 27 upgrade
   migrations, `doctor`'s slash-command audit, shim generation and `.gitignore` repair. A raise on
   the "no stated list" branch would abort `spec-kitty upgrade` mid-chain for exactly the population
   this issue is about (projects whose config predates agent selection), and no new migration could
   record a list first because earlier migrations in the chain call the helper. The ADR that created
   the fallback (`docs/adr/1.x/2026-01-23-6-config-driven-agent-management.md`, Alternatives/Risks)
   requires legacy projects not to break on upgrade. Evidence: `grep -rn get_agent_dirs_for_project`
   → 94 references, 27 migration modules.
2. **The narrowed value is the observed set**: the `AGENT_DIRS` entries whose project surface
   directory already exists. It cannot invent a surface the project does not have, and it keeps
   stale legacy command files repairable (the reason the fallback existed).
3. **The probe is `<agent_root>/<subdir>`**, not the bare root. `.github/` is a common CI directory in
   projects that never chose Copilot; its managed surface is `.github/prompts`.
4. **The read warns once per call** naming `.kittify/config.yaml`, `agents.available`, the remedy and
   the observed agents. `logger.warning`, never stdout (the CLI owns output), never a raise.
5. **`ignored_agent_keys` stays broad.** Over-ignoring generated files is harmless (it only keeps
   untracked files out of `git status`); over-acting rewrites user files. The asymmetry is deliberate
   and is recorded in that function's docstring.

## Evidence

- `src/specify_cli/agent_utils/directories.py:84-86` (fixed shape at `0356bbdcb7`, #6494) —
  `return [] if config.explicit_agent_list else list(AGENT_DIRS)`.
- `src/specify_cli/core/agent_config.py` — `explicit_agent_list` is `False` for a missing file and
  for a config whose `agents`/`tools` section has no `available` key; `AgentConfigError` already
  fails closed for unreadable/invalid configs (#6494).
- Reproduction on `main` `35318ef51c`: a temp project with `.kittify/` and no `config.yaml` returns
  12 dirs; one with `vcs: {type: git}` returns 12; one with `agents: {auto_commit: true}` returns 12.
- Existing tests that pin the widening: `tests/agent/test_agent_config_migration.py`
  (`test_fallback_to_all_agents_when_no_config`,
  `test_agents_section_without_available_key_keeps_legacy_fallback`).
- Documentation that promises the widening: `docs/api/configuration.md:424`
  ("Projects without `agents.available` field default to the full slash-command agent set").

## Open questions (resolved before implementation)

- *Should a project with no agent surface at all return `[]` or fall back to the registry?* `[]`. An
  empty observation is the honest answer (the ADR's "honor deletions"), and the warning names the
  remedy.
- *Does `agent config sync --remove-orphaned` need changing?* No. It already refuses orphan removal
  for a no-list config with its own warning (`src/specify_cli/cli/commands/agent/config.py:796`); it
  never widened through the helper.
