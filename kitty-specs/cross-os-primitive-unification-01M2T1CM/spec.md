# Mission Specification: Cross-OS Primitive Unification

**Mission Branch**: `feat/cross-os-primitive-unification`
**Created**: 2026-09-18
**Status**: Draft
**Input**: GitHub issue #4714 (sub-issue of epic #3864, Windows/cross-platform portability); root-cause follow-up to the #4703 Windows P0 (PR #4709).

## Context

spec-kitty 4.0.0rc3 was **unusable on Windows**: every command aborted with
`RuntimeError: [Errno 13] Permission denied` (#4703). The runtime held an
exclusive `msvcrt.locking()` lock on its own `.update.lock`, then the
asset-verification pass read that same held file. On Windows `msvcrt` locks are
*mandatory* (the OS refuses even the locking process's own read), so the read
raised `PermissionError`; on POSIX the equivalent `flock` is advisory, which is
why it was never caught. PR #4709 point-fixed it — **but** the landing squad
(paula-patterns, architect-alphonso, reviewer-renata) confirmed the root cause
is structural: the cross-OS **lock**, **safe-delete**, and **OS-detection**
primitives are forked across the runtime with **no canonical owner**, and the
point fix actually *increased* one fork count. That fork is why this class of
`PermissionError` bug recurs. This mission closes the class **by construction**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A Windows contributor never hits a self-inflicted lock crash again (Priority: P1)

A contributor runs any spec-kitty command on Windows against an existing
spec-kitty home. The runtime must acquire, hold, and release its coordination
locks without ever reading a path while holding a mandatory lock over it — the
exact #4703 footgun — regardless of which subsystem is locking.

**Why this priority**: This is the recurrence the mission exists to prevent.
#4703 was total (every command) and shipped to users. Preventing its *class*,
not just its instance, is the core deliverable.

**Independent Test**: With a single canonical lock primitive in place, a test
that simulates Windows mandatory-lock semantics on POSIX (acquire the sidecar
lock, then exercise every migrated call site) shows no site reads a payload
while holding a lock over it. The DIRECTIVE_043 gate proves no *other* raw
locking primitive exists to reintroduce the footgun.

**Acceptance Scenarios**:

1. **Given** the runtime holds its coordination lock, **When** any subsystem
   performs its locked operation, **Then** no code path reads the protected
   payload bytes while the lock is held (the lock primitive yields only holder
   metadata, never a handle to the protected resource).
2. **Given** a developer adds a new file that calls `msvcrt.locking`,
   `fcntl.flock`/`lockf`, or constructs a `filelock.FileLock` outside the
   canonical module, **When** the architectural gate runs, **Then** it fails
   with a message naming the offending file and pointing at the canonical
   primitive.
3. **Given** the canonical lock module is deleted or emptied, **When** the gate
   runs, **Then** it fails (non-vacuous floor) rather than trivially passing.

### User Story 2 - A maintainer deletes managed assets safely on every OS (Priority: P1)

A maintainer (or the upgrade/install machinery) removes managed, read-only
assets (`0o444`) during install, upgrade, or skill retirement. On Windows,
`DeleteFile`/`RemoveDirectory` refuse a read-only target; the delete must clear
the write bit first — using one shared helper with one, correct symlink
contract — never following a symlink out of the managed tree.

**Why this priority**: The read-only-managed-asset delete is the sibling
cross-OS footgun to the lock bug; it is already forked into three copies with a
silent contract split (`lstat`+masked vs `stat`+follow-unmasked). A wrong choice
either re-forks or relocates the `PermissionError` onto a symlink target.

**Independent Test**: A test that creates a read-only managed file, a read-only
managed directory, and a managed *symlink*, then deletes each through the single
canonical helper, proves the write bit is cleared on the entry itself (not the
symlink target) and the delete succeeds on both OS semantics.

**Acceptance Scenarios**:

1. **Given** a read-only (`0o444`) managed file, **When** it is deleted through
   the canonical helper, **Then** the delete succeeds on Windows-mandatory and
   POSIX-advisory semantics alike.
2. **Given** a managed entry that is a symlink, **When** it is deleted, **Then**
   the write bit is cleared on the link (no-follow), never on the link target.
3. **Given** any of the previously-forked call sites, **When** the code is
   built, **Then** only the one canonical helper exists (the 3 live copies are
   removed; the frozen migration copy is left untouched by design).

### User Story 3 - A developer has one OS-detection seam (Priority: P2)

A developer needs to branch on "is this Windows?". There must be one public,
testable seam, so the answer cannot drift and can be overridden in tests
*without* faking `os.name` (which flips `pathlib` to `WindowsPath` and crashes
the test process).

**Why this priority**: OS detection is duplicated four ways and scattered across
a wide `os.name == "nt"` / `sys.platform == "win32"` zoo. Consolidating removes
a whole category of "which check did this site use?" drift. Lower priority than
P1 because it is mechanical and not itself a live crash.

**Independent Test**: A test patches the promoted kernel seam's module attribute
and observes every routed consumer follow the override, with no test needing to
set `os.name`.

**Acceptance Scenarios**:

1. **Given** the promoted kernel seam, **When** a consumer checks for Windows,
   **Then** it calls the seam (reached via a patchable module attribute), not an
   inline `os.name`/`sys.platform` literal.
2. **Given** a test overrides the seam, **When** a routed consumer runs, **Then**
   it honours the override without the test faking `os.name`.
3. **Given** a Windows-only C-module import guard (`import msvcrt`/`import fcntl`),
   **When** the seam is applied, **Then** the module-scope import guard may
   legitimately remain a raw platform check (documented exception).

### Edge Cases

- **The canonical lock's own record read.** The canonical primitive reads its
  own *sidecar holder record* while holding the lock — this is legitimate (the
  record is written by the holder and its content is intentional), and is *not*
  the #4703 footgun (which was reading an unrelated payload whose bytes were
  never used). The gate predicate and the invariant must be phrased so the
  canonical home is not self-flagged.
- **Async vs sync callers.** The current canonical async lock cannot serve sync
  hot paths (e.g. bootstrap runs before an event loop); `review/pre_review_gate`
  already hand-rolls a sync `fcntl` for exactly this reason. The unified
  primitive must expose *both* a sync and an async surface over one mechanism.
- **Re-entrancy and test doubles.** `status/locking` keeps thread-local
  re-entrant counts; `review/verdict_commit_queue` references the concrete
  `FileLock` type for a test double. The unified primitive must preserve
  re-entrancy and give those sites a supported seam so migration does not
  silently regress behaviour.
- **Cross-process + blocking-timeout parity.** The `filelock`-family sites rely
  on lock-directory + blocking-acquire-with-timeout semantics; the stdlib
  primitive must replicate them exactly, proven with a POSIX simulation of
  Windows mandatory-lock semantics (do not trust Windows CI alone).
- **Frozen migration copy.** `m_3_2_0rc45_retire_standalone_skill_surface.py`
  contains a fourth inline safe-delete copy; migrations are immutable one-offs —
  it must be excluded from the gate and never rewritten to import the canonical
  util.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | One canonical safe-delete util | As a maintainer, I want a single managed-asset delete helper (clear-read-only-then-unlink/rmdir/rmtree) so the three forked copies collapse to one correct contract. | High | Open |
| FR-002 | Correct symlink contract for safe-delete | As a maintainer, I want the canonical delete to use no-follow (`lstat`) + masked (`S_IMODE`) semantics so a managed-asset delete never clears the write bit on a symlink target outside the managed tree. | High | Open |
| FR-003 | Remove the 3 live safe-delete copies | As a maintainer, I want `skills/installer.py`, `runtime/agent_skills.py`, and `runtime/asset_preparation.py` routed onto the canonical util with their private copies deleted, leaving the frozen migration copy untouched. | High | Open |
| FR-004 | Promote one OS-detection kernel seam | As a developer, I want `kernel/paths.py::_is_windows` promoted to a public, patchable seam so Windows detection has one canonical source. | High | Open |
| FR-005 | Route the OS-detection zoo through the seam | As a developer, I want the 3 `_is_windows` definitions (`kernel/paths.py`, `runtime/home.py`, `runtime/asset_preparation.py`) plus the 1 inline check in `core/file_lock.py` and every other routable `os.name`/`sys.platform` Windows-detection site calling the kernel seam, with only Windows-only C-module import guards left as documented raw exceptions (enforced by FR-012). | Medium | Open |
| FR-006 | One canonical lock primitive | As a developer, I want a single sync+async, sidecar-model, filelock-free (stdlib) lock primitive owned by exactly one module so every subsystem locks through one owner. (Module home — kernel C1 vs `specify_cli.core` C2 — is the design decision recorded in A-04, ratified/validated at `/plan`; the binding spec-level requirements are the home-independent properties in this row, FR-007, and NFR-001/002.) | High | Open |
| FR-007 | Structural read-safety of the lock primitive | As a Windows contributor, I want the lock primitive to derive its own sidecar lock path and yield only holder metadata (never a handle to the protected resource) so a held lock can never be read as a payload. | High | Open |
| FR-008 | Migrate the stdlib-family lock sites | As a developer, I want the raw `msvcrt`/`fcntl` lock sites migrated onto the canonical primitive: **`runtime/asset_preparation.py`** (the `_HELD_LOCKS` cold-install serialization — the #4703-origin site whose fork count the point fix *increased*), `runtime/bootstrap.py`, `tracker/credentials.py`, `paths/windows_migrate.py`, and `review/pre_review_gate.py` (whose sync-only requirement the unified primitive's sync surface must satisfy). | High | Open |
| FR-009 | Migrate the filelock-family sites and retire `filelock` | As a developer, I want `core/checkout_file_lock.py`, `status/locking.py`, `review/verdict_commit_queue.py`, `auth/secure_storage/file_fallback.py`, and the `zeitgeist_client` lock sites (`credentials.py`, `outbox_approval.py`) migrated onto the canonical primitive and the `filelock` dependency removed — preserving re-entrancy, blocking-timeout, and test-double contracts. | High | Open |
| FR-010 | DIRECTIVE_043-governed lock gate | As a maintainer, I want a non-vacuous architectural gate that bans raw `msvcrt`/`fcntl`/`filelock` locking outside the canonical module (import ban + call ban), with a concrete floor, a self-mutation check, and a shrink-only allowlist seeded fail-closed with all current sites (incl. `asset_preparation.py`), and excluding the `upgrade/migrations/` tree. | High | Open |
| FR-011 | Fold campsite-matched hardening in asset_preparation | As a maintainer, I want the anchor-path normalization before sha256 keying and the defensive `_children_tolerated` node-state read guard fixed while `asset_preparation.py` is already being rewritten. | Medium | Open |
| FR-012 | DIRECTIVE_043-governed OS-detection gate | As a maintainer, I want a non-vacuous architectural gate that bans inline `os.name == "nt"` / `sys.platform == "win32"` Windows-detection outside the promoted kernel seam (call/comparison ban), with a concrete floor and an explicit sanctioned-raw allowlist limited to the documented Windows-only C-module import guards — so "route through the seam" is enforced by construction, not reviewer diligence. | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new third-party dependency | The canonical lock primitive introduces zero new third-party runtime dependencies (stdlib `msvcrt`/`fcntl`/`os`/`asyncio` + the already-sanctioned `kernel.clock`); `filelock` is removed from runtime dependencies (`pyproject.toml`), not merely unused (subject to the FR-009 deferral seam per A-01). | Architectural | High | Open |
| NFR-002 | Layer-chain integrity | The enforced import chain `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli` holds after the consolidation; `tests/architectural/` layer rules and `test_pyproject_shape.py` pass with the canonical lock module accepted at its chosen home (A-04). | Architectural | High | Open |
| NFR-003 | Gate non-vacuity | The lock gate fails when the canonical module is deleted/emptied and flags a synthetic injected violation (self-mutation test), so it cannot silently pass. | Reliability | High | Open |
| NFR-004 | Cross-OS parity proof | Lock and safe-delete behaviour is proven on Windows-mandatory semantics via a POSIX simulation (not Windows CI alone), including cross-process contention and blocking-with-timeout. | Reliability | High | Open |
| NFR-005 | Behaviour preservation | Migration is behaviour-preserving for every site: re-entrant counts, blocking-timeout, force-release/truncate-not-unlink, and the verdict-queue test double keep working; no lifecycle behaviour changes beyond the read-safety fix. | Correctness | High | Open |
| NFR-006 | Coverage on new/changed branches | Every new helper/branch introduced by the consolidation carries focused tests in the same change (diff-cover ≥90%), and each function stays at cyclomatic complexity ≤15. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Canonical lock primitive is filelock-free stdlib | The canonical primitive must be a filelock-free stdlib design (the enforcement mechanism for "one primitive"). `kernel` is zero-third-party-dep, so a kernel (C1) home *cannot* import `filelock` — which is precisely why the C1 home forces the correct design; a C2 home must still choose the filelock-free design deliberately. | Technical | High | Open |
| C-002 | Frozen migration is immutable | `upgrade/migrations/m_3_2_0rc45_retire_standalone_skill_surface.py`'s inline safe-delete copy must not be rewritten; the gate must exclude the migrations tree. | Technical | High | Open |
| C-003 | Preserve OS-detection testability | The promoted seam must be overridable in tests via its module attribute; no test may fake `os.name` (it flips `pathlib` and crashes pytest). | Technical | High | Open |
| C-004 | Gate must not self-flag the canonical home | The lock gate's predicate must permit the canonical module's own sidecar-record read and its raw stdlib locking calls (the sanctioned holder), banning them only elsewhere. | Technical | High | Open |
| C-005 | No new DIRECTIVE number | "DIRECTIVE_043 gate" means a new gate governed by the *existing* DIRECTIVE_043 ("Close Defect Classes by Construction"); do not mint a new directive artifact. | Governance | Medium | Open |
| C-006 | `__init__.py` version-bump discipline | Any change to `src/specify_cli/__init__.py` requires a `pyproject.toml` version bump + `CHANGELOG.md` entry (do not prescribe the number; PO owns versioning). | Process | Medium | Open |

### Key Entities

- **Canonical lock primitive** (module home decided at `/plan` — leading
  candidate `kernel/locks.py`, see A-04): sync + async, sidecar-model file lock.
  Owns sidecar-path derivation; yields holder metadata only; seeded from
  `MachineFileLock`. The single sanctioned holder of raw `msvcrt`/`fcntl`.
- **Canonical safe-delete util** (`specify_cli/core/`): clear-read-only-then-remove
  helpers with the no-follow (`lstat`) + masked (`S_IMODE`) contract.
- **OS-detection seam** (`kernel/paths.py`, promoted public): the single
  patchable "is this Windows?" answer.
- **DIRECTIVE_043 lock gate** (`tests/architectural/`): import-ban + call-ban
  with a non-vacuous floor, self-mutation test, and a shrink-only allowlist.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The number of live safe-delete helper copies goes from 3 to 1 (the
  frozen migration copy excluded); every non-migration call site routes through it.
- **SC-002**: `_is_windows` definitions go from 3 (+1 inline check in
  `core/file_lock.py`) to 1 (the promoted kernel seam); routable
  `os.name`/`sys.platform` sites call it, enforced by the non-vacuous FR-012 gate
  whose only sanctioned-raw exceptions are the documented C-module import guards.
- **SC-003**: The count of distinct locking primitives goes from 3 families
  (raw msvcrt/fcntl, `filelock`, scoped fcntl) across ~12 sites toward **1**
  canonical primitive. On the full-scope path `filelock` is removed from runtime
  dependencies; if the FR-009 deferral seam is taken (A-01), `filelock` remains a
  runtime dependency covering exactly the deferred sites, tracked per SC-005 —
  and this success criterion is met only for the migrated (stdlib) families until
  the follow-up lands.
- **SC-004**: A test proving Windows-mandatory lock/delete semantics on POSIX
  passes, demonstrating no site reads a payload while holding a lock over it and
  read-only managed assets delete on both OS semantics.
- **SC-005**: The DIRECTIVE_043 lock gate is non-vacuous (fails when the
  canonical module is emptied and on an injected synthetic violation) and its
  allowlist is empty at mission terminus — or, if the filelock deferral seam is
  taken, covers exactly the deferred filelock sites, and a follow-up sub-issue
  for their burn-down **exists** (its URL recorded in the PR body and the
  design-decisions tracer) as the deferral's proof.
- **SC-006**: A test deletes a command-surface-shaped **symlink whose target
  lies outside the managed tree** through the canonical safe-delete helper and
  shows the no-follow (`lstat`) semantics succeed without clearing the write bit
  on — or otherwise touching — the link target (discharges A-02's proof
  obligation; proves the *negative* that no caller depended on follow-chmod).

## Assumptions

- **A-01**: The operator elected **full scope** (including `filelock` retirement)
  with the filelock wave as the *deferral seam* — if cross-process +
  blocking-timeout parity cannot be proven in-mission, ship the safe-delete +
  OS-seam + kernel lock primitive + stdlib-family migration + gate with the
  ratchet still covering the filelock sites, and burn them down in a fast
  follow-up (see SC-003/SC-005 conditioning). (Wave language, not WP numbers —
  the decomposition is `/tasks`'s job.)
- **A-02**: The command surface materializes some managed commands as symlinks;
  before switching safe-delete to no-follow semantics, the mission proves no
  delete path relies on follow-chmod (SC-006 discharges this obligation; else the
  fix must be adjusted).
- **A-03**: `MachineFileLock` (`core/file_lock.py`) is already sidecar-safe and
  pure stdlib + `kernel.clock`, so unifying is a move + sync-surface extension,
  not a rewrite. `/plan` confirms it has no upward (non-kernel) import before
  committing a kernel home. The `zeitgeist_client` lock sites (FR-009) are local
  *client* consumer code, not upstream-authored surface (CLAUDE.md client-repo
  inversion) — safe to migrate here.
- **A-04**: **Lock-primitive home decision.** The home is decided as **C1
  (`kernel/locks.py`)** on the grounding-squad architecture rationale (tracer
  DD-01: repo precedent `vcs_lock.py`/`atomic.py`/`clock.py`; lower layers
  already *sense* locks so a C2 home would fail-open to a future layer violation;
  kernel's zero-dep rule forces the filelock-free design). This is the design
  decision the issue reserved "for this mission." `/plan` **validates** it against
  the layer tests (`test_layer_rules.py`, `test_pyproject_shape.py`) and may
  revise to C2 (`specify_cli.core`) only if validation fails; the binding
  spec-level requirements (FR-006/007, NFR-001/002, C-001) are home-independent
  either way.

## Non-Goals (deferred, tracked in the PR body / a follow-up sub-issue)

- **NG-01**: The argv false-negative in `__init__.py`'s `_is_next_invocation` /
  `_is_live_work_hook_invocation` / `_is_session_start_invocation` detectors —
  latent today (only eager `--version/-v` is declared) and a separable surface
  requiring a version bump. Tracked, not fixed here.
- **NG-02**: Cold-install sentinel CWE-377 generalization — the sentinel is
  Windows-only and per-user (`%TEMP%`) as shipped; hardening it for a POSIX
  shared `/tmp` is YAGNI unless it is ever generalized. Sentinel *cleanup* is
  likewise a deliberate no-op: the issue concludes "leaving them is defensible"
  (zero-length; unlinking reintroduces a race), so this mission leaves the
  accumulate-in-temp behaviour unchanged.
