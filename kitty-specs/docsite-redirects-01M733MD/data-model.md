# Data Model: Docsite legacy redirects

- **Legacy map** (`site/legacy-redirects.json`): a flat JSON object, sorted by key.
  - Key: a legacy route (`/a/b.html`, leading slash, ends in `.html`).
  - Value: a live directory route (`/a/b/`, or `/` for the root).
  - No comment key; doc-kitty validates every key.
- **Baseline route**: one line of `site/url-baseline.txt`.
- **Move**: one `{from, to, ref, note}` row of `site/moves.yaml`; `collapse` maps each `from` to its chain's final route.
- **Live set**: `route_of(rel)` for every `docs/**/*.md`, minus `unpublished_routes(docs)`.
- **Redirect stub**: doc-kitty's flat page at `<dist>/<key>`, recognised by `redirect_stub_target(html)`, which returns the refresh target or `None`.
