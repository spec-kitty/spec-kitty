# Tracer: Design Decisions — Cross-OS Primitive Unification (01M2T1CM)

Seeded at planning; append during implementation.

## DD-01 — Lock primitive home = kernel (C1), `kernel/locks.py`

Decisive on repo precedent: `kernel/vcs_lock.py`, `kernel/atomic.py`,
`kernel/clock.py` are all zero-third-party-dep cores homed in kernel *so lower
layers adopt them without crossing the layer boundary*. `MachineFileLock`
(`core/file_lock.py`) is already pure stdlib + `kernel.clock`, already
sidecar-model, already #4703-safe → homing it in kernel is a **move, not a
rewrite**. Lower layers already *sense* locks (`charter/offering/resolver.py`,
`src/runtime/next/runtime_bridge.py`), so a C2 (`specify_cli.core`) home would
fail-open to a future layer-violation the moment a lower layer needs to
*acquire*. Kernel's zero-dep rule **forces** the filelock-free design, which is
what satisfies the "one primitive" acceptance.

## DD-02 — `filelock` is retired

Keeping the library forces two primitives, failing #4714's "one canonical lock
primitive". Kernel-home + zero-dep rule = the enforcement mechanism.

## DD-03 — safe-delete home = C2 (`specify_cli/core/`), `lstat`+`S_IMODE` semantics

Pure stdlib so kernel is *possible*, but every caller is in `specify_cli` and
"managed-asset deletion" is a specify_cli concern; no lower layer deletes
managed assets → C2 by the repo's own criterion (the `atomic` docstring rule).
Adopt the no-follow (`lstat`) + masked (`S_IMODE`) semantics — a managed-asset
delete must never follow a symlink out of the managed tree (boundary leak /
CWE-59-adjacent). **Risk to prove before consolidating:** the command surface
materializes managed commands as *symlinks*; prove no delete path relies on
follow-chmod, or the no-follow switch relocates the PermissionError to the link
target.

## DD-04 — OS-detection seam = C1 (promote `kernel/paths.py::_is_windows`)

Mirrors the `clock` single-door pattern. **Testability constraint (load-bearing):**
callers must reach it via the *module attribute* (patchable as
`kernel.paths.is_windows`) so tests override it WITHOUT faking `os.name`
(`os.name="nt"` flips pathlib→WindowsPath and crashes pytest). Import guards for
Windows-only C modules (`import msvcrt`) legitimately stay raw at module scope.

## DD-05 — "DIRECTIVE_043 gate" = a new gate GOVERNED BY the existing directive

DIRECTIVE_043 ("Close Defect Classes by Construction") already exists (directives
run to 051). The ask is a new non-vacuous call-site gate *in the spirit of*
DIRECTIVE_043 (concrete floor + self-mutation test + shrink-only allowlist,
modelled on `test_clock_import_ban.py` / `test_clock_call_ban.py`) — NOT minting
a new directive #043 (a mis-number would be #052). Gate predicate must not
red-flag the canonical primitive's own legitimate sidecar-record read.

## DD-06 — Count corrections vs the issue text

- safe-delete: **3 live copies + 1 frozen migration** (`m_3_2_0rc45…`). The
  migration is immutable; the gate MUST exclude the migrations tree, and it must
  NOT be rewritten to import the canonical util.
- OS-detection: **4** `_is_windows` (kernel + `runtime/home.py` +
  `runtime/asset_preparation.py` + inline `core/file_lock.py` checks) — issue said 2.

## DD-07 — Post-spec review folds (reviewer-renata, 2026-09-18)

- **MF-1 (critical):** `runtime/asset_preparation.py`'s own raw `msvcrt`/`fcntl`
  cold-install locking (`_HELD_LOCKS`, ~L801-835) — the #4703-origin site whose
  fork count the point fix *increased* — was missing from the migration FRs.
  Added to FR-008; SC-003/SC-005's "→1 / allowlist empty" were arithmetically
  unreachable without it.
- **MF-2:** SC-003 conditioned on the A-01 deferral seam (was unconditionally
  "filelock removed", contradicting SC-005).
- **MF-3:** added FR-012 — a non-vacuous OS-detection ban gate (was only a soft
  "routable" mention; vacuously satisfiable).
- **SF-4:** home decision softened out of hard requirements into A-04
  (home-independent properties are binding; C1 is the decided-and-traced home
  that `/plan` validates). The issue reserved the home "for this mission" = a
  plan-phase decision.
- **SF-5:** added SC-006 — gate A-02's symlink proof (delete a real
  command-surface-shaped symlink whose target is outside the managed tree; prove
  the *negative*).
- NH wording: SC-002 count corrected (3 defs + 1 inline), NG-02 folds the
  sentinel-cleanup no-op, SC-005 requires the follow-up sub-issue to exist,
  A-01 uses wave (not WP) language, A-03 notes zeitgeist_client is client code.

## DD-08 — Post-tasks anti-laziness folds (planner-priti, 2026-09-18)

- **MF-1 gate scope = `src/` only**: the clock template scans `(src,tests,scripts)`;
  copying that would red the new gates on ~51 lock + ~41 OS-detection legitimate
  test/script hits (incl. the parity harness's own raw locking). Documented divergence.
- **MF-2/3**: routed 5 previously-uncounted OS-detection sites (`compat/cache`,
  `compat/config`, `compat/history`, `compat/_detect/runtime`,
  `auth/secure_storage/abstract`) into WP01; relabelled the gate allowlist to
  import-guards-only; `pre_review_gate:260` → WP04, `token_manager:109` → WP03.
- **MF-4**: FR-003 is count-only — no safe-delete gate (plan corrected; a
  chmod-then-unlink AST gate is unreliable; a re-forked delete helper is
  duplication, not a crash class).
- **S-1**: gates ban all four idioms (`os.name`, `sys.platform=="win32"`,
  `platform.system()=="Windows"`, `sys.platform.startswith("win")`).
- **S-2**: per-WP exemption files; orchestrator runs WP04→WP05 sequentially.
- **N-1/2/3/4**: WP05 deferral requires a failing-parity test as evidence; WP03
  parity harness's PRIMARY proof is structural (no payload-read code path); WP02
  adds an rmtree-onerror-symlink test; WP03 flags NFR-002 as CI-certified
  (conftest.py cross-cutting) + per-mode helper extraction for complexity ≤15.

## Deferred (tracked, not in this mission)

- argv false-negative detectors in `__init__.py` (`_is_next` / `_is_live_work_hook`
  / `_is_session_start`) — separable surface, needs a version bump; latent today.
- cold-sentinel CWE-377 generalization — YAGNI, Windows-only + per-user `%TEMP%`
  as shipped.
