"""Unit tests for MissionStatus aggregate (WP04, FR-015–FR-023, T025).

Covers:
- MissionStatus.load() for legacy and coord topologies
- Fail-closed behavior when coord worktree is declared but missing
- MissionStatus.claim() returns correct ActiveWPStatus
- ActiveWPStatus field contract
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mission_dir(root: Path, slug: str) -> Path:
    """Create a minimal legacy mission directory in tmp_path."""
    mission_dir = root / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    return mission_dir


def _write_meta(
    mission_dir: Path,
    mission_id: str | None = None,
    coordination_branch: str | None = None,
    topology: str | None = None,
) -> None:
    """Write a meta.json to a mission directory."""
    meta: dict = {}
    if mission_id is not None:
        meta["mission_id"] = mission_id
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    if topology is not None:
        meta["topology"] = topology
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _write_events_file(mission_dir: Path, events: list[dict] | None = None) -> None:
    """Create a status.events.jsonl file with given events (or empty)."""
    lines = ""
    if events:
        lines = "\n".join(json.dumps(e) for e in events)
    (mission_dir / "status.events.jsonl").write_text(lines, encoding="utf-8")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _make_git_repo(path: Path) -> Path:
    repo = path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True, text=True)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / ".kittify").mkdir()
    (repo / "README.md").write_text("test repo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return repo


def _make_event(
    mission_slug: str,
    wp_id: str,
    from_lane: str,
    to_lane: str,
    event_id: str = "01HXYZ0123456789ABCDEFGHXX",
) -> dict:
    return {
        "event_id": event_id,
        "mission_slug": mission_slug,
        "wp_id": wp_id,
        "from_lane": from_lane,
        "to_lane": to_lane,
        "at": "2026-06-01T12:00:00+00:00",
        "actor": "claude",
        "force": False,
        "execution_mode": "worktree",
        "evidence": None,
        "reason": None,
        "review_ref": None,
        "feature_slug": mission_slug,
    }


# ---------------------------------------------------------------------------
# T025.1 — MissionStatus.load() with legacy mission (no coord branch)
# ---------------------------------------------------------------------------


class TestLoadLegacyMission:
    def test_topology_is_legacy_when_no_meta(self, tmp_path: Path) -> None:
        slug = "034-test-feature"
        mission_dir = _make_mission_dir(tmp_path, slug)

        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)

        assert ms.topology == "legacy"
        assert ms.read_dir == mission_dir
        assert ms.mission_id is None
        assert ms.mid8 == ""

    def test_topology_is_legacy_when_meta_has_no_coord_branch(self, tmp_path: Path) -> None:
        slug = "034-test-feature"
        mission_dir = _make_mission_dir(tmp_path, slug)
        _write_meta(mission_dir, mission_id="01KT6HVH12345678901234AB")

        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)

        assert ms.topology == "legacy"
        assert ms.read_dir == mission_dir
        assert ms.mission_id == "01KT6HVH12345678901234AB"
        assert ms.mid8 == "01KT6HVH"

    def test_topology_is_legacy_when_no_coord_worktree_and_no_coord_declared(self, tmp_path: Path) -> None:
        slug = "test-feature"
        _make_mission_dir(tmp_path, slug)

        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)

        assert ms.topology == "legacy"
        assert ms.mission_slug == slug


# ---------------------------------------------------------------------------
# T025.2 — MissionStatus.load() with coordination topology
# ---------------------------------------------------------------------------


class TestLoadCoordMission:
    def test_topology_is_coordination_when_coord_worktree_exists(self, tmp_path: Path) -> None:
        """When the coord worktree exists on disk, topology should be 'coordination'.

        WP03 R3 authority ("name proposes, authority disposes"): topology is
        disposed by the git worktree REGISTRY, not by path shape. A coord
        feature dir created with a bare ``mkdir`` is an unregistered husk that
        now classifies as ``legacy`` (and a declared-but-absent coord branch
        raises ``CoordinationBranchDeleted``). To exercise the genuine
        COORDINATION (R1) path the fixture must materialize a REAL registered
        coord worktree on a REAL coordination branch — mirroring the canonical
        R1 fixture in ``tests/specify_cli/coordination/
        test_worktree_topology_decision_table.py::test_r1_*``.
        """
        repo = _make_git_repo(tmp_path)
        slug = "test-feature"
        mission_id = "01TESTKITTY12345678901234"
        mid8 = mission_id[:8]
        coord_branch = f"kitty/mission-{slug}-{mid8}"

        # Create primary mission dir with coord-branch declaration
        primary_mission_dir = _make_mission_dir(repo, slug)
        _write_meta(primary_mission_dir, mission_id=mission_id, coordination_branch=coord_branch)

        # Materialize a REAL, registered coord worktree on the coord branch so
        # the registry-based topology authority disposes COORDINATION.
        # Path: .worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/
        coord_dir_name = f"{slug}-{mid8}"
        coord_worktree_root = repo / ".worktrees" / f"{coord_dir_name}-coord"
        subprocess.run(
            [
                "git", "-C", str(repo), "worktree", "add", "-q",
                "-b", coord_branch, str(coord_worktree_root),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        coord_mission_dir = coord_worktree_root / "kitty-specs" / coord_dir_name
        coord_mission_dir.mkdir(parents=True)
        _write_meta(coord_mission_dir, mission_id=mission_id, coordination_branch=coord_branch)

        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=repo, mission_slug=slug)

        assert ms.topology == "coordination"
        assert ms.read_dir == coord_mission_dir
        assert ms.mission_id == mission_id
        assert ms.mid8 == mid8


# ---------------------------------------------------------------------------
# T025.3 — Transitional coord topology
# ---------------------------------------------------------------------------


class TestLoadCoordUnavailableFailsClosed:
    def test_uses_primary_when_coord_declared_but_worktree_not_materialized(self, tmp_path: Path) -> None:
        """coord branch declared but no worktree root yet → primary is authoritative."""
        slug = "test-feature"
        mission_id = "01TESTKITTY12345678901234"

        primary_mission_dir = _make_mission_dir(tmp_path, slug)
        _write_meta(
            primary_mission_dir,
            mission_id=mission_id,
            coordination_branch=f"kitty/mission-{slug}-{mission_id[:8]}",
        )

        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)

        assert ms.topology == "legacy"
        assert ms.read_dir == primary_mission_dir
        assert ms.coordination_branch == f"kitty/mission-{slug}-{mission_id[:8]}"

    def test_bare_modern_slug_uses_composed_primary_dir_before_coord_materialized(
        self, tmp_path: Path
    ) -> None:
        """Bare slug mirrors read resolvers: primary dir is ``<slug>-<mid8>``."""
        bare_slug = "demo-feature"
        mission_id = "01ABCDEF1234567890123456"
        mid8 = mission_id[:8]
        full_slug = f"{bare_slug}-{mid8}"
        primary_mission_dir = _make_mission_dir(tmp_path, full_slug)
        _write_meta(
            primary_mission_dir,
            mission_id=mission_id,
            coordination_branch=f"kitty/mission-{full_slug}",
        )

        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=bare_slug)

        assert ms.read_dir == primary_mission_dir
        assert ms.mid8 == mid8

    def test_coord_worktree_materialized_but_missing_mission_dir_resolves_primary(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """WP04 Option B (#1716 / FR-003): coord-empty → aggregate inherits PRIMARY.

        Previously this hard-failed with ``CoordAuthorityUnavailable``. Under the
        operator-decided Option B the canonical surface returns the primary
        checkout, and the aggregate inherits that PRIMARY
        with NO aggregate code change (``_resolve_read_dir`` delegates to the
        surface). The fallback is observable (the surface logs at
        ``logging.WARNING``); the inverted assertion proves coord-empty no longer
        reaches the aggregate's ``CoordAuthorityUnavailable`` seam.
        """
        mission_id = "01STALEKITTY1234567890AB"
        mid8 = mission_id[:8]
        # Canonical post-WP03 dir name carries the mid8 suffix; load by the same
        # handle so the aggregate resolves the coord-empty topology (not legacy).
        full_slug = f"stale-feature-{mid8}"

        primary_dir = _make_mission_dir(tmp_path, full_slug)
        # WP08 (#2533) split the coord-empty warning by stored topology: a coord
        # mission WITH lanes still warns on an unexpected empty coord (the
        # TRUE-POSITIVE this test pins); a solo (no-lanes) COORD mission routes to
        # primary silently. Declare the with-lanes shape so the warning still fires.
        _write_meta(
            primary_dir,
            mission_id=mission_id,
            coordination_branch=f"kitty/mission-{full_slug}",
            topology="lanes_with_coord",
        )
        _write_events_file(primary_dir, [
            _make_event(full_slug, "WP01", "planned", "claimed"),
        ])
        # Root exists, but kitty-specs/<slug>-<mid8>/ is absent (coord-empty).
        (tmp_path / ".worktrees" / f"{full_slug}-coord").mkdir(parents=True)

        from specify_cli.status.aggregate import MissionStatus

        with caplog.at_level(
            logging.WARNING, logger="specify_cli.coordination.surface_resolver"
        ):
            ms = MissionStatus.load(repo_root=tmp_path, mission_slug=full_slug)

        # Option B: the aggregate inherits the PRIMARY checkout (no hard-fail).
        assert ms.read_dir.resolve() == primary_dir.resolve()
        # #7276 WP05 deleted the loud empty-coordination fallback: the read door
        # (``status/read_surface.py::resolve_status_read``) now decides an empty
        # coordination worktree deterministically (the committed coordination ref,
        # or the repository root checkout while that ref holds no log yet), so no
        # fallback WARNING is emitted any more (#7282).
        assert not any(
            r.name == "specify_cli.coordination.surface_resolver"
            and r.levelno == logging.WARNING
            for r in caplog.records
        )

    def test_corrupt_meta_fails_closed_instead_of_legacy_fallback(self, tmp_path: Path) -> None:
        """Existing but corrupt meta.json cannot degrade to a primary-checkout read."""
        slug = "corrupt-meta-feature"
        mission_dir = _make_mission_dir(tmp_path, slug)
        (mission_dir / "meta.json").write_text(
            '{"mission_id":"01CORRUPT12345678901234","coordination_branch":',
            encoding="utf-8",
        )
        _write_events_file(mission_dir, [
            _make_event(slug, "WP01", "planned", "claimed"),
        ])

        from specify_cli.status.aggregate import MissionMetadataUnavailable, MissionStatus

        with pytest.raises(MissionMetadataUnavailable) as exc_info:
            MissionStatus.load(repo_root=tmp_path, mission_slug=slug)

        exc = exc_info.value
        assert exc.mission_slug == slug
        assert exc.primary_candidate == mission_dir

    def test_non_dict_meta_fails_closed_instead_of_legacy_fallback(self, tmp_path: Path) -> None:
        """Existing meta.json must be an object before topology can be trusted."""
        slug = "array-meta-feature"
        mission_dir = _make_mission_dir(tmp_path, slug)
        (mission_dir / "meta.json").write_text("[]", encoding="utf-8")

        from specify_cli.status.aggregate import MissionMetadataUnavailable, MissionStatus

        with pytest.raises(MissionMetadataUnavailable, match="Expected JSON object"):
            MissionStatus.load(repo_root=tmp_path, mission_slug=slug)

    def test_non_string_mission_id_fails_closed(self, tmp_path: Path) -> None:
        """Malformed mission_id cannot be laundered into a legacy read."""
        slug = "bad-mission-id-feature"
        mission_dir = _make_mission_dir(tmp_path, slug)
        (mission_dir / "meta.json").write_text(
            '{"mission_id": ["01BAD"], "coordination_branch": "kitty/mission-bad"}',
            encoding="utf-8",
        )

        from specify_cli.status.aggregate import MissionMetadataUnavailable, MissionStatus

        with pytest.raises(MissionMetadataUnavailable, match="mission_id must be string"):
            MissionStatus.load(repo_root=tmp_path, mission_slug=slug)

    def test_non_string_coordination_branch_fails_closed(self, tmp_path: Path) -> None:
        """Malformed coordination_branch cannot degrade to primary checkout."""
        slug = "bad-coord-branch-feature"
        mission_dir = _make_mission_dir(tmp_path, slug)
        (mission_dir / "meta.json").write_text(
            '{"mission_id": "01BADCOORD12345678901234", "coordination_branch": 123}',
            encoding="utf-8",
        )

        from specify_cli.status.aggregate import MissionMetadataUnavailable, MissionStatus

        with pytest.raises(MissionMetadataUnavailable, match="coordination_branch must be string"):
            MissionStatus.load(repo_root=tmp_path, mission_slug=slug)


# ---------------------------------------------------------------------------
# T025.4 — MissionStatus.claim() returns correct lane
# ---------------------------------------------------------------------------


class TestClaimReturnsCorrectLane:
    def test_claim_returns_active_wp_status_for_known_wp(self, tmp_path: Path) -> None:
        slug = "034-claim-test"
        mission_dir = _make_mission_dir(tmp_path, slug)
        _write_events_file(mission_dir, [
            _make_event(slug, "WP01", "planned", "claimed", event_id="01HXYZ0123456789ABCDEFGH01"),
            _make_event(slug, "WP01", "claimed", "in_progress", event_id="01HXYZ0123456789ABCDEFGH02"),
        ])

        from specify_cli.status import Lane
        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)
        wp_status = ms.claim("WP01")

        assert wp_status.wp_id == "WP01"
        assert wp_status.current_lane == Lane.IN_PROGRESS
        assert wp_status.last_event is not None
        assert wp_status.last_event.wp_id == "WP01"

    def test_claim_current_lane_matches_last_event_to_lane(self, tmp_path: Path) -> None:
        slug = "034-lane-verify"
        mission_dir = _make_mission_dir(tmp_path, slug)
        _write_events_file(mission_dir, [
            _make_event(slug, "WP02", "planned", "claimed", event_id="01HXYZ0123456789ABCDEFGH10"),
        ])

        from specify_cli.status import Lane
        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)
        wp_status = ms.claim("WP02")

        assert wp_status.current_lane == Lane.CLAIMED

    def test_claim_no_events_returns_uninitialized_string(self, tmp_path: Path) -> None:
        """When a WP has no events, get_wp_lane returns 'uninitialized'."""
        slug = "034-empty-wp"
        mission_dir = _make_mission_dir(tmp_path, slug)
        _write_events_file(mission_dir, [])  # empty events

        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)
        wp_status = ms.claim("WP99")

        # 'uninitialized' is the sentinel returned by get_wp_lane for unknown WPs
        assert str(wp_status.current_lane) == "uninitialized"
        assert wp_status.last_event is None


# ---------------------------------------------------------------------------
# T025.5 — ActiveWPStatus field contract
# ---------------------------------------------------------------------------


class TestActiveWPStatusFields:
    def test_active_wp_status_is_frozen(self) -> None:
        from specify_cli.status import Lane
        from specify_cli.status.aggregate import ActiveWPStatus

        aws = ActiveWPStatus(wp_id="WP01", current_lane=Lane.PLANNED, last_event=None)
        with pytest.raises((AttributeError, TypeError)):
            aws.wp_id = "WP02"  # type: ignore[misc]

    def test_active_wp_status_has_required_fields(self) -> None:
        from specify_cli.status import Lane
        from specify_cli.status.aggregate import ActiveWPStatus

        aws = ActiveWPStatus(wp_id="WP01", current_lane=Lane.IN_PROGRESS, last_event=None)
        assert aws.wp_id == "WP01"
        assert aws.current_lane == Lane.IN_PROGRESS
        assert aws.last_event is None

    def test_mission_status_is_frozen(self, tmp_path: Path) -> None:
        slug = "034-frozen-test"
        _make_mission_dir(tmp_path, slug)

        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)
        with pytest.raises((AttributeError, TypeError)):
            ms.mission_slug = "modified"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# T025.6 — Importability from status façade
# ---------------------------------------------------------------------------


class TestStatusFacadeExports:
    def test_mission_status_importable_from_status(self) -> None:
        from specify_cli.status import MissionStatus  # noqa: F401

    def test_active_wp_status_importable_from_status(self) -> None:
        from specify_cli.status import ActiveWPStatus  # noqa: F401

    def test_coord_authority_unavailable_importable_from_status(self) -> None:
        from specify_cli.status import CoordAuthorityUnavailable  # noqa: F401

    def test_mission_metadata_unavailable_importable_from_status(self) -> None:
        from specify_cli.status import MissionMetadataUnavailable  # noqa: F401

    def test_all_three_in_dunder_all(self) -> None:
        import specify_cli.status as status_mod

        assert "MissionStatus" in status_mod.__all__
        assert "ActiveWPStatus" in status_mod.__all__
        assert "CoordAuthorityUnavailable" in status_mod.__all__
        assert "MissionMetadataUnavailable" in status_mod.__all__


# ---------------------------------------------------------------------------
# FR-019 / FR-020 — MissionStatus.transition() and .save() unit tests
# ---------------------------------------------------------------------------


class TestTransitionHappyPath:
    def test_resolve_current_lane_maps_uninitialized_to_genesis(self, tmp_path: Path) -> None:
        """Unseeded transactional reads resolve to genesis, not planned (#1775).

        An unseeded WP cannot be claimed; resolving to genesis lets the FSM reject
        genesis -> claimed instead of silently treating the WP as planned.
        """
        from specify_cli.status import TransitionRequest
        from specify_cli.status.aggregate import MissionStatus
        from specify_cli.status.models import CurrentWpState, Lane

        ms = MissionStatus(
            mission_slug="034-lane-fallback",
            mission_id=None,
            mid8="",
            topology="legacy",
            read_dir=tmp_path,
            repo_root=tmp_path,
        )
        request = TransitionRequest(
            wp_id="WP01",
            to_lane="claimed",
            actor="claude",
            feature_dir=tmp_path,
            mission_slug=ms.mission_slug,
        )

        from_lane, current_actor = ms._resolve_current_lane(
            request=request,
            read_current_wp_state_transactional=lambda **_: CurrentWpState(Lane.UNINITIALIZED, "claude", None),
            lane_unseeded=Lane.GENESIS,
        )

        assert from_lane == "genesis"
        assert current_actor == "claude"

    def test_transition_validates_then_applies(self, tmp_path: Path) -> None:
        """transition() rejects illegal transitions before calling BookkeepingTransaction."""
        slug = "034-transition-test"
        mission_dir = _make_mission_dir(tmp_path, slug)
        _write_events_file(mission_dir, [
            _make_event(slug, "WP01", "planned", "claimed", event_id="01HXYZ0123456789ABCDEFGH01"),
        ])

        from specify_cli.status import TransitionRequest
        from specify_cli.status.emit import TransitionError
        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)

        # planned → claimed → in_progress is valid from 'claimed'
        # But planned → approved is illegal
        bad_request = TransitionRequest(
            wp_id="WP01",
            to_lane="approved",
            actor="claude",
            feature_dir=ms.read_dir,
            mission_slug=slug,
        )
        with pytest.raises(TransitionError) as exc_info:
            ms.transition(bad_request)
        # Must raise — must NOT silently succeed or call BookkeepingTransaction
        assert exc_info.value is not None

    def test_transition_preserves_illegal_move_message(self, tmp_path: Path) -> None:
        """transition() preserves validator diagnostics for illegal moves."""
        slug = "034-invalid-transition"
        mission_dir = _make_mission_dir(tmp_path, slug)
        _write_events_file(mission_dir, [
            _make_event(slug, "WP01", "planned", "claimed", event_id="01HXYZ0123456789ABCDEFGH20"),
        ])

        from specify_cli.status import TransitionRequest
        from specify_cli.status.emit import TransitionError
        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)

        # 'done' is only reachable via merge — transitioning directly is illegal
        bad_request = TransitionRequest(
            wp_id="WP01",
            to_lane="done",
            actor="claude",
            feature_dir=ms.read_dir,
            mission_slug=slug,
        )
        with pytest.raises(TransitionError, match="Illegal transition: claimed -> done"):
            ms.transition(bad_request)

    def test_transition_coerces_unparseable_lanes_in_error_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """transition() preserves unknown-lane diagnostics instead of crashing."""
        slug = "034-coerce-bogus-lanes"
        mission_dir = _make_mission_dir(tmp_path, slug)
        _write_events_file(mission_dir, [
            _make_event(slug, "WP01", "planned", "claimed", event_id="01HXYZ0123456789ABCDEFGH21"),
        ])

        import specify_cli.status as status_pkg
        from specify_cli.status import TransitionRequest
        from specify_cli.status.emit import TransitionError
        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)
        # Force the resolved from-lane to a non-Lane string so the from-lane
        # coercion hits the ValueError -> Lane.PLANNED fallback.
        monkeypatch.setattr(status_pkg, "get_wp_lane", lambda *a, **k: "uninitialized")

        bad_request = TransitionRequest(
            wp_id="WP01",
            to_lane="not-a-real-lane",  # unparseable to-lane -> ValueError fallback too
            actor="claude",
            feature_dir=ms.read_dir,
            mission_slug=slug,
        )
        with pytest.raises(TransitionError, match="Unknown lane"):
            ms.transition(bad_request)

    def test_transition_preserves_guard_error_for_missing_done_evidence(
        self, tmp_path: Path
    ) -> None:
        """Guard failures keep transactional TransitionError text."""
        slug = "034-done-missing-evidence"
        mission_dir = _make_mission_dir(tmp_path, slug)
        _write_events_file(mission_dir, [
            _make_event(slug, "WP01", "planned", "claimed", event_id="01HXYZ0123456789ABCDEFGH26"),
            _make_event(slug, "WP01", "claimed", "in_progress", event_id="01HXYZ0123456789ABCDEFGH27"),
            _make_event(slug, "WP01", "in_progress", "for_review", event_id="01HXYZ0123456789ABCDEFGH28"),
            _make_event(slug, "WP01", "for_review", "approved", event_id="01HXYZ0123456789ABCDEFGH29"),
        ])

        from specify_cli.status import TransitionRequest
        from specify_cli.status.aggregate import MissionStatus
        from specify_cli.status.emit import TransitionError

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)
        with pytest.raises(TransitionError, match="requires evidence"):
            ms.transition(
                TransitionRequest(
                    wp_id="WP01",
                    to_lane="done",
                    actor="claude",
                    feature_dir=ms.read_dir,
                    mission_slug=slug,
                )
            )

    def test_transition_preserves_legacy_alias_noop(self, tmp_path: Path) -> None:
        """Legacy alias self-transitions remain no-ops through the aggregate."""
        slug = "034-doing-noop"
        mission_dir = _make_mission_dir(tmp_path, slug)
        _write_events_file(mission_dir, [
            _make_event(slug, "WP01", "planned", "claimed", event_id="01HXYZ0123456789ABCDEFGH30"),
            _make_event(slug, "WP01", "claimed", "in_progress", event_id="01HXYZ0123456789ABCDEFGH31"),
        ])
        before = (mission_dir / "status.events.jsonl").read_text(encoding="utf-8")

        from specify_cli.status import TransitionRequest
        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)
        event = ms.transition(
            TransitionRequest(
                wp_id="WP01",
                to_lane="doing",
                actor="claude",
                feature_dir=ms.read_dir,
                mission_slug=slug,
            )
        )

        assert str(event.from_lane) == "in_progress"
        assert str(event.to_lane) == "in_progress"
        assert (mission_dir / "status.events.jsonl").read_text(encoding="utf-8") == before

    def test_transition_validates_against_coord_branch_when_worktree_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pre-validation reads coord branch state when no coord worktree exists."""
        slug = "coord-ahead"
        mission_id = "01ABCDEF1234567890123456"
        mid8 = mission_id[:8]
        coord_branch = f"kitty/mission-{slug}-{mid8}"
        repo = _make_git_repo(tmp_path)

        primary_dir = _make_mission_dir(repo, slug)
        _write_meta(primary_dir, mission_id=mission_id, coordination_branch=coord_branch)
        tasks_dir = primary_dir / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01-test.md").write_text(
            "---\nwork_package_id: WP01\ndependencies: []\nsubtasks: []\n---\n# WP01\n",
            encoding="utf-8",
        )
        _write_events_file(primary_dir, [
            _make_event(slug, "WP01", "planned", "claimed", event_id="01HXYZ0123456789ABCDEFGH32"),
        ])
        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "primary claimed")
        _git(repo, "checkout", "-b", coord_branch)
        coord_dir = repo / "kitty-specs" / f"{slug}-{mid8}"
        coord_dir.mkdir(parents=True)
        _write_events_file(coord_dir, [
            _make_event(slug, "WP01", "planned", "claimed", event_id="01HXYZ0123456789ABCDEFGH33"),
            _make_event(slug, "WP01", "claimed", "in_progress", event_id="01HXYZ0123456789ABCDEFGH34"),
        ])
        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "coord in progress")
        _git(repo, "checkout", "main")

        from specify_cli.status import TransitionRequest
        from specify_cli.status.aggregate import MissionStatus
        import specify_cli.coordination.status_transition as status_transition

        marker = object()
        monkeypatch.setattr(
            status_transition,
            "emit_status_transition_transactional",
            lambda *args, **kwargs: marker,
        )

        ms = MissionStatus.load(repo_root=repo, mission_slug=slug)
        assert ms.read_dir == primary_dir
        result = ms.transition(
            TransitionRequest(
                wp_id="WP01",
                to_lane="for_review",
                actor="claude",
                feature_dir=ms.read_dir,
                mission_slug=slug,
                subtasks_complete=True,
                implementation_evidence_present=True,
                repo_root=repo,
            )
        )

        assert result is marker

    def test_transition_rejects_empty_event_log_as_genesis(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty canonical log is unseeded; claim must not bypass genesis.

        WP06 (``fsm-write-path-integrity-01M1TZV6``): the refusal is raised by
        the status-owned pipeline INSIDE the transactional door (validation
        runs once, in-lock), so the door is entered exactly once and nothing
        is persisted.
        """
        slug = "034-empty-log-transition"
        mission_dir = _make_mission_dir(tmp_path, slug)
        _write_events_file(mission_dir, [])
        before = (mission_dir / "status.events.jsonl").read_text(encoding="utf-8")

        from specify_cli.status import TransitionRequest
        from specify_cli.status.emit import TransitionError
        from specify_cli.status.aggregate import MissionStatus
        import specify_cli.coordination.status_transition as status_transition

        entered: list[str] = []
        real_transactional = status_transition.emit_status_transition_transactional

        def _spy_transactional(request, **kwargs):  # noqa: ANN001, ANN003
            entered.append(request.wp_id)
            return real_transactional(request, **kwargs)

        monkeypatch.setattr(
            status_transition,
            "emit_status_transition_transactional",
            _spy_transactional,
        )

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)
        with pytest.raises(TransitionError, match="Illegal transition: genesis -> claimed"):
            ms.transition(
                TransitionRequest(
                    wp_id="WP01",
                    to_lane="claimed",
                    actor="claude",
                    feature_dir=ms.read_dir,
                    mission_slug=slug,
                )
            )
        assert entered == ["WP01"]
        assert (mission_dir / "status.events.jsonl").read_text(encoding="utf-8") == before

    def test_transition_rejects_unknown_wp_in_nonempty_log_as_genesis(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unknown WP rows are unseeded; claim must not bypass genesis.

        The refusal comes from the pipeline inside the transactional door
        (WP06); the log is left untouched.
        """
        slug = "034-unknown-wp-transition"
        mission_dir = _make_mission_dir(tmp_path, slug)
        _write_events_file(mission_dir, [
            _make_event(slug, "WP01", "planned", "claimed", event_id="01HXYZ0123456789ABCDEFGH22"),
        ])
        before = (mission_dir / "status.events.jsonl").read_text(encoding="utf-8")

        from specify_cli.status import TransitionRequest
        from specify_cli.status.emit import TransitionError
        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)
        with pytest.raises(TransitionError, match="Illegal transition: genesis -> claimed"):
            ms.transition(
                TransitionRequest(
                    wp_id="WP99",
                    to_lane="claimed",
                    actor="claude",
                    feature_dir=ms.read_dir,
                    mission_slug=slug,
                )
            )
        assert (mission_dir / "status.events.jsonl").read_text(encoding="utf-8") == before

    def test_transition_infers_workspace_context_for_claimed_to_in_progress(
        self, tmp_path: Path
    ) -> None:
        """The pipeline (not the aggregate) defaults the workspace context (#946).

        ``claimed -> in_progress`` requires a workspace context; the request
        carries none, and the emit still succeeds because the status-owned
        pipeline applies the ``<execution_mode>:<root>`` default inside the
        shell (WP06: the aggregate's own inference was deleted).
        """
        slug = "034-claimed-to-progress"
        mission_dir = _make_mission_dir(tmp_path, slug)
        _write_events_file(mission_dir, [
            _make_event(slug, "WP01", "planned", "claimed", event_id="01HXYZ0123456789ABCDEFGH23"),
        ])

        from specify_cli.status import TransitionRequest
        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)
        event = ms.transition(
            TransitionRequest(
                wp_id="WP01",
                to_lane="in_progress",
                actor="claude",
                feature_dir=ms.read_dir,
                mission_slug=slug,
            )
        )

        assert str(event.to_lane) == "in_progress"
        assert event.event_id in (mission_dir / "status.events.jsonl").read_text(encoding="utf-8")

    def test_transition_infers_for_review_guards(
        self, tmp_path: Path
    ) -> None:
        """The pipeline (not the aggregate) infers the two review gates.

        Neither ``subtasks_complete`` nor ``implementation_evidence_present``
        is supplied; the emit succeeds because the status-owned pipeline
        infers both inside the shell from the authored roster + the event
        log (WP06: the aggregate's own inference was deleted).
        """
        slug = "034-progress-to-review"
        mission_dir = _make_mission_dir(tmp_path, slug)
        _write_events_file(mission_dir, [
            _make_event(slug, "WP01", "planned", "claimed", event_id="01HXYZ0123456789ABCDEFGH24"),
            _make_event(slug, "WP01", "claimed", "in_progress", event_id="01HXYZ0123456789ABCDEFGH25"),
        ])
        (mission_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        tasks_dir = mission_dir / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01-test.md").write_text(
            "---\nwork_package_id: WP01\ndependencies: []\nsubtasks: [T001]\n---\n# WP01\n",
            encoding="utf-8",
        )
        from specify_cli.status import (
            InnerStateChanged,
            Status,
            WPInnerStateDelta,
        )
        from specify_cli.status._unsafe import append_annotations_atomic_verified

        append_annotations_atomic_verified(
            mission_dir,
            [
                InnerStateChanged(
                    event_id="01H33333333333333333333333",
                    wp_id="WP01",
                    at="2026-06-01T13:00:00+00:00",
                    actor="claude",
                    delta=WPInnerStateDelta(subtasks={"T001": Status.DONE}),
                )
            ],
        )

        from specify_cli.status import TransitionRequest
        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)
        event = ms.transition(
            TransitionRequest(
                wp_id="WP01",
                to_lane="for_review",
                actor="claude",
                feature_dir=ms.read_dir,
                mission_slug=slug,
            )
        )

        assert str(event.to_lane) == "for_review"
        assert event.event_id in (mission_dir / "status.events.jsonl").read_text(encoding="utf-8")


class TestSaveReturnType:
    def test_save_uses_real_bookkeeping_transaction_and_returns_commit_receipt(
        self, tmp_path: Path
    ) -> None:
        """save() commits status artifacts through the real BookkeepingTransaction."""
        slug = "save-modern"
        mission_id = "01SAVE12345678901234567890"
        mid8 = mission_id[:8]
        coord_branch = f"kitty/mission-{slug}-{mid8}"
        repo = _make_git_repo(tmp_path)

        from specify_cli.status.aggregate import MissionStatus
        from specify_cli.coordination.workspace import CoordinationWorkspace

        primary_dir = _make_mission_dir(repo, slug)
        _write_meta(primary_dir, mission_id=mission_id, coordination_branch=coord_branch)
        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "add mission meta")
        _git(repo, "branch", coord_branch)

        coord_root = CoordinationWorkspace.resolve(repo, slug, mid8)
        coord_dir = coord_root / "kitty-specs" / f"{slug}-{mid8}"
        coord_dir.mkdir(parents=True)
        events_path = coord_dir / "status.events.jsonl"
        events_path.write_text(
            json.dumps(_make_event(slug, "WP01", "planned", "claimed")) + "\n",
            encoding="utf-8",
        )

        ms = MissionStatus.load(repo_root=repo, mission_slug=slug)
        receipt = ms.save(operation="test-save")

        assert receipt.destination_ref == coord_branch
        assert receipt.commit_sha
        committed = _git(repo, "show", f"{coord_branch}:kitty-specs/{slug}-{mid8}/status.events.jsonl")
        assert "WP01" in committed

    def test_save_supports_identity_bearing_legacy_mission(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Legacy mission (mission_id, no coord branch) commits on the legacy lane.

        WP05 / FR-004 before→after rationale (the prompt flagged this as one of
        the "two tests the write-target flip touches"). Live investigation while
        implementing WP05 established that the ``destination_ref == "legacy-lane"``
        here is NOT produced by the seam WP05 adopts. ``MissionStatus.save`` →
        ``BookkeepingTransaction.acquire`` detects the legacy topology (no
        ``coordination_branch``) and **overrides** the caller-supplied
        ``destination_ref`` with ``_resolve_legacy_lane_destination`` — which
        reads ``git symbolic-ref HEAD`` of the operator's current worktree
        (``transaction.py``). That override is a ``BookkeepingTransaction``
        internal, explicitly OUT of WP05's scope (C-004: "BookkeepingTransaction
        internals are NOT changed"), and it dominates the receipt regardless of
        what ``_identity_for_request`` computes.

        The FR-004 write-target flip WP05 lands is in
        ``coordination/status_transition.py::_identity_for_request`` (routed
        through ``resolve_placement_only(...).ref``); its CWD-invariant
        ``target_branch`` behaviour is proven directly in
        ``tests/specify_cli/coordination/test_status_transition_adoption.py``
        (``test_write_target_flat_arm_yields_target_branch_not_head``) and in the
        WP01 net oracle. This legacy aggregate path therefore correctly STILL
        commits to ``legacy-lane`` post-WP05 — the value is the transaction's
        legacy-lane resolution, not the adopted ``_identity_for_request`` target.
        """
        base_slug = "save-legacy"
        mission_id = "01LEGACY45678901234567890"
        mid8 = mission_id[:8]
        slug = f"{base_slug}-{mid8}"
        repo = _make_git_repo(tmp_path)
        _git(repo, "checkout", "-b", "legacy-lane")
        monkeypatch.chdir(repo)

        mission_dir = _make_mission_dir(repo, slug)
        _write_meta(mission_dir, mission_id=mission_id)
        events_path = mission_dir / "status.events.jsonl"
        events_path.write_text(
            json.dumps(_make_event(slug, "WP02", "planned", "claimed")) + "\n",
            encoding="utf-8",
        )

        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=repo, mission_slug=slug)
        receipt = ms.save(operation="test-save-legacy")

        # Unchanged post-WP05: the legacy-topology BookkeepingTransaction override
        # (C-004 internal, NOT the adopted _identity_for_request seam) resolves the
        # destination to the operator's current lane branch.
        assert receipt.destination_ref == "legacy-lane"
        committed = _git(repo, "show", f"legacy-lane:kitty-specs/{slug}/status.events.jsonl")
        assert "WP02" in committed

    def test_save_fails_closed_without_mission_identity(self, tmp_path: Path) -> None:
        """No-meta missions cannot be persisted through BookkeepingTransaction."""
        slug = "034-save-test"
        _make_mission_dir(tmp_path, slug)

        from specify_cli.status.aggregate import MissionMetadataUnavailable, MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)
        with pytest.raises(MissionMetadataUnavailable, match="mission_id is required"):
            ms.save(operation="test-save")


# ---------------------------------------------------------------------------
# FR-007 / DIRECTIVE_010 — mission_slug ASCII allowlist guard at load()
# ---------------------------------------------------------------------------


class TestMissionSlugAllowlistGuard:
    """``MissionStatus.load()`` rejects slugs outside ``^[A-Za-z0-9_-]+$``."""

    @pytest.mark.parametrize(
        "slug",
        [
            "034-feature-name",
            "test-feature",
            "save-legacy-01ABCDEF",
            "WP_underscored",
            "ABC123",
        ],
    )
    def test_normal_ascii_slug_passes(self, tmp_path: Path, slug: str) -> None:
        """Identifier-safe ASCII slugs load without raising."""
        _make_mission_dir(tmp_path, slug)

        from specify_cli.status.aggregate import MissionStatus

        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=slug)

        assert ms.mission_slug == slug
        # The validated identifier must be pure ASCII (FR-007).
        assert ms.mission_slug.isascii()

    def test_accented_latin_slug_is_rejected(self, tmp_path: Path) -> None:
        """An accented-Latin slug (non-ASCII) is rejected at load()."""
        slug = "café-mission"
        # Defensive: the offending slug must not be ASCII, otherwise the test
        # would not exercise the .isascii() branch of the guard.
        assert not slug.isascii()

        from specify_cli.status.aggregate import InvalidMissionSlug, MissionStatus

        with pytest.raises(InvalidMissionSlug) as exc_info:
            MissionStatus.load(repo_root=tmp_path, mission_slug=slug)

        assert exc_info.value.mission_slug == slug
        assert slug in str(exc_info.value)

    @pytest.mark.parametrize(
        "slug",
        [
            "feature/with-slash",
            "feature with space",
            # "feature.with.dot" is intentionally accepted by the canonical
            # assert_safe_path_segment (interior dots are allowed per WP01
            # grammar decision — D-1 interior-dot reconciliation).
            "feature$injection",
            "..",
            "",
            "naïve",  # accented variant of a common ASCII word
            "münchen-mission",
        ],
    )
    def test_disallowed_slugs_are_rejected(self, tmp_path: Path, slug: str) -> None:
        """Path-injection and non-ASCII slugs all raise InvalidMissionSlug."""
        from specify_cli.status.aggregate import InvalidMissionSlug, MissionStatus

        with pytest.raises(InvalidMissionSlug):
            MissionStatus.load(repo_root=tmp_path, mission_slug=slug)

    def test_invalid_mission_slug_is_value_error_subclass(self) -> None:
        """InvalidMissionSlug is a ValueError so existing handlers can catch it."""
        from specify_cli.status.aggregate import InvalidMissionSlug

        assert issubclass(InvalidMissionSlug, ValueError)

    def test_invalid_mission_slug_importable_from_status_aggregate(self) -> None:
        from specify_cli.status.aggregate import InvalidMissionSlug  # noqa: F401

    def test_invalid_mission_slug_in_aggregate_dunder_all(self) -> None:
        import specify_cli.status.aggregate as aggregate_mod

        assert "InvalidMissionSlug" in aggregate_mod.__all__
