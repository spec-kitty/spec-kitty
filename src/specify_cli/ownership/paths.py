"""The one normaliser and ``kitty-specs/`` test for a work package's ``owned_files`` entries.

``finalize-tasks`` reads them twice: the kitty-specs ban (``mission_parsing``) and the
lane-topology kind normalisation (``kind_normalisation``, #7809). Both must agree on what a
``kitty-specs/`` path is, so both call :func:`is_kitty_specs_path`. Pure: no I/O.
"""

from __future__ import annotations

from kernel.paths import to_posix
from specify_cli.core.constants import KITTY_SPECS_DIR

__all__ = ["is_kitty_specs_path", "normalize_owned_path"]

_KITTY_SPECS_PREFIX = f"{KITTY_SPECS_DIR}/"


def normalize_owned_path(path: str) -> str:
    """An ``owned_files`` entry as a repository-relative POSIX path: stripped, ``\\`` as ``/``, no leading ``./``."""
    normalized = to_posix(path.strip())
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def is_kitty_specs_path(path: str) -> bool:
    """Whether an ``owned_files`` entry (a glob included) targets ``kitty-specs/``, after normalisation."""
    normalized = normalize_owned_path(path)
    return normalized == KITTY_SPECS_DIR or normalized.startswith(_KITTY_SPECS_PREFIX)
