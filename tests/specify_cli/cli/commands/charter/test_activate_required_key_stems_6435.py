"""The required-only floor materialises activation stems, not declared ids (#6435).

An absent required-only key (``skill``) puts the org packs' ``required_skills``
in force. ``charter activate`` materialises that floor into ``activated_skills``,
and every activation writer stores one spelling: the artifact's file stem
(#6527). Before this test existed the floor was written as the raw
``required_<kind>`` **declared id**, so the list carried
``activated_skills: [acme-skill-id, other-skill-file]`` — one declared id beside
one stem.

The fixture is the same for both the materialisation case and the collision case,
so the collision refusal cannot pass by materialising nothing: the non-colliding
half proves the floor is written at all.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.integration]

runner = CliRunner()

REQUIRED_STEM, REQUIRED_ID = "acme-skill-file", "acme-skill-id"
OTHER_STEM, OTHER_ID = "other-skill-file", "other-skill-id"

_SKILL = 'schema_version: "1.0"\nid: {id}\nname: {name}\nsummary: {name} skill.\nbody: Do {name}.\n'


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _skill(pack: Path, stem: str, declared_id: str) -> None:
    _write(pack / "skills" / f"{stem}.skill.yaml", _SKILL.format(id=declared_id, name=stem))


def _project(tmp_path: Path, *, required: str | None) -> Path:
    """A project whose org pack requires *required*, declared by a file whose stem differs from its id."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    pack = tmp_path / "packs" / "acme"
    _skill(pack, REQUIRED_STEM, REQUIRED_ID)
    _skill(pack, OTHER_STEM, OTHER_ID)
    charter = f"org_name: acme\nrequired_skills:\n  - {required}\n" if required else "org_name: acme\n"
    _write(pack / "org-charter.yaml", charter)
    _write(
        tmp_path / ".kittify" / "config.yaml",
        f"mission_type_activations:\n  - software-dev\ncharter_packs:\n  org:\n    packs:\n      - name: acme\n        local_path: {pack}\n",
    )
    return tmp_path


def _activate(root: Path, *args: str):  # noqa: ANN201 — typer's Result
    return runner.invoke(charter_app, ["activate", "--repo-root", str(root), "--no-compile", *args], catch_exceptions=False)


def _listed(root: Path) -> list[str] | None:
    data = yaml.safe_load((root / ".kittify" / "config.yaml").read_text(encoding="utf-8"))
    value = data.get("activated_skills")
    return None if value is None else list(value)


def test_activating_on_an_absent_required_key_writes_the_required_stem_not_its_declared_id(tmp_path: Path) -> None:
    root = _project(tmp_path, required=REQUIRED_ID)
    assert _listed(root) is None

    result = _activate(root, "skill", OTHER_STEM)

    assert result.exit_code == 0, result.output
    written = _listed(root) or []
    # positive control on the same fixture: the required artifact IS materialised ...
    assert REQUIRED_STEM in written, written
    # ... and in the one spelling every activation writer stores (#6435, #6527).
    assert REQUIRED_ID not in written, f"a declared id was stored beside its stem: {written}"
    assert written == [REQUIRED_STEM, OTHER_STEM], written


def test_activating_the_required_artifact_by_its_declared_id_stores_its_stem(tmp_path: Path) -> None:
    root = _project(tmp_path, required=REQUIRED_ID)

    result = _activate(root, "skill", REQUIRED_ID)

    assert result.exit_code == 0, result.output
    written = _listed(root) or []
    assert REQUIRED_STEM in written, written
    assert REQUIRED_ID not in written, written


def _directive(pack: Path, stem: str, declared_id: str) -> None:
    _write(
        pack / "directives" / f"{stem}.directive.yaml",
        f'schema_version: "1.0"\nid: {declared_id}\ntitle: {stem}\nintent: Apply org policy.\nenforcement: required\n',
    )


def _directive_project(tmp_path: Path, *, shadow: bool) -> Path:
    """A project whose org pack requires ``DIRECTIVE_024``; *shadow* reuses its file name for another id."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    pack = tmp_path / "packs" / "acme"
    _directive(pack, "024-locality-of-change", "DIRECTIVE_024")
    _write(pack / "org-charter.yaml", "org_name: acme\nrequired_directives:\n  - DIRECTIVE_024\n")
    packs = [{"name": "acme", "local_path": str(pack)}]
    if shadow:
        # A second layer reuses the required directive's file name for a different id:
        # DIRECTIVE_024 then has no single stem (Decision ``file_name_collision``).
        other = tmp_path / "packs" / "zeta"
        _directive(other, "024-locality-of-change", "ZETA_024")
        _write(other / "org-charter.yaml", "org_name: zeta\n")
        packs.append({"name": "zeta", "local_path": str(other)})
    _write(
        tmp_path / ".kittify" / "config.yaml",
        yaml.safe_dump({"mission_type_activations": ["software-dev"], "charter_packs": {"org": {"packs": packs}}}),
    )
    return tmp_path


def test_a_colliding_required_id_is_still_refused_and_nothing_is_written(tmp_path: Path) -> None:
    """``file_name_collision`` survives the fix: the floor read is what refuses, before any write.

    The no-shadow case on the same fixture family is the positive control: it
    materialises the list, so the refusal is not blanket.
    """
    control = _directive_project(tmp_path / "control", shadow=False)
    assert _activate(control, "directive", "001-architectural-integrity-standard").exit_code == 0
    written = yaml.safe_load((control / ".kittify" / "config.yaml").read_text(encoding="utf-8"))["activated_directives"]
    assert "024-locality-of-change" in written and "DIRECTIVE_024" not in written, written

    root = _directive_project(tmp_path / "collision", shadow=True)

    result = _activate(root, "directive", "001-architectural-integrity-standard")

    assert result.exit_code != 0, result.output
    assert "ActivationIdCollisionError" in result.output or "file name" in result.output.lower(), result.output
    assert "activated_directives" not in (root / ".kittify" / "config.yaml").read_text(encoding="utf-8"), "a refused materialisation must write nothing"


def test_a_required_skill_inherited_through_extends_is_materialised_as_its_stem(tmp_path: Path) -> None:
    """A ``required_skills`` entry a pack inherits through ``extends:`` is not narrowed away (#6435).

    The floor must keep every required id the pack chain puts in force, and spell
    it as its stem: the fix reads the same chain authority the collision refusal
    and every other writer use.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    base = tmp_path / "packs" / "base"
    child = tmp_path / "packs" / "child"
    _skill(base, "base-skill-file", "base-skill-id")
    _write(base / "org-charter.yaml", "org_name: base\nrequired_skills:\n  - base-skill-id\n")
    _skill(child, OTHER_STEM, OTHER_ID)
    _write(child / "org-charter.yaml", "org_name: child\nextends: base\nrequired_skills:\n  - base-skill-id\n")
    _write(
        tmp_path / ".kittify" / "config.yaml",
        "mission_type_activations:\n  - software-dev\ncharter_packs:\n  org:\n    packs:\n"
        f"      - name: child\n        local_path: {child}\n      - name: base\n        local_path: {base}\n",
    )

    result = _activate(tmp_path, "skill", OTHER_STEM)

    assert result.exit_code == 0, result.output
    written = _listed(tmp_path) or []
    assert {"base-skill-file", OTHER_STEM} <= set(written), written
    assert "base-skill-id" not in written, written
