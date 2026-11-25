"""An orchestrator-api change runs the orchestrator-api tests per PR (#7846).

#7809 added a key to the finalize-tasks JSON, which the orchestrator-api ``tasks`` verb
passes through to its success ``data``. The test that pins that key set,
``test_specify_plan_tasks_success_data_key_shape_is_pinned`` in
``tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py``, sat in an
``out_of_matrix_test_dirs`` directory, so no per-PR shard ran it and ``main`` went red in
the nightly only (#7829, #7835), blocking the RC9 cut. The fix claims the tree in the
``execution_context`` row, which roots ``src/specify_cli/orchestrator_api/**`` and the
finalize-tasks source under ``src/specify_cli/cli/commands/agent/**``.

This file lives in ``tests/architectural`` on purpose: a PR that edits only
``.github/ci-module-registry.yml`` (the change that would undo the claim) selects no module
row but does run the architectural battery, so the claim is checked on that PR (#7871
tracks the same hole for ``tests/ci/test_skill_source_routing.py``).

Every assertion drives a production entry point -- module selection (``select_modules``),
the out-of-matrix lookup (``out_of_matrix_test_paths``) and the shard's own directory
resolver (``resolve_module_test_dirs``); none restates the selection rules.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts.ci.gate_selection import DEFAULT_REGISTRY_PATH, out_of_matrix_test_paths, select_modules
from scripts.ci.shard_select import MODULE_SELECTION_MARKER_EXPR, resolve_module_test_dirs

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]

KEY_SHAPE_TEST = "tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py"
KEY_SHAPE_NODE = f"{KEY_SHAPE_TEST}::test_specify_plan_tasks_success_data_key_shape_is_pinned"

#: A sibling test still recorded in ``out_of_matrix_test_dirs`` (negative control for the
#: empty-lookup assertion: the lookup must not answer ``()`` for every path).
STILL_OUT_OF_MATRIX_TEST = "tests/specify_cli/ownership/test_audit_scope.py"

#: #7809's src change (58cc6df5): the finalize-tasks payload the ``tasks`` verb passes through.
PR_7809_SRC_PATHS: tuple[str, ...] = ("src/specify_cli/cli/commands/agent/mission_finalize.py",)

#: The files that build the passed-through payload's keys, and the verb surface, each alone.
ORCHESTRATOR_SURFACE_PATHS: tuple[str, ...] = (
    "src/specify_cli/orchestrator_api/commands.py",
    "src/specify_cli/orchestrator_api/design_phase.py",
    "src/specify_cli/orchestrator_api/envelope.py",
    "src/specify_cli/cli/commands/agent/mission.py",
    "src/specify_cli/cli/commands/agent/mission_finalize.py",
    "src/specify_cli/cli/commands/agent/mission_finalize_commit.py",
    "src/specify_cli/cli/commands/agent/mission_finalize_validation.py",
    "src/specify_cli/cli/commands/agent/mission_create.py",
    "src/specify_cli/cli/commands/agent/mission_branch_context.py",
    "src/specify_cli/cli/commands/agent/tasks_finalize.py",
    "src/specify_cli/ownership/kind_normalisation.py",
)


@pytest.fixture(scope="module")
def owners() -> frozenset[str]:
    """The modules whose shard EXECUTES the key-shape test, resolved by the shard's own resolver.

    Not ``select_modules([KEY_SHAPE_TEST])``: that maps a test path to the modules a src change
    would select (the selection mirror), which is non-empty even for a nightly-only directory.
    """
    registry = yaml.safe_load(Path(DEFAULT_REGISTRY_PATH).read_text(encoding="utf-8"))
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(_REPO_ROOT)  # the resolver keeps only directories that exist, relative to the root
        return frozenset(
            str(row["module"])
            for row in registry["modules"]
            if any(
                KEY_SHAPE_TEST.startswith(f"{directory.rstrip('/')}/")
                for directory in resolve_module_test_dirs(str(row["module"]), json.dumps(row.get("test_dirs") or []))
            )
        )


def test_the_tree_is_claimed_by_execution_context_only(owners: frozenset[str]) -> None:
    assert out_of_matrix_test_paths([KEY_SHAPE_TEST]) == ()
    assert owners == frozenset({"execution_context"})


def test_the_out_of_matrix_lookup_is_not_vacuous() -> None:
    """Negative control: a still-recorded sibling is reported, so ``()`` above means "claimed"."""
    assert out_of_matrix_test_paths([STILL_OUT_OF_MATRIX_TEST]) != ()


def test_replaying_pr_7809_runs_the_key_shape_test(owners: frozenset[str]) -> None:
    """#7809's src change, replayed, selects a module whose shard runs the key-set pin."""
    assert select_modules(PR_7809_SRC_PATHS) & owners


@pytest.mark.parametrize("path", ORCHESTRATOR_SURFACE_PATHS)
def test_an_orchestrator_surface_edit_alone_runs_the_tests(path: str, owners: frozenset[str]) -> None:
    assert select_modules([path]) & owners


def test_a_neighbouring_src_edit_does_not_select_the_row(owners: frozenset[str]) -> None:
    """Negative control: selection is not "every row", so the positives are not vacuous."""
    assert not select_modules(["src/specify_cli/release/__init__.py"]) & owners


def test_the_shard_selection_collects_the_key_shape_test() -> None:
    """The shard runs ``-m MODULE_SELECTION_MARKER_EXPR``; a later mark must not drop the pin silently."""
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", KEY_SHAPE_NODE, "-m", MODULE_SELECTION_MARKER_EXPR, "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert KEY_SHAPE_NODE in collected.stdout.splitlines(), collected.stdout + collected.stderr
