# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-05 · python-pedro · DM-1: status.events.jsonl is proved by event-id containment in the target's committed log, because the union stage reads the coordination worktree's working tree, not the branch's commits. DM-2: status.json stays excluded, as a stated derived-snapshot rule. DM-3: a primary document (meta.json) is landed iff the target's committed copy contains the coordination document (recursive JSON containment), because the target re-authors it after the checkpoint (bake/stamp/flatten).
