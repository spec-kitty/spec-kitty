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

import json
from pathlib import Path

import pytest

import mission_runtime
from specify_cli.consolidation import reconciliation_authorship as authorship
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.consolidation.reconciliation import ApprovedWpCommitSet, MergeOutcomeVerifier
from specify_cli.consolidation.reconciliation_verifier import VerifyStatus
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from tests._support.git_cli import git_out
from tests.consolidation.reconciliation_family import setattr_reconciliation_family

pytestmark = [pytest.mark.git_repo]

#: The real window-start reader, kept before the autouse stub replaces it (R2 unit tests below).
_REAL_WINDOW_STARTS = authorship._planning_window_starts

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

    monkeypatch.setattr(authorship, "_planning_window_starts", _read)


# ---------------------------------------------------------------- the walk range


@pytest.mark.unit
def test_a_default_missions_planning_lane_walks_its_mission_branch_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))

    assert authorship._lane_walk_range(Path(), _manifest(), _PLANNING, "coord0000", None, (_OWNED,)) == ("pin0000", "coord0000", (_OWNED,))


@pytest.mark.unit
def test_every_other_shape_keeps_its_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(False))

    assert authorship._lane_walk_range(Path(), _manifest(), _PLANNING, "coord0000", None, (_OWNED,)) == ("coord0000", "main", ())
    assert authorship._lane_walk_range(Path(), _manifest(), _PLANNING, "coord0000", ("sb0", "sb1"), (_OWNED,)) == ("sb0", "sb1", ())
    assert authorship._lane_walk_range(Path(), _manifest(), _CODE, "coord0000", None, (_OWNED,)) == ("coord0000", f"kitty/mission-{_SLUG}-lane-a", ())


@pytest.mark.unit
def test_an_empty_write_scope_keeps_the_target_range(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty owned scope on the Mission-branch window authors nothing: it never widens to an unscoped walk."""
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))

    assert authorship._lane_walk_range(Path(), _manifest(), _PLANNING, "coord0000", None, ()) == ("coord0000", "main", ())


@pytest.mark.unit
def test_no_planning_pin_keeps_the_target_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))

    assert authorship._lane_walk_range(Path(), _manifest(pin=None), _PLANNING, "coord0000", None, (_OWNED,)) == ("coord0000", "main", ())


@pytest.mark.unit
@pytest.mark.parametrize(
    "error", [mission_runtime.PlanningWriteRefUnavailable(_SLUG, "meta.json is unreadable"), mission_runtime.PlanningCheckoutMissing(_SLUG, _MISSION_BRANCH)]
)
def test_an_undecidable_write_branch_keeps_the_target_range(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """The planning lane then authors nothing, so the gate still refuses content it cannot attribute (fail closed)."""

    def _raise(*_args: object, **_kwargs: object) -> mission_runtime.PlanningWriteRef:
        raise error

    monkeypatch.setattr(mission_runtime, "planning_write_ref", _raise)

    assert authorship._lane_walk_range(Path(), _manifest(), _PLANNING, "coord0000", None, (_OWNED,)) == ("coord0000", "main", ())


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
    assert authorship._is_whole_tree_pattern(pattern)


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
    assert not authorship._is_whole_tree_pattern(pattern)


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

    monkeypatch.setattr(authorship, "_planning_ownership", _read, raising=False)
    return asked


_PKG = "curation/pkg/**"
_PKG_WP03 = "curation/pkg/wp03.py"
_TWO_WP_PLANNING = ExecutionLane(PLANNING_LANE_ID, ("WP02", "WP03"), (_OWNED, "curation/wp03.py"), (), (), 0)


@pytest.mark.unit
def test_the_scope_is_each_approved_work_packages_owned_files(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _ownership(monkeypatch, {"WP02": (_OWNED,), "WP03": ("curation/wp03.py",)})
    states = {"WP02": {"lane": "approved"}, "WP03": {"lane": "done"}}

    assert authorship._approved_planning_scope(Path(), _manifest(), _TWO_WP_PLANNING, states) == {"WP02": (_OWNED,), "WP03": ("curation/wp03.py",)}
    assert asked == [("WP02", "WP03")]


@pytest.mark.unit
def test_no_approved_work_package_gives_an_empty_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _ownership(monkeypatch, {"WP02": (_OWNED,)})

    assert not authorship._approved_planning_scope(Path(), _manifest(), _PLANNING, {"WP02": {"lane": "in_progress"}})
    assert asked == []


@pytest.mark.unit
def test_an_unreadable_approved_ownership_gives_an_empty_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """WP03 is approved but its owned_files cannot be read: no partial scope, the lane authors nothing (fail closed)."""
    _ownership(monkeypatch, {"WP02": (_OWNED,)})
    states = {"WP02": {"lane": "approved"}, "WP03": {"lane": "done"}}

    assert not authorship._approved_planning_scope(Path(), _manifest(), _TWO_WP_PLANNING, states)


@pytest.mark.unit
def test_a_whole_tree_pattern_makes_the_whole_scope_unusable(monkeypatch: pytest.MonkeyPatch) -> None:
    _ownership(monkeypatch, {"WP02": (_OWNED,), "WP03": ("src/**",)})
    states = {"WP02": {"lane": "approved"}, "WP03": {"lane": "approved"}}

    assert not authorship._approved_planning_scope(Path(), _manifest(), _TWO_WP_PLANNING, states)


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

    assert authorship._planning_ownership(tmp_path, _SLUG, ("WP02", "WP03")) == {"WP02": (_OWNED,)}
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
    return coord_base, authorship._collect_authored(repo, manifest, states, coord_base, None, canceled_lane_commits=frozenset())


def _commit_set(pin: str, claim: authorship._AuthoredClaim) -> ApprovedWpCommitSet:
    """The production claim's shape, as :func:`build_approved_wp_set` fills it from :func:`_collect_authored`."""
    return ApprovedWpCommitSet(
        approved={"WP02": tuple(sorted(claim.shas))},
        manifest_wp_ids=frozenset({"WP02", "WP03"}),
        excluded_window_base=pin,
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

    scoped = authorship._scoped_commits(repo, spine, authorship._PlanningScope((((_OWNED,), frozenset(spine)),)), _SLUG)

    assert scoped.touching == [shas["mixed"], shas["owned_and_status"], shas["owned"]]
    assert scoped.whole == frozenset({shas["owned"], shas["owned_and_status"]})


@pytest.mark.integration
def test_an_unreadable_commit_is_dropped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _pin, shas = _mission(tmp_path)

    def _broken(_repo: Path, _sha: str) -> list[str]:
        raise GitProbeError("git show failed")

    setattr_reconciliation_family(monkeypatch, "changed_paths_of", _broken)

    scoped = authorship._scoped_commits(repo, [shas["owned"]], authorship._PlanningScope((((_OWNED,), frozenset({shas["owned"]})),)), _SLUG)
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
    commit_set = _commit_set(pin, claim)

    flagged = {sha for sha, _pid in verifier._unattributable_in((coord_base, "side"), commit_set)}

    assert flagged == {shas["mixed"], shas["stray"], copy}


@pytest.mark.integration
def test_the_squash_blob_axis_refuses_the_stray_and_sneaked_in_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, pin, _shas = _mission(tmp_path)
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))
    _ownership(monkeypatch, {"WP02": (_OWNED,)})
    coord_base, claim = _planning_claim(repo, pin, _PLANNING, {"WP02": {"lane": "approved"}})

    result = MergeOutcomeVerifier(repo)._verify_squash_content(coord_base, _commit_set(pin, claim))

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


# ---------------------------------------------------------------- review 4: operator rulings R1 and R2 (2026-11-27)


def _starts(monkeypatch: pytest.MonkeyPatch, starts: dict[str, str] | None) -> None:
    """Stub each approved planning work package's window start (its claim commit on the Mission branch)."""

    def _read(_repo_root: Path, _manifest: LanesManifest, _lane: ExecutionLane, wp_ids: tuple[str, ...], _events: object) -> dict[str, str] | None:
        return None if starts is None else {wp: starts[wp] for wp in wp_ids if wp in starts}

    monkeypatch.setattr(authorship, "_planning_window_starts", _read)


@pytest.mark.unit
@pytest.mark.parametrize("state", ["canceled", "for_review", "in_progress", "planned", "blocked", "claimed"])
def test_any_non_approved_planning_work_package_empties_the_scope(monkeypatch: pytest.MonkeyPatch, state: str) -> None:
    """R1: the claim admits by path, not by author, so a lane holding a non-approved work package authors nothing, even with disjoint ownership."""
    asked = _ownership(monkeypatch, {"WP02": (_OWNED,), "WP03": ("docs/other/x.md",)})

    assert not authorship._approved_planning_scope(Path(), _manifest(), _TWO_WP_PLANNING, {"WP02": {"lane": "approved"}, "WP03": {"lane": state}})
    assert asked == []


@pytest.mark.unit
def test_a_planning_work_package_with_no_status_row_empties_the_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    _ownership(monkeypatch, {"WP02": (_OWNED,), "WP03": ("docs/other/x.md",)})

    assert not authorship._approved_planning_scope(Path(), _manifest(), _TWO_WP_PLANNING, {"WP02": {"lane": "approved"}})


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
    scope = authorship._PlanningScope((((_PKG,), frozenset({"c2"})), (("docs/a/x.md",), frozenset({"c1", "c2"}))))

    assert scope.patterns == ("curation/pkg/**", "docs/a/x.md")
    assert scope.at("c1") == ("docs/a/x.md",)
    assert scope.owns("c2", "curation/pkg/y.py") and not scope.owns("c1", "curation/pkg/y.py")
    assert not scope.owns("c0", "docs/a/x.md")


@pytest.mark.integration
def test_the_final_walk_drops_a_path_whose_newest_change_keep_rejects(tmp_path: Path) -> None:
    """A rejected newest change is never replaced by an older, accepted one (``keep``)."""
    repo, pin, shas = _mission(tmp_path)
    spine = git_out(repo, "rev-list", "--first-parent", f"{pin}..HEAD").split()

    def _keep(sha: str, _path: str) -> bool:
        return sha != shas["mixed"]

    blobs, _deletions = authorship._final_authored_walk(repo, spine, keep=_keep)

    assert {path for path, _blob in blobs} == {"stray.py", f"kitty-specs/{_SLUG}/status.events.jsonl"}


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
