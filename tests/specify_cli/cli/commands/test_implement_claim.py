"""Seam tests for ``cli/commands/implement_claim.py`` (implement-degod WP08).

Covers the pure claim-commit bundle (``claim_commit_paths``), the protected-branch refusal text,
the propagate/soften table of ``_commit_wp_claim_status`` and the error translation of
``_start_wp_implementation_status``.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer

from specify_cli.cli.commands import implement_claim
from specify_cli.cli.console import console
from specify_cli.git.commit_helpers import SafeCommitHeadMismatch, SafeCommitPathPolicyError
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.status import Lane, StatusEvent
from specify_cli.status.store import append_event, read_events
from tests._support.git_cli import git_out

# Markers are per test: the pure bundle/text seams are ``fast``; everything that runs git is
# ``git_repo`` (pytest.ini: ``fast`` means no subprocess and no git).
_FAST = pytest.mark.fast
_GIT = pytest.mark.git_repo

_SLUG = "demo-01ABCDEF"


def _bundle_inputs(tmp_path: Path, *, coord: bool) -> tuple[Path, Path, Path, list[Path]]:
    repo = tmp_path / "repo"
    primary_dir = repo / "kitty-specs" / _SLUG
    (primary_dir / "tasks").mkdir(parents=True)
    wp_file = primary_dir / "tasks" / "WP01-demo.md"
    wp_file.write_text("wp\n", encoding="utf-8")
    status_dir = (repo / ".worktrees" / f"{_SLUG}-coord" / "kitty-specs" / _SLUG) if coord else primary_dir
    status_dir.mkdir(parents=True, exist_ok=True)
    artifacts = [status_dir / "status.events.jsonl", status_dir / "status.json", status_dir / "tasks.md"]
    for artifact in artifacts:
        artifact.write_text("x\n", encoding="utf-8")
    return repo, primary_dir, wp_file, artifacts


def _write_meta_and_config(repo: Path, feature_dir: Path) -> tuple[Path, Path]:
    meta = feature_dir / "meta.json"
    meta.write_text("{}", encoding="utf-8")
    config = repo / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("x: 1\n", encoding="utf-8")
    return meta, config


@_FAST
def test_claim_commit_paths_flat_stages_wp_file_then_status_artifacts(tmp_path: Path) -> None:
    repo, feature_dir, wp_file, artifacts = _bundle_inputs(tmp_path, coord=False)

    paths = implement_claim.claim_commit_paths(repo_root=repo, feature_dir=feature_dir, wp_file=wp_file, status_artifacts=artifacts, routes_through_coord=False)

    assert paths == [wp_file.resolve(), *(a.resolve() for a in artifacts)]


@_FAST
def test_claim_commit_paths_coord_drops_worktree_nested_artifacts(tmp_path: Path) -> None:
    repo, feature_dir, wp_file, artifacts = _bundle_inputs(tmp_path, coord=True)

    paths = implement_claim.claim_commit_paths(repo_root=repo, feature_dir=feature_dir, wp_file=wp_file, status_artifacts=artifacts, routes_through_coord=True)

    assert paths == [wp_file.resolve()]


@_FAST
def test_claim_commit_paths_appends_meta_then_config_when_present(tmp_path: Path) -> None:
    """Pins today's bundle, including ``.kittify/config.yaml`` (#5673 is NOT fixed here: the claim
    never changes that file, so the future fix is a one-line removal in ``claim_commit_paths``)."""
    repo, feature_dir, wp_file, artifacts = _bundle_inputs(tmp_path, coord=False)
    meta, config = _write_meta_and_config(repo, feature_dir)

    paths = implement_claim.claim_commit_paths(repo_root=repo, feature_dir=feature_dir, wp_file=wp_file, status_artifacts=artifacts, routes_through_coord=False)

    assert paths == [wp_file.resolve(), *(a.resolve() for a in artifacts), meta.resolve(), config.resolve()]


@_FAST
def test_claim_commit_paths_leaves_config_out_when_asked(tmp_path: Path) -> None:
    """``include_config=False`` (the ``--no-auto-commit`` staging) keeps ``meta.json`` and drops only ``config.yaml``."""
    repo, feature_dir, wp_file, artifacts = _bundle_inputs(tmp_path, coord=False)
    meta, _config = _write_meta_and_config(repo, feature_dir)

    paths = implement_claim.claim_commit_paths(
        repo_root=repo, feature_dir=feature_dir, wp_file=wp_file, status_artifacts=artifacts, routes_through_coord=False, include_config=False
    )

    assert paths == [wp_file.resolve(), *(a.resolve() for a in artifacts), meta.resolve()]


@_FAST
def test_claim_commit_paths_skips_absent_meta_and_config(tmp_path: Path) -> None:
    repo, feature_dir, wp_file, _ = _bundle_inputs(tmp_path, coord=False)

    paths = implement_claim.claim_commit_paths(repo_root=repo, feature_dir=feature_dir, wp_file=wp_file, status_artifacts=[], routes_through_coord=False)

    assert paths == [wp_file.resolve()]


class _Policy:
    def __init__(self, protected: bool) -> None:
        self._protected = protected

    def is_protected(self, branch: str) -> bool:
        return self._protected


def _stub_policy(monkeypatch: pytest.MonkeyPatch, protected: bool) -> None:
    # Patch the policy class itself (owner module), not a name the command module looks up.
    monkeypatch.setattr(ProtectionPolicy, "resolve_for_mission", lambda repo_root, slug: _Policy(protected))


@_FAST
def test_protected_branch_error_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_policy(monkeypatch, True)

    assert implement_claim._protected_branch_status_commit_error("main", tmp_path, _SLUG) == (
        "Refusing to start implementation status on protected branch 'main' "
        "before mutating status files. Run this status commit from an allowed "
        "coordination/lane branch, or rerun with --no-auto-commit when you "
        "intentionally want to handle the status artifact commit manually."
    )


@_FAST
def test_unprotected_branch_has_no_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_policy(monkeypatch, False)

    assert implement_claim._protected_branch_status_commit_error("lane-a", tmp_path) is None


@_GIT
def test_raise_if_status_commit_protected_uses_the_checkout_head(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_policy(monkeypatch, True)
    git_out(tmp_path, "init", "-qb", "head-branch")

    with pytest.raises(ValueError, match="protected branch 'head-branch'"):
        implement_claim._raise_if_status_commit_protected(tmp_path, "fallback", True, _SLUG)


@_GIT
def test_raise_if_status_commit_protected_falls_back_outside_a_repository(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_policy(monkeypatch, True)

    with pytest.raises(ValueError, match="protected branch 'fallback'"):
        implement_claim._raise_if_status_commit_protected(tmp_path, "fallback", True, _SLUG)


@_FAST
def test_raise_if_status_commit_protected_is_inert_without_auto_commit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_policy(monkeypatch, True)

    assert implement_claim._raise_if_status_commit_protected(tmp_path, "main", False, _SLUG) is None


_BRANCH = "feat/claim-seam"


@pytest.fixture
def claim_repo(tmp_path: Path) -> SimpleNamespace:
    """A real flat-topology repo checked out on its own recorded target branch, so the REAL
    ``safe_commit`` accepts the claim commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git_out(repo, "init", "-qb", _BRANCH)
    git_out(repo, "config", "user.email", "test@test.com")
    git_out(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    git_out(repo, "add", "-A")
    git_out(repo, "commit", "-qm", "init")
    feature_dir = repo / "kitty-specs" / _SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    meta = {"mission_id": "01KW1P0FZZ9QABCDEF01234567", "mission_slug": _SLUG, "mid8": "01KW1P0F", "topology": "flat", "target_branch": _BRANCH}
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    wp_file = feature_dir / "tasks" / "WP01-demo.md"
    wp_file.write_text("---\nwork_package_id: WP01\n---\nbody\n", encoding="utf-8")
    (feature_dir / "status.events.jsonl").write_text('{"event":"claimed"}\n', encoding="utf-8")
    return SimpleNamespace(repo=repo, feature_dir=feature_dir, wp_file=wp_file)


def _claim(env: SimpleNamespace, *, auto_commit: bool | None = True, status_result: object | None = None) -> None:
    implement_claim._commit_wp_claim_status(
        repo_root=env.repo,
        feature_dir=env.feature_dir,
        mission_slug=_SLUG,
        wp_id="WP01",
        wp_file=env.wp_file,
        auto_commit=auto_commit,
        status_result=SimpleNamespace(status_changed=True) if status_result is None else status_result,
    )


def _head_files(repo: Path) -> set[str]:
    return set(git_out(repo, "show", "--name-only", "--format=", "HEAD").split())


@_GIT
@pytest.mark.parametrize("status_result", [None, SimpleNamespace(status_changed=False)])
def test_claim_commit_is_a_noop_without_a_lane_change(claim_repo: SimpleNamespace, status_result: object, capsys: pytest.CaptureFixture[str]) -> None:
    head_before = git_out(claim_repo.repo, "rev-parse", "HEAD")

    implement_claim._commit_wp_claim_status(
        repo_root=claim_repo.repo,
        feature_dir=claim_repo.feature_dir,
        mission_slug=_SLUG,
        wp_id="WP01",
        wp_file=claim_repo.wp_file,
        auto_commit=True,
        status_result=status_result,
    )

    assert git_out(claim_repo.repo, "rev-parse", "HEAD") == head_before
    assert capsys.readouterr().out == ""


@_GIT
def test_claim_commit_without_auto_commit_stages_the_bundle_and_commits_nothing(claim_repo: SimpleNamespace, capsys: pytest.CaptureFixture[str]) -> None:
    """#3471: ``--no-auto-commit`` stages exactly the claim's own writes and commits nothing.

    ``.kittify/config.yaml`` is present and uncommitted, yet stays unstaged: the claim never writes
    it, so the staging leaves it out (``include_config=False``), unlike the auto-commit bundle.
    Planted breaks (proven red): drop the ``git add`` in ``_stage_claim_writes``; stage with
    ``include_config=True``.
    """
    config = claim_repo.repo / ".kittify" / "config.yaml"
    config.parent.mkdir()
    config.write_text("x: 1\n", encoding="utf-8")
    head_before = git_out(claim_repo.repo, "rev-parse", "HEAD")

    _claim(claim_repo, auto_commit=False)

    assert git_out(claim_repo.repo, "rev-parse", "HEAD") == head_before
    staged = set(git_out(claim_repo.repo, "diff", "--cached", "--name-only").split())
    assert staged == {
        f"kitty-specs/{_SLUG}/meta.json",
        f"kitty-specs/{_SLUG}/tasks/WP01-demo.md",
        f"kitty-specs/{_SLUG}/status.events.jsonl",
    }
    assert ".kittify/config.yaml" not in staged
    assert "auto-commit disabled, changes staged only" in capsys.readouterr().out


@_GIT
def test_claim_commit_commits_the_bundle_on_the_target_branch(claim_repo: SimpleNamespace, capsys: pytest.CaptureFixture[str]) -> None:
    _claim(claim_repo)

    assert git_out(claim_repo.repo, "log", "-1", "--format=%s") == "chore: WP01 claimed for implementation"
    assert _head_files(claim_repo.repo) == {
        f"kitty-specs/{_SLUG}/meta.json",
        f"kitty-specs/{_SLUG}/tasks/WP01-demo.md",
        f"kitty-specs/{_SLUG}/status.events.jsonl",
    }
    assert "WP01 moved to 'doing'" in capsys.readouterr().out


@_GIT
def test_claim_commit_reraises_path_policy_error(claim_repo: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``.worktrees/``-nested artifact leaking into the primary bundle trips the real guard."""
    leaked = claim_repo.repo / ".worktrees" / "coord" / "status.json"
    leaked.parent.mkdir(parents=True)
    leaked.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("specify_cli.cli.commands.agent.tasks._collect_status_artifacts", lambda feature_dir: [leaked])

    with pytest.raises(SafeCommitPathPolicyError):
        _claim(claim_repo)


@_GIT
def test_claim_commit_reraises_head_mismatch(claim_repo: SimpleNamespace) -> None:
    git_out(claim_repo.repo, "checkout", "-qb", "feat/elsewhere")

    with pytest.raises(SafeCommitHeadMismatch):
        _claim(claim_repo)


@_GIT
def test_claim_commit_softens_any_other_failure(claim_repo: SimpleNamespace, capsys: pytest.CaptureFixture[str]) -> None:
    """Re-claiming identical content is an empty commit, which ``safe_commit`` rejects: soft warning."""
    _claim(claim_repo)
    capsys.readouterr()

    _claim(claim_repo)

    out = capsys.readouterr().out
    assert "Warning: Could not auto-commit lane change:" in out
    assert "moved to 'doing'" not in out


def _seed_lane(feature_dir: Path, lane: Lane, actor: str) -> None:
    # The fixture's placeholder log is not a valid event stream; start from a real one.
    (feature_dir / "status.events.jsonl").unlink(missing_ok=True)
    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-WP01-{lane.value}",
            mission_slug=feature_dir.name,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=lane,
            at="2026-01-01T00:00:00+00:00",
            actor=actor,
            force=True,
            execution_mode="worktree",
        ),
    )


def _start(env: SimpleNamespace, actor: str) -> object:
    return implement_claim._start_wp_implementation_status(
        feature_dir=env.feature_dir,
        mission_slug=_SLUG,
        wp_id="WP01",
        effective_actor=actor,
        workspace_path=env.repo / "ws",
        status_execution_mode="worktree",
        repo_root=env.repo,
    )


@_GIT
def test_start_status_records_the_claim(claim_repo: SimpleNamespace) -> None:
    _seed_lane(claim_repo.feature_dir, Lane.PLANNED, "test")

    result = _start(claim_repo, "alice")

    assert result is not None
    assert getattr(result, "status_changed", False) is True
    claim = [event for event in read_events(claim_repo.feature_dir) if event.actor == "alice"]
    assert [(event.from_lane, event.to_lane, event.execution_mode) for event in claim] == [
        (Lane.PLANNED, Lane.CLAIMED, "worktree"),
        (Lane.CLAIMED, Lane.IN_PROGRESS, "worktree"),
    ]
    assert claim[0].policy_metadata is not None
    assert claim[0].policy_metadata["agent"] == "alice"


@_GIT
def test_start_status_translates_a_claim_conflict(claim_repo: SimpleNamespace, capsys: pytest.CaptureFixture[str]) -> None:
    _seed_lane(claim_repo.feature_dir, Lane.PLANNED, "test")
    _start(claim_repo, "alice")
    capsys.readouterr()

    with pytest.raises(typer.Exit) as excinfo:
        _start(claim_repo, "bob")

    assert excinfo.value.exit_code == 1
    assert capsys.readouterr().out.strip() == "Error: WP WP01 is already claimed for implementation by 'alice'"


@_GIT
def test_start_status_translates_a_transition_error(claim_repo: SimpleNamespace, capsys: pytest.CaptureFixture[str]) -> None:
    _seed_lane(claim_repo.feature_dir, Lane.DONE, "test")

    with pytest.raises(typer.Exit) as excinfo:
        _start(claim_repo, "alice")

    assert excinfo.value.exit_code == 1
    assert capsys.readouterr().out.startswith("Error: Could not start implementation status: ")


@_FAST
def test_a_non_git_failure_to_gather_the_claim_bundle_is_reported_as_unstaged(tmp_path: Path) -> None:
    """N-8: with auto-commit off, a non-git failure while gathering the bundle to stage says what
    failed -- the staging -- and that the changes were left unstaged; it no longer escapes to
    ``commit_claim``'s misleading "Could not update WP status" warning.

    Planted break (proven red): gather the bundle outside the staging ``try``.
    """

    def _unreadable_bundle() -> list[Path]:
        raise OSError("status.json: permission denied")

    with console.capture() as capture:
        implement_claim._stage_claim_writes(tmp_path, "WP01", _unreadable_bundle)

    text = " ".join(capture.get().split())
    assert "Warning: Could not stage the claim's changes: status.json: permission denied" in text
    assert "→ WP01 moved to 'doing' (auto-commit disabled, changes left unstaged)" in text
    assert "Could not update WP status" not in text
