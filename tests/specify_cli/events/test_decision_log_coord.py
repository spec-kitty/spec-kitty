"""Unit tests for WP03: DecisionGitLog coord-aware worktree routing.

T017: DecisionGitLog._decisions_file rooted under worktree_root (not repo_root).
T018: _wrap_with_decision_git_log passes coord worktree path when it exists.
T019: _wrap_with_decision_git_log falls back to repo_root when coord absent.
T020: DecisionGitLog.safe_commit uses worktree_root as worktree_root arg.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.events.decision_log import DecisionGitLog
from runtime.next._internal_runtime.events import NullEmitter, RuntimeEventEmitter

pytestmark = [pytest.mark.unit, pytest.mark.fast]
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_coord_meta(repo_root: Path, slug: str) -> Path:
    """Write a coord-topology ``meta.json`` so ``ensure_topology`` classifies COORD.

    WP03 routes coord decisions by the STORED topology (FR-004), so a coord-routing
    test must declare the topology in meta (via ``coordination_branch`` →
    ``ensure_topology`` derives/persists ``topology: coord``) rather than relying on
    a disk-stat. Anchored on the canonical PRIMARY mission dir.
    """
    mission_dir = repo_root / "kitty-specs" / slug
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        '{"coordination_branch":"kitty/mission-' + slug + '","mission_id":"01KT3YBDABCDEFGHIJKLMNOP"}',
        encoding="utf-8",
    )
    return mission_dir


def _make_log(
    repo_root: Path,
    worktree_root: Path,
    *,
    mission_slug: str = "my-mission",
    destination_ref: str = "kitty/mission-my-mission",
    inner: Any | None = None,
    mission_dir: Path | None = None,
) -> DecisionGitLog:
    return DecisionGitLog(
        repo_root=repo_root,
        worktree_root=worktree_root,
        destination_ref=destination_ref,
        mission_slug=mission_slug,
        mission_dir=mission_dir if mission_dir is not None else worktree_root / "kitty-specs" / mission_slug,
        inner=inner or NullEmitter(),
    )


def _fake_write_location(*, checkout_root: Path, path: Path) -> Any:
    """Build a minimal ``WriteLocation`` double for a patched ``placement_seam``.

    coord-artifact-single-home-01M3V4BE WP09 (T051): ``_wrap_with_decision_git_log``'s
    coord-routing arm now resolves ``worktree_root``/``mission_dir`` through
    ``placement_seam(...).write_dir(DECISION_LOG)`` instead of the retired
    on-disk ``.exists()`` ladder (``CoordinationWorkspace.resolve`` /
    ``_resolve_owned_coordination_workspace``). Tests that used to fake the
    ladder by creating a coord directory on disk now patch
    ``mission_runtime.placement_seam`` (the wrapper imports it at call time) to return this double.
    """
    from mission_runtime import Establishment, WriteLocation
    from mission_runtime.artifacts import TopologySurface

    return WriteLocation(
        path=path,
        surface_root=checkout_root,
        surface=TopologySurface.COORD,
        coord_state_before=None,
        establishment=Establishment.NONE,
        seed=None,
    )


def _patch_placement_seam(location: Any) -> Any:
    """Patch ``mission_runtime.placement_seam`` so ``write_dir`` returns *location*.

    ``_wrap_with_decision_git_log`` is not the only ``placement_seam`` caller
    reached in these tests -- ``_mission_routes_through_coordination`` (called
    EARLIER in the same function, to classify topology) ALSO calls
    ``placement_seam(...).read_dir(PRIMARY_METADATA)``. The fake delegates
    every OTHER method to a REAL seam built from the same args, so topology
    classification is unaffected -- only ``write_dir`` is faked.
    """
    from mission_runtime import placement_seam as _real_placement_seam

    class _FakeSeam:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._real = _real_placement_seam(*args, **kwargs)

        def write_dir(self, kind: Any) -> Any:  # noqa: ARG002 - kind unused by the fake
            return location

        def __getattr__(self, name: str) -> Any:
            return getattr(self._real, name)

    # ``_wrap_with_decision_git_log`` imports ``placement_seam`` function-locally
    # from ``mission_runtime`` (cold-import discipline) -- patch the SOURCE
    # module, not ``runtime.next.runtime_bridge`` (which never binds the name
    # at module scope).
    return patch(
        "mission_runtime.placement_seam",
        side_effect=_FakeSeam,
    )


# ---------------------------------------------------------------------------
# T017: _decisions_file is rooted under worktree_root
# ---------------------------------------------------------------------------


class TestDecisionsFileLocation:
    """Verify decisions.events.jsonl is written under worktree_root (T017)."""

    def test_decisions_file_under_worktree_root(self, tmp_path: Path) -> None:
        """When worktree_root != repo_root, decisions_file uses worktree_root."""
        repo_root = tmp_path / "repo"
        worktree_root = tmp_path / "coord-worktree"
        repo_root.mkdir()
        worktree_root.mkdir()
        slug = "my-mission"

        log = _make_log(repo_root, worktree_root, mission_slug=slug)

        expected = worktree_root / "kitty-specs" / slug / "decisions.events.jsonl"
        assert log._decisions_file == expected

    def test_decisions_file_not_under_repo_root_when_coord_present(self, tmp_path: Path) -> None:
        """decisions_file must NOT point into repo_root when coord worktree is set."""
        repo_root = tmp_path / "repo"
        worktree_root = tmp_path / "coord-worktree"
        repo_root.mkdir()
        worktree_root.mkdir()
        slug = "my-mission"

        log = _make_log(repo_root, worktree_root, mission_slug=slug)

        wrong_path = repo_root / "kitty-specs" / slug / "decisions.events.jsonl"
        assert log._decisions_file != wrong_path

    def test_decisions_file_repo_root_when_no_coord(self, tmp_path: Path) -> None:
        """When worktree_root == repo_root (legacy/no coord), file is in repo_root."""
        slug = "legacy-mission"
        log = _make_log(tmp_path, tmp_path, mission_slug=slug)

        expected = tmp_path / "kitty-specs" / slug / "decisions.events.jsonl"
        assert log._decisions_file == expected


# ---------------------------------------------------------------------------
# T018: _wrap_with_decision_git_log coord routing
# ---------------------------------------------------------------------------


class TestWrapWithDecisionGitLogCoordRouting:
    """_wrap_with_decision_git_log selects worktree_root based on coord existence (T018, T019)."""

    def test_coord_worktree_used_when_exists(self, tmp_path: Path) -> None:
        """Coord-routing topology ⇒ ``worktree_root``/``mission_dir`` come from
        ``write_dir(DECISION_LOG)`` (T018, corrected by WP09 T051).

        coord-artifact-single-home-01M3V4BE WP09: the on-disk ``.exists()``
        materialization ladder (``CoordinationWorkspace.resolve`` /
        ``_resolve_owned_coordination_workspace``) is retired — the
        coord-routing arm now resolves THROUGH the write-location accessor.
        This asserts ``_wrap_with_decision_git_log`` threads
        ``WriteLocation.surface_root``/``.path`` into ``DecisionGitLog``
        unchanged.
        """
        from runtime.next.runtime_bridge_decision_log import _wrap_with_decision_git_log

        slug = "my-feature-01KT3YBD"
        base_slug = "my-feature"

        # Stored topology authority (WP02): declare coord-branch topology in meta
        # so ``ensure_topology`` classifies/persists COORD — the routing signal.
        _write_coord_meta(tmp_path, slug)
        coord_path = tmp_path / ".worktrees" / f"{base_slug}-01KT3YBD-coord"
        coord_mission_dir = coord_path / "kitty-specs" / slug
        location = _fake_write_location(checkout_root=coord_path, path=coord_mission_dir)

        inner = MagicMock(spec=RuntimeEventEmitter)

        captured: dict[str, Any] = {}

        def _fake_decision_git_log(
            repo_root: Path,
            worktree_root: Path,
            destination_ref: str,
            mission_slug: str,
            *,
            mission_dir: Path,
            inner: Any,
            mission_id: str = "",
            target: Any = None,
        ) -> Any:
            captured["worktree_root"] = worktree_root
            captured["mission_dir"] = mission_dir
            return inner  # return inner unchanged for simplicity

        with (
            patch(
                "specify_cli.events.decision_log.DecisionGitLog",
                side_effect=_fake_decision_git_log,
            ),
            patch(
                "runtime.next.runtime_bridge_identity._resolve_coordination_branch",
                return_value="kitty/mission-my-feature-01KT3YBD",
            ),
            patch(
                "runtime.next.runtime_bridge_identity._resolve_mission_ulid",
                return_value="01KT3YBDABCDEFGHIJKLMNOP",
            ),
            _patch_placement_seam(location),
        ):
            _wrap_with_decision_git_log(inner, slug, tmp_path)

        assert "worktree_root" in captured
        assert captured["worktree_root"] == coord_path
        assert captured["mission_dir"] == coord_mission_dir

    def test_resolve_mission_ulid_reads_primary_not_coord_worktree(self, tmp_path: Path) -> None:
        """#2091 red-first: identity (``mission_id``) is persisted ONLY on the
        primary checkout's meta.json. Under coordination topology the coord-aware
        resolver returns the materialized coord worktree, whose mission dir has NO
        meta.json — so reading identity there loses the ULID, ``_declared_id``
        becomes ``None``, ``resolve_mid8`` declines to ``""`` (its #1918 contract),
        and ``_wrap_with_decision_git_log`` composes the malformed
        ``kitty/mission-<slug>-`` branch. ``_resolve_mission_ulid`` must read the
        PRIMARY surface and return the ULID. RED on the unfixed code (returns the
        slug), GREEN once the identity read is primary-anchored.
        """
        from runtime.next.runtime_bridge_identity import _resolve_mission_ulid

        slug = "my-feature-01KT3YBD"
        mid8 = "01KT3YBD"
        base_slug = "my-feature"
        ulid = "01KT3YBDABCDEFGHIJKLMNOP"

        # mission_id persisted on the PRIMARY checkout's meta.json only.
        _write_coord_meta(tmp_path, slug)
        # Materialized coord worktree whose mission dir has NO meta.json — the
        # surface the coord-aware resolver would (wrongly) read identity from.
        coord_mission_dir = tmp_path / ".worktrees" / f"{base_slug}-{mid8}-coord" / "kitty-specs" / slug
        coord_mission_dir.mkdir(parents=True)
        assert not (coord_mission_dir / "meta.json").exists()

        assert _resolve_mission_ulid(slug, tmp_path) == ulid, (
            "identity read must anchor on the primary checkout's meta.json, not the coord worktree (which has no meta.json) — #2091"
        )

    def test_repo_root_used_when_coord_absent(self, tmp_path: Path) -> None:
        """When coord worktree does not exist, repo_root becomes worktree_root (T019)."""
        from runtime.next.runtime_bridge_decision_log import _wrap_with_decision_git_log

        slug = "my-feature-01KT3YBD"
        inner = MagicMock(spec=RuntimeEventEmitter)

        captured: dict[str, Any] = {}

        def _fake_decision_git_log(
            repo_root: Path,
            worktree_root: Path,
            destination_ref: str,
            mission_slug: str,
            *,
            mission_dir: Path,
            inner: Any,
            mission_id: str = "",
            target: Any = None,
        ) -> Any:
            captured["worktree_root"] = worktree_root
            captured["mission_dir"] = mission_dir
            return inner

        with (
            patch(
                "specify_cli.events.decision_log.DecisionGitLog",
                side_effect=_fake_decision_git_log,
            ),
            patch(
                "runtime.next.runtime_bridge_identity._resolve_coordination_branch",
                return_value="kitty/mission-my-feature-01KT3YBD",
            ),
            patch(
                "runtime.next.runtime_bridge_identity._resolve_mission_ulid",
                return_value="01KT3YBDABCDEFGHIJKLMNOP",
            ),
        ):
            _wrap_with_decision_git_log(inner, slug, tmp_path)

        assert "worktree_root" in captured
        assert captured["worktree_root"] == tmp_path
        # C-008: the coord-less arm composes the same dir DecisionGitLog used
        # to compose itself.
        assert captured["mission_dir"] == tmp_path / "kitty-specs" / slug

    def test_declared_coord_topology_missing_worktree_resolves_coord_worktree(self, tmp_path: Path) -> None:
        """Modern missions create/use coord worktree instead of dropping audit.

        coord-artifact-single-home-01M3V4BE WP09 (T051): the materialization
        now happens INSIDE ``write_dir`` -- this patches ``placement_seam``
        directly rather than the retired ``CoordinationWorkspace.resolve``
        call this arm no longer makes.
        """
        from runtime.next.runtime_bridge_decision_log import _wrap_with_decision_git_log

        repo_root = tmp_path / "repo"
        slug = "my-feature-01KT3YBD"
        mission_dir = repo_root / "kitty-specs" / slug
        mission_dir.mkdir(parents=True)
        (mission_dir / "meta.json").write_text(
            '{"coordination_branch":"kitty/mission-my-feature-01KT3YBD","mission_id":"01KT3YBDABCDEFGHIJKLMNOP"}',
            encoding="utf-8",
        )
        inner = MagicMock(spec=RuntimeEventEmitter)
        captured: dict[str, Any] = {}

        coord_root = repo_root / ".worktrees" / "my-feature-01KT3YBD-coord"
        coord_mission_dir = coord_root / "kitty-specs" / slug
        location = _fake_write_location(checkout_root=coord_root, path=coord_mission_dir)

        def _fake_decision_git_log(
            repo_root: Path,
            worktree_root: Path,
            destination_ref: str,
            mission_slug: str,
            *,
            mission_dir: Path,
            inner: Any,
            mission_id: str = "",
            target: Any = None,
        ) -> Any:
            captured["worktree_root"] = worktree_root
            captured["mission_dir"] = mission_dir
            return inner

        with (
            patch(
                "specify_cli.events.decision_log.DecisionGitLog",
                side_effect=_fake_decision_git_log,
            ),
            _patch_placement_seam(location),
        ):
            wrapped = _wrap_with_decision_git_log(inner, slug, repo_root)

        assert wrapped is inner
        assert captured["worktree_root"] == coord_root
        assert captured["mission_dir"] == coord_mission_dir

    def test_declared_coord_topology_decision_log_failure_raises(self, tmp_path: Path) -> None:
        """Modern missions fail closed when durable decision audit cannot build.

        coord-artifact-single-home-01M3V4BE WP09 (T051): the failure now
        originates from ``write_dir`` (the one accessor this arm calls)
        instead of the retired ``CoordinationWorkspace.resolve``.
        """
        from runtime.next.runtime_bridge import DecisionGitLogUnavailable
        from runtime.next.runtime_bridge_decision_log import _wrap_with_decision_git_log

        repo_root = tmp_path / "repo"
        slug = "my-feature-01KT3YBD"
        mission_dir = repo_root / "kitty-specs" / slug
        mission_dir.mkdir(parents=True)
        (mission_dir / "meta.json").write_text(
            '{"coordination_branch":"kitty/mission-my-feature-01KT3YBD","mission_id":"01KT3YBDABCDEFGHIJKLMNOP"}',
            encoding="utf-8",
        )
        inner = MagicMock(spec=RuntimeEventEmitter)

        from mission_runtime import placement_seam as _real_placement_seam

        class _FailingSeam:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self._real = _real_placement_seam(*args, **kwargs)

            def write_dir(self, kind: Any) -> Any:  # noqa: ARG002
                raise RuntimeError("coord unavailable")

            def __getattr__(self, name: str) -> Any:
                return getattr(self._real, name)

        with (
            patch(
                "mission_runtime.placement_seam",
                side_effect=_FailingSeam,
            ),
            pytest.raises(DecisionGitLogUnavailable),
        ):
            _wrap_with_decision_git_log(inner, slug, repo_root)


# ---------------------------------------------------------------------------
# WP04 (T010, C-011) — worktree_root selection PRESERVED through the .kind drain.
# Non-identity fixture: primary root != coord root, so an identity fixture (where
# the two coincide) could NOT distinguish a broken selection from a correct one.
# ---------------------------------------------------------------------------


class TestWorktreeRootPreservedThroughKindDrain:
    """C-011: dropping the vestigial ``.kind`` carrier must NOT alter worktree_root."""

    def test_coord_root_selected_over_distinct_primary_root(self, tmp_path: Path) -> None:
        """Coord-routed mission ⇒ selected worktree_root is the COORD root (non-identity).

        The C-011 risk pin. ``repo_root`` (primary) and the materialized coord
        worktree are DISTINCT directories (``primary_root != coord_root``); the
        producer must select the COORD root, not the primary. An identity fixture
        (coord == primary) would pass even if WP04's ``.kind`` drain had broken the
        selection — this non-identity fixture would NOT. Also asserts the converted
        ref-only ``decision_target`` still carries the coordination branch ref (the
        carrier conversion changed only ``.kind``, never ``.ref``).
        """
        from runtime.next.runtime_bridge_decision_log import _wrap_with_decision_git_log

        slug = "my-feature-01KT3YBD"
        mid8 = "01KT3YBD"
        base_slug = "my-feature"
        coord_branch = "kitty/mission-my-feature-01KT3YBD"

        # primary (repo) root and coord root are DISTINCT (non-identity).
        repo_root = tmp_path / "primary-checkout"
        repo_root.mkdir()
        _write_coord_meta(repo_root, slug)
        coord_root = repo_root / ".worktrees" / f"{base_slug}-{mid8}-coord"
        coord_root.mkdir(parents=True)
        assert coord_root != repo_root
        coord_mission_dir = coord_root / "kitty-specs" / slug
        location = _fake_write_location(checkout_root=coord_root, path=coord_mission_dir)

        inner = MagicMock(spec=RuntimeEventEmitter)
        captured: dict[str, Any] = {}

        def _fake_decision_git_log(
            repo_root: Path,
            worktree_root: Path,
            destination_ref: str,
            mission_slug: str,
            *,
            mission_dir: Path,
            inner: Any,
            mission_id: str = "",
            target: Any = None,
        ) -> Any:
            captured["worktree_root"] = worktree_root
            captured["mission_dir"] = mission_dir
            captured["target"] = target
            return inner

        with (
            patch(
                "specify_cli.events.decision_log.DecisionGitLog",
                side_effect=_fake_decision_git_log,
            ),
            patch(
                "runtime.next.runtime_bridge_identity._resolve_coordination_branch",
                return_value=coord_branch,
            ),
            patch(
                "runtime.next.runtime_bridge_identity._resolve_mission_ulid",
                return_value="01KT3YBDABCDEFGHIJKLMNOP",
            ),
            _patch_placement_seam(location),
        ):
            _wrap_with_decision_git_log(inner, slug, repo_root)

        # The risk pin: COORD root selected, NOT the distinct primary root.
        assert captured["worktree_root"] == coord_root
        assert captured["worktree_root"] != repo_root
        assert captured["mission_dir"] == coord_mission_dir
        # The ref-only carrier still routes to the coordination branch ref.
        assert captured["target"] is not None
        assert captured["target"].ref == coord_branch


# ---------------------------------------------------------------------------
# T020: safe_commit called with correct worktree_root
# ---------------------------------------------------------------------------


class TestDecisionGitLogSafeCommitWorktreeRoot:
    """DecisionGitLog passes worktree_root (not repo_root) to safe_commit (T020)."""

    def test_safe_commit_uses_worktree_root(self, tmp_path: Path) -> None:
        """safe_commit is called with worktree_root matching what was passed in."""
        from spec_kitty_events.mission_next import (
            DecisionInputAnsweredPayload,
            DecisionInputRequestedPayload,
            RuntimeActorIdentity,
        )

        repo_root = tmp_path / "repo"
        worktree_root = tmp_path / "coord-worktree"
        repo_root.mkdir()
        worktree_root.mkdir()

        # Pre-create decisions directory
        decisions_dir = worktree_root / "kitty-specs" / "my-mission"
        decisions_dir.mkdir(parents=True)

        log = _make_log(repo_root, worktree_root)

        actor = RuntimeActorIdentity(actor_id="test-agent", actor_type="llm", provider=None, model=None, tool=None)
        req_payload = DecisionInputRequestedPayload(
            run_id="run-001",
            decision_id="dec-001",
            step_id="implement",
            question="Should I proceed?",
            actor=actor,
            input_key=None,
        )
        ans_payload = DecisionInputAnsweredPayload(
            run_id="run-001",
            decision_id="dec-001",
            answer="yes",
            actor=actor,
        )

        safe_commit_calls: list[dict[str, Any]] = []

        def _mock_safe_commit(**kwargs: Any) -> bool:
            safe_commit_calls.append(kwargs)
            return True

        with patch("specify_cli.events.decision_log.safe_commit", side_effect=_mock_safe_commit):
            log.emit_decision_input_requested(req_payload)
            log.emit_decision_input_answered(ans_payload)

        # Exactly one safe_commit call (for the answered event)
        assert len(safe_commit_calls) == 1
        call = safe_commit_calls[0]
        assert call["worktree_root"] == worktree_root
        assert call["repo_root"] == repo_root

    def test_safe_commit_not_called_for_request_only(self, tmp_path: Path) -> None:
        """safe_commit is NOT called for DecisionInputRequested (only for Answered)."""
        from spec_kitty_events.mission_next import (
            DecisionInputRequestedPayload,
            RuntimeActorIdentity,
        )

        decisions_dir = tmp_path / "kitty-specs" / "my-mission"
        decisions_dir.mkdir(parents=True)

        log = _make_log(tmp_path, tmp_path)

        actor = RuntimeActorIdentity(actor_id="test-agent", actor_type="llm", provider=None, model=None, tool=None)
        req_payload = DecisionInputRequestedPayload(
            run_id="run-001",
            decision_id="dec-001",
            step_id="implement",
            question="Should I proceed?",
            actor=actor,
            input_key=None,
        )

        safe_commit_calls: list[Any] = []

        with patch("specify_cli.events.decision_log.safe_commit", side_effect=lambda **kw: safe_commit_calls.append(kw) or True):
            log.emit_decision_input_requested(req_payload)

        assert len(safe_commit_calls) == 0


# ---------------------------------------------------------------------------
# T021: NFR-004 — _wrap_with_decision_git_log never raises when coord absent
# ---------------------------------------------------------------------------


class TestNFR004FallbackNoRaise:
    """NFR-004: _wrap_with_decision_git_log must not abort when coord worktree absent (T021)."""

    def test_decision_log_construction_does_not_abort_when_coord_worktree_missing(self, tmp_path: Path) -> None:
        """_wrap_with_decision_git_log never raises when coord worktree absent (NFR-004)."""
        from runtime.next.runtime_bridge_decision_log import _wrap_with_decision_git_log

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        mission_slug = "my-mission-ABCD1234"
        # Do NOT create the coord worktree — simulates pre-init or legacy mission

        mock_emitter = MagicMock(spec=RuntimeEventEmitter)

        # Must not raise under any circumstance
        try:
            wrapped = _wrap_with_decision_git_log(mock_emitter, mission_slug, repo_root)
        except Exception as exc:
            pytest.fail(f"_wrap_with_decision_git_log raised {type(exc).__name__} when coord worktree was absent — violates NFR-004: {exc}")

        # Wrapped result is usable (either DecisionGitLog or plain emitter)
        assert wrapped is not None
