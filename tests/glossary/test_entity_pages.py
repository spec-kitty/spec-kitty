"""Tests for GlossaryEntityPageRenderer (entity_pages.py).

The test suite uses a lightweight duck-type stub for the DRG because
``glossary:*`` URN nodes are a WP5.1 addition that may not yet exist in
the real ``doctrine`` package (the DRGNode validator enforces that the URN
prefix matches the ``NodeKind`` value exactly, and ``GLOSSARY_SCOPE`` maps
to ``glossary_scope:`` not ``glossary:``).  All 12 test scenarios pass
without the real DRG on this branch.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from glossary.entity_pages import (
    BacklinkEntry,
    GlossaryEntityPageRenderer,
    TermNotFoundError,
)
from tests._perf_helpers import assert_timing_budget

# ---------------------------------------------------------------------------
# Helpers: build fixture DRGs that work with or without the real package
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]

def _make_drg_fixture(
    *,
    term_urns: list[str],
    term_labels: list[str | None] | None = None,
    term_definitions: list[str] | None = None,
    backlinks: list[tuple[str, str]] | None = None,
    extra_nodes: list[Any] | None = None,
) -> Any:
    """Build a duck-type DRG stub with the given glossary terms.

    We always use the duck-type stub here because the real ``doctrine``
    DRG package enforces that the URN prefix must match the ``NodeKind``
    value exactly.  Since ``glossary:*`` URNs are a future addition (WP5.1),
    the real package cannot yet represent them; the stub lets us test the
    renderer logic without that constraint.

    ``backlinks`` is a list of ``(source_urn, target_glossary_urn)`` pairs.
    """
    n = len(term_urns)
    if term_labels is None:
        term_labels = [None] * n
    if term_definitions is None:
        term_definitions = [f"Definition of {u}" for u in term_urns]

    term_labels = list(term_labels) + [None] * (n - len(term_labels))
    term_definitions = list(term_definitions) + [
        f"Definition of {u}" for u in term_urns[len(term_definitions) :]
    ]

    node_map: dict[str, Any] = {}
    for urn, lbl, defn in zip(term_urns, term_labels, term_definitions, strict=False):
        node_map[urn] = SimpleNamespace(urn=urn, kind="glossary_scope", label=lbl, definition=defn)

    nodes = list(node_map.values())
    if extra_nodes:
        nodes.extend(extra_nodes)
        for en in extra_nodes:
            node_map[getattr(en, "urn", "")] = en

    edges: list[Any] = []
    if backlinks:
        for src, tgt in backlinks:
            edges.append(SimpleNamespace(source=src, target=tgt, relation="vocabulary"))

    def get_node(urn: str) -> Any:
        return node_map.get(urn)

    return SimpleNamespace(nodes=nodes, edges=edges, get_node=get_node)


def _make_source_node(urn: str, label: str | None = None) -> Any:
    """Build a non-glossary source node for backlinks."""
    return SimpleNamespace(urn=urn, kind="action", label=label)


# ---------------------------------------------------------------------------
# A renderer subclass that accepts an in-memory DRG to avoid filesystem I/O
# ---------------------------------------------------------------------------


class _FixtureRenderer(GlossaryEntityPageRenderer):
    """Renderer that uses a pre-built DRG instead of loading from disk."""

    def __init__(self, repo_root: Path, drg: Any) -> None:
        super().__init__(repo_root)
        self._fixture_drg = drg

    def generate_all(self) -> list[Path]:
        records = self._extract_term_records(self._fixture_drg)
        written: list[Path] = []
        for rec in records:
            content = self._render_page(rec)
            path = self._write_page(rec.urn, content)
            written.append(path)
        return written

    def generate_one(self, term_id: str) -> Path:
        records = self._extract_term_records(self._fixture_drg)
        matching = [r for r in records if r.urn == term_id]
        if not matching:
            raise TermNotFoundError(f"Term not found in DRG: {term_id}")
        rec = matching[0]
        content = self._render_page(rec)
        return self._write_page(rec.urn, content)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def three_term_drg():
    return _make_drg_fixture(
        term_urns=[
            "glossary:workspace",
            "glossary:work-package",
            "glossary:deployment-target",
        ],
        term_labels=["Workspace", "Work Package", "Deployment Target"],
        term_definitions=[
            "A git worktree used during implementation.",
            "A discrete unit of implementation work.",
            "The environment where code is deployed.",
        ],
        backlinks=[
            ("action:implement", "glossary:workspace"),
            ("action:review", "glossary:workspace"),
            ("action:implement", "glossary:work-package"),
        ],
        extra_nodes=[
            _make_source_node("action:implement", "Implement Action"),
            _make_source_node("action:review", "Review Action"),
        ],
    )


# ---------------------------------------------------------------------------
# Test 1 – generate_all() produces one file per glossary term
# ---------------------------------------------------------------------------


def test_generate_all_three_terms(repo_root, three_term_drg):
    renderer = _FixtureRenderer(repo_root, three_term_drg)
    written = renderer.generate_all()
    assert len(written) == 3
    for p in written:
        assert p.exists(), f"Expected file to exist: {p}"
        assert p.suffix == ".md"


# ---------------------------------------------------------------------------
# Test 2 – page content has term name, definition, and References section
# ---------------------------------------------------------------------------


def test_page_content_has_name_definition_references(repo_root, three_term_drg):
    renderer = _FixtureRenderer(repo_root, three_term_drg)
    renderer.generate_all()

    # workspace term has 2 backlinks so it should have a References section
    page_slug = "glossary-workspace"
    page_path = repo_root / ".kittify" / "charter" / "compiled" / "glossary" / f"{page_slug}.md"
    assert page_path.exists()
    content = page_path.read_text(encoding="utf-8")

    assert "Workspace" in content  # term label
    assert "A git worktree" in content  # definition
    assert "## References" in content
    assert "Implement Action" in content or "action:implement" in content


# ---------------------------------------------------------------------------
# Test 3 – idempotency: generate_all() twice doesn't error; file count unchanged
# ---------------------------------------------------------------------------


def test_generate_all_idempotent(repo_root, three_term_drg):
    renderer = _FixtureRenderer(repo_root, three_term_drg)
    first = renderer.generate_all()
    second = renderer.generate_all()

    assert len(first) == len(second) == 3
    output_dir = repo_root / ".kittify" / "charter" / "compiled" / "glossary"
    md_files = list(output_dir.glob("*.md"))
    assert len(md_files) == 3


# ---------------------------------------------------------------------------
# Test 4 – generate_one() on a known term writes a file containing term name
# ---------------------------------------------------------------------------


def test_generate_one_known_term(repo_root, three_term_drg):
    renderer = _FixtureRenderer(repo_root, three_term_drg)
    path = renderer.generate_one("glossary:deployment-target")
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "Deployment Target" in content or "deployment-target" in content


# ---------------------------------------------------------------------------
# Test 5 – generate_one() on missing term raises TermNotFoundError
# ---------------------------------------------------------------------------


def test_generate_one_missing_term_raises(repo_root, three_term_drg):
    renderer = _FixtureRenderer(repo_root, three_term_drg)
    with pytest.raises(TermNotFoundError):
        renderer.generate_one("glossary:nonexistent-term")


# ---------------------------------------------------------------------------
# Test 6 – missing DRG: generate_all() returns [] without raising
# ---------------------------------------------------------------------------


def test_generate_all_missing_drg_returns_empty(repo_root):
    # No .kittify/doctrine/ directory exists — DRG is unavailable
    renderer = GlossaryEntityPageRenderer(repo_root)
    result = renderer.generate_all()
    assert result == []


# ---------------------------------------------------------------------------
# Test 7 – no .md.tmp files left behind after successful generation
# ---------------------------------------------------------------------------


def test_no_tmp_files_left_behind(repo_root, three_term_drg):
    renderer = _FixtureRenderer(repo_root, three_term_drg)
    renderer.generate_all()

    output_dir = repo_root / ".kittify" / "charter" / "compiled" / "glossary"
    tmp_files = list(output_dir.glob("*.tmp"))
    assert tmp_files == [], f"Found leftover .tmp files: {tmp_files}"


# ---------------------------------------------------------------------------
# Test 8 – performance: 500 terms complete in <10 seconds
# ---------------------------------------------------------------------------


def test_generate_all_writes_a_page_per_term_for_500_terms(repo_root):
    """Functional companion to test_generate_all_500_terms_under_10_seconds
    (split, #4015): generate_all() writes exactly one page per term. Timing
    budget lives in the @performance sibling below."""
    urns = [f"glossary:term-{i:04d}" for i in range(500)]
    drg = _make_drg_fixture(term_urns=urns)
    renderer = _FixtureRenderer(repo_root, drg)

    written = renderer.generate_all()

    assert len(written) == 500


@pytest.mark.performance
def test_generate_all_500_terms_under_10_seconds(repo_root):
    """NFR timing budget only (split, #4015): generate_all() completes in
    under 10 seconds for 500 terms. Functional coverage moved to
    test_generate_all_writes_a_page_per_term_for_500_terms, above."""
    urns = [f"glossary:term-{i:04d}" for i in range(500)]
    drg = _make_drg_fixture(term_urns=urns)
    renderer = _FixtureRenderer(repo_root, drg)

    start = time.monotonic()
    renderer.generate_all()
    elapsed = time.monotonic() - start

    assert_timing_budget(elapsed, 10.0, name="generate_all_500_terms")


# ---------------------------------------------------------------------------
# Test 9 – BacklinkEntry dataclass basic sanity
# ---------------------------------------------------------------------------


def test_backlink_entry_fields():
    entry = BacklinkEntry(
        source_id="action:implement",
        source_type="mission_step",
        label="Implement Action",
        artifact_path="kitty-specs/actions/implement.md",
    )
    assert entry.source_id == "action:implement"
    assert entry.source_type == "mission_step"
    assert entry.artifact_path is not None


# ---------------------------------------------------------------------------
# Test 10 – conflict history section rendered when events exist
# ---------------------------------------------------------------------------


def test_conflict_history_rendered_from_events(repo_root, three_term_drg):
    events_dir = repo_root / ".kittify" / "events" / "glossary"
    events_dir.mkdir(parents=True, exist_ok=True)
    log_path = events_dir / "glossary.events.jsonl"
    event = {
        "event_type": "SemanticCheckEvaluated",
        "step_id": "step-1",
        "timestamp": "2026-01-15T10:00:00Z",
        "findings": [
            {
                "term": {"surface_text": "workspace"},
                "term_id": "glossary:workspace",
                "severity": "high",
                "conflict_type": "ambiguous",
                "resolution": "unresolved",
            }
        ],
    }
    log_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

    renderer = _FixtureRenderer(repo_root, three_term_drg)
    path = renderer.generate_one("glossary:workspace")
    content = path.read_text(encoding="utf-8")

    assert "## Conflict History" in content
    assert "ambiguous" in content


# ---------------------------------------------------------------------------
# Test 11 – missing events dir doesn't raise
# ---------------------------------------------------------------------------


def test_conflict_history_missing_dir_no_raise(repo_root, three_term_drg):
    renderer = _FixtureRenderer(repo_root, three_term_drg)
    # No events dir — should complete normally
    written = renderer.generate_all()
    assert len(written) == 3


# ---------------------------------------------------------------------------
# Test 12 – output slug uses hyphen for colon in URN
# ---------------------------------------------------------------------------


def test_output_slug_replaces_colon_with_hyphen(repo_root, three_term_drg):
    renderer = _FixtureRenderer(repo_root, three_term_drg)
    written = renderer.generate_all()
    output_dir = repo_root / ".kittify" / "charter" / "compiled" / "glossary"
    for p in written:
        assert ":" not in p.name, f"Colon found in filename: {p.name}"
        assert p.parent == output_dir
