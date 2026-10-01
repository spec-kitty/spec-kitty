"""Live per-change test-set uniqueness over the real CI workflows (FR-010 / NFR-004 / SC-004).

Mission ``ci-runtime-stabilisation-01M3TZH6`` WP15. One extension of the existing
selection engine (:class:`_gate_coverage.CompiledGate`, D-044) -- no second authority:

* **One real universe.** The caller supplies a single ``collect_universe()`` result; every
  job's selection is the model evaluated over it (pytest's own marker ``Expression``
  through ``CompiledGate``), never one real collection per job (D-14 cost).
* **Dynamic jobs are expanded, not read as the whole tree.** ``ci-modules.yml::test`` is a
  reusable-workflow caller with no paths of its own, so its gate reads as "the whole tree"
  (R2 F10); it is expanded into one job per registry row, resolved by the SAME
  ``scripts/ci/shard_select`` resolver the shard runs and filtered by the SAME consumer
  marker constant. The architectural battery keeps one job per ``--battery-part`` leg
  (``CompiledGate`` already evaluates a partitioned gate through the shared selector, D-24).
* **Tiers are the OS family only** (:func:`_gate_coverage.gate_os_tier`, D-14): module rows
  run on Python 3.11 and the router / Packs jobs on 3.12, so an interpreter-keyed tier would
  put exactly the router-vs-module duplicates in different tiers and hide them.
* **One per-change classifier** (C-010): :func:`change_triggered` and
  :func:`enumerate_workflows` are imported from ``test_no_duplicate_suite_execution``, where
  they live; the ledger test never imports this module (no cycle).

``python -m tests.architectural._live_uniqueness --workflows-dir DIR --summary`` prints every
same-tier overlap (``pair -> count``) with NO allowlist and exits 1 when any exists: it is the
red-first evidence tool (point it at an archived pre-Mission ``.github/workflows``).
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import yaml

from scripts.ci.shard_select import MODULE_SELECTION_MARKER_EXPR, resolve_module_test_dirs
from tests.architectural import _gate_coverage as gc
from tests.architectural.test_no_duplicate_suite_execution import change_triggered, enumerate_workflows

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

__all__ = [
    "BATTERY_FAMILY",
    "MODULE_MATRIX_JOB",
    "Overlaps",
    "REGISTRY_FILE_NAME",
    "JobKey",
    "LiveJob",
    "OverlapAllowance",
    "expand_gate",
    "group_jobs",
    "label_of",
    "main",
    "module_rows",
    "pairwise_overlaps",
    "per_change_jobs",
    "selected_by_job",
    "stale_allowances",
    "uncovered_overlaps",
]

# ``(workflow, job, row-or-leg)``: the row is a registry module name for ``ci-modules.yml::test``
# and the matrix leg / ``--battery-part`` for a sharded job; ``None`` for a plain job.
JobKey = tuple[str, str, str | None]
Overlaps = dict[tuple[JobKey, JobKey], frozenset[str]]

BATTERY_FAMILY: Final = "battery"
REGISTRY_FILE_NAME: Final = "ci-module-registry.yml"
# The reusable-workflow caller whose whole-tree gate is replaced by one job per registry row.
MODULE_MATRIX_JOB: Final = ("ci-modules.yml", "test")


@dataclass(frozen=True)
class LiveJob:
    """One per-change CI job (or one expanded row / leg of it) and what it selects."""

    key: JobKey
    tier: str  # OS family: "linux" | "windows" | "macos"
    family: str  # BATTERY_FAMILY for the partitioned battery, else the job label
    gates: tuple[gc.Gate, ...]

    @property
    def label(self) -> str:
        return label_of(self.key)


@dataclass(frozen=True)
class OverlapAllowance:
    """A reviewed, scoped exemption for one (job, other-job-or-family) overlap.

    ``scope_marker`` XOR ``scope_files`` bounds which overlapping nodes are covered; a
    per-node entry is rejected by construction (pair x scope keeps the cap meaningful).
    """

    job_a: str  # a job label, e.g. "packs.yml::built-in-corpus-suite"
    job_b_family: str  # a job label or family, e.g. "ci-modules.yml::test[charter]", "battery"
    scope_marker: str | None
    scope_files: frozenset[str]
    reason: str
    issue: str


def label_of(key: JobKey) -> str:
    workflow, job, leg = key
    return f"{workflow}::{job}" + (f"[{leg}]" if leg else "")


def _sort_key(key: JobKey) -> tuple[str, str, str]:
    return (key[0], key[1], key[2] or "")


# ---------------------------------------------------------------------------
# Job enumeration + expansion
# ---------------------------------------------------------------------------


def module_rows(registry_path: Path) -> list[tuple[str, str]]:
    """``(module, test_dirs JSON)`` for every registry row, in registry order."""
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    rows: list[tuple[str, str]] = []
    for row in data["modules"]:
        rows.append((str(row["module"]), json.dumps(row.get("test_dirs") or [])))
    return rows


def _module_row_gates(gate: gc.Gate, rows: Sequence[tuple[str, str]]) -> list[gc.Gate]:
    expanded: list[gc.Gate] = []
    # The shared resolver tests ``os.path.isdir`` relative to the working directory.
    with contextlib.chdir(gc.REPO_ROOT):
        for module, test_dirs_json in rows:
            dirs = resolve_module_test_dirs(module, test_dirs_json)
            if not dirs:
                raise ValueError(f"registry row {module!r} resolves to no test directory; refusing to drop it from the uniqueness check")
            expanded.append(
                dataclasses.replace(gate, paths=dirs, ignores=[], marker_expr=MODULE_SELECTION_MARKER_EXPR, shard=module),
            )
    return expanded


def expand_gate(gate: gc.Gate, rows: Sequence[tuple[str, str]]) -> list[gc.Gate]:
    """The gates one parsed gate stands for: one per registry row for the module matrix, else itself."""
    if (gate.workflow, gate.job) == MODULE_MATRIX_JOB:
        return _module_row_gates(gate, rows)
    return [gate]


def _gate_key(gate: gc.Gate) -> JobKey:
    return (gate.workflow, gate.job, gate.shard or gate.partition)


def _tier_of(key: JobKey, gates: Sequence[gc.Gate]) -> str:
    tiers = {gc.gate_os_tier(gate) for gate in gates}
    resolved = {tier for tier in tiers if tier is not None}
    if None in tiers or len(resolved) != 1:
        raise ValueError(
            f"per-change suite job {label_of(key)} has no single OS-family tier (runs-on "
            f"{sorted({str(gate.runs_on) for gate in gates})}); refusing to leave it out of the uniqueness relation",
        )
    return next(iter(resolved))


def group_jobs(gates: Iterable[gc.Gate], rows: Sequence[tuple[str, str]]) -> list[LiveJob]:
    """Group gates into jobs (module matrix expanded), each carrying its OS-family tier."""
    grouped: dict[JobKey, list[gc.Gate]] = defaultdict(list)
    for gate in gates:
        for expanded in expand_gate(gate, rows):
            grouped[_gate_key(expanded)].append(expanded)
    jobs: list[LiveJob] = []
    for key in sorted(grouped, key=_sort_key):
        members = grouped[key]
        family = BATTERY_FAMILY if any(gate.partition for gate in members) else label_of(key)
        jobs.append(LiveJob(key, _tier_of(key, members), family, tuple(members)))
    return jobs


def per_change_jobs(workflows_dir: Path = gc.WORKFLOWS_DIR, registry_path: Path | None = None) -> list[LiveJob]:
    """Every per-change suite job of *workflows_dir*, module rows and battery legs expanded."""
    registry = registry_path if registry_path is not None else workflows_dir.parent / REGISTRY_FILE_NAME
    rows = module_rows(registry)
    gates: list[gc.Gate] = []
    for path in enumerate_workflows(workflows_dir):
        if change_triggered(path):
            gates.extend(gc.parse_workflow(path))
    return group_jobs(gates, rows)


# ---------------------------------------------------------------------------
# Selection and overlap
# ---------------------------------------------------------------------------


def selected_by_job(jobs: Sequence[LiveJob], universe: Sequence[gc.TestRecord]) -> dict[JobKey, frozenset[str]]:
    """Node-ids each job selects: one ``CompiledGate`` evaluation per job over the one universe."""
    return {job.key: gc._selected_nodeids(job.gates, universe) for job in jobs}


def pairwise_overlaps(jobs: Sequence[LiveJob], selected: Mapping[JobKey, frozenset[str]]) -> Overlaps:
    """Same-tier job pairs sharing at least one node (battery-internal pairs included)."""
    tier = {job.key: job.tier for job in jobs}
    owners: dict[str, list[JobKey]] = defaultdict(list)
    for job in jobs:
        for nodeid in selected[job.key]:
            owners[nodeid].append(job.key)
    found: dict[tuple[JobKey, JobKey], set[str]] = defaultdict(set)
    for nodeid, keys in owners.items():
        ordered = sorted(keys, key=_sort_key)
        for index, first in enumerate(ordered):
            for second in ordered[index + 1 :]:
                if tier[first] == tier[second]:
                    found[(first, second)].add(nodeid)
    return {pair: frozenset(nodes) for pair, nodes in found.items()}


def _side_matches(name: str, job: LiveJob) -> bool:
    return name in {job.label, job.family}


def _in_scope(allowance: OverlapAllowance, record: gc.TestRecord) -> bool:
    if allowance.scope_marker is not None and allowance.scope_marker in record["markers"]:
        return True
    return record["relpath"] in allowance.scope_files


def _covering_index(
    allowlist: Sequence[OverlapAllowance],
    pair: tuple[LiveJob, LiveJob],
    record: gc.TestRecord,
) -> int | None:
    first, second = pair
    for index, allowance in enumerate(allowlist):
        a_first = allowance.job_a == first.label and _side_matches(allowance.job_b_family, second)
        a_second = allowance.job_a == second.label and _side_matches(allowance.job_b_family, first)
        if (a_first or a_second) and _in_scope(allowance, record):
            return index
    return None


def _classify(
    overlaps: Overlaps,
    allowlist: Sequence[OverlapAllowance],
    jobs: Sequence[LiveJob],
    records: Mapping[str, gc.TestRecord],
) -> tuple[Overlaps, set[int]]:
    """Split overlaps into the uncovered remainder; also return which allowlist indices fired."""
    by_key = {job.key: job for job in jobs}
    uncovered: dict[tuple[JobKey, JobKey], set[str]] = {}
    used: set[int] = set()
    for (first, second), nodes in overlaps.items():
        pair = (by_key[first], by_key[second])
        for nodeid in nodes:
            index = _covering_index(allowlist, pair, records[nodeid])
            if index is None:
                uncovered.setdefault((first, second), set()).add(nodeid)
            else:
                used.add(index)
    return {pair: frozenset(nodes) for pair, nodes in uncovered.items()}, used


def uncovered_overlaps(
    overlaps: Overlaps,
    allowlist: Sequence[OverlapAllowance],
    jobs: Sequence[LiveJob],
    records: Mapping[str, gc.TestRecord],
) -> Overlaps:
    """The overlapping nodes no allowance covers: the findings."""
    return _classify(overlaps, allowlist, jobs, records)[0]


def stale_allowances(
    overlaps: Overlaps,
    allowlist: Sequence[OverlapAllowance],
    jobs: Sequence[LiveJob],
    records: Mapping[str, gc.TestRecord],
) -> list[OverlapAllowance]:
    """Allowances that cover no live overlapping node (an entry must earn its place)."""
    used = _classify(overlaps, allowlist, jobs, records)[1]
    return [allowance for index, allowance in enumerate(allowlist) if index not in used]


# ---------------------------------------------------------------------------
# CLI (red-first evidence against an archived workflows directory)
# ---------------------------------------------------------------------------


def _summary_lines(overlaps: Overlaps, tier: Mapping[JobKey, str]) -> list[str]:
    ranked = sorted(overlaps.items(), key=lambda item: (-len(item[1]), _sort_key(item[0][0]), _sort_key(item[0][1])))
    return [f"{label_of(first)} x {label_of(second)} [{tier[first]}] -> {len(nodes)}" for (first, second), nodes in ranked]


def main(argv: Sequence[str] | None = None) -> int:
    """Print every same-tier overlap of ``--workflows-dir`` (no allowlist); exit 1 when any exists."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--workflows-dir", type=Path, default=gc.WORKFLOWS_DIR)
    parser.add_argument("--registry", type=Path, default=None, help="default: <workflows-dir>/../ci-module-registry.yml")
    parser.add_argument("--summary", action="store_true", help="print one 'pair -> count' line per overlapping pair")
    args = parser.parse_args(argv)
    jobs = per_change_jobs(args.workflows_dir, args.registry)
    universe = gc.collect_universe()
    overlaps = pairwise_overlaps(jobs, selected_by_job(jobs, universe))
    if args.summary:
        print(f"{len(jobs)} per-change jobs; {len(overlaps)} overlapping same-tier pairs")
        for line in _summary_lines(overlaps, {job.key: job.tier for job in jobs}):
            print(line)
    return 1 if overlaps else 0


if __name__ == "__main__":
    sys.exit(main())
