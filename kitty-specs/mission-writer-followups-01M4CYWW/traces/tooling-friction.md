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

2026-10-08 · claude-runtime · ruff --select I --fix rewrote unrelated imports during WP07 and had to be reverted; pytest fixture setup costs about 2 minutes per invocation.

2026-10-09 · claude-wp10 · Per-file 'ruff format --check --force-exclude' reports a would-reformat on files not in the ratchet exclude when the new block's multi-line asserts collapse to single lines — expected per CLAUDE.md #5301; resolved with a plain 'ruff format <file>'. Also: test collection is ~85s per bare-pytest run in this repo, so targeted runs were batched to minimise collection passes.

2026-10-09 · claude-wp09 · WP09: provenance ratchet is hand-edited (C8). After prompt edits, ran python -m tests.architectural.test_builtin_pack_provenance_ratchet to learn new per-file counts, then lowered baseline entries by hand: tasks/prompt.md provenance 57->29, tasks-packages 12->10, removed the now-zero tasks-finalize entry. Targeted pytest collection is ~2min each run; batched named files to limit round-trips.

2026-10-09 · claude-wp16 · WP16: pytest collection for tests/prompts and tests/dossier runs ~100s per cold process in this repo; used background runs. ruff format needed --force-exclude for the new test file per the ratchet exclude rule.

2026-10-09 · claude-wp17 · T043 ratchet step was a no-op: ratchet_violations(census(), load_baseline()) returned zero growth and zero stale on the current tree -- prior WPs (WP09, WP16) had already lowered every affected baseline entry, so no hand-edit was needed. spec-kitty doctrine regenerate-graph produced no diff to pack-manifest.yaml/*.graph.yaml (already consistent, matching the WP16 review finding that the analyze depends_on change did not alter the DRG hash).

2026-10-09 · claude-wp11 · spec-kitty doctrine regenerate-graph emits a deprecation banner steering to 'spec-kitty charter', but regenerate-graph still lives only under 'doctrine'. Ran uv sync --frozen first per C13 since it shells out; it only re-hashed the glossary_pack content_hash + manifest_hash (no *.graph.yaml changed).

2026-10-09 · claude-wp12 · [2026-10-09][docs] Adding two new ### headings under the CHANGELOG [Unreleased] section cascaded the docs-retrieval-index anchor dedup numbering across the whole changelog history (463-line index churn), even though only two headings were added; regenerating via scripts/docs/docs_index.py --write produced the expected, path-stable diff.
