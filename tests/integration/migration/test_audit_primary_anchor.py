"""Regression: ``doctor mission-state --audit`` anchors on the PRIMARY checkout.

#2320 re-anchored the ``--fix`` path to the canonical primary main-checkout
(inside ``repair_repo`` → ``_anchor_repair_root`` → ``resolve_canonical_root``),
but the read-only ``--audit`` path resolved its root through
``locate_project_root`` — a *conditional* anchor that stops at the CWD's
worktree. From a non-primary cwd (a coordination / lane worktree) audit and fix
therefore diverged: fix wrote the primary while audit could read a stale
worktree, so a fixed mission still audited as broken (and vice-versa).

The alphonso MINOR-a fold unifies both on the SAME authority at the
``run_mission_state`` seam, so audit and fix resolve to the identical canonical
root from any cwd. These tests exercise that seam through a real git worktree.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.core.paths import resolve_canonical_root

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_ID = "01KWNPA0Q8R9TVWXY2Z3A4B5C0"
_SLUG = "audit-anchor-mission"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _seed_mission(root: Path) -> Path:
    mission = root / "kitty-specs" / _SLUG
    mission.mkdir(parents=True)
    (mission / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": _SLUG,
                "mission_id": _MISSION_ID,
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-07-04T10:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (mission / "status.events.jsonl").write_text(
        json.dumps(
            {
                "actor": "claude-code",
                "at": "2026-07-04T10:00:01+00:00",
                "event_id": "01KWNPA0Q8R9TVWXY2Z3A4B5C6",
                "execution_mode": "worktree",
                "force": False,
                "from_lane": "planned",
                "to_lane": "claimed",
                "mission_id": _MISSION_ID,
                "mission_slug": _SLUG,
                "wp_id": "WP01",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return mission


def _make_primary_with_coord_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """Return (primary_root, coord_worktree_root)."""
    primary = tmp_path / "primary"
    primary.mkdir()
    _git(primary, "init", "-q", "-b", "main")
    _git(primary, "config", "user.email", "audit-test@spec-kitty.test")
    _git(primary, "config", "user.name", "audit test")
    _seed_mission(primary)
    _git(primary, "add", ".")
    _git(primary, "commit", "-q", "-m", "baseline")

    coord = tmp_path / f"{_SLUG}-coord"
    _git(primary, "worktree", "add", "-q", "-b", f"kitty/mission-{_SLUG}-coord", str(coord))
    return primary.resolve(), coord


def test_audit_from_worktree_anchors_on_primary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Invoked from a worktree, ``--audit`` must resolve the canonical PRIMARY
    root — the same root ``--fix`` uses — not the worktree it was invoked from.

    A spy on the audit engine captures the ``repo_root`` the audit actually runs
    against. Before the fold that root was the worktree; after it is the primary
    (== ``resolve_canonical_root(coord)``), so audit and fix agree.
    """
    from specify_cli.cli.commands import _mission_state_doctor as mod

    primary_root, coord = _make_primary_with_coord_worktree(tmp_path)

    captured: dict[str, Path] = {}
    import specify_cli.audit as audit_mod

    real_run_audit = audit_mod.run_audit

    def _spy(options: object) -> object:
        captured["root"] = options.repo_root  # type: ignore[attr-defined]
        return real_run_audit(options)  # type: ignore[arg-type]

    monkeypatch.setattr(audit_mod, "run_audit", _spy)

    mod.run_mission_state(
        audit=True,
        fix=False,
        json_output=True,
        mission=None,
        fail_on=None,
        fixture_dir=None,
        include_fixtures=False,
        manifest_path=None,
        allow_dirty=False,
        repo_root=coord,
    )

    expected = resolve_canonical_root(coord)
    assert captured["root"] == expected == primary_root, (
        "audit must anchor on the canonical primary root (matching --fix), "
        f"got {captured.get('root')!r}; expected {primary_root!r}"
    )
