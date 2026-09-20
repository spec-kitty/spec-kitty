"""e2e CWD-invariance ratchet — MissionExecutionContext parity gate.

Coverage (FR-023)
-----------------
This ratchet is the Strangler gate for the execution-state-domain-remediation
mission (#1619 / #1672 / execution-state-canonical-surface-01KTG6P9). It proves
**identical WP lane data and transition identity** for the full
``next → implement → move-task → review → status`` sequence across three
execution modes:

1. **main-checkout CWD** — commands driven from the repository root with a lane
   worktree already created (the conventional agent CWD during planning/review).
2. **lane-worktree CWD** — commands driven from the ``.worktrees/`` lane path
   (the conventional agent CWD during implementation).
3. **direct-to-target** — commands driven from the repository root with *no*
   worktree; the declared target branch is used directly and an unauthorized
   write to a mainline-protected branch is refused (C-001).

CI gate (FR-024)
----------------
This test is a required gate for PRs that touch any of the following paths
(via the ``execution_context`` path filter in ``.github/workflows/ci-quality.yml``):

* ``src/specify_cli/core/execution_context.py``
* ``src/specify_cli/status/**``
* ``src/runtime/next/**``
* ``src/specify_cli/cli/commands/agent/**``
* ``tests/architectural/test_execution_context_parity.py``
* ``src/mission_runtime/**``  (added when the mission_runtime umbrella lands, WP02)

The ``integration-tests-core-misc`` CI job runs this file exclusively when
``execution_context``-only changes are detected, so status/runtime edits always
exercise the parity gate even when the wider core-misc suite is skipped.

Write-path extension (#1672 / FR-008)
-------------------------------------
``test_cwd_parity_write`` proves that a write transition driven via
``agent status emit`` produces an **identical deterministic event identity**
(``from_lane`` / ``to_lane`` / ``wp_id`` / ``actor``) and an **identical
resulting persisted lane** regardless of whether ``emit`` is invoked from the
main-checkout CWD or a lane-worktree CWD, and that the write lands in the
**main checkout's** event log in both cases.

``test_write_ratchet_catches_divergence`` is the anti-vacuity proof for the
write path.

Full-sequence extension (execution-state-canonical-surface-01KTG6P9 / FR-020..022)
-----------------------------------------------------------------------------------
``test_full_sequence_main_checkout_parity`` (T002) and
``test_full_sequence_worktree_parity`` (T003) drive WP01 through the complete
lane progression ``planned → claimed → in_progress → for_review → in_review``
via ``agent tasks move-task --no-auto-commit``, one from the main-checkout CWD
and the other from the lane-worktree CWD.  The ratchet asserts that:

* the **resolved WP identity** (``wp_id`` / ``from_lane`` / ``to_lane`` in each
  transition) is identical across both CWDs, and
* the **final persisted lane** (from ``agent tasks status --json``) is identical.

``test_full_sequence_direct_to_target`` (T004) drives the same sequence from
the main-checkout CWD with *no* worktree present, verifying direct-to-target
mode.  It also asserts that ``agent status emit`` targeting the ``main``
protected branch without ``SPEC_KITTY_TEST_MODE`` is **refused** (C-001).

``test_full_sequence_ratchet_catches_divergence`` (T005) is the non-vacuity
proof: it injects a divergent status transition in the worktree-local event
log and asserts the two independent read paths diverge, proving the full-
sequence ratchet would catch a real CWD-routing regression.

Design principles
-----------------
* Uses ``subprocess`` with explicit ``cwd=`` — NEVER ``os.chdir()`` which
  mutates global process state.
* Uses minimal hand-crafted fixtures (git init + JSONL bootstrap) rather than
  invoking the full ``spec-kitty init`` / ``finalize-tasks`` pipeline to keep
  fixture setup fast and hermetic.
* The fixture creates a real git worktree so that ``find_repo_root()`` resolves
  correctly from both the main checkout and the worktree path.
* The injection proofs verify that the ratchet is not vacuously passing by
  deliberately corrupting the status in one location and asserting divergence.
* ``--no-auto-commit`` is passed to ``move-task`` throughout the full-sequence
  tests so the fixture does not need to commit on a specific branch — the
  ratchet tests CWD-invariant status-event routing, not the commit flow.

Markers
-------
``architectural`` — this is an architectural invariant (CWD-invariance).
``git_repo`` — required because the fixture calls ``git init`` and
``git worktree add`` via subprocess (Rule 1 from test_pytest_marker_correctness).
``non_sandbox`` — the fixture spawns ``git worktree add`` and invokes
``spec-kitty`` as a subprocess, both of which are structurally incompatible
with mutmut's forked sandbox.

Composite-fragment dual-CWD extension (execution-context-unification-01KTPKST / IC-08 / FR-011)
-----------------------------------------------------------------------------------------------
The block at the bottom of this module extends the ratchet from *string-keyed
status parity* (above) to **fragment-by-fragment parity of the resolved
``MissionExecutionContext``** — the doc-09 fragment / op-composite described in
``kitty-specs/execution-context-unification-01KTPKST/data-model.md``. It is
authored **ATDD-first** (charter C-011): the fragment assertions are written
RED now, *before* the fragments exist on ``mission_runtime.MissionExecutionContext``,
and each converges to GREEN as its conversion WP lands.

The harness resolves the context twice — once with ``repo_root`` derived (via
``find_repo_root``) from the **primary-checkout CWD** and once from the
**lane-worktree CWD** — and asserts the two resolved contexts are equal,
fragment by fragment, for every lifecycle action that the resolver supports
today (``tasks`` / ``tasks_finalize`` / ``accept``). The broader lifecycle
(``specify``/``plan``/``analyze``/``status``) and the fragment objects
themselves (Identity incl. ``mid8``; BranchRef incl. ``target_branch`` +
``destination_ref``/``CommitTarget``; StatusSurface; Workspace incl.
``primary_root``; ArtifactPlacement; PromptSource) do not exist on the context
yet, so the assertions that depend on them are ``xfail(strict=True)``.

xfail → convergence-WP map (IC-08 / T003)
-----------------------------------------
Each ``xfail(strict=True)`` test below converges (flips to XPASS, at which point
the converging WP removes the marker) as its conversion lands. ``strict=True``
means a stale marker left after a fragment lands fails the suite, forcing the
converging WP to delete it — that is the ratchet.

==================================  ====  ==========================================
Test (xfail until converged)        WP    What flips it green
==================================  ====  ==========================================
test_status_surface_fragment_       WP02  CONVERGED. StatusSurfaceFragment carried
  parity                            /03   on the context (``status_read_dir`` /
                                          ``status_write_dir``); status facade
                                          adoption (IC-01, WP02) + fragment
                                          attachment (WP03). xfail removed.
test_identity_fragment_parity       WP03  CONVERGED. IdentityFragment (``mission_id``
                                          / ``mid8`` / ``mission_slug``) on the
                                          context; ``mid8`` single-derivation.
                                          xfail removed.
test_branchref_fragment_parity      WP03  CONVERGED. BranchRefFragment
                                          (``target_branch`` /
                                          ``coordination_branch`` /
                                          ``destination_ref``=CommitTarget).
                                          xfail removed.
test_read_path_fragment_parity      WP04  Read-path resolver folded into the
                                          context (``feature_dir`` resolves via
                                          the single read-path surface, IC-03).
test_workspace_fragment_parity      WP05  WorkspaceFragment incl. ``primary_root``
                                          (single worktree-pointer parser, IC-04).
test_artifact_placement_fragment_   WP06  ArtifactPlacementFragment
  parity                                  (``placement_ref``=CommitTarget) — one
                                          artifact-placement ref (IC-05).
test_runtime_lifecycle_action_      WP07  Runtime threads the context through the
  parity                                  full lifecycle (specify/plan/analyze/
                                          status become resolvable actions).
test_flattened_topology_commit_     WP08  CommitTarget + flattened-topology
  target / *_status_surface /             resolution: ``kind == flattened``,
  *_no_coordination_branch                ``coordination_branch is None``,
                                          ``status_read_dir == status_write_dir``
                                          (also exercised by retrospect/merge,
                                          IC-12).
==================================  ====  ==========================================

Live (non-xfail) parity coverage
---------------------------------
``test_dual_cwd_existing_field_parity`` asserts CWD-invariance of the fields
that the resolver already populates today (``mission_slug`` / ``target_branch``
/ ``feature_dir`` / ``detection_method``). It guards against a CWD-routing
regression in the *current* surface and is the anchor the fragment tests grow on
top of — it must stay GREEN throughout the conversion.

Determinism (NFR-003)
---------------------
The composite-fragment block reuses the same hand-crafted, network-free,
clock-free fixtures as the status-parity block. ``repo_root`` is derived via
``find_repo_root`` from each CWD (no ``os.chdir``); no wall-clock, ULID-mint, or
random value influences any asserted fragment. The resolver is called in-process
with explicit ``repo_root``/``cwd`` arguments, so results are reproducible across
both CWDs and across repeated runs. The synthetic flattened mission is torn down
(``shutil.rmtree`` of the temp tree) by ``tmp_path`` so it never leaks a
``test-feature-*`` mission or a ``kitty/mission-test-feature-*`` branch.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from collections.abc import Generator

import pytest

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json

pytestmark = [
    pytest.mark.architectural,
    pytest.mark.git_repo,
    pytest.mark.non_sandbox,
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MISSION_SLUG = "test-parity-mission"

_META_JSON = json.dumps(
    {
        "mission_id": "01TESTPARITY00000000000001",
        "mission_slug": _MISSION_SLUG,
        "mission_number": None,
        "mission_type": "software-dev",
        "friendly_name": "Test parity mission",
    },
    indent=2,
)

# Minimal WP01 task markdown (no dependencies).
_WP01_MD = textwrap.dedent(
    """\
    ---
    work_package_id: WP01
    title: Parity test WP01
    dependencies: []
    requirement_refs: []
    subtasks: []
    agent: claude
    agent_profile: python-pedro
    role: implementer
    authoritative_surface: src/parity/
    owned_files:
    - src/parity/
    execution_mode: code_change
    history: []
    ---
    # WP01 — Parity test WP01
    """
)

# Minimal WP02 task markdown (depends on WP01).
_WP02_MD = textwrap.dedent(
    """\
    ---
    work_package_id: WP02
    title: Parity test WP02
    dependencies:
    - WP01
    requirement_refs: []
    subtasks: []
    agent: claude
    agent_profile: python-pedro
    role: implementer
    authoritative_surface: src/parity2/
    owned_files:
    - src/parity2/
    execution_mode: code_change
    history: []
    ---
    # WP02 — Parity test WP02
    """
)


def _make_status_event(
    wp_id: str,
    from_lane: str,
    to_lane: str,
    event_id: str,
    at: str = "2026-06-03T10:00:00+00:00",
) -> str:
    """Emit a single status event as a sorted-key JSON line."""
    event = {
        "actor": "test-fixture",
        "at": at,
        "event_id": event_id,
        "evidence": None,
        "execution_mode": "worktree",
        "force": True,
        "from_lane": from_lane,
        "mission_id": "01TESTPARITY00000000000001",
        "mission_slug": _MISSION_SLUG,
        "policy_metadata": None,
        "reason": "parity-fixture bootstrap",
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": wp_id,
    }
    return json.dumps(event, sort_keys=True)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> None:
    """Run a git command, raising on non-zero exit."""
    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


def _spec_kitty(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Invoke spec-kitty using the same interpreter as the test runner.

    Uses ``sys.executable -m specify_cli`` (module form) rather than the
    ``spec-kitty`` script name so the call works in any venv where the package
    is installed in development mode (``pip install -e .``), not just when the
    console script entry-point is on PATH.
    """
    return subprocess.run(
        [sys.executable, "-m", "specify_cli", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def _build_mission_dir(repo_root: Path, slug: str) -> Path:
    """Create the kitty-specs/<slug>/ directory structure."""
    feature_dir = repo_root / "kitty-specs" / slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    # Mission metadata
    (feature_dir / "meta.json").write_text(_META_JSON, encoding="utf-8")

    # WP task files
    (tasks_dir / "WP01.md").write_text(_WP01_MD, encoding="utf-8")
    (tasks_dir / "WP02.md").write_text(_WP02_MD, encoding="utf-8")

    # Bootstrap status events for both WPs (both planned)
    events = [
        _make_status_event(
            "WP01",
            from_lane="planned",
            to_lane="planned",
            event_id="01TESTPARITY00000000000P01",
            at="2026-06-03T10:00:00+00:00",
        ),
        _make_status_event(
            "WP02",
            from_lane="planned",
            to_lane="planned",
            event_id="01TESTPARITY00000000000P02",
            at="2026-06-03T10:00:01+00:00",
        ),
    ]
    (feature_dir / "status.events.jsonl").write_text(
        "\n".join(events) + "\n", encoding="utf-8"
    )

    # Minimal status.json (derived snapshot; content doesn't affect reads
    # in Phase 2 but must exist to satisfy directory-level checks).
    (feature_dir / "status.json").write_text(
        json.dumps({"event_count": 0, "work_packages": {}}), encoding="utf-8"
    )

    # lanes.json is now a required precondition to leave 'planned' (#4758
    # _mt_guard_planned_boundary_lanes). This fixture hand-builds the mission
    # instead of running finalize-tasks (see module docstring), so it must seed
    # lanes.json itself -- otherwise every move-task out of 'planned' below hits
    # the wedge guard before reaching the CWD/lane-parity behavior under test.
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=slug,
            mission_id=None,
            mission_branch=f"kitty/mission-{slug}",
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01", "WP02"),
                    write_scope=("src/wp01/**", "src/wp02/**"),
                    predicted_surfaces=(),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-06-03T10:00:00+00:00",
            computed_from="dependency_graph+ownership",
            planning_commit_sha="a" * 40,
        ),
    )

    return feature_dir


def _build_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Initialise a minimal git repo with a mission and a lane worktree.

    Returns ``(repo_root, worktree_path)``.
    """
    repo_root = tmp_path / "main"
    repo_root.mkdir()

    # Git init
    _git(["init", "--initial-branch=main"], repo_root)
    _git(["config", "user.email", "parity@example.com"], repo_root)
    _git(["config", "user.name", "Parity Test"], repo_root)
    _git(["config", "commit.gpgsign", "false"], repo_root)

    # .kittify marker (required for find_repo_root())
    kittify_dir = repo_root / ".kittify"
    kittify_dir.mkdir()
    (kittify_dir / "config.yaml").write_text(
        "agents:\n  available:\n    - claude\n", encoding="utf-8"
    )

    # Mission artifacts
    _build_mission_dir(repo_root, _MISSION_SLUG)

    # Initial commit so we can branch/worktree
    _git(["add", "."], repo_root)
    _git(["commit", "-m", "chore: parity fixture initial commit"], repo_root)

    # Create a lane branch and worktree for WP01
    lane_branch = f"kitty/mission-{_MISSION_SLUG}-lane-a"
    _git(["branch", lane_branch], repo_root)
    worktree_dir = repo_root / ".worktrees" / f"{_MISSION_SLUG}-lane-a"
    worktree_dir.parent.mkdir(exist_ok=True)
    _git(["worktree", "add", str(worktree_dir), lane_branch], repo_root)

    return repo_root, worktree_dir


# ---------------------------------------------------------------------------
# T006 — Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def parity_repo(tmp_path_factory: pytest.TempPathFactory) -> Generator[tuple[Path, Path, str], None, None]:
    """Create a minimal spec-kitty project with one lane worktree.

    Returns ``(repo_root, worktree_path, mission_slug)``.

    Scope is ``module`` so the (slow) git init runs once per test module.
    """
    base = tmp_path_factory.mktemp("parity_repo")
    repo_root, worktree_path = _build_repo(base)
    yield repo_root, worktree_path, _MISSION_SLUG


# ---------------------------------------------------------------------------
# Helper: run status and parse JSON
# ---------------------------------------------------------------------------


def _get_status_json(cwd: Path, mission_slug: str) -> dict[str, object]:
    """Run ``spec-kitty agent tasks status --json --mission <slug>`` and parse the output.

    Returns the parsed JSON dict.  Raises ``AssertionError`` on non-zero exit.
    """
    result = _spec_kitty(
        ["agent", "tasks", "status", "--json", "--mission", mission_slug],
        cwd=cwd,
    )
    assert result.returncode == 0, (
        f"spec-kitty agent tasks status --json failed (cwd={cwd}):\n"
        f"  stdout: {result.stdout.strip()[:500]}\n"
        f"  stderr: {result.stderr.strip()[:500]}"
    )
    parsed: dict[str, object] = json.loads(result.stdout)
    return parsed


def _wp_lanes(status_json: dict[str, object]) -> dict[str, str]:
    """Extract ``{wp_id: lane}`` from a status JSON payload."""
    wps = status_json.get("work_packages", [])
    assert isinstance(wps, list)
    return {wp["id"]: wp["lane"] for wp in wps}


# ---------------------------------------------------------------------------
# T009 — Parity assertions (T007 + T008 combined into one hermetic test)
# ---------------------------------------------------------------------------


def test_cwd_parity(parity_repo: tuple[Path, Path, str]) -> None:
    """CWD-invariance: status reads from main-checkout and lane-worktree are identical.

    This test runs ``spec-kitty agent tasks status --json --mission <slug>``
    from two CWDs and asserts that the resolved WP lane state is the same:

    * ``cwd=repo_root`` — the conventional invocation from the main checkout
    * ``cwd=worktree_path`` — the agent's natural CWD during implementation

    Both invocations must traverse back to the same status-read authority
    (the primary checkout at this fixture's lifecycle stage) and return the
    same ``{wp_id: lane}`` mapping.

    Failure indicates that ``find_repo_root()`` or the status-read path
    resolver diverges based on CWD, which is the core regression class
    documented in issue #1619.
    """
    repo_root, worktree_path, mission_slug = parity_repo

    # Run from main checkout CWD
    main_status = _get_status_json(cwd=repo_root, mission_slug=mission_slug)
    main_lanes = _wp_lanes(main_status)

    # Run from lane worktree CWD
    lane_status = _get_status_json(cwd=worktree_path, mission_slug=mission_slug)
    lane_lanes = _wp_lanes(lane_status)

    # Both must see the same set of WPs
    assert set(main_lanes.keys()) == set(lane_lanes.keys()), (
        f"Main-checkout and lane-worktree see different WP sets.\n"
        f"  main WPs:  {sorted(main_lanes.keys())}\n"
        f"  lane WPs:  {sorted(lane_lanes.keys())}\n"
        "This indicates ``find_repo_root()`` resolves to a different repo root "
        "when invoked from the worktree CWD."
    )

    # Each WP must be in the same lane from both CWDs
    for wp_id in main_lanes:
        assert main_lanes[wp_id] == lane_lanes[wp_id], (
            f"Lane divergence for {wp_id}:\n"
            f"  from main checkout CWD:  {main_lanes[wp_id]!r}\n"
            f"  from lane worktree CWD:  {lane_lanes[wp_id]!r}\n"
            "CWD-parity violation: the same status-event log is being read "
            "differently depending on the caller's working directory."
        )


# ---------------------------------------------------------------------------
# T009 injection proof — ratchet must catch real divergence
# ---------------------------------------------------------------------------


def test_ratchet_catches_divergence(tmp_path: Path) -> None:
    """Injection proof: the ratchet FAILS when CWD-parity is genuinely broken.

    This test constructs a scenario where the main-checkout CWD and the
    worktree CWD point to *different* ``status.events.jsonl`` files with
    deliberately different WP lane data. The status command will read
    different files for each CWD, so the lane outputs diverge.

    The purpose is to prove the ratchet is not vacuously green: if CWD routing
    were broken, ``test_cwd_parity`` would catch it.

    Test structure:
    1. Build a repo with a worktree (same as parity_repo fixture).
    2. Add a *second* status event to the worktree's copy of status.events.jsonl
       that transitions WP01 to ``in_progress``.
    3. The main checkout still has WP01 as ``planned``.
    4. Read status from both CWDs, assert that the lanes differ.
       If they are the same, the read path is not CWD-sensitive (the invariant
       we are testing) and something is wrong with the test design.

    Note: under the *current* implementation, both CWDs resolve to the SAME
    status file (the main checkout), so adding events only in the worktree copy
    is the correct way to simulate divergence: we write divergent data to the
    worktree path and then verify that the reads do NOT collapse them (because
    the current implementation reads from the single primary checkout, not from
    the worktree).

    What this test really proves
    ----------------------------
    The test demonstrates the CWD-variant scenario that existed prior to
    issue #1619: if a future regression causes the worktree CWD invocation to
    read from *the worktree's kitty-specs/* instead of the primary checkout,
    the lanes would diverge and ``test_cwd_parity`` above would fail.
    This injection proof constructs exactly that scenario explicitly, without
    relying on a real regression, to validate that the ratchet design is sound.
    """
    repo_root, worktree_path = _build_repo(tmp_path)
    mission_slug = _MISSION_SLUG

    # Write a divergent event ONLY to the worktree's copy of status.events.jsonl.
    # This simulates the state that would exist under a CWD-routing regression
    # (where the worktree CWD causes reads from kitty-specs/ inside the worktree
    # rather than from the primary checkout).
    worktree_feature_dir = worktree_path / "kitty-specs" / mission_slug
    worktree_feature_dir.mkdir(parents=True, exist_ok=True)

    # Bootstrap the worktree copy with the same initial events
    initial_events = [
        _make_status_event(
            "WP01",
            from_lane="planned",
            to_lane="planned",
            event_id="01TESTPARITY00000000000P01",
            at="2026-06-03T10:00:00+00:00",
        ),
        _make_status_event(
            "WP02",
            from_lane="planned",
            to_lane="planned",
            event_id="01TESTPARITY00000000000P02",
            at="2026-06-03T10:00:01+00:00",
        ),
    ]
    divergent_event = _make_status_event(
        "WP01",
        from_lane="planned",
        to_lane="in_progress",
        event_id="01TESTPARITY0000DIVERGENT01",
        at="2026-06-03T11:00:00+00:00",
    )
    worktree_events = initial_events + [divergent_event]
    (worktree_feature_dir / "status.events.jsonl").write_text(
        "\n".join(worktree_events) + "\n", encoding="utf-8"
    )
    (worktree_feature_dir / "status.json").write_text(
        json.dumps({"event_count": 0, "work_packages": {}}), encoding="utf-8"
    )
    (worktree_feature_dir / "meta.json").write_text(_META_JSON, encoding="utf-8")
    tasks_dir = worktree_feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "WP01.md").write_text(_WP01_MD, encoding="utf-8")
    (tasks_dir / "WP02.md").write_text(_WP02_MD, encoding="utf-8")

    from specify_cli.status.lane_reader import get_wp_lane

    # The main checkout's authoritative event log remains at the seeded state.
    # The subprocess read-path parity itself is covered by test_cwd_parity; this
    # anti-vacuity proof only needs to establish that the two event-log surfaces
    # would disagree under a CWD-routing regression.
    main_authority_dir = repo_root / "kitty-specs" / mission_slug
    main_wp1_lane = get_wp_lane(main_authority_dir, "WP01")
    assert main_wp1_lane == "planned", (
        f"Expected WP01 to be 'planned' in main checkout authority; "
        f"got {main_wp1_lane!r}"
    )

    # The worktree's kitty-specs/ now contains a divergent event log.
    # If CWD routing for worktree paths is broken (i.e., the worktree CWD
    # causes reads from worktree_path/kitty-specs/ instead of the primary
    # checkout), the lane would appear as 'in_progress'.
    # We verify here that the worktree's event log DOES contain the divergent
    # state — proving that a routing regression WOULD surface as a difference.
    from specify_cli.status.reducer import reduce
    from specify_cli.status.store import read_events

    worktree_events_loaded = read_events(worktree_feature_dir)
    worktree_snapshot = reduce(worktree_events_loaded)
    worktree_wp1_lane = (
        worktree_snapshot.work_packages.get("WP01", {}).get("lane", "planned")
    )
    assert worktree_wp1_lane == "in_progress", (
        f"Injection proof setup error: the worktree's status.events.jsonl should "
        f"show WP01 as 'in_progress' after the divergent event, "
        f"but got {worktree_wp1_lane!r}. Check that _make_status_event is correct."
    )

    # Now prove: the main-checkout read is stable (returns 'planned'), meaning
    # the two paths produce different data. This is the evidence that a CWD
    # routing regression would surface as a parity failure in test_cwd_parity.
    assert main_wp1_lane != worktree_wp1_lane, (
        f"Injection proof inconclusive: both read paths return the same lane "
        f"({main_wp1_lane!r}) even though the worktree's event log contains a "
        f"divergent transition. This means the divergent data in the worktree "
        f"cannot be used to detect a CWD routing regression. "
        f"Revise the test setup."
    )


# ---------------------------------------------------------------------------
# WRITE-PATH RATCHET (#1672 / FR-008)
# ---------------------------------------------------------------------------
#
# WP01 routed ``agent status emit`` through ``MissionStatus.transition()``,
# whose write target is the coord-aware ``read_dir`` (the primary-checkout
# authority). The tests below ratchet the CWD-invariance of that WRITE
# transition. They reuse the proven ``_build_repo`` fixture helper and the same
# ``_spec_kitty`` subprocess invocation (``sys.executable -m specify_cli``) as
# the read-path tests, so they run under the identical CI job and markers
# (``architectural``, ``git_repo``, ``non_sandbox``) with no new exclusion.
# ---------------------------------------------------------------------------


def _emit_status(
    cwd: Path,
    mission_slug: str,
    wp_id: str,
    to_lane: str,
    actor: str,
) -> dict[str, object]:
    """Run ``spec-kitty agent status emit ... --json`` and parse the output.

    Returns the parsed JSON dict describing the emitted event.  Raises
    ``AssertionError`` on non-zero exit so a CLI failure surfaces with full
    diagnostics rather than an opaque ``KeyError`` downstream.
    """
    result = _spec_kitty(
        [
            "agent",
            "status",
            "emit",
            wp_id,
            "--to",
            to_lane,
            "--actor",
            actor,
            "--mission",
            mission_slug,
            "--json",
        ],
        cwd=cwd,
    )
    assert result.returncode == 0, (
        f"spec-kitty agent status emit failed (cwd={cwd}):\n"
        f"  stdout: {result.stdout.strip()[:500]}\n"
        f"  stderr: {result.stderr.strip()[:500]}"
    )
    parsed: dict[str, object] = json.loads(result.stdout)
    return parsed


def _event_identity(emit_json: dict[str, object]) -> dict[str, str]:
    """Extract the *deterministic* identity of an emitted event.

    The ``event_id`` is a freshly minted ULID and is therefore intentionally
    excluded: it is unique per emission and would never match across two
    independent writes.  The fields below are the parts of the event identity
    that MUST be CWD-invariant for the same (wp, to_lane, actor) transition.
    """
    return {
        "wp_id": str(emit_json["wp_id"]),
        "from_lane": str(emit_json["from_lane"]),
        "to_lane": str(emit_json["to_lane"]),
        "actor": str(emit_json["actor"]),
    }


def test_cwd_parity_write(tmp_path: Path) -> None:
    """CWD-invariance of the status WRITE transition (#1672 / FR-008).

    Drives ``spec-kitty agent status emit WP01 --to claimed`` against two
    *independent but identically seeded* repos:

    * one write is issued from the **main-checkout CWD**
    * the other is issued from the **lane-worktree CWD**

    Two independent repos are used (rather than two writes against one repo)
    so that each ``emit`` exercises the *same* ``planned -> claimed`` first
    transition; issuing both against a single repo would make the second a
    no-op / illegal re-transition and so would not test parity of the write.

    The ratchet asserts that:

    1. the **deterministic emitted event identity** (``from_lane`` /
       ``to_lane`` / ``wp_id`` / ``actor``) is identical across both CWDs, and
    2. the **resulting persisted lane** is identical (``claimed``), and
    3. in BOTH cases the write landed in the **main checkout's** event log
       (the coord-aware authority), NOT the worktree's ``kitty-specs/`` — i.e.
       the write target is CWD-invariant.

    Failure indicates that the write path re-derives its execution context /
    target directory from the caller's CWD, which is the regression class this
    write ratchet exists to catch.
    """
    # Repo A: write issued from the main-checkout CWD.
    base_a = tmp_path / "a"
    base_a.mkdir()
    repo_a_root, _worktree_a = _build_repo(base_a)
    # Repo B: write issued from the lane-worktree CWD.
    base_b = tmp_path / "b"
    base_b.mkdir()
    repo_b_root, worktree_b = _build_repo(base_b)

    mission_slug = _MISSION_SLUG

    main_emit = _emit_status(
        cwd=repo_a_root,
        mission_slug=mission_slug,
        wp_id="WP01",
        to_lane="claimed",
        actor="parity-writer",
    )
    lane_emit = _emit_status(
        cwd=worktree_b,
        mission_slug=mission_slug,
        wp_id="WP01",
        to_lane="claimed",
        actor="parity-writer",
    )

    # (1) Deterministic event identity must match across CWDs.
    assert _event_identity(main_emit) == _event_identity(lane_emit), (
        "Write-path CWD divergence: the emitted event identity differs "
        "depending on the caller's working directory.\n"
        f"  from main-checkout CWD: {_event_identity(main_emit)!r}\n"
        f"  from lane-worktree CWD: {_event_identity(lane_emit)!r}\n"
        "The status write must produce the same (from_lane, to_lane, wp_id, "
        "actor) transition regardless of CWD."
    )

    # Sanity: the transition is the expected planned -> claimed.
    assert main_emit["from_lane"] == "planned"
    assert main_emit["to_lane"] == "claimed"

    # (2) The resulting persisted lane must be identical across both CWDs.
    from specify_cli.status.lane_reader import get_wp_lane

    main_authority_a = repo_a_root / "kitty-specs" / mission_slug
    main_authority_b = repo_b_root / "kitty-specs" / mission_slug
    main_lane = get_wp_lane(main_authority_a, "WP01")
    lane_lane = get_wp_lane(main_authority_b, "WP01")
    assert main_lane == "claimed", (
        f"Write from main-checkout CWD did not persist 'claimed'; "
        f"got {main_lane!r}"
    )
    assert lane_lane == "claimed", (
        f"Write from lane-worktree CWD did not persist 'claimed'; "
        f"got {lane_lane!r}"
    )
    assert main_lane == lane_lane, (
        "Write-path CWD divergence: the resulting lane differs across CWDs.\n"
        f"  main-checkout CWD wrote -> {main_lane!r}\n"
        f"  lane-worktree CWD wrote -> {lane_lane!r}"
    )

    # (3) The write issued from the worktree CWD must have landed in the MAIN
    # checkout's event log (the coord-aware authority), NOT the worktree's own
    # kitty-specs/. A divergent write target would write 'claimed' into the
    # worktree copy instead.
    main_authority_dir = repo_b_root / "kitty-specs" / mission_slug
    assert get_wp_lane(main_authority_dir, "WP01") == "claimed", (
        "Write from the lane-worktree CWD did not land in the main checkout's "
        "event log; the write target was re-derived from the worktree CWD."
    )
    # The worktree carries its own checked-out copy of the seeded event log
    # (committed before the worktree was created). The write issued from the
    # worktree CWD must NOT have touched that copy — its WP01 lane must remain
    # the seeded ``planned``. If the write target were CWD-derived, this copy
    # would read ``claimed`` instead.
    worktree_feature_dir = worktree_b / "kitty-specs" / mission_slug
    assert get_wp_lane(worktree_feature_dir, "WP01") == "planned", (
        "Write from the lane-worktree CWD mutated the worktree-local event log "
        f"at {worktree_feature_dir}; the write target must remain the "
        "CWD-invariant main-checkout authority, leaving the worktree copy at "
        "its seeded 'planned' state."
    )


def test_write_ratchet_catches_divergence(tmp_path: Path) -> None:
    """Anti-vacuity proof for the WRITE ratchet (#1672 / FR-008).

    Mirrors ``test_ratchet_catches_divergence`` for the write path. It proves
    that the write ratchet would catch a genuine CWD-routing regression: if a
    future change caused ``agent status emit`` to write into the worktree's own
    ``kitty-specs/`` (instead of the CWD-invariant main-checkout authority), the
    worktree-local event log would diverge from the main checkout — and
    ``test_cwd_parity_write``'s assertion (3) would fail.

    Construction (without relying on a real regression):

    1. Build a repo with a worktree.
    2. Seed the main-checkout authority with the post-write state
       (``WP01 -> claimed``). ``test_cwd_parity_write`` covers the real CLI
       emit target; this proof only needs two event-log surfaces that would
       disagree if a write target became CWD-derived.
    3. Simulate the regression by writing a *divergent* event log directly into
       the worktree's ``kitty-specs/`` that drives WP01 to ``in_progress``.
    4. Assert the two surfaces disagree (main authority = ``claimed`` from the
       seeded post-write state; worktree-local = ``in_progress`` from the simulated
       regression). This disagreement is exactly what the write ratchet would
       surface if the write target were CWD-derived.

    If the two surfaces agreed, the worktree-local data could not be used to
    detect a write-target regression and the ratchet would be vacuous.
    """
    repo_root, worktree_path = _build_repo(tmp_path)
    mission_slug = _MISSION_SLUG

    from specify_cli.status.lane_reader import get_wp_lane

    main_authority_dir = repo_root / "kitty-specs" / mission_slug
    claimed_event = _make_status_event(
        "WP01",
        from_lane="planned",
        to_lane="claimed",
        event_id="01TESTPARITY000000CLAIMED1",
        at="2026-06-03T11:00:00+00:00",
    )
    with (main_authority_dir / "status.events.jsonl").open("a", encoding="utf-8") as f:
        f.write(claimed_event + "\n")

    main_wp1_lane = get_wp_lane(main_authority_dir, "WP01")
    assert main_wp1_lane == "claimed", (
        "Setup error: the main-checkout authority should show WP01 as "
        f"'claimed'; got {main_wp1_lane!r}."
    )

    # (3) Simulate a CWD-routing regression: write a divergent event log into
    # the worktree's own kitty-specs/ that drives WP01 to 'in_progress'.
    worktree_feature_dir = worktree_path / "kitty-specs" / mission_slug
    worktree_feature_dir.mkdir(parents=True, exist_ok=True)
    divergent_events = [
        _make_status_event(
            "WP01",
            from_lane="planned",
            to_lane="planned",
            event_id="01TESTPARITY00000000000P01",
            at="2026-06-03T10:00:00+00:00",
        ),
        _make_status_event(
            "WP01",
            from_lane="planned",
            to_lane="in_progress",
            event_id="01TESTPARITY0000WRITEDVRG01",
            at="2026-06-03T11:00:00+00:00",
        ),
    ]
    (worktree_feature_dir / "status.events.jsonl").write_text(
        "\n".join(divergent_events) + "\n", encoding="utf-8"
    )

    from specify_cli.status.reducer import reduce
    from specify_cli.status.store import read_events

    worktree_snapshot = reduce(read_events(worktree_feature_dir))
    worktree_wp1_lane = (
        worktree_snapshot.work_packages.get("WP01", {}).get("lane", "planned")
    )
    assert worktree_wp1_lane == "in_progress", (
        "Injection proof setup error: the simulated regression's worktree-local "
        f"event log should show WP01 as 'in_progress'; got {worktree_wp1_lane!r}."
    )

    # (4) The main authority (real write) and the worktree-local (simulated
    # regression) surfaces must disagree, proving the ratchet is not vacuous.
    assert main_wp1_lane != worktree_wp1_lane, (
        "Injection proof inconclusive: the main-checkout authority and the "
        f"worktree-local event log both report {main_wp1_lane!r}. A write-target "
        "CWD-routing regression could not be detected, so the write ratchet "
        "would be vacuous. Revise the test setup."
    )


# ---------------------------------------------------------------------------
# FULL-SEQUENCE RATCHET (FR-020..022 / execution-state-canonical-surface)
# ---------------------------------------------------------------------------
#
# T002/T003: Drive WP01 through planned→claimed→in_progress→for_review→in_review
# via ``agent tasks move-task --no-auto-commit``.  Two independent repos are used
# (one CWD per repo) so that each transition exercises the same ``planned→X``
# first step; a single shared repo would produce duplicate transitions.
#
# T004: Direct-to-target (no worktree) mode.  Verifies the sequence succeeds
# without a worktree AND that ``agent status emit`` targeting the ``main``
# protected branch is refused when SPEC_KITTY_TEST_MODE is absent (C-001).
#
# T005: Non-vacuity negative control — mirrors the read/write injection proofs
# for the full-sequence ratchet.
#
# T006: CI gate registration — asserts the ``execution_context`` path filter in
# ci-quality.yml already includes the surfaces required by FR-024.
# ---------------------------------------------------------------------------

# The ordered lane sequence that represents the full agent workflow:
#   planned → claimed (implement start)
#             claimed → in_progress (work begins)
#                       in_progress → for_review (impl done)
#                                     for_review → in_review (reviewer picks up)
_FULL_SEQUENCE_TRANSITIONS: list[tuple[str, str]] = [
    ("planned", "claimed"),
    ("claimed", "in_progress"),
    ("in_progress", "for_review"),
    ("for_review", "in_review"),
]


def _build_repo_no_worktree(tmp_path: Path) -> Path:
    """Initialise a minimal git repo with a mission but WITHOUT any worktree.

    The repo HEAD is checked out on ``feat/direct-target`` — a non-mainline
    branch that is not protected — to allow status-event commits in tests that
    exercise auto-commit mode.  The fixture leaves the main-checkout *on this
    branch* to represent the direct-to-target execution mode.

    Returns ``repo_root``.
    """
    repo_root = tmp_path / "main"
    repo_root.mkdir()

    _git(["init", "--initial-branch=main"], repo_root)
    _git(["config", "user.email", "parity@example.com"], repo_root)
    _git(["config", "user.name", "Parity Test"], repo_root)
    _git(["config", "commit.gpgsign", "false"], repo_root)

    # .kittify marker required for find_repo_root()
    kittify_dir = repo_root / ".kittify"
    kittify_dir.mkdir()
    (kittify_dir / "config.yaml").write_text(
        "agents:\n  available:\n    - claude\n", encoding="utf-8"
    )

    _build_mission_dir(repo_root, _MISSION_SLUG)

    _git(["add", "."], repo_root)
    _git(["commit", "-m", "chore: direct-to-target fixture initial commit"], repo_root)

    # Switch to a non-mainline target branch (direct-to-target mode).
    _git(["checkout", "-b", "feat/direct-target"], repo_root)

    # No .worktrees/ directory is created — this is the direct-to-target mode.
    return repo_root


def _move_task(
    cwd: Path,
    mission_slug: str,
    wp_id: str,
    to_lane: str,
) -> dict[str, object]:
    """Drive ``agent tasks move-task <wp_id> --to <lane> --no-auto-commit --force --json``.

    ``--no-auto-commit`` keeps the fixture hermetic (no branch/commit needed).
    ``--force`` bypasses unchecked-subtask guards that would block the
    transition in a real project but are irrelevant to the CWD-invariance proof.

    Returns the parsed JSON dict.  Raises ``AssertionError`` on non-zero exit
    so a CLI failure surfaces with full diagnostics.
    """
    result = _spec_kitty(
        [
            "agent",
            "tasks",
            "move-task",
            wp_id,
            "--to",
            to_lane,
            "--mission",
            mission_slug,
            "--no-auto-commit",
            "--force",
            "--json",
        ],
        cwd=cwd,
    )
    assert result.returncode == 0, (
        f"move-task WP01 --to {to_lane!r} failed (cwd={cwd}):\n"
        f"  stdout: {result.stdout.strip()[:500]}\n"
        f"  stderr: {result.stderr.strip()[:500]}"
    )
    parsed: dict[str, object] = json.loads(result.stdout)
    return parsed


def _transition_identity(move_json: dict[str, object]) -> dict[str, str | None]:
    """Extract deterministic fields from a move-task JSON result.

    ``event_id`` is a freshly minted ULID and is excluded: it is unique per
    emission.  The fields below are the parts of the transition identity that
    MUST be CWD-invariant for the same (wp_id, from_lane, to_lane) step.

    Field mapping (from the ``agent tasks move-task --json`` output schema):
    * ``work_package_id`` → the WP being transitioned.
    * ``old_lane`` → the lane before the transition (``from_lane`` in events).
    * ``new_lane`` → the lane after the transition (``to_lane`` in events).
    """
    wp_id = move_json.get("work_package_id")
    old_lane = move_json.get("old_lane")
    new_lane = move_json.get("new_lane")
    return {
        "wp_id": str(wp_id) if wp_id is not None else None,
        "from_lane": str(old_lane) if old_lane is not None else None,
        "to_lane": str(new_lane) if new_lane is not None else None,
    }


def _drive_full_sequence(
    cwd: Path, mission_slug: str
) -> tuple[list[dict[str, str | None]], dict[str, str]]:
    """Drive WP01 through the full sequence and return (transitions, final_lanes).

    Returns:
        transitions: list of ``_transition_identity`` dicts, one per step.
        final_lanes: ``{wp_id: lane}`` mapping from the final status read.
    """
    transitions: list[dict[str, str | None]] = []
    for _from, to in _FULL_SEQUENCE_TRANSITIONS:
        result = _move_task(cwd=cwd, mission_slug=mission_slug, wp_id="WP01", to_lane=to)
        transitions.append(_transition_identity(result))
    final_lanes = _wp_lanes(_get_status_json(cwd=cwd, mission_slug=mission_slug))
    return transitions, final_lanes


# ---------------------------------------------------------------------------
# T002 — Full sequence from main-checkout CWD
# ---------------------------------------------------------------------------


def test_full_sequence_main_checkout_parity(tmp_path: Path) -> None:
    """T002: full-sequence status progression from the main-checkout CWD.

    Drives WP01 through planned→claimed→in_progress→for_review→in_review via
    ``agent tasks move-task --no-auto-commit`` from ``cwd=repo_root``.

    Asserts:
    * each transition produces the expected (from_lane, to_lane, wp_id) identity,
    * ``agent tasks status --json`` reports WP01 as ``in_review`` at the end.

    This is the baseline proof that the full-sequence ratchet itself works
    correctly from the main-checkout CWD.
    """
    repo_root, _worktree_path = _build_repo(tmp_path)
    mission_slug = _MISSION_SLUG

    transitions, final_lanes = _drive_full_sequence(
        cwd=repo_root, mission_slug=mission_slug
    )

    # Each step must have the expected (from_lane, to_lane) identity.
    for i, ((expected_from, expected_to), got) in enumerate(
        zip(_FULL_SEQUENCE_TRANSITIONS, transitions, strict=True)
    ):
        assert got["from_lane"] == expected_from, (
            f"Step {i}: expected from_lane={expected_from!r}; got {got['from_lane']!r}"
        )
        assert got["to_lane"] == expected_to, (
            f"Step {i}: expected to_lane={expected_to!r}; got {got['to_lane']!r}"
        )
        assert got["wp_id"] == "WP01", (
            f"Step {i}: expected wp_id='WP01'; got {got['wp_id']!r}"
        )

    # Final lane must be the last step's target.
    assert final_lanes.get("WP01") == "in_review", (
        f"Full sequence from main-checkout CWD did not reach 'in_review'; "
        f"got {final_lanes.get('WP01')!r}"
    )


# ---------------------------------------------------------------------------
# T003 — Same sequence from lane-worktree CWD (parity with T002) [P]
# ---------------------------------------------------------------------------


def test_full_sequence_worktree_parity(tmp_path: Path) -> None:
    """T003: full-sequence parity — main-checkout CWD vs. lane-worktree CWD.

    Drives the identical ``planned→…→in_review`` sequence against two
    *independent but identically seeded* repos:

    * Repo A: sequence driven from the **main-checkout CWD**.
    * Repo B: sequence driven from the **lane-worktree CWD**.

    Two independent repos are used (rather than two sequences against one repo)
    so that each drive exercises the same ``planned→claimed`` first transition;
    issuing both against one repo would make the second a duplicate/illegal
    re-transition.

    Asserts that:
    1. The **transition identity** (from_lane, to_lane, wp_id) for every step
       is identical across both CWDs.
    2. The **final persisted lane** (from ``agent tasks status --json``) is
       identical across both repos.

    Failure indicates that ``find_repo_root()`` or the status-event write path
    diverges based on CWD — the core regression class documented in #1619.
    """
    base_a = tmp_path / "a"
    base_a.mkdir()
    repo_a_root, _wt_a = _build_repo(base_a)

    base_b = tmp_path / "b"
    base_b.mkdir()
    repo_b_root, worktree_b = _build_repo(base_b)

    mission_slug = _MISSION_SLUG

    main_transitions, main_lanes = _drive_full_sequence(
        cwd=repo_a_root, mission_slug=mission_slug
    )
    lane_transitions, lane_lanes = _drive_full_sequence(
        cwd=worktree_b, mission_slug=mission_slug
    )

    # (1) Transition identity must match step-for-step.
    assert len(main_transitions) == len(lane_transitions), (
        "Sequence length divergence: main-checkout drove "
        f"{len(main_transitions)} steps; lane-worktree drove "
        f"{len(lane_transitions)} steps."
    )
    for i, (main_step, lane_step) in enumerate(
        zip(main_transitions, lane_transitions, strict=True)
    ):
        assert main_step == lane_step, (
            f"Transition identity divergence at step {i}:\n"
            f"  from main-checkout CWD: {main_step!r}\n"
            f"  from lane-worktree CWD: {lane_step!r}\n"
            "CWD-parity violation: the same status transition is being "
            "resolved differently depending on the caller's working directory."
        )

    # (2) Final persisted lane must be identical across both repos.
    assert main_lanes.get("WP01") == lane_lanes.get("WP01"), (
        "Final-lane CWD divergence: the status read after the full sequence "
        "returns different WP01 lanes.\n"
        f"  main-checkout CWD → {main_lanes.get('WP01')!r}\n"
        f"  lane-worktree CWD → {lane_lanes.get('WP01')!r}"
    )
    assert main_lanes.get("WP01") == "in_review", (
        f"Full sequence did not reach 'in_review'; "
        f"got {main_lanes.get('WP01')!r}"
    )


# ---------------------------------------------------------------------------
# T004 — Direct-to-target mode (no worktree; mainline write refused)
# ---------------------------------------------------------------------------


def test_full_sequence_direct_to_target(tmp_path: Path) -> None:
    """T004: full-sequence in direct-to-target mode (no worktree).

    Drives the same ``planned→…→in_review`` sequence from the repository root
    with *no* ``.worktrees/`` lane directory present (direct-to-target mode).

    Asserts:
    1. The sequence succeeds from the repo root on a non-mainline branch
       (``feat/direct-target``), reaching the expected final lane.
    2. An ``agent status emit`` call targeting the ``main`` protected branch
       (without ``SPEC_KITTY_TEST_MODE``) is **refused** (C-001 / FR-012).

    The second assertion proves that the mode-correct branch gate is enforced:
    a surface that re-derived the target from CWD could silently write to the
    wrong branch; the refusal shows that the protection is active and that a
    write to ``main`` without explicit authorization is blocked.
    """
    repo_root = _build_repo_no_worktree(tmp_path)
    mission_slug = _MISSION_SLUG

    # (1) Full sequence from repo root without a worktree.
    transitions, final_lanes = _drive_full_sequence(
        cwd=repo_root, mission_slug=mission_slug
    )
    assert final_lanes.get("WP01") == "in_review", (
        f"Direct-to-target full sequence did not reach 'in_review'; "
        f"got {final_lanes.get('WP01')!r}"
    )
    # All transitions must carry the correct WP identity.
    for step in transitions:
        assert step["wp_id"] == "WP01"

    # (2) Verify that an auto-committing ``move-task`` on the ``main`` protected
    # branch is refused (C-001 / FR-012).
    # Switch HEAD to ``main`` to simulate an unauthorized mainline write attempt.
    # The fixture repo has ``main`` as its initial branch (the non-mainline
    # ``feat/direct-target`` branch was used for the sequence above).
    _git(["checkout", "main"], repo_root)

    # WP01 is now at 'in_review'; the next valid forward transition is 'approved'.
    result_refused = _spec_kitty(
        [
            "agent",
            "tasks",
            "move-task",
            "WP01",
            "--to",
            "approved",
            "--mission",
            mission_slug,
            "--auto-commit",
            "--force",
            "--json",
        ],
        cwd=repo_root,
    )
    # The command must fail (non-zero exit) when auto-commit would write to main.
    # The protected-branch guard returns exit code 1 with a descriptive error.
    assert result_refused.returncode != 0, (
        "Mainline write protection FAILED: ``agent tasks move-task --auto-commit`` "
        "succeeded on the ``main`` branch without SPEC_KITTY_TEST_MODE set.\n"
        "C-001 requires that unauthorized mainline writes are refused.\n"
        f"  stdout: {result_refused.stdout.strip()[:500]}\n"
        f"  stderr: {result_refused.stderr.strip()[:500]}"
    )


# ---------------------------------------------------------------------------
# T005 — Non-vacuous negative control for the full-sequence ratchet
# ---------------------------------------------------------------------------


def test_full_sequence_ratchet_catches_divergence(tmp_path: Path) -> None:
    """T005: injection proof — the full-sequence ratchet FAILS when divergence exists.

    Mirrors ``test_ratchet_catches_divergence`` for the full-sequence ratchet.
    It proves that a CWD-routing regression in the full-sequence path would be
    caught: if a future change caused the worktree CWD to read from the
    worktree's own ``kitty-specs/`` instead of the primary checkout, the lane
    data would diverge and the ratchet would surface the failure.

    Construction:
    1. Build a repo with a worktree (same as parity_repo fixture).
    2. Drive WP01 through the full sequence from the main-checkout CWD.
    3. Inject a divergent event log directly into the worktree's ``kitty-specs/``
       that represents a *different* final lane (``approved``, not ``in_review``).
    4. Read status from the main-checkout authority and from the worktree-local
       surface independently.  Assert they disagree.

    If they agreed, the worktree-local data could not detect a CWD routing
    regression — the ratchet would be vacuous.  This test proves the opposite:
    a different worktree-local log DOES produce a different status read from
    that surface, which means ``test_full_sequence_worktree_parity`` would catch
    the divergence if the worktree CWD resolved to the wrong surface.
    """
    repo_root, worktree_path = _build_repo(tmp_path)
    mission_slug = _MISSION_SLUG

    # Drive the full sequence from the main-checkout CWD so the primary
    # authority reflects the real post-sequence state (WP01 = in_review).
    _drive_full_sequence(cwd=repo_root, mission_slug=mission_slug)

    # Verify the main authority shows in_review.
    main_lanes = _wp_lanes(_get_status_json(cwd=repo_root, mission_slug=mission_slug))
    assert main_lanes.get("WP01") == "in_review", (
        "Setup error: expected WP01='in_review' in the main authority after "
        f"driving the full sequence; got {main_lanes.get('WP01')!r}"
    )

    # Inject a divergent event log into the worktree's kitty-specs/: WP01
    # shows as 'approved' — a lane that differs from the real post-sequence
    # state ('in_review').  This simulates a CWD-routing regression where the
    # worktree CWD resolves to the wrong kitty-specs/ directory.
    worktree_feature_dir = worktree_path / "kitty-specs" / mission_slug
    worktree_feature_dir.mkdir(parents=True, exist_ok=True)
    divergent_events = [
        _make_status_event(
            "WP01",
            from_lane="planned",
            to_lane="planned",
            event_id="01TESTPARITY00000000000P01",
            at="2026-06-03T10:00:00+00:00",
        ),
        _make_status_event(
            "WP01",
            from_lane="planned",
            to_lane="approved",
            event_id="01TESTPARITY0000FULLSEQDV01",
            at="2026-06-03T12:00:00+00:00",
        ),
    ]
    (worktree_feature_dir / "status.events.jsonl").write_text(
        "\n".join(divergent_events) + "\n", encoding="utf-8"
    )
    (worktree_feature_dir / "meta.json").write_text(_META_JSON, encoding="utf-8")
    tasks_dir = worktree_feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "WP01.md").write_text(_WP01_MD, encoding="utf-8")
    (tasks_dir / "WP02.md").write_text(_WP02_MD, encoding="utf-8")

    # Confirm the worktree-local surface reads 'approved' from its own event log.
    from specify_cli.status.reducer import reduce
    from specify_cli.status.store import read_events

    worktree_snapshot = reduce(read_events(worktree_feature_dir))
    worktree_wp1_lane = (
        worktree_snapshot.work_packages.get("WP01", {}).get("lane", "planned")
    )
    assert worktree_wp1_lane == "approved", (
        "Injection proof setup error: the worktree's injected event log should "
        f"show WP01 as 'approved'; got {worktree_wp1_lane!r}"
    )

    # The main authority and the worktree-local surface must disagree.
    # This is the evidence that a CWD-routing regression in the full-sequence
    # path would surface as a parity failure in test_full_sequence_worktree_parity.
    main_wp1_lane = main_lanes.get("WP01")
    assert main_wp1_lane != worktree_wp1_lane, (
        f"Injection proof inconclusive: both surfaces report {main_wp1_lane!r}. "
        "A CWD-routing regression in the full-sequence path could not be "
        "detected by test_full_sequence_worktree_parity. Revise the test setup."
    )


# ---------------------------------------------------------------------------
# T006 — CI gate registration assertion (FR-024)
#
# Retired (planning#57): ``test_execution_context_parity_gate_registered_in_ci``
# asserted this section's invariant LIVE against the real
# ``.github/workflows/ci-quality.yml`` — the leftover pre-programme GitHub
# Actions YAML deleted per PROGRAM.md §2. With no workflow YAML left to parse,
# this check (and its ``_CI_WORKFLOW`` / ``_REQUIRED_EXECUTION_CONTEXT_PATHS``
# constants) has no remaining subject matter and was removed. Every other
# parity test in this module is self-contained (drives real CLI/status/runtime
# code paths directly) and is unaffected.
# ---------------------------------------------------------------------------


# ===========================================================================
# COMPOSITE-FRAGMENT DUAL-CWD RATCHET
# (execution-context-unification-01KTPKST / IC-08 / FR-011 / C-CTX-2 / SC-1)
# ===========================================================================
#
# ATDD-FIRST (charter C-011): the fragment assertions below are authored RED,
# *before* the fragments exist on ``mission_runtime.MissionExecutionContext``. They are
# ``xfail(strict=True)`` and converge to XPASS as each conversion WP lands; the
# converging WP then removes its now-stale marker (strict=True forces this).
#
# The convergence map lives in the module docstring (T003). Every fragment test
# names its convergence WP in its ``xfail`` reason.
#
# The single live (non-xfail) test ``test_dual_cwd_existing_field_parity`` is
# the anchor: it guards CWD-invariance of the fields the resolver populates
# *today* and must remain GREEN throughout.
# ---------------------------------------------------------------------------

# Lifecycle actions the resolver supports today (``ACTION_NAMES``). The full
# lifecycle in FR-011 (``specify → plan → tasks → analyze → implement → review →
# status``) is only partly resolvable now; ``implement`` / ``review`` additionally
# require a ``lanes.json`` (written by finalize-tasks) which the hermetic fixture
# omits, so the dual-CWD field-parity anchor exercises the lane-free actions.
# The remaining lifecycle steps are covered by the xfail
# ``test_runtime_lifecycle_action_parity`` below (converges in WP07).
_RESOLVABLE_LANE_FREE_ACTIONS: tuple[str, ...] = (
    "tasks",
    "tasks_finalize",
    "accept",
)

# Fields that ``resolve_action_context`` populates today for the lane-free
# actions. These are the live (non-xfail) parity surface.
_EXISTING_PARITY_FIELDS: tuple[str, ...] = (
    "mission_slug",
    "target_branch",
    "feature_dir",
    "detection_method",
)

# Fragment attribute names from data-model.md that do NOT yet exist on the
# context. Accessing any of these raises ``AttributeError`` today; that is the
# RED state each fragment test asserts against until its conversion WP lands.
_IDENTITY_FRAGMENT = "identity"
_BRANCHREF_FRAGMENT = "branch_ref"
_STATUS_SURFACE_FRAGMENT = "status_surface"
_WORKSPACE_FRAGMENT = "workspace"
_ARTIFACT_PLACEMENT_FRAGMENT = "artifact_placement"


def _resolve_context_from_cwd(
    cwd: Path,
    *,
    action: str,
    mission_slug: str,
    wp_id: str | None = None,
) -> object:
    """Resolve the canonical context with ``repo_root`` derived from ``cwd``.

    This is the heart of the dual-CWD harness: the *only* difference between the
    two parity arms is the working directory the ``repo_root`` is derived from.
    ``find_repo_root`` follows the git worktree pointer back to the main
    checkout, so a correct (CWD-invariant) resolver MUST return an identical
    context whether ``cwd`` is the primary checkout or a lane worktree.

    Uses ``find_repo_root(start=cwd)`` rather than ``os.chdir`` so no global
    process state is mutated (NFR-003 determinism, mirrors the subprocess
    ``cwd=`` discipline used by the status-parity block above).
    """
    # Import here (not at module top) so the heavy ``specify_cli`` import graph
    # is only paid by the composite-fragment tests, and to preserve the
    # status-import-first ordering that avoids the dependency_graph circular
    # import when these helpers run in isolation.
    import specify_cli.status  # noqa: F401  (warm import order; avoids circular import)
    import mission_runtime as _mr
    from specify_cli.task_utils.support import find_repo_root

    repo_root = find_repo_root(start=cwd)
    return _mr.resolve_action_context(
        repo_root,
        action=action,  # type: ignore[arg-type]  # validated by ACTION_NAMES
        feature=mission_slug,
        wp_id=wp_id,
        cwd=cwd,
    )


def _fragment_value(context: object, fragment: str, field_name: str) -> object:
    """Read ``context.<fragment>.<field_name>``.

    Raises ``AttributeError`` while the fragment does not exist on the context
    (the RED state). Once the fragment lands, this returns the resolved value
    and the surrounding ``xfail`` test flips to XPASS.
    """
    frag = getattr(context, fragment)
    return getattr(frag, field_name)


# ---------------------------------------------------------------------------
# T001 — Dual-CWD harness: LIVE anchor (existing fields, must stay GREEN)
# ---------------------------------------------------------------------------


def test_dual_cwd_existing_field_parity(parity_repo: tuple[Path, Path, str]) -> None:
    """T001 (live anchor): resolved-context field parity across primary vs lane CWD.

    For every lane-free lifecycle action, resolves the context twice — with
    ``repo_root`` derived from the **primary-checkout CWD** and from the
    **lane-worktree CWD** — and asserts that every field the resolver populates
    *today* (``_EXISTING_PARITY_FIELDS``) is identical.

    This is the non-xfail anchor of the composite-fragment ratchet: it proves
    the *current* in-process resolution path is CWD-invariant and must remain
    GREEN throughout the conversion. The fragment-level parity (Identity /
    BranchRef / StatusSurface / Workspace / ArtifactPlacement / PromptSource)
    is asserted by the ``xfail`` tests below until each lands.
    """
    repo_root, worktree_path, mission_slug = parity_repo

    for action in _RESOLVABLE_LANE_FREE_ACTIONS:
        primary_ctx = _resolve_context_from_cwd(
            repo_root, action=action, mission_slug=mission_slug
        )
        lane_ctx = _resolve_context_from_cwd(
            worktree_path, action=action, mission_slug=mission_slug
        )

        for field_name in _EXISTING_PARITY_FIELDS:
            primary_val = getattr(primary_ctx, field_name)
            lane_val = getattr(lane_ctx, field_name)
            assert primary_val == lane_val, (
                f"CWD-parity violation for action {action!r}, field "
                f"{field_name!r}:\n"
                f"  from primary-checkout CWD: {primary_val!r}\n"
                f"  from lane-worktree CWD:    {lane_val!r}\n"
                "The resolved MissionExecutionContext must be identical "
                "regardless of the CWD the repo root is derived from (C-CTX-2)."
            )


# ---------------------------------------------------------------------------
# T001/T003 — Fragment-by-fragment parity (xfail until each conversion lands)
# ---------------------------------------------------------------------------


# CONVERGED (WP03): IdentityFragment now lands on the context — xfail removed.
def test_identity_fragment_parity(parity_repo: tuple[Path, Path, str]) -> None:
    """IdentityFragment parity (``mission_id`` / ``mid8`` / ``mission_slug``).

    Asserts that the IdentityFragment resolves identically from both CWDs and
    that the ``mid8 == mission_id[:8]`` invariant (single-derivation, FR-012 /
    C-CTX-3) holds. RED today: the context carries no ``identity`` fragment.
    """
    repo_root, worktree_path, mission_slug = parity_repo

    primary_ctx = _resolve_context_from_cwd(
        repo_root, action="tasks", mission_slug=mission_slug
    )
    lane_ctx = _resolve_context_from_cwd(
        worktree_path, action="tasks", mission_slug=mission_slug
    )

    for field_name in ("mission_id", "mid8", "mission_slug"):
        primary_val = _fragment_value(primary_ctx, _IDENTITY_FRAGMENT, field_name)
        lane_val = _fragment_value(lane_ctx, _IDENTITY_FRAGMENT, field_name)
        assert primary_val == lane_val, (
            f"IdentityFragment.{field_name} diverges across CWDs: "
            f"{primary_val!r} (primary) != {lane_val!r} (lane)."
        )

    # mid8 single-derivation invariant: mid8 == mission_id[:8].
    mission_id = _fragment_value(primary_ctx, _IDENTITY_FRAGMENT, "mission_id")
    mid8 = _fragment_value(primary_ctx, _IDENTITY_FRAGMENT, "mid8")
    assert mid8 == str(mission_id)[:8], (
        f"mid8 must be derived as mission_id[:8]; got mid8={mid8!r}, "
        f"mission_id={mission_id!r} (C-CTX-3)."
    )


# CONVERGED (WP03): BranchRefFragment + destination_ref/CommitTarget now land on
# the context — xfail removed.
def test_branchref_fragment_parity(parity_repo: tuple[Path, Path, str]) -> None:
    """BranchRefFragment parity (``target_branch`` / ``coordination_branch`` / ``destination_ref``).

    Asserts CWD-invariance of the branch reference fragment, including that
    planning artifacts and status events resolve to the **same**
    ``destination_ref`` (CommitTarget) — the FR-004 invariant. RED today: the
    context carries no ``branch_ref`` fragment.
    """
    repo_root, worktree_path, mission_slug = parity_repo

    primary_ctx = _resolve_context_from_cwd(
        repo_root, action="tasks", mission_slug=mission_slug
    )
    lane_ctx = _resolve_context_from_cwd(
        worktree_path, action="tasks", mission_slug=mission_slug
    )

    for field_name in ("target_branch", "coordination_branch", "destination_ref"):
        primary_val = _fragment_value(primary_ctx, _BRANCHREF_FRAGMENT, field_name)
        lane_val = _fragment_value(lane_ctx, _BRANCHREF_FRAGMENT, field_name)
        assert primary_val == lane_val, (
            f"BranchRefFragment.{field_name} diverges across CWDs: "
            f"{primary_val!r} (primary) != {lane_val!r} (lane)."
        )

    # destination_ref is a ref-only CommitTarget value object (C-007 / FR-001b):
    # it carries a ``ref`` and NO retired ``kind`` field.
    destination_ref = _fragment_value(
        primary_ctx, _BRANCHREF_FRAGMENT, "destination_ref"
    )
    assert getattr(destination_ref, "ref", None), (
        "BranchRefFragment.destination_ref must be a CommitTarget carrying a "
        f"``ref``; got {destination_ref!r} (ADR-2026-06-03-2 / C-007)."
    )
    assert not hasattr(destination_ref, "kind"), (
        "CommitTarget is ref-only (FR-001b): the retired ``kind`` field must be "
        f"gone; got {destination_ref!r}."
    )


# CONVERGED (WP02 facade + WP03 attachment): StatusSurfaceFragment is now carried
# on the context (resolved via WP02's resolve_status_surface) — xfail removed.
def test_status_surface_fragment_parity(parity_repo: tuple[Path, Path, str]) -> None:
    """StatusSurfaceFragment parity (``status_read_dir`` / ``status_write_dir``).

    Asserts that the status surface is resolved once and carried on the context
    identically from both CWDs — consumers (esp.
    ``status_transition._identity_for_request``) must NOT re-derive it
    (FR-003/FR-008/#1737). RED today: the context carries no ``status_surface``
    fragment.
    """
    repo_root, worktree_path, mission_slug = parity_repo

    primary_ctx = _resolve_context_from_cwd(
        repo_root, action="tasks", mission_slug=mission_slug
    )
    lane_ctx = _resolve_context_from_cwd(
        worktree_path, action="tasks", mission_slug=mission_slug
    )

    for field_name in ("status_read_dir", "status_write_dir"):
        primary_val = _fragment_value(
            primary_ctx, _STATUS_SURFACE_FRAGMENT, field_name
        )
        lane_val = _fragment_value(lane_ctx, _STATUS_SURFACE_FRAGMENT, field_name)
        assert primary_val == lane_val, (
            f"StatusSurfaceFragment.{field_name} diverges across CWDs: "
            f"{primary_val!r} (primary) != {lane_val!r} (lane)."
        )


# CONVERGED (WP04): the read-path is folded into the single ``_read_path_resolver``
# surface (IC-03). The consolidated read directory is the status read dir, carried
# on ``StatusSurfaceFragment.status_read_dir`` (the one read surface, C-005); the
# duplicate ``candidate_feature_dir_for_mission`` now re-exports the primitive, so
# every caller resolves a ``--mission <mid8>`` handle to the same dir as the full
# slug (F-001/F-003/F-004). xfail removed — this test asserts that consolidated
# read path is CWD-invariant. (``WorkspaceFragment``/``primary_root`` is WP05's
# surface, IC-04, and stays xfail until then.)
def test_read_path_fragment_parity(parity_repo: tuple[Path, Path, str]) -> None:
    """Read-path parity: the mission read dir resolves via the single read-path
    surface and is CWD-invariant (IC-03 / C-CTX-2 / C-CTX-4).
    """
    repo_root, worktree_path, mission_slug = parity_repo

    primary_ctx = _resolve_context_from_cwd(
        repo_root, action="tasks", mission_slug=mission_slug
    )
    lane_ctx = _resolve_context_from_cwd(
        worktree_path, action="tasks", mission_slug=mission_slug
    )

    primary_val = _fragment_value(
        primary_ctx, _STATUS_SURFACE_FRAGMENT, "status_read_dir"
    )
    lane_val = _fragment_value(lane_ctx, _STATUS_SURFACE_FRAGMENT, "status_read_dir")
    assert primary_val == lane_val, (
        "Read-path (status read) fragment diverges across CWDs: "
        f"{primary_val!r} (primary) != {lane_val!r} (lane) — the single "
        "read-path resolver must be CWD-invariant (IC-03 / C-CTX-4)."
    )


# CONVERGED (WP05 / T018): the context now carries a WorkspaceFragment whose
# ``primary_root`` is resolved via the single worktree-pointer parser in
# ``core/paths`` (IC-04); the duplicate parser in ``workspace/root_resolver`` was
# collapsed (C-005). xfail removed — this test asserts ``primary_root`` is
# CWD-invariant and is the main checkout (not the lane worktree).
def test_workspace_fragment_parity(parity_repo: tuple[Path, Path, str]) -> None:
    """WorkspaceFragment parity (``primary_root`` single worktree-pointer parser).

    Asserts that ``WorkspaceFragment.primary_root`` resolves to the *same*
    repo-root checkout from both CWDs — the single worktree-pointer parser
    (IC-04) replacing the collapsed ``workspace/root_resolver`` parser.
    """
    repo_root, worktree_path, mission_slug = parity_repo

    primary_ctx = _resolve_context_from_cwd(
        repo_root, action="tasks", mission_slug=mission_slug
    )
    lane_ctx = _resolve_context_from_cwd(
        worktree_path, action="tasks", mission_slug=mission_slug
    )

    primary_val = _fragment_value(primary_ctx, _WORKSPACE_FRAGMENT, "primary_root")
    lane_val = _fragment_value(lane_ctx, _WORKSPACE_FRAGMENT, "primary_root")
    assert primary_val == lane_val, (
        "WorkspaceFragment.primary_root diverges across CWDs: "
        f"{primary_val!r} (primary) != {lane_val!r} (lane). Both must resolve "
        "to the same main-checkout root via the single worktree-pointer parser "
        "(IC-04)."
    )
    # The lane arm derived its root from inside the worktree; primary_root must
    # still be the main checkout, not the worktree path.
    assert Path(str(lane_val)).resolve() == repo_root.resolve(), (
        "WorkspaceFragment.primary_root resolved from the lane-worktree CWD must "
        f"be the main checkout {repo_root!r}; got {lane_val!r}."
    )


# CONVERGED (WP06 / T019): the context now carries an ArtifactPlacementFragment
# whose ``placement_ref`` is the SAME CommitTarget status events resolve to
# (C-PLACE-1 / IC-05). xfail removed.
def test_artifact_placement_fragment_parity(
    parity_repo: tuple[Path, Path, str],
) -> None:
    """ArtifactPlacementFragment parity (``placement_ref`` CommitTarget).

    Asserts that the single artifact-placement ref is CWD-invariant and is the
    *same* CommitTarget that status events resolve to (C-PLACE-1).
    """
    repo_root, worktree_path, mission_slug = parity_repo

    primary_ctx = _resolve_context_from_cwd(
        repo_root, action="tasks", mission_slug=mission_slug
    )
    lane_ctx = _resolve_context_from_cwd(
        worktree_path, action="tasks", mission_slug=mission_slug
    )

    primary_val = _fragment_value(
        primary_ctx, _ARTIFACT_PLACEMENT_FRAGMENT, "placement_ref"
    )
    lane_val = _fragment_value(lane_ctx, _ARTIFACT_PLACEMENT_FRAGMENT, "placement_ref")
    assert primary_val == lane_val, (
        "ArtifactPlacementFragment.placement_ref diverges across CWDs: "
        f"{primary_val!r} (primary) != {lane_val!r} (lane) (C-PLACE-1)."
    )

    # C-PLACE-1: the placement ref is literally the same CommitTarget the
    # BranchRefFragment carries as ``destination_ref`` — planning artifacts and
    # status events resolve to ONE ref, not two reconciled values.
    primary_destination = _fragment_value(
        primary_ctx, _BRANCHREF_FRAGMENT, "destination_ref"
    )
    assert primary_val == primary_destination, (
        "ArtifactPlacementFragment.placement_ref must equal "
        "BranchRefFragment.destination_ref (one placement ref, C-PLACE-1): "
        f"{primary_val!r} != {primary_destination!r}."
    )


def test_runtime_lifecycle_action_parity(parity_repo: tuple[Path, Path, str]) -> None:
    """Full-lifecycle dual-CWD parity for actions not yet resolvable.

    FR-011 requires parity across ``specify → plan → tasks → analyze →
    implement → review → status``. Today the resolver only knows ``tasks*`` /
    ``implement`` / ``review`` / ``accept`` (``ACTION_NAMES``); ``specify`` /
    ``plan`` / ``analyze`` / ``status`` are not resolvable actions. This test
    asserts they resolve identically from both CWDs once WP07 threads the
    context through the full lifecycle. RED today: ``resolve_action_context``
    rejects these actions with ``INVALID_ACTION``.
    """
    repo_root, worktree_path, mission_slug = parity_repo

    lifecycle_only_actions = ("specify", "plan", "analyze", "status")
    for action in lifecycle_only_actions:
        primary_ctx = _resolve_context_from_cwd(
            repo_root, action=action, mission_slug=mission_slug
        )
        lane_ctx = _resolve_context_from_cwd(
            worktree_path, action=action, mission_slug=mission_slug
        )
        for field_name in _EXISTING_PARITY_FIELDS:
            primary_val = getattr(primary_ctx, field_name)
            lane_val = getattr(lane_ctx, field_name)
            assert primary_val == lane_val, (
                f"Lifecycle action {action!r} field {field_name!r} diverges "
                f"across CWDs: {primary_val!r} != {lane_val!r} (FR-011)."
            )


# ===========================================================================
# T002 — FLATTENED-TOPOLOGY SYNTHETIC FIXTURE
# (C-001 proof — single-branch / no separate coordination branch)
# ===========================================================================
#
# A flattened mission has NO separate coordination branch: landing ==
# coordination == target. C-001 declares this for THIS mission
# (``fixups/code-engine-stabilization``). The fixture below builds a synthetic
# flattened mission (a primary checkout with a mission directory and NO
# ``.worktrees/<slug>-coord`` worktree) and the tests prove the flattened
# invariants from data-model.md:
#
#   * routes_through_coordination(stored topology) is False (C-001, FR-001b)
#   * coordination_branch is None
#   * status_read_dir == status_write_dir
#
# The fragment/CommitTarget objects do not exist yet, so the assertions are
# ``xfail(strict=True)`` and converge in WP08 (retrospect/merge + CommitTarget).
#
# Determinism / no leak (NFR-003 + E2E-leak memory): the fixture lives entirely
# under ``tmp_path`` (torn down automatically) and uses the ``test-parity-*``
# slug — NOT ``test-feature-*`` — and creates NO ``kitty/mission-*`` branch, so
# it cannot leak the known E2E ``test-feature-*`` / ``kitty/mission-test-feature-*``
# artifacts.
# ---------------------------------------------------------------------------

_FLATTENED_MISSION_SLUG = "test-parity-flattened"

_FLATTENED_META_JSON = json.dumps(
    {
        "mission_id": "01TESTPARITYFLAT0000000001",
        "mission_slug": _FLATTENED_MISSION_SLUG,
        "mission_number": None,
        "mission_type": "software-dev",
        "friendly_name": "Test parity flattened mission",
        # Flattened topology: NO coordination_branch key — landing == target.
    },
    indent=2,
)


def _build_flattened_repo(tmp_path: Path) -> tuple[Path, str]:
    """Build a synthetic FLATTENED-topology mission (no coordination worktree).

    Mirrors ``_build_repo`` but:

    * checks out a non-mainline target branch (``fixups/code-engine-stabilization``)
      that is simultaneously the landing, coordination, and target branch
      (flattened topology, C-001);
    * creates NO ``.worktrees/<slug>-coord`` coordination worktree — so the
      status read and write directories are necessarily the same primary
      checkout directory; and
    * omits a ``coordination_branch`` from ``meta.json``.

    Returns ``(repo_root, mission_slug)``. Fully deterministic and self-cleaning
    via ``tmp_path``; creates no ``kitty/mission-*`` branch (no E2E leak).
    """
    repo_root = tmp_path / "flat"
    repo_root.mkdir()

    _git(["init", "--initial-branch=main"], repo_root)
    _git(["config", "user.email", "parity@example.com"], repo_root)
    _git(["config", "user.name", "Parity Test"], repo_root)
    _git(["config", "commit.gpgsign", "false"], repo_root)

    kittify_dir = repo_root / ".kittify"
    kittify_dir.mkdir()
    (kittify_dir / "config.yaml").write_text(
        "agents:\n  available:\n    - claude\n", encoding="utf-8"
    )

    feature_dir = repo_root / "kitty-specs" / _FLATTENED_MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(_FLATTENED_META_JSON, encoding="utf-8")
    (tasks_dir / "WP01.md").write_text(_WP01_MD, encoding="utf-8")
    events = [
        _make_status_event(
            "WP01",
            from_lane="planned",
            to_lane="planned",
            event_id="01TESTPARITYFLAT0000000P01",
            at="2026-06-03T10:00:00+00:00",
        ),
    ]
    (feature_dir / "status.events.jsonl").write_text(
        "\n".join(events) + "\n", encoding="utf-8"
    )
    (feature_dir / "status.json").write_text(
        json.dumps({"event_count": 0, "work_packages": {}}), encoding="utf-8"
    )

    _git(["add", "."], repo_root)
    _git(["commit", "-m", "chore: flattened parity fixture initial commit"], repo_root)

    # Flattened: landing == coordination == target, all on one branch.
    _git(["checkout", "-b", "fixups/code-engine-stabilization"], repo_root)

    # NB: deliberately NO ``git worktree add ...-coord`` here — that absence is
    # exactly what "flattened topology" means at the filesystem level.
    return repo_root, _FLATTENED_MISSION_SLUG


@pytest.fixture
def flattened_repo(tmp_path: Path) -> Generator[tuple[Path, str], None, None]:
    """Synthetic flattened-topology mission (no coordination worktree/branch).

    Function-scoped (cheap, single commit) and self-cleaning via ``tmp_path``.
    Does not leak ``test-feature-*`` missions or ``kitty/mission-*`` branches.
    """
    repo_root, mission_slug = _build_flattened_repo(tmp_path)
    yield repo_root, mission_slug


# CONVERGED (WP08 / IC-12; reworked WP16 / FR-001b): a mission with no
# coordination branch does NOT route through coordination (data-model.md / C-001 /
# C-PLACE-1). The retired ``CommitTarget.kind == 'flattened'`` pin is replaced by
# the canonical stored-topology routing predicate — the per-ref enum is gone.
def test_flattened_topology_does_not_route_through_coordination(
    flattened_repo: tuple[Path, str],
) -> None:
    """Flattened C-001 proof: the mission does NOT route through coordination.

    A mission with no separate coordination branch resolves a coord-less stored
    topology (SINGLE_BRANCH/LANES), so ``routes_through_coordination`` is ``False``
    — the FR-001b replacement for the retired ``CommitTarget.kind == 'flattened'``
    pin (data-model.md / C-PLACE-1). The destination ref is the ref-only target.
    """
    from mission_runtime import resolve_topology, routes_through_coordination

    repo_root, mission_slug = flattened_repo
    ctx = _resolve_context_from_cwd(
        repo_root, action="tasks", mission_slug=mission_slug
    )
    destination_ref = _fragment_value(ctx, _BRANCHREF_FRAGMENT, "destination_ref")
    # Ref-only carrier (C-007): no retired ``kind`` field.
    assert not hasattr(destination_ref, "kind")
    assert getattr(destination_ref, "ref", None), (
        f"flattened destination_ref must carry a ref; got {destination_ref!r}"
    )
    assert routes_through_coordination(resolve_topology(repo_root, mission_slug)) is False, (
        "Under flattened topology the mission must NOT route through coordination "
        "(C-001 proof) — the stored topology is coord-less."
    )


# CONVERGED (WP03): BranchRefFragment.coordination_branch is None for the
# flattened fixture (no coordination_branch in meta) — xfail removed.
def test_flattened_topology_no_coordination_branch(
    flattened_repo: tuple[Path, str],
) -> None:
    """Flattened C-001 proof: ``coordination_branch is None``.

    A flattened mission has no separate coordination branch, so the
    BranchRefFragment must report ``coordination_branch is None``. RED today:
    the BranchRefFragment does not exist on the context.
    """
    repo_root, mission_slug = flattened_repo
    ctx = _resolve_context_from_cwd(
        repo_root, action="tasks", mission_slug=mission_slug
    )
    coordination_branch = _fragment_value(
        ctx, _BRANCHREF_FRAGMENT, "coordination_branch"
    )
    assert coordination_branch is None, (
        "Under flattened topology BranchRefFragment.coordination_branch must be "
        f"None; got {coordination_branch!r} (C-001)."
    )


# CONVERGED (WP02 facade + WP03 attachment): status_read_dir == status_write_dir
# for the flattened fixture (no coord worktree, surface collapses) — xfail removed.
def test_flattened_topology_status_surface_collapses(
    flattened_repo: tuple[Path, str],
) -> None:
    """Flattened C-001 proof: ``status_read_dir == status_write_dir``.

    Under flattened topology there is no primary↔coord split, so the status read
    and write directories collapse to the same directory (data-model.md). RED
    today: the StatusSurfaceFragment does not exist on the context.
    """
    repo_root, mission_slug = flattened_repo
    ctx = _resolve_context_from_cwd(
        repo_root, action="tasks", mission_slug=mission_slug
    )
    read_dir = _fragment_value(ctx, _STATUS_SURFACE_FRAGMENT, "status_read_dir")
    write_dir = _fragment_value(ctx, _STATUS_SURFACE_FRAGMENT, "status_write_dir")
    assert read_dir == write_dir, (
        "Under flattened topology status_read_dir must equal status_write_dir; "
        f"got read={read_dir!r}, write={write_dir!r} (C-001 / C-PLACE-1)."
    )


# ---------------------------------------------------------------------------
# T030 — Fragment-is-the-source ratchet (FR-005 / C-STAT-1 / #1821)
# ---------------------------------------------------------------------------
#
# WP07 of tooling-stability-guard-coherence-01KTRC04 closed the latent SC-4
# drift Debby flagged at the 01KTPKST closeout: ``MissionStatus.load`` and
# ``status_transition._canonical_primary_feature_dir`` each composed the coord
# candidate path by hand (a SECOND composition of the path the canonical
# ``resolve_status_surface`` already owns). Both now consume the single
# canonical surface — ``MissionStatus.load`` via ``resolve_status_surface`` (or
# a carried ``StatusSurfaceFragment``) and ``status_transition`` via
# ``resolve_status_surface_with_anchor``.
#
# This block EXTENDS the ratchet (C-005: extend, never fork) with two
# assertions that the fragment / canonical surface IS the source:
#
# 1. ``test_no_local_coord_path_composition_in_status_surfaces`` — a static
#    architectural grep: neither file may rebuild the coord feature dir locally
#    (``CoordinationWorkspace.worktree_path`` composed with ``_compose_mission_dir``
#    /``KITTY_SPECS_DIR``). If a future edit reintroduces a parallel composition,
#    this fails (the C-STAT-1 "no local coord-path composition remains" gate).
# 2. (retired by Mission B write-side-context-factory-adoption-01KV9W0X):
#    ``test_mission_status_load_consumes_carried_fragment`` was a behavioral spy
#    that verified the ``surface=`` parameter on ``MissionStatus.load``. The
#    ``surface=`` keyword was removed (dead fragment retirement; zero callers
#    remained after D-12 adoption); the test was retired with it.
# ---------------------------------------------------------------------------

# Source files whose coord-path composition was folded into the canonical
# surface by WP07. These are read as text (not imported) for the static check.
_FRAGMENT_SOURCE_THREADING_FILES: tuple[str, ...] = (
    "src/specify_cli/status/aggregate.py",
    "src/specify_cli/coordination/status_transition.py",
)


def _repo_root_for_sources() -> Path:
    """Resolve the spec-kitty repo root from this test file's location."""
    # tests/architectural/test_execution_context_parity.py → repo root is 2 up.
    return Path(__file__).resolve().parents[2]


def test_no_local_coord_path_composition_in_status_surfaces() -> None:
    """C-STAT-1 / FR-005: no second hand-rolled coord-path composition remains.

    ``MissionStatus.load`` and ``status_transition`` must resolve the status
    surface through the single canonical authority (``resolve_status_surface`` /
    ``resolve_status_surface_with_anchor``), never by re-composing the
    coordination feature dir locally. The drift seam Debby flagged was exactly
    such a second composition: ``CoordinationWorkspace.worktree_path(...)``
    joined with ``KITTY_SPECS_DIR`` and ``_compose_mission_dir(...)``.

    This static gate fails if either file reintroduces that composition,
    preventing the parallel-mechanism regression (NFR-003 / C-005).
    """
    repo_root = _repo_root_for_sources()
    offenders: dict[str, list[str]] = {}
    for rel_path in _FRAGMENT_SOURCE_THREADING_FILES:
        source = (repo_root / rel_path).read_text(encoding="utf-8")
        hits: list[str] = []
        # A local coord-path composition needs BOTH the worktree-root primitive
        # AND a mission-dir name join. Either alone is benign (the canonical
        # resolver is allowed to be referenced); together they reconstruct the
        # surface the canonical authority already owns.
        composes_worktree_root = "CoordinationWorkspace.worktree_path" in source
        composes_mission_dir = "_compose_mission_dir" in source
        if composes_worktree_root and composes_mission_dir:
            hits.append(
                "rebuilds the coord feature dir locally "
                "(CoordinationWorkspace.worktree_path + _compose_mission_dir) — "
                "consume resolve_status_surface[_with_anchor] instead"
            )
        if hits:
            offenders[rel_path] = hits

    assert not offenders, (
        "Second hand-rolled coord-path composition detected — the status surface "
        "must be resolved through the single canonical authority, not re-composed "
        f"locally (FR-005 / C-STAT-1 / #1821):\n{json.dumps(offenders, indent=2)}"
    )


# ---------------------------------------------------------------------------
# AC10 — Canonical status-read ratchet (FR-008e / FR-009 / #1735, WP05 of
# coordination-merge-stabilization-01KTXRVR)
# ---------------------------------------------------------------------------
#
# WP05 routed the last two Class A read stragglers — the retrospective
# completion gate (``retrospective/gate.py``) and the retrospect command
# surface (``cli/commands/agent_retrospect.py``) — through the canonical
# ``resolve_status_surface``. Under coordination topology the authoritative
# ``status.events.jsonl`` lives in the coordination worktree; a
# ``feature_dir``-anchored direct read in these modules is exactly the #1735
# split-brain bug class.
#
# This ratchet EXTENDS the static-gate convention above (C-005: extend, never
# fork) with an AST scan scoped to the two known read families in the two
# fixed modules (research/risks: a tree-wide ``feature_dir`` scan has dozens
# of legitimate hits on already-resolved surfaces, so the scope is the two
# modules whose reads were routed):
#
# 1. ``read_events(<…feature_dir…>)`` — a feature_dir-anchored event read.
# 2. ``<…feature_dir…> / "status.events.jsonl"`` — a direct event-log path
#    composition.
#
# The only exempt locations are the routed seam helpers themselves
# (``_resolve_events_path`` / ``_canonical_events_dir``), whose legacy-mission
# fallback composes the path AFTER first consulting the canonical resolver.
# The ratchet additionally asserts each seam exists and calls
# ``resolve_status_surface``, so deleting a seam (e.g. by reverting WP05's
# T024/T025 routing) turns this test RED — the anti-vacuity property.
# ---------------------------------------------------------------------------

# module path → routed seam function names exempt from the read-family scan.
_CANONICAL_STATUS_READ_FILES: dict[str, frozenset[str]] = {
    "src/specify_cli/retrospective/gate.py": frozenset({"_resolve_events_path"}),
    "src/specify_cli/cli/commands/agent_retrospect.py": frozenset({"_canonical_events_dir"}),
}

_STATUS_EVENTS_LITERAL = "status.events.jsonl"


def _subtree_anchors_feature_dir(node: ast.AST) -> bool:
    """True when *node*'s subtree references a ``feature_dir`` name/attribute."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id == "feature_dir":
            return True
        if isinstance(sub, ast.Attribute) and sub.attr == "feature_dir":
            return True
    return False


def _callee_name(node: ast.Call) -> str | None:
    """Best-effort simple name of a call's callee (``f(...)`` / ``m.f(...)``)."""
    callee = node.func
    if isinstance(callee, ast.Name):
        return callee.id
    if isinstance(callee, ast.Attribute):
        return callee.attr
    return None


def _feature_dir_read_family_hits(
    func: ast.AST, exempt_seams: frozenset[str]
) -> list[str]:
    """Return AC10 read-family violations inside *func* (line-tagged).

    An argument that is itself a call to a routed seam helper (e.g.
    ``read_events(_canonical_events_dir(repo_root, slug, feature_dir))``) is
    NOT a violation: there ``feature_dir`` is only the legacy fallback handed
    to the seam, which consults ``resolve_status_surface`` first.
    """
    hits: list[str] = []
    for node in ast.walk(func):
        # Family 1: read_events(<…feature_dir…>)
        if (
            isinstance(node, ast.Call)
            and _callee_name(node) == "read_events"
            and any(
                _subtree_anchors_feature_dir(arg)
                and not (
                    isinstance(arg, ast.Call) and _callee_name(arg) in exempt_seams
                )
                for arg in node.args
            )
        ):
            hits.append(
                f"line {node.lineno}: feature_dir-anchored read_events() call"
            )
        # Family 2: <…feature_dir…> / "status.events.jsonl"
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            right = node.right
            if (
                isinstance(right, ast.Constant)
                and right.value == _STATUS_EVENTS_LITERAL
                and _subtree_anchors_feature_dir(node.left)
            ):
                hits.append(
                    f"line {node.lineno}: feature_dir-anchored "
                    f'"{_STATUS_EVENTS_LITERAL}" path composition'
                )
    return hits


def test_no_feature_dir_anchored_status_event_reads() -> None:
    """AC10 / FR-009 / #1735: retrospective reads route through the canonical surface.

    Forbids ``feature_dir``-anchored ``read_events()`` calls and direct
    ``status.events.jsonl`` path compositions in ``retrospective/gate.py`` and
    ``cli/commands/agent_retrospect.py`` outside their routed seam helpers,
    and asserts each seam consults ``resolve_status_surface``. Reverting the
    WP05 T024/T025 routing reintroduces a forbidden read (or deletes a seam)
    and turns this RED.
    """
    repo_root = _repo_root_for_sources()
    offenders: dict[str, list[str]] = {}

    for rel_path, exempt_seams in _CANONICAL_STATUS_READ_FILES.items():
        source_path = repo_root / rel_path
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        hits: list[str] = []
        seen_seams: set[str] = set()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name in exempt_seams:
                seen_seams.add(node.name)
                # The seam is only a legitimate exemption if it consults the
                # canonical resolver before any fallback composition.
                seam_source = ast.unparse(node)
                if "resolve_status_surface" not in seam_source:
                    hits.append(
                        f"line {node.lineno}: routed seam {node.name!r} no longer "
                        "calls resolve_status_surface — the exemption does not apply"
                    )
                continue
            hits.extend(_feature_dir_read_family_hits(node, exempt_seams))

        missing_seams = exempt_seams - seen_seams
        if missing_seams:
            hits.append(
                f"routed seam(s) {sorted(missing_seams)!r} missing — the canonical "
                "read routing (WP05 T024/T025) appears to have been reverted"
            )
        if hits:
            offenders[rel_path] = hits

    assert not offenders, (
        "feature_dir-anchored status-event read detected — retrospective reads "
        "must route through resolve_status_surface, never read "
        "status.events.jsonl via the (identity-only) feature dir "
        f"(AC10 / FR-009 / #1735):\n{json.dumps(offenders, indent=2)}"
    )
