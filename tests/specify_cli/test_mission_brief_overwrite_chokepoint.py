"""#4921 regression: ``write_mission_brief`` must refuse a destructive overwrite
at the chokepoint, not rely on duplicated CLI gates.

The RED-first arm below (``test_default_call_refuses_and_preserves_bytes``)
must witness the actual DESTROYER on the base branch — an unconditional
overwrite that silently replaces an existing brief's bytes — not a
``TypeError`` from a missing keyword argument. It calls ``write_mission_brief``
using the base (pre-fix) call shape: no ``overwrite`` kwarg at all. On base,
that call succeeds and clobbers the file; ``pytest.raises(BriefExistsError)``
then fails with "DID NOT RAISE", which is the RED this test captures. After
the fix lands, the same call (now defaulting ``overwrite=False``) refuses and
preserves the original bytes — GREEN.

The second arm (brief-only, sidecar-absent) proves the deeper #4910 class:
existence of ``mission-brief.md`` ALONE — independent of the provenance
sidecar — must trigger the refusal, and the refusal must fire BEFORE the
XOR partial-state cleanup unlinks the lone brief file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.mission_brief import (
    BRIEF_SOURCE_FILENAME,
    MISSION_BRIEF_FILENAME,
    BriefExistsError,
    write_mission_brief,
)

pytestmark = [pytest.mark.regression, pytest.mark.unit]


def _brief_path(repo_root: Path) -> Path:
    return repo_root / ".kittify" / MISSION_BRIEF_FILENAME


def _source_path(repo_root: Path) -> Path:
    return repo_root / ".kittify" / BRIEF_SOURCE_FILENAME


# ---------------------------------------------------------------------------
# RED-on-base arm: witnesses the unconditional-overwrite destroyer (#4921).
# ---------------------------------------------------------------------------


def test_default_call_refuses_and_preserves_bytes(tmp_path: Path) -> None:
    """#4921: a second write_mission_brief call with no overwrite kwarg must
    refuse (post-fix default overwrite=False), not silently clobber."""
    write_mission_brief(tmp_path, "# Original Content", "source-a.md")
    original_bytes = _brief_path(tmp_path).read_bytes()

    with pytest.raises(BriefExistsError):
        write_mission_brief(tmp_path, "# Replacement Content", "source-b.md")

    assert _brief_path(tmp_path).read_bytes() == original_bytes


# ---------------------------------------------------------------------------
# Brief-only (sidecar-absent) arm: the #4910 regression class, keyed on
# existence alone, evaluated before the XOR cleanup.
# ---------------------------------------------------------------------------


def test_brief_only_sidecar_absent_refuses_before_xor_cleanup(tmp_path: Path) -> None:
    """A brief present with NO provenance sidecar is unknown provenance; the
    refusal must fire BEFORE the XOR would unlink-then-rewrite it (#4910)."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    brief_path = kittify / MISSION_BRIEF_FILENAME
    brief_path.write_text("# HAND-WRITTEN BRIEF", encoding="utf-8")
    # No brief-source.yaml on purpose: sidecar-absent, brief-only state.

    with pytest.raises(BriefExistsError):
        write_mission_brief(tmp_path, "# New Content", "source.md", overwrite=False)

    assert brief_path.read_text(encoding="utf-8") == "# HAND-WRITTEN BRIEF"
    assert not _source_path(tmp_path).exists()


# ---------------------------------------------------------------------------
# GREEN-side arms: authorized overwrite proceeds; orphan-sidecar recovery
# (brief absent, sidecar present) is untouched by the new gate.
# ---------------------------------------------------------------------------


def test_overwrite_true_replaces_existing_brief(tmp_path: Path) -> None:
    write_mission_brief(tmp_path, "# Original Content", "source-a.md")

    write_mission_brief(tmp_path, "# Replacement Content", "source-b.md", overwrite=True)

    assert "Replacement Content" in _brief_path(tmp_path).read_text(encoding="utf-8")


def test_orphan_sidecar_no_brief_still_recovers(tmp_path: Path) -> None:
    """Sidecar present, brief ABSENT is genuine partial state — recovery must
    proceed even with the new existence-gate in place (overwrite=False)."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / BRIEF_SOURCE_FILENAME).write_text("stale: sidecar", encoding="utf-8")

    brief_path, source_path = write_mission_brief(tmp_path, "# Fresh Content", "source.md")

    assert brief_path.exists()
    assert "Fresh Content" in brief_path.read_text(encoding="utf-8")
    assert source_path.exists()
