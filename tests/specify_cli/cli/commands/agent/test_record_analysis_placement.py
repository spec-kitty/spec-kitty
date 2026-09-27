"""WP03 (coord-primary-partition-lock) -- placement fail-closed for record-analysis.

Red-first coverage (T010 / T013) for the D11 finding at
``mission_record_analysis.py:80`` (``_resolve_record_analysis_placement_ref``):
pre-fix, a resolution failure (``None``) silently degraded the dirty-tree
preflight to its "conservative" (un-filtered, full-dirty-set) mode instead of
surfacing the resolution failure. This is the SECOND ``CommitTarget`` producer
D11 names alongside ``implement.py`` (the squad's earlier finding missed it).

The low-level resolver's ``Optional``-returning contract is UNCHANGED and
stays pinned by the pre-existing
``tests/specify_cli/cli/commands/agent/test_mission_record_analysis.py::
test_placement_ref_none_on_resolution_failure`` -- this WP fails closed at the
CONSUMPTION site (:func:`_require_record_analysis_placement`), not inside the
resolver itself (C-004: a genuinely-legacy, coordination-less mission still
resolves successfully and is unaffected).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from mission_runtime import ActionContextError, CommitTarget

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# T013 / D11 -- _require_record_analysis_placement fail-closed pure helper
# ---------------------------------------------------------------------------


class TestRequireRecordAnalysisPlacementFailClosed:
    def test_none_placement_ref_raises_structured_error(self) -> None:
        from specify_cli.cli.commands.agent.mission_record_analysis import (
            PlacementResolutionRequired,
            _require_record_analysis_placement,
        )

        with pytest.raises(PlacementResolutionRequired) as excinfo:
            _require_record_analysis_placement(None, mission_slug="001-demo")

        assert excinfo.value.error_code == "PLACEMENT_RESOLUTION_REQUIRED"
        assert "001-demo" in str(excinfo.value)
        # #5113 / FR-014: names the real materializing/flattening command
        # with the real slug, never the retired `doctor workspaces --fix`.
        assert "doctor coordination --mission 001-demo --fix" in str(excinfo.value)

    def test_resolved_placement_ref_is_returned_verbatim(self) -> None:
        from specify_cli.cli.commands.agent.mission_record_analysis import (
            _require_record_analysis_placement,
        )

        target = CommitTarget(ref="kitty/mission-001-demo-AAAA1111")
        assert (
            _require_record_analysis_placement(target, mission_slug="001-demo")
            is target
        )


# ---------------------------------------------------------------------------
# Low-level resolver contract stays pinned (Optional, unchanged) -- sanity
# cross-check that this WP did not touch _resolve_record_analysis_placement_ref
# itself.
# ---------------------------------------------------------------------------


class TestResolverContractUnchanged:
    def test_resolver_still_returns_none_on_resolution_failure(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import mission_runtime

        from specify_cli.cli.commands.agent import mission_record_analysis as seam

        def _boom(*_a: object, **_k: object) -> object:
            raise ActionContextError("X", "no context")

        # The resolver routes through ``placement_seam(...).write_target(ANALYSIS_REPORT)``
        # (NOT ``resolve_action_context``); patch the symbol actually on the path so the
        # ActionContextError is raised inside the seam call and caught → None.
        monkeypatch.setattr(mission_runtime, "placement_seam", _boom, raising=False)
        assert (
            seam._resolve_record_analysis_placement_ref(tmp_path, tmp_path / "001-demo")
            is None
        )


# ---------------------------------------------------------------------------
# T014 -- end-to-end: record_analysis() fails closed instead of proceeding
# with the pre-fix "conservative legacy preflight" degradation.
# ---------------------------------------------------------------------------


_RUNNER = CliRunner()


class TestRecordAnalysisCommandFailsClosedOnUnresolvedPlacement:
    """Pre-fix, ``record_analysis()`` computed ``placement_ref`` and passed it
    (possibly ``None``) straight into the dirty-tree preflight, which
    silently ran in "conservative" mode on ``None`` -- masking a genuine
    resolution failure as an unrelated dirty-tree error (or, on a clean
    tree, letting the command proceed as if nothing were wrong). Post-fix,
    the command exits 1 with a structured, actionable
    ``PLACEMENT_RESOLUTION_REQUIRED`` error BEFORE the preflight even runs.
    """

    def test_json_output_reports_structured_error_before_preflight(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from specify_cli.cli.commands.agent import mission_record_analysis as seam
        from specify_cli.cli.commands.agent.mission import app as mission_app

        feature_dir = tmp_path / "001-demo"
        feature_dir.mkdir()
        monkeypatch.setattr(seam, "locate_project_root", lambda: tmp_path)
        monkeypatch.setattr(seam, "get_main_repo_root", lambda _r: tmp_path)
        monkeypatch.setattr(seam, "_find_feature_directory", lambda *_a, **_k: feature_dir)
        monkeypatch.setattr(seam, "_resolve_record_analysis_placement_ref", lambda *_a, **_k: None)

        preflight_calls: list[object] = []
        monkeypatch.setattr(
            seam,
            "_enforce_analysis_report_write_preflight",
            lambda *_a, **_k: preflight_calls.append(1),
        )

        result = _RUNNER.invoke(
            mission_app,
            ["record-analysis", "--json", "--mission", "001-demo"],
            input="# report\n",
            catch_exceptions=False,
        )

        assert result.exit_code == 1
        assert "PLACEMENT_RESOLUTION_REQUIRED" in result.stdout or "canonical write placement" in result.stdout
        # The fail-closed check must gate BEFORE the (now-unreachable) preflight.
        assert preflight_calls == []

    def test_human_output_reports_structured_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from specify_cli.cli.commands.agent import mission_record_analysis as seam
        from specify_cli.cli.commands.agent.mission import app as mission_app

        feature_dir = tmp_path / "001-demo"
        feature_dir.mkdir()
        monkeypatch.setattr(seam, "locate_project_root", lambda: tmp_path)
        monkeypatch.setattr(seam, "get_main_repo_root", lambda _r: tmp_path)
        monkeypatch.setattr(seam, "_find_feature_directory", lambda *_a, **_k: feature_dir)
        monkeypatch.setattr(seam, "_resolve_record_analysis_placement_ref", lambda *_a, **_k: None)

        result = _RUNNER.invoke(
            mission_app,
            ["record-analysis", "--mission", "001-demo"],
            input="# report\n",
            catch_exceptions=False,
        )

        assert result.exit_code == 1
        assert "001-demo" in result.stdout
        assert "canonical write placement" in result.stdout

    def test_resolved_placement_ref_proceeds_to_preflight(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Control: when placement DOES resolve, the command proceeds past
        the new gate to the (mocked) preflight and empty-body check, proving
        the gate does not over-trigger on the healthy path."""
        from specify_cli.cli.commands.agent import mission_record_analysis as seam
        from specify_cli.cli.commands.agent.mission import app as mission_app

        feature_dir = tmp_path / "001-demo"
        feature_dir.mkdir()
        monkeypatch.setattr(seam, "locate_project_root", lambda: tmp_path)
        monkeypatch.setattr(seam, "get_main_repo_root", lambda _r: tmp_path)
        monkeypatch.setattr(seam, "_find_feature_directory", lambda *_a, **_k: feature_dir)
        monkeypatch.setattr(
            seam,
            "_resolve_record_analysis_placement_ref",
            lambda *_a, **_k: CommitTarget(ref="main"),
        )
        monkeypatch.setattr(seam, "_enforce_analysis_report_write_preflight", lambda *_a, **_k: None)

        # Empty stdin -> the pre-existing "empty body" branch, proving control
        # flow reached PAST the placement gate.
        result = _RUNNER.invoke(
            mission_app, ["record-analysis", "--json", "--mission", "001-demo"], input="   \n"
        )
        assert result.exit_code == 1
        assert "empty" in result.stdout.lower()
