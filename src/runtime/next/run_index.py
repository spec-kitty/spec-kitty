"""The RunIndex port — the single locked, repo-relative reader/writer of
``.kittify/runtime/feature-runs.json`` (mission runindex-feature-runs-port,
fixes #5390 / #5389, refs #2624).

Why this module exists
----------------------
The run index maps a mission to its runtime run directory. Two defects lived in
its former single writer (``runtime_bridge_io.get_or_start_run``):

- **#5390 (P0):** ``run_dir`` was persisted as an *absolute* path, so a copied
  or moved project resolved (and mutated) the *original* folder's run cursor.
- **#5389 (P1):** the read-modify-write of the index was unlocked, so concurrent
  ``next`` starts lost each other's registration (last-writer-wins).

This port closes both classes by construction, following the operator-decided
direction (ADR ``2026-08-16-5`` operator-config/env-expand seam — *persisted
state stores a token, never a resolved path*):

1. **Repo-relative token.** ``run_dir`` is serialized as a token relative to the
   invoking ``repo_root`` (canonically ``.kittify/runtime/runs/<run_id>`` — the
   run store is always ``repo_root/.kittify/runtime/runs``) and resolved at read
   time against the *invoking* ``repo_root`` via :func:`kernel.env_expand.expand_raw_template`
   (so a future ``${…}`` runtime-root knob in ``.kitty.env`` still works).
2. **Containment (#2624).** A resolved ``run_dir`` that escapes the invoking repo
   is *refused, never followed* — :class:`RunDirOutsideRepoError`.
3. **Locked read-modify-write (#5389).** Every write takes a dedicated
   ``feature-runs.json.lock`` sidecar (:func:`kernel.locks.machine_file_lock`;
   never the payload path — lock guarantee G1), re-reads the on-disk index inside
   the lock, merges, and atomically replaces.

Single-reader discipline: this module is the ONLY one that names the index
filename literal and opens the index file. ``runtime_bridge_io``'s
``load_feature_runs`` / ``save_feature_runs`` are thin delegates over
:func:`read_index_file` / :func:`write_index_file` (kept so the existing
monkeypatch seams survive), and ``state/contract.py`` imports
:data:`FEATURE_RUNS_FILENAME` rather than duplicating the literal.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kernel.atomic import atomic_write
from kernel.env_expand import expand_raw_template
from kernel.locks import SyncMachineFileLock, machine_file_lock
from runtime.next._internal_runtime.schema import MissionRuntimeError

__all__ = [
    "FEATURE_RUNS_FILENAME",
    "RunDirOutsideRepoError",
    "feature_runs_path",
    "index_lock",
    "read_index_file",
    "resolve_run_dir",
    "runs_root",
    "save_index",
    "serialize_run_dir",
    "write_index_file",
]

#: The run-index filename. Frozen legacy name (a compatibility rename is tracked
#: separately); single-homed here so the single-reader gate has one definition.
FEATURE_RUNS_FILENAME = "feature-runs.json"

_KITTIFY_DIR = ".kittify"
_RUNTIME_SUBDIR = "runtime"
_RUNS_SUBDIR = "runs"
_LOCK_SUFFIX = ".lock"
#: Bounded wait for the index lock. Comfortably above the sub-second hold of a
#: JSON re-read + merge + atomic replace, well under the 60 s stale ceiling.
_LOCK_TIMEOUT_S = 10.0


class RunDirOutsideRepoError(MissionRuntimeError):
    """A stored ``run_dir`` resolves outside the invoking repository root.

    Raised instead of following a nonportable/foreign cursor reference (the
    #5390 copy/move symptom): a copied or moved project must operate on its OWN
    runtime, never the original folder's. Containment discipline of epic #2624.
    """

    error_code = "RUN_DIR_OUTSIDE_REPO"

    def __init__(self, *, token: str, resolved: Path, repo_root: Path) -> None:
        self.token = token
        self.resolved = resolved
        self.repo_root = repo_root
        super().__init__(
            f"Run directory token {token!r} resolves to {resolved} which is outside the "
            f"invoking repository {repo_root}. Refusing to follow a nonportable runtime "
            f"reference; heal a relocated index with `spec-kitty migrate` "
            f"(or inspect it with `spec-kitty doctor run-index`)."
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = super().to_dict()
        payload.update(
            {
                "token": self.token,
                "resolved": str(self.resolved),
                "repo_root": str(self.repo_root),
            }
        )
        return payload


# ---------------------------------------------------------------------------
# Paths + lock
# ---------------------------------------------------------------------------


def feature_runs_path(repo_root: Path) -> Path:
    """The run-index file for ``repo_root``."""
    return repo_root / _KITTIFY_DIR / _RUNTIME_SUBDIR / FEATURE_RUNS_FILENAME


def runs_root(repo_root: Path) -> Path:
    """The deterministic run store for ``repo_root`` (``.kittify/runtime/runs``)."""
    return repo_root / _KITTIFY_DIR / _RUNTIME_SUBDIR / _RUNS_SUBDIR


def _lock_path(repo_root: Path) -> Path:
    """A DEDICATED lock-only sidecar next to the index (never the payload — G1)."""
    return feature_runs_path(repo_root).with_name(FEATURE_RUNS_FILENAME + _LOCK_SUFFIX)


def index_lock(repo_root: Path) -> SyncMachineFileLock:
    """The canonical index write lock: a bounded, blocking machine file lock."""
    return machine_file_lock(_lock_path(repo_root), blocking=True, timeout_s=_LOCK_TIMEOUT_S)


# ---------------------------------------------------------------------------
# File I/O — the sole open sites for the index
# ---------------------------------------------------------------------------


def read_index_file(path: Path) -> dict[str, Any]:
    """Read the raw run-index JSON at ``path`` (``{}`` if missing/corrupt)."""
    if not path.exists():
        return {}
    try:
        loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return loaded
    except (json.JSONDecodeError, OSError):
        return {}


def write_index_file(path: Path, index: dict[str, Any]) -> None:
    """Atomically persist the run-index JSON to ``path`` (raw; no tokenization)."""
    content = json.dumps(index, indent=2, sort_keys=True)
    atomic_write(path, content, mkdir=True)


# ---------------------------------------------------------------------------
# Token serialization + read-time resolution + containment
# ---------------------------------------------------------------------------


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:  # pragma: no cover - defensive (e.g. permission on a prefix)
        return path


def serialize_run_dir(run_dir: str, repo_root: Path) -> str:
    """Return the persisted token for ``run_dir`` — NEVER an absolute in-repo path.

    - An already-relative value is returned as a normalized POSIX token.
    - An absolute path inside ``repo_root`` is relativized to a POSIX token.
    - An absolute path OUTSIDE ``repo_root`` (a foreign/legacy entry this write is
      merely passing through) is left byte-for-byte unchanged — healing such an
      entry is the migration's job, not an incidental side effect of an unrelated
      write (adversarial review C2).
    """
    candidate = Path(run_dir)
    if not candidate.is_absolute():
        return candidate.as_posix()
    resolved = _safe_resolve(candidate)
    root = _safe_resolve(repo_root)
    if _is_within(resolved, root):
        return resolved.relative_to(root).as_posix()
    return run_dir


def resolve_run_dir(stored: str, repo_root: Path) -> Path:
    """Resolve a stored ``run_dir`` token against the INVOKING ``repo_root``.

    ``${VAR}``/``~`` tokens are expanded first (never-raising), then a relative
    token is anchored at ``repo_root`` and an absolute one is taken as-is. The
    resolved location must lie within ``repo_root`` or :class:`RunDirOutsideRepoError`
    is raised (containment, #2624). The RETURNED path is the lexical anchor
    (``repo_root / token`` or the stored absolute), not the symlink-resolved real
    path, so equality with caller-supplied paths is preserved; only the
    containment CHECK compares fully-resolved real paths (so macOS ``/var`` ↔
    ``/private/var`` and symlinked roots are not spuriously refused).
    """
    expanded = expand_raw_template(stored)
    candidate = Path(expanded)
    anchored = candidate if candidate.is_absolute() else (repo_root / candidate)
    if not _is_within(_safe_resolve(anchored), _safe_resolve(repo_root)):
        raise RunDirOutsideRepoError(token=stored, resolved=anchored, repo_root=repo_root)
    return anchored


def save_index(repo_root: Path, index: dict[str, Any]) -> None:
    """Tokenize every entry's ``run_dir`` (never persisting an in-repo absolute
    path) and atomically persist the index for ``repo_root``.

    Foreign/out-of-tree absolute entries pass through untouched (C2); in-repo
    absolute entries are opportunistically healed to relative tokens.
    """
    tokenized: dict[str, Any] = {}
    for key, entry in index.items():
        new_entry = dict(entry)
        run_dir = new_entry.get("run_dir")
        if isinstance(run_dir, str) and run_dir:
            new_entry["run_dir"] = serialize_run_dir(run_dir, repo_root)
        tokenized[key] = new_entry
    write_index_file(feature_runs_path(repo_root), tokenized)
