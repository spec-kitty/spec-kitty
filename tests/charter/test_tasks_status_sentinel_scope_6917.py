"""A read-only board render parses only the profiles its rows name (#6917).

`spec-kitty agent tasks status` renders one structural boolean per claimed row
(``profile.sentinel`` -> the 👤 human-in-charge marker). Before this mission the
render built the whole ``ActiveCharterService`` and then the complete
``AgentProfileRepository``: 26 shipped profile documents plus the lineage graph.
These tests pin the delivered property through the production CLI entry point:

* the render parses at most the documents that can supply the ids its rows name;
* the 👤 marker text is unchanged;
* an empty board parses no profile at all, and an unknown id degrades quietly.

The positive control (a plain catalogue read through the same counter) proves
the probe can actually observe parsed documents.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from charter.offering.agent_profiles.repository import AgentProfileRepository
from specify_cli.cli.commands.agent.tasks import app
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event
from tests.mocked_env import setup_mocked_env

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

runner = CliRunner()

_MISSION_SLUG = "census-mission"
_HIC_PROFILE = "human-in-charge"
_SECOND_PROFILE = "python-pedro"
_UNKNOWN_PROFILE = "no-such-profile"


def _count_profile_parses(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record the filename of every agent-profile document the loader processes.

    The probe sits on the repository's per-document step, so it counts documents
    across built-in, org and project layers (the shipped-parse memoisation sits
    below it and does not hide a document from this count) without depending on
    the shape of the YAML loader.
    """
    parsed: list[str] = []
    real_parse = AgentProfileRepository._parse_profile_from_file  # noqa: SLF001 - test probe

    def _counting_parse(
        self: AgentProfileRepository,
        yaml: Any,
        yaml_file: Path,
        *,
        layer: str,
        built_in_profiles: dict[str, Any],
    ) -> Any:
        parsed.append(Path(yaml_file).name)
        return real_parse(self, yaml, yaml_file, layer=layer, built_in_profiles=built_in_profiles)

    monkeypatch.setattr(AgentProfileRepository, "_parse_profile_from_file", _counting_parse)
    return parsed


def _create_project(
    tmp_path: Path,
    lanes: dict[str, tuple[str, str]],
) -> Path:
    """Create a minimal project + mission whose WPs declare ``lanes``.

    ``lanes`` maps a work-package id to ``(agent_profile, lane)``.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text("activated_agent_profiles: null\n", encoding="utf-8")

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": _MISSION_SLUG, "mission_number": "099", "mission_type": "software-dev"}),
        encoding="utf-8",
    )

    for wp_id, (agent_profile, lane) in lanes.items():
        (tasks_dir / f"{wp_id}-fixture.md").write_text(
            textwrap.dedent(
                f"""\
                ---
                work_package_id: {wp_id}
                title: Fixture {wp_id}
                execution_mode: code_change
                agent_profile: {agent_profile}
                ---
                # {wp_id}
                """
            ),
            encoding="utf-8",
        )
        seed_status_event(
            feature_dir,
            StatusEvent(
                event_id=f"fixture-{wp_id}-{lane}",
                mission_slug=_MISSION_SLUG,
                wp_id=wp_id,
                from_lane=Lane.PLANNED,
                to_lane=Lane(lane),
                at="2026-01-01T00:00:00+00:00",
                actor="test",
                force=True,
                execution_mode="worktree",
            ),
        )

    return feature_dir


def _invoke_status(tmp_path: Path) -> Any:
    workspace = SimpleNamespace(execution_mode="code_change", resolution_kind="lane_workspace")
    with setup_mocked_env(tmp_path, mission_slug=_MISSION_SLUG, workspace_resolution=workspace):
        return runner.invoke(app, ["status", "--mission", _MISSION_SLUG])


# --------------------------------------------------------------------------- #
# The acceptance guard
# --------------------------------------------------------------------------- #


def test_board_render_parses_only_the_profiles_its_rows_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two named profiles ⇒ two documents, not the 26-document catalogue."""
    _create_project(
        tmp_path,
        {
            "WP01": (_HIC_PROFILE, "in_progress"),
            "WP02": (_SECOND_PROFILE, "for_review"),
        },
    )
    parsed = _count_profile_parses(monkeypatch)

    result = _invoke_status(tmp_path)

    assert result.exit_code == 0, result.output
    # Marker parity: the human-in-charge row still renders the 👤 prefix.
    assert "👤" in result.output
    names = {Path(path).name for path in parsed}
    assert names == {f"{_HIC_PROFILE}.agent.yaml", f"{_SECOND_PROFILE}.agent.yaml"}, sorted(names)


def test_catalogue_is_much_larger_than_the_board_needs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Positive control: the counter does see the whole catalogue on a plain read."""
    _create_project(tmp_path, {"WP01": (_HIC_PROFILE, "in_progress")})
    parsed = _count_profile_parses(monkeypatch)

    catalogue = AgentProfileRepository()

    assert len(catalogue.list_all()) > 20, "fixture: the shipped catalogue is expected to be large"
    assert len({Path(path).name for path in parsed}) == len(catalogue.list_all())


def test_empty_board_parses_no_profile_at_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing claimed ⇒ no profile read (the historical lazy guard, still free)."""
    _create_project(tmp_path, {"WP01": ("", "planned")})
    parsed = _count_profile_parses(monkeypatch)

    result = _invoke_status(tmp_path)

    assert result.exit_code == 0, result.output
    assert parsed == []


def test_unknown_profile_id_renders_without_a_marker_or_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An id no layer ships degrades to no marker; the board still renders."""
    _create_project(tmp_path, {"WP01": (_UNKNOWN_PROFILE, "in_progress")})
    parsed = _count_profile_parses(monkeypatch)

    result = _invoke_status(tmp_path)

    assert result.exit_code == 0, result.output
    assert "👤" not in result.output
    # No layer ships ``<id>.agent.yaml`` for it, so the scoped read parses nothing
    # at all -- the unknown id does not fall back to the catalogue.
    assert parsed == []


@pytest.mark.parametrize(
    ("config_text", "label"),
    [
        ("charter: [unclosed\n", "malformed-yaml"),
        ("activated_agent_profiles: 12\n", "invalid-activation-key"),
        ("charter: .kittify/does-not-exist.yaml\n", "dangling-charter-pointer"),
    ],
)
def test_broken_config_still_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config_text: str, label: str
) -> None:
    """A broken ``.kittify/config.yaml`` must not degrade to a markerless board.

    The scoped read does not use activation *state*, but it must not turn a config
    the activation-aware build rejects into a successful render: the builder
    validates the file through the charter configuration authority first
    (charter FR-002 / ``status_failed``). Each class below raised through the old
    ``build_active_charter_service`` path, so each must still fail here.
    """
    _create_project(tmp_path, {"WP01": (_HIC_PROFILE, "in_progress")})
    (tmp_path / ".kittify" / "config.yaml").write_text(config_text, encoding="utf-8")
    parsed = _count_profile_parses(monkeypatch)

    result = _invoke_status(tmp_path)

    assert result.exit_code != 0, label
    assert "👤" not in result.output, label
    assert parsed == [], label
