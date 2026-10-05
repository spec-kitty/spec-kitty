# Quickstart: verify the mirrored terms

```bash
uv run spec-kitty glossary list | grep -E "tool-surface drift|integrating worktree|target-owned bookkeeping"
uv run spec-kitty doctrine regenerate-graph --check
uv run pytest tests/architectural/test_glossary_pack_parity.py tests/architectural/test_pack_manifest_no_author_edit.py tests/architectural/test_builtin_pack_provenance_ratchet.py -q
```
