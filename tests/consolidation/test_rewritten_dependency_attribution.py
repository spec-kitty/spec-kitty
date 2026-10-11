"""Red-first gate test for #5968 — a rewritten, re-approved dependency's
rejected content must not land through a dependent lane under default squash.

Scenario (the #5968 ``reset``/``amend`` arms, at the reconciliation seam): WP02
depends on WP01, so ``implement WP02`` cuts lane-b on top of the approved
lane-a, fast-forwarding WP01's first-attempt commit onto lane-b's first-parent
spine. Review then rejects WP01; the implementer REWRITES lane-a (reset/amend)
to drop ``core.py``/``bad_only.py``, and WP01 is approved again. lane-b still
carries the OLD WP01 commit, so a default ``git merge --squash`` lands the
rejected ``core.py`` on the target.

The pre-#5968 ``_collect_authored`` walks each approved lane's FULL
``coord_base_ref..lane`` first-parent spine, so lane-b's inherited copy of the
rejected files is counted as lane-b's authored content and the squash
blob-attribution axis (``_unattributable_content_squash``) attributes them —
``verify`` returns PASS at exit 0 with "Reconciliation verified".

The contract this pins: authorship is bounded to each lane's OWN creation base
(``first_governed_open_stamp``), so an inherited dependency commit is NOT this
lane's authored content. lane-a (re-approved) authors only ``own.txt``; lane-b
authors only its ``wp02`` work; the rejected ``core.py``/``bad_only.py`` on the
target are attributable to no approved lane and the gate must REFUSE/FAIL and
roll back (never PASS). Drives the real ``build_approved_wp_set`` +
``MergeOutcomeVerifier.verify`` seam against a real ``git merge --squash``
target (``verify_reachability=False``), the default-strategy shape.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from specify_cli.consolidation.reconciliation import (
    MergeOutcomeVerifier,
    VerifyStatus,
    build_approved_wp_set,
)
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_TARGET = "main"
_SLUG = "rewritten-dep-01M5968"
_CORE = "u/wp01/core.py"
_BAD = "u/wp01/bad_only.py"
_WP01_OWN = "u/wp01/own.txt"
_WP02_OWN = "u/wp02/own.txt"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _write(repo: Path, rel: str, body: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(body, encoding="utf-8")


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _lane(lane_id: str, wp_id: str, deps: tuple[str, ...] = ()) -> ExecutionLane:
    return ExecutionLane(
        lane_id=lane_id,
        wp_ids=(wp_id,),
        write_scope=("u",),
        predicted_surfaces=("code",),
        depends_on_lanes=deps,
        parallel_group=0,
    )


def _branch(lane_id: str) -> str:
    name: str = lane_branch_name(_SLUG, lane_id, target_branch=_TARGET)
    return name


_CHAIN = (("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review"), ("for_review", "in_review"), ("in_review", "approved"))


def _ev(events: list[dict[str, object]], wp: str, frm: str, to: str, *, stamp: str | None, force: bool = False) -> None:
    seq = len(events)
    row: dict[str, object] = {
        "actor": "claude",
        "at": f"2026-10-09T00:{seq // 60:02d}:{seq % 60:02d}+00:00",
        "event_id": f"01M5968{seq:019d}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": _SLUG,
        "force": force,
        "from_lane": frm,
        "reason": None,
        "review_ref": None,
        "to_lane": to,
        "wp_id": wp,
    }
    if stamp is not None:
        row["policy_metadata"] = {"lane_head": stamp}
    events.append(row)


def _approve_chain(events: list[dict[str, object]], wp: str, *, claim_stamp: str, approve_stamp: str) -> None:
    """planned->...->approved, stamping the IMPLEMENTATION entry and the approval."""
    for frm, to in _CHAIN:
        if to in ("claimed", "in_progress"):
            stamp: str | None = claim_stamp
        elif to == "approved":
            stamp = approve_stamp
        else:
            stamp = None
        _ev(events, wp, frm, to, stamp=stamp)


@pytest.fixture
def rewritten_dep(tmp_path: Path) -> tuple[Path, Path, LanesManifest, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _TARGET)
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    mission_id = "01M5968000000000000000000"[:26].ljust(26, "0")
    feature_dir = repo / "kitty-specs" / _SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": _SLUG, "mission_id": mission_id, "mission_type": "software-dev", "target_branch": _TARGET}),
        encoding="utf-8",
    )
    manifest = LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=mission_id,
        mission_branch=f"kitty/mission-{_SLUG}",
        target_branch=_TARGET,
        lanes=[_lane("lane-a", "WP01"), _lane("lane-b", "WP02", ("lane-a",))],
        computed_at="2026-10-09T00:00:00+00:00",
        computed_from="test-rewritten-dependency-attribution",
    )
    write_lanes_json(feature_dir, manifest)
    _write(repo, "u/base.txt", "base\n")
    base = _commit(repo, "bootstrap")

    # lane-a: WP01 first attempt (own.txt + the rejected core.py / bad_only.py).
    _git(repo, "checkout", "-q", "-b", _branch("lane-a"), base)
    _write(repo, _WP01_OWN, "own1\n")
    _write(repo, _CORE, 'CORE = "BAD"\n')
    _write(repo, _BAD, "BAD = True\n")
    a1 = _commit(repo, "WP01: first attempt")

    # lane-b: cut from the approved lane-a (ff), WP02's own work on top.
    _git(repo, "checkout", "-q", "-b", _branch("lane-b"), a1)
    _write(repo, _WP02_OWN, "two\n")
    b_tip = _commit(repo, "WP02: work")

    # Review rejects WP01; the implementer REWRITES lane-a (reset arm) to drop
    # core.py / bad_only.py, then WP01 is approved again.
    _git(repo, "checkout", "-q", _branch("lane-a"))
    _git(repo, "reset", "-q", "--hard", base)
    _write(repo, _WP01_OWN, "own1\n")
    a_redo = _commit(repo, "WP01: redo (drop core.py, bad_only.py)")

    # Default-strategy target: a real squash of both lanes in dependency order.
    # lane-b still carries a1, so core.py / bad_only.py land on the target.
    _git(repo, "checkout", "-q", "-b", "target-squash", base)
    _git(repo, "merge", "--squash", _branch("lane-a"))
    _commit(repo, "squash lane-a")
    _git(repo, "merge", "--squash", _branch("lane-b"))
    _commit(repo, "squash lane-b")

    # Stamped event log: WP02's lane base is a1 (the fast-forward point), so its
    # authorship must bound to a1..lane-b = the WP02 commit only.
    events: list[dict[str, object]] = []
    _approve_chain(events, "WP01", claim_stamp=base, approve_stamp=a1)
    _ev(events, "WP01", "approved", "planned", stamp=None, force=True)  # review rejection
    _approve_chain(events, "WP01", claim_stamp=base, approve_stamp=a_redo)  # re-approved at the rewritten tip
    _approve_chain(events, "WP02", claim_stamp=a1, approve_stamp=b_tip)
    (feature_dir / "status.events.jsonl").write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in events), encoding="utf-8"
    )
    return repo, feature_dir, manifest, base, "target-squash"


def test_rewritten_dependency_rejected_content_is_unattributable(
    rewritten_dep: tuple[Path, Path, LanesManifest, str, str],
) -> None:
    repo, feature_dir, manifest, base, target = rewritten_dep

    # Precondition: the rejected content really is on the squash target.
    assert _git(repo, "show", f"{target}:{_CORE}") == 'CORE = "BAD"'

    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=base, excluded_window_base=base)
    assert claim.surface_resolved and claim.refusal is None, (
        f"claim did not resolve cleanly (expected a clean approved claim, "
        f"refusal={claim.refusal!r})"
    )
    squash_claim = replace(claim, verify_reachability=False)
    result = MergeOutcomeVerifier(repo).verify(target, squash_claim)

    assert result.status is not VerifyStatus.PASS, (
        "the gate PASSED while the target carries a rejected, rewritten-away "
        "dependency's content (core.py) that no approved lane authored — #5968 "
        f"false-green. divergence={result.divergence!r}"
    )
    assert result.divergence is not None
    unattributable_paths = {path for path, _blob in result.divergence.unattributable_blobs}
    assert _CORE in unattributable_paths and _BAD in unattributable_paths, (
        f"the rejected files were not flagged unattributable: {unattributable_paths!r}"
    )
