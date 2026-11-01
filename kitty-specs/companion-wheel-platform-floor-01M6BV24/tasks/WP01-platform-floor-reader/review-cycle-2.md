# WP01 review — cycle 2

**Verdict: APPROVED.**

The diff adds `scripts/service_platform.py` (pure-stdlib ELF/Mach-O platform-floor reader),
`tests/cross_cutting/packaging/test_service_platform.py` (48 tests), and native-header fixture
builders in `tests/kernel/service_release_fixture.py`. It implements the WP01 prompt faithfully:
FR-001/FR-002 (floors read from the binaries), FR-005 (unreadable shapes refused with a reason),
FR-006 (Windows never measured), with numeric per-component comparison and a deterministic
per-wheel maximum. No blocking defect found; three non-blocking observations are recorded below
for WP02 or a follow-up.

Validation run by the reviewer, from the lane worktree:

- `uv run --frozen pytest tests/cross_cutting/packaging/test_service_platform.py -q` → **48 passed** (5.43s)
- `uv run --frozen pytest tests/cross_cutting/packaging/test_companion_services_wheel.py -q` → **38 passed** (fixture change is regression-clean; DoD "no change to existing behaviour" holds)
- `uvx ruff check` on the three touched files → **All checks passed**
- `uv run --frozen python -c "from scripts.service_platform import read_floor"` → works from repo root; the test module also loads it by file path
- Extra evidence beyond fixtures: the reader was run against real glibc-linked system binaries —
  `/usr/bin/ls` → `2_38`, `/usr/bin/python3` → `2_38`, `/bin/cat` → `2_34` — and `readelf -V
  /usr/bin/ls` confirms the highest version need is `GLIBC_2.38`. The reader agrees with
  `readelf` on a real, stripped-toolchain-produced ELF.

## Anti-pattern checklist

| # | Item | Result | Evidence |
|---|------|--------|----------|
| 1 | Dead code | **PASS** (sequenced, not orphaned) | `grep -rn "service_platform" src/ scripts/ packages/` finds zero production callers today — but that is the WP's declared design: the WP prompt says "It ships no behaviour change on its own: WP02 wires it into the release build", plan IC-02 reserves `scripts/build_services_wheel.py` (the caller) for WP02, and `lanes.json` lane-b depends on lane-a. The module is in `scripts/` precisely so the `src/`-only no-dead-modules gate (`tests/architectural/test_no_dead_modules.py` walks `src/` only) does not fire on the interim state. **Condition:** mission review must verify WP02 actually lands the callers. |
| 2 | Synthetic-fixture test | **PASS** | The fixtures (`elf64`/`macho64`/`pe64`/`native_asset`) construct real ELF64/Mach-O header bytes; the tests execute the production reader over them and assert on its parsed output. Deleting `scripts/service_platform.py` makes the module-load fixture fail and every test error — the FRs are genuinely exercised. Cross-checked against a real system binary (see above), so the fixtures are not encoding the answer the reader wants to hear. |
| 3 | Silent empty return | **PASS** | Only `except KeyError` exists (`scripts/service_platform.py:99`) and it re-raises as `ValueError`. All five `return None` sites (111, 122, 160, 163, 171) are the spec-sanctioned "target states no floor / binary states no floor" cases, each with an inline comment; see Finding 1 for one narrow edge inside the line-162 guard that could be tighter. |
| 4 | FR coverage | **PASS** | FR-001: `test_the_glibc_floor_is_the_highest_version_need`, `test_several_version_needs_resolve_to_the_highest`, `test_a_three_part_version_name_normalizes_to_major_minor`, stripped-image test, plus the real-binary check. FR-002: `test_the_macos_floor_is_the_build_version_minos`, `test_a_newer_minos_is_reported_as_is`, deprecated-command fallback test. FR-005: `test_an_unreadable_binary_is_refused_with_a_reason` (10 shapes), corrupt-load-command test, mislabelled-asset test. FR-006: `test_windows_states_no_floor_and_is_never_measured`. NFR/C refs are tracked, not gated. |
| 5 | Frozen surface | **PASS** | The single WP commit (`ea66bf9ef0`) touches exactly the three owned files. `git log kitty/mission-...-01M6BV24..HEAD -- services/ contracts/` is empty; the frozen docs page is untouched. |
| 6 | Locked decision | **PASS** | C-004: the reader touches only the passed bytes — no `subprocess`, no rebuild, no host-version consultation (`grep` confirms the only imports are `re`, `collections.abc`, `dataclasses`). NFR-001: stdlib only; `pyproject.toml`/`uv.lock` unchanged (not in the commit). Spec/plan MUST NOT clauses (never rebuild/re-sign/patch, never consult the host's glibc/macOS version) are all respected. |
| 7 | Shared-file ownership | **N/A** | `lanes.json`: WP01's write scope (`scripts/service_platform.py`, the two test files) does not overlap WP02's write scope. `tests/kernel/service_release_fixture.py` is *imported* by WP02's test surface but modified only here, additively; the dependent lane's tests still pass (38 passed above). No coordination note required. |
| 8 | Production fragility | **PASS** | Every new `raise` is fail-loud by design and documented: `UnreadableBinary(ValueError)` is the FR-005 refusal surface (docstring: "the message says why and names the shape found"), and WP02 converts it into the `SERVICE_PLATFORM_FLOOR_UNREADABLE` refusal code; `floor_kind`/`parse_floor` `ValueError`s validate build inputs. All are build-time tooling paths with no transient-race exposure, and `UnreadableBinary` subclasses `ValueError` so the caller can catch it narrowly. |

## Findings (all non-blocking)

**Finding 1 — narrow silent-`None` window on an inconsistent dynamic section (hardening).**
`scripts/service_platform.py:162-163`: a dynamic ELF that carries `DT_VERNEED` but is missing
`DT_STRTAB`, or carries `DT_VERNEED` + `DT_STRTAB` with `DT_VERNEEDNUM` absent, returns `None`
("no versioned symbols") rather than raising `UnreadableBinary`. Per WP prompt T002 step 7 an
inconsistent structure should fail closed. In practice no toolchain emits that combination
(glibc-linked binaries emit all four tags together; musl/static binaries have no `DT_VERNEED`),
the adjacent combination (all present but `DT_STRSZ` missing) *does* fail loud via
`_cstring`'s bounds check, and the mission's state machine runs the SHA-256 digest gate before
the reader, so realistic corruption never reaches this path. Suggested tightening for WP02 or a
follow-up: when any of `DT_VERNEED`/`DT_STRTAB`/`DT_VERNEEDNUM` is present, require all of them,
else `UnreadableBinary("inconsistent dynamic section…")`.

**Finding 2 — terminal Mach-O `cmdsize` overrun is not validated (hardening).**
`scripts/service_platform.py:283-293`: the load-command walk rejects `cmdsize < 8` and every
field read is bounds-checked by `_uint`, so no infinite loop and no out-of-file read is possible
(verified: the `cmdsize 0` corruption test raises "shorter than its own header"). However, the
*last* command's `cmdsize` is never checked against `len(data)`: a final command claiming to
span past EOF is accepted. The WP prompt's stated purpose for the check ("so a corrupt header
cannot loop forever") is met, and every floor value is still read from bounds-checked offsets,
so no wrong floor can be produced. Suggested one-line tightening: after reading `size`, also
require `offset + size <= len(data)`.

**Finding 3 — slightly misleading `floor_kind` message for arbitrary unknowns (cosmetic).**
`scripts/service_platform.py:100`: the `ValueError` appends "; jvm is not native" regardless of
what the unknown target was, so `floor_kind("freebsd-riscv64")` reads oddly. Harmless — the
valid-target list is included — and the test asserts the current wording. Re-word if touched
again; not worth a cycle on its own.

## Positive notes

- Bounds checking is uniformly centralized in `_uint` (negative offset, non-positive size,
  overrun) — every header, dynamic-entry, verneed, vernaux and load-command read goes through it.
- The verneed walk guards both `vna_next == 0` and `vn_next == 0` and every advance is a strictly
  positive unsigned stride, so no spin is possible even on crafted tables.
- `max(highest or (0, 0), …)` plus tuple comparison makes the glibc maximum numeric per
  component; `exceeds("2_39", "2_9")` is `True`, and the `GLIBC_2.2.5` → `2_2` normalization
  matches the data-model invariant (no patch component).
- `required_floor` iterates `sorted(binaries)` and only replaces on strict `>`, so ties report the
  first asset in sorted order exactly as the data model demands.
- The module imports only the standard library, is loadable by path and from the repo root, and
  `__all__` names the full public surface per C-007.
