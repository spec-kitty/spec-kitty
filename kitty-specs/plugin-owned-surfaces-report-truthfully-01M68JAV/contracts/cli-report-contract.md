# Contract: what the CLI reports about agent-surface ownership

The change is a report contract, not an API. Each row is a state the CLI can
already distinguish, the exact human line or panel verbatim intent, and the
machine-readable fact that already carries the same information.

| # | State (`.kittify/config.yaml`) | Command | Human report | Exit | Machine fact |
| --- | --- | --- | --- | --- | --- |
| C1 | `agents.available: []` (stated empty) | `agent config list` | `No CLI-managed agents.` + what that means (a harness or plugin supplies the surfaces; naming an agent hands it to the CLI) | 0 | — (no JSON form) |
| C2 | no `agents.available` key (legacy) | `agent config list` | `No stated agent list.` + every supported agent is available | 0 | — |
| C3 | `agents.available: [k, …]` | `agent config list` | `Configured agents:` + per-agent presence (unchanged) | 0 | — |
| C4 | stated empty | `init` re-run | `Already initialized.` + the project states no CLI-managed agents; nothing installed, verified or restored | 0 | `meta.json` unchanged |
| C5 | stated empty | `init --ai <agent>` | C4 + `--ai <agent> was ignored` (the stated list wins) | 0 | no file written |
| C6 | stated empty | `doctor skills` | `Command Skills: no CLI-managed agents (…) — nothing to check` | 0 | `doctor skills --json` key set unchanged; `configured_agents: []`, `ok: true` |
| C7 | stated empty | `doctor tool-surfaces` | `Tool Surfaces: no CLI-managed agents (…) — nothing to check` | 0 | `--json` envelope unchanged |
| C8 | stated empty | `doctor command-files` | `Command Files: no CLI-managed agents (…) — nothing to check` | 0 | `--json` prints `[]` |
| C9 | `[k]` where k's command skills are missing | `init` re-run | `Initialization incomplete: Configured agent command skills are missing or empty: … Run: spec-kitty agent config sync --create-missing --keep-orphaned` | 1 | — (unchanged, #4425) |

## Invariants

1. No human line in C1/C4–C8 presents `init` or `agent config add` as the repair
   for a problem. C5 names `agent config add <agent>` only as the deliberate way
   to hand a surface to the CLI.
2. C6–C8 never print `all … healthy (0 …)`; that sentence is reserved for a real
   check (asserted by a positive control per command).
3. The stated-list shapes (C3, C9) are byte-identical to the pre-change output.
4. JSON envelopes keep every existing key and value; the new line is a
   human-only payload key.

The C9 recovery command is pinned verbatim by
`tests/init/test_init_stated_empty_agents.py::test_init_rerun_still_fails_for_a_listed_agent_with_missing_skills`.
