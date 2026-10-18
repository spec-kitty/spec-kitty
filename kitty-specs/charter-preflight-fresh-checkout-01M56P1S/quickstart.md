# Quickstart: verifying the charter preflight fresh-checkout fix

## Reproduce the bug (pre-fix, on `main`)

```bash
# In a clone of spec-kitty whose committed manifest stamp lags charter.yaml:
.venv/bin/python -c "
from pathlib import Path
from charter.bundle import compute_bundle_content_hash
from charter.activation.synthesizer.manifest import load_yaml, MANIFEST_PATH
m = load_yaml(Path('.') / MANIFEST_PATH)
print('stamped   :', m.bundle_content_hash)
print('recomputed:', compute_bundle_content_hash(Path('.')))
"  # → the two differ (drift)

.venv/bin/python -c "
from pathlib import Path
from specify_cli.charter_runtime.freshness.computer import compute_freshness
print(compute_freshness(Path('.')).synthesized_drg.state)
"  # → 'stale'  (pre-fix: spec-kitty next then exits CHARTER_PREFLIGHT_FAILED)
```

## Verify the fix

1. **Read-path heal (advancing `next`)** — a fresh/cloned owned checkout whose stamp lags but whose
   artifacts are consistent runs `next` at rc=0; the manifest is re-stamped in place:
   ```bash
   spec-kitty next --mission <m> --owned-checkout <dir> --json   # rc=0, no CHARTER_PREFLIGHT_FAILED
   ```
2. **Query mode does not mutate**: `spec-kitty next --mission <m>` (no `--result`) leaves the manifest
   byte-unchanged.
3. **Genuine inconsistency still blocks**: corrupt a listed artifact so `manifest.verify` fails → `next`
   surfaces an actionable `blocked_reason`, no silent green.
4. **Write-side parity**: after `spec-kitty charter activate <...> --cascade all`,
   `compute_bundle_content_hash(repo) == manifest.bundle_content_hash`.
5. **This repo's committed parity**:
   ```bash
   .venv/bin/python -c "from pathlib import Path; from charter.bundle import compute_bundle_content_hash; from charter.activation.synthesizer.manifest import load_yaml, MANIFEST_PATH; print(compute_bundle_content_hash(Path('.')) == load_yaml(Path('.')/MANIFEST_PATH).bundle_content_hash)"
   # → True
   ```

## Blast-radius tests (this mission)

```bash
PYTHONPATH="$PWD/src:$PWD" .venv/bin/python -m pytest tests/charter_runtime/ -q
PYTHONPATH="$PWD/src:$PWD" .venv/bin/python -m pytest tests/charter/ tests/charter_offering/ -q
make test-fast
# Do NOT run `make test-full`; do NOT regenerate .github/ci-shard-timings.json (CI-owned).
```
