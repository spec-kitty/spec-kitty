"""Fail-closed traversal tests for the derived-view write sinks.

``StatusSnapshot.mission_slug`` is copied verbatim from UNTRUSTED event-record
content (``StatusEvent.from_dict`` → ``reduce``). Three sinks join that slug into
a path and ``mkdir``/write under ``.kittify/derived/``:

- ``progress.generate_progress_json``
- ``lifecycle.generate_lifecycle_json``
- ``views.write_derived_views``

A crafted event ``{"mission_slug": "../../../../evil"}`` must NOT escape the
derived root. The single chokepoint is ``reducer.reduce`` (via
``core.paths.safe_mission_slug``), which downgrades an unsafe slug to ``""`` so
every sink's existing ``slug or feature_dir.name`` fallback engages.

Each sink test asserts:
  1. the traversal target dir does NOT exist after the call, and
  2. output lands under the trusted ``feature_dir.name`` path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.core.paths import MissionMetaReadError
from specify_cli.status.lifecycle import generate_lifecycle_json
from specify_cli.status.lifecycle import _fallback_created_at, _last_merge_marker_at
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.progress import generate_progress_json
from specify_cli.status.reducer import reduce
from specify_cli.status.store import EVENTS_FILENAME
from tests._support.status_seed import seed_status_event
from specify_cli.status.views import write_derived_views

pytestmark = pytest.mark.fast

# Escapes the derived_dir boundary (one level up) while staying inside the test
# sandbox so the assertion never depends on a shared system tmp directory.
# The security property under test is "does not escape derived_dir", which this
# exercises exactly; a deeper "../../../../" slug resolves the same way through
# the same unguarded mkdir but would write to a shared location.
_HOSTILE_SLUG = "../evil"
_FEATURE_NAME = "034-trusted-feature"


def _hostile_event(slug: str = _HOSTILE_SLUG) -> StatusEvent:
    """Build a StatusEvent whose mission_slug is an attacker traversal string."""
    return StatusEvent(
        event_id="01HXYZ0123456789ABCDEFGHJK",
        mission_slug=slug,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-02-08T12:00:00Z",
        actor="claude-opus",
        force=False,
        execution_mode="worktree",
        mission_id=None,
    )


def _seed_hostile_feature_dir(tmp_path: Path) -> Path:
    """Create a feature dir with an event log carrying a hostile mission_slug."""
    feature_dir = tmp_path / "kitty-specs" / _FEATURE_NAME
    feature_dir.mkdir(parents=True)
    seed_status_event(feature_dir, _hostile_event())
    return feature_dir


# --- direct seam unit test (reduce) ---


def test_reduce_downgrades_hostile_mission_slug_to_empty() -> None:
    """The reduce seam sanitizes an unsafe event slug to '' (fail-closed source)."""
    snapshot = reduce([_hostile_event()])

    # Downgraded to empty so every sink falls back to the trusted feature_dir.name.
    assert snapshot.mission_slug == ""


def test_reduce_preserves_a_safe_mission_slug() -> None:
    """A well-formed slug is preserved untouched (guard does not over-reject)."""
    snapshot = reduce([_hostile_event(slug="034-real-mission")])

    assert snapshot.mission_slug == "034-real-mission"


# --- sink integration tests ---


def test_generate_progress_json_fail_closed_on_traversal_slug(tmp_path: Path) -> None:
    feature_dir = _seed_hostile_feature_dir(tmp_path)
    derived_dir = tmp_path / "derived"
    derived_dir.mkdir()

    generate_progress_json(feature_dir, derived_dir)

    # Traversal target must NOT exist; output lands under the trusted name.
    assert not (derived_dir / _HOSTILE_SLUG).resolve().exists()
    assert (derived_dir / _FEATURE_NAME / "progress.json").exists()


def test_generate_lifecycle_json_fail_closed_on_traversal_slug(tmp_path: Path) -> None:
    feature_dir = _seed_hostile_feature_dir(tmp_path)
    derived_dir = tmp_path / "derived"
    derived_dir.mkdir()

    generate_lifecycle_json(feature_dir, derived_dir)

    assert not (derived_dir / _HOSTILE_SLUG).resolve().exists()
    assert (derived_dir / _FEATURE_NAME / "lifecycle.json").exists()


def test_write_derived_views_fail_closed_on_traversal_slug(tmp_path: Path) -> None:
    feature_dir = _seed_hostile_feature_dir(tmp_path)
    derived_dir = tmp_path / "derived"
    derived_dir.mkdir()

    write_derived_views(feature_dir, derived_dir)

    assert not (derived_dir / _HOSTILE_SLUG).resolve().exists()
    assert (derived_dir / _FEATURE_NAME / "status.json").exists()


def test_event_log_round_trips_through_read_with_hostile_slug(tmp_path: Path) -> None:
    """Sanity: the hostile slug survives read_events onto the event (not pre-filtered).

    This proves the sink tests above are exercising a real attack path: the slug
    is NOT scrubbed at read time — it is carried verbatim onto the StatusEvent and
    only sanitized at the reduce seam.
    """
    feature_dir = _seed_hostile_feature_dir(tmp_path)
    raw = (feature_dir / EVENTS_FILENAME).read_text(encoding="utf-8")
    assert json.loads(raw.splitlines()[0])["mission_slug"] == _HOSTILE_SLUG


# --- FR-009 / IC-05: meta.json write-path bypass (empty-event-slug fallback) ---
#
# The reduce seam above only sanitizes the EVENT slug. When the event slug is
# empty, ``generate_lifecycle_json``/``materialize_if_stale`` fall back to
# ``resolve_mission_identity`` which reads ``meta.json``'s ``mission_slug``. Before
# the WP02 chokepoint that meta read was UNVALIDATED, so a hostile meta slug joined
# ``derived/<slug>/`` and ``mkdir``'d outside the derived root — a LIVE write-path
# traversal that #2036 did not close.

# Escapes the derived_dir boundary (one level up) while staying inside the test
# sandbox — same rationale as ``_HOSTILE_SLUG`` above. A deeper "../../../../"
# slug resolves through the same unguarded ``mkdir`` but to a SHARED system tmp
# location that pollutes across test runs and makes the absolute-path
# assertion flaky; ``../evil`` exercises the identical security property
# ("does not escape derived_dir") in a collision-free, sandbox-local way.
_META_HOSTILE_SLUG = "../evil"


def _seed_meta_only_hostile_feature_dir(tmp_path: Path) -> Path:
    """Feature dir whose meta.json slug is hostile and whose event slug is empty.

    The event log carries an EMPTY ``mission_slug`` so the snapshot slug reduces to
    ``""`` and the sinks must fall back to ``resolve_mission_identity`` (the
    meta.json read this WP guards).
    """
    feature_dir = tmp_path / "kitty-specs" / _FEATURE_NAME
    feature_dir.mkdir(parents=True)
    seed_status_event(feature_dir, _hostile_event(slug=""))
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": _META_HOSTILE_SLUG}),
        encoding="utf-8",
    )
    return feature_dir


def test_resolve_mission_identity_passes_through_legitimate_slug(tmp_path: Path) -> None:
    """A LEGITIMATE meta.json slug is returned UNCHANGED (not downgraded). FR-009.

    Un-fakeable pass-through guard: the chokepoint must not be a blanket downgrade
    to ``feature_dir.name`` — that would corrupt the display slug for every real
    mission. A valid slug survives ``safe_mission_slug`` verbatim.
    """
    from specify_cli.mission_metadata import resolve_mission_identity

    feature_dir = tmp_path / "kitty-specs" / _FEATURE_NAME
    feature_dir.mkdir(parents=True)
    legit_slug = "034-real-mission-name"
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": legit_slug}),
        encoding="utf-8",
    )

    identity = resolve_mission_identity(feature_dir)

    assert identity.mission_slug == legit_slug
    # Explicitly NOT downgraded to the trusted directory name.
    assert identity.mission_slug != feature_dir.name


def test_generate_lifecycle_json_fail_closed_on_hostile_meta_slug(tmp_path: Path) -> None:
    """Hostile meta.json slug + empty event slug must not escape derived_dir. FR-009.

    Mutation-verify: reverting the ``safe_mission_slug`` chokepoint in
    ``resolve_mission_identity`` makes this test FAIL — the escaped dir
    (``derived/../../../../evil``) would be created and the trusted output absent.
    """
    feature_dir = _seed_meta_only_hostile_feature_dir(tmp_path)
    derived_dir = tmp_path / "derived"
    derived_dir.mkdir()

    generate_lifecycle_json(feature_dir, derived_dir)

    # No write escapes the derived root; output lands under the trusted name.
    assert not (derived_dir / _META_HOSTILE_SLUG).resolve().exists()
    assert (derived_dir / _FEATURE_NAME / "lifecycle.json").exists()


def test_materialize_if_stale_fail_closed_on_hostile_meta_slug(tmp_path: Path) -> None:
    """The staleness key (``_stale_check_slug`` → meta.json) must not escape. FR-009.

    Drives ``materialize_if_stale`` whose derived-dir location is keyed on
    ``_stale_check_slug(feature_dir)`` → ``resolve_mission_identity`` (the guarded
    meta read). A hostile meta slug must resolve the derived location under the
    trusted ``feature_dir.name``, not an escaped path.

    Mutation-verify: reverting the chokepoint makes this FAIL (escaped dir created).
    """
    from specify_cli.status.views import materialize_if_stale

    feature_dir = _seed_meta_only_hostile_feature_dir(tmp_path)
    repo_root = tmp_path
    derived_root = repo_root / ".kittify" / "derived"

    materialize_if_stale(feature_dir, repo_root)

    assert not (derived_root / _META_HOSTILE_SLUG).resolve().exists()
    assert (derived_root / _FEATURE_NAME).is_dir()


# ── lifecycle.py load_meta contract tests (FR-006b, WP09) ──────────────────
# _fallback_created_at and _last_merge_marker_at both use
# load_meta(feature_dir, allow_missing=True, on_malformed="raise").
# Observable contracts:
#   missing meta  → None (allow_missing absorbs to None, then ``or {}`` yields
#                   an empty dict, so the functions return None gracefully)
#   malformed meta → raises ValueError (on_malformed="raise" propagates)


class TestLifecycleMetaLoadContract:
    """Contract tests for lifecycle.py's load_meta(on_malformed='raise') sites.

    Observable return values per arm (CT4 — not call-graph assertions).
    """

    def test_fallback_created_at_missing_meta_returns_mtime(
        self, tmp_path: Path
    ) -> None:
        """Missing meta.json: _fallback_created_at falls back to dir mtime (never raises).

        With allow_missing=True, load_meta returns None; ``None or {}`` yields {}.
        No ``created_at`` key in the empty dict, so the function falls through to
        ``feature_dir.stat().st_mtime`` and returns a datetime.
        """
        from kernel.clock import datetime

        feature_dir = tmp_path / "kitty-specs" / "099-wp09-lifecycle-contract"
        feature_dir.mkdir(parents=True)
        assert not (feature_dir / "meta.json").exists()

        # Falls back to mtime — always a datetime when the directory exists.
        result = _fallback_created_at(feature_dir)
        assert isinstance(result, datetime)

    def test_fallback_created_at_malformed_meta_raises(self, tmp_path: Path) -> None:
        """Malformed meta.json: _fallback_created_at raises MissionMetaReadError (FR-007 fail-closed)."""
        feature_dir = tmp_path / "kitty-specs" / "099-wp09-lifecycle-contract"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text("{bad json", encoding="utf-8")

        with pytest.raises(MissionMetaReadError, match="Malformed JSON"):
            _fallback_created_at(feature_dir)

    def test_last_merge_marker_at_missing_meta_returns_none(
        self, tmp_path: Path
    ) -> None:
        """Missing meta.json: _last_merge_marker_at returns None without raising.

        With allow_missing=True, load_meta returns None; ``None or {}`` yields {}.
        No ``merged_at`` key in the empty dict so _parse_dt(None) returns None.
        """
        feature_dir = tmp_path / "kitty-specs" / "099-wp09-lifecycle-contract"
        feature_dir.mkdir(parents=True)
        assert not (feature_dir / "meta.json").exists()

        result = _last_merge_marker_at(feature_dir)
        assert result is None

    def test_last_merge_marker_at_malformed_meta_raises(self, tmp_path: Path) -> None:
        """Malformed meta.json: _last_merge_marker_at raises MissionMetaReadError (FR-007 fail-closed)."""
        feature_dir = tmp_path / "kitty-specs" / "099-wp09-lifecycle-contract"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text("{bad json", encoding="utf-8")

        with pytest.raises(MissionMetaReadError, match="Malformed JSON"):
            _last_merge_marker_at(feature_dir)
