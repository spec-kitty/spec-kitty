# Approach — move-task-evidence-fixture-repin-01M6EJZB

- **[2026-11-02][ground] Reproduce before specifying.** The issue's command was rerun in this clone at `origin/main` `9aed3a8012`: 8 failed, 7 passed, every failure led by `IMPLEMENTATION_MISSING`. The failing node set matches the issue exactly.
- **[2026-11-02][ground] Judge the gate, not the test's subject.** The refusal comes from #6715's owned-file evidence gate, whose contract is intended and covered by its own integration tests. The stale seam is the module fixture (no `owned_files`, unowned root deliverable), so the fixture is re-pinned and no production code changes.
- **[2026-11-02][plan] Prototype the remediation before writing tasks.** A throwaway edit (declare `owned_files: src/**`, commit `src/implementation.py`, pass `--agent` on the done node) turned the module 15/15 green, then it was reverted so the WP implements it red-first; the shape is recorded in `research.md` §6.
