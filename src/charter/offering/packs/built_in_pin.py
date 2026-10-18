"""Pin lockfile model for the vendored ``packs/built-in/`` tree (#3504).

``packs/built-in.source.yaml`` records **which spec-kitty-open-packs commit core
vendored ``packs/built-in/`` from** -- the **open-packs -> core** provenance
direction. This is the OPPOSITE anchor to open-packs' own
``built-in.source.yaml`` (core -> open-packs: which core commit open-packs
mirrored from). The two files share a schema shape but never the same meaning;
do not conflate them.

Integrity authority: ``tree_digest`` is :func:`clean_tree_digest` over
``packs/built-in/`` (declared file set, LF-normalised, pollution-immune), NOT
``snapshot_sha256`` (an ``rglob`` walk that a stray ``__pycache__`` perturbs).
The lockfile is a sibling of ``packs/built-in/`` so it is never self-digested.

The ``commit`` is always a 40-hex SHA; a tag is only a resolution input and is
never persisted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.packs.pack_clean_digest import clean_tree_digest
from kernel.pack_tiers import BUILT_IN

__all__ = [
    "BuiltInPin",
    "BuiltInPinError",
    "TreeDigest",
    "load_built_in_pin",
    "verify_built_in_pin",
    "write_built_in_pin",
]

_SHA_RE = re.compile(r"[0-9a-f]{40}")

_HEADER = (
    "# Pin lockfile: which spec-kitty-open-packs commit packs/built-in/ was vendored from.\n"
    "# Direction: open-packs -> core. (open-packs' own built-in.source.yaml records the\n"
    "# OPPOSITE anchor, core -> open-packs.) tree_digest = clean_tree_digest(packs/built-in,\n"
    "# level=built-in); this file sits OUTSIDE packs/built-in/ and is never digested.\n"
)


class BuiltInPinError(ValueError):
    """The pin lockfile is missing, malformed, or violates the SHA-not-tag rule."""


@dataclass(frozen=True)
class TreeDigest:
    """A labelled content digest."""

    algorithm: str
    value: str


@dataclass(frozen=True)
class BuiltInPin:
    """The built-in provenance pin (open-packs -> core)."""

    repository: str
    commit: str
    tree_digest: TreeDigest
    requires_core: str | None = None
    snapshot_sha256: str | None = None

    def __post_init__(self) -> None:
        if not _SHA_RE.fullmatch(self.commit):
            raise BuiltInPinError(f"commit must be a 40-hex lowercase SHA (never a tag); got {self.commit!r}")


def _require_str(data: dict[str, Any], key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise BuiltInPinError(f"{where}: missing or non-string field {key!r}")
    return value


def _optional_str(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise BuiltInPinError(f"field {key!r} must be a string or null")
    return value


def load_built_in_pin(path: Path) -> BuiltInPin:
    """Load and schema-validate the lockfile at *path* (fail closed)."""
    try:
        raw = YAML(typ="safe").load(Path(path).read_text(encoding="utf-8"))
    except (OSError, YAMLError) as exc:
        raise BuiltInPinError(f"cannot read pin lockfile {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise BuiltInPinError(f"{path}: expected a mapping at the top level")
    digest = raw.get("tree_digest")
    if not isinstance(digest, dict):
        raise BuiltInPinError(f"{path}: 'tree_digest' must be a mapping")
    return BuiltInPin(
        repository=_require_str(raw, "repository", str(path)),
        commit=_require_str(raw, "commit", str(path)),
        tree_digest=TreeDigest(
            algorithm=_require_str(digest, "algorithm", "tree_digest"),
            value=_require_str(digest, "value", "tree_digest"),
        ),
        requires_core=_optional_str(raw, "requires_core"),
        snapshot_sha256=_optional_str(raw, "snapshot_sha256"),
    )


def verify_built_in_pin(pin: BuiltInPin, pack_root: Path) -> bool:
    """Return True iff the clean-tree digest of *pack_root* equals the pin's."""
    actual: str = clean_tree_digest(pack_root, level=BUILT_IN)
    return actual == pin.tree_digest.value


def write_built_in_pin(pin: BuiltInPin, path: Path) -> None:
    """Write *pin* to *path* with stable key order and the direction header."""
    payload: dict[str, Any] = {
        "repository": pin.repository,
        "commit": pin.commit,
        "tree_digest": {"algorithm": pin.tree_digest.algorithm, "value": pin.tree_digest.value},
        "requires_core": pin.requires_core,
    }
    if pin.snapshot_sha256 is not None:
        payload["snapshot_sha256"] = pin.snapshot_sha256
    yaml = YAML()
    yaml.default_flow_style = False
    with Path(path).open("w", encoding="utf-8") as handle:
        handle.write(_HEADER)
        yaml.dump(payload, handle)
