"""``charter interview`` detects, proposes, confirms and stores the project languages (#6444, FR-020).

The confirmed list lands in ``.kittify/config.yaml`` under ``languages``. A later interview
shows it as the default; a ``--defaults`` or non-interactive run stores the detected list
only when the key is absent and never overwrites an operator-set key.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app as charter_app

pytestmark = [pytest.mark.regression, pytest.mark.git_repo]

runner = CliRunner()


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=tmp_path, check=True, capture_output=True)
    for key, value in (("user.email", "t@example.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        subprocess.run(["git", "config", key, value], cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.delenv("SPEC_KITTY_NON_INTERACTIVE", raising=False)
    monkeypatch.delenv("SPEC_KITTY_FORCE_INTERACTIVE", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")  # tooling only
    for index in range(4):
        path = tmp_path / "src" / f"m{index}.py"
        path.parent.mkdir(exist_ok=True)
        path.write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def _config(root: Path) -> dict[str, object]:
    loaded = YAML(typ="safe").load((root / ".kittify" / "config.yaml").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _set_config(root: Path, text: str) -> None:
    path = root / ".kittify" / "config.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _detected(root: Path) -> list[str]:
    from charter.activation.evidence.code_reader import CodeReadingCollector

    return list(CodeReadingCollector(root, use_configured_languages=False).collect().languages)


def _interactive_input(languages_answer: str) -> str:
    """The language answer first, then Enter for every later prompt (defaults)."""
    return languages_answer + "\n" + "\n" * 40


def test_interactive_interview_proposes_the_detected_languages_and_stores_the_confirmed_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    monkeypatch.setenv("SPEC_KITTY_FORCE_INTERACTIVE", "1")
    detected = _detected(root)
    assert detected, "control: the fixture has observable languages"

    result = runner.invoke(charter_app, ["interview"], input=_interactive_input("python"))

    assert result.exit_code == 0, result.output
    assert ", ".join(detected) in result.output  # the proposal is shown as the default
    assert _config(root)["languages"] == ["python"]


def test_a_later_interview_shows_the_stored_list_as_the_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    monkeypatch.setenv("SPEC_KITTY_FORCE_INTERACTIVE", "1")
    _set_config(root, "languages:\n- kotlin\n- go\n")

    result = runner.invoke(charter_app, ["interview"], input=_interactive_input(""))

    assert result.exit_code == 0, result.output
    assert "kotlin, go" in result.output
    assert _config(root)["languages"] == ["kotlin", "go"]


def test_an_invalid_answer_is_refused_and_nothing_is_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    monkeypatch.setenv("SPEC_KITTY_FORCE_INTERACTIVE", "1")

    result = runner.invoke(charter_app, ["interview"], input=_interactive_input("jvm"))

    assert result.exit_code != 0
    assert "Not a catalog language" in result.output
    assert not (root / ".kittify" / "config.yaml").exists() or "languages" not in _config(root)


def test_defaults_run_stores_the_detected_list_when_the_key_is_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)

    result = runner.invoke(charter_app, ["interview", "--defaults", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output[result.output.index("{") :])
    assert _config(root)["languages"] == _detected(root)
    assert payload["languages"] == _detected(root)
    assert payload["languages_source"] == "detected"


def test_defaults_run_never_overwrites_an_operator_set_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    _set_config(root, "# operator choice\nlanguages: [go]\n")

    result = runner.invoke(charter_app, ["interview", "--defaults", "--json"])

    assert result.exit_code == 0, result.output
    assert _config(root)["languages"] == ["go"]
    assert "# operator choice" in (root / ".kittify" / "config.yaml").read_text(encoding="utf-8")
    assert json.loads(result.output[result.output.index("{") :])["languages_source"] == "stored"


def test_non_interactive_env_never_prompts_and_stores_the_detected_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    monkeypatch.setenv("SPEC_KITTY_NON_INTERACTIVE", "1")

    result = runner.invoke(charter_app, ["interview", "--defaults"])  # no input: a prompt would abort

    assert result.exit_code == 0, result.output
    assert _config(root)["languages"] == _detected(root)


def test_other_config_keys_survive_the_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    _set_config(root, "vcs:\n  type: git  # keep me\nmerge:\n  strategy: squash\n")

    result = runner.invoke(charter_app, ["interview", "--defaults"])

    assert result.exit_code == 0, result.output
    text = (root / ".kittify" / "config.yaml").read_text(encoding="utf-8")
    assert "# keep me" in text and "strategy: squash" in text
    assert _config(root)["languages"] == _detected(root)
