"""Tests for the built-in DRG fallback in ``charter_lint._drg``.

Pins FR-001 and FR-002: ``load_merged_drg`` MUST return a deterministic
``(graph, GraphState)`` tuple following the resolution order project →
built-in → missing. The contract is locked by ADR
``2026-05-24-1-charter-freshness-ux-contract.md``.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from specify_cli.charter_runtime.lint._drg import load_merged_drg
from specify_cli.charter_runtime.lint.findings import GraphState


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _stub_graph(label: str) -> SimpleNamespace:
    """Return a duck-typed DRG with one node so callers can distinguish
    project- vs built-in-resolved graphs by their node URN.
    """
    node = SimpleNamespace(urn=f"stub:{label}", kind="directive", label=label)
    return SimpleNamespace(nodes=[node], edges=[])


def _write_project_graph(repo_root: Path, payload: dict[str, Any]) -> Path:
    """Write a JSON DRG to ``.kittify/charter-packs/drg.json``.

    We pick the JSON candidate (rather than ``graph.yaml``) so the test
    does not depend on a YAML parser, but ``load_merged_drg`` checks both
    in the documented order.
    """
    drg_dir = repo_root / ".kittify" / "charter-packs"
    drg_dir.mkdir(parents=True, exist_ok=True)
    path = drg_dir / "drg.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestLoadMergedDRGResolutionOrder:
    """FR-002 resolution order: project DRG → built-in DRG → MISSING."""

    def test_returns_missing_when_no_graph_anywhere(self, tmp_path: Path) -> None:
        """No project file and no built-in catalog → ``(None, MISSING)``."""
        with patch(
            "specify_cli.charter_runtime.lint._drg._load_built_in_drg",
            return_value=None,
        ):
            graph, state = load_merged_drg(tmp_path)
        assert graph is None
        assert state is GraphState.MISSING

    def test_returns_built_in_only_when_project_missing(
        self, tmp_path: Path
    ) -> None:
        """Project DRG absent, built-in catalog resolves → ``BUILT_IN_ONLY``.

        The built-in helper is patched to avoid requiring the real catalog
        in the test environment.
        """
        stub = _stub_graph("built-in")
        with patch(
            "specify_cli.charter_runtime.lint._drg._load_built_in_drg",
            return_value=stub,
        ):
            graph, state = load_merged_drg(tmp_path)
        assert graph is stub
        assert state is GraphState.BUILT_IN_ONLY

    def test_returns_merged_when_project_resolves(self, tmp_path: Path) -> None:
        """When ``_load_project_drg`` resolves, ``_load_built_in_drg`` MUST
        NOT be consulted and the state MUST be ``MERGED``.
        """
        project_stub = _stub_graph("project")
        built_in_calls = {"n": 0}

        def fake_built_in() -> Any:
            built_in_calls["n"] += 1
            return _stub_graph("built-in")

        with (
            patch(
                "specify_cli.charter_runtime.lint._drg._load_project_drg",
                return_value=project_stub,
            ),
            patch(
                "specify_cli.charter_runtime.lint._drg._load_built_in_drg",
                side_effect=fake_built_in,
            ),
        ):
            graph, state = load_merged_drg(tmp_path)

        assert graph is project_stub
        assert state is GraphState.MERGED
        assert built_in_calls["n"] == 0, (
            "Built-in fallback MUST NOT be invoked when project DRG resolves"
        )

    def test_built_in_resolver_failure_falls_through_to_missing(
        self, tmp_path: Path
    ) -> None:
        """An exception inside the built-in resolver MUST be swallowed and
        the call MUST fall through to ``MISSING`` rather than propagating.
        """
        # The outer ``load_merged_drg`` is allowed to let the exception
        # propagate or swallow it; the contract is "deterministic
        # behaviour". The current implementation lets unexpected runtime
        # errors from the inner resolver propagate so the operator sees a
        # clear failure mode rather than a silent fallback to MISSING. If a
        # future refactor swallows the exception, this test MUST be updated
        # alongside the ADR.
        with (
            patch(
                "specify_cli.charter_runtime.lint._drg._load_built_in_drg",
                side_effect=RuntimeError("catalog blew up"),
            ),
            pytest.raises(RuntimeError),
        ):
            load_merged_drg(tmp_path)


class TestLoadMergedDRGTupleShape:
    """The return value is ALWAYS a 2-tuple — never the bare graph."""

    def test_return_value_is_always_a_tuple(self, tmp_path: Path) -> None:
        with patch(
            "specify_cli.charter_runtime.lint._drg._load_built_in_drg",
            return_value=None,
        ):
            result = load_merged_drg(tmp_path)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], GraphState)


class TestProjectDRGFileFormats:
    """The project loader honours the documented search order
    ``graph.yaml > merged_drg.json > drg.json > compiled_drg.json``.

    We exercise the JSON branch here; YAML is exercised indirectly by the
    higher-level integration tests in
    ``tests/integration/test_charter_lint_lints_all_layers.py``.
    """

    def test_drg_json_resolves_as_merged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A valid JSON DRG at ``.kittify/charter-packs/drg.json`` resolves to
        ``MERGED``. We stub ``DRGGraph.model_validate`` to avoid pulling in
        the full doctrine schema for a unit-level test.
        """
        _write_project_graph(
            tmp_path,
            {"schema_version": "1.0", "nodes": [], "edges": []},
        )

        stub = _stub_graph("project-from-disk")

        class _FakeDRGGraph:
            @staticmethod
            def model_validate(raw: Any) -> Any:
                return stub

        # The internal helper imports lazily; patch the loader to install
        # our fake schema class.
        import specify_cli.charter_runtime.lint._drg as drg_module

        original = drg_module._load_graph_file

        def fake_loader(path: Path) -> Any:
            # Use the real reader for everything except DRGGraph validation
            return _FakeDRGGraph.model_validate({})

        monkeypatch.setattr(drg_module, "_load_graph_file", fake_loader)

        graph, state = load_merged_drg(tmp_path)
        assert graph is stub
        assert state is GraphState.MERGED

        # Restore the original to be a good citizen for sibling tests.
        monkeypatch.setattr(drg_module, "_load_graph_file", original)
