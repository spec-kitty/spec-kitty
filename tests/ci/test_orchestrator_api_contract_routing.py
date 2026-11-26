"""Pin the per-PR home of the orchestrator-api contract-shape tests (#7870, operator ruling 2026-11-25).

``tests/contract/test_orchestrator_api.py`` checks the orchestrator-api command set, envelope and error
codes against the vendored ``upstream_contract.json`` and the two prose surfaces that enumerate the codes.
It carries ``contract`` and ``fast`` but no ``corpus`` mark, and both ``tests/contract`` router jobs select
``-m "corpus and not windows_ci"``, so no per-PR job ran it: an orchestrator-api change that broke the
contract passed its PR and turned ``main`` red in the nightly -- the class that blocked the RC9 cut
(#7829, #7835, #7846).

The ruling (option A) gives it a path-routed router job, ``tests (orchestrator-api contract)``, gated on a
NON-src group and wired into ``router-gate``. The job's paths are ``gate_selection.CONTRACT_SHAPE_PR_PATHS``,
so the other non-corpus ``tests/contract`` modules (#7874) join by appending a module there and its
triggers to the group: every rule below is derived per module, never written for this one file.

Every assertion reads the parsed router (``scripts/ci/gate_selection.py``), the on-disk workflow and
scrub, or the module's own source; none restates the routing.
"""

from __future__ import annotations

import ast
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.gate_selection import CONTRACT_SHAPE_PR_PATHS, load_router, select_gates
from scripts.ci.router_gate import ADVISORY_JOB_NAMES
from tests.ci._gh_if import BASE_CONTEXT_ALL_FALSE, eval_gh_if

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / ".github" / "workflows" / "ci-router.yml"
SCRUB = ROOT / "tests" / "release" / "ci_retirement_scrub.json"
SRC = ROOT / "src"

GROUP = "orchestrator_api_contract"
JOB = "tests-orchestrator-api-contract"
JOB_NAME = "tests (orchestrator-api contract)"
CONTRACT_MODULE = "tests/contract/test_orchestrator_api.py"
CONTRACT_CONFTEST = "tests/contract/conftest.py"

#: The changes that can break the contract-shape module, each alone: the verb surface, the vendored
#: contract the conftest loads, the contract layer every envelope passes through, the error classes the
#: module imports, the two prose surfaces it parses (read through ``_REPO_ROOT / relative``) and the
#: module and conftest themselves.
POSITIVE_PATHS: tuple[str, ...] = (
    "src/specify_cli/orchestrator_api/commands.py",
    "src/specify_cli/orchestrator_api/envelope.py",
    "src/specify_cli/orchestrator_api/decision_verbs.py",
    "src/specify_cli/core/upstream_contract.json",
    "src/specify_cli/core/contract_gate.py",
    "src/specify_cli/missions/_read_path_resolver.py",
    "src/specify_cli/git/commit_helpers.py",
    "docs/api/orchestrator-api.md",
    "src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md",
    CONTRACT_MODULE,
    CONTRACT_CONFTEST,
)

#: Same-fixture negative controls: real, mapped paths that must NOT select the lane.
NEGATIVE_PATHS: tuple[str, ...] = (
    "src/specify_cli/release/__init__.py",
    "docs/development/how-to/manage-issue-tracker.md",
    "tests/contract/test_terminology_guards.py",
    "src/charter/offering/skills/spec-kitty-runtime-review/SKILL.md",
)


#: Paths that can change the outcome yet are not shape surfaces: what the tests run on (the
#: contract_tools precedent). Each must select the lane too.
ENVIRONMENT_PATHS: tuple[str, ...] = ("tests/conftest.py", "pytest.ini", "pyproject.toml", "uv.lock")


def _jobs() -> dict[str, Any]:
    return dict(yaml.safe_load(ROUTER.read_text(encoding="utf-8"))["jobs"])


def _pytest_command(job: dict[str, Any]) -> str:
    logical = "\n".join(str(step.get("run", "")) for step in job.get("steps", [])).replace("\\\n", " ")
    commands = [line for line in logical.splitlines() if re.search(r"(?<![\w-])pytest(?![\w-])", line)]
    assert len(commands) == 1, f"the lane must run exactly one pytest command, found {commands}"
    return commands[0]


def _pytest_arguments(command: str) -> list[str]:
    """The arguments after ``pytest`` in the lane's command, shell-split."""
    words = shlex.split(command)
    return words[words.index("pytest") + 1 :]


def _src_files_imported_by(module: str) -> set[str]:
    """The ``src/`` files a test module imports at any depth of its body (``from x import y`` / ``import x``)."""
    packages = {entry.name for entry in SRC.iterdir() if entry.is_dir() and not entry.name.startswith((".", "_"))}
    imported: set[str] = set()
    for node in ast.walk(ast.parse((ROOT / module).read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        else:
            continue
        for name in names:
            if name.split(".")[0] not in packages:
                continue
            base = Path("src", *name.split("."))
            for candidate in (base.with_suffix(".py"), base / "__init__.py"):
                if (ROOT / candidate).is_file():
                    imported.add(candidate.as_posix())
    return imported


def _repo_files_read_by(module: str) -> set[str]:
    """The repository files a module names as string literals and reads (a ``docs/`` or ``src/`` path that exists).

    Adjacent literals are joined first (``"a/" "b.md"``), the way the module spells its long skill path.
    """
    tree = ast.parse((ROOT / module).read_text(encoding="utf-8"))
    literals = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    return {literal for literal in literals if literal.startswith(("docs/", "src/")) and "." in literal.rsplit("/", 1)[-1] and (ROOT / literal).is_file()}


@pytest.mark.parametrize("path", POSITIVE_PATHS + ENVIRONMENT_PATHS)
def test_a_path_that_can_break_the_contract_selects_the_lane(path: str) -> None:
    router = load_router()

    selection = select_gates([path], router=router)

    assert GROUP in selection.matched_groups, f"{path} can break the orchestrator-api contract but misses the {GROUP} group"
    assert JOB in selection.selected_jobs, f"{path} selects {GROUP} but not the job gated on it"


@pytest.mark.parametrize("path", NEGATIVE_PATHS)
def test_an_unrelated_diff_does_not_select_the_lane(path: str) -> None:
    selection = select_gates([path], router=load_router())

    assert GROUP not in selection.matched_groups, f"{path} must not route the orchestrator-api contract lane"
    assert JOB not in selection.selected_jobs


@pytest.mark.parametrize("module", CONTRACT_SHAPE_PR_PATHS)
def test_every_src_file_and_prose_surface_a_lane_module_reads_selects_the_lane(module: str) -> None:
    """Derived per module, so a #7874 module that joins CONTRACT_SHAPE_PR_PATHS is held to the same rule.

    The property is "the job runs", not "the group matches": a bare package ``__init__`` (``from
    specify_cli import orchestrator_api`` names ``src/specify_cli/__init__.py``) is deliberately left to
    the FR-004 fail-closed catch-all, which runs every gated job, this lane included.
    """
    imported, read = _src_files_imported_by(module), _repo_files_read_by(module)
    assert imported, f"non-vacuity: the import scan found no src file in {module}"
    if module == CONTRACT_MODULE:
        # non-vacuity: the string-literal scan sees the two enumeration surfaces the module parses
        assert read >= {
            "docs/api/orchestrator-api.md",
            "src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md",
        }
    router = load_router()

    missing = sorted(path for path in imported | read | {module} if JOB not in select_gates([path], router=router).selected_jobs)

    assert missing == [], f"a change to these files runs no `{JOB_NAME}`: {missing}"


def test_the_lane_runs_exactly_the_registered_modules_with_no_narrowing() -> None:
    """One invocation naming CONTRACT_SHAPE_PR_PATHS, no ``-m``/``-k``/``--ignore``: nothing can collect zero silently."""
    job = _jobs()[JOB]
    arguments = _pytest_arguments(_pytest_command(job))

    assert job["name"] == JOB_NAME
    assert CONTRACT_MODULE in CONTRACT_SHAPE_PR_PATHS
    assert [argument for argument in arguments if not argument.startswith("-")] == list(CONTRACT_SHAPE_PR_PATHS), arguments
    narrowing = ("-m", "-k", "--markexpr", "--keyword", "--ignore", "--deselect")
    assert not [argument for argument in arguments if argument.startswith(narrowing)], arguments


def _collected(paths: tuple[str, ...], marker: str) -> list[str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *paths, "-m", marker, "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return [line for line in result.stdout.splitlines() if "::" in line]


def test_the_lane_modules_collect_nothing_under_the_corpus_jobs_marker() -> None:
    """Really collected, not text-searched: a corpus-marked test already has its one home in the corpus jobs
    (test_contracts_routing.py), so the lane would double-run it; and the gap this lane closes is real."""
    assert _collected(CONTRACT_SHAPE_PR_PATHS, "corpus and not windows_ci") == []
    assert _collected(CONTRACT_SHAPE_PR_PATHS, "not corpus"), "non-vacuity: the lane modules collect tests"


def test_the_lane_is_blocking_and_gated_on_the_group_alone() -> None:
    """Gated on the group only: the module reads docstrings (inspect.getsource), so a prose-only diff must still run it."""
    jobs = _jobs()

    assert JOB not in ADVISORY_JOB_NAMES, "the lane must gate the run, not be advisory"
    assert jobs[JOB]["needs"] == ["changes"]
    context = dict(BASE_CONTEXT_ALL_FALSE)
    context[f"changes.{GROUP}"] = True
    assert eval_gh_if(jobs[JOB]["if"], context) is True
    assert eval_gh_if(jobs[JOB]["if"], {**context, f"changes.{GROUP}": False}) is False


def test_the_group_stays_non_src_and_out_of_the_fail_closed_union() -> None:
    """A ``src/``-spelled glob would make the group src-backed (a code-shard group); ``**/`` keeps it a lane trigger."""
    router = load_router()

    assert GROUP not in router.src_backed_groups
    assert not [glob for glob in router.filters[GROUP] if glob.startswith("src/")]
    (unmatched,) = [step for step in _jobs()["changes"]["steps"] if step.get("id") == "unmatched"]
    assert f"steps.filter.outputs.{GROUP}" not in unmatched["run"]


def test_the_scrub_row_is_the_router_group_verbatim() -> None:
    scrub = json.loads(SCRUB.read_text(encoding="utf-8"))
    (row,) = [row for row in scrub["non_src_router_groups"] if row["group"] == GROUP]

    assert list(row["roots"]) == list(load_router().filters[GROUP])
