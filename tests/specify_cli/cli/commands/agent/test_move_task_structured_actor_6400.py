"""#6400: every ``agent tasks move-task`` hop, its paired note and the review-override
verdict note write the structured 4-key actor ``{tool, role, profile, model}``.

Drives the real ``move-task`` Typer entry point (the shared rework-loop harness).
``role`` follows the hop (``status.actor.role_for_hop``), never the profile;
``profile`` comes only from the dispatch binding (``--profile``) or the compact
``--agent`` profile segment, else ``None`` -- the WP frontmatter ``agent_profile`` is
never read into the actor (phase split, spec C-006).
"""

from __future__ import annotations

import builtins
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest

from tests.specify_cli.cli.commands.agent import _rework_loop_harness as h

if TYPE_CHECKING:
    from specify_cli.cli.commands.agent.tasks_move_task import _MoveTaskState

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_IMPLEMENTER_ACTOR = {"tool": "claude", "role": "implementer", "profile": "implementer-ivan", "model": "opus"}
_REVIEWER_ACTOR = {"tool": "codex", "role": "reviewer", "profile": "reviewer-renata", "model": "gpt-5"}


def _with_frontmatter_profile(m: h.ReworkMission, profile: str = "python-pedro") -> None:
    """Plant ``agent_profile`` in the WP frontmatter; the actor must never pick it up."""
    wp_file = m.wp_dir / "WP01-core.md"
    text = wp_file.read_text(encoding="utf-8")
    wp_file.write_text(text.replace("title: Core\n", f"title: Core\nagent_profile: {profile}\n", 1), encoding="utf-8")


def _appended(m: h.ReworkMission, before: int) -> list[dict[str, Any]]:
    return h.events(m)[before:]


def _lane(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in events if "to_lane" in e and "from_lane" in e]


def _annotations(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in events if "delta" in e]


def _assert_no_bare_actor(events: list[dict[str, Any]]) -> None:
    """SC-001: no event the commands appended carries a bare-string actor."""
    bare = [(e.get("to_lane") or "annotation", e.get("actor")) for e in events if not isinstance(e.get("actor"), dict)]
    assert bare == [], f"bare-string actors written: {bare}"


def _move_ok(m: h.ReworkMission, to: str, agent: str, *extra: str) -> list[dict[str, Any]]:
    before = len(h.events(m))
    result = h.move(m, h.WP, to, agent, *extra)
    assert result.exit_code == 0, f"{to}: {result.output}"
    return _appended(m, before)


def test_every_hop_of_an_implement_review_reject_loop_is_structured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-006/FR-007: claim, start, submit, review claim and rejection carry the role of the hop."""
    m = h.build_mission(tmp_path, monkeypatch)
    _with_frontmatter_profile(m)
    start = len(h.events(m))

    h.drive_to_for_review(m)
    h.reject(m, "in_review_to_planned")

    appended = _appended(m, start)
    _assert_no_bare_actor(appended)
    hops = [(e["to_lane"], e["actor"]) for e in _lane(appended)]
    assert hops == [
        ("claimed", _IMPLEMENTER_ACTOR),
        ("in_progress", _IMPLEMENTER_ACTOR),
        ("for_review", _IMPLEMENTER_ACTOR),
        ("in_review", _REVIEWER_ACTOR),
        ("planned", _REVIEWER_ACTOR),
    ]


def test_bare_agent_submit_writes_null_profile_not_the_frontmatter_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare ``--agent claude`` asserts no profile; the WP frontmatter profile is not filled in."""
    m = h.build_mission(tmp_path, monkeypatch)
    _with_frontmatter_profile(m)
    h.drive_to_for_review(m)
    h.reject(m, "in_review_to_in_progress")

    appended = _move_ok(m, "for_review", "claude", "--note", "ready again")

    _assert_no_bare_actor(appended)
    expected = {"tool": "claude", "role": "implementer", "profile": None, "model": None}
    assert [e["actor"] for e in _lane(appended)] == [expected]
    notes = [e for e in _annotations(appended) if (e.get("delta") or {}).get("note") == "ready again"]
    assert len(notes) == 1, _annotations(appended)
    assert notes[0]["actor"] == expected


def test_paired_note_carries_the_final_hop_actor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-007: the ``--note`` annotation of a move carries the structured actor of its final hop."""
    m = h.build_mission(tmp_path, monkeypatch)
    for target in ("claimed", "in_progress"):
        _move_ok(m, target, h.IMPLEMENTER)

    appended = _move_ok(m, "for_review", h.IMPLEMENTER, "--note", "ready for review")

    _assert_no_bare_actor(appended)
    notes = [e for e in _annotations(appended) if (e.get("delta") or {}).get("note") == "ready for review"]
    assert len(notes) == 1, _annotations(appended)
    assert notes[0]["actor"] == _lane(appended)[-1]["actor"] == _IMPLEMENTER_ACTOR


def test_profile_flag_fills_the_profile_on_an_implementer_hop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--profile`` is a dispatch binding: it fills ``profile`` whatever the hop's role."""
    m = h.build_mission(tmp_path, monkeypatch)
    for target in ("claimed", "in_progress"):
        _move_ok(m, target, h.IMPLEMENTER)

    appended = _move_ok(m, "for_review", "claude", "--profile", "python-pedro")

    _assert_no_bare_actor(appended)
    assert [e["actor"] for e in _lane(appended)] == [{"tool": "claude", "role": "implementer", "profile": "python-pedro", "model": None}]


def test_compact_agent_profile_segment_fills_the_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--agent claude::python-pedro`` parses to a bare tool plus the profile segment."""
    m = h.build_mission(tmp_path, monkeypatch)
    for target in ("claimed", "in_progress"):
        _move_ok(m, target, h.IMPLEMENTER)

    appended = _move_ok(m, "for_review", "claude::python-pedro")

    assert [e["actor"] for e in _lane(appended)] == [{"tool": "claude", "role": "implementer", "profile": "python-pedro", "model": None}]


def test_review_approval_with_profile_flag_is_a_reviewer_actor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review claim and approval hops are ``reviewer``; ``--profile`` fills the profile."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)

    appended = _move_ok(m, "in_review", "codex", "--profile", "reviewer-renata")
    appended += _move_ok(m, "approved", "codex", "--profile", "reviewer-renata", "--note", "looks good")

    _assert_no_bare_actor(appended)
    expected = {"tool": "codex", "role": "reviewer", "profile": "reviewer-renata", "model": None}
    assert [(e["to_lane"], e["actor"]) for e in _lane(appended)] == [("in_review", expected), ("approved", expected)]


def test_review_override_verdict_note_is_a_reviewer_actor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-010: the review-override annotation event carries a reviewer actor; the override record keeps its string."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    h.reject(m, "in_review_to_planned")
    h.drive_to_for_review(m)
    _move_ok(m, "in_review", h.REVIEWER)

    appended = _move_ok(m, "approved", h.REVIEWER, "--skip-review-artifact-check", "--note", "rejection superseded")

    _assert_no_bare_actor(appended)
    overrides = [e for e in _annotations(appended) if isinstance((e.get("delta") or {}).get("review"), dict) and e["delta"]["review"].get("reason")]
    assert len(overrides) == 1, _annotations(appended)
    assert overrides[0]["actor"] == _REVIEWER_ACTOR
    # The override record itself stays the string identity the done bookkeeping reads.
    assert overrides[0]["delta"]["review"]["actor"] == h.REVIEWER


def test_building_the_hop_actor_reads_no_wp_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Analysis C1: the move-task actor is built from flags and binding only, never from WP frontmatter I/O."""
    from specify_cli.cli.commands.agent.tasks_move_task_hops import _mt_hop_structured_actor
    from specify_cli.status import Lane

    feature_dir = tmp_path / "kitty-specs" / "m"
    (feature_dir / "tasks").mkdir(parents=True)
    wp_file = feature_dir / "tasks" / "WP01-core.md"
    wp_file.write_text("---\nwork_package_id: WP01\nagent_profile: python-pedro\n---\n", encoding="utf-8")
    reads: list[str] = []
    real_open = builtins.open
    real_read_text = Path.read_text

    def _spy_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        reads.append(str(file))
        return real_open(file, *args, **kwargs)

    def _spy_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        reads.append(str(self))
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", _spy_open)
    monkeypatch.setattr(Path, "read_text", _spy_read_text)
    st = SimpleNamespace(agent="claude", resolved_binding=None, feature_dir=feature_dir, task_id="WP01")

    actor = _mt_hop_structured_actor(cast("_MoveTaskState", st), Lane.IN_PROGRESS, Lane.FOR_REVIEW, "claude")

    assert actor == {"tool": "claude", "role": "implementer", "profile": None, "model": None}
    assert [r for r in reads if r.startswith(str(feature_dir))] == []


def test_explicit_agent_with_an_empty_tool_is_refused_before_any_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit operator ``--agent`` the compact parser rejects refuses with nothing written (as on the base)."""
    m = h.build_mission(tmp_path, monkeypatch)
    before = h.events(m)

    result = h.move(m, h.WP, "claimed", ":x")

    assert result.exit_code == 1, result.output
    assert "Invalid --agent value" in result.output
    assert "Empty agent tool in --agent value" in result.output
    assert "Traceback" not in result.output
    assert h.events(m) == before


def test_recorded_migration_reviewer_identity_stays_a_reconstruction_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A recorded ``migration:`` identity (no ``--agent``) is kept whole, so it stays a seed (#6400 review F3)."""
    from spec_kitty_events import diary

    from specify_cli.cli.commands.agent.tasks import app as tasks_app
    from specify_cli.status import Lane, StatusEvent, is_migration_actor
    from tests._support.reconstruction_seed import reduces_as_reconstruction_seed
    from tests._support.status_seed import seed_status_event
    from typer.testing import CliRunner

    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    seed_status_event(
        m.feature_dir,
        StatusEvent(
            event_id="seed-migration-review-claim",
            mission_slug=m.mission_slug,
            wp_id=h.WP,
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.IN_REVIEW,
            at="2099-01-01T00:00:00+00:00",
            actor="migration:backfill",
            force=True,
            execution_mode="worktree",
        ),
    )
    before = len(h.events(m))

    result = CliRunner().invoke(
        tasks_app,
        ["move-task", h.WP, "--to", "approved", "--mission", m.mission_slug, "--skip-review-artifact-check", "--note", "seeded"],
    )

    assert result.exit_code == 0, result.output
    approvals = [e for e in _lane(_appended(m, before)) if e["to_lane"] == "approved"]
    assert len(approvals) == 1, _appended(m, before)
    assert approvals[0]["actor"] == {"tool": "migration:backfill", "role": "reviewer", "profile": None, "model": None}
    assert is_migration_actor(approvals[0]["actor"])
    assert diary._is_reconstruction_seed(diary.StatusEvent.from_dict(dict(approvals[0])))
    assert reduces_as_reconstruction_seed(approvals[0]["actor"])


def test_explicit_migration_agent_is_parsed_strictly_and_is_not_a_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit ``--agent migration:x`` is parsed like any compact value: tool ``migration``, never a seed (operator 2026-10-29)."""
    from specify_cli.status import is_migration_actor
    from tests._support.reconstruction_seed import reduces_as_reconstruction_seed

    m = h.build_mission(tmp_path, monkeypatch)

    appended = _move_ok(m, "claimed", "migration:x")

    actors = [e["actor"] for e in _lane(appended)]
    assert actors == [{"tool": "migration", "role": "implementer", "profile": None, "model": "x"}]
    assert not is_migration_actor(actors[0])
    assert not reduces_as_reconstruction_seed(actors[0])


def test_explicit_agent_with_more_than_four_segments_parses_like_mark_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit ``--agent`` goes through the strict builder mark-status uses, whatever its segment count."""
    from specify_cli.status import build_status_actor

    m = h.build_mission(tmp_path, monkeypatch)

    appended = _move_ok(m, "claimed", "a:b:c:d:e")

    expected = build_status_actor(role="implementer", agent="a:b:c:d:e", fallback_tool="user", binding=None)
    assert expected == {"tool": "a", "role": "implementer", "profile": "c", "model": "b"}
    assert [e["actor"] for e in _lane(appended)] == [expected]
