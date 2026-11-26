"""The printed recovery of ``RESOLUTION_MERGE_UNREVIEWED`` runs as printed on a protected-main coordination Mission (#5604, #7861).

The refusal's recovery block (``approved_bound._unreviewed_merge_block``) prints one send-back line per work
package (``approved_bound.move_back_command``). The docs (ADR ``2026-10-04-5`` Amendment 2026-11-26, the
orchestrator-api code table, the recovery how-to) quote that line, so it is the single authority: this test runs
it, exactly as printed, through the real CLI on the route fixture's coordination topology (a coordination branch,
target ``main``), and asserts that it exits 0, that the work package leaves ``approved``, and that ``main`` is
untouched. Real git, no in-process status write.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from specify_cli.consolidation.approved_bound import approval_stamp
from tests.terminus.approved_lane_route_support import (
    IMPLEMENTER,
    LANE_A,
    LANE_B,
    RECONCILIATION_VERIFIED,
    RESOLUTION_MERGE_UNREVIEWED,
    RESOLVED_TEXT,
    SHARED_PATH,
    Strategy,
    build_conflicting_lanes_mission,
    cli,
    consolidate,
    events,
    hand_merge,
    independent_approval,
    lane_of,
    merge_own_paths,
    output,
    show,
)
from tests.terminus.conftest import git_rev, sha_reachable

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_HARNESS_VARIABLES = ("SPEC_KITTY_NO_NAG", "SPEC_KITTY_NON_INTERACTIVE")


@pytest.fixture(autouse=True)
def _unset_harness_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _HARNESS_VARIABLES:
        monkeypatch.delenv(key, raising=False)


def _printed_move_back(text: str, wp_id: str, slug: str) -> list[str]:
    """The send-back line the refusal's recovery block printed for *wp_id* (indented, on its own line)."""
    pattern = rf"^\s*(spec-kitty agent tasks move-task {wp_id} --to \S+ --mission {re.escape(slug)})\s*$"
    found = re.search(pattern, text, re.MULTILINE)
    assert found is not None, f"no printed send-back line for {wp_id} in:\n{text}"
    return shlex.split(found.group(1))[1:]


def test_printed_move_back_runs_on_a_protected_main_coordination_mission(tmp_path: Path) -> None:
    route = build_conflicting_lanes_mission(tmp_path, "coord", mid8="01M7WMB7")
    assert route.mission.target_branch == "main" and route.mission.coord_branch != "main", "fixture: protected-main coordination topology"
    hand_merge(route, lane=LANE_B, sibling=LANE_A)
    assert lane_of(route, "WP02") == "approved", "fixture: WP02 is approved before the refusal"

    refused = cli(route, "consolidate", "--mission", route.slug, "--yes", "--strategy", "squash")
    text = output(refused)
    assert refused.returncode == 1 and RESOLUTION_MERGE_UNREVIEWED in text, text
    argv = _printed_move_back(text, "WP02", route.slug)
    assert argv[argv.index("--to") + 1] == "in_progress", f"the refusal prints the send-back to in_progress: {argv}"

    main_before = git_rev(route.repo, "main")
    coord_before = git_rev(route.repo, route.mission.coord_branch)
    moved = cli(route, *argv)

    assert moved.returncode == 0, output(moved)
    assert lane_of(route, "WP02") == "in_progress", output(moved)
    assert git_rev(route.repo, "main") == main_before, "protected main is untouched"
    assert git_rev(route.repo, route.mission.coord_branch) != coord_before, "the send-back is recorded on the coordination branch"

    # The refusal stays until a new independent approval reaches the merge: a re-run still refuses.
    code, again = consolidate(route, "squash")
    assert code != 0, again


@pytest.mark.parametrize("strategy", ["squash", "merge"])
def test_printed_recovery_lands_the_mission_on_a_protected_main_coordination_mission(tmp_path: Path, strategy: Strategy) -> None:
    """Squad-3 F2: the ``RESOLUTION_MERGE_UNREVIEWED`` recovery, followed exactly as printed, lands the Mission.

    The printed send-back (``move-task <WP> --to in_progress``), then submit for review (the resolution is
    already committed, so there is nothing more to resolve), then an independent approval whose stamp reaches
    the merge, then ``consolidate``: exit 0 with the gate's banner, the resolved text on protected ``main``.
    """
    route = build_conflicting_lanes_mission(tmp_path, "coord", mid8="01M7WF2" + strategy[0].upper())
    assert route.mission.target_branch == "main" and route.mission.coord_branch != "main", "fixture: protected-main coordination topology"
    merge = hand_merge(route, lane=LANE_B, sibling=LANE_A)
    assert SHARED_PATH in merge_own_paths(route, merge), "fixture: the hand merge carries its own content"

    refused = cli(route, "consolidate", "--mission", route.slug, "--yes", "--strategy", strategy)
    text = output(refused)
    assert refused.returncode == 1 and RESOLUTION_MERGE_UNREVIEWED in text, text
    assert f"the new approval must reach merge {merge[:7]}" in " ".join(text.split()), text

    moved = cli(route, *_printed_move_back(text, "WP02", route.slug))
    assert moved.returncode == 0, output(moved)
    submitted = cli(route, "agent", "tasks", "move-task", "WP02", "--to", "for_review", "--agent", IMPLEMENTER, "--mission", route.slug)
    assert submitted.returncode == 0, output(submitted)
    review_output, approved = independent_approval(route, "WP02")
    assert approved.returncode == 0, f"{review_output}\n{output(approved)}"
    stamp = approval_stamp(events(route), "WP02")
    assert stamp is not None and sha_reachable(route.repo, merge, stamp), "the re-approval stamp reaches the resolution merge"

    code, landed = consolidate(route, strategy)

    assert code == 0, landed
    assert RECONCILIATION_VERIFIED in landed, landed
    assert show(route.repo, "main", SHARED_PATH) == RESOLVED_TEXT
