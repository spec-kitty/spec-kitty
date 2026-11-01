# REASONS Canvas — Write service API prefix

> Mission: `write-service-api-v1-prefix-01M6BTXH`
> Source: [#6910](https://github.com/spec-kitty/spec-kitty/issues/6910). [spec.md](spec.md) is authoritative; this canvas is non-governing and advisory.

## Requirements

- **Problem.** `contracts/mission-write/openapi.yaml` serves every operation under `/api/v1`; the launcher's client sends bare `/handshake`, `/health` and `/shutdown`, so it would 404 against the real `command-cli`. The operator ruled on 2026-10-31 (spec-kitty-events#156) that the contract wins.
- **Decision (spec § Problem, C-001).** The client conforms to the contract: one prefix constant equal to the contract's `servers` url, every operation path derived from it.
- **Acceptance.** Spec FR-001 … FR-004, SC-001 … SC-003: the three calls succeed against a stand-in that serves only the prefixed routes, a contract test pins every sent path to `<server url>/<declared path>`, and no bare path literal remains in `src/specify_cli/services/`.
- **Definition of done.** Proven red-first through the real entry point (`ServiceClient` against the stand-in service), the pin fails on a bare or doubled path, changelog and the client/launcher/ADR wording state the prefix.

## Entities

- **API prefix** — `/api/v1`, the contract's `servers[0].url`. One constant in `specify_cli.status.write_service_protocol`; never repeated as a literal.
- **Write-service path** — an operation path the client sends: the prefix plus a path the contract declares. Today three; the two work-package write paths bind at #6195 from the same prefix.
- **Stand-in write service** — the launch-contract test double in `tests/specify_cli/services/fake_service.py`; it must answer exactly what the contract declares, or it shadows transport drift.

## Approach

- Additive and local: path constants beside the existing protocol constants, imported by the client; the transport, shapes and refusal vocabulary are untouched.
- The pin lives in the existing contract test that already resolves the module, so the contract stays the single authority and no second path list appears in tests.

## Structure

- `src/specify_cli/status/write_service_protocol.py` — `API_PREFIX` and the three operation paths.
- `src/specify_cli/services/client.py` — sends the constants; docstrings name the prefixed operations.
- `tests/specify_cli/services/fake_service.py`, `test_client.py` — stand-in and garbage handler serve/key on the prefixed routes.
- `tests/contract/test_mission_write_contract.py` — the path pin and its positive control.

## Operations

- Research → specify → plan → tasks → red-first implement/review → accept → local consolidation → aggregate review → changelog/docs → draft PR → CI green → ready for review. The operator merges.
