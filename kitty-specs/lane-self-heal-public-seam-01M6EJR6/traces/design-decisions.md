# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · python-pedro · D1: clean_worktree_policy is a required keyword-only Literal ('refuse-dirty' | 'allow-dirty'), not a bool: the call site must name the policy, and no default means a new caller cannot silently inherit the permissive branch.
