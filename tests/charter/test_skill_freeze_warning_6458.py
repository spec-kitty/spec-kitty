"""Writing ``activated_skills`` freezes the org-required skills (#6458, FR-005..FR-007).

While ``activated_skills`` is absent, the org packs' ``required_skills`` are in
force as they change. The first write freezes them, and ``--only`` writes the
list on every run, so both say so; the generic "use --only to keep activation
narrow" advice is not given for skills (it would not avoid the freeze). An
"all" kind (``toolguide``) never gets the warning. Every case asserts the
written list (C-001).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app
from tests._factories.activation_ledger import read_activation_ledger

from . import skill_pack_support as support

pytestmark = [pytest.mark.integration]

runner = CliRunner()

FREEZE = (
    "Kind 'skill' now has an explicit activation list, so the org packs' required skills are frozen at their current values: "
    "a skill an org pack later adds to required_skills will not reach this project."
)
_FREEZE_MARK = "are frozen at their current values"
_ONLY_ADVICE = "to keep activation narrow"


def _activate(project: Path, *args: str) -> str:
    result = runner.invoke(charter_app, ["activate", "--repo-root", str(project), "--no-compile", *args], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return " ".join(result.output.split())


def _written(project: Path, key: str) -> list[str] | None:
    value = read_activation_ledger(project).get(key)
    return None if value is None else [str(item) for item in value]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """An org pack shipping skills ``required-one``, ``x`` and ``y``; ``required-one`` is required."""
    pack = tmp_path / "pack"
    pack.mkdir()
    for skill_id in ("required-one", "x", "y"):
        support.write_skill(pack, skill_id)
    support.write_org_charter(pack, required_skills=["required-one"])
    support.write_config(tmp_path, pack)
    return tmp_path


def test_the_engine_text_is_the_approved_text() -> None:
    from charter.activation.activation_engine import org_required_freeze_warning

    assert org_required_freeze_warning("skill", "skills") == FREEZE


def test_plain_activation_on_an_absent_key_warns_of_the_freeze_without_the_only_advice(project: Path) -> None:
    assert _written(project, "activated_skills") is None

    out = _activate(project, "skill", "x")

    assert _written(project, "activated_skills") == ["required-one", "x"]
    assert FREEZE in out
    assert out.count(_FREEZE_MARK) == 1
    assert _ONLY_ADVICE not in out
    assert "had no explicit activation set" in out, "the in-force message itself stays"


def test_plain_activation_on_a_present_key_does_not_warn(project: Path) -> None:
    _activate(project, "skill", "x")

    out = _activate(project, "skill", "y")

    assert _written(project, "activated_skills") == ["required-one", "x", "y"]
    assert _FREEZE_MARK not in out


def test_only_on_an_absent_key_warns_of_the_freeze(project: Path) -> None:
    out = _activate(project, "skill", "x", "--only")

    assert _written(project, "activated_skills") == ["required-one", "x"]
    assert FREEZE in out
    assert out.count(_FREEZE_MARK) == 1
    assert _ONLY_ADVICE not in out


def test_only_on_a_present_key_warns_of_the_freeze_every_run(project: Path) -> None:
    _activate(project, "skill", "x")

    out = _activate(project, "skill", "y", "--only")

    assert _written(project, "activated_skills") == ["required-one", "y"]
    assert FREEZE in out
    assert out.count(_FREEZE_MARK) == 1


def test_an_all_kind_never_warns_of_the_freeze(project: Path) -> None:
    """Control: ``toolguide`` (effective when absent: all), plain and ``--only``, same fixture."""
    plain = _activate(project, "toolguide", "gherkin")
    written = _written(project, "activated_toolguides") or []
    assert "gherkin" in written and len(written) > 1
    assert _FREEZE_MARK not in plain
    assert _ONLY_ADVICE in plain, "an 'all' kind keeps the --only advice"

    narrowed = _activate(project, "toolguide", "gherkin", "--only")
    assert _written(project, "activated_toolguides") == ["gherkin"]
    assert _FREEZE_MARK not in narrowed
