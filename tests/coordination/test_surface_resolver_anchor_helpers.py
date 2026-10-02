"""Focused tests for the private helpers T006 extracted from
``resolve_status_surface_with_anchor`` (campsite-clean WP01, IC-01).

This WP changes no behaviour: the broader resolver contract stays covered by
``test_surface_resolver_coord_empty_warning.py`` /
``test_surface_resolver_collapse.py`` / ``test_surface_resolver_solo_coord_primary.py``.
These tests call the two extracted private helpers directly, so the behaviour
they hold is pinned at the unit level even before a caller reaches them.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from mission_runtime import MissionTopology

from specify_cli.coordination.surface_resolver import (
    ResolvedStatusSurface,
    _empty_coord_surface,
    _meta_unreadable_fallback,
)

_LOGGER_NAME = "specify_cli.coordination.surface_resolver"


class TestEmptyCoordSurface:
    """``_empty_coord_surface`` — T006 extraction of the ``CoordState.EMPTY`` branch.

    Lane-a regression fix (coord-artifact-single-home-01M3V4BE, declared
    out-of-map, owner WP01): WP04 widened ``_empty_coord_surface`` with four
    required keyword-only arguments (``repo_root``, ``coord_branch``,
    ``mission_id``, ``for_write``) for the post-fix trailer probe (D4) but did
    not update these call sites. All three tests below now pass the widened
    signature with ``for_write=True`` — the write-path arm, which the
    function's own docstring documents as skipping the git trailer probe
    entirely (``if not for_write: ... coord_branch_is_post_fix(...)``) — so
    ``repo_root`` / ``coord_branch`` / ``mission_id`` are structurally inert
    placeholders for these three calls and no real git repo is needed.
    """

    def test_lanes_with_coord_warns_and_returns_primary(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Today's behaviour (unchanged): the warning fires for
        ``LANES_WITH_COORD`` unconditionally — a mission whose lane worktrees
        were provisioned to write into the coord root, so an empty one is
        genuinely unexpected regardless of post-fix-ness (the router ORs
        ``post_fix or effective_topology is LANES_WITH_COORD``). ``for_write=
        True`` is chosen deliberately: it skips the post-fix probe, and the
        outcome is identical either way for this topology, so the simpler,
        I/O-free call proves the same invariant without a real git fixture.
        """
        feature_dir = tmp_path / "kitty-specs" / "demo-mission"
        composed_coord_dir = tmp_path / ".worktrees" / "demo-mission-coord" / "kitty-specs" / "demo-mission"

        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            surface = _empty_coord_surface(
                feature_dir,
                composed_coord_dir,
                "demo-mission",
                MissionTopology.LANES_WITH_COORD,
                repo_root=tmp_path,
                coord_branch="kitty/mission-demo-mission-ABCDEF01",
                mission_id="ABCDEF01" + "0" * 18,
                for_write=True,
            )

        assert isinstance(surface, ResolvedStatusSurface)
        # The returned surface is the PRIMARY dir, never the coord dir.
        assert surface.surface_path == feature_dir / "status.events.jsonl"
        assert surface.primary_anchor == feature_dir

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING and r.name == _LOGGER_NAME]
        assert len(warnings) == 1, "expected exactly one WARNING-level record from the surface resolver logger"

    def test_solo_coord_stays_quiet_and_returns_primary(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Today's behaviour (unchanged): a solo (no-lanes) coord mission's empty
        coord root is the EXPECTED steady state pre-first-write — no warning.

        ``for_write=True`` is the honest way to pin "pre-first-write": it is
        literally the write-path arm (the one a caller takes before any write
        has ever landed), and it skips the post-fix probe outright, so
        ``post_fix`` stays ``False`` — the same answer a real pre-fix (no
        seed trailer yet) repository would give the read-path probe, without
        needing one.
        """
        feature_dir = tmp_path / "kitty-specs" / "solo-mission"
        composed_coord_dir = tmp_path / ".worktrees" / "solo-mission-coord" / "kitty-specs" / "solo-mission"

        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            surface = _empty_coord_surface(
                feature_dir,
                composed_coord_dir,
                "solo-mission",
                MissionTopology.COORD,
                repo_root=tmp_path,
                coord_branch="kitty/mission-solo-mission-ABCDEF01",
                mission_id="ABCDEF01" + "0" * 18,
                for_write=True,
            )

        assert surface.surface_path == feature_dir / "status.events.jsonl"
        assert surface.primary_anchor == feature_dir
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING and r.name == _LOGGER_NAME]
        assert warnings == [], "solo coord-topology empty fallback must stay quiet"

    def test_does_no_io(self, tmp_path: Path) -> None:
        """Purity of the WRITE-PATH call (``for_write=True``): no directory or file is created.

        This is NOT a blanket claim that ``_empty_coord_surface`` never does
        I/O: the READ-PATH call (``for_write=False``) DOES perform one git
        subprocess call (the post-fix trailer probe,
        ``coord_branch_is_post_fix``) as part of its documented D4 behaviour
        — see ``test_probes_git_only_when_not_for_write`` below, which
        documents that boundary honestly instead of leaving this test's name
        implying a stronger guarantee than the widened helper actually gives.
        """
        feature_dir = tmp_path / "kitty-specs" / "pure-mission"
        composed_coord_dir = tmp_path / ".worktrees" / "pure-mission-coord" / "kitty-specs" / "pure-mission"

        _empty_coord_surface(
            feature_dir,
            composed_coord_dir,
            "pure-mission",
            MissionTopology.COORD,
            repo_root=tmp_path,
            coord_branch="kitty/mission-pure-mission-ABCDEF01",
            mission_id="ABCDEF01" + "0" * 18,
            for_write=True,
        )

        assert not feature_dir.exists()
        assert not composed_coord_dir.exists()

    def test_probes_git_only_when_not_for_write(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Honest I/O boundary (WP04 widening, D4): the READ-PATH call
        (``for_write=False``) performs exactly ONE call to the post-fix
        trailer probe (``coord_branch_is_post_fix``); the WRITE-PATH call
        (``for_write=True``, the one ``test_does_no_io`` exercises) never
        calls it at all. Mocked rather than run against a real repo: the
        point under test is WHETHER the probe fires, not its git internals
        (those are ``coord_seed``'s own test surface).
        """
        from specify_cli.coordination import coord_seed

        calls: list[tuple[Path, str, str]] = []

        def _fake_post_fix(repo_root: Path, coordination_branch: str, mission_id: str) -> bool:
            calls.append((repo_root, coordination_branch, mission_id))
            return False

        monkeypatch.setattr(coord_seed, "coord_branch_is_post_fix", _fake_post_fix)

        feature_dir = tmp_path / "kitty-specs" / "probe-mission"
        composed_coord_dir = tmp_path / ".worktrees" / "probe-mission-coord" / "kitty-specs" / "probe-mission"
        coord_branch = "kitty/mission-probe-mission-ABCDEF01"
        mission_id = "ABCDEF01" + "0" * 18

        _empty_coord_surface(
            feature_dir,
            composed_coord_dir,
            "probe-mission",
            MissionTopology.COORD,
            repo_root=tmp_path,
            coord_branch=coord_branch,
            mission_id=mission_id,
            for_write=False,
        )
        assert calls == [(tmp_path, coord_branch, mission_id)], "for_write=False must probe post-fix-ness exactly once"

        calls.clear()
        _empty_coord_surface(
            feature_dir,
            composed_coord_dir,
            "probe-mission",
            MissionTopology.COORD,
            repo_root=tmp_path,
            coord_branch=coord_branch,
            mission_id=mission_id,
            for_write=True,
        )
        assert calls == [], "for_write=True must never probe post-fix-ness"


class TestMetaUnreadableFallback:
    """``_meta_unreadable_fallback`` — T006 extraction of the second ``meta is None`` arm."""

    def test_prefers_primary_dir_when_it_exists(self, tmp_path: Path) -> None:
        primary_dir = tmp_path / "kitty-specs" / "demo-mission"
        primary_dir.mkdir(parents=True)
        feature_dir = tmp_path / ".worktrees" / "demo-mission-coord" / "kitty-specs" / "demo-mission"

        surface = _meta_unreadable_fallback(primary_dir, feature_dir, "demo-mission")

        assert surface.primary_anchor == primary_dir
        assert surface.surface_path == primary_dir / "status.events.jsonl"

    def test_falls_back_to_feature_dir_when_primary_missing(self, tmp_path: Path) -> None:
        primary_dir = tmp_path / "kitty-specs" / "demo-mission"
        feature_dir = tmp_path / ".worktrees" / "demo-mission-coord" / "kitty-specs" / "demo-mission"
        feature_dir.mkdir(parents=True)

        surface = _meta_unreadable_fallback(primary_dir, feature_dir, "demo-mission")

        assert surface.primary_anchor == feature_dir
        assert surface.surface_path == feature_dir / "status.events.jsonl"

    def test_raises_file_not_found_when_neither_exists(self, tmp_path: Path) -> None:
        primary_dir = tmp_path / "kitty-specs" / "demo-mission"
        feature_dir = tmp_path / ".worktrees" / "demo-mission-coord" / "kitty-specs" / "demo-mission"

        with pytest.raises(FileNotFoundError, match="demo-mission"):
            _meta_unreadable_fallback(primary_dir, feature_dir, "demo-mission")
