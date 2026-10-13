# Analyze phase: fix verification trail (2026-10-10)

Read-only verifier runs over the fixes for the recorded analysis (073426bde, verdict `ready`, 3 medium and 12 low findings).

## Round 1: FAIL

Verified range: 073426bde..175fb2b12.

All 15 ANL findings are resolved in substance. The fixes introduced five new findings, each with a single remedy and none touching an operator ruling:

| Id | Severity | Finding |
|---|---|---|
| NEWA-001 | 3 | The WP03 nested tamper build needs `gradleTestKit()` and a TestKit dir on the real Gradle user home for `--offline`. WP02 proves the mechanism in both modes. |
| NEWA-002 | 3 | WP09 step 1 still said "canonicalise the response document", which contradicts the raw-byte T048. |
| NEWA-003 | 2 | AC-9b row counts were stale after ANL-005 (8 + 4 = 12) in plan sections 8 and 12, research R-7, WP02 and WP11. |
| NEWA-004 | 2 | The WP11 title still said "E-7 provisional rows". |
| NEWA-005 | 2 | spec AC-11c said "WP01 decision record". |

The orchestrator applied one self-ruled fix round under the bounded-autonomy rule for remedy-obvious HALTs.

## Round 2: PASS

Verified range: 175fb2b12..f8bd40000.

- NEWA-001 to NEWA-005 are resolved. Nothing new was found at severity 2 or higher.
- `finalize-tasks --validate-only` reports `validation_passed`.
- `wps.yaml` matches the prompt frontmatter (refs, owned files, dependencies, title) for all 20 WPs, with 0 diffs.
- No absolute home paths are present.
- Residual severity 1: CI is the first real proof of the TestKit run that reuses the outer build's Gradle user home. WP02 requires that experiment before WP03.
