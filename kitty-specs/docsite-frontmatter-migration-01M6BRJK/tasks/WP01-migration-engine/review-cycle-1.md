---
affected_files: []
cycle_number: 1
mission_slug: docsite-frontmatter-migration-01M6BRJK
reproduction_command:
reviewed_at: '2026-11-01T15:37:42Z'
reviewer_agent: reviewer-subagent
wp_id: WP01
---

# WP01 review cycle 1 — REQUEST CHANGES (reviewer-renata, independent subagent)

1. Blocker: not idempotent on the real corpus — `docs/index.md` becomes slug `''`, which the rule rejected on re-run.
2. Major: `related` rule (source-aware) drifted from FR-006/FR-009/D-8.
3. Minor: unknown `external_references` shapes silently dropped.
4. Minor: comment lines in an edited block dropped; mixed line endings normalised.
5. Minor: index basename detection case-sensitive (doc-kitty is case-insensitive).
6. Minor: `--apply` could stop half-way with files written.
7. Minor: `{ref, note}` entries passed through unchecked.
8. Nit: `is_published` not identical to doc-kitty `isDraftStatus`.
9. Nit: `verify_against` missed renames.
