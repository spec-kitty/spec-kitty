# Approach

- 2026-10-04: read-only grounding first (three parallel Explore agents: gates, test seams/churn, invariants), committed as research/code-grounding.md before any spec.
- 2026-10-04: the executor split is done by a verbatim AST splitter (top-level definitions sliced with their leading comments into mapped modules, imports pruned by ruff F401), so no body can drift while moving. Monkeypatch re-pointing is computed from the AST, not by hand.
- 2026-10-04: slice order: #2600 (bake cluster) first because executor imports from it, then #3457 (independent), then the executor split as a commit series.
- 2026-10-04 (WP03): the split was rehearsed end to end in a scratch worktree (splitter -> ruff F401 prune -> byte-identity proof -> AST patch audit -> test rewriter) before the claim, then replayed in the repository root checkout; 599 test edits were mechanical, 7 list/loop entries and 1 parametrized lookup needed hand edits.
- 2026-10-04 (WP03): the AST audit classified every executor patch by which split modules look the name up: 284 single-module re-points, 129 multi-module sites routed through tests/consolidation/executor_family.py, 195 reads/imports re-pointed, 264 left as-is (executor still looks the name up).
- 2026-10-04 (pre-PR): adversarial squad of three (behaviour-drift, architecture, reviewer). Debbie found no behaviour drift; the architect asked for leaf-contract wording and a wider write-side scan; the reviewer asked for PR-body fixes. All folded before the PR opened.
