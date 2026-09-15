"""Mis-mark guard for ``@pytest.mark.performance`` tests (#3665, FR-020).

The nightly full-mode lane (``ci-nightly.yml``, mission
``ci-pipeline-reinstatement-01M1X35E`` WP13/T6) moves performance / heavy-e2e /
interpreter-matrix jobs off the per-PR blocking path onto a nightly + manual-
dispatch cadence (#3595). That move only stays honest if a test can never be
mis-marked ``@pytest.mark.performance`` to *dodge* the PR gate while still
carrying functional coverage: a performance-marked test may assert wall-clock
/ timing-budget facts only (:data:`TIMING_ASSERTION_VOCABULARY`); any other
assertion in its body is functional coverage smuggled onto the nightly-only
cadence, off the per-PR path — a mis-mark this guard flags.

:func:`find_functional_assertions_under_performance_marker` is the pure,
collection-free guard: it takes Python **source text** (never a real,
permanently-collected test) so the planted mis-marked/correctly-marked
fixtures below never become carriers any other marker-completeness gate has
to route (``test_marker_job_completeness.py`` /
``test_fast_tier_marker_completeness.py`` stay untouched by this file).

SC-011 (a per-PR run executes 0 performance/heavy-e2e/interpreter jobs) is
asserted the same way: statically, over the on-disk workflow YAML, never by
actually dispatching a run.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

if TYPE_CHECKING:
    from collections.abc import Iterable

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
NIGHTLY_WORKFLOW = WORKFLOWS_DIR / "ci-nightly.yml"

# A `@pytest.mark.performance` test's body may assert wall-clock / timing-
# budget facts ONLY. An assert whose expression text contains none of these
# tokens is treated as a functional (non-timing) assertion -- the #3665
# mis-mark this guard exists to flag. Additions are LOUD (loosen deliberately,
# reviewed); this is the complete permitted vocabulary today.
TIMING_ASSERTION_VOCABULARY: frozenset[str] = frozenset(
    {
        "elapsed",
        "duration",
        "wall_clock",
        "perf_counter",
        "monotonic",
        "budget",
        "benchmark",
        "seconds",
        "timeout",
    },
)

# Decorator spellings that mark a test performance-tier. Both the bare
# ``@pytest.mark.performance`` and the parametrized-call form
# ``@pytest.mark.performance(...)`` are recognized.
_PERFORMANCE_MARKER_QUALNAME = "pytest.mark.performance"


def _decorator_qualname(node: ast.expr) -> str:
    """Render a decorator expression back to its dotted-name text.

    Unwraps the ``Call`` form (``@pytest.mark.performance(reason=...)``) to
    its callee before rendering, so both spellings resolve to the same
    qualname.
    """
    target = node.func if isinstance(node, ast.Call) else node
    return ast.unparse(target)


def _is_performance_marked(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(_decorator_qualname(decorator) == _PERFORMANCE_MARKER_QUALNAME for decorator in func.decorator_list)


def _iter_asserts(func: ast.FunctionDef | ast.AsyncFunctionDef) -> Iterable[ast.Assert]:
    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            yield node


def find_functional_assertions_under_performance_marker(source: str) -> list[str]:
    """Return one violation message per mis-marked ``@pytest.mark.performance`` test.

    Parses ``source`` (arbitrary Python text -- never a collected test file)
    and, for every function decorated ``@pytest.mark.performance``, checks
    each ``assert`` statement in its body against
    :data:`TIMING_ASSERTION_VOCABULARY`. An assert expression that contains
    NONE of those tokens is a functional assertion mis-marked as performance
    (#3665) -- exactly the coverage SC-011 requires stay off the per-PR path
    only when it is genuinely timing-only. ``[]`` means every performance-
    marked function in ``source`` is a clean timing assertion.
    """
    tree = ast.parse(source)
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _is_performance_marked(node):
            continue
        for assert_node in _iter_asserts(node):
            expr_text = ast.unparse(assert_node.test).lower()
            if not any(token in expr_text for token in TIMING_ASSERTION_VOCABULARY):
                violations.append(
                    f"{node.name}: assert at line {assert_node.lineno} "
                    f"({ast.unparse(assert_node.test)!r}) is not a timing-only "
                    "assertion -- functional coverage under "
                    "@pytest.mark.performance is a mis-mark (#3665)",
                )
    return violations


# ---------------------------------------------------------------------------
# Planted fixtures (source TEXT, never real collected tests -- see module
# docstring). One genuinely mis-marked (functional) case, one clean negative
# control so the guard is proven non-vacuous in both directions.
# ---------------------------------------------------------------------------

_MISMARKED_FUNCTIONAL_PERFORMANCE_TEST = '''
import pytest


@pytest.mark.performance
def test_mismarked_functional_check() -> None:
    """Planted #3665 mis-mark: a functional assertion under @performance."""
    result = {"status": "ok", "count": 3}
    assert result == {"status": "ok", "count": 3}
'''

_CLEAN_TIMING_ONLY_PERFORMANCE_TEST = '''
import time

import pytest


@pytest.mark.performance
def test_clean_timing_budget(benchmark) -> None:
    """Legitimate performance test: timing-only assertion."""
    start = time.perf_counter()
    do_work()
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, "wall_clock budget exceeded"
'''


def test_planted_functional_assertion_under_performance_marker_is_flagged() -> None:
    """T066/T070 anchor: a mis-marked functional @performance test IS flagged.

    Red-on-base reason (T066): before the guard vocabulary/walker existed,
    this assertion failed because no violation was ever detected for the
    planted functional test -- a failed behavioral assertion, never a
    collection/import error (the fixture above is source TEXT, not a real
    collected test, so collection itself is unaffected either way).
    """
    violations = find_functional_assertions_under_performance_marker(
        _MISMARKED_FUNCTIONAL_PERFORMANCE_TEST,
    )
    assert violations, "the guard must flag a functional assertion under @pytest.mark.performance"
    assert "test_mismarked_functional_check" in violations[0]


def test_clean_timing_only_performance_test_is_not_flagged() -> None:
    """Negative control: a genuinely timing-only @performance test is clean.

    Proves the guard is not vacuously loud -- it does not flag every
    performance-marked test, only ones lacking any timing-vocabulary token.
    """
    violations = find_functional_assertions_under_performance_marker(
        _CLEAN_TIMING_ONLY_PERFORMANCE_TEST,
    )
    assert violations == []


def test_non_performance_marked_functional_test_is_ignored() -> None:
    """The guard only inspects @pytest.mark.performance-decorated functions."""
    source = """
def test_ordinary_functional_check() -> None:
    assert {"a": 1} == {"a": 1}
"""
    assert find_functional_assertions_under_performance_marker(source) == []


# ---------------------------------------------------------------------------
# T069/DoD -- SC-011: a per-PR run executes 0 performance/heavy-e2e/
# interpreter-matrix jobs. Asserted statically over the on-disk workflow YAML.
# ---------------------------------------------------------------------------

# Tokens that, if present in a PR-triggered workflow, would put a
# performance / heavy-e2e / interpreter-matrix job on the per-PR blocking
# path -- exactly what SC-011 forbids. These jobs live ONLY in
# ci-nightly.yml (schedule + workflow_dispatch).
FORBIDDEN_PR_PATH_TOKENS: tuple[str, ...] = (
    "-m performance",
    "-m e2e",
    "-m 'performance",
    '-m "performance',
    "interpreter-matrix",
)


def _workflow_on_section(path: Path) -> dict[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    section = data.get("on", data.get(True))
    return section if isinstance(section, dict) else {}


def test_nightly_workflow_never_triggers_on_pull_request() -> None:
    """SC-011 / T067: ``ci-nightly.yml`` is schedule + workflow_dispatch ONLY.

    No ``pull_request`` (or ``push``) trigger means a per-PR run can never
    execute any job this workflow defines -- the structural guarantee that 0
    performance/heavy-e2e/interpreter jobs run on the per-PR blocking path.
    """
    assert NIGHTLY_WORKFLOW.exists(), "ci-nightly.yml (T067) must exist"
    on_section = _workflow_on_section(NIGHTLY_WORKFLOW)
    assert "schedule" in on_section
    assert "workflow_dispatch" in on_section
    assert "pull_request" not in on_section
    assert "push" not in on_section


def test_no_pull_request_workflow_selects_performance_or_interpreter_jobs() -> None:
    """SC-011: every OTHER (pull_request-triggered) workflow stays clean.

    Guards against the expensive cadence leaking back onto the PR path via a
    workflow other than ``ci-nightly.yml``.
    """
    offenders: list[str] = []
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        if path == NIGHTLY_WORKFLOW:
            continue
        on_section = _workflow_on_section(path)
        if "pull_request" not in on_section:
            continue
        text = path.read_text(encoding="utf-8")
        offenders.extend(f"{path.name}: forbidden token {token!r} on the per-PR path" for token in FORBIDDEN_PR_PATH_TOKENS if token in text)
    assert not offenders, "\n".join(offenders)


def test_nightly_workflow_is_full_mode_run_all() -> None:
    """T067/DoD: full-mode run-all-regardless (`if: always()`, `fail-fast: false`).

    The nightly lane must surface the complete failure set, never short-
    circuit like the PR fail-fast lanes.
    """
    text = NIGHTLY_WORKFLOW.read_text(encoding="utf-8")
    assert "fail-fast: false" in text
    assert "if: always()" in text


def _job_steps(job: dict[str, object]) -> list[dict[str, object]]:
    steps = job.get("steps")
    return [step for step in steps if isinstance(step, dict)] if isinstance(steps, list) else []


def test_nightly_suite_steps_are_fail_loud() -> None:
    """#4212 / FR-006: a red nightly suite must make its job red.

    Each suite step runs ``pytest`` under ``set +e`` (run-all-regardless), so
    it must NOT terminate on a bare ``echo "...exit=$?"`` that discards
    pytest's exit into an annotation string -- the swallow that kept the job
    green on a red suite. The captured code must instead be consumed by a
    downstream step that can ``exit 1``. This coexists with the run-all guards
    (``if: always()`` / ``fail-fast: false``) asserted in
    :func:`test_nightly_workflow_is_full_mode_run_all`: capture-and-aggregate
    keeps every suite running, then fails loud at the end.
    """
    data = yaml.safe_load(NIGHTLY_WORKFLOW.read_text(encoding="utf-8")) or {}
    jobs = data.get("jobs") or {}
    for job_name in ("performance-and-e2e", "interpreter-matrix"):
        job = jobs.get(job_name)
        assert isinstance(job, dict), f"{job_name} job missing"
        steps = _job_steps(job)
        suite_steps = [step for step in steps if "pytest" in str(step.get("run") or "")]
        assert suite_steps, f"{job_name}: expected at least one pytest suite step"
        for step in suite_steps:
            run = str(step["run"])
            assert "exit=$?" not in run, (
                f"{job_name}: a suite step discards pytest's exit via a bare "
                'echo "...exit=$?" (the #4212 swallow) -- capture $? into '
                "$GITHUB_ENV and let a terminal step fail on it instead"
            )
        assert any("exit 1" in str(step.get("run") or "") for step in steps), (
            f"{job_name}: no terminal fail-loud step that can `exit 1` on a captured suite exit (#4212)"
        )


def test_nightly_workflow_declares_dispatch_and_honors_mode_input() -> None:
    """DoD: declares `workflow_dispatch` and honors the `mode` input (FR-018/019)."""
    data = yaml.safe_load(NIGHTLY_WORKFLOW.read_text(encoding="utf-8")) or {}
    on_section = data.get("on", data.get(True)) or {}
    dispatch = on_section.get("workflow_dispatch") or {}
    inputs = dispatch.get("inputs") or {}
    assert "mode" in inputs
    assert inputs["mode"].get("default") == "full"
    assert "inputs.mode" in NIGHTLY_WORKFLOW.read_text(encoding="utf-8")


def test_nightly_workflow_houses_performance_and_interpreter_jobs() -> None:
    """T067/T068: the nightly lane houses the perf/e2e jobs AND the >3.12
    interpreter matrix, off the per-PR path."""
    data = yaml.safe_load(NIGHTLY_WORKFLOW.read_text(encoding="utf-8")) or {}
    jobs = data.get("jobs") or {}
    assert "performance-and-e2e" in jobs
    assert "-m performance" in NIGHTLY_WORKFLOW.read_text(encoding="utf-8")

    interpreter_job = jobs.get("interpreter-matrix")
    assert interpreter_job is not None, "T068: interpreter-matrix job missing"
    versions = (
        (interpreter_job.get("strategy") or {})
        .get("matrix", {})
        .get(
            "python-version",
        )
    )
    assert versions, "interpreter-matrix must declare a python-version matrix"
    assert all(_version_tuple(v) > (3, 12) for v in versions), f"interpreter-matrix must run ABOVE 3.12: {versions}"


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in str(version).split("."))


def test_nightly_workflow_actions_are_sha_pinned() -> None:
    """T067: every `uses:` action reference is SHA-pinned (`@<40-hex> # vX`)."""
    data = yaml.safe_load(NIGHTLY_WORKFLOW.read_text(encoding="utf-8")) or {}
    offenders: list[str] = []
    for job_name, job in (data.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            uses = step.get("uses") if isinstance(step, dict) else None
            if not uses or uses.startswith("./"):
                continue
            ref = uses.rsplit("@", 1)[-1]
            if not all(c in "0123456789abcdef" for c in ref) or len(ref) < 40:
                offenders.append(f"{job_name}: {uses!r} is not SHA-pinned")
    assert not offenders, "\n".join(offenders)
