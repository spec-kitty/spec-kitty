---
work_package_id: WP01
title: Platform floor reader for ELF and Mach-O binaries
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-005
- FR-006
- NFR-001
- NFR-003
- C-004
planning_base_branch: issue-6948-companion-wheel-platform-floor
merge_target_branch: issue-6948-companion-wheel-platform-floor
branch_strategy: Planning artifacts for this mission were generated on issue-6948-companion-wheel-platform-floor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6948-companion-wheel-platform-floor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-companion-wheel-platform-floor-01M6BV24
base_commit: e28a174fc9e059d89d36db127a12492f0a278456
created_at: '2026-11-01T15:24:16.922545+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - The reader
history:
- at: '2026-11-01T15:30:00Z'
  actor: planner
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/service_platform.py
create_intent:
- scripts/service_platform.py
- tests/cross_cutting/packaging/test_service_platform.py
execution_mode: code_change
model: ''
owned_files:
- scripts/service_platform.py
- tests/cross_cutting/packaging/test_service_platform.py
- tests/kernel/service_release_fixture.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Platform floor reader for ELF and Mach-O binaries

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter
**before parsing the rest of this prompt**, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile list` and select the best match for
`task_type: implement` on `authoritative_surface: scripts/service_platform.py`.

## Objective

Ship one small, pure-standard-library module that answers, for a native service binary, "what OS
floor does this binary need" — `2_39` for Linux, `11_0` for Apple Silicon macOS — and raises a
named refusal when it cannot tell. It ships no behaviour change on its own: WP02 wires it into the
release build.

Read first: [spec.md](../spec.md) (Domain Language, FR-001/FR-002/FR-005), [research.md](../research.md)
(D4, D5, D6), [data-model.md](../data-model.md) (PlatformFloor, WheelFloor, invariants).

## Where the code goes, and why

`scripts/service_platform.py`, beside the release build script that will be its only caller.

- **Not** `src/kernel/`: `tests/architectural/test_no_dead_modules.py` requires a caller under
  `src/`, and this module's only caller is release tooling. An allowlist entry there is priced debt
  (charter, Standing Order #5).
- **Not** the companion package: `spec_kitty_services/wheel.py` is copied verbatim into every wheel
  and the sdist (`_SOURCE_FILES`), so a build-time-only module there would either ship or silently
  not ship.

The module must import only the standard library (`struct`-free is fine and preferred: parse with
`int.from_bytes`), so it can be loaded by path from a test and from the build script without
`src` on the path.

## Subtasks

### T001 — Red tests first: native fixture headers and the reader's happy paths

Extend `tests/kernel/service_release_fixture.py` (which the companion-wheel tests already import)
with builders that produce **short but structurally valid** native binaries:

- `elf64(*, glibc: str = "2_39", extra: dict[str, str] | None = None) -> bytes` — an ELF64
  little-endian executable with a `PT_DYNAMIC` segment holding `DT_STRTAB`, `DT_STRSZ`,
  `DT_VERNEED` and `DT_VERNEEDNUM`, a `.gnu.version_r`-shaped table (`Elf64_Verneed` plus
  `Elf64_Vernaux` entries for `libc.so.6`) and a string table with the `GLIBC_x.y` names. A few
  hundred bytes is plenty; do not pad it.
- `macho64(*, minos: str = "11_0", futures: bool = False) -> bytes` — a thin 64-bit little-endian
  Mach-O with `LC_BUILD_VERSION` (platform macOS) carrying `minos`; `futures=True` emits the
  deprecated `LC_VERSION_MIN_MACOSX` command instead.
- `pe64() -> bytes` — a minimal `MZ`/`PE\0\0` shaped blob, only because the fixture builder also
  serves the Windows target (no floor there).
- `native_asset(target, **kw) -> bytes` — dispatches on the `ServiceTarget` so the companion-wheel
  tests can stop using `#!/bin/sh` scripts as native fixtures.

Then write `tests/cross_cutting/packaging/test_service_platform.py` covering, **before** the module
exists (so it fails red for the right reason):

- `read_floor(elf64(glibc="2_39"), "linux-x64") == "2_39"`, same for `linux-arm64`;
- `read_floor(macho64(minos="11_0"), "macos-arm64") == "11_0"`;
- the highest of several `GLIBC_*` names wins, and `GLIBC_2.2.5` normalizes to `2_2`;
- an ELF with no `GLIBC_*` version need returns `None` (static / non-glibc);
- `futures=True` Mach-O reads its version from `LC_VERSION_MIN_MACOSX`;
- `read_floor(pe64(), "windows-x64") is None` (no floor kind);
- `floor_kind("windows-x64") is None`, and the three floored targets map to their kinds.

### T002 — Target → floor kind, and the ELF reader

`scripts/service_platform.py`:

- `GLIBC = "glibc"`, `MACOS = "macos"`, and one map from target string to kind or `None`
  (single canonical authority for "does this target's tag state a floor"). The target strings are
  `kernel.service_pin.ServiceTarget` values (`linux-x64`, `linux-arm64`, `macos-arm64`,
  `windows-x64`); an unknown target is a `ValueError`, not a silent `None`.
- `read_floor(data: bytes, target: str) -> str | None` — dispatch to the reader for the kind.
- `UnreadableBinary(ValueError)` carrying the reason in its message.

ELF path (ELF64, little-endian only; the companion has no 32-bit and no big-endian target):

1. `e_ident` magic `\x7fELF`, `EI_CLASS=2`, `EI_DATA=1`, otherwise `UnreadableBinary` with a message
   naming what was found (e.g. "32-bit ELF", "big-endian ELF", "not an ELF file").
2. Program headers (`e_phoff`, `e_phentsize`, `e_phnum`): find `PT_DYNAMIC` (2).
3. Dynamic entries (`Elf64_Dyn`: tag, value): `DT_STRTAB` (5), `DT_STRSZ` (10), `DT_VERNEED`
   (0x6ffffffe), `DT_VERNEEDNUM` (0x6fffffff).
4. Translate each virtual address to a file offset through the `PT_LOAD` segments.
5. Walk `DT_VERNEEDNUM` `Elf64_Verneed` entries and each one's `vn_cnt` `Elf64_Vernaux` entries;
   resolve `vna_name` through the string table; match `^GLIBC_(\d+)\.(\d+)(?:\.(\d+))?$`; return
   the highest as `<major>_<minor>`.
6. No `PT_DYNAMIC` (statically linked) or no `GLIBC_*` name → `None`.
7. Every read is bounds-checked against `len(data)`; a truncated or inconsistent structure raises
   `UnreadableBinary` with a reason. Never let a `struct.error`, `IndexError` or `ValueError` from
   parsing escape as anything but `UnreadableBinary`.

Do not use section headers: a stripped GraalVM image keeps only program headers.

### T003 — The Mach-O reader

Mach-O path (thin 64-bit):

1. Magic `\xcf\xfa\xed\xfe` (MH_MAGIC_64, little-endian). A universal/fat binary
   (`\xca\xfe\xba\xbe` / `\xbe\xba\xfe\xca`) and 32-bit options raise `UnreadableBinary` with a
   message that names the shape ("universal (fat) Mach-O", "32-bit Mach-O").
2. Walk `ncmds` load commands from offset 32, honouring `cmdsize` (a `cmdsize < 8` or a walk past
   the end is `UnreadableBinary`, so a corrupt header cannot loop forever).
3. `LC_BUILD_VERSION` (0x32) with platform macOS (1): `minos` is `xxxx.yy.zz` → `<major>_<minor>`.
   A `LC_BUILD_VERSION` for another platform (iOS, macCatalyst) is not a macOS floor.
4. Fall back to `LC_VERSION_MIN_MACOSX` (0x24) `version` when no macOS `LC_BUILD_VERSION` is
   present.
5. Neither command present → `UnreadableBinary` ("no macOS build-version command").

### T004 — The per-wheel maximum, the comparison, and the refusal surface

- `required_floor(target: str, binaries: Mapping[str, bytes]) -> FloorNeed | None` — the maximum
  measured floor over the binaries, with the asset name that sets it. Deterministic: compare
  numerically, and break ties by sorted asset name. `None` when the target states no floor or no
  binary states one.
- `FloorNeed(floor: str, asset: str)` — a small frozen dataclass.
- `exceeds(measured: str, declared: str) -> bool` — numeric, per component, never lexicographic
  (`2_39` > `2_9`).
- `parse_floor(value: str) -> tuple[int, int]` — validates `^\d+_\d+$` and raises
  `ValueError` otherwise; the build script turns that into its existing refusal code.
- `__all__` naming the public surface (house convention, C-007 in the charter).

## Files

| Path | Action |
|------|--------|
| `scripts/service_platform.py` | create |
| `tests/cross_cutting/packaging/test_service_platform.py` | create |
| `tests/kernel/service_release_fixture.py` | extend with the native-header builders (additive; every existing export keeps its behaviour) |

## Validation

Run exactly these, from the repository root, and record counts in the PR:

```bash
uv run --frozen pytest tests/cross_cutting/packaging/test_service_platform.py -q
uv run --frozen pytest tests/cross_cutting/packaging/test_companion_services_wheel.py -q
uv run --frozen ruff check scripts/service_platform.py tests/cross_cutting/packaging/test_service_platform.py tests/kernel/service_release_fixture.py
uv run --frozen mypy src/kernel/service_pin.py --strict   # the module must not add a src/ dependency; smoke check only
```

Do **not** run the full architectural, e2e or performance sweeps: CI owns those
(`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Definition of done

- The new module exists, imports only the standard library, and its docstring says what it reads
  and why it is build-time-only.
- Happy paths, the no-floor case, the deprecated-command fallback, and every unreadable shape are
  covered by tests that fail before the code and pass after.
- `python -c "from scripts.service_platform import read_floor"` style import works from the repo
  root, and loading the module by file path works too (no package-relative imports).
- No change to any existing behaviour: the companion-wheel tests still pass unchanged.
