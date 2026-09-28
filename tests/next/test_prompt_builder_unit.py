"""Unit tests for the prompt builder."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from charter.activation.compiler import compile_charter, write_compiled_charter
from charter.activation.interview import apply_answer_overrides, default_interview
from tests._factories import provision_test_charter
from tests.lane_test_utils import write_single_lane_manifest
from runtime.next.prompt_builder import (
    _mission_context_header,
    build_decision_prompt,
    _governance_context,
    read_wp_task,
    _write_to_temp,
    build_prompt,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


@pytest.fixture
def feature_dir(tmp_path: Path) -> Path:
    # WP04 fail-closed: mission-type governance resolution requires a
    # provisioned charter (activated mission types). Seed the default
    # activation set via the production provisioner, same shared helper
    # used across the mission-creation test harness.
    provision_test_charter(tmp_path)
    fd = tmp_path / "kitty-specs" / "042-test-feature"
    fd.mkdir(parents=True)
    return fd


@pytest.fixture
def feature_with_wp(feature_dir: Path) -> Path:
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\nlane: planned\n---\n# WP01 Content\nDo stuff.\n",
        encoding="utf-8",
    )
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",))
    return feature_dir


# ---------------------------------------------------------------------------
# _mission_context_header
# ---------------------------------------------------------------------------


class TestMissionContextHeader:
    def test_contains_slug(self, feature_dir: Path) -> None:
        header = _mission_context_header("042-test-feature", feature_dir, "claude")
        assert "042-test-feature" in header

    def test_contains_agent(self, feature_dir: Path) -> None:
        header = _mission_context_header("042-test-feature", feature_dir, "claude")
        assert "claude" in header

    def test_contains_directory(self, feature_dir: Path) -> None:
        header = _mission_context_header("042-test-feature", feature_dir, "claude")
        assert str(feature_dir) in header

    def test_uses_mission_label(self, feature_dir: Path) -> None:
        header = _mission_context_header("042-test-feature", feature_dir, "claude")
        assert "Mission: 042-test-feature" in header
        assert "Mission directory:" in header


class TestBuildDecisionPrompt:
    def test_uses_mission_flag_in_answer_command(self, tmp_path: Path) -> None:
        text, path = build_decision_prompt(
            question="Ship it?",
            options=["yes", "no"],
            decision_id="dec-123",
            mission_slug="042-test-feature",
            agent="claude",
            repo_root=tmp_path,
        )
        assert "Mission: 042-test-feature" in text
        assert "--mission 042-test-feature" in text
        assert "--mission-run" not in text
        path.unlink()


# ---------------------------------------------------------------------------
# read_wp_task
# ---------------------------------------------------------------------------


class TestReadWPTask:
    def test_reads_existing_wp(self, feature_with_wp: Path) -> None:
        wp_file, metadata, content = read_wp_task(feature_with_wp / "tasks", "WP01", "042-test-feature")
        assert wp_file.name == "WP01.md"
        assert metadata.work_package_id == "WP01"
        assert "WP01 Content" in content

    def test_missing_wp_raises_with_recovery(self, feature_dir: Path) -> None:
        (feature_dir / "tasks").mkdir()
        with pytest.raises(FileNotFoundError, match="Restore or regenerate"):
            read_wp_task(feature_dir / "tasks", "WP99", "042-test-feature")

    def test_missing_tasks_dir_raises_with_recovery(self, feature_dir: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Canonical WORK_PACKAGE_TASK directory"):
            read_wp_task(feature_dir / "tasks", "WP01", "042-test-feature")

    def test_unreadable_wp_raises_with_recovery(self, feature_dir: Path) -> None:
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01.md").mkdir()

        with pytest.raises(ValueError, match="Could not read canonical WORK_PACKAGE_TASK file.*Restore or regenerate"):
            read_wp_task(tasks_dir, "WP01", "042-test-feature")


# ---------------------------------------------------------------------------
# _write_to_temp
# ---------------------------------------------------------------------------


class TestWriteToTemp:
    def test_creates_file(self, tmp_path: Path) -> None:
        path = _write_to_temp("implement", "WP01", "test content", agent="claude", mission_slug="042-feat", repo_root=tmp_path)
        assert path.exists()
        assert path.read_text(encoding="utf-8") == "test content"
        path.unlink()  # cleanup

    def test_filename_includes_action_and_wp(self, tmp_path: Path) -> None:
        path = _write_to_temp("review", "WP02", "content", agent="codex", mission_slug="042-feat", repo_root=tmp_path)
        assert "review" in path.name
        assert "WP02" in path.name
        path.unlink()

    def test_filename_without_wp(self, tmp_path: Path) -> None:
        path = _write_to_temp("specify", None, "content", agent="claude", mission_slug="042-feat", repo_root=tmp_path)
        assert "specify" in path.name
        assert "WP" not in path.name
        path.unlink()

    def test_filename_includes_agent_and_feature(self, tmp_path: Path) -> None:
        """Different agents/features produce different filenames (no collisions)."""
        p1 = _write_to_temp("implement", "WP01", "a", agent="claude", mission_slug="042-feat", repo_root=tmp_path)
        p2 = _write_to_temp("implement", "WP01", "b", agent="codex", mission_slug="042-feat", repo_root=tmp_path)
        p3 = _write_to_temp("implement", "WP01", "c", agent="claude", mission_slug="043-other", repo_root=tmp_path)
        assert p1 != p2
        assert p1 != p3
        assert p2 != p3
        assert "claude" in p1.name
        assert "codex" in p2.name
        assert "043-other" in p3.name
        p1.unlink()
        p2.unlink()
        p3.unlink()


# ---------------------------------------------------------------------------
# build_prompt (implement/review actions)
# ---------------------------------------------------------------------------


@pytest.fixture
def feature_with_planning_artifact_wp(feature_dir: Path) -> Path:
    """A planning_artifact WP that resolves to repository root."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP02-planning.md").write_text(
        "---\n"
        "work_package_id: WP02\n"
        "execution_mode: planning_artifact\n"
        "owned_files:\n"
        "  - kitty-specs/042-test-feature/spec.md\n"
        "  - kitty-specs/042-test-feature/plan.md\n"
        "---\n"
        "# WP02 Planning\nUpdate the spec and plan.\n",
        encoding="utf-8",
    )
    return feature_dir


@pytest.fixture
def feature_with_planning_artifact_wp_no_owned_files(feature_dir: Path) -> Path:
    """A planning_artifact WP with no owned_files (so review_paths stays empty)."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP02-planning.md").write_text(
        "---\nwork_package_id: WP02\nexecution_mode: planning_artifact\n---\n# WP02 Planning\nDocs work.\n",
        encoding="utf-8",
    )
    return feature_dir


class TestBuildPromptWPPlanningArtifact:
    """Coverage for the repo-root planning-artifact branch in _build_wp_prompt."""

    @pytest.mark.fast
    def test_implement_prompt_for_planning_artifact_uses_repo_root_workspace_label(self, feature_with_planning_artifact_wp: Path) -> None:
        # planning_artifact WPs now use lane-planning (FR-103/FR-105).
        # The workspace label reflects the unified lane contract.
        repo_root = feature_with_planning_artifact_wp.parent.parent
        text, path = build_prompt(
            action="implement",
            feature_dir=feature_with_planning_artifact_wp,
            mission_slug="042-test-feature",
            wp_id="WP02",
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        assert "Workspace contract: lane lane-planning" in text
        path.unlink()

    @pytest.mark.fast
    def test_review_prompt_for_planning_artifact_without_claim_commit_says_unavailable(self, feature_with_planning_artifact_wp: Path) -> None:
        """planning_artifact WPs now use lane-planning (FR-103/FR-105).
        Review commands use the target branch as the diff base."""
        repo_root = feature_with_planning_artifact_wp.parent.parent
        text, path = build_prompt(
            action="review",
            feature_dir=feature_with_planning_artifact_wp,
            mission_slug="042-test-feature",
            wp_id="WP02",
            agent="codex",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        assert "Workspace contract: lane lane-planning" in text
        assert "REVIEW COMMANDS:" in text
        assert "..HEAD --oneline" in text
        path.unlink()

    @pytest.mark.git_repo
    def test_review_prompt_with_claim_commit_emits_pathspec_review_commands(self, feature_with_planning_artifact_wp: Path) -> None:
        """planning_artifact WPs now use lane-planning (FR-103/FR-105).
        Review commands use the target branch as the diff base (no pathspec scoping)."""
        import subprocess

        repo_root = feature_with_planning_artifact_wp.parent.parent
        for cmd in (
            ["git", "init", "--quiet"],
            ["git", "config", "user.email", "test@example.com"],
            ["git", "config", "user.name", "Test"],
            ["git", "add", "kitty-specs/042-test-feature/tasks/WP02-planning.md"],
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", "chore: WP02 claimed for implementation"],
        ):
            subprocess.run(cmd, cwd=repo_root, capture_output=True, check=True)

        text, path = build_prompt(
            action="review",
            feature_dir=feature_with_planning_artifact_wp,
            mission_slug="042-test-feature",
            wp_id="WP02",
            agent="codex",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        assert "REVIEW COMMANDS:" in text
        assert "..HEAD --oneline" in text
        assert "Workspace contract: lane lane-planning" in text
        path.unlink()

    @pytest.mark.git_repo
    def test_review_prompt_with_claim_commit_no_owned_files_has_empty_pathspec(self, feature_with_planning_artifact_wp_no_owned_files: Path) -> None:
        import subprocess

        repo_root = feature_with_planning_artifact_wp_no_owned_files.parent.parent
        for cmd in (
            ["git", "init", "--quiet"],
            ["git", "config", "user.email", "test@example.com"],
            ["git", "config", "user.name", "Test"],
            ["git", "add", "kitty-specs/042-test-feature/tasks/WP02-planning.md"],
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", "chore: WP02 claimed for implementation"],
        ):
            subprocess.run(cmd, cwd=repo_root, capture_output=True, check=True)

        text, path = build_prompt(
            action="review",
            feature_dir=feature_with_planning_artifact_wp_no_owned_files,
            mission_slug="042-test-feature",
            wp_id="WP02",
            agent="codex",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        assert "REVIEW COMMANDS:" in text
        # No owned_files → no pathspec, no exclude markers
        assert ":(exclude)" not in text
        path.unlink()


class TestBuildPromptWP:
    def test_implement_prompt_structure(self, feature_with_wp: Path) -> None:
        repo_root = feature_with_wp.parent.parent
        text, path = build_prompt(
            action="implement",
            feature_dir=feature_with_wp,
            mission_slug="042-test-feature",
            wp_id="WP01",
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        assert "IMPLEMENT" in text
        assert "WP01" in text
        assert "ISOLATION RULES" in text
        assert "WORK PACKAGE PROMPT BEGINS" in text
        assert "WORK PACKAGE PROMPT ENDS" in text
        assert "WP01 Content" in text
        assert "for_review" in text  # completion instruction
        assert "<subtask-ids>" not in text
        assert "No subtask completion command is needed" in text
        assert path.exists()
        path.unlink()

    def test_review_prompt_structure(self, feature_with_wp: Path) -> None:
        repo_root = feature_with_wp.parent.parent
        text, path = build_prompt(
            action="review",
            feature_dir=feature_with_wp,
            mission_slug="042-test-feature",
            wp_id="WP01",
            agent="codex",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        assert "REVIEW" in text
        assert "WP01" in text
        assert "REVIEWING" in text
        assert "APPROVE" in text
        assert "--to approved" in text
        assert "REJECT" in text
        assert path.exists()
        path.unlink()

    def test_review_prompt_includes_antipattern_checklist(self, feature_with_wp: Path) -> None:
        repo_root = feature_with_wp.parent.parent
        text, path = build_prompt(
            action="review",
            feature_dir=feature_with_wp,
            mission_slug="042-test-feature",
            wp_id="WP01",
            agent="codex",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        assert "Anti-pattern checklist (WP-level cheap version of mission-review)" in text
        assert "PASS / FAIL / N/A" in text
        assert "Dead code" in text
        assert "Production fragility" in text
        path.unlink()

    def test_implement_prompt_for_non_python_charter_contains_no_python_default_bias(self, feature_with_wp: Path) -> None:
        repo_root = feature_with_wp.parent.parent
        charter_dir = repo_root / ".kittify" / "charter"
        charter_dir.mkdir(parents=True, exist_ok=True)

        interview = default_interview(mission="software-dev", profile="minimal")
        interview = apply_answer_overrides(
            interview,
            answers={
                "project_intent": "Build a TypeScript service.",
                "languages_frameworks": "TypeScript 5, Node.js, and repo-local tooling.",
                "testing_requirements": "Vitest for unit and integration checks.",
                "quality_gates": "Project tests pass and project lint/type-check commands pass.",
            },
            selected_paradigms=[],
            selected_directives=[],
            available_tools=["git", "pnpm"],
        )
        compiled = compile_charter(mission="software-dev", interview=interview)
        write_compiled_charter(charter_dir, compiled, force=True)

        text, path = build_prompt(
            action="implement",
            feature_dir=feature_with_wp,
            mission_slug="042-test-feature",
            wp_id="WP01",
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        sanitized = text.lower().replace(str(repo_root).lower(), "")
        for forbidden in (
            r"\bpytest\b",
            r"\bjunit\b",
            r"\bmypy\b",
            r"\bruff\b",
            r"\bcargo\b",
            r"\bjest\b",
        ):
            assert re.search(forbidden, sanitized) is None
        path.unlink()


# ---------------------------------------------------------------------------
# build_prompt (template actions)
# ---------------------------------------------------------------------------


class TestBuildPromptTemplate:
    @patch("runtime.next.prompt_builder.resolve_command")
    @patch("runtime.next.prompt_builder.resolve_project_governance")
    def test_template_prompt_has_header(self, mock_governance, mock_resolve, feature_with_wp: Path) -> None:
        # Mock the resolver to return a fake template
        mock_path = feature_with_wp / "fake-template.md"
        mock_path.write_text("# Specify Template\nCreate spec.md.\n", encoding="utf-8")
        mock_result = MagicMock()
        mock_result.path = mock_path
        mock_resolve.return_value = mock_result
        mock_governance.return_value = MagicMock(
            template_set="software-dev-default",
            paradigms=["test-first"],
            directives=["TEST_FIRST"],
            tools=["git", "pytest"],
            diagnostics=[],
        )

        repo_root = feature_with_wp.parent.parent
        text, path = build_prompt(
            action="specify",
            feature_dir=feature_with_wp,
            mission_slug="042-test-feature",
            wp_id=None,
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        assert "042-test-feature" in text
        assert "claude" in text
        assert "Specify Template" in text
        assert "Governance:" in text
        assert "Template set: software-dev-default" in text
        assert path.exists()
        path.unlink()

    @patch("runtime.next.prompt_builder.resolve_command")
    def test_template_prompt_bootstrap_context_first_load(self, mock_resolve, feature_with_wp: Path) -> None:
        import subprocess

        mock_path = feature_with_wp / "fake-template.md"
        mock_path.write_text("# Specify Template\nCreate spec.md.\n", encoding="utf-8")
        mock_result = MagicMock()
        mock_result.path = mock_path
        mock_resolve.return_value = mock_result

        repo_root = feature_with_wp.parent.parent
        # Charter bundle chokepoint (PR #634) resolves project root via
        # `git rev-parse --git-common-dir`; initialise a minimal git repo.
        subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
        charter_dir = repo_root / ".kittify" / "charter"
        charter_dir.mkdir(parents=True)
        (charter_dir / "charter.md").write_text(
            """# Project Charter

## Policy Summary

- Intent: deterministic change management
- Testing: pytest + coverage

## Governance Activation

```yaml
mission: software-dev
selected_paradigms: [test-first]
selected_directives: [TEST_FIRST]
available_tools: [git]
template_set: software-dev-default
```
""",
            encoding="utf-8",
        )
        (charter_dir / "references.yaml").write_text(
            """schema_version: "1.0.0"
references:
  - id: USER:PROJECT_PROFILE
    kind: user_profile
    title: User Profile
    local_path: library/user-project-profile.md
""",
            encoding="utf-8",
        )
        (charter_dir / "governance.yaml").write_text(
            """doctrine:
  selected_paradigms: [test-first]
  selected_directives: [TEST_FIRST]
  available_tools: [git]
  template_set: software-dev-default
""",
            encoding="utf-8",
        )
        (charter_dir / "directives.yaml").write_text(
            """directives:
  - id: TEST_FIRST
    title: Keep tests strict
""",
            encoding="utf-8",
        )

        first_text, first_path = build_prompt(
            action="specify",
            feature_dir=feature_with_wp,
            mission_slug="042-test-feature",
            wp_id=None,
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        assert "Charter Context (Bootstrap):" in first_text
        first_path.unlink()

        second_text, second_path = build_prompt(
            action="specify",
            feature_dir=feature_with_wp,
            mission_slug="042-test-feature",
            wp_id=None,
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        assert "Governance:" in second_text
        second_path.unlink()


class TestGovernanceContext:
    @patch("runtime.next.prompt_builder.resolve_project_governance")
    def test_governance_context_renders_resolution(self, mock_resolve, feature_dir: Path) -> None:
        mock_resolve.return_value = MagicMock(
            template_set="software-dev-default",
            paradigms=["test-first"],
            directives=["TEST_FIRST"],
            tools=["git", "pytest"],
            diagnostics=["Template set from charter."],
        )
        text = _governance_context(feature_dir.parent.parent)
        assert "Governance:" in text
        assert "Template set: software-dev-default" in text
        assert "Paradigms: test-first" in text
        assert "Directives: TEST_FIRST" in text

    @patch("runtime.next.prompt_builder.resolve_project_governance")
    def test_governance_context_handles_failures(self, mock_resolve, feature_dir: Path) -> None:
        mock_resolve.side_effect = RuntimeError("boom")
        text = _governance_context(feature_dir.parent.parent)
        assert "Governance: unavailable" in text

    @pytest.mark.fast
    def test_scope_not_found_is_not_swallowed(self, feature_dir: Path) -> None:
        from charter.activation.scope import CharterScopeNotFound

        with (
            patch(
                "runtime.next.prompt_builder.build_with_scope",
                side_effect=CharterScopeNotFound("outside configured scopes"),
            ),
            pytest.raises(CharterScopeNotFound, match="outside configured scopes"),
        ):
            _governance_context(
                feature_dir.parent.parent,
                action="implement",
                feature_dir=feature_dir,
            )
