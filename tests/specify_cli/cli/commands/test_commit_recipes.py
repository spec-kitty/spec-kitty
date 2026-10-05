"""Unit tests for the shared ``_commit_recipes.safe_commit_recipe`` renderer.

The scanner that forbids raw ``git commit`` recipe strings under
``src/specify_cli`` lives in ``tests/architectural/test_commit_recipe_strings.py``
so that pull-request CI runs it for every ``src/specify_cli`` change. This
module keeps the renderer's own behaviour tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.commands._commit_recipes import PROTECTED_PRIMARY_HINT, safe_commit_recipe

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_NEEDLE = "git commit"


# ---------------------------------------------------------------------------
# The shared safe_commit_recipe() renderer.
# ---------------------------------------------------------------------------


def test_safe_commit_recipe_renders_files_message_and_branch() -> None:
    recipe = safe_commit_recipe(["foo.py", "bar.py"], "feat(WP01): x", "kitty/mission-demo-lane-a")
    assert recipe == 'spec-kitty safe-commit foo.py bar.py -m "feat(WP01): x" --to-branch kitty/mission-demo-lane-a'


def test_safe_commit_recipe_omits_to_branch_when_none() -> None:
    recipe = safe_commit_recipe(["foo.py"], "chore: x", None)
    assert recipe == 'spec-kitty safe-commit foo.py -m "chore: x"'
    assert "--to-branch" not in recipe


def test_safe_commit_recipe_never_contains_raw_git_commit() -> None:
    """The rendered recipe text itself must never re-trip the scan above."""
    recipe = safe_commit_recipe(["foo.py"], "feat(WP01): x", "main")
    assert _NEEDLE not in recipe


def test_safe_commit_recipe_protected_primary_hint_appended() -> None:
    recipe = safe_commit_recipe(["kitty-specs/demo"], "chore: planning artifacts for demo", "main", protected_primary=True)
    assert PROTECTED_PRIMARY_HINT in recipe
    assert "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS" not in recipe


def test_safe_commit_recipe_omits_hint_by_default() -> None:
    recipe = safe_commit_recipe(["foo.py"], "chore: x", "main")
    assert PROTECTED_PRIMARY_HINT not in recipe


def test_protected_primary_hint_never_suggests_env_bypass() -> None:
    """Charter 'Agent Push Authorization': never point at the env-var escape hatch."""
    assert "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS" not in PROTECTED_PRIMARY_HINT
    assert "protected_branches" in PROTECTED_PRIMARY_HINT.replace(".", "")


# ---------------------------------------------------------------------------
# Pin ``_print_planning_artifact_commit_instructions``'s printed recipe: a
# mutation dropping ``planning_branch`` from its ``safe_commit_recipe(...)``
# call must not survive. Drive the auto-commit-disabled path directly and
# assert on the printed recipe text.
# ---------------------------------------------------------------------------


def test_planning_artifact_recipe_pins_to_branch_on_the_planning_branch(capsys: pytest.CaptureFixture[str]) -> None:
    import typer

    from specify_cli.cli.commands.implement_planning_commit import _print_planning_artifact_commit_instructions

    planning_branch = "kitty/mission-demo-mission-abcd1234"
    lane_branch = "kitty/mission-demo-mission-lane-a"

    with pytest.raises(typer.Exit):
        _print_planning_artifact_commit_instructions(
            current_branch=planning_branch,
            planning_branch=planning_branch,
            auto_commit=False,
            feature_dir=Path("kitty-specs/demo-mission"),
            mission_slug="demo-mission",
        )

    out = capsys.readouterr().out
    assert "spec-kitty safe-commit" in out
    assert "kitty-specs/demo-mission" in out
    assert f"--to-branch {planning_branch}" in out
    assert lane_branch not in out
