"""A content commit on a mixed lane that lies in no WP's work window is REFUSEd, unless an operator attestation recorded after it covers it.

A mixed lane (approved WP01 + canceled WP02) whose every WP work window
resolved, but which carries a non-merge content commit in NO WP's window -- a
straggler landed on the lane after the cancel -- is owned by no governed WP, so
consolidation must REFUSE, naming the lane, the commit, the path and the
override flag, and restore the target (spec FR-013, ADR
``docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md``). An
``--attest-canceled-superseded`` attestation exempts only the stragglers up to
its own ``lane_head`` stamp; a later straggler still REFUSEs.

Driven through the REAL ``spec-kitty consolidate`` CLI
(:func:`tests.terminus.conftest.run_terminus`).

Originally the #5046 closed-world reproductions (mission
mixed-lane-authorship-soundness-01M3M7Y0).

KEPT whole (#5618 part 2): this is the only end-to-end proof of the FR-013 closed world,
so it is not trimmed; it carries the ``slow`` tier marker (each replay exceeds 30 s).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.consolidation.canceled_attestation import record_canceled_superseded_attestation
from tests.terminus.conftest import (
    CoordMission,
    build_coord_mission_mixed_lane_canceled,
    git_rev,
    run_terminus,
)
from tests.terminus.conftest import _git as git
from tests.terminus.mixed_lane_support import ATTEST_FLAG, REFUSE_HEADER, collapse, verdict_block

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression, pytest.mark.slow]


def _plant_straggler(mission: CoordMission, path: str) -> str:
    """Commit real content on WP02's lane after every WP window closed; return its SHA."""
    repo = mission.repo
    git(repo, "checkout", "-q", mission.lane_branches["WP02"])
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{path}\n", encoding="utf-8")
    git(repo, "add", path)
    git(repo, "commit", "-qm", f"straggler {path}")
    sha = git_rev(repo, "HEAD")
    git(repo, "checkout", "-q", mission.target_branch)
    return sha


def test_commit_outside_every_window_on_mixed_lane_is_refused(tmp_path: Path) -> None:
    straggler_path = "src/pkg/straggler.py"
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=(),
        stamp_attribution=True,
        mid8="01M5046V",
    )
    straggler_sha = _plant_straggler(mission, straggler_path)

    pre_sha = mission.rev(mission.target_branch)
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert result.returncode != 0, f"a commit outside every WP window on a mixed lane must not ship at exit 0:\n{flat}"
    verdict = verdict_block(flat, REFUSE_HEADER)
    assert "lane-a" in verdict, f"REFUSE must name the lane:\n{verdict}"
    assert straggler_sha[:10] in verdict, f"REFUSE must name the commit {straggler_sha[:10]}:\n{verdict}"
    assert f"'{straggler_path}'" in verdict, f"REFUSE must name the path:\n{verdict}"
    assert f"{ATTEST_FLAG} WP02" in verdict, f"REFUSE must name the override flag:\n{verdict}"
    assert mission.rev(mission.target_branch) == pre_sha, "REFUSE must restore the target"


def test_straggler_after_the_attestation_still_refuses(tmp_path: Path) -> None:
    """The attestation is bounded by its own ``lane_head`` stamp: a straggler
    committed after it still REFUSEs; following the printed recovery (a fresh
    ``--attest-canceled-superseded`` run, whose new stamp covers both
    stragglers) then consolidates at exit 0.
    """
    mission = build_coord_mission_mixed_lane_canceled(tmp_path, canceled_changes=(), stamp_attribution=True, mid8="01M5046N")
    _plant_straggler(mission, "src/pkg/straggler_one.py")
    refused = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    assert refused.returncode != 0
    pre_sha = mission.rev(mission.target_branch)
    # The operator attests (production recording seam), THEN a second straggler lands.
    record_canceled_superseded_attestation(
        repo_root=mission.repo,
        feature_dir=mission.feature_dir,
        mission_slug=mission.slug,
        wp_id="WP02",
        reason="checked: straggler_one carries no canceled work",
        actor="landing-test-operator",
    )
    late = _plant_straggler(mission, "src/pkg/straggler_two.py")
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    flat = collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode != 0, f"a straggler after the attestation must still refuse:\n{flat}"
    assert late[:10] in flat and "'src/pkg/straggler_two.py'" in flat, flat
    assert mission.rev(mission.target_branch) == pre_sha
    # Following the printed recovery (verify by hand, re-run with the attestation
    # flags) must succeed: each explicit attestation is a new operator act with a
    # fresh lane-head stamp that now covers straggler_two.
    assert f"{ATTEST_FLAG} WP02" in flat, flat
    attest = [ATTEST_FLAG, "WP02", "--attest-reason", "checked: straggler_two carries no canceled work"]
    recovered = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *attest])
    flat = collapse(recovered.stdout + "\n" + recovered.stderr)
    assert recovered.returncode == 0, f"the printed recovery must succeed:\n{flat}"
