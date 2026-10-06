"""Truth-table tests for the widened composition gate (Phase 6 / R-005).

Mission: ``local-custom-mission-loader-01KQ2VNJ`` (WP04).

The runtime bridge's composition gate widens past the built-in
``software-dev`` allow-list to include any custom mission whose active step
sets ``agent_profile`` on its frozen-template entry. These tests lock that
truth table and the supporting ``_resolve_step_agent_profile`` helper.

Critical invariant exercised here: the **built-in fast path must short-circuit
before any frozen-template I/O**. Without that, every built-in dispatch would
pay the cost of loading and parsing the frozen template for every step — and
worse, would couple built-in dispatch correctness to template-on-disk state.
The dedicated ``test_builtin_software_dev_short_circuits_without_run_dir``
asserts the fast path does not call ``_resolve_step_agent_profile``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from runtime.next.runtime_bridge_composition import (
    _resolve_step_agent_profile,
    _resolve_runtime_contract_for_step,
    _should_dispatch_via_composition,
)


pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Frozen-template helpers
# ---------------------------------------------------------------------------


def _write_frozen_template(
    run_dir: Path,
    *,
    mission_key: str,
    steps: list[dict[str, object]],
) -> Path:
    """Write a minimal frozen template at the layout ``_load_frozen_template`` expects.

    The engine reads ``<run_dir>/mission_template_frozen.yaml`` directly; the
    loader (`load_mission_template_file`) accepts the lightweight shorthand
    where top-level ``key`` / ``name`` / ``version`` collapse into a
    ``mission`` block.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    template = {
        "mission": {
            "key": mission_key,
            "name": mission_key,
            "version": "1.0.0",
            "description": f"Test mission for {mission_key}",
        },
        "steps": steps,
    }
    frozen_path = run_dir / "mission_template_frozen.yaml"
    frozen_path.write_text(yaml.safe_dump(template), encoding="utf-8")
    return frozen_path


# ---------------------------------------------------------------------------
# Built-in fast path — must NOT load the frozen template.
# ---------------------------------------------------------------------------


def test_builtin_software_dev_specify_returns_true() -> None:
    """Built-in ``software-dev/specify`` routes through composition unconditionally.

    Since WP07 (FR-007 / FR-008), the fast path is the live charter lookup via
    ``charter.resolve_mission_type_context``. ``repo_root`` is required; without it
    the charter lookup is skipped and the gate falls through. The caller always
    supplies ``repo_root`` at runtime.
    """
    assert _should_dispatch_via_composition("software-dev", "specify", repo_root=_REPO_ROOT) is True


def test_builtin_software_dev_all_composed_actions_return_true() -> None:
    """Every member of the built-in composed-action set routes through composition."""
    for action in ("specify", "plan", "tasks", "implement", "review"):
        assert _should_dispatch_via_composition("software-dev", action, repo_root=_REPO_ROOT) is True, (
            f"Built-in software-dev/{action} should dispatch via composition"
        )


def test_builtin_software_dev_short_circuits_without_run_dir(tmp_path: Path) -> None:
    """The charter fast path MUST NOT call ``_resolve_step_agent_profile``.

    Critical regression trap: the charter lookup (``charter.resolve_mission_type_context``)
    is the fast path for built-in missions since WP07. It short-circuits before any
    frozen-template I/O, preserving the PR #797 invariant that built-in dispatch
    correctness does not depend on template-on-disk state.
    We patch ``_resolve_step_agent_profile`` and assert it was never called.
    """
    with patch(
        "runtime.next.runtime_bridge_composition._resolve_step_agent_profile"
    ) as mock_resolve:
        # Charter lookup returns True for software-dev/specify before
        # _resolve_step_agent_profile (frozen-template path) is ever reached.
        result = _should_dispatch_via_composition(
            "software-dev", "specify", run_dir=tmp_path, repo_root=_REPO_ROOT
        )

    assert result is True
    mock_resolve.assert_not_called()


# ---------------------------------------------------------------------------
# Custom mission widening (R-005)
# ---------------------------------------------------------------------------


def test_unknown_mission_no_run_dir_returns_false() -> None:
    """Unknown missions without a run_dir cannot widen — fall through to legacy DAG."""
    assert _should_dispatch_via_composition("custom", "step1") is False


def test_unknown_mission_with_run_dir_but_no_template_returns_false(
    tmp_path: Path,
) -> None:
    """Run dir exists but no frozen template — gate stays closed."""
    assert (
        _should_dispatch_via_composition("custom", "step1", run_dir=tmp_path) is False
    )


def test_custom_mission_with_agent_profile_returns_true(tmp_path: Path) -> None:
    """A custom mission whose active step has ``agent_profile`` widens the gate."""
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[
            {
                "id": "step1",
                "title": "Custom step one",
                "agent_profile": "implementer-ivan",
            },
        ],
    )

    assert (
        _should_dispatch_via_composition(
            "custom-mission", "step1", run_dir=run_dir
        )
        is True
    )


def test_custom_mission_with_contract_ref_returns_true(tmp_path: Path) -> None:
    """A custom mission whose active step has ``contract_ref`` also widens the gate."""
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[
            {
                "id": "step1",
                "title": "Custom step one",
                "contract_ref": "plan",
            },
        ],
    )

    assert (
        _should_dispatch_via_composition(
            "custom-mission", "step1", run_dir=run_dir
        )
        is True
    )


def test_custom_mission_without_agent_profile_returns_false(tmp_path: Path) -> None:
    """Custom mission step with ``agent_profile=None`` falls through to legacy DAG."""
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[
            {
                "id": "step1",
                "title": "Custom step one",
                # agent_profile omitted → defaults to None
            },
        ],
    )

    assert (
        _should_dispatch_via_composition(
            "custom-mission", "step1", run_dir=run_dir
        )
        is False
    )


def test_custom_mission_with_empty_string_agent_profile_returns_false(
    tmp_path: Path,
) -> None:
    """Empty string ``agent_profile`` is treated as falsy — gate stays closed."""
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[
            {
                "id": "step1",
                "title": "Custom step one",
                "agent_profile": "",
            },
        ],
    )

    assert (
        _should_dispatch_via_composition(
            "custom-mission", "step1", run_dir=run_dir
        )
        is False
    )


def test_custom_mission_unknown_step_returns_false(tmp_path: Path) -> None:
    """Step ID not present in the template — gate stays closed."""
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[
            {
                "id": "step1",
                "title": "Step one",
                "agent_profile": "implementer-ivan",
            },
        ],
    )

    assert (
        _should_dispatch_via_composition(
            "custom-mission", "step_does_not_exist", run_dir=run_dir
        )
        is False
    )


# ---------------------------------------------------------------------------
# _resolve_step_agent_profile direct coverage
# ---------------------------------------------------------------------------


def test_resolve_step_agent_profile_returns_none_when_template_missing(
    tmp_path: Path,
) -> None:
    """No frozen template → ``None`` (helper swallows the engine's error)."""
    nonexistent = tmp_path / "no-such-run"
    assert _resolve_step_agent_profile(nonexistent, "any-step") is None


def test_resolve_step_agent_profile_returns_profile_for_matching_step(
    tmp_path: Path,
) -> None:
    """Direct round-trip: write the template, read the profile back."""
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[
            {
                "id": "step1",
                "title": "Step one",
                "agent_profile": "researcher-robbie",
            },
            {
                "id": "step2",
                "title": "Step two",
                "agent_profile": "architect-alphonso",
            },
        ],
    )

    assert _resolve_step_agent_profile(run_dir, "step1") == "researcher-robbie"
    assert _resolve_step_agent_profile(run_dir, "step2") == "architect-alphonso"


def test_resolve_runtime_contract_synthesizes_from_frozen_template(
    tmp_path: Path,
) -> None:
    """Synthesized contracts survive normal separate-process ``next`` usage.

    The process-local registry may be empty when ``spec-kitty next`` runs, so
    the bridge must be able to synthesize the active step contract from the
    frozen template.
    """
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[
            {
                "id": "step1",
                "title": "Step one",
                "agent_profile": "researcher-robbie",
            },
        ],
    )

    contract = _resolve_runtime_contract_for_step(
        repo_root=tmp_path,
        run_dir=run_dir,
        mission="custom-mission",
        step_id="step1",
    )

    assert contract is not None
    assert contract.id == "custom:custom-mission:step1"
    assert contract.mission == "custom-mission"
    assert contract.action == "step1"


def test_resolve_runtime_contract_uses_contract_ref(tmp_path: Path) -> None:
    """``contract_ref`` resolves against the existing repository by id."""
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[
            {
                "id": "step1",
                "title": "Step one",
                "contract_ref": "plan",
            },
        ],
    )

    contract = _resolve_runtime_contract_for_step(
        repo_root=tmp_path,
        run_dir=run_dir,
        mission="custom-mission",
        step_id="step1",
    )

    assert contract is not None
    assert contract.id == "plan"
    assert contract.mission == "software-dev"
    assert contract.action == "plan"


def test_resolve_step_agent_profile_returns_none_for_missing_step(
    tmp_path: Path,
) -> None:
    """Step not in template → ``None``."""
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[
            {
                "id": "step1",
                "title": "Step one",
                "agent_profile": "implementer-ivan",
            },
        ],
    )

    assert _resolve_step_agent_profile(run_dir, "step_does_not_exist") is None


def test_resolve_step_agent_profile_normalizes_legacy_tasks_substep(
    tmp_path: Path,
) -> None:
    """Legacy ``tasks_outline`` lookup resolves against a template-side ``tasks`` step.

    The helper normalizes legacy substep IDs through
    ``_normalize_action_for_composition`` so in-flight runs that still carry
    ``tasks_outline`` / ``tasks_packages`` / ``tasks_finalize`` step IDs can
    still find their composed counterpart.
    """
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[
            {
                "id": "tasks",
                "title": "Tasks",
                "agent_profile": "architect-alphonso",
            },
        ],
    )

    assert (
        _resolve_step_agent_profile(run_dir, "tasks_outline")
        == "architect-alphonso"
    )
    assert (
        _resolve_step_agent_profile(run_dir, "tasks_packages")
        == "architect-alphonso"
    )
    assert (
        _resolve_step_agent_profile(run_dir, "tasks_finalize")
        == "architect-alphonso"
    )


def test_resolve_step_agent_profile_empty_string_returns_none(tmp_path: Path) -> None:
    """Empty-string ``agent_profile`` collapses to ``None`` at the helper boundary."""
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[
            {
                "id": "step1",
                "title": "Step one",
                "agent_profile": "",
            },
        ],
    )

    assert _resolve_step_agent_profile(run_dir, "step1") is None
