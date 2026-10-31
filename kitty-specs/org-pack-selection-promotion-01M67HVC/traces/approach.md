# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · claude · Red-first: the org-pack promotion test is written and observed failing through the migration entry point before the migration is rewired; interview parity is proven through the CLI.

2026-10-30 · claude · Red recorded before the migration rewire: the three new upgrade tests fail on 6cbeb62 with the org/project stems missing from the ledger and the org id reported 'Unresolved interview selections skipped (not promoted): directive:QA_003' — the reported defect, not an import error.

2026-10-31 · claude · Development-assist test verdicts (development-assist-test-cleanup): all tests this mission added are contract tests, keep as-is — test_selection_resolver.py (resolver contract), the three org/project-pack promotion tests + unknown-id control and step-contract test in the migration module (the fix's own contract), and the CLI parity + unknown-id pair in the interview promotion module. No test_issue_6686*/test_repro_* file was added, no WP##/NFR labels, nothing to fold or split.
