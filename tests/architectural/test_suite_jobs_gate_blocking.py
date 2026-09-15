"""``quality-gate.needs`` ⊇ pytest-jobs containment guard (FR-012, IC-11, #2622).

Mission ``test-suite-friction-remediation-01KXDKBX`` WP17. Contract:
``contracts/quality-gate-needs-containment.md`` (kitty-specs). Single-file
ownership: this module is the SOLE new invariant suite over
``.github/workflows/ci-quality.yml`` for FR-012 (the sibling
``test_ui_e2e_coverage_discovered.py`` owns FR-013 on the same file, serialized
after this one per the plan).

Every ``pytest``-invoking job in ``ci-quality.yml`` must be a member of
``quality-gate.needs`` — the single blocking-verdict authority
(``test_workflow_coherence.py``'s FR-003d pin) — minus a reasoned
:data:`NON_BLOCKING_ALLOWLIST`. Two jobs were un-gated **by convention only**
before this WP (``slow-tests``, ``mutation-testing``); T082 forces both to an
explicit state:

* ``slow-tests`` — group-less/always-on (no dorny filter-group ``if:`` gate,
  like ``lint``/``kernel-tests``/``unit-contract-residual`` already in
  ``needs:``), so it is added to ``quality-gate.needs`` directly
  (``.github/workflows/ci-quality.yml``'s own comment at that ``needs:`` entry
  explains why this is safe: ``scripts/ci/quality_gate_decision.py``'s
  ``filter_true`` is vacuously ``False`` for a job with no filter groups, so
  its ``skipped`` result on every non-push event is legitimately OK, while a
  real ``failure`` on the push runs it DOES execute on now blocks the gate).
* ``mutation-testing`` — ``if: false``-disabled (an ``echo``-only step); it
  invokes no real pytest command today, so the anchored derivation below never
  actually catches it, but it is still listed in the allowlist (with
  rationale) so the "never left silently absent" requirement is satisfied by
  construction rather than by the guard's incidental blind spot.

Anti-goals (contract): do NOT hard-code the current job list (derive
``pytest_jobs`` from the parsed workflow model so a FUTURE job is covered
automatically); do NOT match ``pytest`` inside a comment or a string literal.

The reduced interim ``ci-quality.yml`` runs **no** suite at all. Getting to
that statement honestly took two missions, and the history is the reason the
live check below is shaped the way it is:

* it once asserted the file had *no* pytest jobs and was green for months while
  a full duplicate tier ran inside it — the non-blocking ``sonarcloud`` reporter
  (spec-kitty#3993) reached pytest through a make target, and the derivation
  read only directly-anchored ``pytest`` commands;
* mission ``sonar-per-pr-coverage-reuse`` WP03 taught the gate model to resolve
  make/script indirection (``_gate_coverage``'s "Indirect suite invocations"
  section) by reading the Makefile, so the job became genuinely derived and its
  ``NON_BLOCKING_ALLOWLIST`` entry became a real subtraction;
* WP06 then retired the job itself (#4334): it re-measured what the
  ``ci-modules`` shards had already measured for the same commit, and the per-PR
  Sonar report moved to ``ci-aggregate.yml``'s ``sonar-pr`` job, which executes
  no tests. Its allowlist entry was retired as moot with its subject, recorded
  in ``tests/release/pinning_rule_inventory.json``.

So the empty set is the *same assertion text* that was once worthless, and it
is therefore paired with a fault-injection probe that re-injects a
make-indirect suite job into a copy of the live file and requires the
derivation to find it. The live checks also bind ``quality-gate.needs`` to the
four producer jobs it blocks; the fault-injection substrate keeps the general
containment relation ready for when a suite job returns.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architectural import _gate_coverage as gc
from tests.architectural._workflow_fixtures import write_workflow

pytestmark = [pytest.mark.architectural, pytest.mark.git_repo]

_CI_QUALITY_NAME = "ci-quality.yml"
_QUALITY_GATE_JOB = "quality-gate"

# Reasoned allowlist (contracts/quality-gate-needs-containment.md): a
# pytest-invoking job that is deliberately NOT gate-blocking. Each entry
# carries a why-non-blocking rationale (mirrors the ``CI_INVISIBLE`` ledger
# pattern in ``test_marker_job_completeness.py``). Additions are LOUD — this
# guard subtracts the allowlist from ``pytest_jobs`` before checking
# containment, so a bare, reason-less addition would silently widen the
# non-blocking surface; :func:`test_allowlist_entries_carry_rationale` closes
# that gap. Removals are always safe (shrink-only).
NON_BLOCKING_ALLOWLIST: dict[str, str] = {
    "quarantine-visibility": (
        "Non-blocking BY DESIGN (visible-but-never-gating quarantine surface, "
        "mission ci-suite-map-bind, C-005). "
        "scripts/ci/quality_gate_decision.py's _assert_no_quarantine_job "
        "hard-fails (exit 2) if this job ever enters quality-gate's "
        "needs/job_groups/draft_gated_jobs/release_required_jobs sets, so it "
        "can never legitimately be promoted to gate-blocking — a quarantined "
        "flake must never be able to block a merge."
    ),
    # NOTE: `regression-tests` is deliberately NOT here — it is BLOCKING
    # (a member of `quality-gate.needs`). A red-first P0 reproduction is
    # expected to red mainline AND, because CI is the release authority, must
    # gate releases; a non-blocking regression lane would fake green on P0s
    # (#2772-family course-correction of the #2774 visibility-only design).
    "mutation-testing": (
        "Disabled placeholder (`if: false`, an echo-only step: "
        '`echo "Mutation testing is disabled."`) pending future '
        "mutation-testing tooling. It invokes no real pytest command today "
        "(so the anchored pytest_jobs derivation below never actually flags "
        "it), but is listed here so FR-012's 'never left silently absent' is "
        "satisfied by an explicit declaration rather than by the guard's "
        "incidental blind spot. Re-enabling it MUST be paired with either a "
        "`quality-gate.needs` edge or an updated rationale here."
    ),
    # RETIRED AS MOOT by mission sonar-per-pr-coverage-reuse WP06 (#4334): the
    # `sonarcloud` entry's subject left the scanned file. That job re-ran the
    # whole fast tier under `pytest --cov` for a coverage report the ci-modules
    # shards had already produced, and was removed from ci-quality.yml; the
    # per-PR Sonar report now lives in ci-aggregate.yml's `sonar-pr` job, which
    # executes no tests and so is not a pytest job at all. Keeping the entry
    # would have made it a declaration about a job that is not there -- exactly
    # what its own history warned against (before WP03 it was "a declaration
    # standing in for a subtraction"; WP03 made it real; WP06 removed its
    # subject). Reason recorded in tests/release/pinning_rule_inventory.json.
}


def blocking_violations(
    pytest_jobs: frozenset[str],
    quality_gate_needs: frozenset[str],
    allowlist: dict[str, str],
) -> frozenset[str]:
    """Pure IC-11 relation: ``pytest_jobs - allowlist - needs`` (empty == healthy)."""
    return pytest_jobs - frozenset(allowlist) - quality_gate_needs


def pytest_jobs_of(workflow_name: str) -> frozenset[str]:
    """Jobs in ``workflow_name`` with at least one real pytest invocation.

    **Trap, for the next reader.** This filters ``load_gates()``, which only
    ever parses ``_gate_coverage.WORKFLOW_FILES``. A workflow absent from that
    tuple therefore returns the empty set *without the file being opened* — so
    for a workflow that runs no suite (``ci-quality.yml`` since WP06) this
    answers "empty" for two different reasons and cannot tell them apart. Any
    assertion that a specific file is clean must parse it DIRECTLY; this helper
    is for the general question across the modelled set.
    """
    return frozenset(gate.job for gate in gc.load_gates() if gate.workflow == workflow_name)


def _ci_quality_needs() -> frozenset[str]:
    model = gc.load_workflow_model(gc.WORKFLOWS_DIR / _CI_QUALITY_NAME)
    return frozenset(model.job_needs[_QUALITY_GATE_JOB])


#: A ``sonarcloud``-shaped suite step, re-injected into a COPY of the live
#: ci-quality.yml by the non-vacuity probe below. Deliberately the indirect
#: (make-target) form: that is the spelling the derivation was blind to for
#: months, and the one an "it found nothing" assertion must be able to see.
_REINJECTED_SUITE_JOB = """
  reinjected-reporter:
    runs-on: ubuntu-latest
    steps:
      - name: Run fast tier under coverage
        run: |
          make test-fast
"""


def test_ci_quality_runs_no_suite_and_the_derivation_can_still_see_one_live(tmp_path: Path) -> None:
    """FR-012/IC-11 over ``ci-quality.yml``: the file now executes NO suite.

    **Read the probe before trusting the empty set.** This assertion's exact
    shape -- "``ci-quality.yml`` has no suite-running jobs" -- was green for
    months while a full duplicate tier ran inside the file, because the
    derivation could only see directly-anchored ``pytest`` commands and the
    reporter reached the suite through a make target. Mission
    ``sonar-per-pr-coverage-reuse`` WP03 closed that blindness and WP06 removed
    the duplicate, so the empty set is now true rather than merely unseen -- but
    "true" and "unseen" are indistinguishable from the assertion alone, which is
    the whole reason the earlier green was worthless.

    So the empty set is paired with a fault-injection probe: the SAME
    derivation, over a COPY of the live file with a ``sonarcloud``-shaped
    (make-indirect) suite job re-injected, must find exactly that job. If the
    derivation ever loses the ability to see the form the duplicate used, this
    reds instead of going quietly green.

    Note the file is parsed DIRECTLY rather than filtered out of
    ``load_gates()``: ``ci-quality.yml`` left ``_gate_coverage.WORKFLOW_FILES``
    with the job, so a filtered lookup would now return the empty set without
    ever opening the file -- a second way to be vacuously green.
    """
    live_text = (gc.WORKFLOWS_DIR / _CI_QUALITY_NAME).read_text(encoding="utf-8")
    suite_jobs = frozenset(gate.job for gate in gc.parse_workflow(gc.WORKFLOWS_DIR / _CI_QUALITY_NAME))

    assert suite_jobs == frozenset(), (
        f"{_CI_QUALITY_NAME} must execute no test suite (FR-001/NFR-001) — found: {sorted(suite_jobs)}"
    )
    assert not blocking_violations(suite_jobs, _ci_quality_needs(), NON_BLOCKING_ALLOWLIST)

    probe = write_workflow(tmp_path, live_text + _REINJECTED_SUITE_JOB, name=_CI_QUALITY_NAME)
    probed = frozenset(gate.job for gate in gc.parse_workflow(probe))
    assert probed == frozenset({"reinjected-reporter"}), (
        "the derivation no longer resolves a make-target suite invocation in this file's shape, so "
        f"the empty live set above proves nothing — probe found: {sorted(probed)}"
    )


def test_reduced_quality_gate_needs_exact_blocking_set_live() -> None:
    """Every non-gate producer job blocks the reduced quality gate."""
    assert _ci_quality_needs() == frozenset(
        {"lint", "build-wheel", "clean-install-verification", "uv-lock-check"}
    )


def test_allowlist_entries_carry_rationale() -> None:
    """Contract: every ``NON_BLOCKING_ALLOWLIST`` entry has a non-empty reason."""
    empty = [job for job, reason in NON_BLOCKING_ALLOWLIST.items() if not reason.strip()]
    assert not empty, f"NON_BLOCKING_ALLOWLIST entries with an empty rationale: {empty}"


# ---------------------------------------------------------------------------
# Fault-injection (T083 — non-fakeable evidence).
# ---------------------------------------------------------------------------

_FIXTURE_WORKFLOW = """\
name: fixture
on: push
jobs:
  quality-gate:
    needs: [existing-suite]
    runs-on: ubuntu-latest
    steps:
      - run: echo gate
  existing-suite:
    runs-on: ubuntu-latest
    steps:
      - run: uv run pytest tests/ -m fast
  sneaky-new-suite:
    runs-on: ubuntu-latest
    steps:
      - run: uv run pytest tests/sneaky -m fast
"""


def test_faultinjection_new_pytest_job_without_gate_edge_reds(tmp_path: Path) -> None:
    """FR-012 regression: a NEW pytest job absent from needs/allowlist reds.

    Non-fakeable evidence required by the contract: adds a fake pytest job
    (``sneaky-new-suite``) to a synthetic workflow that is NOT wired into
    ``quality-gate.needs`` and is NOT allowlisted, then asserts the guard
    catches exactly it.
    """
    wf = write_workflow(tmp_path, _FIXTURE_WORKFLOW, name="wf.yml")
    # `gc.load_gates()` only ever parses the 5 real `WORKFLOW_FILES` under
    # `WORKFLOWS_DIR` — the fixture lives outside that dir, so parse it
    # directly with the same underlying parser.
    gates = gc.parse_workflow(wf)
    pytest_jobs = frozenset(gate.job for gate in gates)
    assert pytest_jobs == frozenset({"existing-suite", "sneaky-new-suite"})

    model = gc.load_workflow_model(wf)
    needs = frozenset(model.job_needs[_QUALITY_GATE_JOB])
    violations = blocking_violations(pytest_jobs, needs, {})
    assert violations == frozenset({"sneaky-new-suite"}), (
        f"expected exactly the un-gated fake pytest job to be caught, got {sorted(violations)}"
    )


def test_faultinjection_gated_or_allowlisted_job_does_not_red(tmp_path: Path) -> None:
    """Green control: the SAME fake job wired into needs (or allowlisted) passes.

    Proves the guard does not false-positive once the job is legitimately
    resolved — the negative-control twin of the regression above.
    """
    wf = write_workflow(
        tmp_path,
        _FIXTURE_WORKFLOW.replace(
            "needs: [existing-suite]",
            "needs: [existing-suite, sneaky-new-suite]",
        ),
        name="wf.yml",
    )
    gates = gc.parse_workflow(wf)
    pytest_jobs = frozenset(gate.job for gate in gates)
    model = gc.load_workflow_model(wf)
    needs = frozenset(model.job_needs[_QUALITY_GATE_JOB])
    assert not blocking_violations(pytest_jobs, needs, {})

    # Allowlisting instead of gating is an equally valid resolution.
    wf_allowlisted = write_workflow(tmp_path, _FIXTURE_WORKFLOW, name="wf2.yml")
    gates2 = gc.parse_workflow(wf_allowlisted)
    pytest_jobs2 = frozenset(gate.job for gate in gates2)
    model2 = gc.load_workflow_model(wf_allowlisted)
    needs2 = frozenset(model2.job_needs[_QUALITY_GATE_JOB])
    allowlist = {"sneaky-new-suite": "fixture-only rationale for the negative control"}
    assert not blocking_violations(pytest_jobs2, needs2, allowlist)
