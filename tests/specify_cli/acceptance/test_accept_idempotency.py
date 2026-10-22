"""Accept-gate idempotency / convergence (FR-002, #1883 ROOT-β).

The accept gate snapshots ``git status --porcelain`` and refuses to proceed
when the tree is dirty. The defect: the gate's *own* derived writes
(``acceptance-matrix.json`` rewritten by negative-invariant enforcement and the
``status.json`` view materialized during readiness reads) are accept-owned
artifacts. In ``--no-commit``/``diagnose`` modes those writes are never folded
into a commit, so they stay dirty for the *next* run to trip over. The result
is a non-idempotent gate: a clean tree fails the second accept on state the
tool itself wrote.

C-GATE-2 (contracts/authority-seams.md): ``spec-kitty accept`` re-run on an
unchanged tree converges in every mode; accept-owned writes never trip the
gate's own dirty check.

NFR-003 (fail-closed): the exclusion is scoped *only* to accept-owned paths
under the mission dir. A NON-accept-owned dirty file must still trip the gate.
"""

from __future__ import annotations

import json
import subprocess
from kernel.clock import now_utc_iso
from pathlib import Path

import pytest
import typer

from specify_cli.acceptance import collect_feature_summary
from specify_cli.acceptance.matrix import (
    AcceptanceCriterion,
    AcceptanceMatrix,
    NegativeInvariant,
    write_acceptance_matrix,
)
from specify_cli.cli.commands.accept import accept
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.models import InnerStateChanged, Lane, StatusEvent, WPInnerStateDelta
from specify_cli.status.reducer import materialize
from specify_cli.status.store import append_annotations_atomic_verified
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]

_SLUG = "099-test-feature"
_MISSION_ID = "01JZZZZZZZZZZZZZZZZZZZZZZZ"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _porcelain(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _create_lane_feature(repo_root: Path, *, with_negative_invariant: bool) -> Path:
    """Create a clean, accept-ready lane-based feature on its mission branch."""
    _git(repo_root, "init", ".")
    _git(repo_root, "config", "user.email", "test@test.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "branch", "-M", "main")

    (repo_root / ".kittify").mkdir()
    for required_dir in ("src", "tests", "docs"):
        path = repo_root / required_dir
        path.mkdir()
        (path / ".gitkeep").write_text("")

    feature_dir = repo_root / "kitty-specs" / _SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    # contracts/ is a mission artifact → under the feature dir, not repo root (#2115)
    (feature_dir / "contracts").mkdir(parents=True, exist_ok=True)

    meta = {
        "mission_number": "099",
        "slug": _SLUG,
        "mission_slug": _SLUG,
        "mission_id": _MISSION_ID,
        "mid8": _MISSION_ID[:8],
        "friendly_name": "Test Feature",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00Z",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    for fname in ("spec.md", "plan.md", "tasks.md"):
        (feature_dir / fname).write_text(f"# {fname}\nDone.\n")

    (tasks_dir / "WP01-test.md").write_text(
        "---\n"
        'work_package_id: "WP01"\n'
        'title: "Test WP"\n'
        'lane: "done"\n'
        'assignee: "test-agent"\n'
        'agent: "test-agent"\n'
        'shell_pid: "12345"\n'
        "subtasks: []\n"
        "---\n"
        "# WP01\nDone.\n"
    )

    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id="01TESTACCEPTIDEMPOTENCY0001",
            mission_slug=_SLUG,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.DONE,
            at=now_utc_iso(),
            actor="test-agent",
            force=True,
            execution_mode="direct_repo",
            reason="Test setup: skip to done",
        ),
    )
    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id="01JZZZZZZZZZZZZZZZZZZZZZZY",
                wp_id="WP01",
                at=now_utc_iso(),
                actor="test-agent",
                delta=WPInnerStateDelta(agent="test-agent"),
            )
        ],
    )
    materialize(feature_dir)

    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=_SLUG,
            mission_id=_SLUG,
            mission_branch=_MISSION_BRANCH,
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/**",),
                    predicted_surfaces=("test",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-04-05T12:00:00Z",
            computed_from="test",
        ),
    )

    criteria = [
        AcceptanceCriterion(
            criterion_id="AC1",
            description="feature behaves as specified",
            proof_type="automated_test",
            pass_fail="pass",
        )
    ]
    invariants = []
    if with_negative_invariant:
        invariants = [
            NegativeInvariant(
                invariant_id="NI1",
                description="legacy symbol must be absent",
                verification_method="grep_absence",
                verification_command="ZZZ_PATTERN_THAT_NEVER_MATCHES_ZZZ",
            )
        ]
    write_acceptance_matrix(
        feature_dir,
        AcceptanceMatrix(
            mission_slug=_SLUG,
            criteria=criteria,
            negative_invariants=invariants,
        ),
    )

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "init")
    _git(repo_root, "checkout", "-b", _MISSION_BRANCH)
    return feature_dir


def _run_accept(*, no_commit: bool, diagnose: bool) -> None:
    """Invoke the top-level accept command, swallowing the success Exit(0).

    ``diagnose`` raises ``typer.Exit(0)`` on success; treat a zero exit as a
    clean pass and re-raise any non-zero exit so a tripped gate surfaces.
    """
    try:
        accept(
            mission=_SLUG,
            mode="auto",
            actor="tester",
            test=[],
            json_output=False,
            lenient=False,
            no_commit=no_commit,
            diagnose=diagnose,
            allow_fail=False,
        )
    except typer.Exit as exc:
        if exc.exit_code not in (0, None):
            raise


@pytest.mark.parametrize(
    ("no_commit", "diagnose"),
    [
        (False, False),  # committing mode
        (True, False),  # --no-commit
        (False, True),  # diagnose
    ],
    ids=["commit", "no_commit", "diagnose"],
)
def test_accept_converges_on_unchanged_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_commit: bool,
    diagnose: bool,
) -> None:
    """Running accept twice on an unchanged accepted tree converges.

    Mode matrix (T008): commit / --no-commit / diagnose. The second run must
    NOT trip on accept-owned writes left by the first run. RED on current code:
    in --no-commit/diagnose the matrix/status.json rewrites are left dirty and
    the second accept's git_dirty snapshot trips.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _create_lane_feature(repo_root, with_negative_invariant=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    # First accept run — primes accept-owned writes.
    _run_accept(no_commit=no_commit, diagnose=diagnose)

    # Second accept run on the (semantically) unchanged tree must converge:
    # collect_feature_summary must report a passing gate (no git_dirty trip on
    # accept-owned artifacts).
    summary = collect_feature_summary(
        repo_root,
        _SLUG,
        strict_metadata=True,
        mutate_matrix=not diagnose,
    )
    # The #1883 convergence property: accept-owned writes never trip the gate's
    # own dirty check on the second run, in EVERY mode.
    assert summary.git_dirty == [], (
        f"second accept tripped on accept-owned writes: {summary.git_dirty}"
    )
    if not diagnose:
        # Mutating modes resolve the negative invariant, so the full gate passes
        # on the second run. Diagnose is read-only (mutate_matrix=False): it
        # never executes the invariant, so the matrix verdict stays 'pending' by
        # design — that is not a git_dirty/convergence failure.
        assert summary.ok, f"second accept did not converge: {summary.outstanding()}"


def test_accept_still_trips_on_non_accept_owned_dirt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adversarial (reviewer-renata): the exclusion must not over-exclude.

    A NON-accept-owned dirty file (e.g. source code or a non-owned mission
    artifact) must STILL trip the dirty-tree gate. NFR-003: never weaken the
    protection for paths the accept gate does not own.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _create_lane_feature(repo_root, with_negative_invariant=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    # Dirty a tracked NON-accept-owned file.
    (repo_root / "src" / ".gitkeep").write_text("operator edit\n")

    summary = collect_feature_summary(
        repo_root,
        _SLUG,
        strict_metadata=True,
        mutate_matrix=True,
    )
    assert summary.git_dirty, "gate must trip on non-accept-owned dirty paths"
    assert any("src/.gitkeep" in line for line in summary.git_dirty)
    assert not summary.ok


def test_accept_excludes_dirty_mission_spec_artifacts_only_when_accept_owned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dirty NON-owned artifact under the mission dir still trips the gate.

    The exclusion is keyed on accept-owned *artifact identity* (the matrix and
    status view), not on "anything under the mission dir". A dirty ``spec.md``
    in the same directory must still be reported.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir = _create_lane_feature(repo_root, with_negative_invariant=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    (feature_dir / "spec.md").write_text("# spec.md\nOperator edited.\n")

    summary = collect_feature_summary(
        repo_root,
        _SLUG,
        strict_metadata=True,
        mutate_matrix=True,
    )
    assert any("spec.md" in line for line in summary.git_dirty), (
        f"dirty non-owned mission artifact was wrongly excluded: {summary.git_dirty}"
    )
    assert not summary.ok


def test_accept_still_trips_on_non_owned_kittify_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NFR-003 (post-stopgap contract): a non-owned ``.kittify/`` file still trips.

    History: PR #1908 special-cased ``.kittify/config.yaml`` out of the dirty gate
    (``_filter_accept_owned_project_config`` + ``_expand_untracked_kittify``) to
    paper over readiness *writing* the file. WP08 (#1916) removed the write from the
    readiness path, so that exclusion is RETIRED — there is no longer any
    ``.kittify/`` carve-out NOR the ``_expand_untracked_kittify`` helper that the
    carve-out needed. The standing contract is the plain one: dirt under
    ``.kittify/`` that the accept gate does not own must surface in ``git_dirty``
    and trip the gate, with no exclusion (and no expansion) helper in the path.

    git collapses a fully-untracked ``.kittify/`` tree to a single ``?? .kittify/``
    entry; with the expansion helper retired the gate reports that directory entry
    verbatim. That is the correct post-stopgap behavior — the dirt is surfaced and
    the gate trips. We assert on the ``.kittify`` path (not a specific child file,
    which only the retired expansion produced) and on ``not summary.ok``.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _create_lane_feature(repo_root, with_negative_invariant=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    # Drop a genuinely non-owned file under ``.kittify/`` (an operator note, not a
    # gate-owned artifact). With the stopgap retired there is no carve-out, so the
    # ``.kittify/`` dirt must surface and trip the dirty gate.
    (repo_root / ".kittify" / "operator-note.txt").write_text("operator edit\n")

    summary = collect_feature_summary(
        repo_root,
        _SLUG,
        strict_metadata=True,
        mutate_matrix=True,
    )
    assert any(".kittify" in line for line in summary.git_dirty), (
        f"non-owned .kittify dirt was wrongly excluded: {summary.git_dirty}"
    )
    assert not summary.ok
