# Contract: `scripts/sync_services.py` additions

Existing behaviour is unchanged (`--service`, `--offline`, `--check`; exit 1 with a `SERVICE_*` code on stderr).

- `--extras-only` — fetch (or with `--check`, verify) only the pin's extras, never a native build or the jar. Combinable with `--offline` and `--check`.
- Fetch mode also unpacks every verified extras archive into `<tag dir>/<archive sha256>/` (idempotent; an existing directory is reused).
- `--extras-path <service>:<extra>` — print the absolute extraction root of one extra (`contracts`, `contract_tools`, `fixtures`) and exit 0; it unpacks from the verified cache when needed but never downloads. Missing or mismatched archive → exit 1, `SERVICE_BINARY_MISSING` / `SERVICE_BINARY_DIGEST_MISMATCH` and the remedy `run make sync-services`. Unsafe archive member → exit 1, `SERVICE_ASSET_ARCHIVE_UNSAFE`.
- Python API used by tests and scripts (loaded by path): `extras_root(repo_root, service, extra, cache_root=None) -> Path` with the same refusals as `SyncServicesError`.

Composite action `.github/actions/sync-services`: new input `extras-only` (`"true"`/`"false"`, default `"false"`), passed as `--extras-only`.
