# Quickstart: verify the sdist anchor

```bash
make sync-packs
uv build --sdist -o /tmp/sd
tar tzf /tmp/sd/*.tar.gz | sed 's|^[^/]*/||' | grep -E '^(docs|kitty-specs|site)/'   # expect no output
tar tzf /tmp/sd/*.tar.gz | sed 's|^[^/]*/||' | grep -E '^(README|CHANGELOG)\.md$'     # expect both
uv run --frozen pytest tests/cross_cutting/packaging/test_packaging_safety.py -q
```
