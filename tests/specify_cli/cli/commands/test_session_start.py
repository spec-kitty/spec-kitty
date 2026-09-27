"""T021 — Tests for the session-start CLI command.

Covers: project found/not-found, exit-0 guarantee, _find_project_root traversal,
exception swallowing, and NFR-001 performance (<200ms).
"""

from __future__ import annotations

import time
from functools import partial
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import session_start as session_start_module
from specify_cli.cli.commands.session_start import (
    _find_project_root,
    session_start,
)
from tests._perf_helpers import assert_timing_budget


def _bound_project_root_walk(monkeypatch: pytest.MonkeyPatch, stop: Path) -> None:
    """Bind the command's project-root walk to *stop*, inside this test's tmp tree (#130).

    Production ``session_start()`` walks from cwd all the way to the filesystem
    root. Nothing above ``tmp_path`` is under test control: on a shared machine
    any ancestor (/tmp, /) can gain a stray ``.kittify/`` from a sibling test
    mid-run, which flips outside-project verdicts non-deterministically — the
    exact mechanism that sent these nodes red on some main baselines and green
    on others (issue #130). Bounding the walk to territory this test created
    makes the verdict deterministic while still exercising the real
    find-nothing-then-stay-silent command path; the traversal itself is pinned
    hermetically by ``TestFindProjectRoot``.
    """
    monkeypatch.setattr(
        session_start_module,
        "_find_project_root",
        partial(session_start_module._find_project_root, stop=stop),
    )


pytestmark = [pytest.mark.unit, pytest.mark.fast]

# Build a minimal typer app for testing the session_start command
_app = typer.Typer()
_app.command()(session_start)

runner = CliRunner()


@pytest.fixture
def spec_project(tmp_path: Path) -> Path:
    """A minimal spec-kitty project with .kittify/."""
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".claude").mkdir()
    return tmp_path


class TestSessionStartInsideProject:
    def test_exit_0_inside_project(self, spec_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(spec_project)
        with (
            patch("specify_cli.session_presence.manager.UpgradeChecker") as mock_checker_cls,
            patch("importlib.metadata.version", return_value="3.2.0"),
            patch("specify_cli.compat.plan", side_effect=Exception("no compat")),
        ):
            mock_checker_cls.return_value.get_available_version.return_value = None
            result = runner.invoke(_app, [])
        assert result.exit_code == 0

    def test_outputs_render_result_inside_project(self, spec_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.session_presence.content import SECTION_OPEN

        monkeypatch.chdir(spec_project)
        with (
            patch("specify_cli.session_presence.manager.UpgradeChecker") as mock_checker_cls,
            patch("importlib.metadata.version", return_value="3.2.0"),
            patch("specify_cli.compat.plan", side_effect=Exception("no compat")),
        ):
            mock_checker_cls.return_value.get_available_version.return_value = None
            result = runner.invoke(_app, [])
        assert SECTION_OPEN in result.output


class TestSessionStartOutsideProject:
    def test_exit_0_outside_project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No .kittify/ within the bounded walk region: exit 0."""
        cwd = tmp_path / "outside" / "any" / "project"
        cwd.mkdir(parents=True)
        monkeypatch.chdir(cwd)
        _bound_project_root_walk(monkeypatch, tmp_path)
        result = runner.invoke(_app, [])
        assert result.exit_code == 0

    def test_no_output_outside_project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cwd = tmp_path / "outside" / "any" / "project"
        cwd.mkdir(parents=True)
        monkeypatch.chdir(cwd)
        _bound_project_root_walk(monkeypatch, tmp_path)
        result = runner.invoke(_app, [])
        assert result.output.strip() == ""


class TestFindProjectRoot:
    """Traversal seam coverage — every walk stays inside this test's own tree (#130, #139).

    Nothing above ``tmp_path`` (``/tmp``, ``/``) is under test control:
    sibling tests can pollute a shared ancestor with a stray ``.kittify/``
    mid-run. Walks are therefore pinned either through the explicit
    ``start``/``stop`` parameters, or — for the two nodes exercising the
    production no-arg default — because their ``.kittify/`` marker sits
    *below* ``tmp_path``, terminating the ascent before any shared territory
    is read.
    """

    def test_finds_kittify_at_start(self, spec_project: Path) -> None:
        root = _find_project_root(spec_project)
        assert root == spec_project

    def test_defaults_to_cwd_start(self, spec_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No *start* given: the walk begins at the cwd (production default).

        Safe without a stop boundary — a project at the cwd is found on the
        first check, before any shared ancestor is ever read.
        """
        monkeypatch.chdir(spec_project)
        assert _find_project_root() == spec_project

    def test_walks_up_from_nested_subdir(self, spec_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No-arg call from a nested cwd ascends to the project root (production shape).

        The only node that exercises the unbounded default boundary — *stop*
        left at ``None``, exactly as the production callers
        (``session_start``/``session_stop``) invoke the walk. A regression
        that leaks *start* into the default boundary makes every such walk
        answer ``None`` on the first probe, silently disabling both hook
        commands from any subdirectory while the outer
        ``except Exception: pass`` keeps exit 0 (#139). Hermetic anyway:
        ``.kittify/`` sits *below* ``tmp_path``, so the walk terminates
        before any shared ancestor is read.
        """
        nested = spec_project / "a" / "b" / "c"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        assert _find_project_root() == spec_project

    def test_finds_kittify_exactly_at_stop_boundary(self, spec_project: Path) -> None:
        """The stop boundary itself is still examined before the walk ends."""
        nested = spec_project / "a"
        nested.mkdir()
        root = _find_project_root(nested, stop=spec_project)
        assert root == spec_project

    def test_returns_none_when_region_has_no_kittify(self, tmp_path: Path) -> None:
        """No .kittify/ between start and the stop boundary → None."""
        jail = tmp_path / "no-project-here"
        nested = jail / "a" / "b"
        nested.mkdir(parents=True)
        root = _find_project_root(nested, stop=jail)
        assert root is None

    def test_returns_none_at_filesystem_root(self) -> None:
        """Termination at the true filesystem root.

        Starting AT ``/`` makes ``/.kittify`` the only candidate directory; it
        cannot exist on a test machine (creating it needs root), so the
        fs-root termination branch is exercised without walking through any
        shared territory.
        """
        assert _find_project_root(Path("/")) is None


class TestExitZeroGuarantee:
    def test_exit_0_on_build_content_exception(self, spec_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exception in _build_content(): exit 0, no traceback output."""
        monkeypatch.chdir(spec_project)
        with patch(
            "specify_cli.session_presence.manager.SessionPresenceManager._build_content",
            side_effect=RuntimeError("unexpected crash"),
        ):
            result = runner.invoke(_app, [])
        assert result.exit_code == 0
        assert "Traceback" not in result.output

    def test_exit_0_on_load_agent_config_exception(self, spec_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exception in load_agent_config(): exit 0, no output."""
        monkeypatch.chdir(spec_project)
        with patch(
            "specify_cli.core.agent_config.load_agent_config",
            side_effect=RuntimeError("config load failure"),
        ):
            result = runner.invoke(_app, [])
        assert result.exit_code == 0


class TestNFR001Performance:
    def test_session_start_succeeds_with_mocked_io(self, spec_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """session-start exits 0 with all I/O mocked (NFR-001 functional half)."""
        monkeypatch.chdir(spec_project)
        with (
            patch("specify_cli.session_presence.manager.UpgradeChecker") as mock_checker_cls,
            patch("importlib.metadata.version", return_value="3.2.0"),
            patch("specify_cli.compat.plan", side_effect=Exception("no compat")),
        ):
            mock_checker_cls.return_value.get_available_version.return_value = None
            result = runner.invoke(_app, [])

        assert result.exit_code == 0

    @pytest.mark.performance
    def test_session_start_completes_under_200ms(self, spec_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """NFR-001: session-start must complete in <200ms on a warm filesystem.

        All I/O is mocked to eliminate variability and measure only the
        command dispatch overhead itself.
        """
        monkeypatch.chdir(spec_project)
        with (
            patch("specify_cli.session_presence.manager.UpgradeChecker") as mock_checker_cls,
            patch("importlib.metadata.version", return_value="3.2.0"),
            patch("specify_cli.compat.plan", side_effect=Exception("no compat")),
        ):
            mock_checker_cls.return_value.get_available_version.return_value = None
            start = time.monotonic()
            runner.invoke(_app, [])
            elapsed_ms = (time.monotonic() - start) * 1000

        assert_timing_budget(elapsed_ms, 200, name="session-start NFR-001")
