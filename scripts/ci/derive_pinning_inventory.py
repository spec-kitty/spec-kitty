#!/usr/bin/env python3
"""Derive the pinning-rule inventory for the retiring duplicate-measurement job.

Mission ``sonar-per-pr-coverage-reuse-01M2FR32``, WP06/T028. Requirement
FR-010, constraint C-005, contract
``kitty-specs/sonar-per-pr-coverage-reuse-01M2FR32/contracts/gate-disposition-contract.md``.

Why this script exists
----------------------

    A rule that goes **red** when the topology changes is found by CI.
    A rule that goes **greener by deletion** is found by nobody.

This mission's own hand-written first inventory was roughly **4x understated**
and carried four false positives (docstring prose and synthetic fixtures
mistaken for real dependencies). A transcribed markdown table is
observationally identical to a derived one, so "derived mechanically" is only
credible if the derivation is committed, re-runnable, and diffed by a gate.
:mod:`tests.release.test_pinning_inventory_fresh` is that gate.

What it derives
---------------

Every *rule* (a named, automated construct in the scanned Python surface) that
references one of the :data:`SUBJECTS`:

* ``retiring-job`` -- the retiring job's id, ``sonarcloud``;
* ``retiring-host`` -- its host workflow, ``ci-quality.yml``;
* ``retiring-step`` -- the retiring step's suite invocation, ``make test-fast``
  (and the step's own name).

The host workflow **survives** the retirement -- only the job inside it is
removed -- so a bare ``ci-quality.yml`` reference is *not* by itself a
dependency. That distinction is precisely what the hand inventory got wrong in
both directions, so it is recorded per rule rather than assumed.

Assertion form predicts what relocation does to a rule, so each rule is
classified by the strongest form its occurrences take (see :data:`FORM_RANK`):

==========================  ==============================================
form                        behaviour when the job is retired
==========================  ==============================================
``exact-string``            breaks -- the pinned literal becomes unsatisfiable
``set-equality``            breaks -- reds on removal from the expected set
``path-anchored``           breaks -- its operand disappears
``derived-relation``        usually survives; verify the model covers the new host
``docstring-or-comment``    no dependency by itself, but may assert a fact that
                            stops being true (C-005 forbids leaving it)
``synthetic-fixture``       no dependency -- the string is fixture text
==========================  ==============================================

What it does **not** derive
---------------------------

The *disposition* is a recorded human decision, not a derivation: mechanically
discovering a rule cannot tell you whether the property it guards still has a
subject. Dispositions live in :data:`DISPOSITIONS` (live rules) and
:data:`EXECUTED_LEDGER` (rules whose pre-change identity no longer resolves,
because executing the disposition renamed or removed them). A live rule with no
:data:`DISPOSITIONS` entry is emitted with ``disposition: null`` and the
freshness gate **fails closed** on it -- a newly-added pin can therefore never
enter the tree undispositioned.

Determinism
-----------

The artefact must be byte-identical whichever supported interpreter produces
it, or the freshness gate reds for whoever happens to run a different Python
than the last committer. Two things make that true, and both are deliberate:

* every collection is emitted sorted, and files are walked in sorted order;
* **line numbers come from a text scan, never from ``ast``.** Under PEP 701
  (Python 3.12+) a part of an implicitly-concatenated f-string reports a
  different ``lineno`` than it does on 3.11 — observed live, one line apart, on
  ``test_fast_tier_marker_completeness.py``. ``ast`` is still used, but only for
  things whose positions do not move: scope ranges, docstring ranges, and the
  parent relation that decides assertion form (keyed by scope, not by line).

Verify with ``diff <(python3.11 ... --stdout) <(python3.14 ... --stdout)``.

Usage
-----

``python3 scripts/ci/derive_pinning_inventory.py``
    Write :data:`DEFAULT_ARTEFACT` (``tests/release/pinning_rule_inventory.json``).

``python3 scripts/ci/derive_pinning_inventory.py --check``
    Exit non-zero if the committed artefact differs from a fresh derivation.

``python3 scripts/ci/derive_pinning_inventory.py --stdout``
    Print the derived document without touching the artefact.
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import sys
import tokenize
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTEFACT = REPO_ROOT / "tests" / "release" / "pinning_rule_inventory.json"

#: Directories scanned for rules. ``tests`` is the test tree the contract names;
#: ``scripts`` is included because the workflows call into it, so a script
#: docstring can carry a justification that the retirement falsifies (C-005).
SCAN_ROOTS: tuple[str, ...] = ("tests", "scripts")

#: This file is itself full of subject literals; scanning it would make the
#: inventory self-referential and the gate circular.
SELF_RELPATH = "scripts/ci/derive_pinning_inventory.py"

#: Excluded for the same reason: the freshness gate necessarily quotes the rule
#: ids of retired rules in order to check them, so scanning it would re-enter
#: every retired rule into the live derivation as a "reference" and make the
#: artefact unstable against its own gate.
_SELF_EXCLUDED: frozenset[str] = frozenset({SELF_RELPATH, "tests/release/test_pinning_inventory_fresh.py"})

#: The retiring arrangement, as literal tokens a rule can reference.
#:
#: The job id is matched CASE-SENSITIVELY and on identifier boundaries: the
#: service is spelled ``SonarCloud`` and the unrelated read-only helper is
#: ``sonarcloud_branch_review.sh``, and neither is the job. Both were false
#: positives in the hand inventory.
SUBJECTS: dict[str, tuple[str, ...]] = {
    "retiring-job": (r"(?<![A-Za-z0-9_])sonarcloud(?![A-Za-z0-9_.])",),
    "retiring-host": (r"ci-quality\.yml",),
    "retiring-step": (r"make test-fast", r"Run fast tier under coverage"),
}

_SUBJECT_RES: dict[str, re.Pattern[str]] = {key: re.compile("|".join(patterns)) for key, patterns in SUBJECTS.items()}

#: Strongest-form-wins ordering. A rule that both parses the workflow AND pins a
#: literal is classified by the literal, because that is what breaks first.
FORM_RANK: tuple[str, ...] = (
    "exact-string",
    "set-equality",
    "path-anchored",
    "derived-relation",
    "synthetic-fixture",
    "docstring-or-comment",
)

#: The disposition vocabulary (contract). ``none`` is not a disposition: it
#: records a *derived non-dependency* -- a false positive, kept in the artefact
#: so the next reader does not have to re-adjudicate it.
DISPOSITIONS_VOCABULARY = frozenset({"relocate", "rewrite", "retire-as-moot", "none"})

_MODULE_SCOPE = "<module>"
_MODULE_DOCSTRING_SCOPE = "<module-docstring>"

# ---------------------------------------------------------------------------
# Recorded decisions.
#
# DISPOSITIONS keys are rule ids that resolve in the POST-change tree.
# EXECUTED_LEDGER entries are rules whose PRE-change identity no longer
# resolves, because executing the disposition removed or renamed them -- the
# derivation cannot rediscover them, and without this ledger the audit record of
# what was deleted and why would vanish with the deletion. That is exactly the
# failure mode C-005 exists to prevent, so the ledger is frozen in-tree and the
# freshness gate proves each entry against the live tree (a `retire-as-moot`
# rule must really be gone; a `relocate`/`rewrite` successor must really exist).
# ---------------------------------------------------------------------------

_SUCCESSOR_PIN_PARITY = "tests/release/test_sonar_workflow.py::test_live_sonar_surfaces_pin_the_same_sonar_action_shas"

#: Rules that survive in the post-change tree, with the disposition executed on
#: them. Every live derived rule must appear here or the gate fails closed.
DISPOSITIONS: dict[str, tuple[str, str]] = {
    # -- executed: rewrite ---------------------------------------------------
    "tests/architectural/test_coverage_breadth.py::derive_marker_mismatch_exception_set": (
        "rewrite",
        "Docstring naming the retired job as the present-tense runner of the fast-tier marker "
        "expression. Surfaced only at lane consolidation: this file is WP01's (lane-a) and the "
        "derivation ran in lane-b, so neither lane's tree contained both. The FR-016 derivation "
        "itself is unaffected -- it reads the Makefile, not the workflow -- so only the prose "
        "needed correcting, to past tense naming the mission that retired the job. Recorded rather "
        "than left, because a justification describing something no longer true is exactly what "
        "C-005 forbids, and this one would otherwise have entered the tree undispositioned.",
    ),
    "tests/release/test_release_ci_ownership.py::test_reduced_ci_quality_has_exact_jobs": (
        "rewrite",
        "Set-equality over ci-quality.yml's job ids. The host survives and the equality is still "
        "the guard that a job cannot be added or removed unnoticed, so the rule keeps its subject; "
        "only the retiring member leaves the expected set. Rewritten rather than relocated because "
        "the relation is about this workflow's inventory, not about the retired job.",
    ),
    "tests/architectural/test_no_duplicate_suite_execution.py::KNOWN_LIVE_DUPLICATES": (
        "rewrite",
        "WP04's characterisation seam. It named the live duplicate so the battery's live assertion "
        "passed BECAUSE the rule detected it. Emptying the dict turns the same assertion into the "
        "clean-tree form -- the property (no change-triggered job outside the authorised matrix "
        "reaches the suite) is unchanged; only the characterised state moves from 'one known "
        "duplicate' to 'none'.",
    ),
    "tests/architectural/_gate_coverage.py::WORKFLOW_FILES": (
        "rewrite",
        "Closed allowlist of suite-running workflows, held equal to the derived discovery set by "
        "test_pytest_workflow_set_equals_model_allowlist_live. ci-quality.yml joined it in WP03 "
        "because its sonarcloud job really was running a tier; with that job gone the file runs no "
        "suite, so leaving it in the tuple would make the allowlist assert a workflow that is not "
        "there. The tuple is the subject and it survives.",
    ),
    "tests/architectural/_gate_coverage.py::NON_EMITTER_JOBS": (
        "rewrite",
        "Jobs whose scripts mention --cov in prose but emit no coverage; the sonarcloud member "
        "leaves with its job. NO replacement member: ci-aggregate.yml's sonar-pr mentions --cov "
        "nowhere (checked, 0 occurrences), and ci-aggregate.yml is not in WORKFLOW_FILES at all "
        "because it runs no suite -- so an entry for it would be an exclusion for a job this model "
        "never parses. (The first draft of this reason claimed the successor 'takes its place'; "
        "that was wrong and is recorded rather than quietly corrected.) The set itself has no "
        "reader today, which is a separate pre-existing finding, reported not fixed here.",
    ),
    "tests/architectural/test_suite_jobs_gate_blocking.py::test_ci_quality_suite_jobs_are_all_resolved_and_declared_live": (
        "rewrite",
        "Pinned the resolved suite-job set of ci-quality.yml to exactly {sonarcloud}. The set is "
        "now empty -- and an empty set is the pre-WP03 form that was green while a duplicate tier "
        "ran, so the rewrite pairs the clean-tree assertion with a live non-vacuity probe proving "
        "the derivation still resolves suite jobs elsewhere. Without that probe the rule would be "
        "the exact 'greener by deletion' failure this mission exists to prevent.",
    ),
    "tests/architectural/test_suite_jobs_gate_blocking.py::test_reduced_quality_gate_needs_exact_blocking_set_live": (
        "rewrite",
        "Set-equality over quality-gate.needs. The retiring job was never a member (it is "
        "non-blocking by design), so the assertion itself is unchanged; its surrounding "
        "justification named the allowlisted job and had to stop doing so (C-005).",
    ),
    "tests/architectural/test_workflow_coherence.py::test_make_target_indirection_resolves_to_a_suite_invocation_live": (
        "rewrite",
        "Characterised the make-target resolver against the only live indirection host there was "
        "(ci-quality.yml's sonarcloud reaching the tier through `make test-fast`). No live "
        "workflow reaches the suite through an indirection any more, so the live assertion is "
        "rewritten to the clean-tree form plus a probe that the resolver is still wired; the "
        "resolution capability itself stays proven by its fault-injection twin and negative "
        "control, which are fixture-driven and unaffected.",
    ),
    "tests/architectural/test_ci_quality_path_filters.py::<module-docstring>": (
        "rewrite",
        "Prose only -- no assertion reads it -- but it declares ci-quality.yml a 'six-job producer "
        "... plus the non-blocking sonarcloud reporter', which the retirement falsifies. C-005 "
        "forbids leaving a justification that describes something no longer true.",
    ),
    "tests/architectural/test_suite_jobs_gate_blocking.py::<module-docstring>": (
        "rewrite",
        "Declares 'the reduced interim ci-quality.yml runs exactly one suite: the non-blocking "
        "sonarcloud reporter'. False after the retirement, and it is the module's stated contract, "
        "so it is corrected rather than deleted (C-005).",
    ),
    "tests/architectural/_gate_coverage.py::<module-docstring>": (
        "rewrite",
        "Two passages justify WORKFLOW_FILES' membership and the indirect-invocation resolver by "
        "naming the live sonarcloud duplicate. The resolver stays (a future indirection must not "
        "be invisible again), so the justification is re-expressed in the past tense as the reason "
        "the capability exists, rather than as a live claim.",
    ),
    "tests/architectural/test_workflow_coherence.py::<module-docstring>": (
        "rewrite",
        "Names ci-quality.yml as the file whose former invariants the live checks re-open. Still "
        "true of the file; the sentence is left intact and only the sonarcloud-specific claim in "
        "the affected test's own docstring moves.",
    ),
    "scripts/ci/sonar_project_version.py::<module-docstring>": (
        "rewrite",
        "Declares 'the sonarcloud job in .github/workflows/ci-quality.yml calls this module'. "
        "After the retirement the callers are ci-aggregate.yml's sonar-pr job and sonar.yml. A "
        "module docstring naming a deleted caller is a justification describing something no "
        "longer true (C-005).",
    ),
    # -- executed: relocate --------------------------------------------------
    _SUCCESSOR_PIN_PARITY: (
        "relocate",
        "The cross-surface action-pin parity guard: the anti-drift guarantee that no Sonar surface "
        "can have its SonarSource action pins bumped without the others. Its ci-quality.yml "
        "operand is resolved from the retiring host, so the operand is RE-POINTED (the surviving "
        "surfaces are sonar.yml and ci-aggregate.yml) and the relation is preserved verbatim. "
        "Dropping it would silently remove the only thing stopping the two surfaces drifting.",
    ),
    # -- executed: rewrite (renamed rules; the pre-change names are in the
    #    executed ledger with these as their successors) -------------------
    "tests/architectural/test_suite_jobs_gate_blocking.py::test_ci_quality_runs_no_suite_and_the_derivation_can_still_see_one_live": (
        "rewrite",
        "The live suite-job assertion over ci-quality.yml, renamed as it was rewritten. It pinned "
        "the resolved set to exactly {sonarcloud}; that set is now empty. An empty set here is the "
        "PRE-WP03 form that stayed green for months while a duplicate tier ran, so the rewrite pairs "
        "it with a fault-injection probe (re-inject a make-indirect suite job into a copy of the "
        "live file; the derivation must find exactly it) and parses the file DIRECTLY instead of "
        "filtering load_gates() -- the file left WORKFLOW_FILES, so a filtered lookup would return "
        "empty without ever opening it. Two ways of being vacuously green, both closed.",
    ),
    "tests/architectural/test_workflow_coherence.py::test_no_live_workflow_reaches_the_suite_through_an_indirection": (
        "rewrite",
        "The live make-indirection assertion, renamed as it was rewritten. It characterised the "
        "resolver against the only live indirection host there was; that host is gone and no live "
        "workflow reaches the suite through an indirection today. Rewritten from a characterisation "
        "into a LEDGER over every modelled workflow -- empty now, so a future indirect suite step is "
        "a visible change rather than a silent one -- plus a non-vacuity check that the model is "
        "resolving gates at all. The resolution CAPABILITY is untouched and stays proven by the "
        "fault-injection twin and its negative control, both fixture-driven.",
    ),
    # -- executed: rewrite (prose corrected in place, C-005) ---------------
    "tests/architectural/_gate_coverage.py::<module>": (
        "rewrite",
        "The WORKFLOW_FILES membership commentary justified ci-quality.yml's presence in the tuple "
        "by the live sonarcloud duplicate. Re-expressed in the past tense as the reason the "
        "make-indirection resolver exists, and extended to record the file's removal from the tuple "
        "-- the resolver stays, because the next indirect invocation will not announce itself either.",
    ),
    "tests/architectural/test_no_duplicate_suite_execution.py::<module>": (
        "rewrite",
        "The WP06 FLIP SEAM banner and the KNOWN_LIVE_DUPLICATES commentary described the dict as "
        "'deliberately NOT empty yet'. Rewritten to record the executed flip: what the single row "
        "was, why it went, and where the rule's non-vacuity evidence now lives (the six mutations, "
        "four of them against a real workflow file derived from the live tree).",
    ),
    "tests/architectural/test_no_duplicate_suite_execution.py::<module-docstring>": (
        "rewrite",
        "T029b, three accuracy fixes, none caused by the retirement: the header called "
        "command-position indirection 'closed by construction' when both predicates are ^-anchored "
        "to the logical line, so `true; ${{ matrix.cmd }}` and `echo x && $CMD` walk through "
        "(verified by running indirect_command_form on both). The residue is now disclosed in 'What "
        "remains open' with the closure it needs, cross-referenced to spec-kitty#4367.",
    ),
    "tests/architectural/test_suite_jobs_gate_blocking.py::<module>": (
        "rewrite",
        "Carries the retire-as-moot record left where the allowlist's sonarcloud entry was, and the "
        "comment on the re-injected probe fixture. Prose, written by this disposition rather than "
        "falsified by it.",
    ),
    "tests/architectural/test_suite_jobs_gate_blocking.py::NON_BLOCKING_ALLOWLIST": (
        "rewrite",
        "The allowlist itself survives with its two remaining entries, its shrink-only property and "
        "test_allowlist_entries_carry_rationale unchanged; only the sonarcloud member left (its own "
        "retire-as-moot record is in the executed ledger). Rewrite rather than retire because the "
        "dict is the rule and the dict still has a subject.",
    ),
    "tests/release/test_sonar_workflow.py::<module-docstring>": (
        "rewrite",
        "Declared the per-PR sonarcloud job in ci-quality.yml a bound sibling surface, which the "
        "retirement falsifies. Re-expressed around the declared _SONAR_SURFACES set, and it now "
        "states where the three guards over the retired job were dispositioned, so a reader who "
        "notices they are gone finds the record instead of a silence.",
    ),
    "tests/release/test_sonar_workflow.py::<module>": (
        "rewrite",
        "The sibling-surface comment block. Replaced with the disposition record for the three "
        "guards that resolved an operand from the retiring host -- one relocated, two retired as "
        "moot -- so the reasons sit next to the code a reviewer diffs, not only in the artefact.",
    ),
    "tests/ci/test_sonar_project_version.py::<module-docstring>": (
        "rewrite",
        "Named the sonarcloud job as the caller of the module under test. Corrected to the live "
        "callers (ci-aggregate.yml's sonar-pr and sonar.yml) with the retirement recorded, so the "
        "docstring does not send a reader to a job that is not there (C-005).",
    ),
    # -- examined, no edit needed ------------------------------------------
    # These grip the retiring arrangement by the derivation's predicate but
    # need no change. Recorded so the next reader does not re-adjudicate them,
    # and so "I did not touch it" is distinguishable from "I did not look".
    "scripts/ci/fleet_main.py::main_workflows": (
        "none",
        "A set of WORKFLOW FILE names the fleet reads on main. ci-quality.yml survives the "
        "retirement -- four of its jobs and its quality gate are untouched -- so the membership is "
        "still correct.",
    ),
    "scripts/ci/fleet_verdict.py::PR_WORKFLOWS": (
        "none",
        "Same shape: a registry of per-PR workflow FILE names. The file is still a per-PR workflow; only a job inside it left.",
    ),
    "tests/ci/test_fleet_verdict.py::test_all_existing_pr_workflows_are_registered": (
        "none",
        "Asserts the registry above covers every per-PR workflow file. Unaffected -- the file set did not change, and the test would have red if it had.",
    ),
    "tests/architectural/_gate_coverage.py::_COMPOSITE_ROUTING": (
        "none",
        "A comment noting that job names are unique only WITHIN a workflow, using ci-quality's `changes` job as the example. Nothing to do with the retired job.",
    ),
    "tests/architectural/test_ci_quality_path_filters.py::_CI_QUALITY": (
        "none",
        "A Path to the surviving workflow file. Its assertions are about triggers, path filters and runner labels, all derived over whatever jobs the file has.",
    ),
    "tests/architectural/test_suite_jobs_gate_blocking.py::pytest_jobs_of": (
        "rewrite",
        "Left with no caller when the live rule above stopped using it (that rule must parse the "
        "file directly, because this helper filters load_gates() and so answers 'empty' both for a "
        "clean file and for one absent from WORKFLOW_FILES -- which ci-quality.yml now is). Kept "
        "rather than deleted: it still answers the general cross-workflow question, and the two "
        "reasons it can return empty are exactly the trap worth writing down, so its docstring now "
        "states them. That docstring is what puts it in this inventory.",
    ),
    "tests/architectural/test_suite_jobs_gate_blocking.py::_CI_QUALITY_NAME": (
        "none",
        "The surviving file's name, still the subject of every live check in the module.",
    ),
    "tests/architectural/test_no_duplicate_suite_execution.py::CI_QUALITY_NAME": (
        "none",
        "Retained as the identity of mutation 1's subject (below). The name resolves to a real file that still exists.",
    ),
    "tests/architectural/test_no_duplicate_suite_execution.py::RETIRING_JOB": (
        "none",
        "WP04 built mutation 1 to retire WITH its subject: the test is skipif-ed on "
        "KNOWN_LIVE_DUPLICATES, which WP06 emptied, so it now skips. The constant is that skipped "
        "test's subject identity and is kept deliberately rather than deleted -- deleting it would "
        "delete a mutation test, and the skip is the designed, visible signal that the duplicate is "
        "gone. (Observation for a follow-up: a permanently-skipped mutation is mild dead weight; it "
        "is WP04's declared design and WP06 does not overturn it.)",
    ),
    "tests/architectural/test_no_duplicate_suite_execution.py::RETIRING_JOB_VIA": (
        "none",
        "The invocation form mutation 1 asserted (`make test-fast`). Retires with mutation 1, as "
        "above; the make TARGET itself survives as the fast tier's entry point.",
    ),
    "tests/architectural/test_no_duplicate_suite_execution.py::EVASION_JOB_BODY": (
        "none",
        "A fixture body planting a second suite step inside an already-authorised job. The literal "
        "it shares with the retiring step is incidental -- the fixture proves the ledger authorises "
        "ONE execution, not a budget, and is unaffected by the retirement.",
    ),
    "tests/architectural/test_no_duplicate_suite_execution.py::test_mutation2_inlined_suite_command_is_detected": (
        "none",
        "Mutation 2 replaces a REAL workflow's suite line with an inlined command. Its host is "
        "derived from the live tree, so it re-bound to a surviving suite step at the retirement "
        "rather than breaking -- that re-binding is exactly what WP04 built and what the 40 "
        "passed / 1 skipped run after the flip confirms.",
    ),
    "tests/architectural/test_no_duplicate_suite_execution.py::test_repeated_suite_step_in_an_authorized_job_is_detected": (
        "none",
        "Consumes EVASION_JOB_BODY above, and proves the ledger authorises ONE suite execution per "
        "job rather than a budget: an extra suite step inside an already-authorised job is still a "
        "duplicate. Fixture-driven throughout, so the retirement does not touch it.",
    ),
    "tests/architectural/test_workflow_coherence.py::<module>": (
        "none",
        "The fault-injection fixture comment explains that the renamed make target shares NOTHING "
        "with the live `test-fast` one, so a literal-string resolver would miss it. Still exactly "
        "true, and it is the reason the resolver survives the retirement of its only live host.",
    ),
    "tests/architectural/test_workflow_coherence.py::test_faultinjection_renamed_make_target_still_resolves": (
        "none",
        "Fixture-driven: a renamed target behind make variables must still resolve. This is now the "
        "PRIMARY evidence for the resolution capability, since no live workflow exercises it -- "
        "which is why the live rule above was rewritten rather than deleted.",
    ),
    "tests/architectural/test_workflow_coherence.py::test_reduced_quality_gate_has_no_literal_result_reads_live": (
        "none",
        "About ci-quality.yml's quality-gate consuming toJSON(needs). That job and that property are untouched by the retirement.",
    ),
    "tests/ci/test_sonarcloud_branch_review.py::FIXTURES": (
        "none",
        "FALSE POSITIVE, recorded as the contract requires: the token is the directory name "
        "`tests/ci/fixtures/sonarcloud`, belonging to the read-only REST helper "
        "sonarcloud_branch_review.sh. Unrelated to the job. (The subject regex is boundary-matched "
        "and case-sensitive precisely to keep the helper's own module name out of the inventory; "
        "this path segment is the one spelling that still matches.)",
    ),
    "tests/release/test_coverage_topology_ownership.py::<module-docstring>": (
        "none",
        "FALSE POSITIVE. The docstring's `diff-coverage / sonarcloud` aggregator names come from the "
        "PRE-PROGRAMME ci-quality.yml deleted per PROGRAM.md §2 -- the same paragraph says so, and "
        "says the live half of this guard was retired with that file. A different ci-quality.yml and "
        "a different sonarcloud job; nothing here describes the one this mission retires.",
    ),
    "tests/release/test_release_ci_ownership.py::<module>": (
        "none",
        "Module-level comments on the restored/introduced workflow disposition sets. About FILES, not jobs; the file set is unchanged.",
    ),
    "tests/release/test_release_ci_ownership.py::RESTORED_WORKFLOWS": (
        "none",
        "The frozen restored-workflow FILE set. ci-quality.yml is still a restored workflow.",
    ),
    "tests/release/test_release_ci_ownership.py::UPSTREAM_WORKFLOW_PATHS": (
        "none",
        "The upstream workflow-path inventory. Unchanged -- no file was added or removed.",
    ),
    "tests/release/test_release_ci_ownership.py::test_clean_install_check_name_is_branch_protection_ready": (
        "none",
        "About the clean-install-verification job's name and its fixture references. A surviving job, untouched.",
    ),
    "tests/release/test_release_ci_ownership.py::test_deleting_any_disposition_row_reds_the_enforcer": (
        "none",
        "A fault-injection twin over the convergence map's disposition rows, using ci-quality.yml's "
        "row as its subject. The row is still there; the retirement removes a job, not the file.",
    ),
    "tests/release/test_release_ci_ownership.py::test_quality_gate_blocks_every_reduced_producer_job": (
        "none",
        "Set-equality over quality-gate.needs. The retiring job was never a member -- it was "
        "non-blocking by design -- so this assertion is unchanged, and its passing after the "
        "retirement is the check that nothing was quietly promoted into the blocking set.",
    ),
    "tests/release/test_sonar_workflow.py::test_verdict_job_is_skipped_tolerant_and_excludes_the_report": (
        "none",
        "Its docstring contrasts ci-aggregate's skipped-tolerant verdict with ci-quality.yml's "
        "strict-success quality-gate. Both jobs still exist and the contrast still holds.",
    ),
    # -- no dependency (derived false positives, recorded per the contract) ---
    "tests/architectural/test_no_duplicate_suite_execution.py::real_suite_step_host": (
        "none",
        "Derived relation: the mutation host is resolved FROM the live tree, which is why "
        "mutations 1-3 keep a real-file substrate after the retirement (re-binding to "
        "ci-windows.yml) instead of degrading to fixtures. No literal dependency.",
    ),
}

#: Pre-change rules whose identity does not resolve post-change.
#: ``successor`` is null only for ``retire-as-moot``.
EXECUTED_LEDGER: tuple[dict[str, str | None], ...] = (
    {
        "rule": "tests/release/test_sonar_workflow.py::test_ci_quality_sonarcloud_job_is_pull_request_only",
        "form": "exact-string",
        "disposition": "rewrite",
        "successor": "tests/release/test_sonar_workflow.py::test_report_job_condition_asserts_every_conjunct_individually",
        "reason": (
            "Pinned the normalized condition string EXACTLY equal to "
            "\"github.event_name == 'pull_request'\". That literal is UNSATISFIABLE on the "
            "surviving surface: the per-change report is a workflow_run handler, where the "
            "triggering event is read as github.event.workflow_run.event. A verbatim port would "
            "have passed over a job that never runs. Re-expressed in the new trigger's vocabulary "
            "and -- per the contract -- asserting EACH CONJUNCT INDIVIDUALLY (per-change event, "
            "same-repository origin, assembly success, COMPLETE measurement) rather than pinning "
            "the whole condition as one blob, so dropping any single conjunct is caught. Pinning "
            "the blob is what let the same-origin clause be a text-search artefact in the first "
            "place (NFR-004)."
        ),
    },
    {
        "rule": "tests/release/test_sonar_workflow.py::test_all_three_sonar_surfaces_pin_the_same_sonar_action_shas",
        "form": "path-anchored",
        "disposition": "relocate",
        "successor": _SUCCESSOR_PIN_PARITY,
        "reason": (
            "Renamed as it was re-pointed: with ci-quality.yml no longer invoking either "
            "SonarSource action there are two live Sonar surfaces, not three, and a name asserting "
            "'all three' would be false. The relation -- every live Sonar surface pins the same "
            "commit for each action -- is carried over unchanged and now enumerates the surfaces "
            "from a single declared set, so a fourth surface joins by one edit."
        ),
    },
    {
        "rule": "tests/release/test_sonar_workflow.py::test_ci_quality_sonarcloud_job_pins_both_sonar_actions",
        "form": "path-anchored",
        "disposition": "retire-as-moot",
        "successor": None,
        "reason": (
            "Subject genuinely ceased to exist: ci-quality.yml no longer references "
            "SonarSource/sonarqube-scan-action or sonarqube-quality-gate-action at all, so there "
            "is nothing left in that file for DIR-051 to pin. The DIR-051 property is not lost -- "
            "it holds on sonar.yml (test_sonar_pins_both_sonar_actions) and on ci-aggregate.yml "
            "(test_report_job_actions_are_all_sha_pinned), and the relocated parity guard binds "
            "the two together."
        ),
    },
    {
        "rule": "tests/release/test_sonar_workflow.py::test_ci_quality_and_sonar_pin_the_same_sonar_action_shas",
        "form": "path-anchored",
        "disposition": "retire-as-moot",
        "successor": None,
        "reason": (
            "The two-surface ancestor of the relocated parity guard. Its second operand is the "
            "retiring host, and re-pointing it would make it a character-for-character duplicate "
            "of the relocated guard above -- two names for one relation, which is how a relation "
            "later gets half-maintained. Retired as moot because its specific pair "
            "(ci-quality.yml <-> sonar.yml) ceased to exist; the general relation it asserted is "
            "preserved, not dropped."
        ),
    },
    {
        "rule": "tests/architectural/test_suite_jobs_gate_blocking.py::test_ci_quality_suite_jobs_are_all_resolved_and_declared_live",
        "form": "set-equality",
        "disposition": "rewrite",
        "successor": "tests/architectural/test_suite_jobs_gate_blocking.py::test_ci_quality_runs_no_suite_and_the_derivation_can_still_see_one_live",
        "reason": (
            "Renamed as it was rewritten: the old name claimed the file's suite jobs are 'all "
            "resolved and declared', which is a statement about an allowlist that no longer "
            "subtracts anything. The successor asserts the file runs NO suite, and -- because that "
            "exact assertion was green for months while a duplicate ran -- pairs it with a "
            "fault-injection probe that the derivation can still see a re-injected make-indirect "
            "suite job. Full reason on the successor entry in `derived`."
        ),
    },
    {
        "rule": "tests/architectural/test_workflow_coherence.py::test_make_target_indirection_resolves_to_a_suite_invocation_live",
        "form": "set-equality",
        "disposition": "rewrite",
        "successor": "tests/architectural/test_workflow_coherence.py::test_no_live_workflow_reaches_the_suite_through_an_indirection",
        "reason": (
            "Renamed as it was rewritten: the old name asserts a resolution that no live workflow "
            "exercises any more, since the retiring job was the only host reaching the suite "
            "through a make target. The successor keeps the property as an empty ledger over every "
            "modelled workflow, so a future indirect suite step is visible; the resolution "
            "capability stays proven by the fixture-driven twin. Full reason on the successor entry."
        ),
    },
    {
        "rule": "tests/architectural/test_suite_jobs_gate_blocking.py::NON_BLOCKING_ALLOWLIST['sonarcloud']",
        "form": "set-equality",
        "disposition": "retire-as-moot",
        "successor": None,
        "reason": (
            "The allowlist subtracts a pytest-invoking job from the quality-gate containment "
            "check. Its subject leaves the scanned file, so the entry stops being a subtraction "
            "and becomes a declaration about a job that is not there -- which is what the entry's "
            "own history warns against (before WP03 it was 'a declaration standing in for a "
            "subtraction'). The allowlist itself, its shrink-only property and "
            "test_allowlist_entries_carry_rationale are all untouched and still guard the two "
            "remaining entries."
        ),
    },
    {
        "rule": ".github/workflows/ci-quality.yml::sonarcloud",
        "form": "derived-relation",
        "disposition": "retire-as-moot",
        "successor": ".github/workflows/ci-aggregate.yml::sonar-pr",
        "reason": (
            "The retiring job itself, recorded here so the inventory names its own subject. Its "
            "reporting role moves to ci-aggregate.yml's sonar-pr job, which consumes the "
            "measurement the module matrix already produced instead of re-running a tier "
            "(FR-001/FR-003/NFR-001)."
        ),
    },
)


# ---------------------------------------------------------------------------
# Derivation.
# ---------------------------------------------------------------------------
@dataclass
class _Occurrence:
    """One subject literal found at one place, already classified by form."""

    scope: str
    line: int
    subject: str
    form: str


@dataclass
class _Scope:
    """A named construct whose line range attributes occurrences to a rule."""

    name: str
    start: int
    end: int
    depth: int


@dataclass
class _Rule:
    """A named construct that references the retiring arrangement."""

    file: str
    scope: str
    lines: list[int] = field(default_factory=list)
    subjects: set[str] = field(default_factory=set)
    forms: set[str] = field(default_factory=set)
    file_subjects: set[str] = field(default_factory=set)

    @property
    def rule_id(self) -> str:
        return f"{self.file}::{self.scope}"

    def form(self) -> str:
        for candidate in FORM_RANK:
            if candidate in self.forms:
                return candidate
        return "derived-relation"


def _subject_of(text: str) -> str | None:
    """Return the subject key ``text`` references, or ``None``."""
    for key, pattern in _SUBJECT_RES.items():
        if pattern.search(text):
            return key
    return None


def _subjects_in(text: str) -> set[str]:
    """Every subject key ``text`` references."""
    return {key for key, pattern in _SUBJECT_RES.items() if pattern.search(text)}


def is_dependency(subjects: set[str], form: str, file_subjects: set[str]) -> bool:
    """Whether a rule's grip on the retiring arrangement is real.

    Derived, not declared -- the distinction the hand inventory got wrong in
    both directions. The three clauses, in order:

    0. A synthetic fixture body grips nothing: the string is input to a parser,
       not a claim about the live tree (the contract's own classification).
    1. A rule naming the retiring **job** grips it by definition.
    2. A rule in a file that names the job anywhere is part of a module about
       the retiring arrangement, so its host/step references are in scope too
       (this is what catches a constant such as ``RETIRING_JOB_VIA``, whose own
       text names only the step, and a helper such as ``_ci_quality_text``,
       whose own text names only the host but which exists to feed an assertion
       about the job).
    3. The host workflow **survives** -- only the job inside it is removed --
       so a bare ``ci-quality.yml`` reference grips nothing, UNLESS it is a
       set-equality or exact-string form, i.e. a claim about that file's
       contents rather than a lookup of it.
    """
    if form == "synthetic-fixture":
        return False
    if "retiring-job" in subjects or "retiring-job" in file_subjects:
        return True
    return "retiring-host" in subjects and form in {"set-equality", "exact-string"}


def _iter_python_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def _scopes_of(tree: ast.AST) -> list[_Scope]:
    """Name every construct an occurrence can be attributed to.

    Functions and classes come from their own line ranges; module-level
    assignments name their first target, so a dict such as
    ``NON_BLOCKING_ALLOWLIST`` is a rule in its own right rather than being
    swallowed by ``<module>``.
    """
    scopes: list[_Scope] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            end = node.end_lineno or node.lineno
            scopes.append(_Scope(node.name, node.lineno, end, depth=1))
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            name = _assigned_name(node)
            if name is not None:
                end = node.end_lineno or node.lineno
                scopes.append(_Scope(name, node.lineno, end, depth=0))
    return scopes


def _assigned_name(node: ast.Assign | ast.AnnAssign) -> str | None:
    target = node.targets[0] if isinstance(node, ast.Assign) else node.target
    return target.id if isinstance(target, ast.Name) else None


def _scope_at(scopes: list[_Scope], line: int) -> str:
    """The innermost named construct containing ``line``, else ``<module>``."""
    best: _Scope | None = None
    for scope in scopes:
        if not scope.start <= line <= scope.end:
            continue
        if best is None or (scope.depth, scope.start) >= (best.depth, best.start):
            best = scope
    return best.name if best is not None else _MODULE_SCOPE


def _docstring_lines(tree: ast.Module) -> set[int]:
    """Line numbers occupied by any docstring in the module."""
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        doc = ast.get_docstring(node, clean=False)
        if doc is None:
            continue
        first = node.body[0]
        lines.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return lines


def _comment_lines(source: str) -> set[int]:
    """Line numbers carrying a ``#`` comment token."""
    return {token.start[0] for token in tokenize.generate_tokens(io.StringIO(source).readline) if token.type == tokenize.COMMENT}


def _string_form(node: ast.Constant, value: str, parents: dict[int, ast.AST], docstrings: set[int]) -> str:
    """Classify one string literal by the strongest form its use implies.

    *value* is passed separately rather than re-read from ``node.value``:
    ``ast.Constant.value`` is typed as the union of every literal type, so the
    caller's ``isinstance(..., str)`` narrowing is the only thing that makes
    the string operations below well-typed.
    """
    if node.lineno in docstrings:
        return "docstring-or-comment"
    if "\n" in value and len(value) > 120:
        # A multi-line block long enough to be a workflow/Makefile fixture body.
        return "synthetic-fixture"
    parent = parents.get(id(node))
    if isinstance(parent, ast.Compare):
        return "exact-string"
    if isinstance(parent, ast.Set | ast.Tuple | ast.List | ast.Dict):
        grand = parents.get(id(parent))
        if isinstance(grand, ast.Compare):
            return "set-equality"
        if isinstance(grand, ast.Call) and _call_name(grand) in {"frozenset", "set"}:
            return "set-equality"
        return "set-equality"
    if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Div):
        return "path-anchored"
    if isinstance(parent, ast.Call):
        return "path-anchored" if _call_name(parent) in _PATH_CALLS else "derived-relation"
    return "derived-relation"


_PATH_CALLS = frozenset(
    {
        "load_workflow",
        "workflow_text",
        "parse_workflow",
        "load_workflow_model",
        "read_text",
        "Path",
        "_ci_aggregate_job",
    }
)


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def _forms_by_scope(tree: ast.Module, scopes: list[_Scope], docstrings: set[int]) -> dict[str, set[str]]:
    """``scope -> {assertion form}`` for every subject-bearing string literal.

    Keyed by SCOPE and never by line number, because ``ast`` line numbers are
    not interpreter-stable: under PEP 701 (Python 3.12+) a part of an
    implicitly-concatenated f-string reports a different ``lineno`` than it does
    on 3.11, which would make the committed artefact depend on whichever
    interpreter last ran the derivation. Scope boundaries do not move.
    """
    parents = _parent_map(tree)
    forms: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        value: str = node.value
        if _subject_of(value) is None:
            continue
        scope = _resolve_scope(scopes, node.lineno, docstrings)
        forms.setdefault(scope, set()).add(_string_form(node, value, parents, docstrings))
    return forms


def _resolve_scope(scopes: list[_Scope], line: int, docstrings: set[int]) -> str:
    """The rule a *line* belongs to, naming a module docstring separately."""
    scope = _scope_at(scopes, line)
    if line in docstrings and scope == _MODULE_SCOPE:
        return _MODULE_DOCSTRING_SCOPE
    return scope


def _text_occurrences(source: str, scopes: list[_Scope], docstrings: set[int]) -> Iterator[_Occurrence]:
    """Subject references located by scanning the SOURCE TEXT line by line.

    Line numbers come from the text, not from ``ast``, so the artefact is
    byte-identical whichever supported interpreter derives it (see
    :func:`_forms_by_scope`). The form is filled in per scope afterwards;
    comment and docstring lines are decided here, where the text says so.
    """
    comments = _comment_lines(source)
    for index, text in enumerate(source.splitlines(), start=1):
        subject = _subject_of(text)
        if subject is None:
            continue
        scope = _resolve_scope(scopes, index, docstrings)
        prose = index in docstrings or (index in comments and text.lstrip().startswith("#"))
        form = "docstring-or-comment" if prose else ""
        yield _Occurrence(scope, index, subject, form)


def derive_file(path: Path, relpath: str) -> list[_Rule]:
    """Every rule in one Python file that references the retiring arrangement."""
    source = path.read_text(encoding="utf-8")
    if _subject_of(source) is None:
        return []
    file_subjects = _subjects_in(source)
    tree = ast.parse(source)
    scopes = _scopes_of(tree)
    docstrings = _docstring_lines(tree)
    rules: dict[str, _Rule] = {}
    forms_by_scope = _forms_by_scope(tree, scopes, docstrings)
    for occurrence in _text_occurrences(source, scopes, docstrings):
        rule = rules.setdefault(
            occurrence.scope,
            _Rule(file=relpath, scope=occurrence.scope, file_subjects=file_subjects),
        )
        rule.lines.append(occurrence.line)
        rule.subjects.add(occurrence.subject)
        if occurrence.form:
            rule.forms.add(occurrence.form)
    for scope, forms in forms_by_scope.items():
        if scope in rules:
            rules[scope].forms |= forms
    return [rules[key] for key in sorted(rules)]


def derive(repo_root: Path = REPO_ROOT, roots: Iterable[str] = SCAN_ROOTS) -> list[_Rule]:
    """Derive every rule across the scanned roots, in a stable order."""
    rules: list[_Rule] = []
    for name in roots:
        root = repo_root / name
        if not root.is_dir():
            continue
        for path in _iter_python_files(root):
            relpath = path.relative_to(repo_root).as_posix()
            if relpath in _SELF_EXCLUDED:
                continue
            rules.extend(derive_file(path, relpath))
    rules.sort(key=lambda rule: (rule.file, rule.scope))
    return rules


#: Reason text for a derived non-dependency, keyed by the clause that cleared
#: it. Generated rather than hand-written: ~2/3 of the enumeration is noise, and
#: hand-writing 70 paragraphs of "this one is fine" is how a real dependency
#: gets buried in the middle of them.
_NON_DEPENDENCY_REASONS: dict[str, str] = {
    "host-only": (
        "References only the host workflow, which SURVIVES the retirement (the job is removed, the "
        "file is not), and does so as a lookup or prose mention rather than as a claim about the "
        "file's contents. Nothing it asserts changes."
    ),
    "synthetic": (
        "Synthetic fixture body: the subject literal is INPUT to a parser, not a claim about the "
        "live tree. WP04 built these deliberately so the battery's mutations keep a substrate "
        "after the retirement; they are unaffected by it."
    ),
    "step-only": (
        "References only the `make test-fast` target, which survives as a Makefile target and a "
        "local developer entry point; what retires is one workflow step's USE of it. The file does "
        "not mention the retiring job, so this rule is about the target, not about the job."
    ),
}


def _non_dependency_reason(subjects: set[str], form: str) -> str:
    if form == "synthetic-fixture":
        return _NON_DEPENDENCY_REASONS["synthetic"]
    return _NON_DEPENDENCY_REASONS["step-only" if subjects == {"retiring-step"} else "host-only"]


def _entry(rule: _Rule) -> dict[str, object]:
    dependency = is_dependency(rule.subjects, rule.form(), rule.file_subjects)
    if dependency:
        disposition, reason = DISPOSITIONS.get(rule.rule_id, (None, None))
    else:
        disposition, reason = "none", _non_dependency_reason(rule.subjects, rule.form())
    return {
        "rule": rule.rule_id,
        "file": rule.file,
        "scope": rule.scope,
        "subjects": sorted(rule.subjects),
        "form": rule.form(),
        "lines": sorted(set(rule.lines)),
        "dependency": dependency,
        "disposition": disposition,
        "reason": reason,
    }


def build_document(repo_root: Path = REPO_ROOT) -> dict[str, object]:
    """The committed artefact: the live derivation plus the executed ledger."""
    derived = [_entry(rule) for rule in derive(repo_root)]
    return {
        "_comment": (
            "DERIVED — do not hand-edit. Regenerate with "
            "`python3 scripts/ci/derive_pinning_inventory.py`. Mission "
            "sonar-per-pr-coverage-reuse-01M2FR32, FR-010/C-005/SC-009. "
            "`derived` is re-derived from the live tree on every run; "
            "`executed` is the frozen record of rules whose pre-change identity "
            "no longer resolves because the disposition removed or renamed them."
        ),
        "subjects": {key: list(value) for key, value in sorted(SUBJECTS.items())},
        "scan_roots": list(SCAN_ROOTS),
        "derived": derived,
        "executed": [dict(entry) for entry in EXECUTED_LEDGER],
    }


def serialize(document: dict[str, object]) -> str:
    return json.dumps(document, indent=2, sort_keys=False, ensure_ascii=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="exit non-zero if the artefact is stale")
    parser.add_argument("--stdout", action="store_true", help="print the document instead of writing it")
    parser.add_argument("--artefact", type=Path, default=DEFAULT_ARTEFACT)
    args = parser.parse_args(argv)

    payload = serialize(build_document())
    if args.stdout:
        sys.stdout.write(payload)
        return 0
    if args.check:
        if not args.artefact.exists():
            print(f"missing inventory artefact: {args.artefact}", file=sys.stderr)
            return 1
        if args.artefact.read_text(encoding="utf-8") != payload:
            print(
                f"{args.artefact} is stale — re-run `python3 {SELF_RELPATH}`",
                file=sys.stderr,
            )
            return 1
        return 0
    args.artefact.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
