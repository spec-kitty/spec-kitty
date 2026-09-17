"""Regression: mission-state repair anchors on the PRIMARY checkout (#2320).

``doctor mission-state --fix`` is a repo-level canonicalization. When it is
invoked from inside a worktree (a coordination or lane worktree), the raw
invocation root points at that worktree. Before the #2320 fold, ``repair_repo``
operated on whatever checkout it was handed, which produced the two symptoms the
issue witnessed live:

* **Mechanism 1 — drift never converges.** The materialize step re-wrote
  ``status.json`` inside the *worktree*, leaving the PRIMARY checkout's
  ``status.json`` frozen. A follow-up ``--audit`` (which reads the primary)
  therefore still reported the same ``SNAPSHOT_DRIFT`` blocker.
* **Mechanism 2 — writes into a stale coord worktree.** The repair left
  uncommitted changes (``status.json`` / ``status.events.jsonl`` / ``.kittify/``)
  inside a coordination worktree that should never have been mutated.

The fix re-anchors ``repair_repo`` to the canonical primary main-checkout via
the single worktree-pointer parser, so repair always targets the primary
``kitty-specs/<slug>`` and never touches ``.worktrees/``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.audit.classifiers.status_json import classify_status_json
from specify_cli.migration.mission_state import repair_repo

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_ID = "01KWNP7Q8R9TVWXY2Z3A4B5C00"
_SLUG = "decompose-merge-god-module"

# Canonical lifecycle: a WP walked all the way to ``done`` in the event log,
# while the persisted status.json is frozen at ``planned`` (the live #2320
# shape: "status.json frozen at event 11/88 — all WPs done in the log,
# planned in the snapshot"). Realistic 26-char Crockford ULID event ids +
# canonical 5.x lane vocabulary.
_LANES = ["planned", "claimed", "in_progress", "for_review", "in_review", "approved", "done"]
_EVENT_IDS = [
    "01KWNP7Q8R9TVWXY2Z3A4B5C6D",
    "01KWNP7Q8R9TVWXY2Z3A4B5C7E",
    "01KWNP7Q8R9TVWXY2Z3A4B5C8F",
    "01KWNP7Q8R9TVWXY2Z3A4B5C9G",
    "01KWNP7Q8R9TVWXY2Z3A4B5CAH",
    "01KWNP7Q8R9TVWXY2Z3A4B5CBJ",
]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _lane_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, (from_lane, to_lane) in enumerate(zip(_LANES, _LANES[1:], strict=False)):
        rows.append(
            {
                "actor": "claude-code",
                "at": f"2026-07-03T10:00:{index + 1:02d}+00:00",
                "event_id": _EVENT_IDS[index],
                "execution_mode": "worktree",
                "force": False,
                "from_lane": from_lane,
                "to_lane": to_lane,
                "mission_id": _MISSION_ID,
                "mission_slug": _SLUG,
                "wp_id": "WP01",
            }
        )
    # WP02 stays "planned" (never transitions) so the reducer's authoritative
    # snapshot is NOT all-WPs-done -- this mission is a live, in-development
    # worktree with a stale primary snapshot, not a completed/archived
    # dossier, so the #2320 regression must keep exercising the hard
    # SNAPSHOT_DRIFT/ERROR path (the corpus-tolerance fix's
    # SNAPSHOT_DRIFT_TERMINAL/WARNING downgrade is for archived, all-done
    # missions only).
    rows.append(
        {
            "actor": "claude-code",
            "at": "2026-07-03T10:00:00+00:00",
            "event_id": "01KWNP7Q8R9TVWXY2Z3A4B5C5C",
            "execution_mode": "worktree",
            "force": False,
            "from_lane": "planned",
            "to_lane": "planned",
            "mission_id": _MISSION_ID,
            "mission_slug": _SLUG,
            "wp_id": "WP02",
        }
    )
    return rows


def _seed_mission(root: Path) -> Path:
    """Seed a flattened mission with SNAPSHOT_DRIFT (log reaches done, snapshot planned)."""
    mission = root / "kitty-specs" / _SLUG
    mission.mkdir(parents=True)
    (mission / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": _SLUG,
                "mission_id": _MISSION_ID,
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-07-03T10:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (mission / "status.events.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in _lane_rows()), encoding="utf-8"
    )
    # Frozen / stale snapshot — the drift the audit flags. WP02 is already
    # correctly "planned" here (it never advances); only WP01 is stale.
    (mission / "status.json").write_text(
        json.dumps(
            {
                "summary": {"planned": 2},
                "work_packages": {
                    "WP01": {"lane": "planned"},
                    "WP02": {"lane": "planned"},
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return mission


def _make_primary_with_coord_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """Return (primary_mission_dir, coord_worktree_root) for a repo with drift."""
    primary = tmp_path / "primary"
    primary.mkdir()
    _git(primary, "init", "-q", "-b", "main")
    _git(primary, "config", "user.email", "repair-test@spec-kitty.test")
    _git(primary, "config", "user.name", "repair test")
    primary_mission = _seed_mission(primary)
    _git(primary, "add", ".")
    _git(primary, "commit", "-q", "-m", "baseline")

    coord = tmp_path / f"{_SLUG}-coord"
    _git(primary, "worktree", "add", "-q", "-b", f"kitty/mission-{_SLUG}-coord", str(coord))
    return primary_mission, coord


def test_repair_from_worktree_materializes_primary_status_json(tmp_path: Path) -> None:
    """M1: invoked from a worktree, --fix must clear SNAPSHOT_DRIFT on the PRIMARY.

    Before the fold the materialize step ran against the worktree, so the primary
    stayed frozen and a re-audit still flagged the same blocker.
    """
    primary_mission, coord = _make_primary_with_coord_worktree(tmp_path)

    before = classify_status_json(primary_mission)
    assert any(f.code == "SNAPSHOT_DRIFT" for f in before), (
        "fixture must start with the drift the issue describes"
    )

    # Invoke exactly as a CWD-inside-a-worktree run resolves the root.
    repair_repo(coord, allow_dirty=True)

    after = classify_status_json(primary_mission)
    assert not any(f.code == "SNAPSHOT_DRIFT" for f in after), (
        f"repair must re-materialize the PRIMARY status.json; residual findings: {after}"
    )
    summary = json.loads((primary_mission / "status.json").read_text(encoding="utf-8"))["summary"]
    assert summary["done"] == 1
    assert summary["planned"] == 1


def test_repair_from_worktree_leaves_coord_worktree_clean(tmp_path: Path) -> None:
    """M2: --fix must not write into the coordination worktree it was invoked from."""
    _primary_mission, coord = _make_primary_with_coord_worktree(tmp_path)
    coord_mission = coord / "kitty-specs" / _SLUG
    coord_status_before = (coord_mission / "status.json").read_text(encoding="utf-8")

    repair_repo(coord, allow_dirty=True)

    porcelain = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=coord,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert porcelain.strip() == "", (
        f"repair must not dirty the coord worktree; porcelain: {porcelain!r}"
    )
    assert (coord_mission / "status.json").read_text(encoding="utf-8") == coord_status_before
    # Belt-and-suspenders: no quarantine/manifest artifacts leaked into the worktree.
    assert not (coord / ".kittify").exists()
