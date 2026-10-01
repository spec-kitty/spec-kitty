"""pytest plugin that makes ONE invocation execute exactly one part of the
architectural battery (mission ci-runtime-stabilisation-01M3TZH6, WP05; research
D-02, D-23, D-24, D-26; contract ``contracts/battery-partition.md``).

Invocation form (the literal, statically readable flag is the gate model's input)::

    python -m pytest tests/architectural -m "<base marker>" <base --deselect ...> \\
        -n 4 --dist loadfile -p scripts.ci.battery_partition_plugin --battery-part fast|i/n

Without ``--battery-part`` the plugin is inert, so the nightly backstop (which runs
the base selection with no partition flag) never depends on this code.

Rules the plugin keeps
----------------------
* **Every process computes the part.** Under ``--dist loadfile`` the xdist controller
  does not collect; the workers do. So the part is computed deterministically in the
  controller *and* in every worker from the registry and the committed timings, through
  the one enumeration and the one selector in ``scripts/ci/shard_select.py`` (C-010).
  The controller ships a digest of its part in ``workerinput``; a worker whose own
  digest differs refuses to start (:func:`verify_worker_digest`).
* **It only ignores enumerated test files outside the part.** ``pytest_ignore_collect``
  returns ``True`` for such a file and ``None`` otherwise -- never ``False`` (which would
  force collection and override other ignore logic), never a directory, ``conftest.py``,
  an ``_*.py`` helper or a non-enumerated file. An enumeration gap therefore shows up as
  an overlap (caught by the self-check below), never as a silently lost file.
* **A runtime self-check fails the session** when any executed test's file is outside the
  part (exit status 1, a ``::error::`` line naming the files).
* **It fails closed** (:class:`pytest.UsageError`) when the invocation's paths, marker or
  whole-file deselects differ from the registry ``base`` (``--ignore=<file>`` counts as a
  whole-file deselect: the gate model's ``collect_job_nodeids`` passes the base that way),
  when ``i/n`` disagrees with ``shard_count``, and -- only under ``GITHUB_ACTIONS`` and
  never under ``--collect-only`` -- when the xdist worker count differs from the registry
  ``workers``.
* **It never hides a timing mismatch.** The controller (once) reports files without a
  timing through ``shard_select.report_mismatch`` (annotation + step-summary line), and
  prints a per-part summary (files, predicted load, workers seen, slowest test, per-file
  seconds; roster budget overruns and any test over 180 s as ``::warning::``) to the log
  and ``$GITHUB_STEP_SUMMARY``. Runtime overruns are warnings only -- runner-hardware
  spread is ~1.77x, so a hard runtime budget would mint a flake class; the static budget
  check is a test.

Standard library plus ``pytest``/``yaml`` only; ``yaml`` is imported lazily.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Final

import pytest

from scripts.ci.shard_select import (
    BatteryPartition,
    battery_parts,
    enumerate_base_files,
    escape_workflow_command_message,
    report_mismatch,
)

__all__ = [
    "PARTITION_STATE_KEY",
    "WORKERINPUT_DIGEST_KEY",
    "BaseSelection",
    "BatteryRuntime",
    "BatterySpec",
    "PartSpec",
    "PartitionState",
    "RosterEntry",
    "RunStats",
    "build_state",
    "compute_partition",
    "escalated_exitstatus",
    "files_outside_part",
    "invocation_mismatches",
    "load_battery_spec",
    "load_battery_timings",
    "normalise_deselect",
    "overrun_warnings",
    "parse_part",
    "part_digest",
    "part_problem",
    "pytest_addoption",
    "pytest_configure",
    "pytest_ignore_collect",
    "relativize_arg",
    "running_on_github_actions",
    "summary_lines",
    "verify_worker_digest",
    "worker_count_problem",
    "write_step_summary",
]

#: Key under which the controller ships its part digest to each worker.
WORKERINPUT_DIGEST_KEY: Final = "battery_part_digest"

_FAST: Final = "fast"
_NUMBERED_PART: Final = re.compile(r"([0-9]+)/([0-9]+)")
_REGISTRY_KEY_PATH: Final = "special_tiers.architectural"
_DEFAULT_REGISTRY: Final = ".github/ci-module-registry.yml"
_DEFAULT_TIMINGS: Final = ".github/ci-shard-timings.json"
_TIMINGS_TABLE: Final = "battery_file_durations"
_GITHUB_ACTIONS_ENV: Final = "GITHUB_ACTIONS"
_STEP_SUMMARY_ENV: Final = "GITHUB_STEP_SUMMARY"
_NODE_ID_SEPARATOR: Final = "::"
_SLOW_TEST_SECONDS: Final = 180.0
_TOP_FILES: Final = 10
_SINGLE_PROCESS: Final = "main"
_PREFIX: Final = "battery partition"
_OPTION_DEST: Final = "battery_part"


# ---------------------------------------------------------------------------
# --battery-part
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PartSpec:
    """The requested part: ``fast`` (no index) or the ``index``-th of ``total`` shards."""

    index: int | None
    total: int | None

    @property
    def is_fast(self) -> bool:
        return self.index is None

    @property
    def key(self) -> str:
        return _FAST if self.index is None else f"{self.index}/{self.total}"


def parse_part(value: str) -> PartSpec:
    """Parse ``fast`` or ``i/n`` (``1 <= i <= n``); raise :class:`ValueError` otherwise."""
    if value == _FAST:
        return PartSpec(None, None)
    match = _NUMBERED_PART.fullmatch(value)
    if match:
        index, total = int(match.group(1)), int(match.group(2))
        if 1 <= index <= total:
            return PartSpec(index, total)
    raise ValueError(f"battery-part {value!r} is not 'fast' or 'i/n' with 1 <= i <= n")


def part_problem(part: PartSpec, shard_count: int) -> str | None:
    """Why *part* cannot run against a registry with *shard_count* shards, or ``None``."""
    if part.total is None or part.total == shard_count:
        return None
    return f"{_PREFIX}: part {part.key} disagrees with the registry {_REGISTRY_KEY_PATH}.shards.shard_count {shard_count}"


# ---------------------------------------------------------------------------
# Registry / timings -> typed spec
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RosterEntry:
    """One fast-gate roster file with its runtime budget."""

    path: str
    budget_seconds: int
    reason: str


@dataclass(frozen=True)
class BaseSelection:
    """The battery's base selection: what an unpartitioned run would collect."""

    paths: tuple[str, ...]
    marker: str
    deselect: tuple[str, ...]


@dataclass(frozen=True)
class BatterySpec:
    """``special_tiers.architectural`` of ``.github/ci-module-registry.yml``, typed."""

    workers: int
    base: BaseSelection
    fast_job: str
    max_file_budget_seconds: int
    max_total_measured_seconds: int
    roster: tuple[RosterEntry, ...]
    shards_job: str
    shard_count: int
    granularity: str
    timings_key: str

    @property
    def roster_paths(self) -> tuple[str, ...]:
        return tuple(entry.path for entry in self.roster)


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path}: expected a mapping")
    return value


def _field(node: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in node:
        raise ValueError(f"{_join(path, key)}: missing")
    return node[key]


def _text(node: Mapping[str, Any], key: str, path: str) -> str:
    value = _field(node, key, path)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{_join(path, key)}: expected a non-empty string")
    return value


def _count(node: Mapping[str, Any], key: str, path: str) -> int:
    value = _field(node, key, path)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{_join(path, key)}: expected an integer >= 1")
    return int(value)


def _texts(node: Mapping[str, Any], key: str, path: str, *, allow_empty: bool) -> tuple[str, ...]:
    value = _field(node, key, path)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value) or not (value or allow_empty):
        raise ValueError(f"{_join(path, key)}: expected a {'list' if allow_empty else 'non-empty list'} of non-empty strings")
    return tuple(value)


def _roster(node: Mapping[str, Any], path: str) -> tuple[RosterEntry, ...]:
    items = _field(node, "roster", path)
    if not isinstance(items, list):
        raise ValueError(f"{_join(path, 'roster')}: expected a list")
    entries = []
    for position, raw in enumerate(items):
        where = f"{_join(path, 'roster')}[{position}]"
        item = _mapping(raw, where)
        entries.append(RosterEntry(_text(item, "path", where), _count(item, "budget_seconds", where), _text(item, "reason", where)))
    return tuple(entries)


def load_battery_spec(registry: Mapping[str, Any]) -> BatterySpec:
    """The typed ``special_tiers.architectural`` entry of the parsed *registry*.

    Raises :class:`ValueError` naming the key path of any schema problem.
    """
    tiers = _mapping(_field(registry, "special_tiers", ""), "special_tiers")
    entry = _mapping(_field(tiers, "architectural", "special_tiers"), _REGISTRY_KEY_PATH)
    base = _mapping(_field(entry, "base", _REGISTRY_KEY_PATH), f"{_REGISTRY_KEY_PATH}.base")
    fast = _mapping(_field(entry, "fast_gate", _REGISTRY_KEY_PATH), f"{_REGISTRY_KEY_PATH}.fast_gate")
    shards = _mapping(_field(entry, "shards", _REGISTRY_KEY_PATH), f"{_REGISTRY_KEY_PATH}.shards")
    where = {name: f"{_REGISTRY_KEY_PATH}.{name}" for name in ("base", "fast_gate", "shards")}
    return BatterySpec(
        workers=_count(entry, "workers", _REGISTRY_KEY_PATH),
        base=BaseSelection(
            paths=_texts(base, "paths", where["base"], allow_empty=False),
            marker=_text(base, "marker", where["base"]),
            deselect=_texts(base, "deselect", where["base"], allow_empty=True),
        ),
        fast_job=_text(fast, "job", where["fast_gate"]),
        max_file_budget_seconds=_count(fast, "max_file_budget_seconds", where["fast_gate"]),
        max_total_measured_seconds=_count(fast, "max_total_measured_seconds", where["fast_gate"]),
        roster=_roster(fast, where["fast_gate"]),
        shards_job=_text(shards, "job", where["shards"]),
        shard_count=_count(shards, "shard_count", where["shards"]),
        granularity=_text(shards, "granularity", where["shards"]),
        timings_key=_text(shards, "timings_key", where["shards"]),
    )


def load_battery_timings(timings: Mapping[str, Any], key: str) -> dict[str, float]:
    """``battery_file_durations[key]`` as ``{path: seconds}``; a missing table or key is ``{}``."""
    tables = timings.get(_TIMINGS_TABLE) or {}
    table = _mapping(tables, _TIMINGS_TABLE).get(key) or {}
    result: dict[str, float] = {}
    for file, seconds in _mapping(table, f"{_TIMINGS_TABLE}.{key}").items():
        if isinstance(seconds, bool) or not isinstance(seconds, int | float):
            raise ValueError(f"{_TIMINGS_TABLE}.{key}.{file}: expected a number")
        result[str(file)] = float(seconds)
    return result


# ---------------------------------------------------------------------------
# Invocation vs registry base
# ---------------------------------------------------------------------------
def relativize_arg(arg: str, *, base_dir: Path, root: Path) -> str:
    """*arg* (a path, optionally ``path::node``) as a *root*-relative posix string.

    A relative *arg* is resolved against *base_dir* first. An argument outside
    *root* is returned unchanged.
    """
    head, separator, tail = arg.partition(_NODE_ID_SEPARATOR)
    candidate = Path(os.path.normpath(head if os.path.isabs(head) else base_dir / head))
    try:
        relative = candidate.relative_to(Path(os.path.normpath(root))).as_posix()
    except ValueError:
        return arg
    return relative + separator + tail


def normalise_deselect(arg: str, *, root: Path) -> str:
    """A ``--deselect`` id as pytest matches it: *root*-relative, without ``./`` or an absolute prefix."""
    return relativize_arg(arg, base_dir=root, root=root)


def invocation_mismatches(
    paths: Iterable[str],
    marker: str | None,
    deselects: Iterable[str],
    ignores: Iterable[str],
    spec: BatterySpec,
) -> list[str]:
    """How this invocation differs from the registry ``base`` (empty when it matches).

    A whole-file ``--ignore`` is equivalent to a whole-file ``--deselect``: the
    **union** of both is compared with ``base.deselect``, so a directory
    ``--ignore`` or a node-level ``--deselect file::test`` is still a mismatch.
    """
    problems: list[str] = []
    if set(paths) != set(spec.base.paths):
        problems.append(f"{_PREFIX}: paths {sorted(set(paths))} != registry base.paths {list(spec.base.paths)}")
    if marker != spec.base.marker:
        problems.append(f"{_PREFIX}: -m {marker!r} != registry base.marker {spec.base.marker!r}")
    whole = set(deselects) | set(ignores)
    if whole != set(spec.base.deselect):
        problems.append(f"{_PREFIX}: --deselect/--ignore set {sorted(whole)} != registry base.deselect {list(spec.base.deselect)}")
    return problems


def running_on_github_actions(env: Mapping[str, str]) -> bool:
    """``True`` when *env* says this is a GitHub Actions runner (``GITHUB_ACTIONS=true``)."""
    return env.get(_GITHUB_ACTIONS_ENV) == "true"


def worker_count_problem(numprocesses: int | None, workers: int, *, github_actions: bool, collect_only: bool) -> str | None:
    """Why the xdist worker count is refused, or ``None``.

    Enforced only on CI, and never under ``--collect-only`` (which runs no tests and
    is how the gate model collects a part without ``-n``).
    """
    if not github_actions or collect_only or numprocesses == workers:
        return None
    shown = "no -n" if numprocesses is None else f"-n {numprocesses}"
    return f"{_PREFIX}: {_GITHUB_ACTIONS_ENV} run uses {shown} but the registry {_REGISTRY_KEY_PATH}.workers is {workers}"


# ---------------------------------------------------------------------------
# The part, in every process
# ---------------------------------------------------------------------------
def compute_partition(spec: BatterySpec, root: Path, timings: Mapping[str, float]) -> BatteryPartition:
    """The battery partition: the one enumeration, then the one selector (C-010)."""
    base_files = enumerate_base_files(spec.base.paths, deselect=spec.base.deselect, root=root)
    return battery_parts(base_files, spec.roster_paths, spec.shard_count, timings)


def part_digest(files: Iterable[str]) -> str:
    """sha256 of the sorted, newline-joined *files* -- the cross-process identity of a part."""
    return hashlib.sha256("\n".join(sorted(files)).encode("utf-8")).hexdigest()


def files_outside_part(executed: Iterable[str], part_files: Collection[str]) -> list[str]:
    """The *executed* files that are not in the part, sorted."""
    return sorted(set(executed) - set(part_files))


@dataclass(frozen=True)
class PartitionState:
    """What one process knows about its part; stashed on ``config``."""

    part: PartSpec
    part_files: frozenset[str]
    enumerated: frozenset[str]
    digest: str
    predicted_load: float | None
    budgets: Mapping[str, int]

    @cached_property
    def foreign(self) -> frozenset[str]:
        """Enumerated base files that belong to another part -- the only files ever ignored."""
        return self.enumerated - self.part_files


PARTITION_STATE_KEY: Final = pytest.StashKey[PartitionState]()


def build_state(part: PartSpec, spec: BatterySpec, partition: BatteryPartition) -> PartitionState:
    """The per-process state for *part* from a computed *partition*."""
    part_files = partition.parts[part.key]
    enumerated = frozenset().union(*partition.parts.values())
    budgets = {entry.path: entry.budget_seconds for entry in spec.roster} if part.is_fast else {}
    return PartitionState(part, part_files, enumerated, part_digest(part_files), partition.loads.get(part.key), budgets)


def verify_worker_digest(state: PartitionState, workerinput: Mapping[str, Any]) -> None:
    """Refuse (UsageError) when the controller's digest differs from this worker's (D-23)."""
    expected = workerinput.get(WORKERINPUT_DIGEST_KEY)
    if expected != state.digest:
        raise pytest.UsageError(
            f"{_PREFIX}: worker part digest {state.digest[:12]} != controller digest {str(expected)[:12]} -- the worker computed a different part"
        )


# ---------------------------------------------------------------------------
# Runtime evidence + self-check
# ---------------------------------------------------------------------------
@dataclass
class RunStats:
    """What actually ran: seconds per file and per test, files executed, workers seen."""

    file_seconds: dict[str, float] = field(default_factory=dict)
    test_seconds: dict[str, float] = field(default_factory=dict)
    workers: set[str] = field(default_factory=set)

    def record(self, nodeid: str, seconds: float) -> None:
        """Add one report's *seconds* to its test and its file."""
        file = nodeid.partition(_NODE_ID_SEPARATOR)[0]
        self.file_seconds[file] = self.file_seconds.get(file, 0.0) + seconds
        self.test_seconds[nodeid] = self.test_seconds.get(nodeid, 0.0) + seconds

    @property
    def executed_files(self) -> set[str]:
        return set(self.file_seconds)

    def slowest(self) -> tuple[str, float] | None:
        """The slowest test as ``(nodeid, seconds)``, or ``None`` when nothing ran."""
        if not self.test_seconds:
            return None
        return max(self.test_seconds.items(), key=lambda item: item[1])


def escalated_exitstatus(current: int, outside: Sequence[str]) -> int:
    """``TESTS_FAILED`` when files ran outside the part and the run would otherwise pass; else *current*."""
    if outside and int(current) == int(pytest.ExitCode.OK):
        return int(pytest.ExitCode.TESTS_FAILED)
    return current


def summary_lines(part: PartSpec, *, file_count: int, predicted_load: float | None, stats: RunStats) -> list[str]:
    """The per-part evidence block: part, files, predicted load, workers, slowest test, top files."""
    load = "" if predicted_load is None else f", predicted load {predicted_load:.1f}s"
    lines = [f"battery part {part.key}: {file_count} files{load}", f"workers seen: {', '.join(sorted(stats.workers)) or _SINGLE_PROCESS}"]
    slowest = stats.slowest()
    if slowest is not None:
        lines.append(f"slowest test: {slowest[0]} ({slowest[1]:.1f}s)")
    top = sorted(stats.file_seconds.items(), key=lambda item: (-item[1], item[0]))[:_TOP_FILES]
    lines.extend(f"  {file}: {seconds:.1f}s" for file, seconds in top)
    return lines


def _warning(title: str, message: str) -> str:
    return f"::warning title={title}::{escape_workflow_command_message(message)}"


def overrun_warnings(stats: RunStats, budgets: Mapping[str, int]) -> list[str]:
    """``::warning::`` lines for roster files over budget and any single test over 180 s (warnings only)."""
    lines = []
    for file, budget in sorted(budgets.items()):
        seconds = stats.file_seconds.get(file)
        if seconds is not None and seconds > budget:
            lines.append(_warning("battery budget", f"{file}: {seconds:.1f}s exceeds its {budget}s roster budget"))
    for nodeid, seconds in sorted(stats.test_seconds.items()):
        if seconds > _SLOW_TEST_SECONDS:
            lines.append(_warning("slow test", f"{nodeid}: {seconds:.0f}s exceeds {_SLOW_TEST_SECONDS:.0f}s"))
    return lines


def write_step_summary(lines: Iterable[str], *, env: Mapping[str, str] | None = None) -> None:
    """Append *lines* to the file named by ``$GITHUB_STEP_SUMMARY`` (a no-op when it is unset)."""
    target = (os.environ if env is None else env).get(_STEP_SUMMARY_ENV)
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.writelines(f"{line}\n" for line in lines)


class BatteryRuntime:
    """Controller-side (or single-process) runtime: ships the digest, records reports, self-checks."""

    def __init__(self, state: PartitionState) -> None:
        self.state = state
        self.stats = RunStats()

    @pytest.hookimpl(optionalhook=True)
    def pytest_configure_node(self, node: Any) -> None:
        """xdist: hand each worker the controller's part digest."""
        node.workerinput[WORKERINPUT_DIGEST_KEY] = self.state.digest

    @pytest.hookimpl(optionalhook=True)
    def pytest_testnodeready(self, node: Any) -> None:
        """xdist: remember which workers took part (``gw0`` ...)."""
        self.stats.workers.add(node.gateway.id)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        self.stats.record(report.nodeid, report.duration)

    def outside_files(self) -> list[str]:
        """Executed test files that are not in this part."""
        return files_outside_part(self.stats.executed_files, self.state.part_files)

    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        session.exitstatus = escalated_exitstatus(session.exitstatus, self.outside_files())

    def pytest_terminal_summary(self, terminalreporter: pytest.TerminalReporter) -> None:
        lines = summary_lines(self.state.part, file_count=len(self.state.part_files), predicted_load=self.state.predicted_load, stats=self.stats)
        warnings = overrun_warnings(self.stats, self.state.budgets)
        outside = self.outside_files()
        errors = []
        if outside:
            errors.append(
                f"::error title={_PREFIX}::{escape_workflow_command_message(f'executed test files outside part {self.state.part.key}: ' + ', '.join(outside))}"
            )
        for line in (*lines, *warnings, *errors):
            terminalreporter.write_line(line)
        write_step_summary([f"### {lines[0]}", *(f"- {line.strip()}" for line in lines[1:]), *warnings, *errors])


# ---------------------------------------------------------------------------
# Hooks (decision code lives in the helpers above)
# ---------------------------------------------------------------------------
def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("battery-partition", "architectural battery partition")
    group.addoption("--battery-part", dest=_OPTION_DEST, default=None, metavar="PART", help="run one part of the battery: 'fast' or 'i/n'")
    group.addoption("--battery-registry", dest="battery_registry", default=None, metavar="PATH", help=f"module registry (default <rootpath>/{_DEFAULT_REGISTRY})")
    group.addoption("--battery-timings", dest="battery_timings", default=None, metavar="PATH", help=f"shard timings (default <rootpath>/{_DEFAULT_TIMINGS})")


def _read_registry(path: Path) -> Mapping[str, Any]:
    import yaml  # lazy: only a partitioned run needs it

    if not path.is_file():
        raise pytest.UsageError(f"{_PREFIX}: registry file not found: {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _mapping(loaded, str(path))


def _read_timings(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise pytest.UsageError(f"{_PREFIX}: timings file not found: {path}")
    return _mapping(json.loads(path.read_text(encoding="utf-8")), str(path))


def _load_spec_and_timings(config: pytest.Config) -> tuple[BatterySpec, dict[str, float]]:
    root = config.rootpath
    registry = Path(config.getoption("battery_registry") or root / _DEFAULT_REGISTRY)
    timings = Path(config.getoption("battery_timings") or root / _DEFAULT_TIMINGS)
    try:
        spec = load_battery_spec(_read_registry(registry))
        return spec, load_battery_timings(_read_timings(timings), spec.timings_key)
    except ValueError as error:
        raise pytest.UsageError(f"{_PREFIX}: registry/timings schema problem -- {error}") from error


def _parse_requested_part(raw: str, spec: BatterySpec) -> PartSpec:
    try:
        part = parse_part(raw)
    except ValueError as error:
        raise pytest.UsageError(f"{_PREFIX}: {error}; the registry {_REGISTRY_KEY_PATH}.shards.shard_count is {spec.shard_count}") from error
    problem = part_problem(part, spec.shard_count)
    if problem:
        raise pytest.UsageError(problem)
    return part


def _validate_invocation(config: pytest.Config, spec: BatterySpec) -> None:
    root = config.rootpath
    invocation_dir = Path(config.invocation_params.dir)
    paths = [relativize_arg(arg, base_dir=invocation_dir, root=root) for arg in config.args]
    deselects = [normalise_deselect(arg, root=root) for arg in config.getoption("deselect") or []]
    ignores = [relativize_arg(arg, base_dir=invocation_dir, root=root) for arg in config.getoption("ignore") or []]
    problems = invocation_mismatches(paths, config.getoption("markexpr") or None, deselects, ignores, spec)
    problems_workers = worker_count_problem(
        getattr(config.option, "numprocesses", None),
        spec.workers,
        github_actions=running_on_github_actions(os.environ),
        collect_only=bool(config.getoption("collectonly")),
    )
    if problems_workers:
        problems.append(problems_workers)
    if problems:
        raise pytest.UsageError("\n".join(problems))


def pytest_configure(config: pytest.Config) -> None:
    raw = config.getoption(_OPTION_DEST)
    if raw is None:
        return
    spec, timings = _load_spec_and_timings(config)
    part = _parse_requested_part(raw, spec)
    workerinput = getattr(config, "workerinput", None)
    if workerinput is None:
        _validate_invocation(config, spec)
    partition = compute_partition(spec, config.rootpath, timings)
    state = build_state(part, spec, partition)
    config.stash[PARTITION_STATE_KEY] = state
    if workerinput is not None:
        verify_worker_digest(state, workerinput)
        return
    report_mismatch(partition.resolution, label=f"battery {spec.timings_key}")
    config.pluginmanager.register(BatteryRuntime(state), "battery-partition-runtime")


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    """Ignore an enumerated base file that belongs to another part; never anything else, never ``False``."""
    state = config.stash.get(PARTITION_STATE_KEY, None)
    if state is None or not collection_path.is_file():
        return None
    try:
        relative = collection_path.relative_to(config.rootpath).as_posix()
    except ValueError:
        return None
    return True if relative in state.foreign else None
