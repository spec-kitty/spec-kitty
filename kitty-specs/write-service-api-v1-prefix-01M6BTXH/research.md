# Research: write service API prefix (#6910)

Discovery for mission `write-service-api-v1-prefix-01M6BTXH`. Small, contained fix; the
evidence below is what specify/plan build on.

## Decision 1 — the contract's `servers` entry is the single source of the prefix

**Evidence**

- `contracts/mission-write/openapi.yaml:17-18` declares `servers: [{url: /api/v1}]`; its
  `paths:` map lists `/handshake`, `/health`, `/shutdown`,
  `/missions/{missionId}/work-package-transitions`,
  `/missions/{missionId}/work-package-transitions/batch` and
  `/missions/{missionId}/inner-state-annotations`. Under OpenAPI 3.1 a path is resolved
  against the server url, so the served routes are `/api/v1/<path>`.
- `docs/adr/4.x/2026-10-27-1-the-write-service-protocol-is-loopback-http-with-a-bearer-token.md:63`
  says the contract "is served under `/api/v1`"; D-4 writes the operations without the
  prefix because it documents them relative to the server url.
- Operator ruling 2026-10-31 (spec-kitty/spec-kitty-events#156), quoted in the issue: the
  contract wins, `command-cli` serves `/api/v1/*`.

**Decision**: the client derives every path from one `API_PREFIX` constant that equals the
contract's server url, and the contract test asserts that equality. The client is the
conforming side.

## Decision 2 — the drift survived because the stand-in service shadowed it

**Evidence**

- `src/specify_cli/services/client.py:96,109,121` sends `/handshake`, `/health`,
  `/shutdown`.
- `tests/specify_cli/services/fake_service.py:142-155` (the stand-in "written to the
  launch contract") answers exactly those bare paths, so every existing client test
  passed against a service that does not match the write-service contract.
- `tests/specify_cli/services/test_client.py:113` keys its garbage handler on
  `self.path == "/handshake"`, and both `tests/specify_cli/services/test_launcher.py`
  and `test_service_cli.py` drive the same stand-in.
- No test tied a client path string to `contracts/mission-write`; the contract test
  (`tests/contract/test_mission_write_contract.py:44-51`) pins the *operation list* but
  never looks at the client's transport paths or at `servers`.

**Decision**: red first, through the pre-existing entry point. Move the stand-in service
to the contract's prefixed routes (it claims to follow the contract already), observe the
unchanged client fail against it with the 404 that the real service would give, then fix
the client. The stand-in is test infrastructure, so aligning it with the contract is part
of the fix, not a gate weakening: it makes the double stricter, never looser.

## Decision 3 — no other client operation exists yet, so the prefix must be structural

**Evidence**

- `specify_cli.status.write_service_protocol` holds the typed shapes of the two
  work-package write operations and the batch, but carries no transport; the adapter
  binds at the lane-transition cut-over (#6195, still open — `gh issue view 6195`).
- `src/specify_cli/services/client.py` therefore sends three operations, and only three.

**Decision**: define the prefix plus the three paths in the protocol module (the typed
view of the contract, where the "client-side shapes" already live) and import them in the
client. Adding a fourth path is then a prefixed constant by construction. A helper used
only by tests would be a dead symbol under the `test_no_dead_symbols` gate; a function
imported by the client would be live but contrived, so the pin test derives the prefix
from the contract tree and compares it to the client constant instead.

## Decision 4 — the pin lives in the contract test file

**Evidence**

- `tests/contract/test_mission_write_contract.py` already resolves the contract module
  through `contracts/tools/contract_resolver.py` (`tree` fixture) and owns every
  contract-vs-client parity check (operations, security, header, refusal vocabulary).
- The resolved tree exposes `tree["servers"]` and `tree["paths"]`, exactly what the pin
  needs, with no new fixture and no new dependency.

**Decision**: add the pin there: the client's prefix equals `tree["servers"][0]["url"]`,
every path the client can send is that prefix plus a declared path, and a positive
control shows a bare or doubled path is reported as not conforming. The mirror check in
`test_client.py` (no bare path literals left in the client) is covered by the transport
tests against the prefixed stand-in.

## Open questions

- None blocking. The docs touch is limited to the client/launcher module docstrings and
  the ADR line that names the prefix, so the doc surface stays honest without regenerating
  the CLI reference (shared machine asset cache, see the operator brief).

## Reproduction note

A real `command-cli` binary is not vendored in this checkout (`services/` holds only the
Mission Status Read API; the write core lives in `spec-kitty-events`, charter update
2026-10-29). The stand-in service is the documented launch-contract double, so the repro is
made there: with the stand-in serving `/api/v1/*` only, the pre-fix client raises
`ServiceUnreachable("GET /handshake answered 404")`.
