"""Source of the ``finalize-tasks`` module family, for AST/source pins (#5627).

``mission_finalize`` was split into sibling phase modules. Structural pins
that used to read the one file read the family through this helper instead:
the sources are concatenated (top-level names are unique across the family)
and the ``_mf.`` qualifier of the patch-seam routing is stripped, so a routed
call such as ``_mf.capture_branch_tip(...)`` reads as the plain
``capture_branch_tip(...)`` call it was before the split.
"""

from __future__ import annotations

from pathlib import Path

import re

AGENT_DIR = Path(__file__).resolve().parents[2] / "src/specify_cli/cli/commands/agent"
FINALIZE_MODULE_PATHS: tuple[Path, ...] = (
    AGENT_DIR / "mission_finalize.py",
    AGENT_DIR / "mission_finalize_seams.py",
    AGENT_DIR / "mission_finalize_branch_contract.py",
    AGENT_DIR / "mission_finalize_validation.py",
    AGENT_DIR / "mission_finalize_bootstrap.py",
    AGENT_DIR / "mission_finalize_planning_pin.py",
    AGENT_DIR / "mission_finalize_lanes.py",
    AGENT_DIR / "mission_finalize_commit.py",
)
_ROUTING_QUALIFIER = re.compile(r"\b_mf\.")


def finalize_family_source() -> str:
    """Return the concatenated, routing-normalized source of the finalize family."""
    return "\n\n".join(_ROUTING_QUALIFIER.sub("", path.read_text(encoding="utf-8")) for path in FINALIZE_MODULE_PATHS)
