# Data model

## Route

A site-relative published path in its legacy DocFX form, with a leading slash: `/guides/x.html`, `/adr/1.x/index.html`, `/adr/1.x/README.html`.

- Page route ↔ source: `/<rel>.html` ↔ `docs/<rel>.md`.
- DocFX map form: the route without its leading slash.

## Move (entry of `site/moves.yaml`)

| Field | Required | Meaning |
|---|---|---|
| `from` | yes | The old route. Unique across the ledger. |
| `to` | yes | The route that replaced it; may itself be a later `from` (a chain). |
| `ref` | yes | Provenance: a PR, issue or Mission handle. |
| `note` | no | One-line reason (for example "archived, unpublished: section hub, ADR D-5 rule 4"). |

**Invariants** (checked by `moves_ledger.validate`):

1. No duplicate `from`.
2. No cycle.
3. A collapsed target is a published route (page or section hub).
4. No `from` is a published route.
5. Append-only. Review enforces it, since a PR's diff to the file must only add lines. Recorded history is never edited.

## Baseline (`site/url-baseline.txt`)

A sorted, de-duplicated set of routes plus `#` comment lines.

**Invariants**:

1. It contains every URL of `scripts/docs/redirect_baseline_urls.json` and every key of the derived map.
2. Every route in it is published or is a derived map key with a published target (PR-time mirror of `coverage`).
3. A route leaves only with an amendment recorded in the header (date, PR, ground, ruling).

## Derived redirect map (`scripts/docs/redirect_map.yaml`)

`{from (no slash): collapsed to (no slash)}` for every ledger entry, sorted, behind a header naming the ledger. It is never hand-edited, and `check-map` proves it is current.
