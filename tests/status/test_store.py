"""Tests for the JSONL event store (status.events.jsonl)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from specify_cli.status.models import Lane, StatusEvent


def _git_init(path: Path) -> None:
    """Minimal git init for test fixtures that need a real git root."""
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(path)],
        check=True,
        capture_output=True,
    )
from specify_cli.status.store import (
    EVENTS_FILENAME,
    EventPersistenceError,
    _resolve_mission_id_from_dict,
    _SlugResolver,
    StoreError,
    append_event,
    append_event_verified,
    append_events_atomic,
    append_events_atomic_verified,
    read_events,
    read_events_raw,
    verify_event_readback,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _make_event(
    *,
    event_id: str = "01HXYZ0123456789ABCDEFGHJK",
    mission_slug: str = "034-feature-name",
    mission_id: str | None = None,
    wp_id: str = "WP01",
    from_lane: Lane = Lane.PLANNED,
    to_lane: Lane = Lane.CLAIMED,
) -> StatusEvent:
    """Helper to build a minimal StatusEvent for testing."""
    return StatusEvent(
        event_id=event_id,
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at="2026-02-08T12:00:00Z",
        actor="claude-opus",
        force=False,
        execution_mode="worktree",
        mission_id=mission_id,
    )


# --- round-trip ---


def test_append_and_read_round_trip(tmp_path: Path) -> None:
    """Append a single event then read it back; fields must match."""
    event = _make_event()
    append_event(tmp_path, event)

    events = read_events(tmp_path)
    assert len(events) == 1
    assert events[0] == event


def test_append_event_verified_fails_when_readback_misses_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verified append requires durable readback of the exact transition."""
    event = _make_event(to_lane=Lane.IN_PROGRESS)

    import specify_cli.status.store as status_store

    monkeypatch.setattr(status_store, "append_event", lambda _feature_dir, _event: None)

    with pytest.raises(EventPersistenceError) as exc_info:
        append_event_verified(tmp_path, event)

    message = str(exc_info.value)
    assert "expected event missing after append" in message
    assert "mission_slug=034-feature-name" in message
    assert "wp_id=WP01" in message
    assert "target_lane=in_progress" in message
    assert str(tmp_path / EVENTS_FILENAME) in message
    diagnostic = exc_info.value.to_diagnostic()
    assert diagnostic["diagnostic_code"] == "STATUS_EVENT_PERSISTENCE_VERIFICATION_FAILED"
    assert diagnostic["violated_invariant"] == "STA-002"
    assert diagnostic["work_package_id"] == "WP01"
    assert diagnostic["to_lane"] == "in_progress"
    assert diagnostic["status_events_path"] == str(tmp_path / EVENTS_FILENAME)


def test_append_event_verified_wraps_append_failures_in_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Append failures surface the same structured persistence diagnostic."""
    event = _make_event(to_lane=Lane.IN_PROGRESS)

    import specify_cli.status.store as status_store

    def _raise_append(_feature_dir: Path, _event: StatusEvent) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(status_store, "append_event", _raise_append)

    with pytest.raises(EventPersistenceError) as exc_info:
        append_event_verified(tmp_path, event)

    assert "append failed: disk full" in str(exc_info.value)
    diagnostic = exc_info.value.to_diagnostic()
    assert diagnostic["diagnostic_code"] == "STATUS_EVENT_PERSISTENCE_VERIFICATION_FAILED"
    assert diagnostic["work_package_id"] == "WP01"
    assert diagnostic["to_lane"] == "in_progress"
    assert diagnostic["status_events_path"] == str(tmp_path / EVENTS_FILENAME)


def test_multiple_appends_preserve_order(tmp_path: Path) -> None:
    """Events appended in sequence are returned in the same order."""
    e1 = _make_event(event_id="01AAAA0000000000000000001A", wp_id="WP01")
    e2 = _make_event(event_id="01BBBB0000000000000000002B", wp_id="WP02")
    e3 = _make_event(event_id="01CCCC0000000000000000003C", wp_id="WP03")

    append_event(tmp_path, e1)
    append_event(tmp_path, e2)
    append_event(tmp_path, e3)

    events = read_events(tmp_path)
    assert len(events) == 3
    assert events[0].wp_id == "WP01"
    assert events[1].wp_id == "WP02"
    assert events[2].wp_id == "WP03"


def test_append_events_atomic_persists_full_batch(tmp_path: Path) -> None:
    e1 = _make_event(event_id="01AAAA0000000000000000001A", wp_id="WP01")
    e2 = _make_event(
        event_id="01BBBB0000000000000000002B",
        wp_id="WP01",
        from_lane=Lane.CLAIMED,
        to_lane=Lane.IN_PROGRESS,
    )

    append_events_atomic(tmp_path, [e1, e2])

    events = read_events(tmp_path)
    assert [(event.from_lane, event.to_lane) for event in events] == [
        (Lane.PLANNED, Lane.CLAIMED),
        (Lane.CLAIMED, Lane.IN_PROGRESS),
    ]


def test_append_events_atomic_verified_fails_when_batch_readback_misses_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    e1 = _make_event(event_id="01AAAA0000000000000000001A", wp_id="WP01")
    e2 = _make_event(
        event_id="01BBBB0000000000000000002B",
        wp_id="WP01",
        from_lane=Lane.CLAIMED,
        to_lane=Lane.IN_PROGRESS,
    )

    import specify_cli.status.store as status_store

    monkeypatch.setattr(status_store, "append_events_atomic", lambda _feature_dir, _events: None)

    with pytest.raises(EventPersistenceError) as exc_info:
        append_events_atomic_verified(tmp_path, [e1, e2])

    assert "expected event missing after append" in str(exc_info.value)
    assert "event_id=01AAAA0000000000000000001A" in str(exc_info.value)


def test_verify_event_readback_rejects_wrong_mission_slug(tmp_path: Path) -> None:
    expected = _make_event()
    append_event(tmp_path, replace(expected, mission_slug="999-other-mission"))

    with pytest.raises(EventPersistenceError) as exc_info:
        verify_event_readback(tmp_path, expected)

    assert "expected event missing after append" in str(exc_info.value)


def test_verify_event_readback_rejects_wrong_mission_id(tmp_path: Path) -> None:
    expected = _make_event(mission_id="01HQ0000000000000000000001")
    append_event(tmp_path, replace(expected, mission_id="01HQ0000000000000000000002"))

    with pytest.raises(EventPersistenceError) as exc_info:
        verify_event_readback(tmp_path, expected)

    assert "expected event missing after append" in str(exc_info.value)


def test_verify_event_readback_wraps_read_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _make_event()

    import specify_cli.status.store as status_store

    def _raise_read(_feature_dir: Path) -> list[StatusEvent]:
        raise ValueError("bad json")

    monkeypatch.setattr(status_store, "read_events", _raise_read)

    with pytest.raises(EventPersistenceError) as exc_info:
        verify_event_readback(tmp_path, event)

    assert "readback failed: bad json" in str(exc_info.value)


def test_append_events_atomic_empty_batch_is_noop(tmp_path: Path) -> None:
    append_events_atomic(tmp_path, [])

    assert not (tmp_path / EVENTS_FILENAME).exists()


def test_append_events_atomic_verified_empty_batch_is_noop(tmp_path: Path) -> None:
    append_events_atomic_verified(tmp_path, [])

    assert not (tmp_path / EVENTS_FILENAME).exists()


def test_append_events_atomic_verified_wraps_append_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _make_event()

    import specify_cli.status.store as status_store

    def _raise_append(_feature_dir: Path, _events: list[StatusEvent]) -> None:
        raise OSError("readonly")

    monkeypatch.setattr(status_store, "append_events_atomic", _raise_append)

    with pytest.raises(EventPersistenceError) as exc_info:
        append_events_atomic_verified(tmp_path, [event])

    assert "append failed: readonly" in str(exc_info.value)


def test_append_events_atomic_repairs_missing_trailing_newline(tmp_path: Path) -> None:
    first = _make_event(event_id="01AAAA0000000000000000001A", wp_id="WP01")
    second = _make_event(event_id="01BBBB0000000000000000002B", wp_id="WP02")
    events_path = tmp_path / EVENTS_FILENAME
    events_path.write_text(json.dumps(first.to_dict(), sort_keys=True), encoding="utf-8")

    append_events_atomic(tmp_path, [second])

    assert [event.wp_id for event in read_events(tmp_path)] == ["WP01", "WP02"]


def test_append_events_atomic_replace_failure_leaves_original(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = _make_event(event_id="01AAAA0000000000000000001A", wp_id="WP01")
    append_event(tmp_path, original)

    def _raise_replace(_src: Path, _dst: Path) -> None:
        raise OSError("replace failed")

    import specify_cli.status.store as status_store

    monkeypatch.setattr(status_store.os, "replace", _raise_replace)

    with pytest.raises(OSError, match="replace failed"):
        append_events_atomic(
            tmp_path,
            [
                _make_event(
                    event_id="01BBBB0000000000000000002B",
                    wp_id="WP01",
                    from_lane=Lane.CLAIMED,
                    to_lane=Lane.IN_PROGRESS,
                )
            ],
        )

    events = read_events(tmp_path)
    assert events == [original]
    assert list(tmp_path.glob(f".{EVENTS_FILENAME}.*.tmp")) == []


def test_append_events_atomic_does_not_follow_predictable_temp_symlink(
    tmp_path: Path,
) -> None:
    """A pre-planted legacy temp symlink cannot redirect an atomic append."""
    victim = tmp_path / "victim.txt"
    victim.write_text("KEEP", encoding="utf-8")
    predictable_temp = tmp_path / f"{EVENTS_FILENAME}.tmp"
    predictable_temp.symlink_to(victim)

    event = _make_event()
    append_events_atomic(tmp_path, [event])

    assert victim.read_text(encoding="utf-8") == "KEEP"
    assert predictable_temp.is_symlink()
    assert not (tmp_path / EVENTS_FILENAME).is_symlink()
    assert read_events(tmp_path) == [event]


def test_append_events_atomic_rejects_existing_log_symlink(tmp_path: Path) -> None:
    """Reading the old log must not follow an attacker-controlled symlink."""
    victim = tmp_path / "victim.txt"
    victim.write_text("KEEP", encoding="utf-8")
    events_path = tmp_path / EVENTS_FILENAME
    events_path.symlink_to(victim)

    with pytest.raises(StoreError, match="symbolic link"):
        append_events_atomic(tmp_path, [_make_event()])

    assert victim.read_text(encoding="utf-8") == "KEEP"
    assert events_path.is_symlink()


def test_read_events_skips_retrospective_events(tmp_path: Path) -> None:
    event = _make_event()
    events_file = tmp_path / EVENTS_FILENAME
    events_file.write_text(
        "\n".join(
            [
                json.dumps(event.to_dict(), sort_keys=True),
                json.dumps(
                    {
                        "event_id": "01RETRO000000000000000000",
                        "event_name": "retrospective.completed",
                        "payload": {"record_path": "/retro.yaml"},
                    },
                    sort_keys=True,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    events = read_events(tmp_path)

    assert len(events) == 1
    assert events[0].wp_id == "WP01"


# --- empty / nonexistent ---


def test_read_empty_file(tmp_path: Path) -> None:
    """An empty file returns an empty list (no crash)."""
    events_file = tmp_path / EVENTS_FILENAME
    events_file.write_text("", encoding="utf-8")

    assert read_events(tmp_path) == []


def test_read_nonexistent_file(tmp_path: Path) -> None:
    """Reading from a directory without events file returns empty list."""
    assert read_events(tmp_path) == []


# --- auto-creation ---


def test_file_created_on_first_event(tmp_path: Path) -> None:
    """The JSONL file is created automatically on the first append."""
    events_file = tmp_path / EVENTS_FILENAME
    assert not events_file.exists()

    append_event(tmp_path, _make_event())
    assert events_file.exists()


def test_directory_created_on_first_event(tmp_path: Path) -> None:
    """Parent directories are created if they do not exist."""
    nested = tmp_path / "deep" / "nested" / "feature"
    assert not nested.exists()

    append_event(nested, _make_event())
    assert (nested / EVENTS_FILENAME).exists()


# --- corruption / invalid JSON ---


def test_corruption_invalid_json(tmp_path: Path) -> None:
    """Invalid JSON raises StoreError mentioning the line number."""
    events_file = tmp_path / EVENTS_FILENAME
    events_file.write_text("not valid json\n", encoding="utf-8")

    with pytest.raises(StoreError, match="line 1"):
        read_events(tmp_path)


def test_corruption_reports_line_number(tmp_path: Path) -> None:
    """Corruption on a later line reports the correct line number."""
    event = _make_event()
    good_line = json.dumps(event.to_dict(), sort_keys=True)

    events_file = tmp_path / EVENTS_FILENAME
    events_file.write_text(f"{good_line}\n{good_line}\n{{bad json}}\n", encoding="utf-8")

    with pytest.raises(StoreError, match="line 3"):
        read_events(tmp_path)


def test_corruption_invalid_event_structure(tmp_path: Path) -> None:
    """Valid JSON but missing required fields raises StoreError."""
    events_file = tmp_path / EVENTS_FILENAME
    events_file.write_text('{"foo": "bar"}\n', encoding="utf-8")

    with pytest.raises(StoreError, match="line 1"):
        read_events(tmp_path)


def test_corruption_non_object_event_line(tmp_path: Path) -> None:
    """Valid JSON that is not an object raises StoreError."""
    events_file = tmp_path / EVENTS_FILENAME
    events_file.write_text('["not", "an", "object"]\n', encoding="utf-8")

    with pytest.raises(StoreError, match="Invalid event structure on line 1"):
        read_events(tmp_path)


# --- read_events_raw ---


def test_read_raw_returns_dicts(tmp_path: Path) -> None:
    """read_events_raw returns plain dicts, not StatusEvent objects."""
    event = _make_event()
    append_event(tmp_path, event)

    raw = read_events_raw(tmp_path)
    assert len(raw) == 1
    assert isinstance(raw[0], dict)
    assert raw[0]["wp_id"] == "WP01"


def test_read_raw_rejects_non_object_event_line(tmp_path: Path) -> None:
    """read_events_raw returns dicts or fails closed."""
    events_file = tmp_path / EVENTS_FILENAME
    events_file.write_text('["not", "an", "object"]\n', encoding="utf-8")

    with pytest.raises(StoreError, match="Invalid event structure on line 1"):
        read_events_raw(tmp_path)


# --- deterministic ordering ---


def test_deterministic_key_ordering(tmp_path: Path) -> None:
    """JSON keys in the JSONL file are sorted alphabetically."""
    append_event(tmp_path, _make_event())

    events_file = tmp_path / EVENTS_FILENAME
    line = events_file.read_text(encoding="utf-8").strip()
    parsed = json.loads(line)
    keys = list(parsed.keys())
    assert keys == sorted(keys)


# --- blank lines ---


def test_blank_lines_skipped(tmp_path: Path) -> None:
    """Blank lines interspersed in the file are silently ignored."""
    event = _make_event()
    good_line = json.dumps(event.to_dict(), sort_keys=True)

    events_file = tmp_path / EVENTS_FILENAME
    events_file.write_text(f"\n{good_line}\n\n{good_line}\n\n", encoding="utf-8")

    events = read_events(tmp_path)
    assert len(events) == 2


def test_slug_resolver_finds_kitty_specs_two_levels_up(tmp_path: Path) -> None:
    """Nested feature dirs still resolve via a kitty-specs root two levels up.

    After the FR-001 adoption ``_find_mission_specs_root`` routes through
    ``resolve_canonical_root`` which requires a real git repo.  We ``git init``
    ``tmp_path`` so the resolver finds it as the canonical root and locates
    ``kitty-specs`` there.
    """
    _git_init(tmp_path)
    mission_dir = tmp_path / "kitty-specs" / "034-feature-name"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01KNXQS9ATWWFXS3K5ZJ9E5008"}),
        encoding="utf-8",
    )
    nested_feature_dir = mission_dir / "status"
    nested_feature_dir.mkdir()

    resolver = _SlugResolver(nested_feature_dir)

    assert resolver.resolve("034-feature-name") == "01KNXQS9ATWWFXS3K5ZJ9E5008"


def test_slug_resolver_returns_none_for_malformed_meta(tmp_path: Path) -> None:
    """Malformed legacy meta.json leaves mission_id unresolved instead of crashing."""
    mission_dir = tmp_path / "kitty-specs" / "034-feature-name"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text("{bad json", encoding="utf-8")

    resolver = _SlugResolver(mission_dir)

    assert resolver.resolve("034-feature-name") is None


def test_slug_resolver_returns_none_for_non_dict_meta(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A meta.json that parses to a non-object (e.g. a JSON array) leaves
    mission_id unresolved instead of crashing on ``data.get`` — and logs why.

    Guards the same defect class as the resolver/aggregate non-dict fail-closed
    path: ``json.loads("[]")`` yields a ``list``, on which ``.get`` would raise
    ``AttributeError``. The slug resolver must degrade to ``None`` with a warning.
    """
    mission_dir = tmp_path / "kitty-specs" / "034-feature-name"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text("[]", encoding="utf-8")

    resolver = _SlugResolver(mission_dir)

    with caplog.at_level("WARNING", logger="specify_cli.status.store"):
        assert resolver.resolve("034-feature-name") is None

    assert any(
        "Expected JSON object" in record.getMessage()
        and "034-feature-name" in record.getMessage()
        for record in caplog.records
    ), "non-dict meta.json must emit the canonical 'Expected JSON object' WARNING"


def test_slug_resolver_happy_path_resolves_from_meta(tmp_path: Path) -> None:
    """A valid slug still resolves mission_id from <root>/<slug>/meta.json (guard preserved)."""
    mission_dir = tmp_path / "kitty-specs" / "034-feature-name"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01KNXQS9ATWWFXS3K5ZJ9E5008"}),
        encoding="utf-8",
    )

    resolver = _SlugResolver(mission_dir)

    assert resolver.resolve("034-feature-name") == "01KNXQS9ATWWFXS3K5ZJ9E5008"


def test_slug_resolver_rejects_traversal_slug_without_reading_outside(
    tmp_path: Path,
) -> None:
    """A traversal slug fails closed (None) and never reads a file outside the specs root.

    Plants an attacker-controlled ``meta.json`` two levels above the specs root
    that a ``../../`` slug would reach if the guard were absent.  The resolver
    must return None and must NOT read that file (proving no traversal occurred).
    """
    specs_root = tmp_path / "kitty-specs"
    mission_dir = specs_root / "034-feature-name"
    mission_dir.mkdir(parents=True)

    # Attacker-planted meta.json that a "../../escape" slug would resolve to:
    # <specs_root>/../../escape/meta.json == tmp_path.parent/escape/meta.json
    escape_dir = tmp_path.parent / "escape"
    escape_dir.mkdir(parents=True, exist_ok=True)
    (escape_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01ATTACKERWXS3K5ZJ9E5008XX"}),
        encoding="utf-8",
    )

    resolver = _SlugResolver(mission_dir)

    assert resolver.resolve("../../escape") is None


def test_slug_resolver_rejects_absolute_style_traversal(tmp_path: Path) -> None:
    """A deep traversal slug returns None AND never reads the attacker file.

    Un-fakeable: plants a real attacker ``meta.json`` at the EXACT location the
    ``../../../escape`` slug would resolve to (``<specs_root>/../../../escape``).
    Without the guard, ``resolve()`` would read it and return the attacker
    mission_id; with the guard it must return None and leave the file unread.
    """
    specs_root = tmp_path / "kitty-specs"
    mission_dir = specs_root / "034-feature-name"
    mission_dir.mkdir(parents=True)

    traversal_slug = "../../../escape"
    # _mission_specs_root resolves to <specs_root>; the slug would join to:
    escape_dir = specs_root / traversal_slug
    escape_dir.mkdir(parents=True, exist_ok=True)
    attacker_meta = escape_dir / "meta.json"
    attacker_meta.write_text(
        json.dumps({"mission_id": "01ATTACKERDEEPK5ZJ9E5008XX"}),
        encoding="utf-8",
    )

    resolver = _SlugResolver(mission_dir)

    # Guard returns None (NOT the attacker mission_id) and never reads the file.
    assert resolver.resolve(traversal_slug) is None
    assert attacker_meta.read_text(encoding="utf-8") != ""  # file still intact/unread


def test_resolve_mission_id_from_dict_fail_closed_on_traversal_slug(
    tmp_path: Path,
) -> None:
    """End-to-end event path: a hostile mission_slug in an event record yields None.

    Un-fakeable: plants a real attacker ``meta.json`` at the location the
    ``../escape`` slug resolves to (``<specs_root>/../escape`` == ``tmp_path/escape``).
    Without the guard, the resolver would read it and return the attacker
    mission_id; with the guard the end-to-end resolution must return None.
    """
    specs_root = tmp_path / "kitty-specs"
    mission_dir = specs_root / "034-feature-name"
    mission_dir.mkdir(parents=True)

    # _mission_specs_root == <specs_root>; slug "../escape" → <specs_root>/../escape
    escape_dir = tmp_path / "escape"
    escape_dir.mkdir(parents=True, exist_ok=True)
    (escape_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01ATTACKERESCAPEZJ9E5008XX"}),
        encoding="utf-8",
    )

    resolver = _SlugResolver(mission_dir)

    result = _resolve_mission_id_from_dict({"mission_slug": "../escape"}, resolver)

    assert result is None


# --- FR-002 / IC-01: resolve()-containment against symlink escape -------------


def test_slug_resolver_rejects_symlinked_escape_dir(tmp_path: Path) -> None:
    """A grammar-VALID slug naming a symlink dir that escapes the specs root → None.

    This is the FR-002 hole the segment grammar CANNOT see: the slug
    ``"034-evil-link"`` passes ``assert_safe_path_segment`` (no ``..``, no
    separators), but it names a **symlink directory** under the specs root whose
    target lives OUTSIDE the root. Without resolved-path containment, ``resolve()``
    would follow the link and read the attacker's ``meta.json``. With
    ``ensure_within_any`` on the composed path, it must return ``None`` and never
    read the escaped file.

    Mutation-verify: neutralising the containment (e.g. making ``_is_contained``
    return ``True`` unconditionally) makes this test FAIL — the attacker
    mission_id would be returned.
    """
    specs_root = tmp_path / "kitty-specs"
    mission_dir = specs_root / "034-feature-name"
    mission_dir.mkdir(parents=True)

    # Attacker target OUTSIDE the specs root, with a real meta.json behind it.
    outside_dir = tmp_path / "outside-target"
    outside_dir.mkdir(parents=True)
    attacker_meta = outside_dir / "meta.json"
    attacker_meta.write_text(
        json.dumps({"mission_id": "01ATTACKERSYMLNK5ZJ9E5008X"}),
        encoding="utf-8",
    )

    # Symlink dir UNDER the specs root, grammar-valid name, target outside the root.
    evil_link = specs_root / "034-evil-link"
    evil_link.symlink_to(outside_dir, target_is_directory=True)
    assert evil_link.is_symlink()  # no-op test guard: the link must exist

    resolver = _SlugResolver(mission_dir)

    # Containment rejects: None returned, attacker file NOT consumed.
    assert resolver.resolve("034-evil-link") is None


def test_slug_resolver_resolves_under_symlinked_root(tmp_path: Path) -> None:
    """A legitimate slug RESOLVES even when the specs root is reached via a symlink.

    NFR-003 (macOS false-reject guard): on macOS ``/tmp`` and ``$TMPDIR`` are
    symlinks, so the *logical* specs root differs from its ``resolve()``d form. A
    containment guard that pre-resolves the root but not the candidate (or vice
    versa) would wrongly REJECT a perfectly legitimate slug. ``ensure_within_any``
    resolves both sides consistently, so a legit slug under a symlinked root
    validates.

    Runs on ALL platforms (no ``skip``/``skipif``): the symlinked root is
    constructed explicitly inside ``tmp_path`` so Linux CI exercises it too.
    """
    real_specs_parent = tmp_path / "real"
    real_specs_root = real_specs_parent / "kitty-specs"
    mission_dir = real_specs_root / "034-feature-name"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01LEGITSYMROOTK5ZJ9E5008XY"}),
        encoding="utf-8",
    )

    # Reach the SAME specs root through a symlinked parent directory.
    link_parent = tmp_path / "linked"
    link_parent.symlink_to(real_specs_parent, target_is_directory=True)
    assert link_parent.is_symlink()  # no-op test guard: the link must exist

    # Anchor the resolver on the feature dir as seen THROUGH the symlink, so its
    # logical ``_mission_specs_root`` is the un-resolved (symlinked) path.
    symlinked_mission_dir = link_parent / "kitty-specs" / "034-feature-name"
    resolver = _SlugResolver(symlinked_mission_dir)

    # No false reject: the legitimate slug resolves to its real mission_id.
    assert resolver.resolve("034-feature-name") == "01LEGITSYMROOTK5ZJ9E5008XY"


def test_read_events_lenient_decodes_through_from_dict_fills_defaults_and_skips_bad_lines(tmp_path: Path) -> None:
    """#5340: one advisory reader for the hollow-review check; append order, never raising."""
    from specify_cli.status import read_events_lenient

    structured = {"tool": "claude", "model": None, "profile": "ivan", "role": "implementer"}
    lines = [
        json.dumps({"event_id": "e1", "wp_id": "WP01", "from_lane": "planned", "to_lane": "claimed", "actor": structured}),
        "not json",
        "[1, 2]",
        "",
        json.dumps({"event_id": "e2", "wp_id": "WP01", "from_lane": "claimed", "to_lane": "nowhere", "actor": "x"}),
        json.dumps({"event_id": "e3", "wp_id": "WP01", "from_lane": "claimed", "to_lane": "in_progress", "actor": {"tool": "claude"}}),
        json.dumps({"kind": "annotation", "wp_id": "WP01"}),
        json.dumps({"event_type": "DecisionPointOpened", "wp_id": "WP01"}),
        json.dumps({"wp_id": "WP01", "from_lane": "in_review", "to_lane": "approved", "actor": "rev", "at": None, "force": True}),
    ]
    (tmp_path / EVENTS_FILENAME).write_text("\n".join(lines) + "\n", encoding="utf-8")

    events = read_events_lenient(tmp_path)

    assert [(e.event_id, str(e.to_lane)) for e in events] == [("e1", "claimed"), ("", "approved")]
    assert events[0].actor == structured and events[0].execution_mode == "" and events[0].at == ""
    assert events[1].force is True and events[1].actor == "rev"
    assert read_events_lenient(tmp_path / "absent") == []


class TestMalformedAnnotationHandling:
    """The canonical decoder reports malformed annotation shapes, not AttributeError."""

    @staticmethod
    def _annotation(delta: object) -> dict[str, object]:
        return {
            "kind": "annotation",
            "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAW",
            "wp_id": "WP01",
            "at": "2026-10-11T14:00:00Z",
            "actor": "test-agent",
            "delta": delta,
        }

    @pytest.mark.parametrize(
        ("delta", "reason"),
        [([], "'list' object has no attribute 'get'"),
         ({"subtasks": []}, "'list' object has no attribute 'items'"),
         ({"subtasks": "invalid"}, "'str' object has no attribute 'items'")],
        ids=["delta-list", "subtasks-list", "subtasks-string"],
    )
    @pytest.mark.parametrize("preceding_rows", [False, True], ids=["first-row", "after-blanks"])
    def test_malformed_annotation_raises_line_bearing_store_error(
        self, tmp_path: Path, delta: object, reason: str, preceding_rows: bool,
    ) -> None:
        prefix = json.dumps(_make_event(event_id="01ARZ3NDEKTSV4RRFFQ69G5FAV").to_dict()) + "\n\n \n" if preceding_rows else ""
        log = tmp_path / EVENTS_FILENAME
        original = (prefix + json.dumps(self._annotation(delta)) + "\n").encode()
        log.write_bytes(original)

        with pytest.raises(StoreError) as exc_info:
            read_events(tmp_path)

        line = 4 if preceding_rows else 1
        assert str(exc_info.value) == f"Invalid event structure on line {line}: {reason}"
        assert isinstance(exc_info.value.__cause__, AttributeError)
        assert log.read_bytes() == original

        # Repair only the malformed payload: the same envelope/ULID must be accepted.
        from specify_cli.status.store import read_event_stream

        valid_delta = {"agent": "new-agent", "subtasks": {"T001": "done", "T002": "planned"}}
        log.write_text(prefix + json.dumps(self._annotation(valid_delta)) + "\n", encoding="utf-8")
        stream = read_event_stream(tmp_path)
        assert len(stream.transitions) == int(preceding_rows)
        assert len(stream.annotations) == 1
        assert stream.annotations[0].wp_id == "WP01"
        assert stream.annotations[0].delta.agent == "new-agent"
        assert stream.annotations[0].delta.subtasks == {"T001": "done", "T002": "planned"}


@pytest.mark.parametrize("preceding_rows", [False, True], ids=["first-row", "after-blanks"])
def test_transition_bad_identity_raises_line_bearing_store_error(tmp_path: Path, preceding_rows: bool) -> None:
    """A valid transition envelope with only a malformed slug fails canonically."""
    valid = _make_event(event_id="01ARZ3NDEKTSV4RRFFQ69G5FAV").to_dict()
    valid.pop("mission_id", None)
    malformed = {**valid, "mission_slug": 123}
    prefix = json.dumps(valid) + "\n\n \n" if preceding_rows else ""
    log = tmp_path / EVENTS_FILENAME
    original = (prefix + json.dumps(malformed) + "\n").encode()
    log.write_bytes(original)

    with pytest.raises(StoreError) as exc_info:
        read_events(tmp_path)

    line = 4 if preceding_rows else 1
    assert str(exc_info.value) == f"Invalid event structure on line {line}: 'int' object has no attribute 'strip'"
    assert isinstance(exc_info.value.__cause__, AttributeError)
    assert log.read_bytes() == original

    log.write_text(prefix + json.dumps(valid) + "\n", encoding="utf-8")
    assert len(read_events(tmp_path)) == 1 + int(preceding_rows)
