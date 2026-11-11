"""#7556: record-analysis refuses only on this Mission's own uncommitted paths.

Before the fix, ``agent mission record-analysis`` refused ``DIRTY_WORKTREE`` on any
uncommitted path outside spec-kitty's bookkeeping, including another Mission's
untracked files. Agents worked around it by stashing, excluding or moving those
files. The write commits only the analysis report, so dirt outside this Mission
cannot be mixed into it: it is now reported as a warning. This Mission's own
uncommitted edits still refuse (same fixture, the control).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.cli_mission_fixture_7545 import ANALYSIS_BODY, create_mission, dirty, flat, init_repo, json_of

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(900)]


def _record(mission, tmp_path: Path, *extra: str):
    body = tmp_path / "report.md"
    body.write_text(ANALYSIS_BODY + "\nRe-run.\n", encoding="utf-8")
    return mission.run("agent", "mission", "record-analysis", "--mission", mission.slug, "--input-file", str(body), *extra)


@pytest.fixture()
def mission(tmp_path: Path):
    repo, env = init_repo(tmp_path)
    return create_mission(repo, env, "alpha", topology="single_branch")


def test_another_missions_untracked_files_do_not_refuse_record_analysis(mission, tmp_path: Path) -> None:
    other = mission.repo / "kitty-specs" / "other-01ABCDEF"
    other.mkdir(parents=True)
    (other / "notes.md").write_text("another Mission's residue\n", encoding="utf-8")

    proc = _record(mission, tmp_path, "--json")

    assert proc.returncode == 0, flat(proc)[-2000:]
    payload = json_of(proc)
    assert payload["success"] is True
    assert payload["foreign_dirty_paths"] == ["kitty-specs/other-01ABCDEF/"]
    # The report was committed; the other Mission's file is untouched and still untracked.
    assert dirty(mission.repo) == ["kitty-specs/other-01ABCDEF/notes.md"]


def test_dirt_outside_every_mission_is_a_warning_in_human_output(mission, tmp_path: Path) -> None:
    (mission.repo / "dirty.txt").write_text("operator scratch\n", encoding="utf-8")

    proc = _record(mission, tmp_path)

    assert proc.returncode == 0, flat(proc)[-2000:]
    assert "dirty.txt" in flat(proc)
    assert "dirty.txt" in dirty(mission.repo)


def test_this_missions_own_uncommitted_edit_still_refuses(mission, tmp_path: Path) -> None:
    other = mission.repo / "kitty-specs" / "other-01ABCDEF"
    other.mkdir(parents=True)
    (other / "notes.md").write_text("another Mission's residue\n", encoding="utf-8")
    spec = mission.feature_dir / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\n- **FR-002**: edited, not committed.\n", encoding="utf-8")

    proc = _record(mission, tmp_path, "--json")

    assert proc.returncode == 1, flat(proc)[-2000:]
    payload = json_of(proc)
    assert payload["error_code"] == "DIRTY_WORKTREE"
    assert payload["dirty_paths"] == [f"kitty-specs/{mission.slug}/spec.md"]
