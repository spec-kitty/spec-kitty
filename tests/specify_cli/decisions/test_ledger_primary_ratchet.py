"""FR-009a ratchet: decision-ledger writes and reads stay on the PRIMARY partition.

coord-artifact-single-home-01M3V4BE WP12 (#5023). FR-009a is a ``[ratchet]``
requirement -- it pins EXISTING behaviour that must survive the FR-009
reclassification unchanged. ``decisions/service.py::_ledger_dir`` already
resolved the PRIMARY-partition dir before this WP (#4966 AC-D2); T065 only
reclassifies the TAXONOMY (``MissionArtifactKind.DECISION_LEDGER``) to match.
This test is therefore GREEN both before and after T065 -- by design, a
ratchet, not a red-first reproduction -- and is paired with the FR-009
``[build]`` rows (T064/T066) that DO flip.

Covers both a coordination-routed Mission (where a COORD partition exists to
accidentally mis-route onto) and a ``lanes`` Mission (C-008 control, where
there is no coordination worktree at all) to prove the ledger's home is
genuinely partition-derived, not an accident of topology.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import create_mission_core
from specify_cli.decisions.models import OriginFlow
from specify_cli.decisions.service import open_decision
from tests._factories import provision_test_charter
from tests._factories.coord_mission import make_coord_mission
from tests._support.git_template import clone_template

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_TOPIC_BRANCH = "topic"


def _mission_dir_and_root_for(tmp_path: Path, topology: MissionTopology) -> tuple[Path, str]:
    """Build a Mission under *topology* and return ``(repo_root, mission_dir_name)``.

    ``COORD`` uses WP02's :func:`make_coord_mission` factory (production create
    path). ``LANES`` (the C-008 coord-less control -- no coordination branch at
    all) is built directly via ``create_mission_core`` since the factory
    requires a coordination branch for every shape it produces.
    """
    if topology is MissionTopology.COORD:
        coord = make_coord_mission(tmp_path, topology, materialized=True)
        return coord.repo_root, coord.mission_dir_name
    repo = clone_template(tmp_path / "repo")
    provision_test_charter(repo)
    subprocess.run(["git", "-C", str(repo), "add", ".kittify"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "chore(fixture): provision charter"],
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "-C", str(repo), "checkout", "-b", _TOPIC_BRANCH], check=True, capture_output=True)
    result = create_mission_core(repo, "ratchet-lanes", topology=topology, target_branch=_TOPIC_BRANCH, allow_worktree_context=True)
    mission_dir_name = result.meta["mission_slug"]
    assert isinstance(mission_dir_name, str)
    return repo, mission_dir_name


@pytest.mark.parametrize("topology", [MissionTopology.COORD, MissionTopology.LANES])
def test_ledger_writes_and_reads_stay_primary(tmp_path: Path, topology: MissionTopology) -> None:
    """Open a decision through the production service; the ledger lands PRIMARY.

    ``decisions/service.py::_ledger_dir`` (≈L255-279) resolves
    ``PRIMARY_METADATA`` -- the SAME dir ``_decisions_doctor.py`` (≈L146-156)
    reads back from. Asserts both ``DM-*.md`` and ``index.json`` land under
    the repository root checkout's mission dir (the PRIMARY partition), never
    under ``.worktrees/`` (the coordination worktree), for both a
    coordination-routed and a coord-less topology.
    """
    repo_root, mission_dir_name = _mission_dir_and_root_for(tmp_path, topology)
    root_mission_dir = repo_root / "kitty-specs" / mission_dir_name

    response = open_decision(
        repo_root,
        mission_dir_name,
        origin_flow=OriginFlow.SPECIFY,
        input_key="ratchet-key",
        step_id="ratchet-key",
        question="FR-009a ratchet fixture question?",
        actor="test-fixture",
    )

    dm_path = Path(response.artifact_path)
    index_path = root_mission_dir / "decisions" / "index.json"

    # Write side: both ledger files land under the PRIMARY repo-root checkout.
    assert dm_path.exists(), f"{dm_path} was not written"
    assert index_path.exists(), f"{index_path} was not written"
    assert dm_path.is_relative_to(root_mission_dir), f"{dm_path} did not land under the PRIMARY mission dir {root_mission_dir}"
    assert ".worktrees" not in dm_path.parts, f"{dm_path} landed under a coordination worktree, not the PRIMARY checkout"
    assert ".worktrees" not in index_path.parts

    # Read side: the doctor's parallel ``_ledger_dir`` copy resolves the SAME dir.
    from specify_cli.cli.commands._decisions_doctor import _ledger_dir as _doctor_ledger_dir

    doctor_dir = _doctor_ledger_dir(repo_root, mission_dir_name)
    assert doctor_dir == root_mission_dir, f"doctor's ledger dir {doctor_dir} disagrees with the write side PRIMARY mission dir {root_mission_dir}"
