"""``charter deactivate`` records an exclusion (WP04: US1.1, US1.2, US4.1, US4.3, FR-007, FR-012, FR-013, NFR-001).

Every case is ledger-seeded. Each refusal case first deactivates a non-required id on the
same fixture (positive control, F15), then proves the refusal leaves every
activation file byte-identical (NFR-001).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from kernel.activation_ledger_store import activation_ledger_path
from specify_cli.cli.commands.charter import charter_app
from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

pytestmark = [pytest.mark.fast]

_RUNNER = CliRunner()

#: Built-in directive stems (``packs/built-in/directives``).
_A = "001-architectural-integrity-standard"
_D = "003-decision-documentation-requirement"
_OTHER = "010-specification-fidelity-requirement"
_D_DECLARED = "DIRECTIVE_003"
_ACTIVATION_FILES = (Path(".kittify", "config.yaml"), Path(".kittify", "charter", "charter.yaml"), Path(".kittify", "charter", "activation.yaml"))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def _project(tmp_path: Path, *, packs: dict[str, str] | None = None, **ledger: list[str]) -> Path:
    """A ledger-seeded project; *packs* maps an org pack name to its ``org-charter.yaml`` body."""
    lines = []
    if packs:
        lines += ["charter_packs:", "  org:", "    packs:"]
        for name, body in packs.items():
            _write(tmp_path / "org-packs" / name / "org-charter.yaml", body)
            lines += [f"      - name: {name}", f"        local_path: org-packs/{name}"]
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"], **ledger)
    return tmp_path


def _deactivate(root: Path, *args: str) -> Result:
    return _RUNNER.invoke(charter_app, ["deactivate", "--repo-root", str(root), "--no-compile", *args])


def _snapshot(root: Path) -> dict[Path, bytes | None]:
    return {rel: (root / rel).read_bytes() if (root / rel).exists() else None for rel in _ACTIVATION_FILES}


def _flat(result: Result) -> str:
    return " ".join(result.output.split())


_ACME_REQUIRES_D = f"""
    schema_version: 1
    org_name: Acme
    required_directives:
      - {_D_DECLARED}
"""


# --------------------------------------------------------------------------- #
# US1.1 / US1.2: an exclusion is recorded
# --------------------------------------------------------------------------- #


def test_absent_allow_list_records_an_exclusion(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = _deactivate(root, "directive", _D)

    assert result.exit_code == 0, result.output
    ledger = read_activation_ledger(root)
    assert ledger["deactivated_directives"] == [_D]
    assert "activated_directives" not in ledger


def test_present_allow_list_loses_the_id_and_records_it(tmp_path: Path) -> None:
    root = _project(tmp_path, activated_directives=[_A, _D])

    result = _deactivate(root, "directive", _D)

    assert result.exit_code == 0, result.output
    ledger = read_activation_ledger(root)
    assert ledger["activated_directives"] == [_A]
    assert ledger["deactivated_directives"] == [_D]


def test_a_declared_id_is_recorded_in_stem_spelling(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = _deactivate(root, "directive", _D_DECLARED)

    assert result.exit_code == 0, result.output
    assert read_activation_ledger(root)["deactivated_directives"] == [_D]


# --------------------------------------------------------------------------- #
# US4.1 / FR-013: refusals, each with a same-fixture positive control
# --------------------------------------------------------------------------- #


def test_an_org_required_id_is_refused_and_nothing_is_written(tmp_path: Path) -> None:
    root = _project(tmp_path, packs={"acme": _ACME_REQUIRES_D})
    control = _deactivate(root, "directive", _A)
    assert control.exit_code == 0, control.output
    assert read_activation_ledger(root)["deactivated_directives"] == [_A]
    before = _snapshot(root)

    result = _deactivate(root, "directive", _D)

    assert result.exit_code != 0
    assert "acme" in result.output
    assert "required_directives" in result.output
    assert "Nothing was recorded" in _flat(result)
    assert _snapshot(root) == before


def test_a_required_id_named_by_its_declared_id_is_refused(tmp_path: Path) -> None:
    root = _project(tmp_path, packs={"acme": _ACME_REQUIRES_D})
    assert _deactivate(root, "directive", _A).exit_code == 0
    before = _snapshot(root)

    result = _deactivate(root, "directive", _D_DECLARED)

    assert result.exit_code != 0
    assert "acme" in result.output
    assert _snapshot(root) == before


def test_a_requirement_inherited_through_extends_is_refused_naming_both_packs(tmp_path: Path) -> None:
    overlay = """
        schema_version: 1
        extends: base
        org_name: Overlay
    """
    root = _project(tmp_path, packs={"base": _ACME_REQUIRES_D, "overlay": overlay})
    assert _deactivate(root, "directive", _A).exit_code == 0
    before = _snapshot(root)

    result = _deactivate(root, "directive", _D)

    assert result.exit_code != 0
    assert "base" in result.output
    assert "overlay" in result.output
    assert _snapshot(root) == before


def test_already_denied_warns_and_writes_nothing(tmp_path: Path) -> None:
    root = _project(tmp_path)
    assert _deactivate(root, "directive", _A).exit_code == 0
    before = _snapshot(root)

    result = _deactivate(root, "directive", _A)

    assert result.exit_code == 0, result.output
    assert "already deactivated" in _flat(result)
    assert _snapshot(root) == before


def test_an_unknown_id_is_refused_and_nothing_is_written(tmp_path: Path) -> None:
    root = _project(tmp_path)
    assert _deactivate(root, "directive", _A).exit_code == 0
    before = _snapshot(root)

    result = _deactivate(root, "directive", "no-such-directive")

    assert result.exit_code == 1
    assert "Unknown directive ID 'no-such-directive'" in _flat(result)
    assert _snapshot(root) == before


def test_a_malformed_declared_org_pack_refuses(tmp_path: Path) -> None:
    root = _project(tmp_path, packs={"acme": "schema_version: 1\n"})
    assert _deactivate(root, "directive", _A).exit_code == 0
    (root / "org-packs" / "acme" / "org-charter.yaml").write_text("required_directives: [unclosed\n", encoding="utf-8")
    before = _snapshot(root)

    result = _deactivate(root, "directive", _OTHER)

    assert result.exit_code == 1
    assert "acme" in result.output
    assert _snapshot(root) == before


def test_an_extends_cycle_refuses(tmp_path: Path) -> None:
    root = _project(tmp_path, packs={"one": "schema_version: 1\n", "two": "schema_version: 1\n"})
    assert _deactivate(root, "directive", _A).exit_code == 0
    _write(root / "org-packs" / "one" / "org-charter.yaml", "schema_version: 1\nextends: two\n")
    _write(root / "org-packs" / "two" / "org-charter.yaml", "schema_version: 1\nextends: one\n")
    before = _snapshot(root)

    result = _deactivate(root, "directive", _OTHER)

    assert result.exit_code == 1
    assert "Cycle" in result.output or "cycle" in result.output
    assert _snapshot(root) == before


# --------------------------------------------------------------------------- #
# FR-012 / US4.3: cascade deactivation records only the named id
# --------------------------------------------------------------------------- #

#: A built-in agent profile whose shipped DRG references tactics no other node reaches
#: (exclusive cascade children).
_PARENT = "randy-reducer"
_CHILD = "semantic-compression-semantic-consolidation"


def test_cascade_under_an_absent_allow_list_records_only_the_named_id(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = _deactivate(root, "--cascade", "all", "agent-profile", _PARENT)

    assert result.exit_code == 0, result.output
    assert read_activation_ledger(root) == {"mission_type_activations": ["software-dev"], "deactivated_agent_profiles": [_PARENT]}
    assert f"tactic/{_CHILD}: still active (no allow-list; only {_PARENT} excluded)" in _flat(result)


def test_cascade_drops_an_exclusive_child_from_a_present_list_without_an_exclusion(tmp_path: Path) -> None:
    root = _project(tmp_path, activated_tactics=[_CHILD, "adversarial-qa-handoff"])

    result = _deactivate(root, "--cascade", "all", "agent-profile", _PARENT)

    assert result.exit_code == 0, result.output
    ledger = read_activation_ledger(root)
    assert ledger["activated_tactics"] == ["adversarial-qa-handoff"]
    assert ledger["deactivated_agent_profiles"] == [_PARENT]
    assert "deactivated_tactics" not in ledger


def test_cascade_reaching_a_required_child_skips_it_naming_the_pack(tmp_path: Path) -> None:
    acme = f"""
        schema_version: 1
        required_tactics:
          - {_CHILD}
    """
    root = _project(tmp_path, packs={"acme": acme}, activated_tactics=[_CHILD])

    result = _deactivate(root, "--cascade", "all", "agent-profile", _PARENT)

    assert result.exit_code == 0, result.output
    assert f"tactic/{_CHILD}: skipped (required by acme)" in _flat(result)
    ledger = read_activation_ledger(root)
    assert ledger["activated_tactics"] == [_CHILD]
    assert ledger["deactivated_agent_profiles"] == [_PARENT]
    assert "deactivated_tactics" not in ledger


def test_the_ledger_path_is_the_only_file_a_deactivation_writes(tmp_path: Path) -> None:
    root = _project(tmp_path)
    config_before = (root / ".kittify" / "config.yaml").read_bytes()

    assert _deactivate(root, "directive", _D).exit_code == 0

    assert (root / ".kittify" / "config.yaml").read_bytes() == config_before
    assert not (root / ".kittify" / "charter" / "charter.yaml").exists()
    assert activation_ledger_path(root).is_file()
