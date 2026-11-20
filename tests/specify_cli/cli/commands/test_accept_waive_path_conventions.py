"""``accept --waive-path-conventions --waive-reason`` (#7566, Mission path-conventions-per-type-01M7VRQM, WP04).

The per-run waiver turns path-convention misses into warnings for one run while strict
metadata validation keeps blocking (FR-009, SC-004). It needs a non-blank reason
(FR-011), is recorded on the acceptance history entry, and is forwarded by
``spec-kitty agent mission accept``. The orchestrator-api path offers no per-run
waiver but honours a well-formed meta.json waiver like the CLI (operator ruling Q4,
FR-013).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.acceptance import collect_feature_summary
from specify_cli.cli.commands.accept import accept

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "content-only-01M7VRQM"
_RUNNER_ENV = {"COLUMNS": "200", "TERM": "dumb"}


def _accept_app() -> typer.Typer:
    app = typer.Typer()
    app.command(name="accept")(accept)
    return app


def _invoke(*args: str) -> Any:
    # A one-command Typer app runs that command directly: pass its options only.
    return CliRunner(env=_RUNNER_ENV).invoke(_accept_app(), list(args), terminal_width=200)


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True)


def _content_repo(tmp_path: Path, *, meta_extra: dict[str, object] | None = None, drop_meta: tuple[str, ...] = ()) -> Path:
    """A content repository with no ``src/`` and one never-claimed work package (a strict metadata issue)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q", ".")
    _git(repo_root, "config", "user.email", "test@test.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "branch", "-M", "main")
    (repo_root / ".kittify").mkdir()
    for build_dir in ("tests", "docs", "packs"):
        (repo_root / build_dir).mkdir()
        (repo_root / build_dir / ".gitkeep").write_text("")
    feature_dir = repo_root / "kitty-specs" / _SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_number": "099",
        "slug": _SLUG,
        "mission_slug": _SLUG,
        "mission_id": "01M7VRQMZZZZZZZZZZZZZZZZZZ",
        "mid8": "01M7VRQM",
        "friendly_name": "Content only",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-11-20T00:00:00Z",
        "contracts": "none",
        "contracts_rationale": "content repository; no interfaces",
        **(meta_extra or {}),
    }
    for key in drop_meta:
        meta.pop(key, None)
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    for name in ("spec.md", "plan.md", "tasks.md"):
        (feature_dir / name).write_text(f"# {name}\nDone.\n")
    (feature_dir / "tasks" / "WP01-content.md").write_text("---\nwork_package_id: WP01\ntitle: Content\ndependencies: []\nsubtasks: []\n---\n\n# WP01\n")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "init")
    return repo_root


def _path_violations(summary: Any) -> list[str]:
    return [entry for entry in summary.path_violations if "workspace path: src/" in entry]


def _missing_agent(summary: Any) -> list[str]:
    return [issue for issue in summary.metadata_issues if "WP01: missing agent" in issue]


# --- FR-009 / SC-004 at the summary seam -------------------------------------------------


def test_per_run_waiver_clears_the_path_miss_but_metadata_stays_strict(tmp_path: Path) -> None:
    repo_root = _content_repo(tmp_path)

    summary = collect_feature_summary(repo_root, _SLUG, strict_metadata=True, mutate_matrix=False, path_conventions_waiver_reason="content repository")

    assert _path_violations(summary) == []
    assert any("workspace path: src/" in warning for warning in summary.warnings)
    assert _missing_agent(summary), summary.metadata_issues
    assert summary.ok is False
    assert summary.path_conventions_waiver_reason == "content repository"


def test_without_a_waiver_the_path_miss_blocks(tmp_path: Path) -> None:
    """FR-013 control: the orchestrator-api call shape (strict, no keyword) still reports the miss."""
    repo_root = _content_repo(tmp_path)

    summary = collect_feature_summary(repo_root, _SLUG, strict_metadata=True, mutate_matrix=False)

    assert _path_violations(summary)
    assert summary.path_conventions_waiver_reason is None


def test_meta_json_waiver_applies_on_the_orchestrator_call_shape(tmp_path: Path) -> None:
    """Operator ruling Q4: the meta.json waiver is Mission data, honoured on every accept path."""
    repo_root = _content_repo(tmp_path, meta_extra={"path_conventions": "waived", "path_conventions_rationale": "content repository"})

    summary = collect_feature_summary(repo_root, _SLUG, strict_metadata=True, mutate_matrix=False)

    assert _path_violations(summary) == []
    assert _missing_agent(summary), summary.metadata_issues


@pytest.mark.parametrize(
    ("reason", "meta_extra"),
    [
        ("content repository", None),
        (None, {"path_conventions": "waived", "path_conventions_rationale": "content repository"}),
    ],
    ids=["per-run", "meta-json"],
)
def test_waiver_never_waives_a_missing_mission_artifact(tmp_path: Path, reason: str | None, meta_extra: dict[str, object] | None) -> None:
    """Landing fold: a path-convention waiver covers remappable layout paths only.

    A missing ``contracts/`` Mission artifact still blocks under strict metadata unless the
    Mission declares the narrower #5298 ``"contracts": "none"`` waiver.
    """
    repo_root = _content_repo(tmp_path, meta_extra=meta_extra, drop_meta=("contracts", "contracts_rationale"))

    summary = collect_feature_summary(repo_root, _SLUG, strict_metadata=True, mutate_matrix=False, path_conventions_waiver_reason=reason)

    contracts_blocks = [entry for entry in summary.path_violations if "contracts" in entry]
    assert contracts_blocks, summary.path_violations
    assert summary.ok is False


# --- FR-011: the CLI refuses a waiver without a reason, before any work -----------------


@pytest.mark.parametrize(
    "args",
    [
        ("--waive-path-conventions",),
        ("--waive-path-conventions", "--waive-reason", "   "),
        ("--waive-reason", "why"),
    ],
    ids=["flag-without-reason", "blank-reason", "reason-without-flag"],
)
def test_misused_waiver_flags_are_refused_before_any_work(args: tuple[str, ...]) -> None:
    with patch("specify_cli.cli.commands.accept._resolve_accept_entry") as entry:
        result = _invoke(*args)

    assert result.exit_code == 2, result.output
    assert "--waive-reason" in result.output
    entry.assert_not_called()


def test_help_lists_the_waiver_flags_and_keeps_lenient_discoverable() -> None:
    result = _invoke("--help")
    assert result.exit_code == 0
    help_text = " ".join(result.output.lower().split())
    assert "--waive-path-conventions" in help_text
    assert "--waive-reason" in help_text
    assert "metadata validation stays strict" in help_text
    assert "path-convention" in help_text


# --- Threading: the reason reaches the summary, metadata strictness is untouched ---------


def test_flag_threads_the_reason_with_strict_metadata(tmp_path: Path) -> None:
    from specify_cli.cli.commands import accept as accept_module

    captured: dict[str, Any] = {}

    def _fake_collect(run: Any, *, lenient: bool, diagnose: bool, normalize_encoding: bool) -> Any:
        captured["lenient"] = lenient
        captured["reason"] = run.path_conventions_waiver_reason
        raise typer.Exit(7)

    with (
        patch.object(accept_module, "_resolve_accept_entry", return_value=(tmp_path, None)),
        patch.object(accept_module, "_resolve_mission_identity", return_value=(_SLUG, tmp_path)),
        patch.object(accept_module, "_check_origin_freshness", side_effect=lambda run, *_a, **_k: run),
        patch.object(accept_module, "_record_no_implementation_attestations"),
        patch.object(accept_module, "_refuse_unevidenced_work"),
        patch.object(accept_module, "_collect_summary_or_exit", side_effect=_fake_collect),
    ):
        result = _invoke("--mission", _SLUG, "--json", "--waive-path-conventions", "--waive-reason", "  content repository  ")

    assert result.exit_code == 7, result.output
    assert captured == {"lenient": False, "reason": "content repository"}


def test_agent_mission_accept_forwards_the_flags() -> None:
    from specify_cli.cli.commands.agent import mission as mission_module
    from specify_cli.cli.commands.agent.mission_accept_merge import accept_feature

    app = typer.Typer()
    app.command(name="accept")(accept_feature)
    with patch.object(mission_module, "top_level_accept") as top_level:
        result = CliRunner(env=_RUNNER_ENV).invoke(app, ["--mission", _SLUG, "--waive-path-conventions", "--waive-reason", "why"], terminal_width=200)

    assert result.exit_code == 0, result.output
    kwargs = top_level.call_args.kwargs
    assert kwargs["waive_path_conventions"] is True
    assert kwargs["waive_reason"] == "why"
    assert kwargs["lenient"] is False


def test_the_stamp_records_the_summarys_waiver_reason(tmp_path: Path) -> None:
    """FR-009: the reason carried on the summary reaches the acceptance history entry."""
    from types import SimpleNamespace

    import specify_cli.acceptance as acceptance
    from specify_cli.acceptance.gates_core import PLANNING_ARTIFACT_ONLY_SKIP_REASON

    summary = SimpleNamespace(
        feature_dir=tmp_path,
        acceptance_matrix_dir=None,
        acceptance_matrix_gate_skip_reason=PLANNING_ARTIFACT_ONLY_SKIP_REASON,
        path_conventions_waiver_reason="content repository",
    )
    with patch.object(acceptance, "record_acceptance") as record:
        acceptance._stamp_acceptance_record(cast(Any, summary), "claude", "local", None)

    assert record.call_args.kwargs["path_conventions_waiver_reason"] == "content repository"
    assert record.call_args.kwargs["lenient"] is False
