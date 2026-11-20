# Tooling friction

Tooling touched: orchestrator-api, host accept, move-task, agent status emit, the status event log.

- 2026-11-20: `agent decision open` without `--step-id`/`--slot-key` prints a bare usage error with no JSON, so a `--json` caller cannot parse it.
- 2026-11-20: the first pytest run in a fresh session spent ~10 minutes building a throwaway editable wheel (pip into a temp venv) before collection; later runs collect in ~20-110 s.
