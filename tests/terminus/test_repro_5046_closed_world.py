"""Red-first real-CLI reproduction: closed-world check on mixed lanes (FR-013).

Mission ``mixed-lane-authorship-soundness-01M3M7Y0`` (spec.md FR-013, operator
decision ``01M3NR7XAJGSJCK5YP937KT91H``, ADR
``docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md``).

A mixed lane (approved WP01 + canceled WP02) whose every WP work window
resolved, but which carries a non-merge content commit that lies in NO WP's
window — a straggler landed on the lane after the cancel — shipped that
commit at exit 0 before the fix (the pre-PR squad finding). No governed WP
owns it, so consolidation must REFUSE, naming the lane, the commit and the
path, and restore the target.

Driven through the REAL ``spec-kitty consolidate`` CLI
(:func:`tests.terminus.conftest.run_terminus`).
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

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_STRAGGLER_PATH = "src/pkg/straggler.py"
_REFUSE_HEADER = "Reconciliation refused (fail-closed)"


def _collapse(text: str) -> str:
    return " ".join(text.replace("`", "").split())


def test_commit_outside_every_window_on_mixed_lane_is_refused(tmp_path: Path) -> None:
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=(),
        stamp_attribution=True,
        mid8="01M5046V",
    )
    lane_branch = mission.lane_branches["WP02"]

    # A straggler: a real content commit on the lane AFTER every WP window closed.
    git(mission.repo, "checkout", "-q", lane_branch)
    straggler = mission.repo / _STRAGGLER_PATH
    straggler.parent.mkdir(parents=True, exist_ok=True)
    straggler.write_text("STRAGGLER = 'no governed WP owns this'\n", encoding="utf-8")
    git(mission.repo, "add", _STRAGGLER_PATH)
    git(mission.repo, "commit", "-qm", "straggler after the cancel")
    straggler_sha = git_rev(mission.repo, "HEAD")
    git(mission.repo, "checkout", "-q", mission.target_branch)

    pre_sha = mission.rev(mission.target_branch)
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    flat = _collapse(result.stdout + "\n" + result.stderr)

    assert result.returncode != 0, f"a commit outside every WP window on a mixed lane must not ship at exit 0:\n{flat}"
    idx = flat.find(_REFUSE_HEADER)
    assert idx != -1, f"expected the REFUSE verdict:\n{flat}"
    verdict = flat[idx:]
    assert "lane-a" in verdict, f"REFUSE must name the lane:\n{verdict}"
    assert straggler_sha[:10] in verdict, f"REFUSE must name the commit {straggler_sha[:10]}:\n{verdict}"
    assert f"'{_STRAGGLER_PATH}'" in verdict, f"REFUSE must name the path:\n{verdict}"
    assert "--attest-canceled-superseded WP02" in verdict, f"REFUSE must name the override flag:\n{verdict}"
    assert mission.rev(mission.target_branch) == pre_sha, "REFUSE must restore the target"


def _plant_straggler(mission: CoordMission, path: str) -> str:
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


def test_attestation_is_bounded_by_its_own_lane_head_stamp(tmp_path: Path) -> None:
    """FR-012 x FR-013 (review MAJOR), through the production recording path: the
    attestation clears the straggler it covers; a straggler committed after it
    still REFUSEs."""
    mission = build_coord_mission_mixed_lane_canceled(tmp_path, canceled_changes=(), stamp_attribution=True, mid8="01M5046G")
    _plant_straggler(mission, "src/pkg/straggler_one.py")
    attest = ["--attest-canceled-superseded", "WP02", "--attest-reason", "checked: straggler_one carries no canceled work"]
    first = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *attest])
    flat = _collapse(first.stdout + "\n" + first.stderr)
    assert first.returncode == 0, f"the attested straggler must be exempt:\n{flat}"


def test_straggler_after_the_attestation_still_refuses(tmp_path: Path) -> None:
    mission = build_coord_mission_mixed_lane_canceled(tmp_path, canceled_changes=(), stamp_attribution=True, mid8="01M5046H")
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
    flat = _collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode != 0, f"a straggler after the attestation must still refuse:\n{flat}"
    assert late[:10] in flat and "'src/pkg/straggler_two.py'" in flat, flat
    assert mission.rev(mission.target_branch) == pre_sha
    # Following the printed recovery (verify by hand, re-run with the attestation
    # flags) must succeed: each explicit attestation is a new operator act with a
    # fresh lane-head stamp that now covers straggler_two.
    assert "--attest-canceled-superseded WP02" in flat, flat
    attest = ["--attest-canceled-superseded", "WP02", "--attest-reason", "checked: straggler_two carries no canceled work"]
    recovered = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *attest])
    flat = _collapse(recovered.stdout + "\n" + recovered.stderr)
    assert recovered.returncode == 0, f"the printed recovery must succeed:\n{flat}"
