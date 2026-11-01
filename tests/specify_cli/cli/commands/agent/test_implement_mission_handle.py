"""#6278: ``implement --mission <human-slug>`` resolves the Mission.

The reported defect: a Mission created today is ``<human-slug>-<mid8>``
(``smoke-test-01M6BTQX``). ``agent tasks status --mission smoke-test`` resolved it
through the read-path bare-modern fold, while ``implement WP01 --mission smoke-test``
exited 2 with ``No mission found for handle "smoke-test"`` because it resolves through
``implement_phases.detect_mission_context`` →
``cli.selector_resolution.resolve_mission_handle`` →
``context.mission_resolver.resolve_mission``, whose human-slug rung stripped only a
leading ``NNN-`` prefix.

These tests drive the command's own entry point (``detect_mission_context``) rather
than the helper it calls, so a future change that reintroduces a second resolver for
``implement`` fails here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.cli.commands.implement_phases import detect_mission_context

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_ID = "01M6BTQXBFZMBKVGB8VXBRQW07"
COMPOSED_SLUG = "smoke-test-01M6BTQX"


def _seed_mission(repo_root: Path, slug: str, mission_id: str) -> Path:
    """Write ``kitty-specs/<slug>/meta.json`` and return the mission directory."""
    mission_dir = repo_root / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": mission_id, "mission_slug": slug}),
        encoding="utf-8",
    )
    return mission_dir


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    """A repo holding exactly one mid8-composed Mission."""
    (tmp_path / ".kittify").mkdir()
    _seed_mission(tmp_path, COMPOSED_SLUG, MISSION_ID)
    return tmp_path


class TestImplementAcceptsHumanSlug:
    def test_human_slug_resolves(self, repo_root: Path) -> None:
        number, slug = detect_mission_context("smoke-test", repo_root)
        assert slug == COMPOSED_SLUG
        # mid8-era missions carry no numeric prefix.
        assert number is None

    @pytest.mark.parametrize("handle", ["smoke-test", COMPOSED_SLUG, "01M6BTQX"])
    def test_every_handle_form_returns_the_same_composed_slug(
        self, repo_root: Path, handle: str
    ) -> None:
        assert detect_mission_context(handle, repo_root) == (None, COMPOSED_SLUG)

    def test_unknown_handle_still_refuses(self, repo_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as excinfo:
            detect_mission_context("no-such-mission", repo_root)

        assert excinfo.value.code == 2
        assert "No mission found for handle" in capsys.readouterr().err

    def test_shared_human_slug_refuses_without_guessing(
        self, repo_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_mission(repo_root, "smoke-test-01AAAAAA", "01AAAAAABFZMBKVGB8VXBRQW0")

        with pytest.raises(SystemExit) as excinfo:
            detect_mission_context("smoke-test", repo_root)

        assert excinfo.value.code == 2
        err = capsys.readouterr().err
        assert "smoke-test-01M6BTQX" in err
        assert "smoke-test-01AAAAAA" in err

    def test_json_mode_reports_the_ambiguity_as_structured_data(
        self, repo_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_mission(repo_root, "smoke-test-01AAAAAA", "01AAAAAABFZMBKVGB8VXBRQW0")

        with pytest.raises(SystemExit) as excinfo:
            detect_mission_context("smoke-test", repo_root, json_mode=True)

        assert excinfo.value.code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is False
        assert payload["handle"] == "smoke-test"
        assert {c["slug"] for c in payload["candidates"]} == {
            "smoke-test-01M6BTQX",
            "smoke-test-01AAAAAA",
        }

