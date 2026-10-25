"""A verdict is not a pick-up: it must not clear the review claim's binding (#6630).

``agent action review --profile reviewer-renata`` records the review claim's
resolved binding. The reviewer's own verdict (``move-task --to approved`` with no
``--profile``/``--model``/``--invocation-id``) used to resolve an all-``None``
binding and stamp it as explicit-absence sentinels, which the latest-wins fold
then applied over the claim's profile. These tests drive the real ``move-task``
CLI on a seeded review claim and read the reduced snapshot and the event log.

The explicit-absence semantics for a real pick-up stay pinned in
``test_resolved_binding_reducer.py`` and ``test_resolved_binding_linkage.py``.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typer.testing import CliRunner, Result

from specify_cli.status.models import WPInnerStateDelta
from specify_cli.status.reducer import materialize
from specify_cli.status.resolved_binding import RESOLVED_PROFILE_ABSENT, ResolvedBinding
from specify_cli.status.store import read_event_stream
from tests.specify_cli.status.test_execution_mode_stamp_paths import _build_mission
from tests.utils import _seed_canonical_wp_state

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_REVIEWER_PROFILE = "reviewer-renata"
_CLAIM_BINDING_EVENT_ID = "01H66300000000000000000001"


def _seed_review_claim(repo: Path, mission_slug: str, feature_dir: Path) -> None:
    """Seed WP01 in ``in_review`` plus the review claim's resolved-binding annotation."""
    from specify_cli.status.models import InnerStateChanged
    from specify_cli.status.store import append_annotations_atomic_verified

    _seed_canonical_wp_state(repo, mission_slug, "WP01", "in_review", actor="claude", assignee="Owner", shell_pid="1234", timestamp="2026-10-23T03:16:36Z")
    delta: WPInnerStateDelta = ResolvedBinding(agent_profile=_REVIEWER_PROFILE, agent_profile_version="1.0").to_delta(role="reviewer")
    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id=_CLAIM_BINDING_EVENT_ID,
                wp_id="WP01",
                at="2026-10-23T03:16:37+00:00",
                actor="claude",
                delta=delta,
            )
        ],
    )


def _move_task(mission_slug: str, to: str, *extra: str) -> Result:
    from specify_cli.cli.commands.agent.tasks import app

    args = ["move-task", "WP01", "--to", to, "--mission", mission_slug, "--no-auto-commit", "--force", "--skip-pre-review-gate"]
    return runner.invoke(app, [*args, "--json", "--note", "Review passed", *extra], catch_exceptions=False)


def _wp_snapshot(feature_dir: Path) -> dict[str, object]:
    wp: dict[str, object] = materialize(feature_dir).work_packages["WP01"]
    return wp


def _binding_annotations_after_seed(feature_dir: Path) -> list[dict[str, object]]:
    deltas: list[dict[str, object]] = []
    for annotation in read_event_stream(feature_dir).annotations:
        if annotation.event_id == _CLAIM_BINDING_EVENT_ID:
            continue
        fields = annotation.delta.to_dict()
        if "agent_profile" in fields:
            deltas.append(fields)
    return deltas


@pytest.fixture
def review_claimed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, Path]:
    repo, mission_slug, feature_dir = _build_mission(tmp_path, "verdict-6630", topology="single_branch")
    _seed_review_claim(repo, mission_slug, feature_dir)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))
    assert _wp_snapshot(feature_dir)["agent_profile"] == _REVIEWER_PROFILE
    return mission_slug, feature_dir


@pytest.mark.parametrize("agent_flag", [(), ("--agent", "claude")], ids=["no-agent", "with-agent"])
@pytest.mark.parametrize("verdict", ["approved", "done", "canceled"])
def test_verdict_without_dispatch_flags_keeps_the_review_claim_profile(review_claimed: tuple[str, Path], verdict: str, agent_flag: tuple[str, ...]) -> None:
    mission_slug, feature_dir = review_claimed

    result = _move_task(mission_slug, verdict, *agent_flag)

    assert result.exit_code == 0, result.output
    wp = _wp_snapshot(feature_dir)
    assert wp["lane"] == verdict
    assert wp["agent_profile"] == _REVIEWER_PROFILE
    assert wp["agent_profile_version"] == "1.0"
    assert wp["role"] == "reviewer"
    assert _binding_annotations_after_seed(feature_dir) == []


def test_verdict_with_profile_records_that_profile(review_claimed: tuple[str, Path]) -> None:
    """A dispatch flag on the verdict is an explicit request to record the binding."""
    mission_slug, feature_dir = review_claimed

    result = _move_task(mission_slug, "approved", "--profile", "python-pedro")

    assert result.exit_code == 0, result.output
    assert _wp_snapshot(feature_dir)["agent_profile"] == "python-pedro"


def test_verdict_handing_the_wp_to_another_agent_records_explicit_absence(review_claimed: tuple[str, Path]) -> None:
    """The claim's profile belongs to the previous agent, so it is not carried to a new one."""
    mission_slug, feature_dir = review_claimed

    result = _move_task(mission_slug, "approved", "--agent", "codex")

    assert result.exit_code == 0, result.output
    wp = _wp_snapshot(feature_dir)
    assert wp["agent"] == "codex"
    assert wp["agent_profile"] == RESOLVED_PROFILE_ABSENT


def test_a_non_verdict_reassignment_still_records_explicit_absence(review_claimed: tuple[str, Path]) -> None:
    """Non-vacuity control: a non-verdict hop with ``--agent`` keeps the explicit-absence stamp."""
    mission_slug, feature_dir = review_claimed

    result = _move_task(mission_slug, "blocked", "--agent", "codex")

    assert result.exit_code == 0, result.output
    assert _wp_snapshot(feature_dir)["agent_profile"] == RESOLVED_PROFILE_ABSENT
