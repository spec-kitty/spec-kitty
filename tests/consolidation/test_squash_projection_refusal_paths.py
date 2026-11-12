"""The squash projection refusal names what did not land, and why (#5867).

Two levels:

* the per-path proof (``bookkeeping_projection.unlanded_projected_paths``) returns
  ``(path, ProjectedPathReason)`` for every projected path that did not land, one cell
  per reason, on real git repositories (the driver replay runs the real registered
  drivers, as in ``test_bookkeeping_projection_seam.py``);
* the gate (``phase_gate._assert_squash_projected_content_landed``) renders the code
  ``SQUASH_PROJECTION_NOT_LANDED``, the paths (at most 20, then a count), a remedy per
  reason, and still exits 1 inside the executor's single rollback door.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import typer

from specify_cli.consolidation import bookkeeping_projection as bp
from specify_cli.consolidation import git_probes
from specify_cli.consolidation import phase_gate
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.git_probes import GitProbeError, MergeDriverNotRegisteredError, driver_replay_expected_bytes
from specify_cli.consolidation.run_state import _CoordCheckpoint

pytestmark = pytest.mark.fast

_TRACE = "kitty-specs/m/traces/WP01.md"  # a path with a registered merge driver
_NOTE = "kitty-specs/m/notes/some-note.md"  # a path with no registered merge driver
_MATRIX = "kitty-specs/m/issue-matrix.json"
_PHRASE = "projected coordination bookkeeping content did not land"
_CODE_LINE = "Error code: SQUASH_PROJECTION_NOT_LANDED."


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


def _commit(repo: Path, rel: str, body: str | None, msg: str) -> str:
    path = repo / rel
    if body is None:
        path.unlink()
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def _coord_commit(repo: Path, base: str, rel: str, body: str | None) -> None:
    """Create ``coord`` at *base* and change *rel* there, then return to ``main``."""
    _git(repo, "branch", "coord", base)
    _git(repo, "checkout", "-q", "coord")
    _commit(repo, rel, body, "coord update")
    _git(repo, "checkout", "-q", "main")


def _unlanded(repo: Path, paths: tuple[str, ...], checkpoint: str, pre_squash: str) -> list[tuple[str, bp.ProjectedPathReason]]:
    return bp.unlanded_projected_paths(
        main_repo=repo,
        coord_ref="coord",
        target_ref="main",
        projected_paths=paths,
        checkpoint_sha=checkpoint,
        pre_squash_target_ref=pre_squash,
    )


def _diverged_repo(tmp_path: Path, rel: str) -> tuple[Path, str, str]:
    """Both the target and ``coord`` changed *rel* after the checkpoint."""
    repo = _init_repo(tmp_path)
    checkpoint = _commit(repo, rel, "baseline\n", "checkpoint")
    pre_squash = _commit(repo, rel, "baseline\ntarget edit\n", "target update")
    _coord_commit(repo, checkpoint, rel, "baseline\ncoord edit\n")
    return repo, checkpoint, pre_squash


# --- per-path reasons --------------------------------------------------------


@pytest.mark.git_repo
def test_a_landed_path_is_not_reported(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    checkpoint = _commit(repo, _MATRIX, "{}\n", "checkpoint")
    _coord_commit(repo, checkpoint, _MATRIX, '{"a": 1}\n')
    _commit(repo, _MATRIX, '{"a": 1}\n', "projected")
    assert _unlanded(repo, (_MATRIX,), checkpoint, checkpoint) == []


@pytest.mark.git_repo
def test_target_untouched_since_checkpoint_but_bytes_differ_is_content_differs(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    checkpoint = _commit(repo, _MATRIX, "{}\n", "checkpoint")
    _coord_commit(repo, checkpoint, _MATRIX, '{"a": 1}\n')
    _commit(repo, _MATRIX, '{"a": 2}\n', "wrong landing")
    assert _unlanded(repo, (_MATRIX,), checkpoint, checkpoint) == [(_MATRIX, bp.ProjectedPathReason.CONTENT_DIFFERS)]


@pytest.mark.git_repo
def test_a_path_the_coordination_branch_deleted_is_coordination_blob_missing(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    checkpoint = _commit(repo, _MATRIX, "{}\n", "checkpoint")
    _coord_commit(repo, checkpoint, _MATRIX, None)
    assert _unlanded(repo, (_MATRIX,), checkpoint, checkpoint) == [(_MATRIX, bp.ProjectedPathReason.COORDINATION_BLOB_MISSING)]


@pytest.mark.git_repo
def test_a_diverged_path_with_no_registered_driver_is_no_merge_driver(tmp_path: Path) -> None:
    repo, checkpoint, pre_squash = _diverged_repo(tmp_path, _NOTE)
    _commit(repo, _NOTE, "baseline\ntarget edit\ncoord edit\n", "auto-merged landing")
    assert _unlanded(repo, (_NOTE,), checkpoint, pre_squash) == [(_NOTE, bp.ProjectedPathReason.NO_MERGE_DRIVER)]


@pytest.mark.git_repo
def test_a_diverged_path_whose_landing_is_not_the_driver_output_is_merge_driver_mismatch(tmp_path: Path) -> None:
    repo, checkpoint, pre_squash = _diverged_repo(tmp_path, _TRACE)
    _commit(repo, _TRACE, "baseline\ncoord edit\n", "lossy landing")
    assert _unlanded(repo, (_TRACE,), checkpoint, pre_squash) == [(_TRACE, bp.ProjectedPathReason.MERGE_DRIVER_MISMATCH)]


@pytest.mark.git_repo
def test_a_diverged_path_whose_landing_is_the_driver_output_is_landed(tmp_path: Path) -> None:
    repo, checkpoint, pre_squash = _diverged_repo(tmp_path, _TRACE)
    expected = driver_replay_expected_bytes(repo, _TRACE, base_ref=checkpoint, ours_ref=pre_squash, theirs_ref="coord")
    _commit(repo, _TRACE, expected.decode("utf-8"), "driver landing")
    assert _unlanded(repo, (_TRACE,), checkpoint, pre_squash) == []


@pytest.mark.git_repo
def test_a_probe_error_during_driver_replay_is_probe_failed(tmp_path: Path) -> None:
    repo, checkpoint, pre_squash = _diverged_repo(tmp_path, _TRACE)
    with patch.object(bp, "driver_replay_expected_bytes", side_effect=GitProbeError("git broke")):
        assert _unlanded(repo, (_TRACE,), checkpoint, pre_squash) == [(_TRACE, bp.ProjectedPathReason.PROBE_FAILED)]


@pytest.mark.git_repo
def test_a_failed_attribute_probe_is_probe_failed_not_no_merge_driver(tmp_path: Path) -> None:
    """A non-zero ``git check-attr`` (here: an unresolvable pre-squash ref) is a probe failure, never a missing driver."""
    repo, checkpoint, _pre_squash = _diverged_repo(tmp_path, _TRACE)
    assert _unlanded(repo, (_TRACE,), checkpoint, "refs/heads/no-such-branch") == [(_TRACE, bp.ProjectedPathReason.PROBE_FAILED)]


@pytest.mark.git_repo
def test_the_attribute_probe_raises_on_a_git_failure(tmp_path: Path) -> None:
    repo, _checkpoint, _pre_squash = _diverged_repo(tmp_path, _TRACE)
    with pytest.raises(GitProbeError) as excinfo:
        git_probes._resolve_merge_driver_config_key(repo, "refs/heads/no-such-branch", _TRACE)
    assert not isinstance(excinfo.value, MergeDriverNotRegisteredError)


@pytest.mark.git_repo
def test_a_driver_that_raises_is_merge_driver_failed(tmp_path: Path) -> None:
    """A driver refusing the content (e.g. malformed rows) is deterministic: a re-run repeats it."""
    repo, checkpoint, pre_squash = _diverged_repo(tmp_path, _TRACE)

    def _refusing_driver(_base: str, _ours: str, _theirs: str) -> None:
        raise ValueError("malformed content")

    with patch.object(git_probes, "_resolve_registered_driver_callable", return_value=_refusing_driver):
        assert _unlanded(repo, (_TRACE,), checkpoint, pre_squash) == [(_TRACE, bp.ProjectedPathReason.MERGE_DRIVER_FAILED)]


def test_a_config_key_with_no_registry_entry_is_a_driver_failure() -> None:
    with pytest.raises(git_probes.MergeDriverFailedError):
        git_probes._resolve_registered_driver_callable("spec-kitty-does-not-exist")


@pytest.mark.git_repo
def test_every_failing_path_is_reported_in_order(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, _NOTE, "n\n", "note")
    checkpoint = _commit(repo, _MATRIX, "{}\n", "checkpoint")
    _git(repo, "branch", "coord", checkpoint)
    _git(repo, "checkout", "-q", "coord")
    _commit(repo, _MATRIX, '{"a": 1}\n', "coord matrix")
    _commit(repo, _NOTE, None, "coord drops note")
    _git(repo, "checkout", "-q", "main")
    paths = (_NOTE, "README.md", _MATRIX)
    assert _unlanded(repo, paths, checkpoint, checkpoint) == [
        (_NOTE, bp.ProjectedPathReason.COORDINATION_BLOB_MISSING),
        (_MATRIX, bp.ProjectedPathReason.CONTENT_DIFFERS),
    ]


# --- the gate's refusal -------------------------------------------------------


def _stub_run(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        strategy=MergeStrategy.SQUASH,
        coord_checkpoint=_CoordCheckpoint(ref="refs/heads/kitty/mission-m-01ABCDEF", sha="c" * 40),
        main_repo=tmp_path,
        mission_slug="m",
        target_expected_old_sha="d" * 40,
        lanes_manifest=SimpleNamespace(target_branch="main"),
    )


def _refuse(tmp_path: Path, capsys: pytest.CaptureFixture[str], unlanded: list[tuple[str, bp.ProjectedPathReason]]) -> str:
    paths = [p for p, _ in unlanded] or [_MATRIX]
    with (
        patch.object(phase_gate, "_post_checkpoint_mission_paths", return_value=paths),
        patch.object(phase_gate, "unlanded_projected_paths", return_value=unlanded),
        pytest.raises(typer.Exit) as excinfo,
    ):
        phase_gate._assert_squash_projected_content_landed(_stub_run(tmp_path))  # type: ignore[arg-type]  # a stub run carries only the fields the gate reads
    assert excinfo.value.exit_code == 1
    return " ".join(capsys.readouterr().out.split())


def test_the_refusal_names_the_code_the_phrase_the_path_and_the_remedy(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = _refuse(tmp_path, capsys, [(_MATRIX, bp.ProjectedPathReason.CONTENT_DIFFERS)])
    assert _PHRASE in out
    assert _CODE_LINE in out
    assert _MATRIX in out
    assert "kitty/mission-m-01ABCDEF" in out
    assert "Nothing was torn down" in out
    assert "rolled back" not in out  # the rollback door reports its own outcome (#5867 review)
    assert "make the target's copy match the coordination branch" in out


def test_a_clean_proof_does_not_refuse(tmp_path: Path) -> None:
    with (
        patch.object(phase_gate, "_post_checkpoint_mission_paths", return_value=[_MATRIX]),
        patch.object(phase_gate, "unlanded_projected_paths", return_value=[]),
    ):
        phase_gate._assert_squash_projected_content_landed(_stub_run(tmp_path))  # type: ignore[arg-type]  # a stub run carries only the fields the gate reads


@pytest.mark.parametrize(
    ("reason", "remedy"),
    [
        (bp.ProjectedPathReason.CONTENT_DIFFERS, "make the target's copy match the coordination branch"),
        (bp.ProjectedPathReason.MERGE_DRIVER_MISMATCH, "make the target's copy match the coordination branch"),
        (bp.ProjectedPathReason.NO_MERGE_DRIVER, "has no merge driver"),
        (bp.ProjectedPathReason.MERGE_DRIVER_FAILED, "merge driver refused"),
        (bp.ProjectedPathReason.COORDINATION_BLOB_MISSING, "restore it on the coordination branch"),
        (bp.ProjectedPathReason.PROBE_FAILED, "may succeed"),
    ],
)
def test_each_reason_has_its_own_remedy(tmp_path: Path, capsys: pytest.CaptureFixture[str], reason: bp.ProjectedPathReason, remedy: str) -> None:
    out = _refuse(tmp_path, capsys, [(_MATRIX, reason)])
    assert remedy in out
    assert _CODE_LINE in out


@pytest.mark.parametrize(
    "reason",
    [
        bp.ProjectedPathReason.CONTENT_DIFFERS,
        bp.ProjectedPathReason.MERGE_DRIVER_MISMATCH,
        bp.ProjectedPathReason.NO_MERGE_DRIVER,
        bp.ProjectedPathReason.MERGE_DRIVER_FAILED,
        bp.ProjectedPathReason.COORDINATION_BLOB_MISSING,
    ],
)
def test_a_deterministic_cause_never_says_a_rerun_may_succeed(tmp_path: Path, capsys: pytest.CaptureFixture[str], reason: bp.ProjectedPathReason) -> None:
    out = _refuse(tmp_path, capsys, [(_MATRIX, reason)])
    assert "may succeed" not in out


def test_the_refusal_lists_at_most_twenty_paths_then_a_count(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    unlanded = [(f"kitty-specs/m/traces/WP{i:02d}.md", bp.ProjectedPathReason.CONTENT_DIFFERS) for i in range(1, 26)]
    out = _refuse(tmp_path, capsys, unlanded)
    assert "kitty-specs/m/traces/WP20.md" in out
    assert "kitty-specs/m/traces/WP21.md" not in out
    assert "and 5 more" in out


def test_remedies_are_given_once_per_reason(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    unlanded = [
        (_MATRIX, bp.ProjectedPathReason.CONTENT_DIFFERS),
        (_TRACE, bp.ProjectedPathReason.MERGE_DRIVER_MISMATCH),
        (_NOTE, bp.ProjectedPathReason.PROBE_FAILED),
    ]
    out = _refuse(tmp_path, capsys, unlanded)
    assert out.count("make the target's copy match the coordination branch") == 1
    assert out.count("may succeed") == 1


def test_the_rendered_text_lists_each_path_with_its_reason() -> None:
    text = phase_gate._render_unlanded_projection(
        [(_MATRIX, bp.ProjectedPathReason.CONTENT_DIFFERS), (_NOTE, bp.ProjectedPathReason.COORDINATION_BLOB_MISSING)],
        "refs/heads/coord",
        "main",
    )
    lines = text.splitlines()
    assert any(_MATRIX in line and "differs from coord" in line for line in lines)
    assert any(_NOTE in line and "coord" in line for line in lines)
    assert lines[-1].strip() == _CODE_LINE


def test_no_merge_driver_never_suggests_upgrade(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The replay activates every registered driver itself, so ``spec-kitty upgrade`` cannot add one (#5867 review)."""
    out = _refuse(tmp_path, capsys, [(_NOTE, bp.ProjectedPathReason.NO_MERGE_DRIVER)])
    assert "spec-kitty upgrade" not in out
    assert "make the target's copy match the coordination branch" in out


def test_a_probe_failure_says_what_to_do_if_it_repeats(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = _refuse(tmp_path, capsys, [(_MATRIX, bp.ProjectedPathReason.PROBE_FAILED)])
    assert "if the failure was transient" in out
    assert "if it repeats" in out


def test_a_resume_whose_landing_already_passed_refuses_without_claiming_a_rollback(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """On a resume at a verified PASS anchor the rollback door keeps the landing, so the refusal must not say it rolled back."""
    run = _stub_run(tmp_path)
    run.is_resume = True
    run.reconciliation_result = None
    with (
        patch.object(phase_gate, "_resume_reconciliation_already_passed", return_value=True),
        patch.object(phase_gate, "_post_checkpoint_mission_paths", return_value=[_MATRIX]),
        patch.object(phase_gate, "unlanded_projected_paths", return_value=[(_MATRIX, bp.ProjectedPathReason.CONTENT_DIFFERS)]),
        pytest.raises(typer.Exit) as excinfo,
    ):
        phase_gate._phase_reconcile_before_teardown(run)  # type: ignore[arg-type]  # a stub run carries only the fields the gate reads
    assert excinfo.value.exit_code == 1
    out = " ".join(capsys.readouterr().out.split())
    assert _CODE_LINE in out
    assert _MATRIX in out
    assert "rolled back" not in out
    assert "Reconciliation verified" not in out
