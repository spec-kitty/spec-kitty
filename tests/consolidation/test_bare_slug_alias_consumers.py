"""Consolidation consumers of the bare-slug directory alias (#5651, FR-003, FR-019).

A coordination Mission whose primary directory is the bare slug
(``kitty-specs/<slug>``) while its coordination directory carries the composed
``<slug>-<mid8>`` name ends a consolidation with ONE Mission directory on the
target. Every coordination-kind file of the composed directory (the status pair,
traces, matrices, the decision log, review cycles) rides the squash onto the
target; ``_fold_alias_directory`` removes exactly those, after proving each one
redundant (the status log: every event is in the unioned primary log; any other
file: its bytes equal the primary directory's copy now or at the run's
pre-mutation target tip), and returns them so the existing bookkeeping commit
records the removal. Any file it cannot prove redundant refuses the whole fold
before anything is deleted.

The end-to-end contract is pinned by the reproduction in
``tests/integration/test_merge_lane_planning_data_loss.py`` and by
``test_alias_directory_fold_cli.py``; the cases here run the branches of the
fold and the commit door directly.

Mutation notes: reverting ``_fold_alias_directory`` (or its call in
``_phase_commit_and_assert``) turns the reproduction and
``test_fold_removes_only_the_status_pair_after_proving_the_events`` red;
reverting the event-preservation assert turns
``test_fold_refuses_and_deletes_nothing_when_an_event_is_missing`` red; reverting
the per-file proof turns ``test_fold_refuses_a_coordination_file_the_primary_directory_lacks``
red.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from specify_cli.consolidation import phase_bookkeeping as pb
from specify_cli.consolidation.bookkeeping_projection import AliasFileNotPreserved, AliasFoldRefusal, AliasStatusEventsNotPreserved
from specify_cli.consolidation.state import ConsolidationState
from specify_cli.git.bookkeeping_commit import commit_merge_bookkeeping

pytestmark = pytest.mark.fast

_SLUG = "alias-fold"
_ALIAS = f"{_SLUG}-01KX0000"
_EVENTS = "status.events.jsonl"
_STATUS = "status.json"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def _event(event_id: str, lane: str = "planned") -> str:
    return json.dumps({"event_id": event_id, "wp_id": "WP01", "to_lane": lane}, sort_keys=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _write_files(root: Path, files: Mapping[str, str | bytes]) -> None:
    for relpath, content in files.items():
        target = root / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))


def _write_tracked_mission(
    repo: Path,
    *,
    primary_events: list[str],
    alias_events: list[str],
    primary_files: Mapping[str, str | bytes] | None = None,
    alias_files: Mapping[str, str | bytes] | None = None,
) -> SimpleNamespace:
    """Commit a primary directory and a composed directory, then return a run stand-in.

    The init commit doubles as the run's pre-mutation target tip (``state.pre_mutation_refs``).
    """
    _init_repo(repo)
    primary = repo / "kitty-specs" / _SLUG
    alias = repo / "kitty-specs" / _ALIAS
    primary.mkdir(parents=True)
    alias.mkdir(parents=True)
    _write_files(primary, primary_files or {})
    _write_files(alias, alias_files or {})
    (primary / "meta.json").write_text(json.dumps({"mission_slug": _SLUG}), encoding="utf-8")
    (primary / _EVENTS).write_text("".join(f"{line}\n" for line in primary_events), encoding="utf-8")
    (primary / _STATUS).write_text("{}\n", encoding="utf-8")
    (alias / _EVENTS).write_text("".join(f"{line}\n" for line in alias_events), encoding="utf-8")
    (alias / _STATUS).write_text("{}\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")
    state = ConsolidationState(mission_id=_SLUG, mission_slug=_SLUG, target_branch="main", wp_order=["WP01"])
    state.pre_mutation_refs = {"main": _git(repo, "rev-parse", "HEAD").strip()}
    return SimpleNamespace(
        main_repo=repo,
        mission_slug=_SLUG,
        feature_dir=repo / ".worktrees" / f"{_ALIAS}-coord" / "kitty-specs" / _ALIAS,
        target_events_path=primary / _EVENTS,
        final_bookkeeping_snapshots={},
        done_marked_before_target=False,
        lanes_manifest=SimpleNamespace(target_branch="main"),
        state=state,
    )


def _fold(run: SimpleNamespace) -> list[Path]:
    fold: Any = pb._fold_alias_directory
    result: list[Path] = fold(run)
    return result


def test_fold_removes_only_the_status_pair_after_proving_the_events(tmp_path: Path) -> None:
    run = _write_tracked_mission(
        tmp_path,
        primary_events=[_event("A"), _event("B", "claimed")],
        alias_events=[_event("A")],
    )
    alias = tmp_path / "kitty-specs" / _ALIAS
    (alias / "notes.md").write_text("not a status file\n", encoding="utf-8")

    removed = _fold(run)

    assert sorted(path.name for path in removed) == [_EVENTS, _STATUS]
    assert not (alias / _EVENTS).exists()
    assert not (alias / _STATUS).exists()
    assert (alias / "notes.md").exists(), "any other file under the composed name stays: it must still fail the gate"
    assert (tmp_path / "kitty-specs" / _SLUG / _EVENTS).exists()
    assert set(run.final_bookkeeping_snapshots) == {alias / _EVENTS, alias / _STATUS}, "the removal is enrolled for rollback"


def test_fold_refuses_and_deletes_nothing_when_an_event_is_missing(tmp_path: Path) -> None:
    run = _write_tracked_mission(
        tmp_path,
        primary_events=[_event("A")],
        alias_events=[_event("A"), _event("ONLY-IN-ALIAS", "done")],
    )
    alias = tmp_path / "kitty-specs" / _ALIAS

    with pytest.raises(AliasStatusEventsNotPreserved, match="ONLY-IN-ALIAS"):
        _fold(run)

    assert (alias / _EVENTS).exists()
    assert (alias / _STATUS).exists()
    # The recorder saves run state under ``.kittify/``; only tracked files matter here.
    assert _git(tmp_path, "status", "--porcelain", "--untracked-files=no") == ""


def test_fold_refuses_on_an_unreadable_alias_log_line(tmp_path: Path) -> None:
    run = _write_tracked_mission(tmp_path, primary_events=[_event("A")], alias_events=["{not json"])

    with pytest.raises(AliasStatusEventsNotPreserved, match="not an event"):
        _fold(run)

    assert (tmp_path / "kitty-specs" / _ALIAS / _EVENTS).exists()


def test_fold_is_a_no_op_for_a_mission_whose_status_directory_is_its_primary_directory(tmp_path: Path) -> None:
    run = _write_tracked_mission(tmp_path, primary_events=[_event("A")], alias_events=[_event("A")])
    run.feature_dir = tmp_path / ".worktrees" / "x-coord" / "kitty-specs" / _SLUG

    assert _fold(run) == []

    assert (tmp_path / "kitty-specs" / _ALIAS / _EVENTS).exists()
    assert run.final_bookkeeping_snapshots == {}
    assert _git(tmp_path, "status", "--porcelain") == ""


def test_fold_is_a_no_op_when_the_status_directory_is_a_primary_checkout_path(tmp_path: Path) -> None:
    run = _write_tracked_mission(tmp_path, primary_events=[_event("A")], alias_events=[_event("A")])
    run.feature_dir = tmp_path / "kitty-specs" / _ALIAS

    assert _fold(run) == []

    assert (tmp_path / "kitty-specs" / _ALIAS / _EVENTS).exists()


_TRACE = "traces/mission-trace.md"
_DEEP = "traces/a/b/c.md"
_MATRIX = "issue-matrix.json"


def test_fold_removes_every_coordination_kind_file_proven_redundant_and_the_directories_it_emptied(tmp_path: Path) -> None:
    carried = {_TRACE: "trace\n", _DEEP: "deep\n", _MATRIX: "{}\n", "decisions.events.jsonl": "", "tasks/WP01-x/review-cycle-1.md": "cycle\n"}
    run = _write_tracked_mission(tmp_path, primary_events=[_event("A")], alias_events=[_event("A")], primary_files=carried, alias_files=carried)
    alias = tmp_path / "kitty-specs" / _ALIAS

    removed = _fold(run)

    assert sorted(path.relative_to(alias).as_posix() for path in removed) == sorted([*carried, _EVENTS, _STATUS])
    assert not alias.exists(), "every file went and every directory the fold emptied went with it: the composed name no longer exists"
    assert set(run.final_bookkeeping_snapshots) == set(removed), "every removal is enrolled for rollback"
    assert (tmp_path / "kitty-specs" / _SLUG / _TRACE).read_text(encoding="utf-8") == "trace\n"


def test_fold_leaves_a_directory_it_did_not_empty(tmp_path: Path) -> None:
    run = _write_tracked_mission(tmp_path, primary_events=[_event("A")], alias_events=[_event("A")], primary_files={_TRACE: "t\n"}, alias_files={_TRACE: "t\n"})
    alias = tmp_path / "kitty-specs" / _ALIAS
    (alias / "traces" / "untracked-scratch.md").write_text("mine\n", encoding="utf-8")

    _fold(run)

    assert (alias / "traces" / "untracked-scratch.md").exists(), "an untracked file is unknown content: never removed"
    assert not (alias / _TRACE).exists()
    assert alias.exists()


@pytest.mark.parametrize("relpath", ["spec.md", "plan.md", "meta.json", "src/x.py", "notes/plan.md", "sub/status.json", "tasks/WP01.md"])
def test_fold_never_removes_a_file_that_is_not_a_coordination_kind(tmp_path: Path, relpath: str) -> None:
    run = _write_tracked_mission(
        tmp_path,
        primary_events=[_event("A")],
        alias_events=[_event("A")],
        primary_files={relpath: "same\n", _TRACE: "t\n"},
        alias_files={relpath: "same\n", _TRACE: "t\n"},
    )
    alias = tmp_path / "kitty-specs" / _ALIAS

    removed = _fold(run)

    assert (alias / relpath).exists(), "even byte-equal to the primary copy: it must still fail the gate"
    assert alias / relpath not in removed
    assert not (alias / _TRACE).exists()


def test_fold_proves_a_file_against_the_primary_copy_at_the_pre_mutation_tip(tmp_path: Path) -> None:
    """An untouched seed-carried copy equals the primary copy as it was when the run began, even if the primary copy has since moved on."""
    run = _write_tracked_mission(
        tmp_path, primary_events=[_event("A")], alias_events=[_event("A")], primary_files={_TRACE: "seeded\n"}, alias_files={_TRACE: "seeded\n"}
    )
    (tmp_path / "kitty-specs" / _SLUG / _TRACE).write_text("moved on after the run began\n", encoding="utf-8")

    removed = _fold(run)

    assert tmp_path / "kitty-specs" / _ALIAS / _TRACE in removed


def test_fold_without_a_recorded_pre_mutation_tip_proves_against_the_current_primary_copy_only(tmp_path: Path) -> None:
    run = _write_tracked_mission(
        tmp_path, primary_events=[_event("A")], alias_events=[_event("A")], primary_files={_TRACE: "seeded\n"}, alias_files={_TRACE: "seeded\n"}
    )
    run.state.pre_mutation_refs = {}
    (tmp_path / "kitty-specs" / _SLUG / _TRACE).write_text("moved on\n", encoding="utf-8")

    with pytest.raises(AliasFileNotPreserved):
        _fold(run)


@pytest.mark.parametrize(
    ("primary_files", "why"),
    [
        ({}, "the primary directory lacks the file"),
        ({_TRACE: "other\n"}, "the primary copy differs"),
    ],
    ids=["absent-in-primary", "differs-from-primary"],
)
def test_fold_refuses_a_coordination_file_the_primary_directory_lacks(tmp_path: Path, primary_files: dict[str, str], why: str) -> None:
    run = _write_tracked_mission(
        tmp_path,
        primary_events=[_event("A")],
        alias_events=[_event("A")],
        primary_files=primary_files,
        alias_files={_TRACE: "written after the seed\n"},
    )
    alias = tmp_path / "kitty-specs" / _ALIAS
    run.state.pre_mutation_refs = {"main": _git(tmp_path, "rev-parse", "HEAD").strip()}

    with pytest.raises(AliasFileNotPreserved) as raised:
        _fold(run)

    assert raised.value.relpaths == (_TRACE,), why
    assert raised.value.error_code == "ALIAS_FILE_NOT_PRESERVED"
    assert (alias / _TRACE).exists()
    assert (alias / _EVENTS).exists() and (alias / _STATUS).exists(), "all or nothing: the provable status pair stays too"
    assert _git(tmp_path, "status", "--porcelain", "--untracked-files=no") == ""


def test_fold_refusal_names_every_unproven_file_and_deletes_nothing(tmp_path: Path) -> None:
    run = _write_tracked_mission(
        tmp_path,
        primary_events=[_event("A")],
        alias_events=[_event("A")],
        primary_files={_MATRIX: "{}\n"},
        alias_files={_TRACE: "t1\n", _DEEP: "t2\n", _MATRIX: "{}\n"},
    )

    with pytest.raises(AliasFileNotPreserved) as raised:
        _fold(run)

    assert raised.value.relpaths == (_DEEP, _TRACE)
    assert (tmp_path / "kitty-specs" / _ALIAS / _MATRIX).exists(), "the provable matrix stays as well"


def test_fold_refuses_a_symbolic_link_it_cannot_read_as_the_file_it_names(tmp_path: Path) -> None:
    run = _write_tracked_mission(tmp_path, primary_events=[_event("A")], alias_events=[_event("A")], primary_files={_TRACE: "t\n"})
    alias = tmp_path / "kitty-specs" / _ALIAS
    (alias / "traces").mkdir()
    (alias / _TRACE).symlink_to(tmp_path / "kitty-specs" / _SLUG / _TRACE)
    _git(tmp_path, "add", "-f", ".")
    _git(tmp_path, "commit", "-qm", "a link")

    with pytest.raises(AliasFileNotPreserved) as raised:
        _fold(run)

    assert raised.value.relpaths == (_TRACE,)
    assert (alias / _TRACE).is_symlink()


def test_fold_does_not_confuse_a_nested_status_named_file_with_the_status_pair(tmp_path: Path) -> None:
    """``traces/status.json`` is a trace, proven by its bytes; only the top-level ``status.json`` is the derived snapshot."""
    run = _write_tracked_mission(tmp_path, primary_events=[_event("A")], alias_events=[_event("A")], alias_files={"traces/status.json": '{"x": 1}\n'})

    with pytest.raises(AliasFileNotPreserved) as raised:
        _fold(run)

    assert raised.value.relpaths == ("traces/status.json",)


def test_fold_events_refusal_comes_first_and_is_still_the_events_refusal(tmp_path: Path) -> None:
    run = _write_tracked_mission(tmp_path, primary_events=[_event("A")], alias_events=[_event("A"), _event("LOST")], alias_files={_TRACE: "unproven\n"})

    with pytest.raises(AliasStatusEventsNotPreserved, match="LOST"):
        _fold(run)


def test_both_refusals_are_alias_fold_refusals_with_their_own_codes() -> None:
    assert issubclass(AliasStatusEventsNotPreserved, AliasFoldRefusal)
    assert issubclass(AliasFileNotPreserved, AliasFoldRefusal)
    assert AliasStatusEventsNotPreserved.error_code != AliasFileNotPreserved.error_code


def test_file_refusal_text_names_the_mission_the_directory_every_file_and_the_code(tmp_path: Path) -> None:
    run = _write_tracked_mission(tmp_path, primary_events=[_event("A")], alias_events=[_event("A")], alias_files={_TRACE: "t1\n", _DEEP: "t2\n"})

    with pytest.raises(AliasFileNotPreserved) as raised:
        _fold(run)

    text = raised.value.refusal_text(_SLUG)
    assert text.startswith(f"Mission {_SLUG}: the composed coordination directory kitty-specs/{_ALIAS} was not removed, because ")
    assert f"{_DEEP}, {_TRACE}" in text
    assert f"kitty-specs/{_SLUG}" in text, "it points at the primary Mission directory by name"
    assert "Nothing was deleted and the run was rolled back." in text
    assert text.endswith("Error code: ALIAS_FILE_NOT_PRESERVED.")
    assert "primary log" not in text and "the primary checkout" not in text  # terminology canon: never a bare "primary"


def test_the_commit_door_stages_a_tracked_but_missing_path_as_a_deletion_in_the_same_commit(tmp_path: Path) -> None:
    """The bookkeeping door records a removal of a TRACKED file next to an ordinary update.

    The composed directory's status pair is tracked on the target, so the door's
    ``git add --force`` then ``git commit --only`` stages the removal; a path
    that is neither on disk nor tracked is the case the door refuses.
    """
    run = _write_tracked_mission(tmp_path, primary_events=[_event("A")], alias_events=[_event("A")])
    primary_events = run.target_events_path
    alias = tmp_path / "kitty-specs" / _ALIAS
    primary_events.write_text(primary_events.read_text(encoding="utf-8") + _event("B", "done") + "\n", encoding="utf-8")
    removed = _fold(run)

    commit_merge_bookkeeping(
        repo_root=tmp_path,
        worktree_root=tmp_path,
        mission_slug=_SLUG,
        branch="main",
        destination_ref_override="main",
        message="record done",
        paths=(primary_events, *removed),
    )

    changed = _git(tmp_path, "show", "--name-status", "--format=", "HEAD").splitlines()
    assert sorted(changed) == sorted(
        [
            f"M\tkitty-specs/{_SLUG}/{_EVENTS}",
            f"D\tkitty-specs/{_ALIAS}/{_EVENTS}",
            f"D\tkitty-specs/{_ALIAS}/{_STATUS}",
        ]
    )
    assert _git(tmp_path, "rev-list", "--count", "HEAD") == "2\n", "one bookkeeping commit, not a second one for the removal"
    assert not alias.joinpath(_EVENTS).exists()
    assert _git(tmp_path, "status", "--porcelain") == ""


def test_the_commit_door_stages_the_deletion_of_a_nested_coordination_file_and_leaves_no_directory(tmp_path: Path) -> None:
    """The fold's nested removals go through the same door in the same single commit, and the target keeps no empty directory."""
    run = _write_tracked_mission(
        tmp_path,
        primary_events=[_event("A")],
        alias_events=[_event("A")],
        primary_files={_DEEP: "deep\n"},
        alias_files={_DEEP: "deep\n"},
    )
    removed = _fold(run)

    commit_merge_bookkeeping(
        repo_root=tmp_path,
        worktree_root=tmp_path,
        mission_slug=_SLUG,
        branch="main",
        destination_ref_override="main",
        message="record done",
        paths=(run.target_events_path, *removed),
    )

    assert f"D\tkitty-specs/{_ALIAS}/{_DEEP}" in _git(tmp_path, "show", "--name-status", "--format=", "HEAD").splitlines()
    assert _git(tmp_path, "rev-list", "--count", "HEAD") == "2\n"
    assert not (tmp_path / "kitty-specs" / _ALIAS).exists()
    assert _git(tmp_path, "status", "--porcelain") == ""


def test_the_commit_door_refuses_a_path_that_was_never_tracked(tmp_path: Path) -> None:
    """The other half of the door's contract: a missing, never-tracked path fails the commit."""
    run = _write_tracked_mission(tmp_path, primary_events=[_event("A")], alias_events=[_event("A")])
    ghost = tmp_path / "kitty-specs" / _ALIAS / "ghost.json"
    run.target_events_path.write_text(run.target_events_path.read_text(encoding="utf-8") + _event("B") + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="failed to stage"):
        commit_merge_bookkeeping(
            repo_root=tmp_path,
            worktree_root=tmp_path,
            mission_slug=_SLUG,
            branch="main",
            destination_ref_override="main",
            message="record done",
            paths=(run.target_events_path, ghost),
        )


def _invariant_run(repo: Path, base: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        main_repo=repo,
        mission_slug=base.mission_slug,
        baseline_meta_path=None,
        mission_number_meta_path=None,
        birth_cutover_meta_path=None,
        gate_artifact_restored_paths=[],
        final_bookkeeping_snapshots={},
        done_marked_before_target=False,
        state=base.state,
    )


def test_post_merge_invariant_does_not_wave_through_a_composed_status_pair_left_deleted(tmp_path: Path) -> None:
    """``_is_coord_residue`` in the invariant stays keyed on the bare slug, on purpose (T015).

    The only state in which a composed-directory status file is divergent when the
    invariant runs is a fold that was killed between its unlink and its commit.
    Treating that pair as churn would let the invariant pass and the fold, finding
    nothing left to unlink, would commit no removal: the target would keep a tracked
    file that is gone from disk. The invariant refuses it instead (fail closed), so
    no consumer conversion is made and none is proven needed.
    """
    base = _write_tracked_mission(tmp_path, primary_events=[_event("A")], alias_events=[_event("A")])
    for name in (_EVENTS, _STATUS):
        (tmp_path / "kitty-specs" / _ALIAS / name).unlink()
    invariant: Any = pb._phase_porcelain_invariant

    with pytest.raises(typer.Exit) as raised:
        invariant(_invariant_run(tmp_path, base))

    assert raised.value.exit_code == 1


def test_post_merge_invariant_passes_on_a_clean_checkout(tmp_path: Path) -> None:
    base = _write_tracked_mission(tmp_path, primary_events=[_event("A")], alias_events=[_event("A")])
    invariant: Any = pb._phase_porcelain_invariant

    invariant(_invariant_run(tmp_path, base))
