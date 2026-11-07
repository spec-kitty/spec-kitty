"""Red-first tests for #7307: a lane's own dependency merges are attributed to that lane.

The implement allocator merges each declared dependency lane into a dependent lane
(``Merge dependency lane X into Y``, ``lanes/worktree_allocator.py``) before the
lane's first claim, so the #5968 own-base bound drops those merges from the lane's
authorship. The closed-world scan then skipped a merge only when its default
``--cc`` patch-id was empty, which is false for a clean merge whose parents both
touched one file, so the allocator's own merge read as content that "belongs to NO
approved WP".

The contract pinned here:

* a clean dependency merge adds nothing beyond its parents (``--remerge-diff`` is
  empty), so it carries no content to attribute;
* a dependency merge that resolves a conflict is the lane's own work, attributed to it;
* a merge that is not a lane's own dependency merge, and a foreign commit, still FAIL,
  including a resolution that keeps one side (an empty ``--cc`` diff);
* git older than 2.36 (no ``--remerge-diff``) REFUSEs: the probe raises ``GitProbeError``.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from specify_cli.consolidation import git_probes
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.consolidation.reconciliation import (
    ApprovedWpCommitSet,
    MergeOutcomeVerifier,
    VerifyStatus,
    build_approved_wp_set,
)
from specify_cli.consolidation import wp_attribution
from specify_cli.git import merge_tree_probe
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_TARGET = "main"
_SLUG = "dep-merge-attr-01M7307"
_SHARED = "u/shared.txt"
_SHARED_BASE = "one\ntwo\nthree\nfour\nfive\nsix\n"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _write(repo: Path, rel: str, body: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(body, encoding="utf-8")


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _branch(lane_id: str) -> str:
    name: str = lane_branch_name(_SLUG, lane_id, target_branch=_TARGET)
    return name


def _lane(lane_id: str, wp_id: str, deps: tuple[str, ...] = ()) -> ExecutionLane:
    return ExecutionLane(
        lane_id=lane_id,
        wp_ids=(wp_id,),
        write_scope=("u",),
        predicted_surfaces=("code",),
        depends_on_lanes=deps,
        parallel_group=0,
    )


_CHAIN = (("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review"), ("for_review", "in_review"), ("in_review", "approved"))


def _approve_chain(events: list[dict[str, object]], wp: str, *, claim_stamp: str, approve_stamp: str) -> None:
    for frm, to in _CHAIN:
        seq = len(events)
        row: dict[str, object] = {
            "actor": "reviewer-renata" if to == "approved" else "claude",
            "at": f"2026-11-07T00:{seq // 60:02d}:{seq % 60:02d}+00:00",
            "event_id": f"01M7307{seq:019d}",
            "evidence": None,
            "execution_mode": "worktree",
            "feature_slug": _SLUG,
            "force": False,
            "from_lane": frm,
            "reason": None,
            "review_ref": None,
            "to_lane": to,
            "wp_id": wp,
        }
        stamp = claim_stamp if to in ("claimed", "in_progress") else approve_stamp if to == "approved" else None
        if stamp is not None:
            row["policy_metadata"] = {"lane_head": stamp}
        events.append(row)


def _init_repo(tmp_path: Path) -> tuple[Path, Path, LanesManifest, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _TARGET)
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    mission_id = "01M7307000000000000000000"[:26].ljust(26, "0")
    feature_dir = repo / "kitty-specs" / _SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": _SLUG, "mission_id": mission_id, "mission_type": "software-dev", "target_branch": _TARGET}),
        encoding="utf-8",
    )
    manifest = LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=mission_id,
        mission_branch=f"kitty/mission-{_SLUG}",
        target_branch=_TARGET,
        lanes=[_lane("lane-a", "WP01"), _lane("lane-c", "WP03"), _lane("lane-b", "WP02", ("lane-a", "lane-c"))],
        computed_at="2026-11-07T00:00:00+00:00",
        computed_from="test-dependency-merge-attribution-7307",
    )
    for wp_id in ("WP01", "WP02", "WP03"):
        (feature_dir / "tasks" / f"{wp_id}-work.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: {wp_id} work\ndependencies: []\nsubtasks: []\nowned_files:\n  - u/**\n---\n# {wp_id}\n",
            encoding="utf-8",
        )
    write_lanes_json(feature_dir, manifest)
    _write(repo, _SHARED, _SHARED_BASE)
    base = _commit(repo, "bootstrap")
    manifest.planning_commit_sha = base
    write_lanes_json(feature_dir, manifest)
    base = _commit(repo, "record the planning commit")
    return repo, feature_dir, manifest, base


def _build_mission(tmp_path: Path, *, conflict: bool) -> tuple[Path, Path, LanesManifest, str, str]:
    """lane-a and lane-c edit ``u/shared.txt``; lane-b depends on both, allocator-merged.

    ``conflict=False``: different hunks, so the dependency merge is clean but its
    ``--cc`` diff is non-empty. ``conflict=True``: the same line, resolved by hand.
    Returns ``(repo, feature_dir, manifest, base, dependency_merge_sha)``.
    """
    repo, feature_dir, manifest, base = _init_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", _branch("lane-a"), base)
    _write(repo, _SHARED, _SHARED_BASE.replace("one", "ONE-a"))
    a_tip = _commit(repo, "WP01: edit line one")
    _git(repo, "checkout", "-q", "-b", _branch("lane-c"), base)
    _write(repo, _SHARED, _SHARED_BASE.replace("one" if conflict else "three", "ONE-c" if conflict else "THREE-c"))
    c_tip = _commit(repo, "WP03: edit shared")

    # The allocator: lane-b from lane-a (fast-forward), then merge lane-c in.
    _git(repo, "checkout", "-q", "-b", _branch("lane-b"), a_tip)
    msg = "Merge dependency lane lane-c into lane-b"
    if conflict:
        subprocess.run(["git", "merge", "--no-edit", "-m", msg, _branch("lane-c")], cwd=repo, check=False, capture_output=True)
        _write(repo, _SHARED, _SHARED_BASE.replace("one", "ONE-a+c"))
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", msg)
    else:
        _git(repo, "merge", "--no-ff", "--no-edit", "-m", msg, _branch("lane-c"))
    dep_merge = _git(repo, "rev-parse", "HEAD")
    _write(repo, "u/wp02/own.txt", "two\n")
    b_tip = _commit(repo, "WP02: work")

    events: list[dict[str, object]] = []
    _approve_chain(events, "WP01", claim_stamp=base, approve_stamp=a_tip)
    _approve_chain(events, "WP03", claim_stamp=base, approve_stamp=c_tip)
    _approve_chain(events, "WP02", claim_stamp=dep_merge, approve_stamp=b_tip)
    (feature_dir / "status.events.jsonl").write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events), encoding="utf-8")

    # Merge-strategy landing: lane-b already carries lane-a and lane-c.
    _git(repo, "checkout", "-q", "-b", "target-merge", base)
    _git(repo, "merge", "--no-ff", "--no-edit", _branch("lane-b"))
    return repo, feature_dir, manifest, base, dep_merge


def _verdict(repo: Path, feature_dir: Path, manifest: LanesManifest, base: str) -> tuple[VerifyStatus, list[tuple[str, str]]]:
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=base, excluded_window_base=base)
    assert claim.surface_resolved and claim.refusal is None, f"claim refused: {claim.refusal!r}"
    verifier = MergeOutcomeVerifier(repo)
    unattributable = verifier._unattributable_content("target-merge", claim)
    return verifier.verify("target-merge", claim).status, unattributable


@pytest.mark.parametrize("conflict", [False, True], ids=["clean-merge", "conflict-resolution"])
def test_lane_own_dependency_merge_is_attributed(tmp_path: Path, conflict: bool) -> None:
    repo, feature_dir, manifest, base, dep_merge = _build_mission(tmp_path, conflict=conflict)
    assert _git(repo, "show", "--format=", dep_merge), "fixture: the dependency merge must carry a non-empty --cc diff"
    status, unattributable = _verdict(repo, feature_dir, manifest, base)
    assert dep_merge not in {sha for sha, _pid in unattributable}, f"the lane's own dependency merge was flagged: {unattributable!r}"
    assert status is VerifyStatus.PASS


def test_foreign_conflict_resolution_merge_still_fails(tmp_path: Path) -> None:
    """Negative control: a merge no lane owns, resolving by keeping one side (empty ``--cc``), FAILs."""
    repo, feature_dir, manifest, base, _dep = _build_mission(tmp_path, conflict=False)
    _git(repo, "checkout", "-q", "-b", "foreign", base)
    _write(repo, _SHARED, _SHARED_BASE.replace("one", "FOREIGN"))
    _commit(repo, "foreign edit")
    _git(repo, "checkout", "-q", "target-merge")
    subprocess.run(["git", "merge", "--no-edit", "foreign"], cwd=repo, check=False, capture_output=True)
    _git(repo, "checkout", "--ours", "--", _SHARED)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "merge foreign keeping ours")
    foreign_merge = _git(repo, "rev-parse", "HEAD")
    assert not _git(repo, "show", "--format=", foreign_merge), "fixture: the keep-ours resolution has an empty --cc diff"
    status, unattributable = _verdict(repo, feature_dir, manifest, base)
    assert foreign_merge in {sha for sha, _pid in unattributable}
    assert status is not VerifyStatus.PASS


def test_foreign_commit_still_fails(tmp_path: Path) -> None:
    """Negative control: a non-merge commit outside every lane FAILs."""
    repo, feature_dir, manifest, base, _dep = _build_mission(tmp_path, conflict=False)
    _write(repo, "u/smuggled.txt", "x\n")
    smuggled = _commit(repo, "smuggled")
    status, unattributable = _verdict(repo, feature_dir, manifest, base)
    assert smuggled in {sha for sha, _pid in unattributable}
    assert status is not VerifyStatus.PASS


def test_lane_dependency_merges_names_only_dependency_merges(tmp_path: Path) -> None:
    repo, _fd, _m, base, dep_merge = _build_mission(tmp_path, conflict=False)
    spine = _git(repo, "rev-list", "--first-parent", f"{base}..{_branch('lane-b')}").split()
    assert wp_attribution.lane_dependency_merges(repo, spine, [_branch("lane-c")]) == frozenset({dep_merge})
    assert wp_attribution.lane_dependency_merges(repo, spine, [_branch("lane-a")]) == frozenset(), "lane-c is not a dependency here"
    assert wp_attribution.lane_dependency_merges(repo, spine, []) == frozenset()
    assert wp_attribution.lane_dependency_merges(repo, ["0" * 40], [_branch("lane-c")]) == frozenset(), "an unreadable commit is left out"


@pytest.mark.parametrize("conflict", [False, True], ids=["clean-merge", "conflict-resolution"])
def test_merge_own_changed_paths(tmp_path: Path, conflict: bool) -> None:
    repo, _fd, _m, _base, dep_merge = _build_mission(tmp_path, conflict=conflict)
    assert git_probes.merge_own_changed_paths(repo, dep_merge) == ([_SHARED] if conflict else [])


def test_merge_own_changed_paths_refuses_on_old_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _fd, _m, _base, dep_merge = _build_mission(tmp_path, conflict=False)
    monkeypatch.setattr(git_probes, "remerge_diff_available", lambda _repo: False)
    with pytest.raises(GitProbeError, match="2.36"):
        git_probes.merge_own_changed_paths(repo, dep_merge)


def test_merge_own_changed_paths_raises_on_git_error(tmp_path: Path) -> None:
    repo, _fd, _m, _base = _init_repo(tmp_path)
    with pytest.raises(GitProbeError):
        git_probes.merge_own_changed_paths(repo, "0" * 40)


def test_old_git_refuses_the_closed_world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir, manifest, base, _dep = _build_mission(tmp_path, conflict=False)
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=base, excluded_window_base=base)
    monkeypatch.setattr(git_probes, "remerge_diff_available", lambda _repo: False)
    assert MergeOutcomeVerifier(repo).verify("target-merge", claim).status is VerifyStatus.REFUSE


@pytest.mark.parametrize(
    ("version", "expected"),
    [("git version 2.35.9", False), ("git version 2.36.0", True), ("git version 2.43.0", True), ("garbage", False)],
)
def test_remerge_diff_available_version_gate(monkeypatch: pytest.MonkeyPatch, version: str, expected: bool) -> None:
    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["git", "--version"], returncode=0, stdout=version, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert merge_tree_probe.remerge_diff_available(Path(".")) is expected


# --- Review blocker: a dependency merge made AFTER the lane's approval (#7307) ---------------

_EVIL = "u/evil.txt"


def _build_post_approval_merge(tmp_path: Path, *, canceled_dependency: bool) -> tuple[Path, Path, LanesManifest, str, str]:
    """lane-b (depends on lane-c) is approved at ``b``; lane-c then moves to ``c2``; lane-b
    merges lane-c with a hand-written ``u/evil.txt`` folded into the merge, after approval.

    Returns ``(repo, feature_dir, manifest, base, evil_merge_sha)``; ``target-merge`` is a
    merge-strategy landing and ``target-squash`` a squash landing of lane-c then lane-b.
    """
    repo, feature_dir, manifest, base = _init_repo(tmp_path)
    manifest.lanes = [_lane("lane-c", "WP03"), _lane("lane-b", "WP02", ("lane-c",))]
    (feature_dir / "tasks" / "WP01-work.md").unlink()
    write_lanes_json(feature_dir, manifest)
    base = _commit(repo, "two lanes")
    _git(repo, "checkout", "-q", "-b", _branch("lane-c"), base)
    _write(repo, "u/c.txt", "c1\n")
    c1 = _commit(repo, "WP03: c1")
    _git(repo, "checkout", "-q", "-b", _branch("lane-b"), c1)
    _write(repo, "u/wp02/own.txt", "two\n")
    b_tip = _commit(repo, "WP02: work")
    _git(repo, "checkout", "-q", _branch("lane-c"))
    _write(repo, "u/c.txt", "c2\n")
    c2 = _commit(repo, "WP03: c2")
    _git(repo, "checkout", "-q", _branch("lane-b"))
    _git(repo, "merge", "--no-ff", "--no-commit", _branch("lane-c"))
    _write(repo, _EVIL, "unreviewed\n")
    evil = _commit(repo, "Merge dependency lane lane-c into lane-b")

    events: list[dict[str, object]] = []
    if canceled_dependency:
        _approve_chain(events, "WP03", claim_stamp=base, approve_stamp=c2)
        events[-1]["to_lane"] = "canceled"
        events[-1]["force"] = True
    else:
        _approve_chain(events, "WP03", claim_stamp=base, approve_stamp=c2)
    _approve_chain(events, "WP02", claim_stamp=c1, approve_stamp=b_tip)
    (feature_dir / "status.events.jsonl").write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events), encoding="utf-8")

    _git(repo, "checkout", "-q", "-b", "target-merge", base)
    _git(repo, "merge", "--no-ff", "--no-edit", _branch("lane-c"))
    _git(repo, "merge", "--no-ff", "--no-edit", _branch("lane-b"))
    _git(repo, "checkout", "-q", "-b", "target-squash", base)
    _git(repo, "merge", "--squash", _branch("lane-c"))
    _commit(repo, "squash lane-c")
    _git(repo, "merge", "--squash", _branch("lane-b"))
    _commit(repo, "squash lane-b")
    return repo, feature_dir, manifest, base, evil


def _claim(repo: Path, feature_dir: Path, manifest: LanesManifest, base: str, *, canceled: tuple[str, ...] = ()) -> ApprovedWpCommitSet:
    return build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=base, excluded_window_base=base, excluded_canceled_wp_ids=canceled)


def test_post_approval_dependency_merge_with_own_content_fails_under_merge(tmp_path: Path) -> None:
    repo, feature_dir, manifest, base, evil = _build_post_approval_merge(tmp_path, canceled_dependency=False)
    claim = _claim(repo, feature_dir, manifest, base)
    if claim.refusal is not None:
        return  # refused at claim time: fail-closed, acceptable
    verifier = MergeOutcomeVerifier(repo)
    assert evil in {sha for sha, _pid in verifier._unattributable_content("target-merge", claim)}
    assert verifier.verify("target-merge", claim).status is not VerifyStatus.PASS


def test_post_approval_dependency_merge_with_own_content_fails_under_squash(tmp_path: Path) -> None:
    repo, feature_dir, manifest, base, _evil = _build_post_approval_merge(tmp_path, canceled_dependency=False)
    claim = _claim(repo, feature_dir, manifest, base)
    if claim.refusal is not None:
        return
    result = MergeOutcomeVerifier(repo).verify("target-squash", replace(claim, verify_reachability=False))
    assert result.status is not VerifyStatus.PASS, f"unreviewed {_EVIL} landed under squash"


def test_post_approval_merge_of_canceled_dependency_fails(tmp_path: Path) -> None:
    repo, feature_dir, manifest, base, _evil = _build_post_approval_merge(tmp_path, canceled_dependency=True)
    claim = _claim(repo, feature_dir, manifest, base, canceled=("WP03",))
    if claim.refusal is not None:
        return
    verifier = MergeOutcomeVerifier(repo)
    assert verifier.verify("target-merge", claim).status is not VerifyStatus.PASS
    assert verifier.verify("target-squash", replace(claim, verify_reachability=False)).status is not VerifyStatus.PASS


def test_clean_post_approval_dependency_merge_carries_nothing(tmp_path: Path) -> None:
    """A post-approval dependency merge with an empty remerge-diff adds no content of its own."""
    repo, _fd, _m, _base, evil = _build_post_approval_merge(tmp_path, canceled_dependency=False)
    _git(repo, "checkout", "-q", _branch("lane-b"))
    _git(repo, "reset", "-q", "--hard", f"{evil}^1")
    _git(repo, "merge", "--no-ff", "--no-edit", _branch("lane-c"))
    clean = _git(repo, "rev-parse", "HEAD")
    assert git_probes.merge_own_changed_paths(repo, clean) == []
