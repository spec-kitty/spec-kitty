# Quickstart

```bash
# Report what would change (no writes)
python -m scripts.docs.dockitty_frontmatter_migration --check
# Apply (idempotent; frontmatter only)
python -m scripts.docs.dockitty_frontmatter_migration --apply
# Prove the diff is frontmatter-only against a base
python -m scripts.docs.dockitty_frontmatter_migration --verify-against origin/main
# Readers on the new shapes
python -m scripts.docs.audience_resolver --strict
python -m scripts.docs.related_validator --strict
```

One-off doc-kitty build: see `build-evidence.md` (written at the end of the mission).
