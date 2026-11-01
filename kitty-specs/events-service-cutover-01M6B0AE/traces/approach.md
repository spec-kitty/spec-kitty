# Approach — events-service cut-over

- **[2026-11-01][specify] Grounding before spec.** Two read-only inventory agents (tests/goldens; CI/packaging) plus own checks; live baseline: the pinned linux-x64 binary vs the Python oracle, 677 Missions, 0 differences.
- **[2026-11-01][plan] Topology `single_branch`.** The work is sequential (pin → repoint → wire → remove → release → docs) and deletion-heavy; lane worktrees would add consolidation cost for no parallelism.
- **[2026-11-01][plan] Repoint, then remove.** Consumers move to the pinned assets while the copies still exist (so each repoint is proven against identical bytes), then the copies are deleted.
- **[2026-11-01][implement] Orchestrator implements WP01–WP02, then delegates.** WP03–WP08 went to one implementer subagent (`claude:opus:python-pedro`, WP08 as `scribe-sally`) and one reviewer subagent (`claude:opus:reviewer-renata`), sequentially; every WP got an independent review, and WP01/02/03/06/07 took a second cycle on real findings.
- **[2026-11-01][implement] Deferred fleet-verdict edit.** WP04 could not drop the retiring workflows from `PR_WORKFLOWS` while their files existed; the edit moved into WP06's deletion commit as an agreed out-of-map change.
