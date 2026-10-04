"""Regression: `OSError`/`PermissionError` must not leak through fail-closed
``meta.json`` readers that are documented as "never raises" / "tolerates
absence or corruption".

WP07/WP08/WP09 (closing #3140) narrowed several `except Exception` /
`except (ValueError, OSError)` catches down to `except MissionMetaReadError`
only. ``load_meta_fail_closed`` (``core/paths.py``) wraps *only* the
``ValueError`` its own JSON-parsing path can raise -- it does NOT catch an
``OSError`` raised by the filesystem probe itself
(``Path.exists()``/``.read_text()``). Concretely: ``mission_metadata.load_meta``
calls ``meta_path.exists()`` *before* entering its own try/except -- when the
mission directory itself is unreadable (a directory the process cannot
probe, not an unreadable file), ``Path.exists()`` re-raises ``PermissionError`` instead of
swallowing it (``pathlib`` only swallows ``ENOENT``/``ENOTDIR``/... , not
``EACCES``). That raw ``PermissionError`` then propagates through every
caller whose narrowed ``except MissionMetaReadError`` does not also catch
``OSError``, contradicting those callers' own docstrings.

Each site below is fixed to catch ``(OSError, MissionMetaReadError)``,
matching the pattern already used correctly at
``status/identity_audit.py::classify_mission`` and
``status/store.py::EventStore._mission_id_for_slug`` (both
``except (OSError, MissionMetaReadError)``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests._support.eacces import deny_path_method

pytestmark = [pytest.mark.unit]


def _make_unreadable_mission_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str = "mission"
) -> Path:
    """A mission directory containing a valid meta.json that cannot be probed.

    The denial is injected at the filesystem-probe seam (``Path.exists`` and
    the ``Path`` read methods raise ``PermissionError`` for ``meta.json``)
    rather than via ``chmod(0)`` on the DIRECTORY: root bypasses file mode
    bits, so a chmod-based setup gave a different verdict per uid (#5622).
    Making ``Path.exists()`` itself raise ``PermissionError`` is what
    reproduces the actual defect -- it fires before any JSON-parsing
    try/except is reached; denying only the read would be caught already by
    the JSON-parsing layer's ``except (json.JSONDecodeError, OSError)``.
    """
    mission_dir = tmp_path / name
    mission_dir.mkdir()
    meta_path = mission_dir / "meta.json"
    meta_path.write_text(json.dumps({"mission_id": "01JPROBEUNREADABLEDIRXXXX"}), encoding="utf-8")

    for attr in ("exists", "read_text", "read_bytes"):
        deny_path_method(monkeypatch, attr, meta_path)
    return mission_dir


@pytest.fixture
def unreadable_mission_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return _make_unreadable_mission_dir(tmp_path, monkeypatch)


class TestMetaReadPermissionDeniedRegression:
    """One case per remediated call site (PR #3155 landing fold)."""

    def test_load_meta_fail_closed_itself_raises_raw_permission_error(
        self, unreadable_mission_dir: Path
    ) -> None:
        """Sanity check that the underlying defect is real: the public
        fail-closed reader raises a RAW ``PermissionError``, not the typed
        ``MissionMetaReadError`` its docstring promises for "unreadable".

        This pins the premise for every test below -- if this ever stops
        raising raw ``OSError``, the call-site fixes should be revisited.
        """
        from specify_cli.core.paths import load_meta_fail_closed

        with pytest.raises(PermissionError):
            load_meta_fail_closed(unreadable_mission_dir)

    def test_workflow_load_coord_branch_meta_never_raises(
        self, unreadable_mission_dir: Path
    ) -> None:
        """``agent/workflow.py::_load_coord_branch_meta`` docstring: "Never raises."."""
        from specify_cli.cli.commands.agent.workflow import _load_coord_branch_meta

        assert _load_coord_branch_meta(unreadable_mission_dir) == (None, None, None)

    def test_mission_type_safe_load_meta_tolerates_unreadable_dir(
        self, unreadable_mission_dir: Path
    ) -> None:
        """``mission_type.py::_safe_load_meta`` docstring: tolerates absence/corruption."""
        from specify_cli.cli.commands.mission_type import _safe_load_meta

        assert _safe_load_meta(unreadable_mission_dir) is None

    def test_implement_load_fallback_mission_meta_tolerates_unreadable_dir(
        self, unreadable_mission_dir: Path
    ) -> None:
        """``implement.py::_load_fallback_mission_meta`` -- FR-003 cascade layer 2.

        Previously carried ``except Exception  # meta missing/corrupt is
        legacy`` before the WP07-09 migration narrowed it.
        """
        from specify_cli.cli.commands.implement import _load_fallback_mission_meta

        assert _load_fallback_mission_meta(unreadable_mission_dir) is None

    def test_normalize_mission_lifecycle_records_error_without_raising(
        self, unreadable_mission_dir: Path
    ) -> None:
        """``normalize_mission_lifecycle.py::_load_meta_for_normalization``.

        Previous comment: "keep one broken mission from aborting the run" --
        the whole point of the try/except is that ONE unreadable mission must
        not blow up the batch. Confirms the function returns ``None`` and
        records a per-mission error rather than letting the caller's loop
        crash.
        """
        from specify_cli.migration.normalize_mission_lifecycle import (
            NormalizeMissionLifecycleResult,
            _load_meta_for_normalization,
        )

        result = NormalizeMissionLifecycleResult(slug=unreadable_mission_dir.name, status="ok")

        meta = _load_meta_for_normalization(unreadable_mission_dir, result)

        assert meta is None
        assert result.status == "error"
        assert result.error is not None
        assert "meta.json" in result.error
