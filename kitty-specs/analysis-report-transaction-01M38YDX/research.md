# Research: report-only transaction

Audience: software engineer. Evidence inspected at upstream `18df07fc12b9a8102d456cdc80072beda5c8c3cf`.

## Decisions and evidence

- `src/specify_cli/git/commit_helpers.py` documents and implements #4888 using `git commit --only`, without stash. Preserve it as commit authority; the intake's old stash finding is superseded.
- `src/specify_cli/analysis_report.py::_charter_path` already prefers authoritative YAML. Remaining manifest gaps are selected configuration and WP definitions; the intake's Markdown-only finding is superseded.
- `mission_record_analysis.py` intentionally resolves SPEC/PRIMARY for report writes and uses ANALYSIS_REPORT in commit_for_mission. A clean linked checkout cannot substitute for clean authoritative inputs.
- Default commit failure suppression preserves historical write behavior but is unsuitable for an opt-in transaction success claim.
- Existing Git index/ref locks do not fence arbitrary external input editors. Compare before/after, refuse observed races, and report committed-but-unqualified state without destructive rollback.

## Risks

Resolved governance spans project overrides and configured packs. A partial manifest must not masquerade as complete freshness. Qualify the supported local scope and refuse unsupported mutable dependencies. Runtime status churn must not stale a report, while actual WP definitions must.

## Workflow evidence

Qualified wheel runtime 965d7fd13 created mission 01M38YDXPADJA9431Z5A3KMBCV and run cd0e3b454256425a9c5e4264036d1d77. Public resolve_owned_mission and resolve_configured_template returned the project plan template. Missing owned flags in research/setup-plan/context are recorded limitations; artifacts are authored and committed through supported spec-commit, with next owning state.
