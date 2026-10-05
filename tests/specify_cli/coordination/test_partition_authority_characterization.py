"""#2650 (WP04) -- FR-006 characterization gate.

Pins the CURRENT (as of this WP) behavior of the three partition-decision
sites named in ``data-model.md``'s table, BEFORE any consolidation swap of
``commit_router``'s classifier onto the shared residue predicate (that swap
is WP05's job, T024). This gate is a live snapshot, not a design spec -- if a
future change makes any assertion here false, that is a signal the change
touched one of these three named sites and must be evaluated against the
unified-authority contract in ``contracts/partition-authority-and-warning.md``.

The three sites:

* Read  -- ``implement_cores.py::resolve_precondition_ref``
* Write -- ``coordination/planning_commit.py::partition_files_for_commit``
* Write -- ``coordination/commit_router.py::_group_files_by_partition``

Both cli-side sites (read + write in ``implement.py``/``implement_cores.py``)
already delegate to the shared
``mission_runtime.is_coordination_artifact_residue_path`` predicate (WP01/
WP02, prior WPs in this lane) -- they already route ``kind=None`` paths
(``meta.json``, unrecognized) to PRIMARY, and this WP additionally unifies
the concrete REF value they resolve to (FR-005 ref half; see
``test_precondition_ref_unification.py``). ``commit_router``'s
``_group_files_by_partition`` instead classifies via
``kind_for_mission_file(file) or kind`` -- falling back to the CALLER's
partition (which can be COORD) for a ``kind=None`` path. That fallback is the
#2533-class hole: it is NOT touched by this WP (boundary: ``commit_router.py``
is WP05's surface) -- it is only characterized/pinned here so WP05 has one
gate to swap against.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import (
    CommitTarget,
    MissionArtifactKind,
    is_primary_artifact_kind,
)
from specify_cli.coordination import commit_router
from specify_cli.coordination.coherence import is_coord_residue_churn
from specify_cli.git.protection_policy import ProtectionPolicy

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# Representative path set (T015): a coord-residue path, a PRIMARY path, a
# self-bookkeeping ``kind=None`` path, and an unrecognized ``kind=None`` path.
_COORD_RESIDUE_PATH = "kitty-specs/m/status.events.jsonl"
_PRIMARY_PATH = "kitty-specs/m/spec.md"
_META_PATH = "kitty-specs/m/meta.json"
_UNRECOGNIZED_PATH = "kitty-specs/m/gap-analysis.md"

_COORD_BRANCH = "kitty/mission-m-AAAA1111"
_PRIMARY_REF = "main"
_COORD_REF = _COORD_BRANCH

# A COORD-partition caller kind -- the shape every ``move-task``/status-commit
# caller of ``commit_for_mission`` passes (``STATUS_STATE`` / ``ACCEPTANCE_MATRIX``
# / ``ISSUE_MATRIX`` are COORD-partition members of ``_PLACEMENT_ARTIFACT_KINDS``;
# ``ANALYSIS_REPORT`` was re-homed COORD->PRIMARY by coord-commit-integrity FR-003
# and is no longer one of them).
_COORD_CALLER_KIND = MissionArtifactKind.STATUS_STATE


def _fake_resolve_placement_only(
    _repo_root: Path, _mission_slug: str, *, kind: MissionArtifactKind
) -> CommitTarget:
    """Kind-aware placement stub matching ``test_commit_router_partition.py``'s
    convention: PRIMARY kinds -> the primary ref, everything else -> coord."""
    if is_primary_artifact_kind(kind):
        return CommitTarget(ref=_PRIMARY_REF)
    return CommitTarget(ref=_COORD_REF)


class TestThreeSitesCurrentPartitionDecisions:
    """T015 -- each of the three named sites' current PRIMARY/COORD decision,
    for the representative path set, is a live snapshot in this suite."""

    def test_write_side_partition_files_for_commit(self) -> None:
        """Site 1 (write): ``coordination/planning_commit.py::partition_files_for_commit``."""
        from specify_cli.coordination.planning_commit import partition_files_for_commit

        primary, coord = partition_files_for_commit(
            [_COORD_RESIDUE_PATH, _PRIMARY_PATH, _META_PATH, _UNRECOGNIZED_PATH]
        )
        assert coord == [_COORD_RESIDUE_PATH]
        assert primary == [_PRIMARY_PATH, _META_PATH, _UNRECOGNIZED_PATH]

    def test_read_side_resolve_precondition_ref(self) -> None:
        """Site 2 (read): ``implement_cores.py::resolve_precondition_ref``."""
        from specify_cli.cli.commands.implement_cores import resolve_precondition_ref

        assert resolve_precondition_ref(_COORD_RESIDUE_PATH, _COORD_BRANCH) == _COORD_BRANCH
        assert resolve_precondition_ref(_PRIMARY_PATH, _COORD_BRANCH) == "HEAD"
        assert resolve_precondition_ref(_META_PATH, _COORD_BRANCH) == "HEAD"
        assert resolve_precondition_ref(_UNRECOGNIZED_PATH, _COORD_BRANCH) == "HEAD"

    def test_write_side_group_files_by_partition_agrees_on_recognized_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Site 3 (write): ``commit_router._group_files_by_partition``, under
        a COORD-kind caller -- the RECOGNIZED paths (coord-residue, PRIMARY)
        already agree with the residue predicate: each lands on its OWN
        partition's ref, exactly like sites 1 and 2."""
        monkeypatch.setattr(commit_router, "resolve_placement_only", _fake_resolve_placement_only)

        coord_residue = Path(_COORD_RESIDUE_PATH)
        primary = Path(_PRIMARY_PATH)

        groups = commit_router._group_files_by_partition(
            tmp_path, (coord_residue, primary), "m", kind=_COORD_CALLER_KIND
        )
        ref_by_kind = {
            kind: commit_router.resolve_placement_only(tmp_path, "m", kind=kind).ref for kind, _files in groups
        }
        files_by_kind = dict(groups)
        assert coord_residue in files_by_kind[MissionArtifactKind.STATUS_STATE]
        assert ref_by_kind[MissionArtifactKind.STATUS_STATE] == _COORD_REF
        primary_kind = next(k for k, files in groups if primary in files)
        assert ref_by_kind[primary_kind] == _PRIMARY_REF, (
            "a recognized PRIMARY path (spec.md) under a COORD-kind caller "
            "must still split away onto the PRIMARY ref -- this is the "
            "AGREEING case (contrast with kind=None below)"
        )


class TestDisagreementSetRoutesPrimaryOnResidueButCoordUnderCommitRouter:
    """T016 -- pin the disagreement set: EVERY non-coord-residue path bundled
    under a COORD-kind caller must (post-FR-005) route PRIMARY. Today,
    ``is_coordination_artifact_residue_path`` already routes the ``kind=None``
    set to PRIMARY (the residue-authority answer, unchanged by this WP); but
    ``commit_router``'s ``kind_for_mission_file(...) or kind`` fallback
    routes those SAME paths to the CALLER's partition -- COORD, here -- the
    divergence WP05 removes.

    Framed as "non-coord path under a coord caller", not merely
    ``meta.json`` (squad RISK-4): a future coord-kind caller re-diverges the
    SAME way for ANY unrecognized path, not only this one filename.

    WP05 update (T023/#2650): the second method below was written by WP04 as
    a "document current, #2533-class hole" pin -- its own docstring names the
    exact assertion WP05 (T024) would flip once the classifier swap lands
    (see the module docstring's "NOT touched by this WP... WP05's OWN
    fresh-green test file" note). WP05 owns ``commit_router.py``; flipping
    this method's expected outcome to the POST-swap answer is that same
    change surfacing here, not a scope violation -- the alternative (leaving
    a documented-obsolete assertion red) would fail T026's "coordination
    suite green" gate for a result the fix is SUPPOSED to change.
    """

    @pytest.mark.parametrize("kind_none_path", [_META_PATH, _UNRECOGNIZED_PATH])
    def test_residue_authority_routes_kind_none_to_primary(self, kind_none_path: str) -> None:
        assert is_coord_residue_churn(kind_none_path) is False, (
            f"{kind_none_path!r} is kind=None (not in the coord-residue kind "
            f"set) -- the residue authority must route it PRIMARY"
        )

    @pytest.mark.parametrize("kind_none_path", [_META_PATH, _UNRECOGNIZED_PATH])
    def test_commit_router_kind_none_now_routes_primary_not_the_coord_caller(
        self, kind_none_path: str
    ) -> None:
        """Post-WP05 (#2650 T023): under a COORD-kind caller, a ``kind=None``
        path no longer joins the caller's COORD group -- it routes PRIMARY,
        agreeing with the residue authority above. ``commit_router``'s
        classifier now delegates to
        ``mission_runtime.is_coordination_artifact_residue_path`` instead of
        falling back to the caller's own kind, closing the #2533-class hole
        this class documents."""
        groups = commit_router._group_files_by_partition(
            Path("/tmp"), (Path(kind_none_path),), "m", kind=_COORD_CALLER_KIND
        )
        assert len(groups) == 1  # (single-partition; kind asserted below)
        group_kind, group_files = groups[0]
        assert is_primary_artifact_kind(group_kind), (
            f"{kind_none_path!r} (kind=None) must route to a PRIMARY-partition "
            f"kind -- the residue authority's answer -- instead of the "
            f"COORD-kind caller {_COORD_CALLER_KIND!r}; got {group_kind!r}, "
            f"which would reopen the #2533-class hole WP05 closed"
        )
        assert group_kind != _COORD_CALLER_KIND
        assert Path(kind_none_path) in group_files


class TestIntendedUnifiedContractCliSideOnly:
    """T018 -- the intended-contract assertions THIS WP owns and turns green
    (via T019-T021): the read and write cli-side sites route ``kind=None`` ->
    PRIMARY and agree on the primary ref BY CONSTRUCTION.

    Deliberately does NOT assert anything about ``commit_router``'s
    classifier (that is WP05 T024's OWN fresh-green test file,
    ``test_commit_router_partition_authority.py``) -- see the module note
    below and the standalone regression guard at the bottom of this class
    for why no ``xfail``-pending-WP05 marker is planted here.
    """

    @pytest.mark.parametrize("kind_none_path", [_META_PATH, _UNRECOGNIZED_PATH])
    def test_read_and_write_agree_kind_none_routes_primary(self, kind_none_path: str) -> None:
        from specify_cli.coordination.planning_commit import partition_files_for_commit
        from specify_cli.cli.commands.implement_cores import resolve_precondition_ref

        assert resolve_precondition_ref(kind_none_path, _COORD_BRANCH) == "HEAD"
        primary_files, coord_files = partition_files_for_commit([kind_none_path])
        assert primary_files == [kind_none_path]
        assert coord_files == []


# ---------------------------------------------------------------------------
# #5651 (nightly-suites-green WP02): what ``commit_for_mission`` does on a
# Mission whose metadata is absent, corrupt, ambiguous, or whose directory is
# the composed ``<slug>-<mid8>`` name.  Written GREEN on the base commit,
# before the directory alias set existed, and unchanged afterwards: the alias
# lookup adds no new raise and moves no partition verdict for these inputs.
# ---------------------------------------------------------------------------

_MID8 = "01ABCDEF"
_STEM = "demo-mission"
_COMPOSED = f"{_STEM}-{_MID8}"
_FULL_MISSION_ID = _MID8 + "0" * 18
_STATUS_LOG = "status.events.jsonl"
_SPEC = "spec.md"
_PROTECTED_MAIN = ProtectionPolicy(protected_branches=frozenset({"main"}), operator_hatch_active=False)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _real_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-qb", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "init")
    return repo


def _mission_dir(repo: Path, dir_name: str, meta_text: str | None) -> Path:
    directory = repo / "kitty-specs" / dir_name
    directory.mkdir(parents=True)
    if meta_text is not None:
        (directory / "meta.json").write_text(meta_text, encoding="utf-8")
    (directory / _STATUS_LOG).write_text('{"event": 1}\n', encoding="utf-8")
    (directory / _SPEC).write_text("# spec\n", encoding="utf-8")
    return directory


def _identity_meta(slug: str) -> str:
    return json.dumps({"mission_slug": slug, "mission_id": _FULL_MISSION_ID, "mid8": _MID8, "target_branch": "main"})


def _commit_status_log(repo: Path, handle: str, directory: Path) -> commit_router.CommitRouterResult:
    return commit_router.commit_for_mission(
        repo,
        handle,
        (directory / _STATUS_LOG,),
        "chore: characterization commit",
        _PROTECTED_MAIN,
        kind=MissionArtifactKind.STATUS_STATE,
    )


class TestMetadataShapesCharacterization:
    """Absent, corrupt and ambiguous metadata behave on the base exactly as pinned here."""

    @pytest.mark.parametrize("meta_text", ["{not json", "[1, 2]"], ids=["not-json", "json-not-an-object"])
    def test_corrupt_primary_meta_raises_the_typed_read_error(self, tmp_path: Path, meta_text: str) -> None:
        from specify_cli.core.paths import MissionMetaReadError

        repo = _real_repo(tmp_path)
        directory = _mission_dir(repo, _STEM, meta_text)

        with pytest.raises(MissionMetaReadError):
            _commit_status_log(repo, _STEM, directory)

    def test_absent_primary_meta_is_refused_on_the_protected_branch(self, tmp_path: Path) -> None:
        repo = _real_repo(tmp_path)
        directory = _mission_dir(repo, _STEM, None)

        result = _commit_status_log(repo, _STEM, directory)

        assert result.status == "no_op_wrong_surface"
        assert result.commit_hash is None

    def test_ambiguous_handle_raises_the_action_context_error(self, tmp_path: Path) -> None:
        from mission_runtime.resolution import ActionContextError

        repo = _real_repo(tmp_path)
        first = _mission_dir(repo, "amb-01AAAAAA", _identity_meta("amb-01AAAAAA"))
        _mission_dir(repo, "amb-01BBBBBB", _identity_meta("amb-01BBBBBB"))

        with pytest.raises(ActionContextError, match="matches multiple missions"):
            _commit_status_log(repo, "amb", first)


class TestComposedDirectoryMissionCharacterization:
    """A Mission whose only directory is ``<slug>-<mid8>`` keeps its base partition verdicts."""

    def test_composed_handle_groups_the_status_log_to_the_coord_kind(self, tmp_path: Path) -> None:
        repo = _real_repo(tmp_path)
        directory = _mission_dir(repo, _COMPOSED, _identity_meta(_COMPOSED))
        log = directory / _STATUS_LOG

        groups = commit_router._group_files_by_partition(repo, (log,), _COMPOSED, kind=MissionArtifactKind.STATUS_STATE)

        assert groups == [(MissionArtifactKind.STATUS_STATE, (log,))]

    def test_bare_stem_handle_is_not_treated_as_the_composed_directory(self, tmp_path: Path) -> None:
        """The bare stem is not an alias of a Mission that is already canonical (FR-005)."""
        repo = _real_repo(tmp_path)
        directory = _mission_dir(repo, _COMPOSED, _identity_meta(_COMPOSED))
        log = directory / _STATUS_LOG

        groups = commit_router._group_files_by_partition(repo, (log,), _STEM, kind=MissionArtifactKind.STATUS_STATE)

        assert groups == [(MissionArtifactKind.SPEC, (log,))]
        assert commit_router.partition_for_mission_path(repo, _STEM, log) == "primary"
        assert commit_router.partition_for_mission_path(repo, _COMPOSED, log) == "coordination"

    def test_bare_stem_handle_commit_is_refused_on_the_protected_branch(self, tmp_path: Path) -> None:
        repo = _real_repo(tmp_path)
        directory = _mission_dir(repo, _COMPOSED, _identity_meta(_COMPOSED))

        result = _commit_status_log(repo, _STEM, directory)

        assert result.status == "no_op_wrong_surface"


class TestUnsafeSlugCharacterization:
    """A handle that is not a safe path segment keeps its base behaviour (#5651, review cycle 1).

    Green on the base: grouping never raises for these, and ``commit_for_mission`` raises the
    typed error its placement read raises. The directory alias lookup must add neither a new
    raise to the grouping nor a different error to the commit.
    """

    _UNSAFE_SLUGS = ["", "../x", "a/b", ".hidden", "ok slug"]

    @pytest.mark.parametrize("slug", _UNSAFE_SLUGS)
    def test_grouping_returns_one_group_without_raising(self, tmp_path: Path, slug: str) -> None:
        repo = _real_repo(tmp_path)
        log = repo / "kitty-specs" / "x" / _STATUS_LOG

        groups = commit_router._group_files_by_partition(repo, (log,), slug, kind=MissionArtifactKind.STATUS_STATE)

        assert groups == [(MissionArtifactKind.SPEC, (log,))]

    def test_commit_with_an_empty_slug_raises_the_action_context_error(self, tmp_path: Path) -> None:
        from mission_runtime.resolution import ActionContextError

        repo = _real_repo(tmp_path)

        with pytest.raises(ActionContextError):
            _commit_status_log(repo, "", repo / "kitty-specs" / "x")

    @pytest.mark.parametrize("slug", [s for s in _UNSAFE_SLUGS if s])
    def test_commit_with_an_unsafe_slug_raises_the_unsafe_segment_error(self, tmp_path: Path, slug: str) -> None:
        from specify_cli.core.paths import UnsafePathSegmentError

        repo = _real_repo(tmp_path)

        with pytest.raises(UnsafePathSegmentError):
            _commit_status_log(repo, slug, repo / "kitty-specs" / "x")
