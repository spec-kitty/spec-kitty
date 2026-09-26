# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-26 · claude · specify: mission create minted coord topology on a non-primary branch because resolve_primary_branch(bias=True) returns the current branch when origin/HEAD is unset, while branch-context uses bias=False (filed #5114).

2026-09-26 · claude · specify: decision open raised CoordinationWorktreeUnmaterialized as a raw traceback after writing primary artefacts; advertised remedy 'doctor workspaces --fix' only removes husks. Worked around via CoordinationWorkspace.resolve(); decision events landed in the primary status.events.jsonl while spec-commit routed DM artefacts to coord (reproduced on #5113).

2026-09-26 · claude · specify: no sanctioned 'mission flatten' exists for a live coord mission, so the unintended coord topology was kept.

2026-09-26 · claude · implement: 'agent action implement' merges the planning branch's kitty-specs into each lane (FR-009 merge commit); once the planning branch moves on (handoff notes, review artefacts), every lane's move-task --to for_review refuses with 'kitty-specs changes are not allowed on lane branches'. Canonical remedy (git restore --source <planning branch> -- kitty-specs/ + commit) had to be applied to lanes b, e, h. Separately, a single dirty kitty-specs file in the repo-root checkout (another WP's in-progress research script) blocked every other WP's move-task.
