"""#7860 (FR-012): the claim attributes a default Mission's planning lane against its Mission branch.

Before a default Mission lands, its planning lane writes to its Mission branch, which the
coordination base (the Mission branch's pre-mutation tip) already carries. Measured
``coord_base..<target>`` the planning lane authored nothing, so owned planning content outside the
bookkeeping paths (the pre-#7816 shape) read as un-attributable at the reconciliation gate. The
claim now walks ``<planning pin>..<coordination base>`` for that lane, crediting each approved work
package only for its own ``owned_files`` and only from its own claim commit (operator ruling R2),
keeping by SHA and patch-id only commits whose every path is credited (or bookkeeping) and by blob
only credited paths, so Mission-branch status, stray, mixed and pre-claim commits never read as
approved planning authorship. A lane holding any non-approved work package (ruling R1), a too-broad
or unreadable ownership, or an unprovable window start authors nothing (fail closed). Every other
shape keeps its range.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from pathlib import Path

import pytest

import mission_runtime
from specify_cli.consolidation import planning_lane_scope
from specify_cli.consolidation import reconciliation_authorship as authorship
from specify_cli.consolidation import planning_lane_walk as planning_walk
from specify_cli.consolidation.git_probes import GitProbeError, patch_id_of
from specify_cli.consolidation.mission_base import resolve_mission_base
from specify_cli.consolidation.reconciliation import ApprovedWpCommitSet, MergeOutcomeVerifier
from specify_cli.consolidation.reconciliation_verifier import VerifyStatus, _with_attribution_hint
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from tests._support.git_cli import git_out
from tests.consolidation.reconciliation_family import setattr_reconciliation_family

pytestmark = [pytest.mark.git_repo]

#: The real window-start reader, kept before the autouse stub replaces it (R2 unit tests below).
_REAL_WINDOW_STARTS = planning_walk._planning_window_starts

_SLUG = "auth-01M8EEEE"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"
_OWNED = "curation/apply_curation.py"
_PLANNING = ExecutionLane(PLANNING_LANE_ID, ("WP02",), (_OWNED,), (), (), 0)
_EMPTY_PLANNING = ExecutionLane(PLANNING_LANE_ID, ("WP02",), (), (), (), 0)
_CODE = ExecutionLane("lane-a", ("WP01",), ("src/**",), (), (), 0)


def _manifest(pin: str | None = "pin0000") -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=None,
        mission_branch=_MISSION_BRANCH,
        target_branch="main",
        lanes=[_CODE, _PLANNING],
        computed_at="2026-11-26T00:00:00+00:00",
        computed_from="test",
        planning_artifact_wps=["WP02"],
        planning_commit_sha=pin,
    )


def _reader(on_mission_branch: bool) -> object:
    def _read(*_args: object, **_kwargs: object) -> mission_runtime.PlanningWriteRef:
        return mission_runtime.PlanningWriteRef(branch=_MISSION_BRANCH if on_mission_branch else "main", on_mission_branch=on_mission_branch, landed=False)

    return _read


@pytest.fixture(autouse=True)
def _windows_start_at_the_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each approved planning work package's window starts at the planning pin unless a test says otherwise (R2)."""

    def _read(_repo_root: Path, manifest: LanesManifest, _lane: ExecutionLane, wp_ids: tuple[str, ...], _events: object) -> dict[str, str]:
        assert manifest.planning_commit_sha is not None
        return dict.fromkeys(wp_ids, manifest.planning_commit_sha)

    monkeypatch.setattr(planning_walk, "_planning_window_starts", _read)


# ---------------------------------------------------------------- the walk range


@pytest.mark.unit
def test_a_default_missions_planning_lane_walks_its_mission_branch_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))

    assert planning_walk._lane_walk_range(Path(), _manifest(), _PLANNING, "coord0000", None, (_OWNED,)) == ("pin0000", "coord0000", (_OWNED,))


@pytest.mark.unit
def test_every_other_shape_keeps_its_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(False))

    assert planning_walk._lane_walk_range(Path(), _manifest(), _PLANNING, "coord0000", None, (_OWNED,)) == ("coord0000", "main", ())
    assert planning_walk._lane_walk_range(Path(), _manifest(), _PLANNING, "coord0000", ("sb0", "sb1"), (_OWNED,)) == ("sb0", "sb1", ())
    assert planning_walk._lane_walk_range(Path(), _manifest(), _CODE, "coord0000", None, (_OWNED,)) == ("coord0000", f"kitty/mission-{_SLUG}-lane-a", ())


@pytest.mark.unit
def test_an_empty_write_scope_keeps_the_target_range(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty owned scope on the Mission-branch window authors nothing: it never widens to an unscoped walk."""
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))

    assert planning_walk._lane_walk_range(Path(), _manifest(), _PLANNING, "coord0000", None, ()) == ("coord0000", "main", ())


@pytest.mark.unit
def test_no_planning_pin_keeps_the_target_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))

    assert planning_walk._lane_walk_range(Path(), _manifest(pin=None), _PLANNING, "coord0000", None, (_OWNED,)) == ("coord0000", "main", ())


@pytest.mark.unit
@pytest.mark.parametrize(
    "error", [mission_runtime.PlanningWriteRefUnavailable(_SLUG, "meta.json is unreadable"), mission_runtime.PlanningCheckoutMissing(_SLUG, _MISSION_BRANCH)]
)
def test_an_undecidable_write_branch_keeps_the_target_range(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """The planning lane then authors nothing, so the gate still refuses content it cannot attribute (fail closed)."""

    def _raise(*_args: object, **_kwargs: object) -> mission_runtime.PlanningWriteRef:
        raise error

    monkeypatch.setattr(mission_runtime, "planning_write_ref", _raise)

    assert planning_walk._lane_walk_range(Path(), _manifest(), _PLANNING, "coord0000", None, (_OWNED,)) == ("coord0000", "main", ())


_TOO_BROAD = [
    # a wildcard in the first segment (``fnmatch``'s ``*`` crosses ``/``)
    "*",
    "**",
    "**/*",
    "*.py",
    "?rc/**",
    "[a-z]*/x.py",
    # one literal leading segment: as broad as the inference fallback ``src/**`` (#7860 review 3)
    "src/**",
    "src/*",
    "src",
    "src/",
    "src/**/*",
    "src/*/**",
    "src/**/*.py",
    "./src/**",
    "docs/*.md",
    "docs/**",
    "curation/**",
    # a top-level name with no extension, or a dot-file / dot-directory, reads as a directory
    ".github",
    "README.md/",
    # absolute paths and parent segments are refused outright
    "/abs/x",
    "../x",
    "src/../x.py",
    "",
    "src//x.py",
]


@pytest.mark.unit
@pytest.mark.parametrize("pattern", _TOO_BROAD)
def test_a_pattern_with_fewer_than_two_literal_leading_segments_is_unusable(pattern: str) -> None:
    """A pattern is too broad to scope the window unless two literal path segments lead it (or it names one top-level file)."""
    assert planning_lane_scope.is_whole_tree_pattern(pattern)


@pytest.mark.unit
@pytest.mark.parametrize(
    "pattern",
    [
        _OWNED,
        "curation/pkg/**",
        "src/specify_cli/**",
        "src/specify_cli/*.py",
        "docs/context/topology.md",
        f"kitty-specs/{_SLUG}/notes.md",
        "README.md",
        "pyproject.toml",
        "./README.md",
        "src/a/*b/**",
    ],
)
def test_an_anchored_pattern_is_usable(pattern: str) -> None:
    assert not planning_lane_scope.is_whole_tree_pattern(pattern)


@pytest.mark.unit
@pytest.mark.parametrize("pattern", ["src/*", "src", "src/", "src/**/*", "src/*/**", "src/**/*.py"])
def test_every_refused_spelling_of_src_does_match_the_whole_src_tree(pattern: str) -> None:
    """Why they are refused: each one owns a path no reasonable owner names (review 3 probe)."""
    from specify_cli.ownership.matching import matches_owned

    assert matches_owned("src/deep/nested/evil.py", (pattern,))


def _ownership(monkeypatch: pytest.MonkeyPatch, owned: dict[str, tuple[str, ...]]) -> list[tuple[str, ...]]:
    """Stub the planning work packages' ``owned_files`` read; returns the ids each call asked for."""
    asked: list[tuple[str, ...]] = []

    def _read(_repo_root: Path, _slug: str, wp_ids: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
        asked.append(tuple(wp_ids))
        return {wp: owned[wp] for wp in wp_ids if wp in owned}

    monkeypatch.setattr(planning_walk, "_planning_ownership", _read, raising=False)
    return asked


_PKG = "curation/pkg/**"
_CONFLICT_PATH = "curation/pkg/x.py"
_PKG_WP03 = "curation/pkg/wp03.py"
_TWO_WP_PLANNING = ExecutionLane(PLANNING_LANE_ID, ("WP02", "WP03"), (_OWNED, "curation/wp03.py"), (), (), 0)


@pytest.mark.unit
def test_the_scope_is_each_approved_work_packages_owned_files(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _ownership(monkeypatch, {"WP02": (_OWNED,), "WP03": ("curation/wp03.py",)})
    states = {"WP02": {"lane": "approved"}, "WP03": {"lane": "done"}}

    assert planning_walk._approved_planning_scope(Path(), _manifest(), _TWO_WP_PLANNING, states) == {"WP02": (_OWNED,), "WP03": ("curation/wp03.py",)}
    assert asked == [("WP02", "WP03")]


@pytest.mark.unit
def test_no_approved_work_package_gives_an_empty_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _ownership(monkeypatch, {"WP02": (_OWNED,)})

    assert not planning_walk._approved_planning_scope(Path(), _manifest(), _PLANNING, {"WP02": {"lane": "in_progress"}})
    assert asked == []


@pytest.mark.unit
def test_an_unreadable_approved_ownership_gives_an_empty_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """WP03 is approved but its owned_files cannot be read: no partial scope, the lane authors nothing (fail closed)."""
    _ownership(monkeypatch, {"WP02": (_OWNED,)})
    states = {"WP02": {"lane": "approved"}, "WP03": {"lane": "done"}}

    assert not planning_walk._approved_planning_scope(Path(), _manifest(), _TWO_WP_PLANNING, states)


@pytest.mark.unit
def test_a_whole_tree_pattern_makes_the_whole_scope_unusable(monkeypatch: pytest.MonkeyPatch) -> None:
    _ownership(monkeypatch, {"WP02": (_OWNED,), "WP03": ("src/**",)})
    states = {"WP02": {"lane": "approved"}, "WP03": {"lane": "approved"}}

    assert not planning_walk._approved_planning_scope(Path(), _manifest(), _TWO_WP_PLANNING, states)


@pytest.mark.integration
def test_the_ownership_reader_returns_only_resolved_work_packages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The reader delegates to the evidence axis' one ``owned_files`` read and drops every unresolved id."""
    from specify_cli.consolidation import wp_evidence

    seen: list[tuple[str, ...]] = []

    def _read(repo_root: Path, slug: str, feature_dir: Path, wp_ids: tuple[str, ...]) -> tuple[dict[str, tuple[str, ...]], dict[str, str], Path]:
        seen.append(tuple(wp_ids))
        assert (repo_root, slug) == (tmp_path, _SLUG)
        return {"WP02": (_OWNED,)}, {"WP03": "unreadable"}, tmp_path

    monkeypatch.setattr(wp_evidence, "read_wp_ownership", _read)

    assert planning_walk._planning_ownership(tmp_path, _SLUG, ("WP02", "WP03")) == {"WP02": (_OWNED,)}
    assert seen == [("WP02", "WP03")]


# ---------------------------------------------------------------- real git


def _git(repo: Path, *args: str) -> str:
    return git_out(repo, *args).strip()


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    for relpath, text in files.items():
        (repo / relpath).parent.mkdir(parents=True, exist_ok=True)
        (repo / relpath).write_text(text, encoding="utf-8")
        _git(repo, "add", "--", relpath)
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _mission(tmp_path: Path) -> tuple[Path, str, dict[str, str]]:
    """A default, not-landed Mission on its Mission branch: status, owned, owned+status, mixed and stray commits."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    _commit(repo, {"README.md": "x\n"}, "init")
    _git(repo, "switch", "-qc", _MISSION_BRANCH)
    meta = {"mission_slug": _SLUG, "target_branch": "main", "topology": "lanes_with_coord", "topology_source": "default", "mission_branch": _MISSION_BRANCH}
    pin = _commit(repo, {f"kitty-specs/{_SLUG}/meta.json": json.dumps(meta)}, "planning")
    shas = {
        "status": _commit(repo, {f"kitty-specs/{_SLUG}/status.events.jsonl": "{}\n"}, "chore: status"),
        "owned": _commit(repo, {_OWNED: "VALUE = 1\n"}, "feat(WP02): curation"),
        "owned_and_status": _commit(repo, {_OWNED: "VALUE = 2\n", f"kitty-specs/{_SLUG}/status.events.jsonl": "{}\n{}\n"}, "feat(WP02): curation + status"),
        "mixed": _commit(repo, {_OWNED: "VALUE = 3\n", "sneaky.py": "X = 1\n"}, "feat(WP02): curation and more"),
        "stray": _commit(repo, {"stray.py": "Y = 1\n"}, "stray commit on the Mission branch"),
    }
    return repo, pin, shas


def _planning_claim(repo: Path, pin: str, lane: ExecutionLane, states: dict[str, dict[str, object]]) -> tuple[str, authorship._AuthoredClaim]:
    coord_base = _git(repo, "rev-parse", _MISSION_BRANCH)
    manifest = _manifest(pin=pin)
    manifest.lanes = [lane]
    # The Mission base as the claim resolves it (``build_approved_wp_set``): the taint walk starts there (review 9).
    mission_base = resolve_mission_base(repo, None, mission_branch=_MISSION_BRANCH, mission_slug=_SLUG).sha
    assert mission_base is not None
    return coord_base, authorship._collect_authored(repo, manifest, states, coord_base, None, canceled_lane_commits=frozenset(), mission_base=mission_base)


def _commit_set(repo: Path, claim: authorship._AuthoredClaim) -> ApprovedWpCommitSet:
    """The production claim's shape, as :func:`build_approved_wp_set` fills it from :func:`_collect_authored`.

    The window base is the target tip, as in production (``claim_inputs.build_claim`` passes the
    target's pre-run tip), never the planning pin: a pin base would hide every Mission-branch
    commit below the pin from the squash axis (review 9).
    """
    return ApprovedWpCommitSet(
        approved={"WP02": tuple(sorted(claim.shas))},
        manifest_wp_ids=frozenset({"WP02", "WP03"}),
        excluded_window_base=_git(repo, "rev-parse", "main"),
        enforce_closed_world=True,
        authored_shas=claim.shas,
        authored_patch_ids=claim.patch_ids,
        authored_blobs=claim.blobs,
        authored_deletions=claim.deletions,
        mission_slug=_SLUG,
    )


@pytest.mark.integration
def test_scoped_commits_keep_touching_commits_and_name_the_whole_ones(tmp_path: Path) -> None:
    """A commit enters by SHA only when every path it changes is in scope or bookkeeping; a mixed one only touches."""
    repo, pin, shas = _mission(tmp_path)
    spine = git_out(repo, "rev-list", "--first-parent", f"{pin}..HEAD").split()

    scoped = planning_walk._scoped_commits(repo, spine, planning_walk._PlanningScope((((_OWNED,), frozenset(spine)),)), _SLUG)

    assert scoped.touching == [shas["mixed"], shas["owned_and_status"], shas["owned"]]
    assert scoped.whole == frozenset({shas["owned"], shas["owned_and_status"]})


@pytest.mark.integration
def test_an_unreadable_commit_is_dropped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _pin, shas = _mission(tmp_path)

    def _broken(_repo: Path, _sha: str) -> list[str]:
        raise GitProbeError("git show failed")

    setattr_reconciliation_family(monkeypatch, "changed_paths_of", _broken)

    scoped = planning_walk._scoped_commits(repo, [shas["owned"]], planning_walk._PlanningScope((((_OWNED,), frozenset({shas["owned"]})),)), _SLUG)
    assert scoped.touching == [] and scoped.whole == frozenset()


@pytest.mark.integration
def test_the_claim_attributes_the_owned_planning_content_and_nothing_else(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The owned file's final blob is approved authorship; the stray and sneaked-in paths, and the mixed commit, are not."""
    repo, pin, shas = _mission(tmp_path)
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_OWNED,)})

    coord_base, claim = _planning_claim(repo, pin, _PLANNING, {"WP02": {"lane": "approved"}})

    owned_blob = _git(repo, "rev-parse", f"{coord_base}:{_OWNED}")
    assert (_OWNED, owned_blob) in claim.blobs
    assert {path for path, _blob in claim.blobs} == {_OWNED}
    assert claim.shas == {shas["owned"], shas["owned_and_status"]}
    assert shas["mixed"] not in claim.shas and shas["stray"] not in claim.shas and shas["status"] not in claim.shas
    assert len(claim.patch_ids) == 2


@pytest.mark.integration
def test_the_merge_strategy_closed_world_refuses_the_mixed_and_stray_commits_and_a_cherry_pick(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifier level (merge / rebase): the mixed commit, its cherry-picked copy and the stray commit are un-attributable."""
    repo, pin, shas = _mission(tmp_path)
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_OWNED,)})
    coord_base, claim = _planning_claim(repo, pin, _PLANNING, {"WP02": {"lane": "approved"}})
    _git(repo, "switch", "-qc", "side", shas["owned_and_status"])
    _git(repo, "cherry-pick", shas["mixed"])
    copy = _git(repo, "rev-parse", "HEAD")
    verifier = MergeOutcomeVerifier(repo)
    commit_set = _commit_set(repo, claim)

    flagged = {sha for sha, _pid in verifier._unattributable_in((coord_base, "side"), commit_set)}

    assert flagged == {shas["mixed"], shas["stray"], copy}


@pytest.mark.integration
def test_the_squash_blob_axis_refuses_the_stray_and_sneaked_in_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, pin, _shas = _mission(tmp_path)
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_OWNED,)})
    coord_base, claim = _planning_claim(repo, pin, _PLANNING, {"WP02": {"lane": "approved"}})

    result = MergeOutcomeVerifier(repo)._verify_squash_content(coord_base, _commit_set(repo, claim))

    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert {path for path, _blob in result.divergence.unattributable_blobs} == {"stray.py", "sneaky.py"}


@pytest.mark.integration
def test_a_canceled_planning_work_packages_content_stays_out_of_the_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WP02 approved, WP03 canceled: the lane authors nothing at all (R1), so WP03's commit is in neither ``blobs`` nor ``shas``."""
    repo, pin, _shas = _mission(tmp_path)
    _git(repo, "switch", "-q", _MISSION_BRANCH)
    wp03 = _commit(repo, {"curation/wp03.py": "Z = 1\n"}, "feat(WP03): canceled work")
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_OWNED,), "WP03": ("curation/wp03.py",)})

    _coord_base, claim = _planning_claim(repo, pin, _TWO_WP_PLANNING, {"WP02": {"lane": "approved"}, "WP03": {"lane": "canceled"}})

    assert "curation/wp03.py" not in {path for path, _blob in claim.blobs}
    assert wp03 not in claim.shas
    assert not claim.blobs and not claim.shas


@pytest.mark.integration
def test_two_approved_work_packages_each_credit_their_own_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Control for the R1 probes: with every planning work package approved, each one's own commit is attributed."""
    repo, pin, _shas = _mission(tmp_path)
    _git(repo, "switch", "-q", _MISSION_BRANCH)
    wp02 = _commit(repo, {"curation/pkg/wp02.py": "W = 1\n"}, "feat(WP02): approved work")
    wp03 = _commit(repo, {"curation/other/wp03.py": "Z = 1\n"}, "feat(WP03): disjoint work")
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_PKG,), "WP03": ("curation/other/wp03.py",)})
    lane = ExecutionLane(PLANNING_LANE_ID, ("WP02", "WP03"), (_PKG, "curation/other/wp03.py"), (), (), 0)

    _coord_base, claim = _planning_claim(repo, pin, lane, {"WP02": {"lane": "approved"}, "WP03": {"lane": "done"}})

    assert wp02 in claim.shas and wp03 in claim.shas
    assert {path for path, _blob in claim.blobs} == {"curation/pkg/wp02.py", "curation/other/wp03.py"}


@pytest.mark.integration
@pytest.mark.parametrize("state", ["canceled", "for_review", "in_progress"])
def test_an_overlapping_non_approved_work_packages_commit_stays_out_of_the_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str) -> None:
    """Review 3 probe: WP02 approved owns ``curation/pkg/**``, WP03 owns ``curation/pkg/wp03.py``; WP03's commit is in neither ``shas`` nor ``blobs``."""
    repo, pin, shas = _mission(tmp_path)
    _git(repo, "switch", "-q", _MISSION_BRANCH)
    _commit(repo, {"curation/pkg/wp02.py": "W = 1\n"}, "feat(WP02): approved work")
    wp03 = _commit(repo, {_PKG_WP03: "Z = 1\n"}, "feat(WP03): overlapping work")
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_PKG,), "WP03": (_PKG_WP03,)})
    lane = ExecutionLane(PLANNING_LANE_ID, ("WP02", "WP03"), (_PKG, _PKG_WP03), (), (), 0)

    _coord_base, claim = _planning_claim(repo, pin, lane, {"WP02": {"lane": "approved"}, "WP03": {"lane": state}})

    assert wp03 not in claim.shas
    assert _PKG_WP03 not in {path for path, _blob in claim.blobs}
    assert not claim.shas & set(shas.values())


@pytest.mark.integration
@pytest.mark.parametrize("pattern", ["*", "**", "**/*", "src/**", "src/*", "src", "src/**/*.py"])
def test_a_whole_tree_scope_authors_nothing_on_the_mission_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pattern: str) -> None:
    """A whole-tree or inferred-fallback owned glob would turn the window into an unscoped walk: the lane authors nothing instead."""
    repo, pin, shas = _mission(tmp_path)
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_OWNED, pattern)})
    lane = ExecutionLane(PLANNING_LANE_ID, ("WP02",), (_OWNED, pattern), (), (), 0)

    _coord_base, claim = _planning_claim(repo, pin, lane, {"WP02": {"lane": "approved"}})

    assert not claim.blobs
    assert not claim.shas & set(shas.values())


@pytest.mark.integration
def test_without_the_mission_branch_rule_the_planning_lane_authors_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: the pre-#7860 range ``coord_base..<target>`` is empty for work that sits on the Mission branch."""
    repo, pin, _shas = _mission(tmp_path)
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(False))
    _ownership(monkeypatch, {"WP02": (_OWNED,)})

    _coord_base, claim = _planning_claim(repo, pin, _PLANNING, {"WP02": {"lane": "approved"}})

    assert not claim.blobs


@pytest.mark.integration
def test_an_empty_planning_write_scope_authors_nothing_on_the_mission_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``planning_artifact`` WP with ``owned_files: []`` gives the planning lane an empty scope: status, stray and code commits stay unattributed."""
    repo, pin, shas = _mission(tmp_path)
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": ()})

    _coord_base, claim = _planning_claim(repo, pin, _EMPTY_PLANNING, {"WP02": {"lane": "approved"}})

    paths = {path for path, _blob in claim.blobs}
    assert not paths & {"stray.py", "sneaky.py", f"kitty-specs/{_SLUG}/status.events.jsonl", _OWNED}
    assert not claim.shas & set(shas.values())


@pytest.mark.integration
def test_an_all_empty_ownership_note_prints_with_the_squash_fail_it_explains(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review 7 issue 2: empty ``write_scope`` and ``owned_files``; the reason-4 note now rides on the squash FAIL."""
    repo, pin, _shas = _mission(tmp_path)
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": ()})
    coord_base, claim = _planning_claim(repo, pin, _EMPTY_PLANNING, {"WP02": {"lane": "approved"}})
    manifest = _manifest(pin=pin)
    manifest.lanes = [_EMPTY_PLANNING]
    notes = planning_lane_scope.planning_lane_notes(repo, manifest, {"WP02": {"lane": "approved"}}, coord_base, None, lambda: [])
    # A code lane's approved work stands beside it, as in a real Mission, so the squash axis judges paths.
    code_blob = _git(repo, "rev-parse", f"{coord_base}:README.md")
    commit_set = dataclasses.replace(
        _commit_set(repo, claim), approved={"WP01": (pin,)}, authored_blobs=claim.blobs | {("README.md", code_blob)}, planning_lane_notes=notes
    )

    result = _with_attribution_hint(MergeOutcomeVerifier(repo)._verify_squash_content(coord_base, commit_set), commit_set)

    assert result.status is VerifyStatus.FAIL
    assert "every planning work package's owned_files list is empty" in result.recovery_guidance()


# ---------------------------------------------------------------- review 4: operator rulings R1 and R2 (2026-11-27)


def _starts(monkeypatch: pytest.MonkeyPatch, starts: dict[str, str] | None) -> None:
    """Stub each approved planning work package's window start (its claim commit on the Mission branch)."""

    def _read(_repo_root: Path, _manifest: LanesManifest, _lane: ExecutionLane, wp_ids: tuple[str, ...], _events: object) -> dict[str, str] | None:
        return None if starts is None else {wp: starts[wp] for wp in wp_ids if wp in starts}

    monkeypatch.setattr(planning_walk, "_planning_window_starts", _read)


@pytest.mark.unit
@pytest.mark.parametrize("state", ["canceled", "for_review", "in_progress", "planned", "blocked", "claimed"])
def test_any_non_approved_planning_work_package_empties_the_scope(monkeypatch: pytest.MonkeyPatch, state: str) -> None:
    """R1: the claim admits by path, not by author, so a lane holding a non-approved work package authors nothing, even with disjoint ownership."""
    asked = _ownership(monkeypatch, {"WP02": (_OWNED,), "WP03": ("docs/other/x.md",)})

    assert not planning_walk._approved_planning_scope(Path(), _manifest(), _TWO_WP_PLANNING, {"WP02": {"lane": "approved"}, "WP03": {"lane": state}})
    assert asked == []


@pytest.mark.unit
def test_a_planning_work_package_with_no_status_row_empties_the_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    _ownership(monkeypatch, {"WP02": (_OWNED,), "WP03": ("docs/other/x.md",)})

    assert not planning_walk._approved_planning_scope(Path(), _manifest(), _TWO_WP_PLANNING, {"WP02": {"lane": "approved"}})


def _r1_mission(tmp_path: Path) -> tuple[Path, str, str, str]:
    """WP02 (approved) owns ``curation/pkg/**``; WP02 commits ``wp02.py``, then WP03 commits into WP02's path."""
    repo, pin, _shas = _mission(tmp_path)
    _git(repo, "switch", "-q", _MISSION_BRANCH)
    wp02 = _commit(repo, {"curation/pkg/wp02.py": "W = 1\n"}, "feat(WP02): approved work")
    wp03 = _commit(repo, {"curation/pkg/x.py": "Z = 1\n"}, "feat(WP03): into WP02's path")
    return repo, pin, wp02, wp03


@pytest.mark.integration
@pytest.mark.parametrize(
    ("wp03_owned", "state"),
    [((), "canceled"), (("docs/other/x.md",), "canceled"), (("docs/other/x.md",), "in_progress"), ((), "for_review")],
)
def test_a_non_approved_work_packages_commit_into_the_approved_path_is_never_credited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wp03_owned: tuple[str, ...], state: str
) -> None:
    """R1 (review 4 issue 1): empty, disjoint or in-flight, WP03's commit to ``curation/pkg/x.py`` must not read as WP02's; the lane authors nothing."""
    repo, pin, wp02, wp03 = _r1_mission(tmp_path)
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_PKG,), "WP03": wp03_owned})
    _starts(monkeypatch, {"WP02": pin})
    lane = ExecutionLane(PLANNING_LANE_ID, ("WP02", "WP03"), (_PKG, *wp03_owned), (), (), 0)

    _coord_base, claim = _planning_claim(repo, pin, lane, {"WP02": {"lane": "approved"}, "WP03": {"lane": state}})

    assert wp03 not in claim.shas and wp02 not in claim.shas
    assert not claim.blobs


def _r2_mission(tmp_path: Path) -> tuple[Path, str, str, str, str]:
    """WP02 owns ``curation/pkg/**``: one owned change before its claim commit, the claim commit, one owned change after it."""
    repo, pin, _shas = _mission(tmp_path)
    _git(repo, "switch", "-q", _MISSION_BRANCH)
    early = _commit(repo, {"curation/pkg/early.py": "E = 1\n"}, "an owned change before WP02 was claimed")
    claim_commit = _commit(repo, {f"kitty-specs/{_SLUG}/status.events.jsonl": "{}\n{}\n{}\n"}, "chore: claim WP02")
    late = _commit(repo, {"curation/pkg/late.py": "L = 1\n"}, "feat(WP02): after the claim")
    return repo, pin, early, claim_commit, late


@pytest.mark.integration
def test_an_owned_change_made_before_the_claim_is_not_credited_one_after_it_is(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R2: each approved work package's credit starts at its own claim commit, not at the planning pin."""
    repo, pin, early, claim_commit, late = _r2_mission(tmp_path)
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_PKG,)})
    _starts(monkeypatch, {"WP02": claim_commit})
    lane = ExecutionLane(PLANNING_LANE_ID, ("WP02",), (_PKG,), (), (), 0)

    _coord_base, claim = _planning_claim(repo, pin, lane, {"WP02": {"lane": "approved"}})

    assert late in claim.shas and early not in claim.shas
    assert {path for path, _blob in claim.blobs} == {"curation/pkg/late.py"}
    assert not claim.deletions


def _r2_merge_mission(tmp_path: Path) -> tuple[Path, str, dict[str, str]]:
    """The claim commit reaches the Mission branch through a merge (review 5 issue 1).

    The Mission branch forks a side branch that holds an owned change and then WP02's claim commit;
    the Mission branch meanwhile commits an owned change (``early``), merges the side branch
    (``merge``), then commits WP02's work (``late``). ``early`` and ``side_early`` predate the claim.
    """
    repo, pin, _shas = _mission(tmp_path)
    _git(repo, "switch", "-qc", "side", _MISSION_BRANCH)
    side_early = _commit(repo, {"curation/pkg/side_early.py": "S = 1\n"}, "an owned change on the side branch before the claim")
    claim_commit = _commit(repo, {f"kitty-specs/{_SLUG}/status.events.jsonl": "{}\n{}\n{}\n"}, "chore: claim WP02")
    _git(repo, "switch", "-q", _MISSION_BRANCH)
    early = _commit(repo, {"curation/pkg/early.py": "E = 1\n"}, "an owned change on the Mission branch before the claim was merged in")
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "side")
    merge = _git(repo, "rev-parse", "HEAD")
    late = _commit(repo, {"curation/pkg/late.py": "L = 1\n"}, "feat(WP02): after the claim")
    return repo, pin, {"side_early": side_early, "claim": claim_commit, "early": early, "merge": merge, "late": late}


@pytest.mark.integration
def test_a_change_the_claim_does_not_reach_across_a_merge_is_not_credited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R2, review 5 issue 1: only descendants of the claim commit count (``--ancestry-path``); no merge is in a window (review 6)."""
    repo, pin, shas = _r2_merge_mission(tmp_path)
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_PKG,)})
    _starts(monkeypatch, {"WP02": shas["claim"]})
    lane = ExecutionLane(PLANNING_LANE_ID, ("WP02",), (_PKG,), (), (), 0)

    _coord_base, claim = _planning_claim(repo, pin, lane, {"WP02": {"lane": "approved"}})

    assert shas["late"] in claim.shas
    assert shas["early"] not in claim.shas and shas["merge"] not in claim.shas and shas["side_early"] not in claim.shas
    assert {path for path, _blob in claim.blobs} == {"curation/pkg/late.py"}
    assert not claim.deletions


def _conflict_merge(repo: Path, path: str, resolved: str) -> str:
    """Merge ``side`` into the Mission branch, resolve the conflict at *path* to *resolved*, and return the merge."""
    subprocess.run(["git", "merge", "-q", "--no-ff", "--no-edit", "side"], cwd=repo, capture_output=True, check=False)
    (repo / path).write_text(resolved, encoding="utf-8")
    _git(repo, "add", "--", path)
    _git(repo, "commit", "-qm", "merge side, conflict resolved")
    return _git(repo, "rev-parse", "HEAD")


def _r2_conflict_mission(tmp_path: Path) -> tuple[Path, str, dict[str, str]]:
    """The review-6 shape: the claim and an owned change on a side branch; the Mission branch edits that path before the merge.

    The merge conflicts at ``curation/pkg/x.py`` and is resolved keeping both lines, so its blob holds
    ``early``'s pre-claim line.
    """
    repo, pin, _shas = _mission(tmp_path)
    _git(repo, "switch", "-q", _MISSION_BRANCH)
    _commit(repo, {_CONFLICT_PATH: "BASE = 0\n"}, "the owned file, before the planning work")
    _git(repo, "switch", "-qc", "side", _MISSION_BRANCH)
    claim_commit = _commit(repo, {f"kitty-specs/{_SLUG}/status.events.jsonl": "{}\n{}\n{}\n"}, "chore: claim WP02")
    side = _commit(repo, {_CONFLICT_PATH: "BASE = 0\nS = 1\n"}, "feat(WP02): after the claim, on the side branch")
    _git(repo, "switch", "-q", _MISSION_BRANCH)
    early = _commit(repo, {_CONFLICT_PATH: "BASE = 0\nE = 1  # pre-claim\n"}, "an owned change before the claim was merged in")
    merge = _conflict_merge(repo, _CONFLICT_PATH, "BASE = 0\nE = 1  # pre-claim\nS = 1\n")
    return repo, pin, {"claim": claim_commit, "side": side, "early": early, "merge": merge}


@pytest.mark.integration
def test_a_merge_that_resolves_a_conflict_in_an_owned_path_credits_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R2, review 6 issue 1: a conflict-resolving merge carries pre-claim content, so no merge credits anything.

    The merge descends from the claim commit and lists the resolved path, but it is not credited: not by
    SHA, not by patch-id, not by its blob. The path's newest touching commit is that merge, so the path is
    attributed to nothing at all (fail closed).
    """
    repo, pin, shas = _r2_conflict_mission(tmp_path)
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_PKG,)})
    _starts(monkeypatch, {"WP02": shas["claim"]})
    lane = ExecutionLane(PLANNING_LANE_ID, ("WP02",), (_PKG,), (), (), 0)

    _coord_base, claim = _planning_claim(repo, pin, lane, {"WP02": {"lane": "approved"}})

    assert shas["merge"] not in claim.shas and shas["early"] not in claim.shas
    merge_patch_id = patch_id_of(repo, shas["merge"])
    assert not merge_patch_id or merge_patch_id not in claim.patch_ids
    assert _CONFLICT_PATH not in {path for path, _blob in claim.blobs}
    assert _CONFLICT_PATH not in claim.deletions


@pytest.mark.integration
def test_an_owned_path_a_merge_changed_last_falls_back_to_no_older_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review 6 issue 1: the credited change before a conflict-resolving merge never stands in for the merge's blob."""
    repo, pin, _shas = _mission(tmp_path)
    _git(repo, "switch", "-q", _MISSION_BRANCH)
    _commit(repo, {_CONFLICT_PATH: "BASE = 0\n"}, "the owned file, before the planning work")
    _git(repo, "switch", "-qc", "side", _MISSION_BRANCH)
    _commit(repo, {_CONFLICT_PATH: "BASE = 0\nOTHER = 1\n"}, "a change on a side branch")
    _git(repo, "switch", "-q", _MISSION_BRANCH)
    claim_commit = _commit(repo, {f"kitty-specs/{_SLUG}/status.events.jsonl": "{}\n{}\n{}\n"}, "chore: claim WP02")
    credited = _commit(repo, {_CONFLICT_PATH: "BASE = 0\nW = 1\n"}, "feat(WP02): after the claim")
    merge = _conflict_merge(repo, _CONFLICT_PATH, "BASE = 0\nW = 1\nOTHER = 1\n")
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_PKG,)})
    _starts(monkeypatch, {"WP02": claim_commit})
    lane = ExecutionLane(PLANNING_LANE_ID, ("WP02",), (_PKG,), (), (), 0)

    _coord_base, claim = _planning_claim(repo, pin, lane, {"WP02": {"lane": "approved"}})

    assert credited in claim.shas and merge not in claim.shas
    assert _CONFLICT_PATH not in {path for path, _blob in claim.blobs}
    assert _CONFLICT_PATH not in claim.deletions


_SAME_PATH = "curation/pkg/same.py"


def _same_file_mission(tmp_path: Path, *, pre_claim: dict[str, str] | None, after_claim: dict[str, str] | None = None) -> tuple[Path, str, dict[str, str]]:
    """A clean default Mission: *pre_claim* (if any), WP02's claim commit, then WP02's own change.

    WP02 owns ``curation/pkg/**``. Its own change is *after_claim* (default: appends ``L = 1`` to
    :data:`_SAME_PATH`), so a pre-claim change to that file rides in the credited commit's blob.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (("init", "-q", "-b", "main"), ("config", "user.email", "t@example.com"), ("config", "user.name", "Test"), ("config", "commit.gpgsign", "false")):
        _git(repo, *args)
    _commit(repo, {"README.md": "x\n"}, "init")
    _git(repo, "switch", "-qc", _MISSION_BRANCH)
    meta = {"mission_slug": _SLUG, "target_branch": "main", "topology": "lanes_with_coord", "topology_source": "default", "mission_branch": _MISSION_BRANCH}
    pin = _commit(repo, {f"kitty-specs/{_SLUG}/meta.json": json.dumps(meta)}, "planning")
    shas = {"pin": pin}
    if pre_claim is not None:
        shas["early"] = _commit(repo, pre_claim, "an owned change before WP02 was claimed")
    shas["claim"] = _commit(repo, {f"kitty-specs/{_SLUG}/status.events.jsonl": "{}\n"}, "chore: claim WP02")
    early_text = (pre_claim or {}).get(_SAME_PATH, "")
    shas["late"] = _commit(repo, after_claim or {_SAME_PATH: early_text + "L = 1\n"}, "feat(WP02): after the claim")
    return repo, pin, shas


def _wp02_claim(repo: Path, pin: str, claim_commit: str, monkeypatch: pytest.MonkeyPatch) -> tuple[str, authorship._AuthoredClaim]:
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_PKG,)})
    _starts(monkeypatch, {"WP02": claim_commit})
    lane = ExecutionLane(PLANNING_LANE_ID, ("WP02",), (_PKG,), (), (), 0)
    return _planning_claim(repo, pin, lane, {"WP02": {"lane": "approved"}})


@pytest.mark.integration
def test_a_pre_claim_change_never_rides_a_credited_commits_blob(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R2, review 7 issue 1: a path an uncredited commit changed on the walk is attributed to nothing.

    ``late`` is credited, but its blob of ``same.py`` still holds ``early``'s pre-claim line, so
    neither that blob nor a deletion is attributed (fail closed).
    """
    repo, pin, shas = _same_file_mission(tmp_path, pre_claim={_SAME_PATH: "E = 1  # pre-claim, never reviewed\n"})

    coord_base, claim = _wp02_claim(repo, pin, shas["claim"], monkeypatch)

    assert shas["early"] not in claim.shas
    assert _SAME_PATH not in {path for path, _blob in claim.blobs}
    assert _SAME_PATH not in claim.deletions
    result = MergeOutcomeVerifier(repo)._verify_squash_content(coord_base, _commit_set(repo, claim))
    # No blob or deletion is left to attribute while WP02 resolved commits: the squash axis refuses.
    assert result.status is VerifyStatus.REFUSE


@pytest.mark.integration
def test_a_pre_claim_change_to_a_path_the_work_package_then_deletes_attributes_no_deletion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review 7 issue 1: a credited deletion is not attributed either when an uncredited commit changed the path."""
    repo, pin, shas = _same_file_mission(tmp_path, pre_claim={_SAME_PATH: "E = 1\n"}, after_claim={"curation/pkg/other.py": "O = 1\n"})
    _git(repo, "rm", "-q", "--", _SAME_PATH)
    _git(repo, "commit", "-qm", "feat(WP02): drop same.py")

    _coord_base, claim = _wp02_claim(repo, pin, shas["claim"], monkeypatch)

    assert _SAME_PATH not in claim.deletions
    assert _SAME_PATH not in {path for path, _blob in claim.blobs}
    assert "curation/pkg/other.py" in {path for path, _blob in claim.blobs}


@pytest.mark.integration
def test_a_clean_merge_of_a_pre_claim_change_taints_the_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review 7 issue 1: a clean merge's first-parent diff counts as a change no window credits."""
    repo, pin, shas = _same_file_mission(tmp_path, pre_claim=None, after_claim={"curation/pkg/other.py": "O = 1\n"})
    _git(repo, "switch", "-qc", "side", shas["pin"])
    _commit(repo, {_SAME_PATH: "E = 1  # pre-claim, on a side branch\n"}, "an owned change on a side branch")
    _git(repo, "switch", "-q", _MISSION_BRANCH)
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "side")
    touch = _commit(repo, {_SAME_PATH: "E = 1  # pre-claim, on a side branch\nL = 1\n"}, "feat(WP02): touch same.py")

    coord_base, claim = _wp02_claim(repo, pin, shas["claim"], monkeypatch)

    assert touch in claim.shas
    assert _SAME_PATH not in {path for path, _blob in claim.blobs}
    assert "curation/pkg/other.py" in {path for path, _blob in claim.blobs}
    result = MergeOutcomeVerifier(repo)._verify_squash_content(coord_base, _commit_set(repo, claim))
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert {path for path, _blob in result.divergence.unattributable_blobs} == {_SAME_PATH}


@pytest.mark.integration
def test_without_a_pre_claim_change_the_credited_blob_is_attributed_and_the_squash_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The control of review 7 issue 1: status commits on the walk change no owned path, so a normal Mission still lands."""
    repo, pin, shas = _same_file_mission(tmp_path, pre_claim=None)
    _commit(repo, {f"kitty-specs/{_SLUG}/status.events.jsonl": "{}\n{}\n"}, "chore: WP02 for_review")

    coord_base, claim = _wp02_claim(repo, pin, shas["claim"], monkeypatch)

    assert (_SAME_PATH, _git(repo, "rev-parse", f"{shas['late']}:{_SAME_PATH}")) in claim.blobs
    result = MergeOutcomeVerifier(repo)._verify_squash_content(coord_base, _commit_set(repo, claim))
    assert result.status is VerifyStatus.PASS


_PRE = "curation/pkg/pre.py"
_MOVED = "curation/pkg/moved.py"
_OTHER = "curation/pkg/other.py"
_PRE_TEXT = "E = 1  # pre-claim, never reviewed\nF = 2\nG = 3\nH = 4\n"


def _credited_paths(claim: authorship._AuthoredClaim) -> set[str]:
    return {path for path, _blob in claim.blobs}


@pytest.mark.integration
def test_a_credited_rename_of_a_pre_claim_file_carries_its_taint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review 8 issue 2: a pre-claim file ``git mv``'d by a credited commit stays un-attributed under its new name.

    Read with ``--no-renames`` the move's only change to ``moved.py`` is the credited commit, so the
    pre-claim blob was credited and the squash axis passed. The rename now inherits the source's taint.
    """
    repo, pin, shas = _same_file_mission(tmp_path, pre_claim={_PRE: _PRE_TEXT}, after_claim={_OTHER: "O = 1\n"})
    _git(repo, "mv", _PRE, _MOVED)
    _git(repo, "commit", "-qm", "feat(WP02): move pre.py")

    coord_base, claim = _wp02_claim(repo, pin, shas["claim"], monkeypatch)

    assert _MOVED not in _credited_paths(claim) and _MOVED not in claim.deletions
    assert _PRE not in claim.deletions
    assert _OTHER in _credited_paths(claim)
    result = MergeOutcomeVerifier(repo)._verify_squash_content(coord_base, _commit_set(repo, claim))
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert {path for path, _blob in result.divergence.unattributable_blobs} == {_MOVED}


@pytest.mark.integration
def test_a_credited_copy_of_a_pre_claim_file_carries_its_taint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review 8 issue 2, copies: a credited commit that edits a pre-claim file and copies it leaves the copy un-attributed."""
    repo, pin, shas = _same_file_mission(tmp_path, pre_claim={_PRE: _PRE_TEXT}, after_claim={_OTHER: "O = 1\n"})
    copy = "curation/pkg/copy.py"
    _commit(repo, {_PRE: _PRE_TEXT + "I = 5\n", copy: _PRE_TEXT}, "feat(WP02): edit pre.py and copy it")
    assert any(line.startswith("C") for line in _git(repo, "diff", "-M", "-C", "--name-status", "HEAD^1", "HEAD").splitlines())

    coord_base, claim = _wp02_claim(repo, pin, shas["claim"], monkeypatch)

    assert copy not in _credited_paths(claim) and _PRE not in _credited_paths(claim)
    result = MergeOutcomeVerifier(repo)._verify_squash_content(coord_base, _commit_set(repo, claim))
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert {copy, _PRE} <= {path for path, _blob in result.divergence.unattributable_blobs}


@pytest.mark.integration
def test_a_credited_rename_of_the_work_packages_own_file_is_credited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The control of review 8 issue 2: a rename between two of the work package's own credited files still lands."""
    repo, pin, shas = _same_file_mission(tmp_path, pre_claim=None, after_claim={_PRE: _PRE_TEXT})
    _git(repo, "mv", _PRE, _MOVED)
    _git(repo, "commit", "-qm", "feat(WP02): rename its own file")

    coord_base, claim = _wp02_claim(repo, pin, shas["claim"], monkeypatch)

    assert (_MOVED, _git(repo, "rev-parse", f"HEAD:{_MOVED}")) in claim.blobs
    assert _PRE in claim.deletions
    result = MergeOutcomeVerifier(repo)._verify_squash_content(coord_base, _commit_set(repo, claim))
    assert result.status is VerifyStatus.PASS


@pytest.mark.unit
def test_a_rename_touches_its_source_and_a_copy_does_not() -> None:
    """Review 8: a rename also changes (removes) its source; a copy and a plain change touch only their own path."""
    from specify_cli.consolidation.git_probes import LineageChange

    assert planning_walk._touched_paths(LineageChange(_MOVED, _PRE, renamed=True)) == (_MOVED, _PRE)
    assert planning_walk._touched_paths(LineageChange(_MOVED, _PRE)) == (_MOVED,)
    assert planning_walk._touched_paths(LineageChange(_MOVED, None, renamed=True)) == (_MOVED,)


@pytest.mark.integration
def test_the_lineage_probe_reads_renames_and_copies_and_refuses_a_root_commit(tmp_path: Path) -> None:
    from specify_cli.consolidation.git_probes import LineageChange, first_parent_lineage_changes

    repo, _pin, shas = _same_file_mission(tmp_path, pre_claim={_PRE: _PRE_TEXT}, after_claim={_OTHER: "O = 1\n"})
    _git(repo, "mv", _PRE, _MOVED)
    _git(repo, "commit", "-qm", "rename")
    renamed = _git(repo, "rev-parse", "HEAD")
    _commit(repo, {_MOVED: _PRE_TEXT + "I = 5\n", "curation/pkg/copy.py": _PRE_TEXT}, "edit and copy")

    assert first_parent_lineage_changes(repo, renamed) == [LineageChange(_MOVED, _PRE, renamed=True)]
    assert LineageChange("curation/pkg/copy.py", _MOVED) in first_parent_lineage_changes(repo, "HEAD")
    assert first_parent_lineage_changes(repo, shas["late"]) == [LineageChange(_OTHER)]
    root = _git(repo, "rev-list", "--max-parents=0", "HEAD")
    with pytest.raises(GitProbeError, match="git diff -C --name-status"):
        first_parent_lineage_changes(repo, root)


@pytest.mark.integration
def test_an_uncomputable_window_start_authors_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R2: when an approved work package's claim commit cannot be found, the lane authors nothing (fail closed)."""
    repo, pin, _early, _claim_commit, late = _r2_mission(tmp_path)
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_PKG,)})
    _starts(monkeypatch, None)
    lane = ExecutionLane(PLANNING_LANE_ID, ("WP02",), (_PKG,), (), (), 0)

    _coord_base, claim = _planning_claim(repo, pin, lane, {"WP02": {"lane": "approved"}})

    assert late not in claim.shas
    assert not claim.blobs


@pytest.mark.integration
def test_each_approved_work_package_is_credited_from_its_own_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R2, two work packages: WP03's path changed after WP02's claim but before WP03's own is credited to neither."""
    repo, pin, _shas = _mission(tmp_path)
    _git(repo, "switch", "-q", _MISSION_BRANCH)
    wp02_claim = _commit(repo, {f"kitty-specs/{_SLUG}/status.events.jsonl": "a\n"}, "chore: claim WP02")
    early_wp03 = _commit(repo, {"curation/other/early.py": "E = 1\n"}, "before WP03's claim")
    wp03_claim = _commit(repo, {f"kitty-specs/{_SLUG}/status.events.jsonl": "a\nb\n"}, "chore: claim WP03")
    late_wp03 = _commit(repo, {"curation/other/late.py": "L = 1\n"}, "feat(WP03)")
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_PKG,), "WP03": ("curation/other/**",)})
    _starts(monkeypatch, {"WP02": wp02_claim, "WP03": wp03_claim})
    lane = ExecutionLane(PLANNING_LANE_ID, ("WP02", "WP03"), (_PKG, "curation/other/**"), (), (), 0)

    _coord_base, claim = _planning_claim(repo, pin, lane, {"WP02": {"lane": "approved"}, "WP03": {"lane": "approved"}})

    assert late_wp03 in claim.shas and early_wp03 not in claim.shas
    assert {path for path, _blob in claim.blobs} == {"curation/other/late.py"}


@pytest.mark.integration
def test_a_window_start_missing_for_one_work_package_authors_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, pin, _early, _claim_commit, late = _r2_mission(tmp_path)
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_PKG,), "WP03": ("curation/other/**",)})
    _starts(monkeypatch, {"WP02": pin})
    lane = ExecutionLane(PLANNING_LANE_ID, ("WP02", "WP03"), (_PKG, "curation/other/**"), (), (), 0)

    _coord_base, claim = _planning_claim(repo, pin, lane, {"WP02": {"lane": "approved"}, "WP03": {"lane": "approved"}})

    assert late not in claim.shas and not claim.blobs


@pytest.mark.integration
def test_an_unreadable_window_authors_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, pin, _early, _claim_commit, late = _r2_mission(tmp_path)
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_PKG,)})
    _starts(monkeypatch, {"WP02": "0" * 40})
    lane = ExecutionLane(PLANNING_LANE_ID, ("WP02",), (_PKG,), (), (), 0)

    _coord_base, claim = _planning_claim(repo, pin, lane, {"WP02": {"lane": "approved"}})

    assert late not in claim.shas and not claim.blobs


@pytest.mark.unit
def test_the_planning_scope_credits_a_path_only_inside_its_owners_window() -> None:
    scope = planning_walk._PlanningScope((((_PKG,), frozenset({"c2"})), (("docs/a/x.md",), frozenset({"c1", "c2"}))))

    assert scope.patterns == ("curation/pkg/**", "docs/a/x.md")
    assert scope.at("c1") == ("docs/a/x.md",)
    assert scope.owns("c2", "curation/pkg/y.py") and not scope.owns("c1", "curation/pkg/y.py")
    assert not scope.owns("c0", "docs/a/x.md")


@pytest.mark.integration
def test_the_scoped_final_walk_attributes_a_path_only_when_every_change_to_it_is_credited(tmp_path: Path) -> None:
    """Review 7: one uncredited or dropped change to a path leaves it attributed to nothing; an older credited commit never stands in."""
    repo, pin, shas = _mission(tmp_path)
    spine = git_out(repo, "rev-list", "--first-parent", f"{pin}..HEAD").split()
    owned_everywhere = planning_walk._PlanningScope((((_OWNED,), frozenset(spine)),))
    owned_but_mixed = planning_walk._PlanningScope((((_OWNED,), frozenset(spine) - {shas["mixed"]}),))

    blobs, deletions = planning_walk._scoped_final_walk(repo, spine, owned_everywhere, frozenset())
    assert blobs == {(_OWNED, _git(repo, "rev-parse", f"{shas['mixed']}:{_OWNED}"))} and not deletions
    assert planning_walk._scoped_final_walk(repo, spine, owned_but_mixed, frozenset()) == (set(), set())
    assert planning_walk._scoped_final_walk(repo, spine, owned_everywhere, frozenset({shas["owned"]})) == (set(), set())


@pytest.mark.integration
def test_the_scoped_final_walk_attributes_a_credited_deletion(tmp_path: Path) -> None:
    repo, pin, _shas = _mission(tmp_path)
    _git(repo, "rm", "-q", "--", _OWNED)
    _git(repo, "commit", "-qm", "feat(WP02): drop the curation file")
    spine = git_out(repo, "rev-list", "--first-parent", f"{pin}..HEAD").split()

    assert planning_walk._scoped_final_walk(repo, spine, planning_walk._PlanningScope((((_OWNED,), frozenset(spine)),)), frozenset()) == (set(), {_OWNED})


@pytest.mark.integration
def test_the_scoped_final_walk_names_the_path_it_cannot_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, pin, _shas = _mission(tmp_path)
    spine = git_out(repo, "rev-list", "--first-parent", f"{pin}..HEAD").split()

    def _unreadable(_repo: Path, _ref: str, _path: str) -> str | None:
        raise GitProbeError("boom")

    setattr_reconciliation_family(monkeypatch, "path_state_at", _unreadable)
    with pytest.raises(GitProbeError, match=f"reading {_OWNED} at .* on the planning walk failed: boom"):
        planning_walk._scoped_final_walk(repo, spine, planning_walk._PlanningScope((((_OWNED,), frozenset(spine)),)), frozenset())


def _window_events() -> list[object]:
    return []


@pytest.mark.unit
def test_window_starts_need_an_event_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the claim's event reader no start is proven, even where the evidence axis would give one."""
    from specify_cli.consolidation import wp_evidence

    monkeypatch.setattr(wp_evidence, "planning_evidence_window", lambda *_args: ("start", _MISSION_BRANCH))

    assert _REAL_WINDOW_STARTS(Path(), _manifest(), _PLANNING, ("WP02",), None) is None


@pytest.mark.unit
def test_window_starts_read_the_evidence_axis_window(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.consolidation import wp_evidence

    def _window(_root: Path, _manifest: LanesManifest, _lane: ExecutionLane, wp_id: str, events: object) -> tuple[str, str]:
        assert events is _window_events
        return (f"start-{wp_id}", _MISSION_BRANCH)

    monkeypatch.setattr(wp_evidence, "planning_evidence_window", _window)

    assert _REAL_WINDOW_STARTS(Path(), _manifest(), _TWO_WP_PLANNING, ("WP02", "WP03"), _window_events) == {"WP02": "start-WP02", "WP03": "start-WP03"}


@pytest.mark.unit
@pytest.mark.parametrize("outcome", ["unresolved", "other_shape"])
def test_an_unprovable_or_absent_window_start_gives_no_starts(monkeypatch: pytest.MonkeyPatch, outcome: str) -> None:
    from specify_cli.consolidation import wp_evidence

    def _window(*_args: object) -> tuple[str, str] | None:
        if outcome == "unresolved":
            raise wp_evidence.PlanningWindowUnresolved(wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE, "no claim recorded")
        return None

    monkeypatch.setattr(wp_evidence, "planning_evidence_window", _window)

    assert _REAL_WINDOW_STARTS(Path(), _manifest(), _PLANNING, ("WP02",), _window_events) is None
