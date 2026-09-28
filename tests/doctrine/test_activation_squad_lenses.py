"""Red-first regression test for #3810 — activate doctrine-daphne + randy-reducer.

The shipped charter pack's ``activated_agent_profiles`` allowlist must contain
every profile named as a lens by the canonical adversarial-squad-deployment
procedure's example casting table (the procedure is the single owner of the
squad's casting; the skill only points to it). A project
seeded from the pack otherwise reaches the profile activation gate and cannot
load that lens.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.default_pack import load_default_pack_activation_ids
from specify_cli import app as cli_app

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]

runner = CliRunner()

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROCEDURE_PATH = _REPO_ROOT / "packs" / "built-in" / "procedures" / "adversarial-squad-deployment.procedure.yaml"
_CASTING_ANCHOR = "Example casting (examples, not rules):"
_LENS_LINE_RE = re.compile(r"^\s*-\s*[a-z][a-z-]*\s*:\s*(?P<ids>(?:`[a-z][a-z0-9-]*`,?\s*)+)—", re.MULTILINE)
_ID_RE = re.compile(r"`([a-z][a-z0-9-]*)`")
_MISSING_LENSES = frozenset({"doctrine-daphne", "randy-reducer"})


def _squad_lens_ids() -> frozenset[str]:
    """Extract lens profile ids from the procedure's example casting table."""
    text = _PROCEDURE_PATH.read_text(encoding="utf-8")
    anchor_index = text.index(_CASTING_ANCHOR)
    tail = text[anchor_index:]
    ids: set[str] = set()
    for match in _LENS_LINE_RE.finditer(tail):
        ids.update(_ID_RE.findall(match.group("ids")))
    assert ids, f"expected to find lens ids in {_PROCEDURE_PATH}"
    return frozenset(ids)


def _shipped_activated_agent_profiles() -> frozenset[str]:
    """Load the shipped default pack's profile activation list."""
    ids = load_default_pack_activation_ids().get("activated_agent_profiles", [])
    return frozenset(ids)


def test_squad_lens_ids_present_in_procedure() -> None:
    """The canonical procedure must cast the two lenses that exposed #3810."""
    assert _squad_lens_ids() >= _MISSING_LENSES


def test_missing_lenses_are_activated_in_shipped_default_pack() -> None:
    """#3810: the two missing squad lenses must be in the shipped allowlist."""
    missing = _MISSING_LENSES - _shipped_activated_agent_profiles()
    assert not missing, f"src/charter/activation/packs/default.yaml activated_agent_profiles is missing squad lens(es): {sorted(missing)}"


def test_adversarial_squad_lenses_are_subset_of_activated_default_profiles() -> None:
    """Every lens cast by the procedure must be activated by the shipped pack."""
    missing = _squad_lens_ids() - _shipped_activated_agent_profiles()
    assert not missing, f"adversarial-squad-deployment procedure casts lens(es) absent from the shipped activated_agent_profiles allowlist: {sorted(missing)}"


def _write_shipped_default_config(repo_root: Path) -> None:
    """Create a project whose profile activation state matches the shipped pack."""
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    with (kittify / "config.yaml").open("w", encoding="utf-8") as handle:
        yaml.dump(
            {"activated_agent_profiles": sorted(_shipped_activated_agent_profiles())},
            handle,
        )


@pytest.mark.parametrize("profile_id", sorted(_MISSING_LENSES))
def test_profiles_show_resolves_without_exit_1(profile_id: str, tmp_path: Path) -> None:
    """The activation gate must load each formerly omitted squad lens."""
    _write_shipped_default_config(tmp_path)
    with patch("specify_cli.cli.commands.profiles_cmd.find_repo_root", return_value=tmp_path):
        result = runner.invoke(cli_app, ["profiles", "show", profile_id, "--json"])

    assert result.exit_code == 0, f"expected profile '{profile_id}' to resolve as activated; got exit {result.exit_code}: {result.output}"
