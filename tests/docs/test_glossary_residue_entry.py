"""Structural checks for the ``Residue`` glossary disambiguation (#6759).

"Residue" — a ``kitty-specs/`` child that is not a Mission — has three live
senses in code (write-seam, audit-engine, read-side / ``doctor identity``) and
no glossary entry. This suite pins the contract issue #6759 asks for: one
``docs/context/orchestration.md`` entry naming the three senses with
"do NOT use when" guards, linked from the three owning docstrings and flagged
in the AGENTS.md Terminology Canon.

Like ``test_artifact_placement_seam_page.py``'s Routing checks, it asserts
**structure and citations, not prose wording** — pinning sentences would fight
every future edit. The docstring-link assertions read the real docstrings via
``ast`` (the production reading position), and
``test_link_probe_positive_control`` proves the probe can see a link when one
is present, so the absence assertions cannot pass vacuously.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Union

import pytest

pytestmark = [pytest.mark.unit]

REPO_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATION_PATH = REPO_ROOT / "docs" / "context" / "orchestration.md"
AGENTS_PATH = REPO_ROOT / "AGENTS.md"
RESOLVER_PATH = REPO_ROOT / "src" / "specify_cli" / "context" / "mission_resolver.py"
AUDIT_MODELS_PATH = REPO_ROOT / "src" / "specify_cli" / "audit" / "models.py"
#: A known pre-existing glossary link in a ``src/`` docstring: the positive
#: control proving the docstring-link probe observes links when present.
CONTRACT_PATH = REPO_ROOT / "src" / "specify_cli" / "state" / "contract.py"

ENTRY_ANCHOR = "docs/context/orchestration.md#residue"

RESIDUE_SENSES: tuple[str, ...] = (
    "write-seam residue",
    "audit-engine residue",
    "read-side residue",
)

RESIDUE_SENSE_SYMBOLS: tuple[str, ...] = (
    "is_kitty_specs_residue",
    "RESIDUE_DIRECTORY",
    "is_selectable_mission_dir",
)

AstNode = Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module]


def _section_body(text: str, heading: str, *, heading_level: str = "###") -> str:
    """Return the body of the section starting at ``heading`` up to the next same-level heading."""
    pattern = rf"^{re.escape(heading_level)}\s+{re.escape(heading)}\s*$"
    match = re.search(pattern, text, re.MULTILINE)
    assert match, f"heading {heading!r} not found"
    start = match.end()
    next_heading = re.search(rf"^{re.escape(heading_level)}\s+\S", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


def _docstring_of(path: Path, name: str) -> str:
    """The real docstring of the function or class ``name`` in ``path`` (``ast``-parsed)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, AstNode) and getattr(node, "name", None) == name:
            docstring = ast.get_docstring(node)
            assert docstring is not None, f"{name} in {path} has no docstring"
            return docstring
    pytest.fail(f"function or class {name!r} not found in {path}")


def _assignment_preceding_comment(path: Path, target_name: str, *, window_lines: int = 12) -> str:
    """The comment block immediately above the ``target_name =`` assignment in ``path``.

    Sphinx ``#:`` doc-comments (the docstring form used for module constants
    such as ``RESIDUE_DIRECTORY``) are not reachable through ``ast``; this reads
    the source lines above the assignment instead.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(lines):
        if line.startswith(f"{target_name} ="):
            return "\n".join(lines[max(0, idx - window_lines) : idx])
    pytest.fail(f"assignment {target_name!r} not found in {path}")


def test_residue_entry_present_in_orchestration_glossary() -> None:
    """The glossary carries a ``### Residue`` entry naming all three senses with guards."""
    text = ORCHESTRATION_PATH.read_text(encoding="utf-8")
    assert re.search(r"^###\s+Residue\s*$", text, re.MULTILINE), (
        "docs/context/orchestration.md must carry a 'Residue' disambiguation entry (#6759)"
    )
    section = _section_body(text, "Residue")
    for sense in RESIDUE_SENSES:
        assert sense in section, f"Residue entry is missing the sense {sense!r}"
    for symbol in RESIDUE_SENSE_SYMBOLS:
        assert symbol in section, f"Residue entry must name the owning symbol {symbol!r}"
    assert "Do NOT use when" in section, "Residue entry needs a 'Do NOT use when' guard"


def test_write_seam_docstring_links_entry() -> None:
    """``is_kitty_specs_residue``'s docstring links the glossary entry (write-seam sense)."""
    assert ENTRY_ANCHOR in _docstring_of(RESOLVER_PATH, "is_kitty_specs_residue")


def test_read_side_docstring_links_entry() -> None:
    """``is_selectable_mission_dir``'s docstring links the glossary entry (read-side sense)."""
    assert ENTRY_ANCHOR in _docstring_of(RESOLVER_PATH, "is_selectable_mission_dir")


def test_audit_engine_docstring_links_entry() -> None:
    """``RESIDUE_DIRECTORY``'s doc-comment links the glossary entry (audit-engine sense)."""
    assert ENTRY_ANCHOR in _assignment_preceding_comment(AUDIT_MODELS_PATH, "RESIDUE_DIRECTORY")


def test_terminology_canon_links_entry() -> None:
    """AGENTS.md's Terminology Canon flags the residue footgun and links the entry."""
    text = AGENTS_PATH.read_text(encoding="utf-8")
    canon = _section_body(text, "Terminology Canon", heading_level="##")
    assert ENTRY_ANCHOR in canon, (
        "AGENTS.md Terminology Canon must link docs/context/orchestration.md#residue "
        "alongside the primary/merge/routing footgun bullets (#6759)"
    )


def test_link_probe_positive_control() -> None:
    """The docstring-link probe sees a known pre-existing glossary link (non-vacuity control)."""
    docstring = _docstring_of(CONTRACT_PATH, "StateSurface")
    assert "docs/context/orchestration.md#target-owned-bookkeeping" in docstring, (
        "positive control failed: the known target-owned-bookkeeping glossary link "
        "is no longer in StateSurface's docstring in src/specify_cli/state/contract.py; "
        "re-point this control at another live src/ docstring glossary link"
    )
