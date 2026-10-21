"""``charter deactivate`` refuses an unmigrated project in its own guard (FR-017 hole 2, NFR-001).

``deactivate._refuse_unmigrated`` is the command's own refusal. The activation
write target in ``pack_manager`` refuses the same project too, so an outcome-only
test cannot tell the two apart. These in-process tests pin the guard itself: the
refusal names ``spec-kitty upgrade``, writes nothing, and fires before the
pack-config validation, the required-floor read and the manager call. The same
fixture with a ledger beside it (positive control, F15) deactivates and does
reach the floor read, so the spies are live.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from charter.activation import pack_manager
from charter.activation.activation_ledger import UNMIGRATED_REMEDY
from kernel.activation_ledger_store import activation_ledger_path
from specify_cli.cli.commands.charter import charter_app
from specify_cli.cli.commands.charter import deactivate as deactivate_module
from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

pytestmark = [pytest.mark.fast]

_RUNNER = CliRunner()

#: Built-in directive stems (``packs/built-in/directives``).
_D = "003-decision-documentation-requirement"
_OTHER = "010-specification-fidelity-requirement"
#: A built-in agent profile with exclusive cascade children (as in ``test_deactivate_records_exclusion``).
_PARENT = "randy-reducer"
_LEGACY_CONFIG = f"mission_type_activations:\n- software-dev\nactivated_directives:\n- {_D}\n- {_OTHER}\n"
_ACTIVATION_FILES = (Path(".kittify", "config.yaml"), Path(".kittify", "charter", "charter.yaml"), Path(".kittify", "charter", "activation.yaml"))
_PATHS = pytest.mark.parametrize(
    "args",
    [("directive", _D), ("--cascade", "all", "agent-profile", _PARENT)],
    ids=["direct", "cascade"],
)


def _unmigrated(tmp_path: Path) -> Path:
    """Legacy activation keys in ``config.yaml`` and no ledger: an unmigrated project."""
    (tmp_path / ".kittify").mkdir(parents=True)
    (tmp_path / ".kittify" / "config.yaml").write_text(_LEGACY_CONFIG, encoding="utf-8")
    return tmp_path


def _snapshot(root: Path) -> dict[Path, bytes | None]:
    return {rel: (root / rel).read_bytes() if (root / rel).exists() else None for rel in _ACTIVATION_FILES}


def _deactivate(root: Path, *args: str) -> Result:
    return _RUNNER.invoke(charter_app, ["deactivate", "--repo-root", str(root), "--no-compile", *args])


def _flat(result: Result) -> str:
    return " ".join(result.output.split())


class _Spies:
    """Call recorders around the steps that run after the guard; each delegates to the real step."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.calls: dict[str, int] = {"floor": 0, "validate": 0, "manager": 0}
        monkeypatch.setattr(pack_manager, "read_org_required_provenance", self._wrap("floor", pack_manager.read_org_required_provenance))
        monkeypatch.setattr(deactivate_module, "validate_pack_config", self._wrap("validate", deactivate_module.validate_pack_config))
        monkeypatch.setattr(pack_manager.ActiveCharterManager, "deactivate", self._wrap("manager", pack_manager.ActiveCharterManager.deactivate))

    def _wrap(self, name: str, real: Callable[..., Any]) -> Callable[..., Any]:
        def spy(*args: Any, **kwargs: Any) -> Any:
            self.calls[name] += 1
            return real(*args, **kwargs)

        return spy


@_PATHS
def test_the_guard_refuses_before_the_floor_read_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: tuple[str, ...]) -> None:
    root = _unmigrated(tmp_path)
    spies = _Spies(monkeypatch)
    before = _snapshot(root)

    result = _deactivate(root, *args)

    assert result.exit_code == 1, result.output
    flat = _flat(result)
    assert "ACTIVE_CHARTER_CONFIG_INVALID" in flat
    assert "have not been moved to" in flat
    assert " ".join(UNMIGRATED_REMEDY.split()) in flat
    assert "spec-kitty upgrade" in flat
    assert flat.endswith("Nothing was written.")
    # The command's own guard answered: nothing after it ran.
    assert spies.calls == {"floor": 0, "validate": 0, "manager": 0}
    assert _snapshot(root) == before
    assert not activation_ledger_path(root).exists()


@_PATHS
def test_positive_control_the_same_fixture_with_a_ledger_deactivates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: tuple[str, ...]) -> None:
    root = _unmigrated(tmp_path)
    seed_activation_ledger(root, mission_type_activations=["software-dev"], activated_directives=[_D, _OTHER])
    spies = _Spies(monkeypatch)

    result = _deactivate(root, *args)

    assert result.exit_code == 0, result.output
    assert "spec-kitty upgrade" not in _flat(result)
    assert spies.calls["validate"] == 1
    assert spies.calls["manager"] >= 1
    assert spies.calls["floor"] >= 1, "the floor spy is live: a migrated deactivation reads the required floor"
    ledger = read_activation_ledger(root)
    assert args[-1] in (ledger.get("deactivated_directives", []) + ledger.get("deactivated_agent_profiles", []))


def test_a_mission_type_deactivation_is_not_refused_by_the_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A mission-type deactivation records no deny entry (D-11), so the guard lets it through."""
    root = _unmigrated(tmp_path)
    refusals: list[Path] = []
    monkeypatch.setattr(deactivate_module, "refuse_unmigrated_deny_write", refusals.append)

    deactivate_module._refuse_unmigrated("mission-type", root)
    deactivate_module._refuse_unmigrated("directive", root)

    assert refusals == [root]
