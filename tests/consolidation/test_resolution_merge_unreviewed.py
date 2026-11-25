"""FR-004: a merge on an approved lane that carries its own content and that no review covers refuses at claim time.

``RESOLUTION_MERGE_UNREVIEWED`` (``contracts/refusal-codes.md``) fires before any mutation when a merge
commit on an approved code lane's first-parent spine, beyond the claim base,

* is reached by none of its OWN lane's approval stamps (pre-sync stamps included, #7802), through the
  predicate the gate shares (``reconciliation_authorship.merge_reviewed_by_own_stamps``), or lies inside a
  canceled work package's window (binding addendum 6);
* has no auto-rebase record for its exact SHA (WP02), or has one but was not made under the merge
  attributes the claim trusts (binding addendum 1);
* carries at least one non-bookkeeping own path (``git_probes.merge_own_changed_paths``, behind FR-010).

Every probe error refuses (NFR-002). "No mutation" is proven by reflog lengths and the absence of a
persisted pre-mutation snapshot, never by end-state SHAs alone: the pre-fix late path (land, gate FAIL,
roll back) also ends at the same SHAs.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from specify_cli.consolidation import approved_bound, git_probes, reconciliation_bound
from specify_cli.consolidation.approved_bound import BoundRefusal, BoundRefusalCode, refusal_codes, render_refusals
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.consolidation.reconciliation import ApprovedWpCommitSet, build_approved_wp_set
from specify_cli.lanes import auto_rebase_record
from specify_cli.lanes.models import LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status import materialize_snapshot
from tests.consolidation import characterization_support as cs
from tests.consolidation.test_dependency_merge_attribution_7307 import (
    _EVIL,
    _branch,
    _build_post_approval_merge,
    _commit,
    _init_repo,
    _lane,
    _octopus_merge_with_own_file,
    _write,
)
from tests.terminus.conftest import CoordMission, git_rev, run_terminus
from tests.terminus.mixed_lane_support import collapse
from tests.terminus.post_approval_support import (
    LATE_CONTENT,
    LATE_PATH,
    WP01_PATH,
    Topology,
    build_post_approval_mission,
    lane_worktree,
    rework_and_reapprove,
)
from tests.terminus.rollback_harness import reflog_shas, state_path

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CODE = "RESOLUTION_MERGE_UNREVIEWED"
_SLUG = "dep-merge-attr-01M7307"
_FORGED_MESSAGE = "auto-rebase(lane=lane-a): 1 conflicts resolved by classifier rules"


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True, env=env).stdout.strip()


# --------------------------------------------------------------------------- no-mutation proof (SC-003)


def _branches(mission: CoordMission) -> list[str]:
    return list(dict.fromkeys([mission.target_branch, mission.coord_branch, *mission.lane_branches.values()]))


def _reflog_lengths(mission: CoordMission) -> dict[str, int]:
    return {branch: len(reflog_shas(mission, branch)) for branch in _branches(mission)}


def _snapshot_persisted(mission: CoordMission) -> bool:
    path = state_path(mission)
    return path is not None and bool(json.loads(path.read_text(encoding="utf-8")).get("pre_mutation_refs"))


def _assert_no_mutation(mission: CoordMission, before: dict[str, int]) -> None:
    assert _reflog_lengths(mission) == before, "a branch moved (a land-then-rollback leaves reflog entries even when the tip comes back)"
    assert state_path(mission) is None, "a claim-time refusal persists no consolidation record"
    assert not _snapshot_persisted(mission)


def _consolidate(mission: CoordMission, *extra: str) -> tuple[int, str]:
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, *extra])
    return result.returncode, collapse(result.stdout + "\n" + result.stderr)


# --------------------------------------------------------------------------- terminus (real CLI) shapes


def _evil_merge(mission: CoordMission, *, lane: str = "lane-a", message: str = "merge: carries a file neither parent has", add_late: bool = True) -> str:
    """lane's tip becomes a merge of its approved tip and the Mission branch tip (the auto-rebase parent shape).

    With *add_late* the tree adds ``LATE_PATH`` (own content); without it the merge is clean (empty remerge-diff).
    """
    worktree = lane_worktree(mission, lane)
    anchor = git_rev(mission.repo, mission.coord_branch)
    if add_late:
        late_file = worktree / LATE_PATH
        late_file.parent.mkdir(parents=True, exist_ok=True)
        late_file.write_text(LATE_CONTENT, encoding="utf-8")
        _git(worktree, "add", LATE_PATH)
    tree = _git(worktree, "write-tree")
    merge = _git(worktree, "commit-tree", tree, "-p", "HEAD", "-p", anchor, "-m", message)
    _git(worktree, "reset", "-q", "--hard", merge)
    return merge


def _commit_on_branch(repo: Path, branch: str, path: str, content: str, message: str) -> str:
    """One commit on *branch* through a private index (the branch need not be checked out anywhere)."""
    index = repo / ".git" / "wp05-private-index"
    env = {**os.environ, "GIT_INDEX_FILE": str(index)}
    _git(repo, "read-tree", branch, env=env)
    blob = subprocess.run(["git", "-C", str(repo), "hash-object", "-w", "--stdin"], input=content, capture_output=True, text=True, check=True).stdout.strip()
    _git(repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}", env=env)
    tree = _git(repo, "write-tree", env=env)
    index.unlink(missing_ok=True)
    head = _git(repo, "rev-parse", branch)
    sha = _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit-tree", tree, "-p", head, "-m", message)
    _git(repo, "update-ref", f"refs/heads/{branch}", sha, head)
    return sha


@pytest.mark.parametrize("topology", ["lanes", "coord"])
def test_hand_merge_with_own_content_is_refused_before_any_branch_moves(tmp_path: Path, topology: Topology) -> None:
    mission = build_post_approval_mission(tmp_path, topology)
    merge = _evil_merge(mission)
    before = _reflog_lengths(mission)

    code, flat = _consolidate(mission, "--yes")

    assert code != 0, flat
    assert _CODE in flat, flat
    assert f"merge {merge[:7]}" in flat and "lane lane-a (WP01)" in flat, flat
    assert "Reconciliation FAILED" not in flat, f"the refusal must come at claim time, not at the gate:\n{flat}"
    _assert_no_mutation(mission, before)


def test_hand_merge_of_the_mission_branch_is_refused(tmp_path: Path) -> None:
    """A real ``git merge`` of the advanced Mission branch into the lane, parents ``[lane tip, mission tip]``, with an edit folded in."""
    mission = build_post_approval_mission(tmp_path, "lanes")
    _commit_on_branch(mission.repo, mission.coord_branch, "src/pkg/mission_side.py", "SIDE = 1\n", "mission: side change")
    worktree = lane_worktree(mission, "lane-a")
    lane_tip = git_rev(worktree, "HEAD")
    mission_tip = git_rev(mission.repo, mission.coord_branch)
    _git(worktree, "merge", "--no-ff", "--no-commit", mission.coord_branch)
    (worktree / LATE_PATH).parent.mkdir(parents=True, exist_ok=True)
    (worktree / LATE_PATH).write_text(LATE_CONTENT, encoding="utf-8")
    _git(worktree, "add", LATE_PATH)
    _git(worktree, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", f"Merge {mission.coord_branch} into lane-a")
    merge = git_rev(worktree, "HEAD")
    assert _git(mission.repo, "rev-list", "--parents", "-n1", merge).split()[1:] == [lane_tip, mission_tip], "fixture: the auto-rebase parent shape"
    before = _reflog_lengths(mission)

    code, flat = _consolidate(mission, "--yes")

    assert code != 0 and _CODE in flat and f"merge {merge[:7]}" in flat, flat
    _assert_no_mutation(mission, before)


def test_clean_post_approval_merge_is_not_refused_end_to_end(tmp_path: Path) -> None:
    """**control**: a clean merge of the Mission branch tip (empty remerge-diff) carries nothing to review."""
    mission = build_post_approval_mission(tmp_path, "lanes")
    _evil_merge(mission, add_late=False)

    _code, flat = _consolidate(mission, "--yes")

    assert _CODE not in flat, flat


def test_merge_reached_by_own_stamp_is_not_refused(tmp_path: Path) -> None:
    """**control**: re-approved after the merge (unforced, independent reviewer): its own stamp reaches it."""
    mission = build_post_approval_mission(tmp_path, "lanes")
    _evil_merge(mission)
    rework_and_reapprove(mission, "WP01")

    _code, flat = _consolidate(mission, "--yes")

    assert _CODE not in flat, flat


def test_forged_record_is_harmless_the_gate_still_fails(tmp_path: Path) -> None:
    """Binding addendum 2: a hand-written record may skip the claim-time refusal, but the content never lands."""
    mission = build_post_approval_mission(tmp_path, "lanes")
    merge = _evil_merge(mission)
    lane_branch = mission.lane_branches["WP01"]
    _git(mission.repo, "update-ref", f"refs/spec-kitty/auto-rebase/{lane_branch}/{merge}", merge)
    target_before = git_rev(mission.repo, mission.target_branch)

    code, flat = _consolidate(mission, "--yes")

    assert code != 0, flat
    assert git_rev(mission.repo, mission.target_branch) == target_before, "the target is restored"
    assert LATE_PATH not in _git(mission.repo, "ls-tree", "-r", "--name-only", mission.target_branch).split()
    assert "Reconciliation FAILED" in flat and LATE_PATH in flat, f"the gate's attribution axis FAILs it:\n{flat}"


def test_union_attribute_attack_refuses_at_claim_with_no_branch_moves(tmp_path: Path) -> None:
    """FR-010 x FR-004: a clone-local ``merge=union`` would make a hand resolution re-merge to itself; the claim refuses."""
    mission = build_post_approval_mission(tmp_path, "lanes")
    _commit_on_branch(mission.repo, mission.coord_branch, WP01_PATH, "def wp01() -> int:\n    return 2\n", "mission: same path, other content")
    worktree = lane_worktree(mission, "lane-a")
    subprocess.run(["git", "-C", str(worktree), "merge", "--no-edit", mission.coord_branch], capture_output=True, check=False)
    union = "def wp01() -> int:\n    return 1\n    return 2\n"
    (worktree / WP01_PATH).write_text(union, encoding="utf-8")
    _git(worktree, "add", WP01_PATH)
    _git(worktree, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "hand merge with the union bytes")
    merge = git_rev(worktree, "HEAD")
    assert git_probes.merge_own_changed_paths(mission.repo, merge) == [WP01_PATH], "precondition: without the attribute the resolution is own content"
    common = Path(_git(mission.repo, "rev-parse", "--git-common-dir"))
    common = common if common.is_absolute() else mission.repo / common
    (common / "info").mkdir(exist_ok=True)
    (common / "info" / "attributes").write_text(f"{WP01_PATH} merge=union\n", encoding="utf-8")
    before = _reflog_lengths(mission)

    code, flat = _consolidate(mission, "--yes")

    assert code != 0, flat
    assert "a git probe failed while building the approved-WP claim" in flat and "merge attribute 'union'" in flat, flat
    _assert_no_mutation(mission, before)


# --------------------------------------------------------------------------- forecast (T026)


def _shape(mission: CoordMission, topology: str) -> cs.ShapeMission:
    return cs._from_coord(mission, topology, subject_wp="WP01", window_wps=())


def test_forecast_reports_claim_refused_naming_the_code(tmp_path: Path) -> None:
    """``forecast|single_lane|post_approval_resolution_merge``: the preview is not green while the run refuses."""
    mission = build_post_approval_mission(tmp_path / "forecast", "lanes")
    merge = _evil_merge(mission)
    shape = _shape(mission, "lanes")
    twin = cs.copy_mission(shape, tmp_path / "twin")
    before = _reflog_lengths(mission)

    result = run_terminus(mission, cs.consolidate_args(shape, "forecast"))
    payload = json.loads(result.stdout)

    assert payload.get("error_code") == "CLAIM_REFUSED_FORECAST", payload
    message = json.dumps(payload)
    assert _CODE in message and merge[:7] in message and "lane-a" in message, message
    _assert_no_mutation(mission, before)
    real = run_terminus(twin.coord_mission(), cs.consolidate_args(twin, "run"))
    assert real.returncode != 0 and _CODE in collapse(real.stdout + real.stderr), "forecast and real run agree"


def test_forecast_of_a_clean_merge_names_no_code(tmp_path: Path) -> None:
    """**control**: a clean post-approval merge forecasts no ``RESOLUTION_MERGE_UNREVIEWED``."""
    mission = build_post_approval_mission(tmp_path, "lanes")
    _evil_merge(mission, add_late=False)
    result = run_terminus(mission, cs.consolidate_args(_shape(mission, "lanes"), "forecast"))
    assert _CODE not in result.stdout + result.stderr


def test_refuses_naming_the_git_version_below_remerge_support(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Analysis A13: git without ``--remerge-diff`` refuses the hand merge before any mutation, naming the version it needs."""
    mission = build_post_approval_mission(tmp_path, "lanes")
    _evil_merge(mission)
    before = _reflog_lengths(mission)
    monkeypatch.setattr(git_probes, "remerge_diff_available", lambda _repo: False)

    result = cs.run_in_process(_shape(mission, "lanes"), cs.consolidate_args(_shape(mission, "lanes"), "run"))

    flat = collapse(result.output)
    assert result.exit_code != 0 and result.exception is None, flat
    assert "git >= 2.36" in flat, flat
    _assert_no_mutation(mission, before)


# --------------------------------------------------------------------------- claim level (hand-built, real git)


def _evil_claim(tmp_path: Path) -> tuple[Path, Path, LanesManifest, str, str]:
    return _build_post_approval_merge(tmp_path, canceled_dependency=False)


def _claim(repo: Path, feature_dir: Path, manifest: LanesManifest, base: str, *, canceled: tuple[str, ...] = ()) -> ApprovedWpCommitSet:
    """The claim, after asserting the status log is on disk: a checkout that dropped it would make every claim vacuously pass."""
    assert materialize_snapshot(feature_dir).work_packages, "fixture: the status log must be readable in the current checkout"
    return build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=base, excluded_window_base=base, excluded_canceled_wp_ids=canceled)


def _clean_merge(repo: Path, evil: str) -> str:
    """Replace lane-b's evil merge with a real, clean ``git merge`` of lane-c (empty remerge-diff); back on the checkout holding the log."""
    _git(repo, "checkout", "-q", _branch("lane-b"))
    _git(repo, "reset", "-q", "--hard", f"{evil}^1")
    _git(repo, "merge", "--no-ff", "--no-edit", _branch("lane-c"))
    clean = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "target-squash")
    assert git_probes.merge_own_changed_paths(repo, clean) == [], "fixture: a clean merge"
    return clean


def _codes(claim: ApprovedWpCommitSet) -> list[str]:
    return refusal_codes(claim.refusal or "")


def _refused_merges(claim: ApprovedWpCommitSet) -> set[str]:
    """Short SHAs of the merges the FR-004 block names."""
    text = claim.refusal or ""
    block = text[text.index(f"{_CODE}: ") :] if f"{_CODE}: " in text else ""
    return {token[len("merge ") :] for token in re.findall(r"merge [0-9a-f]{7}(?= carries)", block)}


def test_claim_refuses_the_post_approval_merge_with_own_content(tmp_path: Path) -> None:
    repo, feature_dir, manifest, base, evil = _evil_claim(tmp_path)
    claim = _claim(repo, feature_dir, manifest, base)
    assert claim.refusal is not None and _CODE in _codes(claim), claim.refusal
    assert f"lane lane-b (WP02): merge {evil[:7]} carries its own content on 1 path(s) (e.g. '{_EVIL}')" in claim.refusal
    assert "spec-kitty agent tasks move-task WP02 --to in_progress --mission " + _SLUG in claim.refusal


def test_clean_post_approval_merge_is_not_refused(tmp_path: Path) -> None:
    """**control**: a merge whose remerge-diff is empty is not refused; the claim has no refusal at all."""
    repo, feature_dir, manifest, base, evil = _evil_claim(tmp_path)
    _clean_merge(repo, evil)
    claim = _claim(repo, feature_dir, manifest, base)
    assert claim.refusal is None, claim.refusal


def test_recorded_tool_merge_is_not_refused(tmp_path: Path) -> None:
    """**control**: the record (WP02's ``record()``, never a hand-written ref) exempts the merge at claim time.

    US3 AS3: its auto-resolved content is still judged by the gate; only the claim's code is asserted here.
    """
    repo, feature_dir, manifest, base, evil = _evil_claim(tmp_path)
    assert auto_rebase_record.record(repo, _branch("lane-b"), evil)
    claim = _claim(repo, feature_dir, manifest, base)
    assert _CODE not in _codes(claim), claim.refusal


def test_message_forged_merge_is_refused(tmp_path: Path) -> None:
    repo, feature_dir, manifest, base, evil = _evil_claim(tmp_path)
    parents = _git(repo, "rev-list", "--parents", "-n1", evil).split()[1:]
    forged = _git(repo, "commit-tree", f"{evil}^{{tree}}", *[arg for parent in parents for arg in ("-p", parent)], "-m", _FORGED_MESSAGE)
    _git(repo, "branch", "-f", _branch("lane-b"), forged)
    claim = _claim(repo, feature_dir, manifest, base)
    assert _CODE in _codes(claim) and forged[:7] in _refused_merges(claim), claim.refusal


def test_record_naming_another_commit_refuses(tmp_path: Path) -> None:
    """Binding addendum 4: a record that names a different commit is a read error, never "not recorded"."""
    repo, feature_dir, manifest, base, evil = _evil_claim(tmp_path)
    _git(repo, "update-ref", f"refs/spec-kitty/auto-rebase/{_branch('lane-b')}/{evil}", base)
    with pytest.raises(GitProbeError, match="auto-rebase record"):
        _claim(repo, feature_dir, manifest, base)


def test_probe_error_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir, manifest, base, _evil = _evil_claim(tmp_path)

    def _raise(*_args: object, **_kwargs: object) -> list[str]:
        raise GitProbeError("probe failed")

    monkeypatch.setattr(approved_bound, "merge_own_changed_paths", _raise)
    with pytest.raises(GitProbeError, match="probe failed"):
        _claim(repo, feature_dir, manifest, base)


def test_octopus_merge_with_own_content_refuses(tmp_path: Path) -> None:
    repo, feature_dir, manifest, base, _evil = _evil_claim(tmp_path)
    _octopus_merge_with_own_file(repo)
    with pytest.raises(GitProbeError, match="octopus"):
        _claim(repo, feature_dir, manifest, base)


def test_merge_reached_only_by_the_presync_stamp_is_reviewed(tmp_path: Path) -> None:
    """Binding addendum 5: the claim reads each approved WP's pre-sync stamp as a reach anchor, as the gate does."""
    repo, feature_dir, manifest, base, evil = _evil_claim(tmp_path)
    log = feature_dir / "status.events.jsonl"
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    approval = next(row for row in reversed(rows) if row["wp_id"] == "WP02" and row["to_lane"] == "approved")
    # The reviewer's sync merge (lane_head) never reached this clone; the pre-sync stamp is the merge itself.
    approval["policy_metadata"] = {"lane_head": "f" * 40, "lane_head_presync": evil}
    log.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    claim = _claim(repo, feature_dir, manifest, base)
    assert _CODE not in _codes(claim), claim.refusal


def test_recorded_merge_under_a_lane_committed_union_is_refused(tmp_path: Path) -> None:
    """Binding addendum 1: a recorded merge made under a ``merge=union`` the lane committed (not the target) is a hand merge."""
    repo, feature_dir, manifest, base = _init_repo(tmp_path)
    manifest.lanes = [_lane("lane-c", "WP03"), _lane("lane-b", "WP02", ("lane-c",))]
    (feature_dir / "tasks" / "WP01-work.md").unlink()
    write_lanes_json(feature_dir, manifest)
    _write(repo, "u/p.txt", "base\n")
    base = _commit(repo, "two lanes")
    _git(repo, "checkout", "-q", "-b", _branch("lane-c"), base)
    _write(repo, "u/p.txt", "from c\n")
    c_tip = _commit(repo, "WP03: edit p")
    _git(repo, "checkout", "-q", "-b", _branch("lane-b"), base)
    _write(repo, ".gitattributes", "u/p.txt merge=union\n")
    _write(repo, "u/p.txt", "from b\n")
    b_tip = _commit(repo, "WP02: edit p, union attribute")
    _git(repo, "merge", "--no-edit", _branch("lane-c"))  # the lane checkout honours its committed union: no conflict
    merge = _git(repo, "rev-parse", "HEAD")
    assert auto_rebase_record.record(repo, _branch("lane-b"), merge)
    _write_events(feature_dir, [("WP03", base, c_tip), ("WP02", base, b_tip)])
    _git(repo, "checkout", "-q", "main")
    claim = _claim(repo, feature_dir, manifest, base)
    assert _CODE in _codes(claim) and merge[:7] in _refused_merges(claim), claim.refusal


# --------------------------------------------------------------------------- hand-written event logs


def _row(seq: int, wp: str, frm: str, to: str, stamp: str | None, *, actor: str = "claude") -> dict[str, object]:
    row: dict[str, object] = {
        "actor": actor,
        "at": f"2026-11-07T01:{seq // 60:02d}:{seq % 60:02d}+00:00",
        "event_id": f"01M7W05{seq:019d}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": _SLUG,
        "force": False,
        "from_lane": frm,
        "reason": None,
        "review_ref": None,
        "to_lane": to,
        "wp_id": wp,
    }
    if stamp is not None:
        row["policy_metadata"] = {"lane_head": stamp}
    return row


_APPROVE = (("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review"), ("for_review", "in_review"), ("in_review", "approved"))


def _approval_rows(rows: list[dict[str, object]], wp: str, claim: str, approve: str) -> None:
    for frm, to in _APPROVE:
        stamp = claim if to in ("claimed", "in_progress") else approve
        rows.append(_row(len(rows), wp, frm, to, stamp, actor="reviewer-renata" if to in ("in_review", "approved") else "claude"))


def _write_events(feature_dir: Path, approvals: list[tuple[str, str, str]], extra: list[dict[str, object]] | None = None) -> None:
    rows: list[dict[str, object]] = list(extra or [])
    for wp, claim, approve in approvals:
        _approval_rows(rows, wp, claim, approve)
    for index, row in enumerate(rows):
        row["event_id"] = f"01M7W05{index:019d}"
        row["at"] = f"2026-11-07T01:{index // 60:02d}:{index % 60:02d}+00:00"
    (feature_dir / "status.events.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _three_lane(tmp_path: Path) -> tuple[Path, Path, LanesManifest, str, str]:
    """lane-c depends on lane-b; lane-b carries an unreviewed merge M_b; lane-c merges lane-b after M_b and is approved there."""
    repo, feature_dir, manifest, base = _init_repo(tmp_path)
    manifest.lanes = [_lane("lane-b", "WP02"), _lane("lane-c", "WP03", ("lane-b",))]
    (feature_dir / "tasks" / "WP01-work.md").unlink()
    write_lanes_json(feature_dir, manifest)
    base = _commit(repo, "two lanes")
    _git(repo, "checkout", "-q", "-b", "side", base)
    _write(repo, "u/side.txt", "side\n")
    _commit(repo, "side")
    _git(repo, "checkout", "-q", "-b", _branch("lane-b"), base)
    _write(repo, "u/b.txt", "b1\n")
    b1 = _commit(repo, "WP02: b1")
    _git(repo, "checkout", "-q", "-b", _branch("lane-c"), b1)
    _write(repo, "u/c.txt", "c1\n")
    _commit(repo, "WP03: c1")
    _git(repo, "checkout", "-q", _branch("lane-b"))
    _git(repo, "merge", "--no-ff", "--no-commit", "side")
    _write(repo, _EVIL, "unreviewed\n")
    m_b = _commit(repo, "hand merge on lane-b")
    _git(repo, "checkout", "-q", _branch("lane-c"))
    _git(repo, "merge", "--no-ff", "--no-edit", _branch("lane-b"))
    _write(repo, "u/c.txt", "c2\n")
    c2 = _commit(repo, "WP03: c2")
    _write_events(feature_dir, [("WP02", base, b1), ("WP03", b1, c2)])
    _git(repo, "checkout", "-q", "main")
    return repo, feature_dir, manifest, base, m_b


def test_three_lane_case_uses_the_own_lane_predicate(tmp_path: Path) -> None:
    """A dependent lane's stamp reaching the merge does not exempt it: only lane-b's own stamps count."""
    repo, feature_dir, manifest, base, m_b = _three_lane(tmp_path)
    assert git_probes.sha_reachable_from(repo, m_b, _branch("lane-c")), "fixture: lane-c's approval stamp reaches M_b"
    claim = _claim(repo, feature_dir, manifest, base)
    assert _CODE in _codes(claim), claim.refusal
    assert f"lane lane-b (WP02): merge {m_b[:7]}" in (claim.refusal or "")
    assert _refused_merges(claim) == {m_b[:7]}, "lane-c's own (reviewed) merge is not refused"


def _canceled_window_merge(tmp_path: Path, *, hidden: bool = False) -> tuple[Path, Path, LanesManifest, str, str]:
    """One lane, WP01 and WP02. WP02 claims, the lane gets a merge whose resolution adds ``u/canceled.txt``,
    WP02 is canceled at that merge; WP01 then claims, commits ``w1`` and is approved at ``w1`` (which reaches the merge).

    With *hidden* the hand merge sits behind a clean merge ``T = merge(base, hand)``: only T is on the spine,
    and WP02 is canceled at T. Returns the hand merge's SHA either way."""
    repo, feature_dir, manifest, base = _init_repo(tmp_path)
    manifest.lanes = [replace(_lane("lane-a", "WP01"), wp_ids=("WP01", "WP02"))]
    (feature_dir / "tasks" / "WP03-work.md").unlink()
    write_lanes_json(feature_dir, manifest)
    base = _commit(repo, "one mixed lane")
    _git(repo, "checkout", "-q", "-b", "side", base)
    _write(repo, "u/side.txt", "side\n")
    _commit(repo, "side")
    _git(repo, "checkout", "-q", "-b", _branch("lane-a"), base)
    _git(repo, "merge", "--no-ff", "--no-commit", "side")
    _write(repo, "u/canceled.txt", "canceled work\n")
    merge = _commit(repo, "merge side, folding in canceled work")
    hand = merge
    if hidden:
        merge = _git(repo, "commit-tree", f"{hand}^{{tree}}", "-p", base, "-p", hand, "-m", "clean merge hiding the canceled hand merge")
        _git(repo, "reset", "-q", "--hard", merge)
    _write(repo, "u/w1.txt", "w1\n")
    w1 = _commit(repo, "WP01: w1")
    rows = [
        _row(0, "WP02", "planned", "claimed", base),
        _row(1, "WP02", "claimed", "in_progress", base),
        _row(2, "WP02", "in_progress", "canceled", merge),
    ]
    events: list[dict[str, object]] = list(rows)
    for frm, to in _APPROVE:
        stamp = merge if to in ("claimed", "in_progress") else w1
        events.append(_row(len(events), "WP01", frm, to, stamp, actor="reviewer-renata" if to in ("in_review", "approved") else "claude"))
    _write_events(feature_dir, [], extra=events)
    _git(repo, "checkout", "-q", "main")
    return repo, feature_dir, manifest, base, hand


def test_hidden_merge_inside_a_canceled_window_is_refused(tmp_path: Path) -> None:
    """Review cycle 1 x addendum 6: a canceled window holds a hand merge reached through any parent, not only on the spine."""
    repo, feature_dir, manifest, base, hand = _canceled_window_merge(tmp_path, hidden=True)
    assert hand not in _git(repo, "rev-list", "--first-parent", _branch("lane-a")).split(), "fixture: the hand merge is off the spine"
    claim = _claim(repo, feature_dir, manifest, base, canceled=("WP02",))
    assert claim.refusal is not None and f"merge {hand[:7]}" in claim.refusal and "inside canceled WP02's window" in claim.refusal, claim.refusal


def test_merge_inside_a_canceled_window_is_refused_although_a_later_stamp_reaches_it(tmp_path: Path) -> None:
    """Binding addendum 6 (WP08 review cycle 2 probe): a later approval reaching the merge does not review the canceled WP's merge."""
    repo, feature_dir, manifest, base, merge = _canceled_window_merge(tmp_path)
    assert git_probes.sha_reachable_from(repo, merge, _branch("lane-a")), "fixture"
    claim = _claim(repo, feature_dir, manifest, base, canceled=("WP02",))
    assert claim.refusal is not None, "a canceled WP's merge content must never land"
    assert _CODE in _codes(claim), claim.refusal
    assert f"merge {merge[:7]}" in claim.refusal and "inside canceled WP02's window" in claim.refusal, claim.refusal


# --------------------------------------------------------------------------- predicate agreement (T023 #7)


def _off_spine(repo: Path, evil: str) -> str:
    """Hide the evil merge behind a clean one: ``T = merge(evil^1, evil)`` with evil's tree; only T is on lane-b's first-parent spine."""
    hider = _git(repo, "commit-tree", f"{evil}^{{tree}}", "-p", f"{evil}^1", "-p", evil, "-m", "clean merge hiding the hand merge")
    _git(repo, "branch", "-f", _branch("lane-b"), hider)
    assert git_probes.merge_own_changed_paths(repo, hider) == [], "fixture: the hiding merge is clean"
    assert evil not in _git(repo, "rev-list", "--first-parent", _branch("lane-b")).split(), "fixture: the hand merge is off the spine"
    return hider


@pytest.mark.parametrize("fixture", ["evil", "three_lane", "clean", "forged_message", "off_spine"])
def test_claim_and_gate_agree_on_dropped_merges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixture: str) -> None:
    """The claim refuses exactly the merges the gate drops (``claim.unreviewed_merges`` on a bypassed claim) that carry own content."""
    if fixture == "three_lane":
        repo, feature_dir, manifest, base, _m = _three_lane(tmp_path)
    else:
        repo, feature_dir, manifest, base, evil = _evil_claim(tmp_path)
        if fixture == "clean":
            _clean_merge(repo, evil)
        elif fixture == "forged_message":
            parents = _git(repo, "rev-list", "--parents", "-n1", evil).split()[1:]
            forged = _git(repo, "commit-tree", f"{evil}^{{tree}}", *[a for p in parents for a in ("-p", p)], "-m", _FORGED_MESSAGE)
            _git(repo, "branch", "-f", _branch("lane-b"), forged)
        elif fixture == "off_spine":
            _off_spine(repo, evil)
    claimed = _refused_merges(_claim(repo, feature_dir, manifest, base))
    with monkeypatch.context() as patch:
        patch.setattr(reconciliation_bound, "unreviewed_resolution_merges", lambda *_a, **_k: ())
        bypassed = _claim(repo, feature_dir, manifest, base)
    assert bypassed.refusal is None, bypassed.refusal
    for entry in bypassed.unreviewed_merges:  # precondition: every dropped merge probed cleanly
        git_probes.merge_own_changed_paths(repo, entry.sha)
    lane_branch = {lane.lane_id: _branch(lane.lane_id) for lane in manifest.lanes}
    gate = {
        entry.sha[:7] for entry in bypassed.unreviewed_merges if entry.own_paths and not auto_rebase_record.is_recorded(repo, lane_branch[entry.lane_id], entry.sha)
    }
    assert claimed == gate
    assert (fixture == "clean") == (not claimed), f"{fixture}: {claimed}"


# --------------------------------------------------------------------------- NFR-001 process counts


@pytest.fixture
def remerges(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    import kernel.git

    calls: list[str] = []
    real = kernel.git.remerge_paths

    def _counting(cwd: Path, commit: str, **kwargs: Any) -> Any:
        calls.append(commit)
        return real(cwd, commit, **kwargs)

    monkeypatch.setattr(kernel.git, "remerge_paths", _counting)
    return calls


def test_no_post_approval_merge_runs_no_remerge(tmp_path: Path, remerges: list[str]) -> None:
    from tests.consolidation.test_dependency_merge_attribution_7307 import _build_mission

    repo, feature_dir, manifest, base, _dep = _build_mission(tmp_path, conflict=False)
    remerges.clear()
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=base, excluded_window_base=base)
    assert claim.refusal is None, claim.refusal
    assert remerges == []


def test_refusing_lane_runs_exactly_one_remerge(tmp_path: Path, remerges: list[str]) -> None:
    repo, feature_dir, manifest, base, evil = _evil_claim(tmp_path)
    remerges.clear()
    claim = _claim(repo, feature_dir, manifest, base)
    assert _CODE in _codes(claim)
    assert remerges == [evil]


def test_passing_claim_with_one_clean_merge_runs_exactly_one_remerge(tmp_path: Path, remerges: list[str]) -> None:
    repo, feature_dir, manifest, base, evil = _evil_claim(tmp_path)
    clean = _clean_merge(repo, evil)
    remerges.clear()
    claim = _claim(repo, feature_dir, manifest, base)
    assert claim.refusal is None, claim.refusal
    assert [entry.sha for entry in claim.unreviewed_merges] == [clean], "WP04's advisory entry is still recorded"
    assert remerges == [clean], "one remerge for the merge across the whole claim build (the memo feeds WP04's reader)"


# --------------------------------------------------------------------------- renderer (T024)


def _refusal(lane: str, wps: tuple[str, ...], sha: str, *, path: str = "src/x.py", count: int = 1, canceled: str | None = None) -> BoundRefusal:
    return BoundRefusal(BoundRefusalCode.RESOLUTION_MERGE_UNREVIEWED, lane, f"b-{lane}", wps, commits=(sha,), path=path, own_path_count=count, canceled_wp=canceled)


def test_render_one_refusal() -> None:
    text = render_refusals([_refusal("lane-a", ("WP01",), "a" * 40, count=2)], "m-1")
    lines = text.splitlines()
    assert lines[0] == (
        f"{_CODE}: lane lane-a (WP01): merge aaaaaaa carries its own content on 2 path(s) (e.g. 'src/x.py') and no review approval of the lane reaches it."
    )
    assert "  spec-kitty agent tasks move-task WP01 --to in_progress --mission m-1" in lines
    assert any("--force --note" in line for line in lines)
    assert any("the new approval must reach merge aaaaaaa" in line for line in lines)
    assert lines[-1] == "Then re-run: spec-kitty consolidate --mission m-1"
    assert refusal_codes(text) == [_CODE]


def test_render_two_merges_one_lane_and_two_lanes() -> None:
    text = render_refusals(
        [_refusal("lane-a", ("WP01",), "a" * 40), _refusal("lane-a", ("WP01",), "b" * 40), _refusal("lane-b", ("WP02", "WP03"), "c" * 40)],
        "m-1",
    )
    assert refusal_codes(text) == [_CODE]
    assert sum(line.startswith(f"{_CODE}: ") for line in text.splitlines()) == 1, "only the first line leads with the code"
    assert "lane lane-b (WP02, WP03): merge ccccccc" in text
    assert text.count("move-task WP01 ") == 1 and "move-task WP03 " in text
    assert "must reach merge aaaaaaa, bbbbbbb, ccccccc" in text


def test_render_mixed_codes_puts_the_new_block_last() -> None:
    moved = BoundRefusal(BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL, "lane-b", "b-lane-b", ("WP02",), commits=("d" * 40,), path="p.py")
    text = render_refusals([_refusal("lane-a", ("WP01",), "a" * 40), moved], "m-1")
    assert text.startswith("LANE_MOVED_AFTER_APPROVAL: ")
    assert refusal_codes(text) == ["LANE_MOVED_AFTER_APPROVAL", _CODE]


def test_render_canceled_window_refusal_says_reapproval_does_not_lift_it() -> None:
    text = render_refusals([_refusal("lane-a", ("WP01",), "a" * 40, canceled="WP02")], "m-1")
    assert "was made inside canceled WP02's window" in text
    assert "rebuild the lane without merge aaaaaaa" in text


def test_refusal_codes_lists_the_new_member_last() -> None:
    assert list(BoundRefusalCode)[-1] is BoundRefusalCode.RESOLUTION_MERGE_UNREVIEWED


# --------------------------------------------------------------------------- helper branches (fail closed)


def test_recorded_merge_attributes_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every unconfirmable attribute state reads as "not a tool merge": no source, older git, a guard refusal."""
    repo, _fd, _m, base, evil = _evil_claim(tmp_path)
    hold = approved_bound._recorded_merge_attributes_hold
    assert hold(repo, evil, base) is True, "no attribute anywhere: the record holds"
    assert hold(repo, evil, None) is False
    from specify_cli.git import merge_tree_probe

    with monkeypatch.context() as patch:
        patch.setattr(merge_tree_probe, "check_attr_source_available", lambda _repo: False)
        assert hold(repo, evil, base) is False
    from specify_cli.consolidation import merge_attribute_guard

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise GitProbeError("unregistered driver")

    with monkeypatch.context() as patch:
        patch.setattr(merge_attribute_guard, "assert_registered_merge_behaviour", _refuse)
        assert hold(repo, evil, base) is False
    assert hold(repo, "0" * 40, base) is False, "an unreadable merge never holds"


def test_canceled_window_with_a_missing_stamp_holds_every_merge(tmp_path: Path) -> None:
    """A canceled WP window whose cancel carried no stamp cannot be bounded: every merge reads as inside it."""
    repo, feature_dir, manifest, base, merge = _canceled_window_merge(tmp_path)
    log = feature_dir / "status.events.jsonl"
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        if row["wp_id"] == "WP02" and row["to_lane"] == "canceled":
            row.pop("policy_metadata", None)
    log.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    claim = _claim(repo, feature_dir, manifest, base, canceled=("WP02",))
    assert claim.refusal is not None and "inside canceled WP02's window" in claim.refusal, claim.refusal


# --------------------------------------------------------------------------- review cycle 1: a hand merge off the first-parent spine


def test_claim_refuses_a_hand_merge_hidden_behind_a_clean_merge(tmp_path: Path) -> None:
    repo, feature_dir, manifest, base, evil = _evil_claim(tmp_path)
    _off_spine(repo, evil)
    claim = _claim(repo, feature_dir, manifest, base)
    assert _CODE in _codes(claim) and _refused_merges(claim) == {evil[:7]}, claim.refusal


def test_advisory_field_names_the_hidden_hand_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WP06's hint reads ``unreviewed_merges``: on a claim built as the gate sees it, the hidden merge is named with its own content."""
    repo, feature_dir, manifest, base, evil = _evil_claim(tmp_path)
    hider = _off_spine(repo, evil)
    with monkeypatch.context() as patch:
        patch.setattr(reconciliation_bound, "unreviewed_resolution_merges", lambda *_a, **_k: ())
        claim = _claim(repo, feature_dir, manifest, base)
    entries = {entry.sha: entry for entry in claim.unreviewed_merges}
    assert entries[evil].lane_id == "lane-b" and entries[evil].own_paths == (_EVIL,)
    assert entries[hider].own_paths == (), "the spine's clean merge stays recorded as before"


def _hide_behind_clean_merge(mission: CoordMission) -> str:
    """The review repro: X = hand merge with its own content (-p A -p <mission tip>), T = clean merge (-p A -p X), lane reset to T."""
    worktree = lane_worktree(mission, "lane-a")
    approved_tip = git_rev(worktree, "HEAD")
    mission_tip = git_rev(mission.repo, mission.coord_branch)
    (worktree / LATE_PATH).parent.mkdir(parents=True, exist_ok=True)
    (worktree / LATE_PATH).write_text(LATE_CONTENT, encoding="utf-8")
    _git(worktree, "add", LATE_PATH)
    tree = _git(worktree, "write-tree")
    hand = _git(worktree, "commit-tree", tree, "-p", approved_tip, "-p", mission_tip, "-m", "hand merge")
    hider = _git(worktree, "commit-tree", tree, "-p", approved_tip, "-p", hand, "-m", "clean merge")
    _git(worktree, "reset", "-q", "--hard", hider)
    return hand


@pytest.mark.parametrize("strategy", ["squash", "merge"])
def test_hand_merge_off_the_spine_is_refused_before_any_branch_moves(tmp_path: Path, strategy: str) -> None:
    mission = build_post_approval_mission(tmp_path, "lanes")
    hand = _hide_behind_clean_merge(mission)
    before = _reflog_lengths(mission)

    code, flat = _consolidate(mission, "--yes", "--strategy", strategy)

    assert code != 0 and _CODE in flat and f"merge {hand[:7]}" in flat, flat
    assert "Reconciliation FAILED" not in flat, flat
    _assert_no_mutation(mission, before)


def test_resume_with_a_hand_merge_added_after_the_interrupt_does_not_land(tmp_path: Path) -> None:
    """The frozen lane tip and the gate re-check (``lane_tips_moved_refusal``) keep a hand merge made during the interrupt off the target."""
    mission = build_post_approval_mission(tmp_path, "coord")
    shape = _shape(mission, "coord")
    record = cs.interrupt_after_claim(shape)
    assert record.get("pre_interrupt_lane_tips"), sorted(record)
    hand = _hide_behind_clean_merge(mission)

    code, flat = _consolidate(mission, "--resume", "--yes")

    assert code != 0, flat
    assert LATE_PATH not in _git(mission.repo, "ls-tree", "-r", "--name-only", mission.target_branch).split(), flat
    # The resume rebuilds the claim, so the claim-time refusal names the hidden merge before any branch moves.
    assert "at claim time, before any change" in flat and _CODE in flat and f"merge {hand[:7]}" in flat, flat
