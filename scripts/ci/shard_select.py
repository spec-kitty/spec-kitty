"""The one shard selector for the per-module CI matrix (mission
ci-runtime-stabilisation-01M3TZH6, WP01; research D-01, charter C-010).

``module-tests.yml`` used to carry this algorithm as an inline heredoc, and the
registry skew gate re-typed it. This module is the single authority they all
import instead: ``module-tests.yml`` (step ``select``) runs its ``module`` CLI,
``capture_shard_timings.py`` selects with :data:`MODULE_SELECTION_MARKER_EXPR`,
``tests/architectural/test_module_shard_registry.py`` reuses :func:`lpt_loads`,
and the module-length agreement gate consumes the same constant.

Everything at module scope is standard library only: ``capture_shard_timings.py``
is also run as a bare script (``python -I -S``), so this module must import
without site packages.

Module-row weights are **identity-keyed**. ``module_test_node_durations`` maps
exact pytest node ids to seconds and is the authority: :func:`resolve_node_weights`
joins it to live collection by node id, so an unchanged test keeps its own weight
when others are added, removed or reordered, and a new test takes the deterministic
median of its module's known timings. The old positional pairing is gone: a
same-size reorder used to silently move every weight one place. A module whose
ledger still holds only the legacy positional ``module_test_durations`` array is
weighted uniformly and *loudly* (a ``::warning title=shard timings::`` annotation
plus one ``$GITHUB_STEP_SUMMARY`` line): the ids were never recorded, so guessing
them is not an option -- only a recapture can migrate the row. The same report
names every missing and stale node id, so drift stays visible on the PR that
caused it.

WP02 also owns the battery's file granularity: :func:`enumerate_base_files` is
THE list of battery test files (the WP05 plugin and the WP06 gate model both
call it, D-24), :func:`resolve_file_weights` weighs files by repo-relative path
with a median for untimed ones, and :func:`battery_parts` computes the
``fast`` / ``1/n`` ... ``n/n`` partition with the same LPT as the module rows.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import re
import statistics
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TextIO

__all__ = [
    "DEFAULT_OUT_PATH",
    "DEFAULT_PYTHON_FILES",
    "DEFAULT_TIMINGS_PATH",
    "EXIT_NO_TESTS",
    "EXIT_USAGE",
    "MODULE_NODE_DURATIONS_KEY",
    "MODULE_SELECTION_MARKER_EXPR",
    "NORECURSE_DIR_PATTERNS",
    "BatteryPartition",
    "ModuleTimings",
    "WeightResolution",
    "battery_parts",
    "enumerate_base_files",
    "escape_workflow_command_message",
    "load_module_timings",
    "lpt_assign",
    "lpt_loads",
    "main",
    "parse_shard",
    "report_mismatch",
    "resolve_file_weights",
    "resolve_module_test_dirs",
    "resolve_node_weights",
    "validate_node_durations",
]

#: The single marker authority for module-row selection: the wall-clock/benchmark
#: budget guards (``performance``) and the concurrency/load suite (``stress``)
#: belong to the nightly lanes, never to a module shard.
MODULE_SELECTION_MARKER_EXPR: Final = "not performance and not stress"

#: THE identity-keyed duration table: ``{module: {node_id: seconds}}``. Weights are
#: joined to collected tests by node id, never by position -- a reordered suite of
#: unchanged size therefore cannot silently re-weight other tests. The positional
#: ``module_test_durations`` list is a derived projection of this table (written
#: beside it so the count/length consumers keep one meaning), and a module that has
#: only the legacy list is weighted uniformly with an explicit warning.
MODULE_NODE_DURATIONS_KEY: Final = "module_test_node_durations"

#: Exit status for "nothing to select" -- the legacy heredoc's value.
EXIT_NO_TESTS: Final = 64

#: Exit status for a malformed command line (a bad ``--shard``): argparse's own usage-error status.
EXIT_USAGE: Final = 2

DEFAULT_TIMINGS_PATH: Final = ".github/ci-shard-timings.json"
DEFAULT_OUT_PATH: Final = "shard_tests.txt"

#: pytest's default ``python_files`` (``pytest.ini`` does not override it; pinned
#: by ``test_module_shard_registry.py``).
DEFAULT_PYTHON_FILES: Final = ("test_*.py", "*_test.py")

#: Directory-name patterns pytest does not recurse into: its documented default
#: ``norecursedirs`` (``*.egg .* _darcs build CVS dist node_modules venv {arch}``)
#: plus ``__pycache__`` (it holds no ``.py`` files worth walking).
NORECURSE_DIR_PATTERNS: Final = ("*.egg", ".*", "_darcs", "build", "CVS", "dist", "node_modules", "venv", "{arch}", "__pycache__")

_UNIFORM_WEIGHT: Final = 1.0
_NODE_ID_SEPARATOR: Final = "::"
_LOG_PREFIX: Final = "module-tests"
_WARNING_TITLE: Final = "shard timings"
_SUMMARY_ENV: Final = "GITHUB_STEP_SUMMARY"
_MAX_NAMES_LISTED: Final = 10
_FAST_PART: Final = "fast"
_NO_TIMINGS_REASON: Final = "no timings for this key \N{EM DASH} uniform weights"
_LEGACY_REASON: Final = "legacy positional durations cannot be matched to node ids \N{EM DASH} recapture to record node ids; uniform weights"
_CONFTEST: Final = "conftest.py"


def _least_loaded(loads: Sequence[float]) -> int:
    """Index of the least-loaded bin; the lowest index wins ties."""
    return min(range(len(loads)), key=lambda k: loads[k])


def _require_bins(bins: int) -> None:
    if bins < 1:
        raise ValueError(f"bins must be >= 1, got {bins}")


def lpt_assign(items: Sequence[tuple[str, float]], bins: int) -> list[list[str]]:
    """Greedy LPT (longest-processing-time-first) assignment of *items* to *bins*.

    Items are stable-sorted by weight descending over the caller's order, then
    each goes to the currently least-loaded bin (lowest index on ties). Returns
    one list of item ids per bin, in placement order.
    """
    _require_bins(bins)
    assigned: list[list[str]] = [[] for _ in range(bins)]
    loads = [0.0] * bins
    for item_id, weight in sorted(items, key=lambda pair: pair[1], reverse=True):
        target = _least_loaded(loads)
        assigned[target].append(item_id)
        loads[target] += weight
    return assigned


def lpt_loads(weights: Sequence[float], bins: int) -> list[float]:
    """Bin loads after greedy LPT placement of *weights* (same rule as :func:`lpt_assign`)."""
    _require_bins(bins)
    loads = [0.0] * bins
    for weight in sorted(weights, reverse=True):
        loads[_least_loaded(loads)] += weight
    return loads


@dataclass(frozen=True)
class WeightResolution:
    """Weights for a set of keys, plus whatever did not line up (never silent).

    ``reason`` is ``None`` when the timings agreed with the keys; otherwise it
    is the one-line explanation :func:`report_mismatch` prints.
    """

    weights: tuple[float, ...]
    missing: tuple[str, ...]
    stale: tuple[str, ...]
    reason: str | None

    @property
    def mismatch(self) -> bool:
        return self.reason is not None


def _is_seconds(value: object) -> bool:
    """True for a finite, non-negative, non-bool number of seconds."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    return math.isfinite(float(value)) and float(value) >= 0.0


def validate_node_durations(value: object) -> str | None:
    """``None`` when *value* is a usable node-id -> seconds mapping, otherwise why not.

    THE structural check for ``module_test_node_durations[<module>]``: exact pytest
    node ids (each carrying ``::``) mapped to finite, non-negative seconds. A list
    (the retired positional shape), an empty mapping, a key that is not a node id,
    or a NaN/infinite/negative/bool/string duration is rejected by name so callers
    fail closed on uniform weights instead of weighting a shard with data they
    cannot interpret.
    """
    if not isinstance(value, Mapping):
        return f"expected a node-id -> seconds mapping, got {type(value).__name__}"
    if not value:
        return "no node-id -> seconds entries"
    bad_keys = [str(key) for key in value if not isinstance(key, str) or _NODE_ID_SEPARATOR not in key]
    if bad_keys:
        return f"keys that are not pytest node ids (no '::') -- {_describe_names(len(bad_keys), 'key(s)', bad_keys)}"
    bad_values = [str(key) for key, seconds in value.items() if not _is_seconds(seconds)]
    if bad_values:
        return f"entries with a non-finite/negative/non-numeric duration -- {_describe_names(len(bad_values), 'entry(s)', bad_values)}"
    return None


@dataclass(frozen=True)
class ModuleTimings:
    """What the timings artefact holds for one module: keyed durations, and the legacy list size.

    ``node_durations`` is ``None`` when the module has no identity-keyed table (a legacy
    capture, or no capture at all); ``legacy_entries`` is the length of the positional
    ``module_test_durations`` list, reported so the warning can say how much data is
    waiting on a recapture.
    """

    node_durations: Mapping[str, float] | None
    legacy_entries: int


def resolve_node_weights(
    node_ids: Sequence[str],
    node_durations: Mapping[str, float] | None,
    *,
    legacy_entries: int = 0,
) -> WeightResolution:
    """Weights for *node_ids* from identity-keyed *node_durations* -- never positionally.

    Every collected id keeps its OWN measured seconds, so a reorder or an insertion
    never moves one test's weight onto another. Ids with no timing get the median of
    the module's known timings (deterministic: ``statistics.median`` of the same
    values, and stale keys never skew it). Missing and stale ids are reported.

    Without an identity-keyed table (``None``) the weights are uniform and the reason
    says why: a legacy positional list cannot be paired with collected ids without
    guessing, so it is never paired at all -- fail closed, loudly, until a recapture
    records the node ids.
    """
    reason: str | None
    if node_durations is None:
        reason = f"{legacy_entries} legacy positional durations for {len(node_ids)} collected tests: {_LEGACY_REASON}" if legacy_entries else _NO_TIMINGS_REASON
        return WeightResolution((_UNIFORM_WEIGHT,) * len(node_ids), (), (), reason)
    problem = validate_node_durations(node_durations)
    if problem is not None:
        reason = f"identity-keyed durations unusable ({problem}) \N{EM DASH} uniform weights"
        return WeightResolution((_UNIFORM_WEIGHT,) * len(node_ids), (), (), reason)
    known = {node_id: float(node_durations[node_id]) for node_id in node_ids if node_id in node_durations}
    stale = tuple(sorted(set(node_durations) - set(node_ids)))
    missing = tuple(node_id for node_id in node_ids if node_id not in known)
    if not known:
        reason = f"no identity-keyed duration matches a collected test ({len(stale)} stale) \N{EM DASH} uniform weights"
        return WeightResolution((_UNIFORM_WEIGHT,) * len(node_ids), missing, stale, reason)
    fill = float(statistics.median(known.values()))
    weights = tuple(known.get(node_id, fill) for node_id in node_ids)
    reason = None
    if missing or stale:
        reason = f"{len(missing)} collected tests without a timing get the median {fill:g}s; {len(stale)} identity-keyed timings match no collected test"
    return WeightResolution(weights, missing, stale, reason)


def load_module_timings(timings_path: str | os.PathLike[str], module: str) -> ModuleTimings:
    """Read the timings artefact for *module*: its keyed table (if any) and legacy list length.

    A missing file, an unreadable shape or a module with no rows reads as "no timings".
    The keyed table is returned verbatim (still unvalidated) so that
    :func:`resolve_node_weights` is the single place that judges it.
    """
    try:
        with open(timings_path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except FileNotFoundError:
        return ModuleTimings(None, 0)
    if not isinstance(payload, Mapping):
        return ModuleTimings(None, 0)
    keyed = payload.get(MODULE_NODE_DURATIONS_KEY)
    raw_node_durations = keyed.get(module) if isinstance(keyed, Mapping) else None
    legacy = payload.get("module_test_durations")
    legacy_rows = legacy.get(module) if isinstance(legacy, Mapping) else None
    return ModuleTimings(raw_node_durations, len(legacy_rows) if isinstance(legacy_rows, list) else 0)


def escape_workflow_command_message(message: str) -> str:
    """Escape *message* for a GitHub workflow command (``%``, CR and LF)."""
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _describe_names(count: int, kind: str, names: Sequence[str]) -> str:
    listed = ", ".join(names[:_MAX_NAMES_LISTED])
    more = "" if len(names) <= _MAX_NAMES_LISTED else ", ..."
    return f"{count} {kind}: {listed}{more}"


def _mismatch_message(resolution: WeightResolution) -> str:
    parts = [str(resolution.reason)]
    if resolution.missing:
        parts.append(_describe_names(len(resolution.missing), "missing", resolution.missing))
    if resolution.stale:
        parts.append(_describe_names(len(resolution.stale), "stale", resolution.stale))
    return "; ".join(parts)


def report_mismatch(resolution: WeightResolution, *, label: str, stream: TextIO | None = None) -> None:
    """Report a timing mismatch loudly: annotation on *stream*, one line in the step summary.

    Silent when the resolution agrees. The annotation goes to stdout (resolved at
    call time so captured output sees it); the summary line is appended to the
    file named by ``$GITHUB_STEP_SUMMARY`` when that is set.
    """
    if not resolution.mismatch:
        return
    out = sys.stdout if stream is None else stream
    message = _mismatch_message(resolution)
    print(f"::warning title={_WARNING_TITLE}::{escape_workflow_command_message(f'{label}: {message}')}", file=out)
    summary_path = os.environ.get(_SUMMARY_ENV)
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(f"- {_WARNING_TITLE} \N{EM DASH} {label}: {message.replace(chr(10), ' ')}\n")


def resolve_file_weights(files: Sequence[str], file_durations: Mapping[str, float]) -> WeightResolution:
    """Weights for repo-relative *files* from path-keyed *file_durations*.

    A file with no timing gets the median of the known weights of *files* (stale
    keys never skew it); with no usable timing at all every file weighs ``1.0``.
    Missing files and stale timing keys are reported, never silently dropped.
    """
    known = {f: float(file_durations[f]) for f in files if f in file_durations}
    stale = tuple(sorted(set(file_durations) - set(files)))
    missing = tuple(f for f in files if f not in known)
    if not known:
        return WeightResolution((_UNIFORM_WEIGHT,) * len(files), missing, stale, _NO_TIMINGS_REASON)
    fill = float(statistics.median(known.values()))
    weights = tuple(known.get(f, fill) for f in files)
    reason = None
    if missing or stale:
        reason = f"{len(missing)} files without a timing get the median {fill:g}s; {len(stale)} stale timing keys"
    return WeightResolution(weights, missing, stale, reason)


def _is_norecurse_dir(name: str) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in NORECURSE_DIR_PATTERNS)


def _is_collectable_test_file(name: str, python_files: Sequence[str]) -> bool:
    # pytest has no private-prefix rule: with the default ``python_files`` an ``_x_test.py`` IS collected.
    if name == _CONFTEST:
        return False
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in python_files)


def _walk_test_files(start: Path, python_files: Sequence[str]) -> Iterable[Path]:
    if start.is_file():
        if _is_collectable_test_file(start.name, python_files):
            yield start
        return
    for current, dirs, names in os.walk(start):
        dirs[:] = sorted(d for d in dirs if not _is_norecurse_dir(d))
        for name in sorted(names):
            if _is_collectable_test_file(name, python_files):
                yield Path(current) / name


def enumerate_base_files(
    paths: Sequence[str],
    *,
    deselect: Iterable[str] = (),
    root: Path,
    python_files: Sequence[str] = DEFAULT_PYTHON_FILES,
) -> tuple[str, ...]:
    """THE list of battery test files: repo-relative posix paths, sorted, de-duplicated.

    Mirrors pytest's default collection: it walks each of *paths* under *root*,
    skips :data:`NORECURSE_DIR_PATTERNS`, keeps basenames matching *python_files*
    and drops ``conftest.py``. Only whole-file *deselect*
    entries apply; a node-level entry (containing ``::``) removes tests, not a
    file, so it cannot change the file set and is ignored here.
    """
    dropped = {entry for entry in deselect if _NODE_ID_SEPARATOR not in entry}
    found = {path.relative_to(root).as_posix() for rel in paths for path in _walk_test_files(root / rel, python_files)}
    return tuple(sorted(found - dropped))


@dataclass(frozen=True)
class BatteryPartition:
    """The battery split: ``parts`` by key (``fast``, ``1/n`` ... ``n/n``) and the predicted ``loads`` of the numbered ones."""

    parts: Mapping[str, frozenset[str]]
    loads: Mapping[str, float]
    resolution: WeightResolution


def battery_parts(
    base_files: Sequence[str],
    roster: Sequence[str],
    shard_count: int,
    file_durations: Mapping[str, float],
) -> BatteryPartition:
    """Partition *base_files* into the ``fast`` roster and *shard_count* LPT-balanced shards.

    Pure and order-independent: inputs are sorted before weighing so the result
    depends only on the sets and the timings. Raises :class:`ValueError` for
    ``shard_count < 1`` or a roster entry outside *base_files*.
    """
    if shard_count < 1:
        raise ValueError(f"shard_count must be >= 1, got {shard_count}")
    base = set(base_files)
    outside = sorted(set(roster) - base)
    if outside:
        raise ValueError(f"roster entries not in the base files: {', '.join(outside)}")
    remaining = sorted(base - set(roster))
    # A timed roster file is in the base, not stale: only keys outside the base are reported.
    fast = set(roster)
    resolution = resolve_file_weights(remaining, {file: seconds for file, seconds in file_durations.items() if file not in fast})
    weight = dict(zip(remaining, resolution.weights, strict=True))
    placement = lpt_assign(list(weight.items()), shard_count)
    parts: dict[str, frozenset[str]] = {_FAST_PART: frozenset(roster)}
    loads: dict[str, float] = {}
    for index, files in enumerate(placement, start=1):
        key = f"{index}/{shard_count}"
        parts[key] = frozenset(files)
        loads[key] = sum(weight[f] for f in files)
    return BatteryPartition(parts, loads, resolution)


def resolve_module_test_dirs(module: str, registry_test_dirs_json: str) -> list[str]:
    """The existing test directories to collect for *module*.

    Aggregate and dual-tree modules declare an explicit ``test_dirs`` JSON list
    in the registry; prefer its existing entries. Every other module falls back
    to the mirrored ``tests/<module>`` directory. Returns ``[]`` when neither exists.
    """
    declared = json.loads(registry_test_dirs_json) if registry_test_dirs_json else []
    existing = [d for d in declared if os.path.isdir(d)]
    if existing:
        return existing
    mirror = f"tests/{module}"
    return [mirror] if os.path.isdir(mirror) else []


def _collect_node_ids(python: str, test_dirs: Sequence[str]) -> list[str]:
    collected = subprocess.run(
        [python, "-m", "pytest", *test_dirs, "-m", MODULE_SELECTION_MARKER_EXPR, "--collect-only", "-q"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in collected.stdout.splitlines() if _NODE_ID_SEPARATOR in line]


_SHARD_SPEC: Final = re.compile(r"([0-9]+)/([0-9]+)")


def parse_shard(shard: str) -> tuple[int, int]:
    """Parse a 1-based ``i/n`` shard spec (``1 <= i <= n``); raise :class:`ValueError` otherwise.

    ``0/2`` would otherwise select the last bin through ``[-1]`` and ``3/2`` would raise an
    ``IndexError``; both are a mis-wired matrix row and must fail loudly instead.
    """
    match = _SHARD_SPEC.fullmatch(shard)
    if match:
        idx, total = int(match.group(1)), int(match.group(2))
        if 1 <= idx <= total:
            return idx, total
    raise ValueError(f"shard {shard!r} is not 'i/n' with 1 <= i <= n")


def _error(message: str) -> int:
    print(f"::error::{_LOG_PREFIX}: {message}")
    return EXIT_NO_TESTS


def _select_module(args: argparse.Namespace) -> int:
    try:
        idx, total = parse_shard(args.shard)
    except ValueError as exc:
        print(f"::error::{_LOG_PREFIX}: {exc}")
        return EXIT_USAGE
    test_dirs = resolve_module_test_dirs(args.module, args.test_dirs)
    if not test_dirs:
        return _error(f"no test directory found for module {args.module!r} (looked for tests/{args.module} or the registry's test_dirs)")

    node_ids = _collect_node_ids(args.python, test_dirs)
    if not node_ids:
        return _error(f"pytest collected zero tests for module {args.module!r} under {test_dirs!r}")

    timings = load_module_timings(args.timings, args.module)
    resolution = resolve_node_weights(node_ids, timings.node_durations, legacy_entries=timings.legacy_entries)
    report_mismatch(resolution, label=f"module {args.module}")
    selected = lpt_assign(list(zip(node_ids, resolution.weights, strict=True)), total)[idx - 1]
    Path(args.out).write_text("\n".join(selected), encoding="utf-8")
    print(f"{_LOG_PREFIX}: selected {len(selected)}/{len(node_ids)} tests for {args.module} shard {idx}/{total}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="command", required=True)
    module = sub.add_parser("module", help="select one module row's shard of tests")
    module.add_argument("--module", required=True)
    module.add_argument("--shard", required=True, help="i/n, 1-based")
    module.add_argument("--test-dirs", default="", help="registry test_dirs as a JSON list (may be empty)")
    module.add_argument("--python", default=sys.executable, help="interpreter for the collect-only run")
    module.add_argument("--timings", default=DEFAULT_TIMINGS_PATH)
    module.add_argument("--out", default=DEFAULT_OUT_PATH)
    parts = sub.add_parser("battery-parts", help="print the battery partition (file count and predicted load per part)")
    parts.add_argument("--path", action="append", required=True, help="a test directory or file to enumerate (repeatable)")
    parts.add_argument("--deselect", action="append", default=[], help="a whole-file deselect (repeatable)")
    parts.add_argument("--roster", required=True, help="file listing the fast roster, one repo-relative path per line")
    parts.add_argument("--timings", required=True, help="JSON object mapping repo-relative test file to seconds")
    parts.add_argument("--shards", type=int, required=True)
    parts.add_argument("--root", default=".")
    return parser


def _print_battery_parts(args: argparse.Namespace) -> int:
    root = Path(args.root)
    base = enumerate_base_files(args.path, deselect=args.deselect, root=root)
    roster = [line.strip() for line in Path(args.roster).read_text(encoding="utf-8").splitlines() if line.strip()]
    durations = json.loads(Path(args.timings).read_text(encoding="utf-8"))
    result = battery_parts(base, roster, args.shards, durations)
    report_mismatch(result.resolution, label="battery")
    for key, files in result.parts.items():
        load = f", predicted load {result.loads[key]:.1f}s" if key in result.loads else ""
        print(f"{key}: {len(files)} files{load}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; returns the process exit status."""
    args = _build_parser().parse_args(argv)
    if args.command == "battery-parts":
        return _print_battery_parts(args)
    return _select_module(args)


if __name__ == "__main__":
    raise SystemExit(main())
