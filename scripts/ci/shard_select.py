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

Behaviour is intentionally identical to the retired heredoc, including its
silent uniform-weight fallback when the committed timings do not line up with
the collected tests.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

__all__ = [
    "DEFAULT_OUT_PATH",
    "DEFAULT_TIMINGS_PATH",
    "EXIT_NO_TESTS",
    "MODULE_SELECTION_MARKER_EXPR",
    "lpt_assign",
    "lpt_loads",
    "main",
    "positional_weights",
    "resolve_module_test_dirs",
]

#: The single marker authority for module-row selection: the wall-clock/benchmark
#: budget guards (``performance``) and the concurrency/load suite (``stress``)
#: belong to the nightly lanes, never to a module shard.
MODULE_SELECTION_MARKER_EXPR: Final = "not performance and not stress"

#: Exit status for "nothing to select" -- the legacy heredoc's value.
EXIT_NO_TESTS: Final = 64

DEFAULT_TIMINGS_PATH: Final = ".github/ci-shard-timings.json"
DEFAULT_OUT_PATH: Final = "shard_tests.txt"

_UNIFORM_WEIGHT: Final = 1.0
_NODE_ID_SEPARATOR: Final = "::"
_LOG_PREFIX: Final = "module-tests"


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


def positional_weights(node_ids: Sequence[str], durations: Sequence[float]) -> list[float]:
    """Weights for *node_ids*: the committed *durations* when the counts line up, else uniform.

    The committed timings drop node ids for compactness, so durations pair with
    collected tests by position. A length mismatch degrades to uniform weights.
    """
    if len(durations) == len(node_ids):
        return list(durations)
    return [_UNIFORM_WEIGHT] * len(node_ids)


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


def _load_durations(timings_path: str, module: str) -> list[float]:
    try:
        with open(timings_path, encoding="utf-8") as fh:
            timings = json.load(fh)
    except FileNotFoundError:
        return []
    return list(timings.get("module_test_durations", {}).get(module, []))


def _parse_shard(shard: str) -> tuple[int, int]:
    idx_text, _, total_text = shard.partition("/")
    return int(idx_text), int(total_text)


def _error(message: str) -> int:
    print(f"::error::{_LOG_PREFIX}: {message}")
    return EXIT_NO_TESTS


def _select_module(args: argparse.Namespace) -> int:
    idx, total = _parse_shard(args.shard)
    test_dirs = resolve_module_test_dirs(args.module, args.test_dirs)
    if not test_dirs:
        return _error(f"no test directory found for module {args.module!r} (looked for tests/{args.module} or the registry's test_dirs)")

    node_ids = _collect_node_ids(args.python, test_dirs)
    if not node_ids:
        return _error(f"pytest collected zero tests for module {args.module!r} under {test_dirs!r}")

    weights = positional_weights(node_ids, _load_durations(args.timings, args.module))
    selected = lpt_assign(list(zip(node_ids, weights, strict=True)), total)[idx - 1]
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; returns the process exit status."""
    args = _build_parser().parse_args(argv)
    return _select_module(args)


if __name__ == "__main__":
    raise SystemExit(main())
