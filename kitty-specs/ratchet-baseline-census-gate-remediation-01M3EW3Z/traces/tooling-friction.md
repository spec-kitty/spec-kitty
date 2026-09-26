# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-26 · claude · specify: mission create minted coord topology on a non-primary branch because resolve_primary_branch(bias=True) returns the current branch when origin/HEAD is unset, while branch-context uses bias=False (filed #5114).

2026-09-26 · claude · specify: decision open raised CoordinationWorktreeUnmaterialized as a raw traceback after writing primary artefacts; advertised remedy 'doctor workspaces --fix' only removes husks. Worked around via CoordinationWorkspace.resolve(); decision events landed in the primary status.events.jsonl while spec-commit routed DM artefacts to coord (reproduced on #5113).

2026-09-26 · claude · specify: no sanctioned 'mission flatten' exists for a live coord mission, so the unintended coord topology was kept.
