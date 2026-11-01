# Contract note: the write service is called under `/api/v1`

**Authority**: `contracts/mission-write/openapi.yaml` in this repository (external contract
package; ADR `2026-10-27-1`). This mission changes **no** contract file: it makes the CLI
conform to the one that exists.

## The rule

The contract declares `servers: [{url: /api/v1}]`, so every operation is served at that
prefix plus the path the contract's `paths:` map declares. The launcher's loopback client
(`src/specify_cli/services/client.py`) therefore sends:

| Operation | Method and path | Client constant |
| --- | --- | --- |
| handshake | `GET /api/v1/handshake` | `HANDSHAKE_PATH` |
| health | `GET /api/v1/health` | `HEALTH_PATH` |
| shutdown | `POST /api/v1/shutdown` | `SHUTDOWN_PATH` |

`API_PREFIX = "/api/v1"` is the one place the prefix is written in `src/`; the three paths
are derived from it in `src/specify_cli/status/write_service_protocol.py` (the CLI's typed
view of the contract) and re-exported through the `specify_cli.status` facade.

The two work-package write paths (`/missions/{missionId}/work-package-transitions`,
`.../batch`, `/missions/{missionId}/inner-state-annotations`) are declared by the same
contract but are not sent by this client yet: the adapter binds at the lane-transition
cut-over (#6195). They are built from the same prefix when that lands.

## How the rule is enforced

- `tests/contract/test_mission_write_contract.py::test_the_client_prefix_is_the_contracts_server_url`
  — the client's prefix equals the contract's `servers[0].url`.
- `…::test_the_client_sends_the_pinned_constants_and_no_path_literal` — parses
  `services/client.py`: no string literal may reach `_get`/`_request`, and the path constants
  it sends are exactly the three above (a future operation with a literal fails).
- `…::test_every_path_the_client_sends_is_a_declared_path_under_that_prefix` — each path is
  the server url plus a path the contract declares, and the sent set equals the contract's
  `Service`-tagged paths.
- `…::test_the_path_check_reports_a_path_outside_the_contract` — positive control: a bare
  `/handshake` and a doubled `/api/v1/api/v1/...` are reported.
- `tests/specify_cli/services/test_client.py` — the transport, against a stand-in service
  that answers **only** the prefixed routes (so a bare path is a 404, as it is from the real
  `command-cli`).
