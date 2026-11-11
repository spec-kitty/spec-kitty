# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-11 · claude-orchestrator · Hand-commit 1 (evidence for #7545/#3933): 'agent mission create' committed its scaffold as 'Add scaffold for mission ...' (d4b4ea0be) with no way to add trailers; the dispatch asks every commit to carry a Co-Authored-By trailer, so the history needs a rewrite at closeout.

2026-11-11 · claude-orchestrator · Friction (evidence for #7545/#3933): 'agent decision open' / 'decision resolve' left kitty-specs/<m>/status.events.jsonl modified and decisions/ (DM-*.md, index.json) untracked. No hand commit was needed only because spec-commit took them with spec.md; an agent following the prompt (spec.md + meta.json only) would leave them dirty for the next gate.

2026-11-11 · claude-orchestrator · Hand-commit 2 (#3933 F-04, reproduced on this Mission): setup-plan committed only plan.md (aa9b5a0ca) and left status.events.jsonl (SpecifyCompleted, PlanStarted, PlanCompleted) dirty; research.md, data-model.md, quickstart.md and contracts/ also had to go through spec-commit by hand.

2026-11-11 · claude-orchestrator · Hand-commit 3 (#3933 F-73, reproduced here with this repo's auto_commit: false): 'move-task WP01 --to for_review --note ...' committed the lane transition (4dcc9f711) but left the --note InnerStateChanged row and status.json uncommitted; mark-status also left its annotation dirty. The pre-review gate then ran make test-fast twice (~6 min) inside move-task.

2026-11-11 · claude-orchestrator · Hand-commit 4 (#3933 F-39/F-73 with auto_commit: false): 'move-task WP01 --to approved' (reviewer) exited 0 but left status.events.jsonl, status.json and tasks/WP01-*/review-cycle-1.md uncommitted, printing '(--no-auto-commit)' though the flag was not passed. for_review had committed its transition; approved did not. Also: approval first refused on an issue-matrix with 'unknown' rows the tasks step had seeded, which only the orchestrator can fill.

2026-11-11 · claude-orchestrator · Tally (evidence for #7545): 9 hand commits so far in this Mission, all of files the CLI wrote and left behind (scaffold without trailers, setup-plan's events, and 7 move-task/mark-status residues under this repo's auto_commit: false), plus 1 stash around the WP02 claim (my own code dirt, a legitimate refusal). Every pre-review gate ran make test-fast twice (~6 min per move-task). The issue-matrix seeded 'unknown' rows that blocked the first approval until the orchestrator filled them.

2026-11-11 · claude-orchestrator · Operator follow-up: the auto_commit: false residue (hand commits 3-9) is remediated by D7. A move's record (transition, note, snapshot, review verdict) and mark-status's annotation now commit unless --no-auto-commit is passed; red test test_status_record_commits_with_auto_commit_off_3933.py reproduced it on a single_branch Mission first.
