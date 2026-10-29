"""``agent status emit`` writes the structured 4-key actor (#6400, FR-011).

Driven through the real ``spec-kitty agent status emit`` Typer entry point on a
fixture Mission. The stored event carries ``{tool, role, profile, model}``:
``tool`` is the bare tool of ``--actor`` (a compact ``tool:model:profile`` value
is parsed), ``role`` comes from the hop (``role_for_hop``) and ``profile`` only
from the compact segment (no WP-frontmatter fill in this phase, C-006). The
command's own JSON output keeps echoing the ``--actor`` value as a string.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.status import app
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.models import TransitionRequest
from specify_cli.status.store import read_events
from tests._support.reconstruction_seed import reduces_as_reconstruction_seed
from tests.status.conftest import seed_wp_to_planned

pytestmark = pytest.mark.fast

runner = CliRunner()

_SLUG = "017-test-mission"


@pytest.fixture(autouse=True)
def _disable_emit_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_status_fan_out", lambda *args, **kwargs: None)


@pytest.fixture
def mission_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    feature_dir = repo / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    (repo / ".kittify").mkdir()
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    # The planned profile lives in the frontmatter; this phase must NOT copy it.
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\nagent_profile: python-pedro\nsubtasks: []\n---\n\n# WP01\n",
        encoding="utf-8",
    )
    seed_wp_to_planned(feature_dir, "WP01", slug=_SLUG)
    return repo


def _feature_dir(repo: Path) -> Path:
    return repo / "kitty-specs" / _SLUG


def _advance(repo: Path, *lanes: str) -> None:
    for lane in lanes:
        emit_status_transition(TransitionRequest(feature_dir=_feature_dir(repo), mission_slug=_SLUG, wp_id="WP01", to_lane=lane, actor="claude"))


def _emit(repo: Path, *args: str) -> dict[str, object]:
    with (
        patch("specify_cli.cli.commands.agent.status.locate_project_root", return_value=repo),
        patch("specify_cli.cli.commands.agent.status._find_mission_slug", return_value=_SLUG),
    ):
        result = runner.invoke(app, ["emit", "WP01", "--mission", _SLUG, "--json", *args])
    assert result.exit_code == 0, result.stdout
    payload: dict[str, object] = json.loads(result.stdout)
    return payload


def _last_actor(repo: Path) -> object:
    return read_events(_feature_dir(repo))[-1].actor


def test_claim_records_implementer_actor_without_frontmatter_profile(mission_repo: Path) -> None:
    output = _emit(mission_repo, "--to", "claimed", "--actor", "claude")

    assert _last_actor(mission_repo) == {"tool": "claude", "role": "implementer", "profile": None, "model": None}
    assert output["actor"] == "claude"


def test_review_claim_with_compact_actor_records_reviewer_profile_and_model(mission_repo: Path) -> None:
    _advance(mission_repo, "claimed", "in_progress", "for_review")

    output = _emit(mission_repo, "--to", "in_review", "--actor", "claude-reviewer:opus:reviewer-renata")

    assert _last_actor(mission_repo) == {
        "tool": "claude-reviewer",
        "role": "reviewer",
        "profile": "reviewer-renata",
        "model": "opus",
    }
    # The command output keeps echoing the --actor value verbatim (unchanged contract).
    assert output["actor"] == "claude-reviewer:opus:reviewer-renata"


def test_rejection_leaving_in_review_records_reviewer_role(mission_repo: Path) -> None:
    _advance(mission_repo, "claimed", "in_progress", "for_review", "in_review")
    verdict = json.dumps({"reviewer": "codex", "verdict": "changes_requested", "reference": "review-1"})

    _emit(mission_repo, "--to", "in_progress", "--actor", "codex", "--review-result-json", verdict)

    assert _last_actor(mission_repo) == {"tool": "codex", "role": "reviewer", "profile": None, "model": None}


def test_implementer_hop_to_for_review_records_implementer_role(mission_repo: Path) -> None:
    _advance(mission_repo, "claimed", "in_progress")

    _emit(mission_repo, "--to", "for_review", "--actor", "claude::python-pedro")

    assert _last_actor(mission_repo) == {"tool": "claude", "role": "implementer", "profile": "python-pedro", "model": None}


def test_empty_tool_actor_is_accepted_and_stored_verbatim_as_tool(mission_repo: Path) -> None:
    """An ``--actor`` the compact parser rejects (empty tool) is accepted as on the base (#6400 review)."""
    output = _emit(mission_repo, "--to", "claimed", "--actor", ":x")

    assert _last_actor(mission_repo) == {"tool": ":x", "role": "implementer", "profile": None, "model": None}
    assert output["actor"] == ":x"
    assert output["to_lane"] == "claimed"


def test_status_facade_exports_each_name_once() -> None:
    """``specify_cli.status.__all__`` lists every name once (#6400 consolidation finding)."""
    from collections import Counter

    import specify_cli.status as status_facade

    duplicates = sorted(name for name, count in Counter(status_facade.__all__).items() if count > 1)
    assert duplicates == []
    assert "actor_from_option" in status_facade.__all__


def _assert_reconstruction_seed(actor: object, raw_event: dict[str, object]) -> None:
    """The stored actor is a migration seed for the CLI and for the package reducer alike."""
    from spec_kitty_events import diary

    from specify_cli.status import is_migration_actor
    from specify_cli.status.models import ActorField

    assert is_migration_actor(cast("ActorField", actor))
    assert diary._is_reconstruction_seed(diary.StatusEvent.from_dict(dict(raw_event)))
    assert reduces_as_reconstruction_seed(raw_event["actor"])


def test_migration_actor_is_stored_whole_and_stays_a_reconstruction_seed(mission_repo: Path) -> None:
    """A ``migration:`` ``--actor`` is stored whole as ``tool`` so it keeps its seed status (#6400 review F3)."""
    from specify_cli.status.store import read_events_raw

    _emit(mission_repo, "--to", "claimed", "--actor", "migration:backfill")

    raw = [e for e in read_events_raw(_feature_dir(mission_repo)) if e.get("to_lane") == "claimed"][-1]
    assert raw["actor"] == {"tool": "migration:backfill", "role": "implementer", "profile": None, "model": None}
    _assert_reconstruction_seed(_last_actor(mission_repo), raw)
