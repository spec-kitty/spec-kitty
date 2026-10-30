# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · spec-kitty specify on a topic branch creates the mission with target_branch=main, so spec-commit then refuses the protected ref; recreating with 'agent mission create --start-branch <topic>' (target-branch=<topic>, --pr-bound, --branch-strategy already-confirmed) is the working path. Worth a doc/CLI hint.
