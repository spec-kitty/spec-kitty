---
title: 'ADR: the events domain and its Java services live in spec-kitty-events; core consumes a released, pinned service'
description: 'The Java event services and contracts move to spec-kitty-events; core pins a service-v* release by tag and sha256, fetches it on first use, and fails closed.'
status: Accepted
date: '2026-10-29'
---

# The events domain and its Java services live in spec-kitty-events; core consumes a released, pinned service

**Status:** Accepted (2026-10-29). The decision was made by the operator with the Spec Kitty CEO on 2026-10-29; the operator signed off this record, its *(derived)* clauses included, the same day.

> **What was ruled and what is derived.**
> - **Ruled by the operator (2026-10-29):**
>   - The Java read service (Mission Status Read API) and the Java write service (Mission Write API / event-log write core) leave core for `spec-kitty/spec-kitty-events`, which becomes the canonical owner of the events domain.
>   - The build is Gradle everywhere, and history is preserved in the move.
>   - spec-kitty-events gets a separate `service-vX.Y.Z` release line, and core pins a service tag plus a sha256 per OS binary.
>   - `services/` is frozen in core from the decision onward.
>   - Layout in spec-kitty-events: `service/` and `contracts/`.
>   - The contract bundles ride on `service-v*`. Two release lines exist in total, PyPI `v*` and `service-v*`, and core's `contract-<module>-v*` line retires.
>   - Events CI pins a core SHA for the lock-interop peer, the corpus compare and golden regeneration.
>   - Users get the binary by a first-run, digest-verified fetch, and the wheel stays pure.
>   - The read service is pinned in core for CI conformance only.
>   - acceptance-jvm fetches its contract tools from the pinned release.
> - **Derived:** every clause marked *(derived)*.

**Date:** 2026-10-29

**Deciders:** Stijn Dejongh (operator), with the Spec Kitty CEO.

**Technical Story:**
- Epic #6117 (Mission Write API) and epic #6608 (event-native core).
- #6676 (the fail-closed launcher), #6590 (bundle the charter backend service through CI, the way the packs are), and #6409, #957 and #5528 (read API).
- This record amends:
  - [ADR 2026-10-01-2](2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md) (D-7, D-9 to D-12);
  - [ADR 2026-10-14-1](2026-10-14-1-event-native-core-one-canonical-event-writer.md) (where the writer lives);
  - [ADR 2026-10-22-1](2026-10-22-1-the-java-write-service-is-the-canonical-event-writer.md) (D-1, D-5);
  - [ADR 2026-10-27-1](2026-10-27-1-the-write-service-protocol-is-loopback-http-with-a-bearer-token.md) (the launcher's binary source);
  - [ADR 2026-04-25-1](../3.x/2026-04-25-1-shared-package-boundary.md) (what `spec-kitty-events` is to core).
- It follows the charter precedent: [ADR 2026-10-12-2](2026-10-12-2-charter-extraction-to-its-own-repository.md) (Superseded), [ADR 2026-10-16-1](2026-10-16-1-extract-charter-offering-first-activation-rework-post-ga.md) (Amendment 2026-10-19) and [ADR 2026-10-03-1](2026-10-03-1-charter-read-write-service-strangler.md). It differs from that precedent: here the service code does move, while the Python client side stays in core.

**Reader:** a maintainer changing how core builds, pins, fetches or launches an events service, or deciding where a piece of events-domain work belongs.

---

## Context and Problem Statement

Core holds three things that belong to the events domain:
- `services/mission-status-api/`, a Gradle build (Spring Boot 4, GraalVM 25) with the read service and the `domain-model` and `event-log` libraries the write service is built from (#6192, #6193);
- `contracts/mission-status` and `contracts/mission-write`;
- the workflow `mission-status-api.yml`, which builds per-OS native binaries.

The Python package `spec-kitty-events` already owns event envelopes, payload schemas, fixtures and the reducer the Java `StatusReducer` ports. The events domain is therefore split across two repositories. Every change to an event model means coordinated edits in both: the Python model in spec-kitty-events, then the Java port, contract and goldens in core.

The CLI itself never ran either service. The wheel ships no server (2026-10-01-2 D-7), and the write-service launcher (#6676) is unbuilt. Moving the code costs core nothing at runtime, but it does change how core gets the write binary once #6195 binds the EventBridge to it.

## Decision Drivers

- Single canonical authority: one repository owns an event model, its Java port, its contract and its release.
- Core's job is to consume, pin and launch the binary, not to build it.
- One pin-and-fetch mechanism for every backend service core consumes: the events write service, the charter service (#6590), and the read service for CI.
- Fail closed, with no Python fallback writer (2026-10-22-1 D-5).
- Keep the wheel pure, and keep CLI reads working with no binary present.

## Considered Options

1. Keep the services in core and let spec-kitty-events stay Python-only.
2. Move the services and contracts to spec-kitty-events; core pins a released build (chosen).
3. Move them to a new dedicated service repository.

## Decision Outcome

Chosen option: **2**.

### D-1: spec-kitty-events owns the Java services and the events contracts

- The read service, the `domain-model` and `event-log` libraries, the future `command-cli` write deployable, and `contracts/{mission-status,mission-write,_shared,tools,lint}` live in spec-kitty-events (`service/` and `contracts/`). They are imported with their history.
- Core's copies are removed at the cut-over. Core's history is kept.
- Java work on these modules is filed and done in spec-kitty-events.
- The architecture page `docs/architecture/event-ledger-writers-and-readers.md` moves to spec-kitty-events with the domain. It stays frozen in core, and corrections to it are made there (operator ruling, 2026-10-29).

### D-2: the `service-v*` release line is core's only source for service binaries

- Each `service-vX.Y.Z` release carries, per deployable:
  - `<deployable>-<ver>-<target>[.exe]` for linux-x64, linux-arm64, macos-arm64 and windows-x64, each with a `.sha256`;
  - `<deployable>-<ver>.jar` (the JVM fallback of 2026-10-22-1 D-5).
- Each release also carries `contract-bundles-<ver>.tar.gz`, `contract-tools-<ver>.tar.gz`, `conformance-fixtures-<ver>.tar.gz`, `SHA256SUMS` and an SLSA attestation. Asset names are stable across releases; only `<ver>` changes.
- Core's `contract-<module>-v*` line and `contracts-release.yml` retire.

### D-3: core pins a release by tag and per-asset sha256 *(derived from the ruling)*

- One lockfile per service, `pins/<service>.source.yaml`, shaped like `packs/*.source.yaml`. It records:
  - the repository, the tag, and the resolved commit;
  - the protocol versions and `requires_core`;
  - per target, the asset name and its sha256;
  - the contract and fixture assets.
- The single bump path is `spec-kitty service vendor --service <s> --tag <t>`. A pin gate in CI catches drift.
- A binary is executed only when its bytes match a pinned sha256. A cached copy is re-hashed on every resolve, and a mismatch is deleted and fetched again.

### D-4: users get the binary by a first-run, digest-verified fetch

- The wheel stays `py3-none-any` and ships the pins, not the binaries.
- On first need, the launcher fetches the host target's asset into `${XDG_CACHE_HOME}/spec-kitty/services/<service>/<tag>/` and verifies it.
- `spec-kitty service fetch` pre-fetches. `SPEC_KITTY_SERVICE_ASSET_DIR` serves an offline or air-gapped install from a local directory. Assets served that way are still digest-checked.
- An install-provided slot stays in the resolution order, so a companion platform wheel can be added later without changing the launcher.

### D-5: one launcher, fail-closed, for every pinned service *(derived)*

- `specify_cli` owns one launcher with a per-service policy:
  - **Write service:** one per git common dir, launch-when-down, endpoint file per 2026-10-27-1.
  - **Charter service:** one per worktree, token-gated, per 2026-10-03-1.
  - **Read service:** never launched by the CLI (D-6).
- Resolution order:
  1. an explicit binary path, still digest-checked;
  2. the install-provided slot;
  3. the cached native asset;
  4. the JVM jar on a local JDK 25;
  5. otherwise a refusal.
- Dev-only digest bypass (operator ruling, 2026-10-29): an explicit binary path may skip the digest check only when the developer passes an opt-in flag (`--unpinned-dev`).
  - It is never the default.
  - Every use prints a visible warning.
  - CI and release paths never use it.
- Refusals carry a named code and a remedy: `SERVICE_BINARY_MISSING`, `SERVICE_BINARY_DIGEST_MISMATCH`, `SERVICE_UNSUPPORTED_PLATFORM`, `SERVICE_UNHEALTHY`, `SERVICE_VERSION_MISMATCH`, plus the existing `WRITE_SERVICE_ENDPOINT_*`.
- There is no Python fallback writer. Reads keep working with no binary present.
- The launcher's start, health and stop half of #6676 lives here. The native-image build half moves to spec-kitty-events.

### D-6: the read service is pinned for CI conformance only

- Core pins the read service to run the Python-oracle conformance and corpus comparisons against the released binary.
- The CLI never launches it. 2026-10-01-2 D-5 and D-7 hold.
- Consumers (mission-ui, the pack composer) fetch it from spec-kitty-events themselves.

### D-7: the client side stays in core *(derived)*

These stay in core:
- the EventBridge port and `bind_event_bridge`;
- `LocalFileEventBridge`, until #6195;
- `write_service_protocol.py`;
- `kernel.locks` and `kernel.event_log_append`;
- the Python oracle tests and the CI scripts that drive a binary (`mission_status_corpus_compare.py`, `lock_interop_peer.py`).

spec-kitty-events CI checks out core at a pinned SHA to run them.

### D-8: one owner for HTTP release-asset downloads *(derived)*

- Fetching a release asset is new remote contact.
- It gets one owner module in `kernel` and a sibling gate to `test_remote_contact_owner.py`, with an empty allowlist. It does not become a scattered HTTP call.

### D-9: freeze until removal

- No change lands in core after 2026-10-29 under any of these frozen paths. Queued Java work moves to spec-kitty-events.
  - `services/`;
  - `contracts/mission-status`, `contracts/mission-write`, `contracts/_shared`, `contracts/tools`, `contracts/lint` and `contracts/gradle`;
  - `contracts/README.md`, `contracts/build.gradle` and `contracts/settings.gradle`;
  - `docs/architecture/event-ledger-writers-and-readers.md`.
  - `contracts/fixtures/` stays in core and is not frozen.
- The architectural gate `tests/architectural/test_events_import_frozen.py` enforces the freeze (its `_FROZEN_OBJECTS` is the exact set above). It lands in the same PR as this record.
- Exception path: an operator-approved change to a frozen path may re-pin `_FROZEN_OBJECTS` in the same PR, and that change is ported to spec-kitty-events.
- Exit: the gate is removed together with `services/` at the cut-over. That exit is tracked by #6117, owner Stijn Dejongh.

### Consequences

**Positive**
- One repository owns each event model end to end.
- The pin-and-fetch mechanism, the lockfile and the launcher serve the charter service too (#6590).
- Core CI no longer builds GraalVM binaries.

**Negative**
- Two repositories now pin each other: core pins a `service-v*` release, and events CI pins a core SHA for the interop peer and the corpus compare.
- A golden regeneration becomes a PR in events that records the core SHA.
- A first write on a fresh install needs network access, or a pre-fetched asset directory. Without either, the write refuses.
- A pin bump is a core PR.

**Neutral**
- The Shared Package Boundary now has two artifact kinds for `spec-kitty-events`: the PyPI package (a SemVer range plus the lockfile) and the pinned service binaries (tag plus sha256).

### Confirmation

- After the cut-over, `services/`, `mission-status-api.yml`, `contracts.yml` and `contracts-release.yml` are absent from core.
- The pin gate and the release-asset owner gate are green, and the packaging guards pass with no binary in the wheel or sdist.
- `test_shared_package_boundary.py` accepts the pins.
- The conformance tests run against the pinned fixtures and the pinned binary.

## Pros and Cons of the Options

### Keep the services in core

- Good: there is no cross-repository pin.
- Bad: the events domain stays split, so every event-model change means two coordinated PRs, and core keeps a GraalVM build it does not run.

### Move them to spec-kitty-events (chosen)

- Good: one owner; one release line per artifact kind; core only consumes.
- Bad: mutual pins; network on first write.

### Move them to a new service repository

- Good: a clean separation from the Python package.
- Bad: a third repository to coordinate, and the events domain would still be split between the Python models and the Java port.

## More Information

- Core-side plan, inventory and cut-over runbook: [`docs/plans/events-domain-move/plan.md`](../../plans/events-domain-move/plan.md).
- Precedent for the pin and fetch: [`docs/development/how-to/sync-packs.md`](../../development/how-to/sync-packs.md).

## Amendment 2026-10-30 (Accepted): refusal codes and pin location

The pre-PR review of the implementation (#6590) settled four points this record left implicit. The body above is unchanged.

- **Refusal codes.** Besides the D-5 codes, the launcher and the operator commands use:
  - `SERVICE_PIN_INVALID`: no pin for the service in this core version, or a malformed or placeholder lockfile;
  - `SERVICE_VENDOR_*` (`USAGE`, `COMMIT_REQUIRED`, `TAG_UNRESOLVED`, `RELEASE_UNAVAILABLE`, `RELEASE_INVALID`, `DIGEST_MISMATCH`, `REQUIRES_CORE`): `spec-kitty service vendor` refused a bump or a check.
- **Pin location.** The CLI reads its own pin: the `pins/` directory of the spec-kitty source checkout the running package belongs to, or the `specify_cli/_pins/` resource of the installed wheel. It never reads a pin from the user's project. `spec-kitty service vendor` writes only that source checkout's `pins/`, and only when run inside it.
- **The read service stays off user machines (D-6).** `spec-kitty service fetch --all` covers only the services the CLI launches, and `spec-kitty service status` reports the write service unless another is named. The read service is fetched only when it is named explicitly (`--service read-service`), as CI does.
- **Stop outcomes.** `spec-kitty service stop` has four outcomes: stopped, not running, forced, and unconfirmed. Unconfirmed means the published process is alive but could not be proven to be the instance, so it was not signalled. It exits 1 and names the pid and the log.

## Amendment 2026-10-31 (Accepted): the optional companion services wheel

Operator ruling 2 of 2026-10-31 (#6117) fills the install-provided slot that D-4 reserved. Tracked by #6904; the research and the twelve recommendations the operator accepted are in [`docs/plans/events-domain-move/companion-wheel-research.md`](../../plans/events-domain-move/companion-wheel-research.md). The body above is unchanged; D-4's first-run fetch stays the default for every install.

- **Name.** The companion is the distribution `spec-kitty-services` (import package `spec_kitty_services`). Its source lives in `packages/spec-kitty-services/`, outside `src/`, and is excluded from the CLI sdist.
- **Install.** `spec-kitty-cli` gains the extra `services`, which requires `spec-kitty-services==<cli version>`. `pip install "spec-kitty-cli[services]"` is the one-command offline-ready install; `pip install spec-kitty-services==<cli version>` also works.
- **Version lock.** The companion's version equals the CLI's version, and so does the extra pin. A test and `scripts/release/validate_release.py` check all three. Each companion wheel is built from the same release commit's `pins/` and embeds a `spec_kitty_services/_manifest.json` with `{service, tag, asset, sha256}` per binary.
- **Skew degrades, tampering refuses.** A provider offers nothing when the installed CLI version or the host target differs from its manifest, so resolution falls through to the cache and fetch. Whatever a provider does offer is still digest-checked against the CLI's own pin, and a mismatch refuses with `SERVICE_BINARY_DIGEST_MISMATCH` (D-5 unchanged).
- **Contents.** Each platform wheel carries the native write-service and charter-service builds pinned for its own target, and nothing else: never the read service (D-6), no jar, no contract or fixture assets.
- **Fallback wheel.** A binary-free `py3-none-any` wheel of the same version makes the extra installable on every host (Intel macOS, musl Linux, Linux below the glibc floor, Windows on ARM). Its providers offer nothing, so those hosts use the first-run fetch.
- **Platform tags.** `py3-none-manylinux_2_39_x86_64`, `py3-none-manylinux_2_39_aarch64`, `py3-none-macosx_11_0_arm64` (the first Apple Silicon macOS) and `py3-none-win_amd64`. GraalVM links glibc dynamically, so the Linux floor is the glibc of the spec-kitty-events build hosts (2.39 on `ubuntu-24.04`); `release.yml` passes it to the builder explicitly (`--glibc-floor 2_39`) and must change together with those hosts. Neither floor is yet read from the binary itself (follow-up #6948). Lowering the Linux floor is spec-kitty-events work.
- **Built, never rebuilt.** `scripts/build_services_wheel.py` fetches every asset through `kernel.service_artifacts.fetch_asset` (D-8's owner; every byte is checked against the pinned sha256) and writes the wheels with the standard library, deterministically. A `--verify` pass proves each wheel holds exactly the pinned digests.
- **Size.** PyPI's default per-file limit is 100 MB. The build fails above 95 MB per wheel and warns above 60 MB (the threshold of plan §3.4). No binary size has been measured yet; the estimate is 60–85 MB per platform wheel. Splitting the companion into one wheel per service needs its own amendment.
- **Release.** `release.yml` gains `build-companion-wheels` (to `dist-services/`, never `dist/`) and `publish-companion-pypi` (environment `pypi-services`, Trusted Publishing). `publish-pypi` waits for the companion, so the CLI's exact extra always resolves. With no pin, only the fallback wheel is built and published.
- **Resolution order is unchanged:** explicit path, the install slot, the cached native asset, the jar, then a refusal (D-5).
- **uv workspace member.** The exact extra cannot lock from PyPI, because the companion of version X is published in the same release run as commit X. `packages/spec-kitty-services` is therefore a uv workspace member: `[tool.uv.workspace] members = ["packages/spec-kitty-services"]` and `[tool.uv.sources] spec-kitty-services = { workspace = true }` (operator ruling, 2026-10-31). It is a first-party member, not an override of an external package, so the Shared Package Boundary (ADR 2026-04-25-1) is unchanged. The companion carries a standard-library in-tree build backend, which builds the fallback wheel and shares its wheel writer with the release script.
- **Operator prerequisites before the first release that carries the extra:** claim the PyPI name `spec-kitty-services` (a pending Trusted Publisher does not reserve it; upload the binary-free fallback wheel once), bind its Trusted Publisher to this repository's `release.yml` and the GitHub environment `pypi-services`, and create that environment. Until the name is claimed, anyone could register it, and the CLI's published `services` extra would resolve to their package.
- **PyPI storage quota.** Each release uploads about four wheels of 60-85 MB for the companion against the 10 GB default project quota; prune release candidates or request a raise before the quota runs out.
- **Orphan companion version.** If the companion publishes and the CLI publish then fails, that companion version stays on PyPI and cannot be re-uploaded. This is tolerable: the CLI re-run reuses it through `skip-existing`.
