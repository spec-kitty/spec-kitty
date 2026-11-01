---
work_package_id: WP02
title: Refuse a companion wheel whose tag understates its binaries
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-007
- FR-008
- FR-009
- NFR-002
- C-001
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
- SC-005
- NFR-004
- C-002
planning_base_branch: issue-6948-companion-wheel-platform-floor
merge_target_branch: issue-6948-companion-wheel-platform-floor
branch_strategy: Planning artifacts for this mission were generated on issue-6948-companion-wheel-platform-floor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6948-companion-wheel-platform-floor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-companion-wheel-platform-floor-01M6BV24
base_commit: e28a174fc9e059d89d36db127a12492f0a278456
created_at: '2026-11-01T16:48:06.810799+00:00'
subtasks:
- T005
- T006
- T007
- T008
- T009
phase: Phase 2 - The guard
history:
- at: '2026-11-01T15:30:00Z'
  actor: planner
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/build_services_wheel.py
create_intent:
- docs/changelog/unreleased/6948-platform-floor.fixed.md
execution_mode: code_change
model: ''
owned_files:
- scripts/build_services_wheel.py
- packages/spec-kitty-services/spec_kitty_services/wheel.py
- .github/workflows/release.yml
- tests/cross_cutting/packaging/test_companion_services_wheel.py
- tests/cross_cutting/packaging/test_companion_package.py
- docs/changelog/unreleased/6948-platform-floor.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Refuse a companion wheel whose tag understates its binaries

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter
**before parsing the rest of this prompt**, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile list` and select the best match for
`task_type: implement` on `authoritative_surface: scripts/build_services_wheel.py`.

## Objective

Wire WP01's reader into the two entry points that decide what ships:

- `scripts/build_services_wheel.py --out` measures every binary it is about to bundle and **refuses**
  (`SERVICE_PLATFORM_FLOOR_EXCEEDED`) when one needs a newer OS than the declared floor, naming the
  asset, the measured floor and the remedy; a binary whose floor cannot be read is refused too
  (`SERVICE_PLATFORM_FLOOR_UNREADABLE`). No wheel is written on a refusal.
- `--verify` re-measures the bytes inside each wheel, so a wheel built with a too-low declared floor
  cannot pass verification.
- The macOS floor becomes a build input (`--macos-floor`, default `11_0`) beside `--glibc-floor`.

Read first: [spec.md](../spec.md) (FR-003…FR-009, C-001…C-003), [research.md](../research.md) (D1,
D2, D3, D7, D8), [data-model.md](../data-model.md) (state transitions).

## Hard constraints

- **The tag does not move.** The wheel is still tagged with the *declared* floor. This WP adds a
  guard, not a derivation (decision `01M6BV2A16NMD5QA4VZ8B814HW`).
- **No new fetch, no new file in a wheel.** Floors are read from the bytes the build already
  fetched and digest-verified; the wheels' members and the sdist are unchanged.
- **Existing contract kept.** Exit 1, a stable `SERVICE_*`/`COMPANION_*` code on stderr, the
  "no wheel written on failure" behaviour, and the size gate's place in the order all stay as they
  are.

## Subtasks

### T005 — Red end-to-end tests through the pre-existing entry point

Extend `tests/cross_cutting/packaging/test_companion_services_wheel.py`. Switch its `_assets()`
helper to real native fixture bytes via WP01's `native_asset(...)` (ELF per Linux target, Mach-O for
`macos-arm64`, PE for `windows-x64`), keeping the jar entry it already carries. Then add, failing
first:

1. `test_a_linux_asset_that_needs_more_than_the_declared_floor_refuses` — `elf64(glibc="2_42")` on
   `linux-x64`, default floor: exit 1, `SERVICE_PLATFORM_FLOOR_EXCEEDED` on stderr, the asset name
   and both floors in the message, and `--out` holds no wheel.
2. `test_a_macos_asset_that_needs_more_than_the_declared_floor_refuses` — `macho64(minos="12_0")`:
   same shape, same code.
3. `test_the_wheel_floor_is_the_maximum_over_its_binaries` — the write service at `2_39`, the
   charter service at `2_42`: the refusal names the **charter** asset.
4. `test_a_binary_floor_at_the_declared_floor_is_accepted` (positive control on the same fixture
   shape) — `2_39`/`11_0` binaries build the same five wheels.
5. `test_an_unreadable_asset_is_refused` — a `#!/bin/sh` asset pinned for `linux-x64`: exit 1,
   `SERVICE_PLATFORM_FLOOR_UNREADABLE`, the asset named, no wheel.
6. `test_windows_assets_are_not_measured` — a `windows-x64` asset of any shape still builds
   `win_amd64`.
7. `test_verify_fails_a_wheel_whose_tag_understates_its_binaries` — build with
   `--glibc-floor 2_28` from binaries that need `2_39`, then `--verify` **with the same**
   `--glibc-floor 2_28`: the rebuild is byte-identical, so only the measurement can catch it.
8. `test_a_bad_macos_floor_fails_even_without_a_macos_target` — the macOS half of the existing
   glibc validation test.

### T006 — `build`: measure, compare, refuse; the macOS floor input

In `scripts/build_services_wheel.py`:

- Replace `_floor()` with `_declared_floors(writer, glibc_floor, macos_floor) -> dict[str, str]`
  keyed by floor kind, validated up front through the writer (so both floors are checked whether or
  not that platform is pinned), re-raising the writer's `ValueError` as `COMPANION_BUILD_FAILED`
  exactly as today.
- In `build()`, per target with binaries, call `service_platform.required_floor(target, binaries)` and
  compare with the declared floor for that kind. Above → `BuildError(SERVICE_PLATFORM_FLOOR_EXCEEDED,
  …)`; `UnreadableBinary` → `BuildError(SERVICE_PLATFORM_FLOOR_UNREADABLE, …)`. Both before anything
  is written into `--out` (the scratch-dir pattern already guarantees it — keep it).
- Message shape (stable prefix, then the specifics):
  `<target>: <asset> needs <kind> <measured> from its <source>, above the <declared> the wheel tag
  would claim; raise <--glibc-floor|--macos-floor> to <measured> in release.yml, or pin a build that
  does not need it`
- Pass `macos_floor=` through to `writer.build_companion_wheel(...)`.
- Add `SERVICE_PLATFORM_FLOOR_EXCEEDED` and `SERVICE_PLATFORM_FLOOR_UNREADABLE` as module-level
  constants beside the existing `COMPANION_*` ones, and mention both in the module docstring.
- `--macos-floor` argument with help text mirroring `--glibc-floor`; update the `--glibc-floor` help
  to say the tag is now checked against the binaries.
- Import the reader at the top, after the existing `sys.path` bootstrap:
  `from scripts.service_platform import UnreadableBinary, required_floor` (the script already puts
  the repo root on `sys.path` before its `kernel` imports — reuse that, keep the `# noqa: E402`
  convention).

### T007 — The companion writer: the macOS floor becomes a parameter

In `packages/spec-kitty-services/spec_kitty_services/wheel.py`:

- `DEFAULT_MACOS_FLOOR = "11_0"` beside `DEFAULT_GLIBC_FLOOR`, and add it to `__all__`.
- `_PLATFORMS["macos-arm64"] = "macosx_{macos}_arm64"`.
- `platform_tag(target, glibc_floor=DEFAULT_GLIBC_FLOOR, macos_floor=DEFAULT_MACOS_FLOOR)`: validate
  both floors against `_FLOOR` before resolving the target (so a bad macOS floor refuses even when
  the target is Windows), then format the template.
- `build_companion_wheel(..., glibc_floor=DEFAULT_GLIBC_FLOOR, macos_floor=DEFAULT_MACOS_FLOOR)`.
- Keep the docstring's "one authority for the wheel layout" claim true: the tag templates stay the
  only copy.
- `tests/cross_cutting/packaging/test_companion_package.py` asserts wheel member lists and tags;
  update only what the new parameter legitimately changes (nothing should need to change — prove it
  rather than editing expectations away).

### T008 — `--verify` re-measures the bundled bytes

In `verify()` / `_wheel_problems()`: after the digest checks pass and before/instead of relying on
the rebuild, compute `required_floor(manifest.target, verified_binaries)` from the bytes read out of
the wheel, and append a problem when it exceeds the declared floor for that kind, or when the bytes
cannot be read. Keep the deterministic-rebuild comparison as it is. A wheel whose binaries are at or
below the floor must still verify clean.

### T009 — Say the new rule where a maintainer will look

- `.github/workflows/release.yml`: the comment above the build step now says the declared floor is
  the tag and that the build checks it against the pinned binaries; add the `--macos-floor` flag
  next to `--glibc-floor` only if it makes the two steps no less readable (do not change behaviour
  or reorder steps).
- `docs/changelog/unreleased/6948-platform-floor.fixed.md`: one entry, bold impact-first lead with
  `(#6948)`, before/after, under 1,200 characters, US spelling, no heading. Content: the build now
  reads the OS floor out of each pinned service binary and refuses a companion wheel whose tag
  would understate it (`SERVICE_PLATFORM_FLOOR_EXCEEDED` / `SERVICE_PLATFORM_FLOOR_UNREADABLE`),
  and `--macos-floor` is the new build input; nothing changes for users installing today's wheels.
  Rename the file to `<pr>.fixed.md` once the PR number exists (record it in the WP history).

## Files

| Path | Action |
|------|--------|
| `scripts/build_services_wheel.py` | measure, refuse, `--macos-floor`, docstring/help |
| `packages/spec-kitty-services/spec_kitty_services/wheel.py` | `macos_floor` parameter + constant |
| `.github/workflows/release.yml` | one comment, truthfully describing the check |
| `tests/cross_cutting/packaging/test_companion_services_wheel.py` | native fixtures + the 8 tests above |
| `tests/cross_cutting/packaging/test_companion_package.py` | only if a tag expectation legitimately moves |
| `docs/changelog/unreleased/6948-platform-floor.fixed.md` | create |

## Validation

```bash
uv run --frozen pytest tests/cross_cutting/packaging/ -q
uv run --frozen pytest tests/release/ -q
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
uv run --frozen ruff check scripts/build_services_wheel.py packages/spec-kitty-services tests/cross_cutting/packaging
```

Record counts. Do **not** run `tests/architectural/` as a sweep, e2e or performance suites; run the
specific gate files only if the diff implicates them (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Definition of done

- Every new refusal is proven through `build()` and `verify()` on a fixture that fails red before the
  change, each with a same-fixture positive control (SC-001…SC-004).
- The five wheels built from `2_39` / `11_0` fixtures are named and byte-identical to the pre-change
  build (SC-002) — prove it with the existing reproducibility and member-list tests.
- `--help` names both floors, and `release.yml` no longer implies the floor is unchecked (SC-005).
- Changelog fragment passes its style and spelling gates.
- No wheel member, sdist member or published tag changes (C-001, C-002).
