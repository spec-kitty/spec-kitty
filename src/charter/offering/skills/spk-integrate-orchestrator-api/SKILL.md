---
name: spk-integrate-orchestrator-api
description: "Use Spec Kitty orchestrator-api from external systems, respecting host boundaries, state contracts, and workflow commands."
---

# spk-integrate-orchestrator-api

Use this skill when an agent, script, CI job, or external service needs to drive
Spec Kitty through orchestrator-api.

## Flow

1. Identify the external caller and allowed host boundary.
2. Use documented API contracts rather than scraping local artifacts.
3. Preserve state-machine invariants: no implicit success, no skipped gates.
4. Route mission advancement through runtime decisions.
5. A `PREFLIGHT_FAILED` without a `teardown_error_code` is raised before any lane/target mutation; a refusal leaves refs untouched.

## Legacy Alias

For detailed API contracts and host-boundary rules, use
`spec-kitty-orchestrator-api-operator` when available.
