"""Shared timing helpers and the one authority for start-up limits (#4015, #5419, #5614).

Two things live here.

**The timing-budget assertion (#4015, FR-008, Decision 3).**
``tests/architectural/test_performance_marker_guard.py`` (#3665) forbids a
functional (non-timing) assertion inside a ``@pytest.mark.performance``
test: every ``assert`` in the function body must contain a
``TIMING_ASSERTION_VOCABULARY`` token (``elapsed``, ``budget``, ``seconds``,
...). Nine timing-only tests in the #4015 sweep are genuinely
timing-only-in-intent but assert a bare comparison whose local-variable name
(``p95``, ``avg_ms``, ``median_ms``, ``fastest``, ...) is not in that
vocabulary, so a bare ``assert`` trips the guard even though there is no
functional coverage to protect.

Decision 3 (``research.md``) rejects both workarounds the guard's own
docstring floats -- widening ``TIMING_ASSERTION_VOCABULARY`` (risks a real
functional assertion slipping through the widened vocabulary elsewhere) and
per-variable renames (bespoke, un-auditable, one-off per call site) -- in
favor of one shared helper. :func:`assert_timing_budget` raises the
assertion *inside this module*, not at the call site, so the call site never
contains a bare ``assert`` statement for the guard's ``ast.Assert`` walk to
inspect in the first place -- and its own name embeds the ``budget``
vocabulary token, so any call-site text (``assert_timing_budget(...)``) is
guard-clean by construction even if a future guard revision ever started
inspecting call expressions instead of only ``assert`` statements.

**Runner-relative measures and their limits (mission
``nightly-suites-green-01M44FEP``, FR-007 to FR-012).**
A wall-clock median compared with an absolute number measures the runner as
much as the code: a bare ``--help`` moved between 1.14 s and 1.95 s across
nightly runs with no product change (#5419, #5614). The tests that pay
interpreter cold start therefore assert a *ratio* of two medians sampled
*interleaved in the same run*, so drift in machine speed during the run
moves numerator and denominator together:

* the owned-checkout commands are divided by a **start-up floor**
  (:data:`STARTUP_FLOOR_ARGV`, a bare ``--version``);
* CLI start-up itself is divided by a **fixed interpreter workload**
  (:func:`fixed_workload_argv`, a fresh interpreter that imports a fixed list of
  standard-library modules and then compiles a fixed amount of generated
  source), which contains no product code.

Every limit, every sample count and the measuring helper are defined in this
module and nowhere else; ``tests/architectural/test_perf_limit_authority.py``
fails when another test file defines its own start-up limit. The figures
behind each constant are in
``docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md``.

The timing source is injectable: :class:`Sample` is what one timed run yields
and :func:`measure_interleaved` only needs callables returning samples, so the
pure parts (pairing, medians, ratios, failure naming) are unit-tested without a
subprocess. :func:`write_cpu_plant` produces the test-side slowdown used by the
planted-work tests to prove the relative assertions can fail.
"""

from __future__ import annotations

import os
import statistics
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

#: Spawns per series in one measurement: 5 floor and 5 command runs, interleaved.
SAMPLE_RUNS = 5

#: Ratio limit for an owned-checkout command median over the start-up floor
#: median (``agent tasks status``, ``agent mission setup-plan``,
#: ``agent context resolve``). Chosen from data, not in advance (D5). Of 450
#: clean evaluations (idle and CPU-throttled series, plus a 30-run robustness
#: campaign) the median is 1.39, 360 calibration ratios lay between 1.21 and 1.65,
#: and one campaign evaluation exceeded the first limit tried, 1.70 (its value was
#: not captured). Planted ratios with the committed plant lay between 1.85 and
#: 2.01. The limit is 1.78: 4 percent below the smallest planted value, 8 percent
#: above the largest calibration value, 28 percent above the median clean ratio
#: and 18 percent above the largest ratio any nightly run showed (1.51). Figures
#: and method:
#: ``docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md``.
#: Replaces the absolute 2.5 s (#5419).
OWNED_CHECKOUT_RATIO_LIMIT = 1.78

#: Ratio limit for ``--help`` start-up over the fixed interpreter workload.
#: Catches the ~1.8 s import-time tax #4409 removed (``--help`` fell from
#: ~3.2 s to ~1.0 s) returning, without naming a number of seconds. 60 clean
#: ratios lay between 2.12 and 2.59 and 20 planted ratios between 3.23 and 3.58
#: (decision record): 2.90 is 12 percent above the largest clean value and 11
#: percent below the smallest planted one.
STARTUP_RATIO_LIMIT = 2.90

#: Ratio limit for a WARM (second) ``context list --json`` over the fixed
#: interpreter workload. The regression it exists for is the ~11 s
#: from-scratch asset render coming back on a warm call (WP04's freshness
#: short-circuit dropped): a factor of about ten, against a warm call that
#: costs about a second. 60 warm ratios lay between 2.45 and 2.96; the
#: from-scratch render measured 12.6 to 14.3 (decision record). 6.0 is twice the
#: largest warm value and a little under half the smallest regressed one.
WARM_LEAF_RATIO_LIMIT = 6.0

#: Lower and upper bound, as fractions of the start-up floor median, for the
#: cost of the planted work (planted command median minus clean command
#: median). An oversized plant would pass under any limit, so the bound makes
#: "about half the floor" a checked fact on every machine.
PLANT_MIN_FRACTION_OF_FLOOR = 0.3
PLANT_MAX_FRACTION_OF_FLOOR = 0.7

#: Iterations of the planted CPU-bound loop (:func:`write_cpu_plant`), calibrated
#: so the plant costs about half the start-up floor on the calibration machine
#: (decision record). The loop is CPU-bound, so it scales with the runner; the
#: planted-work test checks the realised cost against the two fractions above on
#: every run.
OWNED_PLANT_ITERATIONS = 12_000_000

#: Iterations of the planted loop for the start-up tests.
STARTUP_PLANT_ITERATIONS = 10_000_000

#: The start-up floor for owned-checkout commands: the cheapest command that
#: still pays the full CLI import chain.
STARTUP_FLOOR_ARGV: tuple[str, ...] = ("--version",)

#: Standard-library modules the fixed interpreter workload imports. Fixed, so
#: the workload costs the same in every run on a given machine and carries no
#: product code.
FIXED_WORKLOAD_MODULES: tuple[str, ...] = (
    "argparse",
    "asyncio",
    "csv",
    "dataclasses",
    "decimal",
    "difflib",
    "email.message",
    "fractions",
    "http.client",
    "json",
    "logging",
    "pathlib",
    "pickle",
    "re",
    "shutil",
    "sqlite3",
    "subprocess",
    "tempfile",
    "typing",
    "unittest",
    "urllib.request",
    "xml.etree.ElementTree",
)

#: Generated functions the fixed interpreter workload compiles (about 0.3 s on the calibration machine).
FIXED_WORKLOAD_FUNCTIONS = 12000

_STDERR_TAIL_CHARS = 1500
_FLOOR_LABEL = "floor"


def assert_timing_budget(measured: float, budget: float, *, name: str = "elapsed") -> None:
    """Assert that a measured wall-clock duration stays within *budget*.

    Args:
        measured: the observed wall-clock value (seconds, ms, or whatever
            unit the caller and *budget* agree on -- this helper is
            unit-agnostic, it only compares the two numbers).
        budget: the maximum permitted value for *measured*.
        name: label used in the failure message (defaults to ``"elapsed"``,
            itself a ``TIMING_ASSERTION_VOCABULARY`` token).

    Raises:
        AssertionError: if ``measured > budget``, naming both values and
            *name* so a nightly failure is diagnosable without re-running
            the test.
    """
    assert measured <= budget, f"{name} budget exceeded: measured={measured!r} > budget={budget!r}"


def expect_budget_exceeded(measured: float, budget: float, *, name: str) -> None:
    """Assert that *measured* is over *budget*: the planted-work counterpart of :func:`assert_timing_budget`.

    Raises:
        AssertionError: if ``measured <= budget``, i.e. the planted slowdown was
            not detected, naming both values and *name* so the failure carries
            the figures a calibration needs.
    """
    if measured > budget:
        return
    raise AssertionError(f"{name} planted work not detected: the budget was not exceeded: measured={measured!r} <= budget={budget!r}")


@dataclass(frozen=True)
class Sample:
    """One timed run: wall-clock seconds, whether it succeeded, and why not."""

    seconds: float
    ok: bool = True
    detail: str = ""


SampleFn = Callable[[], Sample]


@dataclass(frozen=True)
class Series:
    """All samples of one labelled command taken during a measurement."""

    label: str
    samples: tuple[Sample, ...]

    @property
    def failure(self) -> str:
        """The first failed sample's detail, or an empty string when every run succeeded."""
        for sample in self.samples:
            if not sample.ok:
                return f"{self.label}: {sample.detail}"
        return ""

    @property
    def median(self) -> float:
        """Median seconds, or ``inf`` when any run failed or none ran."""
        if not self.samples or self.failure:
            return float("inf")
        return statistics.median(sample.seconds for sample in self.samples)

    @property
    def raw(self) -> list[float]:
        """The sampled durations rounded for a failure message."""
        return [round(sample.seconds, 3) for sample in self.samples]


@dataclass(frozen=True)
class Measurement:
    """The result of one interleaved measurement: the floor and each variant."""

    floor: Series
    variants: Mapping[str, Series]

    def ratio(self, label: str) -> float:
        """Variant median over floor median; ``inf`` when either side failed."""
        floor_median = self.floor.median
        variant_median = self.variants[label].median
        if floor_median == float("inf") or variant_median == float("inf") or floor_median <= 0:
            return float("inf")
        return variant_median / floor_median

    def cost(self, label: str, baseline: str) -> float:
        """Median of *label* minus median of *baseline*, both from this run."""
        return self.variants[label].median - self.variants[baseline].median

    def describe(self, label: str, limit: float, *, title: str) -> str:
        """The assertion name: both medians, the ratio, the limit, the raw samples, any failure."""
        variant = self.variants[label]
        text = (
            f"{title}: command median {variant.median:.3f} s / start-up floor median {self.floor.median:.3f} s "
            f"= ratio {self.ratio(label):.3f} (limit {limit}); command samples {variant.raw}; floor samples {self.floor.raw}"
        )
        failures = [item for item in (self.floor.failure, variant.failure) if item]
        return f"{text}; {'; '.join(failures)}" if failures else text


def measure_group(floor: SampleFn, variants: Mapping[str, SampleFn], *, runs: int = SAMPLE_RUNS) -> Measurement:
    """Take *runs* samples of the floor and of every variant, alternating them.

    Each round runs the floor and every variant once. The order flips on odd
    rounds (floor first, then floor last), so a drift in machine speed during
    the run lands on all series alike. Sampling stops at the first failed run:
    the failure is carried in the result, and a failed series has an infinite
    median.
    """
    order: list[tuple[str, SampleFn]] = [(_FLOOR_LABEL, floor), *variants.items()]
    collected: dict[str, list[Sample]] = {label: [] for label, _ in order}
    for round_index in range(runs):
        spawns = order if round_index % 2 == 0 else list(reversed(order))
        failed = False
        for label, spawn in spawns:
            sample = spawn()
            collected[label].append(sample)
            failed = failed or not sample.ok
        if failed:
            break
    return Measurement(
        floor=Series(_FLOOR_LABEL, tuple(collected.pop(_FLOOR_LABEL))),
        variants={label: Series(label, tuple(samples)) for label, samples in collected.items()},
    )


def measure_interleaved(command: SampleFn, floor: SampleFn, *, runs: int = SAMPLE_RUNS) -> Measurement:
    """Interleave *runs* spawns of one command with *runs* spawns of the floor."""
    return measure_group(floor, {"command": command}, runs=runs)


def spawn_timed(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    accepted_returncodes: Sequence[int] = (0,),
    clock: Callable[[], float] = time.monotonic,
    timeout: float = 120.0,
) -> Sample:
    """Run *argv* once and time it; a rejected exit code fails the sample with the stderr tail."""
    started = clock()
    completed = subprocess.run(list(argv), cwd=cwd, env=dict(env), capture_output=True, text=True, timeout=timeout, check=False)
    seconds = clock() - started
    if completed.returncode in accepted_returncodes:
        return Sample(seconds)
    return Sample(seconds, ok=False, detail=f"exit={completed.returncode}; stderr={completed.stderr[-_STDERR_TAIL_CHARS:]}")


_WORKLOAD_COMPILE = (
    "source = '\\n'.join("
    "f'def f{{i}}(a, b=1):\\n    x = [a, b, {{i}}]\\n    y = {{{{\\'k\\': x, \\'n\\': {{i}}}}}}\\n    return sum(x) + len(y)\\n'"
    " for i in range({functions})); exec(compile(source, 'workload', 'exec'), {{}})"
)


def fixed_workload_argv() -> list[str]:
    """A fresh interpreter doing fixed work: import :data:`FIXED_WORKLOAD_MODULES`, then compile a fixed generated source.

    The standard-library imports alone cost about a tenth of the CLI start-up
    (they come from cached bytecode), a denominator too small for a stable
    ratio. Compiling and executing a fixed amount of generated source adds the
    parse/compile/allocate work that import itself spends its time on. No
    product code and no third-party package is involved.
    """
    imports = "; ".join(f"import {module}" for module in FIXED_WORKLOAD_MODULES)
    return [sys.executable, "-c", f"{imports}; {_WORKLOAD_COMPILE.format(functions=FIXED_WORKLOAD_FUNCTIONS)}"]


def cli_argv(*args: str, module: str = "specify_cli") -> list[str]:
    """The real CLI entry point: ``python -m <module> <args>`` in a fresh interpreter."""
    return [sys.executable, "-m", module, *args]


_PLANT_TEMPLATE = '''\
"""Test-side planted slowdown: chains to any later sitecustomize, then burns CPU."""
import os
import sys


def _burn(iterations):
    value = 0
    for step in range(iterations):
        value = (value * 31 + step) & 0xFFFFFFFF
    return value


def _chain():
    here = os.path.dirname(os.path.abspath(__file__))
    for entry in sys.path:
        if os.path.abspath(entry or ".") == here:
            continue
        candidate = os.path.join(entry or ".", "sitecustomize.py")
        if os.path.isfile(candidate):
            with open(candidate, encoding="utf-8") as handle:
                exec(compile(handle.read(), candidate, "exec"), {{"__name__": "sitecustomize", "__file__": candidate}})
            return


_TOKEN = {token!r}
_BURNED = _TOKEN is None or _TOKEN in sys.argv[1:]
if _BURNED:
    _burn({iterations})
_chain()
'''


def plant_source(iterations: int, *, argv_token: str | None = None) -> str:
    """The ``sitecustomize.py`` text: a fixed-iteration CPU-bound loop, optionally gated on an argv token."""
    return _PLANT_TEMPLATE.format(iterations=int(iterations), token=argv_token)


def write_cpu_plant(directory: Path, iterations: int, *, argv_token: str | None = None) -> Path:
    """Write the planted ``sitecustomize.py`` into *directory* and return the directory.

    Put it first on the child's ``PYTHONPATH`` with :func:`with_plant`. The
    loop is CPU-bound and fixed-iteration, so it scales with the machine the
    way real work does; a sleep would not.
    """
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "sitecustomize.py").write_text(plant_source(iterations, argv_token=argv_token), encoding="utf-8")
    return directory


def with_plant(env: Mapping[str, str], plant_directory: Path) -> dict[str, str]:
    """A copy of *env* with *plant_directory* first on ``PYTHONPATH``."""
    existing = env.get("PYTHONPATH", "")
    return {**env, "PYTHONPATH": f"{plant_directory}{os.pathsep}{existing}" if existing else str(plant_directory)}
