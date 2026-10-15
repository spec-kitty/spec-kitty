"""WP06 T035 — `charter synthesize` works on a fresh project (issue #839).

These integration tests lock in Spec Assumption A2: the public CLI
``spec-kitty charter synthesize`` succeeds on a fresh project (no
hand-seeded ``.kittify/charter-packs/``, no LLM-authored YAML under
``.kittify/charter/generated/``) and produces the minimal artifact set
documented in T031.
"""

from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from pathlib import Path

import pytest
from typer.testing import CliRunner

from charter.activation.synthesizer.manifest import load_yaml
from specify_cli.cli.commands.charter import app as charter_app


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_init(repo: Path) -> None:
    """Initialize a minimal git repo with identity configured."""
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=repo, check=True, capture_output=True,
    )


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
        "  purpose: Test charter for fresh-project synthesize.\n",
        encoding="utf-8",
    )


def _run_generate(project: Path) -> None:
    """Run ``charter generate`` against the project's cwd."""
    with chdir(project):
        result = runner.invoke(
            charter_app, ["generate", "--from-interview"],
            catch_exceptions=False,
        )
    assert result.exit_code == 0, (
        f"charter generate failed: {result.stdout!r}"
    )


def _run_synthesize(project: Path, *args: str) -> object:
    """Run ``charter synthesize`` with extra args, returning the Result."""
    with chdir(project):
        return runner.invoke(
            charter_app, ["synthesize", *args],
            catch_exceptions=False,
        )


# ---------------------------------------------------------------------------
# T035a — synthesize on fresh project via public CLI succeeds
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# #839 follow-up: --dry-run on a fresh project is covered by the intercept
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# T035b — synthesize is idempotent (T033)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# T035c — synthesize without charter.md fails actionably
# ---------------------------------------------------------------------------


def test_synthesize_fresh_seed_unlinks_preexisting_graph(tmp_path: Path) -> None:
    """#1717 Fix A: a fresh-seed synthesize (built_in_only) must remove a stale
    project-local ``graph.yaml`` so the freshness XOR invariant holds.

    Repro of the terminal "invalid" trap: a project carries a committed
    ``.kittify/charter-packs/graph.yaml`` from a prior synthesis era, but
    ``generated/`` is now empty so synthesize takes the fresh-seed path and
    writes a ``built_in_only: true`` manifest. If it leaves graph.yaml behind,
    ``compute_freshness`` classifies the synthesized DRG as ``invalid`` with no
    working remediation.
    """
    from specify_cli.charter_runtime.freshness import compute_freshness

    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)
    _run_generate(tmp_path)

    # Seed a stale project-local graph.yaml (the orphan residue).
    doctrine_dir = tmp_path / ".kittify" / "charter-packs"
    doctrine_dir.mkdir(parents=True, exist_ok=True)
    stale_graph = doctrine_dir / "graph.yaml"
    stale_graph.write_text("schema_version: '1.0'\nnodes: []\nedges: []\n", encoding="utf-8")

    result = _run_synthesize(tmp_path, "--json")
    assert result.exit_code == 0, f"synthesize failed: {result.stdout!r}"

    # The fresh-seed (built_in_only) path must have removed the stale graph.
    assert not stale_graph.exists(), (
        "fresh-seed synthesize left a stale graph.yaml, producing the "
        "built_in_only ∧ graph-present conflict (#1717)"
    )
    # And freshness must NOT be the terminal 'invalid' state.
    freshness = compute_freshness(tmp_path)
    assert freshness.synthesized_drg.state != "invalid", (
        f"synthesized_drg is {freshness.synthesized_drg.state!r}; "
        "fresh-seed must leave a consistent built_in_only state"
    )


def test_synthesize_preserves_registered_direct_project_artifacts(tmp_path: Path) -> None:
    """No generated inputs must not erase the registered direct-write corpus."""
    from charter.activation.project_registration import plan_project_registration, commit_project_registration
    from charter.activation.synthesizer.manifest import verify
    from specify_cli.charter_runtime.freshness.computer import compute_freshness
    from tests.charter.test_project_registration import author_guidance

    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)
    _run_generate(tmp_path)
    assert _run_synthesize(tmp_path, "--json").exit_code == 0
    sources = author_guidance(tmp_path)
    commit_project_registration(plan_project_registration(tmp_path))
    source_bytes = {path: path.read_bytes() for path in sources.values()}
    sidecars = tmp_path / ".kittify/charter/provenance"
    provenance_bytes = {path: path.read_bytes() for path in sidecars.glob("*.yaml")}
    tracked = [tmp_path / ".kittify/charter/synthesis-manifest.yaml", tmp_path / ".kittify/charter-packs/graph.yaml"]
    before_dry_run = {path: path.read_bytes() for path in tracked}
    preview = _run_synthesize(tmp_path, "--dry-run", "--json")
    assert preview.exit_code == 0, preview.stdout
    assert json.loads(preview.stdout)["planned_deletes"] == []
    assert {path: path.read_bytes() for path in tracked} == before_dry_run
    result = _run_synthesize(tmp_path, "--json")
    assert result.exit_code == 0, result.stdout
    manifest = load_yaml(tmp_path / ".kittify/charter/synthesis-manifest.yaml")
    assert sorted((a.kind, tmp_path / a.path) for a in manifest.artifacts) == sorted(sources.items())
    assert not manifest.built_in_only
    verify(manifest, tmp_path)
    assert (tmp_path / ".kittify/charter-packs/graph.yaml").is_file()
    assert {path: path.read_bytes() for path in source_bytes} == source_bytes
    assert {path: path.read_bytes() for path in provenance_bytes} == provenance_bytes
    assert "intentionally empty" not in (tmp_path / ".kittify/charter-packs/PROVENANCE.md").read_text()
    freshness = compute_freshness(tmp_path).synthesized_drg
    assert freshness.state == "fresh", freshness
    payload = json.loads(result.stdout)
    assert sorted((a["kind"], tmp_path / a["path"]) for a in payload["written_artifacts"]) == sorted(sources.items())
