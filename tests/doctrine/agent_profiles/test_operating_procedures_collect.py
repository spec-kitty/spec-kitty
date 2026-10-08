"""``collect_operating_procedure_entries`` is the single falsy-filter authority.

Three consumers (DRG extractor, ``doctor charter-packs`` collector, architectural
gate) harvest the ``collaboration.operating-procedures`` field. This test pins
the one policy they now share: falsy entries (e.g. an authored ``""``) are
dropped, and a profile with no field maps to an empty list — so the harvest can
never diverge one layer up (C-004 single-authority drift).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.agent_profiles.operating_procedures import (
    collect_operating_procedure_entries,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


def _write_profile(profiles_dir: Path, stem: str, body: str) -> None:
    (profiles_dir / f"{stem}.agent.yaml").write_text(body, encoding="utf-8")


def test_falsy_entries_dropped_and_missing_field_is_empty(tmp_path: Path) -> None:
    profiles_dir = tmp_path / "agent_profiles"
    profiles_dir.mkdir()
    _write_profile(
        profiles_dir,
        "has-ops",
        'profile-id: has-ops\ncollaboration:\n  operating-procedures:\n    - ""\n    - real-id\n',
    )
    _write_profile(
        profiles_dir,
        "no-ops",
        "profile-id: no-ops\nname: No Ops\n",
    )

    entries = collect_operating_procedure_entries(profiles_dir)

    # Empty string dropped by the single falsy-filter policy; real id kept.
    assert entries["has-ops"] == ["real-id"]
    # Profile with no operating-procedures field maps to an empty list.
    assert entries["no-ops"] == []


def test_missing_directory_returns_empty_mapping(tmp_path: Path) -> None:
    assert collect_operating_procedure_entries(tmp_path / "absent") == {}
