"""The shared reviewed-merge predicate and the claim's ``unreviewed_merges`` field (FR-004, FR-006, C-003).

The reconciliation gate keeps a merge on an approved lane's authorship spine only when one of
THAT lane's own approval stamps reaches it (#7307). One public predicate,
``merge_reviewed_by_own_stamps``, and one own-stamp reader, ``own_approval_stamps``, carry that
rule, so the claim-time check and the gate hint cannot disagree with the gate.

The claim records every merge the gate drops (``ApprovedWpCommitSet.unreviewed_merges``) with
the merge's own paths and blobs. The field is advisory data for a hint, never authorship.

``test_existing_claim_fields_are_byte_identical`` is a ratchet: the per-field digests were
recorded at the base, before any production change, and must not move.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from charter.hasher import hash_content
from specify_cli.consolidation.reconciliation import ApprovedWpCommitSet, build_approved_wp_set
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from tests.consolidation.reconciliation_family import setattr_reconciliation_family

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_TARGET = "main"
_SLUG = "reviewed-merge-01M7WW0Z"
_MISSION_ID = "01M7WW0Z000000000000000000"
_EVIL = "u/evil.txt"
_FIXED_DATE = "2026-11-20T12:00:00+00:00"


# --- fixture builder ---------------------------------------------------------------------------


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
            "at": f"2026-11-20T00:{seq // 60:02d}:{seq % 60:02d}+00:00",
            "event_id": f"01M7WW0Z{seq:018d}",
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


def _write_events(feature_dir: Path, events: list[dict[str, object]]) -> None:
    (feature_dir / "status.events.jsonl").write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events), encoding="utf-8")


@dataclasses.dataclass(frozen=True)
class _Mission:
    repo: Path
    feature_dir: Path
    manifest: LanesManifest
    base: str
    merge: str
    """The merge under test (``evil``, the clean merge, the reviewed merge, or ``M_b``)."""
    other_stamp: str = ""
    """Three-lane fixture only: lane-c's approval stamp (it reaches ``M_b``)."""


def _init_repo(root: Path, lanes: list[ExecutionLane]) -> tuple[Path, Path, LanesManifest, str]:
    repo = root / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", _TARGET)
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    feature_dir = repo / "kitty-specs" / _SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": _SLUG, "mission_id": _MISSION_ID, "mission_type": "software-dev", "target_branch": _TARGET}),
        encoding="utf-8",
    )
    manifest = LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=_MISSION_ID,
        mission_branch=f"kitty/mission-{_SLUG}",
        target_branch=_TARGET,
        lanes=lanes,
        computed_at="2026-11-20T00:00:00+00:00",
        computed_from="test-reviewed-merge-predicate",
    )
    for lane in lanes:
        for wp_id in lane.wp_ids:
            (feature_dir / "tasks" / f"{wp_id}-work.md").write_text(
                f"---\nwork_package_id: {wp_id}\ntitle: {wp_id} work\ndependencies: []\nsubtasks: []\nowned_files:\n  - u/**\n---\n# {wp_id}\n",
                encoding="utf-8",
            )
    write_lanes_json(feature_dir, manifest)
    _write(repo, "u/base.txt", "base\n")
    base = _commit(repo, "bootstrap")
    manifest.planning_commit_sha = base
    write_lanes_json(feature_dir, manifest)
    base = _commit(repo, "record the planning commit")
    return repo, feature_dir, manifest, base


def _build_two_lane(root: Path, *, variant: str, canceled_dependency: bool = False) -> _Mission:
    """lane-c (WP03) and lane-b (WP02, depends on lane-c); lane-b merges lane-c's later work.

    ``variant``:
    * ``"post"``: the merge carries a hand-written ``u/evil.txt`` and is made AFTER lane-b's approval;
    * ``"clean"``: the merge carries nothing of its own and is made after lane-b's approval;
    * ``"reviewed"``: the ``"post"`` merge, but lane-b is approved AT it (its stamp reaches it).
    """
    repo, feature_dir, manifest, base = _init_repo(root, [_lane("lane-c", "WP03"), _lane("lane-b", "WP02", ("lane-c",))])
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
    if variant == "clean":
        _git(repo, "merge", "--no-ff", "--no-edit", "-m", "Merge dependency lane lane-c into lane-b", _branch("lane-c"))
        merge = _git(repo, "rev-parse", "HEAD")
    else:
        _git(repo, "merge", "--no-ff", "--no-commit", _branch("lane-c"))
        _write(repo, _EVIL, "unreviewed\n")
        merge = _commit(repo, "Merge dependency lane lane-c into lane-b")
    events: list[dict[str, object]] = []
    _approve_chain(events, "WP03", claim_stamp=base, approve_stamp=c2)
    if canceled_dependency:
        events[-1]["to_lane"] = "canceled"
        events[-1]["force"] = True
    _approve_chain(events, "WP02", claim_stamp=c1, approve_stamp=merge if variant == "reviewed" else b_tip)
    _write_events(feature_dir, events)
    _git(repo, "checkout", "-q", _TARGET)
    return _Mission(repo, feature_dir, manifest, base, merge)


def _build_three_lane(root: Path) -> _Mission:
    """lane-a (WP01); lane-b (WP02, depends on lane-a); lane-c (WP03, depends on lane-b).

    lane-b is approved at ``b1``, then hand-merges lane-a's later work with a hand-written file
    (``M_b``, unreviewed by lane-b). lane-c merges lane-b (``M_b`` included, off its first-parent
    spine) and is approved at that merge, so lane-c's stamp reaches ``M_b``.
    """
    repo, feature_dir, manifest, base = _init_repo(
        root,
        [_lane("lane-a", "WP01"), _lane("lane-b", "WP02", ("lane-a",)), _lane("lane-c", "WP03", ("lane-b",))],
    )
    _git(repo, "checkout", "-q", "-b", _branch("lane-a"), base)
    _write(repo, "u/a.txt", "a1\n")
    a1 = _commit(repo, "WP01: a1")
    _git(repo, "checkout", "-q", "-b", _branch("lane-b"), a1)
    _write(repo, "u/wp02/own.txt", "b1\n")
    b1 = _commit(repo, "WP02: b1")
    _git(repo, "checkout", "-q", "-b", _branch("lane-c"), b1)
    _write(repo, "u/wp03/own.txt", "c1\n")
    _commit(repo, "WP03: c1")
    _git(repo, "checkout", "-q", _branch("lane-a"))
    _write(repo, "u/a.txt", "a2\n")
    a2 = _commit(repo, "WP01: a2")
    _git(repo, "checkout", "-q", _branch("lane-b"))
    _git(repo, "merge", "--no-ff", "--no-commit", _branch("lane-a"))
    _write(repo, _EVIL, "unreviewed\n")
    m_b = _commit(repo, "Merge dependency lane lane-a into lane-b")
    _git(repo, "checkout", "-q", _branch("lane-c"))
    _git(repo, "merge", "--no-ff", "--no-edit", "-m", "Merge dependency lane lane-b into lane-c", _branch("lane-b"))
    c_stamp = _git(repo, "rev-parse", "HEAD")
    events: list[dict[str, object]] = []
    _approve_chain(events, "WP01", claim_stamp=base, approve_stamp=a2)
    _approve_chain(events, "WP02", claim_stamp=a1, approve_stamp=b1)
    _approve_chain(events, "WP03", claim_stamp=b1, approve_stamp=c_stamp)
    _write_events(feature_dir, events)
    _git(repo, "checkout", "-q", _TARGET)
    return _Mission(repo, feature_dir, manifest, base, m_b, other_stamp=c_stamp)


_BUILDERS = {
    "two-lane": lambda root: _build_two_lane(root, variant="post"),
    "reviewed": lambda root: _build_two_lane(root, variant="reviewed"),
    "clean": lambda root: _build_two_lane(root, variant="clean"),
    "three-lane": _build_three_lane,
}


@pytest.fixture(autouse=True)
def _fixed_git_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixed commit dates and identity, so every fixture's SHAs are a function of the fixture alone."""
    for name in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
        monkeypatch.setenv(name, _FIXED_DATE)
    for name in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(name, "Test")
    for name in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(name, "t@example.invalid")


def _unbypassed_claim(mission: _Mission, *, canceled: tuple[str, ...] = ()) -> ApprovedWpCommitSet:
    return build_approved_wp_set(
        mission.repo,
        mission.feature_dir,
        mission.manifest,
        coord_base_ref=mission.base,
        excluded_window_base=mission.base,
        excluded_canceled_wp_ids=canceled,
    )


def _claim(mission: _Mission, *, canceled: tuple[str, ...] = ()) -> ApprovedWpCommitSet:
    """The claim with WP05's claim-time ``RESOLUTION_MERGE_UNREVIEWED`` check bypassed.

    These tests pin the gate-side advisory field (``unreviewed_merges``) on claims that hold a merge no
    own stamp reaches; since FR-004 the plain claim refuses such a merge before it is built
    (:func:`test_the_plain_claim_refuses_the_unreviewed_merge`), so the field is read on a claim built
    as the gate sees it.
    """
    from specify_cli.consolidation import reconciliation_bound

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(reconciliation_bound, "unreviewed_resolution_merges", lambda *_args, **_kwargs: ())
        claim = _unbypassed_claim(mission, canceled=canceled)
    assert claim.surface_resolved and claim.refusal is None, f"claim refused: {claim.refusal!r}"
    return claim


def _wp_status(**lanes: str) -> dict[str, dict[str, object]]:
    return {wp: {"lane": lane} for wp, lane in lanes.items()}


# --- T010: the predicate -----------------------------------------------------------------------


def test_merge_reached_by_an_own_stamp_is_reviewed(tmp_path: Path) -> None:
    from specify_cli.consolidation.reconciliation_authorship import merge_reviewed_by_own_stamps

    mission = _build_two_lane(tmp_path, variant="reviewed")
    assert merge_reviewed_by_own_stamps(mission.repo, mission.merge, (mission.merge,)) is True


def test_merge_after_the_newest_own_stamp_is_not_reviewed(tmp_path: Path) -> None:
    from specify_cli.consolidation.reconciliation_authorship import merge_reviewed_by_own_stamps

    mission = _build_two_lane(tmp_path, variant="post")
    b_tip = _git(mission.repo, "rev-parse", f"{mission.merge}^1")
    assert merge_reviewed_by_own_stamps(mission.repo, mission.merge, (b_tip,)) is False


def test_another_lane_s_stamp_does_not_review_a_merge(tmp_path: Path) -> None:
    from specify_cli.consolidation.reconciliation_authorship import merge_reviewed_by_own_stamps

    mission = _build_three_lane(tmp_path)
    b1 = _git(mission.repo, "rev-parse", f"{mission.merge}^1")
    precondition = subprocess.run(["git", "merge-base", "--is-ancestor", mission.merge, mission.other_stamp], cwd=mission.repo, check=False)
    assert precondition.returncode == 0, "fixture: lane-c's approval stamp must reach M_b"
    assert merge_reviewed_by_own_stamps(mission.repo, mission.merge, (b1,)) is False


def test_no_own_stamp_reviews_nothing(tmp_path: Path) -> None:
    from specify_cli.consolidation.reconciliation_authorship import merge_reviewed_by_own_stamps

    mission = _build_two_lane(tmp_path, variant="reviewed")
    assert merge_reviewed_by_own_stamps(mission.repo, mission.merge, ()) is False


def test_an_unknown_stamp_reviews_nothing(tmp_path: Path) -> None:
    """Fail closed: a stamp that names no commit in this clone never reviews a merge."""
    from specify_cli.consolidation.reconciliation_authorship import merge_reviewed_by_own_stamps

    mission = _build_two_lane(tmp_path, variant="reviewed")
    assert merge_reviewed_by_own_stamps(mission.repo, mission.merge, ("f" * 40,)) is False


def test_own_stamps_are_the_newest_approval_of_approved_wps_only() -> None:
    from specify_cli.consolidation.reconciliation_authorship import own_approval_stamps

    lane = ExecutionLane(
        lane_id="lane-x",
        wp_ids=("WP05", "WP01", "WP02", "WP03", "WP04"),
        write_scope=("u",),
        predicted_surfaces=("code",),
        depends_on_lanes=(),
        parallel_group=0,
    )
    work_packages = _wp_status(WP01="approved", WP02="canceled", WP03="approved", WP04="in_review", WP05="done")
    stamps: dict[str, str | None] = {"WP01": "s1", "WP02": "s2", "WP03": None, "WP04": "s4", "WP05": "s5"}
    assert own_approval_stamps(lane, work_packages, stamps) == ("s5", "s1")


def test_own_stamps_carry_each_wp_s_presync_stamp_after_its_lane_head() -> None:
    """#7802: the pre-sync stamp is an own reach anchor, right after its WP's ``lane_head`` stamp."""
    from specify_cli.consolidation.reconciliation_authorship import own_approval_stamps

    lane = ExecutionLane(
        lane_id="lane-x",
        wp_ids=("WP01", "WP02", "WP03"),
        write_scope=("u",),
        predicted_surfaces=("code",),
        depends_on_lanes=(),
        parallel_group=0,
    )
    work_packages = _wp_status(WP01="approved", WP02="done", WP03="canceled")
    stamps: dict[str, str | None] = {"WP01": "h1", "WP02": None, "WP03": "h3"}
    presync: dict[str, str | None] = {"WP01": "p1", "WP02": "p2", "WP03": "p3"}
    assert own_approval_stamps(lane, work_packages, stamps, presync) == ("h1", "p1", "p2")


# --- T010: the claim field ---------------------------------------------------------------------


def test_claim_records_the_dropped_merge(tmp_path: Path) -> None:
    from specify_cli.consolidation.reconciliation_claim_types import UnreviewedMerge

    mission = _build_two_lane(tmp_path, variant="post")
    blob = _git(mission.repo, "rev-parse", f"{mission.merge}:{_EVIL}")
    claim = _claim(mission)
    assert getattr(claim, "unreviewed_merges", None) == (
        UnreviewedMerge(sha=mission.merge, lane_id="lane-b", wp_ids=("WP02",), own_paths=(_EVIL,), own_blobs=((_EVIL, blob),)),
    )


def test_the_plain_claim_refuses_the_unreviewed_merge(tmp_path: Path) -> None:
    """Both layers visible: the unbypassed claim refuses the merge whose own content the advisory field names."""
    mission = _build_two_lane(tmp_path, variant="post")
    refusal = _unbypassed_claim(mission).refusal or ""
    assert refusal.startswith(f"RESOLUTION_MERGE_UNREVIEWED: lane lane-b (WP02): merge {mission.merge[:7]}"), refusal


def test_claim_records_a_clean_dropped_merge_with_no_own_content(tmp_path: Path) -> None:
    from specify_cli.consolidation.reconciliation_claim_types import UnreviewedMerge

    mission = _build_two_lane(tmp_path, variant="clean")
    claim = _claim(mission)
    assert getattr(claim, "unreviewed_merges", None) == (UnreviewedMerge(sha=mission.merge, lane_id="lane-b", wp_ids=("WP02",), own_paths=(), own_blobs=()),)


def test_claim_does_not_record_a_reviewed_merge(tmp_path: Path) -> None:
    mission = _build_two_lane(tmp_path, variant="reviewed")
    assert getattr(_claim(mission), "unreviewed_merges", None) == ()


def test_three_lane_claim_names_the_merge_s_own_lane(tmp_path: Path) -> None:
    mission = _build_three_lane(tmp_path)
    entries = getattr(_claim(mission), "unreviewed_merges", None)
    assert entries is not None
    for_m_b = [entry for entry in entries if entry.sha == mission.merge]
    assert [entry.lane_id for entry in for_m_b] == ["lane-b"]
    assert for_m_b[0].wp_ids == ("WP02",)
    assert for_m_b[0].own_paths == (_EVIL,)


def test_canceled_dependency_lane_commits_are_never_recorded(tmp_path: Path) -> None:
    """A fully-canceled dependency lane's commits are subtracted before the drop: only lane-b's own merge is named."""
    mission = _build_two_lane(tmp_path, variant="post", canceled_dependency=True)
    claim = build_approved_wp_set(
        mission.repo, mission.feature_dir, mission.manifest, coord_base_ref=mission.base, excluded_window_base=mission.base, excluded_canceled_wp_ids=("WP03",)
    )
    entries = getattr(claim, "unreviewed_merges", None)
    assert entries is not None
    canceled_lane = set(_git(mission.repo, "rev-list", f"{mission.base}..{_branch('lane-c')}").split())
    assert not {entry.sha for entry in entries} & canceled_lane
    assert {entry.lane_id for entry in entries} <= {"lane-b"}


def _add_post_approval_octopus(mission: _Mission) -> str:
    """A 3-parent merge on lane-b after its approval stamp, with a file of its own (``u/octo.txt``).

    Its extra parents (lane-c's ``c2`` and lane-b's own ``c1`` base) are anchored, so only the
    octopus itself is new. ``git show --remerge-diff`` skips octopus merges, so the own-content
    probe raises on it.
    """
    repo = mission.repo
    _git(repo, "checkout", "-q", _branch("lane-b"))
    head = _git(repo, "rev-parse", "HEAD")
    c2 = _git(repo, "rev-parse", _branch("lane-c"))
    c1 = _git(repo, "rev-parse", f"{c2}^")
    _git(repo, "checkout", "-q", c2, "--", "u/c.txt")
    _write(repo, "u/octo.txt", "folded into an octopus merge\n")
    _git(repo, "add", "--", "u/c.txt", "u/octo.txt")
    tree = _git(repo, "write-tree")
    octo = _git(repo, "commit-tree", tree, "-p", head, "-p", c2, "-p", c1, "-m", "octopus")
    _git(repo, "reset", "-q", "--hard", octo)
    _git(repo, "checkout", "-q", _TARGET)
    return octo


def test_unreadable_own_content_records_no_entry(tmp_path: Path) -> None:
    """An octopus merge after the approval: the own-content probe raises, so no hint entry, no refusal, no authorship."""
    mission = _build_two_lane(tmp_path, variant="clean")
    octo = _add_post_approval_octopus(mission)
    assert len(_git(mission.repo, "rev-list", "--parents", "-n", "1", octo).split()) == 4, "fixture: a 3-parent merge"
    claim = _claim(mission)
    entries = getattr(claim, "unreviewed_merges", None)
    assert entries is not None
    assert octo not in {entry.sha for entry in entries}
    assert mission.merge in {entry.sha for entry in entries}, "the readable dropped merge is still recorded"
    assert octo not in claim.authored_shas


def test_dropped_merges_skips_a_sha_whose_parents_cannot_be_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.consolidation import reconciliation_authorship

    mission = _build_two_lane(tmp_path, variant="post")
    spine = _git(mission.repo, "rev-list", "--first-parent", f"{mission.base}..{_branch('lane-b')}").split()
    reviewed = [sha for sha in spine if sha != mission.merge]
    real: Callable[[Path, str], bool] = reconciliation_authorship.is_merge_commit
    assert reconciliation_authorship._dropped_merges(mission.repo, spine, reviewed) == (mission.merge,), "precondition: the merge is listed"

    def raising(repo_root: Path, sha: str) -> bool:
        if sha == mission.merge:
            raise reconciliation_authorship.GitProbeError("unreadable parents")
        return real(repo_root, sha)

    setattr_reconciliation_family(monkeypatch, "is_merge_commit", raising)
    assert reconciliation_authorship._dropped_merges(mission.repo, spine, reviewed) == ()


def test_hand_built_claim_defaults_to_no_unreviewed_merges() -> None:
    assert getattr(ApprovedWpCommitSet(), "unreviewed_merges", None) == ()


def test_replace_keeps_the_unreviewed_merges(tmp_path: Path) -> None:
    mission = _build_two_lane(tmp_path, variant="post")
    claim = _claim(mission)
    assert dataclasses.replace(claim, verify_reachability=False).unreviewed_merges == claim.unreviewed_merges


#: The number of ``ApprovedWpCommitSet`` fields before this work package (all but ``unreviewed_merges``).
_PRE_WP_FIELD_COUNT = 33


def test_positional_construction_with_the_pre_wp_arity_still_works() -> None:
    names = [f.name for f in dataclasses.fields(ApprovedWpCommitSet) if f.name != "unreviewed_merges"]
    assert len(names) == _PRE_WP_FIELD_COUNT
    defaults = ApprovedWpCommitSet()
    claim = ApprovedWpCommitSet(*(getattr(defaults, name) for name in names))
    assert claim == defaults


# --- T013: byte-identity ratchet on the existing claim fields ----------------------------------


def _canonical(value: Any) -> str:
    """A deterministic text form: sets and mapping items sorted recursively, ``repr`` for leaves."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        inner = ",".join(f"{f.name}={_canonical(getattr(value, f.name))}" for f in dataclasses.fields(value))
        return f"{type(value).__name__}({inner})"
    if isinstance(value, Mapping):
        return "{" + ",".join(sorted(f"{_canonical(k)}:{_canonical(v)}" for k, v in value.items())) + "}"
    if isinstance(value, (set, frozenset)):
        return "{" + ",".join(sorted(_canonical(v) for v in value)) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_canonical(v) for v in value) + "]"
    return repr(value)


def _field_digests(claim: ApprovedWpCommitSet, repo: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in dataclasses.fields(claim):
        if f.name == "unreviewed_merges":
            continue
        text = _canonical(getattr(claim, f.name)).replace(str(repo), "<REPO>")
        out[f.name] = hash_content(text)
    return out


#: Per-field digests recorded at the base (before any production change of this work package).
_GOLDEN: dict[str, dict[str, str]] = {
    "clean": {
        "approved": "sha256:4dd95e2636fafe2348c7e421479526386370e8a04945f9a00c881b292edac502",
        "approved_lane_content": "sha256:8a1dd6714895012bfb90e286c436b1b2f1d43ae16981b3492147222a18c21885",
        "attested_canceled_wp_ids": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "authored_blobs": "sha256:85e00590dd1b2b71c4c91dacc3c1a183e9028ff66975153911d0bbebc3701ed3",
        "authored_deletions": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "authored_patch_ids": "sha256:7f2eb54f46ca3de3351338954906ccd0d9721b5192ec84eebc80d02fedac2676",
        "authored_shas": "sha256:1a9c407be1c0bbd3435e5f1c684b458083569b003b0486d58b77454359d3c424",
        "bound_lane_branches": "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "bound_lane_tips": "sha256:7652ffb4624a52a7c708d0edd2fe1f757aee3f2f5ff594a27ce6e908549a1a19",
        "canceled_content": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "canceled_dependency_content": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "enforce_closed_world": "sha256:3cbc87c7681f34db4617feaa2c8801931bc5e42d8d0f560e756dd4cd92885f18",
        "excluded_patch_ids": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "excluded_shas": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "excluded_window_base": "sha256:3c1e71c7f90311aef24c5e412ebf7a9da9d9ace54f1c9587f37363ce1030328c",
        "external_dependency_blobs": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "external_dependency_deletions": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "external_dependency_pins": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "external_dependency_refs": "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "external_dependency_shas": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "manifest_wp_ids": "sha256:12efdecf07b2f7ff2ddd3717da35c95f25d27b56a0e8199224b6c37147f1aac9",
        "mission_base": "sha256:65d48cf5f438866a840c7005dec8c73c0ecdc90206604f1137d266484b85a77b",
        "mission_slug": "sha256:c36b8a5673f47eecb2dec6c503a4bd8dc6eee2dd175b64a05da62d1172c900e0",
        "no_implementation_attested_wp_ids": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "path_contributions": "sha256:2e972400b3a3653cd0d26062d6284a4ac773af2868cabd7c4a105764959b1f29",
        "planning_prefix": "sha256:d8d5690f6e60ffa65cd319fa936bcb21b0f4bef05bffea836b9af67aedcc77ba",
        "pre_mission_blobs": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "pre_mission_deletions": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "pre_mission_shas": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "refusal": "sha256:dc937b59892604f5a86ac96936cd7ff09e25f18ae6b758e8014a24c7fa039e91",
        "surface_resolved": "sha256:3cbc87c7681f34db4617feaa2c8801931bc5e42d8d0f560e756dd4cd92885f18",
        "verify_reachability": "sha256:3cbc87c7681f34db4617feaa2c8801931bc5e42d8d0f560e756dd4cd92885f18",
        "window_gaps": "sha256:0d5e0e2f78897ddcfdd6369dbf846f02069532099197765562772ea020572b1e",
    },
    "reviewed": {
        "approved": "sha256:6389c6b83952eff48ab081c021277445d8871e539fd32a05ca5c0a32373b69da",
        "approved_lane_content": "sha256:b00cdc221b4f14dd1067af845b4df20e07894759d3379000e0d7a22b8b603a7f",
        "attested_canceled_wp_ids": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "authored_blobs": "sha256:82b2b7a4d883d1731df1d2605d7f1b40bed2fd805fc8e50ff1ef753cec573440",
        "authored_deletions": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "authored_patch_ids": "sha256:b2cbf4c8820050ebc1c80111e85d2656f86e96ad9afb90500e18143a74ce897b",
        "authored_shas": "sha256:f075c51741a6bb783f2b261428364e0ef36307f96ebae89f3830e4e362ea5b87",
        "bound_lane_branches": "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "bound_lane_tips": "sha256:3e5b5b72b37fc9d00de7a817f3248b1d98c5f402f27b8e18352ee52b0a913b1d",
        "canceled_content": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "canceled_dependency_content": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "enforce_closed_world": "sha256:3cbc87c7681f34db4617feaa2c8801931bc5e42d8d0f560e756dd4cd92885f18",
        "excluded_patch_ids": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "excluded_shas": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "excluded_window_base": "sha256:3c1e71c7f90311aef24c5e412ebf7a9da9d9ace54f1c9587f37363ce1030328c",
        "external_dependency_blobs": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "external_dependency_deletions": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "external_dependency_pins": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "external_dependency_refs": "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "external_dependency_shas": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "manifest_wp_ids": "sha256:12efdecf07b2f7ff2ddd3717da35c95f25d27b56a0e8199224b6c37147f1aac9",
        "mission_base": "sha256:65d48cf5f438866a840c7005dec8c73c0ecdc90206604f1137d266484b85a77b",
        "mission_slug": "sha256:c36b8a5673f47eecb2dec6c503a4bd8dc6eee2dd175b64a05da62d1172c900e0",
        "no_implementation_attested_wp_ids": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "path_contributions": "sha256:cb3d0d8c8ca614c8a81142b0e1df4bd17e299db53b5739c1e1be1420c72b25c0",
        "planning_prefix": "sha256:d8d5690f6e60ffa65cd319fa936bcb21b0f4bef05bffea836b9af67aedcc77ba",
        "pre_mission_blobs": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "pre_mission_deletions": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "pre_mission_shas": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "refusal": "sha256:dc937b59892604f5a86ac96936cd7ff09e25f18ae6b758e8014a24c7fa039e91",
        "surface_resolved": "sha256:3cbc87c7681f34db4617feaa2c8801931bc5e42d8d0f560e756dd4cd92885f18",
        "verify_reachability": "sha256:3cbc87c7681f34db4617feaa2c8801931bc5e42d8d0f560e756dd4cd92885f18",
        "window_gaps": "sha256:0d5e0e2f78897ddcfdd6369dbf846f02069532099197765562772ea020572b1e",
    },
    "three-lane": {
        "approved": "sha256:95fb1265ed1b1f5344e7a5a06890280882452a1e4938697047e984a6a2f100bc",
        "approved_lane_content": "sha256:346aa9eeed95e001436bf381151a8a95cfc9269fc1a584e5818c7b3651b84635",
        "attested_canceled_wp_ids": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "authored_blobs": "sha256:eeb761b4cf5dd2eff846a97f9735b23358576abdcae46afd42fa52dd3c20ee92",
        "authored_deletions": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "authored_patch_ids": "sha256:e859491bcfe4445ad69a647c0c7877262c80dd4d85f149d21ce92591d5d62d1e",
        "authored_shas": "sha256:3f83a5f19878e74c683989470d5b0149cf7ad0c2358038ff486f07df98a46567",
        "bound_lane_branches": "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "bound_lane_tips": "sha256:a00975304845ab0b23476eaf98012e7030da059ac3143681767e9bdbb9b4c621",
        "canceled_content": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "canceled_dependency_content": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "enforce_closed_world": "sha256:3cbc87c7681f34db4617feaa2c8801931bc5e42d8d0f560e756dd4cd92885f18",
        "excluded_patch_ids": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "excluded_shas": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "excluded_window_base": "sha256:3a72acacc2e95dc2f4857cc039dcb104f24bb17d9f066d60b998b1250f73d956",
        "external_dependency_blobs": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "external_dependency_deletions": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "external_dependency_pins": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "external_dependency_refs": "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "external_dependency_shas": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "manifest_wp_ids": "sha256:da7c1146c2679b0b3a124ddb13ebdb51bc7036302ea3b3e309887b0b462c20da",
        "mission_base": "sha256:65d48cf5f438866a840c7005dec8c73c0ecdc90206604f1137d266484b85a77b",
        "mission_slug": "sha256:c36b8a5673f47eecb2dec6c503a4bd8dc6eee2dd175b64a05da62d1172c900e0",
        "no_implementation_attested_wp_ids": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "path_contributions": "sha256:12f86da7f4fbd8544e27b88cbc7a745d6cdbc2b2709310a831a8087182662422",
        "planning_prefix": "sha256:d8d5690f6e60ffa65cd319fa936bcb21b0f4bef05bffea836b9af67aedcc77ba",
        "pre_mission_blobs": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "pre_mission_deletions": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "pre_mission_shas": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "refusal": "sha256:dc937b59892604f5a86ac96936cd7ff09e25f18ae6b758e8014a24c7fa039e91",
        "surface_resolved": "sha256:3cbc87c7681f34db4617feaa2c8801931bc5e42d8d0f560e756dd4cd92885f18",
        "verify_reachability": "sha256:3cbc87c7681f34db4617feaa2c8801931bc5e42d8d0f560e756dd4cd92885f18",
        "window_gaps": "sha256:fc35456f38c525e64bb68ac645b91c2d5daded8a515989d3ecf804f5111da1e5",
    },
    "two-lane": {
        "approved": "sha256:6389c6b83952eff48ab081c021277445d8871e539fd32a05ca5c0a32373b69da",
        "approved_lane_content": "sha256:b00cdc221b4f14dd1067af845b4df20e07894759d3379000e0d7a22b8b603a7f",
        "attested_canceled_wp_ids": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "authored_blobs": "sha256:85e00590dd1b2b71c4c91dacc3c1a183e9028ff66975153911d0bbebc3701ed3",
        "authored_deletions": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "authored_patch_ids": "sha256:7f2eb54f46ca3de3351338954906ccd0d9721b5192ec84eebc80d02fedac2676",
        "authored_shas": "sha256:1a9c407be1c0bbd3435e5f1c684b458083569b003b0486d58b77454359d3c424",
        "bound_lane_branches": "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "bound_lane_tips": "sha256:3e5b5b72b37fc9d00de7a817f3248b1d98c5f402f27b8e18352ee52b0a913b1d",
        "canceled_content": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "canceled_dependency_content": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "enforce_closed_world": "sha256:3cbc87c7681f34db4617feaa2c8801931bc5e42d8d0f560e756dd4cd92885f18",
        "excluded_patch_ids": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "excluded_shas": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "excluded_window_base": "sha256:3c1e71c7f90311aef24c5e412ebf7a9da9d9ace54f1c9587f37363ce1030328c",
        "external_dependency_blobs": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "external_dependency_deletions": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "external_dependency_pins": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "external_dependency_refs": "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "external_dependency_shas": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "manifest_wp_ids": "sha256:12efdecf07b2f7ff2ddd3717da35c95f25d27b56a0e8199224b6c37147f1aac9",
        "mission_base": "sha256:65d48cf5f438866a840c7005dec8c73c0ecdc90206604f1137d266484b85a77b",
        "mission_slug": "sha256:c36b8a5673f47eecb2dec6c503a4bd8dc6eee2dd175b64a05da62d1172c900e0",
        "no_implementation_attested_wp_ids": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "path_contributions": "sha256:2e972400b3a3653cd0d26062d6284a4ac773af2868cabd7c4a105764959b1f29",
        "planning_prefix": "sha256:d8d5690f6e60ffa65cd319fa936bcb21b0f4bef05bffea836b9af67aedcc77ba",
        "pre_mission_blobs": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "pre_mission_deletions": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "pre_mission_shas": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "refusal": "sha256:dc937b59892604f5a86ac96936cd7ff09e25f18ae6b758e8014a24c7fa039e91",
        "surface_resolved": "sha256:3cbc87c7681f34db4617feaa2c8801931bc5e42d8d0f560e756dd4cd92885f18",
        "verify_reachability": "sha256:3cbc87c7681f34db4617feaa2c8801931bc5e42d8d0f560e756dd4cd92885f18",
        "window_gaps": "sha256:0d5e0e2f78897ddcfdd6369dbf846f02069532099197765562772ea020572b1e",
    },
}


@pytest.mark.parametrize("shape", sorted(_BUILDERS))
def test_existing_claim_fields_are_byte_identical(tmp_path: Path, shape: str) -> None:
    builds = []
    for run in ("first", "second"):
        mission = _BUILDERS[shape](tmp_path / run)
        builds.append(_field_digests(_claim(mission), mission.repo))
    assert builds[0] == builds[1], "fixture is not deterministic: two builds of one shape disagree"
    assert builds[0] == _GOLDEN[shape]
