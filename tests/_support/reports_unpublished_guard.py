"""Shared guard: is ``docs/reports/`` ever published as live docs by the docsite?

The terminology guard's ``docs/reports/`` exemption (see
``docs/development/reference/terminology-exemptions.md``, Exempt Surface 5)
is only safe while the docsite never turns those dated point-in-time snapshots
into published, live documentation. Three guard tests assert this:

- ``tests/contract/test_terminology_guards.py::
  test_docs_reports_exemption_is_not_published_as_live_docs``
- ``tests/specify_cli/cli/test_decision_command_shape_consistency.py::
  test_docs_reports_exemption_is_not_published_as_live_docs``
- ``tests/audit/test_no_legacy_agent_profiles_path.py::
  test_docs_reports_exemption_is_not_published_as_live_docs``

All of them call :func:`assert_reports_unpublished`, so there is one check.

The answer comes from the docsite's own publication authority,
``scripts/docs/_dockitty_contract.py`` (ADR 2026-10-31-1 D-8): ``reports`` must
be one of the folders the site excludes (``EXCLUDED_FOLDERS``, which the site's
``exclude`` option carries), and every page under ``docs/reports/`` must be in
``unpublished_routes``. Both are checked, so a contract that stops excluding the
folder fails here even while each report page happens to be a draft (#6943).
"""

from __future__ import annotations

from pathlib import Path

from scripts.docs import _dockitty_contract as contract

#: The folder under ``docs/`` the exemption covers.
REPORTS_FOLDER = "reports"


def reports_published_routes(docs_root: Path) -> list[str]:
    """Routes of ``docs/reports/`` pages the contract would publish (empty when the exemption is safe)."""
    reports = docs_root / REPORTS_FOLDER
    unpublished = contract.unpublished_routes(docs_root)
    routes = (contract.route_of(page.relative_to(docs_root).as_posix()) for page in sorted(reports.rglob("*.md")))
    return [route for route in routes if route not in unpublished]


def assert_reports_unpublished(docs_root: Path) -> None:
    """Fail loudly if the docsite contract publishes ``docs/reports/``.

    Shared assertion body for the guard tests listed in the module docstring,
    so they stay identical by construction instead of by discipline.
    """
    assert REPORTS_FOLDER in contract.EXCLUDED_FOLDERS, (
        "scripts/docs/_dockitty_contract.py no longer excludes docs/reports/ from the docsite "
        f"(EXCLUDED_FOLDERS = {contract.EXCLUDED_FOLDERS!r}). The docs/reports/ exemption in "
        "tests/contract/test_terminology_guards.py, "
        "tests/specify_cli/cli/test_decision_command_shape_consistency.py and "
        "tests/audit/test_no_legacy_agent_profiles_path.py assumes reports/ snapshots are never "
        "published as live docs -- if that changed on purpose, the exemption must be removed or "
        "narrowed, not left in place."
    )
    published = reports_published_routes(docs_root)
    assert published == [], f"docs/reports/ pages the docsite would publish: {published[:10]}"
