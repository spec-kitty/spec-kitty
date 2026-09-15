"""Sonar workflow contract (WP12, C-008/FR-010, `introduced` disposition).

Contract: this file asserts the ON-DISK ``.github/workflows/sonar.yml`` (this WP's
authoritative surface) is a **fork-safe, informational, nightly/dispatch** producer —
never a per-PR merge-blocking job:

* aggregates the ``*-reports`` artefact family (contracts/artefact-naming.md);
* **skips-green** (never hard-fails) when ``SONAR_TOKEN`` is absent (fork-safe,
  NFR-004 precedent);
* uses stock GitHub-hosted runners (``"blacksmith" not in text`` — the private
  Blacksmith producer this mission retires, per FR-017/C-010);
* carries no ``SK_CI_TOKEN`` (this is a public, informational job — no private git
  dependency credentials belong on it);
* declares ``workflow_dispatch`` and runs on ``schedule``/dispatch only (never
  ``pull_request``, so it structurally cannot enter any PR-blocking ``needs:`` chain);
* SHA-pins every third-party action (DIR-051 / charter "Agent Push Authorization"),
  including the two Sonar actions themselves.

**Sibling-surface coverage.** Every live surface that analyses the SAME
SonarCloud project (``sonar-project.properties``' ``sonar.projectKey``) and
hands ``SONAR_TOKEN`` to the SonarSource actions is bound to this one by
:func:`test_live_sonar_surfaces_pin_the_same_sonar_action_shas`, so the DIR-051
pin discipline cannot drift apart between them. That set is
:data:`_SONAR_SURFACES` and it is declared in ONE place: adding a fourth
surface is one edit, and removing one is a reviewed edit rather than a silent
narrowing.

Until mission ``sonar-per-pr-coverage-reuse`` (#4334) the per-PR member of that
set was ``ci-quality.yml``'s ``sonarcloud`` job (spec-kitty#3993). It was
retired because it re-ran the whole fast tier under ``pytest --cov`` for a
coverage report the ``ci-modules`` shards had already produced for the same
commit; the per-PR role moved to ``ci-aggregate.yml``'s ``sonar-pr`` job, which
consumes those artefacts. The three guards this file carried over that job are
dispositioned in ``tests/release/pinning_rule_inventory.json`` (FR-010/C-005) —
one relocated, two retired as moot — and none was dropped without a record.

**Partition note (WP01 coordination):** the `introduced`-set *membership* assertion
(is ``sonar.yml`` registered in the frozen `introduced` disposition set?) lives in
WP01's ``tests/release/test_release_ci_ownership.py`` — this file never duplicates
that assertion, and never edits WP01's owned map/test files.

**Collection-red lazy-load hygiene:** ``sonar.yml`` does not exist on `main` /
pre-WP12 base. Every load below happens INSIDE the test body (never at module import
time), so this file always *collects* — a missing file reds a targeted assertion with
a clear reason, never an import/collection error.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "sonar.yml"

# YAML 1.1 parses the bare `on:` mapping key as the boolean True, not the string
# "on" -- every workflow file in this mission hits this, so triggers are looked
# up under either key (mirrors tests/release/test_release_ci_ownership.py and
# tests/architectural/test_coverage_artefact_contract.py).
_ON_KEYS: tuple[Any, ...] = ("on", True)

# A 40-hex-char SHA, optionally followed by a `# vX.Y.Z` comment -- the SHA-pin
# form every other reinstated workflow in this mission already uses (DIR-051),
# never a floating tag (`@v7`, `@v1.2.0`, `@main`).
_SHA_PIN_RE = re.compile(r"^[^@\s]+@[0-9a-f]{40}(\s*#.*)?$")


def _workflow_text() -> str:
    if not _WORKFLOW_PATH.exists():
        pytest.fail(f"sonar.yml missing: {_WORKFLOW_PATH.relative_to(_REPO_ROOT)} (WP12 not yet delivered)")
    return _WORKFLOW_PATH.read_text(encoding="utf-8")


def _workflow_yaml() -> dict[str, Any]:
    if not _WORKFLOW_PATH.exists():
        pytest.fail(f"sonar.yml missing: {_WORKFLOW_PATH.relative_to(_REPO_ROOT)} (WP12 not yet delivered)")
    loaded = yaml.safe_load(_WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "sonar.yml did not parse to a mapping"
    return loaded


def _triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    for key in _ON_KEYS:
        if key in workflow:
            triggers = workflow[key]
            assert isinstance(triggers, dict), "sonar.yml: `on:` block is not a mapping"
            return triggers
    pytest.fail("sonar.yml: no `on:` trigger block found")


def _iter_uses_values(node: Any) -> list[str]:
    """Recursively collect every ``uses:`` string in a parsed workflow mapping."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "uses" and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_iter_uses_values(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_iter_uses_values(item))
    return found


# ---------------------------------------------------------------------------
# Trigger surface: schedule/dispatch only -- never pull_request (T063).
# ---------------------------------------------------------------------------
def test_sonar_declares_workflow_dispatch() -> None:
    workflow = _workflow_yaml()
    triggers = _triggers(workflow)
    assert "workflow_dispatch" in triggers, "sonar.yml must declare workflow_dispatch (T063)"


def test_sonar_runs_on_schedule_or_dispatch_never_pull_request() -> None:
    """sonar.yml must be an informational nightly/dispatch producer -- it must
    never carry a `pull_request` trigger, which is what would let it enter a
    PR merge-blocking `needs:` chain (T063: 'not the PR merge-blocking needs:')."""
    workflow = _workflow_yaml()
    triggers = _triggers(workflow)
    assert "schedule" in triggers, "sonar.yml must run on a schedule (nightly)"
    assert "pull_request" not in triggers, "sonar.yml must never trigger on pull_request (informational-only, never PR-blocking)"


def test_sonar_dispatch_threads_a_mode_input() -> None:
    """Forward-compat with WP11's cross-cutting dual-mode contract
    (tests/architectural/test_dual_mode_contract.py, not in this WP's targeted
    surface but named by the DoD): workflow_dispatch exposes a `mode` input."""
    workflow = _workflow_yaml()
    triggers = _triggers(workflow)
    dispatch = triggers.get("workflow_dispatch")
    assert isinstance(dispatch, dict), "sonar.yml: workflow_dispatch has no inputs block"
    inputs = dispatch.get("inputs") or {}
    assert "mode" in inputs, "sonar.yml: workflow_dispatch must expose a `mode` input"


def test_sonar_never_appears_in_any_pr_blocking_needs_chain() -> None:
    """No OTHER workflow in this repo may reference a `sonar` job/workflow in
    a `needs:` list -- sonar.yml is a separate workflow file with no
    `pull_request` trigger, so this is a belt-and-suspenders static check that
    no sibling workflow was wired to block on it."""
    workflows_dir = _REPO_ROOT / ".github" / "workflows"
    for path in sorted(workflows_dir.glob("*.yml")):
        if path.name == "sonar.yml":
            continue
        text = path.read_text(encoding="utf-8")
        assert "needs: sonar" not in text and "- sonar" not in text.replace("- sonar-project", ""), (
            f"{path.name}: must not gate on a `sonar` job -- sonar.yml is informational-only"
        )


# ---------------------------------------------------------------------------
# Artefact aggregation: *-reports pattern (contracts/artefact-naming.md).
# ---------------------------------------------------------------------------
def test_sonar_downloads_reports_glob_pattern() -> None:
    """Artifact name ends `-reports`; consumers glob `pattern: '*-reports'`
    (contract Invariant 2)."""
    workflow = _workflow_yaml()
    patterns = [
        step.get("with", {}).get("pattern")
        for job in workflow.get("jobs", {}).values()
        for step in job.get("steps", [])
        if isinstance(step, dict) and "download-artifact" in str(step.get("uses", ""))
    ]
    assert "*-reports" in patterns, f"sonar.yml must download with pattern: '*-reports', found {patterns!r}"


def test_sonar_wires_coverage_report_paths_comma_joined() -> None:
    """No single merged `coverage.xml` -- Sonar merges server-side from a
    comma-joined `sonar.python.coverage.reportPaths` list (contract)."""
    text = _workflow_text()
    assert "sonar.python.coverage.reportPaths" in text, "sonar.yml must wire sonar.python.coverage.reportPaths"


# ---------------------------------------------------------------------------
# Fork-safe degradation: skip-green without SONAR_TOKEN (T064).
# ---------------------------------------------------------------------------
def test_sonar_skips_green_without_token_never_hard_fails() -> None:
    """Fork-safe: absent `SONAR_TOKEN`, the job must degrade to an advisory
    skip, never a hard failure. Every Sonar-scanning step must be gated on the
    resolved token-availability output."""
    workflow = _workflow_yaml()
    text = _workflow_text()
    assert "SONAR_TOKEN" in text, "sonar.yml must reference secrets.SONAR_TOKEN"

    scan_steps = [
        step
        for job in workflow.get("jobs", {}).values()
        for step in job.get("steps", [])
        if isinstance(step, dict) and "sonarqube-scan-action" in str(step.get("uses", ""))
    ]
    assert scan_steps, "sonar.yml must run SonarSource/sonarqube-scan-action"
    for step in scan_steps:
        condition = str(step.get("if", ""))
        assert "enabled" in condition or "SONAR_TOKEN" in condition, f"sonar.yml: the scan step must be gated on token availability, got if: {condition!r}"

    # A missing-token run must not be a bare unconditional job -- there must be
    # a non-fatal notice path (never a `exit 1` unconditional on token absence).
    assert "::error::" not in text.split("SONAR_TOKEN")[0] or "enabled=false" in text, "sonar.yml must not hard-fail before the token-availability check"
    assert "enabled=false" in text, "sonar.yml must emit an explicit disabled/skip signal when SONAR_TOKEN is absent"


# ---------------------------------------------------------------------------
# Stock runners + no private-credential leakage (FR-017/C-010, DIR-050).
# ---------------------------------------------------------------------------
def test_sonar_uses_stock_runners_not_blacksmith() -> None:
    text = _workflow_text().lower()
    assert "blacksmith" not in text, "sonar.yml must use stock GitHub-hosted runners, never the retired private Blacksmith producer"


def test_sonar_carries_no_sk_ci_token() -> None:
    text = _workflow_text()
    assert "SK_CI_TOKEN" not in text, "sonar.yml is a public informational job -- it must never reference SK_CI_TOKEN"
    assert "Configure private git dependencies" not in text


def test_sonar_never_echoes_the_token_value() -> None:
    """DIR-050: never echo the secret's VALUE. Mentioning the token's env-var
    *name* in a human-readable notice (e.g. guiding an operator to provision
    it) is fine and expected; interpolating `secrets.SONAR_TOKEN` or a bare
    `$SONAR_TOKEN`/`${SONAR_TOKEN}` shell expansion into an echo would leak
    the value into job logs and must never appear."""
    text = _workflow_text()
    leak_patterns = (
        "echo ${{ secrets.SONAR_TOKEN",
        'echo "${{ secrets.SONAR_TOKEN',
        "echo $SONAR_TOKEN",
        'echo "$SONAR_TOKEN',
        "echo ${SONAR_TOKEN}",
    )
    for line in text.splitlines():
        stripped = line.strip()
        for pattern in leak_patterns:
            assert pattern not in stripped, f"sonar.yml must never echo the SONAR_TOKEN value: {stripped!r}"


# ---------------------------------------------------------------------------
# SHA-pinning (DIR-051).
# ---------------------------------------------------------------------------
def test_sonar_every_action_is_sha_pinned() -> None:
    workflow = _workflow_yaml()
    uses_values = _iter_uses_values(workflow.get("jobs", {}))
    assert uses_values, "sonar.yml must invoke at least one action"
    local_or_reusable = [u for u in uses_values if u.startswith("./")]
    external = [u for u in uses_values if not u.startswith("./")]
    assert external, "sonar.yml must invoke at least one external (non-reusable-workflow) action"
    for uses in external:
        assert _SHA_PIN_RE.match(uses), f"sonar.yml: action not SHA-pinned (DIR-051): {uses!r}"
    assert not local_or_reusable or all(u.startswith("./") for u in local_or_reusable)


def test_sonar_pins_both_sonar_actions() -> None:
    text = _workflow_text()
    assert re.search(r"SonarSource/sonarqube-scan-action@[0-9a-f]{40}", text), "sonar.yml must SHA-pin SonarSource/sonarqube-scan-action"
    assert re.search(r"SonarSource/sonarqube-quality-gate-action@[0-9a-f]{40}", text), "sonar.yml must SHA-pin SonarSource/sonarqube-quality-gate-action"


# ---------------------------------------------------------------------------
# projectVersion derivation (T063).
# ---------------------------------------------------------------------------
def test_sonar_derives_project_version_from_pyproject() -> None:
    text = _workflow_text()
    assert "pyproject.toml" in text, "sonar.yml must derive sonar.projectVersion from pyproject.toml"
    assert "sonar.projectVersion" in text


# ---------------------------------------------------------------------------
# Cross-surface DIR-051 pin parity.
#
# Every workflow that analyses the SAME SonarCloud project and hands
# SONAR_TOKEN to the SonarSource actions is bound to every other, so a pin
# bumped on one surface and not the others is caught (squad pass 2 MAJOR on
# PR #4013: a floating tag here was a supply-chain hole).
#
# DISPOSITION RECORD (mission sonar-per-pr-coverage-reuse, FR-010/C-005). Three
# guards here resolved an operand from `ci-quality.yml`'s retiring `sonarcloud`
# job:
#
#   * the parity guard below was RELOCATED -- its operand set is re-pointed at
#     the surviving surfaces and the relation is carried over verbatim. It is
#     the anti-drift guarantee and was never a candidate for deletion;
#   * `test_ci_quality_sonarcloud_job_pins_both_sonar_actions` was RETIRED AS
#     MOOT: ci-quality.yml no longer references either SonarSource action, so
#     there is nothing left in it for DIR-051 to pin. The property holds on
#     both live surfaces (`test_sonar_pins_both_sonar_actions`,
#     `test_report_job_actions_are_all_sha_pinned`);
#   * `test_ci_quality_and_sonar_pin_the_same_sonar_action_shas`, the
#     two-surface ancestor of the parity guard, was RETIRED AS MOOT: re-pointing
#     its operand would have made it a duplicate of the relocated guard.
#
# The reasons are recorded in tests/release/pinning_rule_inventory.json and the
# freshness gate proves each one against the live tree.
# ---------------------------------------------------------------------------
_SONAR_SCAN_PIN_RE = re.compile(r"SonarSource/sonarqube-scan-action@([0-9a-f]{40})")
_SONAR_GATE_PIN_RE = re.compile(r"SonarSource/sonarqube-quality-gate-action@([0-9a-f]{40})")

#: Every LIVE workflow that analyses this project's SonarCloud key. Declared in
#: one place so a fourth surface joins the parity relation by one edit, and so
#: narrowing the set is a reviewed edit rather than an operand quietly going
#: missing from an assertion.
_SONAR_SURFACES: tuple[str, ...] = ("sonar.yml", "ci-aggregate.yml")


# ---------------------------------------------------------------------------
# WP05 — the per-change reporting job in ci-aggregate.yml.
#
# Mission ``sonar-per-pr-coverage-reuse-01M2FR32``. Contract:
# ``kitty-specs/sonar-per-pr-coverage-reuse-01M2FR32/contracts/reporting-job-contract.md``.
#
# **Declared limit (C-006).** A ``workflow_run`` handler executes only the
# DEFAULT-BRANCH copy of its workflow file, so this job cannot run on the pull
# request that introduces it. Its proof is therefore BEHAVIOURAL over an
# extracted evaluator, not an observed run: the §C1 execution condition is
# authored as a ``<<'PY' ... PY`` heredoc reading its inputs from the
# environment, and the tests below extract it and execute it with synthetic
# payloads (the harness ``tests/architectural/test_dual_mode_contract.py`` uses
# for ``ci-router.yml``'s ``router-gate``). The first post-integration run is
# observed and recorded by WP06/T032 -- never claimed here.
#
# **Each conjunct is asserted SEPARATELY.** A single whole-condition-string
# assertion would make dropping the same-origin clause -- this mission's
# principal security change -- invisible, and would turn every future edit into
# churn.
# ---------------------------------------------------------------------------
_CI_AGGREGATE_PATH = _REPO_ROOT / ".github" / "workflows" / "ci-aggregate.yml"

#: The per-change reporting job and the terminal verdict job WP05 adds.
_REPORT_JOB = "sonar-pr"
_VERDICT_JOB = "aggregate-gate"

#: The only two trees the change under review may replace (§C3). Everything the
#: scanner's configuration is read from -- ``sonar-project.properties``,
#: ``pyproject.toml``, ``scripts/`` -- stays at trusted content.
_ANALYSED_TREES = ("src", "tests")

_HEREDOC_RE = re.compile(r"<<'PY'\n(.*?)\nPY", re.DOTALL)

#: The NFR-008 binding, as the shell actually runs it. Pinned as one logical
#: command rather than as a substring: a bare ``"verify-revision" in script``
#: check stays green when the invocation is deleted and only the comment that
#: explains it remains -- the §C5 non-vacuity floor forbids exactly that.
_VERIFY_REVISION_COMMAND = (
    'python3 scripts/ci/sonar_pr_analysis.py verify-revision --source out/aggregate/source/source.json --fetched "$(git rev-parse FETCH_HEAD)"'
)


def _live_lines(script: str) -> list[str]:
    """*script*'s EXECUTABLE lines: comments and blanks dropped, ``\\``
    continuations folded into the single logical command the shell runs.

    Every assertion about what a step *does* reads this, never the raw text --
    prose that merely names a command must not be able to satisfy it.
    """
    lines: list[str] = []
    pending = ""
    for raw in script.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        pending = f"{pending} {stripped}" if pending else stripped
        if pending.endswith("\\"):
            pending = pending[:-1].rstrip()
            continue
        lines.append(pending)
        pending = ""
    if pending:
        lines.append(pending)
    return lines


def _ci_aggregate_text() -> str:
    if not _CI_AGGREGATE_PATH.exists():
        pytest.fail(f"ci-aggregate.yml missing: {_CI_AGGREGATE_PATH.relative_to(_REPO_ROOT)}")
    return _CI_AGGREGATE_PATH.read_text(encoding="utf-8")


def _ci_aggregate_yaml() -> dict[str, Any]:
    loaded = yaml.safe_load(_ci_aggregate_text())
    assert isinstance(loaded, dict), "ci-aggregate.yml did not parse to a mapping"
    return loaded


def _ci_aggregate_job(name: str) -> dict[str, Any]:
    jobs = _ci_aggregate_yaml().get("jobs") or {}
    job = jobs.get(name)
    if not isinstance(job, dict):
        pytest.fail(f"ci-aggregate.yml: job {name!r} is missing (WP05 not yet delivered); jobs present: {sorted(jobs)}")
    return job


def _report_job_step(fragment: str) -> dict[str, Any]:
    """The reporting job's step whose name contains *fragment*."""
    for step in _ci_aggregate_job(_REPORT_JOB).get("steps") or []:
        if isinstance(step, dict) and fragment.lower() in str(step.get("name", "")).lower():
            return step
    pytest.fail(f"ci-aggregate.yml: the {_REPORT_JOB!r} job has no step named like {fragment!r}")


# ---------------------------------------------------------------------------
# T023 — the §C1 execution condition, proven conjunct by conjunct.
# ---------------------------------------------------------------------------
#: Slugs the evaluator reports in its ``unmet`` output. One slug per contract
#: §C1 row; the tests below each unmet exactly one of them, so a dropped
#: conjunct reds exactly one named test rather than perturbing a shared string.
_CONJUNCT_PULL_REQUEST_EVENT = "pull-request-event"
_CONJUNCT_SAME_ORIGIN = "same-origin"
_CONJUNCT_ASSEMBLY_SUCCEEDED = "assembly-succeeded"
_CONJUNCT_ASSEMBLY_COMPLETE = "assembly-complete"
_CONJUNCT_COVERAGE_AVAILABLE = "coverage-available"
_CONJUNCT_CREDENTIAL_PRESENT = "credential-present"

_THIS_REPOSITORY = "spec-kitty/spec-kitty"


def _extract_gate_script() -> str:
    step = _report_job_step("execution condition")
    match = _HEREDOC_RE.search(str(step.get("run", "")))
    if match is None:
        pytest.fail(
            "ci-aggregate.yml: the execution-condition step must carry its evaluator in a "
            "`<<'PY' ... PY` heredoc so the condition is extractable and its behaviour testable "
            "(C-006) -- a condition inlined into a workflow `if:` expression cannot be executed by a test"
        )
    return match.group(1)


def _run_gate_script(
    tmp_path: Path,
    *,
    needs: dict[str, Any] | None = None,
    source: dict[str, Any] | None = None,
    repository: str = _THIS_REPOSITORY,
    token_present: bool = True,
) -> dict[str, str]:
    """Execute the extracted evaluator and return its parsed step outputs."""
    script_path = tmp_path / "sonar_pr_gate.py"
    script_path.write_text(_extract_gate_script(), encoding="utf-8")
    output_path = tmp_path / "github_output"
    output_path.touch()
    env = dict(os.environ)
    env.update(
        {
            "NEEDS_JSON": json.dumps(_needs_context() if needs is None else needs),
            "SOURCE_JSON": json.dumps(_source_context() if source is None else source),
            "THIS_REPOSITORY": repository,
            "SONAR_TOKEN_PRESENT": "true" if token_present else "false",
            "GITHUB_OUTPUT": str(output_path),
        }
    )
    completed = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True, env=env, check=False)
    assert completed.returncode == 0, (
        f"the execution-condition evaluator must NEVER fail the job -- a withheld report is a skip, never a failure (FR-008/NFR-003); stderr: {completed.stderr}"
    )
    outputs: dict[str, str] = {}
    for line in output_path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            outputs[key] = value
    return outputs


def _needs_context(*, result: str = "success", complete: str = "true", coverage: str = "true") -> dict[str, Any]:
    return {"collect": {"result": result, "outputs": {"complete": complete, "coverage": coverage, "mode": "pr", "missing": ""}}}


def _source_context(*, event: str = "pull_request", head_repository: str | None = _THIS_REPOSITORY) -> dict[str, Any]:
    return {
        "event": event,
        "conclusion": "success",
        "head_branch": "issue-4334-sonar-reuse-shard-coverage",
        "head_repository": None if head_repository is None else {"full_name": head_repository},
    }


def test_execution_condition_runs_when_all_five_conjuncts_hold(tmp_path: Path) -> None:
    """Baseline. Without it the five refusals below could be satisfied by an
    evaluator that never runs at all."""
    outputs = _run_gate_script(tmp_path)
    assert outputs.get("run") == "true", f"all five conjuncts hold, so the report must run; got {outputs!r}"
    assert outputs.get("unmet", "") == ""


def test_execution_condition_refuses_a_triggering_run_that_is_not_a_pull_request(tmp_path: Path) -> None:
    """§C1 conjunct 1 (FR-014, C-001).

    ``github.event_name == 'pull_request'`` -- the retiring job's condition --
    is ALWAYS false under ``workflow_run``, so a verbatim port would gate a job
    that never runs. The condition must be expressed in the triggering run's own
    vocabulary, and must exclude a push to the primary branch.
    """
    outputs = _run_gate_script(tmp_path, source=_source_context(event="push"))
    assert outputs.get("run") == "false"
    assert outputs.get("unmet") == _CONJUNCT_PULL_REQUEST_EVENT


def test_execution_condition_refuses_a_foreign_head_repository(tmp_path: Path) -> None:
    """§C1 conjunct 2 (FR-011, NFR-004, C-003) -- the mission's principal
    security change.

    ``workflow_run`` runs in base-repo context with full credential access
    regardless of the contribution's origin, so secret withholding no longer
    provides this guarantee and ``source.json`` carries no origin field. This
    conjunct IS the control.
    """
    outputs = _run_gate_script(tmp_path, source=_source_context(head_repository="someone-else/spec-kitty"))
    assert outputs.get("run") == "false"
    assert outputs.get("unmet") == _CONJUNCT_SAME_ORIGIN


def test_execution_condition_refuses_a_missing_head_repository(tmp_path: Path) -> None:
    """Fail CLOSED: an absent origin signal is not a same-origin signal."""
    outputs = _run_gate_script(tmp_path, source=_source_context(head_repository=None))
    assert outputs.get("run") == "false"
    assert outputs.get("unmet") == _CONJUNCT_SAME_ORIGIN


def test_execution_condition_refuses_an_assembly_that_did_not_succeed(tmp_path: Path) -> None:
    """§C1 conjunct 3 (FR-004)."""
    outputs = _run_gate_script(tmp_path, needs=_needs_context(result="failure"))
    assert outputs.get("run") == "false"
    assert outputs.get("unmet") == _CONJUNCT_ASSEMBLY_SUCCEEDED


def test_execution_condition_refuses_an_incomplete_measurement(tmp_path: Path) -> None:
    """§C1 conjunct 4 (FR-007, NFR-006).

    The reconciled artefact uploads even when the assembly fails
    (``if: always()`` / ``if-no-files-found: warn``) and ``complete=false`` is
    written BEFORE the assembly exits, so artefact presence is not evidence of
    completeness. Publishing a partial figure reads as a coverage regression.
    """
    outputs = _run_gate_script(tmp_path, needs=_needs_context(complete="false"))
    assert outputs.get("run") == "false"
    assert outputs.get("unmet") == _CONJUNCT_ASSEMBLY_COMPLETE


def test_execution_condition_refuses_an_empty_coverage_set(tmp_path: Path) -> None:
    outputs = _run_gate_script(tmp_path, needs=_needs_context(coverage="false"))
    assert outputs.get("run") == "false"
    assert outputs.get("unmet") == _CONJUNCT_COVERAGE_AVAILABLE


def test_execution_condition_skips_with_an_advisory_notice_when_the_credential_is_absent(tmp_path: Path) -> None:
    """§C1 conjunct 5 (FR-008). Absent credential => skip, NEVER fail.

    The ``secrets`` context is unavailable in a job-level ``if:``, which is why
    this conjunct lives in the evaluator rather than in the workflow expression.
    """
    outputs = _run_gate_script(tmp_path, token_present=False)
    assert outputs.get("run") == "false"
    assert outputs.get("unmet") == _CONJUNCT_CREDENTIAL_PRESENT


def test_execution_condition_reports_every_unmet_conjunct_not_merely_the_first(tmp_path: Path) -> None:
    """The evaluator decides each conjunct on its own.

    Short-circuiting on the first failure would make the log say "not a pull
    request" while the same-origin clause was also broken -- and would let a
    later edit drop a clause that is masked by an earlier one.
    """
    outputs = _run_gate_script(
        tmp_path,
        source=_source_context(event="push", head_repository="someone-else/spec-kitty"),
        needs=_needs_context(result="failure", complete="false"),
        token_present=False,
    )
    assert outputs.get("run") == "false"
    assert set((outputs.get("unmet") or "").split(",")) == {
        _CONJUNCT_PULL_REQUEST_EVENT,
        _CONJUNCT_SAME_ORIGIN,
        _CONJUNCT_ASSEMBLY_SUCCEEDED,
        _CONJUNCT_ASSEMBLY_COMPLETE,
        _CONJUNCT_CREDENTIAL_PRESENT,
    }


def test_every_scanning_step_is_gated_on_the_resolved_execution_condition() -> None:
    """The evaluator is only a guarantee if the steps that follow honour it."""
    steps = _ci_aggregate_job(_REPORT_JOB).get("steps") or []
    assert len(steps) > 1, "the reporting job must do something after evaluating its condition"
    for step in steps[1:]:
        condition = str(step.get("if", ""))
        assert "steps.gate.outputs.run" in condition, (
            f"ci-aggregate.yml: step {step.get('name')!r} runs regardless of the resolved execution condition (if: {condition!r})"
        )


# ---------------------------------------------------------------------------
# T025/T026 — the job-level declarations (§C1's shape, §C4's guarantees).
#
# The two predicates below are WP04's, imported rather than re-derived: that
# module is the mission's single authority for "is this reporting job declared
# non-blocking / same-origin" (charter SO#6, DIRECTIVE_044), and its docstring
# states they take a path and a job name precisely so WP05 can bind them to the
# real job. WP04 proves them against synthetic workflows; these bind them to the
# shipped file. Imports are LAZY (inside the test bodies) so this module always
# collects.
# ---------------------------------------------------------------------------
def test_report_job_condition_carries_a_gating_same_origin_conjunct() -> None:
    """§C1 conjunct 2 at the workflow-expression layer (mutation 6).

    The evaluator's refusal (above) and this conjunct are two independent
    enforcements of the same guarantee; removing either must red something.
    """
    from tests.architectural import _gate_coverage as gc
    from tests.architectural.test_no_duplicate_suite_execution import SAME_ORIGIN_TERM, same_origin_conjunct

    condition = gc.load_workflow_model(_CI_AGGREGATE_PATH).job_if[_REPORT_JOB]
    assert same_origin_conjunct(condition) == SAME_ORIGIN_TERM, (
        f"ci-aggregate.yml: the {_REPORT_JOB!r} job's `if:` must carry a top-level, gating `{SAME_ORIGIN_TERM}` conjunct (FR-011/NFR-004), got: {condition!r}"
    )


#: The retiring job's trigger vocabulary. On a ``workflow_run`` handler
#: ``github.event_name`` is the string ``workflow_run``, so this literal is
#: UNSATISFIABLE here: a job carrying it would never run, and an assertion
#: carrying it would pass over a job that never runs.
_UNSATISFIABLE_PR_LITERAL = "github.event_name == 'pull_request'"

#: The four §C1 conjuncts expressible in the job-level ``if:``, each as the
#: operand pair it must relate. The fifth (credential presence) is not
#: expressible there -- the ``secrets`` context is unavailable in a job ``if:``
#: -- and is proven behaviourally by the evaluator tests above.
_EXPRESSIBLE_CONJUNCTS: tuple[tuple[str, str, str], ...] = (
    (_CONJUNCT_PULL_REQUEST_EVENT, "github.event.workflow_run.event", "'pull_request'"),
    (_CONJUNCT_SAME_ORIGIN, "github.event.workflow_run.head_repository.full_name", "github.repository"),
    (_CONJUNCT_ASSEMBLY_SUCCEEDED, "needs.collect.result", "'success'"),
    (_CONJUNCT_ASSEMBLY_COMPLETE, "needs.collect.outputs.complete", "'true'"),
)


def test_report_job_condition_asserts_every_conjunct_individually() -> None:
    """FR-014 / C-001, REWRITTEN from the retiring job's pull-request-only pin.

    The rule this replaces asserted the retiring job's normalized ``if:`` was
    EXACTLY ``github.event_name == 'pull_request'``. The property it guarded --
    the per-change report must not run on the primary branch, where it would
    displace the nightly's full-coverage analysis as ``main``'s standing
    SonarCloud branch analysis and degrade the baseline every PR is measured
    against -- still matters. Its expression cannot survive: the report is now a
    ``workflow_run`` handler, where ``github.event_name`` is ``workflow_run``,
    so a verbatim port would have been a literal that is never true, asserted
    over a job that never runs. Both halves would have looked green.

    So it is re-expressed in the new trigger's vocabulary, and -- per
    ``contracts/gate-disposition-contract.md`` -- asserts EACH CONJUNCT
    INDIVIDUALLY as a top-level ``&&`` term, never the whole condition as one
    string. A whole-string assertion is brittle against reordering AND, far
    worse, hides which clause a future edit removed: it is exactly how the
    same-origin clause (this mission's principal security change, NFR-004)
    could become a text-search artefact. ``top_level_conjuncts`` is WP04's,
    imported rather than re-derived (charter SO#6), so a term reached only
    through an ``||`` -- which gates nothing -- is not counted as present.
    """
    from tests.architectural import _gate_coverage as gc
    from tests.architectural.test_no_duplicate_suite_execution import top_level_conjuncts

    condition = gc.load_workflow_model(_CI_AGGREGATE_PATH).job_if[_REPORT_JOB]
    conjuncts = top_level_conjuncts(condition)
    assert conjuncts, f"ci-aggregate.yml: the {_REPORT_JOB!r} job must carry a gating `if:`, got: {condition!r}"

    for slug, left, right in _EXPRESSIBLE_CONJUNCTS:
        matching = [term for term in conjuncts if left in term and right in term and "==" in term]
        assert matching, (
            f"ci-aggregate.yml: the {_REPORT_JOB!r} job's `if:` has no top-level conjunct relating "
            f"{left} to {right} (§C1 {slug!r}) — conjuncts present: {conjuncts}"
        )

    assert _UNSATISFIABLE_PR_LITERAL not in str(condition), (
        f"ci-aggregate.yml: the {_REPORT_JOB!r} job's `if:` carries {_UNSATISFIABLE_PR_LITERAL!r}, the "
        "RETIRING job's vocabulary. On a workflow_run handler github.event_name is 'workflow_run', so "
        "that literal is never true and the job would never run — read "
        "github.event.workflow_run.event instead"
    )


def test_report_job_condition_never_uses_always() -> None:
    """§C1: ``always()`` is PROHIBITED on this job.

    The sibling ``diff-cover`` gate pairs ``always()`` with an internal
    completeness re-check; copying that shape without the re-check publishes a
    partial figure that reads as a coverage regression.
    """
    from tests.architectural import _gate_coverage as gc
    from tests.architectural.test_no_duplicate_suite_execution import condition_uses_always

    condition = gc.load_workflow_model(_CI_AGGREGATE_PATH).job_if[_REPORT_JOB]
    assert not condition_uses_always(condition), f"ci-aggregate.yml: the {_REPORT_JOB!r} job must not use always(), got: {condition!r}"


def test_report_job_declares_both_non_blocking_guarantees() -> None:
    """§C4 (NFR-003, SC-006, mutation 5): job-level ``continue-on-error`` AND
    exclusion from the terminal verdict.

    ``continue-on-error`` keeps the JOB green but not the workflow-run
    conclusion that ``scripts/ci/fleet_verdict.py`` reads, so the two are
    separate, separately-removable guarantees. The third surface -- branch
    protection -- is outside the repository and is declared, never claimed.
    """
    from tests.architectural.test_no_duplicate_suite_execution import missing_non_blocking_declarations

    missing = missing_non_blocking_declarations(_CI_AGGREGATE_PATH, _REPORT_JOB, verdict_job=_VERDICT_JOB)
    assert missing == frozenset(), f"ci-aggregate.yml: the {_REPORT_JOB!r} job lacks non-blocking declaration(s): {sorted(missing)}"


def _run_verdict_script(tmp_path: Path, needs: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    """Execute the verdict job's extracted evaluator against a *needs* context.

    The tolerance is a PREDICATE, so it is tested by running it. Asserting on
    the step's text instead is satisfied by the evaluator's own ``print(...)``
    wording, which names the tolerance without implementing it.
    """
    for step in _ci_aggregate_job(_VERDICT_JOB).get("steps") or []:
        match = _HEREDOC_RE.search(str(step.get("run", "")))
        if match is not None:
            script_path = tmp_path / "aggregate_verdict.py"
            script_path.write_text(match.group(1), encoding="utf-8")
            env = dict(os.environ)
            env["NEEDS_JSON"] = json.dumps(needs)
            return subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True, env=env, check=False)
    pytest.fail(
        f"ci-aggregate.yml: {_VERDICT_JOB!r} must carry its evaluator in a `<<'PY' ... PY` heredoc so its "
        "tolerance is executable by a test rather than merely described in the step's output"
    )


def test_verdict_job_is_skipped_tolerant_and_excludes_the_report(tmp_path: Path) -> None:
    """§C4's declarable seam, modelled on ``ci-router.yml``'s ``router-gate``.

    NOT ``ci-quality.yml``'s ``quality-gate``: both siblings here are
    legitimately skippable (``collect`` carries its own ``if:``; ``diff-cover``
    was observed skipped in run 34842534281), so a verbatim port of the
    strict-success form would fail the verdict on every such run.
    """
    verdict = _ci_aggregate_job(_VERDICT_JOB)
    needs = verdict.get("needs")
    needs = [needs] if isinstance(needs, str) else list(needs or [])
    assert _REPORT_JOB not in needs, (
        f"ci-aggregate.yml: {_VERDICT_JOB!r} must EXCLUDE {_REPORT_JOB!r} -- that exclusion is the workflow-run-conclusion half of the non-blocking guarantee (§C4)"
    )
    assert needs, f"ci-aggregate.yml: {_VERDICT_JOB!r} must gate on the blocking jobs"
    assert "always()" in str(verdict.get("if", "")), f"ci-aggregate.yml: {_VERDICT_JOB!r} must evaluate on every outcome"
    tolerated = _run_verdict_script(tmp_path, {"collect": {"result": "success"}, "diff-cover": {"result": "skipped"}})
    assert tolerated.returncode == 0, (
        f"ci-aggregate.yml: {_VERDICT_JOB!r} must tolerate a SKIPPED sibling -- a verbatim port of "
        "ci-quality.yml's strict-success quality-gate would fail the verdict on every run where a "
        f"legitimately-skippable sibling was skipped (as diff-cover was in run 34842534281); stderr: {tolerated.stderr}"
    )
    failed = _run_verdict_script(tmp_path, {"collect": {"result": "success"}, "diff-cover": {"result": "failure"}})
    assert failed.returncode != 0, (
        f"ci-aggregate.yml: {_VERDICT_JOB!r}'s skipped-tolerance must not be blanket tolerance -- a FAILED "
        f"blocking sibling must still fail the terminal verdict; stdout: {failed.stdout}"
    )


# ---------------------------------------------------------------------------
# T025 — supply chain, blast radius, and the source-tree delivery mechanism.
# ---------------------------------------------------------------------------
def test_report_job_actions_are_all_sha_pinned() -> None:
    """DIR-051. A verbatim relocation of the retiring job would carry
    ``actions/checkout@v4`` and ``astral-sh/setup-uv@v5`` -- floating tags --
    into a file whose every other step is pinned."""
    uses_values = _iter_uses_values(_ci_aggregate_job(_REPORT_JOB))
    assert uses_values, f"ci-aggregate.yml: the {_REPORT_JOB!r} job must invoke at least one action"
    for uses in uses_values:
        assert _SHA_PIN_RE.match(uses), f"ci-aggregate.yml: action not SHA-pinned (DIR-051): {uses!r}"


def test_live_sonar_surfaces_pin_the_same_sonar_action_shas() -> None:
    """Anti-drift across every live Sonar surface (DIR-051).

    RELOCATED by WP06, not dropped: this assertion used to resolve one of its
    operands from ``ci-quality.yml``'s retiring ``sonarcloud`` job, and it is
    the only thing preventing the surfaces' action pins from drifting apart.
    The operand set is now :data:`_SONAR_SURFACES` -- read from one declaration
    rather than spelled into the assertion -- so the relation survives a change
    of membership. The name no longer says "three": with the retirement there
    are two, and a name asserting a count that the data contradicts is the kind
    of stale justification C-005 forbids.

    A surface with NO pin at all reds here rather than being skipped: an absent
    operand is how a parity relation quietly becomes a tautology.
    """
    texts = {name: (_REPO_ROOT / ".github" / "workflows" / name) for name in _SONAR_SURFACES}
    missing = sorted(name for name, path in texts.items() if not path.exists())
    assert not missing, f"declared Sonar surface(s) missing from .github/workflows/: {missing}"
    assert len(_SONAR_SURFACES) >= 2, f"the pin-parity relation needs at least two surfaces to mean anything, got {_SONAR_SURFACES!r}"

    for pattern in (_SONAR_SCAN_PIN_RE, _SONAR_GATE_PIN_RE):
        action = pattern.pattern.split("@(")[0]
        found: dict[str, str] = {}
        for name, path in texts.items():
            match = pattern.search(path.read_text(encoding="utf-8"))
            assert match, f"{name}: {action} is unpinned or absent"
            found[name] = match.group(1)
        assert found == dict.fromkeys(texts, found["sonar.yml"]), (
            f"the live Sonar surfaces pin different commits for {action}: {found} — they analyse the same SonarCloud project and must not drift apart"
        )


def test_report_job_runs_no_test_suite_and_no_dependency_sync() -> None:
    """NFR-007 / FR-013: the whole point is that the measurement is reused.

    ``uv sync --frozen --all-extras`` is deliberately NOT carried over either:
    this job runs no tests, and syncing EXECUTES change-authored build
    configuration in a step holding the publication credential (NFR-004).
    """
    job = _ci_aggregate_job(_REPORT_JOB)
    script = "\n".join(str(step.get("run", "")) for step in job.get("steps") or [])
    for forbidden in ("pytest", "make test", "uv sync", "uv pip install", "pip install"):
        assert forbidden not in script, f"ci-aggregate.yml: the {_REPORT_JOB!r} job must not run {forbidden!r}"


def test_report_job_replaces_only_the_two_analysed_trees() -> None:
    """§C3 as corrected: the base directory stays at the TRUSTED checkout root
    and only the two analysed trees are replaced.

    The refuted design put the change's sources in a subdirectory and pointed
    ``sonar.projectBaseDir`` at it -- but ``sonar-project.properties`` is
    located RELATIVE to the base directory, so the scanner would have loaded the
    change's OWN configuration: the exact FR-012/NFR-005 breach the subdirectory
    was chosen to prevent. Trust is therefore an allowlist of two replaced
    paths, not an enumeration of every file the scanner might read.
    """
    script = str(_report_job_step("analysed trees").get("run", ""))
    trees = " ".join(_ANALYSED_TREES)
    lines = [line.strip() for line in script.splitlines()]
    assert f"rm -rf {trees}" in lines, (
        f"ci-aggregate.yml: the delivery step must `rm -rf {trees}` BEFORE the checkout, so a deletion "
        "in the change under review is honoured rather than leaving a stale trusted file behind"
    )
    checkouts = [line for line in lines if line.startswith("git checkout")]
    assert checkouts == [f'git checkout "$TESTED_SHA" -- {trees}'], (
        "ci-aggregate.yml: the delivery step must restore EXACTLY the two analysed trees from the tested "
        f"revision and nothing else -- every other path (sonar-project.properties, pyproject.toml, scripts/, "
        f".github/) must stay at trusted content; got {checkouts!r}"
    )
    assert lines.index(f"rm -rf {trees}") < lines.index(checkouts[0]), "the delete must precede the checkout"


def test_report_job_binds_the_fetched_revision_to_the_measured_revision() -> None:
    """NFR-008: the fetched merge ref must be proven to equal ``tested_sha``
    before either analysed tree is replaced, and a mismatch must fail LOUD.

    Read over ``_live_lines`` and pinned as the whole invocation, the way
    ``test_report_job_replaces_only_the_two_analysed_trees`` pins the checkout:
    deleting the invocation, truncating its arguments, or demoting it to the
    comment that explains it all red.
    """
    lines = _live_lines(str(_report_job_step("analysed trees").get("run", "")))
    assert _VERIFY_REVISION_COMMAND in lines, (
        "ci-aggregate.yml: the delivery step must EXECUTE the binding of the fetched revision to "
        f"source.json's tested_sha (NFR-008); expected the logical command {_VERIFY_REVISION_COMMAND!r}, got {lines!r}"
    )
    assert "set -euo pipefail" in lines, "ci-aggregate.yml: the delivery step must abort on a failed binding, never continue"
    trees = " ".join(_ANALYSED_TREES)
    assert lines.index(_VERIFY_REVISION_COMMAND) < lines.index(f"rm -rf {trees}"), (
        "ci-aggregate.yml: the binding must precede the tree replacement -- a revision verified after the "
        "change's sources are already in place proves nothing about what is analysed"
    )


def test_report_job_keeps_the_analysis_base_dir_at_the_trusted_root() -> None:
    """§C3: pointing the base directory anywhere else re-creates the refuted
    design, in which the scanner loads the change's own configuration."""
    scan = _report_job_step("SonarCloud Scan")
    base_dir = str((scan.get("with") or {}).get("projectBaseDir", ""))
    assert base_dir == ".", f"ci-aggregate.yml: the scan must analyse the trusted checkout root, got projectBaseDir={base_dir!r}"
    assert "sonar.projectBaseDir" not in _ci_aggregate_text(), "ci-aggregate.yml: the base directory must not be redirected by a -D override either"


def test_report_job_passes_the_publication_settings_explicitly_from_trusted_content() -> None:
    """§C2/§C3: every setting governing WHERE and HOW the report publishes is
    resolved by ``scripts/ci/sonar_pr_analysis.py`` from the trusted tree and
    the authenticated lookup, never read from the change under review."""
    script = "\n".join(str(step.get("run", "")) for step in _ci_aggregate_job(_REPORT_JOB).get("steps") or [])
    assert "scripts/ci/sonar_pr_analysis.py" in script, "ci-aggregate.yml: the reporting job must resolve its arguments through the tested script"
    # Comment lines are excluded: the file DOES name the refused projection, in
    # the prose that explains why it is refused.
    live = "\n".join(line for line in _ci_aggregate_text().splitlines() if not line.strip().startswith("#"))
    assert "workflow_run.pull_requests" not in live, (
        "ci-aggregate.yml: the change identity must come from source.json's validated pr_number, never from "
        "the mutable workflow_run.pull_requests[] projection aggregate_source.py explicitly refuses"
    )


def test_report_job_widens_permissions_job_scoped_only() -> None:
    """The pull-request metadata read needs ``pull-requests: read``. Granting it
    workflow-wide would widen the blast radius of every sibling job."""
    workflow = _ci_aggregate_yaml()
    workflow_permissions = workflow.get("permissions") or {}
    assert "pull-requests" not in workflow_permissions, "ci-aggregate.yml: pull-requests access must NOT be granted workflow-wide"
    report_permissions = _ci_aggregate_job(_REPORT_JOB).get("permissions") or {}
    assert report_permissions.get("pull-requests") == "read", f"ci-aggregate.yml: the {_REPORT_JOB!r} job must declare pull-requests: read"
    # #4355 moved permissions from workflow-level to job-level least-privilege
    # blocks, so "the sibling has no permissions block" is no longer how an
    # unchanged blast radius is expressed. The invariant is unchanged and now
    # states itself directly: no sibling may hold the pull-requests scope this
    # job widens for itself.
    for sibling in ("collect", "diff-cover"):
        sibling_permissions = workflow["jobs"][sibling].get("permissions") or {}
        assert "pull-requests" not in sibling_permissions, (
            f"ci-aggregate.yml: {sibling!r} must not hold pull-requests access — the metadata read is scoped to {_REPORT_JOB!r} alone"
        )


def test_report_job_names_the_publication_blocker_in_tree() -> None:
    """A green pipeline must not mislead a future reader: the report may be
    accepted by CI and still not publish, for a reason recorded as #4350."""
    assert "#4350" in _ci_aggregate_text(), "ci-aggregate.yml: the reporting job must name the publication blocker (#4350) in-tree"


def test_ci_aggregate_never_echoes_the_token_value() -> None:
    """DIR-050, bound to the new host: the evaluator receives a BOOLEAN
    presence signal, never the credential's value."""
    text = _ci_aggregate_text()
    leak_patterns = ("echo ${{ secrets.SONAR_TOKEN", 'echo "${{ secrets.SONAR_TOKEN', "echo $SONAR_TOKEN", 'echo "$SONAR_TOKEN', "echo ${SONAR_TOKEN}")
    for line in text.splitlines():
        for pattern in leak_patterns:
            assert pattern not in line.strip(), f"ci-aggregate.yml must never echo the SONAR_TOKEN value: {line.strip()!r}"
