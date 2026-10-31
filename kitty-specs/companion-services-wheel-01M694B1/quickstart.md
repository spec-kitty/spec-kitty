# Quickstart: companion services wheel

## For a user

```bash
pip install "spec-kitty-cli[services]"   # CLI plus the companion of the same version
spec-kitty service status                 # the write service resolves from the companion; no download
```

On an unsupported host the same command installs the binary-free fallback wheel, and the CLI fetches the service on first use, as before.

## For a maintainer (local build from the checkout's pins)

```bash
PYTHONPATH=src uv run --frozen python scripts/build_services_wheel.py --out dist-services
PYTHONPATH=src uv run --frozen python scripts/build_services_wheel.py --verify dist-services
```

While `pins/` holds no lockfile, this writes and verifies only the fallback wheel.
