"""What ``charter activate``/``deactivate`` cost at a repository's scale, as a ratio (#6506).

The fixture-scale unit tests cannot see this: on a project carrying *this repository's own*
governed charter (165 KB, 1,937 lines, 264 catalog references) the commands used to take 16-18 s,
against a charter budget of ``< 2 s`` for "typical projects" (``.kittify/charter/charter.md``,
"Performance and Scale"). After #6506 they take about 10 s, and a **pure read** of the same
project still takes about 2.7 s — so the absolute budget is unreachable here for any command
that reads the charter at all, and an absolute number is the wrong thing to assert anyway
(ADR ``docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md``: a bare ``--help``
moved 1.14 s -> 1.95 s between nightly runs with no product change).

What this asserts instead, following that ADR:

* the command's median over a **read floor measured interleaved in the same run**, so drift in
  machine speed moves numerator and denominator together;
* the limit lives in :mod:`tests._perf_helpers`, the one authority
  (``tests/architectural/test_perf_limit_authority.py`` enforces it);
* no number of seconds appears here.

The floor is deliberately a *read* (``charter list``) and not the interpreter start-up floor the
owned-checkout tests use: the cost under guard lives in the write path, and the interpreter floor
would say nothing about it. The ratio therefore means "a command that recompiles and rewrites the
governed charter, over a command that only reads the same project".

**This is a runaway guard, not the regression gate.** The command costs 4-6x its own read floor,
so its own variance dominates the ratio instead of cancelling against the floor, and no limit can
separate the pre-fix 16.7 s from the post-fix 10.4 s reliably on a shared runner (measured ratio
ranges overlap across series taken under different load). The exact gate for this class is
structural and runs on every pull request:
``tests/charter/activation/test_charter_write_roundtrips.py`` counts whole-document round trips
(6 now, 18 for the two-cycle shape this replaced). This file catches what a count cannot — a
change that makes the command pathologically slow at scale without adding a round trip — and it
records the floor and command medians in its failure message so the nightly report is readable
without a re-run. The precise before/after medians are recorded in the ADR.

Runs in the nightly ``performance`` job (``-m performance``), never on the pull-request path.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests._perf_helpers import (
    CHARTER_WRITE_RATIO_LIMIT,
    Measurement,
    Sample,
    assert_timing_budget,
    measure_group,
)

pytestmark = [pytest.mark.timing, pytest.mark.performance]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROJECT_SOURCE = _REPO_ROOT / ".kittify"
_PACKS_SOURCE = _REPO_ROOT / "packs"

#: The tactic this repository's own charter activates by default, so both commands change
#: something on every run and the measurement is not a no-op.
_TARGET = ["tactic", "analysis-extract-before-interpret"]

#: Rounds of (floor, activate, deactivate) per measurement. Three is enough for a median over a
#: ratio whose clean spread is wide, and keeps the file to about two minutes: at this fixture's
#: scale one round is roughly 2.7 s of read floor plus 10 s per command.
_ROUNDS = 3


def _template(tmp_path: Path) -> Path:
    """One copy of the repository-scale project, reused as the per-round source."""
    if not (_PROJECT_SOURCE / "charter" / "charter.yaml").is_file():  # pragma: no cover - sdist install
        pytest.skip(f"no project charter under {_PROJECT_SOURCE}")
    template = tmp_path / "template"
    shutil.copytree(_PROJECT_SOURCE, template / ".kittify")
    if _PACKS_SOURCE.is_dir():
        shutil.copytree(_PACKS_SOURCE, template / "packs")
    subprocess.run(["git", "init", "--quiet", str(template)], check=True, capture_output=True)
    return template


def _spawn(tmp_path: Path, template: Path, argv: list[str], label: str) -> Sample:
    """Run one fresh copy of the project, so no sample is warmed by the one before it."""
    project = tmp_path / f"run-{label}"
    shutil.rmtree(project, ignore_errors=True)
    shutil.copytree(template, project)
    command = [sys.executable, "-m", "specify_cli", *argv, "--repo-root", str(project)]
    start = time.perf_counter()
    completed = subprocess.run(command, capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    shutil.rmtree(project, ignore_errors=True)
    if completed.returncode != 0:
        return Sample(elapsed, ok=False, detail=f"{label} exit {completed.returncode}: {completed.stderr[-400:]}")
    return Sample(elapsed)


def _measure(tmp_path: Path) -> Measurement:
    template = _template(tmp_path)
    floor = lambda: _spawn(tmp_path, template, ["charter", "list"], "floor")  # noqa: E731
    variants = {
        "activate": lambda: _spawn(tmp_path, template, ["charter", "activate", *_TARGET], "activate"),
        "deactivate": lambda: _spawn(tmp_path, template, ["charter", "deactivate", *_TARGET], "deactivate"),
    }
    return measure_group(floor, variants, runs=_ROUNDS)


def test_activate_and_deactivate_stay_within_the_write_ratio(tmp_path: Path) -> None:
    measurement = _measure(tmp_path)
    for label in ("activate", "deactivate"):
        assert_timing_budget(
            measurement.ratio(label),
            CHARTER_WRITE_RATIO_LIMIT,
            name=measurement.describe(
                label,
                CHARTER_WRITE_RATIO_LIMIT,
                title=f"charter {label} over the charter list read floor at repository scale",
            ),
        )
