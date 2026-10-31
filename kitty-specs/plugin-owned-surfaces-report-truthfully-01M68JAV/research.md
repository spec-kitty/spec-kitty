# Discovery: plugin-owned surface reports (#6493)

Recorded 2026-10-31 on `origin/main` @ `35318ef51c` (clone `/home/exedev/work/sk-6493`),
CLI `spec-kitty-cli 4.0.0rc8` installed at `~/.local/bin/spec-kitty`.

## Evidence — the reported symptom set, reproduced

Fixture: a git repo with `.kittify/config.yaml` containing
`agents: {available: [], auto_commit: true}` — the stated-empty list #6494 gave
the meaning "no Spec Kitty-managed agents". Transcripts are in
`research/repro-1.txt` … `research/repro-6.txt`.

| # | Command | Observed | Exit |
| --- | --- | --- | --- |
| 1 | `spec-kitty agent config list` | `No agents configured.` + `Run 'spec-kitty init' or use 'spec-kitty agent config add' to add agents.` | 0 |
| 2 | `spec-kitty init --non-interactive` | Already-Initialized panel claiming `Agent skill surfaces were verified on this re-run: missing per-agent skill roots were restored.` | 0 |
| 3 | `spec-kitty init --ai claude --non-interactive` | `Initialization incomplete: Requested agents are not configured. Run: spec-kitty agent config add claude` | 1 |
| 4 | `spec-kitty doctor skills` | `Command Skills: all manifest entries healthy (0 file(s))` | 0 |
| 5 | `spec-kitty doctor tool-surfaces` | `Tool Surfaces: all surfaces healthy (0 checked)` | 0 |
| 6 | `spec-kitty doctor command-files` | `Command Files: all files healthy` | 0 |

`spec-kitty doctor skills --json` in the same fixture returns
`configured_agents: []` with `ok: true` and no other key naming the state, so the
machine-readable record is already truthful; only the human lines are not.

## Evidence — the issue's two halves are two shapes

The issue body cites `init`'s skill check at `init.py:242-266`
(`_check_initialized_command_skills`), which only raises when the *stated* list
contains a command-skill agent. On the stated-empty fixture it returns `[]`
without raising, so repro #3's exit 1 comes from `_validated_agent_selection`
(`init.py:207-214`), not from the skill check. So:

- **Shape A — stated-empty list** (`available: []`): reproducible today as #1, #3, #4, #5, #6.
- **Shape B — listed agent, CLI skills absent** (`available: [claude]`, no
  `.claude/skills/spec-kitty.*`): the "Configured agent command skills are
  missing or empty … Run: spec-kitty agent config sync --create-missing
  --keep-orphaned" path. Reproducible, but indistinguishable on disk from a real
  clone-local delivery gap (#4425), whose advice is *correct*. Telling them apart
  needs the per-harness ownership record that #6472 owns.

## Decisions

- **D1 — Scope to shape A.** The mission makes the state the CLI can already
  distinguish truthful. Shape B is deferred to #6472 and named in the PR's
  `## Deferred`. Rationale: inventing a plugin probe here would create a second
  authority for surface ownership, which #6472 exists to define
  (`traces/design-decisions.md`).
- **D2 — The predicate reads `AgentConfig.explicit_agent_list` (#6494).** Not a
  second YAML parse, so the two shapes cannot drift (`C-002`).
- **D3 — `init --ai <agent>` on a stated-empty project exits 0 and installs
  nothing.** The project's stated list is the single canonical authority for
  which agents the CLI manages; the issue's Expected is that such a project is
  *recognised as set up*.
- **D4 — Human wording only.** JSON envelopes keep their key sets (`NFR-002`);
  `configured_agents: []` already carries the machine-readable fact.
- **D5 — Legacy absent list gets its own truthful line.** No `available` key
  means every agent (#6501), so `No agents configured.` is false there too and
  would otherwise blur D2's new message.

## Open questions for specify/plan

- Should `doctor` report the state once (e.g. a single "no CLI-managed agents"
  banner) or per subcommand? *Resolved in plan: per command, because each already
  prints its own summary line and a banner would need a new shared doctor stage.*
- Does any existing test pin the exact strings? *Resolved during implementation:
  `tests/agent/cli/commands/test_agent_config.py` pins `No agents configured`;
  no test pins the doctor summary lines or the init panel text.*
