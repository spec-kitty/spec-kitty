"""``charter activate <kind> <id> --only`` narrows one kind's list (#6408, FR-012, FR-014).

The default (no ``--only``) stays unchanged except that the materialisation
warning now says the list is frozen. Every dropped-id assertion is measured
against the same fixture's effective set (positive control), and the
stem != declared-id org artifact proves the comparison runs in one spelling.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner, Result

from charter.activation.invocation_context import ProjectContext
from charter.activation.pack_manager import ActiveCharterManager
from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.integration]

runner = CliRunner()

_KEY = "activated_toolguides"
_ORG_STEM = "acme-tool-file"
_ORG_ID = "acme-tool-id"
_TARGET = "gherkin"


def _write_org_pack(root: Path, *, required: bool) -> Path:
    pack = root / "acme"
    (pack / "toolguides").mkdir(parents=True)
    (pack / "toolguides" / f"{_ORG_STEM}.toolguide.yaml").write_text(
        f'schema_version: "1.0"\nid: {_ORG_ID}\ntool: acme\ntitle: Acme tool\nsummary: Acme tool guide.\nguide_path: acme.md\napplies_to_languages: []\n',
        encoding="utf-8",
    )
    charter = f"org_name: acme\nrequired_toolguides:\n  - {_ORG_ID}\n" if required else "org_name: acme\n"
    (pack / "org-charter.yaml").write_text(charter, encoding="utf-8")
    return pack


def _project(tmp_path: Path, *, required: bool = True, extra: str = "") -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    pack = _write_org_pack(tmp_path, required=required)
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        f"mission_type_activations:\n  - software-dev\ncharter_packs:\n  org:\n    packs:\n      - name: acme\n        local_path: {pack}\n{extra}",
        encoding="utf-8",
    )
    return tmp_path


def _activate(root: Path, *args: str) -> Result:
    return runner.invoke(charter_app, ["activate", "--repo-root", str(root), "--no-compile", *args], catch_exceptions=False)


def _list(root: Path) -> list[str] | None:
    data = YAML(typ="safe").load((root / ".kittify" / "config.yaml").read_text(encoding="utf-8"))
    value = data.get(_KEY)
    return None if value is None else list(value)


def _available(root: Path) -> set[str]:
    return set(ActiveCharterManager().list_available(ProjectContext.from_repo(root), "toolguide"))


def _dropped(output: str) -> tuple[int, set[str]]:
    match = re.search(r"No longer in force \((\d+)\): (.*)", " ".join(output.split()).split(" Catalog not recompiled")[0])
    assert match, output
    return int(match.group(1)), {item.strip() for item in match.group(2).split(",")}


def test_fresh_project_only_writes_id_plus_org_required_stem_and_names_every_dropped_toolguide(tmp_path: Path) -> None:
    root = _project(tmp_path)
    available = _available(root)
    assert _TARGET in available and len(available) > 3, "fixture invalid: need other effective toolguides to drop"
    assert _list(root) is None

    result = _activate(root, "toolguide", _TARGET, "--only")

    assert result.exit_code == 0, result.output
    assert _list(root) == [_ORG_STEM, _TARGET]  # org-required written as its stem, not its declared id
    count, dropped = _dropped(result.output)
    stems_kept = {_ORG_STEM, _TARGET}
    assert count == len(dropped)
    assert _ORG_STEM not in dropped and _ORG_ID not in dropped, "a kept stem != id artifact must not be reported dropped"
    assert _TARGET not in dropped
    # every formerly effective toolguide other than the kept ones is named (positive control: `available`)
    assert dropped == {a for a in available if a not in stems_kept and a != _ORG_ID}


def test_only_replaces_a_present_list_and_a_following_plain_activate_appends(tmp_path: Path) -> None:
    root = _project(tmp_path, required=False)
    assert _activate(root, "toolguide", "sonar").exit_code == 0
    assert len(_list(root) or []) > 3, "fixture invalid: the first activation must materialise the effective set"

    narrowed = _activate(root, "toolguide", _TARGET, "--only")
    assert narrowed.exit_code == 0, narrowed.output
    assert _list(root) == [_TARGET]
    assert "sonar" in _dropped(narrowed.output)[1]

    appended = _activate(root, "toolguide", "sonar")
    assert appended.exit_code == 0, appended.output
    assert _list(root) == [_TARGET, "sonar"]
    assert "No longer in force" not in appended.output


def test_only_with_preset_exits_2_with_a_clear_message(tmp_path: Path) -> None:
    root = _project(tmp_path)
    result = runner.invoke(charter_app, ["activate", "--repo-root", str(root), "--preset", "minimal", "--only"])
    assert result.exit_code == 2
    assert "--only cannot be combined with --preset" in result.output
    assert _list(root) is None


def test_without_only_the_list_is_unchanged_and_the_warning_says_it_is_frozen(tmp_path: Path) -> None:
    root = _project(tmp_path)
    available = _available(root)

    result = _activate(root, "toolguide", _TARGET)

    assert result.exit_code == 0, result.output
    written = _list(root) or []
    assert _TARGET in written and set(available) <= set(written) | {_ORG_ID}
    out = " ".join(result.output.split())
    assert "had no explicit activation set. Initialized from the" in out
    assert "This list is now explicit" in out and "--only" in out
    assert "No longer in force" not in out


def test_only_with_cascade_narrows_only_the_named_kind(tmp_path: Path) -> None:
    root = _project(tmp_path, required=False)
    available = set(ActiveCharterManager().list_available(ProjectContext.from_repo(root), "directive"))
    result = _activate(root, "directive", "001-architectural-integrity-standard", "--only", "--cascade", "all")
    assert result.exit_code == 0, result.output
    data = YAML(typ="safe").load((root / ".kittify" / "config.yaml").read_text(encoding="utf-8"))
    listed = data["activated_directives"]
    # the named kind was narrowed (strictly fewer than everything effective before), with the id first ...
    assert listed[0] == "001-architectural-integrity-standard"
    assert set(listed) < available, "fixture invalid or --only did not narrow: the list must be a strict subset of what was effective"
    # ... and cascaded entries of the same kind appended after it, never replaced it
    cascaded = listed[1:]
    assert cascaded, "cascade=all must have appended at least one referenced directive"
    assert "Cascade-activated" in result.output
