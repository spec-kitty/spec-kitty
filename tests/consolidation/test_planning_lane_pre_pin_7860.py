"""#7860 review 9: the planning lane's final-state taint walk starts at the Mission base, not at the planning pin.

The squash axis diffs the landing from the target's pre-run tip, so a change committed to the
Mission branch before ``finalize-tasks`` (between the Mission base and the planning pin, or in
the pin commit itself) is part of the landing. The taint walk (``planning_lane_walk._scoped_final_walk``)
must see it: no window credits it (operator ruling R2), so it leaves the path it changed
attributed to nothing, also when a credited commit later edits, renames or moves that file.
Every test here measures the squash axis from the target tip, as production does
(``claim_inputs.build_claim``: ``excluded_window_base=inputs.target_base``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import mission_runtime
from specify_cli.consolidation import planning_lane_walk as planning_walk
from specify_cli.consolidation import reconciliation_authorship as authorship
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.consolidation.reconciliation import MergeOutcomeVerifier
from specify_cli.consolidation.reconciliation_verifier import VerifyResult, VerifyStatus
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane
from tests.consolidation.reconciliation_family import setattr_reconciliation_family
from tests.consolidation.test_planning_lane_authorship_7860 import (
    _MISSION_BRANCH,
    _PKG,
    _SAME_PATH,
    _SLUG,
    _commit,
    _commit_set,
    _git,
    _manifest,
    _ownership,
    _reader,
    _starts,
    _wp02_claim,
)

pytestmark = [pytest.mark.git_repo]

_PRE_TEXT = "".join(f"V{i} = {i}  # committed before finalize-tasks, never reviewed\n" for i in range(20))
_OTHER = "curation/pkg/other.py"
_SPEC = f"kitty-specs/{_SLUG}/spec.md"


def _pre_pin_mission(tmp_path: Path, pre_pin: dict[str, str]) -> tuple[Path, str, str]:
    """A default Mission: scaffold, *pre_pin* (committed before ``finalize-tasks``), the planning pin, WP02's claim.

    Returns ``(repo, pin, claim commit)``. The scaffold commit adds the Mission directory, so the
    Mission base (``mission_base.resolve_mission_base``, derived) is the ``main`` commit below it.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (("init", "-q", "-b", "main"), ("config", "user.email", "t@example.com"), ("config", "user.name", "Test"), ("config", "commit.gpgsign", "false")):
        _git(repo, *args)
    _commit(repo, {"README.md": "x\n"}, "init")
    _git(repo, "switch", "-qc", _MISSION_BRANCH)
    _commit(repo, {_SPEC: "# spec\n"}, "chore: create the Mission")
    _commit(repo, pre_pin, "committed to the Mission branch before finalize-tasks")
    meta = {"mission_slug": _SLUG, "target_branch": "main", "topology": "lanes_with_coord", "topology_source": "default", "mission_branch": _MISSION_BRANCH}
    pin = _commit(repo, {f"kitty-specs/{_SLUG}/meta.json": json.dumps(meta)}, "planning")
    claim = _commit(repo, {f"kitty-specs/{_SLUG}/status.events.jsonl": "{}\n"}, "chore: claim WP02")
    return repo, pin, claim


def _squash(repo: Path, coord_base: str, claim: authorship._AuthoredClaim) -> VerifyResult:
    """The squash axis measured from the target tip, as production measures it."""
    commit_set = _commit_set(repo, claim)
    assert commit_set.excluded_window_base == _git(repo, "rev-parse", "main")
    return MergeOutcomeVerifier(repo)._verify_squash_content(coord_base, commit_set)


def _credited(claim: authorship._AuthoredClaim) -> set[str]:
    return {path for path, _blob in claim.blobs}


def _assert_fails_on(result: VerifyResult, path: str) -> None:
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert {blob_path for blob_path, _blob in result.divergence.unattributable_blobs} == {path}


@pytest.mark.integration
def test_a_pre_pin_file_a_credited_commit_edits_is_not_credited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review 9 shape 1: 20 unreviewed lines committed before the pin ride a credited one-line edit."""
    repo, pin, claim_commit = _pre_pin_mission(tmp_path, {_SAME_PATH: _PRE_TEXT})
    _commit(repo, {_SAME_PATH: _PRE_TEXT + "L = 1\n", _OTHER: "O = 1\n"}, "feat(WP02): touch same.py")

    coord_base, claim = _wp02_claim(repo, pin, claim_commit, monkeypatch)

    assert _SAME_PATH not in _credited(claim) and _OTHER in _credited(claim)
    _assert_fails_on(_squash(repo, coord_base, claim), _SAME_PATH)


@pytest.mark.integration
def test_a_pre_pin_file_a_credited_commit_edits_alone_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review 9 shape 1 exactly: with nothing else credited, the squash axis has nothing to attribute and refuses."""
    repo, pin, claim_commit = _pre_pin_mission(tmp_path, {_SAME_PATH: _PRE_TEXT})
    _commit(repo, {_SAME_PATH: _PRE_TEXT + "L = 1\n"}, "feat(WP02): touch same.py")

    coord_base, claim = _wp02_claim(repo, pin, claim_commit, monkeypatch)

    assert not claim.blobs and not claim.deletions
    assert _squash(repo, coord_base, claim).status is VerifyStatus.REFUSE


@pytest.mark.integration
def test_a_pre_pin_file_a_credited_commit_renames_is_not_credited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review 9 shape 2: a 100% rename of a pre-pin owned file shows no content in the review diff."""
    repo, pin, claim_commit = _pre_pin_mission(tmp_path, {"curation/pkg/pre.py": _PRE_TEXT})
    _git(repo, "mv", "curation/pkg/pre.py", "curation/pkg/moved.py")
    _commit(repo, {_OTHER: "O = 1\n"}, "feat(WP02): move pre.py")

    coord_base, claim = _wp02_claim(repo, pin, claim_commit, monkeypatch)

    assert "curation/pkg/moved.py" not in _credited(claim)
    _assert_fails_on(_squash(repo, coord_base, claim), "curation/pkg/moved.py")


@pytest.mark.integration
def test_a_pre_pin_non_owned_file_renamed_into_scope_is_not_credited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review 9 shape 3: a pre-pin file outside every ``owned_files`` moved into scope by a credited commit."""
    repo, pin, claim_commit = _pre_pin_mission(tmp_path, {"elsewhere/x.py": _PRE_TEXT})
    (repo / "curation/pkg").mkdir(parents=True, exist_ok=True)
    _git(repo, "mv", "elsewhere/x.py", "curation/pkg/x.py")
    _commit(repo, {_OTHER: "O = 1\n"}, "feat(WP02): move x.py in")

    coord_base, claim = _wp02_claim(repo, pin, claim_commit, monkeypatch)

    assert "curation/pkg/x.py" not in _credited(claim)
    _assert_fails_on(_squash(repo, coord_base, claim), "curation/pkg/x.py")


@pytest.mark.integration
def test_a_change_in_the_planning_pin_commit_itself_is_not_credited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The pin commit is walked too: an owned file it adds stays un-attributed under a later credited edit."""
    repo, pin, claim_commit = _pre_pin_mission(tmp_path, {_SPEC: "# spec\n\nmore\n"})
    _git(repo, "reset", "-q", "--hard", f"{pin}^1")
    meta = {"mission_slug": _SLUG, "target_branch": "main", "topology": "lanes_with_coord", "topology_source": "default", "mission_branch": _MISSION_BRANCH}
    pin = _commit(repo, {f"kitty-specs/{_SLUG}/meta.json": json.dumps(meta), _SAME_PATH: _PRE_TEXT}, "planning, with code in it")
    claim_commit = _commit(repo, {f"kitty-specs/{_SLUG}/status.events.jsonl": "{}\n"}, "chore: claim WP02")
    _commit(repo, {_SAME_PATH: _PRE_TEXT + "L = 1\n", _OTHER: "O = 1\n"}, "feat(WP02): touch same.py")

    coord_base, claim = _wp02_claim(repo, pin, claim_commit, monkeypatch)

    assert _SAME_PATH not in _credited(claim)
    _assert_fails_on(_squash(repo, coord_base, claim), _SAME_PATH)


@pytest.mark.integration
def test_pre_pin_bookkeeping_only_still_lands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The control: a normal default Mission commits only spec, plan and tasks before the pin, and its owned change lands."""
    repo, pin, claim_commit = _pre_pin_mission(tmp_path, {f"kitty-specs/{_SLUG}/plan.md": "# plan\n", f"kitty-specs/{_SLUG}/tasks.md": "# tasks\n"})
    late = _commit(repo, {_SAME_PATH: "S = 1\n", _OTHER: "O = 1\n"}, "feat(WP02): its own change")

    coord_base, claim = _wp02_claim(repo, pin, claim_commit, monkeypatch)

    assert (_SAME_PATH, _git(repo, "rev-parse", f"{late}:{_SAME_PATH}")) in claim.blobs
    assert _squash(repo, coord_base, claim).status is VerifyStatus.PASS


def _scoped_lane(repo: Path, pin: str, claim_commit: str, monkeypatch: pytest.MonkeyPatch) -> tuple[ExecutionLane, str]:
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_PKG,)})
    _starts(monkeypatch, {"WP02": claim_commit})
    return ExecutionLane(PLANNING_LANE_ID, ("WP02",), (_PKG,), (), (), 0), _git(repo, "rev-parse", _MISSION_BRANCH)


def _walk(repo: Path, pin: str, lane: ExecutionLane, coord_base: str, mission_base: str | None) -> planning_walk._LaneAuthorshipWalk:
    manifest = _manifest(pin=pin)
    manifest.lanes = [lane]
    return planning_walk._planning_walk(repo, manifest, lane, {"WP02": {"lane": "approved"}}, coord_base, None, None, mission_base)


@pytest.mark.integration
def test_the_scoped_walk_reads_its_taint_spine_from_the_mission_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The credit spine keeps the pin; the taint spine runs from the Mission base and holds the pin and every commit below it."""
    repo, pin, claim_commit = _pre_pin_mission(tmp_path, {_SAME_PATH: _PRE_TEXT})
    late = _commit(repo, {_OTHER: "O = 1\n"}, "feat(WP02)")
    lane, coord_base = _scoped_lane(repo, pin, claim_commit, monkeypatch)
    main = _git(repo, "rev-parse", "main")

    walk = _walk(repo, pin, lane, coord_base, main)

    assert walk.base == pin and walk.scope is not None and walk.spine == [late]
    assert walk.first_parent == _git(repo, "rev-list", "--first-parent", f"{main}..{coord_base}").split()
    assert pin in walk.first_parent


@pytest.mark.integration
@pytest.mark.parametrize("cause", ["unresolved", "not_below_the_pin", "unreadable"])
def test_a_taint_spine_that_cannot_be_read_authors_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cause: str) -> None:
    """Fail closed: no Mission base, one that is not below the pin, or an unreadable range credits nothing."""
    repo, pin, claim_commit = _pre_pin_mission(tmp_path, {f"kitty-specs/{_SLUG}/plan.md": "# plan\n"})
    _commit(repo, {_OTHER: "O = 1\n"}, "feat(WP02)")
    lane, coord_base = _scoped_lane(repo, pin, claim_commit, monkeypatch)
    mission_base: str | None = {"unresolved": None, "not_below_the_pin": coord_base, "unreadable": _git(repo, "rev-parse", "main")}[cause]
    if cause == "unreadable":

        def _unreadable(*_args: object) -> list[str]:
            raise GitProbeError("boom")

        setattr_reconciliation_family(monkeypatch, "first_parent_commits_in_range", _unreadable)

    walk = _walk(repo, pin, lane, coord_base, mission_base)

    assert walk.scope is None and walk.whole is None and walk.base == coord_base


@pytest.mark.integration
def test_the_claim_without_a_mission_base_credits_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``_collect_authored`` with no Mission base (``mission_base`` unavailable) leaves the planning lane authoring nothing."""
    repo, pin, claim_commit = _pre_pin_mission(tmp_path, {f"kitty-specs/{_SLUG}/plan.md": "# plan\n"})
    late = _commit(repo, {_OTHER: "O = 1\n"}, "feat(WP02)")
    lane, coord_base = _scoped_lane(repo, pin, claim_commit, monkeypatch)
    manifest = _manifest(pin=pin)
    manifest.lanes = [lane]

    claim = authorship._collect_authored(repo, manifest, {"WP02": {"lane": "approved"}}, coord_base, None, canceled_lane_commits=frozenset(), mission_base=None)

    assert late not in claim.shas and not claim.blobs and not claim.deletions
