"""``plan_activation`` owns the org-required freeze warning (#6458, FR-005..FR-007, C-004).

Pure planner tests: the warning is keyed on ``effective_when_absent ==
"required"``; an absent key's in-force message drops the ``--only`` advice for
such a kind; ``"all"`` kinds are unchanged.
"""

from __future__ import annotations

import pytest

from charter.activation.activation_engine import (
    FROZEN_LIST_NOTE,
    ActivationPlan,
    NARROW_UNRESOLVED_WARNING,
    narrow_unresolved_warning,
    org_required_freeze_warning,
    plan_activation,
)

pytestmark = [pytest.mark.unit]

_SKILLS = "activated_skills"
_FREEZE = org_required_freeze_warning("skill", "skills")


def _plan(
    *, config: dict[str, list[str]] | None = None, when_absent: str = "required", narrow: list[str] | None = None, key: str = _SKILLS, kind: str = "skill"
) -> ActivationPlan:
    return plan_activation(
        kind,
        "x",
        yaml_key=key,
        available_ids=["r", "x", "y"],
        config_data=config or {},
        effective_ids=["r"],
        effective_when_absent=when_absent,
        narrow_base=narrow,
        previous_ids=["r"] if narrow is not None else (),
    )


def test_required_kind_absent_key_warns_and_drops_the_only_advice() -> None:
    plan = _plan()

    assert plan.new_list == ["r", "x"]
    assert _FREEZE in plan.warnings
    assert not any(FROZEN_LIST_NOTE.strip() in warning for warning in plan.warnings)
    assert any("so nothing in force was deactivated." in warning for warning in plan.warnings)


def test_required_kind_present_key_does_not_warn() -> None:
    plan = _plan(config={_SKILLS: ["r"]})

    assert plan.new_list == ["r", "x"]
    assert _FREEZE not in plan.warnings


@pytest.mark.parametrize("config", [None, {_SKILLS: ["r", "y"]}])
def test_required_kind_narrowing_warns_every_run(config: dict[str, list[str]] | None) -> None:
    plan = _plan(config=config, narrow=["r"])

    assert plan.new_list == ["r", "x"]
    assert plan.warnings.count(_FREEZE) == 1


def test_all_kind_never_warns_and_keeps_the_only_advice() -> None:
    absent = _plan(when_absent="all", key="activated_toolguides", kind="toolguide")
    narrowed = _plan(when_absent="all", key="activated_toolguides", kind="toolguide", narrow=[])

    assert not any("frozen at their current values" in warning for warning in [*absent.warnings, *narrowed.warnings])
    assert any(warning.endswith(FROZEN_LIST_NOTE) for warning in absent.warnings)


def test_narrow_unresolved_warning_names_the_reason_or_keeps_the_shared_text() -> None:
    assert narrow_unresolved_warning(None) == NARROW_UNRESOLVED_WARNING
    assert narrow_unresolved_warning("") == NARROW_UNRESOLVED_WARNING
    assert narrow_unresolved_warning("a layer is unreadable") == (
        "What stopped being in force cannot be listed: the effective set could not be resolved because a layer is unreadable."
    )
