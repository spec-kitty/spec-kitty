"""Plain tree-hashing helper shared by owned-checkout integration fixtures.

Deliberately NOT a test module and NOT a conftest fixture: a plain helper
module so code outside ``tests/integration/`` (for example a finalize
atomicity oracle) can reuse the same hashing without importing a test module
or a conftest (WP02 T011, plan §Test Layout).
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def hash_tree(root: Path, *, exclude: Path | None = None) -> dict[str, str]:
    """Return ``{relative_posix_path: sha256}`` for every file under ``root``.

    Includes ignored files. Excludes the ``.git`` directory everywhere, and
    excludes exactly ``exclude``'s resolved subtree when it is given (never a
    blanket ``.worktrees/`` exclusion -- a linked worktree elsewhere under
    ``root`` must still be visible to the hash).
    """
    root = root.resolve()
    resolved_exclude = exclude.resolve() if exclude is not None else None
    digest: dict[str, str] = {}
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.name == ".git":
                continue
            if resolved_exclude is not None and entry.resolve() == resolved_exclude:
                continue
            if entry.is_dir() and not entry.is_symlink():
                stack.append(entry)
                continue
            try:
                data = entry.read_bytes()
            except OSError:
                continue
            digest[entry.relative_to(root).as_posix()] = hashlib.sha256(data).hexdigest()  # noqa: TID251 — file-integrity checksum for the R snapshot (standard SHA-256), not charter freshness hashing
    return digest
