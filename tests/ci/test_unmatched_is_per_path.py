"""The FR-004 fail-closed ``unmatched`` signal is computed per path (#7775).

Before #7775 it was computed per diff: ``any src/** changed AND no src-backed group
matched``. One routed src path in a diff therefore masked every unrouted src path
beside it, and the diff ran a narrowed module set. That is how #7763's
``src/specify_cli/skills/**`` change (no src group) rode along with routed
``runtime/**`` and ``tool_surface/**`` paths and ran no ``upgrade`` shard.

Now a diff is run-all when ANY ``src/**`` path matches no src-backed group. Both
evaluators are pinned: the Python authority ``select_gates`` (which builds the
module matrix in ``ci-modules.yml``) and the ``unmatched`` bash step of
``ci-router.yml`` (which gates the router's own jobs). The bash step is executed
here as written in the workflow, with the dorny ``*_files`` outputs it reads
supplied through its ``env``.
"""

from __future__ import annotations

import fnmatch
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.gate_selection import DEFAULT_ROUTER_PATH, load_router, select_gates, select_modules

pytestmark = pytest.mark.fast

UNROUTED = "src/specify_cli/__unrouted_probe__/thing.py"
ROUTED = "src/specify_cli/consolidation/executor.py"
ROUTED_TOO = "src/specify_cli/lanes/persistence.py"


def test_unrouted_src_path_beside_routed_src_paths_forces_run_all() -> None:
    """Red on per-diff ``unmatched``: the routed paths used to mask the unrouted one."""
    selection = select_gates([ROUTED, UNROUTED, ROUTED_TOO])
    assert selection.unmatched_src is True
    router = load_router()
    assert selection.selected_code_shards == router.code_shard_jobs


def test_select_modules_runs_every_module_for_a_masked_unrouted_path() -> None:
    every = select_modules(["src/specify_cli/__unrouted_probe__/x.py"])
    assert select_modules([ROUTED, UNROUTED]) == every


def test_fully_routed_diff_stays_narrow() -> None:
    selection = select_gates([ROUTED, ROUTED_TOO])
    assert selection.unmatched_src is False


def test_non_src_paths_never_trip_unmatched() -> None:
    assert select_gates([ROUTED, "docs/x.md", "tests/ci/test_x.py", "scripts/ci/x.py"]).unmatched_src is False


# --- the workflow's bash step, executed --------------------------------------------------------


def _unmatched_step() -> dict[str, Any]:
    workflow = yaml.safe_load(DEFAULT_ROUTER_PATH.read_text(encoding="utf-8"))
    return next(step for step in workflow["jobs"]["changes"]["steps"] if step.get("id") == "unmatched")


def _filter_step_with() -> dict[str, Any]:
    workflow = yaml.safe_load(DEFAULT_ROUTER_PATH.read_text(encoding="utf-8"))
    step = next(step for step in workflow["jobs"]["changes"]["steps"] if step.get("id") == "filter")
    return dict(step["with"])


def _dorny_files(group: str, paths: list[str]) -> list[str]:
    globs = load_router().filters[group]
    return [path for path in paths if any(fnmatch.fnmatch(path, glob) for glob in globs)]


def _run_unmatched_step(paths: list[str], tmp_path: Path) -> str:
    """Run the step's bash body with each ``env`` entry resolved the way dorny would fill it."""
    step = _unmatched_step()
    env = dict(os.environ)
    for name, expression in step["env"].items():
        ref = str(expression).strip().removeprefix("${{").removesuffix("}}").strip()
        output = ref.removeprefix("steps.filter.outputs.")
        if output.endswith("_files"):
            env[name] = json.dumps(_dorny_files(output.removesuffix("_files"), paths))
        else:
            env[name] = "true" if _dorny_files(output, paths) else "false"
    github_output = tmp_path / "github_output"
    github_output.write_text("", encoding="utf-8")
    env["GITHUB_OUTPUT"] = str(github_output)
    subprocess.run(["bash", "-euo", "pipefail", "-c", step["run"]], env=env, check=True, capture_output=True, text=True)
    lines = [line for line in github_output.read_text(encoding="utf-8").splitlines() if line.startswith("unmatched=")]
    assert len(lines) == 1, lines
    return lines[0].removeprefix("unmatched=")


needs_jq = pytest.mark.skipif(shutil.which("jq") is None, reason="the workflow step uses jq (preinstalled on GitHub runners)")


@needs_jq
@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        ([ROUTED, UNROUTED, ROUTED_TOO], "true"),
        ([UNROUTED], "true"),
        ([ROUTED, ROUTED_TOO], "false"),
        (["docs/x.md"], "false"),
        ([ROUTED, "src/specify_cli/__init__.py"], "true"),
        (["src/specify_cli/skills/installer.py", ROUTED], "false"),
    ],
)
def test_workflow_unmatched_step_is_per_path(paths: list[str], expected: str, tmp_path: Path) -> None:
    assert _run_unmatched_step(paths, tmp_path) == expected
    assert str(select_gates(paths).unmatched_src).lower() == expected


def test_filter_step_lists_files_as_json() -> None:
    """The per-path step reads dorny's ``<group>_files`` outputs, which need ``list-files: json``."""
    assert _filter_step_with().get("list-files") == "json"


def test_unmatched_step_never_inlines_file_lists_into_the_script() -> None:
    """File names are PR-controlled: they reach the script only through ``env``, never ``${{ }}`` in ``run``."""
    assert "${{" not in _unmatched_step()["run"]


def test_src_router_globs_use_only_double_star_and_literal_segments() -> None:
    """``fnmatch`` stands in for dorny's picomatch only while src globs avoid single-segment wildcards.

    ``select_gates`` / ``unrouted_src_paths`` (and this module's execution of the bash step) judge
    paths with :func:`fnmatch.fnmatch`, whose ``*`` also crosses ``/``; picomatch's does not. The two
    agree on a glob whose segments are each either ``**`` or a literal, so every src-backed group's
    glob must have that shape or the Python answer and the workflow's answer can diverge.
    """
    router = load_router()
    bad = [
        (group, glob)
        for group in sorted(router.src_backed_groups)
        for glob in router.filters[group]
        for segment in glob.split("/")
        if segment != "**" and any(char in segment for char in "*?[]{}")
    ]
    assert not bad, f"src-backed router globs with a non-literal segment other than '**': {bad}"
