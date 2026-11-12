"""``move-task --to for_review`` records the evidence tree and refuses a foreign one (#7547).

Mission ``lane-code-verification-01M76AC0`` WP04. Every cell drives the REAL
``_do_move_task`` orchestrator against a REAL lane checkout (a git repository
with a tracked ``src/pkg/__init__.py``) and a REAL lane ``.venv`` built with
``python -m venv --without-pip``. The ``.pth`` file in that venv decides where
``pkg`` loads from:

- pointing at the repository root checkout's ``src`` makes the tree **foreign**
  (the #1907 case: the lane's tests would load another tree's code);
- pointing at ``<lane>/src`` makes it **verified** (the positive control; the
  same fixture, only the ``.pth`` target differs).

Only mission bookkeeping is faked (the recording coordination router of
``tests/review/test_pre_review_gate_integration.py``), so ``status_calls == []``
proves no transition was written.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import typer

from specify_cli.cli.commands.agent import tasks_move_task_gates
from specify_cli.cli.commands.agent.tasks_move_task import _do_move_task, _MoveTaskArgs
from specify_cli.review import gate_registry, pre_review_gate
from specify_cli.status.models import TransitionRequest
from tests.mocked_env import setup_mocked_env
from tests.review.test_pre_review_gate_integration import (
    _MISSION,
    _build_wp_file,
    _fake_ports,
    _fixture_workspace,
    _RecordingCoordRouter,
    _seed_baseline,
    _seed_wp_event,
)

pytestmark = [pytest.mark.git_repo]

_REFUSAL_CODE = "EVIDENCE_TREE_MISMATCH"
_SKIP_ENV = "SPEC_KITTY_SKIP_PRE_REVIEW_GATE"
_HEX40 = re.compile(r"^[0-9a-f]{40}$")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _site_packages(venv: Path) -> Path:
    found = sorted(venv.glob("lib/python*/site-packages")) + sorted(venv.glob("Lib/site-packages"))
    assert found, f"no site-packages under {venv}"
    return found[0]


class _Fixture:
    """A mission root with a lane checkout under it, a lane venv and a test-command marker."""

    def __init__(self, tmp_path: Path, *, changed: bool, extra_frontmatter: str = "") -> None:
        self.root = tmp_path / "mission-root"
        self.root.mkdir()
        self.marker = tmp_path / "test-command-ran.marker"
        # The repository root checkout's own copy of ``pkg`` (the foreign tree).
        (self.root / "src" / "pkg").mkdir(parents=True)
        (self.root / "src" / "pkg" / "__init__.py").write_text("WHERE = 'root'\n", encoding="utf-8")
        self.feature_dir, _wp = _build_wp_file(self.root, _MISSION, "WP01", extra_frontmatter=extra_frontmatter)
        _seed_wp_event(self.feature_dir, "WP01", "in_progress")
        _seed_baseline(self.feature_dir, "WP01-test", failed=0)
        self.lane = self.root / ".worktrees" / "lane-a"
        self._build_lane(changed=changed)
        self.ports, self.router = _fake_ports(self.feature_dir)

    def _build_lane(self, *, changed: bool) -> None:
        lane = self.lane
        lane.mkdir(parents=True)
        _git(lane, "init", "-q", "-b", "main")
        _git(lane, "config", "user.email", "test@example.com")
        _git(lane, "config", "user.name", "Test")
        (lane / ".gitignore").write_text(".venv/\n", encoding="utf-8")
        (lane / "src" / "pkg").mkdir(parents=True)
        (lane / "src" / "pkg" / "__init__.py").write_text("WHERE = 'lane'\n", encoding="utf-8")
        _git(lane, "add", "-A")
        _git(lane, "commit", "-q", "-m", "base")
        _git(lane, "checkout", "-q", "-b", "wip-lane")
        if changed:
            (lane / "src" / "pkg" / "extra.py").write_text("VALUE = 1\n", encoding="utf-8")
            _git(lane, "add", "-A")
            _git(lane, "commit", "-q", "-m", "wip change")
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(lane / ".venv")], check=True)

    def point_pth_at(self, source_root: Path) -> None:
        (_site_packages(self.lane / ".venv") / "lane_src.pth").write_text(f"{source_root}\n", encoding="utf-8")

    def make_foreign(self) -> None:
        self.point_pth_at(self.root / "src")

    def make_verified(self) -> None:
        self.point_pth_at(self.lane / "src")

    def write_review_config(self, *, block: bool = False) -> None:
        script = f"open({str(self.marker)!r}, 'w').write('ran')"
        command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)} --junitxml={{output_file}}"
        lines = ["review:", f"  test_command: {json.dumps(command)}", "  test_output_format: junit_xml"]
        if block:
            lines.append("  fail_on_pre_review_regression: true")
        config = self.root / ".kittify" / "config.yaml"
        existing = config.read_text(encoding="utf-8") if config.exists() else ""
        prefix = existing if not existing or existing.endswith("\n") else existing + "\n"
        config.write_text(prefix + "\n".join(lines) + "\n", encoding="utf-8")

    def move(self, *, force: bool = False, skip: bool = False, json_output: bool = True) -> None:
        with setup_mocked_env(
            self.root,
            mission_slug=_MISSION,
            target_branch="main",
            workspace_resolution=_fixture_workspace(self.lane),
            extra_patches={
                "_validate_ready_for_review": (True, []),
                "_check_unchecked_subtasks": [],
            },
        ):
            _do_move_task(
                _MoveTaskArgs(
                    task_id="WP01",
                    to="for_review",
                    mission=_MISSION,
                    agent=None,
                    assignee=None,
                    shell_pid=None,
                    note=None,
                    review_feedback_file=None,
                    approval_ref=None,
                    reviewer=None,
                    self_review_fallback=False,
                    intended_reviewer=None,
                    reviewer_failure_reason=None,
                    done_override_reason=None,
                    force=force,
                    tracker_ref=None,
                    skip_review_artifact_check=False,
                    auto_commit=False,
                    json_output=json_output,
                    skip_pre_review_gate=skip,
                ),
                ports=self.ports,
            )


def _metadata(router: _RecordingCoordRouter) -> dict[str, Any]:
    assert len(router.status_calls) == 1
    request: TransitionRequest = router.status_calls[0]
    assert request.policy_metadata is not None
    metadata = request.policy_metadata["pre_review_gate"]
    assert isinstance(metadata, dict)
    return metadata


def _last_json_document(stdout: str) -> dict[str, Any]:
    start = stdout.rfind("\n{")
    payload = json.loads(stdout[start + 1 :] if start >= 0 else stdout)
    assert isinstance(payload, dict)
    return payload


@pytest.fixture(autouse=True)
def _no_harness_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agent containers may export gate opt-outs; every cell decides its own."""
    monkeypatch.delenv(_SKIP_ENV, raising=False)


# ---------------------------------------------------------------------------
# Cells 1 and 2: a foreign tree is refused, block toggle or not
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize("block", [False, True], ids=["block_off", "block_on"])
def test_foreign_tree_is_refused_without_running_tests(tmp_path: Path, capsys: pytest.CaptureFixture[str], block: bool) -> None:
    fx = _Fixture(tmp_path, changed=True)
    fx.write_review_config(block=block)
    fx.make_foreign()

    with pytest.raises(typer.Exit) as exc_info:
        fx.move()

    assert exc_info.value.exit_code == 1
    assert fx.router.status_calls == []
    assert not fx.marker.exists(), "the declared test command must not run on a foreign tree"
    payload = _last_json_document(capsys.readouterr().out)
    assert payload["result"] == "error"
    assert payload["error_code"] == _REFUSAL_CODE
    assert payload["transition_applied"] is False
    assert f"Pre-review gate refused ({_REFUSAL_CODE})" in payload["error"]
    assert "--force" in payload["error"]
    gate = payload["pre_review_gate"]
    assert gate["outcome"] == "foreign_tree"
    assert gate["transition_applied"] is False
    assert gate["force_bypassed"] is False
    assert gate["evidence_tree"]["probe"]["status"] == "foreign"
    assert gate["evidence_tree"]["probe"]["foreign"] == ["pkg"]


@pytest.mark.integration
def test_foreign_tree_refusal_human_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fx = _Fixture(tmp_path, changed=True)
    fx.write_review_config()
    fx.make_foreign()

    with pytest.raises(typer.Exit):
        fx.move(json_output=False)

    output = " ".join(capsys.readouterr().out.split())
    assert f"Pre-review gate refused ({_REFUSAL_CODE}): pkg loads from" in output
    assert "re-run with --force to record a bypass" in output
    assert fx.router.status_calls == []


# ---------------------------------------------------------------------------
# Arms that run no test never probe and never refuse (FR-011, C-003)
# ---------------------------------------------------------------------------


def _probe_spy(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    calls: list[Path] = []
    real = tasks_move_task_gates.lane_test_invocation_for

    def spy(root: Path, **kwargs: Any) -> Any:
        calls.append(root)
        return real(root, **kwargs)

    monkeypatch.setattr(tasks_move_task_gates, "lane_test_invocation_for", spy)
    return calls


@pytest.mark.integration
def test_undeclared_gate_on_a_foreign_tree_stays_a_quiet_skip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fx = _Fixture(tmp_path, changed=True)
    fx.make_foreign()
    calls = _probe_spy(monkeypatch)

    fx.move()

    metadata = _metadata(fx.router)
    assert metadata["outcome"] == "skipped"
    assert "evidence_tree" not in metadata
    assert calls == []


@pytest.mark.integration
def test_declared_gate_with_an_empty_diff_on_a_foreign_tree_stays_no_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fx = _Fixture(tmp_path, changed=False)
    fx.write_review_config(block=True)
    fx.make_foreign()
    calls = _probe_spy(monkeypatch)

    fx.move()

    metadata = _metadata(fx.router)
    assert metadata["outcome"] == "no_coverage"
    assert "evidence_tree" not in metadata
    assert calls == []
    assert not fx.marker.exists()


@pytest.mark.integration
def test_override_tier_on_a_foreign_tree_is_refused(tmp_path: Path) -> None:
    fx = _Fixture(tmp_path, changed=True, extra_frontmatter="pre_review_test_scope: tests\n")
    fx.make_foreign()

    with pytest.raises(typer.Exit) as exc_info:
        fx.move()

    assert exc_info.value.exit_code == 1
    assert fx.router.status_calls == []


# ---------------------------------------------------------------------------
# Cell 3: the verified positive control records the evidence tree
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_verified_tree_records_evidence_and_applies(tmp_path: Path) -> None:
    fx = _Fixture(tmp_path, changed=True)
    fx.write_review_config()
    fx.make_verified()

    fx.move()

    metadata = _metadata(fx.router)
    tree = metadata["evidence_tree"]
    assert tree["path"] == ".worktrees/lane-a"
    assert _HEX40.match(tree["head"])
    assert isinstance(tree["dirty"], bool)
    assert tree["probe"]["status"] == "verified"
    assert metadata["outcome"] != "foreign_tree"
    assert "bypassed_refusal" not in metadata


# ---------------------------------------------------------------------------
# Cell 4: --force proceeds and records which refusal it bypassed
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_force_past_a_foreign_tree_records_the_bypass(tmp_path: Path) -> None:
    fx = _Fixture(tmp_path, changed=True)
    fx.write_review_config(block=False)
    fx.make_foreign()

    fx.move(force=True)

    metadata = _metadata(fx.router)
    assert metadata["outcome"] == "foreign_tree"
    # The pre-WP04 formula (block_enabled and force and blocking) gives False here.
    assert metadata["force_bypassed"] is True
    assert metadata["bypassed_refusal"] == _REFUSAL_CODE
    assert "no test run" in (metadata["reason"] or "")
    assert metadata["evidence_tree"]["probe"]["status"] == "foreign"
    assert not fx.marker.exists()


# ---------------------------------------------------------------------------
# Cell 5: no source-layout package -> unverified, never refused
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_unverified_tree_is_never_refused(tmp_path: Path) -> None:
    fx = _Fixture(tmp_path, changed=True)
    fx.write_review_config(block=True)
    _git(fx.lane, "rm", "-q", "--cached", "src/pkg/__init__.py")
    _git(fx.lane, "commit", "-q", "-m", "untrack the package")
    fx.make_foreign()

    fx.move()

    metadata = _metadata(fx.router)
    assert metadata["evidence_tree"]["probe"]["status"] == "unverified"
    assert metadata["outcome"] != "foreign_tree"


# ---------------------------------------------------------------------------
# Cell 6: the skip flag and the skip env var never probe
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize("route", ["flag", "env", "none"])
def test_skip_paths_never_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, route: str) -> None:
    fx = _Fixture(tmp_path, changed=True)
    fx.write_review_config()
    fx.make_foreign()
    calls: list[Path] = []
    real = tasks_move_task_gates.lane_test_invocation_for

    def spy(root: Path, **kwargs: Any) -> Any:
        calls.append(root)
        return real(root, **kwargs)

    monkeypatch.setattr(tasks_move_task_gates, "lane_test_invocation_for", spy)
    if route == "env":
        monkeypatch.setenv(_SKIP_ENV, "1")

    if route == "none":
        with pytest.raises(typer.Exit):
            fx.move()
        assert calls == [fx.lane]
        return

    fx.move(skip=route == "flag")
    assert calls == []
    assert "evidence_tree" not in _metadata(fx.router)


# ---------------------------------------------------------------------------
# Cell 7: the lane's run environment reaches the handler and the override tier
# ---------------------------------------------------------------------------


def _canned_verdict() -> pre_review_gate.GateVerdict:
    return pre_review_gate.GateVerdict(
        outcome=pre_review_gate.GateOutcome.NO_NEW_FAILURES,
        scope=pre_review_gate.ScopeResult.from_override(("tests",)),
    )


@pytest.mark.integration
def test_run_env_reaches_the_dispatched_handler(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fx = _Fixture(tmp_path, changed=True)
    fx.write_review_config()
    fx.make_verified()
    monkeypatch.setenv("VIRTUAL_ENV", "/somewhere/else/.venv")
    seen: list[dict[str, Any]] = []

    def fake_evaluate(*args: Any, **kwargs: Any) -> pre_review_gate.GateVerdict:
        seen.append(kwargs)
        return _canned_verdict()

    monkeypatch.setattr(gate_registry, "evaluate_pre_review_gate", fake_evaluate)

    fx.move()

    assert len(seen) == 1
    run_env = seen[0]["run_env"]
    assert run_env is not None
    assert "VIRTUAL_ENV" not in run_env
    assert run_env.get("PATH") == os.environ.get("PATH")
    assert _metadata(fx.router)["evidence_tree"]["probe"]["status"] == "verified"


@pytest.mark.integration
def test_run_env_reaches_the_override_tier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fx = _Fixture(tmp_path, changed=True, extra_frontmatter="pre_review_test_scope: tests\n")
    fx.write_review_config()
    fx.make_verified()
    monkeypatch.setenv("VIRTUAL_ENV", "/somewhere/else/.venv")
    seen: list[dict[str, Any]] = []

    def fake_evaluate_with_scope(*args: Any, **kwargs: Any) -> pre_review_gate.GateVerdict:
        seen.append(kwargs)
        return _canned_verdict()

    monkeypatch.setattr(pre_review_gate, "evaluate_with_scope", fake_evaluate_with_scope)

    fx.move()

    assert len(seen) == 1
    run_env = seen[0]["run_env"]
    assert run_env is not None
    assert "VIRTUAL_ENV" not in run_env


# ---------------------------------------------------------------------------
# Fail-open and the pure translation seam
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_invocation_failure_fails_open_without_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fx = _Fixture(tmp_path, changed=True)
    fx.write_review_config(block=True)
    fx.make_foreign()

    def boom(root: Path, **kwargs: Any) -> Any:
        raise RuntimeError("cannot build the invocation")

    monkeypatch.setattr(tasks_move_task_gates, "lane_test_invocation_for", boom)

    fx.move()

    metadata = _metadata(fx.router)
    assert "evidence_tree" not in metadata
    assert metadata["outcome"] != "foreign_tree"


def _foreign_verdict() -> pre_review_gate.GateVerdict:
    return pre_review_gate.GateVerdict(
        outcome=pre_review_gate.GateOutcome.FOREIGN_TREE,
        scope=pre_review_gate.ScopeResult.from_override(()),
        reason="pkg loads from /root/src/pkg/__init__.py, outside /lane/src — no test run happened",
        run_state=pre_review_gate.HeadRunState.NOT_STARTED,
    )


@pytest.mark.fast
@pytest.mark.parametrize("block_enabled", [False, True])
def test_translate_records_a_forced_refusal_bypass(block_enabled: bool) -> None:
    effect = tasks_move_task_gates._mt_translate_gate_verdicts([_foreign_verdict()], block_enabled=block_enabled, force=True)

    assert effect.should_exit is False
    assert effect.metadata["force_bypassed"] is True
    assert effect.metadata["bypassed_refusal"] == _REFUSAL_CODE
    assert effect.metadata["outcome"] == "foreign_tree"


@pytest.mark.fast
def test_translate_refuses_an_unforced_foreign_verdict() -> None:
    effect = tasks_move_task_gates._mt_translate_gate_verdicts([_foreign_verdict()], block_enabled=False, force=False)

    assert effect.refused is True
    assert effect.should_exit is True
    assert effect.blocked is False
    assert effect.terminal is False
    assert effect.metadata["transition_applied"] is False
    assert effect.metadata["force_bypassed"] is False
    assert "bypassed_refusal" not in effect.metadata
    assert effect.console_lines == ("[red]Pre-review regression gate: foreign_tree — " + (_foreign_verdict().reason or "") + "[/red]",)
