"""Squash projection never carries plan outputs as coordination bookkeeping (#5552).

``/spec-kitty.plan`` writes ``quickstart.md`` and ``contracts/**`` next to
``spec.md`` / ``research.md`` / ``data-model.md``. Those are PRIMARY-partition
planning artifacts, but the file→kind classifier (``mission_runtime.artifacts``)
had no entry for them, so :func:`kind_for_mission_file` returned ``None`` and
``bookkeeping_projection._post_checkpoint_mission_paths`` kept them in the
projected set (it excludes only KNOWN primary kinds). When a lane merge brought
them onto the coordination ref after the checkpoint and the target had
diverged from the checkpoint for those paths, the squash proof
(:func:`projected_content_matches_target`) found no merge driver and REFUSEd —
"projected coordination bookkeeping content did not land on the target" —
even though the content was byte-identical.

These tests drive the pre-existing entry points on a real git fixture shaped
like the refused run in the issue, plus a coordination-bookkeeping path
(``traces/approach.md``) as the same-fixture positive control: it must stay
projected and still pass the proof.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import (
    CommitTarget,
    MissionArtifactKind,
    TopologySurface,
    is_primary_artifact_kind,
    kind_for_mission_file,
)
from mission_runtime.artifacts import artifact_home_for
from specify_cli.consolidation.bookkeeping_projection import (
    _post_checkpoint_mission_paths,
    projected_content_matches_target,
)

pytestmark = [pytest.mark.git_repo]

_SLUG = "plan-outputs-01M43DRV"
_MISSION = f"kitty-specs/{_SLUG}"
_QUICKSTART = f"{_MISSION}/quickstart.md"
_CONTRACT = f"{_MISSION}/contracts/battery-partition.md"
_NESTED_CONTRACT = f"{_MISSION}/contracts/schemas/green-match.yaml"
_TRACE = f"{_MISSION}/traces/approach.md"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def _write(repo: Path, rel: str, text: str) -> None:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    for rel, text in files.items():
        _write(repo, rel, text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _refused_run_shape(tmp_path: Path) -> tuple[Path, str, str]:
    """Return ``(repo, checkpoint_sha, pre_squash_target_sha)``.

    * ``checkpoint`` — the transaction-start coordination checkpoint: the
      mission has only ``spec.md``.
    * ``coord`` — lane merges after the checkpoint bring the plan outputs and a
      tracer file onto the coordination ref.
    * pre-squash target — the target already carries the plan outputs
      (diverged from the checkpoint for those paths), byte-identical to coord.
    * ``main`` (post-squash target) — the squash lands the coordination
      content, so every path is byte-identical to ``coord``.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    checkpoint = _commit(repo, {f"{_MISSION}/spec.md": "# spec\n"}, "checkpoint")

    plan_outputs = {
        _QUICKSTART: "# Quickstart\n",
        _CONTRACT: "# Battery partition contract\n",
        _NESTED_CONTRACT: "name: green-match\n",
    }
    _git(repo, "checkout", "-q", "-b", "coord")
    _commit(repo, {**plan_outputs, _TRACE: "approach notes\n"}, "lane merges onto coord")

    _git(repo, "checkout", "-q", "main")
    pre_squash = _commit(repo, plan_outputs, "plan outputs already on the target")
    _commit(repo, {_TRACE: "approach notes\n"}, "squash lands coord content")
    return repo, checkpoint, pre_squash


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        # ``quickstart.md`` reuses CHECKLIST: the accept gate already classifies
        # it that way (``acceptance._accept_planning_artifact_kinds``).
        (_QUICKSTART, "checklist"),
        (_CONTRACT, "contract"),
        (_NESTED_CONTRACT, "contract"),
        (f"{_MISSION}/contracts", "contract"),
    ],
)
def test_plan_outputs_classify_to_a_primary_kind(path: str, expected: str) -> None:
    kind = kind_for_mission_file(path, mission_slug=_SLUG)

    assert kind is not None and kind.value == expected
    # The predicate safe-commit and the implement commit partition route on.
    assert is_primary_artifact_kind(kind)


def test_plan_outputs_of_another_mission_stay_unclassified() -> None:
    assert kind_for_mission_file(_QUICKSTART, mission_slug="other-mission") is None
    assert kind_for_mission_file(_CONTRACT, mission_slug="other-mission") is None


def test_contract_kind_resolves_the_primary_surface() -> None:
    """Write placement is unchanged: unknown kinds already fell back to PRIMARY."""
    ref = CommitTarget(ref="feat/plan-outputs")

    home = artifact_home_for(MissionArtifactKind.CONTRACT, ref)

    assert home.read_surface is TopologySurface.PRIMARY
    assert home.write_surface is TopologySurface.PRIMARY
    assert home.commit_target == ref


def test_plan_outputs_are_not_projected_but_coord_bookkeeping_is(tmp_path: Path) -> None:
    repo, checkpoint, _pre_squash = _refused_run_shape(tmp_path)

    paths = _post_checkpoint_mission_paths(repo, _SLUG, checkpoint, "coord")

    assert paths == [_TRACE]


def test_squash_proof_passes_on_the_refused_run_shape(tmp_path: Path) -> None:
    """The #5552 REFUSE: the proof over the projected set must now pass."""
    repo, checkpoint, pre_squash = _refused_run_shape(tmp_path)
    projected = tuple(_post_checkpoint_mission_paths(repo, _SLUG, checkpoint, "coord"))

    assert projected_content_matches_target(
        main_repo=repo,
        coord_ref="coord",
        target_ref="main",
        projected_paths=projected,
        checkpoint_sha=checkpoint,
        pre_squash_target_ref=pre_squash,
    )


def test_the_proof_still_refuses_a_diverged_unclassified_path(tmp_path: Path) -> None:
    """Fail-closed control: the proof itself is unchanged for a path it still owns."""
    repo, checkpoint, pre_squash = _refused_run_shape(tmp_path)

    assert not projected_content_matches_target(
        main_repo=repo,
        coord_ref="coord",
        target_ref="main",
        projected_paths=(_QUICKSTART,),
        checkpoint_sha=checkpoint,
        pre_squash_target_ref=pre_squash,
    )


def test_plan_outputs_commit_to_the_primary_target_not_coordination() -> None:
    """The implement/review commit partition routes plan outputs like spec.md.

    ``workflow._partition_paths_by_primary_kind`` sends PRIMARY kinds to the
    primary target and keeps only coordination bookkeeping on coord; before
    #5552 the unclassified plan outputs fell into the coord bucket.
    """
    from specify_cli.cli.commands.agent.workflow import _partition_paths_by_primary_kind

    status_log = Path(_MISSION) / "status.events.jsonl"
    plan_outputs = [Path(_QUICKSTART), Path(_CONTRACT), Path(_NESTED_CONTRACT)]

    primary_bound, coord_bound = _partition_paths_by_primary_kind([*plan_outputs, status_log], mission_slug=_SLUG)

    assert primary_bound == plan_outputs
    assert coord_bound == [status_log]
