"""Generalised pack pin lockfile model (#3504, #6451).

A pin records **which spec-kitty-open-packs commit a pack was taken from**
(open-packs -> core provenance). One model serves every pack: the built-in pack
(``packs/built-in.source.yaml``) and the internal org pack
(``packs/internal.source.yaml``).

Fields beyond the original built-in pin:

* ``subtree`` -- the relative POSIX path of the pack inside the open-packs
  repository (``built-in`` or ``packs/built-in`` for the two layouts, C-005).
* ``tree_digest.level`` -- the tier ``clean_tree_digest`` runs at. Internal is an
  org pack, so its pin records ``org``. Absent means ``built-in`` (backward
  compatible).

Integrity authority: ``tree_digest`` is :func:`clean_tree_digest` (declared file
set, LF-normalised, pollution-immune). The ``commit`` is always a 40-hex SHA; a
tag is only a resolution input and is never persisted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, cast

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.packs.pack_clean_digest import clean_tree_digest
from kernel.pack_tiers import BUILT_IN, PACK_TIERS, PackTier

__all__ = [
    "PackPin",
    "PackPinError",
    "TreeDigest",
    "load_pack_pin",
    "verify_pack_pin",
    "write_pack_pin",
]

_SHA_RE = re.compile(r"[0-9a-f]{40}")
# Mirrors kernel.git.remote._ALLOWED_URL_SCHEMES (kernel cannot be imported for a private name).
_ALLOWED_REPOSITORY_SCHEMES = ("https://", "file://")

_HEADER = (
    "# Pin lockfile: which spec-kitty-open-packs commit this pack was taken from.\n"
    "# Direction: open-packs -> core. (open-packs' own built-in.source.yaml records the\n"
    "# OPPOSITE anchor, core -> open-packs.) The tree is fetched from the pinned commit,\n"
    "# not vendored; tree_digest = clean_tree_digest(<subtree>, level=<tree_digest.level>).\n"
)


class PackPinError(ValueError):
    """The pin lockfile is missing, malformed, or violates the SHA-not-tag rule."""


@dataclass(frozen=True)
class TreeDigest:
    """A labelled content digest and the tier it was computed at."""

    algorithm: str
    value: str
    level: str = BUILT_IN

    def __post_init__(self) -> None:
        if self.level not in PACK_TIERS:
            raise PackPinError(f"tree_digest.level must be one of {PACK_TIERS}; got {self.level!r}")


def validate_subtree(subtree: str) -> str:
    """Return *subtree* if it is a safe relative POSIX path, else raise."""
    if not subtree or "\\" in subtree:
        raise PackPinError(f"subtree must be a non-empty POSIX path without backslashes; got {subtree!r}")
    if subtree.startswith("-"):
        raise PackPinError(f"subtree must not start with '-'; got {subtree!r}")
    posix = PurePosixPath(subtree)
    if posix.is_absolute() or PureWindowsPath(subtree).drive or ".." in posix.parts:
        raise PackPinError(f"subtree must be relative and must not contain '..'; got {subtree!r}")
    return subtree


@dataclass(frozen=True)
class PackPin:
    """The provenance pin of one pack (open-packs -> core)."""

    repository: str
    commit: str
    tree_digest: TreeDigest
    requires_core: str | None = None
    snapshot_sha256: str | None = None
    subtree: str | None = None

    def __post_init__(self) -> None:
        if not self.repository.startswith(_ALLOWED_REPOSITORY_SCHEMES):
            raise PackPinError(f"repository must be an https:// or file:// URL; got {self.repository!r}")
        if not _SHA_RE.fullmatch(self.commit):
            raise PackPinError(f"commit must be a 40-hex lowercase SHA (never a tag); got {self.commit!r}")
        if self.subtree is not None:
            validate_subtree(self.subtree)


def _require_str(data: dict[str, Any], key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise PackPinError(f"{where}: missing or non-string field {key!r}")
    return value


def _optional_str(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise PackPinError(f"field {key!r} must be a string or null")
    return value


def _read_mapping(path: Path) -> dict[str, Any]:
    try:
        raw = YAML(typ="safe").load(Path(path).read_text(encoding="utf-8"))
    except (OSError, YAMLError) as exc:
        raise PackPinError(f"cannot read pin lockfile {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise PackPinError(f"{path}: expected a mapping at the top level")
    return raw


def load_pack_pin(path: Path, *, require_subtree: bool = True) -> PackPin:
    """Load and schema-validate the lockfile at *path* (fail closed).

    ``require_subtree=False`` is for the transitional ``built_in_pin`` alias only.
    """
    raw = _read_mapping(path)
    digest = raw.get("tree_digest")
    if not isinstance(digest, dict):
        raise PackPinError(f"{path}: 'tree_digest' must be a mapping")
    subtree = _optional_str(raw, "subtree")
    if subtree is None and require_subtree:
        raise PackPinError(f"{path}: missing field 'subtree' (the pack's path inside the open-packs repository)")
    return PackPin(
        repository=_require_str(raw, "repository", str(path)),
        commit=_require_str(raw, "commit", str(path)),
        tree_digest=TreeDigest(
            algorithm=_require_str(digest, "algorithm", "tree_digest"),
            value=_require_str(digest, "value", "tree_digest"),
            level=_optional_str(digest, "level") or BUILT_IN,
        ),
        requires_core=_optional_str(raw, "requires_core"),
        snapshot_sha256=_optional_str(raw, "snapshot_sha256"),
        subtree=subtree,
    )


def verify_pack_pin(pin: PackPin, pack_root: Path) -> bool:
    """Return True iff the clean-tree digest of *pack_root* equals the pin's."""
    actual: str = clean_tree_digest(pack_root, level=cast(PackTier, pin.tree_digest.level))
    return actual == pin.tree_digest.value


def write_pack_pin(pin: PackPin, path: Path) -> None:
    """Write *pin* to *path* with stable key order and the direction header."""
    payload: dict[str, Any] = {"repository": pin.repository, "commit": pin.commit}
    if pin.subtree is not None:
        payload["subtree"] = pin.subtree
    payload["tree_digest"] = {
        "algorithm": pin.tree_digest.algorithm,
        "value": pin.tree_digest.value,
        "level": pin.tree_digest.level,
    }
    if pin.requires_core is not None:
        payload["requires_core"] = pin.requires_core
    if pin.snapshot_sha256 is not None:
        payload["snapshot_sha256"] = pin.snapshot_sha256
    yaml = YAML()
    yaml.default_flow_style = False
    with Path(path).open("w", encoding="utf-8") as handle:
        handle.write(_HEADER)
        yaml.dump(payload, handle)
