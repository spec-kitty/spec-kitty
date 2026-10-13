# Quickstart: working on the Mission Status API service

All commands run from the repository root checkout unless stated. Use `.venv/bin/...`; never a bare `uv run`.

Numbering note: in the work-package numbering of tasks.md the Gradle scaffold is WP03 and the spike is WP02; see `tasks-overview.md` section 1.

## Python side (oracle and CI pins)

- Regenerate goldens: `.venv/bin/python -m tests.contract._mission_status_conformance --write`
- Check goldens equal live Python: `PWHEADLESS=1 .venv/bin/python -m pytest tests/contract/test_mission_status_conformance.py -m "corpus and not windows_ci" -q`
- Routing, workflow and gate-helper pins: `.venv/bin/python -m pytest tests/ci/test_mission_status_routing.py tests/ci/test_mission_status_api_build.py tests/ci/test_mission_status_gate_checks.py -q`
- What would my diff select in CI: `.venv/bin/python scripts/ci/local_gate_parity.py --base-ref origin/main`
- Contextive glossary files stay in sync (no change expected): `.venv/bin/python scripts/generate_contextive_glossaries.py check` (after a `docs/context` edit run `generate` first)
- Baseline for ordinary changes: `make test-fast` (record its counts; never `make test-full`, a bare `tests/architectural/` or `tests/e2e/` during mission work)
- Read-only Sonar survey of a touched Python file: `bash scripts/ci/sonarcloud_branch_review.sh issues --file <path>`

## Java side (JDK 25 on PATH)

- `cd services/mission-status-api && ./gradlew check` (unit, ArchUnit, adapters, contract validation, goldens, JaCoCo rule)
- `./gradlew nativeCompile nativeTest` (runs only the `native`-tagged subset) then `./gradlew nativeSmoke -PnativeBinary=<path to the binary>`
- The served contract document (contract-first, bundled at build time, no springdoc): `curl http://127.0.0.1:8787/api/v1/openapi.yaml` against a running service (curl sends the accepted `Host` form `127.0.0.1:8787`)
- Run against a project: `java -jar build/libs/mission-status-api.jar --mission-status.project-root=<project root> --mission-status.port=8787` (Spring Boot command-line properties are `--name=value`; the jar name is pinned in `build.gradle.kts` by WP03 and the command is run once on the skeleton jar there; plan.md section 13, Bind; loopback only; `localhost` clients that try `::1` first fall back to `127.0.0.1`)

## Before pushing

Run the commands of plan.md section 5, including `make test-fast`. Do not run full-suite targets during mission work. Append to the tracer files under `kitty-specs/mission-status-read-api-overview-01M4EMSA/traces/` at the moment friction or a decision occurs (format in the procedure `mission-tracer-files`).
