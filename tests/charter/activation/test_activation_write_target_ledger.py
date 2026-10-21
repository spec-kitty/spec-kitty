"""The activation write target in the one mode (WP03, WP14; FR-001, FR-017, C-003, NFR-001).

* with a ledger present, :func:`resolve_activation_write_target` returns the
  ledger path and a save that takes ``commit_plan``'s positional
  ``(path, data)`` call plus a ``deny_change=`` keyword;
* a fresh project (no ledger, no legacy key) writes the ledger;
* a legacy save (inside the upgrade scope, or on an unmigrated project) refuses
  a change to a deny entry and accepts a ``deny_change`` with no delta (C-003,
  hole 1); the dangling-pointer text of the write side is unchanged;
* an unmigrated project keeps its legacy target and reads, through ``charter
  context`` too, writing nothing (NFR-001); no ledger is created (hole 3).
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import Result
from typer.testing import CliRunner

from charter.activation.activation_ledger import ActiveCharterConfigError, DenyListChoice, DenyListWriteRefused
from charter.activation.invocation_context import ProjectContext
from charter.activation.pack_context import PackContext
from charter.activation.pack_manager import ActiveCharterManager, prepare_activation_write, resolve_activation_write_target
from charter.activation.charter_yaml_io import apply_yaml_write
from kernel.activation_ledger_store import legacy_activation_scope, activation_ledger_path
from tests._factories.activation_ledger import legacy_seed, read_activation_ledger, seed_activation_ledger

pytestmark = [pytest.mark.fast]

_RUNNER = CliRunner()
_CONFIG = Path(".kittify", "config.yaml")
_CHARTER = Path(".kittify", "charter", "charter.yaml")


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Ledger present: the ledger triple
# --------------------------------------------------------------------------- #


def test_ledger_present_targets_the_ledger(tmp_path: Path) -> None:
    ledger = seed_activation_ledger(tmp_path, activated_tactics=["t1"], mission_type_activations=["software-dev"])

    target, data, _save = resolve_activation_write_target(tmp_path)

    assert target == ledger
    assert dict(data) == {"activated_tactics": ["t1"], "mission_type_activations": ["software-dev"]}


def test_ledger_save_accepts_commit_plans_positional_call(tmp_path: Path) -> None:
    seed_activation_ledger(tmp_path, activated_tactics=["t1"], mission_type_activations=["software-dev"])
    target, data, save = resolve_activation_write_target(tmp_path)

    data["activated_tactics"] = ["t1", "t2"]
    del data["mission_type_activations"]
    save(target, data)

    assert read_activation_ledger(tmp_path) == {"activated_tactics": ["t1", "t2"]}


def test_ledger_save_takes_deny_change_by_keyword(tmp_path: Path) -> None:
    seed_activation_ledger(tmp_path, activated_tactics=["t1", "t2"])
    target, data, save = resolve_activation_write_target(tmp_path)

    data["activated_tactics"] = ["t1"]
    data["deactivated_tactics"] = ["t2"]
    save(target, data, deny_change=DenyListChoice.DEACTIVATE)

    assert read_activation_ledger(tmp_path) == {"activated_tactics": ["t1"], "deactivated_tactics": ["t2"]}


def test_ledger_save_without_a_choice_refuses_a_deny_change(tmp_path: Path) -> None:
    ledger = seed_activation_ledger(tmp_path, activated_tactics=["t1"])
    before = ledger.read_bytes()
    target, data, save = resolve_activation_write_target(tmp_path)

    data["deactivated_tactics"] = ["t1"]
    with pytest.raises(DenyListWriteRefused):
        save(target, data)

    assert ledger.read_bytes() == before


def test_ledger_save_refuses_when_the_ledger_changed_since_the_triple_loaded_it(tmp_path: Path) -> None:
    """A concurrent deactivation between load and save is not read as a removal and dropped."""
    ledger = seed_activation_ledger(tmp_path, activated_tactics=["t1", "t2"])
    target, data, save = resolve_activation_write_target(tmp_path)
    ledger.write_text("activated_tactics:\n- t1\n- t2\ndeactivated_directives:\n- x\n", encoding="utf-8")
    concurrent = ledger.read_bytes()

    data["activated_tactics"] = ["t1"]
    data["deactivated_tactics"] = ["t2"]
    with pytest.raises(ValueError, match="precondition_changed"):
        save(target, data, deny_change=DenyListChoice.DEACTIVATE)

    assert ledger.read_bytes() == concurrent


def test_fresh_project_writes_the_ledger(tmp_path: Path) -> None:
    config = _write(tmp_path / _CONFIG, "vcs:\n  type: git\n")
    before = config.read_bytes()

    target, data, save = resolve_activation_write_target(tmp_path)
    assert target == activation_ledger_path(tmp_path)
    assert dict(data) == {}

    data["mission_type_activations"] = ["software-dev"]
    save(target, data)

    assert read_activation_ledger(tmp_path) == {"mission_type_activations": ["software-dev"]}
    assert config.read_bytes() == before


def test_prepare_activation_write_targets_the_ledger_with_a_deny_change(tmp_path: Path) -> None:
    seed_activation_ledger(tmp_path, activated_tactics=["t1", "t2"])

    prepared = prepare_activation_write(tmp_path, {"activated_tactics": ["t1"], "deactivated_tactics": ["t2"]}, deny_change=DenyListChoice.DEACTIVATE)
    assert prepared.target == activation_ledger_path(tmp_path)
    apply_yaml_write(prepared)

    assert read_activation_ledger(tmp_path) == {"activated_tactics": ["t1"], "deactivated_tactics": ["t2"]}


def test_prepare_activation_write_without_a_choice_refuses_a_deny_change(tmp_path: Path) -> None:
    seed_activation_ledger(tmp_path, activated_tactics=["t1"])

    with pytest.raises(DenyListWriteRefused):
        prepare_activation_write(tmp_path, {"deactivated_tactics": ["t1"]})


def test_list_activated_reads_the_ledger(tmp_path: Path) -> None:
    seed_activation_ledger(tmp_path, activated_tactics=["t1"], deactivated_directives=["D1"])

    listed = ActiveCharterManager().list_activated(ProjectContext.from_repo(tmp_path))

    assert listed["tactic"] == frozenset({"t1"})
    assert listed["directive"] is None


def test_pack_context_reads_the_ledger(tmp_path: Path) -> None:
    seed_activation_ledger(tmp_path, activated_tactics=["t1"], mission_type_activations=["software-dev"])

    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_tactics == frozenset({"t1"})
    assert ctx.activated_mission_types == frozenset({"software-dev"})


# --------------------------------------------------------------------------- #
# Legacy saves (C-003, hole 1): in the upgrade scope and on an unmigrated project
# --------------------------------------------------------------------------- #

_SCOPES = [pytest.param(True, id="upgrade-scope"), pytest.param(False, id="unmigrated")]
_SURFACES = ["charter_yaml", "config_yaml"]


def _scope(repo: Path, in_scope: bool) -> contextlib.AbstractContextManager[None]:
    return legacy_activation_scope(repo) if in_scope else contextlib.nullcontext()


@pytest.mark.parametrize("in_scope", _SCOPES)
@pytest.mark.parametrize("surface", _SURFACES)
def test_legacy_save_refuses_a_deny_change(tmp_path: Path, surface: str, in_scope: bool) -> None:
    legacy = legacy_seed(tmp_path, surface=surface, activated_tactics=["t1"])
    before = legacy.read_bytes()
    with _scope(tmp_path, in_scope):
        target, data, save = resolve_activation_write_target(tmp_path)
        assert target == legacy
        data["deactivated_tactics"] = ["t1"]
        with pytest.raises(ActiveCharterConfigError) as caught:
            save(target, data, deny_change=DenyListChoice.DEACTIVATE)
    assert "deactivated_tactics" in caught.value.body
    assert "spec-kitty migrate activation-ledger" in caught.value.body
    assert legacy.read_bytes() == before
    assert not activation_ledger_path(tmp_path).exists()


@pytest.mark.parametrize("in_scope", _SCOPES)
@pytest.mark.parametrize("surface", _SURFACES)
def test_legacy_save_accepts_a_deny_choice_that_changes_nothing(tmp_path: Path, surface: str, in_scope: bool) -> None:
    """Hole 1: ``charter activate`` and ``--preset --force`` pass a choice that clears nothing here."""
    legacy = legacy_seed(tmp_path, surface=surface, activated_tactics=["t1"])
    with _scope(tmp_path, in_scope):
        target, data, save = resolve_activation_write_target(tmp_path)
        data["activated_tactics"] = ["t1", "t2"]
        save(target, data, deny_change=DenyListChoice.ACTIVATE)
    text = legacy.read_text(encoding="utf-8")
    assert "t2" in text
    assert "deactivated_" not in text
    assert not activation_ledger_path(tmp_path).exists()


@pytest.mark.parametrize("surface", _SURFACES)
def test_legacy_save_keeps_a_hand_edited_deny_key_it_does_not_change(tmp_path: Path, surface: str) -> None:
    """A legacy deny key already on disk (never applied, hole 6) is not a delta: an allow-only save passes."""
    legacy = legacy_seed(tmp_path, surface=surface, activated_tactics=["t1"], deactivated_tactics=["t9"])
    target, data, save = resolve_activation_write_target(tmp_path)
    data["activated_tactics"] = ["t1", "t2"]
    save(target, data)
    assert "t2" in legacy.read_text(encoding="utf-8")


@pytest.mark.parametrize("in_scope", _SCOPES)
def test_legacy_prepare_activation_write_refuses_a_deny_key(tmp_path: Path, in_scope: bool) -> None:
    legacy = legacy_seed(tmp_path, activated_tactics=["t1"])
    before = legacy.read_bytes()
    with _scope(tmp_path, in_scope), pytest.raises(ActiveCharterConfigError) as caught:
        prepare_activation_write(tmp_path, {"deactivated_tactics": ["t1"]}, deny_change=DenyListChoice.DEACTIVATE)
    assert "deactivated_tactics" in caught.value.body
    assert legacy.read_bytes() == before


def test_legacy_prepare_activation_write_drops_a_deny_key_that_changes_nothing(tmp_path: Path) -> None:
    legacy = legacy_seed(tmp_path, activated_tactics=["t1"])
    prepared = prepare_activation_write(tmp_path, {"activated_tactics": ["t1", "t2"], "deactivated_tactics": None}, deny_change=DenyListChoice.ACTIVATE)
    assert prepared.target == legacy
    assert b"deactivated_" not in prepared.desired_bytes
    assert b"t2" in prepared.desired_bytes


def test_dangling_pointer_write_text_is_unchanged(tmp_path: Path) -> None:
    _write(tmp_path / _CONFIG, "charter: .kittify/charter/missing.yaml\n")
    missing = tmp_path / ".kittify" / "charter" / "missing.yaml"
    with legacy_activation_scope(tmp_path), pytest.raises(ActiveCharterConfigError) as caught:
        resolve_activation_write_target(tmp_path)
    assert caught.value.body == (
        f".kittify/config.yaml 'charter:' pointer names {missing}, "
        f"which does not exist.\nRemediation: run the charter-bundle "
        f"migration (`spec-kitty upgrade`) to (re)generate it, or fix "
        f"the 'charter:' pointer."
    )


# --------------------------------------------------------------------------- #
# Unmigrated: the legacy target and reads, nothing written (NFR-001), positive control
# --------------------------------------------------------------------------- #


def _unmigrated_fixture(repo: Path) -> tuple[Path, ...]:
    """A pointer ``config.yaml`` and a ``charter.yaml`` carrying legacy activation keys, no ledger."""
    _write(repo / _CONFIG, "charter: .kittify/charter/charter.yaml\n")
    _write(repo / _CHARTER, "mission_type_activations: [software-dev]\nactivated_tactics: [tdd-red-green-refactor]\n")
    return (repo / _CONFIG, repo / _CHARTER, activation_ledger_path(repo))


def _snapshot(paths: tuple[Path, ...]) -> tuple[bytes | None, ...]:
    return tuple(path.read_bytes() if path.exists() else None for path in paths)


def _charter_context(repo: Path) -> Result:
    import specify_cli.cli.commands.charter as charter_pkg
    from specify_cli.cli.commands.charter import app as charter_app

    args = ["context", "--action", "implement", "--mission-type", "software-dev", "--json"]
    with contextlib.chdir(repo), patch.object(charter_pkg, "find_repo_root", return_value=repo):
        return _RUNNER.invoke(charter_app, args)


def test_unmigrated_write_target_is_the_legacy_surface(tmp_path: Path) -> None:
    files = _unmigrated_fixture(tmp_path)
    before = _snapshot(files)

    target, data, _save = resolve_activation_write_target(tmp_path)
    assert target == tmp_path / _CHARTER
    assert data["activated_tactics"] == ["tdd-red-green-refactor"]

    assert _snapshot(files) == before


def test_unmigrated_charter_context_reads_the_legacy_keys_and_writes_nothing(tmp_path: Path) -> None:
    files = _unmigrated_fixture(tmp_path)
    before = _snapshot(files)

    result = _charter_context(tmp_path)

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["success"] is True
    assert _snapshot(files) == before


def test_same_fixture_reads_once_its_keys_are_in_the_ledger(tmp_path: Path) -> None:
    """F15 positive control: the same fixture also reads from the ledger once its keys are moved."""
    _unmigrated_fixture(tmp_path)
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"], activated_tactics=["tdd-red-green-refactor"])
    _write(tmp_path / _CHARTER, "{}\n")

    result = _charter_context(tmp_path)

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["success"] is True


# --------------------------------------------------------------------------- #
# Helpers behind the re-pointing: the kernel pointer rule, the SPDD probe
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), ({"synthesis_inputs": {}}, None), (".kittify/charter/charter.yaml", ".kittify/charter/charter.yaml")],
    ids=["absent", "inline-mapping", "relative"],
)
def test_legacy_pointer_path_is_the_one_pointer_rule(tmp_path: Path, value: object, expected: str | None) -> None:
    from charter.activation.pack_context import resolve_charter_yaml_pointer
    from kernel.activation_ledger_store import legacy_pointer_path

    want = None if expected is None else tmp_path / expected
    assert legacy_pointer_path(tmp_path, value) == want
    assert resolve_charter_yaml_pointer(tmp_path, {"charter": value} if value is not None else {}) == want


def test_legacy_pointer_path_keeps_an_absolute_pointer(tmp_path: Path) -> None:
    from kernel.activation_ledger_store import legacy_pointer_path

    absolute = tmp_path / "elsewhere" / "charter.yaml"
    assert legacy_pointer_path(tmp_path / "repo", str(absolute)) == absolute


def test_spdd_probe_reads_an_unmigrated_project_like_the_upgrade_scope(tmp_path: Path) -> None:
    from charter.offering.spdd_reasons.activation import is_spdd_reasons_active

    _unmigrated_fixture(tmp_path)
    with legacy_activation_scope(tmp_path):
        in_scope = is_spdd_reasons_active(tmp_path)
    assert is_spdd_reasons_active(tmp_path) is in_scope


def test_spdd_probe_never_applies_a_legacy_deny_key(tmp_path: Path) -> None:
    """Hole 6: a ``deactivated_directives`` on a legacy surface does not turn the probe off; on the ledger it does."""
    from charter.offering.spdd_reasons.activation import is_spdd_reasons_active

    allow = "activated_paradigms: []\nactivated_tactics: []\nactivated_directives: [038-structured-prompt-boundary]\n"
    deny = "deactivated_directives: [038-structured-prompt-boundary]\n"
    _write(tmp_path / _CONFIG, allow)
    assert is_spdd_reasons_active(tmp_path) is True  # positive control
    _write(tmp_path / _CONFIG, allow + deny)
    assert is_spdd_reasons_active(tmp_path) is True
    _write(tmp_path / _CONFIG, "agents: {}\n")
    seed_activation_ledger(
        tmp_path,
        activated_paradigms=[],
        activated_tactics=[],
        activated_directives=["038-structured-prompt-boundary"],
        deactivated_directives=["038-structured-prompt-boundary"],
    )
    assert is_spdd_reasons_active(tmp_path) is False  # the same deny on the ledger applies


def test_spdd_probe_reports_a_malformed_ledger(tmp_path: Path) -> None:
    from charter.offering.spdd_reasons.activation import _SpddActivationConfigError, is_spdd_reasons_active

    _write(tmp_path / _CONFIG, "vcs:\n  type: git\n")
    _write(activation_ledger_path(tmp_path), "- not\n- a mapping\n")
    with pytest.raises(_SpddActivationConfigError, match="root must be a mapping"):
        is_spdd_reasons_active(tmp_path)


def test_spdd_probe_reports_a_malformed_pointed_charter_beside_a_ledger(tmp_path: Path) -> None:
    from charter.offering.spdd_reasons.activation import _SpddActivationConfigError, is_spdd_reasons_active

    _write(tmp_path / _CONFIG, "charter: .kittify/charter/charter.yaml\n")
    _write(tmp_path / _CHARTER, "a: [unclosed\n")
    seed_activation_ledger(tmp_path, activated_paradigms=[])
    with pytest.raises(_SpddActivationConfigError, match="Invalid YAML"):
        is_spdd_reasons_active(tmp_path)
