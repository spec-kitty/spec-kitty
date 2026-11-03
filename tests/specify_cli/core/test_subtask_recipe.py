"""The subtask-completion recipe is rendered in one place, with the WP named (#7108).

Subtask ids are mission-scoped: several work packages routinely author the same
``T001``. ``mark-status`` resolves that with ``--wp`` and refuses an unscoped id
that more than one WP owns, so any recipe the CLI or the runtime prints for an
operator or agent MUST name the owning work package or it is a dead end on the
normal case.

These tests pin the rendered shape at its single home
(:mod:`specify_cli.core.subtask_recipe`) so the four emitters cannot drift.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from specify_cli.core.subtask_recipe import mark_status_recipe

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "port-completion-01M6FZ0K"

#: Import roots that would put I/O or domain knowledge back on the pure refusal path.
_IO_BEARING_ROOTS = frozenset({"pathlib", "kernel", "specify_cli", "subprocess", "json"})


def test_single_id_without_mission_omits_the_mission_flag() -> None:
    assert mark_status_recipe(["T001"], wp_id="WP02") == "spec-kitty agent tasks mark-status T001 --wp WP02 --status done"


def test_mission_slug_is_appended_after_the_status() -> None:
    assert mark_status_recipe(["T001"], wp_id="WP02", mission_slug=_SLUG) == f"spec-kitty agent tasks mark-status T001 --wp WP02 --status done --mission {_SLUG}"


def test_owned_root_is_appended_after_the_mission(tmp_path: Path) -> None:
    """The owned flag keeps its historical *trailing* position (#7108).

    ``tests/integration/test_prompt_builder_owned_arms.py`` asserts the owned
    flag as a suffix of the printed line, and ``--owned-checkout`` is the last
    option an operator appends by hand.
    """
    owned = tmp_path / "owned-root"
    assert (
        mark_status_recipe(["T001"], wp_id="WP02", mission_slug=_SLUG, owned_root=owned)
        == f"spec-kitty agent tasks mark-status T001 --wp WP02 --status done --mission {_SLUG} --owned-checkout {owned}"
    )


def test_multiple_ids_render_space_separated_before_the_options() -> None:
    assert (
        mark_status_recipe(["T001", "T002", "T003"], wp_id="WP02", mission_slug=_SLUG)
        == f"spec-kitty agent tasks mark-status T001 T002 T003 --wp WP02 --status done --mission {_SLUG}"
    )


def test_unknown_mission_renders_no_mission_token_and_never_the_string_none() -> None:
    rendered = mark_status_recipe(["T001"], wp_id="WP02", mission_slug=None)

    assert "--mission" not in rendered
    assert "None" not in rendered


def test_owned_root_accepts_a_plain_string_path() -> None:
    assert (
        mark_status_recipe(["T001"], wp_id="WP02", mission_slug=_SLUG, owned_root=os.sep + "tmp" + os.sep + "own")
        == f"spec-kitty agent tasks mark-status T001 --wp WP02 --status done --mission {_SLUG} --owned-checkout {os.sep}tmp{os.sep}own"
    )


def test_wp_id_is_keyword_only_so_a_caller_cannot_forget_it() -> None:
    with pytest.raises(TypeError):
        mark_status_recipe(["T001"], "WP02")  # type: ignore[misc]


def test_the_module_stays_pure_and_free_of_io_imports() -> None:
    """``tasks_transition_core`` calls this on its pure refusal path.

    A ``pathlib``/``kernel``/status import here would put I/O and event-log
    knowledge back on a decision core that is contractually I/O-free (NFR-001).
    """
    module_path = Path(mark_status_recipe.__code__.co_filename)
    tree = ast.parse(module_path.read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)

    forbidden = {name for name in imported if name.split(".")[0] in _IO_BEARING_ROOTS}
    assert not forbidden, f"subtask_recipe must stay pure; forbidden imports: {sorted(forbidden)}"
