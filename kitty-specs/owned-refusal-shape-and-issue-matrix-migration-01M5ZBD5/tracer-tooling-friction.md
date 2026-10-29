# Tracer: tooling friction

- 2026-10-27: the owned-checkout integration fixture (`checkouts`) takes ~170 s to set up per test module; red-first repro of two cases took 4m42s. Share one fixture per module in new tests.
- 2026-10-27: specify/plan prompts gate on bare `#NNNN` references in planning artefacts; context-only citations were rewritten as `see #NNNN` to keep the issue matrix to the two owned issues.
