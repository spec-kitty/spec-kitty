"""``spec-kitty service fetch | vendor | status | stop`` (#6590, contracts/cli-surface.md).

Typer ``CliRunner`` over the command group; no service is spawned (``ServiceLauncher`` and
the instance probe are replaced where a command would reach a running service). Releases
are ``file://`` fixtures, so nothing touches the network.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from kernel.service_pin import ServicePin, ServiceTarget, write_service_pin
from specify_cli.cli.commands import service as service_module
from specify_cli.services import resolution
from specify_cli.services.client import ServiceUnreachable
from specify_cli.services.launcher import ServiceLauncher, StopOutcome
from specify_cli.services.policies import WRITE_SERVICE
from specify_cli.status.write_service_protocol import (
    EndpointFileError,
    EndpointRefusalCode,
    Handshake,
    WriteServiceEndpoint,
    endpoint_file_path,
    read_endpoint_file,
    repository_id,
)
from tests.kernel.service_release_fixture import FIXTURE_COMMIT, SUMS_FILE, build_release, pin_path

pytestmark = pytest.mark.fast

TAG = "service-v0.1.0"
FAKE_SERVICE = Path(__file__).with_name("fake_service.py")
TOKEN = "t" * 43
#: The only executables the status test lets through: the read-only git probe, exactly `git` (POSIX) or `git.exe` (Windows).
_GIT_EXECUTABLES = frozenset({"git", "git.exe"})
runner = CliRunner()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(service_module, "_repo_root", lambda: root)
    # The CLI's own source checkout: its pins/ is the one the commands read and vendor writes.
    monkeypatch.setattr(resolution, "source_checkout_root", lambda: root)
    monkeypatch.chdir(root)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.delenv("SPEC_KITTY_SERVICE_ASSET_DIR", raising=False)
    monkeypatch.setattr(service_module, "host_target", lambda: ServiceTarget.LINUX_X64)
    monkeypatch.setattr(service_module, "get_version", lambda: "4.0.0rc9")
    return root


@pytest.fixture
def release(tmp_path: Path) -> tuple[ServicePin, Path]:
    return build_release(tmp_path / "releases", tag=TAG)


def _pin(repo: Path, pin: ServicePin) -> Path:
    path = pin_path(repo, pin.service)
    path.parent.mkdir(exist_ok=True)
    write_service_pin(pin, path)
    return path


def _invoke(*args: str) -> Any:
    return runner.invoke(service_module.app, list(args))


def test_help_lists_the_four_subcommands() -> None:
    result = _invoke("--help")
    assert result.exit_code == 0
    for name in ("fetch", "vendor", "status", "stop"):
        assert name in result.output


def test_the_group_is_registered_on_the_root_cli() -> None:
    from specify_cli.cli.commands import _COMMAND_REGISTRARS

    assert _COMMAND_REGISTRARS["service"].__name__ == "_register_service"


def test_an_unknown_service_is_a_usage_error(repo: Path) -> None:
    for command in ("fetch", "status", "stop", "vendor"):
        assert _invoke(command, "--service", "mystery").exit_code == 2


# -- no pins ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("command", ["fetch", "status"])
def test_no_pin_prints_the_message_and_exits_0(repo: Path, monkeypatch: pytest.MonkeyPatch, command: str) -> None:
    monkeypatch.setattr(service_module, "find_pin", lambda service: None)
    result = _invoke(command)
    assert result.exit_code == 0
    assert service_module.NO_PIN_MESSAGE in result.output
    as_json = json.loads(_invoke(command, "--json").stdout)
    assert as_json == {"services": [], "message": service_module.NO_PIN_MESSAGE}


def test_fetch_all_with_no_pin_is_quiet(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service_module, "find_pin", lambda service: None)
    result = _invoke("fetch", "--all")
    assert result.exit_code == 0
    assert service_module.NO_PIN_MESSAGE in result.output


# -- fetch -------------------------------------------------------------------------------------------


def test_fetch_verifies_the_host_build_into_the_cache(repo: Path, release: tuple[ServicePin, Path], tmp_path: Path) -> None:
    pin, _ = release
    _pin(repo, pin)
    asset = pin.assets[ServiceTarget.LINUX_X64]

    result = _invoke("fetch")

    assert result.exit_code == 0, result.output
    cached = tmp_path / "cache" / "spec-kitty" / "services" / "write-service" / TAG / asset.name
    assert cached.is_file()
    assert str(cached) in result.output
    assert asset.sha256[:12] in result.output


def test_fetch_json_shape(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    _pin(repo, pin)

    payload = json.loads(_invoke("fetch", "--json").stdout)

    (entry,) = payload["services"]
    assert entry["service"] == "write-service"
    assert entry["tag"] == TAG
    assert entry["commit"] == FIXTURE_COMMIT
    (asset,) = entry["assets"]
    assert {"target", "name", "state"} <= set(asset)
    assert asset["target"] == "linux-x64"
    assert asset["state"] == "verified"


def test_fetch_falls_back_to_the_jar_on_a_host_without_a_build(repo: Path, release: tuple[ServicePin, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    pin, _ = release
    _pin(repo, pin)
    monkeypatch.setattr(service_module, "host_target", lambda: ServiceTarget.MACOS_ARM64)

    payload = json.loads(_invoke("fetch", "--json").stdout)

    assert payload["services"][0]["assets"][0]["target"] == "jvm"


def test_fetch_refuses_a_host_with_no_build_and_no_jar(repo: Path, tmp_path: Path) -> None:
    pin, _ = build_release(tmp_path / "releases", tag=TAG, assets={ServiceTarget.LINUX_ARM64: b"arm"})
    _pin(repo, pin)

    result = _invoke("fetch")

    assert result.exit_code == 1
    assert "SERVICE_UNSUPPORTED_PLATFORM" in result.output
    assert "linux-arm64" in result.output


def test_a_fetch_refusal_prints_the_code_and_the_remedy(repo: Path, tmp_path: Path) -> None:
    pin, _ = build_release(tmp_path / "releases", tag=TAG, corrupt={"linux-x64"})
    _pin(repo, pin)

    result = _invoke("fetch")

    assert result.exit_code == 1
    assert "SERVICE_BINARY_DIGEST_MISMATCH" in result.output
    assert "Remedy:" in result.output
    assert pin.assets[ServiceTarget.LINUX_X64].sha256 not in result.output

    envelope = json.loads(_invoke("fetch", "--json").stdout)
    assert envelope["error"]["error_code"] == "SERVICE_BINARY_DIGEST_MISMATCH"
    assert envelope["error"]["remedy"]


def test_fetch_offline_without_a_cached_copy_refuses(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    _pin(repo, pin)

    result = _invoke("fetch", "--offline")

    assert result.exit_code == 1
    assert "SERVICE_BINARY_MISSING" in result.output


def test_fetch_refuses_an_invalid_pin(repo: Path) -> None:
    path = pin_path(repo, "write-service")
    path.parent.mkdir()
    path.write_text("service: write-service\n", encoding="utf-8")

    result = _invoke("fetch")

    assert result.exit_code == 1
    assert "SERVICE_PIN_INVALID" in result.output


# -- status ------------------------------------------------------------------------------------------


@pytest.fixture
def absent_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service_module, "instance_state", lambda service, repo_root: service_module.InstanceState("absent"))


def _assets(payload: dict[str, Any]) -> dict[str, str]:
    return {asset["target"]: asset["state"] for asset in payload["services"][0]["assets"]}


def test_status_reports_the_cache_state_per_asset(repo: Path, release: tuple[ServicePin, Path], tmp_path: Path, absent_instance: None) -> None:
    pin, _ = release
    _pin(repo, pin)

    assert _assets(json.loads(_invoke("status", "--json").stdout)) == {"jvm": "missing", "linux-x64": "missing"}
    assert _invoke("fetch").exit_code == 0
    assert _assets(json.loads(_invoke("status", "--json").stdout)) == {"jvm": "missing", "linux-x64": "verified"}
    cached = tmp_path / "cache" / "spec-kitty" / "services" / "write-service" / TAG / pin.assets[ServiceTarget.LINUX_X64].name
    cached.write_bytes(b"tampered")
    assert _assets(json.loads(_invoke("status", "--json").stdout))["linux-x64"] == "corrupt"


def test_status_json_shape_and_human_output(repo: Path, release: tuple[ServicePin, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    pin, _ = release
    _pin(repo, pin)
    monkeypatch.setattr(service_module, "instance_state", lambda service, repo_root: service_module.InstanceState("healthy", "01INSTANCE", 4711))

    result = _invoke("status", "--json")

    assert result.exit_code == 0
    (entry,) = json.loads(result.stdout)["services"]
    assert set(entry) == {"service", "tag", "commit", "assets", "instance"}
    assert entry["instance"] == {"state": "healthy", "instance_id": "01INSTANCE", "port": 4711}
    human = _invoke("status")
    assert human.exit_code == 0
    assert TAG in human.output
    assert FIXTURE_COMMIT[:12] in human.output
    assert "instance: healthy (instance 01INSTANCE, port 4711)" in human.output


def test_status_reports_an_invalid_pin_and_still_exits_0(repo: Path, absent_instance: None) -> None:
    path = pin_path(repo, "write-service")
    path.parent.mkdir()
    path.write_text("nonsense: true\n", encoding="utf-8")

    result = _invoke("status")

    assert result.exit_code == 0
    assert "SERVICE_PIN_INVALID" in result.output


@pytest.mark.integration
def test_status_json_against_a_real_published_endpoint_starts_nothing_and_never_shows_the_token(
    release: tuple[ServicePin, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real (fake) service publishes its endpoint; status reports it healthy with spawning patched to fail."""
    repo = _git_repo(tmp_path / "clone")
    git_common = (repo / ".git").resolve()
    pin, _ = release
    _pin(repo, pin)
    monkeypatch.setattr(service_module, "_repo_root", lambda: repo)
    monkeypatch.setattr(resolution, "source_checkout_root", lambda: repo)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    argv = [sys.executable, str(FAKE_SERVICE), *WRITE_SERVICE.start_args(git_common), "--idle-timeout", "60"]
    process = subprocess.Popen(
        argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={**os.environ, "FAKE_SERVICE_MODE": "healthy"}
    )
    try:
        published = endpoint_file_path(git_common)
        deadline = time.monotonic() + 10
        while not published.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        endpoint = read_endpoint_file(published)

        real_popen = subprocess.Popen
        spawned: list[object] = []

        def git_only_popen(args: Any, *rest: Any, **kwargs: Any) -> Any:
            """Let the read-only git probe (rev-parse --git-common-dir) run; any other process fails the test."""
            if isinstance(args, (list, tuple)) and args and Path(str(args[0])).name in _GIT_EXECUTABLES:
                return real_popen(args, *rest, **kwargs)
            spawned.append(args)
            raise AssertionError(f"status must not spawn {args!r}")

        def refuse_ensure(*args: object, **kwargs: object) -> None:
            raise AssertionError("status must not start a service")

        monkeypatch.setattr(subprocess, "Popen", git_only_popen)
        monkeypatch.setattr(ServiceLauncher, "ensure", refuse_ensure)

        result = runner.invoke(service_module.app, ["status", "--json"])

        assert result.exit_code == 0, result.output
        (entry,) = json.loads(result.stdout)["services"]
        assert entry["instance"] == {"state": "healthy", "instance_id": endpoint.instance_id, "port": endpoint.port}
        assert endpoint.token not in result.stdout
        assert endpoint.token not in result.stderr
        assert spawned == []
    finally:
        process.terminate()
        process.wait(timeout=10)


# -- instance_state (the read-only probe status uses) -----------------------------------------------


def _git_repo(path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def _endpoint() -> WriteServiceEndpoint:
    return WriteServiceEndpoint("127.0.0.1", 4711, TOKEN, "01INSTANCE", 4242, (1,), "2026-10-30T00:00:00Z")


def test_instance_state_of_a_service_the_cli_never_launches_is_absent(tmp_path: Path) -> None:
    assert service_module.instance_state("read-service", tmp_path).state == "absent"


def test_instance_state_outside_a_repository_or_without_an_endpoint_is_absent(tmp_path: Path) -> None:
    outside = tmp_path / "plain"
    outside.mkdir()
    assert service_module.instance_state("write-service", outside).state == "absent"
    assert service_module.instance_state("write-service", _git_repo(tmp_path / "repo")).state == "absent"


def test_instance_state_of_an_untrusted_endpoint_file_is_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def exposed(path: Path) -> WriteServiceEndpoint:
        raise EndpointFileError(EndpointRefusalCode.EXPOSED, "readable by others")

    monkeypatch.setattr(service_module, "read_endpoint_file", exposed)
    assert service_module.instance_state("write-service", _git_repo(tmp_path / "repo")).state == "stale"


class _Client:
    answer: Handshake | None = None

    def __init__(self, endpoint: WriteServiceEndpoint) -> None:
        self.endpoint = endpoint

    def handshake(self) -> Handshake:
        if self.answer is None:
            raise ServiceUnreachable("handshake: connection refused")
        return self.answer


@pytest.mark.parametrize(("instance_id", "same_clone", "expected"), [("01INSTANCE", True, "healthy"), ("01OTHER", True, "stale"), ("01INSTANCE", False, "stale")])
def test_instance_state_asks_one_handshake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, instance_id: str, same_clone: bool, expected: str) -> None:
    repo = _git_repo(tmp_path / "repo")
    clone_id = repository_id((repo / ".git").resolve()) if same_clone else "0" * 64
    monkeypatch.setattr(service_module, "read_endpoint_file", lambda path: _endpoint())
    monkeypatch.setattr(_Client, "answer", Handshake((1,), "0.1.0", instance_id, clone_id))
    monkeypatch.setattr(service_module, "ServiceClient", _Client)

    state = service_module.instance_state("write-service", repo)

    assert state == service_module.InstanceState(expected, "01INSTANCE", 4711)
    assert TOKEN not in json.dumps(state.to_dict())


def test_instance_state_with_nothing_answering_is_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service_module, "read_endpoint_file", lambda path: _endpoint())
    monkeypatch.setattr(_Client, "answer", None)
    monkeypatch.setattr(service_module, "ServiceClient", _Client)
    assert service_module.instance_state("write-service", _git_repo(tmp_path / "repo")).state == "stale"


# -- stop --------------------------------------------------------------------------------------------


class _Launcher:
    outcome: StopOutcome = StopOutcome.STOPPED
    error: Exception | None = None
    calls: list[tuple[str, Path]] = []

    def __init__(self, *, warn: Any) -> None:
        self.warn = warn

    def stop(self, service: str, repo_root: Path) -> StopOutcome:
        self.calls.append((service, repo_root))
        if self.error is not None:
            raise self.error
        if self.outcome is StopOutcome.UNCONFIRMED:
            self.warn(f"the {service} process 4242 is still alive (its log is /x/spec-kitty-write-service/service.log)")
        return self.outcome


@pytest.fixture
def launcher(monkeypatch: pytest.MonkeyPatch) -> type[_Launcher]:
    monkeypatch.setattr(service_module, "ServiceLauncher", _Launcher)
    monkeypatch.setattr(_Launcher, "calls", [])
    monkeypatch.setattr(_Launcher, "error", None)
    return _Launcher


@pytest.mark.parametrize(("outcome", "word"), [(StopOutcome.STOPPED, "stopped"), (StopOutcome.NOT_RUNNING, "not running"), (StopOutcome.FORCED, "forced")])
def test_stop_prints_the_outcome_and_exits_0(repo: Path, launcher: type[_Launcher], monkeypatch: pytest.MonkeyPatch, outcome: StopOutcome, word: str) -> None:
    monkeypatch.setattr(launcher, "outcome", outcome)
    result = _invoke("stop")
    assert result.exit_code == 0
    assert result.stdout.strip() == word
    assert launcher.calls == [("write-service", repo)]


def test_an_unconfirmed_stop_exits_1_naming_the_pid_and_the_log(repo: Path, launcher: type[_Launcher], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(launcher, "outcome", StopOutcome.UNCONFIRMED)
    result = _invoke("stop")
    assert result.exit_code == 1
    assert "unconfirmed" in result.output
    assert "4242" in result.output
    assert "service.log" in result.output


def test_stop_of_a_service_the_cli_never_launches_exits_0(repo: Path, launcher: type[_Launcher]) -> None:
    result = _invoke("stop", "--service", "read-service")
    assert result.exit_code == 0
    assert "not running" in result.output
    assert launcher.calls == []


def test_stop_refuses_an_untrusted_endpoint(repo: Path, launcher: type[_Launcher], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(launcher, "error", EndpointFileError(EndpointRefusalCode.EXPOSED, "the endpoint file is readable by others"))
    result = _invoke("stop")
    assert result.exit_code == 1
    assert EndpointRefusalCode.EXPOSED.value in result.output


def test_stop_outside_a_repository_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outside = tmp_path / "plain"
    outside.mkdir()
    monkeypatch.setattr(service_module, "_repo_root", lambda: outside)
    result = _invoke("stop")
    assert result.exit_code == 1
    assert "cannot stop write-service" in result.output
    assert f"{outside} is not inside a git repository" in result.output
    assert "PosixPath(" not in result.output and "WindowsPath(" not in result.output


def test_stop_with_nothing_running_in_a_real_repository_is_not_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _git_repo(tmp_path / "repo")
    monkeypatch.setattr(service_module, "_repo_root", lambda: repo)
    result = _invoke("stop")
    assert result.exit_code == 0
    assert result.stdout.strip() == "not running"


# -- vendor ------------------------------------------------------------------------------------------


def _vendor_args(pin: ServicePin, *extra: str) -> list[str]:
    return ["vendor", "--tag", TAG, "--repository", pin.repository, "--commit", FIXTURE_COMMIT, *extra]


def test_vendor_writes_the_lockfile_and_check_passes(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, release_dir = release
    (release_dir / "NOTES.txt").write_bytes(b"n")
    with (release_dir / SUMS_FILE).open("a", encoding="utf-8") as sums:
        sums.write(f"{'a' * 64}  NOTES.txt\n")

    result = _invoke(*_vendor_args(pin))

    assert result.exit_code == 0, result.output
    assert pin_path(repo, "write-service").is_file()
    assert TAG in result.output
    assert "NOTES.txt" in result.output
    assert _invoke("vendor", "--check").exit_code == 0
    assert _invoke("vendor", "--check", "--offline").exit_code == 0


def test_vendor_check_fails_on_a_tampered_lockfile(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    assert _invoke(*_vendor_args(pin)).exit_code == 0
    path = pin_path(repo, "write-service")
    path.write_text(path.read_text(encoding="utf-8").replace(pin.assets[ServiceTarget.JVM].sha256, "f" * 64), encoding="utf-8")

    assert _invoke("vendor", "--check", "--offline").exit_code == 0  # shape only
    result = _invoke("vendor", "--check")
    assert result.exit_code == 1
    assert pin.assets[ServiceTarget.JVM].name in result.output


def test_a_vendor_refusal_exits_1_and_leaves_the_lockfile(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, release_dir = release
    path = _pin(repo, pin)
    before = path.read_bytes()
    (release_dir / pin.assets[ServiceTarget.LINUX_X64].name).write_bytes(b"tampered")

    result = _invoke(*_vendor_args(pin))

    assert result.exit_code == 1
    assert "SERVICE_VENDOR_DIGEST_MISMATCH" in result.output
    assert path.read_bytes() == before


def test_vendor_with_credentials_in_the_repository_is_a_usage_error(repo: Path) -> None:
    result = _invoke("vendor", "--tag", TAG, "--repository", "https://bob:hunter2pass@github.com/x/y")
    assert result.exit_code == 2
    assert "hunter2pass" not in result.output
    assert "repository" in result.output


@pytest.mark.parametrize(
    "args",
    [
        ["vendor"],
        ["vendor", "--check", "--tag", TAG],
        ["vendor", "--check", "--commit", FIXTURE_COMMIT],
        ["vendor", "--offline", "--tag", TAG],
        ["vendor", "--tag", TAG, "--protocol-versions", "one"],
        ["vendor", "--tag", TAG, "--protocol-versions", "0"],
    ],
)
def test_vendor_usage_errors_exit_2(repo: Path, args: list[str]) -> None:
    assert _invoke(*args).exit_code == 2


def test_vendor_records_the_protocol_versions(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    assert _invoke(*_vendor_args(pin, "--protocol-versions", "1,2")).exit_code == 0
    assert "protocol_versions:\n- 1\n- 2" in pin_path(repo, "write-service").read_text(encoding="utf-8").replace("  -", "-")


def test_vendor_from_a_file_repository_without_a_commit_is_a_usage_error(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    result = _invoke("vendor", "--tag", TAG, "--repository", pin.repository)
    assert result.exit_code == 2
    assert "SERVICE_VENDOR_COMMIT_REQUIRED" in result.output
    assert not pin_path(repo, "write-service").exists()


def test_vendor_with_a_malformed_tag_is_a_usage_error(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    result = _invoke("vendor", "--tag", "service-v1", "--repository", pin.repository, "--commit", FIXTURE_COMMIT)
    assert result.exit_code == 2
    assert "SERVICE_VENDOR_USAGE" in result.output


def test_vendor_asset_prefix_override(repo: Path, tmp_path: Path) -> None:
    pin, _ = build_release(tmp_path / "custom", tag=TAG, prefix="write-svc")
    assert _invoke(*_vendor_args(pin)).exit_code == 1  # no command-cli build in that release
    result = _invoke(*_vendor_args(pin, "--asset-prefix", "write-svc"))
    assert result.exit_code == 0, result.output
    assert "write-svc-0.1.0-linux-x64" in pin_path(repo, "write-service").read_text(encoding="utf-8")
    assert _invoke("vendor", "--check", "--asset-prefix", "write-svc").exit_code == 2


def test_vendor_help_documents_the_file_commit_rule() -> None:
    result = _invoke("vendor", "--help")
    assert result.exit_code == 0
    assert "file://" in result.output


def test_vendor_refuses_when_the_cli_is_not_a_source_checkout(repo: Path, release: tuple[ServicePin, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """An installed wheel has no source pins/ to rewrite: usage error, nothing written anywhere."""
    pin, _ = release
    monkeypatch.setattr(resolution, "source_checkout_root", lambda: None)
    result = _invoke(*_vendor_args(pin))
    assert result.exit_code == 2
    assert "source checkout" in result.output
    assert "Remedy:" in result.output
    assert not (repo / "pins").exists()


def test_vendor_refuses_outside_the_cli_s_source_checkout(repo: Path, release: tuple[ServicePin, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run from another project, vendor never writes that project's pins/ nor, silently, the CLI's."""
    pin, _ = release
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    monkeypatch.chdir(consumer)
    monkeypatch.setattr(service_module, "_repo_root", lambda: consumer)
    result = _invoke(*_vendor_args(pin))
    assert result.exit_code == 2
    assert str(repo) in result.output
    assert not (consumer / "pins").exists()
    assert not (repo / "pins").exists()


def test_fetch_ignores_a_pin_in_the_user_project(repo: Path, release: tuple[ServicePin, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI's own tree has no pin; a pins/ planted in the user's project is not read."""
    pin, _ = release
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    _pin(consumer, pin)
    monkeypatch.chdir(consumer)
    monkeypatch.setattr(service_module, "_repo_root", lambda: consumer)
    result = _invoke("fetch")
    assert result.exit_code == 0
    assert service_module.NO_PIN_MESSAGE in result.output


# -- F9: fetch uses resolution's refusals ----------------------------------------------------------


def test_fetch_names_a_tampered_asset_dir_file_in_its_remedy(repo: Path, release: tuple[ServicePin, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pin, _ = release
    _pin(repo, pin)
    asset_dir = tmp_path / "offline"
    asset_dir.mkdir()
    tampered = asset_dir / pin.assets[ServiceTarget.LINUX_X64].name
    tampered.write_bytes(b"not the pinned bytes")
    monkeypatch.setenv("SPEC_KITTY_SERVICE_ASSET_DIR", str(asset_dir))

    result = _invoke("fetch")

    assert result.exit_code == 1
    assert "SERVICE_BINARY_DIGEST_MISMATCH" in result.output
    assert str(tampered) in result.output
    assert "SPEC_KITTY_SERVICE_ASSET_DIR" in result.output


def test_fetch_refusal_for_a_pin_without_a_jar_never_mentions_one(repo: Path, tmp_path: Path) -> None:
    pin, _ = build_release(tmp_path / "releases", tag=TAG, assets={ServiceTarget.LINUX_ARM64: b"arm"})
    _pin(repo, pin)
    result = _invoke("fetch")
    assert result.exit_code == 1
    assert "jar" not in result.output.lower()
    assert "java" not in result.output.lower()


def test_vendor_prints_the_native_targets_the_release_lacks(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    result = _invoke(*_vendor_args(pin))
    assert result.exit_code == 0, result.output
    assert "linux-arm64, macos-arm64, windows-x64" in result.output


# -- F11: the read service is never fetched to a user machine implicitly ---------------------------


@pytest.fixture
def write_and_read_pins(repo: Path, tmp_path: Path) -> tuple[ServicePin, ServicePin]:
    write, _ = build_release(tmp_path / "releases", tag=TAG)
    read, _ = build_release(tmp_path / "releases", service="read-service", tag=TAG)
    _pin(repo, write)
    _pin(repo, read)
    return write, read


def _cached_services(tmp_path: Path) -> set[str]:
    root = tmp_path / "cache" / "spec-kitty" / "services"
    return {path.name for path in root.iterdir()} if root.is_dir() else set()


def test_fetch_all_fetches_launchable_services_only(repo: Path, write_and_read_pins: tuple[ServicePin, ServicePin], tmp_path: Path) -> None:
    result = _invoke("fetch", "--all", "--json")
    assert result.exit_code == 0, result.output
    assert [entry["service"] for entry in json.loads(result.stdout)["services"]] == ["write-service"]
    assert _cached_services(tmp_path) == {"write-service"}


def test_fetch_of_the_read_service_still_works_when_named(repo: Path, write_and_read_pins: tuple[ServicePin, ServicePin], tmp_path: Path) -> None:
    result = _invoke("fetch", "--service", "read-service", "--json")
    assert result.exit_code == 0, result.output
    assert [entry["service"] for entry in json.loads(result.stdout)["services"]] == ["read-service"]
    assert _cached_services(tmp_path) == {"read-service"}


def test_status_by_default_covers_the_launchable_service_only(repo: Path, write_and_read_pins: tuple[ServicePin, ServicePin], absent_instance: None) -> None:
    assert [entry["service"] for entry in json.loads(_invoke("status", "--json").stdout)["services"]] == ["write-service"]


# -- F12: status only verifies; it never evicts ----------------------------------------------------


def test_status_reports_a_corrupt_copy_and_leaves_it_in_place(repo: Path, release: tuple[ServicePin, Path], tmp_path: Path, absent_instance: None) -> None:
    pin, _ = release
    _pin(repo, pin)
    assert _invoke("fetch").exit_code == 0
    cached = tmp_path / "cache" / "spec-kitty" / "services" / "write-service" / TAG / pin.assets[ServiceTarget.LINUX_X64].name
    cached.write_bytes(b"tampered")

    assert _assets(json.loads(_invoke("status", "--json").stdout))["linux-x64"] == "corrupt"
    assert cached.read_bytes() == b"tampered", "status evicted the cached copy; it must only verify"


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation needs privileges on Windows")
def test_status_reports_a_symlinked_copy_as_corrupt_and_keeps_it(repo: Path, release: tuple[ServicePin, Path], tmp_path: Path, absent_instance: None) -> None:
    pin, release_dir = release
    _pin(repo, pin)
    asset = pin.assets[ServiceTarget.LINUX_X64]
    cached = tmp_path / "cache" / "spec-kitty" / "services" / "write-service" / TAG / asset.name
    cached.parent.mkdir(parents=True)
    cached.symlink_to(release_dir / asset.name)

    assert _assets(json.loads(_invoke("status", "--json").stdout))["linux-x64"] == "corrupt"
    assert cached.is_symlink()
