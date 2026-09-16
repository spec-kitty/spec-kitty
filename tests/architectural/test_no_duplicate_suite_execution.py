"""Fault-injection battery against duplicate per-change suite execution (NFR-007, SC-007).

Mission ``sonar-per-pr-coverage-reuse-01M2FR32`` WP04. Contract:
``kitty-specs/sonar-per-pr-coverage-reuse-01M2FR32/contracts/reporting-job-contract.md``
§C5.

**The property.** Exactly one authorised matrix executes the test suite per change.
Any *other* change-triggered job that reaches pytest -- in any form, in any
workflow file, including one that does not exist yet -- is a duplicate
execution: the same tests run twice per pull request, for one report.

**Why a battery rather than a mutate-and-revert demonstration.** A one-off
mutation is self-reported, leaves nothing in the tree, and protects nothing
after the pull request closes. Worse, the neighbouring gate
(``test_suite_jobs_gate_blocking``) spent months green while asserting
``ci-quality.yml`` had *no* suite-running jobs -- with a full duplicate tier
sitting in the file -- because its substrate could not see the invocation form
that job uses. That is the failure mode this module exists to make
unrepeatable, so every relation below is exercised against a planted violation,
and the live tree is characterised rather than assumed.

**No second enumerator (charter SO#6).** Every "does this job run the suite"
question is answered by :mod:`tests.architectural._gate_coverage`, the mission's
single authority for that (WP03 taught it to resolve a suite reached through a
make target by *reading the Makefile*: variable table, prerequisites, recipe).
This module composes that model into a relation and injects faults into it; it
re-derives nothing.

**Enumeration is a directory read.** :func:`suite_executing_jobs` globs
``.github/workflows/`` rather than consulting a closed list such as
``_gate_coverage.WORKFLOW_FILES`` -- a closed list cannot see a net-new
workflow file, which is mutation 4.

**Classification fails CLOSED.** Reading the directory is not enough: a
workflow this module declines to call change-triggered is dropped from every
assertion in it, silently, while the non-vacuity floor stays green. So
:func:`change_triggered` is a closed world in the other direction -- it
enumerates the events that are *not* per-change
(:data:`NON_CHANGE_TRIGGER_EVENTS` plus a tags-only push) and treats everything
else as in scope, including trigger spellings and ``on:`` shapes it cannot
parse. The first draft of this module inverted that and lost nine spellings,
``on: [push, pull_request]`` among them; the exclusion set is now pinned by
:data:`NON_CHANGE_TRIGGERED_WORKFLOWS` so narrowing the scan is a reviewed edit
rather than an accident.

**Scope note for WP05.** The per-change reporting job (contract C1/C4) does not
exist yet. Mutations 5 and 6 are therefore proven against synthetic workflows
here, so this module is self-contained and green; the predicates
:func:`missing_non_blocking_declarations` and :func:`same_origin_conjunct` take
a workflow path and a job name precisely so WP05 can bind them to the real job
without reshaping anything.

**Former residual gaps -- RESOLVED by widening ``_gate_coverage`` (#4367).**
WP04 refused four CI-reachable surfaces outright because the model could not
see them and widening it was outside that work package's ownership.
spec-kitty#4367 widened the model, and this module now carries a planted
violation behind each formerly-blind form (the "Former escape hatches"
section below):

1. Local composite actions -- ``uses: ./.github/actions/<name>`` steps are
   spliced into the calling job by ``load_spliced_workflow``, exactly like the
   reusable-workflow calls it already resolved, with the action's own nested
   local actions followed too. A suite execution inside one is attributed to
   the calling job (``via="action <name>"``), so the authorised-count and
   duplicate assertions see it.
2. ``$(MAKE) <target>`` recipe delegation -- ``MAKE`` is seeded in the parsed
   variable table, so the idiomatic sub-make spelling resolves exactly like a
   literal ``make <target>``.
3. ``bash -c '<command>'`` wrapping -- the quoted payload is unwrapped at
   whole-line granularity (before shell-segment splitting, so a payload
   containing ``&&``/``;`` stays one command) and per segment.
4. Runner prefixes -- ``coverage run``, the poetry/pdm/hatch/pipenv family,
   ``xvfb-run``, ``timeout N``, ``.venv/bin/pytest`` and the
   ``<path>/python -m`` interpreters are stripped, so the invocation behind
   each parses as the pytest command it is.

The guards that refused those forms are retired with the blindness: what
replaces them is the same discipline this battery applies everywhere else --
a fault-injection that a suite execution planted behind the form is
DETECTED, and a clean negative control that a benign use of the form is not.

A runner class deliberately remains refused, not resolved: ``tox``/``nox``
(and spellings like ``hatch run test``) delegate to configuration files this
model does not read -- their pytest invocation lives in ``tox.ini`` /
``noxfile.py``, not in the workflow line -- so :data:`BLIND_RUNNER_RES` keeps
refusing a standalone ``pytest`` word behind them.

A fifth surface, command-position indirection (``run: ${{ matrix.cmd }}``, or an
``env:`` variable holding the command), is refused rather than enumerated:
:func:`command_indirection_offenders` rejects ANY GitHub expression in command
position and any shell variable the workflow itself declares there. It is
*refused*, not *closed*: both predicates are ``^``-anchored to the logical line,
so the indirection only has to stop being the first word to walk through (see
item 3 below).

**What remains open, stated plainly.** Three things.

1. :data:`BLIND_RUNNER_RES` is a deny-list, so an unknown runner spelling still
   walks through -- the pre-existing status quo, not a regression. Closing the
   class needs a closed-world rule ("any unresolved standalone ``pytest`` word
   in a change-triggered workflow is refused") plus a shrink-only exception
   ledger for the prose lines in workflows this module does not own; that
   is the right follow-up and remains out of scope here. The #4367 widening
   shrank the blind set -- the canonical ``coverage run`` / ``poetry run`` /
   ``xvfb-run`` / ``timeout N`` / ``<path>/pytest`` spellings now resolve, so
   they can no longer trip even this deny-list -- but it did not close the
   class.
2. :data:`NON_CHANGE_TRIGGER_EVENTS` is now the only allow-list left in the
   module. Each of its four rows widens the blind spot by one event, which is
   why the exclusion ledger pins which live workflows they actually exclude.
3. **Command-position indirection is refused, not closed** (WP06/T029b -- the
   header above overstated this as "closed by construction", which held only
   for an *unprefixed* reference). :data:`GITHUB_EXPRESSION_COMMAND_RE` and
   :data:`DECLARED_VAR_COMMAND_RE` are both ``^``-anchored to the logical line,
   and :func:`indirect_command_form`'s own docstring says so accurately: they
   test the line's *command word*. So ``true; ${{ matrix.cmd }}`` and
   ``echo hello && $CMD`` both escape -- the indirection is present but is no
   longer the first word, and the gate model does not resolve either, so
   :func:`indirect_command_form` returns ``None`` for both. Closing this needs
   the predicate to split a logical line on shell operators (``;``, ``&&``,
   ``||``, ``|``) and test EACH resulting command word -- the #4367 widening
   resolved the four delegation forms but deliberately did not touch this
   predicate. Anchoring is deliberate in the
   meantime: an unanchored scan would refuse every workflow line that merely
   *mentions* an expression or a variable, including legitimate arguments.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, NamedTuple

import pytest
import yaml

from tests.architectural import _gate_coverage as gc

pytestmark = [pytest.mark.architectural, pytest.mark.git_repo]

# ``(workflow file name, job name)`` -- job names are unique only WITHIN a
# workflow, so the pair is the key (``_gate_coverage.JobKey``).
JobKey = tuple[str, str]

MAKEFILE = gc.REPO_ROOT / "Makefile"
CI_QUALITY_NAME = "ci-quality.yml"
RETIRING_JOB: JobKey = (CI_QUALITY_NAME, "sonarcloud")
# The form the retiring duplicate uses today: a make-target delegation.
RETIRING_JOB_VIA = "make test-fast"

# The reporting job's host (contract §C5 "non-vacuity floor ... and to include
# the new host"). ``ci-aggregate.yml`` is ``workflow_run``-triggered, and a
# workflow_run chain fires once per change, so a suite execution parked there
# duplicates just as surely as one in the pull_request workflow itself.
REPORTING_HOST_WORKFLOW = "ci-aggregate.yml"

# Events that do NOT put a workflow on the per-change path.
#
# This is a CLOSED WORLD by deliberate inversion. An allow-list of per-change
# events fails OPEN: every trigger spelling it has not heard of -- and
# ``on: [push, pull_request]``, the most ordinary spelling in GitHub Actions, is
# one of them -- silently drops its workflow out of every assertion in this
# module. The two errors do not cost the same. A workflow wrongly called
# per-change costs one reviewed ledger row; a workflow wrongly called NOT
# per-change is invisible, which is exactly the "gate stays green while the tree
# violates the property" failure this battery exists to make unrepeatable. So
# anything not named here -- an unrecognised event, an ``on:`` block in a shape
# this module cannot parse, a missing ``on:`` block -- counts as change-triggered.
#
# Every row below widens the blind spot and must earn its place:
#   ``schedule``          a cron run is not a change (ci-nightly, sonar).
#   ``workflow_dispatch`` a human-initiated run is not a change.
#   ``workflow_call``     a reusable workflow has no triggers of its own; it is
#                         spliced into its caller by ``load_spliced_workflow``,
#                         so counting it standalone would double-count THE
#                         matrix (module-tests.yml).
#   ``release``           a publication event, like the tags-only push below.
NON_CHANGE_TRIGGER_EVENTS: frozenset[str] = frozenset({"schedule", "workflow_dispatch", "workflow_call", "release"})

# ``on.push`` keys that make a push a per-change event. Only a tags-only push
# (``release.yml``) is exempt: tags are publication refs, whereas branch and
# path filters select *changes*. A ``push:`` with no filters at all fires on
# every push and is per-change too.
PER_CHANGE_PUSH_FILTERS: tuple[str, ...] = (
    "branches",
    "branches-ignore",
    "paths",
    "paths-ignore",
    "tags-ignore",
)

# Live workflows deliberately outside the per-change scan, each with the reason
# it is not a change execution.
#
# Shrink-only in spirit, and in the opposite direction to the authorised ledger:
# a REMOVAL is always safe (the workflow becomes visible to every assertion
# here); an ADDITION hides a whole workflow from the gate and must be justified
# in review. This ledger is the assertion that would have caught the fail-open
# classifier: it pins the exclusion set itself, not merely that *something* was
# scanned.
NON_CHANGE_TRIGGERED_WORKFLOWS: dict[str, str] = {
    "ci-nightly.yml": "schedule + workflow_dispatch: the nightly full/performance/interpreter run.",
    "ci-stale-running-sweep.yml": (
        "schedule + workflow_dispatch only: the reactive stale-running sweep backstop "
        "(ci-terminal-cancel-verdict-01M2NC7Z WP02/4b). No pull_request/push trigger by "
        "design — a PR event can never start it, and it never enters a merge-blocking "
        "needs chain."
    ),
    "module-tests.yml": (
        "workflow_call only: a reusable workflow with no triggers of its own, spliced "
        "into ci-modules.yml's caller job. Counting it standalone would double-count THE matrix."
    ),
    "release.yml": "tags-only push + workflow_dispatch: a publication event, not a change.",
    "sonar.yml": "schedule + workflow_dispatch: the nightly informational SonarCloud scan.",
}

# An authorised job runs the suite exactly once. A second invocation inside an
# already-authorised job is the cheapest evasion available to someone who has
# read this ledger -- append one `run:` step to a job that is already allowed --
# so it is refused by construction rather than by a per-job count nobody
# maintains.
AUTHORIZED_SUITE_INVOCATIONS_PER_JOB = 1

# The authorised per-change suite matrix (contract §C5: "the set of
# change-triggered jobs that execute the suite must equal exactly the matrix").
# Keyed by (workflow, job) and NOT by workflow alone: "just add another job to
# ci-router.yml" is the evasion a workflow-granular ledger would wave through.
#
# Shrink-only in spirit. A removal is always safe; an ADDITION is the loud
# event -- it declares a new per-change execution of the test suite and must be
# justified in review with the reason it is not the duplicate this mission
# exists to remove.
AUTHORIZED_PER_CHANGE_SUITE_JOBS: dict[JobKey, str] = {
    ("ci-modules.yml", "test"): (
        "THE matrix. The per-module shard leg (delegating to module-tests.yml) "
        "is the authoritative per-change suite execution; every coverage "
        "artefact this mission reuses is produced here."
    ),
    ("ci-router.yml", "terminology"): "Path-routed lane: the terminology guard.",
    ("ci-router.yml", "layer-rules"): "Path-routed lane: layer/pyproject shape rules.",
    ("ci-router.yml", "architectural-heavy"): "Path-routed lane: the architectural pole.",
    ("ci-router.yml", "tests-merge"): "Path-routed lane: tests/merge.",
    ("ci-router.yml", "tests-status"): "Path-routed lane: tests/status.",
    ("ci-router.yml", "tests-cli"): "Path-routed lane: tests/cli.",
    ("ci-router.yml", "tests-docs"): "Path-routed lane: tests/docs.",
    ("ci-router.yml", "tests-corpus"): "Path-routed lane: the corpus marker family.",
    ("ci-router.yml", "tests-e2e"): "Path-routed lane: tests/e2e.",
    ("ci-windows.yml", "windows-critical"): ("Platform lane: the windows_ci marker family, which no Linux gate can run."),
    ("packs.yml", "built-in-pack-manifest"): "Packs lane: the pack-manifest guard.",
    ("packs.yml", "built-in-corpus-suite"): "Packs lane: the built-in corpus suite.",
    ("packs.yml", "internal-packaging-safety"): "Packs lane: the wheel-contents guard.",
}

# ---------------------------------------------------------------------------
# >>> WP06 FLIP SEAM -- EXECUTED <<<
#
# WP06 retired the duplicate and emptied THIS CONSTANT (mission
# ``sonar-per-pr-coverage-reuse``, #4334). That turned
# ``test_live_tree_duplicate_set_is_exactly_the_known_set`` from "the rule
# detects exactly the known duplicate" into "the rule finds no duplicate at
# all", i.e. the clean-tree form. The seam is kept, past-tense, because the
# constant is how a NEW duplicate would be declared if one were ever
# deliberately accepted.
#
# WHAT ELSE WP06 HAD TO CHANGE IN THIS MODULE: nothing -- verified, not asserted.
# The claim is cheap to make and was wrong once already (cycle 1 claimed "and
# nothing else" while simulating the WP06 world red 5 tests), so it is stated
# as an enumeration of the things that used to break and why each no longer
# does:
#
#   * The real-file mutations (control, 2, 3a, 3b) used to be anchored on a
#     literal ``ci-quality.yml`` step line and asserted the job name
#     ``sonarcloud``. They now derive both from the live tree via
#     :func:`real_suite_step_host`, which re-binds to a surviving own-text suite
#     step (``ci-windows.yml::windows-critical`` today) when this one goes.
#     Crucially they keep a REAL-FILE substrate after the retirement rather than
#     silently degrading to fixtures.
#   * ``test_mutation1_canonical_retiring_step_is_detected_in_the_live_tree``
#     asserts the retiring job is present, so it cannot survive the retirement.
#     It is ``skipif``-ed on this dict, so emptying the dict retires the test
#     with its subject.
#   * ``test_mutation4_...``'s control compares against this dict, and
#     ``test_known_live_duplicate_rows_still_name_a_real_suite_job`` iterates it;
#     both are already correct over an empty dict.
#
# If a future edit re-anchors anything here on ``ci-quality.yml``, that claim
# stops being true -- re-verify it by simulating the WP06 world (remove the
# suite step from the workflow AND empty this dict) and running the module.
#
# FLIPPED by WP06 (2026-09-14, #4334). The dict is now EMPTY and that is the
# clean-tree assertion: no change-triggered job outside the authorised matrix
# reaches the suite. Between WP04 and WP06 it carried exactly one row --
# ``("ci-quality.yml", "sonarcloud")``, the per-PR SonarCloud reporter that ran
# the whole fast tier a second time (``make test-fast`` under ``pytest --cov``)
# purely to obtain a coverage report the ci-modules shards had already produced.
# That row was the evidence the rule saw REALITY and not only the fixtures
# below; the evidence now lives in the six mutations, four of which run against
# a REAL workflow file derived from the live tree (:func:`real_suite_step_host`)
# rather than against this dict.
#
# ADDING a row here is how a *deliberate, reasoned* duplicate is declared, not
# how one is excused: every row needs a rationale
# (:func:`test_known_live_duplicate_rows_still_name_a_real_suite_job`) and must
# name a job the rule actually finds, so a stale row cannot make the
# characterisation vacuous.
# ---------------------------------------------------------------------------
KNOWN_LIVE_DUPLICATES: dict[JobKey, str] = {}

ACTIONS_DIR = gc.REPO_ROOT / ".github" / "actions"


# ---------------------------------------------------------------------------
# Pure relations
# ---------------------------------------------------------------------------


def normalized_triggers(data: dict[Any, Any]) -> dict[str, Any] | None:
    """A workflow's ``on:`` block as ``event -> config``, or ``None`` if unreadable.

    GitHub accepts three spellings -- a mapping, a list (``on: [push,
    pull_request]``) and a bare string (``on: push``) -- and YAML 1.1 parses the
    bare key ``on`` as the boolean ``True``, so the block also arrives under
    either key depending on the loader's mood. The parameter is therefore
    ``dict[Any, Any]`` and not ``dict[str, Any]``: a parsed workflow genuinely
    does NOT have string keys throughout, and annotating it as if it did made
    the ``data.get(True)`` lookup below an overload error under ``mypy
    --strict`` (WP06/T029b -- no CI workflow runs mypy, so a green pipeline was
    never evidence this was fine).

    ``None`` means "this module does not understand the block". It is NOT the
    same as "the block declares nothing": :func:`change_triggered` resolves it
    to *visible*, never to *skipped*.
    """
    section = data.get("on", data.get(True))
    if isinstance(section, dict):
        return {str(event): config for event, config in section.items()}
    if isinstance(section, str):
        return {section: None}
    if isinstance(section, list) and all(isinstance(item, str) for item in section):
        return dict.fromkeys(section)
    return None


def push_is_per_change(config: Any) -> bool:
    """Whether an ``on.push`` configuration fires per change.

    Only a tags-only push is exempt. A bare ``push:``, a ``push:`` filtered by
    branches or paths, and a ``push:`` of an unrecognised shape all fire per
    change -- the last by the same fail-closed rule as everything else here.
    """
    if not isinstance(config, dict):
        return True
    if any(config.get(key) for key in PER_CHANGE_PUSH_FILTERS):
        return True
    return not config.get("tags")


def change_triggered(path: Path) -> bool:
    """Whether *path* runs once per change -- FAILING CLOSED on anything unfamiliar.

    A workflow that is not change-triggered is invisible to every assertion in
    this module, so "I could not classify this" must resolve to *visible*. The
    workflow is excluded only when EVERY event it declares is a known
    non-per-change event (:data:`NON_CHANGE_TRIGGER_EVENTS`, plus a tags-only
    push); one unrecognised event, an unparseable ``on:`` block or no ``on:``
    block at all puts it back in scope.
    """
    data = gc.load_spliced_workflow(path)
    events = normalized_triggers(data) if isinstance(data, dict) else None
    if not events:
        return True
    return any(push_is_per_change(config) if event == "push" else event not in NON_CHANGE_TRIGGER_EVENTS for event, config in events.items())


def enumerate_workflows(workflows_dir: Path) -> list[Path]:
    """Every workflow file in *workflows_dir*, read from the DIRECTORY.

    Not from a closed list. ``_gate_coverage.WORKFLOW_FILES`` is an allowlist of
    files known to run the suite; a net-new file is by definition not in it, and
    a rule anchored to it would exempt exactly the case mutation 4 injects.
    """
    return sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml"))


def suite_executing_jobs(workflows_dir: Path, *, makefile: Path | None = None) -> dict[JobKey, int]:
    """Change-triggered jobs that execute the suite -> how many times each does.

    Detection is delegated wholesale to ``_gate_coverage.parse_workflow``: a
    directly-anchored ``pytest``, a ``make`` target whose recipe reaches pytest,
    and an in-repo shell script that reaches pytest all count identically. That
    is what makes mutations 1-3 the same finding in three costumes.
    """
    counts: dict[JobKey, int] = {}
    for path in enumerate_workflows(workflows_dir):
        if not change_triggered(path):
            continue
        for gate in gc.parse_workflow(path, makefile=makefile):
            key = (path.name, gate.job)
            counts[key] = counts.get(key, 0) + 1
    return counts


def unauthorized_suite_jobs(workflows_dir: Path, *, makefile: Path | None = None) -> dict[JobKey, int]:
    """Suite-executing jobs outside the authorised matrix -- the duplicates."""
    return {key: count for key, count in suite_executing_jobs(workflows_dir, makefile=makefile).items() if key not in AUTHORIZED_PER_CHANGE_SUITE_JOBS}


def top_level_conjuncts(condition: str | bool | None) -> list[str]:
    """A job ``if:`` expression split into its top-level ``&&`` terms."""
    if not isinstance(condition, str):
        return []
    return gc.split_top_level(gc.normalize_condition(condition), "&&")


# Contract §C1 conjunct 2 (FR-011 / NFR-004 / C-003): the triggering run's head
# repository must equal this repository. Secret withholding no longer provides
# this guarantee once the report is produced from a workflow_run chain, and
# `source.json` carries no origin field -- so this conjunct IS the control.
HEAD_REPOSITORY_REF = "github.event.workflow_run.head_repository.full_name"
THIS_REPOSITORY_REF = "github.repository"

NON_BLOCKING_JOB_LEVEL = "job-level continue-on-error"
NON_BLOCKING_VERDICT_EXCLUSION = "terminal-verdict exclusion"


def same_origin_conjunct(condition: str | bool | None) -> str | None:
    """The same-origin term of *condition*, or ``None`` if it is absent or weakened.

    Required shape: a top-level ``&&`` conjunct asserting equality between the
    triggering run's head repository and this one. A term reached only through
    an ``||`` does not gate anything -- ``A && (origin_ok || anything)`` is
    ``A`` -- so a conjunct containing a top-level ``||``, or an inequality, is
    not the guarantee and is reported as absent.
    """
    for conjunct in top_level_conjuncts(condition):
        if HEAD_REPOSITORY_REF not in conjunct or THIS_REPOSITORY_REF not in conjunct:
            continue
        # Strip the redundant parens a weakened `(A || B)` term carries, or the
        # `||` inside it stays at paren depth 1 and the split sees one part.
        if "!=" in conjunct or len(gc.split_top_level(gc.normalize_condition(conjunct), "||")) > 1:
            continue
        return conjunct
    return None


def condition_uses_always(condition: str | bool | None) -> bool:
    """Whether *condition* contains ``always()`` -- prohibited on the reporting job.

    Contract §C1: the sibling change-coverage gate pairs ``always()`` with an
    internal re-check; copying the shape without the re-check publishes a
    partial figure that reads as a coverage regression.
    """
    return isinstance(condition, str) and "always()" in gc.normalize_condition(condition)


def missing_non_blocking_declarations(path: Path, job: str, *, verdict_job: str) -> frozenset[str]:
    """Which of the two *declarable* non-blocking guarantees (§C4) *job* lacks.

    The third surface -- branch protection -- is outside the repository and is
    declared, never claimed, so no test pins it.
    """
    data = gc.load_spliced_workflow(path)
    jobs = data.get("jobs") or {}
    if job not in jobs:
        message = f"{path.name}: job {job!r} does not exist; the fixture or the wiring has drifted"
        raise AssertionError(message)
    missing: set[str] = set()
    # A literal ``true`` only: ``continue-on-error: ${{ <expr> }}`` is a
    # conditional guarantee, which is not the guarantee.
    if jobs[job].get("continue-on-error") is not True:
        missing.add(NON_BLOCKING_JOB_LEVEL)
    if job in gc.load_workflow_model(path).job_needs.get(verdict_job, ()):
        missing.add(NON_BLOCKING_VERDICT_EXCLUSION)
    return frozenset(missing)


# ---------------------------------------------------------------------------
# Fixtures: synthetic workflows (mutations 4-6) and real-file mutation helpers
# ---------------------------------------------------------------------------

# Mutation 4's payload. Change-triggered, and it reaches the suite through the
# repository's own make target, so only a directory read can find it.
NET_NEW_DUPLICATE_WORKFLOW = """\
name: coverage reporter
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - run: make test-fast
"""
NET_NEW_WORKFLOW_NAME = "ci-coverage-reporter.yml"
NET_NEW_JOB: JobKey = (NET_NEW_WORKFLOW_NAME, "report")

# The same planted duplicate, wearing a different trigger spelling each time.
# Every one of these classified as NOT change-triggered under the previous
# per-change *allow*-list, which dropped the workflow out of every assertion in
# this module -- so the duplicate was invisible without anyone touching a ledger.
EVASION_WORKFLOW_NAME = "ci-evasion.yml"
EVASION_JOB: JobKey = (EVASION_WORKFLOW_NAME, "report")
EVASION_JOB_BODY = """\
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - run: make test-fast
"""
EVASIVE_TRIGGER_BLOCKS: dict[str, str] = {
    "list form": "on: [push, pull_request]",
    "bare scalar push": "on: push",
    "pull_request_target": "on:\n  pull_request_target:\n    types: [opened, synchronize]",
    "merge_group": "on:\n  merge_group:",
    "push filtered by paths": "on:\n  push:\n    paths:\n      - 'src/**'",
    "push with branches-ignore": "on:\n  push:\n    branches-ignore:\n      - gh-pages",
    "event this module has never heard of": "on:\n  some_future_event:\n    types: [created]",
    "malformed trigger block": "on: 42",
    "no trigger block at all": "",
}

# The other half of the closed world: forms that must STAY excluded, or the
# inversion has simply traded a fail-open classifier for a useless one.
LEGITIMATE_NON_CHANGE_BLOCKS: dict[str, str] = {
    "schedule + dispatch": "on:\n  schedule:\n    - cron: '17 3 * * *'\n  workflow_dispatch:",
    "tags-only push": "on:\n  push:\n    tags:\n      - 'v*.*.*'",
    "reusable workflow_call": "on:\n  workflow_call:\n    inputs:\n      module:\n        type: string",
}


def write_triggered_duplicate(workflows_dir: Path, trigger_block: str) -> Path:
    """A workflow carrying *trigger_block* over one planted suite execution."""
    path = workflows_dir / EVASION_WORKFLOW_NAME
    path.write_text(f"name: planted\n{trigger_block}\n{EVASION_JOB_BODY}", encoding="utf-8")
    return path


# Mutation 3's second costume: two hops of make delegation, target names sharing
# nothing with the live ones, selection hidden behind make variables. Only real
# recipe expansion recovers it.
INDIRECTION_MAKEFILE = """\
.PHONY: publish-report inner-tier

TIER_DIRS := tests/unit tests/status
TIER_MARKERS = (fast or unit) and not slow

publish-report:
\tmkdir -p out/reports
\tmake inner-tier

inner-tier:
\tuv run --frozen pytest $(TIER_DIRS) -m "$(TIER_MARKERS)" -n auto -q
"""

# #4367 form 2's payload: recipe-level delegation through the ``$(MAKE)``
# variable (the idiomatic GNU sub-make spelling), reached from a renamed
# outer target. The delegation hop is only recoverable if ``MAKE`` is seeded
# in the model's variable table.
MAKE_VAR_MAKEFILE = """\
.PHONY: report inner-tier

report:
\t$(MAKE) inner-tier

inner-tier:
\tuv run --frozen pytest tests/unit -m fast
"""

# The same delegation spelled the other two ways: brace form and the literal
# command word. All three must resolve IDENTICALLY — the model follows the
# hop, not the spelling.
MAKE_BRACE_MAKEFILE = MAKE_VAR_MAKEFILE.replace("$(MAKE)", "${MAKE}")
LITERAL_MAKE_MAKEFILE = MAKE_VAR_MAKEFILE.replace("$(MAKE)", "make")

# #4367 form 3's payload: the suite execution wrapped in a single-quoted
# ``sh -c`` payload, reached through a make target inside the wrapper.
SHELL_WRAPPER_WORKFLOW = """\
name: wrapped reporter
on:
  pull_request:
    types: [opened, synchronize]
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - run: bash -c 'make test-fast'
"""

# #4367 form 1's payload: the suite execution planted inside a local
# composite action, where GitHub (and, since #4367, the model) splices it
# into the calling job.
HIDDEN_TIER_ACTION = """\
name: hidden tier
description: a composite action that runs the suite where only a splicing model can look
runs:
  using: composite
  steps:
    - shell: bash
      run: uv run --frozen pytest tests/unit -m fast
"""

# The same suite execution behind TWO hops of local composite action — the
# outer action's own ``uses:`` must be followed for the inner one to be seen.
NESTED_ACTION_INNER = HIDDEN_TIER_ACTION
NESTED_ACTION_OUTER = """\
name: outer
description: a composite action that delegates to another local action
runs:
  using: composite
  steps:
    - uses: ./.github/actions/inner-tier
"""

# Negative control for form 1: an action that builds the environment and runs
# no tests. Splicing must not turn its ``uv sync`` into a gate.
SETUP_ACTION = """\
name: setup
description: a composite action that builds the environment and runs no tests
runs:
  using: composite
  steps:
    - shell: bash
      run: uv sync --frozen --all-extras
"""

# Runner forms that #4367 taught the prefix table to strip: each reaches
# pytest through a runner that previously parsed as "no pytest command here".
RUNNER_PREFIX_LINES: tuple[str, ...] = (
    "coverage run -m pytest tests/unit -m fast",
    "poetry run pytest tests/unit",
    "xvfb-run pytest tests/unit",
    "timeout 600 pytest tests/unit",
    ".venv/bin/pytest tests/unit",
)
RUNNER_PREFIX_WORKFLOW = (
    "name: runner prefixes\n"
    "on:\n  pull_request:\n    types: [opened, synchronize]\n"
    "jobs:\n  report:\n    runs-on: ubuntu-latest\n    steps:\n      - run: |\n" + "".join(f"          {line}\n" for line in RUNNER_PREFIX_LINES)
)

# The runner class that DELIBERATELY stays refused: tox/nox delegate to
# configuration files (tox.ini / noxfile.py) the model does not read, so the
# pytest invocation is not on the workflow line and cannot be resolved — only
# refused.
UNRESOLVED_RUNNER_WORKFLOW = """\
name: delegated runner
on:
  pull_request:
    types: [opened, synchronize]
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - run: tox -e py -- pytest tests/unit
"""

# The control's prose lines are copied from the live tree (ci-modules.yml's
# zero-collection error message, ci-windows.yml's pipx install line).
QUIET_RUNNER_WORKFLOW = """\
name: quiet
on:
  pull_request:
    types: [opened, synchronize]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: |
          pipx inject spec-kitty-cli pytest pytest-cov pytest-asyncio pytest-timeout respx pytestarch
          echo "::error::module-tests: pytest collected zero tests"
          uv run --frozen pytest tests/unit -m fast
"""

# §C1/§C4 shape of the per-change reporting job WP05 builds, reduced to the two
# declarations mutations 5 and 6 remove. `verdict` deliberately does NOT list
# `report` in its `needs:` -- that exclusion IS the workflow-run-conclusion half
# of the non-blocking guarantee.
REPORTING_WORKFLOW_TEMPLATE = """\
name: aggregate
on:
  workflow_run:
    workflows: [ci-modules]
    types: [completed]
jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - run: echo collect
  report:
    needs: [collect]
{continue_on_error}    if: >-
      ${{{{ {condition} }}}}
    runs-on: ubuntu-latest
    steps:
      - run: echo report
  verdict:
    needs: [collect]
    runs-on: ubuntu-latest
    steps:
      - run: echo verdict
"""
CONTINUE_ON_ERROR_LINE = "    continue-on-error: true\n"
SAME_ORIGIN_TERM = f"{HEAD_REPOSITORY_REF} == {THIS_REPOSITORY_REF}"
INTACT_REPORT_CONDITION = (
    "github.event.workflow_run.event == 'pull_request' "
    f"&& {SAME_ORIGIN_TERM} "
    "&& github.event.workflow_run.conclusion == 'success' "
    "&& needs.collect.outputs.complete == 'true'"
)
REPORT_JOB = "report"
VERDICT_JOB = "verdict"


def write_reporting_workflow(
    tmp_path: Path,
    *,
    condition: str = INTACT_REPORT_CONDITION,
    non_blocking: bool = True,
    verdict_needs_report: bool = False,
) -> Path:
    """A synthetic §C1/§C4 reporting workflow, optionally with a declaration removed."""
    text = REPORTING_WORKFLOW_TEMPLATE.format(
        continue_on_error=CONTINUE_ON_ERROR_LINE if non_blocking else "",
        condition=condition,
    )
    if verdict_needs_report:
        text = text.replace(
            "  verdict:\n    needs: [collect]\n",
            "  verdict:\n    needs: [collect, report]\n",
        )
    path = tmp_path / "ci-aggregate.yml"
    path.write_text(text, encoding="utf-8")
    return path


class RealSuiteStep(NamedTuple):
    """A live workflow file that spells a suite execution in its own text."""

    workflow: Path
    job: str
    indent: str
    line: str
    """The raw source line, including its indentation and trailing newline."""
    command: str


def real_suite_step_host(workflows_dir: Path | None = None) -> RealSuiteStep:
    """A LIVE workflow whose own text spells exactly one suite execution.

    Mutations 1-3 rewrite a real workflow file rather than a hand-written
    snippet, because a battery fed exclusively synthetic fixtures reproduces the
    blindness it exists to close. The host is therefore DERIVED rather than
    named: when WP06 retires the duplicate step from ``ci-quality.yml`` this
    selector re-binds to a surviving suite step (today's fallback:
    ``ci-windows.yml::windows-critical``), so the retirement does not turn the
    real-file mutations into fixture mutations or red them.

    Every selection requirement is load-bearing for the mutations below:

    * change-triggered, with exactly ONE suite-executing job running the suite
      exactly once -- so the negative control, which replaces the command with
      ``make lint``, can assert the finding drops to *nothing* rather than to
      "everything except this one";
    * the command must appear in the file's OWN text, exactly once -- a job that
      reaches the suite through a spliced reusable workflow (``ci-modules.yml``
      delegating to ``module-tests.yml``) carries no such line, and a copy of it
      in a temporary directory would not splice;
    * the line must be a bare command inside a block scalar, not a ``- run:``
      flow step, so substituting it cannot corrupt the YAML.

    Raising when nothing qualifies is the replacement for the old hard-coded
    anchor assertion: a tree with no own-text suite step at all would silently
    turn every real-file mutation into a no-op.
    """
    directory = workflows_dir if workflows_dir is not None else gc.WORKFLOWS_DIR
    by_workflow: dict[str, dict[str, int]] = {}
    for (workflow, job), count in suite_executing_jobs(directory).items():
        by_workflow.setdefault(workflow, {})[job] = count

    for path in enumerate_workflows(directory):
        jobs = by_workflow.get(path.name) or {}
        if list(jobs.values()) != [AUTHORIZED_SUITE_INVOCATIONS_PER_JOB]:
            continue
        (job,) = jobs
        text = path.read_text(encoding="utf-8")
        for raw in text.splitlines(keepends=True):
            command = raw.strip()
            if not command or command.startswith(("-", "#")) or "run:" in command:
                continue
            if not gc.suite_invocations(command) or text.count(raw) != 1:
                continue
            return RealSuiteStep(
                workflow=path,
                job=job,
                indent=raw[: len(raw) - len(raw.lstrip())],
                line=raw,
                command=command,
            )

    message = (
        f"no workflow in {directory} spells a suite execution in its own text as the sole "
        "invocation of its sole suite-executing job. The real-file mutations below would be "
        "no-ops — re-derive a host, or fix the enumeration that found nothing."
    )
    raise AssertionError(message)


def mutate_live_suite_step(tmp_path: Path, command: str, *, host: RealSuiteStep | None = None) -> Path:
    """Copy the derived live host workflow, rewriting its suite step as *command*.

    *command* is the bare shell command; the host's own indentation is
    re-applied, so a mutation never encodes the layout of one particular
    workflow file.
    """
    resolved = host if host is not None else real_suite_step_host()
    text = resolved.workflow.read_text(encoding="utf-8")
    occurrences = text.count(resolved.line)
    assert occurrences == 1, f"{resolved.workflow.name}: the derived suite step {resolved.command!r} occurs {occurrences} times; the mutation would be ambiguous"
    path = tmp_path / resolved.workflow.name
    path.write_text(text.replace(resolved.line, f"{resolved.indent}{command}\n"), encoding="utf-8")
    return path


def real_workflows_copy(tmp_path: Path) -> Path:
    """A writable copy of the whole live ``.github/workflows/`` directory."""
    destination = tmp_path / "workflows"
    shutil.copytree(gc.WORKFLOWS_DIR, destination)
    return destination


def jobs_of(path: Path, *, makefile: Path | None = None) -> dict[str, int]:
    """Suite-executing job names in ONE workflow file -> invocation count."""
    return {job: count for (_workflow, job), count in suite_executing_jobs(path.parent, makefile=makefile).items() if _workflow == path.name}


# ---------------------------------------------------------------------------
# T018 — non-vacuity floor
# ---------------------------------------------------------------------------


def test_scanned_workflow_set_is_non_empty_and_carries_the_reporting_host() -> None:
    """§C5 floor: the rule must actually look at something, including the new host.

    Without this, narrowing the scanned set -- a glob that stops matching, a
    trigger classification that excludes everything -- would make every
    assertion in this module silently vacuous while staying green.
    """
    scanned = [path.name for path in enumerate_workflows(gc.WORKFLOWS_DIR)]
    assert scanned, "the workflow enumeration found no files at all — the rule is vacuous"

    change_scoped = {path.name for path in enumerate_workflows(gc.WORKFLOWS_DIR) if change_triggered(path)}
    assert change_scoped, "no workflow classified as change-triggered — the rule is vacuous"
    assert REPORTING_HOST_WORKFLOW in change_scoped, (
        f"{REPORTING_HOST_WORKFLOW} hosts the per-change report (§C5) but is not in the "
        f"change-triggered scan — a duplicate parked there would be invisible. Scanned: {sorted(change_scoped)}"
    )


def test_every_live_workflow_is_classified_and_every_exclusion_is_declared() -> None:
    """The floor that "the set is non-empty" is too weak to provide.

    "Something was scanned" stays true while an arbitrary number of workflows
    are silently dropped — which is precisely how a fail-open trigger classifier
    survives a non-vacuity check. This pins the *exclusion set itself*: exactly
    the declared workflows are out of scope, and nothing reaches the
    fail-closed fallback, so a trigger spelling this module cannot read shows up
    here as a named workflow rather than as silence.
    """
    live = enumerate_workflows(gc.WORKFLOWS_DIR)
    unreadable = sorted(path.name for path in live if normalized_triggers(gc.load_spliced_workflow(path)) is None)
    assert not unreadable, (
        "these workflows' `on:` blocks are in a shape this module cannot read. They are still "
        "scanned (the classifier fails closed), but the classification is a fallback rather than "
        f"a reading — teach `normalized_triggers` the shape: {unreadable}"
    )

    excluded = {path.name for path in live if not change_triggered(path)}
    assert excluded == set(NON_CHANGE_TRIGGERED_WORKFLOWS), (
        "the set of workflows excluded from the per-change scan changed.\n"
        f"  excluded: {sorted(excluded)}\n"
        f"  declared: {sorted(NON_CHANGE_TRIGGERED_WORKFLOWS)}\n"
        "A NEW exclusion hides a whole workflow from every assertion in this module — justify it "
        "with a row here, or fix the trigger. A MISSING one means the workflow is now in scope: "
        "delete its row."
    )

    unreasoned = sorted(name for name, why in NON_CHANGE_TRIGGERED_WORKFLOWS.items() if not why.strip())
    assert not unreasoned, f"declared exclusions with an empty rationale: {unreasoned}"


@pytest.mark.parametrize(("spelling", "trigger_block"), sorted(EVASIVE_TRIGGER_BLOCKS.items()))
def test_faultinjection_evasive_trigger_spellings_stay_in_scope(tmp_path: Path, spelling: str, trigger_block: str) -> None:
    """One planted duplicate, nine trigger spellings, zero escapes.

    Each of these walked past the previous per-change allow-list, and the list
    form is the most ordinary spelling in GitHub Actions — no adversary
    required. Asserting classification alone would be too weak, so each case
    also checks the planted execution is actually *reported* as unauthorised.
    """
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    path = write_triggered_duplicate(workflows, trigger_block)

    assert change_triggered(path), f"{spelling}: classified as not-per-change — the workflow is invisible to every assertion in this module"
    assert EVASION_JOB in unauthorized_suite_jobs(workflows), f"{spelling}: classified in scope but the planted duplicate was not reported"


@pytest.mark.parametrize(("spelling", "trigger_block"), sorted(LEGITIMATE_NON_CHANGE_BLOCKS.items()))
def test_legitimate_non_change_triggers_stay_excluded(tmp_path: Path, spelling: str, trigger_block: str) -> None:
    """Negative control: failing closed must not mean flagging everything.

    Without these, ``change_triggered`` could satisfy every case above by
    returning ``True`` unconditionally — a rule that classifies nothing.
    """
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    path = write_triggered_duplicate(workflows, trigger_block)

    assert not change_triggered(path), f"{spelling}: a non-per-change trigger was pulled into the per-change scan"
    assert unauthorized_suite_jobs(workflows) == {}


def test_every_authorized_ledger_row_still_names_a_live_suite_job() -> None:
    """The ledger may not outlive its subject.

    A row whose job has been renamed or deleted is a standing, unreviewed
    exemption: the next job to take that name inherits the authorisation.
    """
    live = suite_executing_jobs(gc.WORKFLOWS_DIR)
    stale = sorted(key for key in AUTHORIZED_PER_CHANGE_SUITE_JOBS if key not in live)
    assert not stale, f"AUTHORIZED_PER_CHANGE_SUITE_JOBS rows no longer name a live suite job — delete them: {stale}"

    unreasoned = sorted(key for key, why in AUTHORIZED_PER_CHANGE_SUITE_JOBS.items() if not why.strip())
    assert not unreasoned, f"authorised rows with an empty rationale: {unreasoned}"


def test_no_authorized_job_executes_the_suite_more_than_once() -> None:
    """The cheapest evasion for someone who has read the ledger.

    Appending one more ``run:`` step to an ALREADY-authorised job reintroduces
    the duplicate without touching the ledger at all. Membership authorises one
    execution, not a budget.
    """
    live = suite_executing_jobs(gc.WORKFLOWS_DIR)
    repeated = {key: count for key, count in live.items() if key in AUTHORIZED_PER_CHANGE_SUITE_JOBS and count > AUTHORIZED_SUITE_INVOCATIONS_PER_JOB}
    assert not repeated, f"authorised jobs executing the suite more than once: {repeated}"


def test_repeated_suite_step_in_an_authorized_job_is_detected(tmp_path: Path) -> None:
    """Fault injection for the guard above, on a copy of the real workflow tree."""
    workflows = real_workflows_copy(tmp_path)
    router = workflows / "ci-router.yml"
    text = router.read_text(encoding="utf-8")
    anchor = "  terminology:\n"
    assert anchor in text, "ci-router.yml no longer declares a `terminology:` job — re-anchor this injection"
    router.write_text(
        text.replace(
            anchor,
            "  terminology-extra:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make test-fast\n" + anchor,
        ),
        encoding="utf-8",
    )
    # A NEW job in an existing authorised workflow is the workflow-granular
    # ledger's blind spot; the (workflow, job) key catches it.
    assert ("ci-router.yml", "terminology-extra") in unauthorized_suite_jobs(workflows)


# ---------------------------------------------------------------------------
# T019 — mutations 1-3
# ---------------------------------------------------------------------------


def test_mutation1_the_live_suite_step_is_detected_through_its_own_spelling() -> None:
    """Mutation 1, proven against LIVE source rather than a fixture.

    The permanent half: whatever the tree's own-text suite step is today, the
    job that carries it is detected, and the job-level detection agrees term for
    term with resolving that raw command line on its own. A rule that found the
    job by name, or that resolved the line differently from the job, fails here.

    This survives WP06 by construction -- the host is derived, so retiring one
    suite step re-binds it rather than redding this.
    """
    live = suite_executing_jobs(gc.WORKFLOWS_DIR)
    host = real_suite_step_host()
    assert (host.workflow.name, host.job) in live, (
        f"{host.workflow.name}::{host.job} spells {host.command!r} in its own text but the rule "
        "did not see it — the detection is blind to a form the live tree uses"
    )

    expected_via = [invocation.via for invocation in gc.suite_invocations(host.command)]
    assert expected_via, f"the derived host {host.command!r} no longer resolves to a suite invocation"
    gates = [gate for gate in gc.parse_workflow(host.workflow) if gate.job == host.job]
    assert [gate.via for gate in gates] == expected_via, (
        f"{host.workflow.name}::{host.job} resolves differently at job level than its raw command line does: {[gate.via for gate in gates]} vs {expected_via}"
    )


@pytest.mark.skipif(
    RETIRING_JOB not in KNOWN_LIVE_DUPLICATES,
    reason="WP06 retired the duplicate; live-tree detection is carried by the derived-host mutation above",
)
def test_mutation1_canonical_retiring_step_is_detected_in_the_live_tree() -> None:
    """The sunsetting half: the duplicate's CANONICAL form, in the live tree.

    This work package is sequenced before the retirement for exactly this
    assertion: the canonical form of the duplicate -- a ``make`` target
    delegation -- is still in the tree, so the rule can be shown to catch it
    there. Demonstrating mutation 1 on a synthetic snippet would have made the
    sequencing worthless.

    It retires with its subject. Emptying ``KNOWN_LIVE_DUPLICATES`` skips it,
    so the WP06 flip needs no edit here.
    """
    live = suite_executing_jobs(gc.WORKFLOWS_DIR)
    assert RETIRING_JOB in live, (
        f"{RETIRING_JOB} runs the fast tier through a make target but the rule did not see it — the detection is blind to the very form the duplicate uses"
    )
    gates = [gate for gate in gc.parse_workflow(gc.WORKFLOWS_DIR / CI_QUALITY_NAME) if gate.job == RETIRING_JOB[1]]
    assert [gate.via for gate in gates] == [RETIRING_JOB_VIA]


def test_mutation_control_removing_the_suite_step_clears_the_finding(tmp_path: Path) -> None:
    """Negative control for mutations 2 and 3: detection follows the COMMAND.

    Without this twin, a rule that flagged the host job by name would pass every
    mutation below while proving nothing about form.
    """
    mutated = mutate_live_suite_step(tmp_path, "make lint")
    assert jobs_of(mutated) == {}


def test_mutation2_inlined_suite_command_is_detected(tmp_path: Path) -> None:
    """Mutation 2, on a copy of the REAL workflow file.

    The shared make target is gone; the selection is written out longhand. A
    rule keyed on the literal string ``make test-fast`` sees nothing here.
    """
    host = real_suite_step_host()
    mutated = mutate_live_suite_step(
        tmp_path,
        'uv run --frozen pytest tests/unit tests/status -m "(fast or unit) and not slow" -n auto -q',
        host=host,
    )
    assert jobs_of(mutated) == {host.job: 1}
    gate = next(gate for gate in gc.parse_workflow(mutated) if gate.job == host.job)
    assert gate.via is None, "an inlined command must be recorded as directly anchored"
    assert gate.paths == ["tests/unit", "tests/status"]


def test_mutation3_script_wrapper_is_detected(tmp_path: Path) -> None:
    """Mutation 3a, on a copy of the REAL workflow file: an invoked shell script.

    Defeats both a literal-string rule and one that only reads make targets --
    the workflow now mentions neither pytest nor make.
    """
    wrapper = "scripts/repro_3115_render_width.sh"
    assert (gc.REPO_ROOT / wrapper).is_file(), f"{wrapper} is the in-repo script this injection wraps; it has moved"
    host = real_suite_step_host()
    mutated = mutate_live_suite_step(tmp_path, f"bash {wrapper}", host=host)
    assert jobs_of(mutated) == {host.job: 1}
    gate = next(gate for gate in gc.parse_workflow(mutated) if gate.job == host.job)
    assert gate.via == f"script {wrapper}"


def test_mutation3_make_delegation_hop_is_detected(tmp_path: Path) -> None:
    """Mutation 3b: one more hop of indirection, behind renamed targets and variables.

    Nothing here shares a name with ``test-fast``; the paths and marker live in
    make variables. Only expanding the real recipe recovers the invocation.
    """
    makefile = tmp_path / "Makefile"
    makefile.write_text(INDIRECTION_MAKEFILE, encoding="utf-8")
    host = real_suite_step_host()
    mutated = mutate_live_suite_step(tmp_path, "make publish-report", host=host)

    assert jobs_of(mutated, makefile=makefile) == {host.job: 1}
    gate = next(gate for gate in gc.parse_workflow(mutated, makefile=makefile) if gate.job == host.job)
    assert gate.via == "make inner-tier"
    assert gate.paths == ["tests/unit", "tests/status"]
    assert gate.marker_expr == "(fast or unit) and not slow"


# ---------------------------------------------------------------------------
# T020 — mutation 4: a net-new workflow file
# ---------------------------------------------------------------------------


def test_mutation4_net_new_workflow_file_is_detected(tmp_path: Path) -> None:
    """A closed candidate list cannot see a file that did not exist when it was written.

    The control half matters as much as the mutation: it pins that the red is
    caused by the new file and not by a parse error introduced when the tree was
    copied.
    """
    workflows = real_workflows_copy(tmp_path)
    before = unauthorized_suite_jobs(workflows)
    assert before == dict.fromkeys(KNOWN_LIVE_DUPLICATES, AUTHORIZED_SUITE_INVOCATIONS_PER_JOB), (
        "control: an unmutated copy of the live tree must reproduce the live finding exactly"
    )

    (workflows / NET_NEW_WORKFLOW_NAME).write_text(NET_NEW_DUPLICATE_WORKFLOW, encoding="utf-8")
    after = unauthorized_suite_jobs(workflows)

    assert set(after) - set(before) == {NET_NEW_JOB}
    assert NET_NEW_WORKFLOW_NAME not in gc.WORKFLOW_FILES, (
        "the injected file is deliberately absent from the closed model allowlist — "
        "if it were listed, this mutation would prove nothing about directory enumeration"
    )


# ---------------------------------------------------------------------------
# T021 — mutations 5-6: removal of the advisory declarations
#
# The per-change reporting job is built by WP05, so these run against a
# synthetic workflow carrying §C1/§C4's declarations. WP05 binds the same two
# predicates to the real job.
# ---------------------------------------------------------------------------


def test_intact_reporting_job_satisfies_both_declarations(tmp_path: Path) -> None:
    """Baseline: with both declarations present, neither relation reports a violation."""
    path = write_reporting_workflow(tmp_path)
    assert missing_non_blocking_declarations(path, REPORT_JOB, verdict_job=VERDICT_JOB) == frozenset()
    assert same_origin_conjunct(gc.load_workflow_model(path).job_if[REPORT_JOB]) == SAME_ORIGIN_TERM
    assert not condition_uses_always(gc.load_workflow_model(path).job_if[REPORT_JOB])


def test_mutation5a_removing_job_level_non_blocking_is_detected(tmp_path: Path) -> None:
    """Mutation 5, first surface: the job may fail the change (NFR-007).

    Today this removal reds nothing — ``continue-on-error`` appears in the test
    tree only inside prose rationales, never as a live assertion.
    """
    path = write_reporting_workflow(tmp_path, non_blocking=False)
    assert missing_non_blocking_declarations(path, REPORT_JOB, verdict_job=VERDICT_JOB) == {NON_BLOCKING_JOB_LEVEL}


def test_mutation5b_admitting_the_report_to_the_verdict_is_detected(tmp_path: Path) -> None:
    """Mutation 5, second surface: the terminal verdict starts blocking on the report.

    ``continue-on-error`` keeps the JOB green but not the workflow-run
    conclusion the aggregate verdict reads, so the exclusion is a separate,
    separately-removable guarantee (§C4).
    """
    path = write_reporting_workflow(tmp_path, verdict_needs_report=True)
    assert missing_non_blocking_declarations(path, REPORT_JOB, verdict_job=VERDICT_JOB) == {NON_BLOCKING_VERDICT_EXCLUSION}


def test_mutation6_removing_the_same_origin_conjunct_is_detected(tmp_path: Path) -> None:
    """Mutation 6: the mission's principal security-relevant change.

    Withheld secrets no longer provide same-origin; this conjunct replaces a
    platform-enforced guarantee with a condition-enforced one, so its silent
    removal must be impossible (FR-011 / SC-008).
    """
    path = write_reporting_workflow(tmp_path, condition=INTACT_REPORT_CONDITION.replace(f"&& {SAME_ORIGIN_TERM} ", ""))
    assert same_origin_conjunct(gc.load_workflow_model(path).job_if[REPORT_JOB]) is None


def test_mutation6_weakening_the_same_origin_conjunct_is_detected(tmp_path: Path) -> None:
    """The conjunct's *presence* is not the guarantee; it must still gate.

    ``A && (origin_ok || fork_ok)`` keeps every token a string search would look
    for while admitting forks, which is the evasion a text-matching rule invites.
    """
    weakened = INTACT_REPORT_CONDITION.replace(
        SAME_ORIGIN_TERM,
        f"({SAME_ORIGIN_TERM} || github.event.workflow_run.event == 'push')",
    )
    path = write_reporting_workflow(tmp_path, condition=weakened)
    assert same_origin_conjunct(gc.load_workflow_model(path).job_if[REPORT_JOB]) is None


def test_always_on_the_reporting_job_is_detected(tmp_path: Path) -> None:
    """§C1: ``always()`` is prohibited on this job.

    The sibling change-coverage gate pairs it with an internal re-check; ported
    without that re-check it publishes a partial figure that reads as a coverage
    regression.
    """
    path = write_reporting_workflow(tmp_path, condition=f"always() && {INTACT_REPORT_CONDITION}")
    assert condition_uses_always(gc.load_workflow_model(path).job_if[REPORT_JOB])


# ---------------------------------------------------------------------------
# T022 — characterise the live tree (see the WP06 FLIP SEAM above)
# ---------------------------------------------------------------------------


def test_live_tree_duplicate_set_is_exactly_the_known_set() -> None:
    """The rule, run against REALITY, finds exactly the duplicates we know about.

    ``KNOWN_LIVE_DUPLICATES`` is now empty, so this is the **clean-tree form**:
    no duplicate per-change suite execution anywhere in ``.github/workflows/``.
    It passes by finding nothing, and that is correct — the duplicate it was
    written to characterise was retired by WP06 (mission
    ``sonar-per-pr-coverage-reuse``, #4334).

    That makes "passes by finding nothing" ambiguous on its own, which is why
    it is **not** load-bearing here: the rule's non-vacuity rests on
    :func:`real_suite_step_host`, which re-binds to a live workflow that still
    spells a suite execution in its own text and *raises* rather than degrading
    to fixtures if none exists. Re-injecting a suite step into any
    change-triggered workflow reds this assertion again.

    Before the retirement this read as a characterisation ("it passes *because*
    the rule detects the still-present duplicate"). Recording the change of
    meaning rather than deleting it: an assertion whose truth condition
    inverted is exactly the kind of thing a later reader must not have to
    reconstruct.
    """
    found = unauthorized_suite_jobs(gc.WORKFLOWS_DIR)
    assert set(found) == set(KNOWN_LIVE_DUPLICATES), (
        "per-change suite executions outside the authorised matrix changed.\n"
        f"  found   : {sorted(found)}\n"
        f"  expected: {sorted(KNOWN_LIVE_DUPLICATES)}\n"
        "A NEW entry is a duplicate suite execution — the defect this gate exists to prevent.\n"
        "A MISSING entry means the duplicate was retired: delete its KNOWN_LIVE_DUPLICATES row "
        "in the same commit (this is the WP06 flip)."
    )


def test_known_live_duplicate_rows_still_name_a_real_suite_job() -> None:
    """The seam cannot outlive its subject, and cannot be padded.

    A row that names a job which does not run the suite would let the
    characterisation above pass while the rule sees nothing — the exact vacuity
    this work package exists to rule out.
    """
    live = suite_executing_jobs(gc.WORKFLOWS_DIR)
    ghosts = sorted(key for key in KNOWN_LIVE_DUPLICATES if key not in live)
    assert not ghosts, (
        f"KNOWN_LIVE_DUPLICATES rows that no longer name a live suite-executing job: {ghosts}. Delete them — a stale row makes the characterisation vacuous."
    )
    unreasoned = sorted(key for key, why in KNOWN_LIVE_DUPLICATES.items() if not why.strip())
    assert not unreasoned, f"KNOWN_LIVE_DUPLICATES rows with an empty rationale: {unreasoned}"


# ---------------------------------------------------------------------------
# Former escape hatches — resolved by widening `_gate_coverage` (#4367)
#
# WP04 refused the forms below outright because the model could not see them
# and widening it was outside that work package's ownership. #4367 widened
# the model: composite actions are spliced into the calling job (with nested
# local actions followed), `$(MAKE)` is seeded in the variable table, a
# whole `sh -c '<command>'` wrapper is unwrapped, and the runner-prefix
# table strips `coverage run` / the poetry family / `xvfb-run` / `timeout N`
# / `<path>/pytest` / `<path>/python -m`. The refusing guards are retired
# with the blindness; what replaces them is this battery's own discipline:
# a planted suite execution behind each form is DETECTED (attributed to the
# job that runs it, so the authorised-count and duplicate assertions see
# it), and a clean negative control is not.
# ---------------------------------------------------------------------------


def composite_action_files(actions_dir: Path) -> list[Path]:
    """Every local composite action definition under *actions_dir*."""
    if not actions_dir.is_dir():
        return []
    return sorted(actions_dir.glob("*/action.yml")) + sorted(actions_dir.glob("*/action.yaml"))


def _composite_run_lines(action: Path) -> list[str]:
    """Logical shell lines of a composite action's ``runs.steps[].run`` scripts."""
    data = yaml.safe_load(action.read_text(encoding="utf-8")) or {}
    steps = ((data.get("runs") or {}).get("steps")) or []
    lines: list[str] = []
    for step in steps:
        if isinstance(step, dict) and isinstance(step.get("run"), str):
            lines.extend(gc.join_continuations(step["run"]))
    return lines


@pytest.mark.parametrize(
    ("spelling", "makefile_text"),
    [
        ("$(MAKE) variable", MAKE_VAR_MAKEFILE),
        ("${MAKE} brace form", MAKE_BRACE_MAKEFILE),
        ("literal make", LITERAL_MAKE_MAKEFILE),
    ],
)
def test_faultinjection_make_delegation_hop_is_resolved(tmp_path: Path, spelling: str, makefile_text: str) -> None:
    """#4367 form 2: ``$(MAKE) <target>`` resolves exactly like ``make <target>``.

    ``makefile_target_invocations`` claims to follow recipe-level delegation
    "so that inserting one more hop of indirection is not an escape hatch" —
    and ``$(MAKE)`` is the idiomatic GNU spelling of exactly that hop. All
    three spellings must resolve identically, or the docstring's claim is
    false again.
    """
    makefile = tmp_path / "Makefile"
    makefile.write_text(makefile_text, encoding="utf-8")
    workflow = tmp_path / "ci-var.yml"
    workflow.write_text(
        "on:\n  pull_request:\n    types: [opened, synchronize]\njobs:\n  report:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make report\n",
        encoding="utf-8",
    )

    assert jobs_of(workflow, makefile=makefile) == {"report": 1}, spelling
    gate = next(gate for gate in gc.parse_workflow(workflow, makefile=makefile))
    assert gate.via == "make inner-tier", spelling
    assert gate.paths == ["tests/unit"], spelling
    assert gate.marker_expr == "fast", spelling


def test_faultinjection_make_delegation_without_pytest_stays_quiet(tmp_path: Path) -> None:
    """Negative control: delegation that does not reach the suite is not a gate."""
    makefile = tmp_path / "Makefile"
    makefile.write_text(
        ".PHONY: report lint-tier\n\nreport:\n\t$(MAKE) lint-tier\n\nlint-tier:\n\truff check .\n",
        encoding="utf-8",
    )
    workflow = tmp_path / "ci-lint.yml"
    workflow.write_text(
        "on:\n  pull_request:\n    types: [opened, synchronize]\njobs:\n  report:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make report\n",
        encoding="utf-8",
    )

    assert jobs_of(workflow, makefile=makefile) == {}


def test_faultinjection_shell_dash_c_wrapper_is_resolved(tmp_path: Path) -> None:
    """#4367 form 3: a suite execution wrapped in ``sh -c '...'`` is detected.

    The wrapper's payload is reached as one command, whatever indirection it
    uses — a make target here. Without unwrapping, the workflow mentions
    neither pytest nor make and every assertion in this module is blind to it.
    """
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "ci-wrapped.yml").write_text(SHELL_WRAPPER_WORKFLOW, encoding="utf-8")

    assert unauthorized_suite_jobs(workflows) == {("ci-wrapped.yml", "report"): 1}
    gate = next(gate for gate in gc.parse_workflow(workflows / "ci-wrapped.yml") if gate.job == "report")
    assert gate.via == "make test-fast"


@pytest.mark.parametrize(
    ("spelling", "command"),
    [
        ("double quotes", 'bash -c "coverage run -m pytest tests/unit -m fast"'),
        ("sh with combined flags", 'sh -ec "pytest tests/unit"'),
        ("options before -c", 'bash -e -c "pytest tests/unit"'),
        ("mid-line segment", 'echo hi && bash -c "pytest tests/unit"'),
        ("operators inside the payload", 'bash -c "make lint && make test-fast"'),
        ("sibling command after the wrapper", 'bash -c "make lint" && make test-fast'),
        ("two wrappers on one line, semicolon", "bash -c 'make lint'; bash -c 'pytest tests/unit -m fast'"),
        ("two wrappers on one line, double quotes", 'bash -c "make lint" && bash -c "pytest tests/unit"'),
        ("runner-prefixed wrapper", 'xvfb-run bash -c "pytest tests/unit"'),
    ],
)
def test_faultinjection_shell_dash_c_spellings_resolve(tmp_path: Path, spelling: str, command: str) -> None:
    """Every wrapper spelling unwraps to the invocation inside it.

    Whole-line wrappers (including a payload carrying ``&&``, which the shell
    splitter would tear apart mid-quote), segment-level wrappers, and a
    wrapper behind a runner prefix all resolve to exactly the suite
    execution they run — never zero, and never a path-less over-claim. A
    line carrying TWO wrappers declines the whole-line unwrap (the payload
    is quote-exclusive and cannot cross the first closing quote) and is
    unwrapped segment-by-segment instead, so the second wrapper's execution
    is seen rather than swallowed into an unparseable payload.
    """
    invocations = gc.suite_invocations(command)
    assert invocations, f"{spelling}: {command!r} resolved to no suite invocation"
    assert all(invocation.paths for invocation in invocations), spelling


def test_faultinjection_shell_dash_c_without_pytest_stays_quiet(tmp_path: Path) -> None:
    """Negative control: a wrapper around a non-suite command is not a gate."""
    assert gc.suite_invocations("bash -c 'make lint'") == []
    assert gc.suite_invocations("bash -c 'ruff check .'") == []


def _write_action(actions_dir: Path, name: str, text: str) -> Path:
    """Write a local composite action definition under *actions_dir*."""
    directory = actions_dir / name
    directory.mkdir(parents=True)
    action = directory / "action.yml"
    action.write_text(text, encoding="utf-8")
    return action


HIDDEN_TIER_CALLER_WORKFLOW = """\
name: action caller
on:
  pull_request:
    types: [opened, synchronize]
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: ./.github/actions/hidden-tier
"""


def test_faultinjection_composite_action_suite_execution_is_attributed_to_the_calling_job(
    tmp_path: Path,
) -> None:
    """#4367 form 1: a suite execution inside a local composite action is seen.

    GitHub splices ``uses: ./.github/actions/<name>`` into the calling job;
    the model now does the same, so the planted execution counts as the
    CALLER's — an unauthorised duplicate, attributed with
    ``via="action <name>"`` so the provenance is reportable.
    """
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "ci-action.yml").write_text(HIDDEN_TIER_CALLER_WORKFLOW, encoding="utf-8")
    actions = tmp_path / "actions"
    _write_action(actions, "hidden-tier", HIDDEN_TIER_ACTION)

    assert unauthorized_suite_jobs(workflows) == {("ci-action.yml", "report"): 1}
    gate = next(gate for gate in gc.parse_workflow(workflows / "ci-action.yml") if gate.job == "report")
    assert gate.via == "action hidden-tier"
    assert gate.paths == ["tests/unit"]
    assert gate.marker_expr == "fast"


def test_faultinjection_nested_composite_action_is_resolved(tmp_path: Path) -> None:
    """Two hops of local composite action, both followed.

    The outer action's own ``uses:`` is spliced before the caller is parsed,
    so the inner action's suite execution is attributed to the calling job.
    """
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "ci-nested.yml").write_text(
        HIDDEN_TIER_CALLER_WORKFLOW.replace("hidden-tier", "outer-tier"),
        encoding="utf-8",
    )
    actions = tmp_path / "actions"
    _write_action(actions, "outer-tier", NESTED_ACTION_OUTER)
    _write_action(actions, "inner-tier", NESTED_ACTION_INNER)

    assert unauthorized_suite_jobs(workflows) == {("ci-nested.yml", "report"): 1}
    gate = next(gate for gate in gc.parse_workflow(workflows / "ci-nested.yml") if gate.job == "report")
    # The INNER action's name: it is the action whose step actually runs.
    assert gate.via == "action inner-tier"


def test_faultinjection_composite_action_make_indirection_is_resolved(tmp_path: Path) -> None:
    """An action step that reaches the suite through a make target, not inline.

    The two resolutions compose: the action is spliced into the caller, and
    its ``make`` step is resolved through the Makefile like any other. The
    gate's ``via`` names the deeper indirection (the make target).
    """
    makefile = tmp_path / "Makefile"
    makefile.write_text(
        ".PHONY: inner-tier\n\ninner-tier:\n\tuv run --frozen pytest tests/unit -m fast\n",
        encoding="utf-8",
    )
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "ci-action-make.yml").write_text(HIDDEN_TIER_CALLER_WORKFLOW, encoding="utf-8")
    actions = tmp_path / "actions"
    _write_action(
        actions,
        "hidden-tier",
        HIDDEN_TIER_ACTION.replace(
            "uv run --frozen pytest tests/unit -m fast",
            "make inner-tier",
        ),
    )

    assert unauthorized_suite_jobs(workflows, makefile=makefile) == {
        ("ci-action-make.yml", "report"): 1,
    }
    gate = next(gate for gate in gc.parse_workflow(workflows / "ci-action-make.yml", makefile=makefile) if gate.job == "report")
    assert gate.via == "make inner-tier"


def test_faultinjection_clean_composite_action_is_not_a_gate(tmp_path: Path) -> None:
    """Negative control: splicing an action that runs no tests adds no gate."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "ci-setup.yml").write_text(
        HIDDEN_TIER_CALLER_WORKFLOW.replace("hidden-tier", "setup"),
        encoding="utf-8",
    )
    actions = tmp_path / "actions"
    _write_action(actions, "setup", SETUP_ACTION)

    assert unauthorized_suite_jobs(workflows) == {}


def test_live_composite_action_wiring_is_spliced_and_still_one_invocation() -> None:
    """The LIVE wiring of #4367 form 1 — proven against the real tree.

    ``ci-modules.yml``'s ``test`` job delegates to ``module-tests.yml`` (a
    reusable workflow) whose own steps use ``./.github/actions/warmup`` —
    two hops the model must both resolve to see the action's steps at all.
    Warmup builds an environment and runs no suite, so the splice must leave
    the authorised single invocation of ``ci-modules.yml::test`` untouched:
    this is both the non-vacuity anchor for form 1 (the splice really runs
    against live files) and the regression guard that a suite execution
    added to ``warmup`` (or any action it gains) becomes VISIBLE here.
    """
    data = gc.load_spliced_workflow(gc.WORKFLOWS_DIR / "ci-modules.yml")
    job_steps = (data.get("jobs") or {}).get("test", {}).get("steps") or []
    spliced_action_runs = [step.get("run", "") for step in job_steps if isinstance(step, dict) and "warmup-venv-" in str(step.get("run", ""))]
    assert spliced_action_runs, (
        "module-tests.yml's `./.github/actions/warmup` step was not spliced into "
        "ci-modules.yml's caller job — the model is blind to the live composite "
        "action wiring again"
    )

    gates = list(gc.parse_workflow(gc.WORKFLOWS_DIR / "ci-modules.yml"))
    assert [(gate.job, gate.via) for gate in gates] == [("test", None)], (
        "ci-modules.yml::test must stay exactly one directly-anchored invocation — "
        "warmup runs no suite, so a second gate here means the splice mis-attributed "
        "a step"
    )


# A standalone ``pytest`` command word: not ``PYTEST_ADDOPTS`` (case), not
# ``pytest.ini`` / ``pytest-cov`` / ``pytestarch`` (the trailing lookahead).
PYTEST_WORD_RE = re.compile(r"(?<![\w-])pytest(?![-\w.])")

# Runner forms a line may reach pytest through WITHOUT the gate model
# resolving it — i.e. a standalone ``pytest`` word the model still cannot
# claim (the guard's condition is conjunctive: model-resolved lines never
# trip, whatever runner they use).
#
# Since #4367 widened ``_gate_coverage``'s prefix table, the CANONICAL
# spellings of ``coverage run`` / ``poetry run`` / ``xvfb-run`` /
# ``timeout N`` / ``<path>/pytest`` resolve, so those rows now catch only
# variant spellings the table still misses (multi-word flag values, an option
# before the duration, ``coverage3``). What genuinely remains unresolved —
# and is the reason ``tox``/``nox`` stay here — are runners that DELEGATE to
# configuration files the model does not read: their pytest invocation lives
# in ``tox.ini`` / ``noxfile.py``, not on the workflow line.
#
# Deny-list, deliberately: its failure mode is missing an unknown runner — the
# status quo — whereas flagging every unresolved ``pytest`` word would red main
# on an error message or a ``pipx inject`` line in workflows this module does
# not own. Closing the class is the recorded follow-up in the module docstring.
BLIND_RUNNER_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bcoverage\s+run\b"),
    re.compile(r"\b(?:poetry|pdm|hatch|pipenv)\s+run\b"),
    re.compile(r"\b(?:tox|nox)\b"),
    re.compile(r"\bxvfb-run\b"),
    re.compile(r"\btimeout\s+\d"),
    re.compile(r"(?:^|[\s;&|])[./][\w./-]*/pytest\b"),
)


def _workflow_run_lines(path: Path) -> list[tuple[str, str]]:
    """``(job, logical shell line)`` for every ``run:`` step in *path*."""
    data = gc.load_spliced_workflow(path)
    lines: list[tuple[str, str]] = []
    for job_name, job in (data.get("jobs") or {}).items():
        for step in (job or {}).get("steps") or []:
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                lines.extend((job_name, logical) for logical in gc.join_continuations(step["run"]))
    return lines


def blind_runner_offenders(*, workflows_dir: Path, actions_dir: Path) -> list[str]:
    """Lines that reach pytest through a runner the gate model cannot strip.

    A suite execution written this way is a duplicate that no assertion in this
    module can see: the model reports "no pytest command here" and the job never
    becomes a gate. The condition is deliberately conjunctive — a known-blind
    runner AND a standalone ``pytest`` word AND nothing the model resolved — so
    a line the model already understands never trips it.
    """
    offenders: list[str] = []
    candidates: list[tuple[str, str]] = []
    for path in enumerate_workflows(workflows_dir):
        if change_triggered(path):
            candidates.extend((f"{path.name}::{job}", line) for job, line in _workflow_run_lines(path))
    for action in composite_action_files(actions_dir):
        candidates.extend((f"{action.parent.name}/{action.name}", line) for line in _composite_run_lines(action))
    for origin, line in candidates:
        if not PYTEST_WORD_RE.search(line) or gc.suite_invocations(line):
            continue
        if any(pattern.search(line) for pattern in BLIND_RUNNER_RES):
            offenders.append(f"{origin}: {line.strip()}")
    return offenders


def test_no_blind_runner_form_reaches_pytest_in_ci() -> None:
    """No CI-reachable line reaches pytest through a runner the model cannot strip."""
    offenders = blind_runner_offenders(workflows_dir=gc.WORKFLOWS_DIR, actions_dir=ACTIONS_DIR)
    assert not offenders, (
        "pytest reached through a runner `_gate_coverage`'s prefix table does not strip — the "
        "invocation parses as 'no pytest command here', so this battery cannot see it. Use a form "
        f"the model resolves (`uv run --frozen pytest ...`), or widen the prefix table: {offenders}"
    )


def test_faultinjection_runner_prefixed_forms_are_resolved(tmp_path: Path) -> None:
    """#4367 form 4: each formerly-blind runner spelling is now a real gate.

    Every one of these lines parsed as "no pytest command here" before #4367
    widened the prefix table; each must now count as a suite execution of the
    job that runs it — and must NOT trip the deny-list guard, because the
    model resolved it (the guard's condition is conjunctive on resolution).
    """
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "ci-runner.yml").write_text(RUNNER_PREFIX_WORKFLOW, encoding="utf-8")
    actions = tmp_path / "actions"
    actions.mkdir()

    assert jobs_of(workflows / "ci-runner.yml") == {"report": len(RUNNER_PREFIX_LINES)}
    coverage_gate = next(gate for gate in gc.parse_workflow(workflows / "ci-runner.yml") if gate.marker_expr == "fast")
    assert coverage_gate.paths == ["tests/unit"]
    assert coverage_gate.via is None
    assert blind_runner_offenders(workflows_dir=workflows, actions_dir=actions) == []


def test_faultinjection_unresolved_runner_delegation_is_still_reported(tmp_path: Path) -> None:
    """Fault injection for the guard above: a runner the model cannot resolve.

    ``tox`` delegates to ``tox.ini`` — the pytest invocation is not on this
    line, so the model resolves nothing and the deny-list is all that sees
    the standalone ``pytest`` word behind it. Without this twin the guard
    would be a scan that has never fired since #4367 emptied its canonical
    payload set.
    """
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "ci-delegate.yml").write_text(UNRESOLVED_RUNNER_WORKFLOW, encoding="utf-8")
    actions = tmp_path / "actions"
    actions.mkdir()

    assert jobs_of(workflows / "ci-delegate.yml") == {}
    assert blind_runner_offenders(workflows_dir=workflows, actions_dir=actions) == [
        "ci-delegate.yml::report: tox -e py -- pytest tests/unit",
    ]


def test_faultinjection_resolvable_and_prose_lines_are_not_reported(tmp_path: Path) -> None:
    """Negative control: neither a resolvable invocation nor a prose mention trips it.

    The prose cases are taken from the live tree — an error message naming
    pytest and a ``pipx inject`` install line — so this pins that the guard
    stays quiet on the workflows it does not own.
    """
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "ci-quiet.yml").write_text(QUIET_RUNNER_WORKFLOW, encoding="utf-8")
    actions = tmp_path / "actions"
    actions.mkdir()

    assert blind_runner_offenders(workflows_dir=workflows, actions_dir=actions) == []


# ---------------------------------------------------------------------------
# Command-position indirection: the command word is resolved at run time
# ---------------------------------------------------------------------------

# A step whose command word is a reference rather than a command runs something
# no static reader can know. Two forms, both confirmed to walk a duplicate past
# every assertion in this module from inside an ordinary `pull_request`
# workflow: `run: ${{ matrix.cmd }}`, and `env: {CMD: make test-fast}` with
# `run: $CMD`.
#
# Unlike BLIND_RUNNER_RES this is NOT a deny-list of spellings: any GitHub
# expression in command position is refused, and so is any shell variable the
# workflow itself declares. Scoping the second half to DECLARED names is what
# keeps it quiet on the live tree — a runner-provided variable such as
# `$GITHUB_OUTPUT` is not an indirection the author chose, and `ci-aggregate.yml`
# mentions one in prose inside a heredoc.
#
# A matrix command supplied through `include:` IS resolved by the gate model
# (`substitute_matrix`), and is still refused here: that resolution depends on a
# matrix shape one edit can change, so the step's command must not be a
# reference in the first place.
#
# The condition is conjunctive, the same way `blind_runner_offenders` is: a
# reference in command position AND nothing the model could resolve on that
# line. `ci-windows.yml` legitimately writes `"$VENV_PYTHON" -m pytest ...` with
# `VENV_PYTHON` declared in step `env:`; the model resolves that line, so the
# battery can see it, so it is not an escape and is not flagged. A `"$CMD"`
# holding a whole command resolves to nothing and is.
GITHUB_EXPRESSION_COMMAND_RE = re.compile(r"^[\"']?\$\{\{")
DECLARED_VAR_COMMAND_RE = re.compile(r"^[\"']?\$\{?(\w+)\}?")


def _declared_env_names(node: Any) -> set[str]:
    """The ``env:`` keys *node* declares (workflow, job or step level)."""
    env = node.get("env") if isinstance(node, dict) else None
    return {str(name) for name in env} if isinstance(env, dict) else set()


def indirect_command_form(logical_line: str, declared: set[str]) -> str | None:
    """*logical_line* if its command word is an UNREADABLE run-time reference.

    ``None`` when the command word is literal, when the referenced name is not
    one the workflow declares, or when the gate model resolved the line anyway.
    """
    command = logical_line.strip()
    if gc.suite_invocations(command):
        return None
    if GITHUB_EXPRESSION_COMMAND_RE.match(command):
        return command
    match = DECLARED_VAR_COMMAND_RE.match(command)
    return command if match and match.group(1) in declared else None


def command_indirection_offenders(*, workflows_dir: Path) -> list[str]:
    """Change-triggered steps whose command word is resolved at run time."""
    offenders: list[str] = []
    for path in enumerate_workflows(workflows_dir):
        if not change_triggered(path):
            continue
        data = gc.load_spliced_workflow(path)
        workflow_env = _declared_env_names(data)
        for job_name, job in (data.get("jobs") or {}).items():
            job_env = workflow_env | _declared_env_names(job)
            for step in (job or {}).get("steps") or []:
                if not isinstance(step, dict) or not isinstance(step.get("run"), str):
                    continue
                declared = job_env | _declared_env_names(step)
                for logical in gc.join_continuations(step["run"]):
                    form = indirect_command_form(logical, declared)
                    if form is not None:
                        offenders.append(f"{path.name}::{job_name}: {form}")
    return offenders


def test_no_change_triggered_step_hides_its_command_behind_a_reference() -> None:
    """A command this battery cannot read is a suite execution it cannot count."""
    offenders = command_indirection_offenders(workflows_dir=gc.WORKFLOWS_DIR)
    assert not offenders, (
        "a change-triggered step whose command word is resolved at run time — whatever it runs, "
        "including the whole test suite, is invisible to every assertion in this module. Write the "
        f"command literally, or move the variable into the command's arguments: {offenders}"
    )


INDIRECT_COMMAND_WORKFLOW = """\
name: indirect
on:
  pull_request:
    types: [opened, synchronize]
env:
  CMD: make test-fast
jobs:
  via-env:
    runs-on: ubuntu-latest
    steps:
      - run: $CMD
  via-matrix:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        cmd: [make test-fast]
    steps:
      - run: ${{ matrix.cmd }}
  via-quoted-env:
    runs-on: ubuntu-latest
    steps:
      - run: |
          "$CMD"
"""

# The control's lines are taken from the live tree: a runner-provided variable
# named in prose inside a heredoc (ci-aggregate.yml), a quoted interpreter
# variable the model DOES resolve (ci-windows.yml), and a literal command with a
# variable in ARGUMENT position, which is not an indirection of the command.
DIRECT_COMMAND_WORKFLOW = """\
name: direct
on:
  pull_request:
    types: [opened, synchronize]
env:
  CMD: make test-fast
  VENV_PYTHON: "__VENV_PYTHON__"
jobs:
  literal:
    runs-on: ubuntu-latest
    steps:
      - run: |
          uv run --frozen pytest tests/unit -m fast
          echo "write $GITHUB_OUTPUT and override the completeness re-check."
          make test-fast ARGS="$CMD"
          "$VENV_PYTHON" -m pytest -m windows_ci --maxfail=1 -v tests/unit
"""


def test_faultinjection_command_indirection_is_reported(tmp_path: Path) -> None:
    """Every escape, planted in an ordinary ``pull_request`` workflow."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "ci-indirect.yml").write_text(INDIRECT_COMMAND_WORKFLOW, encoding="utf-8")

    assert command_indirection_offenders(workflows_dir=workflows) == [
        "ci-indirect.yml::via-env: $CMD",
        "ci-indirect.yml::via-matrix: ${{ matrix.cmd }}",
        'ci-indirect.yml::via-quoted-env: "$CMD"',
    ]


def test_faultinjection_direct_commands_are_not_reported(tmp_path: Path) -> None:
    """Negative control: readable commands, from the workflows this module does not own.

    The quoted-interpreter line is the reason the guard is conjunctive: the
    model resolves it, so the battery can see the suite execution and the step
    is not an escape. Without this control the guard would red ``ci-windows.yml``.
    """
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    workflow = DIRECT_COMMAND_WORKFLOW.replace("__VENV_PYTHON__", (tmp_path / "venv" / "bin" / "python").as_posix())
    (workflows / "ci-direct.yml").write_text(workflow, encoding="utf-8")

    assert command_indirection_offenders(workflows_dir=workflows) == []
