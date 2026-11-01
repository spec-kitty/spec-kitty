# Mission review — companion-wheel-platform-floor-01M6BV24 (#6948)

**Reviewer**: independent aggregate reviewer (whole integrated diff, `origin/main..HEAD` = `295a1d4106..461fa3f51c`, 4 commits)
**Reviewed**: `git diff origin/main..HEAD` (66 files, +3,297/−42; of which 9 non-artifact files, +1,067/−42), `spec.md`, `plan.md`, `data-model.md`, both WP review-cycle notes, and live runs of the reader, the build and the suites.

## Verdict: APPROVE WITH FINDINGS

All findings are non-blocking. The change closes the issue's failure mode at build and verify time for both Linux and macOS, holds constraints C-001…C-004, leaves no caller behind, and I could not make the reader crash, hang, or mis-measure despite targeted fuzzing and real-binary cross-checks.

---

## 1. Does it actually solve #6948?

**Yes, for both platforms, at build and at verify time.**

The issue's failure mode (spec Input line): pip installs a wheel on a host older than the binary needs because the tag's OS minimum was an unchecked constant; the digest check passes and the binary dies at exec (`SERVICE_UNHEALTHY`), with no fallback to the first-run fetch.

- **Build time (Linux)**: `scripts/build_services_wheel.py:207-215` — for each native target with pinned binaries, `_floor_violation` (`scripts/build_services_wheel.py:164-186`) measures the highest `GLIBC_x.y` version need of every binary the wheel would carry (`required_floor`, `scripts/service_platform.py:100-113`) and raises `SERVICE_PLATFORM_FLOOR_EXCEEDED` naming the asset, the measured floor, the declared floor and the remedy, or `SERVICE_PLATFORM_FLOOR_UNREADABLE` naming the asset and the reason. Proven end-to-end by `test_a_linux_asset_that_needs_more_than_the_declared_floor_refuses` (fixture at glibc 2.42 vs declared 2_39: exit 1, all message parts asserted, zero wheels written) and `test_a_macos_asset_that_needs_more_than_the_declared_floor_refuses` (minos 12.0 vs 11_0).
- **Build time (macOS)**: same path; `LC_BUILD_VERSION` `minos` with `LC_VERSION_MIN_MACOSX` fallback (`scripts/service_platform.py:263-306`). The macOS floor, previously only a constant in the writer (`wheel.py` `macosx_11_0_arm64` literal), is now a validated build input (`--macos-floor`, `DEFAULT_MACOS_FLOOR = "11_0"`) — the spec's "most likely to go stale" half is closed.
- **Verify time**: `--verify` re-measures the bundled bytes against the floor the wheel's **own file name** claims (`_tag_floor`, `scripts/build_services_wheel.py:173-176`, used at 295-301), so a wheel built outside the guard with a too-low tag cannot pass however verify is invoked. Proven by `test_verify_fails_a_wheel_whose_tag_understates_its_binaries` (a real wheel rebuilt by the real writer with `glibc_floor="2_28"` around 2_39 binaries fails verify).
- **No wheel can be refused after shipping into `--out`**: `build()` writes every wheel into a scratch sibling directory and moves them into `--out` only in the final `return` after the target loop and the size gate (`scripts/build_services_wheel.py:225-227`); every floor refusal raises inside the loop; `verify` writes nothing. The refusal tests assert the empty `--out` and the cleaned-up scratch.
- **Independent evidence beyond fixtures**: I ran the reader against real system binaries — `/bin/ls`, `/usr/bin/python3`, `/usr/bin/git`, `/usr/bin/dpkg` → `2_38`, agreeing with `readelf -V` (max `GLIBC_2.38`); `/usr/bin/ld.so` → `None` (it genuinely has no version-need table). The parse path is real, not fixture-shaped.

**Gaps named**: none blocking. Two recorded design boundaries, both spec-sanctioned: (a) a statically linked ELF states no floor, so the declared floor stands — correct, a static binary needs no glibc; (b) the guard runs only when pins exist; `pins/` is empty this cycle, so the first real `service-v*` pin exercises it (spec Assumptions). The tag remains the only thing pip checks at install time — runtime resolution is unchanged, as the spec's Boundary requires.

## 2. Spec-to-code fidelity (FR-001…FR-009, SC-001…SC-005)

Every FR is implemented in code and exercised by a test that drives the shipped entry points; I found no requirement implemented only in prose.

| ID | Where it lives | Test evidence |
|----|----------------|---------------|
| FR-001 | `_elf_floor`/`_highest_glibc` via `PT_DYNAMIC → DT_VERNEED` (`service_platform.py:139-262`) | `test_the_glibc_floor_is_the_highest_version_need`, several-needs, three-part-name normalization, stripped-image test; real-binary agreement above |
| FR-002 | `_macho_floor` `LC_BUILD_VERSION`/`LC_VERSION_MIN_MACOSX` | `test_the_macos_floor_is_the_build_version_minos`, deprecated-command fallback, other-platform ignored |
| FR-003 | `required_floor` max per wheel, first-sorted tie-break | `test_the_wheel_floor_is_the_maximum_over_its_binaries` (charter 2_42 named, write-service 2_39 not) |
| FR-004 | `_floor_violation` stable code + asset + both floors + remedy | both `…_refuses` tests assert code, asset, floors, remedy, zero wheels |
| FR-005 | `UnreadableBinary` → `SERVICE_PLATFORM_FLOOR_UNREADABLE` | `test_an_unreadable_asset_is_refused` (script-in-linux-slot, ELF-in-macos-slot) + 10 parametrized malformed-header shapes in `test_service_platform.py` |
| FR-006 | `floor_kind("windows-x64") is None`; `read_floor` returns before parsing | `test_windows_assets_are_not_measured` (arbitrary bytes build the `win_amd64` wheel), `test_windows_states_no_floor_and_is_never_measured` |
| FR-007 | `--macos-floor` CLI input, `DEFAULT_MACOS_FLOOR`, `platform_tag(..., macos_floor=)` | `test_the_macos_floor_is_a_build_input` (12_0 pins → `macosx_12_0_arm64` wheel), `test_the_macos_floor_is_a_parameter_not_a_constant` |
| FR-008 | verify re-measures bundled bytes against the name's tag | `test_verify_fails_a_wheel_whose_tag_understates_its_binaries` |
| FR-009 | `_declared_floors` validates both floors up front via `platform_tag("linux-x64", glibc, macos)` (`build_services_wheel.py:137-148`) | `test_a_bad_macos_floor_fails_even_without_a_macos_target`, `test_a_bad_glibc_floor_fails_even_without_a_linux_target`, `test_both_floors_are_validated_whether_or_not_the_target_uses_them` |

SC-001…SC-004 map one-to-one onto the tests above (refusals with zero wheels; at-or-below-floor positive controls building all 5 wheels; verify understatement; unreadable-vs-Windows). SC-002 I verified **empirically beyond the a→b reproducibility test**: I loaded `origin/main`'s `wheel.py` side by side with the new one and built the linux-x64, macos-arm64 and fallback wheels from identical inputs — names and **bytes are equal in all three cases** (e.g. 9,855 == 9,855 bytes). SC-005: `--help` lists `--macos-floor` (`_parser`), the `release.yml` comment states the check, the changelog entry is accurate, and the negative control (malformed macOS floor refuses) exists.

NFRs: NFR-001 stdlib-only confirmed by import list (`re`, `collections.abc`, `dataclasses`) and an empty diff to `pyproject.toml`/`uv.lock`; NFR-002 no new fetch (the reader sees bytes the build already digest-verified); NFR-003 measured — 0.11 ms (ELF) and 0.01 ms (Mach-O) header reads on synthetic 100 MB binaries; NFR-004 proven by the byte-identity check above. C-001/C-002 hold (tag = declared floor, defaults unchanged, no wheel/sdist member added or removed, reader ships in `scripts/` only); C-003 holds (exit 1, stderr, stable codes, no-wheel-on-failure); C-004 holds (bytes-only reads, no subprocess, no host-version consultation).

## 3. Regressions and blast radius

`git grep` for every changed symbol:

- `build_companion_wheel` — callers: `scripts/build_services_wheel.py` (build loop, verify rebuild) and `packages/spec-kitty-services/_backend/spec_kitty_services_backend.py:55`. The backend builds **only the fallback wheel** (`target=None, binaries={}`), which states no floor; the new `macos_floor` parameter defaults to `11_0` and the fallback tag is untouched. No caller left behind.
- `platform_tag` — signature extended with a defaulted parameter; the only other callers are tests and `_declared_floors`. Backward compatible; `test_platform_tags` (pre-existing, glibc-only parametrization) passes unchanged.
- `_declared_floors`, `_floor_violation`, `_tag_floor` — new helpers, all reachable from `build`/`verify`/`main` (no dead code; WP01's interim no-caller state is discharged).
- `verify`/`build` — the only external caller is `.github/workflows/release.yml`, updated at both the build step (line 382) and the verify step (line 385) to pass `--macos-floor 11_0` beside `--glibc-floor 2_39`. `scripts/release/` has no wheel-tag or floor surface (grepped).
- The macOS tag literal `macosx_11_0_arm64` appears nowhere else as a second tag table; `wheel.py`'s `_PLATFORMS` remains the single authority (`git grep macosx` outside tests/changelog finds only `wheel.py`, the ADR and research docs).
- **`tests/ci/test_mission_status_gate_checks.py`'s `_floor` is a false positive.** That helper (line 56) wraps `mission_status_gate_checks.py native-tag-floor --junit-dir … --floor N`, a CI gate counting executed JUnit `<testcase>` entries so a native test leg that selected no test cannot read as green — a *test-count* floor for the `native-tag-floor` command, unrelated to OS platform floors. No drift; no change needed.

Suites: the packaging suite (which contains all touched tests) and the release suite are green (counts below), including the pre-existing tests around the build backend, sdist and package bundling.

## 4. Correctness of the parsing

- **Bounds checks**: every read goes through `_uint` (`service_platform.py:141-144`), which refuses any read running past the file; `_cstring` bounds the string table by `DT_STRSZ` and requires NUL termination inside it; `_file_offset` refuses a `DT_STRTAB`/`DT_VERNEED` address outside any `PT_LOAD`. I fuzzed 800 mutated-real-ELF and random blobs plus hostile Mach-O shapes (huge `ncmds`, `cmdsize` 0 and 8, huge packed `minos`) across both targets — 1,618 evaluations, **zero unexpected exceptions, zero hangs**; every failure is a clean `UnreadableBinary` with a reason.
- **Loops**: all walks are `for` loops over bounded counts (`phnum`, `size // 16`, `vn_cnt`, `count`, `ncmds`), with `vna_next`/`vn_next` zero-guards — a cyclic or zero step cannot spin (`test_a_corrupt_mach_o_load_command_cannot_loop_or_overrun`).
- **Endianness**: ELF requires `ELFDATA2LSB` and refuses big-endian with a reason; Mach-O reads little-endian only (the arm64 images the target ships); both fat-Mach-O byte orders of `0xCAFEBABE` are refused — which also means a Java class file in a macOS slot is refused as mislabelled, the right direction.
- **Numeric comparison**: `parse_floor` returns `(major, minor)` tuples compared with `>` — `2_39 > 2_9` and `11_0 > 9_0` hold numerically, never lexicographically (asserted directly and by `test_the_comparison_is_numeric_per_component`). Three-part names (`GLIBC_2.2.5`) and `minos` patch components normalize to major.minor, matching PEP 600/425 tag shapes.
- **Statically linked ELF**: no `PT_DYNAMIC` → `None`, declared floor stands — the spec's edge case, and empirically correct (`/usr/bin/ld.so`).
- **Fat Mach-O**: refused ("universal (fat) Mach-O; only a thin arm64 image can be measured") — the spec's refusal-not-guess rule.
- **Mislabelled asset**: a Mach-O in a Linux slot, an ELF in a macOS slot, a shell script anywhere floored — all refused with the shape named (`test_a_wheel_floor_cannot_be_read_from_a_mislabelled_asset`, `test_an_unreadable_asset_is_refused`).
- **Refusal ordering vs `--out`**: impossible to fire after the move — see §1.

Two narrow hardening notes (findings 1 and 2 below), both fail-closed or unreachable in practice.

## 5. The release contract

- **The tag stays the declared floor, never derived**: `_floor_violation` only ever refuses; the remedy message tells the maintainer to raise `--glibc-floor`/`--macos-floor` in `release.yml` "and the published tag with it"; `wheel.py`'s `platform_tag` docstring states the caller owns the floors. Decision `01M6BV2A16NMD5QA4VZ8B814HW` respected.
- **Can a maintainer silently change what hosts can install?** Raising a floor is a one-line, reviewed `release.yml` edit (FR-007's design), the tag change is visible in the wheel file names in the release artifacts, and the new workflow comment says to say so in the changelog. What a maintainer can **no longer** do is publish a wheel whose tag *understates* its binaries — that is the hole this Mission closes. There is no automated gate forcing a changelog entry on a floor raise (the comment is guidance, not enforcement); recorded as finding 5, non-blocking.
- **`release.yml` tells the truth**: both steps pass `--glibc-floor 2_39 --macos-floor 11_0` explicitly; the comment accurately describes the check, both refusal codes, and that raising a floor moves the published tag.
- **Changelog fragment** (`docs/changelog/unreleased/6948-platform-floor.fixed.md`, 867 characters < 1,200): bold impact-first lead with `(#6948)`, **Before:**/**After:**/**What to do:** structure; `check_changelog_style` reports **0 errors** and no warning for this fragment (its 50 length warnings are pre-existing entries). Content is accurate: the guard, both codes, `--macos-floor` as the new input, verify re-checking, and "the published tags and the wheel contents are unchanged" — all verified true above.

## 6. Anything a maintainer would reject the PR for

Nothing found. The diff is tight (two code commits cleanly split reader/guard, two artifact commits), the tag templates render the same strings as before (proven byte-identical), the frozen surfaces (`services/`, `contracts/`, `src/`, the backend, `pyproject.toml`, `uv.lock`) are untouched, and the messages a maintainer will actually see on refusal name the asset, both floors and the remedy. The only cosmetic items are below.

---

## Findings

| # | Location | Severity | Finding |
|---|----------|----------|---------|
| 1 | `scripts/service_platform.py:149-151` | non-blocking (hardening) | A `PT_DYNAMIC` program header with `p_filesz == 0` (or a dynamic segment with no `DT_VERNEED` entry) reads as "states no floor" (declared floor stands) rather than unreadable. No real toolchain emits an empty dynamic segment, a truncated download fails the digest check first, and the genuine static-binary case must read as no-floor — but a present-yet-empty `PT_DYNAMIC` could arguably be refused. Fail-open only in this contrived shape. |
| 2 | `scripts/service_platform.py:170` | non-blocking (cosmetic) | A version-need table missing `DT_STRSZ` makes every name lookup refuse with "outside the 0-byte string table" — fail-closed and correct, but the message names the symptom, not the missing `DT_STRSZ`. |
| 3 | `docs/adr/4.x/2026-10-29-1-…md:226` | non-blocking (docs) | The ADR still says "Neither floor is yet read from the binary itself (follow-up #6948)" — stale in present tense now that both are. The spec explicitly declared amending this ADR out of scope, so the omission is deliberate; a one-line follow-up would tidy it. |
| 4 | `docs/changelog/unreleased/6948-platform-floor.fixed.md` | non-blocking (convention) | Fragment name carries a `-platform-floor` suffix unlike its 19 bare `<issue>.<type>.md` siblings; the plan itself says the name follows the PR number once the PR exists. Style gate passes either way. |
| 5 | `.github/workflows/release.yml:374-380` | non-blocking (design note) | "Say so in the changelog" when raising a floor is comment guidance, not an enforced gate. The tag change remains visible in the reviewed workflow diff and the artifact names, so this is acceptable; noting it as the residual release-contract surface. |
| 6 | `tests/cross_cutting/packaging/test_companion_services_wheel.py:700` (verify-understatement test) | non-blocking (test clarity) | The assertion `"SERVICE_PLATFORM_FLOOR_EXCEEDED" in err or "needs glibc 2_39" in err` is weaker than it looks: at verify time the code is uniformly `COMPANION_VERIFY_FAILED` and only the message carries the floor detail (`_wheel_problems` uses `violation[1]`, `scripts/build_services_wheel.py:299`). That is consistent with C-003 (verify failures keep the existing code) and the data model ("reports … as problems on stderr"), but the `or` hides which branch actually holds. |
| 7 | `tests/ci/test_mission_status_gate_checks.py:56` | false positive | The drift warning about this `_floor` is a false positive: it is a JUnit test-count floor for the `native-tag-floor` CI gate, unrelated to platform floors. No action. |

## Commands run (with counts)

From `/home/exedev/work/sk-6948`, `uv run --frozen`:

| Command | Result |
|---------|--------|
| `uv run --frozen pytest tests/cross_cutting/packaging/ -q` | **218 passed, 1 skipped** (203 s) |
| `uv run --frozen pytest tests/release/ -q` | **277 passed, 6 skipped** (24 s) |
| `uv run --frozen python -m scripts.docs.check_changelog_style` | **0 errors, 50 warnings** (all pre-existing length warnings; none for the 6948 fragment) |
| `uvx ruff check scripts/ packages/spec-kitty-services/ tests/cross_cutting/packaging/ tests/kernel/service_release_fixture.py` | **All checks passed** |

Additional evidence gathered by this reviewer (read-only):

- Reader on ~44 real system binaries, cross-checked against `readelf -V` (`/bin/ls`, `/usr/bin/dpkg` → `2_38` = readelf's max `GLIBC_2.38`; `/usr/bin/ld.so` → `None`).
- 1,618 fuzz evaluations (400 mutated real ELFs + 400 random blobs, both targets, plus 4 hostile Mach-O shapes): 394 floors, 1,214 unreadable refusals, **0 unexpected exceptions, 0 hangs**.
- `exceeds`/`parse_floor` numeric-comparison assertions; mislabelled-asset refusals (PE in a Linux slot, ELF in a macOS slot, script in a macOS slot).
- NFR-003 timing on synthetic 100 MB binaries: ELF 0.11 ms, Mach-O 0.01 ms.
- SC-002 byte-identity: `origin/main`'s `wheel.py` vs the new one, same inputs — linux-x64, macos-arm64 and fallback wheels all name-equal and **byte-equal**.
- `git grep` over all callers of `build_companion_wheel`, `platform_tag`, `_declared_floors`, `verify`, `build`, `DEFAULT_*_FLOOR`, `service_platform`, `macosx_`/`manylinux_` literals (scripts, packages, src, tests, `.github`, docs).

## Not verified

- No real Mach-O or PE from an actual macOS/Windows toolchain was available on this Linux host; the Mach-O path rests on the synthetic fixtures (which build well-formed `LC_BUILD_VERSION`/`LC_VERSION_MIN_MACOSX` commands) and on the spec's assumption that the events builders keep producing thin arm64 images.
- The release workflow end-to-end (a real runner executing `release.yml` with populated pins) cannot run here; the guard is proven on fixtures, per the spec's stated assumption that `pins/` stays empty this cycle.
- The WP review notes reference lane-branch commits (`ea66bf9ef0`, `9d087aa3ff`) that were rebased into `ce8800ae3f`/`55c64dd985` on the mission branch; I reviewed the integrated tip, which is the PR a maintainer will read.
