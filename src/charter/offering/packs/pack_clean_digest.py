"""FR-015 — clean-tree drift digest over a pack's declared, level-aware files.

This digest is **separate** from :func:`snapshot_sha256` (NFR-004, byte-unchanged):
where ``snapshot_sha256`` ``rglob``-walks every installed file, this digest
enumerates only the DECLARED known files of a pack — the recognised artifact
subdirectories, the level's charter/DRG layout files, and ``pack.yaml`` — and
LF-normalizes their content. Enumerating a declared set (never ``rglob``) means
``__pycache__`` and other untracked noise are excluded *by construction*, so the
digest is identical across a ``git archive`` export, a working tree polluted with
``__pycache__``, and an installed copy (NFR-003).

The declared set is **level-aware**: the layout files differ by the declared
``pack_level`` (built-in ships sharded ``*.graph.yaml`` fragments at the root; an
org pack ships ``org-charter.yaml`` + ``drg/fragment.yaml``; a project pack ships
``graph.yaml``). The level comes from the pack's own ``pack.yaml`` descriptor.

The layout constants are read straight from :mod:`kernel.charter_pack_paths`
conventions (``DRG_FRAGMENT`` / ``ORG_CHARTER_FILENAME`` / ``PROJECT_GRAPH_FILENAME``
+ the per-level graph layout) so this module stays independent of any later
resolution seam.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.packs.builtin_manifest import _lf_normalized
from charter.offering.packs.hashing import hash_content_bytes
from charter.offering.packs.pack_descriptor import load_pack_descriptor
from charter.offering.packs.pack_manifest import RECOGNISED_ARTIFACT_DIRS
from kernel.charter_pack_paths import DRG_FRAGMENT, ORG_CHARTER_FILENAME, PROJECT_GRAPH_FILENAME
from kernel.pack_tiers import BUILT_IN, ORG, PackTier

__all__ = ["clean_tree_digest"]

#: The authored pack descriptor at a pack root.
PACK_DESCRIPTOR_FILENAME = "pack.yaml"

#: The DRG shard glob for the built-in pack (fragments live at the pack root).
_BUILT_IN_GRAPH_GLOB = "*.graph.yaml"

#: Build/tool noise never part of a pack's tracked content. Pruned from the
#: artifact-directory walk so the digest matches a ``git archive`` export.
_PYCACHE_DIRNAME = "__pycache__"
_COMPILED_SUFFIXES = (".pyc", ".pyo")


def _layout_files(pack_root: Path, level: PackTier) -> list[Path]:
    """Return the *level*'s charter/DRG layout files under *pack_root*.

    Resolved purely from the :mod:`kernel.charter_pack_paths` conventions:
    built-in → the sharded ``*.graph.yaml`` fragments at the root; org →
    ``org-charter.yaml`` + ``drg/fragment.yaml``; project → ``graph.yaml``.
    """
    if level == BUILT_IN:
        candidates = sorted(pack_root.glob(_BUILT_IN_GRAPH_GLOB))
    elif level == ORG:
        candidates = [pack_root / ORG_CHARTER_FILENAME, pack_root / DRG_FRAGMENT]
    else:
        candidates = [pack_root / PROJECT_GRAPH_FILENAME]
    # Same rule as the artifact walk: a symlinked layout file must not pull
    # content from outside the pack into the digest.
    return [path for path in candidates if not path.is_symlink() and path.is_file()]


def _recognised_dir_names(kinds: Iterable[ArtifactKind] | None) -> set[str]:
    """Recognised artifact-directory names, optionally restricted to *kinds*.

    ``None`` selects every recognised artifact directory. A kind filter keeps
    only the matching artifact dirs; the ``drg`` leaf is not a kind plural and
    is always retained (it is layout, not a kind).
    """
    if kinds is None:
        return set(RECOGNISED_ARTIFACT_DIRS)
    selected = {kind.plural for kind in kinds}
    names = {name for name in RECOGNISED_ARTIFACT_DIRS if name in selected}
    names.add("drg")
    return names


def _artifact_dir_files(dir_path: Path) -> list[Path]:
    """Every tracked file under *dir_path*, pruning ``__pycache__`` / compiled python.

    Uses :func:`os.walk` with in-place directory pruning (never ``rglob``) so
    build noise is skipped by construction rather than filtered afterwards.
    """
    collected: list[Path] = []
    for root, dirnames, filenames in os.walk(dir_path):
        dirnames[:] = [name for name in dirnames if name != _PYCACHE_DIRNAME]
        root_path = Path(root)
        for name in filenames:
            if name.endswith(_COMPILED_SUFFIXES):
                continue
            candidate = root_path / name
            if candidate.is_symlink() or not candidate.is_file():
                continue
            collected.append(candidate)
    return collected


def clean_tree_digest(pack_root: Path, *, level: PackTier, kinds: Iterable[ArtifactKind] | None = None) -> str:
    """Return a reproducible SHA-256 over *pack_root*'s declared file set.

    The declared set is ``pack.yaml`` + the *level*'s layout files + the
    recognised artifact directories (optionally restricted to *kinds*). *level*
    is the tier the pack is configured at: it selects the layout and is the
    inferred level for a legacy ``pack.yaml`` that still omits ``pack_level``
    (deprecation window), so such a pack digests rather than raising. Content is
    LF-normalized before hashing, so the digest is stable across export /
    worktree / installed copy and across platform line endings.

    Raises:
        FileNotFoundError: *pack_root* has no ``pack.yaml``.
        pydantic.ValidationError: ``pack.yaml`` is schema-invalid.
    """
    pack_root = Path(pack_root)
    descriptor_path = pack_root / PACK_DESCRIPTOR_FILENAME
    load_pack_descriptor(descriptor_path, inferred_level=level)

    files: set[Path] = {descriptor_path}
    files.update(_layout_files(pack_root, level))

    for name in _recognised_dir_names(kinds):
        dir_path = pack_root / name
        if dir_path.is_dir():
            files.update(_artifact_dir_files(dir_path))

    payload = bytearray()
    for path in sorted(files, key=lambda candidate: candidate.relative_to(pack_root).as_posix()):
        rel_bytes = path.relative_to(pack_root).as_posix().encode("utf-8")
        content = _lf_normalized(path.read_bytes())
        payload += len(rel_bytes).to_bytes(8, "big")
        payload += rel_bytes
        payload += len(content).to_bytes(8, "big")
        payload += content
    return hash_content_bytes(bytes(payload))
