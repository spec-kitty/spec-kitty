"""Tests for :func:`scripts.docs.check_docs_freshness._check_docs_index_drift`.

WP02 (FR-005): the docs-index freshness gate. Fixtures are built locally in
this file (no shared conftest, per the WP02 task) so each test owns its own
docs tree / committed index without cross-test coupling.

Also carries a C-001 regression pin: WP02 only *appends* to
``check_docs_freshness.py`` alongside ``_check_inventory_lockfile_drift`` —
this file asserts that checker's findings for a known-drifted inventory
fixture are unchanged by WP02's edit.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts.docs import check_docs_freshness as orchestrator
from scripts.docs.docs_index import generate_index, render_index

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.fixture(autouse=True)
def _pin_no_upgrade_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the upgrade-check opt-out set for every test (was a module-level ``setdefault``)."""
    monkeypatch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", os.environ.get("SPEC_KITTY_NO_UPGRADE_CHECK", "1"))


# ---------------------------------------------------------------------------
# Local fixture builders (T010: no shared conftest)
# ---------------------------------------------------------------------------


def _write_page(path: Path, *, title: str, description: str, heading: str) -> None:
    """Write a minimal docs page with frontmatter + one ``##`` heading."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntitle: {title}\ndescription: {description}\n---\n\n## {heading}\n\nSome body text.\n",
        encoding="utf-8",
    )


def _write_fresh_index(docs_root: Path, index_path: Path) -> None:
    """Regenerate ``index_path`` from ``docs_root`` (mirrors ``--write``)."""
    entries = generate_index(docs_root, repo_root=docs_root.parent)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(render_index(entries), encoding="utf-8")


def _stage_one_page(tmp_path: Path) -> tuple[Path, Path]:
    """Stage a docs root with one page + a matching, freshly-generated index."""
    docs_root = tmp_path / "docs"
    _write_page(
        docs_root / "guide.md",
        title="Guide",
        description="A guide.",
        heading="Intro",
    )
    index_path = docs_root / "development" / "3-2-docs-retrieval-index.yaml"
    _write_fresh_index(docs_root, index_path)
    return docs_root, index_path


# ---------------------------------------------------------------------------
# (a) fresh index -> checker passes
# ---------------------------------------------------------------------------


def test_fresh_index_passes(tmp_path: Path) -> None:
    docs_root, index_path = _stage_one_page(tmp_path)

    findings = orchestrator._check_docs_index_drift(index_path, docs_root)

    assert findings == []


# ---------------------------------------------------------------------------
# (b) stale page (heading/description changed, index not regenerated)
# ---------------------------------------------------------------------------


def test_stale_page_emits_error_severity_docs_index_drift(tmp_path: Path) -> None:
    docs_root, index_path = _stage_one_page(tmp_path)

    # Mutate the page's description + heading without regenerating the index.
    _write_page(
        docs_root / "guide.md",
        title="Guide",
        description="A completely rewritten description.",
        heading="Overview",
    )

    findings = orchestrator._check_docs_index_drift(index_path, docs_root)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "DOCS-INDEX-DRIFT"
    assert finding.severity == "error"  # assert severity, not merely non-zero exit
    assert "guide.md" in finding.location
    assert "PYTHONPATH=. uv run python scripts/docs/docs_index.py --write" in (finding.suggested_action)


def test_stale_page_reds_the_aggregate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``check_docs_freshness --ci`` exits non-zero when the new ruler errors."""
    docs_root, index_path = _stage_one_page(tmp_path)
    _write_page(
        docs_root / "guide.md",
        title="Guide",
        description="A completely rewritten description.",
        heading="Overview",
    )
    inventory_path = tmp_path / "inventory.yaml"
    inventory_path.write_text("[]\n", encoding="utf-8")
    ref_path = tmp_path / "ref.md"
    ref_path.write_text("# ref\n", encoding="utf-8")
    agent_ref_path = tmp_path / "agent.md"
    agent_ref_path.write_text("# agent ref\n", encoding="utf-8")

    _isolate_unrelated_subchecks(monkeypatch)
    monkeypatch.setattr(orchestrator, "_SAAS_SYNC_PRESET", True)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")

    report_path = tmp_path / "report.json"
    rc = orchestrator.main(
        [
            "--inventory",
            str(inventory_path),
            "--docs-root",
            str(docs_root),
            "--reference",
            str(ref_path),
            "--agent-reference",
            str(agent_ref_path),
            "--docs-index",
            str(index_path),
            "--link-check",
            "none",
            "--report",
            str(report_path),
            "--ci",
        ]
    )

    assert rc == 1
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["exit_code"] == 1
    drift_findings = [f for f in payload["findings"] if f["rule_id"] == "DOCS-INDEX-DRIFT"]
    assert len(drift_findings) == 1
    assert drift_findings[0]["severity"] == "error"


# ---------------------------------------------------------------------------
# (c) regenerate -> green again
# ---------------------------------------------------------------------------


def test_regenerated_index_is_green_again(tmp_path: Path) -> None:
    docs_root, index_path = _stage_one_page(tmp_path)
    _write_page(
        docs_root / "guide.md",
        title="Guide",
        description="A completely rewritten description.",
        heading="Overview",
    )
    assert orchestrator._check_docs_index_drift(index_path, docs_root) != []

    _write_fresh_index(docs_root, index_path)

    assert orchestrator._check_docs_index_drift(index_path, docs_root) == []


# ---------------------------------------------------------------------------
# Missing-prerequisite skip behavior
# ---------------------------------------------------------------------------


def test_missing_committed_index_skips(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    _write_page(docs_root / "guide.md", title="Guide", description="A guide.", heading="Intro")
    absent_index = docs_root / "development" / "3-2-docs-retrieval-index.yaml"

    findings = orchestrator._check_docs_index_drift(absent_index, docs_root)

    assert findings == []


def test_missing_docs_root_skips(tmp_path: Path) -> None:
    findings = orchestrator._check_docs_index_drift(tmp_path / "index.yaml", tmp_path / "absent-docs")
    assert findings == []


# ---------------------------------------------------------------------------
# C-001 snapshot: the inventory-lockfile-drift ruler is untouched by WP02
# ---------------------------------------------------------------------------


def test_inventory_lockfile_drift_findings_unchanged_by_wp02(tmp_path: Path) -> None:
    """Pin ``_check_inventory_lockfile_drift`` output on a known-drifted fixture.

    WP02 only appends a new sub-check next to this one (C-001); it must never
    perturb the inventory ruler itself. This snapshot exercises the *shared*
    aggregate module end-to-end (not a WP01/WP02 fixture) so a future
    accidental edit to the inventory ruler reds here.
    """
    docs_root = tmp_path / "inv_docs"
    (docs_root).mkdir(parents=True)
    (docs_root / "other.md").write_text(
        "---\nversion_tag: current\ntype: how-to\nowning_workstream: Q\n---\n\n# Other\n\nBody.\n",
        encoding="utf-8",
    )
    inventory_path = tmp_path / "inventory.yaml"
    inventory_path.write_text(
        "- path: inv_docs/missing.md\n  tag: current\n  divio_type: how-to\n  owning_workstream: Q\n  current_target: true\n  citation_refs: []\n  notes: null\n",
        encoding="utf-8",
    )

    findings = orchestrator._check_inventory_lockfile_drift(inventory_path, docs_root)

    assert [(f.rule_id, f.severity, f.location, f.message) for f in findings] == [
        (
            "INVENTORY-LOCKFILE-DRIFT",
            "error",
            "inv_docs/other.md",
            "present in frontmatter, absent from inventory",
        ),
        (
            "INVENTORY-LOCKFILE-DRIFT",
            "error",
            "inv_docs/missing.md",
            "present in inventory, absent from frontmatter walk",
        ),
    ]


# ---------------------------------------------------------------------------
# Test-local isolation helper (mirrors test_check_docs_freshness.py's
# ``_stub_subchecks_clean`` shape, duplicated locally per T010's "no shared
# conftest" instruction).
# ---------------------------------------------------------------------------


def _isolate_unrelated_subchecks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub every sub-check except the docs-index ruler under test."""

    def _fake_leakage(argv: list[str]) -> int:
        report_path = Path(argv[argv.index("--report") + 1])
        report_path.write_text(
            json.dumps({"inventory_rows_count": 0, "findings": [], "exit_code": 0}),
            encoding="utf-8",
        )
        return 0

    def _fake_ref(argv: list[str]) -> int:
        report_path = Path(argv[argv.index("--report") + 1])
        report_path.write_text(json.dumps({"findings": []}), encoding="utf-8")
        return 0

    monkeypatch.setattr(orchestrator, "_invoke_version_leakage", _fake_leakage)
    monkeypatch.setattr(orchestrator, "_invoke_cli_reference_freshness", _fake_ref)
    monkeypatch.setattr(orchestrator, "_check_inventory_lockfile_drift", lambda *_a, **_k: [])
