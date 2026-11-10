# Quickstart: Docsite legacy redirects

```bash
PYTHONPATH=.:src python3 -m scripts.docs.site_redirects          # regenerate site/legacy-redirects.json
PYTHONPATH=.:src python3 -m scripts.docs.site_redirects --check  # exit 1 when the committed map is stale
make docs-site                                                   # build, built-site check, both coverage runs, self-test
```

When you move a page, append the move to `site/moves.yaml` and regenerate the map. When you draft or archive a page, just regenerate: its URL then redirects to the section hub.
