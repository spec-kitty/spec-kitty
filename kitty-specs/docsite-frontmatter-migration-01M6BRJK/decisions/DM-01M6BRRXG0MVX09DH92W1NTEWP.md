# Decision Moment `01M6BRRXG0MVX09DH92W1NTEWP`

- **Mission:** `docsite-frontmatter-migration-01M6BRJK`
- **Origin flow:** `specify`
- **Slot key:** `specify.related.unpublished-targets`
- **Input key:** `related_unpublished_targets`
- **Status:** `resolved`
- **Created:** `2026-11-01T14:38:47.296504+00:00`
- **Resolved:** `2026-11-01T14:39:20.449927+00:00`
- **Opened by:** `cli`
- **Other answer:** `true`

## Question

A published page's related entry that names a draft or excluded page is build-fatal. Move it into the body as a link, drop it, or move it to external_references as a repository URL?

## Options

- external_references with a GitHub repository URL (frontmatter-only)
- Body link
- Drop
- Other

## Final answer

external_references with a GitHub repository URL and the target's title, for every related entry that is not a published page (outside docs/, non-Markdown, draft, excluded). Frontmatter-only, so immutable bodies stay byte-identical, and no dead site link is added. A related entry whose target file no longer exists is dropped. Deviates from the issue's literal 'body link or drop'; flagged for the operator in the PR.

## Rationale

_(none)_

## Change log

- `2026-11-01T14:38:47.296504+00:00` — opened
- `2026-11-01T14:39:20.449927+00:00` — resolved (final_answer="external_references with a GitHub repository URL and the target's title, for every related entry that is not a published page (outside docs/, non-Markdown, draft, excluded). Frontmatter-only, so immutable bodies stay byte-identical, and no dead site link is added. A related entry whose target file no longer exists is dropped. Deviates from the issue's literal 'body link or drop'; flagged for the operator in the PR.")
