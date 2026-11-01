# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · Decision: the index stays permissive for a directive declared id whose file name another layer binds to a different id (compile and consistency check rely on it), while the facade keeps refusing it. The rule is expressed as 'the index knows the id but can name no stem', reusing IdentityIndex.stem/_representable_stem rather than adding a second rule. Writers keep refusing via stored_spelling/collision_error.
