"""Direct tests for ``refresh_snapshot_if_present`` (#5862, #5869).

The helper runs after a backfill has already committed its append, so it must
never create a snapshot and must report every per-Mission read failure instead
of raising.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.core.paths import MissionMetaReadError
from specify_cli.migration import snapshot_refresh
from specify_cli.migration.snapshot_refresh import refresh_snapshot_if_present
from specify_cli.status import StoreError

pytestmark = pytest.mark.unit


def test_absent_snapshot_is_not_created(tmp_path: Path) -> None:
    assert refresh_snapshot_if_present(tmp_path) == (False, None)
    assert not (tmp_path / "status.json").exists()


def test_present_snapshot_is_rematerialized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "status.json").write_text(json.dumps({"stale": True}), encoding="utf-8")
    calls: list[Path] = []
    monkeypatch.setattr(snapshot_refresh, "materialize", calls.append)

    assert refresh_snapshot_if_present(tmp_path) == (True, None)
    assert calls == [tmp_path]


@pytest.mark.parametrize(
    "error",
    [
        StoreError("torn line"),
        OSError("disk full"),
        MissionMetaReadError(Path("meta.json"), ValueError("bad json")),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
    ],
    ids=["store", "os", "meta", "undecodable"],
)
def test_read_failure_is_reported_not_raised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    (tmp_path / "status.json").write_text("{}", encoding="utf-8")

    def _broken(_dir: Path) -> None:
        raise error

    monkeypatch.setattr(snapshot_refresh, "materialize", _broken)

    refreshed, message = refresh_snapshot_if_present(tmp_path)

    assert refreshed is False
    assert message is not None and type(error).__name__ in message
