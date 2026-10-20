# Design decisions: charter-followups-tidy-01M5CCYJ

- **[2026-10-20][specify] A declared `requires_git_repository` ClassVar, checked before `detect()`.** An `apply()`-time repository error is now a recorded `failed`. Operator decision `migration_repo_requirement`.
- **[2026-10-20][specify] The flag is set on shipped migrations, and the content-hash drift is accepted.** Operator decision `migration_flag_ledger_drift`. Recorded in an ADR 2026-10-17-1 note.
- **[2026-10-20][specify] The seam carries `LANGUAGE_TOKENS` only, as plain strings.** `LANGUAGES`/`LanguageSpec` and the family helpers stay internal. Operator decisions `seam_language_catalog` and `seam_language_export_shape`. The census is module-keyed, so FR-008 is enforced by `__all__` plus a negative test.
- **[2026-10-20][specify] The interview writes `languages:` after the answers and before promotion.** Operator decision `interview_language_write_order`. The settle step decides only; `store_language_settlement` writes.
