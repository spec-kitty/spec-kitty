# Data model: frontmatter shapes

| Field | Before | After | Owner of the rule |
| --- | --- | --- | --- |
| `audience` | `docs/context/audience/<p>.md` (scalar or list) or free text | `[{profile: <p>, guidance_text: "Written for the <Persona title> reader."}]` | `_dockitty_contract.profile_of_path` |
| `related` | repo paths | slugs of pages doc-kitty resolves for the source (published source: published pages; draft source: non-excluded pages; excluded source: any page) | `_dockitty_contract.slug_of`, `is_published`; `Corpus.related_target_allowed` |
| `external_references` | absent | `[{url: https://github.com/spec-kitty/spec-kitty/blob/main/<path>, title: <title or path>}]` | migration |
| ADR `doc_status` | absent | `Accepted`/`Proposed` → `active`; `Superseded` → `superseded` | migration (`ADR_DOC_STATUS`) |
| ADR `kind` | absent | `ADR` | migration |

**Slug.** `docs/<p>.md` → `<p>`; a trailing `/README` or `/index` is removed (`docs/index.md` → the
empty slug, as doc-kitty's `slugFromEntryId` keys it; 12 pages name it and are written `- ''`).
Index basenames match case-insensitively, as in doc-kitty's `indexBasenamePattern`.

**Invariants.**
- Bytes after the closing frontmatter fence never change.
- Lines outside the rewritten blocks never change.
- Re-running the migration changes nothing.
- A `related` entry names a page doc-kitty resolves when it builds the source page; anything else is an external reference or dropped.
