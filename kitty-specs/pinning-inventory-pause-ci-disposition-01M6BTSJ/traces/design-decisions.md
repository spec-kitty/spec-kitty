# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · python-pedro · WP02 records the changelog entry as a per-PR fragment (docs/changelog/unreleased/6998.fixed.md, section 'fixed') rather than editing docs/changelog/CHANGELOG.md. #6988 introduced exactly this mechanism so parallel pull requests never conflict on the shared file, and this batch runs ~20 missions concurrently, several of which write changelog entries. WP02's frontmatter owned_files was corrected from docs/changelog/CHANGELOG.md to the fragment path after the spec-kitty guard reported ACTIVE_WP_SCOPE_VIOLATION; the fragment is the real changelog surface now, and the release-time assemble step folds it into [Unreleased]. Style gate: 0 errors (entry 806 chars, under the 900 warning threshold). Spelling gate: 0 findings.
