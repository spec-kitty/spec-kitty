# Research

## Sources (all on main or in history before #5545)

- The removed dashboard: `git show 3d5c85d09^:src/specify_cli/dashboard/handlers/{router,api,features,glossary,lint,static}.py`
  and `git show 3d5c85d09^:src/specify_cli/dossier/api.py`. The full mapping is in [route-inventory.md](route-inventory.md).
- The contract: `contracts/mission-status/paths/missions_missionId_artifacts.yaml`,
  `missions_missionId_artifacts_content.yaml`, the `Artifact*` schemas, responses and examples (added by #5625).
- The reference: `tests/contract/_mission_status_artifacts.py`, which uses `contracts/tools/leak_patterns.py`
  (`SECRET_PATTERNS`, `HUMAN_HOST_PATH_PATTERNS`, `redact_emails`) and `contracts/tools/leak_scan.py`
  (`malformed_artifact_path`).
- The service: `services/mission-status-api/` (README, `Allowlist`, `SafeFiles`, `Listing`, `LeakClasses`, the
  `leak-patterns.json` generated from the Python patterns).
- ADR `docs/adr/4.x/2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md`: D-2, D-4/D-5/D-7 amended, D-9 to
  D-11. The route table there left the artifact surface to a follow-up; the contract (#5625) and this Mission fill it.

## Findings

- The service treats artifacts as out of scope today: `OutOfScopeRoutesTest` and the README "Routes and scope" section.
- No artifact golden exists. The existing conformance goldens cover `/project`, `/missions` and the stream.
- Baseline of the service on main: `./gradlew test` ran 2338 tests, 0 failed, 4 skipped (GraalVM CE 25.0.2, `LC_ALL=C.UTF-8`).
