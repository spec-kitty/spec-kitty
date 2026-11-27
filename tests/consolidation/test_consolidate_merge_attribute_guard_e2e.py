"""#5604 review fold I1 through ``spec-kitty consolidate``: an uncommitted ``merge=union`` in a lane checkout lands nothing.

The #7755 two-lane shape: ``lane-a`` and ``lane-b`` are approved and edit adjacent hunks of one
file, so stock git conflicts when ``consolidate`` auto-rebases ``lane-b`` onto the Mission branch
that now holds ``lane-a``. An uncommitted ``.gitattributes`` with ``merge=union`` in ``lane-b``'s
checkout turned that conflict into a clean merge of bytes no reviewer approved; before the fold the
tool recorded the merge, the claim exempted it as a tool merge, and the Mission landed at exit 0.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.consolidation import stale_sibling_lane_support
from tests.consolidation.stale_sibling_lane_support import LANE_A_TEXT, LANE_B_TEXT, POPUP, SEED, build_stale_sibling_mission
from tests.terminus.conftest import git_out, git_rev, run_terminus

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.slow]


def _flat(result: subprocess.CompletedProcess[str]) -> str:
    return " ".join(((result.stdout or "") + (result.stderr or "")).split())


def _show(repo: Path, ref: str, path: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{path}"], capture_output=True, text=True, check=True).stdout


def test_an_uncommitted_union_in_a_lane_checkout_does_not_land_through_consolidate(tmp_path: Path) -> None:
    scenario = build_stale_sibling_mission(tmp_path)
    mission = scenario.mission
    # The file is ignored (an operator's exclude), so consolidate's dirty-checkout preflight does not see it.
    exclude = Path(git_out(mission.repo, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a", encoding="utf-8") as handle:
        handle.write(".gitattributes\n")
    (scenario.lane_b_worktree / ".gitattributes").write_text(f"{POPUP} merge=union\n", encoding="utf-8")
    tips = {ref: git_rev(mission.repo, ref) for ref in (mission.target_branch, mission.coord_branch, scenario.lane_a_branch, scenario.lane_b_branch)}

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug])

    flat = _flat(result)
    assert result.returncode != 0, flat
    assert "Reconciliation verified" not in flat, flat
    assert "lane-b is stale" in flat and "union" in flat, flat
    for ref, before in tips.items():
        assert git_rev(mission.repo, ref) == before, f"{ref} was left moved: {flat}"
    assert _show(mission.repo, mission.target_branch, POPUP) == SEED
    assert (scenario.lane_b_worktree / POPUP).read_text(encoding="utf-8") == LANE_B_TEXT
    assert git_out(mission.repo, "for-each-ref", "refs/spec-kitty/auto-rebase/") == "", "no auto-rebase merge was recorded"
    assert LANE_A_TEXT != LANE_B_TEXT  # fixture sanity: the two lanes really differ


def _pyproject(deps: list[str]) -> str:
    return '[project]\nname = "demo"\ndependencies = [\n' + "".join(f'  "{dep}",\n' for dep in deps) + "]\n"


def _owning_pyproject(wp: str) -> str:
    return f"---\nwork_package_id: {wp}\ntitle: {wp} work\ndependencies: []\nsubtasks: []\nowned_files:\n  - pyproject.toml\n---\n# {wp}\n"


def test_an_in_run_novel_tool_resolution_is_failed_by_the_gate_and_rolled_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5604 review fold A2 evidence: the gate never reads the auto-rebase record and FAILs a recorded tool resolution
    whose bytes no approval stamp reached.

    Both lanes add a dependency; the in-run auto-rebase resolves the conflict additively and records the merge. The
    claim ran before that merge existed, so the gate is its judge here: it FAILs ``pyproject.toml`` as un-attributable
    and the one rollback restores every branch, the auto-rebased lane included. A merge recorded BEFORE a run is now
    refused at claim time instead (the predicate section of ``test_resolution_merge_unreviewed.py``,
    ``test_forged_record_is_harmless_the_claim_refuses_first``).
    """
    monkeypatch.setattr(stale_sibling_lane_support, "POPUP", "pyproject.toml")
    monkeypatch.setattr(stale_sibling_lane_support, "SEED", _pyproject(["alpha", "bravo"]))
    monkeypatch.setattr(stale_sibling_lane_support, "LANE_A_TEXT", _pyproject(["alpha", "bravo", "charlie"]))
    monkeypatch.setattr(stale_sibling_lane_support, "LANE_B_TEXT", _pyproject(["alpha", "bravo", "delta"]))
    monkeypatch.setattr(stale_sibling_lane_support, "_wp_file", _owning_pyproject)
    scenario = build_stale_sibling_mission(tmp_path)
    mission = scenario.mission
    tips = {ref: git_rev(mission.repo, ref) for ref in (mission.target_branch, mission.coord_branch, scenario.lane_b_branch)}

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug])

    flat = _flat(result)
    assert result.returncode != 0, flat
    assert "✓ lane-b →" in flat, f"fixture: the in-run auto-rebase must have resolved lane-b:\n{flat}"
    assert "Reconciliation FAILED: file 'pyproject.toml'" in flat and "un-attributable" in flat, flat
    for ref, before in tips.items():
        assert git_rev(mission.repo, ref) == before, f"{ref} was left moved: {flat}"
