"""Dual-mode + manual dispatch + merge-eligibility contract (mission
``ci-pipeline-reinstatement-01M1X35E`` WP11, FR-018/FR-019/NFR-008,
SC-009/SC-010).

**Ownership boundary (binding, see the WP11 task file's "Owned_files
partition decision"):** this module is the ONE cross-cutting artefact that
ASSERTS the dual-mode contract against the on-disk reinstated-workflow SET.
It authors NO per-workflow mode/``if:``/``workflow_dispatch`` logic — that is
owned by each workflow-owning WP inside its own file (WP07 ``ci-router.yml``;
WP09 ``module-tests.yml``/``ci-modules.yml``; WP10 ``ci-aggregate.yml``; WP12
``sonar.yml``; WP13 ``ci-nightly.yml``; WP14 ``packs.yml``). This test reads
those files; it never edits them.

The reinstated-workflow SET this module asserts over is **discovered**, not
hardcoded to a fixed cardinality: :data:`REINSTATED_WORKFLOW_CANDIDATES` lists
every workflow this mission's plan (T4/D3, data-model.md E6) commits to
eventually reinstating, and each test filters that list down to the files
that actually exist on disk right now. WP11 depends only on the FOUNDATION
cluster + WP07 + WP09, so at WP11's landing time only ``ci-router.yml``,
``ci-modules.yml`` and ``module-tests.yml`` exist; the four still-pending
sibling workflows (``ci-aggregate.yml``, ``sonar.yml``, ``ci-nightly.yml``,
``packs.yml``) are silently skipped until their owning WPs land them, at
which point this module starts asserting over them automatically without a
code change here (the "on-disk workflow SET" the task file names).

Three invariants are pinned:

* **T057/T058 — dual-mode + dispatch threading.** Every present reinstated
  workflow declares ``workflow_dispatch``, threads a ``mode`` input
  (``pr``/``full``, default ``pr``), and realizes PR fail-fast / full
  run-all-regardless somewhere in its job graph (a matrix ``fail-fast``
  keyed off ``mode``, a per-shard mode branch, or an ``if: always()``
  terminal aggregator — the mechanism the file already uses).
* **T059 — skipped != green.** The terminal aggregator's evaluation logic
  distinguishes a merely-``skipped`` dependency (not blocking) from a
  ``failure``/``cancelled``/``timed_out`` one (blocking) — proven *behaviorally*
  against the extracted, unit-tested classifier ``scripts/ci/router_gate.classify``
  (#4208), not by pattern-matching the source. The router-gate step now reads the
  Actions jobs-API conclusions (the ``needs`` context cannot carry ``timed_out``)
  and calls that classifier, so the evaluation logic lives in an importable module
  rather than an embedded heredoc; these tests exercise it directly.

What this module does **not** and cannot prove: the short-circuit / run-all /
skipped-not-counted-green behaviors are GitHub *host* semantics (matrix
``fail-fast`` cancellation, branch-protection required-check treatment of a
``cancelled``/``skipped`` check). Those are provable only by a real dispatched
run — that evidence lives in
``kitty-specs/ci-pipeline-reinstatement-01M1X35E/dual-mode-dispatch-evidence.md``
(T060), honestly marked PENDING until this mission's workflows go live.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.router_gate import ROUTER_GATE_JOB_NAME, classify

pytestmark = pytest.mark.architectural

# tests/architectural/test_dual_mode_contract.py -> parents[2] is repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS_DIR = _REPO_ROOT / ".github" / "workflows"

# Every workflow this mission's plan (T4) commits to reinstating with
# dual-mode + workflow_dispatch semantics. Discovered, not asserted whole:
# tests below filter this to whichever of these files exist on disk today.
REINSTATED_WORKFLOW_CANDIDATES: tuple[str, ...] = (
    "ci-router.yml",
    "ci-modules.yml",
    "module-tests.yml",
    "ci-aggregate.yml",
    "sonar.yml",
    "ci-nightly.yml",
    "packs.yml",
)

# WP11 claims only after FOUNDATION + WP07 + WP09 are approved/done, so these
# three MUST already be present when this test runs — this is the file's
# non-vacuity floor (and would be red, for the right reason, on any base that
# predates WP07/WP09 landing).
_MINIMUM_PRESENT_AT_WP11_CLAIM_TIME = frozenset({"ci-router.yml", "ci-modules.yml", "module-tests.yml"})

# YAML 1.1 parses the bare `on:` mapping key as the boolean True, not the
# string "on" -- every workflow file hits this, so triggers are looked up
# under either key.
_ON_KEYS: tuple[Any, ...] = ("on", True)


def _present_reinstated_workflows() -> list[Path]:
    """The subset of :data:`REINSTATED_WORKFLOW_CANDIDATES` that exist on disk."""
    return [_WORKFLOWS_DIR / name for name in REINSTATED_WORKFLOW_CANDIDATES if (_WORKFLOWS_DIR / name).is_file()]


def _load_workflow(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    assert isinstance(doc, dict), f"{path}: workflow YAML did not parse to a mapping"
    return doc


def _triggers(workflow: dict[str, Any], path: Path) -> dict[str, Any]:
    for key in _ON_KEYS:
        if key in workflow:
            triggers = workflow[key]
            assert isinstance(triggers, dict), f"{path}: `on:` block is not a mapping"
            return triggers
    raise AssertionError(f"{path}: no `on:` trigger block found (checked keys {_ON_KEYS!r})")


def _mode_input(triggers: dict[str, Any], path: Path) -> dict[str, Any]:
    dispatch = triggers.get("workflow_dispatch")
    assert isinstance(dispatch, dict), f"{path}: workflow_dispatch has no `inputs:` block"
    inputs = dispatch.get("inputs")
    assert isinstance(inputs, dict), f"{path}: workflow_dispatch has no `inputs:` block"
    mode = inputs.get("mode")
    assert isinstance(mode, dict), f"{path}: workflow_dispatch.inputs has no `mode` input"
    return mode


_PRESENT_WORKFLOW_PATHS = _present_reinstated_workflows()
_PRESENT_WORKFLOW_IDS = [p.name for p in _PRESENT_WORKFLOW_PATHS]


# ---------------------------------------------------------------------------
# Non-vacuity floor: the reinstated-workflow SET this module asserts over is
# not empty, and the WP11-cluster-gate dependencies (WP07 ci-router.yml, WP09
# module-tests.yml/ci-modules.yml) are actually present. This is what would
# be red, for the right reason, if this test ran against a base that predates
# those WPs landing (mode wiring / workflow_dispatch absent because the files
# themselves are absent).
# ---------------------------------------------------------------------------
def test_wp07_wp09_reinstated_workflows_are_present() -> None:
    present_names = {p.name for p in _PRESENT_WORKFLOW_PATHS}
    missing = _MINIMUM_PRESENT_AT_WP11_CLAIM_TIME - present_names
    assert not missing, (
        f"WP11 claims only after WP07 (ci-router.yml) + WP09 (module-tests.yml/ci-modules.yml) are approved/done; missing on disk: {sorted(missing)}"
    )
    assert present_names, "no reinstated workflow files found under .github/workflows/"


@pytest.mark.parametrize("workflow_path", _PRESENT_WORKFLOW_PATHS, ids=_PRESENT_WORKFLOW_IDS)
def test_every_present_reinstated_workflow_declares_workflow_dispatch(
    workflow_path: Path,
) -> None:
    """T058 / SC-010 / C-009: manual dispatch on every reinstated workflow."""
    workflow = _load_workflow(workflow_path)
    triggers = _triggers(workflow, workflow_path)
    assert "workflow_dispatch" in triggers, f"{workflow_path.name}: missing workflow_dispatch trigger (SC-010/C-009)"


@pytest.mark.parametrize("workflow_path", _PRESENT_WORKFLOW_PATHS, ids=_PRESENT_WORKFLOW_IDS)
def test_every_present_reinstated_workflow_threads_a_pr_full_mode_input(
    workflow_path: Path,
) -> None:
    """T057: the `mode` input (pr/full) is threaded via dispatch.

    The ``pr`` default (path-scoped fail-fast) is the ordinary case only for
    PR-triggered workflows. A schedule/dispatch-only workflow (the nightly
    ``ci-nightly.yml`` / ``sonar.yml``) never runs per-PR, so its scheduled runs
    are full-mode *by cadence* and it may default ``mode`` to ``full``; the
    input still offers both options either way.
    """
    workflow = _load_workflow(workflow_path)
    triggers = _triggers(workflow, workflow_path)
    mode = _mode_input(triggers, workflow_path)
    is_pr_triggered = "pull_request" in triggers or "push" in triggers
    default = mode.get("default")
    if is_pr_triggered:
        assert default == "pr", (
            f"{workflow_path.name}: PR-triggered workflow's mode input default must be 'pr' "
            "(path-scoped fail-fast is the ordinary per-PR case; full run-all is opt-in)"
        )
    else:
        assert default in {"pr", "full"}, f"{workflow_path.name}: schedule/dispatch-only workflow mode default must be 'pr' or 'full', got {default!r}"
    mode_type = mode.get("type")
    if mode_type == "choice":
        options = mode.get("options")
        assert isinstance(options, list) and set(options) >= {"pr", "full"}, (
            f"{workflow_path.name}: mode choice options must include both 'pr' and 'full', got {options!r}"
        )


# ---------------------------------------------------------------------------
# T057 — concrete PR-fail-fast / full-run-all mechanisms, per file.
# ---------------------------------------------------------------------------


def test_ci_modules_matrix_fail_fast_is_keyed_off_mode() -> None:
    """ci-modules.yml (WP09): `fail-fast: mode != 'full'` is the literal PR
    short-circuit (cancel remaining matrix legs on the first red shard) vs
    full run-all-regardless mechanism (data-model.md E6, research.md D3)."""
    path = _WORKFLOWS_DIR / "ci-modules.yml"
    if not path.is_file():
        pytest.skip("ci-modules.yml not yet reinstated")
    workflow = _load_workflow(path)
    test_job = workflow["jobs"]["test"]
    strategy = test_job.get("strategy")
    assert isinstance(strategy, dict), "ci-modules.yml: job `test` has no `strategy:` block"
    fail_fast_expr = strategy.get("fail-fast")
    assert isinstance(fail_fast_expr, str), (
        "ci-modules.yml: `strategy.fail-fast` must be an expression, not a hardcoded boolean, so PR mode fails fast and full mode does not"
    )
    assert "mode" in fail_fast_expr and "full" in fail_fast_expr, f"ci-modules.yml: strategy.fail-fast ({fail_fast_expr!r}) is not keyed off the mode input"
    # PR mode (mode != 'full') must resolve fail-fast=true; full mode must
    # resolve fail-fast=false. Confirm the expression's polarity directly.
    assert "!=" in fail_fast_expr, (
        f"ci-modules.yml: strategy.fail-fast ({fail_fast_expr!r}) must be a "
        "negated equality against 'full' so pr (or an empty/default mode) "
        "resolves fail-fast=true"
    )


def test_module_tests_shard_run_step_branches_pr_fail_fast_vs_full_run_all() -> None:
    """module-tests.yml (WP09): the per-shard pytest run step propagates the
    real exit status in pr mode (fail fast) but only warns and continues in
    full mode (run-all-regardless); artefact upload always runs regardless of
    shard outcome so full mode reports every failure (SC-009)."""
    path = _WORKFLOWS_DIR / "module-tests.yml"
    if not path.is_file():
        pytest.skip("module-tests.yml not yet reinstated")
    workflow = _load_workflow(path)
    steps = workflow["jobs"]["test"]["steps"]
    run_step = next((s for s in steps if s.get("name") == "Run pytest for this shard"), None)
    assert run_step is not None, "module-tests.yml: missing 'Run pytest for this shard' step"
    run_script = run_step["run"]
    assert 'mode" = "full"' in run_script.replace("$mode", "mode"), "module-tests.yml: run step does not branch on mode"
    assert 'exit "$status"' in run_script, "module-tests.yml: pr-mode branch must propagate the real pytest exit status"

    upload_step = next(
        (s for s in steps if s.get("name") == "Upload coverage + xunit artefacts"),
        None,
    )
    assert upload_step is not None, "module-tests.yml: missing artefact-upload step"
    assert upload_step.get("if") == "always()", (
        "module-tests.yml: artefact upload must be if: always() so full mode reports every shard's failure, not just the first"
    )


def test_ci_router_terminal_gate_declares_if_always_not_cancelled() -> None:
    """ci-router.yml (WP07): the terminal `router-gate` aggregator must
    evaluate regardless of whether any upstream job failed, was cancelled, or
    was skipped by path-scoping -- otherwise a failure upstream would just
    skip the gate itself rather than let it render a verdict."""
    path = _WORKFLOWS_DIR / "ci-router.yml"
    if not path.is_file():
        pytest.skip("ci-router.yml not yet reinstated")
    workflow = _load_workflow(path)
    gate_job = workflow["jobs"]["router-gate"]
    condition = gate_job.get("if", "")
    assert "always()" in condition, f"ci-router.yml: router-gate `if:` ({condition!r}) must contain always()"


# ---------------------------------------------------------------------------
# #4208 wiring/invariant guard (renata MINOR-1) — the router-gate got the
# classifier but NOT the wiring guard the reconciler (#4360-B) got, leaving
# three fail-*closed* drift modes unpinned: a job-name drift wedges the gate
# permanently red (it classifies its own null conclusion as `incomplete`); a
# gate step that stopped invoking the shipped classifier or the `attempts/`
# jobs-API path would read stale/attempt-1 conclusions; a future top-level job
# added OUTSIDE `needs:` could evaluate while in-progress. This is the
# YAML-shape guard mirroring test_ci_aggregate_reconcile_step_invokes_shipped_module.
# ---------------------------------------------------------------------------


def test_router_gate_step_wiring_and_needs_invariant_are_pinned() -> None:
    """#4208 / MINOR-1: pin the router-gate wiring so it cannot silently drift.

    (a) ``ROUTER_GATE_JOB_NAME`` equals the gate job's ``name:`` in
        ``ci-router.yml`` -- the classifier excludes the gate's own row by that
        exact name, so a drift makes it read its own null conclusion as
        ``incomplete`` and block forever (a false-red self-wedge).
    (b) the gate step actually invokes ``scripts/ci/router_gate.py`` over the
        ``attempts/$RUN_ATTEMPT`` jobs-API path (so a re-run reads fresh
        conclusions, not attempt-1 residue).
    (c) the gate's ``needs:`` equals the FULL set of non-gate top-level jobs --
        the invariant that makes "classify every API job" == "classify needs":
        because the gate waits on every other job, none is in-progress when it
        evaluates. A future job added outside ``needs:`` breaks this and fails
        here, rather than silently risking a false-red on an in-progress job.
    """
    path = _WORKFLOWS_DIR / "ci-router.yml"
    workflow = _load_workflow(path)
    gate_job = workflow["jobs"]["router-gate"]

    # (a) job-name coupling between the classifier constant and the YAML.
    assert gate_job.get("name") == ROUTER_GATE_JOB_NAME, (
        f"ci-router.yml: router-gate `name:` ({gate_job.get('name')!r}) must equal "
        f"router_gate.ROUTER_GATE_JOB_NAME ({ROUTER_GATE_JOB_NAME!r}); a drift wedges "
        "the gate permanently red (it classifies its own null conclusion as incomplete)"
    )

    # (b) the step invokes the shipped classifier over the attempts/ jobs-API path.
    steps = gate_job.get("steps") or []
    run_text = "\n".join(str(s.get("run") or "") for s in steps if isinstance(s, dict))
    assert "scripts/ci/router_gate.py" in run_text, "ci-router.yml: the router-gate step must invoke the shipped classifier scripts/ci/router_gate.py"
    assert "attempts/" in run_text and "RUN_ATTEMPT" in run_text, (
        "ci-router.yml: the router-gate step must read the Actions jobs API over the attempts/$RUN_ATTEMPT path (#4208) so a re-run reads fresh conclusions"
    )

    # (c) needs: == the full set of non-gate top-level jobs (classify-all invariant).
    needs = gate_job.get("needs") or []
    needs_set = set(needs) if isinstance(needs, list) else {needs}
    non_gate_jobs = {name for name in workflow["jobs"] if name != "router-gate"}
    assert needs_set == non_gate_jobs, (
        "ci-router.yml: router-gate `needs:` must be exactly the non-gate top-level jobs "
        f"(classify-all == classify-needs invariant). Outside needs: {sorted(non_gate_jobs - needs_set)}; "
        f"extra in needs: {sorted(needs_set - non_gate_jobs)}"
    )


# ---------------------------------------------------------------------------
# T059 / #4208 — merge-eligibility: skipped != green, timed_out distinct from
# cancelled, blocking policy byte-identical to baseline. The evaluation logic
# now lives in the extracted, importable classifier
# ``scripts/ci/router_gate.classify`` (contract C-gate-1..4,
# contracts/helper-contracts.md), so these assertions exercise it directly with
# synthetic jobs-API conclusions rather than extracting an embedded heredoc.
# ---------------------------------------------------------------------------


def test_router_gate_reports_timed_out_distinctly_and_blocks() -> None:
    """C-gate-1: a timed-out dependency is labelled ``timed_out`` (distinct from
    ``cancelled``) AND blocks the gate.

    This is the #4208 fix: a ``timeout-minutes`` kill collapses to ``cancelled``
    in the ``needs`` context, so the jobs-API ``conclusion`` is the only place a
    real timeout survives distinctly.
    """
    decision = classify({"tests-cli": "timed_out", "tests-e2e": "failure"})
    assert decision.blocks
    assert decision.blocking["tests-cli"] == "timed_out"
    assert dict(decision.timed_out) == {"tests-cli": "timed_out"}
    # A failure is not mislabelled as a timeout, and a cancel would not be either.
    assert "tests-e2e" not in decision.timed_out
    assert not classify({"a": "cancelled"}).timed_out


def test_router_gate_blocking_verdict_is_byte_identical_to_baseline() -> None:
    """C-gate-2: the historical needs-context policy is preserved exactly.

    ``failure`` and ``cancelled`` both block, as before; ``timed_out`` (which the
    old gate could only see as ``cancelled``) still blocks. The reported label
    changes, never the pass/fail verdict.
    """
    assert classify({"tests-cli": "cancelled", "tests-e2e": "cancelled"}).blocks
    assert classify({"a": "failure"}).blocks
    assert classify({"a": "cancelled"}).blocks
    assert classify({"a": "timed_out"}).blocks


def test_router_gate_all_success_does_not_block() -> None:
    """C-gate-3: an all-success set passes the gate."""
    decision = classify({"changes": "success", "ruff": "success", "tests-cli": "success"})
    assert not decision.blocks
    assert not decision.blocking


def test_router_gate_merely_skipped_dependency_is_not_blocking() -> None:
    """C-gate-4: a router-scoped skip (a shard not selected for this diff) does
    not block, and it does not mask a real failure sitting alongside it."""
    assert not classify({"changes": "success", "tests-e2e": "skipped"}).blocks
    blocked = classify({"tests-e2e": "skipped", "tests-cli": "failure"})
    assert blocked.blocks
    assert set(blocked.blocking) == {"tests-cli"}


def test_router_gate_fails_closed_on_unfamiliar_or_incomplete_conclusion() -> None:
    """A conclusion outside the non-blocking set blocks -- the gate never turns
    unrecognised or incomplete evidence green (fail-closed)."""
    assert classify({"a": "startup_failure"}).blocks
    assert classify({"a": "action_required"}).blocks
    assert classify({"a": ""}).blocks


def test_ci_router_concurrency_is_per_sha_on_push_and_per_ref_on_pr() -> None:
    """#4347: push→main keys concurrency per-SHA (a singleton group, no cancel) so a
    merge burst never cancel-cascades landed main runs; pull_request / workflow_dispatch
    keep the per-ref self-coalesce. Exact equality, not a substring -- a substring pin
    passes for a broken always-cancel expression such as ``... || true`` that silently
    re-enables the main cancel-cascade (the exact honesty hole #4347 closes)."""
    workflow = _load_workflow(_WORKFLOWS_DIR / "ci-router.yml")
    assert workflow["concurrency"] == {
        "group": "ci-router-${{ github.event_name == 'push' && github.sha || github.ref }}",
        "cancel-in-progress": "${{ github.event_name != 'push' }}",
    }
