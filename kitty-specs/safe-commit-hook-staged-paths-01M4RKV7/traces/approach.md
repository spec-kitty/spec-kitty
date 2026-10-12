# Tracer: Approach — safe-commit-hook-staged-paths-01M4RKV7

Initial approach (from spec): a single post-landing check inside `safe_commit`, shared by the
`--only` route and the FR-022 temp-index route, comparing `git diff-tree --name-only` of the new
commit against the requested path set (+ FR-022 `index_deletions`). On a mismatch the commit has
already landed, so re-sync the operator's real index for the extra paths and raise a new
`SafeCommitRecoveryFailed` subclass (`SafeCommitUnrequestedPaths`) that names them. The
expected-parent route is left untouched (negative control).

- **[2026-10-12][specify] Red-first repro built before any fix.** Library-level harness exercises
  all three routes; the two affected routes are RED and the control GREEN on `origin/main`
  (`8a911083`). Evidence captured in `research/defect-diagnosis-5903.md`.
- **[2026-10-12][specify] Caller survey → FR-006 is `[folded]`.** Every `safe_commit` caller keys
  "DID land" on `isinstance(exc, SafeCommitRecoveryFailed) and exc.commit_sha is not None`, never on
  `SafeCommitIndexResidue` specifically, so the new subclass inherits correct handling with no
  per-caller edit. Confirmed by reading all eight call sites.
- **[2026-10-12][review] Independent adversarial review folded while draft.** One HIGH (Windows
  path-separator) folded inline; two LOW findings dispositioned (docstring precondition + accepted
  note). Review was run by a separate profile-loaded reviewer over the integrated diff, per the
  charter's recommended pre-PR mechanism (reviewer ≠ implementer).
