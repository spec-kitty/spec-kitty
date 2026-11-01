# WP02 review — cycle 1

**Verdict: APPROVED.**

Diff under review: `git diff ea66bf9ef0..9d087aa3ff` on
`kitty/mission-companion-wheel-platform-floor-01M6BV24-lane-b`. Reviewed as an independent
reviewer under a different model from the implementer. No blocking defect found.

The guard is wired exactly where the spec demands: `build()` measures the pinned, digest-verified
bytes per platform target and refuses — with `SERVICE_PLATFORM_FLOOR_EXCEEDED` (asset, measured
floor, declared floor, and the `release.yml` remedy in the message) or
`SERVICE_PLATFORM_FLOOR_UNREADABLE` — while every wheel is still in the scratch directory, so no
refusal can follow a wheel into `--out` (`scripts/build_services_wheel.py:212-215`; the move to
`--out` happens only after all builds and the size gate, lines 225-226). `--verify` re-measures
the bundled bytes against the floor taken from **the wheel's own file name**
(`scripts/build_services_wheel.py:295-301`, `_tag_floor` at 173), so a wheel tagged below what its
binaries need fails however it was built — this is exactly the FR-008 trap (byte-identical rebuild
alone could never catch it). The macOS floor is a validated build input
(`packages/spec-kitty-services/spec_kitty_services/wheel.py`, `DEFAULT_MACOS_FLOOR = "11_0"`,
`platform_tag(..., macos_floor=)`) and both floors are validated up front whether or not the
platform is pinned (FR-009).

Constraints C-001/C-002 hold: defaults are `2_39` / `11_0`, `release.yml` passes those same values
explicitly, the tag templates render the same strings as before, and no wheel or sdist member is
added or removed — the reader ships in `scripts/`, not in the wheel.

## Anti-pattern checklist

| # | Item | Result | Evidence |
|---|------|--------|----------|
| 1 | Dead code | **PASS** | WP01's condition is discharged: `scripts/service_platform.py` now has its production caller (`scripts/build_services_wheel.py:62`); every new helper (`_declared_floors`, `_floor_violation`, `_tag_floor`) is reachable from `build`/`verify`/`main`. |
| 2 | Synthetic-fixture test | **PASS** | The `_assets`/`_repo` fixtures now build real ELF64/Mach-O/PE headers via WP01's `native_asset`/`elf64`/`macho64`/`pe64`; tests drive the shipped CLI entry point end-to-end (fake checkout, file:// release, real pin path). WP01 already proved the reader agrees with `readelf` on a real system binary, so the fixtures do not encode the answer. The verify-understatement test builds a real wheel through the real writer. |
| 3 | Silent empty return | **PASS** | No bare `except`. The two silent-`None` windows WP01's review flagged are closed: a version-need table without `DT_STRTAB`/`DT_VERNEEDNUM` is now `UnreadableBinary` (`scripts/service_platform.py:166-168`), a Mach-O load command past EOF is refused (`scripts/service_platform.py:294`), and `required_floor` re-raises naming the asset (`scripts/service_platform.py:129`). Remaining `None` returns are the spec-sanctioned "states no floor" cases. |
| 4 | FR coverage | **PASS** | FR-003 per-wheel max: `test_the_wheel_floor_is_the_maximum_over_its_binaries` (charter asset at 2_42 named, write-service at 2_39 not). FR-004: both refusal tests assert code, asset, both floors, remedy, and zero wheels written. FR-007: `--macos-floor` build-input test + workflow flag. FR-008: `test_verify_fails_a_wheel_whose_tag_understates_its_binaries`. FR-009: `test_a_bad_macos_floor_fails_even_without_a_macos_target` + `platform_tag` validation tests. SC-001–SC-004 have tests; SC-005 via `--help`, workflow comment, changelog. |
| 5 | Frozen surface | **PASS** | Single commit `9d087aa3ff`; `git status` clean; no edits outside the WP02 owned-files list except the two declared out-of-map files (item 7). No docs page, contract, or service surface touched. |
| 6 | Locked decision | **PASS** | Decision `01M6BV2A16NMD5QA4VZ8B814HW` (the tag is declared, never derived): the remedy tells the maintainer to raise the floor in `release.yml`, the module docstring states "it is never derived from the binaries inside a build", and `_floor_violation` only ever refuses. C-003 kept: exit 1, stable codes, stderr ordering, "no wheel on failure", size-gate position unchanged. |
| 7 | Shared-file ownership | **PASS (judged exception)** | `scripts/service_platform.py` and `tests/cross_cutting/packaging/test_service_platform.py` are WP01-owned. The touches are exactly WP01 review findings 1–2 plus naming the unreadable asset — required because WP02's build is the module's only caller and its refusals must name the binary. Changes are additive and fail-closed; all WP01 tests still pass in the merged suite. WP01 finding 3 (cosmetic `floor_kind` wording) is deliberately untouched, as that review itself recommended. |
| 8 | Production fragility | **PASS** | Refusal precedes any write into `--out` (scratch-dir invariant preserved). Verify's floor comparison uses the tag claimed by the wheel's file name, not just the declared flag, so a stale or low tag is caught regardless of the flags verify is run with. Both new codes are module constants beside the existing `COMPANION_*` set; the malformed-floor path re-raises the writer's `ValueError` as `COMPANION_BUILD_FAILED` exactly as before. |

## Explicit answers to the things that could really be wrong

- **Per-wheel maximum over the right binaries:** yes — the measurement dict is built per target
  from pins `if target in pin.assets` only (`scripts/build_services_wheel.py:203-213`), so the max
  is over the binaries *that wheel* carries, not over all pins.
- **Refusal after a wheel is written:** no — all wheels are built into a mkdtemp scratch dir and
  moved into `--out` only after every build and size check succeeds; a `BuildError` falls into the
  `finally: rmtree(scratch)`.
- **`--verify` catching an understated tag:** yes — `claimed[kind]` is overridden with the floor
  parsed out of the wheel's own file name (`_tag_floor`), so the comparison is against the tag the
  wheel claims, independent of the declared flags.
- **Published tags / wheel contents unchanged (C-001/C-002):** yes — defaults `2_39`/`11_0`,
  `release.yml` passes the same values, templates render identically, and the
  reproducibility/member-list tests (SC-002) pass unchanged.
- **Changelog style:** yes — bold impact-first lead, `(#6948)`, marked **Before**/**After**, 867
  characters (< 1,200), no heading; `check_changelog_style` reports 0 errors and no warning on the
  new fragment; `check_spelling --pass unreleased` clean.

## Findings (all non-blocking)

1. **Test shape deviation from T005.7 (improvement, accept).** The prompt prescribed verifying the
   understated wheel *with the same* `--glibc-floor 2_28`; the shipped test instead builds the
   2_28-tagged wheel directly through the writer and verifies with default flags. Because the
   implementation compares against the tag in the file name, this proves the stronger property —
   the understatement is caught whatever the declared flag is. `test_companion_services_wheel.py`,
   `test_verify_fails_a_wheel_whose_tag_understates_its_binaries`.
2. **Refusal message wording.** The message omits the prompt's literal "from its `<source>`"
   phrase but carries target, asset, kind, measured floor, declared floor, and remedy
   (`scripts/build_services_wheel.py:165-169`) — the substance FR-004 requires.
3. **Follow-up at merge time:** T009 says to rename
   `docs/changelog/unreleased/6948-platform-floor.fixed.md` to the PR number once the PR exists and
   record it in the WP history.

## Validation run by the reviewer (lane worktree)

- `uv run --frozen pytest tests/cross_cutting/packaging/ -q` → **214 passed, 1 skipped** (94.8s)
- `uv run --frozen pytest tests/release/ -q` → **277 passed, 6 skipped** (18.6s)
- `test_companion_services_wheel.py` collects 49 tests (38 pre-change + 11 new/changed cases)
- `uvx ruff check scripts/build_services_wheel.py scripts/service_platform.py packages/spec-kitty-services/spec_kitty_services/wheel.py` → **All checks passed**
- `uv run --frozen python -m scripts.docs.check_changelog_style` → **0 errors** (no warning cited for the new 6948 fragment)
- `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased` → **0 findings**
