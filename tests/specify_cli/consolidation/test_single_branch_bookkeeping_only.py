"""Unprotected single_branch consolidate is bookkeeping-only (#5100 WP04 T020).

``contracts/single-branch-execution.md``'s consolidate table: for an
unprotected target (``mission_branch == target_branch``), consolidate lands
no git merge and deletes no branch. Drives the REAL executor phase functions
(``_phase_merge_lanes``, ``_phase_mission_to_target``,
``_delete_mission_branch``, ``_run_has_code_wps``) against a minimal but
real git repo -- the established ``_MergeRunState``-construction pattern this
test suite already uses (``tests/consolidation/test_coordination_flatten_on_branch_delete.py``).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from specify_cli.consolidation import executor as ex
from specify_cli.consolidation.state import ConsolidationState
from specify_cli.consolidation import (
    phase_bookkeeping,
    phase_teardown,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_ID = "01BOOKKEEPINGONLYMISSION01"
_SLUG = "single-branch-bookkeeping-only"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def _branch_exists(repo: Path, branch: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", f"refs/heads/{branch}"],
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )


@pytest.fixture
def repo_root_repo(tmp_path: Path) -> Path:
    """A real git repo on the unprotected target branch, mirroring a
    single_branch mission with ONE repo-root lane holding a real CODE WP --
    everything already lives directly on the target, ``trunk``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "trunk")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Spec Kitty Test")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "seed")

    feature_dir = repo / "kitty-specs" / _SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mid8": _MISSION_ID[:8].lower(),
                "mission_slug": _SLUG,
                "topology": "single_branch",
                "target_branch": "trunk",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks" / "WP01-test.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Code change\nexecution_mode: code_change\nowned_files:\n- src/**\n---\n\nBody.\n",
        encoding="utf-8",
    )
    (repo / "src").mkdir()
    (repo / "src" / "impl.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "feat: WP01 implementation")
    return repo


def _repo_root_lanes_manifest() -> SimpleNamespace:
    """``mission_branch == target_branch`` -- the unprotected bookkeeping-
    only shape (contracts/single-branch-execution.md)."""
    return SimpleNamespace(
        mission_slug=_SLUG,
        target_branch="trunk",
        mission_branch="trunk",
        lanes=[SimpleNamespace(lane_id="lane-planning", wp_ids=["WP01"])],
    )


def _build_run(repo: Path, lanes_manifest: SimpleNamespace, *, planning_artifact_only: bool = True) -> ex._MergeRunState:
    feature_dir = repo / "kitty-specs" / _SLUG
    state = ConsolidationState(
        mission_id=_MISSION_ID,
        mission_slug=_SLUG,
        target_branch="trunk",
        wp_order=["WP01"],
    )
    return ex._MergeRunState(
        main_repo=repo,
        mission_slug=_SLUG,
        canonical_id=_MISSION_ID,
        canonical_mission_id=_MISSION_ID,
        feature_dir=feature_dir,
        target_feature_dir=feature_dir,
        lanes_manifest=lanes_manifest,
        all_wp_ids=["WP01"],
        push=False,
        delete_branch=True,
        remove_worktree=True,
        strategy=ex.MergeStrategy.SQUASH,
        assume_yes=True,
        planning_artifact_only=planning_artifact_only,
        state=state,
        is_resume=False,
        baseline_mission_id=_MISSION_ID,
    )


# ---------------------------------------------------------------------------
# _delete_mission_branch: the target-branch-deletion safety guard
# ---------------------------------------------------------------------------


def test_delete_mission_branch_never_deletes_the_target_branch(repo_root_repo: Path) -> None:
    run = _build_run(repo_root_repo, _repo_root_lanes_manifest())

    result = phase_teardown._delete_mission_branch(run)

    assert result is True
    assert _branch_exists(repo_root_repo, "trunk"), "the target branch must survive a bookkeeping-only consolidate"


def test_delete_mission_branch_control_still_deletes_a_real_mission_branch(repo_root_repo: Path) -> None:
    """Control: a genuinely distinct mission branch is still deleted."""
    _git(repo_root_repo, "branch", "kitty/mission-distinct")
    manifest = SimpleNamespace(
        mission_slug=_SLUG,
        target_branch="trunk",
        mission_branch="kitty/mission-distinct",
        lanes=[SimpleNamespace(lane_id="lane-a", wp_ids=["WP01"])],
    )
    run = _build_run(repo_root_repo, manifest, planning_artifact_only=False)

    result = phase_teardown._delete_mission_branch(run)

    assert result is True
    assert not _branch_exists(repo_root_repo, "kitty/mission-distinct")


# ---------------------------------------------------------------------------
# _phase_mission_to_target: no-op when mission_branch == target_branch
# ---------------------------------------------------------------------------


def test_phase_mission_to_target_is_a_noop_for_bookkeeping_only(repo_root_repo: Path) -> None:
    """Characterization (review cycle-1 nit 5): ``planning_artifact_only``
    defaults to ``True`` in :func:`_build_run`, so the OLD (pre-cycle-2)
    ``if run.planning_artifact_only: return`` gate would ALSO have skipped
    here -- this alone does not discriminate the NEW same-branch check.
    ``test_phase_mission_to_target_is_a_noop_even_when_not_lane_based_
    planning_artifact_only`` below isolates the new condition specifically."""
    run = _build_run(repo_root_repo, _repo_root_lanes_manifest())

    with patch("specify_cli.lanes.consolidation.integrate_mission_into_target") as mock_integrate:
        ex._phase_mission_to_target(run)

    mock_integrate.assert_not_called()


def test_phase_mission_to_target_is_a_noop_even_when_not_lane_based_planning_artifact_only(repo_root_repo: Path) -> None:
    """Discriminating (review cycle-1 nit 5): ``planning_artifact_only=False``
    here, so the OLD gate (``if run.planning_artifact_only: return``) would
    NOT have skipped -- only the NEW ``mission_branch == target_branch``
    check added ahead of it does. Proves the new check is the one actually
    doing the work for the bookkeeping-only case, not a redundant no-op
    beside the pre-existing lane-based gate."""
    run = _build_run(repo_root_repo, _repo_root_lanes_manifest(), planning_artifact_only=False)

    with patch("specify_cli.lanes.consolidation.integrate_mission_into_target") as mock_integrate:
        ex._phase_mission_to_target(run)

    mock_integrate.assert_not_called()


def test_phase_mission_to_target_control_still_merges_a_protected_target(repo_root_repo: Path) -> None:
    """Control: a genuine mission_branch != target_branch still runs the
    real merge phase (this WP does not touch the protected-target case,
    WP08/IC-05 -- this only proves the new gate does not over-skip)."""
    manifest = SimpleNamespace(
        mission_slug=_SLUG,
        target_branch="trunk",
        mission_branch="kitty/mission-distinct",
        lanes=[SimpleNamespace(lane_id="lane-a", wp_ids=["WP01"])],
    )
    run = _build_run(repo_root_repo, manifest, planning_artifact_only=False)

    with patch("specify_cli.lanes.consolidation.integrate_mission_into_target") as mock_integrate:
        mock_integrate.return_value = SimpleNamespace(success=True, commit=None)
        ex._phase_mission_to_target(run)

    mock_integrate.assert_called_once()


# ---------------------------------------------------------------------------
# _phase_merge_lanes: the repo-root lane is skipped, never merged
# ---------------------------------------------------------------------------


def test_phase_merge_lanes_skips_the_repo_root_lane(repo_root_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Characterization (review cycle-1 nit 5): ``planning_artifact_only``
    defaults to ``True``, so the OLD gated condition (``run.
    planning_artifact_only and is_planning_lane(lane)``) would ALSO have
    skipped here -- ``test_phase_merge_lanes_skips_the_repo_root_lane_even_
    when_not_lane_based_planning_artifact_only`` below isolates the new,
    unconditional form specifically."""
    run = _build_run(repo_root_repo, _repo_root_lanes_manifest())

    with patch("specify_cli.lanes.consolidation.consolidate_lane_into_mission") as mock_consolidate:
        ex._phase_merge_lanes(run)

    mock_consolidate.assert_not_called()
    assert "trunk" in capsys.readouterr().out


def test_phase_merge_lanes_skips_the_repo_root_lane_even_when_not_lane_based_planning_artifact_only(
    repo_root_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Discriminating (review cycle-1 nit 5): ``planning_artifact_only=False``
    here, so the OLD condition (``run.planning_artifact_only and
    is_planning_lane(lane)``) would NOT have skipped -- it would have
    attempted to consolidate the repo-root lane as an ordinary code lane.
    Only the NEW unconditional ``is_repo_root_lane(lane)`` check (#5100 T020)
    skips it -- exactly the single_branch-with-code-WPs manifest shape this
    WP exists to serve, where the repo-root lane genuinely holds real code
    but must still never be lane-merged (there is nowhere to merge it FROM;
    it already lives on the target)."""
    run = _build_run(repo_root_repo, _repo_root_lanes_manifest(), planning_artifact_only=False)

    with patch("specify_cli.lanes.consolidation.consolidate_lane_into_mission") as mock_consolidate:
        ex._phase_merge_lanes(run)

    mock_consolidate.assert_not_called()
    assert "trunk" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _run_has_code_wps: the WP-kind question sees the real code WP
# ---------------------------------------------------------------------------


def test_run_has_code_wps_true_for_a_single_branch_manifest_with_a_code_wp(repo_root_repo: Path) -> None:
    run = _build_run(repo_root_repo, _repo_root_lanes_manifest())

    assert phase_bookkeeping._run_has_code_wps(run) is True


def test_run_has_code_wps_false_for_a_genuinely_planning_only_manifest(repo_root_repo: Path) -> None:
    feature_dir = repo_root_repo / "kitty-specs" / _SLUG
    (feature_dir / "tasks" / "WP01-test.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Docs\nexecution_mode: planning_artifact\nowned_files:\n- kitty-specs/**\n---\n\nBody.\n",
        encoding="utf-8",
    )
    _git(repo_root_repo, "add", "-A")
    _git(repo_root_repo, "commit", "-q", "-m", "convert WP01 to planning_artifact")
    run = _build_run(repo_root_repo, _repo_root_lanes_manifest())

    assert phase_bookkeeping._run_has_code_wps(run) is False


def test_run_has_code_wps_false_for_a_legacy_wp_with_no_execution_mode(repo_root_repo: Path) -> None:
    """Review cycle-2 fix (issue 2): a WP file with NO ``execution_mode`` at
    all (legacy shape) must NOT flip a lane-planning-only manifest into "has
    code" -- ``infer_execution_mode`` DEFAULTS an ambiguous, signal-free body
    to ``code_change``, which the prior ``entry.metadata.execution_mode or
    WorkProductKind.CODE_CHANGE`` wrongly trusted as real code (the exact
    shape of ``test_merge_lane_planning_data_loss.py::
    test_planning_only_bookkeeping_reaches_target_branch``'s WP fixtures --
    no ``execution_mode``, a plain "Body." with no path/signal words)."""
    feature_dir = repo_root_repo / "kitty-specs" / _SLUG
    (feature_dir / "tasks" / "WP01-test.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Untyped legacy WP\nagent: researcher-ryan\ndependencies: []\n---\n\nBody.\n",
        encoding="utf-8",
    )
    _git(repo_root_repo, "add", "-A")
    _git(repo_root_repo, "commit", "-q", "-m", "convert WP01 to an untyped legacy WP")
    run = _build_run(repo_root_repo, _repo_root_lanes_manifest())

    assert phase_bookkeeping._run_has_code_wps(run) is False


def test_run_has_code_wps_true_for_a_legacy_lanes_mission_with_a_body_inferred_code_wp(repo_root_repo: Path) -> None:
    """Review cycle-3 fix (issue 1): the reviewer's fixture. A LANES-topology
    mission with a real, non-repo-root code lane (``lane-a``) holding WP01,
    whose frontmatter has NO ``execution_mode`` but whose body genuinely
    evidences code (``src/parser.py`` / ``tests/test_parser.py``). This
    normalizes to ``code_change`` / ``mode_source == "inferred_legacy"`` --
    the SAME shape the cycle-2 fix's frontmatter-only filter wrongly
    excluded, over-correcting past the untyped-bare-default case above. The
    lane-shape floor (``has_code_lanes`` -- a real code lane always means
    code) must make this True regardless of that per-WP ambiguity."""
    feature_dir = repo_root_repo / "kitty-specs" / _SLUG
    (feature_dir / "tasks" / "WP01-test.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Parser\nagent: researcher-ryan\ndependencies: []\n---\n\nImplement `src/parser.py` and add `tests/test_parser.py`.\n",
        encoding="utf-8",
    )
    _git(repo_root_repo, "add", "-A")
    _git(repo_root_repo, "commit", "-q", "-m", "convert WP01 to a body-inferred legacy code WP")
    manifest = SimpleNamespace(
        mission_slug=_SLUG,
        target_branch="trunk",
        mission_branch="kitty/mission-legacy-lanes",
        lanes=[SimpleNamespace(lane_id="lane-a", wp_ids=["WP01"])],
    )
    run = _build_run(repo_root_repo, manifest, planning_artifact_only=False)

    assert phase_bookkeeping._run_has_code_wps(run) is True


# ---------------------------------------------------------------------------
# --skip-lanes control (T020): the synthesized no-lane manifest is the SAME
# repo-root / mission_branch==target_branch shape this WP's guards key on --
# it must keep working, unaffected.
# ---------------------------------------------------------------------------


def test_skip_lanes_synthesized_manifest_is_unaffected_by_the_wp04_guards(repo_root_repo: Path) -> None:
    """``_synthesize_no_lane_manifest`` (T021/FR-012, ``--skip-lanes``) builds
    a manifest with the SAME shape this WP's guards key on: one
    ``PLANNING_LANE_ID`` lane, ``mission_branch == target_branch``. Confirm
    the three WP04 guards (``_delete_mission_branch``,
    ``_phase_mission_to_target``, ``_run_has_code_wps``) all still resolve
    sanely against it: the target branch is never deleted, the mission-to-
    target phase is correctly a no-op (nothing to merge — the WPs already
    live on the target), and the WP-kind question reflects this mission's
    real, EXPLICITLY-typed code WP -- none of this WP's changes regress
    ``--skip-lanes``."""
    from specify_cli.consolidation.executor import _synthesize_no_lane_manifest
    from specify_cli.status.emit import emit_status_transition
    from specify_cli.status.models import TransitionRequest

    status_feature_dir = repo_root_repo / "kitty-specs" / _SLUG
    # ``_synthesize_no_lane_manifest`` reads its WP ids off the REDUCED status
    # snapshot, never off ``lanes.json`` (there is none, by definition, under
    # ``--skip-lanes``) -- seed the one WP it must see.
    emit_status_transition(
        TransitionRequest(
            feature_dir=status_feature_dir,
            mission_slug=_SLUG,
            wp_id="WP01",
            to_lane="planned",
            actor="seed",
            force=True,
            reason="seed",
        )
    )
    manifest = _synthesize_no_lane_manifest(
        main_repo=repo_root_repo,
        mission_slug=_SLUG,
        status_feature_dir=status_feature_dir,
        primary_meta_dir=status_feature_dir,
        target_override=None,
    )

    assert manifest.mission_branch == manifest.target_branch == "trunk"
    assert manifest.lanes[0].lane_id == "lane-planning"

    run = _build_run(repo_root_repo, manifest)

    with patch("specify_cli.lanes.consolidation.integrate_mission_into_target") as mock_integrate:
        ex._phase_mission_to_target(run)
    mock_integrate.assert_not_called()

    result = phase_teardown._delete_mission_branch(run)
    assert result is True
    assert _branch_exists(repo_root_repo, "trunk")

    assert phase_bookkeeping._run_has_code_wps(run) is True
