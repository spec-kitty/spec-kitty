"""``charter activate ... --only`` prints only narrow lines (#6457, FR-001..FR-004).

Under ``--only`` the absent-key preservation warnings ("initialized from ...")
describe a list that is never written, so they are not printed; a mission-type
key that was absent put nothing in force, so nothing "cannot be listed"; a kind
whose effective set cannot be resolved gets one reasoned warning and a footer
that says what dropped is unknown; and every run names the list it wrote. The written list and exit code are asserted in every
case (C-001), and the plain path on the same fixture is the positive control.
"""

from __future__ import annotations

import dataclasses
import subprocess
from collections.abc import Iterable
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner, Result

import charter.activation.effective_set as effective_set
from charter.activation.activation_engine import EffectiveSet
from specify_cli.cli.commands.charter import charter_app
from tests._factories.activation_ledger import read_activation_ledger

pytestmark = [pytest.mark.integration]

runner = CliRunner()

_TOOLGUIDES = "activated_toolguides"
_TARGET = "gherkin"
_REASON = "the test made the toolguide set unresolvable"
_UNRESOLVED = "What stopped being in force cannot be listed"


def _activate(root: Path, *args: str) -> Result:
    return runner.invoke(charter_app, ["activate", "--repo-root", str(root), "--no-compile", *args], catch_exceptions=False)


def _flat(output: str) -> str:
    return " ".join(output.split())


def _written(root: Path, key: str) -> list[str] | None:
    """*key* as written, from the activation ledger or (unmigrated project) ``config.yaml``."""
    ledger = read_activation_ledger(root)
    source = ledger if key in ledger else YAML(typ="safe").load((root / ".kittify" / "config.yaml").read_text(encoding="utf-8")) or {}
    value = source.get(key)
    return None if value is None else [str(item) for item in value]


def _empty_project(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("charter_packs: {}\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def unresolvable_toolguides(monkeypatch: pytest.MonkeyPatch) -> None:
    """The effective toolguide set cannot be resolved (seeded from the real ids, with a known reason)."""
    real = effective_set.resolve_effective_sets

    def resolve(repo_root: Path, yaml_keys: Iterable[str]) -> dict[str, EffectiveSet]:
        sets = real(repo_root, yaml_keys)
        if _TOOLGUIDES in sets:
            entry = sets[_TOOLGUIDES]
            sets[_TOOLGUIDES] = dataclasses.replace(entry, ids=frozenset(), resolved=False, reason=_REASON, fallback_ids=entry.ids | entry.fallback_ids)
        return sets

    monkeypatch.setattr(effective_set, "resolve_effective_sets", resolve)


def test_only_on_an_absent_mission_type_key_prints_no_preservation_or_unresolved_warning(tmp_path: Path) -> None:
    root = _empty_project(tmp_path)
    assert _written(root, "mission_type_activations") is None

    result = _activate(root, "mission-type", "software-dev", "--only")

    assert result.exit_code == 0, result.output
    assert _written(root, "mission_type_activations") == ["software-dev"]
    out = _flat(result.output)
    assert "initialized from" not in out.lower()
    assert "could not be resolved" not in out
    assert "Now listed for mission-type (1): software-dev" in out
    assert "No longer in force (0): (none)" in out
    assert out.index("Now listed for") < out.index("No longer in force")


def test_plain_activation_on_an_absent_mission_type_key_still_says_what_it_initialized_from(tmp_path: Path) -> None:
    """Positive control for the mission-type case: the preservation note is the plain path's, not removed."""
    root = _empty_project(tmp_path)

    result = _activate(root, "mission-type", "software-dev")

    assert result.exit_code == 0, result.output
    written = _written(root, "mission_type_activations") or []
    assert "software-dev" in written and len(written) > 1
    out = _flat(result.output)
    assert "initialized from the" in out
    assert "Now listed for" not in out and "No longer in force" not in out


@pytest.mark.usefixtures("unresolvable_toolguides")
def test_only_on_an_unresolvable_kind_prints_exactly_one_reasoned_warning(tmp_path: Path) -> None:
    root = _empty_project(tmp_path)

    result = _activate(root, "toolguide", _TARGET, "--only")

    assert result.exit_code == 0, result.output
    assert _written(root, _TOOLGUIDES) == [_TARGET]
    out = _flat(result.output)
    assert out.count(_UNRESOLVED) == 1, out
    assert f"{_UNRESOLVED}: the effective set could not be resolved because {_REASON}." in out
    assert "initialized from" not in out.lower()
    assert f"Now listed for toolguide (1): {_TARGET}" in out
    # What dropped is not known, so the footer does not claim "(0): (none)" (Decision ``only_unknown_footer``).
    assert "No longer in force: unknown (see the warning above)" in out
    assert "No longer in force (" not in out
    assert out.index(_UNRESOLVED) < out.index("No longer in force")


@pytest.mark.usefixtures("unresolvable_toolguides")
def test_plain_activation_on_an_unresolvable_kind_keeps_the_preservation_warning(tmp_path: Path) -> None:
    """Positive control: the same fixture without ``--only`` still says what the list was initialized from."""
    root = _empty_project(tmp_path)

    result = _activate(root, "toolguide", _TARGET)

    assert result.exit_code == 0, result.output
    written = _written(root, _TOOLGUIDES) or []
    assert _TARGET in written and len(written) > 1
    out = _flat(result.output)
    assert f"could not be resolved because {_REASON}; initialized from the" in out
    assert _UNRESOLVED not in out


def test_only_on_a_present_list_names_the_written_list_with_its_count(tmp_path: Path) -> None:
    root = _empty_project(tmp_path)
    assert _activate(root, "toolguide", "sonar").exit_code == 0
    assert len(_written(root, _TOOLGUIDES) or []) > 1, "fixture invalid: the first activation must materialise a list"

    result = _activate(root, "toolguide", _TARGET, "--only")

    assert result.exit_code == 0, result.output
    assert _written(root, _TOOLGUIDES) == [_TARGET]
    out = _flat(result.output)
    assert f"Now listed for toolguide (1): {_TARGET}" in out
    assert "No longer in force (" in out and "sonar" in out
    assert out.index("Now listed for") < out.index("No longer in force")
    assert "initialized from" not in out.lower() and "could not be resolved" not in out


def test_activation_warnings_are_printed_literally_not_as_markup() -> None:
    """A warning naming a ``[bracketed]`` token is escaped, as the preset warnings are."""
    from charter.activation.api import ActivationResult
    from specify_cli.cli.commands.charter._app import console
    from specify_cli.cli.commands.charter.activate import _render_activation_result
    from charter.activation.project_registration import ProjectRegistrationPlan
    from charter.drg import load_built_in_graph

    registration = ProjectRegistrationPlan(Path("."), load_built_in_graph(), (), (), ())
    result = ActivationResult(warnings=["id [red]x[/red] kept"])
    with console.capture() as captured:
        _render_activation_result(result, registration, only=False, kind="tactic")

    assert "id [red]x[/red] kept" in captured.get()
