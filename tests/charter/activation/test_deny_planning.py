"""The deny-aware planners (WP04: data-model.md §3, US1.3, US1.4, US1.5, FR-007, FR-008, FR-009).

Pure planner tests: one per row of data-model.md §3 that WP04 owns. Nothing is
read from disk; the config mapping, the available ids and the required floor are
data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from charter.activation.activation_engine import (
    ActivationPlan,
    DeactivationRefused,
    EffectiveSet,
    RequiredArtifactDeactivationError,
    UnknownActivationIdError,
    check_deactivation_permitted,
    commit_plan,
    deny_delta,
    plan_activation,
    plan_deactivation,
    promote_activations,
)
from charter.activation.activation_ledger import DenyListChoice, _effective_deny
from charter.activation.org_pack_discovery import RequiringPack
from charter.offering.artifact_kinds import ArtifactKind

pytestmark = [pytest.mark.fast, pytest.mark.unit]

_KEY = "activated_directives"
_DENY = "deactivated_directives"
_SKILLS = "activated_skills"
_ACME = (RequiringPack("acme"),)


def _activate(artifact_id: str, config: dict[str, Any], **kwargs: Any) -> ActivationPlan:
    kwargs.setdefault("available_ids", {"a", "b", "d", "x"})
    kwargs.setdefault("current_deny", config.get(_DENY, ()))
    return plan_activation("directive", artifact_id, yaml_key=_KEY, config_data=config, deny_key=_DENY, **kwargs)


def _deactivate(artifact_id: str, config: dict[str, Any], **kwargs: Any) -> ActivationPlan:
    kwargs.setdefault("available_ids", {"a", "b", "d", "x"})
    kwargs.setdefault("required_by", {})
    kwargs.setdefault("current_deny", config.get(_DENY, ()))
    return plan_deactivation("directive", artifact_id, yaml_key=_KEY, config_data=config, deny_key=_DENY, **kwargs)


# --------------------------------------------------------------------------- #
# Activation (US1.4, US1.5, D-09)
# --------------------------------------------------------------------------- #


def test_activating_a_denied_id_under_absent_all_is_deny_only() -> None:
    plan = _activate("d", {_DENY: ["d"]}, effective_ids=["a", "b"])

    assert plan.new_list is None  # the allow list stays absent: "all" keeps arriving
    assert plan.new_deny_list == []
    assert plan.deny_change is DenyListChoice.ACTIVATE
    assert plan.activated == ["d"]


def test_activating_a_denied_skill_under_absent_required_materialises_the_in_force_set() -> None:
    plan = plan_activation(
        "skill",
        "x",
        yaml_key=_SKILLS,
        available_ids={"r1", "x"},
        config_data={"deactivated_skills": ["x"]},
        effective_ids=["r1"],
        effective_when_absent="required",
        deny_key="deactivated_skills",
        current_deny=["x"],
    )

    assert plan.new_list == ["r1", "x"]
    assert plan.new_deny_list == []
    assert plan.deny_change is DenyListChoice.ACTIVATE


@pytest.mark.parametrize(("allow", "expected"), [([], ["x"]), (["a"], ["a", "x"])])
def test_activating_a_denied_id_appends_to_a_present_list_and_clears_it(allow: list[str], expected: list[str]) -> None:
    plan = _activate("x", {_KEY: allow, _DENY: ["x", "b"]})

    assert plan.new_list == expected
    assert plan.new_deny_list == ["b"]
    assert plan.deny_change is DenyListChoice.ACTIVATE


def test_only_narrows_to_the_required_stems_plus_x_and_clears_only_x() -> None:
    plan = _activate("x", {_KEY: ["a", "b"], _DENY: ["x", "r"]}, narrow_base=["r"], previous_ids=["a", "b"], available_ids={"a", "b", "r", "x"})

    assert plan.new_list == ["r", "x"]
    assert plan.new_deny_list == ["r"]
    assert plan.deny_change is DenyListChoice.ACTIVATE
    assert plan.deactivated == ["a", "b"]


def test_materialising_an_absent_list_leaves_out_effective_denied_ids() -> None:
    plan = _activate("x", {_DENY: ["d"]}, effective_ids=["a", "d"], effective_deny=frozenset({"d"}))

    assert plan.new_list == ["a", "x"]
    assert plan.deny_key is None  # nothing about the deny-list changes
    assert plan.deny_change is None


def test_the_available_fallback_also_leaves_out_effective_denied_ids() -> None:
    plan = _activate("x", {_DENY: ["d"]}, effective_deny=frozenset({"d"}))

    assert "d" not in (plan.new_list or [])
    assert plan.new_list is not None and "x" in plan.new_list


def test_a_plain_activation_records_no_deny_change() -> None:
    plan = _activate("x", {_KEY: ["a"]})

    assert plan.new_list == ["a", "x"]
    assert (plan.deny_key, plan.new_deny_list, plan.deny_change) == (None, None, None)


def test_the_reinstating_choice_is_carried_through() -> None:
    plan = _activate("x", {_KEY: ["a"], _DENY: ["x"]}, deny_change=DenyListChoice.CASCADE_INCLUDE_DEACTIVATED)

    assert plan.deny_change is DenyListChoice.CASCADE_INCLUDE_DEACTIVATED


# --------------------------------------------------------------------------- #
# Deactivation (US1.1, US1.2, US4.1, D-08, D-11)
# --------------------------------------------------------------------------- #


def test_deactivating_under_an_absent_list_records_an_exclusion_only() -> None:
    plan = _deactivate("d", {})

    assert plan.new_list is None
    assert plan.new_deny_list == ["d"]
    assert plan.deny_change is DenyListChoice.DEACTIVATE
    assert plan.deactivated == ["d"]


def test_deactivating_from_a_present_list_removes_and_records() -> None:
    plan = _deactivate("d", {_KEY: ["a", "d"], _DENY: ["b"]})

    assert plan.new_list == ["a"]
    assert plan.new_deny_list == ["b", "d"]
    assert plan.deny_change is DenyListChoice.DEACTIVATE


def test_an_empty_list_stays_empty_and_records_the_exclusion() -> None:
    plan = _deactivate("d", {_KEY: []})

    assert plan.new_list == []
    assert plan.new_deny_list == ["d"]


def test_a_declared_spelling_in_the_allow_list_is_removed_too() -> None:
    plan = _deactivate("d", {_KEY: ["a", "DIRECTIVE_D"]}, also_matches=("DIRECTIVE_D",))

    assert plan.new_list == ["a"]
    assert plan.new_deny_list == ["d"]


def test_an_already_denied_id_is_a_flagged_no_op() -> None:
    plan = _deactivate("d", {_DENY: ["d"]})

    assert plan.noop
    assert plan.deny_change is None
    assert any("already deactivated" in warning for warning in plan.warnings)


def test_an_unknown_id_raises_before_any_post_state() -> None:
    with pytest.raises(UnknownActivationIdError):
        _deactivate("nope", {})


def test_an_id_only_the_allow_list_knows_is_still_removable() -> None:
    plan = _deactivate("legacy-only", {_KEY: ["legacy-only", "a"]})

    assert plan.new_list == ["a"]
    assert plan.new_deny_list == ["legacy-only"]


def test_a_required_id_is_refused_naming_pack_and_policy_key() -> None:
    with pytest.raises(RequiredArtifactDeactivationError) as excinfo:
        _deactivate("d", {}, required_by={"d": _ACME})

    error = excinfo.value
    assert isinstance(error, DeactivationRefused)
    assert isinstance(error, ValueError)
    assert (error.kind, error.artifact_id, error.reason, error.policy_key) == ("directive", "d", "required", "required_directives")
    assert error.requiring == _ACME
    assert str(error) == "Cannot deactivate directive 'd': required by org pack 'acme' (required_directives). Nothing was recorded."


def test_the_refusal_names_every_requiring_pack_and_the_inheriting_one() -> None:
    requiring = (RequiringPack("base"), RequiringPack("base", via="overlay"), RequiringPack("other"))

    with pytest.raises(RequiredArtifactDeactivationError) as excinfo:
        check_deactivation_permitted("directive", "d", {"d": requiring})

    assert str(excinfo.value) == (
        "Cannot deactivate directive 'd': required by org packs 'base', 'base' (via 'overlay'), 'other' (required_directives). Nothing was recorded."
    )


def test_the_refusal_is_checked_before_the_unknown_id() -> None:
    with pytest.raises(RequiredArtifactDeactivationError):
        _deactivate("nope", {}, required_by={"nope": _ACME})


def test_a_permitted_id_passes_the_refusal_seam() -> None:
    check_deactivation_permitted("directive", "a", {"d": _ACME})


def test_deactivation_refused_is_abstract() -> None:
    with pytest.raises(TypeError):
        DeactivationRefused("directive", "d", "required", "message")


def test_a_cascade_child_drops_its_allow_entry_but_records_no_exclusion() -> None:
    plan = _deactivate("d", {_KEY: ["a", "d"]}, record_exclusion=False)

    assert plan.new_list == ["a"]
    assert (plan.deny_key, plan.new_deny_list, plan.deny_change) == (None, None, None)


def test_a_cascade_child_under_an_absent_list_is_a_no_op() -> None:
    plan = _deactivate("d", {}, record_exclusion=False)

    assert plan.noop
    assert plan.new_list is None


def test_a_mission_type_deactivation_has_no_deny_list() -> None:
    plan = plan_deactivation(
        "mission-type",
        "research",
        yaml_key="mission_type_activations",
        config_data={"mission_type_activations": ["software-dev", "research"]},
        available_ids={"software-dev", "research"},
        required_by={},
        deny_key=None,
    )

    assert plan.new_list == ["software-dev"]
    assert plan.deny_key is None


# --------------------------------------------------------------------------- #
# Effective deny, deltas, the single write
# --------------------------------------------------------------------------- #


def test_effective_deny_subtracts_the_required_floor_in_identity_space() -> None:
    class _Index:
        def declared_id(self, kind: ArtifactKind, token: str) -> str | None:
            return "DIRECTIVE_D" if token in {"d", "DIRECTIVE_D"} else None

        def stem(self, kind: ArtifactKind, token: str) -> str | None:
            return {"DIRECTIVE_D": "d", "d": "d"}.get(token)

    stems = _effective_deny(ArtifactKind.DIRECTIVE, ["DIRECTIVE_D", "x", "y"], {"x"}, _Index()).stems

    assert stems == frozenset({"d", "y"})
    assert not _effective_deny(ArtifactKind.DIRECTIVE, ["d"], {"d"}, _Index())


def test_deny_delta_reports_added_and_cleared() -> None:
    assert deny_delta(["a", "b"], ["b", "c"]) == (["c"], ["a"])
    assert deny_delta(None, ["a"]) == (["a"], [])
    assert deny_delta(["a"], None) == ([], ["a"])


def test_commit_plan_writes_both_keys_with_one_save() -> None:
    calls: list[tuple[dict[str, Any], DenyListChoice | None]] = []

    def save(path: Path, data: dict[str, Any], *, deny_change: DenyListChoice | None = None) -> None:
        calls.append((dict(data), deny_change))

    config: dict[str, Any] = {_KEY: ["a", "d"]}
    commit_plan(Path("ledger"), config, _deactivate("d", config), save=save)

    assert calls == [({_KEY: ["a"], _DENY: ["d"]}, DenyListChoice.DEACTIVATE)]


def test_commit_plan_leaves_an_absent_allow_list_absent_and_removes_an_emptied_deny_list() -> None:
    calls: list[dict[str, Any]] = []

    def save(path: Path, data: dict[str, Any], *, deny_change: DenyListChoice | None = None) -> None:
        calls.append(dict(data))

    config: dict[str, Any] = {_DENY: ["d"]}
    commit_plan(Path("ledger"), config, _activate("d", config), save=save)

    assert calls == [{}]


def test_commit_plan_without_a_deny_change_keeps_the_two_argument_save() -> None:
    calls: list[dict[str, Any]] = []
    config: dict[str, Any] = {_KEY: ["a"]}

    commit_plan(Path("cfg"), config, _activate("x", config), save=lambda path, data: calls.append(dict(data)))

    assert calls == [{_KEY: ["a", "x"]}]


# --------------------------------------------------------------------------- #
# Promotion never re-adds a denied id (US1.3, FR-009, F17)
# --------------------------------------------------------------------------- #


class _Verbatim:
    """An identity that knows no artifact: every token is its own stem."""

    def declared_id(self, kind: ArtifactKind, token: str) -> str | None:
        del kind, token
        return None

    def stem(self, kind: ArtifactKind, token: str) -> str | None:
        del kind, token
        return None


def _promote(
    config: dict[str, Any], promotions: dict[str, list[str]], *, required: frozenset[str] = frozenset(), **kwargs: Any
) -> tuple[Any, list[dict[str, Any]]]:
    """Promote with ``D*`` derived from *config*'s deny list less *required* (what the seam hands the engine)."""
    writes: list[dict[str, Any]] = []
    denied = {_KEY: _effective_deny(ArtifactKind.DIRECTIVE, config.get(_DENY, ()), required, _Verbatim())}
    outcome = promote_activations(
        promotions,
        config_path=Path("ledger"),
        config_data=config,
        save=lambda path, data: writes.append(dict(data)),
        effective_sets=kwargs.pop("effective_sets", {}),
        denied=denied,
        **kwargs,
    )
    return outcome, writes


def test_promotion_skips_effective_denied_ids_and_reports_them() -> None:
    outcome, writes = _promote({_KEY: ["a"], _DENY: ["d"]}, {_KEY: ["d", "b"]})

    assert outcome.committed[0].new_list == ["a", "b"]
    assert outcome.skipped_denied == {_KEY: ["d"]}
    assert writes[-1][_DENY] == ["d"]


def test_a_required_id_is_exempt_from_a_stale_deny_entry() -> None:
    outcome, _writes = _promote({_KEY: ["a"], _DENY: ["d"]}, {_KEY: ["d"]}, required=frozenset({"d"}))

    assert outcome.committed[0].new_list == ["a", "d"]
    assert outcome.skipped_denied == {}


def test_org_required_promotion_of_other_ids_keeps_denied() -> None:
    effective = {_KEY: EffectiveSet(kind="directive", yaml_key=_KEY, ids=frozenset({"b", "d"}))}

    outcome, writes = _promote({_DENY: ["d"]}, {_KEY: ["a"]}, effective_sets=effective, required=frozenset({"a"}))

    assert outcome.committed[0].new_list == ["b", "a"]
    assert writes[-1][_DENY] == ["d"]
    assert outcome.skipped_denied == {_KEY: ["d"]}


def test_mission_type_seeding_keeps_denied() -> None:
    outcome, writes = _promote({_KEY: ["a"], _DENY: ["d"]}, {_KEY: ["x", "d"]})

    assert "d" not in outcome.committed[0].new_list
    assert writes[-1][_DENY] == ["d"]
    assert outcome.skipped_denied == {_KEY: ["d"]}
    assert any("'d'" in message for message in outcome.skipped_denied_messages())
