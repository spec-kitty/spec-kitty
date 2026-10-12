# Tracer — Tooling Friction

Running log of tooling friction encountered during the mission. One dated entry per incident.

- **2026-10-12** — `gh` CLI in this cloud session: GraphQL is blocked at the proxy; `gh issue view/list/search` 403. Must use REST (`gh api repos/{owner}/{repo}/...`) and the CCR routes for draft/ready/auto-merge. The GitHub *search* endpoint is also blocked (repo-scoped endpoints only), so tracker keyword discovery had to fall back to repo-scoped cross-refs + open-PR scan.
- **2026-10-12** — `spec-kitty` CLI emits a `CharterCatalogMissWarning` (toolguide:typescript-mutation-tools scope_filtered) on every `charter context` invocation; noise, not an error.
- **2026-10-12** — The slash-command templates (`.claude/commands/`) are not checked into this repo's own dogfooding tree, so the specify→plan→tasks flow is driven via the `spec-kitty` CLI directly rather than `/spec-kitty.specify`.
