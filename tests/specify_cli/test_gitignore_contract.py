"""Integration tests: gitignore policy stays aligned with the state contract."""

import subprocess
from pathlib import Path

import pytest
# The tests and helpers shared with this suite's always-on lift live once, in
# ``tests/architectural/_lifted_root_gitignore_contract.py`` (#5015); importing a test is what makes pytest collect it here.
from tests.architectural._lifted_root_gitignore_contract import test_repo_gitignore_covers_local_runtime as test_repo_gitignore_covers_local_runtime
from tests.architectural._lifted_root_gitignore_contract import test_runtime_entries_match_contract as test_runtime_entries_match_contract

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


def test_contract_runtime_entries_complete():
    """Contract runtime entries are non-empty and contain known patterns."""
    from specify_cli.state.contract import get_runtime_gitignore_entries

    entries = get_runtime_gitignore_entries()
    assert len(entries) >= 4, f"Expected at least 4 runtime entries, got {len(entries)}"  # noqa: PLR2004
    assert ".kittify/merge-state.json" in entries
    assert ".kittify/encoding-provenance/" in entries
    assert ".kittify/runtime/" in entries
    assert ".kittify/events/" in entries
    assert ".kittify/dossiers/" in entries
    assert ".worktrees/" in entries  # execution-worktrees root (#3689)
    # FIX-M2-05: the FEATURE-rooted leg -- the dossier SNAPSHOT is nested
    # inside each mission's own kitty-specs/<feature>/ tree (save_snapshot()
    # writes feature_dir/.kittify/dossiers/<slug>/…), a DIFFERENT physical
    # location than dossier_parity_baseline's genuinely project-rooted
    # sibling (which is what keeps ".kittify/dossiers/" above alive).
    assert "kitty-specs/*/.kittify/dossiers/" in entries


def test_dossier_snapshot_is_feature_rooted_not_project_rooted():
    """FIX-M2-05 regression lock: dossier_snapshot must stay FEATURE-rooted.

    Root cause of the reported ``spec-kitty merge`` failure (git/ref_advance.py's
    dirty-checked-out-worktree resync, #1826): ``dossier_snapshot`` was declared
    ``root=StateRoot.PROJECT`` with a path_pattern missing the mandatory
    ``kitty-specs/<feature>/`` prefix that ``save_snapshot()``
    (``dossier/snapshot.py``) actually writes under. That made
    ``get_runtime_gitignore_entries()`` emit a root-anchored ``.kittify/dossiers/``
    pattern that never matched the real write location, so a fresh
    ``spec-kitty init`` never protected it. Pin both the root and the exact
    physical path so a regression here fails LOUD instead of silently drifting
    the gitignore generator away from reality again.
    """
    from specify_cli.state.contract import STATE_SURFACES, GitClass, StateRoot

    surface = next(s for s in STATE_SURFACES if s.name == "dossier_snapshot")
    assert surface.root == StateRoot.FEATURE
    assert surface.git_class == GitClass.IGNORED
    assert surface.path_pattern == "kitty-specs/<feature>/.kittify/dossiers/<feature>/snapshot-latest.json"

    # dossier_parity_baseline is a DIFFERENT artifact at a genuinely
    # project-rooted physical location (drift_detector.py (deleted, #274) wrote
    # repo_root/.kittify/dossiers/<slug>/parity-baseline.json) -- confirm this
    # fix did not accidentally move it too.
    baseline = next(s for s in STATE_SURFACES if s.name == "dossier_parity_baseline")
    assert baseline.root == StateRoot.PROJECT
    assert baseline.path_pattern == ".kittify/dossiers/<feature>/parity-baseline.json"


def test_gitignore_manager_protects_dossier_snapshot(tmp_path: Path) -> None:
    """FIX-M2-05: fresh init protection hides the mission-nested dossier snapshot.

    Regression test for the reported golden-path failure: a fresh
    ``spec-kitty init`` project's ``.gitignore`` must actually cover the real
    physical write location of ``save_snapshot()``
    (``<feature_dir>/.kittify/dossiers/<slug>/snapshot-latest.json``, i.e.
    NESTED inside ``kitty-specs/<mission>/``) -- not just the project-root
    ``.kittify/dossiers/`` pattern that never matched it. A sibling per-mission
    ``.kittify/config.yaml`` (a real, TRACKED file) must stay un-ignored so this
    fix does not over-broadly blanket-ignore the mission's whole ``.kittify/``.
    """
    from specify_cli.gitignore_manager import GitignoreManager

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    result = GitignoreManager(tmp_path).protect_all_agents()

    assert result.success
    assert _is_ignored(
        tmp_path,
        "kitty-specs/some-mission/.kittify/dossiers/some-mission/snapshot-latest.json",
    )
    # A second mission's snapshot is covered by the same glob (not a
    # per-mission literal that only happens to match one slug).
    assert _is_ignored(
        tmp_path,
        "kitty-specs/other-mission-01ABC/.kittify/dossiers/other-mission-01ABC/snapshot-latest.json",
    )
    assert not _is_ignored(tmp_path, "kitty-specs/some-mission/.kittify/config.yaml")


def test_gitignore_manager_protects_encoding_provenance(tmp_path: Path) -> None:
    """Fresh init protection hides the global encoding provenance log."""
    from specify_cli.gitignore_manager import GitignoreManager

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    result = GitignoreManager(tmp_path).protect_all_agents()

    assert result.success
    assert _is_ignored(tmp_path, ".kittify/encoding-provenance/global.jsonl")


def test_contract_runtime_entries_include_skill_projection_surfaces():
    """#2412: the per-machine install ledger is a runtime-ignored contract
    entry. The shared skill projection root is not a whole-root entry any
    more (#6474): a team's own skills share ``.agents/skills/``, so only Spec
    Kitty's skill folders are ignored, through the configured-agent block."""
    from specify_cli.state.contract import get_runtime_gitignore_entries

    entries = get_runtime_gitignore_entries()
    assert ".agents/skills/" not in entries
    assert not any(entry.startswith(".agents") for entry in entries)
    assert ".kittify/skills-manifest.json" in entries


def test_gitignore_manager_protects_skill_projection(tmp_path: Path) -> None:
    """Fresh init protection hides Spec Kitty's projected skills and the manifest, not a team skill."""
    from specify_cli.gitignore_manager import GitignoreManager

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    result = GitignoreManager(tmp_path).protect_all_agents(["codex"])

    assert result.success
    assert _is_ignored(tmp_path, ".agents/skills/spec-kitty-implement/SKILL.md")
    assert _is_ignored(tmp_path, ".agents/skills/spec-kitty.implement/SKILL.md")
    assert _is_ignored(tmp_path, ".kittify/skills-manifest.json")
    assert not _is_ignored(tmp_path, ".agents/skills/team-skill/SKILL.md")


def test_contract_runtime_entries_include_ops_index():
    """The Op-index performance cache is a runtime-ignored contract entry."""
    from specify_cli.state.contract import get_runtime_gitignore_entries

    entries = get_runtime_gitignore_entries()
    # File-level entry -- NOT collapsed to kitty-ops/, because the durable
    # per-Op records under kitty-ops/ are tracked.
    assert "kitty-ops/ops-index.jsonl" in entries
    assert "kitty-ops/" not in entries


def test_gitignore_manager_protects_ops_index(tmp_path: Path) -> None:
    """Fresh init protection hides the Op-index cache but not durable records."""
    from specify_cli.gitignore_manager import GitignoreManager

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    result = GitignoreManager(tmp_path).protect_all_agents()

    assert result.success
    assert _is_ignored(tmp_path, "kitty-ops/ops-index.jsonl")
    # Durable per-Op audit records stay trackable.
    assert not _is_ignored(tmp_path, "kitty-ops/01HXYZ.jsonl")


def test_research_evidence_logs_are_trackable():
    """Investigation evidence logs under research/ are not masked by *.log."""

    repo_root = Path(__file__).resolve().parents[2]

    evidence = "kitty-specs/example-mission/research/evidence.log"
    non_research = "kitty-specs/example-mission/runtime.log"
    generic = "tmp/dev.log"

    assert not _is_ignored(repo_root, evidence)
    assert _is_ignored(repo_root, non_research)
    assert _is_ignored(repo_root, generic)


def test_charter_synthesis_artifacts_are_trackable():
    """KD-2 charter synthesis artifacts must be commit-ready."""

    repo_root = Path(__file__).resolve().parents[2]

    assert not _is_ignored(repo_root, ".kittify/charter/synthesis-manifest.yaml")
    assert not _is_ignored(repo_root, ".kittify/charter/provenance/directive-demo.yaml")
    assert not _is_ignored(repo_root, ".kittify/doctrine/graph.yaml")


def _is_ignored(repo_root: Path, path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", path],
        cwd=repo_root,
        check=False,
    )
    return result.returncode == 0


def test_derived_views_dir_is_gitignored():
    """#2369: .kittify/derived/ (regenerable materialize output) must be in the
    runtime gitignore set so `spec-kitty materialize` never dirties the tree /
    fails accept's git_dirty check. Registry-driven — the derived_mission_views
    StateSurface (root=PROJECT, git_class=IGNORED) collapses to this entry."""
    from specify_cli.state.contract import get_runtime_gitignore_entries

    entries = get_runtime_gitignore_entries()
    assert ".kittify/derived/" in entries, entries


def test_gitignore_manager_protects_worktrees_root(tmp_path: Path) -> None:
    """Fresh init gitignores the execution-worktrees root (#3689).

    Historically only the <0.13.1 migration excluded ``.worktrees/`` (via the
    local-only ``.git/info/exclude``), so every project initialised since
    then showed ``?? .worktrees/`` after its first mission worktree.
    """
    from specify_cli.gitignore_manager import GitignoreManager

    manager = GitignoreManager(tmp_path)
    manager.protect_all_agents()

    content = (tmp_path / ".gitignore").read_text()
    assert ".worktrees/" in content
