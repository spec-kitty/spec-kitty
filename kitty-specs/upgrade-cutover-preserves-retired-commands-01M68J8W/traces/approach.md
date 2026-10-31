# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · Grounded #6547 on main@35318ef51c: the issue's own repro build (5068301dd, 2026-10-20 10:06) predates the #6431 adoption floor (49b520ce, 19:55), so its exact steps no longer reproduce on main — the floor stamps 2.1.4/3.0.2 as settled at FIRST adoption. The surviving hole is the cutover shape: a ledger adopted by a build without the floor (backfill recorded success, retirees recorded, writers absent) is never re-baselined, and ledger-diff re-selects the writers. Reproduced that shape against MigrationRunner.upgrade.
