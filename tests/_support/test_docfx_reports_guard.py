"""Planted-config tests for the docs/reports/ docfx-publication guard.

Proves the guard in ``tests/_support/docfx_reports_guard.py`` actually
detects the vacuous-prone shapes the prior per-file implementations missed
(a bare ``"reports" in pattern`` substring test): a catch-all glob, a
``src``-relative entry, and — on the "must not false-positive" side — a
safe ``exclude`` carve-out and the real ``docs/docfx.json`` as it stands
today.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

from tests._support.docfx_reports_guard import (
    PROBE_REPORT_PATH,
    assert_docfx_does_not_publish_reports,
    docfx_publishes_reports,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_DOCFX_CONFIG_PATH = REPO_ROOT / "docs" / "docfx.json"


def _config(*content_entries: dict[str, object]) -> dict[str, object]:
    return {"build": {"content": list(content_entries)}}


# ---------------------------------------------------------------------------
# Must FAIL (i.e. docfx_publishes_reports(...) is True): configs that
# publish docs/reports/ as live docs, including shapes a naive
# substring check on "reports" would miss or mishandle.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "config"),
    [
        ("dot-slash src", _config({"src": "./reports", "files": ["**.md"]})),
        ("parent-relative src", _config({"src": "../docs/reports", "files": ["**.md"]})),
        ("files given as a bare string", _config({"files": "**.md"})),
        ("brace alternation", _config({"files": ["{reports,context}/**.md"]})),
        ("dot-slash files pattern", _config({"files": ["./reports/**.md"]})),
        ("raw resource section", {"build": {"resource": [{"files": ["reports/**"]}]}}),
        (
            "sub-tree exclude that spares sibling reports",
            _config({"files": ["**.md"], "exclude": ["reports/tracer-friction-recon/**"]}),
        ),
    ],
)
def test_fails_for_shapes_a_literal_matcher_misses(label: str, config: dict[str, object]) -> None:
    """#5258 pre-PR squad: each of these publishes docs/reports/ as live docs."""
    assert docfx_publishes_reports(config) is True, label


def test_fails_for_explicit_reports_glob() -> None:
    """An explicit reports/**.md glob obviously publishes docs/reports/."""
    config = _config({"files": ["reports/**.md"]})
    assert docfx_publishes_reports(config) is True


def test_fails_for_catch_all_glob() -> None:
    """A catch-all **.md glob publishes docs/reports/ too -- it has no
    "reports" substring at all, which is exactly what the old vacuous-prone
    ``"reports" in pattern`` check missed.
    """
    config = _config({"files": ["**.md"]})
    assert docfx_publishes_reports(config) is True


def test_fails_for_src_relative_reports_entry() -> None:
    """A ``"src": "reports"`` entry publishes everything under reports/ via
    its own files globs, without the literal substring "reports" needing to
    appear in any glob pattern -- another shape the old check missed.
    """
    config = _config({"src": "reports", "files": ["**.md"]})
    assert docfx_publishes_reports(config) is True


def test_fails_when_one_of_several_entries_publishes_it() -> None:
    """Only one entry among several needs to publish the probe path."""
    config = _config(
        {"files": ["index.md", "toc.yml"]},
        {"files": ["reports/**.md"]},
    )
    assert docfx_publishes_reports(config) is True


# ---------------------------------------------------------------------------
# Must PASS (i.e. docfx_publishes_reports(...) is False): configs that do
# NOT publish docs/reports/, including the shape the old guard wrongly
# flagged as a false positive.
# ---------------------------------------------------------------------------


def test_passes_for_the_real_docfx_config() -> None:
    """The real docs/docfx.json, as it stands today, never publishes reports/."""
    config = json.loads(REAL_DOCFX_CONFIG_PATH.read_text(encoding="utf-8"))
    assert docfx_publishes_reports(config) is False


def test_passes_for_catch_all_glob_with_reports_excluded() -> None:
    """A catch-all glob with an explicit exclude for reports/** is safe.

    The old ``"reports" in pattern`` substring check scanned BOTH files and
    exclude patterns without distinguishing them, so it wrongly failed on
    this exact shape: the literal substring "reports" appears in the
    (safe) exclude list, not in a publishing files glob.
    """
    config = _config({"files": ["**.md"], "exclude": ["reports/**"]})
    assert docfx_publishes_reports(config) is False


def test_passes_when_probe_is_not_under_entrys_src() -> None:
    """An entry scoped to an unrelated src never reaches docs/reports/."""
    config = _config({"src": "api", "files": ["**.md"]})
    assert docfx_publishes_reports(config) is False


def test_passes_for_no_content_entries() -> None:
    assert docfx_publishes_reports({"build": {"content": []}}) is False


# ---------------------------------------------------------------------------
# The shared assertion wrapper both guard tests call.
# ---------------------------------------------------------------------------


def test_assert_wrapper_passes_for_the_real_config() -> None:
    assert_docfx_does_not_publish_reports(REAL_DOCFX_CONFIG_PATH)


def test_assert_wrapper_raises_for_a_publishing_config(tmp_path: Path) -> None:
    docfx_path = tmp_path / "docfx.json"
    docfx_path.write_text(
        json.dumps({"build": {"content": [{"files": ["reports/**.md"]}]}}),
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="docs/reports/"):
        assert_docfx_does_not_publish_reports(docfx_path)


def test_probe_report_path_matches_a_real_report_snapshot() -> None:
    """PROBE_REPORT_PATH names a file that really exists under docs/reports/,
    so this guard's probe reflects an actual dated snapshot rather than a
    made-up path that could drift out of sync with reality.
    """
    assert (REPO_ROOT / "docs" / PROBE_REPORT_PATH).exists()
