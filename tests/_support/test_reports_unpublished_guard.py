"""Self-tests for the docs/reports/ publication guard (``tests/_support/reports_unpublished_guard.py``).

The guard reads the docsite contract, so its teeth are proven by changing the
contract: drop ``reports`` from the excluded folders and the guard must fail on
the live tree and on a planted one (#6943).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docs import _dockitty_contract as contract
from tests._support.reports_unpublished_guard import (
    assert_reports_unpublished,
    reports_published_routes,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"


def _without_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    kept = tuple(folder for folder in contract.EXCLUDED_FOLDERS if folder != "reports")
    monkeypatch.setattr(contract, "EXCLUDED_FOLDERS", kept)


def _planted(tmp_path: Path) -> Path:
    report = tmp_path / "reports" / "recon" / "2026-09-26" / "matrix.md"
    report.parent.mkdir(parents=True)
    report.write_text("---\ntitle: Matrix\ndoc_status: active\n---\n\n# Matrix\n", encoding="utf-8")
    return tmp_path


def test_the_live_tree_does_not_publish_reports() -> None:
    assert len(list((DOCS_ROOT / "reports").rglob("*.md"))) >= 5  # non-vacuous: the guard sees real reports
    assert_reports_unpublished(DOCS_ROOT)


def test_a_contract_that_stops_excluding_reports_fails_the_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    _without_reports(monkeypatch)

    with pytest.raises(AssertionError, match="no longer excludes docs/reports/"):
        assert_reports_unpublished(DOCS_ROOT)


def test_an_active_report_page_is_published_once_the_folder_is_not_excluded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    docs = _planted(tmp_path)
    assert reports_published_routes(docs) == []  # positive control: excluded folder, nothing published

    _without_reports(monkeypatch)

    assert reports_published_routes(docs) == ["/reports/recon/2026-09-26/matrix/"]
