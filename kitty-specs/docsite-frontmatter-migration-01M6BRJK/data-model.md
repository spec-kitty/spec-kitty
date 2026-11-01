# Data model: frontmatter shapes

| Field | Before | After | Owner of the rule |
| --- | --- | --- | --- |
| `audience` | `docs/context/audience/<p>.md` (scalar or list) or free text | `[{profile: <p>, guidance_text: "Written for the <Persona title> reader."}]` | `_dockitty_contract.profile_of_path` |
| `related` | repo paths | slugs of published pages | `_dockitty_contract.slug_of`, `is_published` |
| `external_references` | absent | `[{url: https://github.com/spec-kitty/spec-kitty/blob/main/<path>, title: <title or path>}]` | migration |
| ADR `doc_status` | absent | `Accepted`/`Proposed` → `active`; `Superseded` → `superseded` | migration (`ADR_DOC_STATUS`) |
| ADR `kind` | absent | `ADR` | migration |

**Slug.** `docs/<p>.md` → `<p>`; a trailing `/README` or `/index` is removed (`docs/index.md` → the
root slug, written `index` by doc-kitty's `ROOT_ENTRY_ID`; no current `related` entry names it).

**Invariants.**
- Bytes after the closing frontmatter fence never change.
- Lines outside the rewritten blocks never change.
- Re-running the migration changes nothing.
- A `related` entry names a published page; anything else is an external reference.
