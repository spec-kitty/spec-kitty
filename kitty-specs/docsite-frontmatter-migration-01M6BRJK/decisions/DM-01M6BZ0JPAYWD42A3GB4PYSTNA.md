# Decision Moment `01M6BZ0JPAYWD42A3GB4PYSTNA`

- **Mission:** `docsite-frontmatter-migration-01M6BRJK`
- **Origin flow:** `plan`
- **Slot key:** `plan.excluded.not-migrated`
- **Input key:** `excluded_folders_migrated`
- **Status:** `resolved`
- **Created:** `2026-11-01T16:27:49.834333+00:00`
- **Resolved:** `2026-11-01T16:27:52.694079+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should pages in the excluded folders (archive, reports, convergence) be migrated to the new shapes so readers carry one shape, or left untouched?

## Options

- Leave untouched; readers skip excluded folders as doc-kitty gates do
- Migrate them too
- Other

## Final answer

Leave untouched. A reviewed evidence bundle under docs/archive is byte-pinned by tests/architectural/test_archive_root_byte_identical.py; doc-kitty never reads excluded folders and its own gates skip them (ADR D-8). Readers and the shape test skip them too, so each still carries one shape for the pages they judge. Reverses the earlier assumption 'excluded trees are migrated too'.

## Rationale

_(none)_

## Change log

- `2026-11-01T16:27:49.834333+00:00` - opened
- `2026-11-01T16:27:52.694079+00:00` - resolved (final_answer="Leave untouched. A reviewed evidence bundle under docs/archive is byte-pinned by tests/architectural/test_archive_root_byte_identical.py; doc-kitty never reads excluded folders and its own gates skip them (ADR D-8). Readers and the shape test skip them too, so each still carries one shape for the pages they judge. Reverses the earlier assumption 'excluded trees are migrated too'.")
