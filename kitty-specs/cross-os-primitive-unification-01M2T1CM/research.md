# Research — Cross-OS Primitive Unification (Phase 0)

## R-01 — Lock-primitive home (A-04 resolution)

**Decision**: Home the canonical lock primitive at **`kernel/locks.py`** (C1),
seeded from `MachineFileLock` (`src/specify_cli/core/file_lock.py`).

**Rationale**:
- Repo precedent: `kernel/vcs_lock.py`, `kernel/atomic.py`, `kernel/clock.py` are
  all zero-third-party-dep cores homed in kernel *so lower layers adopt them
  without crossing the layer boundary*. The `atomic` docstring states the exact
  decision rule: home in kernel when a lower layer needs to adopt without
  crossing the boundary.
- Import-clean (validated): `MachineFileLock`'s only non-stdlib import is
  `kernel.clock` (`file_lock.py:35`). Moving it makes that intra-kernel; nothing
  drags `specify_cli` upward. `src/kernel/` imports no `specify_cli`.
- Lower layers already *sense* locks (`charter/offering/resolver.py` reads the
  `version.lock` sentinel; `src/runtime/next/runtime_bridge.py` detects `.lock`
  contention). A C2 (`specify_cli.core`) home would fail-open the moment a lower
  layer needs to *acquire* — the recurrence the mission exists to end.
- Kernel's zero-dep rule (C-001) forces the filelock-free design, which is what
  satisfies "one primitive".

**Alternatives considered**: C2 (`specify_cli.core`) — rejected: cannot be
adopted by charter/runtime without a layer violation; would leave the door open
to re-forking downward. Kept as the fallback only if `test_layer_rules.py` /
`test_pyproject_shape.py` reject a kernel `asyncio` module (not expected).

## R-02 — Safe-delete home + contract

**Decision**: `specify_cli/core/safe_delete.py` (C2), **no-follow (`lstat`) +
masked (`S_IMODE`)** semantics.

**Rationale**: every caller is in `specify_cli`; managed-asset deletion is a
specify_cli concern; no lower layer deletes managed assets (the `atomic`
criterion → C2). No-follow is correct: a managed-asset delete must never clear
the write bit on a symlink target outside the managed tree (boundary leak /
CWE-59-adjacent). `S_IMODE` masks the file-type bits out of the chmod.

**Alternatives**: kernel home — rejected (YAGNI; no lower-layer adopter, would
bloat the zero-dep root). Follow-symlink (`stat`) — rejected (the boundary leak).

## R-03 — Cross-OS parity proof strategy (NFR-004)

**Decision**: Prove Windows-mandatory semantics on POSIX via simulation, not
Windows CI alone. The lock primitive's read-safety and the safe-delete
read-only-then-remove are exercised under a test harness that emulates the
mandatory-lock refusal (the #4703 signature: process's own read of its held lock
raises `PermissionError`). Cross-process contention + blocking-with-timeout are
covered with real subprocesses/threads.

**Rationale**: the #4703 bug was invisible on POSIX because `flock` is advisory;
trusting POSIX CI is what let it ship. The filelock retirement (R-04) is the
highest risk precisely because lock-directory + blocking-timeout semantics must
be replicated exactly. Red-first parity tests are the guard.

**Known divergence class to cover** (from prior missions): mandatory-vs-advisory,
read-only-delete refusal, no-directory-flock on Windows. Trace ALL read sites
(the #4703 point fix itself missed a third self-held-lock read).

## R-04 — filelock retirement (FR-009) — the deferral seam

**Decision**: Full-scope target = remove `filelock>=3.13.0` (`pyproject.toml:84`)
after migrating all 6 sites. Deferral seam per A-01: if cross-process parity
cannot be proven in-mission, ship the stdlib migration + gate with the ratchet
still covering the filelock sites and burn them down in a tracked follow-up.

**Contracts to preserve** (else silent regression):
- `status/locking.py` — thread-local re-entrant counts.
- `review/verdict_commit_queue.py` — references the concrete `FileLock` type for
  a test double → the primitive must offer a supported injection seam.
- `auth/secure_storage/file_fallback.py` — fixed `timeout=10` blocking acquire.
- `zeitgeist_client/*` — local *client* consumer code (CLAUDE.md client-repo
  inversion), safe to migrate here; not upstream-authored surface.

## R-05 — Gate design (FR-010/FR-012, DIRECTIVE_043)

**Scope decision (post-tasks squad MF-1)**: both new gates scan **`src/` only** —
a deliberate divergence from the clock template's `SCAN_ROOTS=(src,tests,scripts)`.
Rationale: `tests/` and `scripts/` legitimately exercise raw `msvcrt`/`fcntl`/the
concrete lock type and inline platform branches (the parity harness *must*
simulate raw locking), so scanning them would red on ~51 lock + ~41 OS-detection
legitimate hits with no achievable empty terminal. The gates ban re-forking in
*production* code. Recorded in each gate docstring. **Idiom coverage (S-1)**: the
OS-detection gate bans all four — `os.name=="nt"`, `sys.platform=="win32"`,
`platform.system()=="Windows"`, `sys.platform.startswith("win")`. **Exemption
files are per-WP** (S-2, `_exemptions/lock-ban-wp0N.txt`) so parallel migration
WPs don't collide. **No safe-delete gate (MF-4)**: FR-003 is count-only
(copy-removal + review); a chmod-then-unlink AST gate is unreliable and a
re-forked delete helper is duplication, not a crash class.

**Decision**: Two non-vacuous `tests/architectural/` gates modelled on
`test_clock_import_ban.py` + `test_clock_call_ban.py`:
- **Lock gate**: AST import-ban (`import msvcrt`/`fcntl`/`filelock`,
  `from filelock import …`) + call-ban (`msvcrt.locking(...)`,
  `fcntl.flock/lockf(...)`, `FileLock(...)`) outside `kernel/locks.py`. Concrete
  floor (assert the canonical module *contains* the primitive so deleting the
  door fails). Self-mutation meta-test (feed a synthetic violation → must flag).
  Shrink-only allowlist seeded fail-closed with all current sites,
  **excluding `src/specify_cli/upgrade/migrations/`** (C-002, immutable one-offs).
- **OS-detection gate**: ban inline `os.name == "nt"` / `sys.platform == "win32"`
  outside the promoted `kernel/paths.py` seam; sanctioned-raw allowlist limited
  to the documented Windows-only C-module import guards.

**Predicate caveat (C-004)**: the lock gate must permit the canonical module's
own raw stdlib calls and its legitimate sidecar-record read — the invariant is
"no raw locking *outside* the sanctioned holder" + "no reading a *payload* while
holding a lock over it", not a blunt "no read under lock" (which would flag the
holder's own record read).

## R-06 — Supply-chain security note (plan directive 051 / mandatory)

This mission **removes** a third-party dependency (`filelock>=3.13.0`) and adds
**zero** new ones (the primitives are stdlib + `kernel.clock`). Net supply-chain
posture **improves**: one fewer external package, one fewer transitive-update
surface, no new registry/lifecycle-script exposure. No install-time lifecycle
scripts are introduced. Adversarial evidence: the grounding + post-spec squads
challenged the design; no contested finding was dropped (see design-decisions
tracer DD-07). Disposition of the filelock-retirement risk: **accepted** with the
A-01 deferral seam + red-first parity tests as mitigation.

## R-07 — DIRECTIVE_043 disambiguation (C-005)

DIRECTIVE_043 ("Close Defect Classes by Construction") already exists; directives
run to 051. "DIRECTIVE_043 gate" = a new gate *governed by* that directive, NOT a
new directive artifact. No `packs/built-in/directives/` file is added.
