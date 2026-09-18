"""WP02 no-selector regression tests: exit code 2 on missing --mission.

For each of the four commands cleaned up in WP02 (next_step, research,
mission_resolve_command, accept), verifies that:
1. ``--feature`` is rejected outright by the parser (unknown option, exit 2).
2. Omitting ``--mission`` exits with code 2 and a readable message.
3. No uncaught TypeError escapes.
"""

from __future__ import annotations
import pathlib
import pytest
import typer
from typer.testing import CliRunner
from specify_cli import app as main_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]
runner = CliRunner()


class TestNextNoSelector:
    def test_feature_flag_rejected_exit2(self):
        result = runner.invoke(main_app, ["next", "--feature", "some-slug"])
        assert result.exit_code == 2, result.output
        assert "no such option" in result.output.lower()

    def test_no_mission_raises_discovery_not_bad_parameter(self):
        # C5 (mission-handle-resolution WP05): a missing --mission is no longer
        # a usage error. With no missions present (``/tmp`` has no kitty-specs)
        # the resolver raises the typed discovery signal, NOT typer.BadParameter.
        from specify_cli.cli.commands.next_cmd import (
            MissingHandleDiscovery,
            _resolve_mission_slug,
        )

        with pytest.raises(MissingHandleDiscovery) as exc:
            _resolve_mission_slug(None, pathlib.Path("/tmp"))
        assert exc.value.listings == []
        assert not isinstance(exc.value, typer.BadParameter)

    def test_no_mission_no_type_error(self):
        from specify_cli.cli.commands.next_cmd import (
            MissingHandleDiscovery,
            _resolve_mission_slug,
        )

        try:
            _resolve_mission_slug(None, pathlib.Path("/tmp"))
        except MissingHandleDiscovery:
            pass
        except TypeError as e:
            raise AssertionError(f"TypeError: {e}") from e


class TestResearchNoSelector:
    def test_feature_flag_rejected_exit2(self):
        app = typer.Typer()
        from specify_cli.cli.commands.research import research

        app.command()(research)
        result = runner.invoke(app, ["--feature", "some-slug"])
        assert result.exit_code == 2, result.output
        assert "no such option" in result.output.lower()

    def test_no_mission_exit2_readable_message(self):
        app = typer.Typer()
        from specify_cli.cli.commands.research import research

        app.command()(research)
        result = runner.invoke(app, [])
        assert result.exit_code == 2, result.output
        assert not isinstance(result.exception, TypeError)

    def test_no_mission_no_type_error(self):
        app = typer.Typer()
        from specify_cli.cli.commands.research import research

        app.command()(research)
        result = runner.invoke(app, [])
        assert not isinstance(result.exception, TypeError)


class TestContextMissionResolveNoSelector:
    def test_feature_flag_rejected_exit2(self):
        result = runner.invoke(
            main_app,
            ["context", "mission-resolve", "--feature", "some-slug", "--wp", "WP01"],
        )
        assert result.exit_code == 2, result.output
        assert "no such option" in result.output.lower()

    def test_no_mission_exit2(self):
        result = runner.invoke(main_app, ["context", "mission-resolve", "--wp", "WP01"])
        assert result.exit_code == 2, result.output
        assert not isinstance(result.exception, TypeError)


class TestAcceptNoSelector:
    def test_feature_flag_rejected_exit2(self):
        result = runner.invoke(main_app, ["accept", "--feature", "some-slug"])
        assert result.exit_code == 2, result.output
        assert "no such option" in result.output.lower()

    def test_no_mission_exit2_readable_message(self):
        result = runner.invoke(main_app, ["accept"])
        assert result.exit_code == 2, result.output
        out = result.output.lower()
        assert "required" in out or "mission" in out

    def test_no_mission_no_type_error(self):
        result = runner.invoke(main_app, ["accept"])
        assert not isinstance(result.exception, TypeError)
