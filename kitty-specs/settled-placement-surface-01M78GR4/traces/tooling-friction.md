# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-12 · claude-orchestrator · Live repro on main: spec-commit WRONG_SURFACE from the coord worktree (relative path); from the root the remedy says git checkout <topic>, which git refuses (coord worktree holds it); implement on protected root refuses with --no-auto-commit advice the agent action command lacks; baseline-tests.json silently left untracked.

2026-11-12 · claude-orchestrator · CLI lifecycle commits (status transitions, finalize-tasks, record-analysis, implement claim) are unsigned (%G? = N) although commit.gpgsign=true with an ssh key; the host flags them Unverified (#5197). Deferred to the post-consolidation history cleanup, which re-signs every commit.

2026-11-12 · python-pedro · WP01: the T001 integration test takes ~95s serially (real create + finalize per row); the prompt's 'walk from nearest existing ancestor' was unnecessary because find_ancestor already walks a not-yet-created path; primary_partition_checkout's raw-repo_root vs main-root comparison is behaviour-equivalent only because every caller treats holder==repo_root like None.

2026-11-12 · claude-orchestrator · WP01 approval refused SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT: the orchestrator claimed WP01 with --agent claude and no --profile, so the implementer was recorded claude:: and a same-tool reviewer (claude::reviewer-renata) cannot be proven independent (#6715 R1). Recovery without touching the gate: send back to planned with a no-code-finding note, re-claim with --profile python-pedro, re-review. Lesson: always pass --profile on implement claims. Also: the issue-matrix completeness gate blocks the FIRST approval of a multi-WP Mission until every cited issue has a verdict.

2026-11-12 · python-pedro · WP02: the prompt's write_dir(kind) lookup for COORD kinds on the PRIMARY arm recursed through establish_coord_write_location's own seed commit (tests/coordination/test_coord_seed.py undeclared-branch case); the checkout is now looked up with a PRIMARY kind. Settled-mission CLI fixtures cost ~4s setup each, so the new suites take minutes under xdist.

2026-11-12 · python-pedro · WP03: implement_phases.py (the one caller of the claim preflight) was missing from owned_files although T011 requires threading feature_dir there; the WP's T010 cases (b)/(c) assumed move-task writes WP-file bytes, but WP metadata (note, agent) persists as status annotations on the topic branch, so the red test was re-aimed at the annotations; each subprocess CLI fixture costs ~25s, making red/green loops slow.

2026-11-12 · claude-orchestrator · WP03 for_review: the pre-review coverage gate skipped itself ('no_coverage - no changed files detected for this WP') on a single_branch Mission although the WP committed source changes; reviewers run the tests directly. WP03's tests also needed SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS only to build an explicit lanes_with_coord fixture on protected main (finalize refuses otherwise); removed before any assertion.
