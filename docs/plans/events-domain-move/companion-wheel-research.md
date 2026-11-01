---
title: Companion services wheel — research note
description: 'Read-only research for the optional spec-kitty-services companion platform wheel that fills the spec_kitty.service_binaries slot (#6904).'
doc_status: active
type: explanation
audience:
- profile: internal/maintainer
  guidance_text: Written for the Maintainer reader.
updated: '2026-10-31'
---
# Companion services wheel: research note

**Status:** ruled and built. The operator accepted all twelve recommendations below on 2026-10-31, plus the uv workspace member for the exact extra; they are recorded in ADR 2026-10-29-1, Amendment 2026-10-31, and delivered by Mission `companion-services-wheel-01M694B1` (#6904).
**Tracks:** #6904 (child of #6117). This delivers operator ruling 2 of 2026-10-31 (#6117 comment 6544221340).
**Reader:** a maintainer who has to rule on the open points, or who builds the companion wheel.

Every claim cites either a file in this repository at `origin/main` (2026-10-31) or a named external source. Statements marked *estimate* are reasoning, not measurements.

## 1. What exists today

### The install slot is built and digest-checked

- `src/specify_cli/services/resolution.py:91` defines `BINARY_PROVIDER_GROUP = "spec_kitty.service_binaries"`.
  - An entry point is named after the service (for example `write-service`).
  - Its value loads to a zero-argument callable that returns a path or `None` (`_provided_path`, :316).
- Resolution order (`resolve_binary`, :444) is: explicit path, then the install slot, then the cache or fetch, then the jar.
- A path from the install slot goes through `_match_supplied` (:249):
  - its bytes must equal the pinned host build, or the pinned jar;
  - it is then adopted into the cache (`kernel.service_artifacts.adopt_asset`), so the cached copy runs, never the file inside site-packages.
- A path that does not match the pin refuses with `SERVICE_BINARY_DIGEST_MISMATCH`. It does **not** fall through to the cache.
- A provider that raises refuses with `SERVICE_BINARY_MISSING`.

### Tests: four gaps

Tests in `tests/specify_cli/services/test_resolution.py` (:348–:399, :712) cover:
- the install slot winning over an empty cache;
- the real `entry_points` selection;
- a provider that returns `None`;
- a binary that is not the pinned build, and a provider that raises.

They do not cover:
- the install slot winning over a cache that is already warm;
- a wrong-digest binary refusing while the cache is warm;
- the install slot supplying a jar;
- an explicit path beating the install slot.

### Pins

- `pins/` holds only `README.md`. `spec-kitty-events` has no `service-v*` tag yet (checked with `git ls-remote`).
- The services are `write-service` (launchable), `charter-service` (pinned, not yet launchable) and `read-service` (CI only, never launched; `services/policies.py:56-60`).
- The targets come from `kernel.service_pin.ServiceTarget`: `linux-x64`, `linux-arm64`, `macos-arm64`, `windows-x64` and `jvm`.

### The fetch owner

- `kernel.service_artifacts.fetch_asset(pin, asset, *, offline, cache_root, asset_dir)` verifies every byte against the pinned sha256 before it returns a path.
- Downloads go through `kernel.release_assets` (gate `tests/architectural/test_release_asset_download_owner.py`). That gate scans only `src/`, so a build script elsewhere is not gated, but it should still call `fetch_asset`.

### The release workflow

- `.github/workflows/release.yml` builds with `python -m build` (:189).
- The packs drift check is at :186–187.
- "Verify wheel contents" assumes exactly one wheel in `dist/` (:209).
- Publishing uses PyPI Trusted Publishing, scoped to the `pypi` environment and the `spec-kitty-cli` project (:326–386).

### Packaging guards

- `tests/cross_cutting/packaging/test_packaging_safety.py:282-333` already fails any wheel or sdist member that ends in a target suffix or `.jar`, or that sits under a cache path.
- The CLI sdist includes the bare `README.md` with gitignore semantics (`pyproject.toml:266-269`). A nested `packages/**/README.md` would leak into the sdist unless `packages/**` is excluded.
- `test_pyproject_shape.py:140-151` treats every `src/*` directory that holds Python files as first-party, so the companion module must not live under `src/`.

## 2. External facts

### PyPI limits

- PyPI allows 100 MB per file and 10 GB per project by default.
- Raising either limit takes a request to `pypi/support`. A file-size increase also requires at least one existing release under 100 MB.
- Source: docs.pypi.org/project-management/storage-limits, quoted through search because this session's network blocks that host; pypi/support #243, #3757 and #7112.

### Wheel tags and glibc

- The tags are `manylinux_2_X_{x86_64,aarch64}`, `macosx_11_0_arm64` and `win_amd64` (packaging.python.org platform-compatibility-tags).
- GraalVM native images link glibc dynamically by default, against the glibc of the build host.
  - The events native job builds on `ubuntu-24.04`, which has glibc 2.39 (`.github/workflows/mission-status-api.yml:149-171`).
  - A `manylinux2014` (glibc 2.17) tag would therefore be untrue.
  - Source: graalvm.org native-image static-executables guide; z3prover/z3#7232 shows the same failure in the wild.

### Size

- **No binary size has ever been measured.** No release has been cut (`plan.md:38`).
- Published minimal Spring Boot native images are 48–129 MB uncompressed (Baeldung 82.8 MB; alexcheng1982/spring-boot-native-samples).
- *Estimate:*
  - 30–40 MB compressed per native binary;
  - **60–85 MB per platform wheel holding the write and charter binaries**: under the 100 MB cap, with little headroom;
  - adding a jar (25–40 MB) to each platform wheel would likely push it over the cap.

### Install behaviour

- With `pip install spec-kitty-cli[services]`, pip picks the platform wheel that matches the host.
- When no wheel matches and the companion has no sdist, the whole install fails, `spec-kitty-cli` included.
- PEP 508 markers can skip the requirement per OS and architecture, but they cannot tell glibc from musl or read the glibc version.
- A `py3-none-any` wheel of the same version is the fallback pip picks when no platform wheel matches.

## 3. Decisions for the operator (recommendations)

| # | Open point | Recommendation |
|---|---|---|
| 1 | Name | Distribution `spec-kitty-services`, import package `spec_kitty_services`. |
| 2 | Extra or separate install | Both work. Add an extra `services` on `spec-kitty-cli` (`spec-kitty-services==<cli version>`), so `pip install "spec-kitty-cli[services]"` is the one offline-ready command; `pip install spec-kitty-services==<cli version>` also works. Plan §3.4 named the extra `[native]`; `services` matches the distribution name. |
| 3 | Version lock | The companion's version equals the CLI's version exactly. It is built from the `pins/` of the same release commit and embeds a manifest of `{service, tag, target, sha256}`. Its provider returns `None` (fall through to the cache or fetch) when the installed `spec-kitty-cli` version differs from the version it was built for, so a version skew degrades to option A instead of refusing with `DIGEST_MISMATCH`. Resolution still digest-checks whatever the provider returns. |
| 4 | Contents | The native write service and charter service for the host target. Not the read service (ruling 3, D-6). Not the jar: the jar fallback stays on the fetch path, which keeps each wheel under the cap. |
| 5 | Unsupported hosts | Also publish a **binary-free `py3-none-any` fallback wheel** whose providers return `None`. Every host then resolves the extra (Intel macOS, musl, old glibc, win-arm64) and falls through to the option A fetch. No PEP 508 markers are needed, and no sdist. |
| 6 | Linux tag | Tag honestly with the glibc floor of the build: `manylinux_2_39` for the `ubuntu-24.04` builds. This floor is a build input recorded per release, not a guess. Hosts with an older glibc get the fallback wheel. Lowering the floor (`--static-nolibc`, or an older builder) is an events-side follow-up. |
| 7 | Size | The build fails when any companion wheel exceeds **95 MB** and warns above 60 MB (plan §3.4). Splitting into one wheel per service is the documented escape, and needs its own amendment. Budget: roughly 4 × 60–85 MB per release against 10 GB, so old RC releases need pruning after about 30 releases. |
| 8 | Build | `scripts/build_services_wheel.py` reads the release commit's `pins/`, fetches every native target of every user-facing service through `kernel.service_artifacts.fetch_asset` (digest-verified; nothing is rebuilt), and writes the wheels deterministically with the standard library (`WHEEL`, `METADATA`, `RECORD`, `entry_points.txt`). It adds no build dependency. The Python source lives in `packages/spec-kitty-services/`, which is excluded from the CLI sdist. |
| 9 | Release job | A new `build-companion-wheels` job (`needs: build-release`) writes to `dist-services/`, not `dist/`, and runs `twine check`, the size cap and the digest guard. A separate `publish-companion-pypi` job uses its own environment (`pypi-services`) and a Trusted Publisher for the new project, and runs **before** `publish-pypi`, so the CLI's `==` extra can always resolve. **Operator action:** register `spec-kitty-services` on PyPI (a pending publisher) and create the environment. |
| 10 | Empty pins | With no pin, only the fallback wheel is built. The extra still resolves, and nothing ships a binary. |
| 11 | `sync_services.py` in `release.yml` | Cheap. Add `sync_services.py --service all` after the packs check: it fetches and digest-verifies the host's assets, so a later `--check` would not fail on a cold cache. The companion job's all-target verification is the stronger guard. Also add the service steps to `RELEASE_CHECKLIST.md`. |
| 12 | Slicing | One PR. The ADR amendment is its first commit. Nothing here is large enough to need stacked PRs. |
