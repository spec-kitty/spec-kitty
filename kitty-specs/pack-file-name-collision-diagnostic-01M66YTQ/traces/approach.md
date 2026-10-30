# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · Grounded the defect first: an org pack reusing the built-in file name 024-locality-of-change with id ACME_024 passes 'charter pack validate' (0 errors) and doctor prints 'Collisions: none', while IdentityIndex.stored_spelling already refuses it with ActivationIdCollisionError. Scope kept to four WPs: identity query, validate leg, doctor leg, docs.
