"""Tests for dashboard CLI command status reporting accuracy.

Detects the bug where spec-kitty dashboard CLI command reports error
even though the dashboard actually starts successfully.

Bug Report: findings/0.5.1/2025-11-13_24_dashboard_cli_false_error.md

Problem:
- CLI shows: "❌ Unable to start or locate the dashboard"
- Reality: Dashboard IS running on the specified port
- Impact: Misleading error message, user thinks it failed

These tests validate that CLI status reporting matches actual dashboard state.
"""

import ast
import pytest
import subprocess
import textwrap
import time
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory, mkstemp
from collections.abc import Iterator
import signal
import os
import socket
import sys
from urllib.request import urlopen
from urllib.error import URLError
import json

import kernel.clock as clock_module
from kernel.clock import FrozenClock, now_epoch
from kernel.locks import machine_file_lock
from tests.test_isolation_helpers import get_venv_python

pytestmark = pytest.mark.git_repo

_DASHBOARD_TEST_MANIFEST_ENV = "SPEC_KITTY_DASHBOARD_TEST_MANIFEST"
_DASHBOARD_TEST_MANIFEST_FILENAME = "dashboard-test-processes.json"
_DASHBOARD_TEST_MANIFEST_STALE_SECONDS = 10 * 60


def is_dashboard_accessible(port: int, timeout: float = 2.0) -> bool:
    """Check if dashboard is accessible on the given port.

    Args:
        port: Port number to check
        timeout: Timeout in seconds

    Returns:
        True if dashboard responds, False otherwise
    """
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/features", timeout=timeout) as response:
            if response.status != 200:
                return False

            payload = json.loads(response.read().decode())
            return isinstance(payload, dict) and isinstance(payload.get("features"), list)
    except (URLError, OSError, Exception):
        return False


def run_dashboard_cli(
    *args: str,
    cwd: Path,
    timeout: float = 30,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    command = [str(get_venv_python()), "-m", "specify_cli.__init__", *args]
    dashboard_port = _extract_dashboard_port(args)
    if dashboard_port is not None:
        _record_dashboard_candidate(dashboard_port, cwd)

    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if dashboard_port is not None and is_dashboard_accessible(dashboard_port, timeout=0.3):
        _record_dashboard_candidate(dashboard_port, cwd, pids=_process_ids_for_port(dashboard_port))
    return result


def _extract_dashboard_port(args: tuple[str, ...]) -> int | None:
    if not args or args[0] != "dashboard" or "--kill" in args:
        return None
    try:
        index = args.index("--port")
        return int(args[index + 1])
    except (ValueError, IndexError):
        return None


def port_has_listener(port: int) -> bool:
    """Return whether a process is listening on the given port."""
    result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True, check=False)
    return bool(result.stdout.strip())


def _process_ids_for_port(port: int) -> list[int]:
    result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True, check=False)
    pids = []
    for raw_pid in result.stdout.splitlines():
        try:
            pids.append(int(raw_pid.strip()))
        except ValueError:
            continue
    return pids


def wait_for_port_state(port: int, *, occupied: bool, timeout: float = 2.0, interval: float = 0.1) -> bool:
    """Poll until a port becomes occupied or free."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_has_listener(port) is occupied:
            return True
        time.sleep(interval)
    return port_has_listener(port) is occupied


_reserved_test_ports: set[int] = set()


def reserve_free_port() -> int:
    """Reserve an OS-assigned free loopback port and remember it for cleanup.

    Hard-coded ports went red on hosts where a platform service already owns
    the port (issue #39: exe.dev VMs run one on 127.0.0.1:9999). With a
    reserved port the CLI starts the dashboard where the test expects it, so
    "CLI status matches actual dashboard state" is exercised deterministically.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    _reserved_test_ports.add(port)
    return port


def wait_for_dashboard_state(
    port: int,
    *,
    accessible: bool,
    timeout: float = 3.0,
    interval: float = 0.1,
) -> bool:
    """Poll until the dashboard becomes accessible or inaccessible."""
    deadline = time.monotonic() + timeout
    probe_timeout = max(interval, 0.1)
    while time.monotonic() < deadline:
        if is_dashboard_accessible(port, timeout=probe_timeout) is accessible:
            return True
        time.sleep(interval)
    return is_dashboard_accessible(port, timeout=probe_timeout) is accessible


def kill_dashboard_process(port: int):
    """Kill any dashboard process running on the given port."""
    try:
        # Find process using the port
        pids = _process_ids_for_port(port)
        if pids:
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass
            wait_for_port_state(port, occupied=False, timeout=1.5)
    except Exception:
        pass


def _dashboard_test_manifest_path() -> Path:
    override = os.environ.get(_DASHBOARD_TEST_MANIFEST_ENV)
    if override:
        return Path(override)

    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    cache_root = Path(xdg_cache_home) if xdg_cache_home else Path.home() / ".cache"
    return cache_root / "spec-kitty" / _DASHBOARD_TEST_MANIFEST_FILENAME


def _load_dashboard_test_manifest(manifest_path: Path | None = None) -> list[dict[str, object]]:
    path = manifest_path or _dashboard_test_manifest_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _write_dashboard_test_manifest(entries: list[dict[str, object]], manifest_path: Path | None = None) -> None:
    path = manifest_path or _dashboard_test_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp_path = mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(raw_tmp_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(entries, handle, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


@contextmanager
def _dashboard_manifest_lock(manifest_path: Path | None = None) -> Iterator[None]:
    path = manifest_path or _dashboard_test_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    with machine_file_lock(lock_path, blocking=True, timeout_s=None):
        yield


def _manifest_ints(value: object) -> set[int]:
    if not isinstance(value, list):
        return set()

    ints: set[int] = set()
    for raw_value in value:
        if isinstance(raw_value, bool):
            continue
        if isinstance(raw_value, int):
            ints.add(raw_value)
        elif isinstance(raw_value, str):
            try:
                ints.add(int(raw_value))
            except ValueError:
                continue
    return ints


def _manifest_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _record_dashboard_candidate(
    port: int,
    project_dir: Path,
    *,
    pids: list[int] | None = None,
    manifest_path: Path | None = None,
) -> None:
    path = manifest_path or _dashboard_test_manifest_path()
    with _dashboard_manifest_lock(path):
        entries = _load_dashboard_test_manifest(path)
        started_at = now_epoch()
        current_listener_pids = set(_process_ids_for_port(port))
        updated = []
        for entry in entries:
            if entry.get("port") == port:
                previous_pids = _manifest_ints(entry.get("pids"))
                previous_started_at = _manifest_float(entry.get("started_at"))
                # Only the same process still listening on this port proves this
                # is a continuation rather than a fresh launch on a recycled
                # port -- carry the original started_at forward in that one
                # case; otherwise this is a new launch and gets a fresh clock
                # reading so the stale-age gate cannot fire on it prematurely.
                if previous_pids and previous_pids & current_listener_pids and previous_started_at is not None:
                    started_at = previous_started_at
                continue
            updated.append(entry)
        updated.append(
            {
                "pids": pids or [],
                "port": port,
                "project_dir": str(project_dir.resolve()),
                "started_at": started_at,
            }
        )
        _write_dashboard_test_manifest(updated, path)


def _cleanup_stale_dashboard_manifest_entries(
    *,
    max_age_seconds: float = _DASHBOARD_TEST_MANIFEST_STALE_SECONDS,
    manifest_path: Path | None = None,
) -> int:
    """Reap only stale dashboard test ports recorded by this module."""
    path = manifest_path or _dashboard_test_manifest_path()
    with _dashboard_manifest_lock(path):
        now = now_epoch()
        retained = []
        killed = 0

        for entry in _load_dashboard_test_manifest(path):
            port = entry.get("port")
            started_at = _manifest_float(entry.get("started_at"))
            if not isinstance(port, int) or isinstance(port, bool) or started_at is None:
                continue

            if now - started_at < max_age_seconds:
                retained.append(entry)
                continue

            if not port_has_listener(port):
                continue

            if not is_dashboard_accessible(port, timeout=0.3):
                continue

            manifest_pids = _manifest_ints(entry.get("pids"))
            if manifest_pids and manifest_pids.isdisjoint(_process_ids_for_port(port)):
                continue

            kill_dashboard_process(port)
            killed += 1

        if retained:
            _write_dashboard_test_manifest(retained, path)
        else:
            path.unlink(missing_ok=True)

        return killed


class TestDashboardCLIStatusReporting:
    """Test CLI command accurately reports dashboard status."""

    def test_cli_reports_success_when_dashboard_starts(self):
        """CRITICAL: Verify CLI reports success when dashboard actually starts.

        This test detects the bug in v0.5.1 where CLI shows error even
        though dashboard starts successfully.
        """
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create minimal spec-kitty project structure
            (tmpdir / ".kittify").mkdir()
            kitty_specs = tmpdir / "kitty-specs"
            kitty_specs.mkdir()

            # Create a test feature
            feature_dir = kitty_specs / "001-test-feature"
            feature_dir.mkdir()
            (feature_dir / "spec.md").write_text("# Test Feature")
            (feature_dir / "plan.md").write_text("# Test Plan")

            # Initialize git (required for spec-kitty)
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

            # Reserve a genuinely free loopback port for this test
            test_port = reserve_free_port()

            # Run dashboard command
            result = run_dashboard_cli(
                "dashboard",
                "--port",
                str(test_port),
                cwd=tmpdir,
            )

            # Check if dashboard is actually accessible
            dashboard_running = wait_for_dashboard_state(test_port, accessible=True, timeout=3.0)

            try:
                if dashboard_running:
                    # BUG DETECTION: If dashboard is running, CLI should have reported success
                    assert result.returncode == 0, (
                        f"CLI should report success (exit 0) when dashboard starts, "
                        f"got exit code {result.returncode}.\n"
                        f"Dashboard IS accessible on port {test_port}.\n"
                        f"CLI output: {result.stdout}\n"
                        f"CLI stderr: {result.stderr}"
                    )

                    # Should show success message
                    output = result.stdout + result.stderr
                    assert "✅" in output or "success" in output.lower() or "running" in output.lower(), (
                        f"CLI should show success message when dashboard starts.\nDashboard IS accessible on port {test_port}.\nGot: {output}"
                    )

                    # Should NOT show error message
                    assert "❌" not in output and "Unable to start" not in output, (
                        f"CLI should NOT show error when dashboard is running.\nDashboard IS accessible on port {test_port}.\nGot: {output}"
                    )
                else:
                    # Dashboard not running - CLI should report error
                    assert result.returncode != 0, "CLI should report error when dashboard doesn't start"

            finally:
                # Cleanup: Kill the dashboard
                kill_dashboard_process(test_port)

    def test_cli_reports_error_when_dashboard_fails(self):
        """Verify CLI reports error when dashboard genuinely fails to start."""
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create INVALID project structure (missing .kittify)
            # This should cause dashboard to fail

            # Try to start dashboard in non-spec-kitty project
            result = run_dashboard_cli(
                "dashboard",
                cwd=tmpdir,
            )

            # Should report error
            assert result.returncode != 0, "CLI should exit with error when project not initialized"

            output = result.stdout + result.stderr

            # Should show error message
            assert "❌" in output or "error" in output.lower() or "Unable" in output, f"CLI should show error message when dashboard fails. Got: {output}"

    def test_dashboard_accessibility_matches_cli_status(self):
        """Verify CLI status matches whether dashboard is actually accessible."""
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create valid project
            (tmpdir / ".kittify").mkdir()
            (tmpdir / "kitty-specs").mkdir()

            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

            test_port = reserve_free_port()

            # Run dashboard
            result = run_dashboard_cli(
                "dashboard",
                "--port",
                str(test_port),
                cwd=tmpdir,
            )

            # Check actual state
            is_accessible = wait_for_dashboard_state(test_port, accessible=True, timeout=3.0)
            cli_reported_success = result.returncode == 0

            try:
                # This is the key assertion - they should match
                assert is_accessible == cli_reported_success, (
                    f"CLI status (exit {result.returncode}) should match dashboard accessibility ({is_accessible}).\n"
                    f"Dashboard accessible: {is_accessible}\n"
                    f"CLI reported success: {cli_reported_success}\n"
                    f"CLI output: {result.stdout}\n"
                    f"CLI stderr: {result.stderr}"
                )
            finally:
                kill_dashboard_process(test_port)


class TestDashboardProcessLifecycle:
    """Test dashboard process management and lifecycle."""

    def test_dashboard_process_actually_starts(self):
        """Verify dashboard process is created and running."""
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            (tmpdir / ".kittify").mkdir()
            (tmpdir / "kitty-specs").mkdir()

            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

            test_port = reserve_free_port()

            # Start dashboard
            run_dashboard_cli(
                "dashboard",
                "--port",
                str(test_port),
                cwd=tmpdir,
            )

            wait_for_dashboard_state(test_port, accessible=True, timeout=3.0)

            # Check if process exists
            ps_result = subprocess.run(["lsof", "-ti", f":{test_port}"], capture_output=True, text=True)

            try:
                has_process = bool(ps_result.stdout.strip())

                assert has_process, f"Dashboard process should exist on port {test_port} after command runs"

                # Verify it's accessible
                assert is_dashboard_accessible(test_port), f"Dashboard should be accessible on port {test_port}"
            finally:
                kill_dashboard_process(test_port)

    def test_dashboard_kill_flag_works(self):
        """Verify --kill flag stops the dashboard."""
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            (tmpdir / ".kittify").mkdir()
            (tmpdir / "kitty-specs").mkdir()

            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

            test_port = reserve_free_port()

            # Start dashboard
            run_dashboard_cli(
                "dashboard",
                "--port",
                str(test_port),
                cwd=tmpdir,
            )

            wait_for_dashboard_state(test_port, accessible=True, timeout=3.0)

            # Verify it's running
            if is_dashboard_accessible(test_port):
                # Kill it
                kill_result = run_dashboard_cli(
                    "dashboard",
                    "--kill",
                    cwd=tmpdir,
                )

                # Should not be accessible anymore
                stopped = wait_for_dashboard_state(test_port, accessible=False, timeout=2.0)
                assert stopped, f"Dashboard should be stopped after --kill, but still accessible on {test_port}"

                # Kill command should report success
                output = kill_result.stdout + kill_result.stderr
                assert "✅" in output or "stopped" in output.lower() or "killed" in output.lower(), f"--kill should report success. Got: {output}"


class TestDashboardErrorMessages:
    """Test dashboard error message quality."""

    def test_error_message_helpful_when_not_initialized(self):
        """Verify helpful error when project not initialized."""
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Don't create .kittify (not initialized)

            result = run_dashboard_cli(
                "dashboard",
                cwd=tmpdir,
            )

            # Should fail
            assert result.returncode != 0, "Should fail when project not initialized"

            output = result.stdout + result.stderr

            # Should mention init or project setup
            assert "init" in output.lower() or "project" in output.lower() or ".kittify" in output.lower(), (
                f"Error should suggest initialization or mention project. Got: {output}"
            )

            # Should mention project or worktree
            assert "project" in output.lower() or "worktree" in output.lower(), f"Error should mention project or worktree. Got: {output}"


class TestDashboardAPIVerification:
    """Test dashboard API endpoint verification."""

    def test_api_features_endpoint_returns_data(self):
        """Verify /api/features endpoint works when dashboard running."""
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create valid project with feature
            (tmpdir / ".kittify").mkdir()
            kitty_specs = tmpdir / "kitty-specs"
            kitty_specs.mkdir()

            feature_dir = kitty_specs / "001-test"
            feature_dir.mkdir()
            (feature_dir / "spec.md").write_text("# Test Spec")

            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

            test_port = reserve_free_port()

            # Start dashboard
            run_dashboard_cli(
                "dashboard",
                "--port",
                str(test_port),
                cwd=tmpdir,
            )

            wait_for_dashboard_state(test_port, accessible=True, timeout=3.0)

            try:
                # Test API endpoint
                if is_dashboard_accessible(test_port):
                    with urlopen(f"http://127.0.0.1:{test_port}/api/features", timeout=3.0) as response:
                        assert response.status == 200, "API should return 200 when dashboard running"

                        data = json.loads(response.read().decode())
                        assert "features" in data, f"API should return features list. Got: {data}"

                        # Should have features array
                        assert len(data["features"]) >= 0, "Should return features array (may be empty)"
            finally:
                kill_dashboard_process(test_port)

    def test_api_returns_valid_json(self):
        """Verify API returns valid JSON structure."""
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            (tmpdir / ".kittify").mkdir()
            (tmpdir / "kitty-specs").mkdir()

            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

            test_port = reserve_free_port()

            run_dashboard_cli(
                "dashboard",
                "--port",
                str(test_port),
                cwd=tmpdir,
            )

            wait_for_dashboard_state(test_port, accessible=True, timeout=3.0)

            try:
                if is_dashboard_accessible(test_port):
                    with urlopen(f"http://127.0.0.1:{test_port}/api/features", timeout=3.0) as response:
                        data = json.loads(response.read().decode())

                        # Should have required fields
                        assert isinstance(data, dict), "Response should be dict"
                        assert "features" in data, "Should have features field"
                        assert isinstance(data["features"], list), "Features should be list"
            finally:
                kill_dashboard_process(test_port)


class TestDashboardRaceConditions:
    """Test for race conditions in dashboard startup."""

    def test_cli_waits_for_dashboard_to_start(self):
        """Verify CLI doesn't report error if dashboard takes time to start."""
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            (tmpdir / ".kittify").mkdir()
            kitty_specs = tmpdir / "kitty-specs"
            kitty_specs.mkdir()

            # Create multiple features (slower startup)
            for i in range(1, 4):
                feature_dir = kitty_specs / f"00{i}-test"
                feature_dir.mkdir()
                (feature_dir / "spec.md").write_text(f"# Feature {i}")
                (feature_dir / "plan.md").write_text(f"# Plan {i}")

            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

            test_port = reserve_free_port()

            # Run dashboard
            result = run_dashboard_cli(
                "dashboard",
                "--port",
                str(test_port),
                cwd=tmpdir,
                timeout=10,
            )

            try:
                # Check if actually accessible
                is_accessible = wait_for_dashboard_state(test_port, accessible=True, timeout=5.0)

                if is_accessible:
                    # Dashboard started - CLI should not have reported error
                    output = result.stdout + result.stderr

                    # This test will catch race conditions where dashboard starts
                    # but CLI reports error due to timing
                    assert result.returncode == 0 or "running" in output.lower(), (
                        f"CLI should indicate success if dashboard is accessible.\n"
                        f"Dashboard IS running on port {test_port}.\n"
                        f"CLI exit code: {result.returncode}\n"
                        f"CLI output: {output}"
                    )
            finally:
                kill_dashboard_process(test_port)


class TestDashboardCleanup:
    """Test dashboard cleanup and process management."""

    def test_no_orphaned_processes_after_kill(self):
        """Verify --kill actually terminates dashboard process."""
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            (tmpdir / ".kittify").mkdir()
            (tmpdir / "kitty-specs").mkdir()

            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

            test_port = reserve_free_port()

            # Start dashboard
            run_dashboard_cli(
                "dashboard",
                "--port",
                str(test_port),
                cwd=tmpdir,
            )

            wait_for_dashboard_state(test_port, accessible=True, timeout=3.0)

            # Get process ID
            ps_before = subprocess.run(["lsof", "-ti", f":{test_port}"], capture_output=True, text=True)

            if ps_before.stdout.strip():
                # Kill dashboard
                run_dashboard_cli(
                    "dashboard",
                    "--kill",
                    cwd=tmpdir,
                )

                wait_for_port_state(test_port, occupied=False, timeout=2.0)

                # Check process is gone
                ps_after = subprocess.run(["lsof", "-ti", f":{test_port}"], capture_output=True, text=True)

                assert not ps_after.stdout.strip(), f"Dashboard process should be terminated after --kill.\nProcess still running: {ps_after.stdout}"

                # Verify not accessible
                assert not is_dashboard_accessible(test_port, timeout=1.0), "Dashboard should not be accessible after --kill"


# Module-level cleanup: reap only stale dashboard ports this module recorded.
@pytest.fixture(autouse=True, scope="module")
def cleanup_stale_dashboard_manifest_entries():
    """Cleanup orphaned dashboard processes without a process-name-wide sweep."""
    _cleanup_stale_dashboard_manifest_entries()

    yield

    _cleanup_stale_dashboard_manifest_entries()


# Per-test cleanup: Kill dashboards on specific test ports
@pytest.fixture(autouse=True, scope="function")
def cleanup_test_dashboards():
    """Cleanup any test dashboard processes after each test."""
    yield

    # Cleanup only the ports this worker actually reserved.
    for port in sorted(_reserved_test_ports):
        kill_dashboard_process(port)
    _reserved_test_ports.clear()


def _simple_name_bindings(tree: ast.Module) -> dict[str, ast.AST]:
    bindings: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            bindings[node.target.id] = node.value
    return bindings


def _literal_strings(
    node: ast.AST,
    bindings: dict[str, ast.AST],
    resolving: frozenset[str] = frozenset(),
) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Name) and node.id in bindings and node.id not in resolving:
        return _literal_strings(bindings[node.id], bindings, resolving | {node.id})

    strings: list[str] = []
    for child in ast.iter_child_nodes(node):
        strings.extend(_literal_strings(child, bindings, resolving))
    return strings


def _subprocess_command_strings(call: ast.Call, bindings: dict[str, ast.AST]) -> list[str]:
    if not isinstance(call.func, ast.Attribute) or call.func.attr not in {
        "Popen",
        "call",
        "check_call",
        "check_output",
        "run",
    }:
        return []
    if not isinstance(call.func.value, ast.Name) or call.func.value.id != "subprocess":
        return []
    if not call.args:
        return []

    return _literal_strings(call.args[0], bindings)


def _process_sweep_violations(tree: ast.Module) -> list[str]:
    bindings = _simple_name_bindings(tree)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(alias.name == "psutil" for alias in node.names):
            violations.append(f"{node.lineno}: psutil import permits machine-wide process iteration")
        if isinstance(node, ast.ImportFrom) and node.module == "psutil":
            violations.append(f"{node.lineno}: psutil import permits machine-wide process iteration")
        if isinstance(node, ast.Attribute) and node.attr == "process_iter":
            violations.append(f"{node.lineno}: psutil process iteration")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "process_iter":
            violations.append(f"{node.lineno}: psutil process iteration")

        if not isinstance(node, ast.Call):
            continue

        command_strings = _subprocess_command_strings(node, bindings)
        if not command_strings:
            continue

        command_text = " ".join(command_strings)
        command_words = command_text.split()
        broad_tools = {word.rsplit("/", 1)[-1] for word in command_words} & {
            "pgrep",
            "killall",
        }
        for tool in sorted(broad_tools):
            violations.append(f"{node.lineno}: broad process kill tool {tool}")
        if any(command == "ps" and option in {"aux", "-A", "-e", "-ef"} for command, option in zip(command_words, command_words[1:], strict=False)):
            violations.append(f"{node.lineno}: broad process enumeration")
        if "run_dashboard_server" in command_text:
            violations.append(f"{node.lineno}: dashboard process-name subprocess sweep")

    return violations


def test_no_process_name_wide_dashboard_kill():
    """Guard against reintroducing a process-name-wide dashboard sweep (#70)."""
    source = Path(__file__).read_text(encoding="utf-8")
    violations = _process_sweep_violations(ast.parse(source))

    assert not violations, (
        f"This module must not use a process-name-wide dashboard cleanup sweep; scope cleanup to _reserved_test_ports instead (see #70): {violations}"
    )


_MUTATION_DASHBOARD_NAME = "run_" + "dashboard_server"
_MUTATION_PGREP = "pg" + "rep"
_MUTATION_KILLALL = "kill" + "all"


def _mutation_source(*lines: str) -> str:
    """Build adversarial snippets without tripping this module's text gate."""
    return "\n".join(lines)


@pytest.mark.parametrize(
    ("source", "expected_violation"),
    [
        ("import psutil\npsutil.process_iter()", "psutil import"),
        ("import psutil as ps\nps.process_iter()", "psutil import"),
        ("from psutil import process_iter\nprocess_iter()", "psutil import"),
        (
            _mutation_source(
                "import subprocess",
                f'subprocess.run(["{_MUTATION_PGREP}", "-f", "{_MUTATION_DASHBOARD_NAME}"])',
            ),
            "broad process kill tool pgrep",
        ),
        (
            _mutation_source(
                "import subprocess",
                f'command = ["{_MUTATION_PGREP}", "-f", "{_MUTATION_DASHBOARD_NAME}"]',
                "subprocess.run(command)",
            ),
            "broad process kill tool pgrep",
        ),
        (
            _mutation_source(
                "import subprocess",
                f'subprocess.run(["sh", "-c", "{_MUTATION_PGREP} -f {_MUTATION_DASHBOARD_NAME}"])',
            ),
            "broad process kill tool pgrep",
        ),
        (
            _mutation_source(
                "import subprocess",
                f'subprocess.run(["{_MUTATION_KILLALL}", "-f", "{_MUTATION_DASHBOARD_NAME}"])',
            ),
            "broad process kill tool killall",
        ),
        (
            _mutation_source(
                "import subprocess",
                f'subprocess.run("ps aux | grep {_MUTATION_DASHBOARD_NAME}", shell=True)',
            ),
            "broad process enumeration",
        ),
        (
            _mutation_source(
                "import subprocess",
                f'subprocess.run(["sh", "-c", "ps aux | grep {_MUTATION_DASHBOARD_NAME}"])',
            ),
            "broad process enumeration",
        ),
        (
            _mutation_source(
                "import subprocess",
                'result = subprocess.run(["ps", "aux"])',
                f'"{_MUTATION_DASHBOARD_NAME}" in result.stdout',
            ),
            "broad process enumeration",
        ),
    ],
)
def test_process_sweep_guard_catches_known_mutation(source: str, expected_violation: str):
    """Prove the guard fails for each process-wide cleanup mechanism from #365."""
    violations = _process_sweep_violations(ast.parse(source))
    assert any(expected_violation in violation for violation in violations)


def test_process_sweep_guard_allows_port_scoped_cleanup():
    """Keep the intended lsof-by-reserved-port cleanup outside the blocklist."""
    source = 'import subprocess\nsubprocess.run(["lsof", "-ti", f":{port}"])'
    assert not _process_sweep_violations(ast.parse(source))


def test_record_dashboard_candidate_gives_new_launch_on_recycled_port_a_fresh_started_at(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A fresh launch on a recycled port must not inherit the old occupant's started_at.

    Regression for the squad pass-2 MAJOR on PR#523: recording port 61999 at
    an old instant, then re-recording the same port later for a live,
    unrelated process, must not leave the old ``started_at`` in place --
    that is exactly what disarmed the stale-age gate.
    """
    manifest = tmp_path / "manifest.json"
    port = 61999
    old_instant = clock_module.datetime.fromtimestamp(1_000_000.0, tz=clock_module.UTC)
    new_instant = clock_module.datetime.fromtimestamp(1_001_200.0, tz=clock_module.UTC)
    module = sys.modules[__name__]

    monkeypatch.setattr(clock_module, "DEFAULT_CLOCK", FrozenClock(instant=old_instant))
    monkeypatch.setattr(module, "_process_ids_for_port", lambda _port: [1111])
    _record_dashboard_candidate(port, tmp_path / "old-project", pids=[1111], manifest_path=manifest)

    monkeypatch.setattr(clock_module, "DEFAULT_CLOCK", FrozenClock(instant=new_instant))
    monkeypatch.setattr(module, "_process_ids_for_port", lambda _port: [4242])
    _record_dashboard_candidate(port, tmp_path / "new-project", pids=[4242], manifest_path=manifest)

    [entry] = _load_dashboard_test_manifest(manifest)
    assert entry["started_at"] == 1_001_200.0
    assert entry["pids"] == [4242]


def test_record_dashboard_candidate_keeps_started_at_when_same_process_still_listens(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Re-recording a port whose listener is unchanged must keep the original started_at."""
    manifest = tmp_path / "manifest.json"
    port = 61999
    original_instant = clock_module.datetime.fromtimestamp(1_000_000.0, tz=clock_module.UTC)
    later_instant = clock_module.datetime.fromtimestamp(1_000_030.0, tz=clock_module.UTC)
    module = sys.modules[__name__]

    monkeypatch.setattr(clock_module, "DEFAULT_CLOCK", FrozenClock(instant=original_instant))
    monkeypatch.setattr(module, "_process_ids_for_port", lambda _port: [5555])
    _record_dashboard_candidate(port, tmp_path / "project", pids=[5555], manifest_path=manifest)

    monkeypatch.setattr(clock_module, "DEFAULT_CLOCK", FrozenClock(instant=later_instant))
    _record_dashboard_candidate(port, tmp_path / "project", pids=[5555], manifest_path=manifest)

    [entry] = _load_dashboard_test_manifest(manifest)
    assert entry["started_at"] == 1_000_000.0
    assert entry["pids"] == [5555]


@pytest.mark.stress
@pytest.mark.non_sandbox
def test_concurrent_record_dashboard_candidate_updates_do_not_lose_entries(tmp_path: Path) -> None:
    """Concurrent manifest recorders must serialize their read-modify-write updates."""
    manifest = tmp_path / "manifest.json"
    ports = (61991, 61992)
    ready_paths = [tmp_path / f"ready-{port}" for port in ports]
    start_path = tmp_path / "start"
    worker = textwrap.dedent(
        """
        import importlib
        import sys
        import time
        from pathlib import Path

        manifest = Path(sys.argv[1])
        port = int(sys.argv[2])
        ready = Path(sys.argv[3])
        start = Path(sys.argv[4])
        module = importlib.import_module("tests.cross_cutting.dashboard.test_dashboard_cli_accuracy")
        original_load = module._load_dashboard_test_manifest

        def delayed_load(path):
            entries = original_load(path)
            time.sleep(0.1)
            return entries

        module._load_dashboard_test_manifest = delayed_load
        module._process_ids_for_port = lambda _port: []
        ready.write_text("", encoding="utf-8")
        deadline = time.monotonic() + 10
        while not start.exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("worker did not receive the start signal")
            time.sleep(0.01)
        module._record_dashboard_candidate(port, start.parent, pids=[port], manifest_path=manifest)
        """
    )
    commands = [[sys.executable, "-c", worker, str(manifest), str(port), str(ready), str(start_path)] for port, ready in zip(ports, ready_paths, strict=True)]
    processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for command in commands]

    try:
        deadline = time.monotonic() + 10
        while not all(path.exists() for path in ready_paths):
            if time.monotonic() >= deadline:
                raise TimeoutError("workers did not become ready")
            time.sleep(0.01)
        start_path.write_text("", encoding="utf-8")
        for process in processes:
            _, stderr = process.communicate(timeout=10)
            assert process.returncode == 0, stderr.decode(encoding="utf-8", errors="replace")
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            if process.poll() is None:
                process.wait(timeout=2)

    entries = _load_dashboard_test_manifest(manifest)
    assert _manifest_ints([entry["port"] for entry in entries]) == set(ports)


def test_stale_manifest_reaper_kills_only_old_recorded_dashboard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    fresh_port = 61001
    stale_port = 61002
    killed_ports = []
    now = clock_module.datetime.fromtimestamp(2_000.0, tz=clock_module.UTC)

    monkeypatch.setattr(clock_module, "DEFAULT_CLOCK", FrozenClock(instant=now))
    module = sys.modules[__name__]
    monkeypatch.setattr(module, "port_has_listener", lambda port: port in {fresh_port, stale_port})
    monkeypatch.setattr(module, "_process_ids_for_port", lambda port: [111] if port == fresh_port else [222])
    monkeypatch.setattr(module, "is_dashboard_accessible", lambda port, timeout=0.3: port in {fresh_port, stale_port})
    monkeypatch.setattr(module, "kill_dashboard_process", lambda port: killed_ports.append(port))
    _write_dashboard_test_manifest(
        [
            {
                "pids": [111],
                "port": fresh_port,
                "project_dir": str(tmp_path / "fresh"),
                "started_at": 1999.0,
            },
            {
                "pids": [222],
                "port": stale_port,
                "project_dir": str(tmp_path / "stale"),
                "started_at": 1000.0,
            },
        ],
        manifest,
    )

    killed = _cleanup_stale_dashboard_manifest_entries(max_age_seconds=60, manifest_path=manifest)

    assert killed == 1
    assert killed_ports == [stale_port]
    assert _load_dashboard_test_manifest(manifest) == [
        {
            "pids": [111],
            "port": fresh_port,
            "project_dir": str(tmp_path / "fresh"),
            "started_at": 1999.0,
        }
    ]


def test_dashboard_with_symlinked_kitty_specs():
    """Test dashboard works with symlinked kitty-specs directory (worktree structure).

    This tests the scenario from the bug report where kitty-specs is a symlink
    to a worktree directory, which was causing false error reporting.
    """
    with TemporaryDirectory() as tmpdir:
        test_project = Path(tmpdir) / "test_project"
        test_project.mkdir()

        # Create .kittify directory (required by dashboard)
        kittify_dir = test_project / ".kittify"
        kittify_dir.mkdir()

        # Initialize git repo (required by dashboard)
        subprocess.run(["git", "init"], cwd=test_project, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=test_project, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=test_project, check=True, capture_output=True)

        # Create a worktree structure
        worktrees_dir = test_project / ".worktrees"
        worktrees_dir.mkdir()

        # Create worktree with kitty-specs
        worktree_feature = worktrees_dir / "001-test-feature"
        worktree_feature.mkdir()
        worktree_kitty_specs = worktree_feature / "kitty-specs"
        worktree_kitty_specs.mkdir()
        feature_dir = worktree_kitty_specs / "001-test-feature"
        feature_dir.mkdir()

        # Create spec.md and plan.md
        (feature_dir / "spec.md").write_text("# Test Feature\n\nA test feature.")
        (feature_dir / "plan.md").write_text("# Implementation Plan\n\n## Overview\nTest plan.")

        # Create symlink to worktree kitty-specs (this is the key test scenario)
        kitty_specs = test_project / "kitty-specs"
        kitty_specs.symlink_to(worktree_kitty_specs, target_is_directory=True)

        # Verify symlink structure
        assert kitty_specs.is_symlink(), "kitty-specs should be a symlink"
        assert (kitty_specs / "001-test-feature" / "spec.md").exists(), "Should access spec.md through symlink"

        try:
            # Run dashboard command
            test_port = reserve_free_port()
            result = run_dashboard_cli(
                "dashboard",
                "--port",
                str(test_port),
                cwd=test_project,
                timeout=30,
            )

            # Dashboard should start successfully
            if wait_for_dashboard_state(test_port, accessible=True, timeout=3.0):
                assert result.returncode == 0, (
                    f"CLI should report success when dashboard accessible.\nExit code: {result.returncode}\nStdout: {result.stdout}\nStderr: {result.stderr}"
                )

                assert "✅" in result.stdout or "started" in result.stdout.lower(), (
                    f"CLI should show success message when dashboard running.\nStdout: {result.stdout}"
                )
            else:
                # If dashboard not accessible, error is acceptable
                assert result.returncode != 0, "CLI should report error when dashboard not accessible"

        finally:
            # Cleanup
            kill_dashboard_process(test_port)
