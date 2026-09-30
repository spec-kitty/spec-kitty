"""Dashboard lifecycle and health management utilities.

This module handles starting, stopping, and monitoring the dashboard server.
Uses psutil for cross-platform process management (Windows, Linux, macOS).
"""

from __future__ import annotations

import json
import logging
import secrets
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import psutil

from specify_cli.core.atomic import atomic_write
from specify_cli.core.process_liveness import is_process_alive as _canonical_is_process_alive

from .server import PortUnavailableError, find_free_port, start_dashboard

logger = logging.getLogger(__name__)

__all__ = [
    "ensure_dashboard_running",
    "stop_dashboard",
    "_parse_dashboard_file",
    "_write_dashboard_file",
    "_check_dashboard_health",
    "DashboardStatus",
    "get_dashboard_status",
]


@dataclass(frozen=True)
class DashboardStatus:
    """Observed state of the per-project dashboard daemon."""

    healthy: bool
    url: str | None = None
    port: int | None = None
    token: str | None = None
    pid: int | None = None


def _parse_dashboard_file(dashboard_file: Path) -> tuple[str | None, int | None, str | None, int | None]:
    """Read dashboard metadata from disk.

    Format:
        Line 1: URL (http://127.0.0.1:port)
        Line 2: Port (integer)
        Line 3: Token (optional)
        Line 4: PID (optional, for process tracking)
    """
    try:
        content = dashboard_file.read_text(encoding='utf-8')
    except Exception:
        return None, None, None, None

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return None, None, None, None

    url = lines[0] if lines else None
    port = None
    token = None
    pid = None

    if len(lines) >= 2:
        try:
            port = int(lines[1])
        except ValueError:
            port = None

    if len(lines) >= 3:
        token = lines[2] or None

    if len(lines) >= 4:
        try:
            pid = int(lines[3])
        except ValueError:
            pid = None

    return url, port, token, pid


def _write_dashboard_file(
    dashboard_file: Path,
    url: str,
    port: int,
    token: str | None,
    pid: int | None = None,
) -> None:
    """Persist dashboard metadata to disk.

    Args:
        dashboard_file: Path to .dashboard metadata file
        url: Dashboard URL (http://127.0.0.1:port)
        port: Port number
        token: Security token (optional)
        pid: Process ID of background dashboard (optional)
    """
    lines = [url, str(port)]
    if token:
        lines.append(token)
    if pid is not None:
        lines.append(str(pid))
    content = "\n".join(lines) + "\n"
    atomic_write(dashboard_file, content, mkdir=True)


def _is_process_alive(pid: int) -> bool:
    """Check if a process with the given PID is alive.

    Canonical implementation lives in ``specify_cli.core.process_liveness``
    (SC-7: one liveness probe across the CLI). This wrapper preserves the
    dashboard's existing import surface while delegating to the single source
    of truth.

    Args:
        pid: Process ID to check

    Returns:
        True if process exists and is running, False otherwise
    """
    return _canonical_is_process_alive(pid)


def _is_spec_kitty_dashboard(port: int, timeout: float = 0.3) -> bool:
    """Check if the process on the given port is a spec-kitty dashboard.

    Uses health check endpoint fingerprinting to safely identify spec-kitty dashboards.
    Only returns True if we can confirm it's a spec-kitty dashboard.

    Args:
        port: Port number to check
        timeout: Health check timeout in seconds

    Returns:
        True if confirmed to be a spec-kitty dashboard, False otherwise
    """
    health_url = f"http://127.0.0.1:{port}/api/health"
    data = _fetch_dashboard_json_payload(health_url, timeout=timeout)
    return bool(data and 'project_path' in data and 'status' in data)


def _fetch_dashboard_json_payload(url: str, timeout: float = 0.5) -> dict | None:
    """Fetch and decode a JSON payload from the loopback dashboard, or None.

    The raw localhost GET + JSON decode lives here so ``dashboard/`` owns its
    own probe (the sync daemon's copy is not borrowed any more). The
    dashboard-specific contract checks (``project_path``/``features``) live in
    the callers, not in this transport helper.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # nosec B310 — url is always http://127.0.0.1:<port>/...
            if response.status != 200:
                return None
            payload = response.read()
    except Exception:
        return None

    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    return data if isinstance(data, dict) else None


def _fetch_dashboard_features_payload(port: int, timeout: float = 0.5) -> dict | None:
    """Fetch dashboard bootstrap data and ensure it matches the UI contract."""
    url = f"http://127.0.0.1:{port}/api/features"
    data = _fetch_dashboard_json_payload(url, timeout=timeout)
    if data is None:
        return None

    features = data.get('features')
    if not isinstance(features, list):
        return None

    return data


def _check_dashboard_bootstrap(
    port: int,
    project_dir: Path,
    expected_token: str | None,
    timeout: float = 0.5,
) -> bool:
    """Verify that the dashboard can satisfy the browser bootstrap contract."""
    if not _check_dashboard_health(port, project_dir, expected_token, timeout=timeout):
        return False

    return _fetch_dashboard_features_payload(port, timeout=timeout) is not None


def _cleanup_orphaned_dashboards_in_range(start_port: int = 9237, port_count: int = 100) -> int:
    """Clean up orphaned spec-kitty dashboard processes in the port range.

    This function safely identifies spec-kitty dashboard processes via health check
    fingerprinting and kills only confirmed spec-kitty processes. This handles orphans
    that have no .dashboard file (e.g., from failed startups or deleted temp projects).

    Args:
        start_port: Starting port number (default: 9237)
        port_count: Number of ports to check (default: 100)

    Returns:
        Number of orphaned processes killed
    """
    import subprocess

    killed_count = 0

    for port in range(start_port, start_port + port_count):
        # Check if port is occupied
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.1)
                if sock.connect_ex(('127.0.0.1', port)) != 0:
                    # Port is free, skip
                    continue
        except Exception:
            continue

        # Port is occupied - check if it's a spec-kitty dashboard
        if _is_spec_kitty_dashboard(port):
            # It's a spec-kitty dashboard - try to find and kill the process
            try:
                # Use lsof to find PID listening on this port
                result = subprocess.run(
                    ['lsof', '-ti', f':{port}', '-sTCP:LISTEN'],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=2,
                )
                if result.returncode == 0 and result.stdout.strip():
                    pids = [int(pid) for pid in result.stdout.strip().split('\n') if pid.strip()]
                    for pid in pids:
                        try:
                            proc = psutil.Process(pid)
                            proc.kill()
                            killed_count += 1
                        except psutil.NoSuchProcess:
                            pass  # Already dead
                        except psutil.AccessDenied:
                            pass  # Can't kill (permissions)
            except Exception:
                # Can't use lsof or failed to kill - skip this port
                pass

    return killed_count


def _check_dashboard_health(
    port: int,
    project_dir: Path,
    expected_token: str | None,
    timeout: float = 0.5,
) -> bool:
    """Verify that the dashboard on the port belongs to the provided project."""
    health_url = f"http://127.0.0.1:{port}/api/health"
    data = _fetch_dashboard_json_payload(health_url, timeout=timeout)
    if data is None:
        return False

    remote_path = data.get('project_path')
    if not remote_path:
        return False

    try:
        remote_resolved = str(Path(remote_path).resolve())
    except Exception:
        remote_resolved = str(remote_path)

    try:
        expected_path = str(project_dir.resolve())
    except Exception:
        expected_path = str(project_dir)

    if remote_resolved != expected_path:
        return False

    remote_token = data.get('token')
    if expected_token:
        return remote_token == expected_token

    return True


def get_dashboard_status(project_dir: Path, timeout: float = 0.5) -> DashboardStatus:
    """Return dashboard daemon health for a project."""
    project_dir_resolved = project_dir.resolve()
    dashboard_file = project_dir_resolved / '.kittify' / '.dashboard'
    if not dashboard_file.exists():
        return DashboardStatus(healthy=False)

    url, port, token, pid = _parse_dashboard_file(dashboard_file)
    if port is None:
        return DashboardStatus(healthy=False, url=url, token=token, pid=pid)

    health_url = f"http://127.0.0.1:{port}/api/health"
    data = _fetch_dashboard_json_payload(health_url, timeout=timeout)
    if data is None:
        return DashboardStatus(
            healthy=False,
            url=url or f"http://127.0.0.1:{port}",
            port=port,
            token=token,
            pid=pid,
        )

    remote_path = data.get('project_path')
    remote_token = data.get('token')
    try:
        remote_resolved = str(Path(str(remote_path)).resolve())
    except Exception:
        remote_resolved = str(remote_path)

    healthy = remote_resolved == str(project_dir_resolved)
    if healthy and token:
        healthy = remote_token == token

    return DashboardStatus(
        healthy=healthy,
        url=url or f"http://127.0.0.1:{port}",
        port=port,
        token=token,
        pid=pid,
    )


def ensure_dashboard_running(
    project_dir: Path,
    preferred_port: int | None = None,
    background_process: bool = True,
) -> tuple[str, int, bool]:
    """
    Ensure a dashboard server is running for the provided project directory.

    This function:
    1. Checks if a dashboard is already running (health check)
    2. Cleans up this project's orphaned process if stored PID is dead
    3. If starting new dashboard fails due to port exhaustion, cleans up orphaned
       spec-kitty dashboards across the entire port range and retries
    4. Starts a new dashboard if needed
    5. Stores the PID for future cleanup

    Returns:
        Tuple of (url, port, started) where started is True when a new server was launched.
    """
    project_dir_resolved = project_dir.resolve()
    dashboard_file = project_dir_resolved / '.kittify' / '.dashboard'

    existing_url = None
    existing_port = None
    existing_token = None
    existing_pid = None

    # STEP 1: Check if we have a stale .dashboard file from a dead process
    if dashboard_file.exists():
        existing_url, existing_port, existing_token, existing_pid = _parse_dashboard_file(dashboard_file)

        # Only reuse a running daemon when the UI bootstrap endpoint is valid.
        if existing_port is not None and _check_dashboard_bootstrap(
            existing_port, project_dir_resolved, existing_token
        ):
            url = existing_url or f"http://127.0.0.1:{existing_port}"
            return url, existing_port, False

        # Dashboard not responding - clean up orphaned process if we have a PID
        if existing_pid is not None and not _is_process_alive(existing_pid):
            # Process is dead, clean up the metadata file
            dashboard_file.unlink(missing_ok=True)
        elif existing_pid is not None and existing_port is not None:
            # PID is alive but port not responding - kill the orphan
            try:
                proc = psutil.Process(existing_pid)
                proc.kill()
                dashboard_file.unlink(missing_ok=True)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Already dead or can't kill - just clean up metadata
                dashboard_file.unlink(missing_ok=True)
        else:
            # No PID recorded - just clean up metadata file
            dashboard_file.unlink(missing_ok=True)

    # STEP 2: Try to start a new dashboard
    if preferred_port is not None:
        try:
            port_to_use = find_free_port(preferred_port, max_attempts=1)
        except RuntimeError:
            port_to_use = None
    else:
        port_to_use = None

    token = secrets.token_hex(16)

    # Try starting dashboard - if it fails due to port exhaustion, cleanup and retry
    try:
        port, pid = start_dashboard(
            project_dir_resolved,
            port=port_to_use,
            background_process=background_process,
            project_token=token,
        )
    except PortUnavailableError:
        # Port exhaustion (typed via error_code, not message text): try cleaning
        # up orphaned dashboards and retry once.
        killed = _cleanup_orphaned_dashboards_in_range()
        if killed > 0:
            # Cleanup succeeded, retry starting dashboard
            port, pid = start_dashboard(
                project_dir_resolved,
                port=port_to_use,
                background_process=background_process,
                project_token=token,
            )
        else:
            # No orphans found or couldn't clean up - re-raise original error
            raise

    url = f"http://127.0.0.1:{port}"

    # Wait for dashboard to become healthy (20 seconds with exponential backoff)
    # Start with quick checks, then slow down for slower systems
    retry_delays = [0.1] * 10 + [0.25] * 40 + [0.5] * 20  # ~20 seconds total
    for delay in retry_delays:
        if _check_dashboard_health(port, project_dir_resolved, token):
            _write_dashboard_file(dashboard_file, url, port, token, pid)
            return url, port, True
        time.sleep(delay)

    # Dashboard started but never became healthy
    # Bug #117 Fix: Check if process is actually running BEFORE declaring failure
    # Health check may timeout on slow systems, but dashboard is actually accessible
    if pid is not None and _is_process_alive(pid):
        # Process is alive, health check just timing out (slow system or busy dashboard)
        # This is a success case - dashboard is running, even if health check is slow
        _write_dashboard_file(dashboard_file, url, port, token, pid)
        return url, port, True

    # Health check failed AND process is not alive - check for orphaned dashboard
    if _is_spec_kitty_dashboard(port):
        # Port has a spec-kitty dashboard but for wrong project - orphan detected
        # Clean up the failed process we just started
        if pid is not None:
            try:
                proc = psutil.Process(pid)
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Cleanup orphaned dashboards and retry ONCE
        killed = _cleanup_orphaned_dashboards_in_range()
        if killed > 0:
            # Retry starting dashboard after cleanup
            token = secrets.token_hex(16)
            port, pid = start_dashboard(
                project_dir_resolved,
                port=port_to_use,
                background_process=background_process,
                project_token=token,
            )
            url = f"http://127.0.0.1:{port}"

            # Wait for health check again
            for delay in retry_delays:
                if _check_dashboard_health(port, project_dir_resolved, token):
                    _write_dashboard_file(dashboard_file, url, port, token, pid)
                    return url, port, True
                time.sleep(delay)

            # Retry also failed - check if process is alive after retry
            if pid is not None and _is_process_alive(pid):
                _write_dashboard_file(dashboard_file, url, port, token, pid)
                return url, port, True

    # Process is actually dead - clean up and raise error
    if pid is not None:
        try:
            proc = psutil.Process(pid)
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    raise RuntimeError(f"Dashboard failed to start on port {port} for project {project_dir_resolved}")


def stop_dashboard(project_dir: Path, timeout: float = 5.0) -> tuple[bool, str]:
    """
    Attempt to stop the dashboard server for the provided project directory.

    Tries graceful HTTP shutdown first, then falls back to killing by PID if needed.

    Returns:
        Tuple[bool, str]: (stopped, message)
    """
    project_dir_resolved = project_dir.resolve()
    dashboard_file = project_dir_resolved / '.kittify' / '.dashboard'

    if not dashboard_file.exists():
        return False, "No dashboard metadata found."

    _, port, token, pid = _parse_dashboard_file(dashboard_file)
    if port is None:
        dashboard_file.unlink(missing_ok=True)
        return False, "Dashboard metadata was invalid and has been cleared."

    if not _check_dashboard_health(port, project_dir_resolved, token):
        dashboard_file.unlink(missing_ok=True)
        return False, "Dashboard was already stopped. Metadata has been cleared."

    shutdown_url = f"http://127.0.0.1:{port}/api/shutdown"

    def _attempt_get() -> tuple[bool, str | None]:
        params = {}
        if token:
            params['token'] = token
        query = urllib.parse.urlencode(params)
        request_url = f"{shutdown_url}?{query}" if query else shutdown_url
        try:
            urllib.request.urlopen(request_url, timeout=1)  # nosec B310 — URL is localhost dashboard shutdown endpoint
            return True, None
        except urllib.error.HTTPError as exc:
            if exc.code == 403:
                return False, "Dashboard refused shutdown (token mismatch)."
            if exc.code in (404, 405, 501):
                return False, None
            return False, f"Dashboard shutdown failed with HTTP {exc.code}."
        except OSError as exc:
            return False, f"Dashboard shutdown request failed: {exc}"
        except Exception as exc:
            return False, f"Unexpected error during shutdown: {exc}"

    def _attempt_post() -> tuple[bool, str | None]:
        payload = json.dumps({'token': token}).encode('utf-8')
        request = urllib.request.Request(
            shutdown_url,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            urllib.request.urlopen(request, timeout=1)  # nosec B310 — URL is localhost dashboard control endpoint
            return True, None
        except urllib.error.HTTPError as exc:
            if exc.code == 403:
                return False, "Dashboard refused shutdown (token mismatch)."
            if exc.code == 501:
                return False, "Dashboard does not support remote shutdown (upgrade required)."
            return False, f"Dashboard shutdown failed with HTTP {exc.code}."
        except OSError as exc:
            return False, f"Dashboard shutdown request failed: {exc}"
        except Exception as exc:
            return False, f"Unexpected error during shutdown: {exc}"

    # Try graceful HTTP shutdown first
    ok, error_message = _attempt_get()
    if not ok and error_message is None:
        ok, error_message = _attempt_post()

    if not ok and pid is not None:
        return _terminate_by_pid(pid, dashboard_file)

    if not ok:
        return False, error_message or "Dashboard shutdown failed."

    return _wait_for_shutdown(port, project_dir_resolved, token, pid, dashboard_file, timeout)


def _terminate_by_pid(pid: int, dashboard_file: Path) -> tuple[bool, str]:
    """Attempt graceful SIGTERM then SIGKILL for a known PID."""
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        try:
            proc.wait(timeout=3.0)
            dashboard_file.unlink(missing_ok=True)
            return True, f"Dashboard stopped via process termination (PID {pid})."
        except psutil.TimeoutExpired:
            proc.kill()
            time.sleep(0.2)
            dashboard_file.unlink(missing_ok=True)
            return True, f"Dashboard force killed after graceful termination timeout (PID {pid})."
    except psutil.NoSuchProcess:
        dashboard_file.unlink(missing_ok=True)
        return True, f"Dashboard was already dead (PID {pid})."
    except psutil.AccessDenied:
        return False, f"Permission denied to kill dashboard process (PID {pid})."
    except Exception as e:
        logger.error(f"Unexpected error stopping dashboard process {pid}: {e}")
        return False, f"Failed to kill dashboard process (PID {pid}): {e}"


def _wait_for_shutdown(
    port: int,
    project_dir: Path,
    token: str | None,
    pid: int | None,
    dashboard_file: Path,
    timeout: float,
) -> tuple[bool, str]:
    """Poll until the dashboard stops responding, then clean up or force-kill."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _check_dashboard_health(port, project_dir, token):
            dashboard_file.unlink(missing_ok=True)
            return True, f"Dashboard stopped and metadata cleared (port {port})."
        time.sleep(0.1)

    if pid is not None:
        try:
            psutil.Process(pid).kill()
            dashboard_file.unlink(missing_ok=True)
            return True, f"Dashboard forced stopped (force kill, PID {pid}) after {timeout}s timeout."
        except psutil.NoSuchProcess:
            dashboard_file.unlink(missing_ok=True)
            return True, f"Dashboard process ended (PID {pid})."
        except Exception as e:
            logger.error(f"Failed to force kill dashboard process {pid}: {e}")

    return False, f"Dashboard did not stop within {timeout} seconds."
