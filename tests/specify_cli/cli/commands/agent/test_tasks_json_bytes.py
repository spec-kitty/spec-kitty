"""Byte-freeze suite for the 13 ``--json`` emission sites of ``agent tasks``.

Mission ``tasks-py-degod-wave2-01KWH9EQ`` WP01 (FR-005 pre-step, parity-contract
Layer 2). The pre-existing golden harness (``test_tasks_cli_contract.py``)
shape-checks the ``--json`` envelopes via ``_shape()`` — structurally sound but
byte-blind. This suite pins the EXACT stdout bytes of every JSON emission site
in ``src/specify_cli/cli/commands/agent/tasks.py`` (site→subcommand map:
``kitty-specs/tasks-py-degod-wave2-01KWH9EQ/research.md`` D3) so the routing
work of the relocation WPs is provably byte-identical.

Contract semantics:

* One fixture case per emission site — 13 total, no gaps. The ``status --json``
  leg (``RealRender(indent=2).json_envelope`` since WP04; originally a
  status-specific Render subclass at tasks.py:1235, printed at :4117) is ONE
  site: the indent=2 envelope. Fixture ``site`` labels keep freeze-time names.
* Assertion is FULL-STDOUT byte equality (``result.stdout == expected_stdout``)
  — never shape checks, never ``len() == N`` golden counts (CT5 #2076).
* Fixtures were frozen from ACTUAL runs against the untouched tree via
  ``typer.testing.CliRunner`` — never hand-composed.
* "Compact" sites use ``json.dumps`` DEFAULT separators ``(', ', ': ')`` —
  NOT ``separators=(",", ":")`` (research.md D2). The frozen bytes encode this.

Determinism note: ``list-tasks --json`` embeds the absolute task-file path
(``"path": str(task_file)``), which varies with ``tmp_path``. Both the freeze
run and this test normalize the ephemeral project root to the documented
placeholder ``<TMP>`` before comparison (the ONLY transformation applied to
captured stdout); every other byte is compared exactly as emitted.

Fixture data is production-shaped (charter/testing-principles): a real-format
mission slug with a valid 26-char Crockford ULID ``mission_id`` and its
``mid8`` tail, real WP ids, realistic spec/tasks content — no placeholders.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from tests.mocked_env import setup_mocked_env

# In-process CliRunner over the ``app`` object — no subprocess, no git — so the
# whole suite stays in the ``fast`` lane, matching the sibling
# ``test_tasks_cli_contract.py`` (marker-correctness Rules 1 & 2, FR-009).
pytestmark = pytest.mark.fast

runner = CliRunner()

FIXTURES = Path(__file__).parent / "fixtures" / "tasks_cli" / "json"
BYTE_CONTRACTS = FIXTURES / "byte_contracts.json"

#: Placeholder substituted for the ephemeral project root in captured stdout.
#: Applied identically at freeze time and at assert time (see module docstring).
TMP_PLACEHOLDER = "<TMP>"

# Production-shaped mission identity: valid 26-char Crockford-base32 ULID,
# mid8-suffixed slug (mission-identity model, CLAUDE.md 083+).
MISSION_ID = "01KWG4RZ8Q3TCEH2M5N7P9RSTV"
MID8 = MISSION_ID[:8]
MISSION_SLUG = f"checkout-latency-audit-{MID8}"

_SPEC_MD = """\
# Mission Specification: Checkout Latency Audit

## Requirements

### Functional Requirements

- **FR-001**: The checkout pipeline MUST record per-stage latency for every order.
- **FR-002**: A daily rollup MUST flag p95 checkout latency regressions beyond the agreed budget.
"""

_TASKS_MD = """\
# Tasks: Checkout Latency Audit

## WP01 - Baseline latency probe instrumentation

- [ ] T001 Add timing probes around the payment authorization call
- [ ] T002 Emit structured latency events to the metrics sink

## WP02 - Latency regression report rollup

- [ ] T003 Aggregate probe events into the daily latency report
- [ ] T004 Alert when p95 checkout latency regresses beyond budget
"""

_WP01_MD = """\
---
work_package_id: WP01
title: Baseline latency probe instrumentation
dependencies: []
requirement_refs: []
phase: Phase 1 - Instrumentation
agent: "claude:fable:python-pedro:implementer"
agent_profile: python-pedro
shell_pid: "268505"
execution_mode: code_change
---

# Work Package WP01 - Baseline latency probe instrumentation

Instrument the checkout pipeline with per-stage latency probes.

## Activity Log

- 2026-07-01T09:00:00Z - system - Prompt created.
"""

# ``{refs}`` is filled per scenario: ``[]`` for the healthy mission,
# ``["FR-002a"]`` (well-formed grammar, but not declared in ``_SPEC_MD`` --
# requirement-id-grammar-01M3NRCA WP03: a letter suffix is now valid grammar,
# so this reads as unknown_spec_id, not malformed) for the stale-frontmatter
# scenario that triggers the tasks.py:3585 error leg.
_WP02_MD_TEMPLATE = """\
---
work_package_id: WP02
title: Latency regression report rollup
dependencies:
- WP01
requirement_refs: {refs}
phase: Phase 2 - Reporting
agent: ""
agent_profile: ""
shell_pid: ""
execution_mode: code_change
---

# Work Package WP02 - Latency regression report rollup

Aggregate the WP01 probe events into the daily latency regression report.

## Activity Log

- 2026-07-01T09:05:00Z - system - Prompt created.
"""


def build_mission(project_root: Path, *, stale_wp02_refs: bool = False) -> Path:
    """Stage the production-shaped fixture mission under ``project_root``.

    Returns the mission's feature directory. Shared by this suite and the WP01
    freeze script that generated ``byte_contracts.json`` — the frozen bytes are
    only valid against exactly this repository state.
    """
    (project_root / ".kittify").mkdir(exist_ok=True)
    feature_dir = project_root / "kitty-specs" / MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": MISSION_ID,
                "mid8": MID8,
                "mission_slug": MISSION_SLUG,
                "mission_number": 112,
                "mission_type": "software-dev",
                "friendly_name": "Checkout Latency Audit",
            }
        ),
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text(_SPEC_MD, encoding="utf-8")
    (feature_dir / "tasks.md").write_text(_TASKS_MD, encoding="utf-8")
    (tasks_dir / "WP01-baseline-latency-probe-instrumentation.md").write_text(
        _WP01_MD, encoding="utf-8"
    )
    wp02_refs = '["FR-002a"]' if stale_wp02_refs else "[]"
    (tasks_dir / "WP02-latency-regression-report-rollup.md").write_text(
        _WP02_MD_TEMPLATE.format(refs=wp02_refs), encoding="utf-8"
    )
    append_event(
        feature_dir,
        StatusEvent(
            event_id="01KWG4S0B3E7H9JKMNPQRSTVWX",
            mission_slug=MISSION_SLUG,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.APPROVED,
            at="2026-07-01T09:15:00+00:00",
            actor="claude",
            force=True,
            execution_mode="worktree",
        ),
    )
    return feature_dir


@dataclass(frozen=True)
class _CaseSetup:
    """Harness wiring for one byte case (fixture holds the contract data)."""

    #: "bare_project" (no mission staged), "mission", or "mission_stale_refs"
    #: (WP02 frontmatter carries a malformed requirement ref).
    scenario: str
    #: Patch ``_find_mission_slug`` to the fixture slug (False for the case
    #: whose contract IS the real resolver's missing-``--mission`` error).
    resolve_mission: bool = True
    #: Module attrs stubbed to return ``None`` — the established patch seams
    #: (research.md D7) for side-effecting emitters whose output would be
    #: environment-dependent (sparse-checkout probe, event emission).
    null_patches: tuple[str, ...] = ()
    #: Provide a resolved execution workspace (``status`` classifies each WP).
    workspace: bool = False


_SPARSE = "_emit_sparse_session_warning"

# One entry per emission site of research.md D3 — 13 total, keyed identically
# to fixtures/tasks_cli/json/byte_contracts.json.
_CASE_SETUP: dict[str, _CaseSetup] = {
    "missing_mission_flag_error": _CaseSetup("bare_project", resolve_mission=False),
    "add_history_success": _CaseSetup(
        "mission", null_patches=(_SPARSE,)
    ),
    "generic_error_invalid_mark_status": _CaseSetup("mission"),
    "status_success_indent2": _CaseSetup("mission", workspace=True),
    "mark_status_none_resolved_error": _CaseSetup("mission", null_patches=(_SPARSE,)),
    "list_tasks_success": _CaseSetup("mission"),
    "map_requirements_unknown_wp_error": _CaseSetup("mission", null_patches=(_SPARSE,)),
    "map_requirements_malformed_ref_error": _CaseSetup(
        "mission", null_patches=(_SPARSE,)
    ),
    "map_requirements_unknown_spec_ref_error": _CaseSetup(
        "mission", null_patches=(_SPARSE,)
    ),
    "map_requirements_stale_frontmatter_error": _CaseSetup(
        "mission_stale_refs", null_patches=(_SPARSE,)
    ),
    "map_requirements_success": _CaseSetup("mission", null_patches=(_SPARSE,)),
    "validate_workflow_success": _CaseSetup("mission"),
    "list_dependents_success": _CaseSetup("mission"),
}


def _load_cases() -> dict[str, dict[str, Any]]:
    data: dict[str, dict[str, Any]] = json.loads(
        BYTE_CONTRACTS.read_text(encoding="utf-8")
    )
    return data


@dataclass
class _InvokeOutcome:
    """Exit code + normalized stdout of one frozen invocation."""

    exit_code: int
    stdout: str = field(default="")


def invoke_case(name: str, case: dict[str, Any], tmp_path: Path) -> _InvokeOutcome:
    """Stage the case's scenario, run its argv in-process, normalize stdout.

    Shared verbatim with the freeze script: the bytes stored in the fixture
    were produced by THIS function against the untouched tree, so the test
    exercises the exact capture path that generated its expectations.
    """
    setup = _CASE_SETUP[name]
    if setup.scenario != "bare_project":
        build_mission(tmp_path, stale_wp02_refs=setup.scenario == "mission_stale_refs")

    kwargs: dict[str, Any] = {}
    if setup.resolve_mission and setup.scenario != "bare_project":
        kwargs["mission_slug"] = MISSION_SLUG
    if setup.workspace:
        kwargs["workspace_resolution"] = SimpleNamespace(
            execution_mode="code_change", resolution_kind="lane_workspace"
        )
    if setup.null_patches:
        kwargs["extra_patches"] = dict.fromkeys(setup.null_patches)

    argv = [str(arg) for arg in case["argv"]]
    with setup_mocked_env(tmp_path, **kwargs):
        result = runner.invoke(app, argv)

    stdout = (result.stdout or "").replace(str(tmp_path), TMP_PLACEHOLDER)
    return _InvokeOutcome(exit_code=result.exit_code, stdout=stdout)


def test_byte_contracts_pin_all_13_sites() -> None:
    """Layer-2 completeness: 13 cases, keyed 1:1 with the harness setup table."""
    cases = _load_cases()
    assert len(cases) == 13
    assert set(cases) == set(_CASE_SETUP)
    # Every case names its emission site so reviewers can audit D3 coverage.
    assert all(spec["site"].startswith("tasks.py:") for spec in cases.values())


@pytest.mark.parametrize("name", sorted(_CASE_SETUP))
def test_json_emission_site_is_byte_identical(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each emission site's full stdout matches its frozen bytes exactly."""
    case = _load_cases()[name]
    monkeypatch.chdir(tmp_path)
    outcome = invoke_case(name, case, tmp_path)
    assert outcome.exit_code == case["exit_code"], outcome.stdout
    assert outcome.stdout == case["expected_stdout"]
