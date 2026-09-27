"""Unit tests for documentation composition wiring (#502).

C-007 enforcement (spec constraint):
    The following symbols MUST NOT appear in any unittest.mock.patch target
    in this file. Reviewer greps; any hit blocks approval.

        - _dispatch_via_composition
        - StepContractExecutor.execute
        - ProfileInvocationExecutor.invoke
        - _load_frozen_template
        - load_validated_graph
        - resolve_context
"""

from __future__ import annotations

from pathlib import Path

import pytest

import sys
import types
from unittest.mock import MagicMock, patch

from specify_cli.mission_step_contracts.executor import _ACTION_PROFILE_DEFAULTS
from runtime.next.runtime_bridge import (
    _check_composed_action_guard,
)


pytestmark = pytest.mark.fast


_DOC_ACTIONS = ("discover", "audit", "design", "generate", "validate", "publish", "accept")
_PROFILE_DEFAULTS = {
    "discover": "researcher-robbie",
    "audit": "researcher-robbie",
    "design": "architect-alphonso",
    "generate": "implementer-ivan",
    "validate": "reviewer-renata",
    "publish": "reviewer-renata",
    "accept": "reviewer-renata",
}
_GATE_ARTIFACT = {
    "discover": "spec.md",
    "audit": "gap-analysis.md",
    "design": "plan.md",
    "validate": "audit-report.md",
    "publish": "release.md",
}


def test_documentation_in_composed_actions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-002 + FR-015: documentation entry present with the 6 expected verbs.

    After WP07 (_COMPOSED_ACTIONS_BY_MISSION removed), the action sequence is
    sourced from charter.resolve_mission_type_context.  This test mocks the
    MissionTypeRepository so the test remains self-contained.
    """
    doc_mt = MagicMock()
    doc_mt.id = "documentation"
    doc_mt.action_sequence = list(_DOC_ACTIONS)
    doc_mt.extends = None

    mock_repo = MagicMock()
    mock_repo.get.side_effect = lambda k: doc_mt if k == "documentation" else None

    # WP04 (mission up-mission-type-seam-01KZY1JB): resolve_mission_type_context
    # now resolves through the layered factory
    # ``resolve_layered_mission_types``, not ``MissionTypeRepository.default()``.
    # mock_repo already exposes the ``.get(id)`` interface the roster needs.
    mock_resolve_layered = MagicMock(return_value=mock_repo)

    fake_module = types.ModuleType("charter.offering.missions.mission_type_repository")
    fake_module.resolve_layered_mission_types = mock_resolve_layered  # type: ignore[attr-defined]

    monkeypatch.setitem(
        sys.modules, "charter.offering.missions.mission_type_repository", fake_module
    )
    from charter.activation.mission_type_profiles import resolve_mission_type_context

    with patch(
        "charter.activation.mission_type_profiles.existing_mission_types",
        return_value=["documentation", "plan", "research", "software-dev"],
    ):
        result = resolve_mission_type_context(
            tmp_path, mission_type="documentation"
        ).action_sequence

    assert set(result) == frozenset(_DOC_ACTIONS)


@pytest.mark.parametrize("action,profile", list(_PROFILE_DEFAULTS.items()))
def test_profile_defaults_per_action(action: str, profile: str) -> None:
    """FR-016: documentation profile defaults wired in executor._ACTION_PROFILE_DEFAULTS."""
    assert _ACTION_PROFILE_DEFAULTS[("documentation", action)] == profile


@pytest.mark.parametrize("action,artifact", list(_GATE_ARTIFACT.items()))
def test_guard_fails_when_artifact_missing(
    tmp_path: Path, action: str, artifact: str
) -> None:
    """FR-007 + FR-008: each documentation action's guard names the missing artifact."""
    failures = _check_composed_action_guard(action, tmp_path, mission="documentation")
    assert any(artifact in msg for msg in failures), (
        f"expected '{artifact}' in failures for action {action}; got {failures}"
    )


def test_generate_guard_fails_with_empty_docs_root(tmp_path: Path) -> None:
    """FR-008(d): generate gate is 'any *.md under docs/'; empty feature_dir fails."""
    failures = _check_composed_action_guard("generate", tmp_path, mission="documentation")
    assert any("docs" in msg.lower() for msg in failures), failures


def test_generate_guard_passes_with_one_md_under_docs(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "intro.md").write_text("# intro\n", encoding="utf-8")
    failures = _check_composed_action_guard("generate", tmp_path, mission="documentation")
    assert not any("docs" in msg.lower() for msg in failures), failures


def test_unknown_documentation_action_fails_closed(tmp_path: Path) -> None:
    """FR-017: unknown actions emit a structured failure rather than silently passing."""
    failures = _check_composed_action_guard("ghost", tmp_path, mission="documentation")
    assert failures == ["No guard registered for documentation action: ghost"]


@pytest.mark.parametrize("action", _DOC_ACTIONS)
def test_known_action_passes_when_artifact_present(
    tmp_path: Path, action: str
) -> None:
    """FR-007 happy path: each guard returns no failures when its artifact exists."""
    # Author the artifact required by this action.
    if action == "generate":
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "intro.md").write_text("# intro", encoding="utf-8")
    elif action == "accept":
        pass  # no gate artifact — terminal status commit step
    else:
        (tmp_path / _GATE_ARTIFACT[action]).write_text(f"# {action}", encoding="utf-8")

    failures = _check_composed_action_guard(action, tmp_path, mission="documentation")
    assert failures == [], f"expected no failures; got {failures}"
