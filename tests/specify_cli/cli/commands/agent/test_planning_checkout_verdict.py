"""#7594: ``setup-plan`` and ``check-prerequisites`` give one checkout verdict.

A Mission created without ``--topology`` mints a topic branch and checks it out in the
repository root checkout; ``meta.target_branch`` stays the branch the operator stood on.
The planning partition writes to the topic branch until the Mission lands, also after
``finalize-tasks`` settled it to ``lanes_with_coord`` (the coordination worktree then holds
the topic branch and the root checkout is back on the target).

Before the fix the two commands compared different operands: ``setup-plan`` preferred the
minted ``meta.mission_branch`` and ``check-prerequisites`` compared the primary checkout's
HEAD with ``meta.target_branch``, so their ``branch_matches_target`` verdicts were opposite
in both phases. Every test drives the real ``agent mission`` commands from a real checkout
of a Mission built by the real ``agent mission create`` core and settled by the real
``finalize-tasks``; both directions of the verdict are asserted, so a hard-coded answer
cannot pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    THREE_LANES,
    DefaultMission,
    _quiet_status_fanout,
    current_branch,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

__all__ = ["_quiet_status_fanout"]

_UNPROTECTED = "work"


def _contract(cwd: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> dict[str, object]:
    """Run ``agent mission <args> --json`` from *cwd*; return the branch contract fields."""
    from specify_cli.cli.commands.agent.mission import app

    monkeypatch.chdir(cwd)
    result = CliRunner().invoke(app, [*args, "--json"], catch_exceptions=False)
    payloads = [json.loads(line) for line in result.output.splitlines() if line.startswith("{")]
    assert payloads, result.output
    payload = payloads[-1]
    assert "branch_matches_target" in payload, payload
    context = payload["branch_context"]
    assert isinstance(context, dict)
    return {
        "current_branch": payload["current_branch"],
        "target_branch": payload["target_branch"],
        "expected_checkout_branch": context["expected_checkout_branch"],
        "branch_matches_target": payload["branch_matches_target"],
    }


def _setup_plan(mission: DefaultMission, cwd: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    return _contract(cwd, monkeypatch, "setup-plan", "--mission", mission.slug)


def _check_prerequisites(mission: DefaultMission, cwd: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    return _contract(cwd, monkeypatch, "check-prerequisites", "--mission", mission.slug, "--paths-only", "--include-tasks")


def _expected(*, current: str, target: str, expected_checkout: str) -> dict[str, object]:
    return {
        "current_branch": current,
        "target_branch": target,
        "expected_checkout_branch": expected_checkout,
        "branch_matches_target": current == expected_checkout,
    }


@pytest.fixture
def mission(tmp_path: Path) -> DefaultMission:
    created = make_default_mission(tmp_path, THREE_LANES, standing_on=_UNPROTECTED)
    assert created.topic and current_branch(created.root) == created.topic
    return created


def test_before_settlement_both_commands_accept_the_minted_topic_branch(mission: DefaultMission, monkeypatch: pytest.MonkeyPatch) -> None:
    expected = _expected(current=mission.topic, target=_UNPROTECTED, expected_checkout=mission.topic)
    assert expected["branch_matches_target"] is True
    assert _setup_plan(mission, mission.root, monkeypatch) == expected
    assert _check_prerequisites(mission, mission.root, monkeypatch) == expected


def test_after_settlement_both_commands_name_the_topic_branch_from_either_checkout(mission: DefaultMission, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(mission.root)
    code, payload = run_finalize(mission)
    assert code == 0, payload
    assert current_branch(mission.root) == _UNPROTECTED
    coord = mission.coord_mission_dir.parents[1]

    on_target = _expected(current=_UNPROTECTED, target=_UNPROTECTED, expected_checkout=mission.topic)
    assert on_target["branch_matches_target"] is False
    assert _setup_plan(mission, mission.root, monkeypatch) == on_target
    assert _check_prerequisites(mission, mission.root, monkeypatch) == on_target

    on_topic = _expected(current=mission.topic, target=_UNPROTECTED, expected_checkout=mission.topic)
    assert on_topic["branch_matches_target"] is True
    assert _setup_plan(mission, coord, monkeypatch) == on_topic
    assert _check_prerequisites(mission, coord, monkeypatch) == on_topic


def test_explicit_topology_expects_the_target_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: an explicit unprotected Mission plans on its target; both commands agree."""
    explicit = make_default_mission(tmp_path, THREE_LANES, standing_on=_UNPROTECTED, explicit="lanes")
    assert current_branch(explicit.root) == _UNPROTECTED
    expected = _expected(current=_UNPROTECTED, target=_UNPROTECTED, expected_checkout=_UNPROTECTED)
    assert _setup_plan(explicit, explicit.root, monkeypatch) == expected
    assert _check_prerequisites(explicit, explicit.root, monkeypatch) == expected


def test_protected_single_branch_mint_expects_the_minted_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5100: an explicit ``single_branch`` Mission on protected ``main`` plans on its minted branch; both commands agree."""
    minted = make_default_mission(tmp_path, THREE_LANES, standing_on="main", explicit="single_branch")
    assert minted.topic and minted.topic != "main"
    assert current_branch(minted.root) == minted.topic
    expected = _expected(current=minted.topic, target="main", expected_checkout=minted.topic)
    assert expected["branch_matches_target"] is True
    assert _setup_plan(minted, minted.root, monkeypatch) == expected
    assert _check_prerequisites(minted, minted.root, monkeypatch) == expected


@pytest.mark.parametrize("meta_text", ["{not json", json.dumps({"mission_slug": "probe"})], ids=["corrupt", "no-target"])
def test_an_unreadable_or_targetless_meta_degrades_to_a_silent_match(mission: DefaultMission, meta_text: str) -> None:
    """#3124: the verdict never reports a spurious disagreement when ``meta.json`` cannot name a target."""
    from specify_cli.cli.commands.agent.mission_branch_context import resolve_planning_checkout_verdict

    (mission.root_mission_dir / "meta.json").write_text(meta_text, encoding="utf-8")
    verdict = resolve_planning_checkout_verdict(mission.root, mission.slug, invoking_root=mission.root, fallback_branch="fallback")
    assert verdict.current_branch == mission.topic
    assert verdict.expected_checkout_branch == mission.topic
    assert verdict.target_branch == "fallback"
