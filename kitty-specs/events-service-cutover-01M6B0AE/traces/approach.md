# Approach — events-service cut-over

- **[2026-11-01][specify] Grounding before spec.** Two read-only inventory agents (tests/goldens; CI/packaging) plus own checks; live baseline: the pinned linux-x64 binary vs the Python oracle, 677 Missions, 0 differences.
- **[2026-11-01][plan] Topology `single_branch`.** The work is sequential (pin → repoint → wire → remove → release → docs) and deletion-heavy; lane worktrees would add consolidation cost for no parallelism.
- **[2026-11-01][plan] Repoint, then remove.** Consumers move to the pinned assets while the copies still exist (so each repoint is proven against identical bytes), then the copies are deleted.
