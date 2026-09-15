"""Tests pinning the project-layer-override behavior (P2, Robert review 2026-05).

Design decision (confirmed by user): project > org > shipped is the intended
precedence.  The project layer MAY override shipped and org nodes.  When it
does, ``merge_three_layers`` emits a ``logging.WARNING`` naming the URN and
the original provenance so the override is operator-visible.

These tests invert Robert's suggestion #6 (which expected a hard-fail) to
match the accepted behavior: override succeeds, warning is emitted.
"""

from __future__ import annotations

import logging

import pytest

from charter.drg import (
    DRGGraph,
    DRGNode,
    NodeKind,
    OrgDRGFragment,
)
from charter.activation.drg_activation import merge_three_layers

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _built_in_with_node(urn: str) -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-05-19T00:00:00Z",
        generated_by="test",
        nodes=[DRGNode(urn=urn, kind=NodeKind.DIRECTIVE)],
        edges=[],
    )


def _empty_built_in() -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-05-19T00:00:00Z",
        generated_by="test",
        nodes=[],
        edges=[],
    )


def _project_with_node(urn: str) -> DRGGraph:
    """Build a project-layer graph with a node at *urn*.

    The URN prefix determines the kind (``directive:`` → DIRECTIVE, etc.).
    We use DIRECTIVE kind (matching the ``directive:`` prefix) so Pydantic
    validation passes.  What matters is that the *provenance* differs, not
    the kind.
    """
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-05-19T00:00:00Z",
        generated_by="test",
        nodes=[DRGNode(urn=urn, kind=NodeKind.DIRECTIVE)],
        edges=[],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProjectNodeOverridesShippedAndEmitsWarning:
    """Project node overrides a shipped node (built-in → project)."""

    def test_project_node_overrides_shipped_node(self, caplog: pytest.LogCaptureFixture) -> None:
        """Project wins; merged graph carries the project node."""
        urn = "directive:shared-policy"
        built_in = _built_in_with_node(urn)
        project = _project_with_node(urn)

        with caplog.at_level(logging.WARNING, logger="charter.drg"):
            merged = merge_three_layers(
                built_in=built_in, org_fragments=[], project=project
            )

        # Project node must be in the merged graph.
        matching = [n for n in merged.nodes if n.urn == urn]
        assert len(matching) == 1, "override URN must appear exactly once"
        winning_node = matching[0]
        # Both nodes have kind=DIRECTIVE (URN prefix enforces this).
        # What matters is that provenance == "project" (project node won).
        assert winning_node.kind == NodeKind.DIRECTIVE
        assert getattr(winning_node, "provenance", None) == "project"

    def test_project_overrides_shipped_emits_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A WARNING must name the URN when project overrides shipped."""
        urn = "directive:shared-policy"
        built_in = _built_in_with_node(urn)
        project = _project_with_node(urn)

        with caplog.at_level(logging.WARNING, logger="charter.drg"):
            merge_three_layers(built_in=built_in, org_fragments=[], project=project)

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warning_records, "at least one WARNING must be emitted on built_in override"
        combined = " ".join(r.getMessage() for r in warning_records)
        assert urn in combined, f"WARNING must mention the URN {urn!r}; got: {combined!r}"


class TestProjectNodeOverridesOrgAndEmitsWarning:
    """Project node overrides an org-tier node (org:... → project)."""

    def test_project_node_overrides_org_node(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        urn = "directive:org-policy"
        fragment = OrgDRGFragment.model_validate(
            {
                "pack_name": "acme",
                "source_kind": "local_path",
                "source_ref": "/nonexistent/acme",
                "layer_index": 1,
                "provenance_marker": "org",
                "nodes": [{"id": "org-policy", "kind": "directives", "title": "Org Policy"}],
                "edges": [],
            }
        )
        project = _project_with_node(urn)

        with caplog.at_level(logging.WARNING, logger="charter.drg"):
            merged = merge_three_layers(
                built_in=_empty_built_in(), org_fragments=[fragment], project=project
            )

        matching = [n for n in merged.nodes if n.urn == urn]
        assert len(matching) == 1
        assert getattr(matching[0], "provenance", None) == "project"

    def test_project_overrides_org_emits_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        urn = "directive:org-policy"
        fragment = OrgDRGFragment.model_validate(
            {
                "pack_name": "acme",
                "source_kind": "local_path",
                "source_ref": "/nonexistent/acme",
                "layer_index": 1,
                "provenance_marker": "org",
                "nodes": [{"id": "org-policy", "kind": "directives", "title": "Org Policy"}],
                "edges": [],
            }
        )
        project = _project_with_node(urn)

        with caplog.at_level(logging.WARNING, logger="charter.drg"):
            merge_three_layers(
                built_in=_empty_built_in(), org_fragments=[fragment], project=project
            )

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warning_records, "WARNING must be emitted on org-tier override"
        combined = " ".join(r.getMessage() for r in warning_records)
        assert urn in combined, f"WARNING must mention the URN {urn!r}; got: {combined!r}"


class TestNoWarningWhenProjectIntroducesNewUrn:
    """Project adds a brand-new URN not in shipped or org — no warning expected."""

    def test_no_warning_for_new_project_urn(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        built_in = _built_in_with_node("directive:existing")
        project = _project_with_node("directive:brand-new")  # not in built_in or org

        with caplog.at_level(logging.WARNING, logger="charter.drg"):
            merged = merge_three_layers(
                built_in=built_in, org_fragments=[], project=project
            )

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        # No override happened, so no warning.
        assert not warning_records, (
            f"No WARNING expected when project introduces a new URN; "
            f"got: {[r.getMessage() for r in warning_records]}"
        )
        # Both nodes must be present.
        urns = {n.urn for n in merged.nodes}
        assert "directive:existing" in urns
        assert "directive:brand-new" in urns
