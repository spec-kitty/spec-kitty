# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-11 · planner-priti · Use checkout .venv/bin/spec-kitty 4.0.0rc7, not ambient rc6. Topology single_branch targets issue-5924-status-doctor-corrupt-log; GitHub PR target main. Source packs are canonical when global prompts drift.

2026-10-11 · planner-priti · Parent baseline: tests/status/test_doctor.py 55 passed; make test-fast 2501 passed, 5 skipped, one stale local retired dashboard __pycache__ failure (environment issue https://github.com/spec-kitty/spec-kitty/issues/6050). Parent removed only verified generated pyc/empty retired dirs; named gate test_no_retired_subsystems.py then 12 passed, no product edits. Planner did not duplicate tests. Runtime specify-success call timed out at 30s after persisting issued plan, before prompt output; query confirmed discovery/specify completed and plan issued. Executing issued plan from canonical source pack and setup-plan, no state edits or replayed success.

2026-10-11 · pi:implementer-ivan:openai-codex:gpt-6.1-sol · Scoped strict mypy reports existing store.py:737 no-any-return because narrow imported EventStream is Any under the repository follow_imports=skip override. Archived pre-production source from 41930fe8 reproduces exactly the same diagnostic. Reported separately as https://github.com/spec-kitty/spec-kitty/issues/6051; no suppression, parser refactor or typing scope expansion. Doctor and new focused tests pass strict mypy.

2026-10-11 · implementer-ivan · Cycle1 validation: coverage239pass/1valid remaining fail; doctor97% store88%, diff-cover vs RED324defbc45 current24 production lines100%. Ruff force-exclude lint/format and complexity15 green; strict mypy doctor/newtest silent imports green. Existing store no-any-return:737 remains #6051 without suppression. Single failing-test confirmation hit60s timeout after F; not completed/retried. Tracer helper canonically commits its targeted tracer despite disabled task auto_commit; task/history files staged only by explicit paths. Stash23beedea22315d535d7a39af3da080c17abbb456 and untracked evidence preserved.

2026-10-11 · implementer-ivan · Final255 named tests green15.23s; ruff force-exclude lint/format and complexity15 green. Strict mypy doctor/helper/newtests with silent imports initially helper:73 no-any-return (already typed dependency_graph not analysed in circular import); explicitly adding existing dependency_graph.py as fourth typecheck target passes, no ignore/cast/source edit. Known store debt#6051 unchanged. Coverage36current-production-diff lines100%. Stash23beedea22315d535d7a39af3da080c17abbb456/evidence untouched; no extra broad tests.
