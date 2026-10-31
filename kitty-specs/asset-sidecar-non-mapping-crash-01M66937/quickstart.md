# Quickstart: asset-sidecar-non-mapping-crash-01M66937

## Reproduce the defect (pre-fix)

```bash
uv run python - <<'EOF'
import tempfile
from pathlib import Path
from charter.offering.assets.repository import AssetRepository

with tempfile.TemporaryDirectory() as td:
    org = Path(td) / "org" / "assets"
    org.mkdir(parents=True)
    (org / "bad.asset.yaml").write_text("- a\n")
    AssetRepository(Path("packs/built-in/assets"), org_dirs=[org])
    print("loads with warnings, no crash")
EOF
```

Pre-fix main: `AttributeError: 'list' object has no attribute 'get'`.
After the fix: the sidecar is skipped with a
`Skipping invalid org asset bad.asset.yaml: expected a YAML mapping, got list`
warning and construction succeeds.

## Verify the fix

```bash
# per-kind regression matrix (red on pre-fix main, green after)
uv run pytest tests/charter_offering/test_non_mapping_sidecar_skip.py -q

# existing base-layer behaviour unchanged (ratchet)
uv run pytest tests/charter_offering/test_base_org_layer.py -q
```
