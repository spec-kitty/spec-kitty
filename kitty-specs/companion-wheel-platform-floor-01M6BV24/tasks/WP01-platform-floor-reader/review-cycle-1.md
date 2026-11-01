# Review cycle 1 — WP01 (platform floor reader)

**Reviewer**: `claude` on profile `reviewer-renata` · **Date**: 2026-11-01
**Diff**: `ea66bf9ef0 feat(WP01): read the platform floor out of an ELF or Mach-O binary (#6948)`
(`scripts/service_platform.py` 297 lines, `tests/cross_cutting/packaging/test_service_platform.py`, `tests/kernel/service_release_fixture.py`)

## Verdict: APPROVED (no changes requested)

## Anti-pattern checklist

| # | Item | Result | Evidence |
|---|------|--------|----------|
| 1 | Dead code | N/A at WP level | The module's only caller is WP02 (`scripts/build_services_wheel.py`), a declared dependency of this WP, and the mission's aggregate review verifies the caller exists at the tip. Shipping the reader and its tests as their own reviewed slice is the plan's IC-01/IC-02 split; if WP02 were dropped, this module must be deleted with it. |
| 2 | Synthetic-fixture test | PASS | Every test calls the production reader (`read_floor`, `required_floor`, `exceeds`, `parse_floor`). Deleting `scripts/service_platform.py` makes the module fail to import: 48 errors, re-run to confirm red. The fixtures are bytes, not dicts, and the code under test parses them. |
| 3 | Silent empty return | PASS with reasons | `return None` appears at four points in `_elf_floor`, each documented: no `PT_DYNAMIC` (statically linked), no `DT_VERNEED`/`DT_STRTAB`, `DT_VERNEEDNUM == 0`, and no `GLIBC_*` name. Each means "this binary states no glibc floor", which the spec's edge cases require (FR-001, data-model). No `except: pass`, no bare `pass`. |
| 4 | FR coverage | PASS | FR-001 (ELF version needs) — `test_the_glibc_floor_is_the_highest_version_need`, `test_several_version_needs_resolve_to_the_highest`, `test_a_glibc_floor_is_found_through_a_stripped_image`; FR-002 (Mach-O `minos`) — `test_the_macos_floor_is_the_build_version_minos`, `test_the_deprecated_minimum_command_is_read_when_it_is_all_there_is`; FR-005 (unreadable refused) — ten parametrised shapes plus `test_a_corrupt_mach_o_load_command_cannot_loop_or_overrun`; FR-006 (Windows unmeasured) — `test_windows_states_no_floor_and_is_never_measured`. |
| 5 | Frozen surface | PASS | `git log --oneline kitty/mission-…-01M6BV24..HEAD` touches no `services/`, `contracts/` or frozen docs page (ADR 2026-10-29-1 D-9). |
| 6 | Locked decision | PASS | No tag is derived or moved here; the module only reports a measured floor (decision `01M6BV2A16NMD5QA4VZ8B814HW`, constraint C-001). |
| 7 | Shared-file ownership | PASS | WP01 owns all three touched paths; WP02 owns none of them. |
| 8 | Production fragility | PASS | Every `raise` is a `UnreadableBinary` refusal with a reason (the build turns it into a stable code). No request/worker path, no retry logic. |

## Live evidence beyond the fixtures

The reader was run against real binaries on this host and compared with `objdump -T`:

```
/bin/ls          reader=2_38   objdump max GLIBC_2.38
/usr/bin/python3 reader=2_38   objdump max GLIBC_2.38
/usr/bin/git     reader=2_38   objdump max GLIBC_2.38
/usr/lib/klibc/bin/cpio (statically linked, stripped)  -> None
/usr/lib/klibc/bin/sleep (statically linked, stripped) -> None
```

Agreement on all five, including the static case and a stripped image: the parse path is real, not
fixture-shaped.

## Notes (no change requested)

- `_cstring` decodes with `errors="replace"`; a non-UTF-8 name simply fails the `GLIBC_` match and
  contributes no floor. That is the conservative direction (the declared floor stands) and cannot
  invent a floor.
- `_macho_floor` prefers `LC_BUILD_VERSION` over `LC_VERSION_MIN_MACOSX` when an image carries
  both, as planned. A real arm64 image carries one or the other.
- `e_phentsize` is used as given; every read is bounds-checked against the file length, so a bogus
  value produces a refusal, not an overrun.

## Tests run

```
uv run --frozen pytest tests/cross_cutting/packaging/test_service_platform.py -q      # 48 passed
uv run --frozen pytest tests/cross_cutting/packaging/test_companion_services_wheel.py -q  # 38 passed
uvx ruff check scripts/service_platform.py tests/cross_cutting/packaging/test_service_platform.py tests/kernel/service_release_fixture.py  # clean
```
