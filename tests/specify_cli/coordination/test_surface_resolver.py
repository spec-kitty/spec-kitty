"""Tests for specify_cli.coordination.surface_resolver."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import inspect

from specify_cli.coordination import surface_resolver
from specify_cli.coordination.surface_resolver import (
    resolve_status_surface,
    resolve_status_surface_with_anchor,
)
from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

pytestmark = pytest.mark.fast


def _write_meta(feature_dir: Path, **fields: object) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(fields), encoding="utf-8")


def test_resolve_primary_checkout_when_no_coord_branch(tmp_path: Path) -> None:
    _write_meta(tmp_path / "kitty-specs" / "my-mission", mission_id="01KTDVHZKGCHCW6HQ4V577PNES")
    result = resolve_status_surface(tmp_path, "my-mission")
    assert result == tmp_path / "kitty-specs" / "my-mission" / "status.events.jsonl"


def test_resolve_coordination_worktree_when_coord_branch_set(tmp_path: Path) -> None:
    _write_meta(
        tmp_path / "kitty-specs" / "my-mission",
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        coordination_branch="kitty/mission-my-mission-01KTDVHZ",
    )
    result = resolve_status_surface(tmp_path, "my-mission")
    expected = tmp_path / ".worktrees" / "my-mission-01KTDVHZ-coord" / "kitty-specs" / "my-mission-01KTDVHZ" / "status.events.jsonl"
    assert result == expected


def test_raises_when_meta_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_status_surface(tmp_path, "no-such-mission")


def test_mid8_is_first_8_chars_of_mission_id(tmp_path: Path) -> None:
    _write_meta(
        tmp_path / "kitty-specs" / "my-mission",
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        coordination_branch="kitty/mission-my-mission-01KTDVHZ",
    )
    result = resolve_status_surface(tmp_path, "my-mission")
    assert "my-mission-01KTDVHZ-coord" in str(result)


def test_resolve_uses_explicit_mid8_field_when_present(tmp_path: Path) -> None:
    _write_meta(
        tmp_path / "kitty-specs" / "my-mission",
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        mid8="ABCD1234",
        coordination_branch="kitty/mission-my-mission-ABCD1234",
    )
    result = resolve_status_surface(tmp_path, "my-mission")
    assert "my-mission-ABCD1234-coord" in str(result)


def test_slug_with_mid8_already_embedded_is_not_doubled(tmp_path: Path) -> None:
    _write_meta(
        tmp_path / "kitty-specs" / "my-mission-01KTDVHZ",
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        coordination_branch="kitty/mission-my-mission-01KTDVHZ",
    )
    result = resolve_status_surface(tmp_path, "my-mission-01KTDVHZ")
    assert "my-mission-01KTDVHZ-coord" in str(result)
    assert "my-mission-01KTDVHZ-01KTDVHZ" not in str(result)


def test_materialized_coord_worktree_resolves_exactly_once(tmp_path: Path) -> None:
    """FR-036 (#1772): a coord-topology mission resolves the status surface
    exactly once — no nested ``.worktrees/<m>-coord/.worktrees/<m>-coord/…``.

    Before the single-pass fix, ``resolve_status_surface`` first called the
    coord-aware ``candidate_feature_dir_for_mission`` (which already returns the
    materialized coord feature dir), then *re-derived* a coord root and resolved
    a **second** time. When a nested ``.worktrees/<m>-coord`` directory exists
    *inside* the coord worktree, that second coord-aware resolution picked it,
    producing a path with ``.worktrees`` twice. This regression plants exactly
    that nested trap and proves the single-pass resolver ignores it: the result
    contains ``.worktrees`` exactly once and points at the real coord feature
    dir.
    """
    slug = "my-mission-01KTDVHZ"  # slug already embeds mid8 → coord-aware on 1st pass
    mid8 = "01KTDVHZ"
    coord_root = tmp_path / ".worktrees" / f"{slug}-coord"
    coord_feature_dir = coord_root / "kitty-specs" / slug
    _write_meta(
        coord_feature_dir,
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        mid8=mid8,
        coordination_branch=f"kitty/mission-{slug}",
    )

    # Plant the nested-coord trap that the old double-resolution would follow.
    nested_trap = coord_root / ".worktrees" / f"{slug}-coord" / "kitty-specs" / slug
    _write_meta(
        nested_trap,
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        mid8=mid8,
        coordination_branch=f"kitty/mission-{slug}",
    )

    result = resolve_status_surface(tmp_path, slug)

    assert str(result).count(".worktrees") == 1, f"FR-036 regression: status surface double-resolved into a nested path: {result}"
    assert result == coord_feature_dir / "status.events.jsonl"


def test_merged_coord_mission_resolves_primary_before_stale_coord_worktree(
    tmp_path: Path,
) -> None:
    """Primary completion evidence outranks a stale materialized coord husk."""
    slug = "merged-mission-01KTDVHZ"
    primary_dir = tmp_path / "kitty-specs" / slug
    coord_dir = tmp_path / ".worktrees" / f"{slug}-coord" / "kitty-specs" / slug
    _write_meta(
        primary_dir,
        mission_slug=slug,
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        mid8="01KTDVHZ",
        mission_type="software-dev",
        coordination_branch=f"kitty/mission-{slug}",
        topology="coord",
        merged_at="2026-08-30T00:00:00+00:00",
    )
    _write_meta(
        coord_dir,
        mission_slug=slug,
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        mid8="01KTDVHZ",
        mission_type="software-dev",
        coordination_branch=f"kitty/mission-{slug}",
        topology="coord",
    )
    # Merged-with-events (squad pass 2): primary wins even when coord also
    # carries a log — and even without its own log (see
    # test_merged_primary_wins_even_when_only_coord_has_events).
    (primary_dir / "status.events.jsonl").write_text("", encoding="utf-8")
    (coord_dir / "status.events.jsonl").write_text("", encoding="utf-8")

    resolved = resolve_status_surface_with_anchor(tmp_path, slug)

    assert resolved.read_dir.resolve() == primary_dir.resolve()
    assert resolved.primary_anchor.resolve() == primary_dir.resolve()


def test_merged_primary_wins_even_when_only_coord_has_events(
    tmp_path: Path,
) -> None:
    """Pin (squad pass 2 MINOR, option b): merge evidence makes primary
    authoritative even when only the coord husk carries a
    ``status.events.jsonl`` — a stale coord log must not resurrect husk reads
    after the merge. The primary-side empty read is accepted: the runtime
    bridge's merged gate returns terminal before any surface read matters."""
    slug = "merged-nolog-01KTDVHZ"
    coord_dir = tmp_path / ".worktrees" / f"{slug}-coord" / "kitty-specs" / slug
    _write_meta(
        tmp_path / "kitty-specs" / slug,
        mission_slug=slug,
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        mid8="01KTDVHZ",
        mission_type="software-dev",
        coordination_branch=f"kitty/mission-{slug}",
        topology="coord",
        merged_at="2026-08-30T00:00:00+00:00",
    )
    _write_meta(
        coord_dir,
        mission_slug=slug,
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        mid8="01KTDVHZ",
        mission_type="software-dev",
        coordination_branch=f"kitty/mission-{slug}",
        topology="coord",
    )
    (coord_dir / "status.events.jsonl").write_text("", encoding="utf-8")

    resolved = resolve_status_surface_with_anchor(tmp_path, slug)

    assert resolved.read_dir.resolve() == (tmp_path / "kitty-specs" / slug).resolve()


def test_unmerged_coord_mission_keeps_coord_surface_when_all_wps_terminal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No merge marker => no primary re-anchor: an unmerged coord mission still
    reads its coord worktree (squad pass 1: primary can be stale until merge).

    Mutation guard (squad pass 2): ``is_mission_completed`` is patched ``True``
    so re-widening the resolver helper back to it makes this test fail."""
    import specify_cli.status as status_pkg

    monkeypatch.setattr(status_pkg, "is_mission_completed", lambda *_a, **_k: True)
    slug = "unmerged-mission-01KTDVHZ"  # both surfaces get event logs below
    coord_dir = tmp_path / ".worktrees" / f"{slug}-coord" / "kitty-specs" / slug
    _write_meta(
        tmp_path / "kitty-specs" / slug,
        mission_slug=slug,
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        mid8="01KTDVHZ",
        mission_type="software-dev",
        coordination_branch=f"kitty/mission-{slug}",
        topology="coord",
    )
    _write_meta(
        coord_dir,
        mission_slug=slug,
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        mid8="01KTDVHZ",
        mission_type="software-dev",
        coordination_branch=f"kitty/mission-{slug}",
        topology="coord",
    )
    (tmp_path / "kitty-specs" / slug / "status.events.jsonl").write_text("", encoding="utf-8")
    (coord_dir / "status.events.jsonl").write_text("", encoding="utf-8")

    resolved = resolve_status_surface_with_anchor(tmp_path, slug)

    assert resolved.read_dir.resolve() == coord_dir.resolve()


def test_corrupt_primary_meta_does_not_break_coord_resolution(
    tmp_path: Path,
) -> None:
    """Corrupt PRIMARY meta with a valid coord surface must not raise out of
    resolution (squad pass 1 MINOR): the merged-primary pre-check reads as
    not-merged and resolution proceeds on the coord worktree's own meta."""
    slug = "corrupt-mission-01KTDVHZ"
    coord_dir = tmp_path / ".worktrees" / f"{slug}-coord" / "kitty-specs" / slug
    primary_dir = tmp_path / "kitty-specs" / slug
    _write_meta(
        coord_dir,
        mission_slug=slug,
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        mid8="01KTDVHZ",
        mission_type="software-dev",
        coordination_branch=f"kitty/mission-{slug}",
        topology="coord",
    )
    primary_dir.mkdir(parents=True, exist_ok=True)
    (primary_dir / "meta.json").write_text("{not json", encoding="utf-8")

    resolved = resolve_status_surface_with_anchor(tmp_path, slug)

    assert resolved.read_dir.resolve() == coord_dir.resolve()


def test_unresolvable_mid8_fails_closed_instead_of_fabricating(tmp_path: Path) -> None:
    """C-cluster fix (FR-005 / F-001): when a coord-topology mission declares a
    coordination branch but no declared source carries the mid8 (no ``mid8``
    field, no >=8-char ``mission_id``, and the slug embeds no mid8), the resolver
    must fail closed with :class:`StatusReadPathNotFound` rather than fabricate a
    wrong-but-plausible ``(slug+"00000000")[:8]`` coord path.
    """
    _write_meta(
        tmp_path / "kitty-specs" / "my-mission",
        coordination_branch="kitty/mission-my-mission",
    )
    with pytest.raises(StatusReadPathNotFound):
        resolve_status_surface(tmp_path, "my-mission")


def test_fabricated_mid8_idiom_is_gone_from_source() -> None:
    """The forbidden fabrication idiom ``(... + "00000000")[:8]`` must have zero
    occurrences in the resolver source — fabricating a mid8 violates the 3.x
    invariant that unresolvable context raises rather than falling back."""
    source = inspect.getsource(surface_resolver)
    assert "00000000" not in source


# ---------------------------------------------------------------------------
# ResolvedStatusSurface.read_dir + meta-None fallback surfaces
# ---------------------------------------------------------------------------


def test_resolved_surface_read_dir_is_parent_of_surface_path(tmp_path: Path) -> None:
    """``read_dir`` returns the directory containing the resolved events file."""
    from specify_cli.coordination.surface_resolver import (
        resolve_status_surface_with_anchor,
    )

    feature_dir = tmp_path / "kitty-specs" / "my-mission"
    _write_meta(feature_dir, mission_id="01KTDVHZKGCHCW6HQ4V577PNES")
    resolved = resolve_status_surface_with_anchor(tmp_path, "my-mission")
    assert resolved.read_dir == feature_dir
    assert resolved.surface_path.parent == resolved.read_dir


def test_meta_absent_but_primary_dir_exists_returns_primary_surface(
    tmp_path: Path,
) -> None:
    """When ``meta.json`` is absent but the primary mission dir exists, the
    resolver returns the primary status surface (the create→first-write window
    authority) rather than raising."""
    # Directory exists with NO meta.json so ``load_meta`` returns None on both
    # the coord-aware candidate and the re-anchored primary dir.
    primary = tmp_path / "kitty-specs" / "my-mission"
    primary.mkdir(parents=True, exist_ok=True)
    result = resolve_status_surface(tmp_path, "my-mission")
    assert result == primary / "status.events.jsonl"


# ---------------------------------------------------------------------------
# read_worktree_registry / _coord_branch_exists fail-closed (OSError) branches
# ---------------------------------------------------------------------------


def test_read_worktree_registry_raises_when_git_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing/unexecutable git raises :class:`WorktreeRegistryUnavailable`
    (fail closed — never guess topology from path shape)."""
    from specify_cli.coordination.surface_resolver import (
        WorktreeRegistryUnavailable,
        read_worktree_registry,
    )

    def _boom(*_a: object, **_k: object) -> None:
        raise OSError("git not found")

    monkeypatch.setattr(surface_resolver.subprocess, "run", _boom)
    with pytest.raises(WorktreeRegistryUnavailable) as excinfo:
        read_worktree_registry(tmp_path)
    assert excinfo.value.error_code == "WORKTREE_REGISTRY_UNAVAILABLE"
    assert excinfo.value.repo_root == tmp_path


def test_read_worktree_registry_raises_on_nonzero_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-zero git exit surfaces the stderr detail in the fail-closed error."""
    import subprocess as _sp

    from specify_cli.coordination.surface_resolver import (
        WorktreeRegistryUnavailable,
        read_worktree_registry,
    )

    def _fail(*_a: object, **_k: object) -> _sp.CompletedProcess[str]:
        return _sp.CompletedProcess(args=["git"], returncode=128, stdout="", stderr="fatal: not a git repo")

    monkeypatch.setattr(surface_resolver.subprocess, "run", _fail)
    with pytest.raises(WorktreeRegistryUnavailable) as excinfo:
        read_worktree_registry(tmp_path)
    assert "not a git repo" in str(excinfo.value)


def test_coord_branch_exists_treats_non_repo_as_present(tmp_path: Path) -> None:
    """In a non-git directory the deleted-branch probe must NOT fire R3: it
    returns ``True`` (branch treated as present) so the resolver never invents a
    :class:`CoordinationBranchDeleted` from a non-repo context."""
    from specify_cli.coordination.surface_resolver import _coord_branch_exists

    # tmp_path is not a git repository → rev-parse --git-dir returns non-zero.
    assert _coord_branch_exists(tmp_path, "kitty/mission-anything") is True


def test_coord_branch_exists_treats_guest_of_enclosing_repo_as_present(
    tmp_path: Path,
) -> None:
    """#154: an ad-hoc directory INSIDE some unrelated checkout is not a repo
    context either.

    ``git rev-parse`` answers for any directory under a repository, so when an
    ambient ancestor checkout sits above the mission root (a dev host whose
    basetemp lives inside one), the walk-up finds THAT repo. Its ref space says
    nothing about this mission's declared branch, so firing R3 against it would
    invent a data-loss verdict from a foreign repo — the same contract violation
    the non-repo arm above forbids, one level removed."""
    import subprocess as _sp

    from specify_cli.coordination.surface_resolver import _coord_branch_exists

    outer = tmp_path / "ambient-checkout"
    outer.mkdir()
    _sp.run(["git", "init", "-q", "-b", "main", str(outer)], check=True)
    guest = outer / "ad-hoc" / "mission-root"
    guest.mkdir(parents=True)

    # The enclosing repo genuinely has no such ref — and that must not matter.
    assert _coord_branch_exists(guest, "kitty/mission-anything") is True


def test_coord_branch_exists_returns_true_when_git_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An OSError invoking git is treated fail-open for the branch probe (R2)."""
    from specify_cli.coordination.surface_resolver import _coord_branch_exists

    def _boom(*_a: object, **_k: object) -> None:
        raise OSError("git exploded")

    monkeypatch.setattr(surface_resolver.subprocess, "run", _boom)
    assert _coord_branch_exists(tmp_path, "kitty/mission-x") is True


def test_coordination_branch_deleted_raised_when_branch_gone(tmp_path: Path) -> None:
    """#1889 R3: coord branch declared in meta but DELETED from git (and no coord
    worktree) raises :class:`CoordinationBranchDeleted` with the distinct code."""
    import subprocess as _sp

    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    # Real git repo so the rev-parse probe runs and reports the branch absent.
    _sp.run(["git", "init", "-q", str(tmp_path)], check=True)
    _sp.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "t@t.invalid"],
        check=True,
    )
    _sp.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    _write_meta(
        tmp_path / "kitty-specs" / "my-mission",
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        coordination_branch="kitty/mission-my-mission-01KTDVHZ-coord",
    )
    with pytest.raises(CoordinationBranchDeleted) as excinfo:
        resolve_status_surface(tmp_path, "my-mission")
    err = excinfo.value
    assert err.error_code == "COORDINATION_BRANCH_DELETED"
    assert err.coordination_branch == "kitty/mission-my-mission-01KTDVHZ-coord"
    assert "doctor coordination --fix" in err.next_step


def test_for_mission_factory_fills_payload_from_probe_inputs(tmp_path: Path) -> None:
    """#4403: the ``for_mission`` factory is the ONE payload authority — it
    composes ``coord_candidate`` via the ``coord_feature_dir`` single grammar
    and threads the caller's authoritative ``primary_candidate`` through,
    producing the same fields the former per-site hand-rolled builds did."""
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
    from specify_cli.missions._read_path_resolver import coord_feature_dir

    primary = tmp_path / "kitty-specs" / "my-mission-01KTDVHZ"
    err = CoordinationBranchDeleted.for_mission(
        repo_root=tmp_path,
        mission_slug="my-mission",
        mid8="01KTDVHZ",
        coordination_branch="kitty/mission-my-mission-01KTDVHZ-coord",
        primary_candidate=primary,
    )
    assert isinstance(err, CoordinationBranchDeleted)
    assert err.error_code == "COORDINATION_BRANCH_DELETED"
    assert err.repo_root == tmp_path
    assert err.mission_slug == "my-mission"
    assert err.mid8 == "01KTDVHZ"
    assert err.coordination_branch == "kitty/mission-my-mission-01KTDVHZ-coord"
    assert err.coord_candidate == coord_feature_dir(tmp_path, "my-mission", "01KTDVHZ")
    assert err.primary_candidate == primary
    assert "doctor coordination --fix" in err.next_step


def test_for_mission_factory_coerces_none_branch(tmp_path: Path) -> None:
    """#4403 defensive arm: a ``None`` branch (unreachable on real DELETED
    paths — the probe answers DELETED only when a branch was supplied) coerces
    to ``""`` instead of crashing the data-loss raise."""
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    err = CoordinationBranchDeleted.for_mission(
        repo_root=tmp_path,
        mission_slug="my-mission",
        mid8="01KTDVHZ",
        coordination_branch=None,
        primary_candidate=tmp_path / "kitty-specs" / "my-mission-01KTDVHZ",
    )
    assert err.coordination_branch == ""


def test_coord_mid8_derived_from_slug_when_meta_lacks_id(tmp_path: Path) -> None:
    """``_coord_mid8`` cascade layer 3: when meta declares neither ``mid8`` nor a
    >=8-char ``mission_id`` but the slug embeds one, the slug-derived mid8 is used
    to compose the coord path (rather than failing closed)."""
    slug = "my-mission-01KTDVHZ"  # the canonical <slug>-<mid8> form
    _write_meta(
        tmp_path / "kitty-specs" / slug,
        coordination_branch=f"kitty/mission-{slug}-coord",
    )
    result = resolve_status_surface(tmp_path, slug)
    assert f"{slug}-coord" in str(result)


# ---------------------------------------------------------------------------
# WP09 — stored-topology adoption on the relocated read sites (randy #2 / #2062)
# ---------------------------------------------------------------------------


def test_husk_authoritative_false_for_flattened_stored_topology(tmp_path: Path) -> None:
    """``_husk_is_authoritative_surface`` is False for a coord-less stored topology.

    The now-WIRED FR-006 guard (WP08 left it dead behind a ``# MUTATION`` marker):
    a FLATTENED mission (stored ``topology: single_branch``, NO
    ``coordination_branch``) must NOT trust a lingering ``-coord`` husk — a stale
    husk would otherwise re-leak #2062 on the surface read leg.
    """
    from specify_cli.coordination.surface_resolver import (
        _husk_is_authoritative_surface,
    )

    _write_meta(
        tmp_path / "kitty-specs" / "flat-mission-01KTDVHZ",
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        topology="single_branch",
    )
    assert _husk_is_authoritative_surface(tmp_path, "flat-mission-01KTDVHZ") is False


def test_husk_authoritative_true_for_coord_stored_topology(tmp_path: Path) -> None:
    """A coord-routing stored topology keeps the husk authoritative (C-006)."""
    from specify_cli.coordination.surface_resolver import (
        _husk_is_authoritative_surface,
    )

    _write_meta(
        tmp_path / "kitty-specs" / "coord-mission-01KTDVHZ",
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        topology="coord",
        coordination_branch="kitty/mission-coord-mission-01KTDVHZ-coord",
    )
    assert _husk_is_authoritative_surface(tmp_path, "coord-mission-01KTDVHZ") is True


def test_husk_authoritative_true_for_unbackfilled_legacy(tmp_path: Path) -> None:
    """No stored ``topology`` (un-backfilled legacy) → husk stays authoritative."""
    from specify_cli.coordination.surface_resolver import (
        _husk_is_authoritative_surface,
    )

    _write_meta(
        tmp_path / "kitty-specs" / "legacy-mission-01KTDVHZ",
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        coordination_branch="kitty/mission-legacy-mission-01KTDVHZ-coord",
    )
    assert _husk_is_authoritative_surface(tmp_path, "legacy-mission-01KTDVHZ") is True


def test_effective_surface_topology_prefers_stored_over_relay() -> None:
    """``_effective_surface_topology`` READS the stored shape, not a coord relay.

    randy #2: even when the value-read ``coord_branch`` is present (which the
    retired ``classify_topology(coord_branch, …)`` relay would classify COORD),
    the STORED ``single_branch`` topology disposes — proving the relocated read
    site reads the stored value rather than relaying the coord-value inference.
    """
    from mission_runtime import MissionTopology

    from specify_cli.coordination.surface_resolver import (
        _effective_surface_topology,
    )

    meta = {"topology": "single_branch", "coordination_branch": "kitty/stale-coord"}
    result = _effective_surface_topology(None, meta, coord_branch="kitty/stale-coord")
    assert result is MissionTopology.SINGLE_BRANCH


def test_effective_surface_topology_relays_only_when_unbackfilled() -> None:
    """No stored ``topology`` ⇒ derive ONCE from the coord-value (legacy fallback)."""
    from mission_runtime import MissionTopology

    from specify_cli.coordination.surface_resolver import (
        _effective_surface_topology,
    )

    meta: dict[str, object] = {"coordination_branch": "kitty/real-coord"}
    result = _effective_surface_topology(None, meta, coord_branch="kitty/real-coord")
    assert result is MissionTopology.COORD


def test_effective_surface_topology_threaded_wins() -> None:
    """A caller-threaded topology takes precedence over both stored and relay."""
    from mission_runtime import MissionTopology

    from specify_cli.coordination.surface_resolver import (
        _effective_surface_topology,
    )

    meta = {"topology": "coord", "coordination_branch": "kitty/c"}
    result = _effective_surface_topology(MissionTopology.LANES, meta, coord_branch="kitty/c")
    assert result is MissionTopology.LANES
