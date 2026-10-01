"""Red-first pins for the blocking home of the orphaned corpus tests (WP10, D-13/D-22).

Packs owns the ``-m corpus`` suite as ADVISORY (FR-009). That left 40 corpus-marked
node-ids with no other blocking per-PR home: the whole of
``tests/contract/test_example_round_trip.py`` and
``tests/integration/test_mission_review_contract_gate.py`` (both trees are outside
the module matrix) plus the single ``performance``-marked class
``tests/doctrine/test_shipped_profiles.py::TestShippedProfilesPerformance`` (the other
363 corpus tests of that file are already run by the ``charter`` module row).

D-22 gives them one required router job, ``tests (corpus-blocking)``, gated only on the
router ``corpus`` group, and Packs' advisory corpus run deselects exactly those
selections so nothing executes twice. This module pins that from REAL collection
(``gc.collect_job_nodeids``, the established authority) -- never a hand count:

* the 40 are selected by exactly one required router job, and by it alone;
* no advisory job (the Packs corpus run) selects any of them;
* no module-matrix row selects any of them;
* ``corpus`` is a gated filter group again (WP09's transitional exemption is gone);
* the job's ``if:`` is evaluated semantically, not by substring.
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
from tests.architectural import test_workflow_coherence
from tests.ci.test_ci_module_wiring import _BASE_CONTEXT_ALL_FALSE, _eval_gh_if

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS = _REPO_ROOT / ".github" / "workflows"

_JOB = "tests-corpus-blocking"
_PERFORMANCE_CLASS = "tests/doctrine/test_shipped_profiles.py::TestShippedProfilesPerformance"
_BLOCKING_SELECTION: tuple[str, ...] = (
    "tests/contract/test_example_round_trip.py",
    "tests/integration/test_mission_review_contract_gate.py",
    _PERFORMANCE_CLASS,
)
_MARKER = "corpus and not windows_ci"
_EXPECTED_COUNT = 40
_PACKS_CORPUS_JOB = "built-in-corpus-suite"
_MODULE_MARKER_RE = re.compile(r'-m\s+"(?P<expr>[^"]+)"')


def _selection_probe(marker_expr: str | None) -> gc.Gate:
    """A probe gate over the three blocking selections under *marker_expr*."""
    return gc.Gate(workflow="probe", job="probe", shard=None, paths=list(_BLOCKING_SELECTION), marker_expr=marker_expr)


@pytest.fixture(scope="module")
def expected_nodeids() -> frozenset[str]:
    """The REAL collected node-ids of the blocking selection under the corpus marker."""
    nodeids = frozenset(gc.collect_job_nodeids(_selection_probe(_MARKER)))
    assert len(nodeids) == _EXPECTED_COUNT, (
        f"the corpus-blocking selection collects {len(nodeids)} node-ids, expected {_EXPECTED_COUNT}: "
        "a corpus test was added to or removed from one of the three selections -- update _EXPECTED_COUNT consciously"
    )
    return nodeids


_collected_by_marker: dict[str | None, frozenset[str]] = {}


def _collected_under(marker_expr: str | None) -> frozenset[str]:
    """Real node-ids of the three selections under *marker_expr* (cached per marker)."""
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

    assert set(selecting) == {_JOB}, f"the 40 must be selected by exactly one router job, got {sorted(selecting)}"
    assert selecting[_JOB] == expected_nodeids, "the corpus-blocking job must select ALL 40 node-ids"
    assert _JOB in _router_jobs()["router-gate"]["needs"], "the corpus-blocking job must be in router-gate.needs (that is what makes it blocking)"


def test_the_blocking_job_runs_the_corpus_marker_over_exactly_the_three_selections() -> None:
    gate = _gate_of("ci-router.yml", _JOB)

    assert gate.marker_expr == _MARKER
    assert sorted(gate.paths) == sorted(_BLOCKING_SELECTION)
    assert not gate.ignores, "the blocking job deselects nothing: it must run all 40"


# ---------------------------------------------------------------------------
# no advisory job selects the orphans (no double execution)
# ---------------------------------------------------------------------------
def test_no_advisory_job_selects_the_orphans(expected_nodeids: frozenset[str]) -> None:
    corpus_gate = _gate_of("packs.yml", _PACKS_CORPUS_JOB)
    probe = gc.Gate(
        workflow="probe",
        job="probe",
        shard=None,
        paths=list(_BLOCKING_SELECTION),
        ignores=list(corpus_gate.ignores),
        marker_expr=corpus_gate.marker_expr,
    )

    leaked = _gate_selection(probe, expected_nodeids)
    assert not leaked, f"Packs' advisory corpus run still selects {len(leaked)} blocking node-ids (double execution): {sorted(leaked)}"
    assert corpus_gate.marker_expr == _MARKER, "Packs must keep running the corpus marker (advisory lane otherwise unchanged)"
    assert _selecting_jobs("packs.yml", expected_nodeids) == {}, "no Packs job may select a blocking node-id"


def test_packs_deselects_each_of_the_three_selections_individually(expected_nodeids: frozenset[str]) -> None:
    """Dropping any ONE deselect leaks exactly that selection's node-ids back into Packs."""
    corpus_gate = _gate_of("packs.yml", _PACKS_CORPUS_JOB)
    for dropped in _BLOCKING_SELECTION:
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

    all_false = {**_BASE_CONTEXT_ALL_FALSE, "changes.corpus": False}
    assert _eval_gh_if(job["if"], {**all_false, "changes.corpus": True}) is True
    assert _eval_gh_if(job["if"], all_false) is False
    for group in ("docs", "architectural", "ci_config", "cli"):
        other = {**all_false, f"changes.{group}": True}
        assert _eval_gh_if(job["if"], other) is False, f"{group} alone must not select the corpus-blocking job"
