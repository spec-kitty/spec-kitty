# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · spec-kitty specify creates the mission against the current branch (main here), and spec-commit then refuses the protected target. Recovering meant deleting the scaffold and recreating via 'spec-kitty agent mission create --start-branch issue-6792-... --topology lanes --pr-bound'; the specify command has no --start-branch of its own, so the first attempt burned a mission id.
