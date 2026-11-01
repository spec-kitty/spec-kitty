# Decision Moment `01M6BW2S981SKQWXKCBNQD8RBW`

- **Mission:** `docsite-frontmatter-migration-01M6BRJK`
- **Origin flow:** `plan`
- **Slot key:** `plan.related.source-aware-publication`
- **Input key:** `related_source_aware`
- **Status:** `resolved`
- **Created:** `2026-11-01T15:36:36.392742+00:00`
- **Resolved:** `2026-11-01T15:36:39.513818+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which related targets must leave related? The spec said every unpublished target; doc-kitty only resolves related for pages it builds (an excluded page is never built; a draft is built only in a drafts-on preview, where drafts exist but excluded pages never do).

## Options

- Source-aware: published source -> published targets only; draft source -> any non-excluded page; excluded source -> any page
- Uniform: every unpublished target leaves related
- Other

## Final answer

Source-aware, mirroring the build: a published page's related names published pages only; a draft page's related may name drafts but no excluded page; an excluded page (never built, immutable history) keeps its related slugs to any existing page. Avoids rewriting 127 entries (105 in excluded history, 22 on drafts) into GitHub URLs for no build benefit. The corpus-shape test enforces the published rule, so when #6932 or an author publishes a draft, any related entry into a draft is named by the test. Autonomous-run default after review finding; flagged for the operator.

## Rationale

_(none)_

## Change log

- `2026-11-01T15:36:36.392742+00:00` — opened
- `2026-11-01T15:36:39.513818+00:00` — resolved (final_answer="Source-aware, mirroring the build: a published page's related names published pages only; a draft page's related may name drafts but no excluded page; an excluded page (never built, immutable history) keeps its related slugs to any existing page. Avoids rewriting 127 entries (105 in excluded history, 22 on drafts) into GitHub URLs for no build benefit. The corpus-shape test enforces the published rule, so when #6932 or an author publishes a draft, any related entry into a draft is named by the test. Autonomous-run default after review finding; flagged for the operator.")
