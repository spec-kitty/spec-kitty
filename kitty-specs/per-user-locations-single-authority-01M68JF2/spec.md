# Mission Specification: One authority for per-user cache and state locations

**Mission Branch**: `kitty/mission-per-user-locations-single-authority-01M68JF2`
**Created**: 2026-10-31
**Status**: Ready for planning
**Input**: GitHub issue #6488 — "Per-user cache and state locations differ between callers on macOS and Windows", under the operator triage decision of 2026-10-19: **`platformdirs` semantics win for cache and state; `kernel.user_dirs` adopts that rule and every caller resolves through it.**

## Context

Six production callers resolve a per-user cache, state or config directory, and today
they do not agree. `specify_cli.core.upgrade_notifier`,
`charter.offering.packs.pack_fetch.default_cache_root` and
`kernel.service_artifacts.default_cache_root` use the kernel helpers, which follow an
XDG-only rule on every platform (so `~/.cache/spec-kitty` on macOS);
`specify_cli.compat.cache._resolve_cache_dir` and
`specify_cli.compat.config._resolve_config_dir` call `platformdirs` directly (so
`~/Library/Caches/spec-kitty` on macOS); `runtime.next._runtime_pkg_notice._marker_path`
uses the kernel state helper, whose fallback is the literal `~/.cache` rather than the
XDG `~/.local/state`. On macOS a user therefore ends up with two cache trees that never
see each other's writes: the upgrade nag, the pack cache and the service cache in one,
the upgrade-check cache in the other. Two fallbacks in `compat/cache.py` and
`compat/config.py` can never run (`platformdirs` is a hard dependency), and one docstring
claims a rule the code does not follow.

The operator named the authority: `platformdirs` semantics, everywhere, with
`kernel.user_dirs` as the single implementation. This Mission delivers that, moves the
files that must move, discards what the old rules left behind, and pins the platform
branches with tests that fail when any caller diverges again.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A macOS user has one cache, not two (Priority: P1)

A macOS user runs `spec-kitty` commands that nag about an upgrade, fetch pinned packs
and services, and notify about the retired runtime package. Every one of those writes
lands under `~/Library/Caches/spec-kitty` (and the one-time marker under
`~/Library/Application Support/spec-kitty`), the same directories `platformdirs`
prescribes for a macOS app, instead of splitting between `~/.cache/spec-kitty` and
`~/Library/Caches/spec-kitty`.

**Why this priority**: it is the defect the issue reports, and it is the only story that
changes where a user's files live.

**Independent Test**: on a faked macOS (`sys.platform = "darwin"`, Windows seam off),
resolve every caller and assert each path lies under the one authority's macOS
directory; on Linux assert the cache and config paths are byte-identical to today.

**Acceptance Scenarios**:

1. **Given** a macOS home with no XDG variables set, **When** each of the six callers
   resolves its directory, **Then** every cache caller resolves under
   `~/Library/Caches/spec-kitty`, and the state and config callers resolve under
   `~/Library/Application Support/spec-kitty`.
2. **Given** `XDG_CACHE_HOME` set on macOS, **When** any caller resolves, **Then** it
   resolves under `$XDG_CACHE_HOME/spec-kitty`, because `platformdirs` gives an XDG
   variable precedence on macOS too.
3. **Given** Linux, **When** each caller resolves, **Then** the cache path is still
   `${XDG_CACHE_HOME:-~/.cache}/spec-kitty`, the config path is still
   `${XDG_CONFIG_HOME:-~/.config}/spec-kitty`, and only the state path is new
   (`${XDG_STATE_HOME:-~/.local/state}/spec-kitty`).

---

### User Story 2 - A divergent caller cannot come back unnoticed (Priority: P1)

A maintainer reviewing a future change to one caller is told by the test suite that the
caller left the single authority, instead of finding out from a user whose cache split
again.

**Why this priority**: the issue was possible because each caller had its own tests
pinning its own rule; nothing compared them. Without this story the fix regresses.

**Independent Test**: enumerate every production caller in one test, resolve all of them
under one faked platform, and assert every path is under the authority; re-introduce a
hand-rolled rule in any caller and watch the test go red.

**Acceptance Scenarios**:

1. **Given** the resolved directory of every caller on a faked platform, **When** the
   convergence test compares them to the authority's directory, **Then** it passes.
2. **Given** one caller reverted to `Path.home() / ".cache" / "spec-kitty"` (the
   pre-fix `pack_fetch` rule), **When** the same test runs, **Then** it fails and names
   that caller.
3. **Given** a new caller that resolves a per-user directory by hand, **When** the suite
   runs, **Then** the inventory test fails until the caller is added to the convergence
   test (or routed through the authority).

---

### User Story 3 - The old locations are gone (Priority: P2)

A user on macOS (or Windows) upgrades and, on the first command that resolves a per-user
directory, the cache and marker directories the old rules wrote are removed. Nothing is
migrated, because they hold only disposable caches and one one-time marker.

**Why this priority**: without it the duplicate tree stays on disk forever and the next
reader of `~/.cache/spec-kitty` on macOS reads stale state.

**Independent Test**: plant a legacy root with a file in it under a faked platform,
resolve a directory through the CLI startup path, assert the root is gone; plant a root
that is still the current location for some kind and assert it survives untouched.

**Acceptance Scenarios**:

1. **Given** a faked macOS home holding `~/.cache/spec-kitty/upgrade-check.json`,
   **When** the CLI's startup housekeeping runs, **Then** `~/.cache/spec-kitty` is
   removed and the resolved cache directory is untouched.
2. **Given** a Linux home holding `~/.cache/spec-kitty/open-packs/`, **When** the CLI
   starts, **Then** nothing is removed, because that directory is still the live cache
   root on Linux.
3. **Given** a legacy root that is a symlink pointing outside the home folder, or that
   contains a git checkout, **When** housekeeping runs, **Then** it is left in place and
   the command still succeeds.

---

### Edge Cases

- **Linux state vs Linux cache**: the pre-fix state rule (`~/.cache`) is the post-fix
  *cache* rule on Linux. Cleanup must never remove a path that is current for any kind,
  or it deletes the live pack and service caches.
- **An empty or unset variable**: `platformdirs` treats an empty XDG variable as unset;
  the authority must too.
- **A relative XDG value**: used as given, as `platformdirs` does.
- **`platformdirs` cannot be imported**: it is a hard dependency, so no caller keeps a
  fallback; the import failure is an install defect, not a runtime branch.
- **An unwritable home**: resolution must still work (it reads environment variables
  only), and cleanup must degrade to silence rather than fail the command.
- **A marker file that cannot be deleted**: the notice is shown once more; the command
  exits with the code it would have had.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One resolution authority | As a user, I want every per-user cache, state and config directory resolved by one rule so that my files do not split between two trees. | High | Open | [build] | no — today four callers resolve a different path than the other two on macOS |
| FR-002 | `platformdirs` semantics, `appauthor=False` | As a user, I want the locations my OS prescribes (`~/Library/Caches`, `~/Library/Application Support`, `%LOCALAPPDATA%`, XDG) so that the CLI behaves like other apps and packagers can find my files. | High | Open | [build] | no — the kernel helpers use an XDG-only rule on every platform |
| FR-003 | Every caller routed | As a maintainer, I want `upgrade_notifier`, `pack_fetch.default_cache_root`, `service_artifacts.default_cache_root`, `compat/cache._resolve_cache_dir`, `compat/config._resolve_config_dir` and `_runtime_pkg_notice._marker_path` to call the authority so that no caller owns a copy of the rule. | High | Open | [build] | no — five of them carry their own rule today |
| FR-004 | Explicit platform selection | As a maintainer on Linux, I want the authority to pick the `Windows`/`MacOS`/`Unix` `platformdirs` class from the platform seams so that the macOS and Windows branches are testable without those hosts. | High | Open | [build] | no — `platformdirs` picks its class at import time, so no test can reach macOS from Linux |
| FR-005 | macOS and Windows branch pins | As a maintainer, I want a test that pins each platform branch exactly (path, XDG precedence, empty-variable fallback) so that a platform regression fails on a Linux host. | High | Open | [ratchet] | yes — paired on the same fixture with FR-006's divergence probe, which fails when a caller leaves the authority |
| FR-006 | Divergence guard | As a maintainer, I want one test that resolves every caller and asserts each result lies under the authority so that a caller that reinvents the rule fails the suite. | High | Open | [ratchet] | no — a no-op fix leaves the two rules disagreeing and the test red |
| FR-007 | Dead fallbacks removed | As a maintainer, I want the unreachable `ImportError` fallbacks in `compat/cache.py` and `compat/config.py` deleted so that there is exactly one implementation of the rule. | Medium | Open | [build] | no — the fallbacks exist today and encode a third rule |
| FR-008 | Zombie divergence removed | As a maintainer, I want `user_cache_dir(windows_local_appdata=False)` gone with its two callers so that no caller can opt out of the platform rule. | Medium | Open | [build] | no |
| FR-009 | Legacy locations discarded | As a user, I want the pre-convergence cache and marker directories removed once so that I do not keep a dead duplicate tree. | Medium | Open | [build] | no — nothing removes them today |
| FR-010 | Cleanup is bounded and safe | As a user, I want cleanup to touch only the enumerated legacy roots, never a path that is current for any kind, never a symlink that escapes the home folder, and never a git checkout, so that no real data is at risk. | High | Open | [build] | no |
| FR-011 | Truthful docs | As a reader, I want the `_runtime_pkg_notice` docstring and the user docs to state the rule the code follows, so that the next contributor does not re-derive it. | Medium | Open | [build] | no — the docstring names `platformdirs` while the code does not use it |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Layer purity | `kernel.user_dirs` and the cleanup module import only the standard library, `kernel.*` and `platformdirs`; the existing architectural import tests stay green with unchanged allowlists. | Maintainability | High | Open |
| NFR-002 | Resolution stays pure | Resolving any of the three directories creates no directory, writes no file and opens no socket; asserted by a test that resolves into a non-existent temporary base and asserts nothing was created. | Reliability | High | Open |
| NFR-003 | Cleanup cannot fail a command | Cleanup adds at most one `stat` per legacy candidate, runs at most once per process, and never raises: every failure is logged at debug level and the command's exit code is unchanged. | Reliability | High | Open |
| NFR-004 | Startup budget | The CLI startup performance tests (existing) stay green; the added housekeeping must not add an import of `charter` or `specify_cli` to the kernel path nor more than 10 ms to a cold `--help`. | Performance | Medium | Open |
| NFR-005 | Fast tests | The new and rewritten location tests carry `pytest.mark.unit` and `pytest.mark.fast` and complete in under 5 s together. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Operator ruling | Platformdirs semantics win for cache and state; no divergence is preserved for byte-compatibility (operator triage, 2026-10-19). | Business | High | Open |
| C-002 | Scope boundary | XDG for `~/.kittify` and `~/.spec-kitty` is issue #2904 and is out of scope; the project-local layout does not change. | Technical | High | Open |
| C-003 | Kernel import rule | `kernel/` imports no `charter` or `specify_cli` module; `platformdirs` remains the only sanctioned third-party import in the kernel layer. | Technical | High | Open |
| C-004 | No data migration | The removed locations hold disposable caches and one one-time marker; nothing is copied to the new location. | Technical | Medium | Open |
| C-005 | Windows unverified on host | No Windows or macOS host is available: those branches are pinned by faked platform seams and `platformdirs`' own documented layout, and the PR says so. | Technical | Medium | Open |

### Key Entities

- **Per-user directory kind**: cache, state or config — the three questions the authority
  answers.
- **Caller**: a production function that needs one of those directories; each must reach
  the authority and append only its own subpath.
- **Legacy location**: a path a pre-fix rule wrote to; disposable, and discarded only
  when it is no longer current for any kind.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a faked macOS with no XDG variables, 6 of 6 callers resolve under the one authority's macOS directories (0 divergent). — [build] · no-op passable: no
- **SC-002**: On Linux, the cache and config paths of all 6 callers are byte-identical to the pre-change outputs; only the state path changes (`~/.cache/spec-kitty` → `~/.local/state/spec-kitty`). — [build] · no-op passable: no
- **SC-003**: Reverting any single caller to a hand-rolled rule makes the divergence test fail: 6 of 6 reverts detected. — [ratchet] · no-op passable: no
- **SC-004**: A planted legacy root is removed, and a planted root that is current for some kind survives, in the same test run on one fixture. — [build] · no-op passable: no
- **SC-005**: `docs/changelog/CHANGELOG.md` carries one `[Unreleased]` entry citing `(#6488)`, and the docs that name a cache path state the platform rule. — [build] · no-op passable: no
