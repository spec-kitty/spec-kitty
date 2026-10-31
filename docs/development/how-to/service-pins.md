---
title: How to fetch, verify and bump the pinned service binaries
description: Fetch and verify the pinned spec-kitty-events service builds in a checkout or in CI, work offline, run an unpinned local build, and bump a pin with spec-kitty service vendor.
doc_status: active
updated: '2026-10-30'
audience: docs/context/audience/internal/maintainer.md
type: how-to
related:
- docs/adr/4.x/2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md
- docs/development/how-to/sync-packs.md
---
# How to fetch, verify and bump the pinned service binaries

Core runs services it does not build: the write service, the Mission Status read service and the
charter service. Their source and their releases live in `spec-kitty-events`, which publishes each
build as a `service-vX.Y.Z` GitHub release: per-OS native binaries, a portable jar, the contract
bundles and the conformance fixtures, each with a SHA-256 digest
([ADR 2026-10-29-1](../../adr/4.x/2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md)).

A **service pin** is the lockfile `pins/<service>.source.yaml`. It records which released build core
runs: the tag, the commit it resolves to, the protocol versions, the core version range it needs,
and the file name and digest of every asset. The wheel ships the pins (as `specify_cli/_pins/`) but
never a binary: every asset is fetched and checked against its pinned digest before it is used.

The CLI reads **its own** pin, never one in the user's project. It looks in the `pins/` directory of
the spec-kitty source checkout the running `specify_cli` package belongs to (an editable install;
the checkout's `pyproject.toml` must name `spec-kitty-cli`), and otherwise in the `specify_cli/_pins/`
resource of the installed wheel. A `pins/` directory in the project you run spec-kitty in is ignored:
the pin names the build this CLI runs, so a project cannot choose it.

> **No pin exists yet.** `pins/` holds only its `README.md` until `spec-kitty-events` cuts its first
> `service-v*` release. Until then `make sync-services` prints `no service pinned` and exits 0, and
> every command that needs a service refuses with `SERVICE_PIN_INVALID`. The pull request that adds
> the first pin also wires the `sync-services` action into CI and `sync-services` into `make dev-setup`.

## Fetch and verify in a checkout

```bash
make sync-services                  # fetch and verify every pinned asset for this host
make sync-services ARGS=--check     # verify the cached copies only; fetch, write and delete nothing
make sync-services ARGS=--offline   # use the cache and SPEC_KITTY_SERVICE_ASSET_DIR only
```

For each pin, the target takes the host's native build (the jar when the pin has no build for this
host) plus every extras asset, and fetches and verifies each into
`${XDG_CACHE_HOME:-~/.cache}/spec-kitty/services/<service>/<tag>/<name>`. It exits 1 with a stable
`SERVICE_*` code on any failure. The script behind it is `scripts/sync_services.py`; pass
`--service <name>` to handle one service.

## Fetch and verify in CI

The composite action `.github/actions/sync-services` restores the cache, keyed on
`hashFiles('pins/*.source.yaml')`, and then runs `scripts/sync_services.py --service all`. It takes
the same `python` and `python-exe` inputs as `.github/actions/sync-packs`. No job uses it yet;
`tests/ci/test_sync_services.py` fails, saying "wire it now", once a pin exists and no workflow uses
it.

## What a user does

Nothing, normally: the first command that needs a service fetches, verifies and starts it.

- `spec-kitty service fetch [--service <name> | --all] [--offline]` fetches and verifies ahead of time.
  `--all` covers the services the CLI launches; the read service is pinned for CI conformance only
  ([ADR 2026-10-29-1](../../adr/4.x/2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md) D-6),
  so it is fetched only when named with `--service read-service`.
- `spec-kitty service status [--service <name>] [--json]` shows the pin, the cache state and the
  running instance. It only reads, like `make sync-services ARGS=--check`: it starts nothing, writes
  nothing and evicts nothing. A cached copy that does not verify is reported `corrupt` and left in
  place; the next fetch or start replaces it.
- `spec-kitty service stop [--service <name>]` stops this clone's running instance.
- On a machine with no network, run `spec-kitty service fetch` on a connected machine and copy the
  cache, or set `SPEC_KITTY_SERVICE_ASSET_DIR` to a directory that holds the pinned asset files
  (flat, or under `<tag>/`). Its files are digest-checked and copied into the cache, never run in place.

## Bump a pin

Bump a pin only with the vendor command, never by hand:

```bash
spec-kitty service vendor --service write-service --tag service-v0.2.0
spec-kitty service vendor --service write-service --check
git add pins/write-service.source.yaml && git commit
```

`vendor` reads the release's `SHA256SUMS`, downloads and hashes every asset it pins, and writes the
lockfile. It prints the native targets the release has no build for. `--check` verifies the lockfile
offline against the shape rules and, online, against the release. Tags follow
`service-v<major>.<minor>.<patch>[-<pre-release>]`; build metadata (`+...`) is refused. The
repository must be an `https://` or `file://` URL without credentials.

A bump writes only the `pins/` of the spec-kitty source checkout the CLI runs from, and only when you
run it inside that checkout (an editable install, for example `uv run spec-kitty service vendor ...`
in your clone). Anywhere else it is a usage error (exit 2, `SERVICE_VENDOR_USAGE`) and nothing is
written.

> **Maintainer note: cross-check the digests out of band.** `vendor` trusts the release's own
> `SHA256SUMS`. Before you commit a bump, compare the vendored digests with a second source: the
> asset digests GitHub shows on the release page, or the build attestation:
>
> ```bash
> gh attestation verify <downloaded asset> --repo spec-kitty/spec-kitty-events \
>   --signer-workflow spec-kitty/spec-kitty-events/.github/workflows/service-release.yml \
>   --source-ref refs/tags/<tag>
> ```

## Run a local build of a service

When you work on `spec-kitty-events`, point core at your own build:

```bash
export SPEC_KITTY_WRITE_SERVICE_BINARY=/path/to/your/build/spec-kitty-write-service
export SPEC_KITTY_SERVICE_UNPINNED=1   # prints a warning on every start
```

Without `SPEC_KITTY_SERVICE_UNPINNED=1` an explicit path must still match the pinned digest. The
opt-in is honoured only together with an explicit path (`SPEC_KITTY_<SERVICE>_BINARY`). The start
timeout is `SPEC_KITTY_SERVICE_START_TIMEOUT` (seconds, default 15).

## Refusal codes

| Code | Meaning | What to do |
|---|---|---|
| `SERVICE_PIN_INVALID` | No pin for the service in this core version, or the lockfile is malformed or a placeholder. | Wait for the first release, or re-run `spec-kitty service vendor`. |
| `SERVICE_BINARY_MISSING` | The asset is not in the cache and cannot be fetched (offline, unreachable, or the cache is full or not writable), or the verified binary cannot be executed (no exec permission, a `noexec` mount). | Fetch while online, set `SPEC_KITTY_SERVICE_ASSET_DIR`, free space in or fix the cache, or move the cache (`XDG_CACHE_HOME`) to an exec-capable file system. |
| `SERVICE_BINARY_DIGEST_MISMATCH` | The bytes are not the pinned bytes. | Delete the copy and fetch again; if it persists, the release or mirror does not match the pin. |
| `SERVICE_UNSUPPORTED_PLATFORM` | The pin has no build for this host, and either no jar or no Java 25+ runtime to run the pinned jar. | Install a Java 25 runtime (`JAVA_HOME`, or an absolute `PATH` entry) when the pin has a jar, or use a supported host. |
| `SERVICE_UNHEALTHY` | The service started but did not become healthy, or its directory in the git common dir cannot be created or written (a read-only or full `.git`, a symlinked `service.log`). | Read the service log, run `spec-kitty service stop`, retry; or make the directory the message names writable. |
| `SERVICE_VERSION_MISMATCH` | The running service speaks no protocol version this CLI accepts. | Upgrade spec-kitty, or stop the running service. |
| `SERVICE_VENDOR_*` | `spec-kitty service vendor` refused (usage, an unresolvable tag, an unavailable or invalid release, a digest mismatch, a `requires_core` range this version does not satisfy). | Follow the remedy the command prints. |
