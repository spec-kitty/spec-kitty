"""owned-checkout-lifecycle-authority WP04 (T017/T019) — ``placement_seam(owned=)``.

Gives the ONE placement authority an owned arm that cannot fold to the
repository root checkout (R-04, contracts/owned-checkout-carrier.md §7), and
pins that topology is decided exactly once, at minting (FR-023, R-16): the
placement layer no longer refuses by topology at all
(``_require_owned_single_branch`` is deleted).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import (
    ActionContextError,
    MissionArtifactKind,
    MissionTopology,
    TopologySurface,
    is_primary_artifact_kind,
    placement_seam,
    routes_through_coordination,
)
from mission_runtime.owned_checkout import OwnedCheckout, OwnedRefusalCode

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MID8 = "01M3PACE"  # valid 8-char Crockford base32 tail (F4 handle-canonicalisation tests need a real mid8 suffix)
_SLUG = f"owned-placement-seam-{_MID8}"


def _mint(tmp_path: Path, *, topology: MissionTopology = MissionTopology.SINGLE_BRANCH, target_branch: str = "main") -> OwnedCheckout:
    repository_root = tmp_path / "R"
    owned_root = tmp_path / "P"
    mission_dir = owned_root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    repository_root.mkdir()
    # A real ``meta.json`` matching the fact's own fields: the mission-context
    # builder reads meta fresh off disk (byte-identical legacy-arm behaviour,
    # T021) rather than trusting the fact's fields directly, so a fact minted
    # over a directory whose meta disagrees is not a scenario this WP's
    # resolvers are meant to support (the minter is the SOLE source of a
    # fact, and it only ever mints from an already-consistent meta read).
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01M3PACE000000000000000001",
                "mission_slug": _SLUG,
                "slug": _SLUG,
                "mission_type": "software-dev",
                "topology": topology.value,
                "target_branch": target_branch,
            }
        ),
        encoding="utf-8",
    )
    return OwnedCheckout._mint(
        repository_root=repository_root,
        owned_root=owned_root,
        mission_dir=mission_dir,
        mission_slug=_SLUG,
        topology=topology,
        write_branch=target_branch,
    )


def _boom(name: str):
    def _raise(*_args: object, **_kwargs: object) -> None:
        raise AssertionError(f"{name} must not be called on the owned arm (R1)")

    return _raise


def _patch_zero_fold_spies(monkeypatch: pytest.MonkeyPatch) -> None:
    """R1 (review cycle 2): make every fold/walk/subprocess primitive a fact
    reaches this WP's owned arm raise, so a real call is loud, not silent."""
    monkeypatch.setattr("specify_cli.core.paths.get_main_repo_root", _boom("get_main_repo_root"))
    monkeypatch.setattr(
        "specify_cli.missions._read_path_resolver.candidate_feature_dir_for_mission",
        _boom("candidate_feature_dir_for_mission"),
    )
    monkeypatch.setattr(
        "specify_cli.missions._read_path_resolver.resolve_handle_to_read_path",
        _boom("resolve_handle_to_read_path"),
    )
    monkeypatch.setattr(subprocess, "run", _boom("subprocess.run"))


def test_primary_kinds_read_dir_is_mission_dir_with_zero_git_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every PRIMARY-partition kind's ``read_dir`` equals ``fact.mission_dir``
    with NO fold to ``get_main_repo_root``, NO handle walk
    (``candidate_feature_dir_for_mission`` / ``resolve_handle_to_read_path``)
    and NO ``subprocess.run`` call (NFR-002 / contract §7 / review cycle 2
    R1) -- verified via a real monkeypatched RAISE, not just an omitted
    assertion."""
    fact = _mint(tmp_path)
    _patch_zero_fold_spies(monkeypatch)

    seam = placement_seam(fact.repository_root, _SLUG, owned=fact)
    for kind in MissionArtifactKind:
        if not is_primary_artifact_kind(kind) or kind is MissionArtifactKind.RETROSPECTIVE:
            continue
        assert seam.read_dir(kind) == fact.mission_dir, kind


def test_mission_context_for_owned_is_zero_fold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R1: ``mission_context_for(owned=)`` itself makes zero folds/walks/git
    calls, using a mid8 handle (not just the slug) as the reviewer's own
    probe did."""
    from mission_runtime import mission_context_for

    fact = _mint(tmp_path)
    _patch_zero_fold_spies(monkeypatch)

    context = mission_context_for(fact.repository_root, _MID8, owned=fact)
    assert context.artifact(MissionArtifactKind.SPEC).read_dir == fact.mission_dir


def test_resolve_artifact_surface_owned_is_zero_fold_for_spec_and_status_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R1: ``resolve_artifact_surface(owned=)`` for both a PRIMARY kind (SPEC)
    and a COORD-partition kind under a coord-less topology (STATUS_STATE,
    single_branch) makes zero folds/walks/git calls."""
    from mission_runtime.resolution import resolve_artifact_surface

    fact = _mint(tmp_path)
    _patch_zero_fold_spies(monkeypatch)

    spec = resolve_artifact_surface(fact.repository_root, _SLUG, MissionArtifactKind.SPEC, owned=fact)
    assert spec.path == fact.mission_dir
    status = resolve_artifact_surface(fact.repository_root, _SLUG, MissionArtifactKind.STATUS_STATE, owned=fact)
    assert status.path == fact.mission_dir


def test_owned_resolver_never_consulted(tmp_path: Path) -> None:
    """R1: a resolver that raises whenever ``.resolve()`` or ``.all_missions()``
    is called is never consulted when a fact is present.

    Review cycle 3 (non-blocking #2): passes the MID8 handle, not the exact
    slug on disk. With the exact slug, the pre-WP04 handle-walk never needed
    to consult the resolver in the first place (the legacy code path takes a
    fast exact-match branch before ever reaching the resolver), so that form
    passed on the cycle-1 source (c220d467d) too -- vacuously. The mid8 form
    forces the OLD walk to canonicalize via ``candidate_feature_dir_for_mission``
    / the resolver; verified by running this exact test against a scratch
    worktree checked out at c220d467d, where it fails
    (``AssertionError: resolver.resolve('01M3PACE') must not be called with a
    fact present``), and it passes at every commit from 5ba2888e8 onward."""
    from mission_runtime import mission_context_for

    class _ExplosiveResolver:
        def resolve(self, handle: str) -> object:
            raise AssertionError(f"resolver.resolve({handle!r}) must not be called with a fact present")

        def all_missions(self) -> object:
            raise AssertionError("resolver.all_missions() must not be called with a fact present")

    fact = _mint(tmp_path)
    context = mission_context_for(fact.repository_root, _MID8, owned=fact, resolver=_ExplosiveResolver())
    assert context.artifact(MissionArtifactKind.SPEC).read_dir == fact.mission_dir


def test_owned_explicit_topology_conflict_is_refused(tmp_path: Path) -> None:
    """R1: an explicit ``topology`` argument that disagrees with the fact's
    own stored topology raises ``OwnedRefusalCode.OWNED_TOPOLOGY_UNSUPPORTED``
    (the code path existed before this cycle; only the pin was missing)."""
    from mission_runtime import mission_context_for

    fact = _mint(tmp_path, topology=MissionTopology.SINGLE_BRANCH)
    with pytest.raises(ActionContextError) as excinfo:
        mission_context_for(fact.repository_root, _SLUG, MissionTopology.LANES, owned=fact)
    assert excinfo.value.code == OwnedRefusalCode.OWNED_TOPOLOGY_UNSUPPORTED


def test_owned_target_branch_comes_from_the_fact_not_meta(tmp_path: Path) -> None:
    """R1: the target branch comes from ``owned.write_branch`` even when
    ``meta.json`` on disk says otherwise -- the fact, not a re-read, is
    authoritative once minted."""
    from mission_runtime import mission_context_for

    fact = _mint(tmp_path, target_branch="codex/from-the-fact")
    # Corrupt meta.json on disk AFTER minting so a re-read would disagree.
    (fact.mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01M3PACE000000000000000001",
                "mission_slug": _SLUG,
                "slug": _SLUG,
                "mission_type": "software-dev",
                "topology": "single_branch",
                "target_branch": "codex/from-disk-not-the-fact",
            }
        ),
        encoding="utf-8",
    )

    context = mission_context_for(fact.repository_root, _SLUG, owned=fact)
    assert context.artifact(MissionArtifactKind.SPEC).commit_target is not None
    assert context.artifact(MissionArtifactKind.SPEC).commit_target.ref == "codex/from-the-fact"


def test_primary_kinds_write_target_is_target_branch(tmp_path: Path) -> None:
    fact = _mint(tmp_path, target_branch="release/main")
    seam = placement_seam(fact.repository_root, _SLUG, owned=fact)
    for kind in MissionArtifactKind:
        if not is_primary_artifact_kind(kind):
            continue
        assert seam.write_target(kind).ref == "release/main", kind


# ===========================================================================
# T019 — topology has exactly ONE authority (the minter); the placement layer
# no longer refuses a coordination-routing fact.
# ===========================================================================


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _lanes_with_coord_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A real git repo carrying a ``lanes_with_coord`` mission with a
    materialised coordination worktree -- so a COORD-partition read has a real
    location to resolve to (not just the declared-but-unmaterialized window)."""
    r = tmp_path / "R"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "wp04-t019@example.test")
    _git(r, "config", "user.name", "WP04 T019")
    _git(r, "config", "commit.gpgsign", "false")
    (r / "README.md").write_text("seed\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "seed")

    p = tmp_path / "P"
    _git(r, "worktree", "add", "-qb", "codex/owned-coord", str(p))
    mid8 = "01M3LAWC"
    mission_id = f"{mid8}00000000000000000001"
    mission = p / "kitty-specs" / f"{_SLUG}-{mid8}"
    mission.mkdir(parents=True)
    coord_branch = f"kitty/mission-owned-coord-{mid8.lower()}"
    _git(r, "branch", coord_branch)
    coord_worktree = r / ".worktrees" / f"{_SLUG}-{mid8}-coord"
    _git(r, "worktree", "add", "-q", str(coord_worktree), coord_branch)
    (coord_worktree / "kitty-specs" / f"{_SLUG}-{mid8}").mkdir(parents=True)
    _git(coord_worktree, "add", "-A")
    subprocess.run(["git", "commit", "-qm", "materialize coord"], cwd=coord_worktree, check=False)

    (mission / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mission_slug": f"{_SLUG}-{mid8}",
                "slug": f"{_SLUG}-{mid8}",
                "mission_type": "software-dev",
                "topology": "lanes_with_coord",
                "target_branch": "codex/owned-coord",
                "coordination_branch": coord_branch,
            }
        ),
        encoding="utf-8",
    )
    _git(p, "add", "-A")
    _git(p, "commit", "-qm", "owned coord mission")
    return r, p


def test_lanes_with_coord_fact_places_spec_on_target_branch(tmp_path: Path) -> None:
    """Red-first (T019): on base this refuses with ``OWNED_TOPOLOGY_UNSUPPORTED``
    (the now-deleted ``_require_owned_single_branch`` guard); after the fix, a
    ``lanes_with_coord`` fact places a PRIMARY kind on the target branch exactly
    like any other topology."""
    r, p = _lanes_with_coord_repo(tmp_path)
    mid8 = "01M3LAWC"
    slug = f"{_SLUG}-{mid8}"
    fact = OwnedCheckout._mint(
        repository_root=r,
        owned_root=p,
        mission_dir=p / "kitty-specs" / slug,
        mission_slug=slug,
        topology=MissionTopology.LANES_WITH_COORD,
        write_branch="codex/owned-coord",
    )

    target = placement_seam(r, slug, owned=fact).write_target(MissionArtifactKind.SPEC)
    assert target.ref == "codex/owned-coord"


def _lanes_with_coord_fact(r: Path, p: Path) -> OwnedCheckout:
    mid8 = "01M3LAWC"
    slug = f"{_SLUG}-{mid8}"
    return OwnedCheckout._mint(
        repository_root=r,
        owned_root=p,
        mission_dir=p / "kitty-specs" / slug,
        mission_slug=slug,
        topology=MissionTopology.LANES_WITH_COORD,
        write_branch="codex/owned-coord",
    )


def test_lanes_with_coord_fact_stamps_status_state_coord_and_spec_primary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T019 step 6 table row 4: a materialised coord-partition kind stamps
    COORD at the REAL coordination-worktree path (review cycle 1 F2/F3) --
    never the vacuous stamp-only assertion the rejected version pinned.

    The path is under ``owned.repository_root/.worktrees`` (never under the
    selected owned checkout ``P``) and actually exists on disk. Row 3 (a
    PRIMARY kind under the same coord-routing topology) stamps PRIMARY at
    ``owned.mission_dir``.
    """
    from mission_runtime.resolution import resolve_artifact_surface

    r, p = _lanes_with_coord_repo(tmp_path)
    fact = _lanes_with_coord_fact(r, p)

    git_calls = []
    real_run = subprocess.run

    def _counting_run(*args: object, **kwargs: object) -> object:
        git_calls.append(args)
        return real_run(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(subprocess, "run", _counting_run)

    status_surface = resolve_artifact_surface(r, fact.mission_slug, MissionArtifactKind.STATUS_STATE, owned=fact)
    assert status_surface.surface_kind is TopologySurface.COORD
    assert status_surface.path.is_relative_to(r / ".worktrees")
    assert status_surface.path.exists()
    assert status_surface.path != fact.mission_dir

    # Row-4 git-call count (Activity Log requirement, T019 step 6): a
    # MATERIALIZED coord read is ZERO subprocess calls --
    # ``probe_coord_state`` classifies MATERIALIZED/EMPTY/UNMATERIALIZED from
    # ``Path.exists()`` alone; only the DELETED leg (absent coord dir +
    # declared branch) shells out to ``git rev-parse`` once. This assertion
    # is the recorded count, not a floor.
    assert git_calls == []

    spec_surface = resolve_artifact_surface(r, fact.mission_slug, MissionArtifactKind.SPEC, owned=fact)
    assert spec_surface.surface_kind is TopologySurface.PRIMARY
    assert spec_surface.path == fact.mission_dir


def test_single_branch_fact_stamps_status_state_primary_at_mission_dir(tmp_path: Path) -> None:
    """T019 step 6 table row 2: a COORD-partition kind under ``single_branch``
    (no coordination routing at all) stamps PRIMARY at ``owned.mission_dir`` --
    the review cycle 1 F3 regression this pins."""
    from mission_runtime.resolution import resolve_artifact_surface

    fact = _mint(tmp_path)  # single_branch, no coordination_branch in meta

    surface = resolve_artifact_surface(fact.repository_root, _SLUG, MissionArtifactKind.STATUS_STATE, owned=fact)
    assert surface.surface_kind is TopologySurface.PRIMARY
    assert surface.path == fact.mission_dir


def test_row3_primary_kind_reads_mission_dir_even_when_coord_unmaterialized(tmp_path: Path) -> None:
    """T019 table row 3 (review cycle 2 R2 item 1): a PRIMARY kind (SPEC)
    resolves ``owned.mission_dir``, stamped PRIMARY, under a
    ``lanes_with_coord`` fact whose coordination worktree is NOT yet
    materialised -- exactly the mission create -> first materialisation
    window when spec/plan are written. Before this fix,
    ``resolve_artifact_surface(..., SPEC, owned=fact)`` raised
    ``OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`` because the status surface
    was built eagerly for every kind."""
    from mission_runtime.resolution import resolve_artifact_surface

    r, p = _lanes_with_coord_repo(tmp_path)
    fact = _lanes_with_coord_fact(r, p)
    coord_worktree = r / ".worktrees" / f"{_SLUG}-01M3LAWC-coord"
    _git(r, "worktree", "remove", "--force", str(coord_worktree))

    surface = resolve_artifact_surface(r, fact.mission_slug, MissionArtifactKind.SPEC, owned=fact)
    assert surface.surface_kind is TopologySurface.PRIMARY
    assert surface.path == fact.mission_dir


def test_row4_coord_empty_state_fails_closed_never_silently_primary(tmp_path: Path) -> None:
    """T019 table row 4 / #1716 (review cycle 2 R2 item 2): the coordination
    worktree ROOT exists but its mission directory is absent (``CoordState.
    EMPTY``) -- documented as "a fail-closed condition, never a silent
    primary fallback". A COORD-partition kind (STATUS_STATE) must fail
    closed with the typed refusal, never silently resolve the primary
    checkout instead."""
    from mission_runtime.resolution import resolve_artifact_surface

    r, p = _lanes_with_coord_repo(tmp_path)
    fact = _lanes_with_coord_fact(r, p)
    # Remove only the mission subdirectory under the coord worktree, leaving
    # the coord worktree root itself present -- CoordState.EMPTY.
    coord_mission_dir = r / ".worktrees" / f"{_SLUG}-01M3LAWC-coord" / "kitty-specs" / f"{_SLUG}-01M3LAWC"
    import shutil

    shutil.rmtree(coord_mission_dir)

    with pytest.raises(ActionContextError) as excinfo:
        resolve_artifact_surface(r, fact.mission_slug, MissionArtifactKind.STATUS_STATE, owned=fact)
    assert excinfo.value.code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE


def test_unmaterialized_coord_fails_closed_never_a_predicted_path(tmp_path: Path) -> None:
    """review cycle 1 F2: the declared-but-not-yet-materialised coordination
    worktree fails closed with a typed ``OwnedRefusalCode`` error -- never a
    silently-returned path that does not exist on disk."""
    from mission_runtime.resolution import resolve_artifact_surface

    r, p = _lanes_with_coord_repo(tmp_path)
    fact = _lanes_with_coord_fact(r, p)
    # Remove the coordination worktree the fixture materialised, so the coord
    # state probes UNMATERIALIZED (the declared-but-not-yet-created window).
    coord_worktree = r / ".worktrees" / f"{_SLUG}-01M3LAWC-coord"
    _git(r, "worktree", "remove", "--force", str(coord_worktree))

    with pytest.raises(ActionContextError) as excinfo:
        resolve_artifact_surface(r, fact.mission_slug, MissionArtifactKind.STATUS_STATE, owned=fact)
    assert excinfo.value.code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE


# ---------------------------------------------------------------------------
# WP19 cycle 2: the fail-closed boundary of ``tolerate_unmaterialized_coord``.
# ---------------------------------------------------------------------------

_COORD_MID8 = "01M3LAWC"


def _tolerant_status_read_dir(r: Path, fact: OwnedCheckout) -> Path:
    from mission_runtime import mission_context_for

    context = mission_context_for(r, fact.mission_slug, owned=fact, tolerate_unmaterialized_coord=True)
    return context.artifact(MissionArtifactKind.STATUS_STATE).read_dir


def test_tolerate_flag_unmaterialized_returns_the_declared_coord_candidate_never_p(tmp_path: Path) -> None:
    """With the flag, UNMATERIALIZED (declared, not yet created) resolves the DECLARED coordination
    candidate under ``repository_root/.worktrees`` -- not P, not ``mission_dir``."""
    r, p = _lanes_with_coord_repo(tmp_path)
    fact = _lanes_with_coord_fact(r, p)
    coord_worktree = r / ".worktrees" / f"{_SLUG}-{_COORD_MID8}-coord"
    _git(r, "worktree", "remove", "--force", str(coord_worktree))

    read_dir = _tolerant_status_read_dir(r, fact)

    assert read_dir == coord_worktree / "kitty-specs" / f"{_SLUG}-{_COORD_MID8}"
    assert read_dir != fact.mission_dir
    assert not read_dir.is_relative_to(p)
    assert read_dir.is_relative_to(r / ".worktrees")
    assert not read_dir.exists()


def test_tolerate_flag_empty_still_fails_closed_never_substituting_primary(tmp_path: Path) -> None:
    """#1716: EMPTY (worktree root present, mission dir absent) stays fail-closed under the flag."""
    import shutil

    r, p = _lanes_with_coord_repo(tmp_path)
    fact = _lanes_with_coord_fact(r, p)
    shutil.rmtree(r / ".worktrees" / f"{_SLUG}-{_COORD_MID8}-coord" / "kitty-specs" / f"{_SLUG}-{_COORD_MID8}")

    with pytest.raises(ActionContextError) as excinfo:
        _tolerant_status_read_dir(r, fact)
    assert excinfo.value.code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE


def test_tolerate_flag_none_state_still_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NONE (no mid8 signal) stays fail-closed under the flag."""
    from specify_cli.missions import _read_path_resolver

    r, p = _lanes_with_coord_repo(tmp_path)
    fact = _lanes_with_coord_fact(r, p)
    monkeypatch.setattr(_read_path_resolver, "probe_coord_state", lambda *_a, **_k: _read_path_resolver.CoordState.NONE)

    with pytest.raises(ActionContextError) as excinfo:
        _tolerant_status_read_dir(r, fact)
    assert excinfo.value.code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE


def test_tolerate_flag_deleted_coordination_branch_still_raises_the_deleted_error(tmp_path: Path) -> None:
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    r, p = _lanes_with_coord_repo(tmp_path)
    fact = _lanes_with_coord_fact(r, p)
    _git(r, "worktree", "remove", "--force", str(r / ".worktrees" / f"{_SLUG}-{_COORD_MID8}-coord"))
    _git(r, "branch", "-D", f"kitty/mission-owned-coord-{_COORD_MID8.lower()}")

    with pytest.raises(CoordinationBranchDeleted):
        _tolerant_status_read_dir(r, fact)


# ===========================================================================
# F4 — handle canonicalisation: slug, mid8, and mission id all name the fact.
# ===========================================================================


@pytest.mark.parametrize("handle_kind", ["slug", "mid8", "mission_id"])
def test_owned_handle_forms_all_resolve_the_same_fact(tmp_path: Path, handle_kind: str) -> None:
    fact = _mint(tmp_path)
    handle = {
        "slug": _SLUG,
        "mid8": _MID8,
        "mission_id": "01M3PACE000000000000000001",
    }[handle_kind]

    seam = placement_seam(fact.repository_root, handle, owned=fact)
    assert seam.read_dir(MissionArtifactKind.SPEC) == fact.mission_dir


def test_owned_handle_mismatch_is_refused(tmp_path: Path) -> None:
    fact = _mint(tmp_path)
    with pytest.raises(ActionContextError) as excinfo:
        placement_seam(fact.repository_root, "some-unrelated-mission", owned=fact)
    assert fact.mission_slug in str(excinfo.value)
    assert "some-unrelated-mission" in str(excinfo.value)


def test_owned_handle_prefix_match_is_refused(tmp_path: Path) -> None:
    """R3 (review cycle 2): a handle that merely STARTS WITH the mid8 --
    never a legitimate mission-id or mid8 form -- is refused, not silently
    accepted by an over-permissive prefix check."""
    fact = _mint(tmp_path)
    with pytest.raises(ActionContextError):
        placement_seam(fact.repository_root, f"{_MID8}-something-else", owned=fact)


def test_symlinked_owned_root_resolves_to_the_real_mission_dir(tmp_path: Path) -> None:
    """T016 edge case: a symlinked P -- owned identity is canonical."""
    real_p = tmp_path / "P-real"
    real_p.mkdir()
    link_p = tmp_path / "P-link"
    link_p.symlink_to(real_p, target_is_directory=True)
    r = tmp_path / "R"
    r.mkdir()

    mission_dir = link_p / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01M3SYMLINKCASE00000001",
                "mission_slug": _SLUG,
                "slug": _SLUG,
                "mission_type": "software-dev",
                "topology": "single_branch",
                "target_branch": "main",
            }
        ),
        encoding="utf-8",
    )
    fact = OwnedCheckout._mint(
        repository_root=r,
        owned_root=link_p,
        mission_dir=mission_dir,
        mission_slug=_SLUG,
        topology=MissionTopology.SINGLE_BRANCH,
        write_branch="main",
    )

    seam = placement_seam(fact.repository_root, _SLUG, owned=fact)
    resolved = seam.read_dir(MissionArtifactKind.SPEC)
    assert resolved.is_relative_to(real_p.resolve())


def test_require_owned_single_branch_is_gone() -> None:
    """DoD gate: the deleted guard is not re-introduced under any name."""
    import mission_runtime.resolution as resolution_module

    assert not hasattr(resolution_module, "_require_owned_single_branch")


# ===========================================================================
# S1 (review cycle 3) — ``mission_context_for(owned=)`` must be built from
# the SAME per-kind rule as ``resolve_artifact_surface`` /
# ``resolve_placement_only`` (``_owned_read_dir_for_kind`` /
# ``_owned_commit_target_for_kind``), not a second, independently-diverging
# copy of it.
# ===========================================================================


def test_mission_context_for_owned_calls_the_per_kind_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """S1 (review cycle 3, blocking item 1): ``_mission_context_for_owned``
    must build every ``MissionArtifactContext`` by CALLING
    ``_owned_read_dir_for_kind`` / ``_owned_commit_target_for_kind`` -- the
    SAME per-kind rule ``resolve_artifact_surface`` / ``resolve_placement_only``
    already use -- rather than re-implementing the primary/non-primary
    branching and the ``coord_ref`` expression a second time inline.

    This pins the CALL, not merely the resulting value: a reintroduced
    second copy that happens to compute identical values (as the cycle-2
    duplicate did -- the two copies only ever disagreed on whether they
    raise, not on what they return when they don't) would still be caught,
    where a pure value-agreement assertion could not distinguish it. Verified
    red first: at the cycle-2 tip (5ba2888e8 / 66bfb2855, the pre-cycle-3
    source) neither spy is ever invoked, so both call lists are empty
    against the expected full kind list."""
    import mission_runtime.resolution as resolution_module
    from mission_runtime import mission_context_for

    read_calls: list[MissionArtifactKind] = []
    commit_calls: list[MissionArtifactKind] = []
    real_read = resolution_module._owned_read_dir_for_kind
    real_commit = resolution_module._owned_commit_target_for_kind

    def _spy_read(owned: OwnedCheckout, mission_slug: str, kind: MissionArtifactKind, *, resolver: object, tolerate_unmaterialized_coord: bool = False) -> Path:
        read_calls.append(kind)
        return real_read(owned, mission_slug, kind, resolver=resolver, tolerate_unmaterialized_coord=tolerate_unmaterialized_coord)

    def _spy_commit(owned: OwnedCheckout, mission_slug: str, kind: MissionArtifactKind, *, resolver: object) -> object:
        commit_calls.append(kind)
        return real_commit(owned, mission_slug, kind, resolver=resolver)

    monkeypatch.setattr(resolution_module, "_owned_read_dir_for_kind", _spy_read)
    monkeypatch.setattr(resolution_module, "_owned_commit_target_for_kind", _spy_commit)

    fact = _mint(tmp_path)
    mission_context_for(fact.repository_root, _SLUG, owned=fact)

    all_kinds = list(MissionArtifactKind)
    assert read_calls == all_kinds
    assert commit_calls == all_kinds


_AGREEMENT_KINDS = list(MissionArtifactKind)  # review cycle 4 item 2: RETROSPECTIVE included -- all three resolvers agree on it.
_AGREEMENT_TOPOLOGIES = [
    MissionTopology.SINGLE_BRANCH,
    MissionTopology.LANES,
    MissionTopology.COORD,
    MissionTopology.LANES_WITH_COORD,
]


@pytest.mark.parametrize("topology", _AGREEMENT_TOPOLOGIES, ids=["single_branch", "lanes", "coord", "lanes_with_coord"])
@pytest.mark.parametrize("coord_state", ["materialized", "empty", "unmaterialized"])
@pytest.mark.parametrize("kind", _AGREEMENT_KINDS, ids=[k.value for k in _AGREEMENT_KINDS])
def test_mission_context_for_owned_agrees_with_the_per_kind_resolvers(
    tmp_path: Path,
    topology: MissionTopology,
    coord_state: str,
    kind: MissionArtifactKind,
) -> None:
    """S1: ``mission_context_for(owned=)`` must agree with
    ``resolve_artifact_surface`` / ``resolve_placement_only`` for every
    (topology, coordination state, kind) cell -- 4 topologies x 3 states x
    18 kinds -- because all three now share exactly ONE per-kind rule.

    Review cycle 4: the coordination-worktree mutation (``empty`` /
    ``unmaterialized``) is applied for EVERY topology, not just a
    coordination-routing one -- ``single_branch`` / ``lanes`` never route
    through coordination at all (:func:`routes_through_coordination`), so
    every cell for those topologies must resolve regardless of
    ``coord_state``, and that claim is only pinned if the mutation actually
    ran. Only a coordination-routing topology (``coord`` /
    ``lanes_with_coord``) whose worktree is not MATERIALIZED can make the
    WHOLE-context build fail closed with
    ``OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`` (accepted, IC-05 ->
    ``blocked``): it must resolve the COORD kinds too. When it does, the
    single-kind resolvers must still succeed per kind -- a PRIMARY kind
    resolves (T019 row 3) and a COORD-partition kind raises the SAME
    documented code from both ``resolve_artifact_surface`` and
    ``resolve_placement_only``."""
    import shutil

    from mission_runtime import mission_context_for
    from mission_runtime.owned_checkout import OwnedCheckout
    from mission_runtime.resolution import resolve_artifact_surface, resolve_placement_only

    r, p = _lanes_with_coord_repo(tmp_path)
    mid8 = "01M3LAWC"
    slug = f"{_SLUG}-{mid8}"
    coord_worktree = r / ".worktrees" / f"{slug}-coord"
    if coord_state == "empty":
        shutil.rmtree(coord_worktree / "kitty-specs" / slug)
    elif coord_state == "unmaterialized":
        _git(r, "worktree", "remove", "--force", str(coord_worktree))
    # "materialized": leave the fixture's coordination worktree as-is. Applied
    # unconditionally, for every topology -- single_branch/lanes never probe
    # this worktree at all, so exercising the mutation for them too is what
    # actually pins "resolves regardless of coord_state", rather than merely
    # asserting it against an untouched fixture.

    fact = OwnedCheckout._mint(
        repository_root=r,
        owned_root=p,
        mission_dir=p / "kitty-specs" / slug,
        mission_slug=slug,
        topology=topology,
        write_branch="codex/owned-coord",
    )

    refusal: ActionContextError | None = None
    try:
        context = mission_context_for(r, slug, owned=fact)
    except ActionContextError as exc:
        refusal = exc
    if refusal is not None:
        assert refusal.code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE
        # This refusal is only an accepted whole-context outcome when the
        # cell actually routes through coordination and is NOT materialized
        # -- never for single_branch/lanes, and never for "materialized".
        assert routes_through_coordination(topology)
        assert coord_state != "materialized"
        if is_primary_artifact_kind(kind):
            surface = resolve_artifact_surface(r, slug, kind, owned=fact)
            assert surface.path == fact.mission_dir
            target = resolve_placement_only(r, slug, kind=kind, owned=fact)
            assert target.ref == fact.write_branch
        else:
            # The other half of "raise the documented code consistently":
            # a COORD-partition kind's READ side refuses per kind too, with
            # the SAME code (resolve_artifact_surface -- review cycle 4 item
            # 3). resolve_placement_only does NOT raise here: R2 (review
            # cycle 2) made placement deliberately never probe coordination
            # MATERIALIZATION -- it resolves to the declared coordination
            # branch value regardless of EMPTY/UNMATERIALIZED, which is the
            # existing, already-verified contract (not something this cycle
            # changes); assert that positive value instead of a raise.
            with pytest.raises(ActionContextError) as surface_excinfo:
                resolve_artifact_surface(r, slug, kind, owned=fact)
            assert surface_excinfo.value.code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE
            target = resolve_placement_only(r, slug, kind=kind, owned=fact)
            assert target.ref == f"kitty/mission-owned-coord-{mid8.lower()}"  # the declared coordination_branch (_lanes_with_coord_repo)
        return

    artifact_ctx = context.artifact(kind)
    surface = resolve_artifact_surface(r, slug, kind, owned=fact)
    assert artifact_ctx.read_dir == surface.path, (topology, coord_state, kind)
    target = resolve_placement_only(r, slug, kind=kind, owned=fact)
    assert artifact_ctx.commit_target == target, (topology, coord_state, kind)
