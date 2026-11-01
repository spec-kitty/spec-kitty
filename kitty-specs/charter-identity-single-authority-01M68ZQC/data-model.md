# Data model: Charter identity single authority

No persisted data changes. The entities below are the in-memory shapes this Mission moves
the rule into; none of them is serialized, and none outlives its invocation (C-003).

## IdentityEntry (existing)

One artifact file as the index sees it: `kind`, `stem` (the file stem), `declared_id` (the
file's `id:` field), `layer` (`project` | `org` | `built-in`) and `path`. Ordered by layer
precedence: project, then org packs last-declared-first, then built-in.

## IdentityIndex (existing; new methods were not added to the file — one public lookup was
  split out)

The per-invocation authority. This Mission leans on and, where noted, exposes:

| Member | Direction | Semantics |
| --- | --- | --- |
| `declared_id(kind, token)` | stem / declared id / URN → declared id | stem first, then declared id, then (directives) the normalised id |
| `stem(kind, token)` | token → activation stem | directives id-first, other kinds stem-first |
| `stem_for_declared_id(kind, id)` | declared id / URN → stem | id-first; tries a directive id verbatim then normalised; a directive stem must round-trip and be unambiguous |
| `has_declared_id(kind, token)` | declared id test | literal or normalised directive id |
| `names_a_file(kind, token)` | stem test | whether the token is a file stem (first-match precedence, no round-trip requirement) |

## Facade (existing public functions, now index-backed)

`resolve_artifact_urn` (token → URN), `resolve_config_id` (URN → stem) and
`resolve_selected_id_to_stem` (selection → stem). They add no state; each builds (or, with
a `ResolutionPass`, reuses) one index over the roots its caller passed.

## ResolutionPass (existing; one field added)

A pass-scoped memo: `scans` (layer scan per roots), `ids` (canonical parse per file) and the
new `indexes` (one index per root set). Nothing in it survives its pass.
