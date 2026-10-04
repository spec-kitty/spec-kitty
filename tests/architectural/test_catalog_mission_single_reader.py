"""Architectural pin: ``catalog.mission`` has exactly one reader (#4908 / #4993).

Moved verbatim from
``tests/specify_cli/cli/commands/charter/test_recompile_preserves_mission_4908.py``
(#5619 SPLIT-BY-KIND): a source-tree grep is an architectural invariant, not
a charter CLI regression. Only the repository-root derivation changed to
match this file's location.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural


def test_catalog_mission_is_read_only_through_the_shared_accessor() -> None:
    """AC-B3 / NFR-003 / SC-002 grep proof: no second ``catalog.mission``
    parser survives outside ``charter_yaml_io.read_catalog_field`` /
    ``read_catalog_mission``. Issue #4993 claimed three readers; the true
    count was two (the claimed third read ``catalog.languages``) -- both
    now delegate, so a direct ``catalog["mission"]`` / ``catalog.get(
    "mission")`` read anywhere in ``src/``, the accessor module included, is
    a regression."""
    repo_root = Path(__file__).resolve().parents[2]
    accessor_path = repo_root / "src" / "charter" / "activation" / "charter_yaml_io.py"
    pattern = re.compile(r"""catalog(\.get\(|\[)["']mission["']""")

    # Non-vacuity: the pattern must match the direct-read forms it exists to
    # catch, and the scan root must reach the accessor module.
    assert pattern.search('catalog.get("mission")')
    assert pattern.search("catalog['mission']")
    assert accessor_path.is_file()

    # The accessor reads through ``read_catalog_field(repo_root, "mission")``,
    # which the pattern does not match, so it needs no exclusion.
    hits: list[str] = []
    for path in (repo_root / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            hits.append(str(path.relative_to(repo_root)))

    assert hits == [], f"catalog.mission must be read only through charter.activation.charter_yaml_io.read_catalog_mission -- found direct reads in: {hits}"
