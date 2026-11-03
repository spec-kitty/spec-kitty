# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · pi · finalize-tasks refuses to commit planning artifacts on the protected target branch, so this mission's topic branch had to be created before finalize rather than at PR time; tasks step also assumes tasks.md already exists.

2026-11-03 · pi · Lane worktrees carry no fetched pack tree, so pack-dependent architectural gates fail there with 'no synced files under packs/internal' — false reds unless make sync-packs is run per lane. Verify in the primary clone before recording any such red.
