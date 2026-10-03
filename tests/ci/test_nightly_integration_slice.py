"""The nightly integration slice is a real lane, and the checkup is non-vacuous.

``tests/characterization/test_trio_json_envelope.py`` is marked ``integration``
and ``git_repo`` only. It is not under a module ``test_dirs`` root, and the
interpreter shard that lists ``tests/characterization`` selects
``fast or unit``. Nothing else runs it. The static gate model still reports
zero orphans, because ``module-tests.yml``'s pytest line has no static paths
and the model then treats ``-m "not performance and not stress"`` as the
whole tree. This file is the checkup that does not trust that reading.

Charter review (no dead code) is the second half: a public function of the
selector that the workflow and these tests never name is a finding.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.ci.integration_slice import (
    SLICE_MARKER_EXPR,
    covered_prefixes,
    stranded_integration_files,
    unreferenced_public_functions,
)

pytestmark = [pytest.mark.fast]

_REPO = Path(__file__).resolve().parents[2]
_SELECTOR = _REPO / "scripts" / "ci" / "integration_slice.py"
_WORKFLOW = _REPO / ".github" / "workflows" / "ci-nightly.yml"
_TRIO = "tests/characterization/test_trio_json_envelope.py"
_JOB = "integration-slice"


def _workflow() -> dict[str, object]:
    loaded = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _job_run_text(job: dict[str, object]) -> str:
    steps = job.get("steps")
    if not isinstance(steps, list):
        return ""
    parts: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        run = step.get("run")
        if isinstance(run, str):
            parts.append(run)
    return "\n".join(parts)


def test_stranded_integration_file_is_selected_until_its_directory_is_covered(tmp_path: Path) -> None:
    """Planted break: covering the file's directory drops it from the slice."""
    characterization = tmp_path / "tests" / "characterization"
    characterization.mkdir(parents=True)
    (characterization / "test_trio.py").write_text(
        "import pytest\npytestmark = pytest.mark.integration\n\ndef test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    home = tmp_path / "tests" / "integration"
    home.mkdir()
    (home / "test_home.py").write_text(
        "import pytest\npytestmark = pytest.mark.integration\n\ndef test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    fast = tmp_path / "tests" / "cli"
    fast.mkdir()
    (fast / "test_fast.py").write_text(
        "import pytest\npytestmark = [pytest.mark.integration, pytest.mark.fast]\n\ndef test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    found = stranded_integration_files(tmp_path, covered=("tests/integration",))
    assert found == ["tests/characterization/test_trio.py"]
    covered_too = stranded_integration_files(
        tmp_path,
        covered=("tests/integration", "tests/characterization"),
    )
    assert covered_too == []


def test_dead_code_checkup_flags_an_unreferenced_function(tmp_path: Path) -> None:
    """Planted break: a public function nothing calls is dead code."""
    module = tmp_path / "sample.py"
    module.write_text(
        "def used():\n    return 1\n\ndef unused():\n    return 2\n\ndef main():\n    return used()\n",
        encoding="utf-8",
    )
    caller = tmp_path / "caller.py"
    caller.write_text("main()\n", encoding="utf-8")
    assert unreferenced_public_functions(module, [module, caller]) == ["unused"]


def test_live_trio_envelope_is_on_the_slice_and_directory_lanes_are_not() -> None:
    files = stranded_integration_files(_REPO)
    assert _TRIO in files
    assert all(not path.startswith("tests/integration/") for path in files)
    assert all(not path.startswith("tests/next/") for path in files)
    prefixes = covered_prefixes(_REPO)
    assert "tests/integration" in prefixes
    assert all(not any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes) for path in files)


def test_selector_has_no_dead_public_function() -> None:
    corpus = [_SELECTOR, _WORKFLOW, Path(__file__)]
    assert unreferenced_public_functions(_SELECTOR, corpus) == []


def test_nightly_job_runs_the_slice_and_fails_closed_when_it_is_empty() -> None:
    workflow = _workflow()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[_JOB]
    assert isinstance(job, dict)
    run_text = _job_run_text(job)
    assert "python -m scripts.ci.integration_slice" in run_text
    assert f'-m "{SLICE_MARKER_EXPR}"' in run_text
    assert "--dist loadfile" in run_text
    assert "-ne 5" not in run_text
    assert "${INTEGRATION_SLICE_EXIT:-1}" in run_text
    assert "--suite-key integration-slice" in run_text
    summary = jobs["nightly-summary"]
    assert isinstance(summary, dict)
    assert _JOB in summary["needs"]
