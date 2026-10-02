"""Unit tests for the pure three-way recency helper (#3942 / WP02 T003).

Each test builds a temp git repo with a shared base commit, then advances the
target and/or a mission (lane) branch on the SAME PRIMARY-partition planning
file, and asserts ``target_newer_primary_artifacts`` returns exactly the paths
the target should keep. The helper is pure (git reads only), so these drive it
directly against real refs — no mocks.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation import planning_recency
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.consolidation.planning_recency import target_newer_primary_artifacts

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

MISSION_SLUG = "099-recency-helper"
SPEC_REL = f"kitty-specs/{MISSION_SLUG}/spec.md"
WP_REL = f"kitty-specs/{MISSION_SLUG}/tasks/WP01.md"
DRIVER_REL = f"kitty-specs/{MISSION_SLUG}/status.events.jsonl"
TARGET = "main"
SOURCE = "kitty/mission-recency-lane-a"


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _write(repo: Path, rel: str, content: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _commit(repo: Path, rel: str, content: str, message: str) -> None:
    _write(repo, rel, content)
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", message], repo)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", TARGET], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Spec Kitty"], repo)
    _run(["git", "config", "commit.gpgsign", "false"], repo)
    # Shared base commit both branches diverge from.
    _write(repo, SPEC_REL, "# Spec\n\nbase\n")
    _write(repo, WP_REL, "# WP01\n\nbase\n")
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", "base planning"], repo)
    return repo


def test_target_advanced_lane_stale_is_returned(tmp_path: Path) -> None:
    """Case 1: target advanced the path, lane never touched it → target-newer."""
    repo = _init_repo(tmp_path)
    _run(["git", "branch", SOURCE], repo)
    # Lane advances an UNRELATED file only; leaves spec.md at base.
    _run(["git", "checkout", SOURCE], repo)
    _commit(repo, WP_REL, "# WP01\n\nlane detail\n", "lane work (other file)")
    # Target advances spec.md.
    _run(["git", "checkout", TARGET], repo)
    _commit(repo, SPEC_REL, "# Spec\n\ntarget newer\n", "refine spec on target")

    result = target_newer_primary_artifacts(repo, TARGET, SOURCE)

    assert Path(SPEC_REL) in result
    # The lane-only file must NOT be flagged as target-newer.
    assert Path(WP_REL) not in result


def test_lane_advanced_only_is_not_returned(tmp_path: Path) -> None:
    """Case 2: only the lane advanced the path → -X theirs is correct; not returned."""
    repo = _init_repo(tmp_path)
    _run(["git", "branch", SOURCE], repo)
    _run(["git", "checkout", SOURCE], repo)
    _commit(repo, SPEC_REL, "# Spec\n\nlane newer\n", "refine spec on lane")
    # Target leaves spec.md at base (advances nothing on it).

    result = target_newer_primary_artifacts(repo, TARGET, SOURCE)

    assert Path(SPEC_REL) not in result


def test_both_advanced_target_later_wins_by_committer_date(tmp_path: Path) -> None:
    """Case 3 (documented tiebreak): both advanced → later committer-date wins.

    Target commits strictly after the lane, so the committer-date tiebreak keeps
    the target copy (target wins on later date or a tie).
    """
    repo = _init_repo(tmp_path)
    _run(["git", "branch", SOURCE], repo)
    # Lane edit first (older committer-date).
    _run(["git", "checkout", SOURCE], repo)
    _commit_dated(repo, SPEC_REL, "# Spec\n\nlane edit\n", "lane spec", "2026-01-01T00:00:00")
    # Target edit second (strictly-later committer-date).
    _run(["git", "checkout", TARGET], repo)
    _commit_dated(repo, SPEC_REL, "# Spec\n\ntarget edit\n", "target spec", "2026-06-01T00:00:00")

    result = target_newer_primary_artifacts(repo, TARGET, SOURCE)

    assert Path(SPEC_REL) in result


def test_both_advanced_lane_later_wins_is_not_returned(tmp_path: Path) -> None:
    """Case 3 mirror: both advanced but the LANE commit is strictly later → not returned."""
    repo = _init_repo(tmp_path)
    _run(["git", "branch", SOURCE], repo)
    _run(["git", "checkout", TARGET], repo)
    _commit_dated(repo, SPEC_REL, "# Spec\n\ntarget edit\n", "target spec", "2026-01-01T00:00:00")
    _run(["git", "checkout", SOURCE], repo)
    _commit_dated(repo, SPEC_REL, "# Spec\n\nlane edit\n", "lane spec", "2026-06-01T00:00:00")

    result = target_newer_primary_artifacts(repo, TARGET, SOURCE)

    assert Path(SPEC_REL) not in result


def test_driver_covered_kind_is_never_returned(tmp_path: Path) -> None:
    """FR-003: a driver-covered (non-primary) kind is excluded even when target-newer."""
    repo = _init_repo(tmp_path)
    # Seed the driver-covered file at base so a later target edit is a modify.
    _commit(repo, DRIVER_REL, '{"v": 0}\n', "seed driver artifact")
    _run(["git", "branch", SOURCE], repo)
    _run(["git", "checkout", TARGET], repo)
    _commit(repo, DRIVER_REL, '{"v": 1}\n', "advance driver artifact on target")

    result = target_newer_primary_artifacts(repo, TARGET, SOURCE)

    assert Path(DRIVER_REL) not in result


def test_equal_committer_date_tie_favours_target(tmp_path: Path) -> None:
    """Case 3 tie (pins the conservative default): equal committer-date → target wins.

    Both sides advance the same path at the byte-identical committer-date; the
    ``target_ct >= source_ct`` rule must keep the target copy (do-not-clobber default).
    """
    repo = _init_repo(tmp_path)
    _run(["git", "branch", SOURCE], repo)
    tie = "2026-03-15T12:00:00"
    _run(["git", "checkout", SOURCE], repo)
    _commit_dated(repo, SPEC_REL, "# Spec\n\nlane edit\n", "lane spec", tie)
    _run(["git", "checkout", TARGET], repo)
    _commit_dated(repo, SPEC_REL, "# Spec\n\ntarget edit\n", "target spec", tie)

    result = target_newer_primary_artifacts(repo, TARGET, SOURCE)

    assert Path(SPEC_REL) in result


def test_changed_paths_restricts_candidate_set(tmp_path: Path) -> None:
    """The optional ``changed_paths`` filter narrows the candidates a caller considers.

    Target advances both spec.md and WP01.md (both target-newer), but a caller
    that passes ``changed_paths=[SPEC_REL]`` gets only spec.md back — the WP path,
    though genuinely target-newer, is outside the supplied surface.
    """
    repo = _init_repo(tmp_path)
    _run(["git", "branch", SOURCE], repo)
    # Lane leaves both at base; target advances both.
    _run(["git", "checkout", TARGET], repo)
    _commit(repo, SPEC_REL, "# Spec\n\ntarget newer\n", "refine spec on target")
    _commit(repo, WP_REL, "# WP01\n\ntarget newer\n", "refine wp on target")

    unfiltered = target_newer_primary_artifacts(repo, TARGET, SOURCE)
    assert Path(SPEC_REL) in unfiltered and Path(WP_REL) in unfiltered

    filtered = target_newer_primary_artifacts(repo, TARGET, SOURCE, changed_paths=[SPEC_REL])
    assert filtered == [Path(SPEC_REL)]


def test_all_primary_planning_kinds_protected(tmp_path: Path) -> None:
    """Every PRIMARY-partition planning kind (not just spec.md/WP*.md) is protected.

    Pins the CHANGELOG/synthesis claim that plan.md, data-model.md and research.md
    are covered by the ``is_primary_artifact_kind`` classification, not only the two
    end-to-end specimen files.
    """
    repo = _init_repo(tmp_path)
    kinds = [
        f"kitty-specs/{MISSION_SLUG}/plan.md",
        f"kitty-specs/{MISSION_SLUG}/data-model.md",
        f"kitty-specs/{MISSION_SLUG}/research.md",
    ]
    for rel in kinds:
        _commit(repo, rel, "base\n", f"seed {rel}")
    _run(["git", "branch", SOURCE], repo)
    _run(["git", "checkout", TARGET], repo)
    for rel in kinds:
        _commit(repo, rel, "target newer\n", f"advance {rel} on target")

    result = target_newer_primary_artifacts(repo, TARGET, SOURCE)

    for rel in kinds:
        assert Path(rel) in result, f"{rel} should be protected as a primary planning kind"


DECISION_INDEX_REL = f"kitty-specs/{MISSION_SLUG}/decisions/index.json"


def test_decision_ledger_index_is_never_returned_as_target_newer(tmp_path: Path) -> None:
    """FORWARD GUARD (coord-artifact-single-home-01M3V4BE WP12, FR-009b, #5023):
    ``decisions/index.json`` is never flagged target-newer, even though it is
    a both-sides-divergent, both-advanced path here.

    Driver-covered PRIMARY-partition paths (today: only the decision-index
    ledger, WP11's ``spec-kitty-decision-index`` driver) must be excluded from
    this module's own target-favouring ``git merge-file --ours`` recency
    restore -- the driver already unions both sides' entries; letting this
    helper also flag the path would let ``lanes/consolidation.py``'s
    ``_restore_target_newer_planning`` silently overwrite the driver's unioned
    squash result with the target's pre-squash bytes, dropping a lane-added
    decision entry (FR-009b).

    This test is a FORWARD guard: GREEN at the WP base (the ledger is still a
    COORD-partition kind there, so ``_is_primary_planning_path`` already
    excludes it for an unrelated reason). It is RED on the commit that lands
    T065 (the artifacts.py reclassification) WITHOUT the driver-skip fix in
    this module, and GREEN again once the fix lands alongside it.
    """
    repo = _init_repo(tmp_path)
    _commit(repo, DECISION_INDEX_REL, '{"entries": []}\n', "seed decision index")
    _run(["git", "branch", SOURCE], repo)
    _run(["git", "checkout", SOURCE], repo)
    _commit_dated(repo, DECISION_INDEX_REL, '{"entries": [{"decision_id": "lane"}]}\n', "lane entry", "2026-01-01T00:00:00")
    _run(["git", "checkout", TARGET], repo)
    _commit_dated(repo, DECISION_INDEX_REL, '{"entries": [{"decision_id": "target"}]}\n', "target entry", "2026-06-01T00:00:00")

    result = target_newer_primary_artifacts(repo, TARGET, SOURCE)

    assert Path(DECISION_INDEX_REL) not in result, (
        "decisions/index.json must never be returned as target-newer -- it is "
        "driver-covered (spec-kitty-decision-index), and the recency restore "
        "would clobber the driver's unioned squash result"
    )


def _commit_dated(repo: Path, rel: str, content: str, message: str, iso: str) -> None:
    """Commit ``content`` to ``rel`` with a fixed author+committer date (stable tiebreak)."""
    import os

    _write(repo, rel, content)
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-m", message],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_COMMITTER_DATE": iso, "GIT_AUTHOR_DATE": iso},
    )


def test_unreadable_diff_refuses_instead_of_reporting_nothing_target_newer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-013: a failed ``git diff`` must not read as "target advanced nothing" —
    that empty set would let the squash overwrite target-newer PRIMARY artifacts."""
    repo = _init_repo(tmp_path)
    _run(["git", "branch", SOURCE], repo)
    _commit(repo, SPEC_REL, "# Spec\n\ntarget newer\n", "refine spec on target")
    monkeypatch.setattr(planning_recency, "git_diff_names_checked", lambda *_a, **_k: None)

    with pytest.raises(GitProbeError, match="git diff"):
        target_newer_primary_artifacts(repo, TARGET, SOURCE)
