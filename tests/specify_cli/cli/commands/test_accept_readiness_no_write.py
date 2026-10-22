"""Regression for #1916 (WP08): accept readiness must be side-effect-free.

Root cause: readiness paths could persist project identity while running in
no-write modes — an incomplete identity got minted and written to
``.kittify/config.yaml``, and a second readiness run tripped on a file the gate
itself wrote. The write was removed from the readiness path; these tests pin
that it stays off it.

RED precondition (squad note — without it the test is green-from-start): the
project's ``.kittify/config.yaml`` MUST carry **provably-incomplete** identity
(``build_id`` missing). ``ensure_identity`` returns early WITHOUT writing once
identity is complete, so a complete fixture never reproduces the bug.

(The sync emitter whose eager init was the original write path retired with the
sync transport, issue #5; the two emitter-level regression tests went with it.)
"""

from __future__ import annotations

import json
import subprocess
from kernel.clock import now_utc_iso
from pathlib import Path

import pytest
import typer

from specify_cli.identity.project import ensure_identity, load_identity
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]

_SLUG = "099-accept-readiness-no-write"
_MISSION_ID = "01JZZZZZZZZZZZZZZZZZZZZZZB"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"
_CONFIG_RELPATH = ".kittify/config.yaml"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True)


def _porcelain_status(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _write_incomplete_config(repo_root: Path) -> Path:
    """Write a ``.kittify/config.yaml`` with provably-incomplete project identity.

    ``project.build_id`` (required for ``ProjectIdentity.is_complete``) is omitted so
    ``ensure_identity`` would mint + persist it unless the write has been moved off the
    readiness path.
    """
    config_path = repo_root / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "project:\n"
        "  uuid: 11111111-1111-4111-8111-111111111111\n"
        "  slug: accept-readiness-no-write\n"
        "  node_id: abcdef012345\n"
        # build_id intentionally omitted → identity incomplete
        "\n"
    )
    return config_path


def test_incomplete_identity_precondition(tmp_path: Path) -> None:
    """Guard (RED precondition 1): the fixture identity MUST be incomplete."""
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    config_path = _write_incomplete_config(repo_root)

    identity = load_identity(config_path)
    assert identity.build_id is None, "fixture identity must be incomplete (build_id missing)"
    assert not identity.is_complete, "fixture identity must be incomplete to reproduce #1916"


def test_write_authorized_ensure_identity_still_persists(tmp_path: Path) -> None:
    """Positive contrast: a WRITE-authorized ``ensure_identity`` STILL persists.

    Proves the fix scoped the write off the readiness path rather than globally
    disabling identity persistence: ``ensure_identity`` at a write-authorized boundary
    continues to mint and persist a complete identity to ``.kittify/config.yaml``.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    config_path = _write_incomplete_config(repo_root)

    before = load_identity(config_path)
    assert not before.is_complete

    identity = ensure_identity(repo_root)
    assert identity.is_complete, "write-authorized ensure_identity must complete identity"

    persisted = load_identity(config_path)
    assert persisted.is_complete, "ensure_identity must PERSIST the completed identity"
    assert persisted.build_id is not None


# ── End-to-end CLI convergence (stopgap-retired) ──────────────────────────────


def _create_acceptready_feature(repo_root: Path) -> Path:
    """Clean, accept-ready lane-based mission on its mission branch."""
    from specify_cli.acceptance.matrix import (
        AcceptanceCriterion,
        AcceptanceMatrix,
        NegativeInvariant,
        write_acceptance_matrix,
    )
    from specify_cli.status.reducer import materialize

    _git(repo_root, "init", ".")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "branch", "-M", "main")

    _write_incomplete_config(repo_root)
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
        "friendly_name": "Accept Readiness No-Write",
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
        "---\n"
        "# WP01\nDone.\n"
    )

    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id="01TESTACCEPTREADINESSNOWR01",
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

    write_acceptance_matrix(
        feature_dir,
        AcceptanceMatrix(
            mission_slug=_SLUG,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="AC1",
                    description="feature behaves as specified",
                    proof_type="automated_test",
                    pass_fail="pass",
                )
            ],
            negative_invariants=[
                NegativeInvariant(
                    invariant_id="NI1",
                    description="legacy symbol must be absent",
                    verification_method="grep_absence",
                    verification_command="ZZZ_PATTERN_THAT_NEVER_MATCHES_ZZZ",
                )
            ],
        ),
    )

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "init")
    _git(repo_root, "checkout", "-b", _MISSION_BRANCH)
    return feature_dir


def _run_readiness(repo_root: Path) -> int | None:
    """Drive the real ``accept(no_commit=True)`` command path; return exit code."""
    from specify_cli.cli.commands.accept import accept

    exit_code: int | None = 0
    try:
        accept(
            mission=_SLUG,
            mode="auto",
            actor="tester",
            test=[],
            json_output=False,
            lenient=False,
            no_commit=True,
            diagnose=False,
            allow_fail=False,
        )
    except typer.Exit as exc:
        exit_code = exc.exit_code
    return exit_code


def test_accept_no_commit_converges_without_project_config_filter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two ``accept --no-commit`` runs converge with the stopgap retired.

    ``_filter_accept_owned_project_config`` is gone, so the project-root
    ``.kittify/config.yaml`` is no longer special-cased by the dirty gate.
    Convergence must hold because readiness writes nothing — not because the write
    is filtered out. The config file (incomplete identity) must stay byte-unchanged.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _create_acceptready_feature(repo_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    config_path = repo_root / _CONFIG_RELPATH
    bytes_before = config_path.read_bytes()

    _run_readiness(repo_root)
    status_after_first = _porcelain_status(repo_root)
    _run_readiness(repo_root)
    status_after_second = _porcelain_status(repo_root)

    assert config_path.read_bytes() == bytes_before, (
        "accept readiness mutated .kittify/config.yaml (identity write on readiness path)"
    )
    assert status_after_first == status_after_second, (
        "two readiness runs diverged in working-tree dirt"
    )
    dirty_paths = [
        line[3:].strip() for line in status_after_second.splitlines() if line.strip()
    ]
    assert _CONFIG_RELPATH not in dirty_paths, (
        ".kittify/config.yaml left dirty by readiness — readiness must not write it"
    )
