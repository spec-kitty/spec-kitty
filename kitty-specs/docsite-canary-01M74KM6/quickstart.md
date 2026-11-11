# Quickstart: Docsite canary deploy

## Probe a site

```bash
PYTHONPATH=.:src python3 -m scripts.docs.site_live_probe https://docs.spec-kitty.ai
PYTHONPATH=.:src python3 -m scripts.docs.site_live_probe http://127.0.0.1:8000 --attempts 1   # a local build
```

One line per URL; exit 0 when every class passes, 1 otherwise, 2 when the sample cannot be derived.

## Run the canary (operator only)

1. Announce the window and freeze docs merges to `main`.
2. Actions, "Deploy Docs to GitHub Pages", Run workflow on `main`, tick `canary`.
3. Read the `canary-probe` job's report. The `deploy` job republishes DocFX afterwards in every case; check that `https://docs.spec-kitty.ai` serves DocFX again.
4. Lift the freeze.

## Tests

```bash
uv run --frozen pytest tests/docs/test_site_live_probe.py -q --tb=line
```
