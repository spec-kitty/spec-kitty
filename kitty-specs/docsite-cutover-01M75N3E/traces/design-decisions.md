# Design decisions

- **[2026-11-11][specify] No alert issue.** A failed smoketest turns the run red; #2361's optional alert issue is not adopted (operator decision).
- **[2026-11-11][plan] Canary removed, not repurposed.** The smoketest is the one live-probe mechanism; a canary of the current site would duplicate it.
- **[2026-11-11][plan] DocFX build job removed from the deploy workflow.** Its sources stay until #6943; a revert of the pull request restores the DocFX build and deploy jobs and the canary.
- **[2026-11-11][plan] Least privilege.** Default `contents: read`; `pages: read` on the probe job; write scopes on `deploy` only.
- **[2026-11-11][implement] Archived links to `docs/llms.txt` priced, not rewritten.** Two `docs/archive/architecture/` pages link to the deleted file; archive bodies are immutable, so `site/link-debt.json` lists them under the `relative-links` gate (burn-down #7489).
- **[2026-11-11][implement] WP01 review findings folded into WP02.** `actions/configure-pages` pinned by commit (v6.0.0); the failure tests now judge a modelled run conclusion that reads `continue-on-error`, with a self-test that a swallowed failure turns the run green.
