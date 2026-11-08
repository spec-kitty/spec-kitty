"""The one shard selector for the nightly ``integration-next-shard-<N>`` jobs (#7456, #6787).

``ci-nightly.yml`` used to run ``pytest tests/integration tests/next`` as ONE job. The
#6715 lifecycle files took that lane from 9-17 min to 24-40 min (run 42516534769: 40:41
of suite time, ~2.5 worker-hours on 4 cores), and a single job cannot get faster, so the
lane is split into N independent jobs. Each job asks this script which test FILES it
owns and hands pytest that list under the same ``-n auto --dist loadfile`` it always used.

The partition is a deterministic, file-level longest-processing-time-first (LPT) split:

* The file universe is :func:`scripts.ci.shard_select.enumerate_base_files` over
  :data:`ROOTS`, the same enumeration the architectural battery partition uses, so a new
  test file under either root is owned by exactly one shard the day it lands. Nothing is
  hand-listed, so there is no list to forget to extend.
* Weights are ``battery_file_durations["integration_next"]`` in
  ``.github/ci-shard-timings.json`` (repo-relative file to seconds). A file with no timing
  weighs the median of the known ones, reported as a ``::warning::`` and a step-summary line
  through ``shard_select.report_mismatch`` and never silently. Recapture with
  ``python scripts/ci/capture_shard_timings.py --suite integration_next --from-junit <dir> --write``
  from the per-shard ``xunit-nightly-integration-next-shard-<N>.xml`` artefacts.
* The result depends only on the file set and the timings, never on enumeration order.

``tests/architectural/test_integration_next_shard_coverage.py`` proves, against the live
tree and the workflow text, that every file runs exactly once across the shards.

Standard library only at module scope (the workflow runs it with the runner's bare
``python3``); the sibling helper is imported once the repo root is on ``sys.path``.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from scripts.ci.shard_select import BatteryPartition

__all__ = [
    "EXIT_NO_TESTS",
    "EXIT_USAGE",
    "JOB_KEY_PREFIX",
    "ROOTS",
    "SHARD_COUNT",
    "SHARD_JOB_KEYS",
    "SUITE",
    "TIMINGS_PATH",
    "load_file_durations",
    "plan_shards",
    "shard_files",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
#: The two roots the retired single ``integration-next`` job ran, by directory (not ``-m integration``:
#: tests/next carries no such marker, and a marker lane would silently drop its files; #4729).
ROOTS: Final = ("tests/integration", "tests/next")
#: ``battery_file_durations[SUITE]`` in the committed timings artefact.
SUITE: Final = "integration_next"
#: Every nightly shard job key is ``<JOB_KEY_PREFIX><N>``.
JOB_KEY_PREFIX: Final = "integration-next-shard-"
#: How many ``integration-next-shard-<N>`` jobs ``ci-nightly.yml`` must define; every job passes ``--shard <N>/SHARD_COUNT``.
SHARD_COUNT: Final = 4
#: The job keys that must exist, in order.
SHARD_JOB_KEYS: Final = tuple(f"{JOB_KEY_PREFIX}{number}" for number in range(1, SHARD_COUNT + 1))
TIMINGS_PATH: Final = REPO_ROOT / ".github" / "ci-shard-timings.json"
EXIT_NO_TESTS: Final = 64
EXIT_USAGE: Final = 2
_LOG_PREFIX: Final = "integration-next-shard"
_DURATIONS_TABLE: Final = "battery_file_durations"


def _ensure_repo_root_on_path() -> None:
    """Put the repo root on ``sys.path`` (a bare ``python3 scripts/ci/x.py`` has only ``scripts/ci`` there)."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


def load_file_durations(timings_path: Path = TIMINGS_PATH) -> dict[str, float]:
    """``battery_file_durations[SUITE]`` as ``{path: seconds}``; a missing file, table or suite is ``{}``."""
    if not timings_path.is_file():
        return {}
    payload = json.loads(timings_path.read_text(encoding="utf-8"))
    table = payload.get(_DURATIONS_TABLE) if isinstance(payload, dict) else None
    suite = table.get(SUITE) if isinstance(table, dict) else None
    if not isinstance(suite, dict):
        return {}
    return {str(path): float(seconds) for path, seconds in suite.items()}


def plan_shards(files: Sequence[str], durations: Mapping[str, float], shard_count: int) -> BatteryPartition:
    """LPT-partition *files* into *shard_count* shards keyed ``1/n`` ... ``n/n`` (pure, order-independent)."""
    _ensure_repo_root_on_path()
    from scripts.ci.shard_select import battery_parts

    partition = battery_parts(files, (), shard_count, durations)
    # `battery_parts` always carries a (here empty) `fast` roster part; this lane has none.
    return dataclasses.replace(partition, parts={key: owned for key, owned in partition.parts.items() if key in partition.loads})


def shard_files(shard: str, *, root: Path = REPO_ROOT, timings_path: Path = TIMINGS_PATH) -> tuple[tuple[str, ...], BatteryPartition]:
    """The sorted files shard ``i/n`` owns, plus the whole partition (for reporting)."""
    _ensure_repo_root_on_path()
    from scripts.ci.shard_select import enumerate_base_files, parse_shard

    index, total = parse_shard(shard)
    files = enumerate_base_files(ROOTS, root=root)
    partition = plan_shards(files, load_file_durations(timings_path), total)
    return tuple(sorted(partition.parts[f"{index}/{total}"])), partition


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--shard", required=True, help="i/n, 1-based: the shard whose test files to select")
    parser.add_argument("--out", type=Path, required=True, help="write one repo-relative test file per line here (a pytest @argsfile)")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root to enumerate (default: this checkout)")
    parser.add_argument("--timings", type=Path, default=TIMINGS_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; returns the process exit status (``EXIT_NO_TESTS`` for an empty shard, fail-closed)."""
    args = _build_parser().parse_args(argv)
    _ensure_repo_root_on_path()
    from scripts.ci.shard_select import report_mismatch

    try:
        files, partition = shard_files(args.shard, root=args.root, timings_path=args.timings)
    except ValueError as exc:
        print(f"::error::{_LOG_PREFIX}: {exc}")
        return EXIT_USAGE
    report_mismatch(partition.resolution, label="integration-next")
    if not files:
        print(f"::error::{_LOG_PREFIX}: shard {args.shard} owns no test file under {', '.join(ROOTS)}; an empty shard is a lost signal, not a skip")
        return EXIT_NO_TESTS
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(files) + "\n", encoding="utf-8")
    total_files = sum(len(owned) for owned in partition.parts.values())
    print(f"{_LOG_PREFIX}: shard {args.shard} owns {len(files)} of {total_files} files, predicted load {partition.loads[args.shard]:.0f}s -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
