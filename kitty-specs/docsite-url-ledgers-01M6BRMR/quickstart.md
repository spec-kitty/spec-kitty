# Quickstart: record a docs move

1. Move the page (`git mv docs/a/old.md docs/b/new.md`).
2. Append to `site/moves.yaml`:
   `  - {from: /a/old.html, to: /b/new.html, ref: "#<issue>"}`
   If `/a/old.html` is not yet in `site/url-baseline.txt`, it is added in step 3.
3. Regenerate DocFX's map and check the ledgers:
   ```bash
   python3 scripts/docs/redirect_stub_generator.py regenerate-map
   python3 scripts/docs/redirect_stub_generator.py check-map
   uv run --frozen pytest tests/docs/test_moves_ledger.py -q
   ```
   The test names any key missing from the baseline; add it in sorted position.
4. A new page: append its route to `site/url-baseline.txt` in the same PR. The deploy job warns about any it finds missing.
5. Never edit or delete an existing ledger line. A further move of the same page is a new entry from its previous route.
