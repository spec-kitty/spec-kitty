# Discovery: derive the companion wheel's platform floor from the binary (#6948)

Follow-up to #6904 (the optional `spec-kitty-services` companion wheel; ADR
2026-10-29-1, Amendment 2026-10-31). Findings gathered before the spec, on
`main` at `287a226cfe`.

## Grounding

The defect is live on current `main`:

- `scripts/build_services_wheel.py` reads the Linux floor from `--glibc-floor`
  (`release.yml` passes `2_39`) and the macOS floor from the constant
  `macosx_11_0_arm64` in `packages/spec-kitty-services/spec_kitty_services/wheel.py`
  (`_PLATFORMS`). Nothing reads either value from the pinned asset.
- `git log -S "glibc"`, `git log -S "minos"` and `git grep` for
  `version_r|LC_BUILD_VERSION|minos` find no binary-format reader anywhere in
  `src/`, `scripts/`, `tests/` or `packages/`: no partial fix exists.
- Not superseded: #6904 landed the builder (`0d37f75acb`) and a follow-up that
  made it runnable directly (`0ddf298468`), and `pins/` still holds only
  `README.md`, so no release binary exists to measure yet. The issue is the
  recorded follow-up, unassigned and uncommented until this Mission claimed it.

## Decisions

### D1 — The declared floor stays the tag; the measurement is a one-sided guard

The issue allows either "derive the tag from the binary" or "refuse when it is
above the declared tag". Decision: **refuse**. The tag keeps the declared floor
(`--glibc-floor`, and a new `--macos-floor`) and the build refuses when a
binary's measured floor is above it, with `SERVICE_PLATFORM_FLOOR_EXCEEDED`.

Why:

- The declared floor is a **release contract**, not a guess: `release.yml` ties
  the Linux floor to the `ubuntu-24.04` events builders
  (`docs/plans/events-domain-move/companion-wheel-research.md` §"Wheel tags and
  glibc", option 6: "This floor is a build input recorded per release"), and
  the 4.0.0rc8 changelog entry tells users "glibc 2.39 or newer".
- Deriving the tag silently would move that contract inside a release build:
  a runner upgrade would silently narrow the set of hosts that can install the
  companion (a user-visible change with no changelog, no operator decision).
- Deriving it also *widens* the claim when the measurement comes out lower
  (an events build on an older image), which is a change the events side owns.
- The failure mode in the issue is one-sided and is fully closed by the guard:
  "pip installs the platform wheel on a host older than what the binary needs".
- A refusal names the measured value and the remedy, so bumping the floor stays
  a deliberate, reviewable one-line change in `release.yml`.

The measurement is still *derived from the binary* — it is what decides whether
the tag is true — and it also reports the per-wheel maximum across the binaries
that wheel carries, which one global constant could not express.

### D2 — A wheel's floor is the maximum over the binaries it carries

A platform wheel carries the write service and the charter service. The tag must
satisfy both, so the measured floor is the maximum of each bundled binary's
floor, and the refusal names the asset that sets it.

### D3 — An unreadable asset on a floored target is a refusal, not a pass

`SERVICE_PLATFORM_FLOOR_UNREADABLE` refuses a linux/macOS asset whose headers
cannot be read (not an ELF/Mach-O, 32-bit, big-endian, a fat Mach-O, truncated,
or a Mach-O with no macOS build-version/min-version command). Silently falling
back to the declared floor is the very defect being fixed: an unmeasured tag is
an unchecked claim. Tests therefore stop using `#!/bin/sh` scripts as native
fixtures and use minimal real ELF/Mach-O headers, which is what the issue asks
for ("tests on small fixture ELF and Mach-O headers").

Windows (`win_amd64`) states no OS minimum, so it is not measured.

### D4 — Read the ELF floor from the version-need strings, not the version index

`.gnu.version_r` (`DT_VERNEED`) is reached through `PT_DYNAMIC`, so a stripped
GraalVM image with no section headers still works. Walk `Elf64_Verneed` →
`Elf64_Vernaux`, resolve `vna_name` through `DT_STRTAB`/`DT_STRSZ`, and take the
highest `GLIBC_<major>.<minor>[.<patch>]` name. Version *indexes* (`vna_other`)
are not a stable encoding of the glibc release, so they are not used. An ELF
with no `GLIBC_*` version need (static, or a non-glibc runtime) has no floor and
cannot exceed the declared one.

### D5 — Read the macOS floor from `LC_BUILD_VERSION` `minos`

Walk the load commands; `LC_BUILD_VERSION` (0x32) `minos`, platform macOS (1),
falling back to the deprecated `LC_VERSION_MIN_MACOSX` (0x24) when present. The
`minos` word is `xxxx.yy.zz`, so `11.0` becomes the floor `11_0`.

### D6 — Where the reader lives: `scripts/service_platform.py`

- Not `src/kernel/`: `tests/architectural/test_no_dead_modules.py` requires a
  caller under `src/`, and this reader's only caller is the release build
  script; an allowlist entry would be priced debt (charter, Standing Order #5).
- Not the companion package: `wheel.py` is copied verbatim into every wheel and
  the sdist (`_SOURCE_FILES`), so build-time-only code there would either ship
  or silently not ship, and the packaging invariants
  (`tests/cross_cutting/packaging/test_companion_package.py`) would need to
  explain the gap.
- `scripts/` already holds release tooling that imports `kernel` with
  `src` on the path, and the build script already puts the repo root on
  `sys.path`, so `from scripts.service_platform import ...` works both under
  `python scripts/build_services_wheel.py` and under pytest.

### D7 — `verify` measures the bundled bytes too

`--verify` rebuilds each wheel from its digest-verified bundled bytes and
compares names and bytes. It therefore also measures the floor of those bytes
and reports a wheel whose tag claims less than the binaries need: without that,
a wheel built with a too-low `--glibc-floor` would reproduce byte-for-byte and
pass.

### D8 — macOS floor becomes a build input, with the constant as its default

`macosx_11_0_arm64` becomes `_PLATFORMS["macos-arm64"] = "macosx_{macos}_arm64"`
filled from `DEFAULT_MACOS_FLOOR = "11_0"` (beside `DEFAULT_GLIBC_FLOOR`), and
`--macos-floor` lets `release.yml` raise it the way `--glibc-floor` already
allows. Both are validated up front, whether or not the target is pinned.

## Evidence

- `scripts/build_services_wheel.py:120-127` (`_floor`), `:269` (`--glibc-floor`),
  `packages/spec-kitty-services/spec_kitty_services/wheel.py:79-87`
  (`DEFAULT_GLIBC_FLOOR`, `_PLATFORMS`), `.github/workflows/release.yml:373-380`.
- `docs/plans/events-domain-move/companion-wheel-research.md` §"Wheel tags and
  glibc" (options 5 and 6: the fallback wheel for older hosts, and the floor as
  a recorded build input).
- `docs/adr/4.x/2026-10-29-1-...` D-4 (hosts older than what the binary needs
  fall back), D-5 (`SERVICE_UNSUPPORTED_PLATFORM` and the other refusal codes).
- `tests/cross_cutting/packaging/test_companion_services_wheel.py` (the
  pre-existing entry point for every build/verify assertion, including
  `test_the_glibc_floor_is_a_build_input`).
- Reference formats: ELF gABI (`Elf64_Phdr`, `Elf64_Dyn`, `Elf64_Verneed`,
  `Elf64_Vernaux`, `SHT_GNU_verneed`), `mach-o/loader.h`
  (`LC_BUILD_VERSION`, `LC_VERSION_MIN_MACOSX`), PEP 600 / PEP 425 (manylinux
  and `macosx_<major>_<minor>_<arch>` tags).

## Open questions (for specify/plan)

1. **Universal (fat) Mach-O.** Not supported: refused as unreadable with a
  message naming the reason. The events native job builds a thin arm64 image,
  so this costs nothing today; if a fat build ever appears, taking the maximum
  `minos` across slices is the follow-up. No issue filed — it is unreachable
  until such an asset exists.
2. **musl targets.** No companion target is musl, so there is no musl floor to
   read; `linux-*` is glibc-only by construction (`manylinux_*`).
3. **A measured floor below the declared one.** Kept silent (the tag stays the
   contract). If the events side lowers its builders, the operator lowers
   `--glibc-floor` in `release.yml` in a reviewed change with a changelog entry.
