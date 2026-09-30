"""NFR-002 regression gate: _build_prompt_or_error via charter.resolve_mission_type_context.

WP07 / FR-007 / FR-008 / NFR-002.

After deleting _COMPOSED_ACTIONS_FOR_PROMPT, _build_prompt_or_error uses
charter.resolve_mission_type_context to check whether an action is a composed action
(and therefore produces a marker prompt file) or a file-based template action.

These tests verify the new path works correctly for all software-dev steps and
that the frozenset table is gone.
"""

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
# Composed actions produce a marker file (not an error)
# ---------------------------------------------------------------------------


class TestComposedActionMarkerFile:
    """_build_prompt_or_error returns a marker file path for composed actions."""

    @pytest.mark.parametrize("action", _SW_DEV_ACTIONS)
    def test_software_dev_action_returns_marker_path(
        self, action: str, tmp_path: Path
    ) -> None:
        """For software-dev composed actions (wp_id=None), returns a marker path."""
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

        assert path is not None, (
            f"Expected a marker path for composed action '{action}', got error: {error}"
        )
        assert error is None
        assert Path(path).exists(), f"Marker file {path} does not exist on disk"

    @pytest.mark.parametrize("action", _DOCUMENTATION_ACTIONS)
    def test_documentation_action_returns_marker_path(
        self, action: str, tmp_path: Path
    ) -> None:
        """For documentation composed actions (wp_id=None), returns a marker path."""
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

        assert path is not None, (
            f"Expected a marker path for documentation action '{action}', got error: {error}"
        )
        assert error is None

    @pytest.mark.parametrize("action", _RESEARCH_ACTIONS)
    def test_research_action_returns_marker_path(
        self, action: str, tmp_path: Path
    ) -> None:
        """For research composed actions (wp_id=None), returns a marker path."""
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

        assert path is not None, (
            f"Expected a marker path for research action '{action}', got error: {error}"
        )
        assert error is None


# ---------------------------------------------------------------------------
# Charter call site is actually reached
# ---------------------------------------------------------------------------


class TestCharterCallSiteReached:
    """_build_prompt_or_error uses charter.resolve_mission_type_context, not a table."""

    def test_charter_called_for_composed_action(self, tmp_path: Path) -> None:
        """_build_prompt_or_error calls charter.resolve_mission_type_context."""
        call_log: list[str] = []

        def _record_call(
            repo_root: object, *, mission_type: str | None = None, feature_dir: object = None
        ) -> SimpleNamespace:
            call_log.append(mission_type)
            return SimpleNamespace(action_sequence=_SW_DEV_ACTIONS)

        with patch(
            "charter.activation.mission_type_profiles.resolve_mission_type_context",
            side_effect=_record_call,
        ):
            _build_prompt_or_error(
                action="specify",
                feature_dir=tmp_path,
                mission_slug="test-mission",
                wp_id=None,
                agent="test",
                repo_root=tmp_path,
                mission_type="software-dev",
            )

        assert "software-dev" in call_log, (
            "_build_prompt_or_error did not call charter.resolve_mission_type_context"
        )


# ---------------------------------------------------------------------------
# wp_id check: composed fast path only applies when wp_id is None
# ---------------------------------------------------------------------------


class TestWpIdGuard:
    """When wp_id is set, the composed fast path MUST NOT be taken."""

    def test_wp_id_set_skips_composed_path(self, tmp_path: Path) -> None:
        """When wp_id is provided, the action is treated as a WP prompt (not composed)."""
        # Create a minimal spec.md so build_prompt doesn't crash on missing artifact.
        (tmp_path / "spec.md").write_text("# spec", encoding="utf-8")

        with patch(
            "charter.activation.mission_type_profiles.resolve_mission_type_context",
            return_value=SimpleNamespace(action_sequence=_SW_DEV_ACTIONS),
        ):
            # With wp_id set, the code should NOT take the composed path.
            # It will try to call build_prompt and either fail gracefully or succeed.
            path, _error, _error_code = _build_prompt_or_error(
                action="implement",
                feature_dir=tmp_path,
                mission_slug="test-mission",
                wp_id="WP01",  # wp_id is NOT None → should skip the composed marker
                agent="test",
                repo_root=tmp_path,
                mission_type="software-dev",
            )

        # The WP-scoped path skips the composed marker entirely.
        # When wp_id is set, _is_composed_action is always False (because
        # `wp_id is None` is False), so the composed marker fast-path is never
        # taken.  Either the template builder succeeds (path is a real path) or
        # it fails gracefully (path is None, error is set) — but a composed
        # marker path must never be produced for a WP-scoped action.
        if path is not None:
            assert "spec-kitty-composed-" not in str(path), (
                "WP-scoped actions must not produce a composed marker; "
                f"got path: {path}"
            )
        else:
            # path is None = template builder failed gracefully; that is acceptable,
            # but _error must explain why (not be an empty string).
            assert _error, (
                "When _build_prompt_or_error returns path=None, error must be non-empty"
            )


# ---------------------------------------------------------------------------
# NFR-002: marker file contents
# ---------------------------------------------------------------------------


class TestMarkerFileContents:
    """Marker file written for composed actions has the right header."""

    def test_marker_file_contains_mission_type_and_action(self, tmp_path: Path) -> None:
        """Marker file for a composed action names the mission type and action."""
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
