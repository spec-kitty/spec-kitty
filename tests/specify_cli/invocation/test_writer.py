"""Tests for InvocationWriter (schema v2 events)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.invocation.errors import AlreadyClosedError, InvocationError, InvocationWriteError
from specify_cli.invocation.lifecycle import LIFECYCLE_LOG_RELATIVE_PATH
from specify_cli.invocation.propagator import PROPAGATION_ERRORS_PATH
from specify_cli.invocation.record import OpCompletedEvent, OpStartedEvent
from specify_cli.invocation.writer import EVENTS_DIR, INDEX_PATH, InvocationWriter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]
_INVOCATION_ID = "01ABCDEFGHJKMNPQRSTVWXYZ12"
_INVOCATION_ID_2 = "01BCDEFGHJKMNPQRSTVWXYZ123"


def _make_started(invocation_id: str = _INVOCATION_ID, **overrides: object) -> OpStartedEvent:
    defaults: dict[str, object] = {
        "invocation_id": invocation_id,
        "profile_id": "implementer-fixture",
        "action": "generate",
        "request_text": "test request",
        "governance_context_hash": "abcdef0123456789",
        "governance_context_available": True,
        "actor": "claude",
        "mode_of_work": "task_execution",
        "started_at": "2026-04-21T12:00:00+00:00",
    }
    defaults.update(overrides)
    return OpStartedEvent(**defaults)  # type: ignore[arg-type]


def _make_completed(invocation_id: str = _INVOCATION_ID, **overrides: object) -> OpCompletedEvent:
    defaults: dict[str, object] = {
        "invocation_id": invocation_id,
        "completed_at": "2026-04-21T13:00:00+00:00",
        "outcome": "done",
        "closed_by": "agent",
    }
    defaults.update(overrides)
    return OpCompletedEvent(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWriteStartedCreatesFile:
    def test_write_started_creates_file(self, tmp_path: Path) -> None:
        writer = InvocationWriter(tmp_path)
        file_path = writer.write_started(_make_started())
        assert file_path.exists()

    def test_write_started_contains_valid_json_line(self, tmp_path: Path) -> None:
        writer = InvocationWriter(tmp_path)
        file_path = writer.write_started(_make_started())
        lines = [line for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["event"] == "started"
        assert data["invocation_id"] == _INVOCATION_ID
        assert data["profile_id"] == "implementer-fixture"
        assert data["mode_of_work"] == "task_execution"

    def test_write_started_creates_events_dir(self, tmp_path: Path) -> None:
        writer = InvocationWriter(tmp_path)
        events_dir = tmp_path / EVENTS_DIR
        assert not events_dir.exists()
        writer.write_started(_make_started())
        assert events_dir.exists()


class TestKittyOpsStorage:
    def test_events_dir_is_kitty_ops(self) -> None:
        assert EVENTS_DIR == "kitty-ops"
        assert INDEX_PATH == "kitty-ops/ops-index.jsonl"
        assert PROPAGATION_ERRORS_PATH == "kitty-ops/propagation-errors.jsonl"

    def test_index_written_at_kitty_ops_ops_index(self, tmp_path: Path) -> None:
        writer = InvocationWriter(tmp_path)
        writer.write_started(_make_started())

        assert (tmp_path / "kitty-ops" / "ops-index.jsonl").exists()
        assert not (tmp_path / "invocation-index.jsonl").exists()
        assert not (tmp_path / ".kittify" / "events" / "invocation-index.jsonl").exists()

    @pytest.mark.parametrize(
        "invalid_id",
        ["../outside", "nested/path", ".", "", "01abcdefghjkmnpqrstvwxyz12"],
    )
    def test_invocation_path_rejects_non_ulid_before_composing_path(
        self,
        tmp_path: Path,
        invalid_id: str,
    ) -> None:
        writer = InvocationWriter(tmp_path)

        with pytest.raises(ValueError, match="26-char ULID"):
            writer.invocation_path(invalid_id)

        assert not (tmp_path / "outside.jsonl").exists()

    def test_invocation_path_rejects_symlink_escape_from_kitty_ops(
        self,
        tmp_path: Path,
    ) -> None:
        writer = InvocationWriter(tmp_path)
        events_dir = tmp_path / EVENTS_DIR
        events_dir.mkdir()
        outside = tmp_path / "outside.jsonl"
        outside.write_text("attacker controlled\n", encoding="utf-8")
        link = events_dir / f"{_INVOCATION_ID}.jsonl"
        try:
            link.symlink_to(outside)
        except OSError as exc:  # pragma: no cover - platform privilege dependent
            pytest.skip(f"symlinks unavailable: {exc}")

        with pytest.raises(ValueError, match="outside trusted roots"):
            writer.invocation_path(_INVOCATION_ID)

    def test_index_append_does_not_follow_preplanted_symlink(
        self,
        tmp_path: Path,
    ) -> None:
        events_dir = tmp_path / EVENTS_DIR
        events_dir.mkdir()
        outside = tmp_path / "outside-index.jsonl"
        outside.write_text("KEEP\n", encoding="utf-8")
        try:
            (events_dir / "ops-index.jsonl").symlink_to(outside)
        except OSError as exc:  # pragma: no cover - platform privilege dependent
            pytest.skip(f"symlinks unavailable: {exc}")

        InvocationWriter(tmp_path).write_started(_make_started())

        assert outside.read_text(encoding="utf-8") == "KEEP\n"


def test_lifecycle_log_relative_path_is_kitty_ops() -> None:
    assert Path("kitty-ops") / "lifecycle.jsonl" == LIFECYCLE_LOG_RELATIVE_PATH


class TestWriteCompletedAppendsLine:
    def test_write_completed_appends_second_line(self, tmp_path: Path) -> None:
        writer = InvocationWriter(tmp_path)
        writer.write_started(_make_started())
        writer.write_completed(_make_completed())
        file_path = writer.invocation_path(_INVOCATION_ID)
        lines = [
            line for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        assert len(lines) == 2
        completed_data = json.loads(lines[1])
        assert completed_data["event"] == "completed"
        assert completed_data["outcome"] == "done"
        assert completed_data["closed_by"] == "agent"

    def test_write_completed_returns_path(self, tmp_path: Path) -> None:
        writer = InvocationWriter(tmp_path)
        writer.write_started(_make_started())
        path = writer.write_completed(_make_completed())
        assert path == writer.invocation_path(_INVOCATION_ID)

    def test_write_completed_rejects_same_root_symlink_substitution(
        self,
        tmp_path: Path,
    ) -> None:
        writer = InvocationWriter(tmp_path)
        target = writer.write_started(_make_started(_INVOCATION_ID_2))
        link = tmp_path / EVENTS_DIR / f"{_INVOCATION_ID}.jsonl"
        try:
            link.symlink_to(target.name)
        except OSError as exc:  # pragma: no cover - platform privilege dependent
            pytest.skip(f"symlinks unavailable: {exc}")

        with pytest.raises(ValueError, match="symbolic link"):
            writer.write_completed(_make_completed(_INVOCATION_ID))

        rows = target.read_text(encoding="utf-8").splitlines()
        assert len(rows) == 1

    def test_write_completed_rejects_embedded_started_id_mismatch(
        self,
        tmp_path: Path,
    ) -> None:
        writer = InvocationWriter(tmp_path)
        path = tmp_path / EVENTS_DIR / f"{_INVOCATION_ID}.jsonl"
        path.parent.mkdir()
        path.write_text(
            _make_started(_INVOCATION_ID_2).to_jsonl_line() + "\n",
            encoding="utf-8",
        )

        with pytest.raises(InvocationError, match="identity mismatch"):
            writer.write_completed(_make_completed(_INVOCATION_ID))

        assert len(path.read_text(encoding="utf-8").splitlines()) == 1


class TestWriteStartedAppendOnly:
    def test_write_started_mode_is_exclusive_create(self, tmp_path: Path) -> None:
        """A second write_started with the same id raises InvocationWriteError (x mode)."""
        writer = InvocationWriter(tmp_path)
        writer.write_started(_make_started())
        with pytest.raises(InvocationWriteError, match="ULID collision"):
            writer.write_started(_make_started())


class TestWriteStartedCollisionRaises:
    def test_preexisting_file_raises_invocation_write_error(self, tmp_path: Path) -> None:
        writer = InvocationWriter(tmp_path)
        # Pre-create the file manually (simulating collision).
        events_dir = tmp_path / EVENTS_DIR
        events_dir.mkdir(parents=True)
        collision_path = events_dir / f"{_INVOCATION_ID}.jsonl"
        collision_path.write_text("existing content\n", encoding="utf-8")
        with pytest.raises(InvocationWriteError):
            writer.write_started(_make_started())


class TestAlreadyClosed:
    def test_double_complete_raises_already_closed_error(self, tmp_path: Path) -> None:
        writer = InvocationWriter(tmp_path)
        writer.write_started(_make_started())
        writer.write_completed(_make_completed())
        with pytest.raises(AlreadyClosedError):
            writer.write_completed(_make_completed())

    @pytest.mark.parametrize(
        ("link_kwargs", "link_event"),
        [
            ({"ref": "spec.md"}, "artifact_link"),
            ({"sha": "abc123"}, "commit_link"),
        ],
    )
    def test_complete_after_correlation_link_raises_already_closed_error(
        self, tmp_path: Path, link_kwargs: dict[str, str], link_event: str
    ) -> None:
        writer = InvocationWriter(tmp_path)
        writer.write_started(_make_started())
        writer.write_completed(_make_completed())
        writer.append_correlation_link(_INVOCATION_ID, **link_kwargs)

        with pytest.raises(AlreadyClosedError):
            writer.write_completed(_make_completed(outcome="failed"))

        file_path = writer.invocation_path(_INVOCATION_ID)
        events = [
            json.loads(line)["event"]
            for line in file_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert events == ["started", "completed", link_event]

    def test_complete_nonexistent_invocation_raises_invocation_error(
        self, tmp_path: Path
    ) -> None:
        writer = InvocationWriter(tmp_path)
        with pytest.raises(InvocationError):
            writer.write_completed(_make_completed(invocation_id=_INVOCATION_ID_2))


class TestWrittenLineShapes:
    """Written lines contain exactly the schema-v2 fields and nothing else."""

    def test_completed_line_contains_exactly_v2_fields(self, tmp_path: Path) -> None:
        writer = InvocationWriter(tmp_path)
        writer.write_started(_make_started())
        writer.write_completed(_make_completed(evidence_ref=".kittify/evidence/x"))

        lines = writer.invocation_path(_INVOCATION_ID).read_text(encoding="utf-8").splitlines()
        data = json.loads(lines[1])
        assert set(data) == {
            "event",
            "invocation_id",
            "completed_at",
            "outcome",
            "closed_by",
            "evidence_ref",
        }
        assert data["closed_by"] == "agent"

    def test_completed_line_omits_none_evidence_ref(self, tmp_path: Path) -> None:
        writer = InvocationWriter(tmp_path)
        writer.write_started(_make_started())
        writer.write_completed(_make_completed())

        data = json.loads(
            writer.invocation_path(_INVOCATION_ID).read_text(encoding="utf-8").splitlines()[1]
        )
        assert set(data) == {"event", "invocation_id", "completed_at", "outcome", "closed_by"}

    def test_started_line_omits_none_fields(self, tmp_path: Path) -> None:
        writer = InvocationWriter(tmp_path)
        writer.write_started(_make_started(router_confidence=None))

        data = json.loads(
            writer.invocation_path(_INVOCATION_ID).read_text(encoding="utf-8").splitlines()[0]
        )
        assert "router_confidence" not in data
        assert "mission_id" not in data
        assert "wp_id" not in data

    def test_index_entry_shape_unchanged(self, tmp_path: Path) -> None:
        writer = InvocationWriter(tmp_path)
        writer.write_started(_make_started())
        entry = json.loads(
            (tmp_path / "kitty-ops" / "ops-index.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
        assert entry == {
            "invocation_id": _INVOCATION_ID,
            "profile_id": "implementer-fixture",
            "started_at": "2026-04-21T12:00:00+00:00",
        }

    def test_unchanged_event_shapes_byte_identical(self, tmp_path: Path) -> None:
        """artifact_link / commit_link shapes are untouched by the schema split."""
        writer = InvocationWriter(tmp_path)
        writer.write_started(_make_started())
        writer.append_correlation_link(
            _INVOCATION_ID, kind="artifact", ref="spec.md", at="2026-06-10T21:00:00+00:00"
        )
        writer.append_correlation_link(_INVOCATION_ID, sha="abc123", at="2026-06-10T21:00:01+00:00")

        lines = writer.invocation_path(_INVOCATION_ID).read_text(encoding="utf-8").splitlines()
        assert json.loads(lines[1]) == {
            "event": "artifact_link",
            "invocation_id": _INVOCATION_ID,
            "at": "2026-06-10T21:00:00+00:00",
            "kind": "artifact",
            "ref": "spec.md",
        }
        assert json.loads(lines[2]) == {
            "event": "commit_link",
            "invocation_id": _INVOCATION_ID,
            "at": "2026-06-10T21:00:01+00:00",
            "sha": "abc123",
        }


class TestInvocationPathFormat:
    def test_path_is_invocation_id_only(self, tmp_path: Path) -> None:
        """Filename must be <invocation_id>.jsonl — NOT <profile_id>-<invocation_id>.jsonl."""
        writer = InvocationWriter(tmp_path)
        path = writer.invocation_path(_INVOCATION_ID)
        assert path.name == f"{_INVOCATION_ID}.jsonl"
        # Confirm there is no profile_id prefix
        assert "implementer" not in path.name


def test_append_correlation_rejects_embedded_started_id_mismatch(
    tmp_path: Path,
) -> None:
    writer = InvocationWriter(tmp_path)
    path = tmp_path / EVENTS_DIR / f"{_INVOCATION_ID}.jsonl"
    path.parent.mkdir()
    path.write_text(
        _make_started(_INVOCATION_ID_2).to_jsonl_line() + "\n",
        encoding="utf-8",
    )

    with pytest.raises(InvocationError, match="identity mismatch"):
        writer.append_correlation_link(_INVOCATION_ID, ref="spec.md")

    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
