"""The blocking per-PR home of corpus tests (WP10, D-13/D-22; live since the #5510 arch fold).

Packs owns the ``-m corpus`` suite as ADVISORY (FR-009: job-level ``continue-on-error``).
A corpus test that no OTHER non-advisory per-PR job selects therefore has no blocking home:
its red never reaches the PR verdict. D-22 gives those orphans one required router job,
``tests (corpus-blocking)``, gated only on the router ``corpus`` group, and Packs' advisory
corpus run deselects exactly that job's selections so nothing executes twice. At the time of
writing the orphans are the whole of ``tests/contract/test_example_round_trip.py`` and
``tests/integration/test_mission_review_contract_gate.py`` (both outside the module matrix)
plus the ``performance``-marked class ``TestShippedProfilesPerformance`` (the module shard
marker deselects it from the ``charter`` row).

* **Live, never a snapshot** (:func:`test_every_corpus_test_has_a_blocking_per_pr_home`):
  the orphans are computed from one real collection -- corpus-marked tests minus those any
  non-advisory per-change job selects (:func:`_live_uniqueness.blocking_jobs`, the same
  per-change job model and ``CompiledGate`` selection the uniqueness gate uses) -- and must
  be exactly the corpus-blocking job's selection. A new corpus test anywhere only Packs
  reaches goes red here. Positive controls plant a synthetic orphan and prove the advisory
  exclusion is load-bearing.
* **Derived wiring pins** (fast, real ``--collect-only`` over the job's own selections):
  the job's selections are READ from ``ci-router.yml``, never restated; exactly one router job
  selects them, no Packs job does, Packs deselects each one individually, no module row runs
  them, ``corpus`` is a gated filter group, and the job's ``if:`` is evaluated semantically.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.coverage_guard_lib import registry_rows, resolve_test_dirs
from scripts.ci.gate_selection import load_router
from tests.architectural import _gate_coverage as gc
from tests.architectural import _live_uniqueness as lu
from tests.architectural import test_workflow_coherence
from tests.ci._gh_if import BASE_CONTEXT_ALL_FALSE, eval_gh_if

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS = _REPO_ROOT / ".github" / "workflows"

_ROUTER = "ci-router.yml"
_JOB = "tests-corpus-blocking"
_JOB_KEY: lu.JobKey = (_ROUTER, _JOB, None)
_CORPUS_MARKER = "corpus"
_PERFORMANCE_CLASS = "tests/doctrine/test_shipped_profiles.py::TestShippedProfilesPerformance"
_MARKER = "corpus and not windows_ci"
_PACKS_CORPUS_JOB = "built-in-corpus-suite"
_PACKS_CORPUS_KEY: lu.JobKey = ("packs.yml", _PACKS_CORPUS_JOB, None)
_MODULE_MARKER_RE = re.compile(r'-m\s+"(?P<expr>[^"]+)"')
_FINDINGS_SHOWN = 10


def _blocking_selection() -> tuple[str, ...]:
    """The corpus-blocking job's positional selections, READ from ``ci-router.yml`` (never restated)."""
    return tuple(_gate_of(_ROUTER, _JOB).paths)


def _selection_probe(marker_expr: str | None) -> gc.Gate:
    """A probe gate over the blocking job's selections under *marker_expr*."""
    return gc.Gate(workflow="probe", job="probe", shard=None, paths=list(_blocking_selection()), marker_expr=marker_expr)


@pytest.fixture(scope="module")
def expected_nodeids() -> frozenset[str]:
    """The REAL collected node-ids of the blocking selection under the corpus marker."""
    nodeids = frozenset(gc.collect_job_nodeids(_selection_probe(_MARKER)))
    assert nodeids, "non-vacuity: the corpus-blocking job's selections must collect corpus tests"
    return nodeids


_collected_by_marker: dict[str | None, frozenset[str]] = {}


def _collected_under(marker_expr: str | None) -> frozenset[str]:
    """Real node-ids of the blocking job's selections under *marker_expr* (cached per marker)."""
    if marker_expr not in _collected_by_marker:
        _collected_by_marker[marker_expr] = frozenset(gc.collect_job_nodeids(_selection_probe(marker_expr)))
    return _collected_by_marker[marker_expr]


def _entry_selects(gate: gc.Gate, nodeid: str) -> bool:
    """Do the gate's positional paths select *nodeid* and none of its ignores exclude it?"""
    relpath = nodeid.split("::", 1)[0]
    in_paths = not gate.paths or any(gc.path_matches(relpath, nodeid, entry) for entry in gate.paths)
    ignored = any(gc.path_matches(relpath, nodeid, entry) for entry in gate.ignores)
    return in_paths and not ignored


def _gate_selection(gate: gc.Gate, expected: frozenset[str]) -> frozenset[str]:
    """The expected node-ids *gate* really selects: its paths/ignores/marker over real collection."""
    candidates = frozenset(nodeid for nodeid in expected if _entry_selects(gate, nodeid))
    if not candidates:
        return frozenset()
    return candidates & _collected_under(gate.marker_expr)


def _selecting_jobs(workflow: str, expected: frozenset[str]) -> dict[str, frozenset[str]]:
    """``{job: selected-orphans}`` for every job of *workflow* that selects at least one orphan."""
    selecting: dict[str, frozenset[str]] = {}
    for gate in gc.parse_workflow(_WORKFLOWS / workflow):
        selected = _gate_selection(gate, expected)
        if selected:
            selecting[gate.job] = selecting.get(gate.job, frozenset()) | selected
    return selecting


def _gate_of(workflow: str, job: str) -> gc.Gate:
    gates = [gate for gate in gc.parse_workflow(_WORKFLOWS / workflow) if gate.job == job]
    assert len(gates) == 1, f"{workflow}::{job} must run exactly one pytest invocation, found {len(gates)}"
    return gates[0]


def _router_jobs() -> dict[str, Any]:
    workflow = yaml.safe_load((_WORKFLOWS / "ci-router.yml").read_text(encoding="utf-8"))
    return dict(workflow["jobs"])


# ---------------------------------------------------------------------------
# exactly one required job selects the orphans
# ---------------------------------------------------------------------------
def test_exactly_one_required_router_job_selects_the_orphans(expected_nodeids: frozenset[str]) -> None:
    selecting = _selecting_jobs("ci-router.yml", expected_nodeids)

    assert set(selecting) == {_JOB}, f"the orphans must be selected by exactly one router job, got {sorted(selecting)}"
    assert selecting[_JOB] == expected_nodeids, "the corpus-blocking job must select ALL of its corpus node-ids"
    assert _JOB in _router_jobs()["router-gate"]["needs"], "the corpus-blocking job must be in router-gate.needs (that is what makes it blocking)"


def test_the_blocking_job_runs_the_corpus_marker_over_explicit_selections() -> None:
    gate = _gate_of(_ROUTER, _JOB)

    assert gate.marker_expr == _MARKER
    assert gate.paths, "the blocking job must name its selections (an empty path list would run the whole tree)"
    assert not gate.ignores, "the blocking job deselects nothing: it must run every orphan it names"


# ---------------------------------------------------------------------------
# no advisory job selects the orphans (no double execution)
# ---------------------------------------------------------------------------
def test_no_advisory_job_selects_the_orphans(expected_nodeids: frozenset[str]) -> None:
    corpus_gate = _gate_of("packs.yml", _PACKS_CORPUS_JOB)
    probe = gc.Gate(
        workflow="probe",
        job="probe",
        shard=None,
        paths=list(_blocking_selection()),
        ignores=list(corpus_gate.ignores),
        marker_expr=corpus_gate.marker_expr,
    )

    leaked = _gate_selection(probe, expected_nodeids)
    assert not leaked, f"Packs' advisory corpus run still selects {len(leaked)} blocking node-ids (double execution): {sorted(leaked)}"
    assert corpus_gate.marker_expr == _MARKER, "Packs must keep running the corpus marker (advisory lane otherwise unchanged)"
    assert _selecting_jobs("packs.yml", expected_nodeids) == {}, "no Packs job may select a blocking node-id"


def test_packs_deselects_each_blocking_selection_individually(expected_nodeids: frozenset[str]) -> None:
    """Dropping any ONE deselect leaks exactly that selection's node-ids back into Packs."""
    corpus_gate = _gate_of("packs.yml", _PACKS_CORPUS_JOB)
    for dropped in _blocking_selection():
        remaining = [entry for entry in corpus_gate.ignores if entry != dropped]
        assert len(remaining) == len(corpus_gate.ignores) - 1, f"Packs must deselect {dropped!r} exactly once"
        probe = gc.Gate(workflow="probe", job="probe", shard=None, paths=[dropped], ignores=remaining, marker_expr=_MARKER)
        assert _gate_selection(probe, expected_nodeids), f"deselecting {dropped!r} must be what removes it from Packs"


# ---------------------------------------------------------------------------
# no module-matrix row selects the orphans
# ---------------------------------------------------------------------------
def _module_marker() -> str:
    """The marker ``module-tests.yml`` applies to every module shard (read, never restated)."""
    text = (_WORKFLOWS / "module-tests.yml").read_text(encoding="utf-8")
    match = _MODULE_MARKER_RE.search(text[text.index("-m pytest") :] if "-m pytest" in text else text)
    assert match, "module-tests.yml no longer carries a literal -m marker -- re-derive this pin"
    return match.group("expr")


def test_no_module_row_selects_the_orphans(expected_nodeids: frozenset[str]) -> None:
    owned_dirs = [str(test_dir.relative_to(_REPO_ROOT)).replace("\\", "/") for row in registry_rows() for test_dir in resolve_test_dirs(row)]
    module_rows_see = frozenset(nodeid for nodeid in expected_nodeids if any(gc.path_matches(nodeid.split("::", 1)[0], nodeid, entry) for entry in owned_dirs))

    # Only the performance class sits under a module-owned tree (tests/doctrine -> `charter`).
    assert module_rows_see == {nodeid for nodeid in expected_nodeids if nodeid.startswith(_PERFORMANCE_CLASS)}
    assert module_rows_see, "non-vacuity: the performance class must be inside the charter row's tree"
    # ...and the module shard marker deselects it, so no module shard executes it.
    marker = _module_marker()
    assert module_rows_see.isdisjoint(_collected_under(marker)), f"module marker {marker!r} must deselect the performance class"
    assert module_rows_see <= frozenset(gc.collect_job_nodeids(_selection_probe("performance"))), "the class must carry `performance`"


# ---------------------------------------------------------------------------
# corpus is a gated group again
# ---------------------------------------------------------------------------
def test_corpus_group_is_gated_again() -> None:
    assert "corpus" not in test_workflow_coherence._DELIBERATELY_UNGATED_FILTER_GROUPS, "WP09's TRANSITIONAL ungated entry must be removed"
    assert load_router().job_gates[_JOB] == frozenset({"corpus"}), "the blocking job is gated on the corpus group, and only on it"


def test_the_blocking_job_if_is_evaluated_semantically() -> None:
    job = _router_jobs()[_JOB]
    assert job["needs"] == ["changes"]

    all_false = {**BASE_CONTEXT_ALL_FALSE, "changes.corpus": False}
    assert eval_gh_if(job["if"], {**all_false, "changes.corpus": True}) is True
    assert eval_gh_if(job["if"], all_false) is False
    for group in ("docs", "architectural", "ci_config", "cli"):
        other = {**all_false, f"changes.{group}": True}
        assert eval_gh_if(job["if"], other) is False, f"{group} alone must not select the corpus-blocking job"


# ---------------------------------------------------------------------------
# live: every corpus test has a blocking per-PR home
# ---------------------------------------------------------------------------
def _blocking_home_gaps(jobs: list[lu.LiveJob], universe: list[gc.TestRecord]) -> tuple[frozenset[str], frozenset[str]]:
    """``(unhomed, double_homed)`` corpus node-ids over *universe*.

    *unhomed*: corpus tests no non-advisory per-change job selects at all (the corpus-blocking
    job included) -- they run only in an advisory lane, or nowhere. *double_homed*: tests the
    corpus-blocking job selects although another non-advisory job already runs them.
    """
    blocking = lu.blocking_jobs(jobs)
    home = [job for job in blocking if job.key == _JOB_KEY]
    assert home, f"{lu.label_of(_JOB_KEY)} must be a non-advisory per-change job"
    orphans = lu.unhomed(_CORPUS_MARKER, [job for job in blocking if job.key != _JOB_KEY], universe)
    corpus = [record for record in universe if _CORPUS_MARKER in record["markers"]]
    homed_by_job = lu.selected_by_job(home, corpus)[_JOB_KEY]
    return orphans - homed_by_job, homed_by_job - orphans


@pytest.fixture(scope="module")
def live_jobs() -> list[lu.LiveJob]:
    return lu.per_change_jobs()


@pytest.fixture(scope="module")
def live_universe() -> list[gc.TestRecord]:
    return gc.collect_universe()


@pytest.mark.slow
def test_every_corpus_test_has_a_blocking_per_pr_home(live_jobs: list[lu.LiveJob], live_universe: list[gc.TestRecord]) -> None:
    """Live: corpus tests minus every non-advisory per-change selection == the corpus-blocking job's selection."""
    corpus = [record for record in live_universe if _CORPUS_MARKER in record["markers"]]
    assert corpus, "non-vacuity: the live universe must carry corpus-marked tests"
    unhomed, double_homed = _blocking_home_gaps(live_jobs, live_universe)

    assert not unhomed, (
        f"{len(unhomed)} corpus test(s) have no blocking per-PR home (only the advisory Packs lane, or nothing, runs them); "
        f"add their file to {lu.label_of(_JOB_KEY)} and deselect it from Packs: {sorted(unhomed)[:_FINDINGS_SHOWN]}"
    )
    assert not double_homed, (
        f"{lu.label_of(_JOB_KEY)} selects {len(double_homed)} corpus test(s) another blocking job already runs "
        f"(double execution): {sorted(double_homed)[:_FINDINGS_SHOWN]}"
    )


def _planted_record(relpath: str, *markers: str) -> gc.TestRecord:
    return {"nodeid": f"{relpath}::test_planted", "relpath": relpath, "markers": [_CORPUS_MARKER, *markers]}


_PLANTED_ORPHAN = _planted_record("tests/planted_corpus/test_orphan.py")


def test_positive_control_a_corpus_test_only_packs_reaches_is_reported(live_jobs: list[lu.LiveJob]) -> None:
    """A corpus test outside every blocking job (Packs, advisory, still selects it) goes red."""
    packs = [job for job in live_jobs if job.key == _PACKS_CORPUS_KEY]
    assert lu.selected_by_job(packs, [_PLANTED_ORPHAN])[_PACKS_CORPUS_KEY], "control premise: the advisory Packs run selects the plant"

    unhomed, double_homed = _blocking_home_gaps(live_jobs, [_PLANTED_ORPHAN])

    assert unhomed == {_PLANTED_ORPHAN["nodeid"]}
    assert not double_homed


def test_positive_control_the_advisory_exclusion_is_load_bearing(live_jobs: list[lu.LiveJob]) -> None:
    """Counting the advisory Packs job as a home (the old ``_gate_coverage`` view) would hide the plant."""
    assert lu.unhomed(_CORPUS_MARKER, live_jobs, [_PLANTED_ORPHAN]) == frozenset(), "every job, advisory included, homes it"
    assert lu.unhomed(_CORPUS_MARKER, lu.blocking_jobs(live_jobs), [_PLANTED_ORPHAN]) == {_PLANTED_ORPHAN["nodeid"]}
    assert _PACKS_CORPUS_KEY not in {job.key for job in lu.blocking_jobs(live_jobs)}, "Packs' corpus run is advisory"


def test_negative_control_a_corpus_test_in_a_blocking_selection_is_homed(live_jobs: list[lu.LiveJob]) -> None:
    """A new corpus test inside the job's selections is homed by it -- no frozen count to bump."""
    planted = _planted_record(next(entry for entry in _blocking_selection() if "::" not in entry))

    assert _blocking_home_gaps(live_jobs, [planted]) == (frozenset(), frozenset())
