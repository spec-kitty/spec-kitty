# Contract: `site/moves.yaml`

```yaml
# round-trip: skip: illustration of the YAML ledger file shape, not a Pydantic model
# <provenance header: comments only>
kind: docs-moves-ledger
version: 1
moves:
  - {from: /old/route.html, to: /new/route.html, ref: "#1234"}
  - {from: /archived/page.html, to: /section/index.html, ref: "#3914", note: "archived, unpublished: section hub (ADR D-5 rule 4)"}
```

- `kind` must be `docs-moves-ledger` and `version` must be `1`, or readers refuse the file.
- Readers: `scripts/docs/moves_ledger.py` (`load_moves`, `collapse`, `validate`, `source_pairs`); later, the doc-kitty `redirects.json` generator (#6933).
- Writers: people, by appending entries. No tool rewrites the file.
- Derived output: `redirect_stub_generator.py regenerate-map` → `scripts/docs/redirect_map.yaml`; `check-map` exits 1 when that file is stale.
