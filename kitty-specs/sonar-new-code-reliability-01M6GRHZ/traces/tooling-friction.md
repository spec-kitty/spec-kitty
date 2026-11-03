# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · python-pedro · SonarCloud's issues API accepts `inNewCodePeriod=true` and silently ignores it on this project (returns all 23 BUG issues, not the 4 on new code). `sinceLeakPeriod=true` is the parameter that reflects the leak period. The issue's work list appears to have been built from the non-filtering call.

2026-11-03 · python-pedro · A fake-seam test (`monkeypatch.setattr` on specify_cli.mission_metadata.read_tracked_meta, then calling backfill_identity._tracked_mission_id) perturbed a later test's git-backed fixture in the same pytest process: the following test saw the tracked meta.json as corrupt. Not reproduced by an equivalent standalone probe; the guard module was narrowed to the shape assertion and the behavioural contract left to tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py, which owns it.
