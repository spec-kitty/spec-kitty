# Tooling friction

Tooling touched: orchestrator-api, host accept, move-task, agent status emit, the status event log.

- 2026-11-20: `agent decision open` without `--step-id`/`--slot-key` prints a bare usage error with no JSON, so a `--json` caller cannot parse it.
