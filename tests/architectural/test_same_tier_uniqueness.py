"""FR-010 / NFR-004 / SC-004 -- live per-change test-set uniqueness within an OS tier.

Mission ``ci-runtime-stabilisation-01M3TZH6`` WP15. Duplicate per-PR test selections must not
creep back: no node may be selected by two per-change CI jobs of the same OS-family tier
unless a reviewed, scoped allowance covers that exact overlap.

* **Live, not synthetic.** The relation is evaluated over the real workflows
  (``.github/workflows``) and one real ``--collect-only`` universe (D-14 cost: collected once
  per module, jobs filtered by the model through ``CompiledGate``, never one real collection
  per job). ``ci-modules.yml::test`` is expanded into one job per registry row and the
  architectural battery keeps one job per ``--battery-part`` leg
  (:mod:`tests.architectural._live_uniqueness`).
* **Tiers are the OS family only** (D-14, :func:`_gate_coverage.gate_os_tier`). Module rows run
  on Python 3.11 and the router / Packs jobs on 3.12; an interpreter-keyed tier would put exactly
  the router-vs-module duplicates in different tiers and hide them. Interpreter diversity is the
  nightly matrix's job (#5250).
* **Allowlist rules.** Pair x scope, never per node; every entry carries a reason and an issue,
  must match at least one live overlapping node (a stale entry fails), and
  ``len(ALLOWLIST) <= _ALLOWLIST_CEILING <= _ALLOWLIST_HARD_CAP``. The ceiling may only be
  lowered. Overlaps inside the architectural battery are the partition proof's business and are
  never allowlisted.
* **Positive controls.** A planted overlapping job is reported, the same overlap inside an
  allowlisted scope is not, the retired router duplicate shape (``tests-cli`` running
  ``pytest tests/cli``, as on the merge-base) is reported, and a stale allowance is reported.

The earlier premise of this file ("no workflow YAML left to parse", with the live half retired)
was stale: the router / modules / Packs / Windows workflows exist, and the job-name-prefix tiers
(``fast-tests`` / ``integration-tests``) it keyed on matched no live job, so the relation was
vacuous. The FR-010 red-first is recorded against the pre-Mission workflows with
``python -m tests.architectural._live_uniqueness --workflows-dir <archived .github/workflows>``.
"""

from __future__ import annotations

import collections
from pathlib import Path

import pytest

from scripts.ci.shard_select import MODULE_SELECTION_MARKER_EXPR
from tests.architectural import _gate_coverage as gc
from tests.architectural import _live_uniqueness as lu

pytestmark = [pytest.mark.architectural]

_LINUX = "ubuntu-24.04"
_WINDOWS = "windows-latest"
_BATTERY = lu.BATTERY_FAMILY
_NO_FILES: frozenset[str] = frozenset()
_FINDINGS_SHOWN = 10

# Ratchet constant: may only be lowered, never raised (shrink-only).
_ALLOWLIST_CEILING = 4
_ALLOWLIST_HARD_CAP = 10

_PACKS_CORPUS = "packs.yml::built-in-corpus-suite"

# Reviewed overlaps, each a (job, other job or family) pair bounded by a marker or file scope. The Packs lane fires on
# pack / kitty-specs / .kittify DATA diffs (#3008: a data-only PR used to skip every corpus reader), the module rows and
# the code-scoped battery on CODE diffs, so a PR touching both runs the overlapping readers twice. Folding the overlay
# concept into the same-tier relation itself is tracked in #3315.
ALLOWLIST: tuple[lu.OverlapAllowance, ...] = (
    lu.OverlapAllowance(
        job_a=_PACKS_CORPUS,
        job_b_family="ci-modules.yml::test[charter]",
        scope_marker="corpus",
        scope_files=_NO_FILES,
        reason=(
            "corpus-reader overlay: the Packs lane fires on pack / kitty-specs / .kittify data diffs and on unmatched src, the charter row on "
            "src/charter/**; re-judging the readers against changed data is the point (#3008), so a PR touching both runs them twice"
        ),
        issue="#3315",
    ),
    lu.OverlapAllowance(
        job_a=_PACKS_CORPUS,
        job_b_family="ci-modules.yml::test[glossary]",
        scope_marker="corpus",
        scope_files=_NO_FILES,
        reason="same overlay for the glossary gate-terms reader (tests/glossary/test_gate_terms.py): data-diff trigger on Packs, code-diff trigger on the row",
        issue="#3315",
    ),
    lu.OverlapAllowance(
        job_a=_PACKS_CORPUS,
        job_b_family=_BATTERY,
        scope_marker=None,
        scope_files=frozenset(
            {
                "tests/architectural/test_bare_prose_corpus_ratchet.py",
                "tests/architectural/test_transition_guard_shrink_only.py",
            },
        ),
        reason=(
            "corpus ratchets that must also run on data-only diffs (#3008): the battery is code-scoped, so removing them from it would drop "
            "them from every code PR (C-001) while removing them from Packs would blind data-only PRs"
        ),
        issue="#3315",
    ),
    lu.OverlapAllowance(
        job_a="packs.yml::built-in-pack-manifest",
        job_b_family=_BATTERY,
        scope_marker=None,
        scope_files=frozenset({"tests/architectural/test_pack_manifest_no_author_edit.py"}),
        reason=(
            "blocking pack-manifest guard on built-in data diffs (Packs); the battery copy covers code diffs (C-001). Four fast tests, "
            "so the duplicated runner-minutes are negligible next to splitting the guard's trigger"
        ),
        issue="#5510",
    ),
)

_PLANTED_WORKFLOW = "ci-planted.yml"
_PLANTED_JOB = "dup"
_PLANTED_LABEL = f"{_PLANTED_WORKFLOW}::{_PLANTED_JOB}"
_CLI_ROW = "cli"
_CLI_ROW_LABEL = f"ci-modules.yml::test[{_CLI_ROW}]"

_RETIRED_ROUTER_JOB = """\
on: pull_request
jobs:
  tests-cli:
    runs-on: ubuntu-24.04
    steps:
      - run: uv run --frozen pytest tests/cli -q
"""

# Per-job anchors whose modelled selection must equal one real ``pytest --collect-only`` of the job's own CLI.
_ANCHOR_JOBS: tuple[tuple[str, str], ...] = (
    ("ci-router.yml", "terminology"),
    ("ci-router.yml", "layer-rules"),
    ("ci-router.yml", "archive-freeze"),
    ("ci-router.yml", "tests-corpus-blocking"),
    ("packs.yml", "built-in-pack-manifest"),
    ("packs.yml", "internal-packaging-safety"),
)


# ---------------------------------------------------------------------------
# Live fixtures (one universe per module)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def universe() -> list[gc.TestRecord]:
    return gc.collect_universe()


@pytest.fixture(scope="module")
def records(universe: list[gc.TestRecord]) -> dict[str, gc.TestRecord]:
    return {record["nodeid"]: record for record in universe}


@pytest.fixture(scope="module")
def jobs() -> list[lu.LiveJob]:
    return lu.per_change_jobs()


@pytest.fixture(scope="module")
def selected(jobs: list[lu.LiveJob], universe: list[gc.TestRecord]) -> dict[lu.JobKey, frozenset[str]]:
    return lu.selected_by_job(jobs, universe)


@pytest.fixture(scope="module")
def overlaps(jobs: list[lu.LiveJob], selected: dict[lu.JobKey, frozenset[str]]) -> lu.Overlaps:
    return lu.pairwise_overlaps(jobs, selected)


def _describe(findings: lu.Overlaps) -> str:
    lines = []
    for (first, second), nodes in sorted(findings.items(), key=lambda item: (-len(item[1]), item[0][0][0], item[0][0][1])):
        shown = ", ".join(sorted(nodes)[:_FINDINGS_SHOWN])
        lines.append(f"{lu.label_of(first)} x {lu.label_of(second)}: {len(nodes)} node(s), first {_FINDINGS_SHOWN}: {shown}")
    return "\n".join(lines)


def _job(jobs: list[lu.LiveJob], workflow: str, job: str, leg: str | None = None) -> lu.LiveJob:
    [found] = [candidate for candidate in jobs if candidate.key == (workflow, job, leg)]
    return found


# ---------------------------------------------------------------------------
# Live assertions
# ---------------------------------------------------------------------------


def test_no_per_change_overlap_outside_the_allowlist(
    jobs: list[lu.LiveJob],
    overlaps: lu.Overlaps,
    records: dict[str, gc.TestRecord],
) -> None:
    """No node is selected by two same-tier per-change jobs unless an allowance covers that overlap."""
    findings = lu.uncovered_overlaps(overlaps, ALLOWLIST, jobs, records)
    assert not findings, (
        "per-change jobs of the same OS tier select the same tests (a duplicate execution per PR; fold it into one job or add a reasoned, "
        f"scoped allowance with an issue):\n{_describe(findings)}"
    )


def test_allowlist_entries_are_reasoned_live_and_capped(
    jobs: list[lu.LiveJob],
    overlaps: lu.Overlaps,
    records: dict[str, gc.TestRecord],
) -> None:
    labels = {job.label for job in jobs}
    sides = labels | {job.family for job in jobs}
    for entry in ALLOWLIST:
        assert entry.reason.strip(), f"allowance {entry.job_a} x {entry.job_b_family} has no reason"
        assert entry.issue.startswith("#") and entry.issue[1:].isdigit(), f"allowance {entry.job_a} needs a '#<number>' issue, got {entry.issue!r}"
        assert (entry.scope_marker is None) != (not entry.scope_files), f"allowance {entry.job_a} must set exactly one of scope_marker / scope_files"
        assert entry.job_a in labels, f"allowance names {entry.job_a!r}, which is not a live per-change job label"
        assert entry.job_b_family in sides, f"allowance names {entry.job_b_family!r}, which is neither a live job label nor a family"
    stale = lu.stale_allowances(overlaps, ALLOWLIST, jobs, records)
    assert not stale, f"stale allowances (they cover no live overlapping node; delete them): {[(a.job_a, a.job_b_family) for a in stale]}"
    assert len(ALLOWLIST) <= _ALLOWLIST_CEILING <= _ALLOWLIST_HARD_CAP, (
        f"allowlist has {len(ALLOWLIST)} entries; ceiling {_ALLOWLIST_CEILING} (shrink-only) must stay <= {_ALLOWLIST_HARD_CAP}"
    )


def test_per_change_job_set_is_non_vacuous(jobs: list[lu.LiveJob], selected: dict[lu.JobKey, frozenset[str]]) -> None:
    """The relation ranges over real jobs: expanded module rows, the battery, Packs, all tiered."""
    registry_rows = [module for module, _ in lu.module_rows(gc.WORKFLOWS_DIR.parent / lu.REGISTRY_FILE_NAME)]
    module_jobs = [job for job in jobs if (job.key[0], job.key[1]) == lu.MODULE_MATRIX_JOB]
    assert sorted(job.key[2] or "" for job in module_jobs) == sorted(registry_rows), "ci-modules.yml::test must expand into exactly one job per registry row"
    assert {job.tier for job in module_jobs} == {"linux"}, "every expanded module row must be tiered linux (the splice carries the delegate's runs-on)"
    assert [job for job in jobs if job.family == _BATTERY], "no architectural-battery job in the per-change set"
    assert [job for job in jobs if job.key[0] == "packs.yml"], "no Packs job in the per-change set"
    assert all(job.tier for job in jobs), "every per-change job must be tiered"
    assert max(sum(1 for job in jobs if job.tier == tier) for tier in {job.tier for job in jobs}) >= 2, "no tier holds two jobs: the relation would be vacuous"
    empty = sorted(job.label for job in jobs if not selected[job.key])
    assert not empty, f"per-change jobs selecting no test (a vacuous job hides drift): {empty}"


@pytest.mark.parametrize(("workflow", "job"), _ANCHOR_JOBS, ids=[f"{w}::{j}" for w, j in _ANCHOR_JOBS])
def test_modelled_selection_matches_real_collect_for_anchor_jobs(
    workflow: str,
    job: str,
    jobs: list[lu.LiveJob],
    selected: dict[lu.JobKey, frozenset[str]],
) -> None:
    """Fidelity anchor: the modelled selection of a small job equals pytest's own collection of its CLI."""
    live = _job(jobs, workflow, job)
    real = frozenset(nodeid for gate in live.gates for nodeid in gc.collect_job_nodeids(gate))
    assert real, f"{live.label}: real collection selected nothing"
    assert selected[live.key] == real, (
        f"{live.label}: modelled selection differs from the real collection "
        f"(model-only {sorted(selected[live.key] - real)[:5]}, real-only {sorted(real - selected[live.key])[:5]})"
    )


# ---------------------------------------------------------------------------
# Positive controls (no real workflow is mutated)
# ---------------------------------------------------------------------------


def _scoping_marker(nodes: frozenset[str], records: dict[str, gc.TestRecord]) -> str:
    """A marker carried by some, but not all, of *nodes* (so a scoped allowance can be narrower than the overlap)."""
    counts = collections.Counter[str](marker for nodeid in nodes for marker in records[nodeid]["markers"])
    partial = [marker for marker, count in counts.most_common() if count < len(nodes)]
    assert partial, "the control needs a marker that scopes the overlap down"
    return partial[0]


def _plant(
    jobs: list[lu.LiveJob],
    universe: list[gc.TestRecord],
    selected: dict[lu.JobKey, frozenset[str]],
    planted_gate: gc.Gate,
) -> tuple[list[lu.LiveJob], lu.Overlaps]:
    planted = lu.group_jobs([planted_gate], [])
    with_planted = [*jobs, *planted]
    return with_planted, lu.pairwise_overlaps(with_planted, {**selected, **lu.selected_by_job(planted, universe)})


def _pair_nodes(overlaps: lu.Overlaps, label_a: str, label_b: str) -> frozenset[str]:
    return frozenset().union(*(nodes for (first, second), nodes in overlaps.items() if {lu.label_of(first), lu.label_of(second)} == {label_a, label_b}))


def test_planted_overlap_outside_allowlist_is_reported(
    jobs: list[lu.LiveJob],
    universe: list[gc.TestRecord],
    records: dict[str, gc.TestRecord],
    selected: dict[lu.JobKey, frozenset[str]],
) -> None:
    """A third Linux job duplicating one module row's directory is flagged; inside an allowlisted marker scope it is not."""
    cli = _job(jobs, "ci-modules.yml", "test", _CLI_ROW)
    paths = list(cli.gates[0].paths)
    full_gate = gc.Gate(_PLANTED_WORKFLOW, _PLANTED_JOB, None, paths=paths, marker_expr=MODULE_SELECTION_MARKER_EXPR, runs_on=_LINUX)
    planted_jobs, planted_overlaps = _plant(jobs, universe, selected, full_gate)
    flagged = lu.uncovered_overlaps(planted_overlaps, ALLOWLIST, planted_jobs, records)
    assert _pair_nodes(flagged, _PLANTED_LABEL, _CLI_ROW_LABEL), "a job planted over the cli row's directory was not reported"

    marker = _scoping_marker(selected[cli.key], records)
    scoped_gate = gc.Gate(_PLANTED_WORKFLOW, _PLANTED_JOB, None, paths=paths, marker_expr=f"({MODULE_SELECTION_MARKER_EXPR}) and {marker}", runs_on=_LINUX)
    allowance = lu.OverlapAllowance(_PLANTED_LABEL, _CLI_ROW_LABEL, marker, _NO_FILES, "planted control", "#5510")
    scoped_jobs, scoped_overlaps = _plant(jobs, universe, selected, scoped_gate)
    assert _pair_nodes(scoped_overlaps, _PLANTED_LABEL, _CLI_ROW_LABEL), "the scoped plant must still overlap (the control would be vacuous)"
    twin = lu.uncovered_overlaps(scoped_overlaps, (*ALLOWLIST, allowance), scoped_jobs, records)
    assert not _pair_nodes(twin, _PLANTED_LABEL, _CLI_ROW_LABEL), "an overlap inside an allowlisted marker scope must not be reported"
    # The same allowance must not become a blanket pass for the unscoped plant.
    leaked = lu.uncovered_overlaps(planted_overlaps, (*ALLOWLIST, allowance), planted_jobs, records)
    assert _pair_nodes(leaked, _PLANTED_LABEL, _CLI_ROW_LABEL), "a scoped allowance swallowed an overlap outside its scope"


def test_retired_router_duplicate_shape_is_reported(
    tmp_path: Path,
    jobs: list[lu.LiveJob],
    universe: list[gc.TestRecord],
    records: dict[str, gc.TestRecord],
    selected: dict[lu.JobKey, frozenset[str]],
) -> None:
    """The pre-Mission router job ``tests-cli`` (``pytest tests/cli``) against the expanded ``cli`` row is reported.

    The permanent node-level twin of the FR-010 merge-base red, and of the router lane's directory-level
    pre-check (``router_dirs_owned_by_a_module``): it names the shape on the real ``cli`` row, with real nodes.
    """
    workflow = tmp_path / "ci-router.yml"
    workflow.write_text(_RETIRED_ROUTER_JOB, encoding="utf-8")
    [retired_gate] = gc.parse_workflow(workflow)
    retired_jobs, retired_overlaps = _plant(jobs, universe, selected, retired_gate)
    flagged = lu.uncovered_overlaps(retired_overlaps, ALLOWLIST, retired_jobs, records)
    assert _pair_nodes(flagged, "ci-router.yml::tests-cli", _CLI_ROW_LABEL), "the retired router duplicate shape was not reported against the cli row"


def test_stale_allowance_is_reported(jobs: list[lu.LiveJob], overlaps: lu.Overlaps, records: dict[str, gc.TestRecord]) -> None:
    """An allowance naming a pair that never overlaps covers nothing, so it is stale."""
    ghost = lu.OverlapAllowance("ci-router.yml::terminology", _BATTERY, "corpus", _NO_FILES, "ghost control", "#5510")
    assert lu.stale_allowances(overlaps, (*ALLOWLIST, ghost), jobs, records)[-1] == ghost


# ---------------------------------------------------------------------------
# Synthetic fault injection over the OS-tier relation (independent of the live suite)
# ---------------------------------------------------------------------------


def _synthetic(nodeid: str, *markers: str) -> gc.TestRecord:
    return {"nodeid": nodeid, "relpath": nodeid.partition("::")[0], "markers": list(markers)}


def test_same_tier_relation_bites_on_synthetic_double_run() -> None:
    """Two Linux gates selecting the same synthetic test are a same-tier double run; a Windows twin is a different tier."""
    double_run = _synthetic("tests/synthetic/test_double.py::test_a", "fast")
    linux_a = gc.Gate("synthetic", "alpha", None, paths=["tests/synthetic/"], marker_expr="fast", runs_on=_LINUX)
    linux_b = gc.Gate("synthetic", "beta", None, paths=["tests/synthetic/"], marker_expr="fast", runs_on=_LINUX)
    windows = gc.Gate("synthetic", "gamma", None, paths=["tests/synthetic/"], marker_expr="fast", runs_on=_WINDOWS)
    counts = gc.os_tier_shard_counts([linux_a, linux_b, windows], [double_run])
    assert counts[double_run["nodeid"]] == {"linux": 2, "windows": 1}, "the OS-tier relation failed to flag a synthetic same-tier double run"


def test_scoped_allowance_is_narrow_not_a_blanket_pass() -> None:
    """An allowed overlay overlap is not reported, while a genuine double run between two home jobs still is."""
    corpus_case = _synthetic("tests/synthetic/corpus_case/test_overlap.py::test_a", "fast", "corpus")
    genuine_case = _synthetic("tests/synthetic/genuine_case/test_double.py::test_b", "fast")
    home = gc.Gate("synthetic", "home-alpha", None, paths=["tests/synthetic/corpus_case/", "tests/synthetic/genuine_case/"], marker_expr="fast", runs_on=_LINUX)
    other = gc.Gate("synthetic", "home-beta", None, paths=["tests/synthetic/genuine_case/"], marker_expr="fast", runs_on=_LINUX)
    overlay = gc.Gate("synthetic", "overlay", None, paths=["tests/synthetic/corpus_case/"], marker_expr="corpus", runs_on=_LINUX)
    synthetic_jobs = lu.group_jobs([home, other, overlay], [])
    universe = [corpus_case, genuine_case]
    synthetic_overlaps = lu.pairwise_overlaps(synthetic_jobs, lu.selected_by_job(synthetic_jobs, universe))
    by_nodeid = {record["nodeid"]: record for record in universe}
    allowance = lu.OverlapAllowance("synthetic::overlay", "synthetic::home-alpha", "corpus", _NO_FILES, "intentional corpus overlay", "#3315")
    findings = lu.uncovered_overlaps(synthetic_overlaps, [allowance], synthetic_jobs, by_nodeid)
    assert set(findings.values()) == {frozenset({genuine_case["nodeid"]})}, "only the genuine two-home-job double run may remain"
    assert not lu.stale_allowances(synthetic_overlaps, [allowance], synthetic_jobs, by_nodeid)


def test_interpreter_split_does_not_split_the_tier() -> None:
    """A 3.11 module row and a 3.12 router job on the same OS family are ONE tier (D-14), so their duplicate is flagged."""
    node = _synthetic("tests/synthetic/test_dup.py::test_a", "fast")
    # Stands for a module row (Python 3.11 via the warmup action) and a router job (Python 3.12): same OS family.
    module_row = gc.Gate("synthetic-modules.yml", "test", "cli", paths=["tests/synthetic/"], marker_expr="fast", runs_on=_LINUX)
    router_job = gc.Gate("synthetic-router.yml", "tests-cli", None, paths=["tests/synthetic/"], runs_on=_LINUX)
    assert gc.os_tier_shard_counts([module_row, router_job], [node])[node["nodeid"]] == {"linux": 2}
    synthetic_jobs = lu.group_jobs([module_row, router_job], [])
    synthetic_overlaps = lu.pairwise_overlaps(synthetic_jobs, lu.selected_by_job(synthetic_jobs, [node]))
    assert len(synthetic_overlaps) == 1, "an interpreter difference must not hide a same-OS duplicate"


def test_untiered_per_change_job_fails_closed() -> None:
    """A per-change gate whose ``runs-on`` cannot be resolved raises rather than dropping out of the relation."""
    unresolved = gc.Gate("synthetic", "matrixed", None, paths=["tests/synthetic/"], runs_on=None)
    with pytest.raises(ValueError, match="no single OS-family tier"):
        lu.group_jobs([unresolved], [])
