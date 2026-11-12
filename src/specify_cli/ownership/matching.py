"""The owned-file matcher: one glob rule for a work package's ``owned_files``.

Shared by the owned-file evidence axis (``consolidation.wp_evidence``), ``move-task`` and the
review range, so review and the evidence gate classify a changed path the same way. Mission
``review-context-wp-diff-01M774QF`` moved it verbatim out of ``consolidation/wp_evidence.py``
(which re-exports both names) so ``review`` and ``runtime`` can import it without
``consolidation``. It mirrors the commit guard's own matcher
(``policy.commit_guard._matches_any_glob``), a separate, pre-existing authority for commit
scoping that this module does not replace.

A leaf: stdlib only, no ``specify_cli`` imports.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable, Sequence

__all__ = ["matches_owned", "owned_patterns"]


def owned_patterns(owned_files: Iterable[str]) -> tuple[str, ...]:
    """Normalized ownership globs for a work package (blank entries dropped, ``./`` and ``\\`` normalized)."""
    return tuple(pattern.replace("\\", "/").removeprefix("./") for pattern in owned_files if pattern.strip())


def matches_owned(path: str, patterns: Sequence[str]) -> bool:
    """Glob match of a repo-relative *path* against ownership *patterns*: the evidence axis' matcher.

    ``move-task`` and the evidence axis share it. It mirrors the commit guard's own matcher
    (``policy.commit_guard._matches_any_glob``), a separate, pre-existing authority for commit
    scoping that this does not replace.
    """
    normalized = path.replace("\\", "/").removeprefix("./")
    for pattern in patterns:
        if fnmatch.fnmatch(normalized, pattern):
            return True
        prefix = pattern.replace("/**", "").replace("/*", "").rstrip("/")
        if prefix and normalized.startswith(prefix + "/"):
            return True
    return False
