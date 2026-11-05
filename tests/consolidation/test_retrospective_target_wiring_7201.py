"""Production wiring for #7201's resolved retrospective destination.

The defect this closes lived in a *connection*, not in a helper: the consolidate
run resolved the landing branch and never handed it to the terminus, so the
retrospective bookkeeping commit asked `safe_commit` for the stale `meta.json`
target and was refused. A suite that only drives the terminus directly (or that
stubs the teardown seam) stays green with every one of those forwards deleted, so
these tests pin the connections themselves:

* `phase_teardown._teardown_coord_worktree` → `teardown_coordination_topology`
  (the persist leg that commits before the coordination worktree is destroyed);
* `cli.commands.consolidate._run_real_merge` → `run_retrospective_postcondition`
  (the second terminus call in the same run);
* `teardown_coordination_topology` → `_persist_retrospective` → the terminus,
  asserted on the real seam rather than on a stub of it.

Each test drives the production function and asserts the resolved target reaches
the next real owner, so deleting a forward fails a test here.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from specify_cli.cli.commands import consolidate as consolidate_cmd
from specify_cli.consolidation import executor as ex
from specify_cli.consolidation import phase_teardown
from specify_cli.consolidation.state import ConsolidationState

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MISSION_ID = "01M6P3E46H9C4SES0ZXSBZ88NG"
MISSION_SLUG = f"terminus-target-wiring-{MISSION_ID[:8]}"
META_TARGET = "main"
LANDING_BRANCH = "topic-landing"


def _feature_dir(repo: Path) -> Path:
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": MISSION_ID,
                "mid8": MISSION_ID[:8].lower(),
                "mission_slug": MISSION_SLUG,
                "target_branch": META_TARGET,
            }
        ),
        encoding="utf-8",
    )
    return feature_dir


def _run_state(repo: Path, *, target_branch: str) -> ex._MergeRunState:
    """A merge run state whose *meta* target and *resolved* target differ (#7201)."""
    feature_dir = _feature_dir(repo)
    lanes_manifest = SimpleNamespace(
        target_branch=target_branch,
        mission_branch=f"kitty/mission-{MISSION_SLUG}",
        lanes=[],
    )
    return ex._MergeRunState(
        main_repo=repo,
        mission_slug=MISSION_SLUG,
        canonical_id=MISSION_ID,
        canonical_mission_id=MISSION_ID,
        feature_dir=feature_dir,
        target_feature_dir=feature_dir,
        lanes_manifest=lanes_manifest,
        all_wp_ids=["WP01"],
        push=False,
        delete_branch=True,
        remove_worktree=True,
        teardown_coordination=True,
        strategy=ex.MergeStrategy.SQUASH,
        assume_yes=True,
        planning_artifact_only=False,
        state=ConsolidationState(
            mission_id=MISSION_ID,
            mission_slug=MISSION_SLUG,
            target_branch=target_branch,
            wp_order=["WP01"],
        ),
        is_resume=False,
        baseline_mission_id=MISSION_ID,
    )


# ---------------------------------------------------------------------------
# Consolidate's teardown persist leg
# ---------------------------------------------------------------------------


def test_teardown_leg_threads_the_resolved_merge_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_teardown_coord_worktree` hands the seam the run's resolved target."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run = _run_state(repo, target_branch=LANDING_BRANCH)
    captured: dict[str, Any] = {}

    def _fake_seam(*_args: object, **kwargs: object) -> bool:
        captured.update(kwargs)
        return True

    monkeypatch.setattr(
        "specify_cli.coordination.teardown.teardown_coordination_topology",
        _fake_seam,
    )

    assert phase_teardown._teardown_coord_worktree(run) is None
    assert captured.get("destination_ref") == LANDING_BRANCH, (
        "#7201: the persist leg must commit the retrospective on the resolved merge target, not on the stale meta.json target"
    )
    assert captured.get("projection_gate") is None, "ungated run keeps the ungated seam"


# ---------------------------------------------------------------------------
# Consolidate's post-merge terminus call
# ---------------------------------------------------------------------------


def test_post_merge_call_site_threads_the_resolved_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_run_real_merge` hands the terminus the resolved target it just landed on."""
    repo = tmp_path / "repo"
    repo.mkdir()
    captured: dict[str, Any] = {}

    def _fake_merge(**_kwargs: object) -> None:
        return None

    def _fake_terminus(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(consolidate_cmd, "_run_lane_based_consolidation", _fake_merge)
    monkeypatch.setattr(consolidate_cmd, "run_retrospective_postcondition", _fake_terminus)

    consolidate_cmd._run_real_merge(
        repo,
        resolved_mission=MISSION_SLUG,
        resolved_target_branch=LANDING_BRANCH,
        resolved_strategy=ex.MergeStrategy.SQUASH,
        delete_branch=True,
        remove_worktree=True,
        push=False,
        allow_sparse_checkout=False,
        yes=True,
    )

    assert captured.get("mission_slug") == MISSION_SLUG
    assert captured.get("destination_ref") == LANDING_BRANCH, "#7201: the second terminus call in the same run must carry the same resolved target"


# ---------------------------------------------------------------------------
# The real persist seam forwards to the real terminus entry point
# ---------------------------------------------------------------------------


def test_persist_seam_forwards_the_destination_to_the_terminus(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`teardown_coordination_topology` → `_persist_retrospective` → terminus."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _feature_dir(repo)
    captured: dict[str, Any] = {}

    def _fake_terminus(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(
        "specify_cli.post_merge.retrospective_terminus.run_retrospective_postcondition",
        _fake_terminus,
    )

    from specify_cli.coordination.teardown import teardown_coordination_topology

    # An empty mid8 is a legacy / never-coordinated Mission: the destroy leg is a
    # documented no-op, so the persist leg is exercised on its own.
    assert teardown_coordination_topology(repo, MISSION_SLUG, "", destination_ref=LANDING_BRANCH) is True
    assert captured.get("destination_ref") == LANDING_BRANCH


def test_persist_seam_defaults_the_destination_to_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No destination supplied → the terminus keeps placement resolution (same fixture)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _feature_dir(repo)
    captured: dict[str, Any] = {}

    def _fake_terminus(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(
        "specify_cli.post_merge.retrospective_terminus.run_retrospective_postcondition",
        _fake_terminus,
    )

    from specify_cli.coordination.teardown import teardown_coordination_topology

    assert teardown_coordination_topology(repo, MISSION_SLUG, "") is True
    assert captured.get("destination_ref") is None
