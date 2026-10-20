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
    (tmp_path / "karma.conf.js").write_text("module.exports = {};\n", encoding="utf-8")
    (tmp_path / "build.js").write_text("// tooling\n", encoding="utf-8")
    for index in range(10):
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


def test_an_invalid_answer_is_asked_again_then_stored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    monkeypatch.setenv("SPEC_KITTY_FORCE_INTERACTIVE", "1")

    result = runner.invoke(charter_app, ["interview"], input=_interactive_input("cobol\npython"))

    assert result.exit_code == 0, result.output
    assert "Not a catalog language: cobol" in result.output
    assert _config(root)["languages"] == ["python"]


def test_a_family_answer_is_stored_like_a_declared_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    monkeypatch.setenv("SPEC_KITTY_FORCE_INTERACTIVE", "1")

    result = runner.invoke(charter_app, ["interview"], input=_interactive_input("jvm"))

    assert result.exit_code == 0, result.output
    assert _config(root)["languages"] == ["jvm"]


def test_repeated_invalid_answers_fail_after_bounded_retries_and_write_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    monkeypatch.setenv("SPEC_KITTY_FORCE_INTERACTIVE", "1")

    result = runner.invoke(charter_app, ["interview"], input=_interactive_input("cobol\ncobol\ncobol"))

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
    assert payload["languages"] == ["python"], "a tooling-only package.json is not a second language"
    assert "DETECTED, not confirmed" in payload["languages_notice"]
    assert "python" in payload["languages_notice"]
    assert ".kittify/config.yaml" in payload["languages_notice"]


def test_defaults_run_never_overwrites_an_operator_set_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    _set_config(root, "# operator choice\nlanguages: [go]\n")

    result = runner.invoke(charter_app, ["interview", "--defaults", "--json"])

    assert result.exit_code == 0, result.output
    assert _config(root)["languages"] == ["go"]
    assert "# operator choice" in (root / ".kittify" / "config.yaml").read_text(encoding="utf-8")
    payload = json.loads(result.output[result.output.index("{") :])
    assert payload["languages_source"] == "stored"
    assert payload["languages_notice"] is None


def test_non_interactive_env_without_defaults_never_prompts_the_language_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    monkeypatch.setenv("SPEC_KITTY_NON_INTERACTIVE", "1")

    # No --defaults: only the language step is non-interactive. The remaining questions
    # prompt, and the empty input aborts them AFTER the language step has settled; an
    # aborted interview stores neither the answers nor the languages (#6542).
    result = runner.invoke(charter_app, ["interview"], input="")

    assert result.exit_code != 0
    assert not _has_languages(root)
    assert "Project languages (comma-separated" not in result.output


def test_non_interactive_text_output_makes_the_operator_aware(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)

    result = runner.invoke(charter_app, ["interview", "--defaults"])

    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())
    assert "Languages (detected): python" in flat
    assert "DETECTED, not confirmed: python" in flat
    assert "languages:" in flat and ".kittify/config.yaml" in flat and "interactively" in flat
    assert _config(root)["languages"] == ["python"]


def test_other_config_keys_survive_the_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    _set_config(root, "vcs:\n  type: git  # keep me\nmerge:\n  strategy: squash\n")

    result = runner.invoke(charter_app, ["interview", "--defaults"])

    assert result.exit_code == 0, result.output
    text = (root / ".kittify" / "config.yaml").read_text(encoding="utf-8")
    assert "# keep me" in text and "strategy: squash" in text
    assert _config(root)["languages"] == _detected(root)


# -- the languages are stored with the answers, never before them (#6542) ------------


def _has_languages(root: Path) -> bool:
    path = root / ".kittify" / "config.yaml"
    return path.exists() and "languages" in _config(root)


def _answers_file(root: Path) -> Path:
    return root / ".kittify" / "charter" / "interview" / "answers.yaml"


def test_an_abort_after_the_language_step_stores_neither_languages_nor_answers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)

    result = runner.invoke(charter_app, ["interview"], input="")

    assert result.exit_code != 0
    assert not _has_languages(root)
    assert not _answers_file(root).exists()


def test_a_failing_answers_write_stores_no_languages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("charter.activation.interview.write_interview_answers", boom)

    result = runner.invoke(charter_app, ["interview", "--defaults", "--json"])

    assert result.exit_code == 1
    assert not _has_languages(root)


def test_an_interactive_change_followed_by_an_abort_keeps_the_previous_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    monkeypatch.setenv("SPEC_KITTY_FORCE_INTERACTIVE", "1")
    _set_config(root, "languages:\n- go\n")

    result = runner.invoke(charter_app, ["interview"], input="python\n")  # the next prompt hits EOF and aborts

    assert result.exit_code != 0
    assert _config(root)["languages"] == ["go"]


def test_a_completed_run_stores_the_answers_and_the_languages_and_promotion_keeps_them(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)

    result = runner.invoke(charter_app, ["interview", "--defaults", "--json", "--selected-directives", "DIRECTIVE_010"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output[result.output.index("{") :])
    assert (root / payload["interview_path"]).exists()
    assert _config(root)["languages"] == ["python"]
    assert payload["languages"] == ["python"]
    assert payload["languages_source"] == "detected"
    assert "DETECTED, not confirmed" in payload["languages_notice"]
    assert "activated_directives" in _config(root), "promotion ran and its write sits beside the languages"


def test_a_detected_store_that_loses_the_race_to_a_set_key_reports_the_kept_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.activation import api
    from charter.activation.language_settlement import LanguageSettlement

    root = _repo(tmp_path, monkeypatch)
    real_store = api.store_language_settlement

    def key_set_meanwhile(repo_root: Path, settlement: LanguageSettlement) -> bool:
        with (repo_root / ".kittify" / "config.yaml").open("a", encoding="utf-8") as handle:
            handle.write("\nlanguages: [go]\n")
        return real_store(repo_root, settlement)

    monkeypatch.setattr("charter.activation.api.store_language_settlement", key_set_meanwhile)

    result = runner.invoke(charter_app, ["interview", "--defaults", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output[result.output.index("{") :])
    assert _config(root)["languages"] == ["go"]
    assert payload["languages"] == ["go"]
    assert payload["languages_source"] == "stored"
    assert payload["languages_notice"] is None


def test_a_failing_languages_store_after_the_answers_exits_non_zero_without_claiming_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("config is read-only")

    monkeypatch.setattr("charter.activation.api.store_language_settlement", boom)

    result = runner.invoke(charter_app, ["interview", "--defaults", "--json"])

    assert result.exit_code == 1
    assert "config is read-only" in result.output
    assert ".kittify/config.yaml" in result.output
    assert "answers were saved" in result.output
    assert "re-running is safe" in result.output
    assert '"success": true' not in result.output
    assert not _has_languages(root)
