"""``kernel.git`` — the one owner of reading paths from git.

Split of responsibilities (mission git-paths-are-data, #5392/#5400):

* **How** lives here: :func:`run_git` (one subprocess seam), NUL-delimited
  (``-z``) output for every path listing, one lossless decode rule, the
  :class:`GitPath` value type with component-wise relations, and typed
  entries.
* **What** is asked by intent through the listing queries
  (:func:`status_entries`, :func:`tree_paths`, :func:`changed_paths`, ...).
  Domain decisions (for example "would a reset clobber this local file")
  stay with their owners and are expressed on :class:`GitPath`.

Callers never build a path-listing git argv or split git output themselves;
``tests/architectural/test_git_path_listing_owner.py`` enforces that.
"""

from __future__ import annotations

from kernel.git.listing import (
    IndexEntry,
    NameStatusEntry,
    NumstatEntry,
    StatusEntry,
    TreeEntry,
    changed_entries,
    changed_paths,
    commit_paths,
    index_entries,
    is_tracked,
    log_paths,
    numstat_entries,
    status_entries,
    tracked_paths,
    tree_entry,
    tree_paths,
)
from kernel.git.paths import GitPath
from kernel.git.runner import GitCommandError, GitResult, decode_path, run_git

__all__ = [
    "GitCommandError",
    "GitPath",
    "GitResult",
    "IndexEntry",
    "NameStatusEntry",
    "NumstatEntry",
    "StatusEntry",
    "TreeEntry",
    "changed_entries",
    "changed_paths",
    "commit_paths",
    "decode_path",
    "index_entries",
    "is_tracked",
    "log_paths",
    "numstat_entries",
    "run_git",
    "status_entries",
    "tracked_paths",
    "tree_entry",
    "tree_paths",
]
