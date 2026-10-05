"""One authority for start-up limits, and the pure parts of the relative measure (FR-007, FR-012).

``tests/_perf_helpers.py`` holds every start-up limit, every sample count and
the interleaved measuring helper. This file checks that, and unit-tests the
pure parts of the helper with injected timings. It lives in
``tests/architectural`` (not ``tests/performance``) because no job runs an
unmarked test in ``tests/performance``: the architectural jobs run this file on
every pull request.

Three groups of tests:

* the helper's pairing, medians, ratios, failure naming and plant mechanics,
  all with injected timings or tiny real subprocesses;
* the FR-007 positive control: the six nightly rows of ``code-grounding.md``
  section 4.2 fed through the helper, showing the previous absolute assertion
  red where the ratio assertion is green;
* the FR-012 single-authority check: no test file that spawns a fresh CLI
  interpreter for timing defines its own numeric limit, either beside the test
  (a module-level constant) or inline (a numeric literal passed as the limit of
  ``assert_timing_budget`` / ``expect_budget_exceeded``).

The single-authority check is one fact, not a size gate and not a ratchet: it
has no allowlist.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import pytest

from tests._perf_helpers import (
    OWNED_CHECKOUT_RATIO_LIMIT,
    OWNED_LOWEST_CLEAN_RATIO,
    OWNED_PLANT_MAX_FRACTION_OF_FLOOR,
    OWNED_PLANT_MIN_FRACTION_OF_FLOOR,
    SAMPLE_RUNS,
    STARTUP_LOWEST_CLEAN_RATIO,
    STARTUP_PLANT_MAX_FRACTION_OF_CLEAN,
    STARTUP_PLANT_MIN_FRACTION_OF_CLEAN,
    STARTUP_RATIO_LIMIT,
    WARM_LEAF_RATIO_LIMIT,
    Sample,
    Series,
    assert_timing_budget,
    expect_budget_exceeded,
    fixed_workload_argv,
    measure_group,
    measure_interleaved,
    plant_source,
    spawn_timed,
    with_plant,
    write_cpu_plant,
)

pytestmark = [pytest.mark.architectural]

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = REPO_ROOT / "tests"
AUTHORITY_FILE = TESTS_ROOT / "_perf_helpers.py"
THIS_FILE = Path(__file__).resolve()
OWNED_PERFORMANCE_FILES = (
    "tests/performance/test_owned_checkout_perf.py",
    "tests/performance/test_cli_startup_budget_4409.py",
    "tests/performance/test_cli_startup_agent_commands_freshness.py",
)

# --------------------------------------------------------------------------- helpers under test


def _scripted(values: Sequence[float], *, log: list[str] | None = None, tag: str = "") -> Callable[[], Sample]:
    """A sample source that replays *values*; each call appends *tag* to *log*."""
    iterator: Iterator[float] = iter(values)

    def spawn() -> Sample:
        if log is not None:
            log.append(tag)
        return Sample(next(iterator))

    return spawn


def test_measure_interleaved_alternates_floor_and_command_and_reverses_every_other_round() -> None:
    log: list[str] = []
    measurement = measure_interleaved(
        _scripted([2.0] * 4, log=log, tag="command"),
        _scripted([1.0] * 4, log=log, tag="floor"),
        runs=4,
    )
    assert log == ["floor", "command", "command", "floor", "floor", "command", "command", "floor"]
    assert measurement.ratio("command") == pytest.approx(2.0)


def test_medians_ignore_one_outlier_in_each_series() -> None:
    measurement = measure_interleaved(
        _scripted([2.0, 2.0, 9.0, 2.0, 2.0]),
        _scripted([1.0, 1.0, 1.0, 5.0, 1.0]),
    )
    assert measurement.variants["command"].median == pytest.approx(2.0)
    assert measurement.floor.median == pytest.approx(1.0)
    assert measurement.ratio("command") == pytest.approx(2.0)


def test_default_sample_count_is_the_documented_five() -> None:
    assert SAMPLE_RUNS == 5
    log: list[str] = []
    measure_interleaved(_scripted([1.0] * 5, log=log, tag="c"), _scripted([1.0] * 5, log=log, tag="f"))
    assert (log.count("c"), log.count("f")) == (5, 5)


def test_group_measurement_interleaves_every_variant_with_the_floor() -> None:
    log: list[str] = []
    measurement = measure_group(
        _scripted([1.0, 1.0], log=log, tag="floor"),
        {"clean": _scripted([1.4, 1.4], log=log, tag="clean"), "planted": _scripted([1.9, 1.9], log=log, tag="planted")},
        runs=2,
    )
    assert log == ["floor", "clean", "planted", "planted", "clean", "floor"]
    assert measurement.cost("planted", "clean") == pytest.approx(0.5)
    assert measurement.ratio("planted") == pytest.approx(1.9)


def test_a_failed_sample_makes_the_ratio_infinite_names_the_failure_and_stops_sampling() -> None:
    log: list[str] = []

    def failing() -> Sample:
        log.append("command")
        return Sample(0.1, ok=False, detail="exit=2; stderr=boom")

    measurement = measure_interleaved(failing, _scripted([1.0] * 5, log=log, tag="floor"))
    assert measurement.ratio("command") == float("inf")
    assert len(log) == 2  # one round, then stop
    text = measurement.describe("command", 1.7, title="agent tasks status")
    assert "exit=2; stderr=boom" in text
    assert text.startswith("agent tasks status: command median inf s")


def test_a_failed_floor_makes_the_ratio_infinite() -> None:
    measurement = measure_interleaved(_scripted([1.0] * 5), lambda: Sample(0.5, ok=False, detail="exit=1"))
    assert measurement.ratio("command") == float("inf")
    assert "floor: exit=1" in measurement.describe("command", 1.7, title="t")


def test_an_empty_series_and_a_zero_floor_have_infinite_medians_and_ratios() -> None:
    assert Series("none", ()).median == float("inf")
    zero_floor = measure_interleaved(_scripted([1.0] * 5), _scripted([0.0] * 5))
    assert zero_floor.ratio("command") == float("inf")


def test_describe_carries_both_medians_the_ratio_the_limit_and_the_raw_samples() -> None:
    measurement = measure_interleaved(_scripted([1.5] * 5), _scripted([1.0] * 5))
    text = measurement.describe("command", 1.7, title="agent tasks status")
    for fragment in ("command median 1.500", "floor median 1.000", "ratio 1.500", "limit 1.7", "[1.5, 1.5, 1.5, 1.5, 1.5]"):
        assert fragment in text


def test_expect_budget_exceeded_passes_over_budget_and_names_the_figures_when_not_detected() -> None:
    expect_budget_exceeded(1.9, 1.78, name="x")
    for measured in (1.78, 1.5):
        with pytest.raises(AssertionError, match=r"planted work not detected.*measured=.*<= budget=1\.78") as caught:
            expect_budget_exceeded(measured, 1.78, name="clean ratio 1.4; plant cost 0.2")
        assert "clean ratio 1.4; plant cost 0.2" in str(caught.value)


def test_spawn_timed_uses_the_injected_clock_and_reports_success() -> None:
    ticks = iter([10.0, 10.25])
    sample = spawn_timed([sys.executable, "-c", "pass"], cwd=REPO_ROOT, env={}, clock=lambda: next(ticks))
    assert (sample.ok, sample.seconds) == (True, 0.25)


def test_spawn_timed_fails_a_rejected_exit_code_with_the_stderr_tail() -> None:
    code = "import sys; sys.stderr.write('tail-marker'); sys.exit(3)"
    sample = spawn_timed([sys.executable, "-c", code], cwd=REPO_ROOT, env={})
    assert not sample.ok
    assert "exit=3" in sample.detail
    assert "tail-marker" in sample.detail


def test_spawn_timed_accepts_an_explicitly_accepted_exit_code() -> None:
    sample = spawn_timed([sys.executable, "-c", "import sys; sys.exit(1)"], cwd=REPO_ROOT, env={}, accepted_returncodes=(0, 1))
    assert sample.ok


def test_the_fixed_workload_is_a_fresh_interpreter_that_imports_only_the_standard_library() -> None:
    argv = fixed_workload_argv()
    assert argv[0] == sys.executable
    assert "specify_cli" not in argv[-1]
    completed = subprocess.run(argv, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr


def test_a_plant_source_compiles_and_embeds_its_iteration_count() -> None:
    source = plant_source(12345)
    compile(source, "sitecustomize.py", "exec")
    assert "_burn(12345)" in source


def _run_with_plant(directory: Path, *args: str) -> str:
    env = with_plant({"PATH": ""}, directory)
    code = "import sitecustomize, sys; print(getattr(sitecustomize, '_BURNED', None))"
    completed = subprocess.run([sys.executable, "-c", code, *args], env=env, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def test_an_ungated_plant_burns_in_every_interpreter(tmp_path: Path) -> None:
    write_cpu_plant(tmp_path / "plant", 10)
    assert _run_with_plant(tmp_path / "plant") == "True"


def test_a_gated_plant_burns_only_when_the_argv_token_is_present(tmp_path: Path) -> None:
    write_cpu_plant(tmp_path / "plant", 10, argv_token="agent")
    assert _run_with_plant(tmp_path / "plant", "agent", "tasks") == "True"
    assert _run_with_plant(tmp_path / "plant", "--version") == "False"


def test_a_plant_chains_to_a_later_sitecustomize(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    (other / "sitecustomize.py").write_text("import builtins\nbuiltins.CHAINED_MARKER = 'chained'\n", encoding="utf-8")
    write_cpu_plant(tmp_path / "plant", 10)
    env = with_plant({"PATH": ""}, tmp_path / "plant")
    env["PYTHONPATH"] = f"{env['PYTHONPATH']}{os.pathsep}{other}"
    completed = subprocess.run(
        [sys.executable, "-c", "import builtins; print(builtins.CHAINED_MARKER)"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.stdout.strip() == "chained", completed.stderr


def test_with_plant_puts_the_plant_directory_first_and_keeps_the_existing_path(tmp_path: Path) -> None:
    assert with_plant({"PYTHONPATH": "/x"}, tmp_path)["PYTHONPATH"] == f"{tmp_path}{os.pathsep}/x"
    assert with_plant({}, tmp_path)["PYTHONPATH"] == str(tmp_path)


def test_the_limits_and_plant_bounds_are_sane_numbers() -> None:
    assert 1.0 < OWNED_CHECKOUT_RATIO_LIMIT < 5.0
    assert STARTUP_RATIO_LIMIT > 1.0
    assert WARM_LEAF_RATIO_LIMIT > 1.0
    assert 0.0 < OWNED_PLANT_MIN_FRACTION_OF_FLOOR < OWNED_PLANT_MAX_FRACTION_OF_FLOOR
    assert 0.0 < STARTUP_PLANT_MIN_FRACTION_OF_CLEAN < STARTUP_PLANT_MAX_FRACTION_OF_CLEAN


def test_the_owned_plant_band_always_detects_and_still_bounds_the_limit() -> None:
    """An in-band owned plant is detected at the limit and not at a limit about a third wider (#5753).

    Detection needs ``clean ratio + cost fraction > limit``. The lower edge must
    clear that at the lowest clean ratio ever seen; the upper edge sets the widest
    limit an in-band plant would still catch.
    """
    assert OWNED_LOWEST_CLEAN_RATIO + OWNED_PLANT_MIN_FRACTION_OF_FLOOR > OWNED_CHECKOUT_RATIO_LIMIT
    widest_detected_limit = OWNED_LOWEST_CLEAN_RATIO + OWNED_PLANT_MAX_FRACTION_OF_FLOOR
    assert widest_detected_limit < 1.4 * OWNED_CHECKOUT_RATIO_LIMIT


def test_the_startup_plant_band_always_detects_and_still_bounds_the_limit() -> None:
    """An in-band start-up plant multiplies the clean ratio by ``1 + fraction``; same two edges as the owned band (#5753)."""
    assert STARTUP_LOWEST_CLEAN_RATIO * (1 + STARTUP_PLANT_MIN_FRACTION_OF_CLEAN) > STARTUP_RATIO_LIMIT
    widest_detected_limit = STARTUP_LOWEST_CLEAN_RATIO * (1 + STARTUP_PLANT_MAX_FRACTION_OF_CLEAN)
    assert widest_detected_limit < 1.4 * STARTUP_RATIO_LIMIT


# --------------------------------------------------------------------------- FR-007 positive control

#: The absolute budget the owned-checkout tests asserted before this change
#: (``CLI_COLD_START_BUDGET_SECONDS``). Kept here only as historical test data
#: for the positive control below; it is not a live limit.
_HISTORICAL_ABSOLUTE_BUDGET_SECONDS = 2.5

#: ``code-grounding.md`` section 4.2: nightly run id, ``--help`` median (the
#: start-up floor of that run), the owned-command medians, whether the nightly
#: reported the previous absolute assertion red. "About" figures are the junit
#: time divided by five.
_NIGHTLY_ROWS: tuple[tuple[str, float, tuple[float, ...], bool], ...] = (
    ("36811585861", 1.95, (2.71, 2.85, 2.76), True),
    ("36920764277", 1.83, (2.65, 2.72, 2.62), True),
    ("36960774283", 1.14, (1.54,), False),
    ("37094126479", 1.76, (1.88,), False),
    ("37177460494", 1.94, (2.60, 2.70, 2.60), True),
    ("37225822329", 1.72, (2.52, 2.59, 2.54), True),
)


@pytest.mark.parametrize(("run_id", "floor_seconds", "owned_medians", "was_red"), _NIGHTLY_ROWS)
def test_the_ratio_assertion_is_green_on_every_nightly_row_where_the_absolute_one_was_red(
    run_id: str, floor_seconds: float, owned_medians: tuple[float, ...], was_red: bool
) -> None:
    for owned_seconds in owned_medians:
        measurement = measure_interleaved(_scripted([owned_seconds] * SAMPLE_RUNS), _scripted([floor_seconds] * SAMPLE_RUNS))
        command_median = measurement.variants["command"].median
        if was_red:
            with pytest.raises(AssertionError, match="budget exceeded"):
                assert_timing_budget(command_median, _HISTORICAL_ABSOLUTE_BUDGET_SECONDS, name=f"run {run_id} absolute")
        else:
            assert_timing_budget(command_median, _HISTORICAL_ABSOLUTE_BUDGET_SECONDS, name=f"run {run_id} absolute")
        assert_timing_budget(measurement.ratio("command"), OWNED_CHECKOUT_RATIO_LIMIT, name=f"run {run_id} ratio")


def test_the_nightly_rows_are_the_six_recorded_runs_four_of_them_red() -> None:
    assert len(_NIGHTLY_ROWS) == 6
    assert sum(1 for *_, was_red in _NIGHTLY_ROWS if was_red) == 4


# --------------------------------------------------------------------------- FR-012 single authority

_LIMIT_NAME = re.compile(r"(BUDGET|LIMIT|CEILING|THRESHOLD)", re.IGNORECASE)
_CLI_SPAWN_EVIDENCE = re.compile(r"""["']-m["']\s*,\s*["']specify_cli|\bcli_argv\(|\bspawn_timed\(""")
_TIMING_EVIDENCE = re.compile(r"\b(?:assert_timing_budget|expect_budget_exceeded)\(")
#: The two helpers that take a limit as their second positional argument (``budget=`` as a keyword).
_LIMIT_HELPERS = frozenset({"assert_timing_budget", "expect_budget_exceeded"})
_LIMIT_ARGUMENT_POSITION = 1
_LIMIT_KEYWORD = "budget"


def _numeric_expression(node: ast.expr) -> bool:
    """True for a number, or arithmetic on numbers (``2.5``, ``-1``, ``2 * 1.5``)."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    if isinstance(node, ast.UnaryOp):
        return _numeric_expression(node.operand)
    if isinstance(node, ast.BinOp):
        return _numeric_expression(node.left) and _numeric_expression(node.right)
    return False


def spawns_cli_for_timing(source: str) -> bool:
    """True when *source* spawns a fresh CLI interpreter and asserts a timing budget."""
    return bool(_CLI_SPAWN_EVIDENCE.search(source) and _TIMING_EVIDENCE.search(source))


def module_level_limit_definitions(source: str) -> list[str]:
    """Names of module-level numeric limits in *source*.

    A module-level assignment (plain or annotated) whose target name contains
    ``BUDGET``, ``LIMIT``, ``CEILING`` or ``THRESHOLD`` and whose value is a
    number or arithmetic on numbers. An import from the authority, or an
    alias of one, is not a definition.
    """
    found: list[str] = []
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if not _numeric_expression(value):
            continue
        found.extend(target.id for target in targets if isinstance(target, ast.Name) and _LIMIT_NAME.search(target.id))
    return found


def inline_numeric_limit_lines(source: str) -> list[int]:
    """Line numbers of calls that pass a numeric literal as the limit of a timing helper.

    A call to ``assert_timing_budget`` or ``expect_budget_exceeded`` (by name or as an
    attribute) whose limit is a number or arithmetic on numbers: the second positional
    argument, or the ``budget=`` keyword. A limit that is a name (an import from the
    authority) or an expression over names is not flagged; the measured value (the
    first argument) is never a limit.
    """
    flagged: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        if name not in _LIMIT_HELPERS:
            continue
        limits = [node.args[_LIMIT_ARGUMENT_POSITION]] if len(node.args) > _LIMIT_ARGUMENT_POSITION else []
        limits += [keyword.value for keyword in node.keywords if keyword.arg == _LIMIT_KEYWORD]
        if any(_numeric_expression(limit) for limit in limits):
            flagged.append(node.lineno)
    return sorted(flagged)


def _timing_spawning_test_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(TESTS_ROOT.rglob("*.py")):
        if path in (AUTHORITY_FILE, THIS_FILE):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if spawns_cli_for_timing(text):
            files.append(path)
    return files


def test_no_test_file_that_times_a_cli_spawn_defines_its_own_numeric_limit() -> None:
    offenders: dict[str, list[str]] = {}
    for path in _timing_spawning_test_files():
        names = module_level_limit_definitions(path.read_text(encoding="utf-8"))
        if names:
            offenders[path.relative_to(REPO_ROOT).as_posix()] = names
    assert not offenders, f"start-up limits must live in tests/_perf_helpers.py, not beside the test: {offenders}"


def test_the_scan_covers_the_three_owned_performance_files() -> None:
    scanned = {path.relative_to(REPO_ROOT).as_posix() for path in _timing_spawning_test_files()}
    missing = [name for name in OWNED_PERFORMANCE_FILES if name not in scanned]
    assert not missing, f"the single-authority scan no longer reaches {missing}"


def test_the_authority_module_defines_the_limits_the_scan_protects() -> None:
    defined = module_level_limit_definitions(AUTHORITY_FILE.read_text(encoding="utf-8"))
    assert {"OWNED_CHECKOUT_RATIO_LIMIT", "STARTUP_RATIO_LIMIT", "WARM_LEAF_RATIO_LIMIT"} <= set(defined)


_PLANTED_LIMIT_SOURCE = """\
import subprocess
import sys

from tests._perf_helpers import assert_timing_budget

_X_BUDGET_SECONDS = 3.0


def test_startup() -> None:
    subprocess.run([sys.executable, "-m", "specify_cli", "--help"], check=False)
    assert_timing_budget(1.0, _X_BUDGET_SECONDS)
"""

_AUTHORITY_IMPORT_SOURCE = """\
import subprocess
import sys

from tests._perf_helpers import STARTUP_RATIO_LIMIT, assert_timing_budget

_RUNS = 5
_HELP_LIMIT = STARTUP_RATIO_LIMIT


def test_startup() -> None:
    subprocess.run([sys.executable, "-m", "specify_cli", "--help"], check=False)
    assert_timing_budget(1.0, _HELP_LIMIT)
"""


def test_self_test_a_planted_module_level_limit_beside_a_cli_spawn_is_flagged() -> None:
    assert spawns_cli_for_timing(_PLANTED_LIMIT_SOURCE)
    assert module_level_limit_definitions(_PLANTED_LIMIT_SOURCE) == ["_X_BUDGET_SECONDS"]


def test_self_test_an_import_from_the_authority_is_not_flagged() -> None:
    assert spawns_cli_for_timing(_AUTHORITY_IMPORT_SOURCE)
    assert module_level_limit_definitions(_AUTHORITY_IMPORT_SOURCE) == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("_A_LIMIT: float = 2.5\n", ["_A_LIMIT"]),
        ("_B_CEILING = 2 * 1.5\n", ["_B_CEILING"]),
        ("_C_THRESHOLD = -1\n", ["_C_THRESHOLD"]),
        ("_RUNS = 5\n", []),
        ("_D_BUDGET = SOMETHING + 1\n", []),
        ("_E_LIMIT = True\n", []),
        ("def f() -> None:\n    _F_LIMIT = 3.0\n", []),
        ("x: int\n", []),
    ],
)
def test_self_test_limit_definition_detection(source: str, expected: list[str]) -> None:
    assert module_level_limit_definitions(source) == expected


def test_self_test_a_file_without_a_cli_spawn_or_without_a_timing_assertion_is_out_of_scope() -> None:
    assert not spawns_cli_for_timing("from tests._perf_helpers import assert_timing_budget\nassert_timing_budget(1, 2)\n")
    assert not spawns_cli_for_timing('subprocess.run([sys.executable, "-m", "specify_cli"])\n')


_INLINE_LITERAL_SOURCE = """\
import subprocess
import sys

from tests._perf_helpers import assert_timing_budget, expect_budget_exceeded


def test_startup() -> None:
    subprocess.run([sys.executable, "-m", "specify_cli", "--help"], check=False)
    assert_timing_budget(1.0, 3.0)
    expect_budget_exceeded(5.0, 2 * 1.5, name="planted")
"""


@pytest.mark.parametrize(
    ("source", "expected_lines"),
    [
        ("assert_timing_budget(x, 3.0)\n", [1]),
        ("expect_budget_exceeded(x, 3.0, name='n')\n", [1]),
        ("assert_timing_budget(x, budget=3.0)\n", [1]),
        ("expect_budget_exceeded(x, budget=2, name='n')\n", [1]),
        ("assert_timing_budget(x, 2 * 1.5)\n", [1]),
        ("assert_timing_budget(x, -1)\n", [1]),
        ("helpers.assert_timing_budget(x, 3.0)\n", [1]),
        ("assert_timing_budget(x, 1.0)\nassert_timing_budget(y, LIMIT)\nexpect_budget_exceeded(z, 4.5, name='n')\n", [1, 3]),
        ("assert_timing_budget(x, STARTUP_RATIO_LIMIT)\n", []),
        ("assert_timing_budget(x, budget=STARTUP_RATIO_LIMIT)\n", []),
        ("assert_timing_budget(x, FRACTION * floor_seconds, name='n')\n", []),
        ("assert_timing_budget(1.0, limit)\n", []),
        ("assert_timing_budget(x, True)\n", []),
        ("assert_timing_budget(x)\n", []),
        ("other_helper(x, 3.0)\n", []),
    ],
)
def test_self_test_inline_numeric_limit_detection(source: str, expected_lines: list[int]) -> None:
    assert inline_numeric_limit_lines(source) == expected_lines


def test_self_test_an_inline_literal_limit_beside_a_cli_spawn_is_flagged() -> None:
    assert spawns_cli_for_timing(_INLINE_LITERAL_SOURCE)
    assert inline_numeric_limit_lines(_INLINE_LITERAL_SOURCE) == [9, 10]


def test_no_test_file_that_times_a_cli_spawn_passes_an_inline_numeric_limit() -> None:
    offenders: dict[str, list[int]] = {}
    for path in _timing_spawning_test_files():
        lines = inline_numeric_limit_lines(path.read_text(encoding="utf-8"))
        if lines:
            offenders[path.relative_to(REPO_ROOT).as_posix()] = lines
    assert not offenders, f"start-up limits must be named in tests/_perf_helpers.py, not passed as a literal: {offenders}"
