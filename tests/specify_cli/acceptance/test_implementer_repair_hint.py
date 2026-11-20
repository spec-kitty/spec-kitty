"""The missing-implementer refusal names only a command that works, and running it clears the refusal (#5781).

Before #5781 the strict accept gate printed ``move-task <WP> --to <current lane> --agent <name>``.
No lane's ``allowed_targets()`` contains itself, so that command could never succeed. The repair
is now derived from the state machine (``review_roles.implementer_claim_target``): for each lane
from which an implementing claim is legal, this test RUNS the printed command, as printed, against
a real git Mission, and checks the refusal is gone. For every other lane it checks that no
command is printed.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys

import pytest

from specify_cli.acceptance import collect_feature_summary
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.models import TransitionRequest
from tests.integration.coord_topology_fixture import FlatTopologyContext

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_WP = "WP01"
#: A generic placeholder actor: its moves are never an implementing claim (``review_roles``).
_GENERIC = "user"
_COMMAND = re.compile(r"`(spec-kitty [^`]+)`")


def _reset_to_planned(ctx: FlatTopologyContext) -> None:
    seed = {
        "event_id": "01M04SEEDPLANNEDGENESIS001",
        "mission_slug": ctx.slug,
        "wp_id": _WP,
        "from_lane": "genesis",
        "to_lane": "planned",
        "at": "2026-01-01T00:00:00+00:00",
        "actor": "finalize-tasks",
        "force": False,
        "execution_mode": "direct_repo",
    }
    ctx.status_events_path.write_text(json.dumps(seed) + "\n", encoding="utf-8")


def _drive(ctx: FlatTopologyContext, *hops: tuple[str, bool]) -> None:
    for to_lane, force in hops:
        emit_status_transition(
            TransitionRequest(
                feature_dir=ctx.primary_feature_dir,
                mission_slug=ctx.slug,
                wp_id=_WP,
                to_lane=to_lane,
                actor=_GENERIC,
                force=force,
                reason="fixture" if force else None,
                workspace_context="direct_repo:." if to_lane == "in_progress" else None,
            )
        )


def _commit(ctx: FlatTopologyContext) -> None:
    subprocess.run(["git", "-C", str(ctx.repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(ctx.repo), "commit", "-qm", "fixture state", "--allow-empty"], check=True, capture_output=True)


def _issue(ctx: FlatTopologyContext) -> str | None:
    summary = collect_feature_summary(ctx.repo, ctx.slug, strict_metadata=True, mutate_matrix=False)
    issues = [issue for issue in summary.metadata_issues if issue.startswith(f"{_WP}: missing agent")]
    assert len(issues) <= 1
    return issues[0] if issues else None


# lane -> the hops that reach it with no implementing claim on the log
_REPAIRABLE = {
    "planned": (),
    "claimed": (("claimed", False),),
    "blocked": (("blocked", False),),
}
_UNREPAIRABLE = {
    "in_progress": (("claimed", False), ("in_progress", False)),
    "for_review": (("for_review", True),),
    "in_review": (("in_review", True),),
    "approved": (("approved", True),),
    "done": (("done", True),),
}


@pytest.mark.parametrize("lane", sorted(_REPAIRABLE))
def test_the_printed_repair_runs_and_clears_the_refusal(flat_topology_mission: FlatTopologyContext, lane: str) -> None:
    ctx = flat_topology_mission
    _reset_to_planned(ctx)
    _drive(ctx, *_REPAIRABLE[lane])
    _commit(ctx)

    issue = _issue(ctx)
    assert issue is not None, f"a {lane} WP with no implementing claim must be refused"
    match = _COMMAND.search(issue)
    assert match is not None, issue
    argv = shlex.split(match.group(1).replace("<name>", "claude::python-pedro"))
    assert argv[0] == "spec-kitty"

    result = subprocess.run([sys.executable, "-m", "specify_cli", *argv[1:]], cwd=ctx.repo, capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _issue(ctx) is None


@pytest.mark.parametrize("lane", sorted(_UNREPAIRABLE))
def test_no_command_is_printed_where_none_is_legal(flat_topology_mission: FlatTopologyContext, lane: str) -> None:
    ctx = flat_topology_mission
    _reset_to_planned(ctx)
    _drive(ctx, *_UNREPAIRABLE[lane])
    _commit(ctx)

    issue = _issue(ctx)

    assert issue is not None, f"a {lane} WP with no implementing claim must be refused"
    assert _COMMAND.search(issue) is None, issue
    assert f"--to {lane}" not in issue
