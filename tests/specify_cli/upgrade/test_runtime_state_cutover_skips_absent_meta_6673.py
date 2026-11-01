"""#6673: the runtime-state cutover never stubs a ``meta.json`` for a Mission git already tracks.

The ``3.2.6rc1`` cutover walks every ``kitty-specs/`` child and flips its ``status_phase``.
:func:`~specify_cli.migration.runtime_state_cutover._flip_phase` writes a one-key
``{"status_phase": "1"}`` ``meta.json`` when the file is missing, which would hand a Mission
whose tracked ``meta.json`` is absent from the working tree an identity-less file that a later
``migrate backfill-identity`` mints into. ``cutover_mission`` therefore skips such a Mission before
its seed phase, which keeps the shipped ``3.2.6rc1`` migration module byte-identical (DIRECTIVE_044).

Proven on ``main`` before the fix: ``RuntimeStateBackfillMigration().apply()`` created
``{"status_phase": "1"}`` in a folder whose corrupt ``meta.json`` was tracked and deleted.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_zz_runtime_state_backfill import RuntimeStateBackfillMigration

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_REFUSED = "corrupt-mission-01CORRUP"
_CUT_OVER = "legacy-mission-01LEGACYM"
_WP_WITH_LANE = "---\nwork_package_id: WP01\ntitle: leftover\nlane: doing\n---\n# WP01\n"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def _build_project(root: Path) -> None:
    """A corrupt-tracked-absent Mission beside a legacy Mission that still needs the cutover."""
    root.mkdir(parents=True)
    (root / ".kittify").mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")

    refused = root / "kitty-specs" / _REFUSED
    refused.mkdir(parents=True)
    (refused / "meta.json").write_text("{not json\n", encoding="utf-8")
    (refused / "spec.md").write_text("# corrupt\n", encoding="utf-8")

    legacy = root / "kitty-specs" / _CUT_OVER
    (legacy / "tasks" / "doing").mkdir(parents=True)
    (legacy / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01LEGACYMZZZZZZZZZZZZZZZ",
                "mission_slug": _CUT_OVER,
                "slug": _CUT_OVER,
                "friendly_name": "legacy mission",
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (legacy / "spec.md").write_text("# legacy\n", encoding="utf-8")
    (legacy / "tasks" / "doing" / "WP01-x.md").write_text(_WP_WITH_LANE, encoding="utf-8")

    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    (refused / "meta.json").unlink()


def test_the_cutover_skips_a_mission_with_a_tracked_absent_meta(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    root = tmp_path / "proj"
    _build_project(root)
    refused = root / "kitty-specs" / _REFUSED

    with caplog.at_level(logging.WARNING):
        RuntimeStateBackfillMigration().apply(root)

    # The guard: no meta.json (and no event log) is written for the refused Mission.
    assert not (refused / "meta.json").exists(), "the cutover stubbed a meta.json for a tracked-absent Mission"
    assert not (refused / "status.events.jsonl").exists()
    assert any("meta.json" in record.getMessage() and _REFUSED in record.getMessage() for record in caplog.records), caplog.text
    # Positive control on the same fixture: the cutover still runs for the other Mission, so the
    # assertion above cannot pass because the walk never visits anything.
    assert (root / "kitty-specs" / _CUT_OVER / "meta.json").is_file()
    assert "status_phase" in json.loads((root / "kitty-specs" / _CUT_OVER / "meta.json").read_text(encoding="utf-8"))


def test_a_pre_identity_mission_with_no_meta_anywhere_is_not_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """The skip keys on *git tracking the path*; a folder git holds nothing for keeps the old behaviour."""
    root = tmp_path / "proj"
    _build_project(root)
    legacy = root / "kitty-specs" / _CUT_OVER
    (legacy / "meta.json").unlink()
    _git(root, "rm", "--cached", "-q", f"kitty-specs/{_CUT_OVER}/meta.json")
    _git(root, "commit", "-q", "-m", "drop the meta")

    with caplog.at_level(logging.WARNING):
        result = RuntimeStateBackfillMigration().apply(root)

    # No notice for the folder git holds no meta.json for: nothing to restore, nothing to refuse.
    assert not any(_CUT_OVER in record.getMessage() and "meta.json" in record.getMessage() for record in caplog.records), caplog.text
    assert result.success
