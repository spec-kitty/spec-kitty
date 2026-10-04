# Design decisions — regression-slice-cleanup

- 2026-10-04 — Branch named `issue-5618-regression-slice-cleanup` (charter) instead of the brief's `fix/regression-slice-cleanup`; the charter wins.
- 2026-10-04 — Removing `regression` does not de-route tests (module shards select `not performance and not stress`); it only moves `fast`/`unit` tests into `make test-fast`.
- 2026-10-04 — Operator direction: no planning-branch draft PR while no multi-user runs are ongoing; the early draft #5626 was closed and the PR opens at closeout.
- 2026-10-04 — `regression` markers on green, closed-issue pins that a ledger rated KEEP stay in place (for example #2745). The ledgers deliberately keep issue pins in the per-PR `regression` slice; aligning them with `tests/regression/README.md` (open-P0-only) is a separate policy decision.
- 2026-10-04 — Unreadable-path tests inject `PermissionError` at the I/O seam rather than skipping under root, so the refusal is exercised on every uid; no root skipif was needed.
