# Research — legacy doctor audits must not claim health over nothing

**Mission**: legacy-doctor-empty-audit-truthful-01M68WJ9 · **Issue**: #6891
**Grounded on**: `origin/main` at `6f73b2a98e`

## 1. Grounding: does the issue still reproduce, and was it superseded?

It reproduces, unmodified, on current `main`.

**Fixture** (the issue's own reproduction, plus the tool folder a real legacy
project has): `.kittify/config.yaml` containing only

```yaml
agents:
  auto_commit: true
```

a hand-written `.claude/commands/spec-kitty.<command>.md` tree (14 files, stale
bodies), no `.agents/skills` manifest.

```
$ spec-kitty doctor skills
Command Skills: all manifest entries healthy (0 file(s))     # exit 0
$ spec-kitty doctor tool-surfaces
Tool Surfaces: all surfaces healthy (0 checked)              # exit 0
$ spec-kitty doctor command-files
Command Files — 112 issue(s) found                           # exit 1
```

Transcripts: `research/repro-1.txt` (bare legacy, no tool folder),
`research/repro-2.txt` (the realistic shape above — the false green next to a
sibling command that reports real problems), `research/repro-3.txt` (legacy with
on-disk leftovers: the config-independent scans still fire),
`research/repro-4.txt` (stated-list positive control),
`research/repro-5.txt` (stated-empty shape, #6894's).

**Not superseded.** `git log -S "all manifest entries healthy"` shows no
change since the extraction into `_command_surface_doctor.py`; #6501 established
the every-agent fallback but did not touch these summaries; #6493 (stated-empty,
in review as PR #6894, **OPEN, unmerged**) defers this legacy shape here in its
own `## Deferred` ("#6891 — legacy no-list projects still get a vacuous healthy
line"). No ADR or changelog entry covers it.

## 2. Why the checks silently pass

Both audits derive their examined set from `AgentConfig.available`, which is
`[]` for a config with no `agents.available` key (`explicit_agent_list=False`,
the #6501 every-agent fallback).

| Command | Examined set | Summary when the set is empty |
| --- | --- | --- |
| `doctor skills` | `configured_agents = sorted(set(config.available) & SUPPORTED_AGENTS)` → `[]`; manifest entries → `0`; slash commands → nothing | `all manifest entries healthy (0 file(s))` — `_print_command_skill_report`, gated only on `payload["ok"]` |
| `doctor tool-surfaces` | `_configured_tool_keys` → `[]` → `run_tool_surfaces(..., configured_tools=[])` → `report.summary.surfaces == 0` | `all surfaces healthy (0 checked)` — `_print_tool_surface_human`, gated only on `report.ok and not report.findings` |

The audits are structurally right; the *summary* conflates "examined and
healthy" with "examined nothing". `ok` is `True` in both cases because no check
produced a finding — over an empty set, trivially.

Two things are **not** vacuous and must stay working (they are already
config-independent):

- `command_installer.verify()` scans the manifest, **and** on-disk
  `.agents/skills/spec-kitty-<command>/` (orphans/collisions) and legacy dotted
  folders — regardless of `config.available`. `research/repro-3.txt` shows a
  collision found in the legacy shape today.
- `_tool_folder_findings` reports `no_tool_folder` for a legacy project with no
  tool folder at all (`research/repro-1.txt`), which is why `doctor skills`
  exits 1 there and `doctor tool-surfaces` still exits 0.

## 3. What "nothing examined" means, precisely

- **skills**: report is `ok` (no drift/gaps/orphans/stale/unsafe/legacy/
  collisions/uninstalled/vibe) **and** `len(manifest.entries) == 0`. Any on-disk
  leftover would have set `ok=False`, so `ok && entries == 0` ⇔ nothing was
  examined.
- **tool-surfaces**: `report.summary.surfaces == 0` (and `report.ok`, no
  findings).

Empty for two different reasons, which must be named differently:

- **legacy** (`explicit_agent_list=False`): no agent list is stated, every agent
  is available, so the CLI cannot tell which surfaces to verify. **This
  Mission.**
- **stated empty** (`explicit_agent_list=True`, `available == []`): the project
  states the CLI manages no agents. **#6493 / PR #6894** — not this Mission.

## 4. Survey of the code the change touches

`src/specify_cli/cli/commands/_command_surface_doctor.py`

- `_load_command_skill_state` — the only place that loads `AgentConfig` for
  `doctor skills`; already returns six values, one of which
  (`configured_agents`) collapses both empty shapes to `[]`. It must carry the
  distinction (a `stated_agent_list` flag read off the already-loaded config —
  no second parse).
- `_command_skill_payload` / `_print_command_skill_report` — payload builds
  `ok`; the report prints the health line on `ok` alone. The fix belongs in the
  report, and the payload's human-only key is where the reason rides
  (`_HUMAN_ONLY_KEYS` already strips such keys from `--json`).
- `_configured_tool_keys` / `_configured_tool_keys_or_exit` — the analogous
  config read for `doctor tool-surfaces`; `run_tool_surfaces` receives the
  list, and `_print_tool_surface_human` prints the health line.
- `_print_tool_surface_human` — the tool-surface health line. JSON comes from
  `outcome.to_json()`, which this Mission does not touch.

Other callers of the same shapes (must not change): `doctor command-files`
(its own config read, C-003), `_tool_folder_findings`, the slash-command
section (`_print_slash_command_report` prints nothing for zero configured
agents — silent, not a false claim).

Single source of truth for "the project states no agent list":
`AgentConfig.explicit_agent_list` (already the reader used by
`save_agent_config`, `ignore_entries`, `directories`). #6894 adds
`no_cli_managed_agents(config)` for the stated-empty side; this Mission must not
add a second predicate for the legacy side beyond reading
`explicit_agent_list`.

## 5. Overlap with PR #6894 (open)

#6894 touches `_print_command_skill_report`, `_print_tool_surface_human`,
`run_command_files` and adds the config parameter those functions need. This
Mission touches the two summary functions and the state tuple. Both changes are
in the same small area; the second to merge resolves a textual conflict. To keep
that conflict small:

- reuse the config the command already loads (no new loader),
- keep `--json` key sets identical (the sibling PR's stated intent too),
- do not restate or re-decide the stated-empty wording: if #6894 has landed at
  rebase time, call its `no_cli_managed_agents` path instead of duplicating it.

## 6. Test surface

- `tests/specify_cli/cli/commands/test_doctor_skills.py` — the existing
  `CliRunner` harness for `doctor skills` (`_write_config`, `_invoke`,
  `_payload`); its `_write_config` always states a list, which is exactly the
  gap: no test has ever run the commands on a **no-list** config.
- `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py` — pins the
  subcommand set, flags, help bodies and exit-code contract (the help text is
  not changing).
- No test asserts either summary string today (`grep "all surfaces healthy"`
  over `tests/` returns nothing), which is how the false green survived.
