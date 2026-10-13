# Pre-merge fold verification (2026-10-13)

## Scope

This verification is independent of the fold implementers. It covers the pre-merge fold range `60b295202..050820812` on lane-b. Commits in that range:

- Java folds J1 to J14: `d3f20f13f..b2b7827d9`.
- Python, CI and workflow folds C1 to C8, merged as `050820812`.

Its findings F1 to F5 were fixed in `4dc35c7d5`.

## Verdict

PASS, once F1 to F5 are fixed. All 22 fold items were verified against their source findings, the rulings in `analyze.ruling.md` (2026-10-13 section), and live probes:

- Config-source vectors: cwd `config/`, `config/*/`, profile-specific files, `SPRING_CONFIG_NAME` and `-Dspring.config.location`.
- 20 hostile requests checked for path echo.
- Strict projection on every serving path.

## Gates at 050820812 (scratch worktree)

| Gate | Result |
|------|--------|
| `./gradlew --offline clean check`, contract bundle digest `fadf8a86…0effd` | `test` 2264, `perfTest` 14, `kitTest` 3, `nativeTagJvmTest` 3; 0 failures |
| `ruff check .` | green |
| `ruff format --check .` (3604 files) | green |
| `tests/ci` and `tests/contract` targeted suites | 319 passed, 1 failed (F1) |
| Implicated `tests/architectural` gates | 298 passed, 1 skipped |

## Findings and their fixes in 4dc35c7d5

| Finding | Severity | Fix |
|---------|----------|-----|
| F1: perf test class missing `@Tag("perf")` | high | tag added |
| F2: README attestation text stale | low | rewritten |
| F3: README overstated the config pin | info | narrowed |
| F4: malformed query percent-encoding returned 500 | info | now 400 Problem, red-first `MalformedQueryTest` |
| F5: orphaned Javadoc block | nit | merged |

## After the fixes

- `./gradlew --offline clean check`: green.
- `test_mission_status_api_build.py`: 156 passed.
- Gate checks: 29 passed.
- Conformance: 54 passed.
- `test_no_tmp_paths_in_tests.py`: 4 passed.
- `test_no_manual_global_state_mutation.py`: 44 passed.
- `ruff`: green.
- `nativeCompile` and `nativeSmoke`: green. The smoke digest `7007f777…ebb6` is unchanged.
