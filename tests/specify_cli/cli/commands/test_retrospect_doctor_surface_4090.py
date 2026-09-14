"""Track B red-first (#4090): retrospect and ``doctor mission-state`` disagree.

Post-merge reader divergence. After a real ``spec-kitty merge`` of a coord
mission, two partitions survive for the same mission:

* the **PRIMARY** partition (``kitty-specs/<slug>/``) — the merged record: every
  WP terminal (``done``), and — matching what a real merge produces on HEAD —
  **NO ``merged_at`` marker** on ``meta.json`` (its writer was deleted in #2258
  and never re-added);
* a diverged **COORD husk** (``.worktrees/<slug>-coord/kitty-specs/<slug>/``) —
  the stale pre-merge surface: the same WPs still recorded ``approved`` (never
  ``done``), no merge marker.

Two REAL readers resolve that state differently:

* ``retrospect create``'s completion check
  (:func:`retrospect._check_mission_completed` →
  :func:`retrospect._canonical_events_path` →
  :func:`coordination.surface_resolver.resolve_status_surface`) routes through
  the primary-wins guard ``_primary_mission_is_completed`` →
  ``is_mission_merged`` → ``meta.get("merged_at")``. With ``merged_at`` ABSENT
  the guard is dormant, so the resolver falls to the ``.worktrees`` husk
  short-circuit and reads the **stale coord** surface → sees the WPs
  non-terminal (``approved``) → raises ``MISSION_NOT_COMPLETED``.
* ``doctor mission-state`` re-anchors to the canonical primary checkout
  (:func:`migration.mission_state._anchor_repair_root`) and its read engine
  (:func:`audit.engine.run_audit`) scans ``<root>/kitty-specs`` — the **PRIMARY**
  partition, structurally never the ``.worktrees`` husk — where all 11 WPs are
  terminal.

Before WP04 the two readers DISAGREED (11 open on the husk vs 0 open / 11 terminal
on primary). WP04's fix — restoring the ``merged_at`` writer + a reopen-aware
``is_mission_merged`` — re-arms the primary-wins guard, so retrospect resolves the
same authoritative primary surface the doctor already reads and both agree.

Scope note: this test **constructs** the post-merge state (it hardcodes the
``merged_at`` absence rather than running a real ``spec-kitty merge`` — C-003
forbids dogfooding the coord merge here), so it guards the **resolver-agreement
contract** across both real readers. The complementary writer-regression guard —
that a real merge actually stamps ``merged_at`` (the #2258 re-deletion guard) —
lives in ``tests/specify_cli/status/test_merged_at_writer_and_reopen_4090.py``.
Post-WP04 this test PASSES (the ``xfail`` marker was removed at the green-flip).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.audit.engine import run_audit
from specify_cli.audit.models import AuditOptions
from specify_cli.cli.commands.retrospect import (
    _canonical_events_path,
    _check_mission_completed,
)
from specify_cli.context.mission_resolver import ResolvedMission
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.coordination.surface_resolver import resolve_status_surface
from specify_cli.migration.mission_state import _anchor_repair_root
from specify_cli.status import read_events
from specify_cli.status import reduce as reduce_events

pytestmark = [pytest.mark.fast]

_SLUG = "merged-4090-01KTDVHZ"
_MID = "01KTDVHZKGCHCW6HQ4V577PNES"
_MID8 = "01KTDVHZ"
_N_WPS = 11
_NON_TERMINAL_LANE = "approved"
_TERMINAL_LANE = "done"

# retrospect's own terminal set (``TERMINAL_LANES`` = frozenset{"done",
# "canceled"}): ``approved`` is NOT terminal for retrospect, which is exactly
# why the stale coord husk reads as incomplete.
_RETROSPECT_TERMINAL = frozenset({"done", "canceled"})

# Chain up to (and including) ``approved``; the primary partition appends
# ``done`` on top so its WPs are terminal.
_CHAIN = ["planned", "claimed", "in_progress", "for_review", "in_review", "approved"]


def _write_meta(mission_dir: Path, *, merged_at: str | None) -> None:
    """Write a coord mission ``meta.json``, optionally carrying ``merged_at``."""
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_slug": _SLUG,
        "mission_id": _MID,
        "mid8": _MID8,
        "mission_type": "software-dev",
        "coordination_branch": f"kitty/mission-{_SLUG}",
        "topology": "coord",
    }
    if merged_at is not None:
        meta["merged_at"] = merged_at
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _write_events(mission_dir: Path, *, final_lane: str) -> None:
    """Write ``status.events.jsonl`` driving ``_N_WPS`` WPs to ``final_lane``."""
    chain = _CHAIN + ([_TERMINAL_LANE] if final_lane == _TERMINAL_LANE else [])
    lines: list[str] = []
    seq = 0
    for i in range(1, _N_WPS + 1):
        wp_id = f"WP{i:02d}"
        prev: str | None = None
        for lane in chain:
            seq += 1
            if prev is None:
                prev = lane
                continue
            lines.append(
                json.dumps(
                    {
                        "actor": "claude",
                        "at": f"2026-08-30T00:00:{seq:02d}+00:00",
                        "event_id": f"01EV{seq:022d}"[:26],
                        "evidence": None,
                        "execution_mode": "worktree",
                        "feature_slug": _SLUG,
                        "force": False,
                        "from_lane": prev,
                        "reason": None,
                        "review_ref": None,
                        "to_lane": lane,
                        "wp_id": wp_id,
                    },
                    sort_keys=True,
                )
            )
            prev = lane
    (mission_dir / "status.events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_post_merge_state(repo_root: Path) -> tuple[Path, Path]:
    """Construct the real post-merge partition state directly (C-003: no merge).

    PRIMARY partition: 11 WPs ``done``, and a ``merged_at`` marker — the state a
    real ``spec-kitty merge`` leaves on HEAD now that WP04 restored the marker's
    writer (it had been deleted in #2258 and never re-added). COORD husk: the
    same 11 WPs still ``approved``, no marker, and diverged from primary (a
    separate ``status.events.jsonl`` at a ``.worktrees`` path — ``run_audit``
    cannot reach it, and its content differs from primary).

    Returns ``(primary_dir, coord_husk_dir)``.
    """
    primary_dir = repo_root / KITTY_SPECS_DIR / _SLUG
    coord_husk_dir = repo_root / ".worktrees" / f"{_SLUG}-coord" / KITTY_SPECS_DIR / _SLUG

    # PRIMARY: 11 done, WITH merged_at — the post-WP04 real-merge reality: the
    # restored writer stamps the marker, so the resolver's primary-wins guard
    # (``_primary_mission_is_completed`` -> ``is_mission_merged``) fires.
    _write_meta(primary_dir, merged_at="2026-08-30T02:00:00+00:00")
    _write_events(primary_dir, final_lane=_TERMINAL_LANE)

    # COORD husk: 11 approved, no marker — the stale surface that survives merge.
    _write_meta(coord_husk_dir, merged_at=None)
    _write_events(coord_husk_dir, final_lane=_NON_TERMINAL_LANE)

    return primary_dir, coord_husk_dir


def _open_wp_ids(events_dir: Path) -> list[str]:
    """Reduce a partition's event log and return its non-terminal WP ids.

    Uses the canonical status reducer (the same seam both real readers reduce
    through) so the two legs are compared on identical reduction semantics.
    """
    events = read_events(events_dir)
    snapshot = reduce_events(events)
    return sorted(wp_id for wp_id, wp_state in snapshot.work_packages.items() if str(wp_state.get("lane", "")) not in _RETROSPECT_TERMINAL)


def test_retrospect_and_doctor_agree_on_merged_mission_wp_states(tmp_path: Path) -> None:
    """The real retrospect and real doctor readers must agree post-merge (#4090).

    Was RED on HEAD before WP04: retrospect resolved the stale coord husk (11
    open) while doctor resolved the primary (0 open / 11 terminal). WP04 restored
    the ``merged_at`` writer, so a real post-merge primary carries the marker;
    the resolver's primary-wins guard now fires and retrospect reads the same
    authoritative primary the doctor does. Both see 0 open — this passes.
    """
    repo_root = tmp_path
    primary_dir, coord_husk_dir = _build_post_merge_state(repo_root)

    # --- Real divergence precondition: the two partitions genuinely differ. ---
    assert coord_husk_dir.is_dir()
    assert ".worktrees" in coord_husk_dir.parts
    primary_open = _open_wp_ids(primary_dir)
    husk_open = _open_wp_ids(coord_husk_dir)
    assert primary_open == []  # primary: all 11 terminal (done)
    assert len(husk_open) == _N_WPS  # husk: all 11 non-terminal (approved)

    # --- REAL doctor read leg -------------------------------------------------
    # ``doctor mission-state`` re-anchors to the canonical primary checkout via
    # the real ``_anchor_repair_root`` (its innermost root resolver), then reads
    # via the real ``run_audit`` engine, which scans ``<root>/kitty-specs`` and
    # so structurally reads the PRIMARY partition — never the ``.worktrees`` husk.
    doctor_root = _anchor_repair_root(repo_root, scan_root=None)
    assert doctor_root == repo_root.resolve()
    doctor_partition = doctor_root / KITTY_SPECS_DIR / _SLUG
    assert ".worktrees" not in doctor_partition.parts  # doctor reads primary

    report = run_audit(AuditOptions(repo_root=doctor_root))
    assert _SLUG in {m.mission_slug for m in report.missions}  # doctor found the primary mission

    doctor_open_wps = _open_wp_ids(doctor_partition)
    # Doctor sees all 11 terminal — holds on HEAD AND after the WP04 fix.
    assert doctor_open_wps == []

    # --- REAL retrospect read leg --------------------------------------------
    resolved = ResolvedMission(
        mission_id=_MID,
        mission_slug=_SLUG,
        feature_dir=primary_dir,
        mid8=_MID8,
    )
    # ``_check_mission_completed`` is the exact predicate ``retrospect create``
    # gates on (non-empty ⇒ ``MISSION_NOT_COMPLETED``); it routes through
    # ``_canonical_events_path`` → ``resolve_status_surface``.
    retrospect_open = _check_mission_completed(resolved, repo_root)
    retrospect_open_wps = sorted(w["wp_id"] for w in retrospect_open)

    # Diagnostic context for the RED (not load-bearing — the surface flips to
    # primary after the WP04 fix, so this is never a hard assertion).
    retrospect_surface = _canonical_events_path(repo_root, _SLUG)
    resolver_surface = resolve_status_surface(repo_root, _SLUG)

    # --- Load-bearing: the two REAL readers must agree ------------------------
    # RED on HEAD: retrospect reads the husk → 11 open; doctor reads primary →
    # 0 open. The fix (WP04) makes retrospect resolve the same primary surface,
    # so both see 0 open and this passes (XPASS ⇒ drop the xfail marker).
    assert retrospect_open_wps == doctor_open_wps, (
        "#4090 post-merge reader divergence: retrospect resolved "
        f"{retrospect_surface} (resolver: {resolver_surface}) and reports "
        f"{len(retrospect_open_wps)} open WP(s) {retrospect_open_wps}, while "
        f"doctor read the primary partition {doctor_partition} and reports "
        f"{len(doctor_open_wps)} open WP(s). The merged mission's readers must "
        "agree on the authoritative post-merge surface."
    )
