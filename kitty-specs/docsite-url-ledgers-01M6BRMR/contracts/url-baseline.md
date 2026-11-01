# Contract: `site/url-baseline.txt`

- One route per line, leading slash, sorted; blank lines and lines starting with `#` are ignored (doc-kitty's baseline format).
- The header records the sources (DocFX walk of a named commit, the derived map keys), the exclusions (`/kitty-specs/**`, `/toc.html`) and the amendments inherited from `scripts/docs/redirect_baseline_urls.json`.
- Readers: `moves_ledger.load_baseline`; `redirect_stub_generator.py coverage` and `baseline-drift`; later, `dockitty-check-redirect-coverage` (ADR D-11).
- Grows on publish. A route is removed only by a recorded amendment.
