# Data model

## HistoricalRenderList (package data, JSON)
```json
{"schema_version": 1,
 "sources": ["src/doctrine/skills", "src/charter/offering/skills"],
 "renders": {"<skill>/<relative path>": ["<sha256 hex>", "..."]}}
```
- Keys use `/`, no `..`, no leading `/`. Values sorted, unique, 64 lowercase hex chars.
- Invariant: append-only across regenerations; contains every current render (raw; for `SKILL.md` also shared + native projection).

## Global asset inventory (`~/.kittify/cache/<owner>-assets.json`)
- schema 1 (read only): `{"schema_version": 1, "entries": {"<anchor-relative posix>": FileState}}`
- schema 2 (written): `{"schema_version": 2, "entries": {"<absolute posix>": FileState}}`
- Transition: first assessment that reads schema 1 rewrites schema 2 (once).

## Kept file report (in-memory; doctor output)
| field | meaning |
|---|---|
| path | absolute path of the kept file |
| kind | `stale_canonical` (canonical skill file, unproven) · `edited_retired` (retired skill content not proven) · `old_root_leftover` (proven copy under the old home root) |
| reason | disposition reason |
| remedy | one line: what the user can do |

## New doctor finding codes (append-only public JSON)
- `global-skill-kept-stale` (warning)
- `retired-skill-kept-edited` (warning)

## VerifyReport / VerifyResult additions
- `command_installer.VerifyReport.outdated: list[str]` — disk == manifest hash != canonical render.
- `verifier.VerifyResult.retired: list[ManagedFileEntry]` — entry's skill absent from a non-empty registry, file present; counted in `ok`.
