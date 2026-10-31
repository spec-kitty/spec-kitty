# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · docs/api/cli-commands.md: a full 'uv run python -m scripts.docs.build_cli_reference' could not complete here — its per-command 'uv run spec-kitty ... --help' capture timed out (TimeoutExpired on 'orchestrator-api cancel-decision --help' after 30s), consistent with the shared-host cache contention the batch brief warns about. Worked around by rendering ONLY the three changed sections through the same scripts.docs.build_cli_reference.capture_help seam and splicing them into the committed page; scripts.docs.check_docs_freshness --ci then reports errors=0 with only the four pre-existing HELP-DRIFT warnings (charter activate, migrate activation-ledger, migrate ledger, service status), none of them mine.

2026-10-31 · python-pedro · move-task WP01 --to for_review: the implementation was committed (3858fc9328) BEFORE the WP was claimed, so the 'no implementation commit since claim' guard could only be satisfied with --force (the documented path when there is genuinely nothing left to commit). Separately the pre-review regression gate reported 'source_mismatch — baseline captured under DeclaredCommandScopeSource/text; head ran under DeclaredCommandScopeSource/junit_xml — failure identities are not comparable' and still allowed the transition; the two collections differ in failure-identity scheme, so its verdict is not evidence about this diff either way. Recorded, not worked around.
