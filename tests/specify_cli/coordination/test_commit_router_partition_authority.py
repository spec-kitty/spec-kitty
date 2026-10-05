"""#2650 (WP05) -- FR-005 classifier-swap authority tests (T024/T025).

Pins the POST-swap behavior of ``commit_router._group_files_by_partition``:
the per-file PRIMARY/COORD split is now decided EXCLUSIVELY by the shared
``mission_runtime.is_coordination_artifact_residue_path`` predicate -- the
same authority ``implement.py``/``implement_cores.py`` already use -- not by
the retired ``kind_for_mission_file(file) or kind`` classifier (the
#2533-class hole WP04's characterization gate,
``test_partition_authority_characterization.py``, pinned before this WP's
fix).

* T024 -- structural: a ``kind=None`` path (``meta.json`` / unrecognized)
  routes PRIMARY even under a COORD-kind caller, and the retired classifier
  is demonstrably no longer driving the split.
* T025 -- caller-is-PRIMARY behavior preservation (squad RISK-4): a
  PRIMARY-caller mixed batch still routes coord-residue paths to the COORD
  ref and primary paths to the PRIMARY ref. T024's disagreement-set framing
  is a COORD-caller scenario and does not, by itself, prove the buckets are
  ABSOLUTE rather than merely flipped relative to the caller -- this class
  rules that out.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mission_runtime import (
    CommitTarget,
    MissionArtifactKind,
    MissionTopology,
    is_primary_artifact_kind,
    kind_for_mission_file,
)
from specify_cli.coordination import commit_router
from specify_cli.git.protection_policy import ProtectionPolicy

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_COORD_RESIDUE_PATH = "kitty-specs/m/status.events.jsonl"
_PRIMARY_PATH = "kitty-specs/m/spec.md"
_META_PATH = "kitty-specs/m/meta.json"
_UNRECOGNIZED_PATH = "kitty-specs/m/gap-analysis.md"

_PRIMARY_REF = "main"
_COORD_REF = "kitty/mission-m-AAAA1111"

# A COORD-partition caller kind -- the shape every ``move-task``/status-commit
# caller of ``commit_for_mission`` passes.
_COORD_CALLER_KIND = MissionArtifactKind.STATUS_STATE
# A PRIMARY-partition caller kind -- the shape ``spec_commit_cmd.py`` /
# ``mission_finalize.py`` pass.
_PRIMARY_CALLER_KIND = MissionArtifactKind.TASKS_INDEX


def _fake_resolve_placement_only(
    _repo_root: Path, _mission_slug: str, *, kind: MissionArtifactKind
) -> CommitTarget:
    """Kind-aware placement stub matching ``test_commit_router_partition.py``'s
    convention: PRIMARY kinds -> the primary ref, everything else -> coord."""
    if is_primary_artifact_kind(kind):
        return CommitTarget(ref=_PRIMARY_REF)
    return CommitTarget(ref=_COORD_REF)


# ---------------------------------------------------------------------------
# T024 -- kind=None routes PRIMARY under a COORD-kind caller
# ---------------------------------------------------------------------------


class TestKindNoneRoutesPrimaryUnderCoordCaller:
    """T024.1 -- the kind=None set routes PRIMARY, never the COORD caller's
    own partition (the #2533-class hole this WP closes)."""

    @pytest.mark.parametrize("kind_none_path", [_META_PATH, _UNRECOGNIZED_PATH])
    def test_solo_kind_none_path_routes_primary(
        self, kind_none_path: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(commit_router, "resolve_placement_only", _fake_resolve_placement_only)

        groups = commit_router._group_files_by_partition(
            Path("/tmp"), (Path(kind_none_path),), "m", kind=_COORD_CALLER_KIND
        )

        assert len(groups) == 1  # (single-partition; kind asserted below)
        group_kind, group_files = groups[0]
        assert is_primary_artifact_kind(group_kind), (
            f"{kind_none_path!r} (kind=None) must route PRIMARY under a "
            f"COORD-kind caller ({_COORD_CALLER_KIND!r}); got {group_kind!r}"
        )
        assert Path(kind_none_path) in group_files

    def test_mixed_batch_kind_none_joins_the_primary_bucket_not_the_coord_caller(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A kind=None path bundled alongside a genuine coord-residue file,
        under a COORD-kind caller, lands in the PRIMARY group -- not the
        COORD one -- proving the split, not merely a solo-file coincidence."""
        monkeypatch.setattr(commit_router, "resolve_placement_only", _fake_resolve_placement_only)

        meta = Path(_META_PATH)
        residue = Path(_COORD_RESIDUE_PATH)
        groups = commit_router._group_files_by_partition(
            Path("/tmp"), (meta, residue), "m", kind=_COORD_CALLER_KIND
        )

        files_by_kind = dict(groups)
        primary_kind = next(k for k, files in groups if meta in files)
        assert is_primary_artifact_kind(primary_kind)
        assert meta not in files_by_kind.get(_COORD_CALLER_KIND, ())
        assert residue in files_by_kind[_COORD_CALLER_KIND]


class TestKindClassifierNoLongerDrivesTheSplit:
    """T024.2 -- behaviorally frame that the retired
    ``kind_for_mission_file(...) or kind`` classifier no longer decides the
    split: a path that classifier would have called COORD-by-caller-fallback
    now routes PRIMARY, and ``kind_for_mission_file`` is not even consulted
    to reach that answer for the kind=None solo-file case.

    Framed behaviorally (not via a source-text scan) so this survives rename
    churn on the retired classifier's call shape.
    """

    def test_unrecognized_path_disagrees_with_the_retired_classifier(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(commit_router, "resolve_placement_only", _fake_resolve_placement_only)

        path = Path(_UNRECOGNIZED_PATH)
        assert kind_for_mission_file(path, mission_slug="m") is None, (
            "fixture assumption: gap-analysis.md must be kind=None for this "
            "test to exercise the retired classifier's fallback branch"
        )
        # The retired classifier's answer: kind_for_mission_file(...) or kind == kind.
        retired_classifier_answer = _COORD_CALLER_KIND

        groups = commit_router._group_files_by_partition(
            Path("/tmp"), (path,), "m", kind=_COORD_CALLER_KIND
        )
        group_kind, _files = groups[0]
        assert group_kind != retired_classifier_answer, (
            "the split still agrees with the retired "
            "'kind_for_mission_file(...) or kind' classifier -- the swap "
            "onto the residue predicate did not take effect"
        )
        assert is_primary_artifact_kind(group_kind)

    def test_membership_is_immune_to_kind_for_mission_files_return_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``kind_for_mission_file`` MAY still be consulted post-swap (to pick
        a representative kind for ref resolution on a genuinely mixed batch)
        -- but its return value must never decide PARTITION MEMBERSHIP.
        Stubbing it to return the CALLER's own COORD kind for a kind=None
        path -- reproducing exactly what the retired ``kind_for_mission_
        file(...) or kind`` fallback effectively produced -- must NOT pull
        the file into the COORD group: membership is decided exclusively by
        ``is_coordination_artifact_residue_path``."""
        monkeypatch.setattr(commit_router, "resolve_placement_only", _fake_resolve_placement_only)
        monkeypatch.setattr(
            commit_router, "kind_for_mission_file", lambda *_a, **_kw: _COORD_CALLER_KIND
        )

        groups = commit_router._group_files_by_partition(
            Path("/tmp"), (Path(_META_PATH),), "m", kind=_COORD_CALLER_KIND
        )
        assert len(groups) == 1  # (single-partition; kind asserted below)
        group_kind, group_files = groups[0]
        assert is_primary_artifact_kind(group_kind), (
            "meta.json landed in a COORD-labelled group even though "
            "is_coordination_artifact_residue_path says it is NOT residue -- "
            "kind_for_mission_file's return value is influencing partition "
            "membership again, reopening the #2533-class hole"
        )
        assert Path(_META_PATH) in group_files


# ---------------------------------------------------------------------------
# T025 -- caller-is-PRIMARY behavior preservation (squad RISK-4)
# ---------------------------------------------------------------------------


class TestCallerIsPrimaryBucketsStayAbsolute:
    """T025 -- a PRIMARY-kind caller's mixed batch still routes a coord-residue
    file to the COORD ref and a primary file to the PRIMARY ref. Modeled on
    ``test_commit_router_partition.py``'s
    ``test_mixed_batch_routes_each_file_to_its_own_partition_ref`` (a
    COORD-caller scenario) -- this is its PRIMARY-caller mirror, ruling out a
    regression where the split is still computed RELATIVE to
    ``caller_is_primary`` (and inverts refs for a PRIMARY caller) instead of
    absolutely.
    """

    def test_primary_caller_mixed_batch_routes_each_file_to_its_absolute_ref(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(commit_router, "resolve_placement_only", _fake_resolve_placement_only)

        primary_file = Path(_PRIMARY_PATH)
        coord_file = Path(_COORD_RESIDUE_PATH)

        groups = commit_router._group_files_by_partition(
            Path("/tmp"), (primary_file, coord_file), "m", kind=_PRIMARY_CALLER_KIND
        )

        assert len(groups) == 2  # (primary+coord split; kinds asserted below)
        files_by_kind = dict(groups)
        primary_group_kind = next(k for k, files in groups if primary_file in files)
        coord_group_kind = next(k for k, files in groups if coord_file in files)

        ref_by_kind = {
            kind: commit_router.resolve_placement_only(Path("/tmp"), "m", kind=kind).ref
            for kind, _files in groups
        }

        assert ref_by_kind[primary_group_kind] == _PRIMARY_REF, (
            "a PRIMARY file under a PRIMARY-kind caller must land on the "
            "PRIMARY ref"
        )
        assert ref_by_kind[coord_group_kind] == _COORD_REF, (
            "a coord-residue file under a PRIMARY-kind caller must STILL "
            "land on the COORD ref -- refs must never invert for a PRIMARY "
            "caller (squad RISK-4)"
        )
        assert coord_file not in files_by_kind[primary_group_kind]
        assert primary_file not in files_by_kind[coord_group_kind]

    def test_primary_caller_kind_none_path_stays_in_the_callers_own_primary_group(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The fast path is unaffected: under a PRIMARY-kind caller, a
        kind=None file (already PRIMARY per the residue authority) is never
        split into a second group -- single group, caller's own kind, no
        extra ``resolve_placement_only`` call (byte-identical fast path)."""
        calls: list[MissionArtifactKind] = []

        def _spy_resolve(
            _repo_root: Path, _mission_slug: str, *, kind: MissionArtifactKind
        ) -> CommitTarget:
            calls.append(kind)
            return _fake_resolve_placement_only(_repo_root, _mission_slug, kind=kind)

        monkeypatch.setattr(commit_router, "resolve_placement_only", _spy_resolve)

        spec_file = Path(_PRIMARY_PATH)
        meta_file = Path(_META_PATH)

        groups = commit_router._group_files_by_partition(
            Path("/tmp"), (spec_file, meta_file), "m", kind=_PRIMARY_CALLER_KIND
        )

        assert groups == [(_PRIMARY_CALLER_KIND, (spec_file, meta_file))]
        assert calls == [], (
            "a batch that is entirely the caller's own partition must take "
            "the zero-resolve fast path"
        )


class TestCommitForMissionEndToEndPrimaryCallerRefsNotInverted:
    """T025 -- end-to-end (``commit_for_mission``) confirmation, through the
    full public entry point (not just the internal
    ``_group_files_by_partition`` helper), that a PRIMARY-kind caller's mixed
    batch commits the coord-residue file to the COORD ref."""

    def test_primary_caller_end_to_end_commits_land_on_absolute_refs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mission_slug = "001-demo"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)

        spec_file = feature_dir / "spec.md"
        spec_file.write_text("# Spec\n", encoding="utf-8")
        status_file = feature_dir / "status.events.jsonl"
        status_file.write_text("{}\n", encoding="utf-8")

        coord_worktree = tmp_path / ".worktrees" / "coord"
        coord_worktree.mkdir(parents=True)

        monkeypatch.setattr(commit_router, "resolve_placement_only", _fake_resolve_placement_only)
        monkeypatch.setattr(
            commit_router, "resolve_topology", lambda *_a, **_kw: MissionTopology.COORD
        )
        monkeypatch.setattr(
            commit_router, "_resolve_mission_target_branch", lambda *_a, **_kw: _PRIMARY_REF
        )

        def _fake_materialise(
            repo_root: Path,
            _mission_slug: str,
            _placement: object,
            files: tuple[Path, ...],
            *,
            kind: MissionArtifactKind,
            primary_paths_created_this_invocation: frozenset[Path] | None = None,
        ) -> tuple[Path, tuple[Path, ...]]:
            staged: list[Path] = []
            for src in files:
                dst = coord_worktree / src.relative_to(repo_root)
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                staged.append(dst)
            return coord_worktree, tuple(staged)

        monkeypatch.setattr(commit_router, "_materialise_coord_worktree", _fake_materialise)

        safe_commit_calls: list[dict[str, object]] = []

        def _fake_safe_commit(**kwargs: object) -> object:
            safe_commit_calls.append(kwargs)

            class _Result:
                sha = "cafef00d"

            return _Result()

        monkeypatch.setattr(commit_router, "safe_commit", _fake_safe_commit)

        policy = ProtectionPolicy(protected_branches=frozenset(), operator_hatch_active=False)

        result = commit_router.commit_for_mission(
            tmp_path,
            mission_slug,
            (spec_file, status_file),
            "chore: spec + status",
            policy,
            kind=_PRIMARY_CALLER_KIND,
        )

        assert len(safe_commit_calls) == 2
        ref_by_filename: dict[str, str] = {}
        for call in safe_commit_calls:
            target = call["target"]
            assert isinstance(target, CommitTarget)
            paths = call["paths"]
            assert isinstance(paths, tuple)
            for path in paths:
                ref_by_filename[Path(path).name] = target.ref

        assert ref_by_filename["spec.md"] == _PRIMARY_REF
        assert ref_by_filename["status.events.jsonl"] == _COORD_REF, (
            "status.events.jsonl (coord residue) must land on the COORD ref "
            "even though the caller's own kind is PRIMARY -- refs must not "
            "invert for a PRIMARY caller (squad RISK-4)"
        )
        assert result.status == "committed"


# ---------------------------------------------------------------------------
# #5651 -- the directory alias set: a bare-slug coordination Mission's composed
# ``<slug>-<mid8>`` status files are COORD; nothing else about the composed name is.
# ---------------------------------------------------------------------------

_ALIAS_SLUG = "alias-demo"
_ALIAS_MID8 = "01M5651A"
_ALIAS_COMPOSED = f"{_ALIAS_SLUG}-{_ALIAS_MID8}"
_ALIAS_STEM = "alias-stem"


def _write_meta(repo: Path, dir_name: str, meta: dict[str, object]) -> None:
    import json

    directory = repo / "kitty-specs" / dir_name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


@pytest.fixture
def bare_slug_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """One bare-slug coordination Mission whose recorded identity proves its ``mid8``."""
    monkeypatch.setattr(commit_router, "resolve_placement_only", _fake_resolve_placement_only)
    _write_meta(tmp_path, _ALIAS_SLUG, {"mission_id": _ALIAS_MID8 + "0" * 18, "mid8": _ALIAS_MID8})
    # Look-alike neighbours on disk: a prefix-matching lookup would pair these with the bare slug.
    for neighbour in (f"{_ALIAS_SLUG}-01ZZZZZZ", f"{_ALIAS_COMPOSED}-x"):
        _write_meta(tmp_path, neighbour, {"mission_slug": neighbour})
    # A Mission named ``<stem>-abcdefgh`` that records no identity at all.
    _write_meta(tmp_path, f"{_ALIAS_STEM}-abcdefgh", {"mission_slug": f"{_ALIAS_STEM}-abcdefgh"})
    return tmp_path


def _partition_of(repo: Path, slug: str, rel_path: str) -> str:
    """The partition the router's grouping puts ``rel_path`` in, under a PRIMARY caller kind."""
    path = Path(rel_path)
    groups = commit_router._group_files_by_partition(repo, (path,), slug, kind=_PRIMARY_CALLER_KIND)
    ((group_kind, group_files),) = groups
    assert group_files == (path,)
    return "primary" if is_primary_artifact_kind(group_kind) else "coordination"


@pytest.mark.parametrize("status_file", ["status.json", "status.events.jsonl"])
def test_composed_status_files_group_to_coord_for_a_bare_slug_mission(bare_slug_repo: Path, status_file: str) -> None:
    assert _partition_of(bare_slug_repo, _ALIAS_SLUG, f"kitty-specs/{_ALIAS_COMPOSED}/{status_file}") == "coordination"


@pytest.mark.parametrize(
    "rel_path",
    [
        pytest.param(f"kitty-specs/{_ALIAS_SLUG}-01ZZZZZZ/status.json", id="different-mid8"),
        pytest.param(f"kitty-specs/{_ALIAS_COMPOSED}-x/status.json", id="suffixed-composed-name"),
        pytest.param(f"kitty-specs/other-demo-{_ALIAS_MID8}/status.json", id="other-slug-same-mid8"),
        pytest.param(f"kitty-specs/{_ALIAS_COMPOSED}/spec.md", id="composed-dir-planning-file"),
        pytest.param(f"kitty-specs/{_ALIAS_COMPOSED}/src/x.py", id="composed-dir-code-file"),
    ],
)
def test_nothing_but_the_exact_composed_status_files_leaves_the_primary_partition(bare_slug_repo: Path, rel_path: str) -> None:
    assert _partition_of(bare_slug_repo, _ALIAS_SLUG, rel_path) == "primary"


def test_a_slug_tail_that_looks_like_a_mid8_is_not_an_alias_without_recorded_identity(bare_slug_repo: Path) -> None:
    """``alias-stem-abcdefgh`` records no identity, so querying the bare ``alias-stem`` proves nothing."""
    assert _partition_of(bare_slug_repo, _ALIAS_STEM, f"kitty-specs/{_ALIAS_STEM}-abcdefgh/status.json") == "primary"


def test_the_alias_does_not_move_the_bare_directorys_own_verdicts(bare_slug_repo: Path) -> None:
    assert _partition_of(bare_slug_repo, _ALIAS_SLUG, f"kitty-specs/{_ALIAS_SLUG}/status.json") == "coordination"
    assert _partition_of(bare_slug_repo, _ALIAS_SLUG, f"kitty-specs/{_ALIAS_SLUG}/spec.md") == "primary"


def test_the_alias_set_is_resolved_once_per_grouping_call(bare_slug_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = commit_router.mission_dir_aliases
    calls: list[str] = []

    def _counting(repo_root: Path, mission_slug: str) -> frozenset[str]:
        calls.append(mission_slug)
        return real(repo_root, mission_slug)

    monkeypatch.setattr(commit_router, "mission_dir_aliases", _counting)
    files = tuple(Path(f"kitty-specs/{_ALIAS_COMPOSED}/{name}") for name in ("status.json", "status.events.jsonl", "spec.md"))

    commit_router._group_files_by_partition(bare_slug_repo, files, _ALIAS_SLUG, kind=_COORD_CALLER_KIND)

    assert calls == [_ALIAS_SLUG]


def test_an_empty_batch_reads_no_metadata(bare_slug_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _must_not_run(repo_root: Path, mission_slug: str) -> frozenset[str]:
        raise AssertionError("an empty batch must not read metadata")

    monkeypatch.setattr(commit_router, "mission_dir_aliases", _must_not_run)

    assert commit_router._group_files_by_partition(bare_slug_repo, (), _ALIAS_SLUG, kind=_COORD_CALLER_KIND) == []


def test_the_representative_kind_of_a_split_batch_is_classified_under_the_composed_name(bare_slug_repo: Path) -> None:
    """The coordination bucket's ref-resolution kind comes from the composed-directory file itself."""
    spec = Path(f"kitty-specs/{_ALIAS_SLUG}/spec.md")
    matrix = Path(f"kitty-specs/{_ALIAS_COMPOSED}/acceptance-matrix.json")

    groups = commit_router._group_files_by_partition(bare_slug_repo, (spec, matrix), _ALIAS_SLUG, kind=_PRIMARY_CALLER_KIND)

    assert dict(groups) == {
        _PRIMARY_CALLER_KIND: (spec,),
        MissionArtifactKind.ACCEPTANCE_MATRIX: (matrix,),
    }


def test_partition_for_mission_path_without_names_keeps_the_single_name_verdict(tmp_path: Path) -> None:
    composed_status = Path(f"kitty-specs/{_ALIAS_COMPOSED}/status.json")

    assert commit_router.partition_for_mission_path(tmp_path, _ALIAS_SLUG, composed_status) == "primary"
    assert (
        commit_router.partition_for_mission_path(
            tmp_path, _ALIAS_SLUG, composed_status, mission_dir_names=frozenset({_ALIAS_SLUG, _ALIAS_COMPOSED})
        )
        == "coordination"
    )
