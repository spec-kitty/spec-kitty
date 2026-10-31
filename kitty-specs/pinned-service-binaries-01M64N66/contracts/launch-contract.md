# Contract: core launcher ↔ service process (accepted 2026-10-29)

Accepted by the spec-kitty-events operator on 2026-10-29 (relayed by session A). spec-kitty-events records it in `contracts/mission-write` at cut-over. `/shutdown` stays provisional until `command-cli` exists.

## Write service (scope: one per git common dir)
1. **Start:** `<binary> serve --git-common-dir <absolute path> [--idle-timeout <seconds>]`. For the JVM fallback: `java -jar <jar> serve …`.
2. The service takes an exclusive OS lock on `<gcd>/spec-kitty-write-service/service.lock` for its whole life. If the lock is held, it exits 0 without publishing.
3. The service publishes `<gcd>/spec-kitty-write-service/endpoint.json` by writing a temporary file and renaming it. The fields and modes follow ADR 2026-10-27-1 D-2. It deletes the file at exit only while it still names its own `instance_id`.
4. The service's stdout and stderr go to `<gcd>/spec-kitty-write-service/service.log`. The launcher opens that file in append mode for the child.
5. **Ready:** the endpoint file passes `read_endpoint_file`, then `GET /handshake` with `Authorization: Bearer <token>` returns a `repositoryId` equal to `sha256(realpath(gcd))` and `protocolVersions` that intersect the CLI's, then `GET /health` returns `status: ready` with the same `instanceId`.
6. **Stop:** `POST /shutdown` (bearer). The health status reads `draining`, then the service exits. If the process is still alive after 10 s and its pid still matches the endpoint instance, the launcher sends SIGTERM on POSIX or calls TerminateProcess on Windows.

## Charter service (later; recorded for shape only)
The same shape with `--worktree <path>`, and a per-worktree endpoint directory. It is out of scope for this mission beyond a policy stub.

## Read service
The CLI never launches it (ADR 2026-10-29-1 D-6).
