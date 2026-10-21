"""Every specify_cli-side activation reader honours the deny-list (WP06: FR-016, M2).

One test per reader: ``profiles list`` / ``profiles show``, the invocation
registry, the empty-charter fallback, the implement precondition, the
finalize-tasks bootstrap gate, the ``tasks status`` human-in-charge marker and
the ``charter list`` deactivated column. Each fixture is ledger-seeded.
Positive control (F15): each
test first shows the id served on the same fixture, then denies it.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from charter.activation.exceptions import CharterActivationError
from specify_cli.charter_runtime.preflight.runner import _deactivated_mission_default_profile_warnings
from specify_cli.cli.commands import profiles_cmd
from specify_cli.cli.commands.agent.mission_finalize_bootstrap import _enforce_charter_activation_gate
from specify_cli.cli.commands.agent.tasks_status_cmd import _get_hic_marker
from specify_cli.cli.commands.agent.workflow_executor import implement_check_wp_charter_precondition
from specify_cli.cli.commands.charter import charter_app
from specify_cli.invocation.empty_charter import GENERIC_AGENT_ID, is_charter_empty
from specify_cli.invocation.errors import ProfileNotFoundError
from specify_cli.invocation.registry import ProfileRegistry
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.fast]

_RUNNER = CliRunner()
_PROFILE = "python-pedro"
_DEFAULT_PROFILE = "implementer-ivan"
_HIC = "human-in-charge"


def _project(tmp_path: Path, **ledger: list[str]) -> Path:
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text("", encoding="utf-8")
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"], **ledger)
    return tmp_path


def _deny_profile(root: Path, *profiles: str) -> None:
    seed_activation_ledger(root, deactivated_agent_profiles=list(profiles))


def _profiles(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> Any:
    monkeypatch.setattr(profiles_cmd, "find_repo_root", lambda: root)
    result = _RUNNER.invoke(profiles_cmd.app, [*args, "--json"])
    return result.exit_code, json.loads(result.output)


def test_profiles_list_omits_a_denied_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    _code, rows = _profiles(root, monkeypatch, "list")
    assert _PROFILE in {row["profile_id"] for row in rows}

    _deny_profile(root, _PROFILE)
    _code, rows = _profiles(root, monkeypatch, "list")
    assert _PROFILE not in {row["profile_id"] for row in rows}
    _code, annotated = _profiles(root, monkeypatch, "list", "--all")
    states = {row["profile_id"]: row["state"] for row in annotated}
    assert states[_PROFILE] == "available"
    assert states[_DEFAULT_PROFILE] == "activated"


def test_profiles_show_refuses_a_denied_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    code, payload = _profiles(root, monkeypatch, "show", _PROFILE)
    assert code == 0 and payload["profile_id"] == _PROFILE

    _deny_profile(root, _PROFILE)
    code, payload = _profiles(root, monkeypatch, "show", _PROFILE)
    assert code == 1
    assert payload["error"] == "profile_not_activated"
    assert _PROFILE not in payload["activated_candidates"]


def test_invocation_registry_omits_a_denied_profile(tmp_path: Path) -> None:
    root = _project(tmp_path)
    assert _PROFILE in {profile.profile_id for profile in ProfileRegistry(root).list_all()}

    _deny_profile(root, _PROFILE)
    assert _PROFILE not in {profile.profile_id for profile in ProfileRegistry(root).list_all()}


@pytest.mark.parametrize("resolver", ["resolve", "resolve_local"])
def test_invocation_registry_resolution_refuses_a_denied_profile(tmp_path: Path, resolver: str) -> None:
    """WP06 closeout LOW: ``resolve`` and ``resolve_local`` refuse a denied profile, not only ``list_all``."""
    root = _project(tmp_path)
    assert getattr(ProfileRegistry(root), resolver)(_PROFILE).profile_id == _PROFILE  # positive control

    _deny_profile(root, _PROFILE)
    with pytest.raises(ProfileNotFoundError):
        getattr(ProfileRegistry(root), resolver)(_PROFILE)


def test_an_agent_profile_deny_disengages_the_empty_charter_fallback(tmp_path: Path) -> None:
    """A deny entry is explicit configuration: the fallback must not pin a profile the charter excluded."""
    root = _project(tmp_path)
    assert is_charter_empty(root) is True

    _deny_profile(root, GENERIC_AGENT_ID)
    assert is_charter_empty(root) is False


def test_implement_precondition_refuses_a_denied_profile(tmp_path: Path) -> None:
    root = _project(tmp_path)
    wp: Any = SimpleNamespace(frontmatter=f"---\nagent_profile: {_PROFILE}\n---\n")
    implement_check_wp_charter_precondition(root, wp, "01")

    _deny_profile(root, _PROFILE)
    with pytest.raises(CharterActivationError, match=f"charter activate agent-profile {_PROFILE}"):
        implement_check_wp_charter_precondition(root, wp, "01")


def test_finalize_bootstrap_gate_refuses_a_denied_profile(tmp_path: Path) -> None:
    root = _project(tmp_path)
    meta: Any = SimpleNamespace(agent_profile=_PROFILE)
    _enforce_charter_activation_gate(meta, "WP01", root)

    _deny_profile(root, _PROFILE)
    with pytest.raises(CharterActivationError, match=_PROFILE):
        _enforce_charter_activation_gate(meta, "WP01", root)


def test_preflight_warns_for_a_denied_mission_default_profile(tmp_path: Path) -> None:
    root = _project(tmp_path)
    assert _deactivated_mission_default_profile_warnings(root) == []

    _deny_profile(root, _DEFAULT_PROFILE)
    warnings = _deactivated_mission_default_profile_warnings(root)
    assert len(warnings) == 1 and _DEFAULT_PROFILE in warnings[0]


def test_tasks_status_keeps_the_structural_marker_of_a_denied_sentinel(tmp_path: Path) -> None:
    """The 👤 marker reads ``profile.sentinel``, a structural property: deny no more hides it than narrowing does."""
    root = _project(tmp_path)
    assert _get_hic_marker(_HIC, root) == "👤 "

    _deny_profile(root, _HIC)
    assert _get_hic_marker(_HIC, root) == "👤 "


def _list_row(root: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> dict[str, Any]:
    monkeypatch.chdir(root)
    result = _RUNNER.invoke(charter_app, ["list", "--json"])
    assert result.exit_code == 0, result.output
    rows = {row["kind"]: row for row in json.loads(result.output)["kinds"]}
    return rows[kind]


def test_charter_list_shows_the_deactivated_column(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    assert _list_row(root, monkeypatch, "agent-profile")["deactivated"] == []

    _deny_profile(root, _PROFILE)
    assert _list_row(root, monkeypatch, "agent-profile")["deactivated"] == [_PROFILE]
    assert _list_row(root, monkeypatch, "directive")["deactivated"] == []

    monkeypatch.chdir(root)
    human = _RUNNER.invoke(charter_app, ["list"])
    assert human.exit_code == 0, human.output
    assert "Deactivated" in human.output and _PROFILE in human.output
