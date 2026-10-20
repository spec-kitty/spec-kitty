# Approach: charter-followups-tidy-01M5CCYJ

- **[2026-10-20][plan] One Mission, four parallel work packages.** WP01 is the migration repository requirement (#6539). WP02 is the language settlement module plus the write-with-answers change (#6540 + #6542, one WP because both rewrite `settle_project_languages`). WP03 puts `LANGUAGE_TOKENS` on the seam (#6541). WP04 adds the reconcile tests (#6543). The files are disjoint, so there are four lanes.
- **[2026-10-20][plan] An execution-based audit, not grep, decides which migrations need a git repository.** Squad evidence: about 10 migrations reach `resolve_canonical_repo_root` transitively through `charter.activation.*`.
