# Research: CLI to write-service protocol

Sources: a two-agent research squad over the repository (2026-10-27): the contract tooling and the
CLI's write-path refusals. Every claim cites the file it came from.

## R-1 Where contracts live and what a module must satisfy

- **Decision**: a new module `contracts/mission-write/`, auto-discovered by every contract tool and
  by `contracts/build.gradle` (`listFiles()`); no workflow matrix edit is needed.
- **Findings**: `example_check` exits 2 without a `required_examples.json` entry
  (`contracts/tools/example_check.py`, `MANIFEST_MODULE_MISSING`); `bundle.py`, `resolver_parity.py`
  and `release_check.py` require at least 5 path items (`DEFAULT_MIN_PATHS = 5`); every property,
  request bodies included, needs `x-source` or `x-derived` (`citation_check.py`); vacuum's
  `enum-case` rule allows only snake_case or PascalCase enum values (`contracts/lint/ruleset.yaml`);
  `non-2xx-is-problem` requires every refusal to compose `Problem`; response objects are closed.
- **Consequence**: UPPER_SNAKE codes and reason URNs are written as `oneOf` of `const`, each with a
  description, not as `enum`.

## R-2 Declaring the bearer scheme

- **Decision**: amend `layout_check.check_bundles` to admit a root `components` whose only key is
  `securitySchemes`; any other component key keeps the `TRACKED_BUNDLE` refusal (operator ruling).
- **Finding**: `layout_check.py` refuses any root `components` (`TRACKED_BUNDLE`); no
  `securitySchemes` exists anywhere under `contracts/`.
- **Alternatives**: an `x-` extension plus prose (declined: generated clients would not send the
  header).

## R-3 Refusal codes on today's write paths

- **Decision**: reuse the CLI's codes verbatim; mint provisional reason URNs for guards; mark
  protocol-only codes (operator ruling `guard_refusal_codes`).
- **Findings**: guard and state-machine refusals are a free-text `TransitionError`
  (`status/emit.py`, `status/transitions.py`, `status/wp_state.py`); the only machine codes for
  them are the `orchestrator-api` edge literals (`orchestrator_api/wp_lifecycle.py`:
  `TRANSITION_REJECTED`, `WP_ALREADY_CLAIMED`, `DEPENDENCIES_NOT_SATISFIED`, `WP_NOT_FOUND`).
  Placement, lock and durability failures carry codes in class attributes across
  `coordination/types.py`, `coordination/policy.py`, `coordination/transaction_errors.py`,
  `coordination/surface_resolver.py`, `coordination/status_transition.py`, `status/locking.py`,
  `status/store.py`. There is no single registry.
- **Consequence**: the parity inventory is the first single map of these codes; its test reads
  each cited source file for the literal.

## R-4 The EventBridge port today

- **Finding**: `runtime/next/event_bridge.py` defines `WorkPackageTransition(write_location, rows,
  write_contract)` and `WorkPackageTransitionPort.record_work_package_transition`; the unit is the
  append only. `register_runtime_emitter_factory` binds the other half
  (`runtime/next/_internal_runtime/events.py`). Both binders are allowlisted as dead until #6675.
- **Decision**: one binder `bind_event_bridge` beside `register_runtime_emitter_factory`; the
  shapes in `specify_cli.status` (issue comment item 2).

## R-5 Read service precedent

- **Finding**: `services/mission-status-api/README.md` binds `127.0.0.1` only, refuses a foreign
  `Host`, a foreign `Origin` and `Sec-Fetch-Site: cross-site` with `403 request_refused`. It has no
  token and writes no file.
- **Decision**: the write service keeps the same guard and adds the bearer token; the guard's
  refusal is `REQUEST_REFUSED`.

## R-6 Toolchain

- **Finding**: the contract toolchain runs on a JDK 21 (the Contracts workflow uses Temurin 21);
  the read service needs GraalVM/JDK 25. This Mission touches no service, so JDK 21 (present) is
  the one needed.
