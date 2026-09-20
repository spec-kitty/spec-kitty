"""Regression tests for #4785 Finding 2-core / Finding 3 (WP04).

``charter synthesize``'s fresh-project short-circuit used to key on the mere
*absence* of ``.kittify/charter/generated/`` -- a signal an ESTABLISHED store
(one that has been really activated and/or really synthesized before) can
also satisfy once its ``generated/`` directory is emptied or cleaned up.
Misclassifying that store as "fresh" silently discards its real state and
replaces it with the minimal built-in-only seed (Contract C2).

This file pins:

- An established store (real ``activated_*`` selection, or a real prior
  synthesis manifest) is NOT classified fresh and does NOT take the
  minimal-doctrine seed short-circuit, even with no ``generated/`` dir.
- A genuinely fresh store (freshly generated, never activated, never
  synthesized) still takes the seed path -- the "don't over-narrow fresh"
  regression net the WP prompt calls out explicitly.
- ``generate``/``synthesize`` both fail closed (Contract C3 / FR-006) when
  invoked from inside a linked git worktree, and the PRIMARY checkout's
  ``.kittify/`` is left untouched.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.regression, pytest.mark.non_sandbox, pytest.mark.git_repo]

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers (mirrors tests/integration/test_charter_synthesize_fresh.py)
# ---------------------------------------------------------------------------


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True, capture_output=True)


def _write_minimal_interview(repo: Path) -> None:
    interview_dir = repo / ".kittify" / "charter" / "interview"
    interview_dir.mkdir(parents=True, exist_ok=True)
    (interview_dir / "answers.yaml").write_text(
        "mission: software-dev\n"
        "profile: minimal\n"
        "selected_paradigms: []\n"
        "selected_directives: []\n"
        "available_tools: []\n"
        "answers:\n"
        "  purpose: Test charter for the #4785 fresh-gate regression suite.\n",
        encoding="utf-8",
    )


def _run_generate(project: Path) -> object:
    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        return runner.invoke(charter_app, ["generate", "--from-interview"], catch_exceptions=False)
    finally:
        os.chdir(old_cwd)


def _run_synthesize(project: Path, *args: str) -> object:
    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        return runner.invoke(charter_app, ["synthesize", *args], catch_exceptions=False)
    finally:
        os.chdir(old_cwd)


def _assert_no_generated_dir(project: Path) -> None:
    generated_dir = project / ".kittify" / "charter" / "generated"
    if generated_dir.exists():
        for sub in ("directives", "tactics", "styleguides"):
            sub_dir = generated_dir / sub
            if sub_dir.exists():
                assert not list(sub_dir.glob("*.yaml")), f"Test pre-condition violated: agent YAMLs already present in {sub_dir}"


# ---------------------------------------------------------------------------
# T017/T018 -- established store (real activated_*) must NOT take the
# fresh-project branch.
# ---------------------------------------------------------------------------


def test_synthesize_established_store_via_activated_directives_does_not_seed(tmp_path: Path) -> None:
    """A store with a real, non-empty ``activated_directives`` selection is
    established -- ``synthesize`` must not report "fresh project" or
    short-circuit to the minimal-doctrine seed, even though
    ``.kittify/charter/generated/`` is still absent.
    """
    from charter.activation.charter_yaml_io import update_charter_yaml_section

    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)
    _run_generate(tmp_path)

    charter_yaml = tmp_path / ".kittify" / "charter" / "charter.yaml"
    assert charter_yaml.is_file(), "test pre-condition: charter generate must have produced charter.yaml"

    # Canonical writer (charter_yaml_io.update_charter_yaml_section) -- the
    # ONLY writer path `activate`/`deactivate`/`compile_charter` use (INV-9).
    # Simulates the real state `charter activate` would leave without
    # depending on the built-in doctrine corpus's exact id vocabulary.
    update_charter_yaml_section(charter_yaml, "activation", {"activated_directives": ["PROJECT_PROBE_DIRECTIVE"]})

    _assert_no_generated_dir(tmp_path)
    doctrine_dir = tmp_path / ".kittify" / "doctrine"
    assert not doctrine_dir.exists(), "test pre-condition: no doctrine tree yet"

    result = _run_synthesize(tmp_path, "--json")

    combined = (result.stdout or "") + (getattr(result, "output", "") or "")
    assert "fresh project" not in combined.lower(), f"established store (non-empty activated_directives) was misclassified as fresh: {combined!r}"
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        payload = None
    if payload is not None:
        assert payload.get("mode") not in {"fresh_project_seed", "fresh_project_seed_dry_run"}, f"established store took the fresh-project seed mode: {payload!r}"
    # The fresh-seed short-circuit is the ONLY thing that materializes
    # .kittify/doctrine/ on a store with no generated/ dir and no registered
    # direct-write project artifacts -- it must not have fired.
    assert not doctrine_dir.exists(), "established store must not have the minimal-doctrine seed materialized"


# ---------------------------------------------------------------------------
# T017/T018 -- established store (real PRIOR synthesis) must NOT take the
# fresh-project branch, and must NOT re-seed.
# ---------------------------------------------------------------------------


def test_synthesize_established_store_via_real_manifest_does_not_reseed(tmp_path: Path) -> None:
    """A store whose ``synthesis-manifest.yaml`` already records a REAL
    (``built_in_only: false``) synthesis is established -- a later
    ``synthesize`` with ``generated/`` absent must not clobber it back down
    to the ``built_in_only: true`` seed marker (the exact #4785 repro: a
    real store loses its ``generated/`` dir and gets silently reset).
    """
    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)
    _run_generate(tmp_path)

    manifest_path = tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    real_manifest_text = (
        "schema_version: '3'\n"
        "mission_id: null\n"
        "created_at: '2026-01-01T00:00:00+00:00'\n"
        "run_id: 01JTESTRUNIDXXXXXXXXXXXXXX\n"
        "adapter_id: generated\n"
        "adapter_version: '0.0.0'\n"
        "synthesizer_version: '0.0.0'\n"
        "manifest_hash: " + ("a" * 64) + "\n"
        "artifacts: []\n"
        "built_in_only: false\n"
    )
    manifest_path.write_text(real_manifest_text, encoding="utf-8")

    _assert_no_generated_dir(tmp_path)

    result = _run_synthesize(tmp_path, "--json")

    combined = (result.stdout or "") + (getattr(result, "output", "") or "")
    assert "fresh project" not in combined.lower(), f"established store (real built_in_only: false manifest) was misclassified as fresh: {combined!r}"
    # The manifest must not have been silently overwritten by the fresh-seed
    # template (which always stamps built_in_only: true).
    assert "built_in_only: false" in manifest_path.read_text(encoding="utf-8"), (
        "established store's real synthesis manifest was clobbered by the fresh-project seed"
    )


# ---------------------------------------------------------------------------
# Regression net -- a genuinely fresh store (never activated, never
# synthesized) must still seed. "Don't over-narrow fresh."
# ---------------------------------------------------------------------------


def test_synthesize_truly_fresh_store_still_seeds(tmp_path: Path) -> None:
    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)
    _run_generate(tmp_path)

    doctrine_dir = tmp_path / ".kittify" / "doctrine"
    assert not doctrine_dir.exists(), "test pre-condition: no doctrine tree yet"
    _assert_no_generated_dir(tmp_path)

    result = _run_synthesize(tmp_path, "--json")

    assert result.exit_code == 0, f"synthesize failed on a truly fresh store: {result.stdout!r}"
    payload = json.loads(result.stdout)
    assert payload.get("mode") == "fresh_project_seed", (
        f"a truly fresh store (no compiled catalog, never activated) must still take the minimal-doctrine seed path: {payload!r}"
    )
    assert doctrine_dir.is_dir()
    assert (doctrine_dir / "PROVENANCE.md").is_file()


# ---------------------------------------------------------------------------
# T019 -- worktree-safe write root for generate/synthesize (Contract C3 /
# FR-006 / NFR-004).
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_with_worktree(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("freshgate_repo_wt")
    subprocess.run(["git", "init", "--quiet", str(root)], check=True, capture_output=True)
    for key, val in (("user.email", "t@e.com"), ("user.name", "T")):
        subprocess.run(["git", "-C", str(root), "config", key, val], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "config", "commit.gpgsign", "false"], check=True, capture_output=True)
    (root / "README.md").write_text("seed\n")
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "seed", "--quiet"], check=True, capture_output=True)
    worktree = root.parent / (root.name + "-lane-b")
    subprocess.run(
        ["git", "-C", str(root), "worktree", "add", "-B", "lane-b", str(worktree)],
        check=True,
        capture_output=True,
    )
    from kernel.git_topology import clear_caches

    clear_caches()
    return root, worktree


def test_generate_from_linked_worktree_fails_closed(repo_with_worktree: tuple[Path, Path]) -> None:
    main_root, worktree = repo_with_worktree

    old_cwd = os.getcwd()
    try:
        os.chdir(worktree)
        result = runner.invoke(charter_app, ["generate", "--from-interview"], catch_exceptions=False)
    finally:
        os.chdir(old_cwd)

    assert result.exit_code != 0, f"generate must fail closed from a linked worktree; got: {result.stdout!r}"
    combined = (result.stdout or "") + (getattr(result, "output", "") or "")
    assert "repository-root checkout or dedicated clone" in combined, combined
    # No charter write must have landed in the PRIMARY checkout either.
    assert not (main_root / ".kittify" / "charter" / "charter.yaml").exists()


def test_synthesize_from_linked_worktree_fails_closed(repo_with_worktree: tuple[Path, Path]) -> None:
    main_root, worktree = repo_with_worktree

    old_cwd = os.getcwd()
    try:
        os.chdir(worktree)
        result = runner.invoke(charter_app, ["synthesize", "--json"], catch_exceptions=False)
    finally:
        os.chdir(old_cwd)

    assert result.exit_code != 0, f"synthesize must fail closed from a linked worktree; got: {result.stdout!r}"
    combined = (result.stdout or "") + (getattr(result, "output", "") or "")
    assert "repository-root checkout or dedicated clone" in combined, combined
    # No charter write must have landed in the PRIMARY checkout either.
    assert not (main_root / ".kittify").exists()
