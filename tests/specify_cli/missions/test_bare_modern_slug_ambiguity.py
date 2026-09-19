"""Regression coverage for #4723: a bare human slug matching >1 mission must
raise :class:`MissionSelectorAmbiguous`, never collapse to ``MISSION_NOT_FOUND``.

``resolve_bare_modern_mission_dir_name`` globs ``kitty-specs/<slug>-*/meta.json``
for the composed ``<slug>-<mid8>`` primary directory a bare human slug names.
Before this fix, ``len(matches) != 1`` covered BOTH the zero-match (genuinely
unknown handle) and the multi-match (ambiguous handle) cases with the same
``return None`` — so an operator who typed ``--mission payment`` when both
``payment-01M2TM6J`` and ``payment-01M2TM6M`` existed was told the mission did
not exist at all, instead of being told which two it could be (C-CTX-4 / C-009
no-silent-fallback contract).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.missions._read_path_resolver import (
    MISSION_AMBIGUOUS_SELECTOR_CODE,
    MissionSelectorAmbiguous,
    resolve_bare_modern_mission_dir_name,
)

pytestmark = [pytest.mark.fast]


def _seed_composed_mission(tmp_path: Path, *, slug: str, mid8: str, mission_id: str) -> Path:
    """Create ``kitty-specs/<slug>-<mid8>/meta.json`` (composed primary dir)."""
    dir_name = f"{slug}-{mid8}"
    mission_dir = tmp_path / "kitty-specs" / dir_name
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": mission_id, "mission_slug": dir_name}),
        encoding="utf-8",
    )
    return mission_dir


def test_bare_slug_matching_two_missions_raises_ambiguous(tmp_path: Path) -> None:
    """#4723: two composed dirs sharing a bare human slug raise
    MissionSelectorAmbiguous — not a silent ``None`` (which callers render as
    MISSION_NOT_FOUND)."""
    _seed_composed_mission(
        tmp_path,
        slug="payment",
        mid8="01M2TM6J",
        mission_id="01M2TM6JABCDEFGHJKMNPQRSTV",
    )
    _seed_composed_mission(
        tmp_path,
        slug="payment",
        mid8="01M2TM6M",
        mission_id="01M2TM6MABCDEFGHJKMNPQRSTV",
    )

    with pytest.raises(MissionSelectorAmbiguous) as excinfo:
        resolve_bare_modern_mission_dir_name(tmp_path, "payment")

    assert excinfo.value.error_code == MISSION_AMBIGUOUS_SELECTOR_CODE
    assert excinfo.value.handle == "payment"
    assert set(excinfo.value.candidates) == {
        "payment-01M2TM6J",
        "payment-01M2TM6M",
    }


def test_bare_slug_matching_zero_missions_still_returns_none(tmp_path: Path) -> None:
    """The zero-match leg is unchanged: a genuinely unknown bare slug still
    declines with ``None`` (the caller's existing not-found handling)."""
    (tmp_path / "kitty-specs").mkdir(parents=True)

    assert resolve_bare_modern_mission_dir_name(tmp_path, "no-such-mission") is None


def test_bare_slug_matching_one_mission_still_resolves(tmp_path: Path) -> None:
    """The single-match leg is unchanged: an unambiguous bare slug resolves to
    the composed dir name exactly as before."""
    _seed_composed_mission(
        tmp_path,
        slug="invoicing",
        mid8="01M2TM7A",
        mission_id="01M2TM7AABCDEFGHJKMNPQRSTV",
    )

    assert resolve_bare_modern_mission_dir_name(tmp_path, "invoicing") == "invoicing-01M2TM7A"
