"""Matrix writers take the Mission lock, and one key (mission-writer-followups WP04, US3).

* FR-004: ``scaffold_issue_matrix`` runs its exists check and its write in one hold, so a verdict recorded
  between them is never overwritten by the placeholder map.
* FR-005: the acceptance-matrix helpers, the verdict guard and the issue-verdict splice used to key their lock on
  ``matrix_dir.name``. On a legacy bare-directory coordination Mission that is ``060-test-01COORD0`` for a writer
  on the coordination directory and ``060-test`` for a writer on the primary directory: two lock files for one
  Mission, so the two never excluded each other. Every writer now keys through ``mission_lock_key``.
"""

from __future__ import annotations

import json
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import specify_cli.cli.commands.agent.issue_verdict as issue_verdict
import specify_cli.tasks.issue_matrix as issue_matrix
from specify_cli.acceptance import matrix as acceptance_matrix
from specify_cli.status import FeatureStatusLockTimeoutError, mission_lock_key
from specify_cli.status.locking import feature_status_lock_path, holds_status_lock
from specify_cli.tasks.issue_matrix import ISSUE_MATRIX_JSON_FILENAME, IssueMatrixEntry
from specify_cli.workspace.root_resolver import resolve_status_lock_root
from tests._meta_overlap import run_overlap

pytestmark = [pytest.mark.unit]

SLUG = "060-test"
MID8 = "01COORD0"
COORD_NAME = f"{SLUG}-{MID8}"
FLAT_SLUG = "070-flat"
JOIN_SECONDS = 20.0
SHORT_LOCK_WAIT = 0.3
ISSUE = "#5001"


class _OpenPolicy:
    """The duck-typed protection policy: nothing is protected."""

    def is_protected(self, ref: str) -> bool:
        return False


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True, capture_output=True)


def _write_meta(directory: Path, meta: dict[str, object]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return directory


@pytest.fixture
def bare_coord_mission(tmp_path: Path) -> tuple[Path, Path, Path]:
    """``(repo, primary_dir, coord_dir)`` for a legacy bare-directory coordination Mission."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_init(repo)
    primary = _write_meta(
        repo / "kitty-specs" / SLUG,
        {
            "mission_slug": SLUG,
            "slug": SLUG,
            "friendly_name": "Test",
            "mission_type": "software-dev",
            "target_branch": "main",
            "created_at": "2026-04-13T00:00:00+00:00",
            "mission_id": f"{MID8}XXXXXXXXXXXXXXXXXX",
            "mid8": MID8,
            "coordination_branch": f"kitty/mission-{COORD_NAME}",
        },
    )
    coord = repo / ".worktrees" / f"{COORD_NAME}-coord" / "kitty-specs" / COORD_NAME
    coord.mkdir(parents=True)
    return repo, primary, coord


@pytest.fixture
def flat_mission(tmp_path: Path) -> tuple[Path, Path]:
    """``(repo, feature_dir)`` for a flat Mission whose spec cites one implementation-target issue."""
    repo = tmp_path / "flat"
    repo.mkdir()
    _git_init(repo)
    feature_dir = _write_meta(repo / "kitty-specs" / FLAT_SLUG, {"mission_slug": FLAT_SLUG, "mission_type": "software-dev", "target_branch": "main"})
    (feature_dir / "spec.md").write_text(f"# Spec\n\nThis Mission fixes {ISSUE} in the code.\n", encoding="utf-8")
    return repo, feature_dir


def _fake_write_issue_matrix(**kwargs: Any) -> None:
    """The write step of the issue-verdict splice without the git commit, so the lock is the only variable."""
    matrix_dir: Path = kwargs["matrix_dir"]
    issue_matrix._atomic_write_issue_matrix(matrix_dir / ISSUE_MATRIX_JSON_FILENAME, kwargs["rows"])


# ---------------------------------------------------------------------------
# FR-004: the scaffold's exists check and write are one hold
# ---------------------------------------------------------------------------


def test_scaffold_does_not_overwrite_a_verdict_recorded_between_its_check_and_its_write(monkeypatch: pytest.MonkeyPatch, flat_mission: tuple[Path, Path]) -> None:
    repo, feature_dir = flat_mission
    monkeypatch.setattr(issue_verdict, "write_issue_matrix", _fake_write_issue_matrix)

    def scaffold() -> None:
        issue_matrix.scaffold_issue_matrix(
            feature_dir, feature_dir / "spec.md", repo_root=repo, mission_slug=FLAT_SLUG, policy=_OpenPolicy(), fold_into_caller_commit=True
        )

    def record_verdict() -> None:
        issue_verdict._locked_reread_splice_and_write(
            repo_root=repo,
            mission_slug=FLAT_SLUG,
            matrix_dir=feature_dir,
            issue_ref=ISSUE,
            updated_entry=IssueMatrixEntry(verdict="fixed", evidence_ref="abc123"),
            policy=_OpenPolicy(),
            actor="tester",
        )

    errors = run_overlap(
        monkeypatch,
        scaffold,
        record_verdict,
        pause_when=lambda path: path.name == ISSUE_MATRIX_JSON_FILENAME,
        atomic_modules=(issue_matrix,),
    )

    assert errors == []
    rows = json.loads((feature_dir / ISSUE_MATRIX_JSON_FILENAME).read_text(encoding="utf-8"))["rows"]
    assert rows[ISSUE]["verdict"] == "fixed"


def test_scaffold_is_idempotent_and_leaves_an_existing_matrix_alone(flat_mission: tuple[Path, Path]) -> None:
    repo, feature_dir = flat_mission
    existing = feature_dir / ISSUE_MATRIX_JSON_FILENAME
    existing.write_text('{"keep": "me"}\n', encoding="utf-8")

    result = issue_matrix.scaffold_issue_matrix(
        feature_dir, feature_dir / "spec.md", repo_root=repo, mission_slug=FLAT_SLUG, policy=_OpenPolicy(), fold_into_caller_commit=True
    )

    assert result == existing
    assert existing.read_text(encoding="utf-8") == '{"keep": "me"}\n'


# ---------------------------------------------------------------------------
# FR-005: key or root? the bare-directory coordination Mission
# ---------------------------------------------------------------------------


def test_the_two_directories_share_one_root_so_the_key_is_the_divergence(bare_coord_mission: tuple[Path, Path, Path]) -> None:
    """Cause of FR-005 on this fixture: the keys differ; the lock root does not (plan A9)."""
    repo, primary, coord = bare_coord_mission
    assert resolve_status_lock_root(primary, repo) == resolve_status_lock_root(coord, repo) == repo
    # The old keying, ``feature_status_lock(repo_root, matrix_dir.name)``, names two different lock files.
    assert feature_status_lock_path(repo, coord.name) != feature_status_lock_path(repo, primary.name)
    # The canonical key names one.
    assert mission_lock_key(primary, repo_root=repo) == mission_lock_key(coord, repo_root=repo) == COORD_NAME


def _acceptance_splice(repo: Path, matrix_dir: Path, hold: Callable[[], None]) -> None:
    acceptance_matrix.locked_reread_splice_and_write(
        repo_root=repo, mission_slug=SLUG, matrix_dir=matrix_dir, splice=lambda _matrix: hold(), commit=False, timeout=SHORT_LOCK_WAIT
    )


def _issue_row_splice(repo: Path, matrix_dir: Path, hold: Callable[[], None]) -> None:
    def write(**kwargs: Any) -> None:
        hold()
        _fake_write_issue_matrix(**kwargs)

    patcher = pytest.MonkeyPatch()
    patcher.setattr(issue_verdict, "write_issue_matrix", write)
    try:
        issue_verdict._locked_reread_splice_and_write(
            repo_root=repo,
            mission_slug=SLUG,
            matrix_dir=matrix_dir,
            issue_ref=ISSUE,
            updated_entry=IssueMatrixEntry(verdict="fixed"),
            policy=_OpenPolicy(),
            actor="tester",
        )
    finally:
        patcher.undo()


def _verdict_guard(repo: Path, matrix_dir: Path, hold: Callable[[], None]) -> None:
    with acceptance_matrix.locked_acceptance_verdict_guard(repo, matrix_dir, timeout=SHORT_LOCK_WAIT):
        hold()


SECTIONS: dict[str, Callable[[Path, Path, Callable[[], None]], None]] = {
    "acceptance_splice": _acceptance_splice,
    "issue_row_splice": _issue_row_splice,
    "verdict_guard": _verdict_guard,
}


def _seed_passing_matrix(matrix_dir: Path) -> None:
    """A matrix whose verdict is ready, so the verdict guard reaches its critical section."""
    criterion = acceptance_matrix.AcceptanceCriterion(criterion_id="AC-001", description="Works", proof_type="manual_qa", evidence="checked", pass_fail="pass")
    acceptance_matrix.write_acceptance_matrix(matrix_dir, acceptance_matrix.AcceptanceMatrix(mission_slug=SLUG, criteria=[criterion]))


def _hold_section_on_thread(section: str, repo: Path, matrix_dir: Path) -> tuple[threading.Thread, threading.Event, threading.Event]:
    inside, release = threading.Event(), threading.Event()

    def hold() -> None:
        inside.set()
        release.wait(JOIN_SECONDS)

    thread = threading.Thread(target=lambda: SECTIONS[section](repo, matrix_dir, hold), name=f"holder-{section}")
    thread.start()
    assert inside.wait(JOIN_SECONDS), f"{section} never reached its critical section"
    return thread, inside, release


@pytest.mark.parametrize("held_by", ["acceptance_splice", "issue_row_splice"])
@pytest.mark.parametrize("contender", ["acceptance_splice", "issue_row_splice", "verdict_guard"])
def test_matrix_writers_on_the_two_directories_of_one_mission_exclude_each_other(
    monkeypatch: pytest.MonkeyPatch, bare_coord_mission: tuple[Path, Path, Path], held_by: str, contender: str
) -> None:
    repo, primary, coord = bare_coord_mission
    monkeypatch.setattr(issue_verdict, "BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS", SHORT_LOCK_WAIT)
    _seed_passing_matrix(primary)
    holder, _inside, release = _hold_section_on_thread(held_by, repo, coord)
    try:
        with pytest.raises(FeatureStatusLockTimeoutError):
            SECTIONS[contender](repo, primary, lambda: None)
    finally:
        release.set()
        holder.join(JOIN_SECONDS)
    assert not holder.is_alive()


def test_the_verdict_guard_and_the_nested_acceptance_record_share_one_reentrant_lock(bare_coord_mission: tuple[Path, Path, Path]) -> None:
    """``record_acceptance`` inside the guard nests on the guard's lock instead of taking a second one (WP02, A13)."""
    from specify_cli.mission_metadata import record_acceptance

    repo, primary, coord = bare_coord_mission
    _seed_passing_matrix(coord)
    lock_path = feature_status_lock_path(repo, COORD_NAME)
    with acceptance_matrix.locked_acceptance_verdict_guard(repo, coord, timeout=SHORT_LOCK_WAIT):
        assert holds_status_lock(lock_path)
        record_acceptance(primary, accepted_by="tester", mode="local")
        assert holds_status_lock(lock_path)
    assert not holds_status_lock(lock_path)


def test_the_guard_still_refuses_a_missing_matrix(bare_coord_mission: tuple[Path, Path, Path]) -> None:
    repo, primary, _coord = bare_coord_mission
    with (
        pytest.raises(acceptance_matrix.AcceptanceVerdictNotReadyError),
        acceptance_matrix.locked_acceptance_verdict_guard(repo, primary, timeout=SHORT_LOCK_WAIT),
    ):
        pytest.fail("a missing matrix is never ready")
