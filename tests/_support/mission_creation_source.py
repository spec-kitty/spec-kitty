"""Source of the ``mission_creation`` module family, for AST/source pins (#5634).

``specify_cli.core.mission_creation`` was split into sibling leaf modules with
the bodies moved verbatim. Structural pins that used to read the one file read
the family through this helper instead: the module list is derived from disk
(``core/mission_creation*.py``), so a new sibling joins every pin
automatically, and :func:`family_source` strips the ``_mc.`` qualifier of the
patch-seam routing, so a routed ``_mc.get_current_branch(...)`` reads as the
plain ``get_current_branch(...)`` call it was before the split.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
CORE_DIR = SRC / "specify_cli" / "core"
MISSION_CREATION_MODULE_PATHS: tuple[Path, ...] = tuple(sorted(CORE_DIR.glob("mission_creation*.py")))
FACADE: Path = CORE_DIR / "mission_creation.py"
DECISIONS: Path = CORE_DIR / "mission_creation_decisions.py"
#: The leaf modules: the family minus the façade and the pure decisions module.
LEAVES: tuple[Path, ...] = tuple(path for path in MISSION_CREATION_MODULE_PATHS if path not in (FACADE, DECISIONS))
_ROUTING_QUALIFIER = re.compile(r"\b_mc\.")


def family_source() -> str:
    """Return the concatenated, routing-normalized source of the whole family."""
    return "\n\n".join(_ROUTING_QUALIFIER.sub("", path.read_text(encoding="utf-8")) for path in MISSION_CREATION_MODULE_PATHS)
