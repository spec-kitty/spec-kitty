# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-11 · planner-priti · Use checkout .venv/bin/spec-kitty 4.0.0rc7, not ambient rc6. Topology single_branch targets issue-5924-status-doctor-corrupt-log; GitHub PR target main. Source packs are canonical when global prompts drift.

2026-10-11 · planner-priti · Parent baseline: tests/status/test_doctor.py 55 passed; make test-fast 2501 passed, 5 skipped, one stale local retired dashboard __pycache__ failure (environment issue https://github.com/spec-kitty/spec-kitty/issues/6050). Parent removed only verified generated pyc/empty retired dirs; named gate test_no_retired_subsystems.py then 12 passed, no product edits. Planner did not duplicate tests. Runtime specify-success call timed out at 30s after persisting issued plan, before prompt output; query confirmed discovery/specify completed and plan issued. Executing issued plan from canonical source pack and setup-plan, no state edits or replayed success.
