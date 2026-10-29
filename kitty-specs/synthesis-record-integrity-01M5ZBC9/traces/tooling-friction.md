# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-27 · claude · Claimed the issues after spec/plan, not before: the brief's RUN list did not name the claim step; the internal issue-to-mission-delivery procedure was found only while looking for tracer-file names. Agent command copies are absent in this checkout (.claude/commands missing), so canonical prompts were read from packs/built-in until the skills surfaced.

2026-10-27 · claude · WP01 move-task for_review: pre-review regression gate reported source_mismatch (baseline DeclaredCommandScopeSource/text vs head junit_xml) and did not compare; pytest startup in lane worktrees 50-130s.

2026-10-27 · claude · WP01 approval refused by the issue-matrix gate for context-only citations in research.md (#4226, #5452, #6117, #6442, #6510, #6608, #6685, events #92); analysis step did not flag them. Approval left review-cycle-1.md + a history event uncommitted (--no-auto-commit) on the coord worktree; committed by hand with safe-commit.

2026-10-27 · claude · Integrated blast-radius run caught a re-pin WP01 missed: tests/specify_cli/cli/commands/charter/test_activate_preserve.py (out-of-matrix, nightly-only) still asserted the #6404 full-run strip. Per-WP greps for 'legacy applies' missed the phrase "legacy 'applies' edge" with quotes. Results on consolidated head: tests/charter+charter_offering 8952 passed/30 skipped; charter CLI + arch gates 638 passed/1 failed (this test); make test-fast 2476 passed/6 skipped.
