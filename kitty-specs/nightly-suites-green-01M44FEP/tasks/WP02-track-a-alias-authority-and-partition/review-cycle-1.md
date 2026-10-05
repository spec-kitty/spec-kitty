---
affected_files: []
cycle_number: 1
mission_slug: nightly-suites-green-01M44FEP
reproduction_command:
reviewed_at: '2026-10-05T06:29:05Z'
reviewer_agent: reviewer-renata
wp_id: WP02
---

# WP02 review cycle 1: changes requested

Reviewer: reviewer-renata. Two small changes; everything else verified.

1. **`mission_dir_aliases` raises, contrary to its contract** (`src/specify_cli/missions/_read_path_resolver.py:927-931`, `_read_literal_primary_meta`). `_compose_primary_feature_dir` raises `UnsafePathSegmentError` for slugs such as the empty string, `../x`, `a/b`, `.hidden` and `ok slug`. On the base `_group_files_by_partition` returned one group for these; now it raises, and `commit_for_mission(slug="")` changes its error type. Catch `ValueError` around the compose and return the one-name set, as `mission_runtime/resolution.py::_mid8_from_primary_meta` does. Add tests, and a base-green characterization for the empty slug.
2. **A malformed recorded identity yields an alias** (`:934-948`, `:974-978`). A recorded `mid8` of `../x`, `a/b`, one character or 26 characters, or a `mission_id` with path separators or leading spaces, produces names like `foo-../x`. Add the composed name only when it is a safe single path segment (the existing safe-segment guard); otherwise return the one-name set. Add tests.

Verified: red then green through real `commit_for_mission` and real git; the characterization commit is green on the base; `_declared_mid8` is a justified variant; the silent metadata adapter honours the census; 409 gate tests and 239 behavioural tests pass; the reproduction now fails later, at the reconciliation gate.

Note for WP03: a canonical directory whose recorded `mid8` differs from its tail gains a `foo-<tail>-<mid8>` alias.
