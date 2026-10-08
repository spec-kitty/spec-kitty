# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-08 · claude · Seed: (1) mission create still commits 'Add scaffold for feature <slug>' (mission_creation_commit.py:95) - in scope as FR-012. (2) branch-context/create report target_branch = the topic branch itself when started off a stacked PR branch; fine for single_branch but the PR base question (stack on PR 5890 vs main) is not represented anywhere in the Mission contract. (3) The YAML glossary pack header says regenerate via scratchpad/migrate_glossary_pack.py, which is not in the repo. (4) generate_contextive_glossaries.py check is red at HEAD (orchestration.yml stale since #5780) and no CI job runs it.

2026-10-08 · python-pedro · tests/conftest.py wall-clock AST scan over the whole tests tree costs ~2-3 min on any cold digest (every test-file edit); an interrupted run never writes the cache, so a timeout wrapper re-pays it every time. pkill -f/pgrep -f patterns match the invoking shell.

2026-10-08 · claude-orchestrator · move-task --to planned with --review-feedback-file committed the lane transition but left the follow-up annotation event (subtask reset, release_runtime_claim) and the feedback file uncommitted, so the next implement claim refused with WRITE_CHECKOUT_DIRTY until the orchestrator committed them by hand.

2026-10-08 · claude-orchestrator · Parallel streams on a single_branch Mission: implement refuses a second WP with WRITE_CHECKOUT_OCCUPIED (correct for one checkout). To run the runtime stream (WP05->WP06->WP14->WP07) in parallel, the orchestrator records its status with move-task (claimed, in_progress) and the implementer works in a separate git worktree on branch stream/runtime, merged back into the target branch before each review. The CLI has no first-class way to say 'this WP runs in another checkout' for single_branch.

2026-10-08 · claude-runtime · A fresh worktree's first pytest run builds the test venv (about 4 minutes); later runs are fast.

2026-10-08 · claude-runtime · A -n 4 --dist loadfile sweep gave 'Unknown mission type None' failures in tests/integration/test_owned_next_runtime.py (3 tests) that pass serially on the same tree (26/26). Re-run serially before attributing a parallel-run failure to a change.

2026-10-08 · claude-runtime · pytest collection takes about 2 minutes per invocation after test edits; the WP06 prompt named tests/doctrine/test_doctrine_regenerate_graph_roundtrip.py but the gate lives in tests/architectural/.
