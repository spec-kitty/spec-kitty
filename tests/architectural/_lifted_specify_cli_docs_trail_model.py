"""Single home of the trail-model doc subsection checks (#5015).

Both ``tests/specify_cli/docs/test_trail_model_doc.py`` (out of matrix) and its always-on lift
``tests/architectural/test_lifted_specify_cli_docs_trail_model.py`` import these tests, so the per-PR gate
runs exactly what the source suite runs and the two cannot drift apart.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRAIL = REPO_ROOT / "docs/architecture/trail-model.md"


def test_trail_model_has_mode_enforcement_subsection() -> None:
    content = TRAIL.read_text()
    assert "### Mode Enforcement at Tier 2 Promotion" in content


def test_trail_model_has_correlation_links_subsection() -> None:
    content = TRAIL.read_text()
    assert "### Correlation Links (Tier 1 extension)" in content


def test_trail_model_has_saas_read_model_policy_section() -> None:
    content = TRAIL.read_text()
    assert "## SaaS Read-Model Policy" in content


def test_trail_model_has_saas_policy_table_header() -> None:
    """The 16-row policy table must be present in operator doc."""
    content = TRAIL.read_text()
    assert "| mode_of_work | event | project | include_request_text | include_evidence_ref |" in content


def test_trail_model_has_tier2_deferral_subsection() -> None:
    content = TRAIL.read_text()
    assert "## Tier 2 SaaS Projection — Deferred" in content


def test_trail_model_has_host_surfaces_subsection() -> None:
    """Pulled forward from WP05/T021."""
    content = TRAIL.read_text()
    assert "## Host surfaces that teach the trail" in content
    assert "host-surface-parity.md" in content


def test_trail_model_mode_prose_updated() -> None:
    """The documentation-only disclaimer must be gone."""
    content = TRAIL.read_text()
    assert "Mode-of-work is a documentation-level taxonomy in 3.2" not in content
    assert "Runtime enforcement is active" in content
