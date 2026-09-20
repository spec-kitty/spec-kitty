"""WP01 — repair normalizes a legacy non-``bulk_edit`` ``change_mode`` (FR-001/002/003).

``spec-kitty doctor mission-state --fix`` used to abort a mission whose
``meta.json`` carried a non-canonical ``change_mode`` (e.g. the retired
``regular`` value): ``validate_meta`` returned an error and ``_canonicalize_meta``
raised ``ValueError``, so the mission was reported ``error`` and never healed.

After WP01 the repair NORMALIZES such a value to ABSENT during canonicalization
(before validation), counting the mission ``updated`` and recording
``normalized_change_mode:{old_value}`` in the result's ``meta_actions`` — exit 0,
no ``ValueError`` (SC-001). The dropped value is captured in the action tag
itself (fidelity, #4780), mirroring ``removed_meta_key:{key}``. Re-running
yields no second diff (NFR-002, SC-005), and any non-canonical value — not just
``regular`` — is healed identically (FR-011).

Tactic references:
- ``acceptance-test-first`` / ``atdd-adversarial-acceptance``: the failing
  acceptance test is authored before the production change.
- ``function-over-form-testing``: assert the observable repair outcome (status,
  persisted meta.json, recorded action), not implementation structure.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.audit.shape_registry import (
    KNOWN_TOP_LEVEL_KEYS_BY_ARTIFACT,
    META_COORDINATION_KEYS,
)
from specify_cli.migration.mission_state import repair_repo

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "legacy-change-mode-mission"
_MISSION_ID = "01KWNP7Q8R9TVWXY2Z3A4B5C00"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _seed_mission(root: Path, *, change_mode: object) -> Path:
    """Seed a flat mission whose meta.json carries a non-canonical ``change_mode``."""
    mission = root / "kitty-specs" / _SLUG
    mission.mkdir(parents=True)
    meta: dict[str, object] = {
        "slug": _SLUG,
        "mission_slug": _SLUG,
        "friendly_name": "Legacy change_mode mission",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-07-03T10:00:00+00:00",
        "mission_id": _MISSION_ID,
        "change_mode": change_mode,
    }
    (mission / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return mission


def _init_repo(tmp_path: Path, *, change_mode: object) -> tuple[Path, Path]:
    """Return (primary_root, mission_dir) for a committed repo with the seed."""
    primary = tmp_path / "primary"
    primary.mkdir()
    _git(primary, "init", "-q", "-b", "main")
    _git(primary, "config", "user.email", "wp01-test@spec-kitty.test")
    _git(primary, "config", "user.name", "wp01 test")
    mission = _seed_mission(primary, change_mode=change_mode)
    _git(primary, "add", ".")
    _git(primary, "commit", "-q", "-m", "baseline")
    return primary, mission


def test_repair_normalizes_regular_change_mode(tmp_path: Path) -> None:
    """A ``change_mode: regular`` mission is repaired (updated), not aborted (error)."""
    primary, mission = _init_repo(tmp_path, change_mode="regular")

    # Must NOT raise a ValueError — the repair heals instead of aborting.
    report = repair_repo(primary)

    result = next(m for m in report.missions if m.mission_slug == _SLUG)
    assert result.status == "updated", (
        f"expected the legacy change_mode mission to be repaired, got {result.status!r} with validation_errors={result.validation_errors!r}"
    )
    assert result.validation_errors == []
    assert "normalized_change_mode:regular" in result.meta_actions

    persisted = json.loads((mission / "meta.json").read_text(encoding="utf-8"))
    assert "change_mode" not in persisted

    summary = report.to_dict()["summary"]
    assert isinstance(summary, dict)
    assert summary["missions_error"] == 0
    assert summary["missions_updated"] == 1


def test_repair_normalization_is_idempotent(tmp_path: Path) -> None:
    """NFR-002 / SC-005: a second ``repair_repo`` run makes no further change."""
    primary, mission = _init_repo(tmp_path, change_mode="regular")

    first = repair_repo(primary)
    first_result = next(m for m in first.missions if m.mission_slug == _SLUG)
    assert first_result.status == "updated"

    # Commit the healed tree so the second run starts from a clean checkout.
    _git(primary, "add", ".")
    _git(primary, "commit", "-q", "-m", "post-repair")

    second = repair_repo(primary)
    second_result = next(m for m in second.missions if m.mission_slug == _SLUG)
    assert second_result.status == "unchanged"
    assert second_result.meta_actions == []
    assert second.to_dict()["summary"]["missions_updated"] == 0  # type: ignore[index]

    persisted = json.loads((mission / "meta.json").read_text(encoding="utf-8"))
    assert "change_mode" not in persisted


@pytest.mark.parametrize(
    "change_mode",
    [
        "regular",
        "yolo",
        "",
        42,
        None,
        ["bulk_edit"],
    ],
)
def test_repair_normalizes_any_non_canonical_change_mode(tmp_path: Path, change_mode: object) -> None:
    """FR-011: every non-``bulk_edit`` value — string or malformed — is healed."""
    primary, mission = _init_repo(tmp_path, change_mode=change_mode)

    report = repair_repo(primary)

    result = next(m for m in report.missions if m.mission_slug == _SLUG)
    assert result.status == "updated"
    assert f"normalized_change_mode:{change_mode}" in result.meta_actions
    persisted = json.loads((mission / "meta.json").read_text(encoding="utf-8"))
    assert "change_mode" not in persisted


def test_repair_preserves_bulk_edit_change_mode(tmp_path: Path) -> None:
    """The canonical ``bulk_edit`` value is preserved, never normalized away."""
    primary, mission = _init_repo(tmp_path, change_mode="bulk_edit")

    report = repair_repo(primary)

    result = next(m for m in report.missions if m.mission_slug == _SLUG)
    assert not any(action.startswith("normalized_change_mode") for action in result.meta_actions)
    persisted = json.loads((mission / "meta.json").read_text(encoding="utf-8"))
    assert persisted["change_mode"] == "bulk_edit"


def test_fix_repairs_without_registry_edit(tmp_path: Path) -> None:
    """FR-010 / SC-004: --fix now heals a legacy change_mode, and the audit shape
    registry needs no ``change_mode`` entry to agree it is repairable.

    ``change_mode`` is a *writer-schema* key (``MissionMetaOptional``), so it is
    already a known audit key derived from the writer — NOT a bespoke registry
    addition. This test guards that the fix path did not (and need not) add a
    hardcoded ``change_mode`` entry to ``audit/shape_registry.py``.
    """
    primary, _mission = _init_repo(tmp_path, change_mode="regular")

    report = repair_repo(primary)
    result = next(m for m in report.missions if m.mission_slug == _SLUG)
    assert result.status == "updated"

    known = KNOWN_TOP_LEVEL_KEYS_BY_ARTIFACT["meta.json"]
    # change_mode is known (writer-derived), so it is never UNKNOWN_SHAPE...
    assert "change_mode" in known
    # ...but it must NOT have been added as a bespoke non-writer registry entry.
    assert "change_mode" not in META_COORDINATION_KEYS


def test_error_after_meta_write_still_reports_normalized_action(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Report-fidelity (#4780): if a later repair step raises AFTER the
    normalized meta.json was written, the error result must still record the
    ``normalized_change_mode`` action that actually occurred on disk — not drop
    it to an empty ``meta_actions``.

    Reproduces the reviewer's non-blocking edge case by seeding an events file
    (so the status branch runs) and forcing the row canonicalizer to raise
    after the meta write has already persisted the normalization.
    """
    import specify_cli.migration.mission_state as ms

    primary, mission = _init_repo(tmp_path, change_mode="regular")
    # Presence of an events file makes _repair_mission enter the status branch,
    # where the injected failure fires — after the meta write above it. Commit
    # it so repair_repo does not refuse a dirty relevant path.
    (mission / "status.events.jsonl").write_text("", encoding="utf-8")
    _git(primary, "add", ".")
    _git(primary, "commit", "-q", "-m", "seed events file")

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected failure after meta write")

    monkeypatch.setattr(ms, "_canonicalize_status_rows", _boom)

    report = repair_repo(primary)

    result = next(m for m in report.missions if m.mission_slug == _SLUG)
    assert result.status == "error"
    assert any("injected failure" in e for e in result.validation_errors)
    # The persisted normalization must still be reported, not silently dropped.
    assert "normalized_change_mode:regular" in result.meta_actions
    persisted = json.loads((mission / "meta.json").read_text(encoding="utf-8"))
    assert "change_mode" not in persisted
