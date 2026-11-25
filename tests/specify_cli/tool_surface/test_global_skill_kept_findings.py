"""``doctor tool-surfaces`` names every global skill file the sync kept (#5983, #7700, #2527).

A canonical global skill file whose bytes are not a proven Spec Kitty render is kept,
and so is an edited copy of a retired skill. Both stay byte-for-byte; the report
lists each as a warning so the operator can review it. A project surface that
``--fix`` skipped carries the reason, so the fix never reads as convergence.
"""

from __future__ import annotations

import stat
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from specify_cli.core.config import CLAUDE_CONFIG_DIR_ENV
from specify_cli.tool_surface.enums import ToolSurfaceKind
from specify_cli.tool_surface.findings import (
    GLOBAL_SKILL_KEPT_STALE,
    RETIRED_SKILL_KEPT_EDITED,
    SEVERITY_WARNING,
    make_finding,
)
from specify_cli.tool_surface.model import SurfaceInstance
from specify_cli.tool_surface.repair import RepairResult, explain_skipped
from specify_cli.tool_surface.service import run_tool_surfaces
from specify_cli.tool_surface.status import SurfaceStatus

pytestmark = [pytest.mark.fast]

_KEPT_CODES = {GLOBAL_SKILL_KEPT_STALE, RETIRED_SKILL_KEPT_EDITED}
_PROJECT_SKILL = Path(".claude/skills/spk-run-implement-review/SKILL.md")


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.delenv(CLAUDE_CONFIG_DIR_ENV, raising=False)
    return home


@pytest.fixture
def project(tmp_path: Path, home: Path) -> Path:
    project = tmp_path / "project"
    (project / ".kittify").mkdir(parents=True)
    (project / ".kittify" / "config.yaml").write_text("project:\n  uuid: test-uuid-5983\nagents:\n  available:\n    - claude\n", encoding="utf-8")
    return project


def _seed_global(home: Path, relative: str, data: bytes) -> Path:
    path = home / ".claude" / "skills" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _kept(payload: dict[str, object]) -> list[dict[str, object]]:
    findings = payload["findings"]
    assert isinstance(findings, list)
    return [f for f in findings if f["code"] in _KEPT_CODES]


def test_edited_canonical_global_skill_is_reported_and_left_alone(home: Path, project: Path) -> None:
    baseline = run_tool_surfaces(project, ("claude",)).to_json()
    mine = _seed_global(home, "spk-run-implement-review/SKILL.md", b"# my own notes\n")

    payload = run_tool_surfaces(project, ("claude",)).to_json()

    kept = _kept(payload)
    assert [(f["code"], f["path"], f["severity"], f["tool_key"]) for f in kept] == [(GLOBAL_SKILL_KEPT_STALE, str(mine), SEVERITY_WARNING, "claude")]
    assert kept[0]["repair_command"], "the finding names a remedy"
    assert payload["ok"] == baseline["ok"], "a kept file is a warning, not an error"
    summary, baseline_summary = payload["summary"], baseline["summary"]
    assert isinstance(summary, dict) and isinstance(baseline_summary, dict)
    assert summary["warnings"] == baseline_summary["warnings"] + 1
    assert mine.read_bytes() == b"# my own notes\n"


def test_edited_retired_global_skill_is_reported(home: Path, project: Path) -> None:
    edited = _seed_global(home, "spk-gate-merge/SKILL.md", b"# my merge notes\n")

    kept = _kept(run_tool_surfaces(project, ("claude",)).to_json())

    assert [(f["code"], f["path"]) for f in kept] == [(RETIRED_SKILL_KEPT_EDITED, str(edited))]
    assert edited.read_bytes() == b"# my merge notes\n"


def test_clean_home_reports_no_kept_files(home: Path, project: Path) -> None:
    assert _kept(run_tool_surfaces(project, ("claude",)).to_json()) == []


def test_a_kind_filter_without_charter_skills_leaves_global_findings_out(home: Path, project: Path) -> None:
    _seed_global(home, "spk-run-implement-review/SKILL.md", b"# my own notes\n")

    payload = run_tool_surfaces(project, ("claude",), kinds=[ToolSurfaceKind.COMMAND_SKILL]).to_json()

    assert _kept(payload) == []


def test_a_tool_filter_for_another_agent_leaves_claude_files_out(home: Path, project: Path) -> None:
    _seed_global(home, "spk-run-implement-review/SKILL.md", b"# my own notes\n")

    payload = run_tool_surfaces(project, ("claude", "codex"), tool_filter="codex").to_json()

    assert _kept(payload) == []


def test_fix_reports_kept_global_files_after_the_repair(home: Path, project: Path) -> None:
    mine = _seed_global(home, "spk-run-implement-review/SKILL.md", b"# my own notes\n")

    payload = run_tool_surfaces(project, ("claude",), fix=True).to_json()

    assert [f["path"] for f in _kept(payload)] == [str(mine)]
    assert mine.read_bytes() == b"# my own notes\n"


def test_a_skipped_project_surface_carries_its_reason(home: Path, project: Path) -> None:
    run_tool_surfaces(project, ("claude",), fix=True)
    edited = (project / _PROJECT_SKILL).read_bytes() + b"\nmy note\n"
    path = project / _PROJECT_SKILL
    path.chmod(path.stat().st_mode | stat.S_IWUSR)  # the fix installed it read-only (0444)
    path.write_bytes(edited)

    outcome = run_tool_surfaces(project, ("claude",), fix=True)

    assert (project / _PROJECT_SKILL).read_bytes() == edited
    assert outcome.repair is not None
    repair = outcome.repair.to_json()
    reasons = repair["skipped_reasons"]
    assert isinstance(reasons, dict)
    assert set(reasons) == set(outcome.repair.skipped), "every skipped surface has a reason"
    skill_reasons = [reason for sid, reason in reasons.items() if "spk-run-implement-review" in sid]
    assert skill_reasons and all("drifted" in reason for reason in skill_reasons)


def test_a_file_in_a_shared_root_names_no_single_tool(home: Path, project: Path) -> None:
    shared = home / ".agents" / "skills" / "spk-run-implement-review" / "SKILL.md"
    shared.parent.mkdir(parents=True)
    shared.write_bytes(b"# my own notes\n")

    kept = _kept(run_tool_surfaces(project, ("claude", "codex"), tool_filter="codex").to_json())

    assert [(f["path"], f["tool_key"]) for f in kept] == [(str(shared), None)]


def _status(surface_id: str, state: str, message: str | None) -> SurfaceStatus:
    definition = SimpleNamespace(kind="charter_skill")
    instance = cast(SurfaceInstance, SimpleNamespace(surface_id=surface_id, path=Path("x"), owner="claude", definition=definition))
    findings = (make_finding("managed-file-drift", SEVERITY_WARNING, message),) if message else ()
    return SurfaceStatus(instance=instance, state=state, findings=findings)


def test_explain_skipped_covers_every_skipped_surface() -> None:
    result = RepairResult(skipped=("a", "b", "c", "a"))
    statuses = [_status("a", "drifted", "edited by the user"), _status("b", "not_applicable", None)]

    explained = explain_skipped(result, statuses)

    assert explained.to_json()["skipped_reasons"] == {
        "a": "drifted: edited by the user",
        "b": "not_applicable",
        "c": "not reported after the repair",
    }
