"""``kernel.git`` — the one owner of reading paths from git and the owner of every remote read (push is excluded, FR-015).

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

The package also owns remote contact (:mod:`kernel.git.remote`): callers never
build a remote-contacting git argv themselves;
``tests/architectural/test_remote_contact_owner.py`` enforces that.
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
    tree_entries,
    tree_entry,
    tree_paths,
)
from kernel.git.paths import GitPath
from kernel.git.remote import (
    CLONE_TIMEOUT,
    FETCH_TIMEOUT,
    LS_REMOTE_TIMEOUT,
    AheadBehind,
    RemoteUnreachable,
    clone_repository,
    describe_remote_head,
    divergence,
    fetch_branches,
    fetch_tags,
    no_prompt_env,
    remote_heads,
    resolve_remote,
    tracking_ref,
)
from kernel.git.runner import GitCommandError, GitResult, decode_path, run_git

__all__ = [
    "CLONE_TIMEOUT",
    "FETCH_TIMEOUT",
    "LS_REMOTE_TIMEOUT",
    "AheadBehind",
    "GitCommandError",
    "GitPath",
    "GitResult",
    "IndexEntry",
    "NameStatusEntry",
    "NumstatEntry",
    "RemoteUnreachable",
    "StatusEntry",
    "TreeEntry",
    "changed_entries",
    "changed_paths",
    "clone_repository",
    "commit_paths",
    "decode_path",
    "describe_remote_head",
    "divergence",
    "fetch_branches",
    "fetch_tags",
    "index_entries",
    "is_tracked",
    "log_paths",
    "no_prompt_env",
    "numstat_entries",
    "remote_heads",
    "resolve_remote",
    "run_git",
    "status_entries",
    "tracked_paths",
    "tracking_ref",
    "tree_entries",
    "tree_entry",
    "tree_paths",
]
