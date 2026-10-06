"""Tests for WP04: canonical fail-closed mission-identity contract in runtime_bridge.

Covers T014 (red-first: flat-path persists ULID; empty-mid8 fails closed):
  - _resolve_mission_ulid returns None (not slug) when meta has no mission_id
  - _resolve_mission_ulid returns ULID when meta carries mission_id
  - _wrap_with_decision_git_log for flat mission uses ULID from meta (not slug)
  - _wrap_with_decision_git_log for coord mission with no ULID fails closed

2026-08-04 (PR #3175 landing fold, marker-correctness gates): the WP08
(#3155) corrupt-meta regression class that used to live in this file drove
real ``git init``/``git commit`` via ``subprocess`` (see
``TestMissionRoutesThroughCoordinationCorruptMeta`` in
``test_runtime_bridge_identity_git_repo.py``) while every test *left* in this
module only exercises ``unittest.mock.patch`` — no subprocess, no git. Two
``tests/architectural/test_pytest_marker_correctness.py`` gates fired on the
mixed file: Rule 1 (a subprocess/git user must carry ``git_repo``) and Rule 2
(a ``fast``-marked file must NOT invoke subprocess). Splitting the corrupt-meta
class into its own git_repo-marked file lets this module keep the accurate
``fast`` marker for the genuinely mock-only, sub-second tests below, per the
Rule 2 fix-hint's explicit split option (docs/context/testing-taxonomy.md →
'Fast'/'Git Repo').
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from runtime.next.runtime_bridge import (
    DecisionGitLogUnavailable,
    _wrap_with_decision_git_log,
)
from runtime.next.runtime_bridge_identity import _resolve_mission_ulid
from runtime.next._internal_runtime.events import NullEmitter

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ULID = "01KWDABC1234567890ABCDEFGH"
_SLUG = "my-mission-01KWDABC"


def _meta_dir(tmp_path: Path, slug: str) -> Path:
    """Create and return kitty-specs/<slug>/ in tmp_path."""
    d = tmp_path / "kitty-specs" / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_meta(feature_dir: Path, *, mission_id: str | None = None) -> None:
    """Write a minimal meta.json, optionally with mission_id."""
    meta: dict[str, object] = {
        "mission_slug": feature_dir.name,
        "mission_type": "software-dev",
        "mission_number": None,
    }
    if mission_id is not None:
        meta["mission_id"] = mission_id
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


# ---------------------------------------------------------------------------
# T014 (a) — _resolve_mission_ulid returns ULID or None via SSOT
# ---------------------------------------------------------------------------


class TestResolveMissionUlid:
    """Unit tests for _resolve_mission_ulid against the SSOT contract."""

    def test_returns_none_when_no_mission_id_in_meta(self, tmp_path: Path) -> None:
        """When meta.json exists but has no mission_id, return None (not the slug).

        RED on pre-fix code: the old implementation returns mission_slug as fallback.
        """
        feature_dir = _meta_dir(tmp_path, _SLUG)
        _write_meta(feature_dir)  # no mission_id written

        with patch(
            "runtime.next.runtime_bridge_identity._primary_runtime_feature_dir",
            return_value=feature_dir,
        ):
            result = _resolve_mission_ulid(_SLUG, tmp_path)

        assert result is None, (
            f"Expected None (fail-closed, no slug fallback) but got {result!r}"
        )

    def test_returns_none_when_meta_json_missing(self, tmp_path: Path) -> None:
        """When meta.json is absent entirely, return None (fail-closed).

        RED on pre-fix code: the old implementation returns mission_slug as fallback.
        """
        feature_dir = _meta_dir(tmp_path, _SLUG)
        # No meta.json written

        with patch(
            "runtime.next.runtime_bridge_identity._primary_runtime_feature_dir",
            return_value=feature_dir,
        ):
            result = _resolve_mission_ulid(_SLUG, tmp_path)

        assert result is None, (
            f"Expected None when meta.json absent but got {result!r}"
        )

    def test_returns_ulid_when_mission_id_in_meta(self, tmp_path: Path) -> None:
        """When meta.json has a mission_id, return it (regression guard).

        GREEN on both pre-fix and post-fix code — preserves happy-path behaviour.
        """
        feature_dir = _meta_dir(tmp_path, _SLUG)
        _write_meta(feature_dir, mission_id=_ULID)

        with patch(
            "runtime.next.runtime_bridge_identity._primary_runtime_feature_dir",
            return_value=feature_dir,
        ):
            result = _resolve_mission_ulid(_SLUG, tmp_path)

        assert result == _ULID, (
            f"Expected ULID {_ULID!r} but got {result!r}"
        )
        assert result != _SLUG, "ULID must not equal the slug"


# ---------------------------------------------------------------------------
# T014 (b) — empty-mid8 composition fails closed for coord topology
# ---------------------------------------------------------------------------


class TestWrapWithDecisionGitLogIdentityContract:
    """Integration tests for _wrap_with_decision_git_log identity sourcing."""

    def test_flat_mission_with_ulid_passes_ulid_to_decision_git_log(
        self, tmp_path: Path
    ) -> None:
        """Flat mission with ULID in meta: DecisionGitLog receives ULID (regression).

        GREEN on both pre-fix and post-fix code — regression guard for the happy path.
        """
        feature_dir = _meta_dir(tmp_path, _SLUG)
        _write_meta(feature_dir, mission_id=_ULID)

        emitter = NullEmitter()
        with (
            patch(
                "runtime.next.runtime_bridge_identity._primary_runtime_feature_dir",
                return_value=feature_dir,
            ),
            patch(
                "runtime.next.runtime_bridge._mission_routes_through_coordination",
                return_value=False,
            ),
            patch(
                "runtime.next.runtime_bridge_identity._resolve_coordination_branch",
                return_value="kitty/mission-my-mission-01KWDABC-lane-a",
            ),
        ):
            result = _wrap_with_decision_git_log(emitter, _SLUG, tmp_path)

        from specify_cli.events.decision_log import DecisionGitLog

        assert isinstance(result, DecisionGitLog), (
            "Expected DecisionGitLog wrapper for flat mission with ULID"
        )
        assert result._mission_id == _ULID, (  # type: ignore[attr-defined]
            f"DecisionGitLog must use ULID {_ULID!r}, got {result._mission_id!r}"
        )

    def test_flat_mission_without_ulid_mission_id_is_none_not_slug(
        self, tmp_path: Path
    ) -> None:
        """Flat mission with no ULID in meta: DecisionGitLog._mission_id is None.

        RED on pre-fix code: the old _resolve_mission_ulid returns slug, which
        flows into DecisionGitLog._mission_id = slug (persisting slug into a
        mission_id field, violating FR-004).
        """
        feature_dir = _meta_dir(tmp_path, _SLUG)
        _write_meta(feature_dir)  # no mission_id

        emitter = NullEmitter()
        with (
            patch(
                "runtime.next.runtime_bridge_identity._primary_runtime_feature_dir",
                return_value=feature_dir,
            ),
            patch(
                "runtime.next.runtime_bridge._mission_routes_through_coordination",
                return_value=False,
            ),
            patch(
                "runtime.next.runtime_bridge_identity._resolve_coordination_branch",
                return_value="kitty/mission-my-mission-lane-a",
            ),
        ):
            result = _wrap_with_decision_git_log(emitter, _SLUG, tmp_path)

        from specify_cli.events.decision_log import DecisionGitLog

        assert isinstance(result, DecisionGitLog), (
            "Expected DecisionGitLog wrapper for flat mission"
        )
        assert result._mission_id is None, (  # type: ignore[attr-defined]
            f"DecisionGitLog._mission_id must be None (not slug) when no ULID "
            f"available; got {result._mission_id!r}"
        )

    def test_coord_mission_without_ulid_fails_closed(self, tmp_path: Path) -> None:
        """Coord-routing mission with no ULID raises DecisionGitLogUnavailable.

        GREEN on both pre-fix and post-fix: the existing mid8 guard already
        fires when no ULID can be resolved. This test ensures the guard is
        NOT regressed by the WP04 changes.
        """
        feature_dir = _meta_dir(tmp_path, _SLUG)
        _write_meta(feature_dir)  # no mission_id → mid8 is ""

        emitter = NullEmitter()
        with (
            patch(
                "runtime.next.runtime_bridge_identity._primary_runtime_feature_dir",
                return_value=feature_dir,
            ),
            patch(
                "runtime.next.runtime_bridge._mission_routes_through_coordination",
                return_value=True,  # coord topology
            ),
            patch(
                "runtime.next.runtime_bridge_identity._resolve_coordination_branch",
                return_value="kitty/mission-my-mission-01KWDABC-lane-a",
            ),
            pytest.raises(DecisionGitLogUnavailable),
        ):
            _wrap_with_decision_git_log(emitter, _SLUG, tmp_path)
