"""`spec-kitty doctor charter-packs` surfaces the operating-procedures resolution scan (M3).

Every ``collaboration.operating-procedures`` entry on a built-in agent profile
must resolve to a real ``procedure:`` DRG node. This proves the diagnostic is
wired into ``doctor charter-packs``: the shipped (triaged) tree reports a
present-and-empty finding and stays healthy; an injected unresolved entry
populates the finding and flips the report unhealthy.
"""

from __future__ import annotations

import pytest

from specify_cli.cli.commands import _doctrine_collect
from specify_cli.cli.commands._doctrine_collect import _run_operating_procedures_check
from specify_cli.cli.commands._doctrine_health import DoctrineHealthReport

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_clean_built_in_tree_reports_present_and_empty() -> None:
    report = DoctrineHealthReport()

    _run_operating_procedures_check(report)

    # The shipped (triaged) tree resolves every entry: the finding is present
    # and empty, and the scan appends no operating-procedures error.
    assert report.org_drg["operating_procedures_unresolved"] == []
    errors = report.org_drg.get("errors") or []
    assert not any("operating-procedures" in str(e) for e in errors)


def test_unresolved_entry_flips_healthy_and_records_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from charter.offering.agent_profiles import operating_procedures as opmod

    fake = opmod.UnresolvedOpProc(
        profile_id="synthetic-profile",
        entry="not-a-real-procedure",
        reason="no_node",
        resolved_kind=None,
    )
    monkeypatch.setattr(opmod, "resolve_operating_procedure_entries", lambda *a, **k: [fake])
    report = DoctrineHealthReport()

    _run_operating_procedures_check(report)

    finding = report.org_drg["operating_procedures_unresolved"]
    assert finding == [
        {
            "profile_id": "synthetic-profile",
            "entry": "not-a-real-procedure",
            "reason": "no_node",
            "resolved_kind": None,
        }
    ]
    assert report.healthy is False
    errors = report.org_drg["errors"]
    assert isinstance(errors, list)
    assert any("operating-procedures" in str(e) for e in errors)


def test_scan_error_is_recorded_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> object:
        raise RuntimeError("graph unavailable")

    monkeypatch.setattr(_doctrine_collect, "load_built_in_graph", _boom, raising=False)
    # The function imports load_built_in_graph locally; patch at its source.
    from charter.offering.drg import loader

    monkeypatch.setattr(loader, "load_built_in_graph", _boom)
    report = DoctrineHealthReport()

    _run_operating_procedures_check(report)

    assert report.healthy is False
    assert any("operating-procedures scan error" in str(e) for e in report.org_drg.get("errors", []))
