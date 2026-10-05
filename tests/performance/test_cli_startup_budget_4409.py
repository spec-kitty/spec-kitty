"""#4409: `spec-kitty --help` must not re-acquire its import-time tax.

Before this guard, a bare ``--help`` cost ~3.2 s while importing the package
itself cost ~0.2 s. Almost all of the difference was one transitive import:
``jsonschema`` eagerly loads its format checkers, and one of those
(``rfc3987_syntax.syntax_helpers``, which builds a Lark grammar at import
time) costs ~1.8 s on its own. Eight modules imported ``jsonschema`` at module
scope, so whichever the CLI touched first paid for all of them — on a path
that validates nothing.

Deferring those imports to their single call sites took ``--help`` to ~1.0 s.
The tax is easy to reintroduce by accident: one ``import jsonschema`` at the
top of a module the CLI imports is enough. This test is the ratchet.

It lives in the ``performance`` lane (nightly) rather than the per-PR gate —
wall-clock budgets are environment-sensitive, and a shared runner under load
should not turn a green change red. The structural half of the guard (no
module-scope ``jsonschema`` import anywhere in ``src/``) is cheap and
deterministic, so that half runs everywhere.

The wall-clock half carries no absolute number of seconds (#5419, #5614): it
asserts the ratio of the ``--help`` median to the median of a fixed interpreter
workload (a fresh interpreter that imports a fixed list of standard-library
modules and then compiles a fixed amount of generated source), both sampled interleaved in the same run, against
``STARTUP_RATIO_LIMIT`` in ``tests/_perf_helpers.py``. A runner that is slower
by some factor slows both by about that factor; the ~1.8 s ``jsonschema``
format-checker tax this test exists for does not slow the workload.
"""

from __future__ import annotations

import ast
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from tests._perf_helpers import (
    PLANT_MAX_FRACTION_OF_FLOOR,
    PLANT_MIN_FRACTION_OF_FLOOR,
    STARTUP_PLANT_ITERATIONS,
    STARTUP_RATIO_LIMIT,
    Measurement,
    Sample,
    assert_timing_budget,
    cli_argv,
    expect_budget_exceeded,
    fixed_workload_argv,
    measure_group,
    measure_interleaved,
    spawn_timed,
    with_plant,
    write_cpu_plant,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

_HELP_MODULE = "specify_cli.__init__"


def _is_type_checking_guard(node: ast.AST) -> bool:
    """True if ``node`` is ``if TYPE_CHECKING:`` or ``if typing.TYPE_CHECKING:``.

    The guard's body never executes at runtime, so imports inside it are
    exempt from the module-scope scan below.
    """
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


#: Bare callee names that dynamically import a module by string name, when
#: the call target is an unqualified ``ast.Name`` (``__import__(...)``, or
#: ``import_module(...)`` after ``from importlib import import_module``). A
#: module-scope call to either, with a first positional string argument of
#: ``"jsonschema"`` (or a ``jsonschema.`` submodule), pays the exact same
#: startup tax as a plain ``import jsonschema`` (#4536).
#:
#: A qualified call (``ast.Attribute``) is matched separately below by its
#: trailing attribute name alone -- ``.import_module`` -- so it also catches
#: ``importlib.import_module(...)`` and any aliased spelling of the module
#: (``import importlib as il; il.import_module(...)``), not just the one
#: fixed dotted string the original #4409 guard hardcoded (#4536
#: completeness). Out of scope: a callee ALIASED to a different bare name
#: (``from importlib import import_module as im; im(...)``) -- recognizing
#: that needs name-binding analysis, not a syntactic shape check, and is a
#: deliberate boundary, not an oversight.
_DYNAMIC_IMPORT_CALLEE_NAMES: frozenset[str] = frozenset({"__import__", "import_module"})
_DYNAMIC_IMPORT_ATTRIBUTE_TAIL = "import_module"


def _is_dynamic_jsonschema_import_call(node: ast.AST) -> bool:
    """True if ``node`` is a module-scope dynamic ``jsonschema`` import call.

    Matches by callee SHAPE, not a fixed dotted string: a bare name in
    ``_DYNAMIC_IMPORT_CALLEE_NAMES`` (``__import__``, ``import_module``), or
    any attribute access whose trailing name is ``import_module`` regardless
    of the value expression (``importlib.import_module``,
    ``il.import_module``, ...).
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        is_dynamic_import = func.id in _DYNAMIC_IMPORT_CALLEE_NAMES
    elif isinstance(func, ast.Attribute):
        is_dynamic_import = func.attr == _DYNAMIC_IMPORT_ATTRIBUTE_TAIL
    else:
        return False
    if not is_dynamic_import:
        return False
    if not node.args:
        return False
    first_arg = node.args[0]
    if not (isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str)):
        return False
    return first_arg.value == "jsonschema" or first_arg.value.startswith("jsonschema.")


def _module_scope_jsonschema_imports(source: str) -> list[int]:
    """Return line numbers importing jsonschema outside deferred call sites.

    An import guarded by ``if TYPE_CHECKING:`` is exempt: that branch is
    ``False`` at runtime and never executes, so it never pulls in the
    ``jsonschema._format -> rfc3987_syntax`` chain this scan exists to catch.
    The guard's ``else:`` branch (and everything else — plain module-scope
    imports, ``try:``-guarded imports, class-body imports) still executes at
    import time and stays flagged. Also flags the dynamic-import spellings
    ``importlib.import_module("jsonschema")``, ``__import__("jsonschema")``,
    a bare ``import_module("jsonschema")`` (via
    ``from importlib import import_module``), and an aliased-module form
    such as ``il.import_module("jsonschema")`` (via
    ``import importlib as il``) (#4536) — each a call with the exact same
    runtime cost the plain-``import`` scan already catches, previously
    invisible to it.
    """
    offending: list[int] = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return
        if isinstance(node, ast.Import):
            if any(alias.name == "jsonschema" or alias.name.startswith("jsonschema.") for alias in node.names):
                offending.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None and (node.module == "jsonschema" or node.module.startswith("jsonschema.")):
                offending.append(node.lineno)
        elif isinstance(node, ast.Call) and _is_dynamic_jsonschema_import_call(node):
            offending.append(node.lineno)
        if isinstance(node, ast.If) and _is_type_checking_guard(node):
            for else_stmt in node.orelse:
                visit(else_stmt)
            return
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(ast.parse(source))
    return offending


#: Non-vacuity floor (#4536): a mis-rooted or empty ``src`` glob would scan
#: zero files and vacuously report zero offenders. 300 is well below the
#: actual tree size (1308 ``*.py`` files under ``src/`` at authoring time) but
#: high enough that only a genuinely broken scan root could ever fall under
#: it — this is a floor against "scanned nothing", not a tracked exact count.
_MIN_SRC_PY_FILE_FLOOR = 300


def _assert_scan_covered_the_tree(scanned: list[Path]) -> None:
    """Fail loudly if ``scanned`` looks like a mis-rooted or empty glob (#4536)."""
    assert len(scanned) > _MIN_SRC_PY_FILE_FLOOR, (
        f"#4536: the module-scope jsonschema scan only found {len(scanned)} file(s). "
        "A mis-rooted or empty `src` glob would vacuously report zero offenders -- "
        "something is wrong with the scan root, not (necessarily) the source tree."
    )


def test_jsonschema_stays_out_of_module_scope() -> None:
    """The structural half scans every source module, not a hand-picked list.

    A module-scope ``import jsonschema`` anywhere in ``src/`` can reintroduce
    the whole format-checker chain for every CLI invocation.
    """
    scanned = sorted((REPO_ROOT / "src").rglob("*.py"))
    _assert_scan_covered_the_tree(scanned)

    offending = {path.relative_to(REPO_ROOT).as_posix(): lines for path in scanned if (lines := _module_scope_jsonschema_imports(path.read_text(encoding="utf-8")))}

    assert not offending, (
        f"#4409: source modules import jsonschema at module scope ({offending}). "
        "That pulls jsonschema._format -> rfc3987_syntax (~1.8s) into every "
        "`spec-kitty` invocation. Import it inside the function that validates."
    )


@pytest.mark.parametrize(
    "source",
    (
        "try:\n    import jsonschema\nexcept ImportError:\n    pass\n",
        "class Validator:\n    import jsonschema\n",
    ),
)
def test_indented_module_scope_jsonschema_import_is_detected(source: str) -> None:
    """The structural guard remains non-vacuous for indented module blocks."""
    assert _module_scope_jsonschema_imports(source)


def test_function_local_jsonschema_import_is_allowed() -> None:
    """Deferred call-site imports are the intended fast-startup pattern."""
    assert _module_scope_jsonschema_imports("def validate():\n    import jsonschema\n") == []


def test_type_checking_guarded_jsonschema_import_is_allowed() -> None:
    """A ``TYPE_CHECKING``-guarded import never executes, so it pays no startup cost."""
    assert _module_scope_jsonschema_imports("from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from jsonschema import validate\n") == []


def test_else_branch_of_type_checking_guard_is_still_detected() -> None:
    """The ``else:`` branch of a ``TYPE_CHECKING`` guard executes at runtime, so it stays flagged."""
    assert _module_scope_jsonschema_imports("from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    pass\nelse:\n    import jsonschema\n")


# ---------------------------------------------------------------------------
# #4536 -- non-vacuity floor. ``test_jsonschema_stays_out_of_module_scope``
# built ``offending`` from a glob with NO minimum-count assertion: a
# mis-rooted or empty ``src`` glob scans zero files and reports zero
# offenders -- a vacuously "clean" pass that proves nothing was actually
# scanned. RED-first demo below.
# ---------------------------------------------------------------------------


def test_mis_rooted_or_empty_scan_is_caught_by_the_floor(tmp_path: Path) -> None:
    """RED-first #4536 demo: a mis-rooted/empty ``src`` glob is now caught.

    Before ``_assert_scan_covered_the_tree`` existed, scanning zero files
    reported zero offenders and ``assert not offending`` passed vacuously.
    """
    empty_root = tmp_path / "definitely-empty-src"
    empty_root.mkdir()
    scanned = sorted(empty_root.rglob("*.py"))
    assert scanned == [], "the demo requires a genuinely empty scan root"
    with pytest.raises(AssertionError, match="#4536"):
        _assert_scan_covered_the_tree(scanned)


# ---------------------------------------------------------------------------
# #4536 -- dynamic-import coverage. ``_module_scope_jsonschema_imports`` only
# recognized ``import``/``from ... import`` statements -- a module-scope
# ``importlib.import_module("jsonschema")`` or ``__import__("jsonschema")``
# call pays the exact same startup tax and was invisible to the guard.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    (
        'import importlib\nimportlib.import_module("jsonschema")\n',
        '__import__("jsonschema")\n',
        'import importlib\nimportlib.import_module("jsonschema.validators")\n',
        'from importlib import import_module\nimport_module("jsonschema")\n',
        'import importlib as il\nil.import_module("jsonschema")\n',
        'from importlib import import_module\nimport_module("jsonschema.validators")\n',
    ),
)
def test_dynamic_jsonschema_import_is_flagged(source: str) -> None:
    """RED-first #4536 demo: a dynamic module-scope jsonschema import is caught.

    C-003-safe: this fixture is a planted source STRING (never a real
    ``src/`` file -- the scout confirmed no dynamic jsonschema import exists
    there today). Covers the ``importlib.import_module`` / ``__import__``
    dotted-name spellings plus the two the completeness follow-up added: a
    bare ``import_module`` name (``from importlib import import_module``)
    and an aliased module attribute (``import importlib as il``) -- both pay
    the identical startup tax and were previously invisible to the fixed
    ``_DYNAMIC_IMPORT_CALLEE_NAMES`` fixed-name set.
    """
    assert _module_scope_jsonschema_imports(source)


def test_dynamic_jsonschema_import_inside_a_function_is_allowed() -> None:
    """A dynamically-imported jsonschema inside a function body is deferred, same as a plain ``import``."""
    assert _module_scope_jsonschema_imports('def validate():\n    import importlib\n    importlib.import_module("jsonschema")\n') == []


def test_new_dynamic_import_spellings_inside_a_function_are_allowed() -> None:
    """The two #4536-completeness spellings are deferred the same way inside a function body."""
    assert _module_scope_jsonschema_imports('def validate():\n    from importlib import import_module\n    import_module("jsonschema")\n') == []
    assert _module_scope_jsonschema_imports('def validate():\n    import importlib as il\n    il.import_module("jsonschema")\n') == []


def test_unrelated_import_module_attribute_call_is_not_flagged() -> None:
    """An ``.import_module(...)`` call on an unrelated object/argument is not a jsonschema import.

    Guards against over-broadening: matching the trailing attribute name
    alone (``.import_module``) only matters combined with the existing
    first-arg check for the ``"jsonschema"`` string -- an unrelated receiver
    calling ``.import_module`` with a different module name must stay clean.
    """
    assert _module_scope_jsonschema_imports('obj.import_module("something_else")\n') == []


def _startup_env() -> dict[str, str]:
    """This checkout's own ``src/`` first, so the measured CLI is the one under test."""
    return {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}


def _help_sample(plant: Path | None = None) -> Callable[[], Sample]:
    env = _startup_env() if plant is None else with_plant(_startup_env(), plant)
    argv = cli_argv("--help", module=_HELP_MODULE)
    return lambda: spawn_timed(argv, cwd=REPO_ROOT, env=env)


def _workload_sample() -> Callable[[], Sample]:
    argv, env = fixed_workload_argv(), _startup_env()
    return lambda: spawn_timed(argv, cwd=REPO_ROOT, env=env)


def _assert_startup_ratio(measurement: Measurement, label: str, title: str, record_property: Callable[[str, object], None] | None = None) -> None:
    if record_property is not None:
        # Recorded in the xunit report on PASS too, so a nightly run can be read for calibration.
        record_property("ratio", round(measurement.ratio(label), 4))
        record_property("workload_median_seconds", round(measurement.floor.median, 4))
        record_property("command_median_seconds", round(measurement.variants[label].median, 4))
    name = measurement.describe(label, STARTUP_RATIO_LIMIT, title=title)
    assert_timing_budget(measurement.ratio(label), STARTUP_RATIO_LIMIT, name=name)


@pytest.mark.performance
def test_help_stays_inside_its_startup_budget(record_property: Callable[[str, object], None]) -> None:
    """The wall-clock half: nightly-only, measured through the real entry point.

    ``--help`` is sampled interleaved with a fixed interpreter workload and the
    ratio of the two medians is held to ``STARTUP_RATIO_LIMIT``.
    """
    measurement = measure_interleaved(_help_sample(), _workload_sample())
    _assert_startup_ratio(measurement, "command", "spec-kitty --help startup / fixed interpreter workload", record_property)


@pytest.mark.performance
def test_planted_cpu_work_turns_the_startup_ratio_assertion_red(tmp_path: Path, record_property: Callable[[str, object], None]) -> None:
    """FR-010: CPU-bound work planted into ``--help`` start-up, test side only, must fail the ratio.

    The plant is a fixed-iteration loop in a ``sitecustomize.py`` first on the
    child's ``PYTHONPATH``. It costs a measured fraction of the clean ``--help``
    median (between ``PLANT_MIN_FRACTION_OF_FLOOR`` and ``PLANT_MAX_FRACTION_OF_FLOOR``),
    so it is a start-up regression of a stated size and not an arbitrary one. The
    figures are recorded in the xunit report before any assertion and the
    did-not-detect failure message carries them too.
    """
    plant = write_cpu_plant(tmp_path / "plant", STARTUP_PLANT_ITERATIONS)
    measurement = measure_group(_workload_sample(), {"clean": _help_sample(), "planted": _help_sample(plant)})
    clean_seconds = measurement.variants["clean"].median
    cost_seconds = measurement.cost("planted", "clean")
    record_property("planted_ratio", round(measurement.ratio("planted"), 4))
    record_property("clean_ratio", round(measurement.ratio("clean"), 4))
    record_property("plant_cost_fraction", round(cost_seconds / clean_seconds, 4))
    record_property("workload_median_seconds", round(measurement.floor.median, 4))
    record_property("clean_median_seconds", round(clean_seconds, 4))
    record_property("planted_median_seconds", round(measurement.variants["planted"].median, 4))
    where = measurement.describe("planted", STARTUP_RATIO_LIMIT, title="spec-kitty --help startup, planted")
    figures = f"clean ratio {measurement.ratio('clean'):.3f}; plant cost {cost_seconds / clean_seconds:.3f} of clean --help; {where}"
    assert_timing_budget(
        cost_seconds, PLANT_MAX_FRACTION_OF_FLOOR * clean_seconds, name=f"plant cost above {PLANT_MAX_FRACTION_OF_FLOOR} of clean --help; {figures}"
    )
    assert_timing_budget(
        PLANT_MIN_FRACTION_OF_FLOOR * clean_seconds, cost_seconds, name=f"plant cost below {PLANT_MIN_FRACTION_OF_FLOOR} of clean --help; {figures}"
    )
    expect_budget_exceeded(measurement.ratio("planted"), STARTUP_RATIO_LIMIT, name=figures)
