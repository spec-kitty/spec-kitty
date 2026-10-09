"""WP05 -- run-state store hardening (mission fsm-write-path-integrity-01M1TZV6).

Pins User Story 5 / SC-006 through the run-state store alone (contract
``contracts/run-state-store.md`` §4, data-model §8):

- RS-1  two missions sharing a ``mission_slug`` but with distinct ``mission_id``
        resolve DISTINCT runs (FR-016, C-003 -- the 083 identity model);
- RS-2  a live ``feature-runs.json`` entry whose ``state.json`` is absent is a
        loud structured error, never a silent fresh run (FR-016);
- RS-3  a kill inside ``_write_snapshot`` leaves the previous ``state.json``
        or the complete new one, never a torn cursor (FR-015);
- RS-4  the progress query leaves tracked ``status.json`` byte-identical (FR-017).

Plus the Q9 migration contract (decision ``01M1V8J842E7CJR6MGZ0MW3DQF``,
``design-notes/WP05-run-state.md``): in-place rekey on first touch, keyed by
``mission_id`` or ``legacy-<slug>``, idempotent and lossless.

The test boundary is the store itself: template discovery and the engine's
``start_mission_run`` are replaced by a recording fake so the assertions
speak only about index keys, run identity, and file bytes.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import pytest

from runtime.next import runtime_bridge_io as io_seam
from runtime.next._internal_runtime import MissionRunRef
from runtime.next._internal_runtime.engine import MissionRunSnapshot, _append_event, _write_snapshot
from runtime.next._internal_runtime.schema import MissionRuntimeError
from runtime.next.runtime_bridge_io import RunStateMissing, run_index_key

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION_ID_A = "01AAAAAAAAAAAAAAAAAAAAAAAA"
_MISSION_ID_B = "01BBBBBBBBBBBBBBBBBBBBBBBB"
_SLUG = "dup-slug"
_MISSION_TYPE = "software-dev"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _index_path(repo_root: Path) -> Path:
    return repo_root / ".kittify" / "runtime" / "feature-runs.json"


def _write_index(repo_root: Path, index: dict[str, dict[str, Any]]) -> None:
    path = _index_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")


def _read_index(repo_root: Path) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = json.loads(_index_path(repo_root).read_text(encoding="utf-8"))
    return loaded


def _make_run_dir(repo_root: Path, run_id: str, *, with_state: bool = True) -> Path:
    run_dir = repo_root / ".kittify" / "runtime" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    if with_state:
        (run_dir / "state.json").write_text("{}", encoding="utf-8")
    return run_dir


def _entry(run_id: str, run_dir: Path, *, mission_id: str | None, slug: str | None = _SLUG) -> dict[str, Any]:
    entry: dict[str, Any] = {"run_id": run_id, "run_dir": str(run_dir), "mission_type": _MISSION_TYPE}
    if mission_id is not None:
        entry["mission_id"] = mission_id
    if slug is not None:
        entry["mission_slug"] = slug
    return entry


def _write_meta(repo_root: Path, slug: str, mission_id: str | None) -> None:
    feature_dir = repo_root / "kitty-specs" / slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {"mission_slug": slug, "mission_type": _MISSION_TYPE, "mission_number": None}
    if mission_id is not None:
        meta["mission_id"] = mission_id
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


class _FakeEngine:
    """Recording stand-in for ``start_mission_run`` (the engine is outside the boundary)."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.started: list[str] = []

    def __call__(self, **kwargs: Any) -> MissionRunRef:
        run_id = f"fresh-run-{len(self.started) + 1}"
        self.started.append(run_id)
        run_dir = _make_run_dir(self.repo_root, run_id)
        return MissionRunRef(run_id=run_id, run_dir=str(run_dir), mission_key=_MISSION_TYPE)


@pytest.fixture
def fake_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _FakeEngine:
    """Stub template discovery + engine start so ``get_or_start_run`` exercises only the store."""
    engine = _FakeEngine(tmp_path)
    monkeypatch.setattr(io_seam, "start_mission_run", engine)
    monkeypatch.setattr(io_seam, "_runtime_template_key", lambda mission_type, repo_root: mission_type)
    monkeypatch.setattr(io_seam, "_workflow_runtime_template", lambda *a, **k: (None, None))
    return engine


def _snapshot(run_id: str, *, issued_step_id: str | None) -> MissionRunSnapshot:
    return MissionRunSnapshot(
        run_id=run_id,
        mission_key=_MISSION_TYPE,
        template_path="template.yaml",
        template_hash="deadbeef",
        issued_step_id=issued_step_id,
    )


# ---------------------------------------------------------------------------
# RS-1 -- slug collision resolves distinct runs (T026 -> T027)
# ---------------------------------------------------------------------------


def test_slug_collision_resolves_distinct_runs(tmp_path: Path, fake_engine: _FakeEngine) -> None:
    """Given mission A's run is indexed under the shared slug, When mission B
    (same slug, distinct ``mission_id``) resolves its run, Then B gets a
    different run -- never A's cursor -- and both stay indexed by identity."""
    run_dir_a = _make_run_dir(tmp_path, "run-a")
    _write_index(tmp_path, {_SLUG: _entry("run-a", run_dir_a, mission_id=_MISSION_ID_A)})
    _write_meta(tmp_path, _SLUG, _MISSION_ID_B)

    ref_b = io_seam.get_or_start_run(_SLUG, tmp_path, _MISSION_TYPE)

    assert ref_b.run_id != "run-a", "mission B resolved mission A's run through the shared slug"
    index = _read_index(tmp_path)
    assert set(index) == {_MISSION_ID_A, _MISSION_ID_B}, "index must be keyed by mission_id, never by slug"
    assert index[_MISSION_ID_A]["run_id"] == "run-a"
    assert index[_MISSION_ID_B]["run_id"] == ref_b.run_id
    assert index[_MISSION_ID_B]["mission_slug"] == _SLUG


def test_run_index_key_is_mission_id_or_legacy_slug() -> None:
    assert run_index_key(_SLUG, _MISSION_ID_A) == _MISSION_ID_A
    assert run_index_key(_SLUG, None) == f"legacy-{_SLUG}"
    assert run_index_key(_SLUG, "") == f"legacy-{_SLUG}"


# ---------------------------------------------------------------------------
# Q9 -- in-place rekey on first touch (T027)
# ---------------------------------------------------------------------------


def test_legacy_slug_entry_without_mission_id_still_resolves_and_is_rekeyed(tmp_path: Path, fake_engine: _FakeEngine) -> None:
    """Given a pre-WP05 slug-keyed entry with no ``mission_id`` for a mission
    that still has none, When the run is resolved, Then the same run comes
    back and the entry now lives under ``legacy-<slug>``."""
    run_dir = _make_run_dir(tmp_path, "run-legacy")
    _write_index(tmp_path, {_SLUG: _entry("run-legacy", run_dir, mission_id=None, slug=None)})
    _write_meta(tmp_path, _SLUG, None)

    ref = io_seam.get_or_start_run(_SLUG, tmp_path, _MISSION_TYPE)

    assert ref.run_id == "run-legacy"
    assert fake_engine.started == []
    index = _read_index(tmp_path)
    assert set(index) == {f"legacy-{_SLUG}"}
    assert index[f"legacy-{_SLUG}"]["run_id"] == "run-legacy"
    assert index[f"legacy-{_SLUG}"]["mission_slug"] == _SLUG


def test_slug_entry_with_matching_mission_id_is_adopted_and_rekeyed(tmp_path: Path, fake_engine: _FakeEngine) -> None:
    """Given a pre-WP05 slug-keyed entry whose stored ``mission_id`` is the
    caller's, When the run is resolved, Then it is reused (no fresh run) and
    moved under the ``mission_id`` key."""
    run_dir = _make_run_dir(tmp_path, "run-a")
    _write_index(tmp_path, {_SLUG: _entry("run-a", run_dir, mission_id=_MISSION_ID_A)})
    _write_meta(tmp_path, _SLUG, _MISSION_ID_A)

    ref = io_seam.get_or_start_run(_SLUG, tmp_path, _MISSION_TYPE)

    assert ref.run_id == "run-a"
    assert fake_engine.started == []
    assert set(_read_index(tmp_path)) == {_MISSION_ID_A}


def test_canonicalize_run_index_is_idempotent_and_lossless() -> None:
    """Given a mixed pre/post-WP05 index, When it is canonicalized twice, Then
    the second pass is a no-op, every run survives, and an entry whose
    canonical slot is already taken is kept rather than overwritten."""
    mixed: dict[str, Any] = {
        "slug-with-id": {"run_id": "r1", "run_dir": "/r1", "mission_id": _MISSION_ID_A},
        "slug-no-id": {"run_id": "r2", "run_dir": "/r2", "mission_id": None},
        "bare-legacy": {"run_id": "r3", "run_dir": "/r3"},
        _MISSION_ID_B: {"run_id": "r4", "run_dir": "/r4", "mission_id": _MISSION_ID_B, "mission_slug": "x"},
        "legacy-old": {"run_id": "r5", "run_dir": "/r5", "mission_slug": "old"},
        "collides": {"run_id": "r6", "run_dir": "/r6", "mission_id": _MISSION_ID_B, "mission_slug": "collides"},
    }

    once, changed_once = io_seam._canonicalize_run_index(mixed)
    twice, changed_twice = io_seam._canonicalize_run_index(once)

    assert changed_once is True
    assert changed_twice is False
    assert twice == once
    assert set(once) == {_MISSION_ID_A, "legacy-slug-no-id", "legacy-bare-legacy", _MISSION_ID_B, "legacy-old", "collides"}
    assert sorted(e["run_id"] for e in once.values()) == ["r1", "r2", "r3", "r4", "r5", "r6"]
    assert once[_MISSION_ID_B]["run_id"] == "r4", "occupant of the canonical slot must not be overwritten"
    assert once["legacy-bare-legacy"]["mission_slug"] == "bare-legacy", "moved entries carry their display slug"
    assert mixed["bare-legacy"] == {"run_id": "r3", "run_dir": "/r3"}, "input index is not mutated"


def test_rekey_persists_once_then_index_bytes_are_stable(tmp_path: Path, fake_engine: _FakeEngine) -> None:
    """Given a slug-keyed index, When the run is resolved twice, Then the file
    is rewritten by the first touch only (byte-identical afterwards)."""
    run_dir = _make_run_dir(tmp_path, "run-a")
    _write_index(tmp_path, {_SLUG: _entry("run-a", run_dir, mission_id=_MISSION_ID_A)})
    _write_meta(tmp_path, _SLUG, _MISSION_ID_A)

    io_seam.get_or_start_run(_SLUG, tmp_path, _MISSION_TYPE)
    after_first = _index_path(tmp_path).read_bytes()
    io_seam.get_or_start_run(_SLUG, tmp_path, _MISSION_TYPE)

    assert _index_path(tmp_path).read_bytes() == after_first
    assert set(json.loads(after_first)) == {_MISSION_ID_A}


def test_read_only_resolvers_never_persist_the_rekey(tmp_path: Path) -> None:
    """Given a slug-keyed index, When only the read-only resolvers run, Then
    they see the canonical view but leave ``feature-runs.json`` untouched
    (query mode and OC construction stay non-mutating)."""
    run_dir = _make_run_dir(tmp_path, "run-a")
    _write_index(tmp_path, {_SLUG: _entry("run-a", run_dir, mission_id=_MISSION_ID_A)})
    _write_meta(tmp_path, _SLUG, _MISSION_ID_A)
    before = _index_path(tmp_path).read_bytes()

    ref = io_seam._existing_run_ref(_SLUG, tmp_path, _MISSION_TYPE)
    resolved_dir = io_seam._resolve_run_dir_for_mission(tmp_path, _SLUG)

    assert ref is not None and ref.run_id == "run-a"
    assert resolved_dir == run_dir
    assert _index_path(tmp_path).read_bytes() == before


def test_read_only_resolvers_do_not_adopt_another_missions_slug_entry(tmp_path: Path) -> None:
    run_dir = _make_run_dir(tmp_path, "run-a")
    _write_index(tmp_path, {_SLUG: _entry("run-a", run_dir, mission_id=_MISSION_ID_A)})
    _write_meta(tmp_path, _SLUG, _MISSION_ID_B)

    assert io_seam._existing_run_ref(_SLUG, tmp_path, _MISSION_TYPE) is None
    assert io_seam._resolve_run_dir_for_mission(tmp_path, _SLUG) is None


# ---------------------------------------------------------------------------
# RS-2 -- loud missing-state error (T028)
# ---------------------------------------------------------------------------


def test_missing_state_with_live_entry_raises_and_starts_nothing(tmp_path: Path, fake_engine: _FakeEngine) -> None:
    """Given a live index entry whose ``state.json`` is gone, When the run is
    resolved, Then a structured error is raised, no run is started and the
    index is untouched."""
    run_dir = _make_run_dir(tmp_path, "run-a", with_state=False)
    _write_meta(tmp_path, _SLUG, _MISSION_ID_A)
    _write_index(tmp_path, {_MISSION_ID_A: _entry("run-a", run_dir, mission_id=_MISSION_ID_A)})
    index_bytes_before = _index_path(tmp_path).read_bytes()
    runs_before = sorted(p.name for p in (tmp_path / ".kittify" / "runtime" / "runs").iterdir())

    with pytest.raises(RunStateMissing) as excinfo:
        io_seam.get_or_start_run(_SLUG, tmp_path, _MISSION_TYPE)

    assert fake_engine.started == [], "a fresh run was silently started over the orphaned entry"
    assert sorted(p.name for p in (tmp_path / ".kittify" / "runtime" / "runs").iterdir()) == runs_before
    assert _index_path(tmp_path).read_bytes() == index_bytes_before
    err = excinfo.value
    assert isinstance(err, MissionRuntimeError)
    assert (err.mission_id, err.run_id, err.run_dir) == (_MISSION_ID_A, "run-a", run_dir)
    assert err.to_dict()["error_code"] == "RUN_STATE_MISSING"
    assert err.to_dict()["run_dir"] == str(run_dir)
    assert "spec-kitty doctor" in str(err)


def test_existing_run_ref_raises_on_missing_state_instead_of_none(tmp_path: Path) -> None:
    """The read-only resolver shares the loud contract: a missing cursor is an
    error, not "no run" (which would let query mode preview a phantom fresh run)."""
    run_dir = _make_run_dir(tmp_path, "run-a", with_state=False)
    _write_meta(tmp_path, _SLUG, _MISSION_ID_A)
    _write_index(tmp_path, {_MISSION_ID_A: _entry("run-a", run_dir, mission_id=_MISSION_ID_A)})

    with pytest.raises(RunStateMissing):
        io_seam._existing_run_ref(_SLUG, tmp_path, _MISSION_TYPE)


# ---------------------------------------------------------------------------
# RS-3 -- atomic cursor write + crash-safe journal append (T029)
# ---------------------------------------------------------------------------


def test_write_snapshot_crash_window_keeps_previous_cursor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given a persisted cursor, When the process dies between writing the new
    bytes and publishing them, Then ``state.json`` still holds the previous
    complete cursor; a later successful write publishes the new one cleanly."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_snapshot(run_dir, _snapshot("r1", issued_step_id="step-1"))
    previous = (run_dir / "state.json").read_bytes()

    real_replace = os.replace

    def _crash(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("simulated kill before publish")

    monkeypatch.setattr(os, "replace", _crash)
    with pytest.raises(OSError):
        _write_snapshot(run_dir, _snapshot("r1", issued_step_id="step-2"))

    assert (run_dir / "state.json").read_bytes() == previous, "cursor was torn or overwritten mid-write"
    # FR-006: the staging tmp now has a UNIQUE name, so a failed publish cleans
    # it up (an un-recoverable-by-convention orphan would otherwise accumulate
    # across crashes); state.json still holds the previous complete cursor.
    assert not any(p.name.endswith(".tmp") for p in run_dir.iterdir()), "a failed publish must not leave an orphan staging tmp"

    monkeypatch.setattr(os, "replace", real_replace)
    _write_snapshot(run_dir, _snapshot("r1", issued_step_id="step-2"))

    assert [p.name for p in run_dir.iterdir()] == ["state.json"]
    assert json.loads((run_dir / "state.json").read_text(encoding="utf-8"))["issued_step_id"] == "step-2"


def test_write_snapshot_stages_tmp_in_the_run_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R13 (Windows): the staging file must live next to the target so the
    publish is a same-filesystem rename. FR-006: the staging name is UNIQUE
    (``state.json.<rand>.tmp``), never a fixed ``state.json.tmp``, so two
    writers to one run dir cannot collide on the staging path."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    seen: list[tuple[str, str]] = []
    real_replace = os.replace

    def _spy(src: Any, dst: Any) -> None:
        seen.append((str(src), str(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", _spy)
    _write_snapshot(run_dir, _snapshot("r1", issued_step_id=None))

    assert len(seen) == 1
    src, dst = seen[0]
    assert dst == str(run_dir / "state.json")
    staged = Path(src)
    assert staged.parent == run_dir and staged.name.startswith("state.json.") and staged.name.endswith(".tmp")
    assert staged.name != "state.json.tmp", "FR-006: the staging name must be unique, not the fixed footgun name"


def test_append_event_journal_lines_are_whole_even_when_fsync_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given a journal with one event, When a second append dies at the
    durability barrier, Then every line on disk is still a complete JSON
    record (the whole line is written in one write; earlier lines untouched)."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _append_event(run_dir, "First", {"n": 1})
    journal = run_dir / "run.events.jsonl"
    first_line = journal.read_bytes()

    def _fail(_fd: int) -> None:
        raise OSError("simulated kill at fsync")

    monkeypatch.setattr(os, "fsync", _fail)
    with pytest.raises(OSError):
        _append_event(run_dir, "Second", {"n": 2})

    raw = journal.read_bytes()
    assert raw.startswith(first_line)
    lines = raw.decode("utf-8").splitlines()
    assert [json.loads(line)["event_type"] for line in lines] == ["First", "Second"]
    assert raw.endswith(b"\n")


# ---------------------------------------------------------------------------
# RS-4 -- pure progress read (T030)
# ---------------------------------------------------------------------------


def _seed_planned_wp(feature_dir: Path, wp_id: str) -> None:
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{wp_id}-work.md").write_text(f"# {wp_id}\n", encoding="utf-8")
    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{wp_id}-planned",
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )


def test_progress_query_leaves_tracked_status_json_byte_identical(tmp_path: Path) -> None:
    """Given a mission whose committed ``status.json`` lags the event log,
    When the progress query runs, Then the tracked file's bytes are unchanged
    and the weighted percentage is still computed from the pure reduce."""
    from runtime.next.decision import _compute_wp_progress

    feature_dir = tmp_path / "kitty-specs" / "042-mission"
    _seed_planned_wp(feature_dir, "WP01")
    status_json = feature_dir / "status.json"
    status_json.write_bytes(b'{"tracked": "as-committed", "work_packages": {}}\n')
    before = status_json.read_bytes()

    counts = _compute_wp_progress(feature_dir)

    assert counts is not None and counts["total_wps"] == 1
    assert "weighted_percentage" in counts
    assert status_json.read_bytes() == before, "progress query rewrote tracked status.json"


def test_progress_query_logs_when_weighted_progress_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """The fallback is a logged warning, never a silent swallow; the lane
    counts are still returned."""
    import specify_cli.status as status_pkg

    from runtime.next.decision import _compute_wp_progress

    feature_dir = tmp_path / "kitty-specs" / "042-mission"
    _seed_planned_wp(feature_dir, "WP01")

    def _boom(_snapshot: Any) -> Any:
        raise RuntimeError("weights exploded")

    monkeypatch.setattr(status_pkg, "compute_weighted_progress", _boom)
    with caplog.at_level(logging.WARNING, logger="runtime.next.decision"):
        counts = _compute_wp_progress(feature_dir)

    assert counts is not None and counts["planned_wps"] == 1
    assert "weighted_percentage" not in counts
    assert any("weighted progress unavailable" in rec.getMessage() and "weights exploded" in rec.getMessage() for rec in caplog.records)


@pytest.mark.parametrize("legacy_key", [_SLUG, f"legacy-{_SLUG}"])
@pytest.mark.parametrize("with_state", [True, False])
def test_identity_backfill_never_silently_restarts_legacy_run(tmp_path: Path, fake_engine: _FakeEngine, legacy_key: str, with_state: bool) -> None:
    """Backfill cannot prove a no-ID run's ownership; require repair before resuming."""
    from specify_cli.migration.backfill_identity import backfill_mission

    run_dir = _make_run_dir(tmp_path, "run-legacy", with_state=with_state)
    journal = run_dir / "events.jsonl"
    journal.write_text('{"event_type":"old-history"}\n', encoding="utf-8")
    _write_meta(tmp_path, _SLUG, None)
    _write_index(tmp_path, {legacy_key: _entry("run-legacy", run_dir, mission_id=None)})
    result = backfill_mission(tmp_path / "kitty-specs" / _SLUG)
    assert result.action == "wrote" and result.mission_id
    index_before = _index_path(tmp_path).read_bytes()
    journal_before = journal.read_bytes()

    for resolve in (
        lambda: io_seam._existing_run_ref(_SLUG, tmp_path, _MISSION_TYPE),
        lambda: io_seam._resolve_run_dir_for_mission(tmp_path, _SLUG),
        lambda: io_seam.get_or_start_run(_SLUG, tmp_path, _MISSION_TYPE),
    ):
        with pytest.raises(MissionRuntimeError) as excinfo:
            resolve()
        assert excinfo.value.to_dict()["error_code"] == "RUN_IDENTITY_MIGRATION_REQUIRED"
        assert "run-legacy" in str(excinfo.value)
        assert result.mission_id in str(excinfo.value)

    assert fake_engine.started == []
    assert _index_path(tmp_path).read_bytes() == index_before
    assert journal.read_bytes() == journal_before


def test_verified_legacy_identity_binding_resumes_original_run(tmp_path: Path, fake_engine: _FakeEngine) -> None:
    """The repair described by the error keeps the original cursor and journal."""
    from specify_cli.migration.backfill_identity import backfill_mission

    run_dir = _make_run_dir(tmp_path, "run-legacy")
    _write_meta(tmp_path, _SLUG, None)
    _write_index(tmp_path, {_SLUG: _entry("run-legacy", run_dir, mission_id=None)})
    result = backfill_mission(tmp_path / "kitty-specs" / _SLUG)
    assert result.mission_id
    entry = _read_index(tmp_path)[_SLUG]
    entry["mission_id"] = result.mission_id
    _write_index(tmp_path, {result.mission_id: entry})

    ref = io_seam.get_or_start_run(_SLUG, tmp_path, _MISSION_TYPE)

    assert ref.run_id == "run-legacy"
    assert fake_engine.started == []
