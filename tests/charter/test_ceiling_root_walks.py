"""The project-root walks of the ``charter`` and ``runtime`` layers honour the ceiling (#7056).

These walks find a Spec Kitty project by its ``.kittify`` marker (or a sibling
convention) and are reached from the next-run planner, the charter lint checks and the
catalog-miss diagnosis. They used the same hand-rolled ancestor loop as the
``specify_cli`` walks and climbed straight through ``GIT_CEILING_DIRECTORIES``, so a
hermetic tree inside another Spec Kitty checkout resolved into that checkout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.context_renderers import catalog_diagnosis
from charter.activation.neutrality import lint as neutrality_lint
from runtime.next._internal_runtime import planner
from specify_cli.cli.commands import regen

CEILING_ENV = "GIT_CEILING_DIRECTORIES"


@pytest.fixture(autouse=True)
def _no_ambient_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)


@pytest.fixture
def ambient_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """``(<tmp>/outer``, ``<tmp>/outer/ceiling/work)``: a Spec Kitty project above the ceiling."""
    outer = (tmp_path / "outer").resolve()
    (outer / ".kittify").mkdir(parents=True)
    (outer / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    (outer / "kitty-specs").mkdir()
    ceiling = (outer / "ceiling").resolve()
    work = (ceiling / "work").resolve()
    work.mkdir(parents=True)
    monkeypatch.setenv(CEILING_ENV, str(ceiling))
    return outer, work


def test_catalog_diagnosis_project_layer_stops_at_the_ceiling(ambient_project: tuple[Path, Path]) -> None:
    outer, work = ambient_project

    class _Repository:
        _project_dir = work

    assert catalog_diagnosis._repository_repo_root(_Repository()) is None


def test_catalog_diagnosis_still_finds_a_project_below_the_ceiling(ambient_project: tuple[Path, Path]) -> None:
    _outer, work = ambient_project
    (work / ".kittify").mkdir()

    class _Repository:
        _project_dir = work

    assert catalog_diagnosis._repository_repo_root(_Repository()) == work


def test_neutrality_lint_repo_root_stops_at_the_ceiling(ambient_project: tuple[Path, Path]) -> None:
    _outer, work = ambient_project
    (work / "src").mkdir()

    # No pyproject below the ceiling, so the walk must fall back to the cwd rather than
    # adopt the project above it.
    assert neutrality_lint._find_repo_root(work) == Path.cwd()


def test_neutrality_lint_still_finds_a_pyproject_below_the_ceiling(ambient_project: tuple[Path, Path]) -> None:
    _outer, work = ambient_project
    (work / "pyproject.toml").write_text("[project]\nname = 'y'\n", encoding="utf-8")

    assert neutrality_lint._find_repo_root(work) == work


def test_next_planner_project_root_stops_at_the_ceiling(ambient_project: tuple[Path, Path]) -> None:
    _outer, work = ambient_project
    mission_dir = work / "kitty-specs" / "some-mission"
    mission_dir.mkdir(parents=True)

    # The mission dir's own kitty-specs parent rule is below the ceiling, so the mission
    # still resolves -- but it must resolve to its own project, never the ambient one.
    assert planner._infer_project_root(mission_dir) == work


def test_next_planner_does_not_adopt_a_project_above_the_ceiling(ambient_project: tuple[Path, Path]) -> None:
    _outer, work = ambient_project
    nested = work / "scratch"
    nested.mkdir()

    assert planner._infer_project_root(nested) is None


def test_regen_repo_root_stops_at_the_ceiling(ambient_project: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    import typer

    outer, work = ambient_project
    # A dev-checkout-shaped tree *above* the ceiling: templates plus the fixture tree
    # regen looks for. Only a walk that crosses the ceiling can find it.
    (outer / regen._TEMPLATES_REL).mkdir(parents=True)
    (outer / "tests" / "specify_cli").mkdir(parents=True)
    module_dir = work / "src" / "specify_cli" / "cli" / "commands"
    module_dir.mkdir(parents=True)
    monkeypatch.setattr(regen, "__file__", str(module_dir / "regen.py"))
    monkeypatch.chdir(work)

    with pytest.raises(typer.BadParameter):
        regen._repo_root()


def test_regen_repo_root_finds_the_dev_checkout_below_the_ceiling(ambient_project: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _outer, work = ambient_project
    (work / regen._TEMPLATES_REL).mkdir(parents=True)
    (work / "tests" / "specify_cli").mkdir(parents=True)
    module_dir = work / "src" / "specify_cli" / "cli" / "commands"
    module_dir.mkdir(parents=True)
    monkeypatch.setattr(regen, "__file__", str(module_dir / "regen.py"))
    monkeypatch.chdir(work)

    assert regen._repo_root() == work
