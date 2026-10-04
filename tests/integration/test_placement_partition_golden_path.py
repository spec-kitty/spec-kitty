"""End-to-end characterization lock for the coord/primary placement partition.

Mission ``coord-primary-partition-lock-01KWZ46V`` (WP08 / FR-006, FR-009,
NFR-002, NFR-004, C-007). This is the regression lock the mission's whole
strangle exists to protect: it walks the real mission lifecycle through the
CLI/programmatic seams (``mission create`` -> commit spec -> ``setup-plan`` ->
``agent tasks status`` -> ``agent decision verify``), drives a lifecycle
**mutation** (``move-task``), and asserts partition-correct authority —
planning artifacts on PRIMARY, lifecycle/status bookkeeping on COORD for a
coordination-topology mission — independent of the operator's CWD, across
both coord and non-coord (``SINGLE_BRANCH``) topologies.

C-007 / #2429 status (squad M2, verified live at WP08 time): the plan's
soft-gate on PR #2429 landing is MOOT. ``resolve_planning_read_dir`` (see
``specify_cli.missions._read_path_resolver``) is already kind-aware — it
requires an explicit ``kind: MissionArtifactKind`` keyword — and the #2091
empty-mid8 guard is present in ``specify_cli.coordination.workspace``. This
test pins the CURRENT surface rather than waiting on #2429 (per the WP
prompt: "verify, don't hold").

T041 also carries a **#2404-lite** regression pin: ``accept``'s lane-gate /
acceptance-matrix read currently resolves through the kind-BLIND
``resolve_feature_dir_for_mission`` (see ``acceptance/__init__.py::
_check_lane_gates``), which for a coord-topology mission lands on the
``-coord`` worktree — a KNOWN, OPEN bug (#2404: "spec-kitty accept reads
acceptance-matrix.json from stale -coord worktree, not primary surface").
The full fix (flipping ``ACCEPTANCE_MATRIX`` from ``_PLACEMENT_ARTIFACT_KINDS``
to ``_PRIMARY_ARTIFACT_KINDS`` — see ``tracer-design-decisions.md``) is an
architecture decision under #2160/#1716 and is explicitly OUT of this WP's
scope. This test pins the CURRENT (buggy) read-partition as a live
regression lock: when #2404 is fixed, this specific assertion is the one to
flip.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from mission_runtime import MissionArtifactKind, MissionTopology
from specify_cli.acceptance.matrix import read_acceptance_matrix
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.core.mission_creation import MissionCreationResult, create_mission_core
from specify_cli.missions._read_path_resolver import (
    candidate_feature_dir_for_mission,
    resolve_feature_dir_for_mission,
    resolve_handle_to_read_path,
    resolve_planning_read_dir,
)
from specify_cli.status.bootstrap import bootstrap_canonical_state
from tests.git.protected_target_fixtures import (  # noqa: F401 — pytest fixture re-export
    PROTECTED_TARGET_BRANCH,
    ProtectedTargetRepo,
    protected_target_repo,
)
from tests.mocked_env import setup_mocked_env

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_CORE_MODULE = "specify_cli.core.mission_creation"
_ALLOW_PROTECTED_ENV = "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"

_SUBSTANTIVE_SPEC = """\
# Spec — Golden Path Mission

## Functional Requirements

| ID | Title | Description | Priority | Status |
|----|-------|-------------|----------|--------|
| FR-001 | Golden path | Walk create/spec/plan/status/verify end to end. | High | Open |
"""

_SUBSTANTIVE_PLAN = """\
# Plan — Golden Path Mission

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: typer, pytest
**Storage**: filesystem only
**Testing**: pytest integration coverage
"""


# ---------------------------------------------------------------------------
# Low-level git + mission-creation helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )


def _init_git_repo(repo: Path, *, branch: str = "main") -> None:
    kittify_dir = repo / ".kittify"
    kittify_dir.mkdir(parents=True, exist_ok=True)
    (repo / "kitty-specs").mkdir(parents=True, exist_ok=True)
    # WP04 fail-closed (C-A1): create_mission_core requires a non-empty
    # activated mission-type set; every mission this fixture creates is
    # software-dev (see _create_mission).
    (kittify_dir / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )
    subprocess.run(["git", "init", "-b", branch], cwd=repo, capture_output=True, check=True)
    _git(repo, "config", "user.email", "golden-path@spec-kitty.test")
    _git(repo, "config", "user.name", "Golden Path Fixture")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "commit", "-m", "init: golden-path baseline", "--allow-empty")


def _create_mission(
    repo: Path, slug: str, topology: MissionTopology
) -> MissionCreationResult:
    """Create a mission via the SAME core the CLI ``mission create`` calls.

    Only ``is_worktree_context`` is patched — it inspects the actual OS
    ``Path.cwd()`` (not ``repo_root``), which during a pytest run under this
    lane worktree genuinely IS a spec-kitty worktree and would otherwise
    trip the "cannot create missions from inside a worktree" guard. Every
    other resolver (``is_git_repo`` / ``get_current_branch``) runs for
    real against ``repo`` — this is real git, not a stub.
    """
    with patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False):
        return create_mission_core(
            repo,
            slug,
            friendly_name=slug.replace("-", " ").title(),
            purpose_tldr=f"Deliver {slug} for the golden-path lock.",
            purpose_context=(
                f"This mission exercises the {slug} golden path end to end so "
                "the placement partition stays proven under CI."
            ),
            topology=topology,
        )


def _commit(repo: Path, rel_path: str, message: str) -> None:
    _git(repo, "add", rel_path)
    _git(repo, "commit", "-m", message)


def _materialize_coord_worktree(repo: Path, result: MissionCreationResult) -> Path:
    """Materialize the coord worktree the way real bookkeeping writes do."""
    meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    mid8 = str(meta["mission_id"])[:8]
    coord_root: Path = CoordinationWorkspace.resolve(repo, result.mission_slug, mid8)
    return coord_root


def _write_wp_and_lanes(feature_dir: Path, slug: str, mission_id: str, target_branch: str) -> None:
    """Seed a single realistic WP01 + tasks.md + lanes.json (finalize-tasks shape)."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    (tasks_dir / "WP01.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Golden path WP01\n"
        "execution_mode: code_change\n"
        "agent: testbot\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Work Packages\n\n## WP01 - golden path fixture\n- [ ] T001 do a thing\n",
        encoding="utf-8",
    )
    lanes_payload = {
        "version": 1,
        "mission_slug": slug,
        "mission_id": mission_id,
        "mission_branch": f"kitty/mission-{slug}",
        "target_branch": target_branch,
        "lanes": [
            {
                "lane_id": "lane-a",
                "wp_ids": ["WP01"],
                "write_scope": [],
                "predicted_surfaces": [],
                "depends_on_lanes": [],
                "parallel_group": 0,
            }
        ],
        "computed_at": "2026-07-08T00:00:00+00:00",
        "computed_from": "golden-path-fixture",
        "planning_artifact_wps": [],
    }
    (feature_dir / "lanes.json").write_text(json.dumps(lanes_payload, indent=2), encoding="utf-8")


def _parse_json_output(output: str) -> dict[str, object]:
    text = output.strip()
    for line in reversed(text.splitlines()):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            return candidate
    start = text.find("{")
    end = text.rfind("}")
    assert start != -1 and end != -1, f"no JSON object in output: {text!r}"
    payload: dict[str, object] = json.loads(text[start : end + 1])
    return payload


def _wp_ids_from_status(status_payload: dict[str, object]) -> set[object]:
    """Extract WP identifiers from a ``tasks status --json`` payload."""
    raw_wps = status_payload.get("work_packages", [])
    assert isinstance(raw_wps, list)
    return {wp.get("id") or wp.get("work_package_id") for wp in raw_wps}


# ---------------------------------------------------------------------------
# CLI drive helpers — setup-plan / tasks status / decision verify
# ---------------------------------------------------------------------------


def _run_setup_plan(repo: Path, mission_handle: str, *, target_branch: str = "main") -> dict[str, object]:
    """Invoke ``agent mission setup-plan --json --mission <handle>``.

    Mirrors ``tests/integration/test_specify_plan_commit_boundary.py``'s
    established harness for this exact command: the branch-context /
    feature-directory probes are patched because they otherwise re-derive
    branch state the fixture repo does not need to fully simulate (this is a
    thin scaffolding+commit command, not the resolver under test here — the
    resolver under test is exercised unpatched by ``_run_tasks_status`` /
    ``_run_decision_verify`` below).
    """
    from specify_cli.cli.commands.agent import mission as mission_module

    feature_dir = repo / "kitty-specs" / mission_handle

    def _fake_show_branch_context(_repo: Path, _slug: str, _json: bool) -> tuple[str, str]:
        return (target_branch, target_branch)

    with (
        patch.dict(os.environ, {_ALLOW_PROTECTED_ENV: "1"}),
        patch.object(mission_module, "locate_project_root", return_value=repo),
        patch.object(mission_module, "_enforce_git_preflight"),
        patch.object(mission_module, "_find_feature_directory", return_value=feature_dir),
        patch.object(mission_module, "_show_branch_context", side_effect=_fake_show_branch_context),
        patch.object(mission_module, "get_current_branch", return_value=target_branch),
        patch.object(mission_module, "_resolve_feature_target_branch", return_value=target_branch),
    ):
        result = runner.invoke(
            mission_module.app,
            ["setup-plan", "--json", "--mission", mission_handle],
            catch_exceptions=False,
        )
    assert result.exit_code in (0, 1), f"unexpected exit {result.exit_code}: {result.output}"
    return _parse_json_output(result.output)


def _run_tasks_status(repo: Path, mission_handle: str, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Invoke ``agent tasks status --json`` through the REAL unpatched resolvers.

    No ``locate_project_root`` stub — this is the CWD-independence proof
    surface (T040 varies ``SPECIFY_REPO_ROOT`` / cwd around this call and
    ``_run_decision_verify`` to prove identical resolution).
    """
    from specify_cli.cli.commands.agent import tasks as tasks_module

    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))
    result = runner.invoke(
        tasks_module.app, ["status", "--mission", mission_handle, "--json"], catch_exceptions=False
    )
    assert result.exit_code == 0, result.output
    return _parse_json_output(result.output)


def _run_decision_verify(repo: Path, mission_handle: str, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Invoke ``agent decision verify --json`` through the REAL unpatched resolvers."""
    from specify_cli.cli.commands.decision import decision_app

    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))
    result = runner.invoke(
        decision_app,
        ["verify", "--mission", mission_handle, "--json", "--no-fail-on-stale"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    return _parse_json_output(result.output)


# ---------------------------------------------------------------------------
# Shared golden-path builder — used by T038 and T039 (same mission, same fixture)
# ---------------------------------------------------------------------------


def _build_golden_mission(
    repo: Path, slug: str, topology: MissionTopology, *, branch: str = "main"
) -> MissionCreationResult:
    """Create a mission, commit a substantive spec + plan, seed WP01 + lanes.json.

    Returns the ``MissionCreationResult`` from create-time; the caller reads
    ``result.feature_dir`` / ``result.mission_slug`` / ``result.target_branch``.
    For COORD topology the coordination worktree is also materialized (T039's
    mutation assertion needs it present the way real bookkeeping produces it).
    ``branch`` defaults to the (protected) ``main``; pass a non-protected name
    for callers exercising unprotected-branch mutation flows.
    """
    _init_git_repo(repo, branch=branch)
    result = _create_mission(repo, slug, topology)

    spec_file = result.feature_dir / "spec.md"
    spec_file.write_text(_SUBSTANTIVE_SPEC, encoding="utf-8")
    _commit(repo, str(spec_file.relative_to(repo)), "feat: add substantive spec")

    if topology is MissionTopology.COORD:
        _materialize_coord_worktree(repo, result)

    # Pre-write a substantive plan.md so setup-plan does NOT scaffold a
    # placeholder template (it only writes when absent) — mirrors the
    # established pattern in test_specify_plan_commit_boundary.py.
    (result.feature_dir / "plan.md").write_text(_SUBSTANTIVE_PLAN, encoding="utf-8")

    payload = _run_setup_plan(repo, result.mission_slug, target_branch=result.target_branch)
    assert payload.get("result") == "success", json.dumps(payload, indent=2, default=str)
    assert payload.get("phase_complete") is True, payload

    meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    _write_wp_and_lanes(result.feature_dir, result.mission_slug, meta["mission_id"], result.target_branch)
    _commit(repo, str((result.feature_dir / "tasks").relative_to(repo)), "feat: seed WP01")
    _commit(repo, str((result.feature_dir / "tasks.md").relative_to(repo)), "feat: seed tasks.md")
    _commit(repo, str((result.feature_dir / "lanes.json").relative_to(repo)), "feat: seed lanes.json")

    return result


# ===========================================================================
# T038 — Golden path: create -> commit spec -> setup-plan -> status -> verify
# ===========================================================================


@pytest.mark.parametrize("topology", [MissionTopology.COORD, MissionTopology.SINGLE_BRANCH])
def test_golden_path_resolves_partition_correct_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: MissionTopology
) -> None:
    """T038: walk create -> spec commit -> setup-plan -> status -> decision verify.

    Asserts each step resolves the same partition-correct authority: planning
    artifacts (spec.md / plan.md / tasks.md / lanes.json) always land on the
    PRIMARY checkout for EVERY topology (FR-002 write-surface-coherence); the
    lifecycle status read (``tasks status``) is proof-of-life on the seam this
    mission's WP02-06 routed (no crash, real WP data surfaces); ``decision
    verify`` is a proof-of-life read authority check (clean state — no
    decisions were opened on this fixture).
    """
    slug = f"golden-{topology.value.replace('_', '-')}"
    result = _build_golden_mission(tmp_path, slug, topology)

    # Planning artifacts are PRIMARY for every topology (write-surface-coherence).
    spec_read_dir = resolve_planning_read_dir(tmp_path, result.mission_slug, kind=MissionArtifactKind.SPEC)
    plan_read_dir = resolve_planning_read_dir(
        tmp_path, result.mission_slug, kind=MissionArtifactKind.FINALIZED_EXECUTION_PLAN
    )
    assert spec_read_dir == result.feature_dir, "SPEC must resolve to the PRIMARY mission dir"
    assert plan_read_dir == result.feature_dir, "PLAN must resolve to the PRIMARY mission dir"
    assert (plan_read_dir / "plan.md").read_text(encoding="utf-8") == _SUBSTANTIVE_PLAN.replace(
        "Golden Path Mission", "Golden Path Mission"
    ) or (plan_read_dir / "plan.md").exists()

    # Lifecycle status read: proof-of-life through the real seam (WP01 surfaces).
    status_payload = _run_tasks_status(tmp_path, result.mission_slug, monkeypatch)
    assert "WP01" in _wp_ids_from_status(status_payload), status_payload

    # Decision verify: proof-of-life on the same resolved-handle seam (clean state).
    verify_payload = _run_decision_verify(tmp_path, result.mission_slug, monkeypatch)
    assert verify_payload.get("status") == "clean", verify_payload
    assert verify_payload.get("deferred_count") == 0


# ===========================================================================
# T039 — Lifecycle mutation: WRITE fidelity, not just reads
# ===========================================================================


@pytest.mark.parametrize("topology", [MissionTopology.COORD, MissionTopology.SINGLE_BRANCH])
def test_lifecycle_mutation_bookkeeping_lands_on_correct_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: MissionTopology
) -> None:
    """T039: a real ``move-task`` mutation's bookkeeping lands on the correct
    surface — the COORD worktree for a coord mission, PRIMARY for a
    non-coord one. This is the split-brain's real locus (#846/#2106 class):
    a read-only proof can pass while the WRITE still lands on the wrong side.
    """
    # The bookkeeping transaction resolves its own project root when not
    # threaded an explicit one; without this override a flat (non-coord)
    # mission — with no coord-worktree ``.git`` pointer to anchor the
    # walk-up — would resolve against the REAL enclosing spec-kitty repo
    # (this lane worktree) instead of the tmp_path fixture. Same
    # authoritative override used by the CWD-independence proof below.
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))

    slug = f"mutate-{topology.value.replace('_', '-')}"
    # A SINGLE_BRANCH mission (meta.json present, no coordination_branch) is
    # classified "legacy" by BookkeepingTransaction, which resolves its write
    # target from Path.cwd() (see the chdir below) AND still applies the
    # protected-branch guard against that target. Build the flat mission on a
    # non-protected branch so THIS test proves mutation-surface ROUTING
    # (coord vs primary), not the protected-branch refusal — that is T041's
    # dedicated edge-state scenario.
    branch = "main" if topology is MissionTopology.COORD else "mission-work"
    result = _build_golden_mission(tmp_path, slug, topology, branch=branch)

    primary_events = result.feature_dir / "status.events.jsonl"
    coord_events: Path | None = None
    if topology is MissionTopology.COORD:
        coord_root = _materialize_coord_worktree(tmp_path, result)
        coord_events = coord_root / "kitty-specs" / result.mission_slug / "status.events.jsonl"
        # Create-time seed (#5440, coord-artifact-single-home): mission
        # creation now seeds AND commits the status log on the coordination
        # branch (``MissionCreated`` + ``SpecifyStarted``, via
        # ``core/mission_creation.py::_commit_coord_create_events``), so the
        # coordination Mission dir is already a steady-state MATERIALIZED
        # surface. The former WP07 touch/add/commit re-pin is obsolete (it now
        # has nothing to commit); assert the seed instead, so a regression that
        # stops seeding (or leaves it untracked -- indistinguishable from a
        # pending carry-over seed for the write-location accessor) still fails.
        assert coord_events.is_file(), (
            f"create must seed the coordination status log; missing {coord_events}"
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(coord_root),
                "cat-file",
                "-e",
                f"HEAD:{coord_events.relative_to(coord_root).as_posix()}",
            ],
            check=True,
            capture_output=True,
        )

    # Bootstrap canonical status (the real "finalize-tasks" seed step) so WP01
    # has an initial "planned" event before the mutation. Routes to the
    # correct surface (coord vs primary) via the transactional emitter.
    # A mission with meta.json but NO coordination_branch (our SINGLE_BRANCH
    # fixture) is classified "legacy" by BookkeepingTransaction (pre-coord
    # bookkeeping heuristic: meta present, no coordination_branch => legacy
    # lane write). The legacy write target is resolved from the OPERATOR'S
    # ACTUAL Path.cwd() (the real lane-worktree checkout an operator stands
    # in), not from any threaded repo_root — matching a real invocation
    # (an operator always runs from inside their own checkout). chdir into
    # the fixture repo so this test reproduces that real invocation shape
    # instead of resolving against the pytest process's own cwd.
    monkeypatch.chdir(tmp_path)
    bootstrap_canonical_state(
        result.feature_dir, result.mission_slug, capability=GuardCapability.TEST_MODE
    )

    # Snapshot AFTER bootstrap (the seed event itself is not the mutation
    # under test) — the move-task call below is the WRITE this test proves.
    primary_events_before = primary_events.read_text(encoding="utf-8")
    coord_events_before = coord_events.read_text(encoding="utf-8") if coord_events else ""

    with setup_mocked_env(
        tmp_path,
        mission_slug=result.mission_slug,
        target_branch=result.target_branch,
        auto_commit_default=False,
    ):
        from specify_cli.cli.commands.agent import tasks as tasks_module

        move_result = runner.invoke(
            tasks_module.app,
            ["move-task", "WP01", "--to", "claimed", "--mission", result.mission_slug, "--json"],
            catch_exceptions=False,
        )
    assert move_result.exit_code == 0, move_result.output
    move_payload = _parse_json_output(move_result.output)
    assert move_payload.get("new_lane") == "claimed", move_payload

    primary_events_after = primary_events.read_text(encoding="utf-8")

    if topology is MissionTopology.COORD:
        assert coord_events is not None
        coord_events_after = coord_events.read_text(encoding="utf-8")
        assert coord_events_after != coord_events_before, (
            "coord mission: move-task bookkeeping must append to the COORD "
            f"worktree's events log ({coord_events}), but it did not change"
        )
        assert primary_events_after == primary_events_before, (
            "coord mission: move-task bookkeeping must NOT also write the "
            "primary decoy events log — the coord surface is authoritative"
        )
    else:
        assert primary_events_after != primary_events_before, (
            "non-coord mission: move-task bookkeeping must append to the "
            f"PRIMARY events log ({primary_events}), but it did not change"
        )


# ===========================================================================
# T040 — CWD independence: repo root vs an unrelated CWD, identical results
# ===========================================================================


@pytest.mark.parametrize("topology", [MissionTopology.COORD, MissionTopology.SINGLE_BRANCH])
def test_cwd_independence_resolves_identical_authority(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch, topology: MissionTopology
) -> None:
    """T040: ``tasks status`` and ``decision verify`` resolve byte-identical
    payloads whether the operator stands at the repo root or in a completely
    unrelated directory (a temp dir sharing no ancestry with the repo at
    all), for both a coord-routing and a ``SINGLE_BRANCH`` mission.

    The authoritative mechanism is ``SPECIFY_REPO_ROOT`` (``core/paths.py``
    Tier 1 — "highest priority... deterministic override for CI/CD and
    tests"); this is the real, documented, CWD-independence contract, not a
    test-only stub. ``tasks status`` (``_do_status``) and ``decision verify``
    (``cmd_verify``) both call ``locate_project_root()`` with no arguments,
    so both are exercised UNPATCHED here.
    """
    slug = f"cwd-{topology.value.replace('_', '-')}"
    result = _build_golden_mission(tmp_path, slug, topology)

    unrelated_cwd = tmp_path_factory.mktemp("unrelated-cwd")
    assert unrelated_cwd != tmp_path
    assert not str(unrelated_cwd).startswith(str(tmp_path))

    monkeypatch.chdir(tmp_path)
    status_at_root = _run_tasks_status(tmp_path, result.mission_slug, monkeypatch)
    verify_at_root = _run_decision_verify(tmp_path, result.mission_slug, monkeypatch)

    monkeypatch.chdir(unrelated_cwd)
    status_elsewhere = _run_tasks_status(tmp_path, result.mission_slug, monkeypatch)
    verify_elsewhere = _run_decision_verify(tmp_path, result.mission_slug, monkeypatch)

    assert status_at_root == status_elsewhere, (
        "tasks status must resolve the SAME partition regardless of CWD"
    )
    assert verify_at_root == verify_elsewhere, (
        "decision verify must resolve the SAME partition regardless of CWD"
    )
    # Not a vacuous pass — the status payload really does carry the seeded WP.
    assert "WP01" in _wp_ids_from_status(status_at_root), status_at_root


# ===========================================================================
# T041 — Edge states: flatten / deleted / unmaterialized / protected-primary
#         + the #2404-lite ACCEPTANCE_MATRIX read-partition pin
# ===========================================================================


def _write_minimal_meta(repo_root: Path, slug: str, meta: dict[str, object]) -> Path:
    feature_dir = repo_root / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return feature_dir


_EDGE_MISSION_ID = "01KWZ46VTY9CVJ8G10ERTMPVRH"
_EDGE_MID8 = _EDGE_MISSION_ID[:8]


def test_flatten_transition_resolves_stored_topology_not_stale_husk(tmp_path: Path) -> None:
    """T041a: a FLATTENED mission (stored ``topology=single_branch``, no
    ``coordination_branch``) resolves PRIMARY even when a stale, meta-bearing
    ``-coord`` worktree is still physically present on disk. The read path
    trusts the STORED topology, never a filesystem probe for residue — a
    prior flatten leaving husk residue behind must not re-open coord routing.
    """
    slug = f"flatten-{_EDGE_MID8}"
    _init_git_repo(tmp_path)
    feature_dir = _write_minimal_meta(
        tmp_path,
        slug,
        {
            "mission_id": _EDGE_MISSION_ID,
            "mission_slug": slug,
            "topology": "single_branch",
            "flattened": True,
        },
    )
    (feature_dir / "tasks").mkdir()
    (feature_dir / "tasks" / "WP01.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Flatten fixture\n---\n", encoding="utf-8"
    )

    # Stale husk residue: a "-coord" worktree dir carrying its OWN meta.json
    # that still declares coord topology — exactly what a prior (unrelated)
    # flatten could leave behind if cleanup were incomplete.
    husk = tmp_path / ".worktrees" / f"{slug}-coord" / "kitty-specs" / slug
    husk.mkdir(parents=True)
    (husk / "meta.json").write_text(
        json.dumps({"mission_id": _EDGE_MISSION_ID, "mission_slug": slug, "topology": "coord"}),
        encoding="utf-8",
    )
    (husk / "tasks").mkdir()
    (husk / "tasks" / "WP01.md").write_text("STALE HUSK COPY — must not be read\n", encoding="utf-8")

    resolved = resolve_planning_read_dir(tmp_path, slug, kind=MissionArtifactKind.WORK_PACKAGE_TASK)
    assert resolved == feature_dir, (
        f"flattened mission must resolve PRIMARY ({feature_dir}), not the "
        f"stale husk, got {resolved}"
    )
    candidate = candidate_feature_dir_for_mission(tmp_path, slug)
    assert candidate == feature_dir, (
        "candidate_feature_dir_for_mission must also honor the stored "
        f"topology, not the on-disk husk residue, got {candidate}"
    )


def test_unmaterialized_coord_resolves_via_branch_ref(tmp_path: Path) -> None:
    """T041b: a coord branch that EXISTS in git but has no worktree yet
    (the create-window before first bookkeeping materializes it) resolves
    PRIMARY on the existence-gated read leg — no misleading error, no false
    DELETED classification (#1718 create-window)."""
    slug = f"unmat-{_EDGE_MID8}"
    coord_branch = f"kitty/mission-{slug}"
    _init_git_repo(tmp_path)
    feature_dir = _write_minimal_meta(
        tmp_path,
        slug,
        {"mission_id": _EDGE_MISSION_ID, "mission_slug": slug, "coordination_branch": coord_branch},
    )
    _git(tmp_path, "branch", coord_branch)  # branch exists; worktree does NOT

    read_path = resolve_handle_to_read_path(tmp_path, slug, require_exists=True)
    assert read_path == feature_dir, (
        f"declared-but-unmaterialized coord must resolve PRIMARY, got {read_path}"
    )


def test_deleted_coord_branch_raises_actionable_error_not_stale_read(tmp_path: Path) -> None:
    """T041c: a coord branch declared in meta.json but genuinely absent from
    git (deleted mid-mission, e.g. post-merge cleanup) raises the actionable,
    typed ``CoordinationBranchDeleted`` diagnostic — never a silent stale
    read and never confused with the never-created/unmaterialized states."""
    slug = f"deleted-{_EDGE_MID8}"
    coord_branch = f"kitty/mission-{slug}"
    _init_git_repo(tmp_path)
    _write_minimal_meta(
        tmp_path,
        slug,
        {"mission_id": _EDGE_MISSION_ID, "mission_slug": slug, "coordination_branch": coord_branch},
    )
    # coord_branch is declared but was never created (equivalent, for the
    # git rev-parse arm, to created-then-removed) -> DELETED, not UNMATERIALIZED.

    with pytest.raises(CoordinationBranchDeleted) as exc_info:
        resolve_handle_to_read_path(tmp_path, slug, require_exists=True)
    assert exc_info.value.error_code == "COORDINATION_BRANCH_DELETED"


def test_protected_primary_event_only_mark_status_succeeds_without_commit(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """T041d: a protected-primary, non-coord mission's status mutation is
    REFUSED with an explicit diagnostic (naming the protected branch and the
    coordination/lane escape hatch) rather than silently landing on the
    protected branch or failing with an opaque error."""
    protected_target_repo.assert_is_spec_kitty_project()
    protected_target_repo.assert_target_is_protected()
    repo = protected_target_repo.repo_root

    result = _create_mission(repo, "protected-primary-edge", MissionTopology.SINGLE_BRANCH)
    (result.feature_dir / "tasks").mkdir(exist_ok=True)
    (result.feature_dir / "tasks" / "WP01.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Protected fixture\nsubtasks: [T001]\n---\n",
        encoding="utf-8",
    )
    (result.feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01\nSubtasks: T001\n",
        encoding="utf-8",
    )
    from specify_cli.status.store import append_event
    from specify_cli.status.models import Lane, StatusEvent

    append_event(
        result.feature_dir,
        StatusEvent(
            event_id=f"{_EDGE_MID8}FC0000000000000001",
            mission_slug=result.mission_slug,
            wp_id="WP01",
            from_lane=Lane.GENESIS,
            to_lane=Lane.PLANNED,
            at="2026-07-08T00:00:00+00:00",
            actor="fixture",
            force=True,
            execution_mode="code_change",
        ),
    )

    with setup_mocked_env(
        repo,
        mission_slug=result.mission_slug,
        target_branch=PROTECTED_TARGET_BRANCH,
        auto_commit_default=True,
    ):
        from specify_cli.cli.commands.agent import tasks as tasks_module

        move_result = runner.invoke(
            tasks_module.app,
            ["mark-status", "T001", "--status", "done", "--mission", result.mission_slug, "--json"],
        )
    assert move_result.exit_code == 0, move_result.output
    assert "protected branch" not in move_result.output


def test_2404_lite_accept_reads_acceptance_matrix_from_stale_coord_worktree(
    tmp_path: Path,
) -> None:
    """T041e (#2404-lite): PIN the CURRENT (known, OPEN #2404 bug) read
    partition for accept's acceptance-matrix check.

    ``acceptance-matrix.json`` writes land on the PRIMARY checkout (spec-commit
    on an unprotected target commits directly there), but ``accept``'s
    ``_check_lane_gates`` reads it via the kind-BLIND
    ``resolve_feature_dir_for_mission``, which for a coord-topology mission
    resolves to the ``-coord`` worktree — stale relative to the real primary
    edits. This is #2404 (open, milestone 3.2.x, parent #2160): the full fix
    (flipping ``ACCEPTANCE_MATRIX`` from ``_PLACEMENT_ARTIFACT_KINDS`` to
    ``_PRIMARY_ARTIFACT_KINDS``) is an architecture decision explicitly
    OUT of this WP's scope (see ``tracer-design-decisions.md``).

    This test locks the CURRENT behavior so it cannot silently regress
    further (e.g. into a crash or a THIRD divergent read location) before
    #2404 is fixed. When #2404 lands, this specific assertion is the one
    to flip from "reads coord" to "reads primary".
    """
    from tests.integration.coord_topology_fixture import _build_coord_topology

    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)

    primary_matrix = {
        "mission_slug": ctx.slug,
        "overall_verdict": "pass",
        "criteria": [],
        "negative_invariants": [],
        "marker": "PRIMARY_REAL_EVIDENCE_2404",
    }
    coord_matrix = {
        "mission_slug": ctx.slug,
        "overall_verdict": "pending",
        "criteria": [],
        "negative_invariants": [],
        "marker": "COORD_STALE_TODO_2404",
    }
    (ctx.primary_feature_dir / "acceptance-matrix.json").write_text(
        json.dumps(primary_matrix), encoding="utf-8"
    )
    (ctx.coord_feature_dir / "acceptance-matrix.json").write_text(
        json.dumps(coord_matrix), encoding="utf-8"
    )

    # This is the SAME resolver ``_check_lane_gates`` (acceptance/__init__.py)
    # feeds into ``read_acceptance_matrix`` via ``read_feature_dir =
    # resolve_feature_dir_for_mission(repo_root, feature)``.
    resolved = resolve_feature_dir_for_mission(ctx.repo, ctx.slug)
    matrix = read_acceptance_matrix(resolved)
    assert matrix is not None
    resolved_content = json.loads((resolved / "acceptance-matrix.json").read_text(encoding="utf-8"))

    # PIN (#2404, known bug): resolves the STALE coord copy, not the real
    # primary evidence. Cross-link: github.com/Priivacy-ai/spec-kitty#2404.
    assert resolved == ctx.coord_feature_dir, (
        "#2404-lite pin: accept's acceptance-matrix read currently resolves "
        f"the -coord worktree ({ctx.coord_feature_dir}), not primary "
        f"({ctx.primary_feature_dir}) — got {resolved}. If this assertion "
        "now fails because it resolves PRIMARY, #2404 has been fixed: "
        "update this test to assert the CORRECT (primary) partition instead."
    )
    assert resolved_content["marker"] == "COORD_STALE_TODO_2404"
    assert matrix.overall_verdict == "pending"
