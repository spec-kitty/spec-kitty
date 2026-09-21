"""Independent lstat oracle. No production imports; atime alone is excluded."""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class Node:
    """Raw filesystem observation, including absent roots and empty directories."""

    kind: str
    sha256: str | None = None
    target: str | None = None
    mode: int | None = None
    mtime_ns: int | None = None


Snapshot = dict[tuple[str, str], Node]


def snapshot(roots: Mapping[str, Path]) -> Snapshot:
    """Observe all nodes without following links, filtering Git or ignored files."""
    result: Snapshot = {}

    def visit(root_id: str, path: Path, relative: str) -> None:
        try:
            info = path.lstat()
        except FileNotFoundError:
            result[(root_id, relative)] = Node("absent")
            return
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISLNK(info.st_mode):
            node = Node("symlink", target=os.readlink(path), mode=mode, mtime_ns=info.st_mtime_ns)
        elif stat.S_ISREG(info.st_mode):
            # Independent file-integrity oracle, not charter canonical hashing.
            digest = hashlib.sha256(path.read_bytes()).hexdigest()  # noqa: TID251 -- raw filesystem checksum
            node = Node("file", sha256=digest, mode=mode, mtime_ns=info.st_mtime_ns)
        elif stat.S_ISDIR(info.st_mode):
            node = Node("directory", mode=mode, mtime_ns=info.st_mtime_ns)
        else:
            node = Node("special", mode=mode, mtime_ns=info.st_mtime_ns)
        result[(root_id, relative)] = node
        if node.kind == "directory":
            for child in sorted(path.iterdir()):
                visit(root_id, child, child.name if relative == "." else f"{relative}/{child.name}")

    for root_id, path in sorted(roots.items()):
        visit(root_id, path, ".")
    return result


#: ``specify_cli.runtime.asset_preparation._cold_install_sentinel`` names its
#: per-user lock-coordination directory ``f"{runtime_root.name}-cold-install"``
#: (a sibling of ``kernel.paths.get_runtime_state_root()``, #4756 WP02). The
#: cold-install serialization lock is acquired on ANY cold-anchor path
#: ``recheck_assets`` takes -- including one that ultimately refuses without
#: writing a single asset -- and ``kernel.locks.machine_file_lock``'s G3
#: ("release truncates, never unlinks") leaves its empty ``.lock`` sidecar on
#: disk afterward. That is process-coordination infrastructure this oracle
#: must not mistake for an asset/content change; production's own
#: ``check_assets`` mirrors the same tolerance for the identical reason
#: (``_is_cold_install_sentinel_materialization``).
_COLD_INSTALL_SUFFIX = "-cold-install"


def _cold_install_exclusions(
    keys: Iterable[tuple[str, str]],
) -> tuple[frozenset[tuple[str, str]], frozenset[tuple[str, str]]]:
    """Identify cold-install sentinel keys purely structurally.

    No production import (module docstring): this recognizes the SAME
    ``f"{name}-cold-install"`` naming convention ``_cold_install_sentinel``
    documents and is bound to, rather than importing the function that
    builds the path.

    Returns ``(ignored, mtime_only)``:
      - ``ignored`` -- the sentinel directory itself and everything nested
        under it (its persistent ``.lock`` sidecar). Never compared.
      - ``mtime_only`` -- the sentinel directory's immediate parent. Its
        KIND/MODE are still compared for real drift; only its ``mtime_ns``
        (perturbed by the sentinel directory springing into existence, or
        by its ``.lock`` sidecar being created/truncated inside it) is
        excluded from the comparison.
    """
    key_set = set(keys)
    sentinel_dirs = {(root, relative) for root, relative in key_set if relative.split("/")[-1].endswith(_COLD_INSTALL_SUFFIX)}
    ignored: set[tuple[str, str]] = set()
    mtime_only: set[tuple[str, str]] = set()
    for root, relative in sentinel_dirs:
        ignored.add((root, relative))
        segments = relative.split("/")
        mtime_only.add((root, "/".join(segments[:-1]) or "."))
        prefix = f"{relative}/"
        ignored |= {(r, rel) for r, rel in key_set if r == root and rel.startswith(prefix)}
    return frozenset(ignored), frozenset(mtime_only)


def _is_sentinel_parent_materialization(before_node: Node | None, after_node: Node | None) -> bool:
    """Did a sentinel-parent key spring into existence purely to hold the sentinel?

    A cold-anchor recheck acquires the cold-install serialization lock via
    ``mkdir(parents=True)``, which materializes not only the sentinel
    directory (already in ``ignored``) but, when its parent did not yet
    exist, that parent too -- an ``absent -> bare directory`` transition on
    the sentinel's immediate parent. That container carries no asset content
    (any real child is its own, still-compared key), so it is the same
    coordination side effect the mtime-only tolerance already covers for a
    pre-existing parent -- just one layer deeper, where the parent itself is
    newly created. Tolerate ONLY absent -> directory; a file, a symlink, or a
    real mode change on a pre-existing directory is still caught.
    """
    before_absent = before_node is None or before_node.kind == "absent"
    return before_absent and after_node is not None and after_node.kind == "directory"


def assert_unchanged(before: Snapshot, after: Snapshot) -> None:
    """Enforce exact within-fixture purity, including parent mtimes.

    The one deliberate exception is the cold-install sentinel (see
    :func:`_cold_install_exclusions`): a serialization lock a cold-anchor
    recheck can leave behind even on a path that refuses without writing
    any asset is not the kind of drift this oracle exists to catch. That
    tolerance extends to the sentinel's immediate parent -- its mtime when
    it pre-exists, and its bare ``absent -> directory`` materialization when
    the sentinel's own ``mkdir(parents=True)`` created it (see
    :func:`_is_sentinel_parent_materialization`).
    """
    all_keys = before.keys() | after.keys()
    ignored, mtime_only = _cold_install_exclusions(all_keys)
    changed = []
    for key in sorted(all_keys):
        if key in ignored:
            continue
        before_node, after_node = before.get(key), after.get(key)
        if key in mtime_only:
            if _is_sentinel_parent_materialization(before_node, after_node):
                continue
            if before_node is not None and after_node is not None:
                before_node = replace(before_node, mtime_ns=None)
                after_node = replace(after_node, mtime_ns=None)
        if before_node != after_node:
            changed.append(key)
    assert not changed, f"Filesystem changed: {changed}"


@dataclass(frozen=True)
class Effect:
    """Net persistent operation; raw timestamps remain in the snapshots."""

    root: str
    path: str
    action: str
    before: Node
    after: Node


def _action(before: Node, after: Node) -> str | None:
    if before.kind == "absent" and after.kind != "absent":
        return "create"
    if after.kind == "absent" and before.kind != "absent":
        return "delete"
    if before.kind != after.kind:
        return "replace"
    if before.sha256 != after.sha256:
        return "update"
    if before.target != after.target:
        return "retarget"
    if before.mode != after.mode:
        return "chmod"
    return None


def net_delta(before: Snapshot, after: Snapshot) -> tuple[Effect, ...]:
    """Derive path/kind/content/mode effects; mtime-only churn is purity evidence.

    A child's create changes parent mtime without a separate apply operation.
    Git internals remain present; callers must report their changes separately.
    No cross-copy content or timestamp-field normalization is performed here.

    The cold-install sentinel directory itself (see
    :func:`_cold_install_exclusions`) is excluded here too: its appearance is
    process-coordination infrastructure, never an owner-effect this oracle
    should report as a "create". The sentinel's *parent* is NOT excluded here,
    unlike in :func:`assert_unchanged`: when a real ``apply`` legitimately
    provisions into a cold home, creating that home root is a genuine planned
    owner-effect the caller's expected-effect set accounts for, so net_delta
    must report it faithfully.
    """
    all_keys = before.keys() | after.keys()
    ignored, _mtime_only = _cold_install_exclusions(all_keys)
    effects = []
    for root, path in sorted(all_keys):
        if (root, path) in ignored:
            continue
        old = before.get((root, path), Node("absent"))
        new = after.get((root, path), Node("absent"))
        action = _action(old, new)
        if action:
            effects.append(Effect(root, path, action, old, new))
    return tuple(effects)
