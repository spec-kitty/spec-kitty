# Quickstart

```bash
make dev-setup              # uv sync + make sync-packs
make sync-packs             # fetch/verify packs/built-in and packs/internal
spec-kitty charter pack vendor --pack built-in --ref <sha> --subtree packs/built-in   # bump pin
python scripts/sync_packs.py --check                                                  # CI pin gate
uv build && python -m zipfile -l dist/*.whl | grep packs/built-in | head
```
