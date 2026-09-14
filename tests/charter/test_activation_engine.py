"""Unit tests for ``charter.activation.activation_engine`` (WP10, T047).

Covers the pure plan/commit seam:

- T044/NFR-003 (I-AC1): ``plan_activation`` is pure — byte-compare config before
  and after a failing ``plan_activation`` proves no write occurred.
- T046/FR-012 (Contract C3.1): unknown ID raises a structured error naming the
  kind + missing ID + recovery path; no plan is produced.
- T045: happy-path ``plan_activation`` → ``commit_plan`` writes the config
  exactly once with the appended ID.
- T046/FR-021: a project with no explicit activation restrictions behaves as
  before PR #1535 (default-pack materialization in the plan, then append).
- Deactivation mirror: ``plan_deactivation`` removes from the list, no-ops with a
  warning when absent, and raises ``NoActivationRestrictionsError`` on the
  no-restrictions state.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.activation.activation_engine import (
    ActivationPlan,
    NoActivationRestrictionsError,
    UnknownActivationIdError,
    commit_plan,
    plan_activation,
    plan_deactivation,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_AVAILABLE = ["001-foo", "002-bar", "003-baz"]


def _yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    return yaml


def _load(config_path: Path) -> tuple[dict[str, Any], YAML]:
    yaml = _yaml()
    data = yaml.load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    return (data or {}), yaml


def _save_with(yaml: YAML):
    """Return a single-write ``save`` callable bound to *yaml* (round-trip)."""

    def _save(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            yaml.dump(data, fh)

    return _save


@pytest.fixture()
def config_path(tmp_path: Path) -> Path:
    """A config.yaml with an explicit (non-empty) directive activation list."""
    path = tmp_path / ".kittify" / "config.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "# project config\nactivated_directives:\n  - 001-foo\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# T044 / NFR-003 — purity: failing plan_activation writes nothing
# ---------------------------------------------------------------------------


def test_plan_activation_unknown_id_is_non_mutating(config_path: Path) -> None:
    """I-AC1: config bytes are unchanged after a failing plan_activation."""
    before = config_path.read_bytes()
    data, _ = _load(config_path)

    with pytest.raises(UnknownActivationIdError):
        plan_activation(
            "directive",
            "999-nonexistent",
            yaml_key="activated_directives",
            available_ids=_AVAILABLE,
            config_data=data,
        )

    # plan_activation never reaches commit_plan, so nothing was written.
    assert config_path.read_bytes() == before


def test_plan_activation_does_not_mutate_config_data(config_path: Path) -> None:
    """plan_activation must not mutate the input mapping (purity)."""
    data, _ = _load(config_path)
    snapshot = list(data["activated_directives"])

    plan_activation(
        "directive",
        "002-bar",
        yaml_key="activated_directives",
        available_ids=_AVAILABLE,
        config_data=data,
    )

    assert list(data["activated_directives"]) == snapshot


# ---------------------------------------------------------------------------
# T046 / FR-012 / C3.1 — structured unknown-ID error
# ---------------------------------------------------------------------------


def test_unknown_id_error_names_kind_id_and_recovery(config_path: Path) -> None:
    data, _ = _load(config_path)

    with pytest.raises(UnknownActivationIdError) as exc_info:
        plan_activation(
            "directive",
            "999-nonexistent",
            yaml_key="activated_directives",
            available_ids=_AVAILABLE,
            config_data=data,
        )

    err = exc_info.value
    assert err.kind == "directive"
    assert err.artifact_id == "999-nonexistent"
    message = str(err)
    assert "directive" in message
    assert "999-nonexistent" in message
    assert "charter list --show-available" in message
    assert "doctor doctrine" in message


# ---------------------------------------------------------------------------
# T045 — happy path: plan -> commit writes exactly once
# ---------------------------------------------------------------------------


def test_plan_then_commit_writes_once_with_appended_id(config_path: Path) -> None:
    data, yaml = _load(config_path)

    plan = plan_activation(
        "directive",
        "002-bar",
        yaml_key="activated_directives",
        available_ids=_AVAILABLE,
        config_data=data,
    )
    assert isinstance(plan, ActivationPlan)
    assert plan.new_list == ["001-foo", "002-bar"]
    assert plan.activated == ["002-bar"]

    write_calls: list[Path] = []
    save = _save_with(yaml)

    def counting_save(path: Path, payload: dict[str, Any]) -> None:
        write_calls.append(path)
        save(path, payload)

    commit_plan(config_path, data, plan, save=counting_save)

    assert write_calls == [config_path]  # exactly one write
    reloaded, _ = _load(config_path)
    assert list(reloaded["activated_directives"]) == ["001-foo", "002-bar"]


def test_already_activated_is_noop_with_warning(config_path: Path) -> None:
    data, _ = _load(config_path)

    plan = plan_activation(
        "directive",
        "001-foo",
        yaml_key="activated_directives",
        available_ids=_AVAILABLE,
        config_data=data,
    )

    assert plan.activated == []
    assert plan.new_list == ["001-foo"]
    assert any("already activated" in w for w in plan.warnings)


# ---------------------------------------------------------------------------
# T046 / FR-021 — backward compatibility: no explicit restrictions
# ---------------------------------------------------------------------------


def test_no_restrictions_materializes_what_is_in_force_then_appends(tmp_path: Path) -> None:
    """#4253: a kind absent from config materializes what is EFFECTIVE, then appends.

    ``default_ids`` is gone from this planner (#4399 squad MINOR): once the
    preserved set became the effective corpus, no reachable path consumed it —
    validation guarantees the requested id is in ``available_ids``, so the
    empty-availability branch it guarded could not occur.
    """
    path = tmp_path / ".kittify" / "config.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("# no activation keys\n", encoding="utf-8")

    data, _ = _load(path)

    plan = plan_activation(
        "directive",
        "003-baz",
        yaml_key="activated_directives",
        available_ids=_AVAILABLE,
        config_data=data,
        effective_ids=["001-foo", "002-bar"],
    )

    assert plan.new_list == ["001-foo", "002-bar", "003-baz"]
    assert plan.activated == ["003-baz"]
    assert any("no explicit activation set" in w for w in plan.warnings)


def test_no_restrictions_failing_id_still_non_mutating(tmp_path: Path) -> None:
    """FR-021 + NFR-003: unknown ID on no-restrictions kind writes nothing."""
    path = tmp_path / ".kittify" / "config.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("# no activation keys\n", encoding="utf-8")
    before = path.read_bytes()
    data, _ = _load(path)

    with pytest.raises(UnknownActivationIdError):
        plan_activation(
            "directive",
            "999-nope",
            yaml_key="activated_directives",
            available_ids=_AVAILABLE,
            config_data=data,
            effective_ids=["001-foo"],
        )

    assert path.read_bytes() == before


# ---------------------------------------------------------------------------
# Deactivation mirror
# ---------------------------------------------------------------------------


def test_plan_deactivation_removes_id(config_path: Path) -> None:
    data, _ = _load(config_path)

    plan = plan_deactivation(
        "directive",
        "001-foo",
        yaml_key="activated_directives",
        config_data=data,
    )

    assert plan.new_list == []
    assert plan.deactivated == ["001-foo"]


def test_plan_deactivation_absent_id_is_noop_with_warning(config_path: Path) -> None:
    data, _ = _load(config_path)

    plan = plan_deactivation(
        "directive",
        "002-bar",
        yaml_key="activated_directives",
        config_data=data,
    )

    assert plan.new_list == ["001-foo"]
    assert plan.deactivated == []
    assert any("Nothing to deactivate" in w for w in plan.warnings)


def test_plan_deactivation_no_restrictions_raises(tmp_path: Path) -> None:
    """No baseline => structured error, never a fabricated list."""
    path = tmp_path / ".kittify" / "config.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("# no activation keys\n", encoding="utf-8")
    before = path.read_bytes()
    data, _ = _load(path)

    with pytest.raises(NoActivationRestrictionsError) as exc_info:
        plan_deactivation(
            "directive",
            "001-foo",
            yaml_key="activated_directives",
            config_data=data,
        )

    assert exc_info.value.kind == "directive"
    assert "spec-kitty upgrade" in str(exc_info.value)
    assert path.read_bytes() == before


def test_malformed_list_fails_closed(tmp_path: Path) -> None:
    """A present-but-non-list activation value fails closed (no plan)."""
    path = tmp_path / ".kittify" / "config.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("activated_directives: not-a-list\n", encoding="utf-8")
    data, _ = _load(path)

    with pytest.raises(ValueError, match="must be a list"):
        plan_activation(
            "directive",
            "001-foo",
            yaml_key="activated_directives",
            available_ids=_AVAILABLE,
            config_data=data,
        )
