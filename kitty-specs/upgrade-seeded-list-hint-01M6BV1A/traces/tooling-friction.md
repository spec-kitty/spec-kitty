# tooling-friction

2026-11-01 · python-pedro · The pre-review regression gate runs review.test_command (here: make test-fast, ~6 min on an idle host) under a 300 s budget, so on this host (load average ~197) every WP transition timed out twice. The scope was run by hand to completion instead (2678 passed, 18 failed, all reproducing on pristine origin/main) and the transition recorded the skip from the documented flag. Known batch-wide issue #6865.

2026-11-01 · python-pedro · After spec-kitty agent mission accept, next --result success re-walks specify/plan/tasks/analyze from the top and records completed lifecycle rows for steps that were not re-run, so the Op log shows work that did not happen. The close-out continued with the explicit wrap-up commands instead of driving next further.

2026-11-01 · python-pedro · 18 commits authored as op(researcher-robbie)/op(architect-alphonso) for other missions (kitty-ops/01M6C*.jsonl) landed on top of this branch's tip between 16:55 and 16:57 while next was replaying steps; they were excised before consolidation (kept on backup-6684-dirty-history). Cross-agent writes into a private clone are a fleet hazard, not a mission defect.
