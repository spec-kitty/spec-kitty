# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-a · spec-commit refused PROTECTED_BRANCH_REFUSED: the mission was created non-interactively on protected main, so its branch contract pointed at main. Rebound target_branch to the topic branch issue-6772-charter-packs-refusal-code and set pr_bound=true in meta.json, matching the shape a create --start-branch --pr-bound would have produced (mission identity fields untouched).
