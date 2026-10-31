# Research: Pinned service binaries

## R-1: Where the HTTP download lives
- **Decision:** `kernel.release_assets` is the one owner, written with the standard library's `urllib.request`.
- **Rationale:**
  - `kernel` is zero-dependency (`src/kernel/pyproject.toml`).
  - The precedent `kernel.git.remote` owns git remote contact.
  - `urllib` honours `HTTPS_PROXY`/`NO_PROXY`, and `ssl` honours `SSL_CERT_FILE`/`SSL_CERT_DIR`, which matches agent and corporate proxy setups.
- **Alternatives:**
  - `httpx`/`requests` in `specify_cli`: rejected, because primitives belong in `kernel` (C-004) and the sync script would gain a heavier import.
  - Downloading through the `gh` CLI: rejected, because it is not available to users.

## R-2: Release download URL shape
- **Decision:** `<repository>/releases/download/<tag>/<asset>` for `https://` sources. For `file://` sources the same relative layout under the given directory (`<dir>/<tag>/<asset>`), so fixtures and offline mirrors match.
- **Rationale:** this is GitHub's stable public asset URL, it needs no API token for public repositories, and it is one predictable shape for mirrors.
- **Alternatives:** the GitHub REST API for assets was rejected: it needs JSON parsing and authentication for rate limits.

## R-3: Verification points
- **Decision:** verify a sha256:
  1. after download, before the rename into the cache;
  2. on every resolve;
  3. immediately before `exec` — re-hash the file to be executed, to close the time-of-check window between resolve and spawn.
- **Rationale:** NFR-003 ("100% of executed binaries verified immediately before execution").
- **Note:** a re-hash of an 80 MB binary costs about 50 ms. Checks 2 and 3 each happen only on a cold start, so the warm path (an endpoint already published) hashes nothing.

## R-4: Process contract
- **Decision:** `<bin> serve --git-common-dir <abs> [--idle-timeout s]`, with `service.lock`, `endpoint.json` published by rename and `service.log`. Readiness means a handshake with a matching repositoryId and an intersecting protocol, followed by health `ready`. Stop means `POST /shutdown`, with a SIGTERM/TerminateProcess fallback after 10 s when the pid matches the endpoint instance.
- **Status:** accepted by the spec-kitty-events operator on 2026-10-29 (relayed by session A). spec-kitty-events records it in `contracts/mission-write`. `/shutdown` stays provisional until `command-cli` exists.
- **Consequence:** the fake service in tests implements exactly this, so the real binary drops in.

## R-5: Detached spawn
- **Decision:**
  - POSIX: `subprocess.Popen(..., start_new_session=True, stdin=DEVNULL, stdout/stderr=service.log)`.
  - Windows: `creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW`.
- **Rationale:** the service must outlive the CLI invocation (ADR 2026-10-22-1 D-2), and stdio must not hold the CLI's pipes open.

## R-6: JVM fallback detection
- **Decision:** only when no native asset exists for the host target, or its download is unavailable and a jar is pinned. Run `java -version` (from `JAVA_HOME/bin` first, then `PATH`) and parse the major version; it must be at least 25. The jar runs as `java -jar <jar> serve …`.
- **Rationale:** ADR 2026-10-22-1 D-5. Avoid the cost of spawning a JVM on the normal path.

## R-7: CI wiring before the first release
- **Decision:** ship the composite action and the sync script with their guard tests, but wire no job and add no pin gate until a real pin exists. The cut-over PR, which consumes the first `service-v*` release, adds the jobs.
- **Rationale:** C-003. A job with nothing to fetch would be vacuous or red.

## R-8: Registry routing for the new package
- **Decision:** add `src/specify_cli/services/**` to an existing module row whose `test_dirs` gains `tests/specify_cli/services`. Pick the row in implement after reading the current registry. `tests/kernel` stays with the `kernel` row.
- **Rationale:** an unmapped `src/**` path trips the router's fail-closed catch-all.

## Adversarial evidence
- No dependency decision, so the DIRECTIVE_051 adversarial pass is not triggered. The launcher's security posture (token handling, loopback, digest gating) is put to the pre-PR adversarial squad at closeout.
