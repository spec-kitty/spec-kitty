"""Verifier axes for the Mission base bound (#7560, WP04).

History the target lacks below the Mission base (``claim.pre_mission_*``, built by
:func:`_pre_mission_attribution`) has the standing of content already on the target on every
window axis: the closed world, the squash blob and deletion axes, the vacuous squash check and
the patch-id window. Every exemption is keyed on an exact SHA or an exact ``(path, blob)`` /
deletion, never on a patch-id, and each test has a same-fixture control. A re-lettered copy of a
pre-Mission commit (new SHA, same patch) is still judged: that is the fail-closed residual.

The small fork: ``R`` (the target) has ``src/app.py``, ``old/r.py`` and ``old/s.py``. The
upstream history ``R..B`` adds ``up/a.py``, adds ``up/x.py`` and reverts it, deletes
``old/r.py`` and ends with the overlay commit ``B`` (the Mission base). One lane cut from ``B``
holds the approved ``src/lane.py``; the Mission branch is that lane's tip.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from specify_cli.consolidation import reconciliation_verifier
from specify_cli.consolidation.git_probes import blob_id_at, patch_id_of
from specify_cli.consolidation.mission_base import MissionBase, MissionBaseProvenance, MissionBaseReason
from specify_cli.consolidation.reconciliation import (
    ApprovedWpCommitSet,
    MergeOutcomeVerifier,
    PreMissionHistory,
    VerifyStatus,
    _pre_mission_attribution,
    mission_base_note,
)
from specify_cli.lanes.compute import lane_created_branch
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from tests.consolidation.reconciliation_family import setattr_reconciliation_family

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "mission-base-verifier-01M7560V"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"
_EMPTY_PRE_MISSION: dict[str, object] = {
    "pre_mission_shas": frozenset(),
    "pre_mission_blobs": frozenset(),
    "pre_mission_deletions": frozenset(),
}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def _write(repo: Path, path: str, content: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", f"write {path}")
    return _git(repo, "rev-parse", "HEAD")


def _delete(repo: Path, path: str) -> str:
    _git(repo, "rm", "-q", path)
    _git(repo, "commit", "-qm", f"delete {path}")
    return _git(repo, "rev-parse", "HEAD")


def _manifest() -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=None,
        mission_branch=_MISSION_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/lane.py",),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-11-13T00:00:00+00:00",
        computed_from="test-mission-base-verifier",
    )


@dataclass
class _Fork:
    repo: Path
    manifest: LanesManifest
    root: str  # R: the target's pre-run tip (the window base)
    base: str  # B: the Mission base
    add_a: str  # adds up/a.py
    add_x: str  # adds up/x.py (reverted below the base)
    lane_commit: str  # the approved lane's own commit


@pytest.fixture
def fork(tmp_path: Path) -> _Fork:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    _write(repo, "src/app.py", "APP = 0\n")
    _write(repo, "old/r.py", "R = 0\n")
    root = _write(repo, "old/s.py", "S = 0\n")

    _git(repo, "checkout", "-q", "-b", "upstream")
    add_a = _write(repo, "up/a.py", "A = 1\n")
    add_x = _write(repo, "up/x.py", "X = 1\n")
    _delete(repo, "up/x.py")
    _delete(repo, "old/r.py")
    base = _write(repo, "overlay/cfg.txt", "fork = true\n")

    manifest = _manifest()
    lane = lane_created_branch(manifest, "lane-a")
    _git(repo, "checkout", "-q", "-b", lane, base)
    lane_commit = _write(repo, "src/lane.py", "LANE = 1\n")
    _git(repo, "branch", _MISSION_BRANCH, lane_commit)
    _git(repo, "checkout", "-q", "main")
    return _Fork(repo, manifest, root, base, add_a, add_x, lane_commit)


def _history(fx: _Fork) -> PreMissionHistory:
    return _pre_mission_attribution(fx.repo, fx.root, MissionBase(fx.base, MissionBaseProvenance.RECORDED), feature_dir=None, lanes_manifest=None)


def _claim(fx: _Fork, history: PreMissionHistory | None = None, **overrides: object) -> ApprovedWpCommitSet:
    """A production-shaped merge claim for the one approved lane, carrying *history*."""
    pre = history or PreMissionHistory(MissionBase(fx.base, MissionBaseProvenance.RECORDED))
    fields: dict[str, object] = {
        "approved": {"WP01": (fx.lane_commit,)},
        "excluded_window_base": fx.root,
        "surface_resolved": True,
        "enforce_closed_world": True,
        "authored_shas": frozenset({fx.lane_commit}),
        "authored_patch_ids": frozenset({patch_id_of(fx.repo, fx.lane_commit)}),
        "mission_slug": _SLUG,
        "planning_prefix": f"kitty-specs/{_SLUG}",
        "mission_base": pre.base,
        "pre_mission_shas": pre.shas,
        "pre_mission_blobs": pre.blobs,
        "pre_mission_deletions": pre.deletions,
    }
    fields.update(overrides)
    return ApprovedWpCommitSet(**fields)  # type: ignore[arg-type]


def _squash_claim(fx: _Fork, squashed: str, history: PreMissionHistory | None, **overrides: object) -> ApprovedWpCommitSet:
    authored = frozenset({("src/lane.py", blob_id_at(fx.repo, squashed, "src/lane.py"))})
    return _claim(fx, history, verify_reachability=False, authored_blobs=authored, **overrides)


def _landed(fx: _Fork, name: str, *, cherry_pick: str | None = None) -> str:
    """The target after a merge-strategy landing: ``R`` (+ an optional re-lettered copy) merged ``--no-ff`` with the Mission branch."""
    _git(fx.repo, "checkout", "-q", "-b", name, fx.root)
    if cherry_pick is not None:
        # An empty commit first, so the copy gets a new parent and a new SHA (a same-second
        # cherry-pick onto the original's own parent would reproduce the original commit).
        _git(fx.repo, "commit", "-q", "--allow-empty", "-m", "pad")
        _git(fx.repo, "cherry-pick", cherry_pick)
    _git(fx.repo, "merge", "-q", "--no-ff", "--no-edit", _MISSION_BRANCH)
    _git(fx.repo, "checkout", "-q", "main")
    return _git(fx.repo, "rev-parse", name)


def _squashed(fx: _Fork, name: str, source: str) -> str:
    """The target after a squash landing of *source* onto ``R``."""
    _git(fx.repo, "checkout", "-q", "-b", name, fx.root)
    _git(fx.repo, "merge", "-q", "--squash", source)
    _git(fx.repo, "commit", "-qm", f"squash {source}")
    _git(fx.repo, "checkout", "-q", "main")
    return _git(fx.repo, "rev-parse", name)


def _on_mission_branch(fx: _Fork, edit: str, path: str, content: str = "") -> str:
    """One post-base commit directly on the Mission branch (Mission work no WP authored)."""
    _git(fx.repo, "checkout", "-q", _MISSION_BRANCH)
    sha = _delete(fx.repo, path) if edit == "delete" else _write(fx.repo, path, content)
    _git(fx.repo, "checkout", "-q", "main")
    return sha


def _pre_base(fx: _Fork) -> set[str]:
    return set(_git(fx.repo, "rev-list", f"{fx.root}..{fx.base}").split())


# --- 1. closed world --------------------------------------------------------------------


def test_closed_world_exempts_pre_mission_commits_with_a_same_fixture_control(fork: _Fork) -> None:
    target = _landed(fork, "landed")
    history = _history(fork)
    assert history.shas == _pre_base(fork)

    assert MergeOutcomeVerifier(fork.repo).verify(target, _claim(fork, history)).is_pass

    control = MergeOutcomeVerifier(fork.repo).verify(target, _claim(fork))
    assert control.status is VerifyStatus.FAIL
    flagged = {sha for sha, _pid in control.divergence.unattributable_content}  # type: ignore[union-attr]
    # Every content commit of R..B is flagged (the revert of up/x.py and the deletion included).
    assert flagged == _pre_base(fork)


def test_relettered_copy_of_a_pre_mission_commit_is_still_flagged(fork: _Fork) -> None:
    """Residual, fail-closed: the exemption is by exact SHA, so a copy (new SHA, same patch) is judged."""
    target = _landed(fork, "relettered", cherry_pick=fork.add_a)
    copy = _git(fork.repo, "rev-parse", f"{target}^1")
    assert copy != fork.add_a and patch_id_of(fork.repo, copy) == patch_id_of(fork.repo, fork.add_a)

    result = MergeOutcomeVerifier(fork.repo).verify(target, _claim(fork, _history(fork)))

    assert result.status is VerifyStatus.FAIL
    assert [sha for sha, _pid in result.divergence.unattributable_content] == [copy]  # type: ignore[union-attr]


def test_mission_commit_reapplying_a_reverted_pre_mission_patch_is_still_flagged(fork: _Fork) -> None:
    reapplied = _on_mission_branch(fork, "write", "up/x.py", "X = 1\n")
    assert patch_id_of(fork.repo, reapplied) == patch_id_of(fork.repo, fork.add_x)
    target = _landed(fork, "reapplied")
    history = _history(fork)
    assert reapplied not in history.shas

    result = MergeOutcomeVerifier(fork.repo).verify(target, _claim(fork, history))

    assert result.status is VerifyStatus.FAIL
    assert [sha for sha, _pid in result.divergence.unattributable_content] == [reapplied]  # type: ignore[union-attr]


# --- 2./3. squash blobs and deletions ----------------------------------------------------


def test_squash_attributes_pre_mission_blobs_and_deletions(fork: _Fork) -> None:
    squashed = _squashed(fork, "squashed", _MISSION_BRANCH)
    history = _history(fork)
    assert ("up/a.py", blob_id_at(fork.repo, squashed, "up/a.py")) in history.blobs
    assert "old/r.py" in history.deletions

    assert MergeOutcomeVerifier(fork.repo).verify(squashed, _squash_claim(fork, squashed, history)).is_pass

    control = MergeOutcomeVerifier(fork.repo).verify(squashed, _squash_claim(fork, squashed, None))
    assert control.status is VerifyStatus.FAIL
    divergence = control.divergence
    assert divergence is not None
    assert {path for path, _blob in divergence.unattributable_blobs} == {"up/a.py", "overlay/cfg.txt"}
    assert divergence.unattributable_deletions == ("old/r.py",)


def test_squash_post_base_change_of_a_pre_mission_path_stays_unattributable(fork: _Fork) -> None:
    _on_mission_branch(fork, "write", "up/a.py", "A = 2\n")
    _on_mission_branch(fork, "delete", "old/s.py")
    squashed = _squashed(fork, "squashed-post-base", _MISSION_BRANCH)
    history = _history(fork)

    result = MergeOutcomeVerifier(fork.repo).verify(squashed, _squash_claim(fork, squashed, history))

    assert result.status is VerifyStatus.FAIL
    divergence = result.divergence
    assert divergence is not None
    assert divergence.unattributable_blobs == (("up/a.py", blob_id_at(fork.repo, squashed, "up/a.py")),)
    assert divergence.unattributable_deletions == ("old/s.py",)


# --- 4. vacuous squash --------------------------------------------------------------------


def test_vacuous_squash_with_only_pre_mission_content_passes(fork: _Fork) -> None:
    squashed = _squashed(fork, "squashed-base", fork.base)
    vacuous = {"approved": {"WP01": ()}, "authored_shas": frozenset(), "authored_patch_ids": frozenset()}

    claim = _claim(fork, _history(fork), verify_reachability=False, **vacuous)
    assert MergeOutcomeVerifier(fork.repo).verify(squashed, claim).is_pass

    control = MergeOutcomeVerifier(fork.repo).verify(squashed, _claim(fork, verify_reachability=False, **vacuous))
    assert control.status is VerifyStatus.REFUSE


def test_vacuous_squash_with_post_base_content_still_refuses(fork: _Fork) -> None:
    squashed = _squashed(fork, "squashed-mission", _MISSION_BRANCH)
    vacuous = {"approved": {"WP01": ()}, "authored_shas": frozenset(), "authored_patch_ids": frozenset()}

    result = MergeOutcomeVerifier(fork.repo).verify(squashed, _claim(fork, _history(fork), verify_reachability=False, **vacuous))

    assert result.status is VerifyStatus.REFUSE


def test_vacuous_squash_reads_no_blob_without_pre_mission_blobs(fork: _Fork, monkeypatch: pytest.MonkeyPatch) -> None:
    squashed = _squashed(fork, "squashed-noblob", fork.base)

    def _forbidden(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("no blob read without pre-Mission blobs (NFR-001)")

    monkeypatch.setattr(reconciliation_verifier, "blob_id_at", _forbidden)
    verifier = MergeOutcomeVerifier(fork.repo)

    assert verifier._window_has_non_bookkeeping_change(squashed, _claim(fork), fork.root) is True


# --- 5. the patch-id window ---------------------------------------------------------------


def test_patch_id_window_skips_pre_mission_carriers_and_keeps_mission_ones(fork: _Fork) -> None:
    canceled_pid = patch_id_of(fork.repo, fork.add_x)
    plain = _landed(fork, "plain")
    history = _history(fork)

    claim = _claim(fork, history, excluded_patch_ids=frozenset({canceled_pid}))
    assert MergeOutcomeVerifier(fork.repo).verify(plain, claim).is_pass

    control = MergeOutcomeVerifier(fork.repo).verify(plain, _claim(fork, excluded_patch_ids=frozenset({canceled_pid})))
    assert control.status is VerifyStatus.FAIL
    assert ("", canceled_pid) in control.divergence.reachable_excluded  # type: ignore[union-attr]

    reapplied = _on_mission_branch(fork, "write", "up/x.py", "X = 1\n")
    through_mission = _landed(fork, "through-mission")
    reread = _history(fork)
    verifier = MergeOutcomeVerifier(fork.repo)

    reached = verifier._reachable_excluded(through_mission, _claim(fork, reread, excluded_patch_ids=frozenset({canceled_pid})))

    assert reached == [("", canceled_pid)]
    assert patch_id_of(fork.repo, reapplied) == canceled_pid


def test_patch_id_window_still_reports_a_relettered_copy_of_a_pre_mission_commit(fork: _Fork) -> None:
    """Residual, fail-closed: only the exact pre-Mission SHA leaves the window, never its copy."""
    canceled_pid = patch_id_of(fork.repo, fork.add_a)
    target = _landed(fork, "relettered-window", cherry_pick=fork.add_a)
    claim = _claim(fork, _history(fork), excluded_patch_ids=frozenset({canceled_pid}))

    assert MergeOutcomeVerifier(fork.repo)._reachable_excluded(target, claim) == [("", canceled_pid)]


# --- 6. NFR-001: empty pre-Mission sets keep today's verdicts -----------------------------


@pytest.mark.parametrize("shape", ["merge", "squash", "vacuous", "excluded"])
def test_empty_pre_mission_sets_keep_todays_verdict(fork: _Fork, shape: str) -> None:
    if shape == "merge":
        target = _landed(fork, "nfr-merge")
        claim = _claim(fork)
    elif shape == "excluded":
        target = _landed(fork, "nfr-excluded")
        claim = _claim(fork, excluded_patch_ids=frozenset({patch_id_of(fork.repo, fork.add_a)}))
    else:
        target = _squashed(fork, f"nfr-{shape}", _MISSION_BRANCH if shape == "squash" else fork.base)
        if shape == "squash":
            claim = _squash_claim(fork, target, None)
        else:
            claim = _claim(fork, verify_reachability=False, approved={"WP01": ()}, authored_shas=frozenset(), authored_patch_ids=frozenset())
    today = ApprovedWpCommitSet(**{name: getattr(claim, name) for name in claim.__dataclass_fields__ if name not in _EMPTY_PRE_MISSION and name != "mission_base"})
    verifier = MergeOutcomeVerifier(fork.repo)

    assert verifier.verify(target, claim) == verifier.verify(target, today)


def test_patch_id_window_without_pre_mission_history_is_todays_single_probe(fork: _Fork, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def _spy(_repo: Path, base: str, tip: str) -> set[str]:
        calls.append((base, tip))
        return set()

    monkeypatch.setattr(reconciliation_verifier, "patch_ids_in_range", _spy)
    verifier = MergeOutcomeVerifier(fork.repo)

    assert verifier._window_patch_ids(fork.root, _MISSION_BRANCH, _claim(fork)) == set()
    assert calls == [(fork.root, _MISSION_BRANCH)]


# --- the claim-side helpers (pre-Mission history, base settling, note) ----------------------


def test_pre_mission_attribution_computes_no_patch_ids(fork: _Fork, monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbidden(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("the pre-Mission history needs no patch-ids: the exemption is by exact SHA")

    setattr_reconciliation_family(monkeypatch, "patch_id_of", _forbidden)
    base = MissionBase(fork.base, MissionBaseProvenance.RECORDED)

    assert _pre_mission_attribution(fork.repo, fork.root, base, feature_dir=None, lanes_manifest=None).shas == _pre_base(fork)
    # The window base already reaches the base: nothing pre-Mission.
    assert _pre_mission_attribution(fork.repo, fork.base, base, feature_dir=None, lanes_manifest=None) == PreMissionHistory(base)


def test_mission_base_note_is_silent_for_a_missing_mission_branch_and_never_quotes_git() -> None:
    """The note decides on the typed reason, never on the reason's text (Arch-3/4)."""
    gone = MissionBase(None, MissionBaseProvenance.UNAVAILABLE, "the Mission branch does not resolve", MissionBaseReason.MISSION_BRANCH_UNRESOLVED)
    assert mission_base_note(ApprovedWpCommitSet(mission_base=gone)) is None

    for leaky in (
        "git probe failed: fatal: bad revision 'x'",
        "git probe failed: git log failed (exit 128): fatal: x; secret; more stderr",
        "no mission_base_sha recorded; git probe failed: fatal: bad revision 'x'",
        "rev-list exploded",
    ):
        probe = MissionBase(None, MissionBaseProvenance.UNAVAILABLE, leaky, MissionBaseReason.PROBE_FAILED)
        note = mission_base_note(ApprovedWpCommitSet(mission_base=probe))
        assert note == "Mission base unavailable (a git probe failed); reconciliation windows are bounded by the target's pre-run tip only."
    plain = MissionBase(None, MissionBaseProvenance.UNAVAILABLE, "no mission_base_sha recorded", MissionBaseReason.NOT_RECORDED)
    assert mission_base_note(ApprovedWpCommitSet(mission_base=plain)) == (
        "Mission base unavailable (no mission_base_sha recorded); reconciliation windows are bounded by the target's pre-run tip only."
    )
    sha = "0123456789abcdef0123456789abcdef01234567"
    derived = MissionBase(sha, MissionBaseProvenance.DERIVED, "git probe failed: fatal: boom", MissionBaseReason.PROBE_FAILED)
    with_history = mission_base_note(ApprovedWpCommitSet(mission_base=derived, pre_mission_shas=frozenset({"a"})))
    assert with_history is not None and "fatal" not in with_history and "(derived: a git probe failed)" in with_history
