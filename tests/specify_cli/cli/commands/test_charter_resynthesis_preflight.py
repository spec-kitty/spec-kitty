"""Resynthesis prerequisites must fail before activation is persisted (#4101)."""

from pathlib import Path
import subprocess
from typing import cast

import pytest
from typer.testing import CliRunner

from charter.activation.pack_context import PackContext
from specify_cli.cli.commands.charter import app
from tests.charter.test_project_registration import author_guidance

pytestmark = [pytest.mark.unit, pytest.mark.fast]
runner = CliRunner()


def test_resynthesis_missing_interview_preserves_activation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    author_guidance(tmp_path)
    config = tmp_path / ".kittify/config.yaml"
    config.write_text("activated_agent_profiles: []\n", encoding="utf-8")
    before = config.read_bytes()
    result = runner.invoke(app, ["activate", "agent-profile", "ops-responder", "--cascade", "all", "--resynthesize"])
    assert result.exit_code == 1, result.output
    assert config.read_bytes() == before
    assert not (tmp_path / ".kittify/charter/synthesis-manifest.yaml").exists()
    assert "interview" in result.output.lower()


# ---------------------------------------------------------------------------
# FR-015 / #4400: an absent key is seeded from the effective set, or the
# preflight refuses before any write.
# ---------------------------------------------------------------------------


class _Context:
    """The two activation attributes ``_future_selections`` reads."""

    def __init__(self, *, directives: frozenset[str] | None = None, skills: frozenset[str] | None = None) -> None:
        self.activated_directives = directives
        self.activated_skills = skills


def _context(*, directives: frozenset[str] | None = None) -> PackContext:
    return cast(PackContext, _Context(directives=directives))


def _seam_spy(monkeypatch: pytest.MonkeyPatch, result: object) -> list[list[str]]:
    from specify_cli.cli.commands.charter import _resynthesis_preflight as preflight

    calls: list[list[str]] = []

    def spy(repo_root: Path, keys: list[str]) -> dict[str, object]:
        calls.append(list(keys))
        return dict.fromkeys(keys, result)

    monkeypatch.setattr(preflight, "resolve_effective_sets", spy)
    return calls


def test_absent_key_is_seeded_from_the_effective_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.activation.activation_engine import EffectiveSet
    from specify_cli.cli.commands.charter._resynthesis_preflight import _future_selections

    seed = EffectiveSet(kind="directive", yaml_key="activated_directives", ids=frozenset({"a", "b"}))
    calls = _seam_spy(monkeypatch, seed)

    selections = _future_selections(tmp_path, _context(), {"activated_directives": {"c"}})

    assert selections == {"activated_directives": frozenset({"a", "b", "c"})}
    assert calls == [["activated_directives"]]


def test_unresolved_effective_set_refuses_before_any_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.activation.activation_engine import EffectiveSet
    from specify_cli.cli.commands.charter._resynthesis_preflight import _future_selections

    seed = EffectiveSet(kind="directive", yaml_key="activated_directives", resolved=False, reason="declared org pack root /x is not a directory")
    _seam_spy(monkeypatch, seed)

    with pytest.raises(ValueError, match=r"Cannot resolve the effective directive set for resynthesis: declared org pack root /x"):
        _future_selections(tmp_path, _context(), {"activated_directives": {"c"}})


def test_present_key_and_required_kind_do_not_ask_the_seam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.charter._resynthesis_preflight import _future_selections

    calls = _seam_spy(monkeypatch, None)

    selections = _future_selections(
        tmp_path,
        _context(directives=frozenset({"x"})),
        {"activated_directives": {"c"}, "activated_skills": {"s"}},
    )

    assert selections == {"activated_directives": frozenset({"x", "c"}), "activated_skills": frozenset({"s"})}
    assert calls == []
