"""Acceptance: inline Feedback Survey trigger hooks (WP06 / T030).

Pins FR-005 / FR-006 / FR-007 / FR-015 / FR-018 through the **production**
CLI entry points (``profile-invocation complete``, ``consolidate``,
``agent mission finalize-tasks``). Never talks to a non-loopback address.
"""

from __future__ import annotations

import json
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import typer
from click.testing import Result
from typer.testing import CliRunner

from specify_cli import app as cli_app
from specify_cli.cli.commands import consolidate as consolidate_module
from specify_cli.feedback.endpoint import ENV_FEEDBACK_URL
from specify_cli.feedback.models import SurveyTrigger
from specify_cli.feedback.preferences import SurveyPreferences, load_preferences, preferences_path
from specify_cli.invocation.executor import ProfileInvocationExecutor
from specify_cli.invocation.modes import ModeOfWork
from specify_cli.invocation.writer import EVENTS_DIR
from tests.reliability.fixtures.mission import (
    MissionFixture,
    WorkPackageSpec,
    append_status_event,
    create_mission_fixture,
    write_work_package,
)
from tests.specify_cli.feedback.loopback_server import loopback_server
from specify_cli.status.models import Lane

pytestmark = [pytest.mark.unit, pytest.mark.fast]

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "invocation" / "fixtures" / "profiles"

_COMPACT_CTX = MagicMock()
_COMPACT_CTX.mode = "compact"
_COMPACT_CTX.text = "compact governance context"

_SURVEY_INPUT = "4\n\n\ny\n"


class ArgvCliRunner(CliRunner):
    """CliRunner that also patches ``sys.argv`` so the CLI sees the real prog name."""

    def invoke(  # type: ignore[override]
        self,
        app: Any,
        args: str | Sequence[str] | None = None,
        **kwargs: Any,
    ) -> Result:
        argv = ["spec-kitty", *(list(args) if args is not None and not isinstance(args, str) else [])]
        with patch.object(sys, "argv", argv):
            return super().invoke(app, args, **kwargs)


runner = ArgvCliRunner(env={"COLUMNS": "200", "TERM": "dumb"})


@pytest.fixture(autouse=True)
def _skip_global_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("specify_cli.runtime.bootstrap.ensure_runtime", lambda: None)
    monkeypatch.setattr("specify_cli.runtime.agent_skills.ensure_global_agent_skills", lambda: None)
    monkeypatch.setattr("specify_cli.runtime.agent_commands.ensure_global_agent_commands", lambda: None)
    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        lambda: __import__(
            "specify_cli.distribution.profile",
            fromlist=["stock_distribution_profile"],
        ).stock_distribution_profile(),
    )
    # Host hooks refuse offers in CI; keep this suite able to exercise the
    # interactive path even when the agent harness exports CI=1.
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr("specify_cli.feedback.hooks.is_ci_env", lambda: False)


def _setup_project(tmp_path: Path) -> Path:
    profiles_dir = tmp_path / ".kittify" / "profiles"
    profiles_dir.mkdir(parents=True)
    for yaml_file in FIXTURES_DIR.glob("*.agent.yaml"):
        shutil.copy(yaml_file, profiles_dir / yaml_file.name)
    (tmp_path / EVENTS_DIR).mkdir(parents=True, exist_ok=True)
    return tmp_path


def _open_invocation(project: Path) -> str:
    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        payload = executor.invoke(
            "implement the request",
            profile_hint="implementer-fixture",
            mode_of_work=ModeOfWork.TASK_EXECUTION,
        )
    return payload.invocation_id


def _run_complete(project: Path, *args: str, input_text: str | None = None, env: dict[str, str] | None = None) -> Result:
    merged_env = {"COLUMNS": "200", "TERM": "dumb", **(env or {})}
    with (
        patch("specify_cli.cli.commands.profile_invocation.find_repo_root", return_value=project),
        patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ),
    ):
        return runner.invoke(
            cli_app,
            ["profile-invocation", "complete", *args],
            input=input_text,
            env=merged_env,
        )


def _read_events(project: Path, invocation_id: str) -> list[dict[str, object]]:
    text = (project / EVENTS_DIR / f"{invocation_id}.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _interactive_env(url: str | None = None) -> dict[str, str]:
    env: dict[str, str] = {"SPEC_KITTY_FORCE_INTERACTIVE": "1"}
    if url is not None:
        env[ENV_FEEDBACK_URL] = url
    return env


# ---------------------------------------------------------------------------
# Op-close: profile-invocation complete (full loopback path)
# ---------------------------------------------------------------------------


def test_op_close_done_offers_and_submits_via_loopback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _setup_project(tmp_path)
    inv_id = _open_invocation(project)
    monkeypatch.setattr("specify_cli.feedback.hooks.is_interactive", lambda: True)

    # CliRunner feeds answers through typer.prompt; the production timed
    # first-question reader uses select()/readline on the real stdin fd and
    # cannot see CliRunner's isolated input. Keep the production
    # ``first_question_timeout_s=30`` call site (unit-tested) but route the
    # timed reader through the same ask path CliRunner can drive.
    from specify_cli.feedback.terminal_form import _default_ask

    monkeypatch.setattr(
        "specify_cli.feedback.terminal_form._read_line_with_timeout",
        lambda prompt, _timeout_s: _default_ask(prompt),
    )

    with loopback_server("ok") as server:
        result = _run_complete(
            project,
            "--invocation-id",
            inv_id,
            "--outcome",
            "done",
            input_text=_SURVEY_INPUT,
            env=_interactive_env(server.url),
        )
        assert result.exit_code == 0, result.output
        events = _read_events(project, inv_id)
        assert events[-1]["event"] == "completed"
        assert events[-1]["outcome"] == "done"
        assert server.wait_for(1, timeout=5.0), f"no submission: {server.received!r}\noutput={result.output!r}"
        body, _headers = server.received[0]
        assert body["trigger"] == "op_close"
        assert body["harness"] == "cli"
        assert body["rating"] == 4


def test_op_close_abandoned_never_offers(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    inv_id = _open_invocation(project)

    with loopback_server("ok") as server:
        result = _run_complete(
            project,
            "--invocation-id",
            inv_id,
            "--outcome",
            "abandoned",
            input_text=_SURVEY_INPUT,
            env=_interactive_env(server.url),
        )
        assert result.exit_code == 0, result.output
        assert not server.wait_for(1, timeout=0.5)
        assert server.received == []
        assert _read_events(project, inv_id)[-1]["outcome"] == "abandoned"


def test_op_close_json_stdout_byte_identical_to_noop_hook(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--json`` stdout must be byte-identical with the hook forced to a no-op."""
    from specify_cli.feedback import hooks as hooks_mod

    project = _setup_project(tmp_path)
    real_hook = hooks_mod.offer_after_op_close

    def _complete_json(inv_id: str, hook: Any) -> Result:
        monkeypatch.setattr("specify_cli.feedback.hooks.offer_after_op_close", hook)
        return _run_complete(
            project,
            "--invocation-id",
            inv_id,
            "--outcome",
            "done",
            "--json",
            env=_interactive_env("http://127.0.0.1:9/feedback"),
        )

    baseline = _complete_json(_open_invocation(project), lambda *_a, **_k: None)
    assert baseline.exit_code == 0, baseline.output

    live = _complete_json(_open_invocation(project), real_hook)
    assert live.exit_code == 0, live.output

    baseline_payload = json.loads(baseline.stdout)
    live_payload = json.loads(live.stdout)
    for payload in (baseline_payload, live_payload):
        payload.pop("invocation_id", None)
    assert live_payload == baseline_payload
    assert set(json.loads(live.stdout)) == {
        "result",
        "invocation_id",
        "outcome",
        "evidence_ref",
        "artifact_links",
        "commit_link",
    }


def test_op_close_non_interactive_leaves_last_shown_untouched(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    inv_id = _open_invocation(project)

    assert not preferences_path().exists()
    with loopback_server("ok") as server:
        result = _run_complete(
            project,
            "--invocation-id",
            inv_id,
            "--outcome",
            "done",
            input_text=_SURVEY_INPUT,
            env={
                "SPEC_KITTY_NON_INTERACTIVE": "1",
                ENV_FEEDBACK_URL: server.url,
            },
        )
        assert result.exit_code == 0, result.output
        assert not server.wait_for(1, timeout=0.5)
        assert server.received == []

    prefs = load_preferences(preferences_path())
    if isinstance(prefs, SurveyPreferences):
        assert prefs.last_shown_at is None
    else:
        # Unreadable or missing file both mean the window was not consumed.
        assert not preferences_path().exists() or prefs.last_shown_at is None  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Mission-end: consolidate (recorder on the production entry point)
# ---------------------------------------------------------------------------


def _build_consolidate_app() -> typer.Typer:
    app = typer.Typer()
    app.command()(consolidate_module.consolidate)
    return app


def _patch_consolidate_boundaries(monkeypatch: pytest.MonkeyPatch, mission: MissionFixture) -> None:
    monkeypatch.setattr(consolidate_module, "_enforce_git_preflight", lambda *a, **kw: None)
    monkeypatch.setattr(consolidate_module, "find_repo_root", lambda: mission.repo_root)
    monkeypatch.setattr(consolidate_module, "get_main_repo_root", lambda _repo: mission.repo_root)
    monkeypatch.setattr(consolidate_module, "_validate_target_branch", lambda *a, **kw: None)
    monkeypatch.setattr(
        consolidate_module,
        "_resolve_target_branch",
        lambda *a, **kw: ("main", "cli"),
    )
    monkeypatch.setattr(consolidate_module, "show_banner", lambda: None)


def _write_lanes_json(mission: MissionFixture) -> None:
    (mission.mission_dir / "lanes.json").write_text(
        json.dumps(
            {
                "version": 1,
                "mission_slug": mission.mission_slug,
                "mission_id": mission.mission_id,
                "mission_branch": f"kitty/mission-{mission.mission_slug}",
                "target_branch": "main",
                "lanes": [
                    {
                        "lane_id": "lane-a",
                        "wp_ids": ["WP01"],
                        "write_scope": [],
                        "predicted_surfaces": [],
                        "depends_on_lanes": [],
                        "parallel_group": 0,
                    }
                ],
                "computed_at": "2026-05-14T12:00:00+00:00",
                "computed_from": "dependency_graph+ownership",
                "planning_artifact_wps": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_consolidate_offers_mission_end_on_success_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission,
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.APPROVED,
        event_id="01M3PK9WHOOKS00000000001",
    )
    _write_lanes_json(mission)
    monkeypatch.chdir(mission.repo_root)
    _patch_consolidate_boundaries(monkeypatch, mission)

    calls: list[tuple[object, dict[str, Any]]] = []

    def _record(trigger: SurveyTrigger, **kwargs: Any) -> None:
        calls.append((trigger, kwargs))

    monkeypatch.setattr("specify_cli.feedback.hooks.offer_after_trigger", _record)
    monkeypatch.setattr(consolidate_module, "_run_real_merge", lambda *a, **k: None)

    consolidator = ArgvCliRunner(env={"COLUMNS": "200", "TERM": "dumb"})
    success = consolidator.invoke(
        _build_consolidate_app(),
        ["--mission", mission.mission_slug, "--yes"],
    )
    assert success.exit_code == 0, success.output
    assert len(calls) == 1
    assert calls[0][0] is SurveyTrigger.MISSION_END
    assert calls[0][1]["json_output"] is False
    success_code = success.exit_code

    calls.clear()
    dry = consolidator.invoke(
        _build_consolidate_app(),
        ["--mission", mission.mission_slug, "--dry-run"],
    )
    # Dry-run may exit non-zero on incomplete fixtures; the offer must never fire.
    assert calls == []
    dry_code = dry.exit_code

    calls.clear()

    def _fail(*_a: object, **_k: object) -> None:
        raise typer.Exit(1)

    monkeypatch.setattr(consolidate_module, "_run_real_merge", _fail)
    failed = consolidator.invoke(
        _build_consolidate_app(),
        ["--mission", mission.mission_slug, "--yes"],
    )
    assert failed.exit_code == 1
    assert calls == []
    # Positive control: success exit was unchanged by the recorder itself.
    assert success_code == 0
    assert dry_code in {0, 1}


# ---------------------------------------------------------------------------
# Planning-complete: agent mission finalize-tasks (recorder)
# ---------------------------------------------------------------------------


def _setup_finalize_feature(tmp_path: Path, mission_slug: str = "060-hook-mission") -> Path:
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(
        "---\ntitle: Hook Mission\n---\n\n## Functional Requirements\n\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "|----|-------------|---------------------|--------|\n"
        "| FR-001 | First requirement | works | Proposed |\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01\n\nNo dependencies.\n",
        encoding="utf-8",
    )
    (tasks_dir / "WP01-test.md").write_text(
        '---\nwork_package_id: "WP01"\ntitle: "Test WP01"\n'
        "requirement_refs:\n  - FR-001\ndependencies: []\n"
        "owned_files:\n  - src/hook_demo/**\n"
        "authoritative_surface: src/hook_demo/\n"
        "execution_mode: code_change\n"
        "subtasks: []\n---\n\n# WP01\n",
        encoding="utf-8",
    )
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": mission_slug,
                "mission_type": "software-dev",
                "target_branch": "main",
            }
        ),
        encoding="utf-8",
    )
    return feature_dir


def _stub_finalize_to_commit_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tmp_path: Path,
    mission_slug: str,
    feature_dir: Path,
) -> None:
    """Stub finalize-tasks collaborators so the real command reaches the commit pipeline."""
    from specify_cli.cli.commands.agent import mission_finalize as mf

    monkeypatch.setattr(mf, "_resolve_repo_root", lambda json_output=False: tmp_path)
    monkeypatch.setattr(mf, "_resolve_mission_slug", lambda *_a, **_k: mission_slug)
    monkeypatch.setattr(mf, "_resolve_target_branch", lambda *_a, **_k: "main")
    monkeypatch.setattr(mf, "_resolve_merge_target_branch", lambda *_a, **_k: "main")
    monkeypatch.setattr(mf, "_validate_occurrence_map_ready", lambda *_a, **_k: None)
    monkeypatch.setattr(mf, "_preflight_recovered_pr_bound_contract", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mf,
        "_persist_branch_contract_for_finalize",
        lambda *_a, **_k: mf.TargetBranchPersistOutcome(persisted=False),
    )
    monkeypatch.setattr(mf, "_scaffold_issue_matrix_if_present", lambda *_a, **_k: None)
    monkeypatch.setattr(mf, "_advisory_issue_matrix_lint", lambda *_a, **_k: None)
    monkeypatch.setattr(mf, "resolve_checkout_identity", lambda *_a, **_k: MagicMock())
    monkeypatch.setattr(mf, "_load_manifest", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mf,
        "_resolve_dependencies_and_refs",
        lambda *_a, **_k: MagicMock(
            wp_dependencies={"WP01": []},
            wp_requirement_refs={"WP01": ["FR-001"]},
        ),
    )
    monkeypatch.setattr(mf, "_validate_dependency_graph", lambda *_a, **_k: None)
    monkeypatch.setattr(mf, "_validate_requirement_mapping", lambda *_a, **_k: None)
    monkeypatch.setattr(mf, "_detect_dependency_conflicts", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mf,
        "_read_spec_requirement_ids",
        lambda *_a, **_k: ({"FR-001"}, {"FR-001"}, [], "# Spec\n"),
    )
    empty_state = MagicMock(
        work_packages=[],
        updated_count=0,
        modified_wps=[],
        unchanged_wps=[],
        preserved_wps=[],
        ownership_warnings=[],
        requirement_extraction_warnings=[],
        post_integration_acceptance_warnings=[],
        inmemory_frontmatter={},
    )
    monkeypatch.setattr(mf, "_run_bootstrap_loop", lambda *a, **k: empty_state)
    monkeypatch.setattr(mf, "_flush_frontmatter_writes", lambda *_a, **_k: None)
    monkeypatch.setattr(mf, "_assert_no_write_in_validate_only", lambda *_a, **_k: None)
    monkeypatch.setattr(mf, "_surface_post_integration_acceptance_warnings", lambda *_a, **_k: None)
    monkeypatch.setattr(mf, "_validate_owned_files_not_in_mission_specs", lambda *_a, **_k: None)
    monkeypatch.setattr(mf, "_regenerate_or_report_tasks_md", lambda *_a, **_k: False)
    monkeypatch.setattr(mf, "_emit_tasks_started", lambda *_a, **_k: None)
    monkeypatch.setattr(mf, "_emit_validate_only_report", lambda *_a, **_k: None)
    monkeypatch.setattr(mf, "_warn_missing_meta", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mf,
        "_read_meta_for_emission",
        lambda *_a, **_k: {
            "mission_slug": mission_slug,
            "mission_type": "software-dev",
            "target_branch": "main",
        },
    )
    monkeypatch.setattr(mf, "_gather_validation_frontmatter", lambda *_a, **_k: ({}, {}))
    monkeypatch.setattr(mf, "_validate_ownership_manifests", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mf,
        "_project_lane_inputs",
        lambda *_a, **_k: (MagicMock(all_canceled=False), {}, {}, {}),
    )
    monkeypatch.setattr(mf, "_raise_stale_canceled_dependencies_if_any", lambda *_a, **_k: None)
    monkeypatch.setattr(mf, "resolve_wp_manifests", lambda *_a, **_k: {})
    monkeypatch.setattr(mf, "FinalizeFrontmatterSource", lambda **_k: MagicMock())

    class _FakeSeam:
        def read_dir(self, _kind: object) -> Path:
            return feature_dir

    monkeypatch.setattr("mission_runtime.placement_seam", lambda *_a, **_k: _FakeSeam())


def test_finalize_offers_planning_complete_on_success_not_validate_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.cli.commands.agent import mission_finalize as mf
    from specify_cli.cli.commands.agent.mission import app as mission_app

    mission_slug = "060-hook-mission"
    feature_dir = _setup_finalize_feature(tmp_path, mission_slug)
    monkeypatch.chdir(tmp_path)
    _stub_finalize_to_commit_pipeline(
        monkeypatch,
        tmp_path=tmp_path,
        mission_slug=mission_slug,
        feature_dir=feature_dir,
    )

    calls: list[tuple[object, dict[str, Any]]] = []

    def _record(trigger: SurveyTrigger, **kwargs: Any) -> None:
        calls.append((trigger, kwargs))

    monkeypatch.setattr("specify_cli.feedback.hooks.offer_after_trigger", _record)
    monkeypatch.setattr(mf, "_run_commit_pipeline", lambda *a, **k: None)

    finalize_runner = ArgvCliRunner(env={"COLUMNS": "200", "TERM": "dumb"})

    validate = finalize_runner.invoke(
        mission_app,
        ["finalize-tasks", "--mission", mission_slug, "--validate-only"],
    )
    assert calls == [], f"validate-only offered: {calls!r}\n{validate.output}"
    validate_code = validate.exit_code

    success = finalize_runner.invoke(
        mission_app,
        ["finalize-tasks", "--mission", mission_slug],
    )
    assert success.exit_code == 0, success.output
    assert len(calls) == 1, f"expected one offer, got {calls!r}\n{success.output}"
    assert calls[0][0] is SurveyTrigger.PLANNING_COMPLETE
    assert calls[0][1]["json_output"] is False

    calls.clear()

    def _boom(*_a: object, **_k: object) -> None:
        raise typer.Exit(1)

    monkeypatch.setattr(mf, "_run_commit_pipeline", _boom)
    failed = finalize_runner.invoke(
        mission_app,
        ["finalize-tasks", "--mission", mission_slug],
    )
    assert failed.exit_code == 1
    assert calls == []
    assert validate_code in {0, 1}
