"""Frozen record of every skill render Spec Kitty shipped (#7700).

A user-global or project skill file written by an older release has no
ownership record, so the install surfaces could only keep it as unproven
content, forever. This module is their one proof source for that case: a
file whose bytes are a render Spec Kitty itself shipped for the *same*
``<skill>/<relative path>`` is proven generated output, which may be
refreshed or retired. Anything else stays under the consent rule.

The data file ``data/historical_skill_renders.json`` is generated from git
history by ``scripts/skills/build_historical_skill_digests.py``, reviewed,
and committed; nothing here reads git. The reader fails closed: a missing
or malformed file proves nothing and never raises.
"""

from __future__ import annotations

import functools
import json
import logging
import re
from importlib import resources

__all__ = [
    "is_historical_render",
]

logger = logging.getLogger(__name__)

_DATA_PACKAGE = "specify_cli.skills.data"
_DATA_FILE = "historical_skill_renders.json"
_SCHEMA_VERSION = 1
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


def _data_bytes() -> bytes:
    return resources.files(_DATA_PACKAGE).joinpath(_DATA_FILE).read_bytes()


def _parse(raw: bytes) -> dict[str, frozenset[str]]:
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError("unsupported historical render list")
    renders = payload.get("renders")
    if not isinstance(renders, dict):
        raise ValueError("historical render list has no renders")
    parsed: dict[str, frozenset[str]] = {}
    for key, digests in renders.items():
        if not isinstance(key, str) or not isinstance(digests, list):
            raise ValueError("invalid historical render entry")
        if not all(isinstance(value, str) and _SHA256_HEX.fullmatch(value) for value in digests):
            raise ValueError(f"invalid digest for {key}")
        parsed[key] = frozenset(digests)
    return parsed


@functools.cache
def _renders() -> dict[str, frozenset[str]]:
    try:
        return _parse(_data_bytes())
    except (OSError, ValueError, UnicodeError) as exc:
        logger.debug("Historical skill render list unavailable; it proves nothing: %s", exc)
        return {}


def _clear_cache() -> None:
    """Forget the memoized list (tests that swap the data file)."""
    _renders.cache_clear()


def _key(skill_name: str, relative_path: str) -> str:
    return f"{skill_name}/{relative_path.replace(chr(92), '/')}"


def _historical_render_digests(skill_name: str, relative_path: str) -> frozenset[str]:
    """Every sha256 Spec Kitty shipped for *relative_path* inside skill *skill_name*."""
    return _renders().get(_key(skill_name, relative_path), frozenset())


def is_historical_render(skill_name: str, relative_path: str, sha256: str | None) -> bool:
    """Whether *sha256* is a render Spec Kitty shipped for exactly this skill path."""
    return sha256 is not None and sha256 in _historical_render_digests(skill_name, relative_path)
