"""The cheap legacy charter-layout predicate (FR-011 / FR-012, #3732).

One function, :func:`detect_legacy_charter_layout`, names the **structural**
legacy shapes a project can still carry from before the charter-pack cutover:
the retired project layer directory, a standalone ``governance.yaml`` with the
retired selection key, and the retired keys in ``.kittify/config.yaml``. The
cutover upgrade migration (``m_4_0_0rc6_charter_pack_cutover``) and the CLI-root
gate (WP14) share it, so the gate and the migration cannot disagree.

Cost budget (research/runtime-seams.md §3): two ``stat`` calls plus one read of
``config.yaml`` (about 1 KB) on a project with no legacy state; YAML is parsed
only when a substring prefilter hits. ``charter.yaml`` is never read here (it is
155 KB in this repository); its legacy keys are the migration's own content
checks.

Layering (C-007): this module runs on every CLI invocation once WP14 wires the
gate, so it imports nothing from ``charter.*`` and loads PyYAML lazily.

Totality: the predicate never raises. An unreadable or unparseable file is
reported as a finding (:data:`UNREADABLE_PROJECT_ROOT`, :data:`UNREADABLE_CONFIG`,
:data:`UNREADABLE_GOVERNANCE_FILE`) so the gate can name it and the migration
is selected, where ``apply()`` fails with a named error. Every filesystem probe
is an ``os.lstat`` or a read inside ``try/except OSError``: on Python 3.11
``Path.is_dir()`` / ``Path.is_symlink()`` re-raise ``EACCES``.

This module is one of the few places allowed to spell the retired names (with
the cutover migration modules); it is exempt by file from the FR-016 and FR-018
gates.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from kernel.charter_pack_paths import KITTIFY_DIRNAME

__all__ = [
    "CONFIG_KEY_FINDINGS",
    "LEGACY_PROJECT_ROOT_POSIX",
    "LEGACY_PROJECT_ROOT_RELPATH",
    "LEGACY_SELECTION_KEYWORD",
    "ORGANISATION_PACKS_KEYWORD",
    "UNREADABLE_CONFIG",
    "UNREADABLE_GOVERNANCE_FILE",
    "UNREADABLE_PROJECT_ROOT",
    "detect_legacy_charter_layout",
    "governance_file_path",
    "is_convertible_organisation_pack",
    "legacy_org_block",
]

# --------------------------------------------------------------------------- #
# Retired names (the only spellings outside the cutover migration modules)
# --------------------------------------------------------------------------- #

#: The retired project layer directory under ``.kittify/``.
_LEGACY_PROJECT_DIRNAME = "doctrine"
#: The retired project layer, relative to the repository root.
LEGACY_PROJECT_ROOT_RELPATH = PurePosixPath(KITTIFY_DIRNAME, _LEGACY_PROJECT_DIRNAME)
#: :data:`LEGACY_PROJECT_ROOT_RELPATH` as a string, for prefix checks.
LEGACY_PROJECT_ROOT_POSIX = LEGACY_PROJECT_ROOT_RELPATH.as_posix()
#: The retired key spelling shared by ``doctrine.org``, ``governance.doctrine``,
#: ``tracker.doctrine``, the standalone ``governance.yaml`` and ``answers.yaml``.
LEGACY_SELECTION_KEYWORD = _LEGACY_PROJECT_DIRNAME
#: The retired flat org list key (OD-4).
ORGANISATION_PACKS_KEYWORD = "organisation_packs"

_ORG_KEY = "org"
_GOVERNANCE_KEY = "governance"
_TRACKER_KEY = "tracker"
_CONFIG_FILENAME = "config.yaml"
_CHARTER_DIRNAME = "charter"
_GOVERNANCE_FILENAME = "governance.yaml"
_PREFILTER_KEYWORDS = (LEGACY_SELECTION_KEYWORD.encode(), ORGANISATION_PACKS_KEYWORD.encode())

# --------------------------------------------------------------------------- #
# Finding names (stable; cheapest check first)
# --------------------------------------------------------------------------- #

_LEGACY_PROJECT_ROOT = "legacy_project_root"
UNREADABLE_PROJECT_ROOT = "unreadable_project_root"
_LEGACY_GOVERNANCE_FILE = "legacy_governance_file"
UNREADABLE_GOVERNANCE_FILE = "unreadable_governance_file"
UNREADABLE_CONFIG = "unreadable_config"
_LEGACY_ORG_PACKS_KEY = "legacy_org_packs_key"
_LEGACY_ORGANISATION_PACKS_KEY = "legacy_organisation_packs_key"
_LEGACY_GOVERNANCE_SELECTION_KEY = "legacy_governance_selection_key"
_LEGACY_TRACKER_OWNERSHIP_KEY = "legacy_tracker_ownership_key"

#: Every finding name, in the order :func:`detect_legacy_charter_layout` reports them.
_STRUCTURAL_FINDINGS: tuple[str, ...] = (
    _LEGACY_PROJECT_ROOT,
    UNREADABLE_PROJECT_ROOT,
    _LEGACY_GOVERNANCE_FILE,
    UNREADABLE_GOVERNANCE_FILE,
    UNREADABLE_CONFIG,
    _LEGACY_ORG_PACKS_KEY,
    _LEGACY_ORGANISATION_PACKS_KEY,
    _LEGACY_GOVERNANCE_SELECTION_KEY,
    _LEGACY_TRACKER_OWNERSHIP_KEY,
)

#: The findings that name a retired key in ``config.yaml``. The cutover
#: migration confirms them with a dry run before re-selecting itself after a
#: recorded application: a key it cannot rewrite (``charter_packs`` is not a
#: mapping) is kept for review and must not re-select it on every upgrade.
CONFIG_KEY_FINDINGS: frozenset[str] = frozenset(
    {_LEGACY_ORG_PACKS_KEY, _LEGACY_ORGANISATION_PACKS_KEY, _LEGACY_GOVERNANCE_SELECTION_KEY, _LEGACY_TRACKER_OWNERSHIP_KEY}
)

#: An org block names packs either as a ``packs`` list or in the single-pack form (``local_path``).
_ORG_BLOCK_FORMS = ("packs", "local_path")


def governance_file_path(root: Path) -> Path:
    """Return the standalone legacy ``.kittify/charter/governance.yaml`` of *root*."""
    return root / KITTIFY_DIRNAME / _CHARTER_DIRNAME / _GOVERNANCE_FILENAME


def legacy_org_block(config: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Return ``doctrine.org`` when it carries a pack list or the single-pack form."""
    section = config.get(LEGACY_SELECTION_KEYWORD)
    org = section.get(_ORG_KEY) if isinstance(section, Mapping) else None
    if isinstance(org, Mapping) and any(field in org for field in _ORG_BLOCK_FORMS):
        return org
    return None


def is_convertible_organisation_pack(entry: object) -> bool:
    """True for an ``organisation_packs[]`` entry expressible as a canonical pack entry.

    Only a mapping with a string ``name`` and ``path`` and a ``source`` that is
    absent or ``local_path`` converts; anything else is kept for review.
    """
    if not isinstance(entry, Mapping):
        return False
    source = entry.get("source", "local_path")
    return isinstance(entry.get("name"), str) and isinstance(entry.get("path"), str) and source == "local_path"


def _has_mapping_key(data: Mapping[str, Any], section: str, key: str) -> bool:
    block = data.get(section)
    return isinstance(block, Mapping) and key in block


def _config_findings(data: Mapping[str, Any]) -> list[str]:
    findings: list[str] = []
    if legacy_org_block(data) is not None:
        findings.append(_LEGACY_ORG_PACKS_KEY)
    flat = data.get(ORGANISATION_PACKS_KEYWORD)
    if isinstance(flat, list) and any(is_convertible_organisation_pack(entry) for entry in flat):
        findings.append(_LEGACY_ORGANISATION_PACKS_KEY)
    if _has_mapping_key(data, _GOVERNANCE_KEY, LEGACY_SELECTION_KEYWORD):
        findings.append(_LEGACY_GOVERNANCE_SELECTION_KEY)
    if _has_mapping_key(data, _TRACKER_KEY, LEGACY_SELECTION_KEYWORD):
        findings.append(_LEGACY_TRACKER_OWNERSHIP_KEY)
    return findings


def _load_prefiltered(path: Path) -> tuple[bool, Any]:
    """Return ``(readable, data)`` for *path*; ``data`` is ``None`` when the prefilter misses.

    An absent file is readable with no data. Any read or parse error is
    ``(False, None)``.
    """
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return True, None
    except OSError:
        return False, None
    if not any(token in raw for token in _PREFILTER_KEYWORDS):
        return True, None
    import yaml  # lazy: parsed only on a prefilter hit (cost budget, research §3)

    try:
        return True, yaml.safe_load(raw)
    except (yaml.YAMLError, UnicodeDecodeError, ValueError, RecursionError):
        return False, None


def _legacy_root_finding(root: Path) -> str | None:
    """The finding for the retired project layer: a directory or any symlink there.

    ``os.lstat`` inside ``try``: absent (``ENOENT``/``ENOTDIR``) is no finding,
    any other ``OSError`` (``EACCES``, ``EIO``) is :data:`UNREADABLE_PROJECT_ROOT`.
    """
    legacy_root = root.joinpath(*LEGACY_PROJECT_ROOT_RELPATH.parts)
    try:
        mode = os.lstat(legacy_root).st_mode
    except (FileNotFoundError, NotADirectoryError):
        return None
    except (OSError, ValueError):
        return UNREADABLE_PROJECT_ROOT
    if stat.S_ISLNK(mode) or stat.S_ISDIR(mode):
        return _LEGACY_PROJECT_ROOT
    return None


def detect_legacy_charter_layout(root: Path) -> tuple[str, ...]:
    """Return the structural legacy charter-layout findings of the project at *root*.

    An empty tuple means the project carries none of them. The function never
    raises.
    """
    findings: list[str] = []
    root_finding = _legacy_root_finding(root)
    if root_finding is not None:
        findings.append(root_finding)

    readable, governance = _load_prefiltered(governance_file_path(root))
    if not readable:
        findings.append(UNREADABLE_GOVERNANCE_FILE)
    elif isinstance(governance, Mapping) and LEGACY_SELECTION_KEYWORD in governance:
        findings.append(_LEGACY_GOVERNANCE_FILE)

    readable, config = _load_prefiltered(root / KITTIFY_DIRNAME / _CONFIG_FILENAME)
    if not readable:
        findings.append(UNREADABLE_CONFIG)
    elif isinstance(config, Mapping):
        findings.extend(_config_findings(config))
    return tuple(findings)
