"""Repro #4969 — ``implement`` cuts a fresh lane from local main, shadowing an
approved lane that exists only as ``origin/<lane>``.

Mechanism (DEBRIEF §4, root R2 / C-4): lane base resolution does not consult the
origin ref. When an approved lane branch exists only remotely (``origin/<lane>``)
and not locally, ``implement``'s workspace allocation cuts a fresh lane branch
from local ``main`` instead of resolving off ``origin/<lane>`` — so the approved
remote work is shadowed. Backstopped by origin-aware base resolution + stable lane
identity (WP03/WP04, C-4).

RED-first: driven through the REAL ``spec-kitty implement`` CLI (no ``_run_git`` /
subprocess mocking). The approved lane commit is pushed to a real bare origin and
the local lane branch deleted, so it lives only as ``origin/<lane>``. Today the
lane ``implement`` resolves does NOT descend from ``origin/<lane>`` → the
"origin tip is an ancestor" assertion fails → ``xfail(strict=True)``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import build_coord_mission, run_terminus, sha_reachable

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def test_4969_implement_base_must_consult_origin_lane_ref(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M4969A")

    # ``implement``'s workspace allocator requires a fuller meta.json than the merge
    # path — enrich it (fixture surgery, not a CLI mock) so control reaches base
    # resolution rather than failing early on schema validation.
    meta_path = mission.feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update({"created_at": "2026-09-24T00:00:00+00:00", "friendly_name": "Terminus Repro", "slug": mission.slug})
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _git(mission.repo, "add", "-A")
    _git(mission.repo, "commit", "-qm", "chore: enrich meta for implement")

    lane = mission.lane_branch("WP01")

    # The approved lane exists ONLY as origin/<lane>: push it, then drop the local ref.
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
    _git(mission.repo, "remote", "add", "origin", str(bare))
    _git(mission.repo, "push", "-q", "origin", f"{lane}:{lane}")
    _git(mission.repo, "push", "-q", "origin", f"{mission.target_branch}:{mission.target_branch}")
    origin_lane_tip = mission.rev(f"origin/{lane}")
    assert origin_lane_tip, "fixture precondition: origin/<lane> must resolve"
    _git(mission.repo, "branch", "-D", lane)
    assert not mission.rev(lane), "fixture precondition: local lane must be gone"

    run_terminus(mission, ["implement", "WP01", "--mission", mission.slug, "--no-auto-commit"])

    # Corrected invariant: the resolved lane's base consults origin/<lane>, so the
    # approved remote tip is reachable from it. Today implement ignores origin and
    # cuts fresh from local main → origin tip is NOT an ancestor of the resolved lane.
    assert sha_reachable(mission.repo, origin_lane_tip, lane), (
        f"implement's lane base did not consult origin/{lane} (tip {origin_lane_tip[:10]}): "
        f"the approved remote lane was shadowed by a fresh cut from local main (#4969)"
    )
