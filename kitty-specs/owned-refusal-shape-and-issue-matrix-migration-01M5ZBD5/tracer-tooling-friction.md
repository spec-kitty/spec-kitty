# Tracer: tooling friction

- 2026-10-27: the owned-checkout integration fixture (`checkouts`) takes ~170 s to set up per test module; red-first repro of two cases took 4m42s. Share one fixture per module in new tests.
- 2026-10-27: specify/plan prompts gate on bare `#NNNN` references in planning artefacts; context-only citations were rewritten as `see #NNNN` to keep the issue matrix to the two owned issues.
- 2026-10-29: after rebasing over 88 main commits, both the cached test venv (`.pytest_cache/spec-kitty-test-venv`) and the global `uv tool` install kept the old `spec_kitty_events` (missing `SIGNIFICANCE_EVALUATED`): 16 false reds and a crashing CLI until both were rebuilt.
- 2026-10-29: the mission's ADR id collided with one main took meanwhile (`2026-10-27-1`); renumbered to `-2` during the rebase.
- 2026-10-29: a rate limit cut a reviewer off mid-review; resuming the same agent preserved its work.
