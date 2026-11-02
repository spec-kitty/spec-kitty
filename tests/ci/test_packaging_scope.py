"""Prose optimizations cannot hide package inputs or uncertain changes."""

from pathlib import Path
import subprocess

import pytest

from scripts.ci.packaging_scope import requires_build, select_from_environment

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "paths",
    [
        ["src/kernel/clock.py"],
        ["hatch_build.py"],
        ["pyproject.toml"],
        ["uv.lock"],
        ["README.md"],
        ["LICENSE"],
        ["pins/read-service.source.yaml"],
        ["packs/built-in.source.yaml"],
        ["tests/conftest.py"],
        [".github/workflows/ci-quality.yml"],
        ["docs/changelog/CHANGELOG.md"],
        ["docs/../pyproject.toml"],
        [],
        ["docs/explanation.md", "src/probe.py"],
        ["docs/image.png"],
    ],
)
def test_all_shipping_or_uncertain_inputs_build(paths: list[str]) -> None:
    assert requires_build(paths, ROOT)


def test_non_input_documentation_prose_can_omit_wheel() -> None:
    assert not requires_build(["docs/development/example.md", "docs/reference/example.rst"], ROOT)


def _config(root: Path, extra: str = "") -> None:
    (root / "pyproject.toml").write_text(
        '[build-system]\nbuild-backend = "hatchling.build"\n[project]\nreadme = "README.md"\n[tool.hatch.build.hooks.custom]\npath = "hatch_build.py"\n' + extra,
        encoding="utf-8",
    )


def test_declared_and_symlinked_documentation_inputs_build(tmp_path: Path) -> None:
    _config(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "intro.md").write_text("readme", encoding="utf-8")
    (tmp_path / "README.md").symlink_to("docs/intro.md")
    assert requires_build(["docs/intro.md"], tmp_path)
    assert not requires_build(["docs/other.md"], tmp_path)
    _config(tmp_path, '[tool.hatch.build.targets.wheel.force-include]\n"docs" = "package/docs"\n')
    assert requires_build(["docs/other.md"], tmp_path)


@pytest.mark.parametrize("config", ["", "[project]\n", "not toml", '[build-system]\nbuild-backend="other"\n'])
def test_bad_or_unknown_configuration_builds(tmp_path: Path, config: str) -> None:
    (tmp_path / "pyproject.toml").write_text(config, encoding="utf-8")
    assert requires_build(["docs/example.md"], tmp_path)


def test_git_diff_errors_and_non_pr_events_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVENT_NAME", "push")
    assert select_from_environment(tmp_path)
    monkeypatch.setenv("EVENT_NAME", "pull_request")
    monkeypatch.setenv("BASE_SHA", "0" * 40)
    monkeypatch.setenv("HEAD_SHA", "b" * 40)
    assert select_from_environment(tmp_path)
    monkeypatch.setenv("BASE_SHA", "a" * 40)
    assert select_from_environment(tmp_path)  # not a git repository


def test_real_diff_positive_and_negative_controls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _config(tmp_path)
    (tmp_path / "docs").mkdir()
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)

    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-c", "user.name=CI", "-c", "user.email=ci@example.test", *args], cwd=tmp_path, text=True).strip()

    git("add", "pyproject.toml")
    git("commit", "-qm", "initial")
    base = git("rev-parse", "HEAD")
    monkeypatch.setenv("EVENT_NAME", "pull_request")
    monkeypatch.setenv("BASE_SHA", base)
    for path, expected in [("docs/explanation.md", False), ("README.md", True)]:
        (tmp_path / path).write_text("changed", encoding="utf-8")
        git("add", path)
        git("commit", "-qm", "update")
        monkeypatch.setenv("HEAD_SHA", git("rev-parse", "HEAD"))
        assert select_from_environment(tmp_path) is expected
    # Rename detection otherwise reports only docs/moved.md, hiding deletion
    # of the declared root readme from the selector.
    monkeypatch.setenv("BASE_SHA", git("rev-parse", "HEAD"))
    git("mv", "README.md", "docs/moved.md")
    git("commit", "-qm", "move a package input into documentation")
    monkeypatch.setenv("HEAD_SHA", git("rev-parse", "HEAD"))
    assert select_from_environment(tmp_path)
