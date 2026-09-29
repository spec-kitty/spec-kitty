"""Red-first regression: #5100 planning-lane ref facet (FR-001, FR-002, WP02).

Pre-fix, ``lane_branch_name(slug, "lane-planning")`` silently returns
``"main"`` when no target branch is supplied, and the ``for_review`` gate
(``evaluate_for_review_gate``) predicts a ``.worktrees/<slug>-lane-planning``
path that is never created for a planning-artifact work package (planning WPs
execute directly in the repository root, per ``is_planning_lane``). Both
defects mean:

* a planning WP can never legitimately reach ``for_review`` (the gate always
  looks for a worktree that does not exist);
* a code WP that depends on the planning lane silently resolves the
  dependency's branch to ``"main"`` instead of the mission's real target
  branch, so on a repo with no ``main`` branch the dependency merge is
  skipped with a spurious warning.

This module drives the REAL entry points -- ``lane_branch_name``,
``evaluate_for_review_gate`` and ``allocate_lane_worktree`` -- against a
mission whose target branch is ``feat/x`` and which has **no ``main`` branch
at all**, so a silent fallback to ``"main"`` is caught immediately by a
missing-branch symptom rather than an accidental green.

Fixture shape adapted from ``tests/lanes/test_lane_allocation_integrity_e2e.py``
(``_build_coord_mission``) with the coordination parts dropped -- this is a
legacy/no-coordination-branch mission, mirroring
``tests/specify_cli/cli/commands/agent/test_claim_ancestry_gate.py``'s
``_write_meta_and_lanes`` shape.

Scope limit (WP02): the claim-base ref this module relies on
(``refs/spec-kitty/wp-base/<mission_slug>/<wp_id>``) is recorded here with a
raw ``git update-ref`` call, not via ``specify_cli.lanes.claim_base`` --
that module does not exist yet at RED time (T007 lands it later in this same
WP), and importing a not-yet-existing symbol at module top would turn a RED
run into a collection-time ``ImportError`` rather than an assertion failure.
The raw call reproduces the documented ref contract
(``contracts/single-branch-execution.md``, "Claim base and for_review")
byte-for-byte.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import specify_cli.lanes.worktree_allocator as worktree_allocator_module
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.for_review_gate import evaluate_for_review_gate
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from tests.utils import _seed_canonical_wp_state, write_wp

pytestmark = [pytest.mark.regression, pytest.mark.git_repo, pytest.mark.integration]

_TARGET_BRANCH = "feat/x"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(repo: Path) -> None:
    """Initialize a repo checked out on ``_TARGET_BRANCH`` -- deliberately NO
    ``main`` branch, so a silent fallback to ``"main"`` fails loudly (missing
    branch) instead of quietly succeeding against a same-content branch."""
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", _TARGET_BRANCH)
    _git(repo, "config", "user.email", "wp02-5100@example.invalid")
    _git(repo, "config", "user.name", "WP02 Regression")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")


def _write_meta(feature_dir: Path, mission_slug: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "mission_id": "01ISSUE5100PLANNINGLANEXX",
        "mission_slug": mission_slug,
        "mid8": "01ISSUE5",
        "mission_type": "software-dev",
        "target_branch": _TARGET_BRANCH,
        "created_at": "2026-09-28T00:00:00+00:00",
        "friendly_name": "#5100 planning-lane ref fixture",
        # Deliberately no "coordination_branch": this is a legacy/no-coord
        # mission, matching test_claim_ancestry_gate.py's fixture shape.
    }
    (feature_dir / "meta.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _manifest(mission_dirname: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=mission_dirname,
        mission_id="01ISSUE5100PLANNINGLANEXX",
        mission_branch=f"kitty/mission-{mission_dirname}",
        target_branch=_TARGET_BRANCH,
        lanes=[
            ExecutionLane(
                lane_id=PLANNING_LANE_ID,
                wp_ids=("WP01",),
                write_scope=("kitty-specs/**",),
                predicted_surfaces=("planning",),
                depends_on_lanes=(),
                parallel_group=0,
            ),
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP02",),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(PLANNING_LANE_ID,),
                parallel_group=1,
            ),
        ],
        computed_at="2026-09-28T00:00:00Z",
        computed_from="test",
        planning_artifact_wps=["WP01"],
    )


def _build_mission(tmp_path: Path, tag: str) -> tuple[Path, str, Path, LanesManifest]:
    mission_dirname = f"issue-5100-{tag}"
    repo = tmp_path / mission_dirname / "repo"
    _init_repo(repo)

    feature_dir = repo / "kitty-specs" / mission_dirname
    _write_meta(feature_dir, mission_dirname)

    write_wp(repo, mission_dirname, "planned", "WP01")
    write_wp(repo, mission_dirname, "planned", "WP02")

    manifest = _manifest(mission_dirname)
    write_lanes_json(feature_dir, manifest)

    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "planning: seed WP01/WP02 + lanes.json")
    return repo, mission_dirname, feature_dir, manifest


def _claim_base_ref(mission_slug: str, wp_id: str) -> str:
    """The documented claim-base ref contract (T007), reproduced verbatim."""
    return f"refs/spec-kitty/wp-base/{mission_slug}/{wp_id}"


def _record_claim_base(repo: Path, mission_slug: str, wp_id: str) -> str:
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", _claim_base_ref(mission_slug, wp_id), head)
    return head


def _forbid_planning_worktree_predict(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if anything asks the allocator to predict a worktree for
    the planning lane -- the repo-root lane has no worktree to predict."""
    original = worktree_allocator_module.predict_lane_worktree

    def _guarded(repo_root: Path, mission_slug: str, lane_id: str) -> tuple[Path, str]:
        if lane_id == PLANNING_LANE_ID:
            raise AssertionError("predict_lane_worktree must never be asked to resolve the planning lane")
        return original(repo_root, mission_slug, lane_id)

    monkeypatch.setattr(worktree_allocator_module, "predict_lane_worktree", _guarded)


def test_planning_lane_for_review_gate_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenarios 1, 2, 4: claim -> refused (no commit) -> refused (status-only
    commit) -> passes (real implementation commit) -- with no ``.worktrees/
    ...-lane-planning`` path ever touched."""
    _forbid_planning_worktree_predict(monkeypatch)

    repo, mission_dirname, feature_dir, _manifest_obj = _build_mission(tmp_path, "lifecycle")

    # Claim WP01: record the claim-base ref and mark it in_progress.
    _seed_canonical_wp_state(
        repo,
        mission_dirname,
        "WP01",
        "in_progress",
        actor="claude",
        assignee="Owner",
        shell_pid="1234",
        timestamp="2026-09-28T01:00:00Z",
    )
    _record_claim_base(repo, mission_dirname, "WP01")

    # Scenario 2 (control): no commit since claim -> still refused.
    control = evaluate_for_review_gate(repo, mission_dirname, "WP01")
    assert control.passed is False, control.reason

    # Scenario 4: a status-only commit (WP02 claimed) must NOT satisfy the gate.
    _seed_canonical_wp_state(
        repo,
        mission_dirname,
        "WP02",
        "claimed",
        actor="claude",
        assignee="Owner",
        shell_pid="1234",
        timestamp="2026-09-28T01:05:00Z",
    )
    status_events_path = feature_dir / "status.events.jsonl"
    assert status_events_path.exists()
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "status: WP02 claimed (status-only)")

    status_only = evaluate_for_review_gate(repo, mission_dirname, "WP01")
    assert status_only.passed is False, status_only.reason

    # Scenario 1: a real implementation commit (outside kitty-specs status
    # paths) satisfies the gate -- no --force needed.
    src_dir = repo / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "impl.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", "src")
    _git(repo, "commit", "-q", "-m", "feat: WP01 implementation")

    decision = evaluate_for_review_gate(repo, mission_dirname, "WP01")
    assert decision.passed is True, decision.reason

    # No worktree was ever created (or asked for) for the planning lane.
    assert not (repo / ".worktrees" / f"{mission_dirname}-{PLANNING_LANE_ID}").exists()
    worktrees_dir = repo / ".worktrees"
    if worktrees_dir.exists():
        assert not any(PLANNING_LANE_ID in child.name for child in worktrees_dir.iterdir())


def test_dependent_lane_merges_target_branch_not_main(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario 3: allocating a code lane that depends on the planning lane
    merges the mission's real target branch (``feat/x``), never ``"main"`` --
    and never warns that the dependency branch "does not resolve"."""
    repo, mission_dirname, _feature_dir, manifest = _build_mission(tmp_path, "depmerge")

    # WP01's real implementation lands directly on the target branch (the
    # repository-root checkout planning-artifact WPs execute in).
    src_dir = repo / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "planning_output.py").write_text("PLANNED = True\n", encoding="utf-8")
    _git(repo, "add", "src")
    _git(repo, "commit", "-q", "-m", "feat: WP01 implementation")

    capsys.readouterr()  # drain any setup noise
    worktree_path, _branch = allocate_lane_worktree(
        repo_root=repo,
        mission_slug=mission_dirname,
        wp_id="WP02",
        lanes_manifest=manifest,
    )
    captured = capsys.readouterr()

    assert "WARNING" not in captured.out, captured.out
    assert (worktree_path / "src" / "planning_output.py").exists()


def test_lane_branch_name_requires_target_branch_keyword() -> None:
    """Scenario 5: the planning lane's branch cannot be resolved without
    naming the target branch -- the keyword is required, not defaulted."""
    with pytest.raises(TypeError):
        lane_branch_name("some-mission", PLANNING_LANE_ID)  # type: ignore[call-arg]
