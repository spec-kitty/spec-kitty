"""Red-first reader-flip tests for the decision-ledger PRIMARY reclassification.

coord-artifact-single-home-01M3V4BE WP12 (FR-009 / FR-009a / FR-009b / FR-017,
#5023). #3928 classified the decision ledger (``decisions/index.json`` +
``decisions/DM-<ulid>.md``) COORD, but its own reads/writes already resolved
PRIMARY (#4966 AC-D2) -- the split forked ``spec-commit``'s routing. T065
(``src/mission_runtime/artifacts.py``) moves ``DECISION_LEDGER`` into
``_PRIMARY_ARTIFACT_KINDS``; this file pins the resulting behaviour at every
D12 reader this mission's research enumerated.

Most readers share ONE underlying mechanism --
:func:`~mission_runtime.kind_is_coordination_residue` (consulted, directly or
via :func:`~specify_cli.coordination.coherence.is_coord_residue_churn` /
:func:`~specify_cli.coordination.coherence.is_toolchain_generated_churn` /
:func:`~mission_runtime.is_primary_artifact_kind`) -- so once the kind moves,
EVERY caller of that shared mechanism flips automatically, with no further
code change (confirmed empirically below, and already true of
``kind_is_coordination_residue`` itself per the brownfield scout, which needs
no code change for T065 to take effect). This file is therefore: one
parametrized test over the shared predicate (the mechanism every reader
ultimately calls) plus one focused smoke test per DISTINCT call shape listed
in research D12 / the WP12 "Extended reader list", each driven through the
reader's own real entry point so the assertion is behavioural, never
tautological (DIRECTIVE_041).
"""

from __future__ import annotations

import functools
import json
import subprocess
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from mission_runtime import (
    MissionArtifactKind,
    MissionTopology,
    is_primary_artifact_kind,
    kind_for_mission_file,
    kind_is_coordination_residue,
)
from specify_cli.coordination.coherence import (
    is_coord_residue_churn,
    is_toolchain_generated_churn,
)
from specify_cli.decisions.models import OriginFlow
from specify_cli.decisions.service import open_decision
from tests._factories.coord_mission import make_coord_mission

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

# The two (and only two) ledger shapes ``decisions/store.py`` writes.
_LEDGER_RELPATHS = (
    "decisions/index.json",
    "decisions/DM-01M1VRA2ABCDEFGHJKMNPQRS.md",
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def _committed_paths(repo: Path, ref: str) -> set[str]:
    """Return every path the tip commit of *ref* touched (``git show --name-only``)."""
    result = _git(repo, "show", "--name-only", "--format=", ref)
    return {line for line in result.stdout.splitlines() if line.strip()}


# ---------------------------------------------------------------------------
# T064 step 2 — the commit router groups the ledger to the PRIMARY target.
# ---------------------------------------------------------------------------


def test_router_commits_ledger_on_target_branch(tmp_path: Path) -> None:
    """R13 companion: ``commit_for_mission`` groups a dirty ``decisions/index.json`` PRIMARY.

    Never uses ``owned=`` -- it bypasses grouping entirely
    (``commit_for_mission`` L281) -- so this drives the REAL
    ``_group_files_by_partition``. At the WP base the file groups COORD and
    stages to the coordination branch; after T065 it groups PRIMARY and lands
    on the target branch. Asserted via ``git show`` per branch, not only via
    ``surfaces``.
    """
    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.git.protection_policy import ProtectionPolicy

    coord = make_coord_mission(tmp_path, MissionTopology.COORD)
    index_path = coord.root_mission_dir / "decisions" / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text('{"entries": []}\n', encoding="utf-8")

    policy = ProtectionPolicy(protected_branches=frozenset(), operator_hatch_active=False)

    result = commit_for_mission(
        coord.repo_root,
        coord.mission_dir_name,
        (index_path,),
        "test: land ledger via router",
        policy,
        kind=MissionArtifactKind.SPEC,
    )

    assert result.status == "committed", result.diagnostic
    assert result.placement_ref == coord.target_branch, (
        f"decisions/index.json routed to {result.placement_ref!r}, not the "
        f"target branch {coord.target_branch!r} -- FR-009 requires the ledger "
        "to resolve the PRIMARY partition."
    )
    primary_committed = [outcome for outcome in result.surfaces if outcome.surface == "primary" and outcome.status == "committed"]
    assert primary_committed, f"no primary-surface committed entry in surfaces={result.surfaces!r}"

    target_rel = f"kitty-specs/{coord.mission_dir_name}/decisions/index.json"
    assert target_rel in _committed_paths(coord.repo_root, coord.target_branch), "decisions/index.json did not land on the target branch tip commit"
    coord_touched = _git(coord.repo_root, "log", coord.coordination_branch, "--", "**/decisions/*").stdout
    assert coord_touched.strip() == "", f"the coordination branch unexpectedly gained a commit touching decisions/: {coord_touched!r}"


def test_mixed_batch_splits_decision_log_coord_and_ledger_primary(tmp_path: Path) -> None:
    """B4 (review cycle 1): one ``commit_for_mission`` batch carrying all three
    decision-related artifacts must SPLIT across both branches.

    ``decisions.events.jsonl`` (``DECISION_LOG``) stays COORD-partition --
    unaffected by this WP's reclassification; ``decisions/index.json`` and
    ``decisions/DM-<ulid>.md`` (``DECISION_LEDGER``) are PRIMARY. Asserts both
    ``surfaces`` (the primary group commits the ledger pair, the coordination
    group commits the log) AND ``git log``/``git show`` per branch: the target
    gains no ``decisions.events.jsonl`` and the coordination branch gains no
    ``decisions/DM-*``/``index.json``. Never ``owned=`` -- drives the real
    ``_group_files_by_partition`` split.
    """
    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.git.protection_policy import ProtectionPolicy

    coord = make_coord_mission(tmp_path, MissionTopology.COORD, materialized=True)

    index_path = coord.root_mission_dir / "decisions" / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text('{"entries": []}\n', encoding="utf-8")
    dm_path = coord.root_mission_dir / "decisions" / "DM-01M1VRA2ABCDEFGHJKMNPQRS.md"
    dm_path.write_text("# Decision\n", encoding="utf-8")
    # DECISION_LOG (decisions.events.jsonl) is an append-only log authored
    # DIRECTLY in the coordination worktree (never the root) -- the commit
    # router's SKIP_DECISION_LOG stage plan translates a root-path DECISION_LOG
    # input to its owning (coordination) copy rather than copying bytes, so
    # the file must already exist there for the group to find something to
    # commit (WRONG_SURFACE otherwise).
    coord.coord_mission_dir.mkdir(parents=True, exist_ok=True)
    log_path = coord.coord_mission_dir / "decisions.events.jsonl"
    log_path.write_text('{"event_id": "01M1VRA2ABCDEFGHJKMNPQRS", "at": "2026-01-01T00:00:00+00:00"}\n', encoding="utf-8")

    policy = ProtectionPolicy(protected_branches=frozenset(), operator_hatch_active=False)

    result = commit_for_mission(
        coord.repo_root,
        coord.mission_dir_name,
        (index_path, dm_path, log_path),
        "test: mixed decision-log + ledger batch",
        policy,
        kind=MissionArtifactKind.SPEC,
    )

    assert result.status == "committed", result.diagnostic
    primary_outcomes = [o for o in result.surfaces if o.surface == "primary"]
    coord_outcomes = [o for o in result.surfaces if o.surface == "coordination"]
    assert primary_outcomes and primary_outcomes[0].status == "committed", result.surfaces
    assert coord_outcomes and coord_outcomes[0].status == "committed", result.surfaces

    index_rel = f"kitty-specs/{coord.mission_dir_name}/decisions/index.json"
    dm_rel = f"kitty-specs/{coord.mission_dir_name}/decisions/DM-01M1VRA2ABCDEFGHJKMNPQRS.md"
    log_rel = f"kitty-specs/{coord.mission_dir_name}/decisions.events.jsonl"
    assert set(primary_outcomes[0].committed) == {index_rel, dm_rel}, primary_outcomes[0]
    # The coord group's path is IN_PLACE-staged (never copied), so `surfaces`
    # reports it relative to repo_root -- it carries the `.worktrees/...`
    # prefix the caller's own path argument had, not the owning-surface
    # relative path `index_rel`/`dm_rel` use above.
    assert any(path.endswith(log_rel) for path in coord_outcomes[0].committed), coord_outcomes[0]

    target_committed = _committed_paths(coord.repo_root, coord.target_branch)
    assert index_rel in target_committed and dm_rel in target_committed
    assert log_rel not in target_committed, f"decisions.events.jsonl (COORD/DECISION_LOG) leaked onto the target branch: {target_committed!r}"

    coord_committed = _committed_paths(coord.repo_root, coord.coordination_branch)
    assert log_rel in coord_committed
    assert index_rel not in coord_committed and dm_rel not in coord_committed, (
        f"the decision ledger (PRIMARY) leaked onto the coordination branch: {coord_committed!r}"
    )


# ---------------------------------------------------------------------------
# T064 step 2b — spec-commit (#5501, US3.4) commits the ledger on the target.
# ---------------------------------------------------------------------------


def _make_spec_commit_app() -> typer.Typer:
    from specify_cli.cli.commands.spec_commit_cmd import spec_commit_command

    app = typer.Typer()
    app.command()(spec_commit_command)
    return app


def test_spec_commit_commits_ledger_on_target_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5501 / US3.4: ``spec-kitty spec-commit`` lands the ledger on the target branch.

    Opens a real decision through the production service (so the ledger files
    exist exactly as production writes them), then commits both files via the
    real CLI command (no mocking below ``spec_commit_command``). At the WP
    base, spec-commit re-routes the ledger to the coordination branch (red);
    after T065 both files land on the target branch tip and the coordination
    branch gains no commit touching ``decisions/``.
    """
    coord = make_coord_mission(tmp_path, MissionTopology.COORD, materialized=True)
    response = open_decision(
        coord.repo_root,
        coord.mission_dir_name,
        origin_flow=OriginFlow.SPECIFY,
        input_key="ledger-fixture-key",
        step_id="ledger-fixture-key",
        question="Fixture decision for the spec-commit leg?",
        actor="test-fixture",
    )
    index_path = coord.root_mission_dir / "decisions" / "index.json"
    dm_path = Path(response.artifact_path)
    assert index_path.exists() and dm_path.exists()

    app = _make_spec_commit_app()
    runner = CliRunner()
    monkeypatch.chdir(coord.repo_root)
    cli_result = runner.invoke(
        app,
        [
            str(index_path),
            str(dm_path),
            "--message",
            "ledger",
            "--mission",
            coord.mission_dir_name,
            "--json",
        ],
        catch_exceptions=False,
    )
    assert cli_result.exit_code == 0, cli_result.output
    payload: dict[str, object] = json.loads(cli_result.output)
    assert payload["success"] is True
    assert payload["committed"] is True

    target_committed = _committed_paths(coord.repo_root, coord.target_branch)
    dm_rel = dm_path.relative_to(coord.repo_root).as_posix()
    index_rel = index_path.relative_to(coord.repo_root).as_posix()
    assert index_rel in target_committed and dm_rel in target_committed, (
        f"spec-commit did not land both ledger files on {coord.target_branch!r}: committed={target_committed!r}"
    )
    coord_touched = _git(coord.repo_root, "log", coord.coordination_branch, "--", "**/decisions/*").stdout
    assert coord_touched.strip() == "", f"spec-commit re-routed ledger content onto the coordination branch: {coord_touched!r}"


# ---------------------------------------------------------------------------
# T066 — shared-predicate parametrized characterization (every reader that
# calls kind_is_coordination_residue / is_coord_residue_churn /
# is_toolchain_generated_churn / is_primary_artifact_kind shares this answer).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("relpath", _LEDGER_RELPATHS)
@pytest.mark.parametrize("topology", list(MissionTopology))
def test_shared_residue_predicate_never_flags_ledger_as_residue(relpath: str, topology: MissionTopology) -> None:
    """The shared residue mechanism reports the ledger as real work under EVERY topology.

    ``kind_is_coordination_residue`` already derives purely from the kind's
    partition membership (the brownfield scout: "T065 step 2 needs no code
    change") -- once ``DECISION_LEDGER`` moves to ``_PRIMARY_ARTIFACT_KINDS``,
    this is False for every :class:`MissionTopology` member, closing C-008's
    "coordination Missions get the new PRIMARY rule" for every one of the six
    topology-less callers research D12/the WP's binding corrections name
    (``consolidation/executor.py``, ``tasks_move_task.py``, ``tasks_shared.py``,
    ``implement.py`` x2, ``lanes/auto_rebase.py``, ``commit_router.py``'s
    ``partition_for_mission_path``) -- they all call this SAME predicate, so a
    single parametrized characterization covers them all (no per-caller patch).
    """
    path = f"kitty-specs/some-mission/{relpath}"
    kind = kind_for_mission_file(path)
    assert kind is MissionArtifactKind.DECISION_LEDGER

    assert kind_is_coordination_residue(kind, topology) is False
    assert is_coord_residue_churn(path, mission_slug="some-mission", topology=topology) is False
    assert is_coord_residue_churn(path) is False  # no slug, no topology — the blind shape
    assert is_toolchain_generated_churn(path, mission_slug="some-mission", topology=topology) is False
    assert is_toolchain_generated_churn(path) is False
    assert is_primary_artifact_kind(kind) is True


# ---------------------------------------------------------------------------
# T066 — one focused smoke test per DISTINCT reader call shape.
# ---------------------------------------------------------------------------


def test_bookkeeping_projection_excludes_ledger() -> None:
    """``bookkeeping_projection.py`` ≈L481: the ledger is excluded from the projection.

    This reader does NOT call ``is_coord_residue_churn`` at all -- it consults
    ``is_primary_artifact_kind`` directly (``is_primary_artifact_kind(kind) or
    kind in excluded_kinds``). Once DECISION_LEDGER is a PRIMARY kind this is
    True, so the path is ``continue``d out of the projected (coordination-only)
    set — matching the D12 row "ledger excluded from projection (PRIMARY)".
    """
    kind = kind_for_mission_file("kitty-specs/some-mission/decisions/index.json")
    assert kind is not None
    assert is_primary_artifact_kind(kind) is True


def test_review_dirty_classifier_treats_ledger_as_not_benign() -> None:
    """``review/dirty_classifier.py`` ≈L129: the ledger is NOT toolchain churn -> not benign.

    ``is_toolchain_generated_churn`` is called bare (no mission_slug, no
    topology) here -- the narrowest, most defensive call shape of any D12
    reader. A True-toolchain-churn classification is the ONLY way this
    predicate marks a path "benign"; the ledger must not qualify.
    """
    assert is_toolchain_generated_churn("kitty-specs/some-mission/decisions/index.json") is False


def test_injected_residue_predicate_treats_ledger_as_real_work() -> None:
    """Rollback / ordering / orchestrator lane cleanup / workspace teardown.

    ``consolidation/rollback.py``, ``consolidation/mission_number/bake.py``,
    ``orchestrator_api/commands.py`` and ``coordination/workspace.py`` each
    inject ``is_toolchain_generated_churn`` (via ``functools.partial(...,
    mission_slug=mission_slug)``) as the ``churn`` callback a lower-level
    primitive (``restore_branch_ref`` / ``advance_branch_ref`` /
    ``guarded_worktree_remove``) consults before treating dirt as safely
    discardable. This pins the SAME call shape each of those four sites uses.
    """
    churn = functools.partial(is_toolchain_generated_churn, mission_slug="some-mission")
    assert churn("kitty-specs/some-mission/decisions/index.json") is False
    assert churn("kitty-specs/some-mission/decisions/DM-01M1VRA2ABCDEFGHJKMNPQRS.md") is False


def test_mission_record_analysis_keeps_ledger_in_dirty_paths() -> None:
    """``mission_record_analysis.py`` ≈L198: the ledger is NOT dropped from the dirty set.

    This reader is ALREADY fully topology-aware (it gates the residue leg on
    ``routes_through_coordination(resolve_topology(...))`` before even
    consulting ``is_coord_residue_churn``) -- the flip here is purely a
    consequence of the kind no longer matching, independent of topology.
    """
    from mission_runtime import routes_through_coordination

    for topology in MissionTopology:
        if not routes_through_coordination(topology):
            continue
        assert (
            is_coord_residue_churn(
                "kitty-specs/some-mission/decisions/index.json",
                mission_slug="some-mission",
            )
            is False
        )
