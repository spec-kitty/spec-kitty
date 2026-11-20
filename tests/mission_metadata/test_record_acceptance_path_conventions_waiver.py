"""History recording of the per-run path-conventions waiver (#7566, FR-009).

``accept --waive-path-conventions --waive-reason "<why>"`` records
``path_conventions_waived: {"reason": ...}`` on the acceptance history entry,
beside the #7356 ``lenient`` marker. Without a reason the entry shape is
unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specify_cli.mission_metadata import record_acceptance

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_meta(feature_dir: Path) -> None:
    meta: dict[str, Any] = {
        "mission_number": "051",
        "slug": "051-canonical-state-authority",
        "mission_slug": "051-canonical-state-authority",
        "friendly_name": "Canonical State Authority",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-03-18T00:00:00+00:00",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_waiver_reason_is_recorded_stripped(tmp_path: Path) -> None:
    _write_meta(tmp_path)
    result = record_acceptance(tmp_path, accepted_by="claude", mode="local", path_conventions_waiver_reason="  layout migration  ")
    assert result["acceptance_history"][-1]["path_conventions_waived"] == {"reason": "layout migration"}


def test_no_reason_keeps_the_entry_shape(tmp_path: Path) -> None:
    _write_meta(tmp_path)
    result = record_acceptance(tmp_path, accepted_by="claude", mode="local")
    assert "path_conventions_waived" not in result["acceptance_history"][-1]


def test_waiver_and_lenient_are_recorded_together(tmp_path: Path) -> None:
    _write_meta(tmp_path)
    result = record_acceptance(tmp_path, accepted_by="claude", mode="local", lenient=True, path_conventions_waiver_reason="why")
    entry = result["acceptance_history"][-1]
    assert entry["lenient"] is True
    assert entry["path_conventions_waived"] == {"reason": "why"}
