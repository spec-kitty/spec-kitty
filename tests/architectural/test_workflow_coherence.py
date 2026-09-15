"""Workflow-coherence relation primitives (FR-003/FR-005/FR-008/FR-011, WP04).

These bound the delivery-topology relations this mission owns, over the SAME
parsed model as the marker invariant (``_gate_coverage.WorkflowModel``):

  FR-003a  every ``needs.<job>.result`` read is declared in that job's ``needs:``
  FR-003b  every dorny filter output (except the deliberately non-gating
           groups — the ``any_src`` probe, and the ``ci`` CI-infrastructure
           group, spec-kitty#4386) is consumed by >=1 job ``if:``
  FR-003c  every filter glob matches >=1 tracked path
  FR-003d  the quality-gate verdict consumes ``toJSON(needs)`` and reads ZERO
           literal ``needs.<job>.result`` — membership in ``needs:`` IS the
           blocking authority (WP03 reshape; a literal read reappearing = drift)
  FR-005   every diff-cover critical-path entry is backed by >=1 ``--cov`` emitter
  FR-008   the pytest-invoking-workflow set == the parse model's allowlist
           (a fifth suite-running workflow fails closed)
  FR-011   the quality-gate JOB_GROUPS table == the parsed job-``if:`` gating map
           (Decision 8 two-authority rule; ``quarantine-visibility`` stays out of
           the blocking set, C-005)

The interim convergence topology restores ``ci-windows.yml`` and a reduced
``ci-quality.yml``. The live checks below re-open the subset of the former
relations that those two files can support; the old five-workflow suite-model
relations remain retired until the deferred topology workflows are restored.

WHAT REMAINS: the pure relation primitives below (``needs_declaration_violations``,
``unconsumed_filter_groups``, ``glob_is_live``, ``critical_path_backed_by``,
``parse_job_groups``) never read a real workflow file — each is exercised only
against a ``WorkflowModel`` built from FIXTURE YAML (``_workflow_fixtures``) or
literal data constructed in-line by the ``test_faultinjection_*`` tests, so
they keep proving each relation actually reds on a planted violation
regardless of whether any workflow YAML exists on disk.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
from typing import TYPE_CHECKING

import pytest

from tests.architectural import _gate_coverage as gc
from tests.architectural._workflow_fixtures import filter_workflow, write_workflow

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.architectural, pytest.mark.git_repo]

# ``"job-name": [ "grp", ... ]`` rows of the JOB_GROUPS heredoc (FR-011).
_JOB_GROUPS_ROW_RE = re.compile(r'"([\w-]+)":\s*\[([^\]]*)\]')
_QUOTED_RE = re.compile(r'"([\w-]+)"')

# FR-003c exception ledger — shrink-only, one row per (workflow, group, glob).
#
# ``test_vestigial_glob_rows_stay_earned`` keeps this honest: a row whose glob
# has left the workflow, or which has become live, reds until it is deleted —
# the ledger cannot outlive its subject.
VESTIGIAL_FILTER_GLOBS: dict[tuple[str, str, str], str] = {}

# NFR-007 fault-injection pair: a make target whose NAME shares nothing with
# the live ``test-fast`` one, so a resolver that matched the literal string
# ``make test-fast`` would miss it. Resolution must come from READING the
# Makefile: variables expanded, recipe parsed, pytest command recovered.
_RENAMED_TIER_MAKEFILE = """\
.PHONY: coverage-tier lint-only

TIER_DIRS := tests/unit tests/status
TIER_MARKERS = (fast or unit) and not slow

coverage-tier:
\tenv -u FORCE_COLOR PWHEADLESS=1 uv run --frozen pytest $(TIER_DIRS) \\
\t  -m "$(TIER_MARKERS)" --ignore=tests/unit/skipme -n auto -q

lint-only:
\tuv run --frozen ruff check src/
"""

_MAKE_CALLER_WORKFLOW = """\
name: fixture
on: push
jobs:
  reporter:
    runs-on: ubuntu-latest
    steps:
      - run: |
          mkdir -p out/reports
          make coverage-tier
"""

_MAKE_NON_SUITE_WORKFLOW = """\
name: fixture
on: push
jobs:
  linter:
    runs-on: ubuntu-latest
    steps:
      - run: make lint-only
"""


# ---------------------------------------------------------------------------
# Pure relation primitives (fault-injection substrate).
# ---------------------------------------------------------------------------


def _tracked_paths() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=gc.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return set(result.stdout.splitlines())


def test_needs_result_reads_are_declared_live() -> None:
    """FR-003a: no phantom ``needs.<job>.result`` read in a restored workflow."""
    for name in gc.WORKFLOW_FILES:
        model = gc.load_workflow_model(gc.WORKFLOWS_DIR / name)
        violations = needs_declaration_violations(model)
        assert not violations, f"{name}:\n" + "\n".join(violations)


def test_every_restored_filter_group_is_consumed_live() -> None:
    """FR-003b: every named filter group gates at least one job (or is a recorded non-gater).

    The only exemptions are the deliberately non-gating groups in
    ``_DELIBERATELY_UNGATED_FILTER_GROUPS`` (``any_src`` — contract Invariant 1;
    ``ci`` — spec-kitty#4386, whose per-PR executor is the always-on
    ci-modules.yml matrix, pinned by tests/ci/test_ci_module_wiring.py).
    """
    for name in gc.WORKFLOW_FILES:
        model = gc.load_workflow_model(gc.WORKFLOWS_DIR / name)
        unconsumed = unconsumed_filter_groups(model)
        assert not unconsumed, f"{name}: unconsumed filter groups {sorted(unconsumed)}"


def dead_filter_globs(
    name: str,
    model: gc.WorkflowModel,
    tracked: set[str],
) -> list[tuple[str, str, str]]:
    """FR-003c: ``(workflow, group, glob)`` rows matching no tracked path."""
    return [
        (name, group, glob)
        for group, globs in model.filter_groups.items()
        for glob in globs
        if not glob_is_live(glob, tracked)
    ]


def test_every_restored_filter_glob_is_live() -> None:
    """FR-003c: no restored filter glob names a nonexistent tracked path."""
    tracked = _tracked_paths()
    for name in gc.WORKFLOW_FILES:
        model = gc.load_workflow_model(gc.WORKFLOWS_DIR / name)
        dead = [
            row
            for row in dead_filter_globs(name, model, tracked)
            if row not in VESTIGIAL_FILTER_GLOBS
        ]
        assert not dead, f"{name}: dead filter globs {dead}"


def test_vestigial_glob_rows_stay_earned() -> None:
    """Each ledger row is still declared, still dead, and still explained.

    Without this, the ledger would be a place to park findings: a glob deleted
    from its workflow (the intended fix) would leave a row behind quietly
    excusing nothing, and a reason-less row could widen the exception surface
    in silence.
    """
    tracked = _tracked_paths()
    dead = {
        row
        for name in gc.WORKFLOW_FILES
        for row in dead_filter_globs(
            name, gc.load_workflow_model(gc.WORKFLOWS_DIR / name), tracked,
        )
    }

    stale = sorted(row for row in VESTIGIAL_FILTER_GLOBS if row not in dead)
    assert not stale, (
        "VESTIGIAL_FILTER_GLOBS rows no longer describe a dead declared glob "
        f"(the workflow was fixed, or the path became tracked) — delete them: {stale}"
    )
    unreasoned = sorted(row for row, why in VESTIGIAL_FILTER_GLOBS.items() if not why.strip())
    assert not unreasoned, f"VESTIGIAL_FILTER_GLOBS rows with an empty rationale: {unreasoned}"


def test_pytest_workflow_set_equals_model_allowlist_live() -> None:
    """FR-008: every discovered pytest workflow is intentionally modeled."""
    assert gc.discover_pytest_workflows() == frozenset(gc.WORKFLOW_FILES)


def test_no_live_workflow_reaches_the_suite_through_an_indirection() -> None:
    """NFR-007: a ``run:`` step reaching the suite via a make target IS a gate,
    and today no live workflow does.

    REWRITTEN by mission ``sonar-per-pr-coverage-reuse`` WP06 (#4334). This
    assertion was a *characterisation*: ``ci-quality.yml``'s ``sonarcloud``
    reporter executed a full test tier through a make target rather than a
    directly-anchored ``pytest`` command, and until WP03 the gate model could
    not see that at all — ``_gate_coverage`` documented the job as "not (and
    cannot be) collected as a gate here", so a whole duplicate suite execution
    sat in the tree while every invariant built on this substrate reported "no
    pytest jobs in ci-quality.yml": green, and wrong. WP06 retired the job, so
    the characterisation has no subject left.

    What remains is the *ledger*: the indirect-gate set over every modelled
    workflow, which is empty today. This is not a claim that indirection is
    impossible — it is the record that nothing currently uses it, so a future
    step that does is a visible, reviewed change rather than a silent one. The
    RESOLUTION CAPABILITY is unaffected by the retirement and stays proven by
    :func:`test_faultinjection_renamed_make_target_still_resolves` (a target
    renamed behind make variables is still resolved) and its negative control
    :func:`test_faultinjection_make_target_without_pytest_is_not_a_gate`, both
    fixture-driven.
    """
    indirect = {
        (gate.workflow, gate.job, gate.via) for gate in gc.load_gates() if gate.via is not None
    }
    assert indirect == set(), (
        "a live workflow now reaches the test suite through an indirection "
        f"(make target or in-repo script): {sorted(indirect)}. That is not forbidden, but it is the "
        "form that hid a duplicate suite execution for months — declare it deliberately here, and "
        "check tests/architectural/test_no_duplicate_suite_execution.py agrees it is not a duplicate"
    )
    # Non-vacuity: the ledger above is only meaningful while the model is
    # really parsing workflows. An empty gate set entirely would satisfy it.
    assert gc.load_gates(), "the gate model resolved NO suite invocations at all — the empty indirect set above proves nothing"


def test_faultinjection_renamed_make_target_still_resolves(tmp_path: Path) -> None:
    """NFR-007: resolution reads the Makefile, so a target rename cannot evade it.

    The fixture target is named ``coverage-tier`` — nothing a literal
    ``make test-fast`` match could catch — and its paths/marker live behind
    make variables, so only real expansion recovers them.
    """
    makefile = tmp_path / "Makefile"
    makefile.write_text(_RENAMED_TIER_MAKEFILE, encoding="utf-8")
    workflow = write_workflow(tmp_path, _MAKE_CALLER_WORKFLOW, name="reporter.yml")

    gates = gc.parse_workflow(workflow, makefile=makefile)

    assert [gate.job for gate in gates] == ["reporter"]
    gate = gates[0]
    assert gate.via == "make coverage-tier"
    assert gate.paths == ["tests/unit", "tests/status"]
    assert gate.marker_expr == "(fast or unit) and not slow"
    assert gate.ignores == ["tests/unit/skipme"]


def test_faultinjection_make_target_without_pytest_is_not_a_gate(tmp_path: Path) -> None:
    """Negative control: widened detection must not call every ``make`` a suite run.

    Without this twin, a resolver that flagged any ``make`` invocation would
    pass the regression above while making ``discover_pytest_workflows``
    meaningless.
    """
    makefile = tmp_path / "Makefile"
    makefile.write_text(_RENAMED_TIER_MAKEFILE, encoding="utf-8")
    workflow = write_workflow(tmp_path, _MAKE_NON_SUITE_WORKFLOW, name="linter.yml")

    assert gc.parse_workflow(workflow, makefile=makefile) == []


def test_reduced_quality_gate_has_no_literal_result_reads_live() -> None:
    """FR-003d: the reduced gate consumes the complete needs context as JSON."""
    model = gc.load_workflow_model(gc.WORKFLOWS_DIR / "ci-quality.yml")
    text = (gc.WORKFLOWS_DIR / "ci-quality.yml").read_text(encoding="utf-8")

    assert model.needs_result_reads["quality-gate"] == frozenset()
    assert "NEEDS_JSON: ${{ toJSON(needs) }}" in text


def needs_declaration_violations(model: gc.WorkflowModel) -> list[str]:
    """FR-003a: every ``needs.<job>.result`` read declared in that job's needs."""
    out: list[str] = []
    for job, reads in model.needs_result_reads.items():
        undeclared = reads - set(model.job_needs.get(job, ()))
        if undeclared:
            out.append(f"job {job!r} reads needs.<x>.result for undeclared job(s) {sorted(undeclared)} (declared needs: {sorted(model.job_needs.get(job, ()))})")
    return out


# Deliberately non-gating filter groups (FR-003b exemption set). Each entry is
# a group the contract forbids from gating any router job, so FR-003b must not
# flag it as unconsumed:
#
# * ``any_src`` — the FR-004 probe; contract Invariant 1 ("never gate a job on
#   ``any_src`` directly"). Its live consumer is the ``unmatched`` computation
#   in the ``changes`` job itself.
# * ``ci`` (spec-kitty#4386) — the CI-infrastructure group
#   (``scripts/ci/**`` + ``.github/workflows/**``). Its per-PR executor is the
#   ci-modules.yml module matrix, which runs on EVERY PR, so no router job may
#   gate on it — a router ``tests (ci)`` job would double-run the suite per PR,
#   the exact duplicate class test_no_duplicate_suite_execution.py removes. The
#   group is not dead: the ``changes`` job exports it as a live output, and
#   tests/ci/test_ci_module_wiring.py pins both its routing and its two
#   deliberate exclusions — the exemption here is safe only together with that
#   pin. Adding a new deliberately-ungated group means naming it here AND
#   pinning it the same way, never silently.
_DELIBERATELY_UNGATED_FILTER_GROUPS = frozenset({"any_src", "ci"})


def unconsumed_filter_groups(model: gc.WorkflowModel) -> set[str]:
    """FR-003b: filter groups (minus the deliberate non-gaters) with no job ``if:`` consumer."""
    consumed: set[str] = set()
    for groups in model.job_gating_groups.values():
        consumed |= set(groups)
    return (set(model.filter_groups) - _DELIBERATELY_UNGATED_FILTER_GROUPS) - consumed


def glob_is_live(glob: str, tracked: set[str]) -> bool:
    """FR-003c: does ``glob`` match >=1 tracked path?

    The trailing-``/**`` fast path below is a literal prefix check, which is
    only valid when nothing EARLIER in the glob is itself a wildcard (e.g.
    ``docs/**``). A glob with a wildcard segment before the trailing ``/**``
    (e.g. ``kitty-specs/**/tasks/**``, mission ci-scoping-gate-reliability
    #3008) would make that prefix contain a literal ``*`` character, which
    can never match a real tracked path -- a false "dead glob" negative, not
    a real one. Route those through the general ``fnmatch`` branch instead,
    which correctly treats every ``*``/``**`` as a wildcard throughout.
    """
    normalized = glob.rstrip("/")
    if normalized.endswith("/**") and "*" not in normalized[:-3]:
        prefix = normalized[:-3].rstrip("/") + "/"
        return any(path.startswith(prefix) for path in tracked)
    if "*" in normalized:
        return any(fnmatch.fnmatch(path, normalized) for path in tracked)
    return normalized in tracked or any(path.startswith(normalized + "/") for path in tracked)


def critical_path_backed_by(entry: str, cov_targets: set[str]) -> str | None:
    """FR-005: a ``--cov`` target that is an ancestor-or-equal of ``entry``, if any.

    ``cov_targets`` may hold either shape a ``--cov`` flag takes since #2975
    (a ``src/``-relative path or a dotted module, e.g.
    ``specify_cli.charter_runtime``); both are normalized to the same
    ``src/``-relative form via ``gc.cov_target_repo_path`` before comparing,
    so a dotted emitter still backs its critical-path entry.
    """
    package = entry[:-2] if entry.endswith("/*") else entry
    package = package.rstrip("/")
    for cov in cov_targets:
        target = gc.cov_target_repo_path(cov)
        if package == target or package.startswith(target + "/"):
            return cov
    return None


def parse_job_groups(quality_gate_run_text: str) -> dict[str, set[str]]:
    """Parse the ``JOB_GROUPS = { ... }`` heredoc dict into ``job -> {groups}``."""
    match = re.search(r"JOB_GROUPS\s*=\s*\{(.*?)\}\s*\n", quality_gate_run_text, re.DOTALL)
    assert match, "JOB_GROUPS table not found in the quality-gate decision step"
    return {row.group(1): set(_QUOTED_RE.findall(row.group(2))) for row in _JOB_GROUPS_ROW_RE.finditer(match.group(1))}



# ---------------------------------------------------------------------------
# Fault-injection (per relation, fixture YAML / fixture data).
# ---------------------------------------------------------------------------


def test_faultinjection_undeclared_needs_read_reds(tmp_path: Path) -> None:
    """FR-003a: a ``needs.ghost.result`` read without a declaration reds."""
    wf = write_workflow(
        tmp_path,
        """\
        name: fixture
        on: push
        jobs:
          agg:
            needs: [a]
            runs-on: ubuntu-latest
            steps:
              - run: echo "${{ needs.ghost.result }}"
          a:
            runs-on: ubuntu-latest
            steps:
              - run: echo hi
        """,
    )
    violations = needs_declaration_violations(gc.load_workflow_model(wf))
    assert any("ghost" in v for v in violations), violations


def test_faultinjection_unconsumed_filter_group_reds(tmp_path: Path) -> None:
    """FR-003b: a filter group gated by no job ``if:`` reds."""
    wf = write_workflow(
        tmp_path,
        filter_workflow(
            {"used": ["src/a/**"], "orphan_group": ["src/b/**"]},
            unmatched_refs=None,
            gated_jobs={"job-a": ["used"]},
        ),
    )
    assert unconsumed_filter_groups(gc.load_workflow_model(wf)) == {"orphan_group"}


def test_faultinjection_deliberately_ungated_group_is_exempt_but_orphans_still_red(tmp_path: Path) -> None:
    """FR-003b twin: the recorded non-gaters are exempt, everything else still reds.

    Without this twin, widening the exemption set (spec-kitty#4386 added ``ci``
    next to ``any_src``) could not be fault-injected: a resolver that exempted
    EVERY group would pass ``test_every_restored_filter_group_is_consumed_live``
    while the guard went vacuous. A deliberately-ungated group with no job
    ``if:`` is exempt; a genuinely dead group in the same workflow still reds.
    """
    wf = write_workflow(
        tmp_path,
        filter_workflow(
            {"ci": ["scripts/ci/**"], "orphan_group": ["src/b/**"]},
            unmatched_refs=None,
            gated_jobs={},
        ),
    )
    assert unconsumed_filter_groups(gc.load_workflow_model(wf)) == {"orphan_group"}


def test_faultinjection_dead_glob_reds() -> None:
    """FR-003c: a glob matching no tracked path reds (pure helper)."""
    tracked = {"src/real/module.py", "tests/real/test_it.py"}
    assert glob_is_live("src/real/**", tracked)
    assert not glob_is_live("src/deleted_package/**", tracked)


def test_faultinjection_unbacked_critical_path_reds() -> None:
    """FR-005: a critical path with no ``--cov`` ancestor reds (pure helper)."""
    cov = {"src/specify_cli/status", "src/kernel"}
    assert critical_path_backed_by("src/kernel/*", cov) == "src/kernel"
    assert critical_path_backed_by("src/orphaned_pkg/*", cov) is None


def test_faultinjection_extra_pytest_workflow_reds(tmp_path: Path) -> None:
    """FR-008: a pytest-invoking workflow outside the allowlist is discovered."""
    write_workflow(
        tmp_path,
        """\
        name: sneaky
        on: push
        jobs:
          hidden:
            runs-on: ubuntu-latest
            steps:
              - run: uv run pytest tests/hidden -m fast
        """,
        name="sneaky.yml",
    )
    discovered = gc.discover_pytest_workflows(tmp_path)
    assert discovered == frozenset({"sneaky.yml"})
    assert discovered != frozenset(gc.WORKFLOW_FILES)


def test_faultinjection_job_groups_mapping_drift_reds() -> None:
    """FR-011: a JOB_GROUPS row disagreeing with the parsed gating reds."""
    run_text = 'JOB_GROUPS = {\n    "fast-tests-sync": ["sync", "drifted_extra"],\n}\n'
    table = parse_job_groups(run_text)
    assert table == {"fast-tests-sync": {"sync", "drifted_extra"}}
    # A parsed gating that lacks ``drifted_extra`` would make table != parsed.
    parsed = {"fast-tests-sync": {"sync"}}
    assert table != parsed
