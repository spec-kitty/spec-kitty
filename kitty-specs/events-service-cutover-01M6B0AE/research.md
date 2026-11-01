# Research: events-service cut-over

Evidence for every decision is in [research/code-grounding.md](research/code-grounding.md).

| # | Decision | Rationale | Alternatives considered |
|---|---|---|---|
| D-1 | Pin with `spec-kitty service vendor --service read-service --tag service-v0.1.0-rc.1` (default asset prefix `mission-status-api`). | The only sanctioned bump path (ADR D-3, `pins/README.md`). | Hand-written pin: forbidden. |
| D-2 | Unpack extras in `scripts/sync_services.py`, into `<cache>/<service>/<tag>/<archive-sha256>/`, from the verified cached archive only, with `tarfile` `filter="data"` plus explicit refusal of links and non-regular members; expose the path with `--extras-path <service>:<extra>`. | One owner for fetch, verify and unpack; digest-keyed, so a pin bump never reads a stale tree; no new HTTP point (the release-asset owner gate is untouched). | A new `kernel` function: fails `test_no_dead_symbols` (no `src/` caller). Copying the trees into the repository: contradicts plan Q5 ("fetched, not copied"). |
| D-3 | `--extras-only` on `sync_services.py` and an `extras-only` input on the composite action; `make dev-setup` uses it. | Contributors and conformance jobs need ≈230 KB, not a 95 MB binary; keeps the read service off contributor machines unless asked (DM `01M6B0JYP9B0CMBWRQ7TR7GBVN`). | Fetch everything everywhere: 95 MB per job/contributor for no test that uses it. |
| D-4 | A single test reader `tests/pinned_service_assets.py` that **fails** with `SERVICE_BINARY_MISSING … run make sync-services` when an extra is absent. | Charter SO #4 (no silent green); the packs precedent (`BuiltInPackMissing`). | `pytest.skip`: hides a missing fetch. |
| D-5 | Point the oracle's `Contract` at `bundle/<module>` and read single schemas by `title` from the resolved bundle. | `resolve(bundle dir)` equals `resolve(source dir)` for both modules (verified). | Keep a copy of the sources: duplicates events' authority. |
| D-6 | Delete the 25 tool unit tests, `test_mission_status_examples.py` and `test_mission_status_contract_1_1.py`. | They test code and layout owned by spec-kitty-events; the released tools differ from core's for 4 scripts and lack `tools/fixtures/`. Residual: port to events. | Run them against the released tools: they depend on fixtures the release does not ship. |
| D-7 | Nightly compare: a `ci-nightly.yml` job that fetches the host native build with the action and runs the existing compare script against it. | ADR D-6 (CI conformance against the released binary); live evidence 677/677 equal. | Keep the jar build: needs `services/`. Rely on events' nightly only: it compares events' jar, not the build core pins. |
| D-8 | acceptance-jvm Gradle check: a thin core wrapper `scripts/ci/acceptance_jvm_gradle_pin_check.py` calling the pinned tool's `check_acceptance_jvm(root)`. | The released CLI's bare run scans a `contracts/` subproject core no longer has. Residual: an acceptance-only flag upstream. | Patch the tool: events-side change (C-005). |

No `[NEEDS CLARIFICATION]` remains. No dependency decision is made, so no supply-chain or adversarial-evidence pass is owed.
