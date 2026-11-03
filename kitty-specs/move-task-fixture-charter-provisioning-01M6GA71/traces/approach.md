# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · pi:python-pedro · Fix the fixture, not the assertion: the move-task git-validation fixture is an unprovisioned project, so every review-ward node reads code_producing from code_producing_for's caught-exception fallback instead of the resolved software-dev profile. Provision through tests/_factories.provision_test_charter (the production init provisioner) and pin it with a red-first resolution/no-fallback pair.
