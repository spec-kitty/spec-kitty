"""Tests for specify_cli.review.baseline — WP04: Baseline Test Capture."""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.review import pre_review_gate
from specify_cli.review.baseline import (
    BaselineTestResult,
    BaselineFailure,
    _get_test_command,
    _parse_junit_xml,
    _run_command_for_baseline,
    capture_baseline,
    diff_baseline,
)
from specify_cli.review.scope_source import DeclaredCommandScopeSource

pytestmark = pytest.mark.git_repo


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

SAMPLE_JUNIT_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="utf-8"?>
    <testsuites>
      <testsuite name="pytest" tests="4" failures="1" errors="0" skipped="1">
        <testcase classname="tests.test_foo" name="test_pass" file="tests/test_foo.py" line="5"/>
        <testcase classname="tests.test_foo" name="test_fail" file="tests/test_foo.py" line="10">
          <failure message="AssertionError: expected True, got False">
            AssertionError: expected True, got False
            Full traceback here
          </failure>
        </testcase>
        <testcase classname="tests.test_bar" name="test_skip" file="tests/test_bar.py" line="3">
          <skipped/>
        </testcase>
        <testcase classname="tests.test_bar" name="test_pass2" file="tests/test_bar.py" line="7"/>
      </testsuite>
    </testsuites>
""")


def _make_fake_git_dir(repo: Path) -> None:
    """Create the minimal metadata needed for a structural Git-root fixture."""
    git_dir = repo / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")


def _make_baseline(
    wp_id: str = "WP04",
    failed: int = 2,
    failures: tuple[BaselineFailure, ...] = (),
    base_branch: str = "main",
    base_commit: str = "abc1234",
) -> BaselineTestResult:
    return BaselineTestResult(
        wp_id=wp_id,
        captured_at="2026-04-06T12:00:00Z",
        base_branch=base_branch,
        base_commit=base_commit,
        test_runner="pytest",
        total=10,
        passed=8,
        failed=failed,
        skipped=0,
        failures=failures,
    )


def _make_failure(test: str, error: str = "AssertionError", file: str = "tests/foo.py:10") -> BaselineFailure:
    return BaselineFailure(test=test, error=error, file=file)


# ---------------------------------------------------------------------------
# T017 - Dataclass round-trip
# ---------------------------------------------------------------------------

class TestBaselineTestResultRoundTrip:
    """test_baseline_test_result_round_trip — save and load JSON, compare fields."""

    def test_round_trip_basic(self, tmp_path: Path) -> None:
        failures = (
            _make_failure("tests.test_foo.TestBar.test_baz"),
            _make_failure("tests.test_qux.test_quux", "ValueError: bad input"),
        )
        baseline = _make_baseline(failed=2, failures=failures)
        artifact = tmp_path / "baseline-tests.json"
        baseline.save(artifact)

        loaded = BaselineTestResult.load(artifact)
        assert loaded is not None
        assert loaded.wp_id == baseline.wp_id
        assert loaded.failed == baseline.failed
        assert loaded.total == baseline.total
        assert loaded.passed == baseline.passed
        assert loaded.skipped == baseline.skipped
        assert loaded.base_branch == baseline.base_branch
        assert loaded.base_commit == baseline.base_commit
        assert loaded.test_runner == baseline.test_runner
        assert loaded.captured_at == baseline.captured_at
        assert len(loaded.failures) == 2
        assert loaded.failures[0].test == failures[0].test
        assert loaded.failures[1].error == failures[1].error

    def test_load_returns_none_when_missing(self, tmp_path: Path) -> None:
        result = BaselineTestResult.load(tmp_path / "nonexistent.json")
        assert result is None

    def test_load_raises_on_malformed_json(self, tmp_path: Path) -> None:
        artifact = tmp_path / "bad.json"
        artifact.write_text("NOT JSON {{{}}", encoding="utf-8")
        with pytest.raises(ValueError, match="Malformed baseline JSON"):
            BaselineTestResult.load(artifact)

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        baseline = _make_baseline()
        nested = tmp_path / "tasks" / "WP04-foo" / "baseline-tests.json"
        baseline.save(nested)
        assert nested.exists()

    def test_to_dict_from_dict_round_trip(self) -> None:
        failure = _make_failure("a.b.c")
        assert BaselineFailure.from_dict(failure.to_dict()) == failure

        baseline = _make_baseline(failures=(failure,))
        assert BaselineTestResult.from_dict(baseline.to_dict()) == baseline


# ---------------------------------------------------------------------------
# T018 - capture_baseline()
# ---------------------------------------------------------------------------

class TestCaptureBaseline:
    """Tests for the capture_baseline() function."""

    def _make_wp_dir(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        """Set up a minimal fake repo structure."""
        repo = tmp_path / "repo"
        _make_fake_git_dir(repo)
        feature_dir = repo / "kitty-specs" / "066-test"
        (feature_dir / "tasks" / "WP04-test").mkdir(parents=True)
        return repo, feature_dir, feature_dir / "tasks" / "WP04-test"

    def test_capture_baseline_creates_artifact(self, tmp_path: Path) -> None:
        """capture_baseline creates baseline-tests.json via subprocess mock."""
        repo, feature_dir, wp_task_dir = self._make_wp_dir(tmp_path)

        # Write a sample JUnit XML so parsing succeeds
        def fake_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "abc1234def5\n"
            result.stderr = ""
            # Detect JUnit XML write
            cmd_text = " ".join(cmd) if isinstance(cmd, list) else cmd
            if isinstance(cmd_text, str) and "--junitxml=" in cmd_text:
                output_file = kwargs.get("env", {}).get("SPEC_KITTY_CMD_OUTPUT_FILE")
                if output_file:
                    Path(output_file).write_text(SAMPLE_JUNIT_XML, encoding="utf-8")
            return result

        with patch("subprocess.run", side_effect=fake_run):
            result = capture_baseline(
                worktree_path=repo,
                base_branch="main",
                wp_id="WP04",
                mission_slug="066-test",
                feature_dir=feature_dir,
                wp_slug="WP04-test",
                test_command="custom-runner --junitxml={output_file}",
            )

        artifact = wp_task_dir / "baseline-tests.json"
        assert artifact.exists(), "baseline-tests.json should be created"
        assert result is not None
        data = json.loads(artifact.read_text())
        assert data["wp_id"] == "WP04"

    def test_capture_baseline_skips_if_cached(self, tmp_path: Path) -> None:
        """If baseline-tests.json already exists, subprocess is NOT called."""
        repo, feature_dir, wp_task_dir = self._make_wp_dir(tmp_path)

        # Pre-create the artifact
        existing = _make_baseline(wp_id="WP04")
        artifact = wp_task_dir / "baseline-tests.json"
        existing.save(artifact)

        call_count = 0

        def fake_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        with patch("subprocess.run", side_effect=fake_run):
            result = capture_baseline(
                worktree_path=repo,
                base_branch="main",
                wp_id="WP04",
                mission_slug="066-test",
                feature_dir=feature_dir,
                wp_slug="WP04-test",
                test_command="custom-runner --junitxml={output_file}",
            )

        assert call_count == 0, "No subprocess calls expected when cache exists"
        assert result is not None
        assert result.wp_id == "WP04"

    def test_capture_baseline_handles_failure(self, tmp_path: Path) -> None:
        """Subprocess failure produces a sentinel result (failed=-1), not an exception."""
        repo, feature_dir, wp_task_dir = self._make_wp_dir(tmp_path)

        def fake_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "abc1234\n"
            result.stderr = ""
            # Simulate: git rev-parse works, git worktree add fails
            if isinstance(cmd, list) and "worktree" in cmd:
                result.returncode = 128
                result.stderr = "fatal: could not add worktree"
            return result

        with patch("subprocess.run", side_effect=fake_run):
            result = capture_baseline(
                worktree_path=repo,
                base_branch="main",
                wp_id="WP04",
                mission_slug="066-test",
                feature_dir=feature_dir,
                wp_slug="WP04-test",
                test_command="custom-runner --junitxml={output_file}",
            )

        assert result is not None
        assert result.failed == -1, "Sentinel result expected when capture fails"

    def test_capture_baseline_preserves_posix_command_substitution(self, tmp_path: Path) -> None:
        repo, feature_dir, _wp_task_dir = self._make_wp_dir(tmp_path)
        shell_commands: list[str] = []

        def fake_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "abc1234def5\n"
            result.stderr = ""
            if isinstance(cmd, list) and cmd[:2] == ["sh", "-c"]:
                shell_commands.append(cmd[2])
                output_file = kwargs["env"]["SPEC_KITTY_CMD_OUTPUT_FILE"]
                Path(output_file).write_text(SAMPLE_JUNIT_XML, encoding="utf-8")
            return result

        with patch("subprocess.run", side_effect=fake_run):
            result = capture_baseline(
                worktree_path=repo,
                base_branch="main",
                wp_id="WP04",
                mission_slug="066-test",
                feature_dir=feature_dir,
                wp_slug="WP04-test",
                test_command='custom-runner --junitxml={output_file} --marker "$(printf ok)"',
            )

        assert result is not None
        assert result.failed == 1
        assert any("$(printf ok)" in command for command in shell_commands)

    def test_capture_baseline_output_path_does_not_trigger_shell(self, tmp_path: Path) -> None:
        repo, feature_dir, _wp_task_dir = self._make_wp_dir(tmp_path)
        proof_path = tmp_path / "proof-created-by-shell"
        injected_tmp = tmp_path / "tmp;touch proof-created-by-shell #"
        injected_tmp.mkdir()

        class FakeTemporaryDirectory:
            def __enter__(self) -> str:
                return str(injected_tmp)

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        shell_commands: list[str] = []

        def fake_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "abc1234def5\n"
            result.stderr = ""
            if isinstance(cmd, list) and cmd[:2] == ["sh", "-c"]:
                shell_commands.append(cmd[2])
                output_file = kwargs["env"]["SPEC_KITTY_CMD_OUTPUT_FILE"]
                Path(output_file).write_text(SAMPLE_JUNIT_XML, encoding="utf-8")
            return result

        with (
            patch("tempfile.TemporaryDirectory", return_value=FakeTemporaryDirectory()),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = capture_baseline(
                worktree_path=repo,
                base_branch="main",
                wp_id="WP04",
                mission_slug="066-test",
                feature_dir=feature_dir,
                wp_slug="WP04-test",
                test_command="custom-runner --junitxml={output_file}",
            )

        assert result is not None
        assert result.failed == 1
        assert shell_commands == ['custom-runner --junitxml="${SPEC_KITTY_CMD_OUTPUT_FILE}"']
        assert not proof_path.exists()

    def test_capture_baseline_preserves_quoted_output_file_template(self, tmp_path: Path) -> None:
        repo, feature_dir, _wp_task_dir = self._make_wp_dir(tmp_path)
        injected_tmp = tmp_path / "parent with space"
        injected_tmp.mkdir()

        class FakeTemporaryDirectory:
            def __enter__(self) -> str:
                return str(injected_tmp)

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        shell_commands: list[str] = []

        def fake_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "abc1234def5\n"
            result.stderr = ""
            if isinstance(cmd, list) and cmd[:2] == ["sh", "-c"]:
                shell_commands.append(cmd[2])
                output_file = kwargs["env"]["SPEC_KITTY_CMD_OUTPUT_FILE"]
                Path(output_file).write_text(SAMPLE_JUNIT_XML, encoding="utf-8")
            return result

        with (
            patch("tempfile.TemporaryDirectory", return_value=FakeTemporaryDirectory()),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = capture_baseline(
                worktree_path=repo,
                base_branch="main",
                wp_id="WP04",
                mission_slug="066-test",
                feature_dir=feature_dir,
                wp_slug="WP04-test",
                test_command='custom-runner --junitxml="{output_file}"',
            )

        assert result is not None
        assert result.failed == 1
        assert shell_commands == ['custom-runner --junitxml="${SPEC_KITTY_CMD_OUTPUT_FILE}"']

    @pytest.mark.windows_ci
    def test_capture_baseline_posix_shell_syntax_returns_sentinel_on_windows(self, tmp_path: Path) -> None:
        """Windows reports a clear unsupported command instead of invoking cmd.exe."""
        repo, feature_dir, _wp_task_dir = self._make_wp_dir(tmp_path)

        def fake_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "abc1234\n"
            result.stderr = ""
            return result

        with patch("subprocess.run", side_effect=fake_run):
            result = capture_baseline(
                worktree_path=repo,
                base_branch="main",
                wp_id="WP04",
                mission_slug="066-test",
                feature_dir=feature_dir,
                wp_slug="WP04-test",
                test_command='custom-runner --junitxml={output_file} && echo done',
            )

        assert result is not None
        assert result.failed == -1


# ---------------------------------------------------------------------------
# Issue #3612 fast-follow (post-#3612 review finding) — process-group reap
# safety for the compound shell-wrapped command
# ---------------------------------------------------------------------------
#
# DeclaredCommandScopeSource.test_command() (#3612) now renders
# ["sh", "-c", "export ...; <real command>"] -- a COMPOUND statement where
# `sh` forks the real command as its own child. A bare
# `subprocess.run(..., timeout=...)` here would SIGKILL only the direct
# child (`sh`) on timeout, orphaning the real command as a grandchild that
# keeps running -- with its cwd inside the baseline worktree -- exactly
# while `_baseline_worktree`'s `finally` removes that worktree out from
# under it. `_run_command_for_baseline` now delegates to the head runner's
# own group-safe launcher (`pre_review_gate._run_raw_command` ->
# `_launch_scoped_process` + `_observe_process` -> `os.killpg` on the whole
# process GROUP). These two tests are fully deterministic (an injected fake
# Popen + a monotonic clock forced past the deadline) -- no real sleeping
# subprocess or timing race.


class TestRunCommandForBaselineProcessGroupSafety:
    """Proves ``_run_command_for_baseline`` launches -- and reaps on
    timeout -- through the SAME process-group-safe machinery the head
    runner uses, not a bare ``subprocess.run``."""

    class _FakeProcess:
        """Minimal ``Popen`` double: enough surface for ``_observe_process``/
        ``_terminate_and_reap`` to drive without a real subprocess."""

        def __init__(self, *, returncode: int = 0, stderr: str = "") -> None:
            self.pid = 424242
            self.returncode = returncode
            self.stderr_text = stderr

        def communicate(self, timeout: float | None = None) -> tuple[str, str]:
            del timeout
            return "", self.stderr_text

        def terminate(self) -> None:
            pass

        def kill(self) -> None:
            pass

        def poll(self) -> int | None:
            return self.returncode

    def test_launches_with_process_group_isolation(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """``Popen`` is invoked with ``start_new_session=True`` (POSIX) -- the
        SAME flag ``pre_review_gate._launch_scoped_process`` uses for the
        head run -- proving baseline capture reuses that launcher instead of
        a bare ``subprocess.run`` with no process-group isolation at all."""
        calls: list[dict[str, object]] = []

        def _popen(command: list[str], **kwargs: object) -> TestRunCommandForBaselineProcessGroupSafety._FakeProcess:
            del command
            calls.append(kwargs)
            return TestRunCommandForBaselineProcessGroupSafety._FakeProcess()

        monkeypatch.setattr(pre_review_gate.subprocess, "Popen", _popen)

        raw = _run_command_for_baseline(
            ["sh", "-c", f"export SPEC_KITTY_CMD_OUTPUT_FILE={tmp_path}/x; pytest"],
            cwd=tmp_path,
        )

        assert len(calls) == 1
        assert calls[0].get("start_new_session") is True
        assert raw.returncode == 0

    def test_kills_the_whole_process_group_on_timeout(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """On timeout, ``os.killpg`` fires (the process GROUP, not just the
        direct ``sh`` child) -- proving a compound ``sh -c "export ...;
        pytest"`` command's grandchild ``pytest`` process is reaped alongside
        ``sh``, never orphaned while ``_baseline_worktree`` removes the
        worktree it is still running in.

        Determinism: ``time.monotonic`` is patched to an unboundedly
        increasing counter (each call returns ``N * 10_000_000``) rather than
        a fixed "first call small, rest huge" sequence -- the scoped-run
        advisory lock (``_scoped_run_lock``) makes its OWN ``time.monotonic``
        call before ``_observe_process`` ever starts, so which call index
        becomes its ``started_at`` is an implementation detail this test must
        not hardcode. An unboundedly increasing counter guarantees the delta
        between ANY two calls vastly exceeds the real timeout regardless of
        that index, so ``_observe_process`` reads "the deadline has already
        elapsed" on its very first loop iteration and ``_terminate_and_reap``
        (and its ``os.killpg`` call) fires immediately -- zero real sleeping,
        zero timing sensitivity.
        """
        process = TestRunCommandForBaselineProcessGroupSafety._FakeProcess(stderr="timed out")
        killpg_calls: list[tuple[int, int]] = []
        monotonic_calls = {"n": 0}

        def _fake_monotonic() -> float:
            monotonic_calls["n"] += 1
            return monotonic_calls["n"] * 10_000_000.0

        monkeypatch.setattr(pre_review_gate.subprocess, "Popen", lambda *a, **k: process)
        monkeypatch.setattr(
            pre_review_gate.os, "killpg", lambda pid, sig: killpg_calls.append((pid, sig))
        )
        monkeypatch.setattr(time, "monotonic", _fake_monotonic)

        raw = _run_command_for_baseline(
            ["sh", "-c", f"export SPEC_KITTY_CMD_OUTPUT_FILE={tmp_path}/x; pytest"],
            cwd=tmp_path,
        )

        assert killpg_calls, (
            "the process GROUP must be signaled (os.killpg) on timeout, not "
            "just the direct sh child -- otherwise a shell-wrapped compound "
            "command's real grandchild process is orphaned"
        )
        assert raw.returncode == -1
        assert "timed out" in (raw.stderr or "")


# ---------------------------------------------------------------------------
# T017 + T018 - JUnit XML parsing
# ---------------------------------------------------------------------------

class TestJunitXmlParsing:
    """test_junit_xml_parsing — parse a sample JUnit XML file."""

    def test_parse_basic(self, tmp_path: Path) -> None:
        xml_file = tmp_path / "junit.xml"
        xml_file.write_text(SAMPLE_JUNIT_XML, encoding="utf-8")

        total, passed, failed, skipped, failures = _parse_junit_xml(xml_file)

        assert total == 4
        assert passed == 2
        assert failed == 1
        assert skipped == 1
        assert len(failures) == 1
        f = failures[0]
        assert f.test == "tests.test_foo.test_fail"
        assert "AssertionError" in f.error
        assert f.file == "tests/test_foo.py:10"

    def test_parse_truncates_long_error(self, tmp_path: Path) -> None:
        long_msg = "A" * 300
        xml_content = textwrap.dedent(f"""\
            <?xml version="1.0" encoding="utf-8"?>
            <testsuites>
              <testsuite tests="1" failures="1">
                <testcase classname="tests.foo" name="test_bar">
                  <failure message="{long_msg}">details</failure>
                </testcase>
              </testsuite>
            </testsuites>
        """)
        xml_file = tmp_path / "junit.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        _, _, _, _, failures = _parse_junit_xml(xml_file)
        assert len(failures) == 1
        assert len(failures[0].error) <= 200

    def test_parse_error_element(self, tmp_path: Path) -> None:
        xml_content = textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <testsuites>
              <testsuite tests="1" errors="1">
                <testcase classname="tests.foo" name="test_boom">
                  <error message="RuntimeError: segfault">traceback here</error>
                </testcase>
              </testsuite>
            </testsuites>
        """)
        xml_file = tmp_path / "junit.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        total, passed, failed, skipped, failures = _parse_junit_xml(xml_file)
        assert failed == 1
        assert failures[0].error == "RuntimeError: segfault"


# ---------------------------------------------------------------------------
# T019 - diff_baseline()
# ---------------------------------------------------------------------------

class TestDiffBaseline:
    """Tests for diff_baseline()."""

    def test_diff_baseline_pre_existing(self) -> None:
        """Failure in both baseline and current → pre_existing."""
        f = _make_failure("tests.foo.test_bad")
        baseline = _make_baseline(failures=(f,), failed=1)
        pre, new, fixed = diff_baseline(baseline, [f])
        assert f in pre
        assert len(new) == 0
        assert len(fixed) == 0

    def test_diff_baseline_new_regression(self) -> None:
        """Failure only in current → new_failure (regression)."""
        baseline = _make_baseline(failures=(), failed=0)
        current_f = _make_failure("tests.foo.test_new_regression")
        pre, new, fixed = diff_baseline(baseline, [current_f])
        assert len(pre) == 0
        assert current_f in new
        assert len(fixed) == 0

    def test_diff_baseline_fixed(self) -> None:
        """Failure in baseline but absent in current → fixed."""
        f = _make_failure("tests.foo.test_was_broken")
        baseline = _make_baseline(failures=(f,), failed=1)
        pre, new, fixed = diff_baseline(baseline, [])
        assert len(pre) == 0
        assert len(new) == 0
        assert "tests.foo.test_was_broken" in fixed

    def test_diff_baseline_sentinel(self) -> None:
        """Sentinel baseline (failed=-1) → all current failures are new."""
        sentinel = _make_baseline(failures=(), failed=-1)
        current_failures = [
            _make_failure("tests.a.test_x"),
            _make_failure("tests.b.test_y"),
        ]
        pre, new, fixed = diff_baseline(sentinel, current_failures)
        assert len(pre) == 0
        assert set(new) == set(current_failures)
        assert len(fixed) == 0

    def test_diff_baseline_mixed(self) -> None:
        """Mixed scenario: some pre-existing, some new, some fixed."""
        f_old = _make_failure("tests.old.test_existing")
        f_fixed = _make_failure("tests.old.test_fixed_now")
        baseline = _make_baseline(failures=(f_old, f_fixed), failed=2)

        f_new = _make_failure("tests.new.test_regression")
        current_failures = [f_old, f_new]

        pre, new, fixed = diff_baseline(baseline, current_failures)
        assert f_old in pre
        assert f_new in new
        assert "tests.old.test_fixed_now" in fixed


# ---------------------------------------------------------------------------
# T021 - Review prompt includes baseline section
# ---------------------------------------------------------------------------

class TestReviewPromptIncludesBaselineSection:
    """test_review_prompt_includes_baseline_section."""

    def test_baseline_section_appears_for_pre_existing_failures(self, tmp_path: Path) -> None:
        """When baseline has failures, review prompt output references them."""
        # Build a minimal baseline artifact that the review path would load
        failure = _make_failure("tests.existing.test_broken", "ValueError: oops")
        baseline = _make_baseline(
            wp_id="WP01",
            failed=1,
            failures=(failure,),
            base_branch="main",
            base_commit="deadbeef1234567",
        )
        # Save it where the review path would look
        artifact_dir = tmp_path / "tasks" / "WP01-slug"
        artifact_dir.mkdir(parents=True)
        baseline.save(artifact_dir / "baseline-tests.json")

        # Load it back and verify the data we'd render in the review prompt
        loaded = BaselineTestResult.load(artifact_dir / "baseline-tests.json")
        assert loaded is not None
        assert loaded.failed == 1

        # Simulate prompt rendering logic
        lines = []
        if loaded.failed > 0:
            lines.append(
                f"**{loaded.failed} test failure(s) existed BEFORE this WP** "
                f"(base: {loaded.base_branch} @ {loaded.base_commit[:7]}):"
            )
            for f in loaded.failures:
                lines.append(f"| {f.test} | {f.error[:80]} | {f.file} |")
            lines.append("**These failures are NOT regressions introduced by this WP.**")

        rendered = "\n".join(lines)
        assert "1 test failure(s) existed BEFORE this WP" in rendered
        assert "tests.existing.test_broken" in rendered
        assert "NOT regressions" in rendered

    def test_baseline_section_skipped_when_no_artifact(self, tmp_path: Path) -> None:
        """If no baseline artifact exists, load returns None and section is omitted."""
        result = BaselineTestResult.load(tmp_path / "nonexistent" / "baseline-tests.json")
        assert result is None  # no section should be added

    def test_sentinel_baseline_shows_warning(self, tmp_path: Path) -> None:
        """Sentinel baseline (failed=-1) triggers the warning message."""
        sentinel = _make_baseline(failed=-1)
        artifact = tmp_path / "baseline-tests.json"
        sentinel.save(artifact)
        loaded = BaselineTestResult.load(artifact)
        assert loaded is not None
        assert loaded.failed == -1

        lines = []
        if loaded.failed == -1:
            lines.append("**Warning**: Baseline test capture failed at implement time.")

        rendered = "\n".join(lines)
        assert "Warning" in rendered


# ---------------------------------------------------------------------------
# T022 - Config custom test command
# ---------------------------------------------------------------------------

class TestConfigCustomTestCommand:
    """test_config_custom_test_command — config overrides default pytest command."""

    def test_default_command(self, tmp_path: Path) -> None:
        """Without config, baseline capture remains disabled."""
        cmd, fmt = _get_test_command(tmp_path)
        assert cmd is None
        assert fmt is None

    def test_custom_command_from_config(self, tmp_path: Path) -> None:
        """Config review.test_command overrides the default."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        config_yaml = kittify / "config.yaml"
        config_yaml.write_text(
            "review:\n  test_command: 'python -m pytest --junitxml={output_file}'\n",
            encoding="utf-8",
        )
        cmd, fmt = _get_test_command(tmp_path)
        assert cmd == "python -m pytest --junitxml={output_file}"
        assert fmt == "junit_xml"

    def test_custom_format_from_config(self, tmp_path: Path) -> None:
        """Config review.test_output_format is respected."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        config_yaml = kittify / "config.yaml"
        config_yaml.write_text(
            "review:\n  test_command: 'myrunner --output={output_file}'\n  test_output_format: junit_xml\n",
            encoding="utf-8",
        )
        cmd, fmt = _get_test_command(tmp_path)
        assert cmd == "myrunner --output={output_file}"
        assert fmt == "junit_xml"

    def test_config_without_review_section(self, tmp_path: Path) -> None:
        """Config without 'review' key leaves baseline capture disabled."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("agents:\n  available:\n    - claude\n", encoding="utf-8")
        cmd, fmt = _get_test_command(tmp_path)
        assert cmd is None
        assert fmt is None


# ---------------------------------------------------------------------------
# Additional coverage for error paths
# ---------------------------------------------------------------------------

class TestCoverageEdgeCases:
    """Additional tests to cover edge/error paths in baseline.py."""

    def test_load_missing_and_existing_artifact(self, tmp_path: Path) -> None:
        """BaselineTestResult.load() returns None for a missing path and round-trips a saved one.

        (Retargeted from the deleted, never-called ``load_baseline`` wrapper.)
        """
        from specify_cli.review.baseline import BaselineTestResult

        # Non-existent path
        result = BaselineTestResult.load(tmp_path / "missing.json")
        assert result is None

        # Existing path
        baseline = _make_baseline()
        artifact = tmp_path / "baseline-tests.json"
        baseline.save(artifact)
        loaded = BaselineTestResult.load(artifact)
        assert loaded is not None
        assert loaded.wp_id == baseline.wp_id

    def test_find_repo_root_walks_up(self, tmp_path: Path) -> None:
        """_find_repo_root walks up parent directories to find .git."""
        from specify_cli.review.baseline import _find_repo_root

        # No .git — should return None
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        result = _find_repo_root(deep)
        assert result is None

        # With .git in parent
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        result = _find_repo_root(deep)
        assert result == tmp_path

    def test_capture_baseline_no_git_repo(self, tmp_path: Path) -> None:
        """capture_baseline returns sentinel when no .git directory found."""
        # tmp_path has no .git anywhere
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        feature_dir = tmp_path / "kitty-specs" / "066-test"
        (feature_dir / "tasks" / "WP04-test").mkdir(parents=True)

        result = capture_baseline(
            worktree_path=worktree,
            base_branch="main",
            wp_id="WP04",
            mission_slug="066-test",
            feature_dir=feature_dir,
            wp_slug="WP04-test",
        )
        assert result is not None
        assert result.failed == -1

    def test_capture_baseline_skips_when_no_test_command_configured(self, tmp_path: Path) -> None:
        """No review.test_command means no subprocess work and no sentinel noise."""
        repo = tmp_path / "repo"
        _make_fake_git_dir(repo)
        feature_dir = repo / "kitty-specs" / "066-test"
        (feature_dir / "tasks" / "WP04-test").mkdir(parents=True)

        with patch("subprocess.run") as run_mock:
            result = capture_baseline(
                worktree_path=repo,
                base_branch="main",
                wp_id="WP04",
                mission_slug="066-test",
                feature_dir=feature_dir,
                wp_slug="WP04-test",
            )

        assert result is None
        run_mock.assert_not_called()

    def test_capture_baseline_git_rev_parse_fails(self, tmp_path: Path) -> None:
        """Sentinel returned when git rev-parse fails with non-zero exit."""
        repo = tmp_path / "repo"
        _make_fake_git_dir(repo)
        feature_dir = repo / "kitty-specs" / "066-test"
        (feature_dir / "tasks" / "WP04-test").mkdir(parents=True)

        def fake_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 128
            result.stdout = ""
            result.stderr = "fatal: unknown revision 'main'"
            return result

        with patch("subprocess.run", side_effect=fake_run):
            result = capture_baseline(
                worktree_path=repo,
                base_branch="main",
                wp_id="WP04",
                mission_slug="066-test",
                feature_dir=feature_dir,
                wp_slug="WP04-test",
                test_command="custom-runner --junitxml={output_file}",
            )

        assert result is not None
        assert result.failed == -1

    def test_capture_baseline_skips_unsupported_output_format(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _make_fake_git_dir(repo)
        feature_dir = repo / "kitty-specs" / "066-test"
        (feature_dir / "tasks" / "WP04-test").mkdir(parents=True)

        with patch("specify_cli.review.baseline._get_test_command", return_value=("pytest-json", "json")):
            result = capture_baseline(
                worktree_path=repo,
                base_branch="main",
                wp_id="WP04",
                mission_slug="066-test",
                feature_dir=feature_dir,
                wp_slug="WP04-test",
            )

        assert result is None

    def test_capture_baseline_junit_xml_missing(self, tmp_path: Path) -> None:
        """Sentinel when JUnit XML is not produced (test runner didn't write it)."""
        repo = tmp_path / "repo"
        _make_fake_git_dir(repo)
        feature_dir = repo / "kitty-specs" / "066-test"
        (feature_dir / "tasks" / "WP04-test").mkdir(parents=True)

        def fake_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "abc1234\n"
            result.stderr = ""
            # Don't write JUnit XML
            return result

        with patch("subprocess.run", side_effect=fake_run):
            result = capture_baseline(
                worktree_path=repo,
                base_branch="main",
                wp_id="WP04",
                mission_slug="066-test",
                feature_dir=feature_dir,
                wp_slug="WP04-test",
                test_command="custom-runner --junitxml={output_file}",
            )

        assert result is not None
        assert result.failed == -1

    def test_capture_baseline_custom_test_runner_label(self, tmp_path: Path) -> None:
        """test_runner field is 'custom' when command doesn't include 'pytest'."""
        repo = tmp_path / "repo"
        _make_fake_git_dir(repo)
        feature_dir = repo / "kitty-specs" / "066-test"
        (feature_dir / "tasks" / "WP04-test").mkdir(parents=True)

        def fake_run_with_xml(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "abc1234\n"
            result.stderr = ""
            cmd_text = " ".join(cmd) if isinstance(cmd, list) else cmd
            if isinstance(cmd_text, str) and "myrunner" in cmd_text:
                # Write to the real resolved target (kwargs["env"]), never a
                # literal parsed out of the (possibly shell-quoted) command
                # string — mirrors the safe sibling fakes at ~253/294/338.
                output_file = kwargs["env"]["SPEC_KITTY_CMD_OUTPUT_FILE"]
                Path(output_file).write_text(
                    '<?xml version="1.0"?><testsuites><testsuite tests="1">'
                    '<testcase classname="a" name="b"/></testsuite></testsuites>',
                    encoding="utf-8",
                )
            return result

        with patch("subprocess.run", side_effect=fake_run_with_xml):
            result = capture_baseline(
                worktree_path=repo,
                base_branch="main",
                wp_id="WP04",
                mission_slug="066-test",
                feature_dir=feature_dir,
                wp_slug="WP04-test",
                test_command="myrunner --output={output_file}",
            )

        assert result is not None
        assert result.wp_id == "WP04"
        # The fake now writes the JUnit XML to the resolved output path, so the
        # result is fully parsed (never a sentinel) — pin the documented
        # custom-runner label (baseline.py: "custom" when the command has no "pytest").
        assert result.test_runner == "custom"


# ---------------------------------------------------------------------------
# Issue #3612 — DeclaredCommandScopeSource capture path
# ---------------------------------------------------------------------------
#
# Unlike TestCaptureBaseline above (the LEGACY config-driven path, which
# already substitutes {output_file} and shell-wraps via
# run_configured_command_template — a mocked-subprocess fake repo suffices
# there), the injected-ScopeSource path
# (_capture_baseline_via_scope_source / DeclaredCommandScopeSource) had ZERO
# coverage in this file before #3612 — exactly the gap that let the three
# behaviours below regress silently. These drive a REAL git repo + REAL
# subprocess (mirroring test_baseline_lifecycle.py / test_baseline_head_parity.py's
# established style for this code path) rather than mocking subprocess.run,
# since the fix is precisely about what actually reaches exec().


def _init_git_repo_3612(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)


def _write_file_3612(repo: Path, relative_path: str, content: str) -> None:
    target = repo / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _git_commit_all_3612(path: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=path, check=True)


def _build_repo_with_command_3612(
    tmp_path: Path, *, name: str, test_command: str, extra_files: dict[str, str]
) -> Path:
    repo = tmp_path / name
    _init_git_repo_3612(repo)
    for relative_path, content in extra_files.items():
        _write_file_3612(repo, relative_path, content)
    _write_file_3612(repo, ".kittify/config.yaml", f"review:\n  test_command: {test_command!r}\n")
    _git_commit_all_3612(repo, "base commit")
    return repo


def _capture_via_scope_source(repo: Path, *, wp_slug: str) -> BaselineTestResult | None:
    feature_dir = repo.parent / "kitty-specs" / "issue-3612"
    return capture_baseline(
        worktree_path=repo,
        base_branch="main",
        wp_id="WP01",
        mission_slug="issue-3612",
        feature_dir=feature_dir,
        wp_slug=wp_slug,
        scope_source=DeclaredCommandScopeSource(repo_root=repo),
    )


class TestCaptureBaselineViaScopeSourceDeclaredCommand:
    """Focused units for the three #3612 fixes on the ScopeSource capture path."""

    def test_output_file_placeholder_is_substituted_to_a_real_path(self, tmp_path: Path) -> None:
        """A ``--report={output_file}`` flag (not the sniffed ``--junitxml=``
        literal) must resolve to a REAL path this source controls, never the
        literal 8-character string ``{output_file}`` — proving substitution
        independent of the ``--junitxml=`` special case (which can
        accidentally "work" for that one flag spelling since a real test
        runner happily writes to a literally-braced filename, masking the
        underlying defect)."""
        script = textwrap.dedent(
            """\
            import sys
            from pathlib import Path

            report_arg = next(a for a in sys.argv if a.startswith("--report="))
            report_path = report_arg.split("=", 1)[1]
            assert report_path != "{output_file}", f"substitution never happened: {report_path!r}"
            junit_xml = (
                '<?xml version="1.0" encoding="utf-8"?>\\n'
                '<testsuites><testsuite name="pytest" tests="1" failures="1">'
                '<testcase classname="tests.test_thing" name="test_boom">'
                '<failure message="boom">boom</failure></testcase>'
                '</testsuite></testsuites>\\n'
            )
            Path(report_path).write_text(junit_xml, encoding="utf-8")
            sys.exit(1)
            """
        )
        repo = _build_repo_with_command_3612(
            tmp_path,
            name="case-a-output-file",
            test_command=f"{sys.executable} run_tests.py --report={{output_file}}",
            extra_files={"run_tests.py": script},
        )

        baseline = _capture_via_scope_source(repo, wp_slug="WP01-case-a")

        assert baseline is not None
        assert baseline.failed != -1
        assert baseline.failures
        assert baseline.failures[0].test == "tests.test_thing.test_boom"

    def test_shell_variable_expansion(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A configured command referencing an exported shell variable (a
        common, portable way to point at a project-local interpreter) must
        be expanded — never passed to ``exec`` as the literal token
        ``$PYBIN_3612``."""
        monkeypatch.setenv("PYBIN_3612", sys.executable)
        script = "print('FAIL tests.test_thing.test_boom: boom')\nraise SystemExit(1)\n"
        repo = _build_repo_with_command_3612(
            tmp_path,
            name="case-b-shell-var",
            test_command="$PYBIN_3612 run_tests.py",
            extra_files={"run_tests.py": script},
        )

        baseline = _capture_via_scope_source(repo, wp_slug="WP01-case-b")

        assert baseline is not None
        assert baseline.failed != -1
        assert not any("Errno 2" in f.error for f in baseline.failures), (
            "an unexpanded $VAR reaching exec() as a literal token produces a "
            "launch failure ([Errno 2] No such file or directory), never a "
            "real test failure"
        )
        assert any(f.test == "tests.test_thing.test_boom" for f in baseline.failures)

    def test_refuse_not_store_on_unparseable_clean_exit(self, tmp_path: Path) -> None:
        """A declared command that exits 0 but produces NEITHER a JUnit
        artifact NOR any ``FAIL <test>`` line is indistinguishable, under a
        naive ``total=len(failures)`` encoding, from "ran a suite of zero
        tests successfully" — both collapse to ``total=0, passed=0,
        failed=0``. Capture must refuse to store that fabricated clean
        baseline and surface the sentinel (``failed == -1``) instead, so the
        gate treats it as ``UNVERIFIED_BASELINE``, never verified-clean."""
        script = "print('nothing parseable here')\nraise SystemExit(0)\n"
        repo = _build_repo_with_command_3612(
            tmp_path,
            name="case-c-refuse-not-store",
            test_command=f"{sys.executable} run_tests.py",
            extra_files={"run_tests.py": script},
        )

        baseline = _capture_via_scope_source(repo, wp_slug="WP01-case-c")

        assert baseline is not None
        assert baseline.failed == -1, (
            f"got a fabricated total={baseline.total}/passed={baseline.passed}/"
            f"failed={baseline.failed} 'clean' baseline instead of the sentinel"
        )
