# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · The stand-in is opt-in from the caller that already verified the landing (accept --mode pr --merge-commit -> baseline.verify_pr_merge_evidence), so no second verifier and no new write exist; the base, owned_files match, bookkeeping exclusion and independence check are unchanged, and a planning commit that is not an ancestor of the landing is refused instead of diffed.
