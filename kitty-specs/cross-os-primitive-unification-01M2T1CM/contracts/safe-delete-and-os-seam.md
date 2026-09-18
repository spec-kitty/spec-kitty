# Contract — Safe-delete util + OS-detection seam + gates

## A. Safe-delete util (`specify_cli/core/safe_delete.py`)

```python
def force_writable(path: Path) -> None:
    """Restore the owner write bit before removing a managed asset.
    NO-FOLLOW: chmod(stat.S_IMODE(path.lstat().st_mode) | stat.S_IWRITE)."""

def safe_unlink(path: Path) -> None: ...   # force_writable on retry, then unlink
def safe_rmdir(path: Path) -> None: ...     # force_writable on retry, then rmdir
def safe_rmtree(path: Path) -> None: ...    # rmtree with an onerror force-writable shim
```

**Guarantees**
- SD1 — no-follow (`lstat`) + masked (`S_IMODE`): never touches a symlink target
  outside the managed tree (FR-002, SC-006).
- SD2 — Windows read-only refusal handled (clear bit → remove) (FR-001).
- SD3 — one implementation; installer.py / agent_skills.py / asset_preparation.py
  route through it, their private copies deleted (FR-003). The frozen migration
  `m_3_2_0rc45…` copy is untouched (C-002).

**Acceptance test (SC-006, the negative proof)**: create a managed symlink whose
target lies OUTSIDE the managed tree; delete via `safe_unlink`; assert the delete
succeeds and the target's mode + existence are unchanged.

## B. OS-detection seam (`kernel/paths.py`)

```python
def is_windows() -> bool:
    """Canonical Windows check. Reach it via the module attribute so tests can
    monkeypatch `kernel.paths.is_windows` WITHOUT faking os.name."""
    return os.name == "nt"
```

**Guarantees**
- OS1 — consumers do `from kernel.paths import is_windows` and call `is_windows()`
  (patchable), never an inline literal (FR-005).
- OS2 — patchable without faking `os.name` (C-003).
- OS3 — Windows-only C-module import guards (`import msvcrt`/`import fcntl` at
  module scope) may stay raw (documented allowlist in the FR-012 gate).

## C. Gates (`tests/architectural/`) — DIRECTIVE_043

**Both gates scan `src/` ONLY** (post-tasks squad MF-1) — a deliberate divergence
from the clock template's `SCAN_ROOTS=(src,tests,scripts)`; `tests/`/`scripts/`
legitimately use raw primitives + platform branches (the parity harness must).
**Exemption files are per-WP** (`_exemptions/lock-ban-wp0N.txt`) so parallel
migration WPs shrink independently (S-2). **There is no safe-delete gate** —
FR-003 is count-only (MF-4).

**Lock gate (`test_lock_primitive_ban.py`)** — FR-010, NFR-003
- Import-ban: `import msvcrt|fcntl|filelock`, `from filelock import …` outside `kernel/locks.py` (src/ only).
- Call-ban: `msvcrt.locking(...)`, `fcntl.flock/lockf(...)`, `FileLock(...)` outside `kernel/locks.py`.
- Floor: assert `kernel/locks.py` contains `msvcrt.locking` AND `fcntl.flock` (door can't be deleted to pass).
- Self-mutation: synthetic violation string must be flagged.
- Allowlist: shrink-only per-WP files, seeded fail-closed with every current `src/` site; excludes `src/specify_cli/upgrade/migrations/`.
- Predicate honours the holder (C-004): permits `kernel/locks.py`'s own raw calls + sidecar-record read.

**OS-detection gate (`test_os_detection_ban.py`)** — FR-012
- Ban all four idioms (S-1) — `os.name == "nt"`, `sys.platform == "win32"`,
  `platform.system() == "Windows"`, `sys.platform.startswith("win")` — outside `kernel/paths.py` (src/ only).
- Floor + self-mutation as above.
- Sanctioned-raw allowlist: the module-scope Windows-only C-module **import guards ONLY**
  (`if <win>: import msvcrt/fcntl`). Routable branches (`token_manager:109`,
  `pre_review_gate:260`, `abstract.py:44`, `compat/*`) are ROUTED, not allowlisted.

**Terminal state**
- Lock allowlist: empty (full scope) OR exactly the deferred filelock sites with a
  tracked follow-up sub-issue that exists (A-01/SC-005).
- OS allowlist: import-guards only.
