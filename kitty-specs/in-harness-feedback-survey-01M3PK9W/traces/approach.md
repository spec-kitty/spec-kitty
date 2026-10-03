# Approach — in-harness-feedback-survey-01M3PK9W

Initial approach (from spec + plan): a new `specify_cli.feedback` bounded context with thin adapters. Agents are reached through the same renderer seam that carries the startup upgrade check (agent-check → native ask → agent-submit). Humans in a terminal get an inline form gated by `is_interactive()`. Delivery is a detached single-attempt sender. The upstream build ships dormant (no default endpoint); downstream distributions supply one via `DistributionProfile`.

- 2026-09-30 — Command surface slimmed at operator request: a single `spec-kitty feedback` command with `--status` / `--prompts`, and no subcommand group.
- 2026-09-30 — All mission artifacts must stay vendor-neutral (operator direction): no company identity in spec, plan, code, docs, or defaults.
# Approach — in-harness-feedback-survey-01M3PK9W

Initial approach (from spec + plan): a new `specify_cli.feedback` bounded context with thin adapters. Agents are reached through the same renderer seam that carries the startup upgrade check (agent-check → native ask → agent-submit). Humans in a terminal get an inline form gated by `is_interactive()`. Delivery is a detached single-attempt sender. The upstream build ships dormant (no default endpoint); downstream distributions supply one via `DistributionProfile`.

- 2026-09-30 — Command surface slimmed at operator request: a single `spec-kitty feedback` command with `--status` / `--prompts`, and no subcommand group.
- 2026-09-30 — All mission artifacts must stay vendor-neutral (operator direction): no company identity in spec, plan, code, docs, or defaults.
- 2026-10-01 — WP08 (docs): documented SHIPPED behaviour, verified against `spec-kitty feedback --help` and a live quickstart run (isolated HOME, loopback listener). Glossary context `docs/context/feedback.md` (four terms as `candidate`, "telemetry" only as an avoid term); how-to `give-feedback.md`; reference additions in the env-var and configuration pages; changelog entry under Unreleased (edited the canonical `docs/changelog/CHANGELOG.md`; root `CHANGELOG.md` is a symlink). The two new pages also needed the page-inventory and docs-retrieval-index rows the docs-freshness gate demands.
- 2026-10-01 — WP08: the contextive generator emits nothing for the new context (no traceability-map entry), so no `.contextive/feedback.yml` was added.
