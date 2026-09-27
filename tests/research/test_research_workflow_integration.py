#!/usr/bin/env python3
"""Integration tests for research mission workflows."""

from __future__ import annotations

import subprocess
import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]  # non_sandbox: run_cli subprocess fixture
@pytest.fixture
def research_project_root(tmp_path: Path) -> Path:
    """Create a test research mission project."""
    project_dir = tmp_path / "test-research"
    project_dir.mkdir()

    # Initialize git
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project_dir, check=True, capture_output=True)

    # Create .kittify structure with research mission
    kittify = project_dir / ".kittify"
    kittify.mkdir()

    # Copy missions from current repo (new location in src/)
    import shutil

    src_missions = Path.cwd() / "src" / "specify_cli" / "missions"
    if src_missions.exists():
        shutil.copytree(src_missions, kittify / "missions")

    # Set research as active mission
    active_link = kittify / "active-mission"
    try:
        active_link.symlink_to(Path("missions") / "research")
    except (OSError, NotImplementedError):
        # Fallback for systems without symlink support
        active_link.write_text("research\n")

    # Initial commit
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Init research project"], cwd=project_dir, check=True, capture_output=True)

    return project_dir

def test_citation_validation_with_valid_data(tmp_path: Path) -> None:
    """Citation validation should pass with valid citations."""
    from specify_cli.validators.research import validate_citations

    evidence_log = tmp_path / "evidence-log.csv"
    evidence_log.write_text(
        "timestamp,source_type,citation,key_finding,confidence,notes\n"
        '2025-01-15T10:00:00,journal,"Smith (2024). Title. Journal.",Finding,high,Notes\n'
    )

    result = validate_citations(evidence_log)
    assert not result.has_errors

def test_citation_validation_catches_errors(tmp_path: Path) -> None:
    """Citation validation should catch completeness errors."""
    from specify_cli.validators.research import validate_citations

    invalid_log = tmp_path / "invalid.csv"
    invalid_log.write_text(
        "timestamp,source_type,citation,key_finding,confidence,notes\n2025-01-15T10:00:00,invalid_type,,Empty,wrong,\n"
    )

    result = validate_citations(invalid_log)
    assert result.has_errors
    assert result.error_count >= 2

def test_source_register_validation(tmp_path: Path) -> None:
    """Source register validation should work in research context."""
    from specify_cli.validators.research import validate_source_register

    valid = tmp_path / "sources.csv"
    valid.write_text(
        "source_id,citation,url,accessed_date,relevance,status\n"
        'smith2024,"Citation",https://example.com,2025-01-15,high,reviewed\n'
    )

    result = validate_source_register(valid)
    assert not result.has_errors

def test_full_research_workflow_via_cli(tmp_path: Path, run_cli) -> None:
    """Full research workflow using CLI commands end-to-end."""
    import subprocess

    # Initialize research project via CLI
    result = run_cli(tmp_path, "init", "research-test", "--ai", "claude")

    project_dir = tmp_path / "research-test"
    assert result.returncode == 0, f"CLI init failed: {result.stderr}"
    assert project_dir.exists(), "spec-kitty init did not create project directory"

    # Init git for testing
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Init"], cwd=project_dir, check=True, capture_output=True)

    # Create a feature so mission current has explicit feature context.
    mission_slug = "001-research-test"
    feature_dir = project_dir / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "feature_number": "001",
                "slug": mission_slug,
                "mission_slug": mission_slug,
                "friendly_name": "Research Test",
                "mission": "research",
                "target_branch": "main",
                "created_at": "2026-03-20T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    # Verify research mission active for the explicit feature.
    result = run_cli(project_dir, "mission", "current", "--mission", mission_slug)
    assert result.returncode == 0
    assert "research" in result.stdout.lower()

    # Create CSV artifacts
    research_dir = project_dir / "research"
    research_dir.mkdir()

    (research_dir / "evidence-log.csv").write_text(
        "timestamp,source_type,citation,key_finding,confidence,notes\n"
        '2025-01-15T10:00:00,journal,"Smith (2024). Title.",Finding,high,Notes\n'
    )

    (research_dir / "source-register.csv").write_text(
        "source_id,citation,url,accessed_date,relevance,status\n"
        'smith2024,"Smith (2024). Title.",https://example.com,2025-01-15,high,reviewed\n'
    )

    # Validate artifacts
    from specify_cli.validators.research import validate_citations, validate_source_register

    result_cit = validate_citations(research_dir / "evidence-log.csv")
    assert not result_cit.has_errors

    result_src = validate_source_register(research_dir / "source-register.csv")
    assert not result_src.has_errors

def test_deliverables_path_in_meta_json(tmp_path: Path) -> None:
    """meta.json should correctly store and retrieve deliverables_path."""
    import json

    from specify_cli.mission import get_deliverables_path

    # Create feature structure
    feature_dir = tmp_path / "kitty-specs" / "001-market-research"
    feature_dir.mkdir(parents=True)

    # Write meta.json with deliverables_path
    meta_file = feature_dir / "meta.json"
    meta_file.write_text(
        json.dumps(
            {"mission": "research", "slug": "001-market-research", "deliverables_path": "docs/research/market-study/"}
        )
    )

    # Verify retrieval
    result = get_deliverables_path(feature_dir)
    assert result == "docs/research/market-study/"

def test_deliverables_path_not_in_kitty_specs(tmp_path: Path) -> None:
    """deliverables_path must NOT be inside kitty-specs/."""
    from specify_cli.mission import validate_deliverables_path

    # Should reject kitty-specs paths
    is_valid, error = validate_deliverables_path("kitty-specs/001-test/research/")
    assert not is_valid
    assert "kitty-specs" in error.lower()

    # Should accept proper paths
    is_valid, error = validate_deliverables_path("docs/research/001-test/")
    assert is_valid

def test_research_deliverables_separate_from_planning(tmp_path: Path) -> None:
    """Research deliverables should be separate from planning artifacts."""
    import json

    from specify_cli.mission import get_deliverables_path, get_mission_type

    # Create feature structure
    feature_dir = tmp_path / "kitty-specs" / "001-research"
    feature_dir.mkdir(parents=True)

    # Create research planning artifacts (in kitty-specs)
    research_planning = feature_dir / "research"
    research_planning.mkdir()
    (research_planning / "evidence-log.csv").write_text("timestamp,source_type,citation\n")
    (research_planning / "source-register.csv").write_text("source_id,citation,url\n")

    # Create meta.json with deliverables path
    meta_file = feature_dir / "meta.json"
    meta_file.write_text(
        json.dumps({"mission_type": "research", "deliverables_path": "docs/research/001-research/"})
    )

    # Verify separation
    assert get_mission_type(feature_dir) == "research"
    deliverables = get_deliverables_path(feature_dir)
    assert deliverables == "docs/research/001-research/"

    # Planning artifacts exist in kitty-specs
    assert (research_planning / "evidence-log.csv").exists()
    assert (research_planning / "source-register.csv").exists()

    # Deliverables path is NOT in kitty-specs
    assert not deliverables.startswith("kitty-specs")

def test_default_deliverables_path_generation(tmp_path: Path) -> None:
    """Should generate default deliverables path when not specified."""
    import json

    from specify_cli.mission import get_deliverables_path

    # Create feature with research mission but NO deliverables_path
    feature_dir = tmp_path / "kitty-specs" / "002-literature-review"
    feature_dir.mkdir(parents=True)

    meta_file = feature_dir / "meta.json"
    meta_file.write_text(
        json.dumps(
            {
                "mission_type": "research",
                "slug": "002-literature-review",
                # Note: no deliverables_path
            }
        )
    )

    # Should return default path
    result = get_deliverables_path(feature_dir)
    assert result == "docs/research/002-literature-review/"
