---
affected_files: []
cycle_number: 1
mission_slug: merge-seam-test-isolation-campsite-01M3F61E
reproduction_command:
reviewed_at: '2026-09-26T18:53:32Z'
reviewer_agent: claude-reviewer
wp_id: WP07
---

# WP07 review feedback (cycle 1) - reviewer-renata

**Verdict: REJECT (changes requested).** The chdir conversion itself is correct; the rejection is for a gate regression the formatting churn caused.

## What passed (keep it)

- All 64 cwd sites were converted. An AST-normalised comparison against the lane-a merge base `c8b00455d6` shows every file matches base once each try/finally-chdir becomes `with contextlib.chdir(...)`. The check covered indentation scope, statement placement, `with` item order (chdir first, as before), and assertions. The only non-mechanical deltas are the two optional-cwd `_invoke` helpers, which now use `nullcontext()`; every caller passes `cwd=`, so the fallback does not change behaviour.
- The census, home-pin, and sys-modules gates are green: 58 passed on both lane and base.
- The shard files under `-n 4 --dist loadfile` give 133 passed and 2 skipped on both lane and base.
- `S2.yaml` is now `rows: []`, and that is correct. No `src/**` edits, and ruff check is clean.

## Required changes

1. **BLOCKING: `tests/architectural/test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_still_genuinely_reformats` is RED on the lane and GREEN on base.** Running `ruff format` on explicit paths skipped `[tool.ruff.format].exclude`, so 7 files on the #473 formatter-debt ratchet came out fully formatted. They are:
   - `test_charter_decision_integration.py`
   - `test_charter_prereq_suppression.py`
   - `test_charter_widen.py`
   - `test_charter_widen_integration.py`
   - `test_decision.py`
   - `test_decision_widen_subcommand.py`
   - `test_specify_widen.py`

   Fix it with option (a) unless the orchestrator approves (b):
   - (a) **Preferred:** revert the formatting-only hunks in those files, such as joined `assert ..., (msg)` lines, joined comprehensions and joined `.write_text(...)` calls. Keep only the mutation-site conversions. Then confirm the ratchet test is green.
   - (b) Remove the 7 entries from `pyproject.toml` `[tool.ruff.format].exclude`. This list is shrink-only, so removal is allowed. It is an out-of-map, cross-cutting edit, though: it needs orchestrator sign-off, a full `tests/architectural/` run, and care about conflicts with sibling sweep WPs.
2. **LOW: the scope and evidence are inaccurate.** The formatting-only rewrites of assertion messages go beyond the mutation sites, which breaks the rule against refactoring beyond them. The Activity Log also says "ruff format --check clean" without mentioning that these files are format-excluded. After fixing item 1, run `tests/architectural/test_ruff_format_exclude_ratchet.py` and record the result with the other neighbouring-gate evidence.
