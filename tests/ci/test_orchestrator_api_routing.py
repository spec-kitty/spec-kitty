"""An orchestrator-api change runs the orchestrator-api tests per PR (#7846).

#7809 added a key to the finalize-tasks JSON, which the orchestrator-api ``tasks`` verb
passes through to its success ``data``. The test that pins that key set,
``test_specify_plan_tasks_success_data_key_shape_is_pinned`` in
``tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py``, sat in an
``out_of_matrix_test_dirs`` directory, so no per-PR shard ran it and ``main`` went red in
the nightly only (#7829, #7835), blocking the RC9 cut. The fix claims both orchestrator-api
test trees in the ``execution_context`` row, which roots ``src/specify_cli/orchestrator_api/**``
and the finalize-tasks source under ``src/specify_cli/cli/commands/agent/**``.

Every assertion drives the production entry points ``select_modules`` /
``out_of_matrix_test_paths``; none restates the routing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.ci.gate_selection import DEFAULT_REGISTRY_PATH, out_of_matrix_test_paths, select_modules

pytestmark = pytest.mark.fast

KEY_SHAPE_TEST = "tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py"
MIRROR_TEST = "tests/orchestrator_api/test_merge_mission_destructive_refusal.py"
TEST_FILES: tuple[str, ...] = (KEY_SHAPE_TEST, MIRROR_TEST)

#: #7809's src change (58cc6df5): the finalize-tasks payload the ``tasks`` verb passes through.
PR_7809_SRC_PATHS: tuple[str, ...] = ("src/specify_cli/cli/commands/agent/mission_finalize.py",)

#: Paths whose edit changes what the orchestrator-api tests check, each alone.
ORCHESTRATOR_SURFACE_PATHS: tuple[str, ...] = (
    "src/specify_cli/orchestrator_api/commands.py",
    "src/specify_cli/orchestrator_api/design_phase.py",
    "src/specify_cli/orchestrator_api/envelope.py",
    "src/specify_cli/cli/commands/agent/mission_finalize.py",
    "src/specify_cli/cli/commands/agent/tasks_finalize.py",
)


def _owners(test_file: str) -> frozenset[str]:
    """The modules whose shard EXECUTES ``test_file``: ``test_dirs``, else ``tests/<module>``.

    Not ``select_modules([test_file])``: that maps a test path to the modules a src change
    would select (the selection mirror), which is non-empty even for a nightly-only directory.
    """
    registry = yaml.safe_load(Path(DEFAULT_REGISTRY_PATH).read_text(encoding="utf-8"))
    return frozenset(
        str(row["module"])
        for row in registry["modules"]
        if any(test_file.startswith(f"{str(d).rstrip('/')}/") for d in (row.get("test_dirs") or [f"tests/{row['module']}"]))
    )


@pytest.mark.parametrize("test_file", TEST_FILES)
def test_orchestrator_api_tests_are_in_the_per_pr_matrix(test_file: str) -> None:
    assert out_of_matrix_test_paths([test_file]) == ()
    assert _owners(test_file) == frozenset({"execution_context"})


def test_replaying_pr_7809_runs_the_key_shape_test() -> None:
    """#7809's src change, replayed, selects a module whose shard runs the key-set pin."""
    assert select_modules(PR_7809_SRC_PATHS) & _owners(KEY_SHAPE_TEST)


@pytest.mark.parametrize("path", ORCHESTRATOR_SURFACE_PATHS)
@pytest.mark.parametrize("test_file", TEST_FILES)
def test_an_orchestrator_surface_edit_alone_runs_the_tests(path: str, test_file: str) -> None:
    assert select_modules([path]) & _owners(test_file)


def test_a_test_file_edit_runs_its_own_tree() -> None:
    """Editing a test in either tree selects the module whose shard runs that tree."""
    for test_file in TEST_FILES:
        assert select_modules([test_file]) & _owners(test_file), test_file
