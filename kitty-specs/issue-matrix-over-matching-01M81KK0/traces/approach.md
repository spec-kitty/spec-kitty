# Approach

- **[2026-11-22][plan] One work package, red-first.** The colour filter, the commit-citation rule, the scope rule and the pattern convergence all touch the same two modules and one test family, so they ship as one work package. Acceptance tests go in first through `discover_issue_references` and `classify_occurrence`.
- **[2026-11-22][implement] No re-pins were needed.** The new rules broke none of the 3010 tests in the issue-matrix family (123 files): no existing test pinned a research, plan or contracts reference as gating, or a colour or commit citation as a reference. Disposition: the change is narrower than feared; positive controls in the new test file carry the fail-safe guarantee.
