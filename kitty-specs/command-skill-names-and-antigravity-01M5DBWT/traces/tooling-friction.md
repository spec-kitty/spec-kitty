# Tooling friction

- **[2026-10-20][specify] Antigravity docs host unreachable.** `antigravity.google` fails DNS from the build container, so the workflows-to-skills guide could not be re-read; the spec records the Antigravity dotted-name behaviour as unverified (#6470). Workaround: rely on the issue's quoted guide and the spec-valid name.
- **[2026-10-20][specify] Container restart mid-planning.** A worker restart dropped one scout's delivered report; recovered from the task transcript. Disposition: workaround, no tracker item.
- **[2026-10-20][plan] Occurrence-map template vs schema.** The documented schema in docs/api/bulk-edit-gate.md shows `schema_version`/`mission` keys that the validator rejects as additional properties. Candidate gap (docs drift).
- **[2026-10-20][implement] Approval leaves status uncommitted.** On single_branch, `move-task --to approved` left status.events.jsonl/status.json and review-cycle-1.md uncommitted, so the next `implement` refused WRITE_CHECKOUT_DIRTY; committed with safe-commit. Candidate gap.
- **[2026-10-21][implement WP08] Test HOME hides the uv cache.** The per-worker isolated HOME starts with an empty uv cache, so the one real-`skills-ref` test (`uvx --offline`, never downloads) skips unless `UV_CACHE_DIR` points at a warm cache; run with `UV_CACHE_DIR=$(uv cache dir)` to exercise it. Disposition: documented in the test module, no tracker item.
- **[2026-10-21][implement WP08] `actionlint` not installed.** Ran it as `uvx --from actionlint-py actionlint .github/workflows/ci-router.yml` (clean). Disposition: workaround.
