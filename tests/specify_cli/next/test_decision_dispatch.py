"""Prompt resolution for runtime step decisions."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from runtime.next.decision import _build_prompt_or_error


pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Known action sequences
# ---------------------------------------------------------------------------

_SW_DEV_ACTIONS = ["specify", "plan", "tasks", "implement", "review"]
_DOCUMENTATION_ACTIONS = [
    "discover",
    "audit",
    "design",
    "generate",
    "validate",
    "publish",
    "accept",
]
_RESEARCH_ACTIONS = ["scoping", "methodology", "gathering", "synthesis", "output"]


# ---------------------------------------------------------------------------
# Verify frozenset is gone
# ---------------------------------------------------------------------------


class TestFrozensetDeletion:
    """Acceptance criterion: _COMPOSED_ACTIONS_FOR_PROMPT must not exist."""

    def test_composed_actions_for_prompt_does_not_exist(self) -> None:
        """_COMPOSED_ACTIONS_FOR_PROMPT MUST NOT be importable from decision."""
        import runtime.next.decision as decision_module

        assert not hasattr(decision_module, "_COMPOSED_ACTIONS_FOR_PROMPT"), (
            "_COMPOSED_ACTIONS_FOR_PROMPT still exists in decision.py — FR-007 violated"
        )


# ---------------------------------------------------------------------------
# Composed actions resolve real prompt files
# ---------------------------------------------------------------------------


class TestComposedActionPromptFile:
    """Composed actions resolve an actionable prompt file."""

    @pytest.mark.parametrize("action", _SW_DEV_ACTIONS)
    def test_software_dev_action_returns_prompt_path(
        self, action: str, tmp_path: Path
    ) -> None:
        """Software-dev actions resolve a prompt when no WP is selected."""
        with patch(
            "charter.activation.mission_type_profiles.resolve_mission_type_context",
            return_value=SimpleNamespace(action_sequence=_SW_DEV_ACTIONS),
        ):
            path, error, _error_code = _build_prompt_or_error(
                action=action,
                feature_dir=tmp_path,
                mission_slug="test-mission",
                wp_id=None,  # composed path requires wp_id=None
                agent="test",
                repo_root=tmp_path,
                mission_type="software-dev",
            )

        assert path is not None, error
        assert error is None
        assert Path(path).exists()
        assert "This step is dispatched via composition." not in Path(path).read_text(encoding="utf-8")

    @pytest.mark.parametrize("action", _DOCUMENTATION_ACTIONS)
    def test_documentation_action_returns_prompt_path(
        self, action: str, tmp_path: Path
    ) -> None:
        """Documentation actions resolve a prompt when no WP is selected."""
        with patch(
            "charter.activation.mission_type_profiles.resolve_mission_type_context",
            return_value=SimpleNamespace(action_sequence=_DOCUMENTATION_ACTIONS),
        ):
            path, error, _error_code = _build_prompt_or_error(
                action=action,
                feature_dir=tmp_path,
                mission_slug="test-mission",
                wp_id=None,
                agent="test",
                repo_root=tmp_path,
                mission_type="documentation",
            )

        assert path is not None, error
        assert error is None
        assert "This step is dispatched via composition." not in Path(path).read_text(encoding="utf-8")

    @pytest.mark.parametrize("action", _RESEARCH_ACTIONS)
    def test_research_action_returns_prompt_path(
        self, action: str, tmp_path: Path
    ) -> None:
        """Research actions resolve a prompt when no WP is selected."""
        with patch(
            "charter.activation.mission_type_profiles.resolve_mission_type_context",
            return_value=SimpleNamespace(action_sequence=_RESEARCH_ACTIONS),
        ):
            path, error, _error_code = _build_prompt_or_error(
                action=action,
                feature_dir=tmp_path,
                mission_slug="test-mission",
                wp_id=None,
                agent="test",
                repo_root=tmp_path,
                mission_type="research",
            )

        assert path is not None, error
        assert error is None
        assert "This step is dispatched via composition." not in Path(path).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Missing prompt is a blocking error
# ---------------------------------------------------------------------------


def test_missing_wp_prompt_is_blocked(tmp_path: Path) -> None:
    """A WP step with no template stays an error (-> blocked); only non-WP steps get a fallback prompt."""
    with patch("runtime.next.prompt_builder.build_prompt", side_effect=FileNotFoundError("missing implement.md")):
        path, error, _error_code = _build_prompt_or_error(
            action="implement",
            feature_dir=tmp_path,
            mission_slug="test-mission",
            wp_id="WP01",
            agent="test",
            repo_root=tmp_path,
            mission_type="software-dev",
        )

    assert path is None
    assert error == "no actionable prompt template for software-dev/implement: missing implement.md"


# ---------------------------------------------------------------------------
# WP prompts keep their own resolution path
# ---------------------------------------------------------------------------


class TestWpIdGuard:
    """A WP-scoped action still resolves a WP prompt."""

    def test_wp_id_set_skips_composed_path(self, tmp_path: Path) -> None:
        """When wp_id is provided, the action is treated as a WP prompt (not composed)."""
        # Create a minimal spec.md so build_prompt doesn't crash on missing artifact.
        (tmp_path / "spec.md").write_text("# spec", encoding="utf-8")

        with patch(
            "charter.activation.mission_type_profiles.resolve_mission_type_context",
            return_value=SimpleNamespace(action_sequence=_SW_DEV_ACTIONS),
        ):
            path, _error, _error_code = _build_prompt_or_error(
                action="implement",
                feature_dir=tmp_path,
                mission_slug="test-mission",
                wp_id="WP01",
                agent="test",
                repo_root=tmp_path,
                mission_type="software-dev",
            )

        # A WP prompt may fail when its board and workspace are absent, but
        # resolution must still give either a real file or a diagnostic.
        if path is not None:
            assert Path(path).is_file()
        else:
            assert _error


# ---------------------------------------------------------------------------
# Prompt content
# ---------------------------------------------------------------------------


class TestPromptFileContents:
    """Resolved prompt content identifies the action."""

    def test_prompt_file_contains_mission_type_and_action(self, tmp_path: Path) -> None:
        with patch(
            "charter.activation.mission_type_profiles.resolve_mission_type_context",
            return_value=SimpleNamespace(action_sequence=_SW_DEV_ACTIONS),
        ):
            path, error, _error_code = _build_prompt_or_error(
                action="specify",
                feature_dir=tmp_path,
                mission_slug="test-mission",
                wp_id=None,
                agent="test",
                repo_root=tmp_path,
                mission_type="software-dev",
            )

        assert path is not None
        assert error is None
        content = Path(path).read_text(encoding="utf-8")
        assert "software-dev" in content
        assert "specify" in content


def test_software_dev_specify_prompt_contains_action_instructions() -> None:
    """A selected composed step must give the agent its real specify work."""
    repo_root = Path(__file__).parents[3]
    mission_slug = "upgrade-preview-mission-health-01M1V6E1"
    mission_dir = repo_root / "kitty-specs" / mission_slug

    path, error, _error_code = _build_prompt_or_error(
        action="specify",
        feature_dir=mission_dir,
        mission_slug=mission_slug,
        wp_id=None,
        agent="codex",
        repo_root=repo_root,
        mission_type="software-dev",
    )

    assert error is None
    assert path is not None
    prompt = Path(path).read_text(encoding="utf-8")
    assert "## Primary Invariant: What Are We Building?" in prompt
    assert "spec-kitty spec-commit" in prompt
    assert "This step is dispatched via composition." not in prompt


@pytest.mark.parametrize(
    ("mission_type", "action", "instruction"),
    [
        ("documentation", "discover", "## What This Step Produces"),
        ("research", "scoping", "## Core Authorship Focus"),
        ("plan", "specify", "## What This Step Is — and Is Not"),
    ],
)
def test_other_mission_types_receive_authored_action_instructions(
    tmp_path: Path, mission_type: str, action: str, instruction: str
) -> None:
    path, error, _error_code = _build_prompt_or_error(
        action=action,
        feature_dir=tmp_path,
        mission_slug="test-mission",
        wp_id=None,
        agent="codex",
        repo_root=tmp_path,
        mission_type=mission_type,
    )

    assert error is None
    assert path is not None
    assert instruction in Path(path).read_text(encoding="utf-8")
