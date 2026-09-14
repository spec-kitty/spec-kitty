"""Coverage breadth: every matrix slice measures the FULL top-level package set.

Mission ``sonar-per-pr-coverage-reuse-01M2FR32``, WP01 (FR-013 / FR-016 / NFR-009).

Why this gate exists
--------------------
``.github/workflows/module-tests.yml`` used to build one ``--cov=<target>`` flag per
entry of its per-module ``cov_target`` input (the registry row's *ownership*
declaration). 16 of the 17 registry rows declare a **narrow** target, so each slice
measured only the package its module is named for.

That is not a cosmetic narrowing. ``coverage.py`` does not record an executed line
outside its measurement scope as *zero* — it **drops** the measurement entirely, so
the line is `absent` from the report. Slices routinely execute code belonging to
other packages (a ``lanes`` test that walks the status store, a ``cli`` test that
drives the whole command surface), and every one of those hits was silently
discarded before it reached the reconciled union. Measured consequence at planning
time: the matrix union recorded 71,070 covered statements (55.15% of the
128,878-statement union) while the single broad step the mission retires recorded
42,933 (33.31%) — with 4,391 statements covered by the retiring step and by no
slice at all.

The fix belongs in the **runner**, not the inventory: ``.github/ci-module-registry.yml``
and ``tests/release/ci_retirement_scrub.json`` are census-derived ownership records
whose ``cov_targets`` must stay byte-identical
(``tests/architectural/test_module_shard_registry.py::test_registry_consumes_scrub_verbatim_no_divergent_rescrub``).
So the registry keeps declaring *who owns what*, and this gate pins *what every
slice measures*.

What is asserted
----------------
* the coverage targets the pytest step emits are the full top-level set **derived
  from the source tree** — never a transcribed literal, which would be a second
  authority that drifts the first time a package is added or renamed;
* that derivation cannot vary per matrix input (no workflow-expression
  interpolation reaches it, and the step no longer consumes ``cov_target``);
* the ``cov_target`` input itself is retained, because other gates read it as the
  ownership declaration.

FR-016 (the marker-mismatch exception set) and the committed per-file baselines are
asserted at the bottom of this file against ``tests/release/coverage_breadth_baseline.json``.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "module-tests.yml"
_MAKEFILE_PATH = _REPO_ROOT / "Makefile"
_BASELINE_PATH = _REPO_ROOT / "tests" / "release" / "coverage_breadth_baseline.json"

# The ``id:`` of the step that actually invokes pytest with the coverage flags.
_PYTEST_STEP_ID = "pytest-run"

# The heredoc delimiter the pytest step uses for the program that emits the
# coverage targets. Naming it here (rather than matching the whole ``run:`` block)
# keeps this gate a *behaviour* assertion: the block can be reformatted, re-ordered
# or re-commented freely as long as the emitted target set stays correct.
_COV_PROGRAM_DELIMITER = "COV_PY"

_NO_PROGRAM_HINT = (
    f"{_WORKFLOW_PATH.relative_to(_REPO_ROOT)}'s {_PYTEST_STEP_ID!r} step does not derive its "
    f"coverage targets from the source tree (no <<'{_COV_PROGRAM_DELIMITER}' program found).\n"
    "It still builds one --cov flag per entry of the per-module `inputs.cov_target`, so each "
    "slice measures ONLY its own module's package and every line it executes outside that "
    "package is DROPPED from the report (coverage.py does not record it as zero — it records "
    "nothing at all).\n"
    "See mission sonar-per-pr-coverage-reuse-01M2FR32 WP01 / FR-013."
)


# ---------------------------------------------------------------------------
# Derivations — every expected value below comes from a canonical on-disk
# authority (the source tree, the Makefile, the workflow), never a literal.
# ---------------------------------------------------------------------------
def expected_coverage_targets() -> list[str]:
    """The full top-level coverage-target set, derived from ``src/``.

    A target is importable top-level *code*: a directory holding ``__init__.py``
    (a package) or a public single-file module (``src/doctrine.py``, the
    ``charter.offering`` compatibility shim). Both forms are measured by the step
    this mission retires, so both must stay measured or a file loses coverage.
    """
    targets: set[str] = set()
    for entry in sorted(_SRC.iterdir()):
        if entry.is_dir() and (entry / "__init__.py").is_file():
            targets.add(entry.name)
        elif entry.is_file() and entry.suffix == ".py" and not entry.name.startswith("_"):
            targets.add(entry.stem)
    return sorted(targets)


def _workflow() -> dict[str, Any]:
    return dict(yaml.safe_load(_WORKFLOW_PATH.read_text(encoding="utf-8")))


def _pytest_step_script() -> str:
    steps = _workflow()["jobs"]["test"]["steps"]
    for step in steps:
        if step.get("id") == _PYTEST_STEP_ID:
            return str(step["run"])
    raise AssertionError(
        f"{_WORKFLOW_PATH.relative_to(_REPO_ROOT)} has no step with id {_PYTEST_STEP_ID!r}; this gate can no longer locate the coverage invocation."
    )


def _extract_cov_target_program(script: str) -> str | None:
    """Return the heredoc program that emits the coverage targets, if present."""
    opener = f"<<'{_COV_PROGRAM_DELIMITER}'"
    if opener not in script:
        return None
    body = script.split(opener, 1)[1]
    lines: list[str] = []
    for line in body.splitlines()[1:]:
        if line.strip() == _COV_PROGRAM_DELIMITER:
            return "\n".join(lines)
        lines.append(line)
    return None


def _without_comments(script: str) -> str:
    """Drop comment-only lines so a *prose* mention is never read as a consumption."""
    return "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("#"))


def _emitted_coverage_targets(program: str) -> list[str]:
    """Run the workflow's own program and return what it emits, sorted."""
    completed = subprocess.run(
        [sys.executable, "-c", program],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, (
        f"the coverage-target program embedded in {_WORKFLOW_PATH.relative_to(_REPO_ROOT)} exited {completed.returncode}:\n{completed.stderr}"
    )
    return sorted(line.strip() for line in completed.stdout.splitlines() if line.strip())


def _makefile_variable(name: str) -> str:
    text = _MAKEFILE_PATH.read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(name)}\s*[:?+]?=\s*(?P<value>.*)$", text, re.MULTILINE)
    assert match is not None, f"Makefile no longer defines {name}; the retiring step's selection cannot be derived."
    return match.group("value").strip()


def _slice_marker_expression() -> str:
    """The marker expression every matrix slice applies, read from the workflow."""
    match = re.search(r'-m\s+"(?P<expr>[^"]+)"', _pytest_step_script())
    assert match is not None, "module-tests.yml's pytest step no longer carries a quoted -m expression."
    return match.group("expr")


def _collect_node_ids(paths: list[str], marker_expression: str) -> set[str]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *paths,
            "-m",
            marker_expression,
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    node_ids = {line.strip() for line in completed.stdout.splitlines() if "::" in line}
    assert node_ids, (
        f"pytest collected nothing for {paths!r} under -m {marker_expression!r} "
        f"(exit {completed.returncode}):\n{completed.stdout[-2000:]}\n{completed.stderr[-2000:]}"
    )
    return node_ids


def derive_marker_mismatch_exception_set() -> list[str]:
    """FR-016: tests the retiring step selects and every matrix slice deselects.

    The retired step's marker expression (``Makefile``'s ``FAST_TIER_MARKERS``,
    which ``ci-quality.yml``'s ``sonarcloud`` job ran via ``make test-fast`` until
    mission ``sonar-per-pr-coverage-reuse``, #4334) did not
    exclude the ``performance`` family; every matrix slice does
    (``module-tests.yml``'s ``-m "not performance"``). Over the same directories,
    the difference is exactly the declared exception to "no per-file regression".

    Derived on every run — never transcribed — so the set can be re-checked rather
    than re-read.
    """
    dirs = _makefile_variable("FAST_TIER_DIRS").split()
    retiring = _collect_node_ids(dirs, _makefile_variable("FAST_TIER_MARKERS"))
    slices = _collect_node_ids(dirs, _slice_marker_expression())
    return sorted(retiring - slices)


def _baseline() -> dict[str, Any]:
    assert _BASELINE_PATH.exists(), (
        f"{_BASELINE_PATH.relative_to(_REPO_ROOT)} is missing; NFR-009/SC-004 compare against a "
        "recorded baseline, and a baseline with no path is one an implementer invents at "
        "approval time."
    )
    return dict(json.loads(_BASELINE_PATH.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# T001/T002 — breadth
# ---------------------------------------------------------------------------
def test_every_shard_measures_the_full_top_level_package_set() -> None:
    program = _extract_cov_target_program(_pytest_step_script())
    assert program is not None, _NO_PROGRAM_HINT

    assert _emitted_coverage_targets(program) == expected_coverage_targets(), (
        "the coverage targets module-tests.yml emits are not the full top-level set derived "
        "from src/. Every slice must measure every package, or cross-module coverage is dropped "
        "from the reconciled union (FR-013)."
    )


def test_coverage_targets_cannot_vary_per_matrix_input() -> None:
    script = _pytest_step_script()
    program = _extract_cov_target_program(script)
    assert program is not None, _NO_PROGRAM_HINT

    assert "${{" not in program, (
        "the coverage-target program interpolates a workflow expression, so the measured set can "
        "still vary per matrix row. Breadth must be constant across slices (FR-013)."
    )
    assert "inputs.cov_target" not in _without_comments(script), (
        f"the {_PYTEST_STEP_ID!r} step still consumes `inputs.cov_target`. That input is the "
        "registry row's OWNERSHIP declaration, read verbatim by "
        "tests/architectural/test_module_shard_registry.py — it must not drive what a slice "
        "MEASURES."
    )


def test_cov_target_input_is_retained_as_the_ownership_declaration() -> None:
    """Breadth moves to the runner; the inventory's declaration stays put."""
    workflow = _workflow()
    # YAML 1.1 parses the bare `on:` key as the boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict)
    for trigger in ("workflow_call", "workflow_dispatch"):
        inputs = triggers[trigger]["inputs"]
        assert "cov_target" in inputs, (
            f"the {trigger!r} `cov_target` input was removed. WP01 changes what the runner "
            "measures, not what the inventory declares — the caller (ci-modules.yml) and the "
            "registry gates still depend on this input existing."
        )


# ---------------------------------------------------------------------------
# T005/T004/T006 — exception set and baselines
# ---------------------------------------------------------------------------
def test_baseline_records_its_own_provenance() -> None:
    baseline = _baseline()
    exception_set = baseline["marker_mismatch_exception_set"]
    assert exception_set["derivation"].endswith("derive_marker_mismatch_exception_set"), (
        "the exception set must name the committed derivation that produces it, so it can be re-derived rather than re-read (FR-016)."
    )
    assert exception_set["retiring_step_selection"]["marker_expression"] == _makefile_variable("FAST_TIER_MARKERS")
    assert exception_set["retiring_step_selection"]["paths"] == _makefile_variable("FAST_TIER_DIRS").split()
    assert exception_set["slice_selection"]["marker_expression"] == _slice_marker_expression()

    retiring = baseline["per_file_covered"]["retiring_step"]
    assert retiring["command"], "the retiring step's per-file baseline must cite the command that produced it."
    assert retiring["files"], "the retiring step's per-file baseline is empty."


def test_marker_mismatch_exception_set_is_reproducible() -> None:
    """Re-run the derivation; the committed output must come back unchanged.

    Two ``--collect-only`` passes over the fast-tier directories (~10 s together) —
    deliberately kept in the blocking architectural gate rather than marked slow, so
    a selection change that silently widens the exception set cannot land unnoticed.
    """
    baseline = _baseline()
    committed = list(baseline["marker_mismatch_exception_set"]["node_ids"])
    assert derive_marker_mismatch_exception_set() == committed, (
        "the committed marker-mismatch exception set no longer reproduces. Re-derive it and "
        "re-check WP01's no-regression verdict — do not widen the set to make this pass."
    )
