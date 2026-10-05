"""Truthful approval stamps for hand-built consolidation fixtures (#5668).

``consolidate`` bounds an approved work package to the commit its ``approved`` event
names (``policy_metadata.lane_head``). A fixture that writes the ``approved`` event BEFORE
the lane's code commit exists, and never stamps it, is a legacy mission whose approval
cannot be bounded: the claim refuses it (``APPROVAL_STAMP_MISSING``). The truthful
statement for such a fixture is "review approved the lane's code commit"; these helpers
record exactly that, once the lane commit exists. Never a product switch: the production
rule is unchanged, only the fixture states what was reviewed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from specify_cli.lanes.compute import is_planning_lane, lane_created_branch
from specify_cli.lanes.persistence import read_lanes_json


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
    return done.stdout.strip()


def with_lane_head(event: dict[str, object], lane_tip: str) -> dict[str, object]:
    """*event* carrying ``policy_metadata.lane_head = lane_tip`` (the commit review approved)."""
    existing = event.get("policy_metadata")
    metadata = dict(existing) if isinstance(existing, dict) else {}
    metadata["lane_head"] = lane_tip
    return {**event, "policy_metadata": metadata}


def approved_lane_tips(repo: Path, feature_dir: Path) -> dict[str, str]:
    """``{wp_id: tip}`` of every work package on an existing, non-planning lane branch."""
    manifest = read_lanes_json(feature_dir)
    assert manifest is not None, f"no lanes.json under {feature_dir}"
    tips: dict[str, str] = {}
    for lane in manifest.lanes:
        if is_planning_lane(lane):
            continue
        branch = lane_created_branch(manifest, lane.lane_id)
        if _git(repo, "branch", "--list", branch):
            tips.update({wp_id: _git(repo, "rev-parse", branch) for wp_id in lane.wp_ids})
    return tips


def restamp_log_at_lane_tips(repo: Path, feature_dir: Path, *, coord_branch: str | None = None) -> None:
    """Stamp every ``approved`` event of *feature_dir*'s log with its lane's CURRENT tip, and commit it.

    Call it once the lane commits exist, with the target branch checked out and the log
    tracked there. When *coord_branch* is given it is then fast-forwarded to the target, as
    the production fixtures do after writing their status log.
    """
    tips = approved_lane_tips(repo, feature_dir)
    log = feature_dir / "status.events.jsonl"
    original = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    events = [
        with_lane_head(event, tips[str(event["wp_id"])]) if event.get("to_lane") == "approved" and event.get("wp_id") in tips else event for event in original
    ]
    if events == original:
        return
    log.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")
    _git(repo, "add", str(log.relative_to(repo)))
    _git(repo, "commit", "-qm", "test: record that review approved the lane tips")
    if coord_branch is not None:
        _git(repo, "branch", "-f", coord_branch, _git(repo, "rev-parse", "HEAD"))
