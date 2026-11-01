# Data Model — Agent String Parser Hardening

Audience: software-engineer. Updated: 2026-10-30.

No stored entity changes. This page records the touched value shapes.

## Compact agent string (CLI value, not stored)

`tool:model:profile:role` — at most four `:`-separated segments; the bare `tool`
form is valid.

Validation rules after this mission:

| Segment | Rule |
|---|---|
| tool | stripped; blank after strip → `ValueError` (empty tool) |
| model | stripped; blank after strip → `None` |
| profile | stripped; blank after strip → `None` |
| role | stripped; blank after strip → `None` |
| count | more than four segments → `ValueError` naming the count |

## Structured actor (stored, unchanged shape)

`{tool: str|None, role: str|None, profile: str|None, model: str|None}` — written
by agent/operator status events since #6400. This mission only changes which
values the parser extracts from an explicit `--agent`; the dict shape, the event
envelope and the snapshot are untouched.

## Lenient builder input (free-text `--actor`, recorded identity)

Values with more than four segments, a `migration:` prefix, or an unparseable
tool are stored whole as `tool` (unchanged #6400 behavior).

## State transitions

None. The parser is pure: `str → (tool, model, profile, role) | ValueError`.
