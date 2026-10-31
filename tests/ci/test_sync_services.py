"""``scripts/sync_services.py``, ``make sync-services`` and the sync-services action (#6590, FR-012).

The script fetches and verifies every pinned service asset for this host (the
native build, else the jar, plus every extras asset) into the shared cache;
``--offline`` uses the cache only and ``--check`` verifies without changing
anything. The composite action restores that cache keyed on the pin files and
runs the script. It is wired into no job until the first real pin lands
(research R-7, C-003); the ratchet below fails, saying "wire it now", as soon as
a ``pins/*.source.yaml`` exists while no workflow uses the action.

The script is loaded by file path (it is not a package module), the way
``tests/ci/test_lock_interop_peer.py`` loads its script.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from kernel.service_artifacts import cached_path
from kernel.service_pin import PINS_DIR, ServicePin, ServiceTarget, write_service_pin
from tests.kernel.service_release_fixture import build_release, pin_path

pytestmark = pytest.mark.fast

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO / "scripts" / "sync_services.py"
_ACTION = _REPO / ".github" / "actions" / "sync-services" / "action.yml"
_PACKS_ACTION = _REPO / ".github" / "actions" / "sync-packs" / "action.yml"
_WORKFLOWS = _REPO / ".github" / "workflows"
_ACTION_REF = "./.github/actions/sync-services"
_CACHE_STEP = "actions/cache@"


def _load_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    spec = importlib.util.spec_from_file_location("sync_services", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def sync() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as patch:
        yield _load_module(patch)


@pytest.fixture
def host_linux_x64(sync: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the host to linux-x64, so the tests do not depend on the machine running them."""
    monkeypatch.setattr(sync, "host_target", lambda: ServiceTarget.LINUX_X64)


@pytest.fixture(autouse=True)
def _no_asset_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPEC_KITTY_SERVICE_ASSET_DIR", raising=False)


def _pinned_repo(tmp_path: Path, **release: Any) -> tuple[Path, ServicePin]:
    """A repository root whose ``pins/`` holds the pin of a ``file://`` fixture release."""
    repo = tmp_path / "repo"
    (repo / PINS_DIR).mkdir(parents=True)
    pin, _ = build_release(tmp_path / "release", **release)
    write_service_pin(pin, pin_path(repo, pin.service))
    return repo, pin


def _extras() -> dict[str, bytes]:
    return {"contracts": b"contract bundle", "fixtures": b"conformance fixtures"}


# --------------------------------------------------------------------------- #
# T026: the script
# --------------------------------------------------------------------------- #


def test_no_pin_prints_no_service_pinned_and_exits_0(sync: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / PINS_DIR).mkdir()
    (tmp_path / PINS_DIR / "README.md").write_text("no pins yet\n", encoding="utf-8")

    assert sync.main([], repo_root=tmp_path, cache_root=tmp_path / "cache") == 0
    assert capsys.readouterr().out.strip() == sync.NO_SERVICE_PINNED


def test_no_pins_directory_at_all_exits_0(sync: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert sync.main(["--check"], repo_root=tmp_path, cache_root=tmp_path / "cache") == 0
    assert sync.NO_SERVICE_PINNED in capsys.readouterr().out


@pytest.mark.usefixtures("host_linux_x64")
def test_online_fetch_from_a_file_release_verifies_host_build_and_extras(sync: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, pin = _pinned_repo(tmp_path, extras=_extras())
    cache = tmp_path / "cache"

    assert sync.main(["--service", "all"], repo_root=repo, cache_root=cache) == 0

    out = capsys.readouterr().out
    fetched = [pin.assets[ServiceTarget.LINUX_X64], *pin.extras.values()]
    for asset in fetched:
        assert cached_path(pin, asset, cache).is_file()
        assert asset.name in out
    # The host has a native build, so the jar is not fetched.
    assert not cached_path(pin, pin.assets[ServiceTarget.JVM], cache).exists()


@pytest.mark.usefixtures("host_linux_x64")
def test_offline_with_a_warm_cache_succeeds_without_the_release(sync: ModuleType, tmp_path: Path) -> None:
    repo, pin = _pinned_repo(tmp_path, extras=_extras())
    cache = tmp_path / "cache"
    assert sync.main([], repo_root=repo, cache_root=cache) == 0

    for path in (tmp_path / "release").rglob("*"):
        if path.is_file():
            path.unlink()  # the release is gone: only the cache can answer

    assert sync.main(["--offline"], repo_root=repo, cache_root=cache) == 0


@pytest.mark.usefixtures("host_linux_x64")
def test_offline_with_a_cold_cache_refuses_missing(sync: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, _ = _pinned_repo(tmp_path)

    assert sync.main(["--offline"], repo_root=repo, cache_root=tmp_path / "cache") == 1
    assert "SERVICE_BINARY_MISSING" in capsys.readouterr().err


@pytest.mark.usefixtures("host_linux_x64")
def test_check_passes_then_fails_after_a_byte_flip_without_changing_the_cache(sync: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, pin = _pinned_repo(tmp_path, extras=_extras())
    cache = tmp_path / "cache"
    assert sync.main([], repo_root=repo, cache_root=cache) == 0
    assert sync.main(["--check"], repo_root=repo, cache_root=cache) == 0
    capsys.readouterr()

    native = cached_path(pin, pin.assets[ServiceTarget.LINUX_X64], cache)
    data = bytearray(native.read_bytes())
    data[0] ^= 0x01
    native.write_bytes(bytes(data))

    assert sync.main(["--check"], repo_root=repo, cache_root=cache) == 1
    err = capsys.readouterr().err
    assert f"SERVICE_BINARY_DIGEST_MISMATCH {native.name}" in err
    assert pin.assets[ServiceTarget.LINUX_X64].sha256 not in err
    # --check changes nothing: the bad copy is reported, not evicted.
    assert native.read_bytes() == bytes(data)


@pytest.mark.usefixtures("host_linux_x64")
def test_check_with_an_empty_cache_names_each_missing_asset(sync: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, pin = _pinned_repo(tmp_path, extras=_extras())
    cache = tmp_path / "cache"

    assert sync.main(["--check"], repo_root=repo, cache_root=cache) == 1

    err = capsys.readouterr().err
    for asset in (pin.assets[ServiceTarget.LINUX_X64], *pin.extras.values()):
        assert f"SERVICE_BINARY_MISSING {asset.name}" in err
    assert not cache.exists(), "--check must not create the cache"


@pytest.mark.usefixtures("host_linux_x64")
def test_a_corrupted_release_asset_refuses_digest_mismatch(sync: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, _ = _pinned_repo(tmp_path, corrupt={ServiceTarget.LINUX_X64.value})

    assert sync.main([], repo_root=repo, cache_root=tmp_path / "cache") == 1
    assert "SERVICE_BINARY_DIGEST_MISMATCH" in capsys.readouterr().err


def test_a_host_without_a_native_build_takes_the_jar(sync: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync, "host_target", lambda: ServiceTarget.MACOS_ARM64)
    repo, pin = _pinned_repo(tmp_path)
    cache = tmp_path / "cache"

    assert sync.main([], repo_root=repo, cache_root=cache) == 0
    assert cached_path(pin, pin.assets[ServiceTarget.JVM], cache).is_file()
    assert not cached_path(pin, pin.assets[ServiceTarget.LINUX_X64], cache).exists()


def test_no_native_build_and_no_jar_refuses_unsupported_platform(
    sync: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sync, "host_target", lambda: None)
    repo, _ = _pinned_repo(tmp_path, assets={ServiceTarget.LINUX_X64: b"native only"})

    assert sync.main([], repo_root=repo, cache_root=tmp_path / "cache") == 1
    assert "SERVICE_UNSUPPORTED_PLATFORM" in capsys.readouterr().err


def test_an_invalid_pin_refuses_pin_invalid(sync: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / PINS_DIR).mkdir()
    pin_path(tmp_path, "write-service").write_text("service: write-service\n", encoding="utf-8")

    assert sync.main([], repo_root=tmp_path, cache_root=tmp_path / "cache") == 1
    assert "SERVICE_PIN_INVALID write-service" in capsys.readouterr().err


def test_a_named_service_without_a_pin_refuses_pin_invalid(sync: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert sync.main(["--service", "read-service"], repo_root=tmp_path, cache_root=tmp_path / "cache") == 1
    assert "SERVICE_PIN_INVALID read-service" in capsys.readouterr().err


@pytest.mark.usefixtures("host_linux_x64")
def test_a_named_service_fetches_only_that_service(sync: ModuleType, tmp_path: Path) -> None:
    repo, pin = _pinned_repo(tmp_path)
    pin_path(repo, "read-service").write_text("not: a valid pin\n", encoding="utf-8")
    cache = tmp_path / "cache"

    assert sync.main(["--service", "write-service"], repo_root=repo, cache_root=cache) == 0
    assert cached_path(pin, pin.assets[ServiceTarget.LINUX_X64], cache).is_file()
    # --service all reaches the broken read-service pin and refuses.
    assert sync.main([], repo_root=repo, cache_root=cache) == 1


def test_pinned_services_lists_only_lockfiles(sync: ModuleType, tmp_path: Path) -> None:
    pins = tmp_path / PINS_DIR
    pins.mkdir()
    for name in ("write-service.source.yaml", "read-service.source.yaml", "README.md", "notes.yaml"):
        (pins / name).write_text("x\n", encoding="utf-8")

    assert sync.pinned_services(tmp_path) == ["read-service", "write-service"]


def test_the_script_uses_the_kernel_host_rule(sync: ModuleType) -> None:
    """One authority: the script carries no target table of its own (F5)."""
    from kernel import service_hosts

    assert sync.host_target is service_hosts.host_target
    assert sync.select_build is service_hosts.select_build
    assert not hasattr(sync, "HOST_TARGETS")


def test_the_script_imports_only_kernel_from_the_project() -> None:
    source = _SCRIPT_PATH.read_text(encoding="utf-8")
    project_imports = set(re.findall(r"^(?:from|import)\s+(specify_cli|charter|runtime|mission_runtime|glossary|kernel)\b", source, re.MULTILINE))
    assert project_imports == {"kernel"}


def test_the_script_runs_standalone_with_pythonpath_src(tmp_path: Path) -> None:
    """``PYTHONPATH=src python scripts/sync_services.py`` works without an editable install, as the action runs it."""
    env = {"PYTHONPATH": str(_REPO / "src"), "XDG_CACHE_HOME": str(tmp_path / "cache"), "PATH": ""}
    result = subprocess.run([sys.executable, str(_SCRIPT_PATH), "--help"], capture_output=True, text=True, env=env, check=False, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "--offline" in result.stdout


def test_makefile_has_a_sync_services_target_that_is_not_in_dev_setup() -> None:
    makefile = (_REPO / "Makefile").read_text(encoding="utf-8")
    target = re.search(r"^sync-services:.*##.*\n\t(?P<recipe>.+)$", makefile, re.MULTILINE)
    assert target is not None, "the sync-services target (with a ## help comment) is missing"
    assert "scripts/sync_services.py --service all" in target.group("recipe")
    dev_setup = re.search(r"^dev-setup:.*\n((?:\t.*\n)+)", makefile, re.MULTILINE)
    assert dev_setup is not None
    assert "sync-services" not in dev_setup.group(1), "wire sync-services into dev-setup only together with the first real pin"


# --------------------------------------------------------------------------- #
# T027: the composite action
# --------------------------------------------------------------------------- #


def _steps(path: Path) -> list[dict[str, Any]]:
    steps = yaml.safe_load(path.read_text(encoding="utf-8"))["runs"]["steps"]
    assert isinstance(steps, list)
    return steps


def _cache_step(path: Path) -> dict[str, Any]:
    (step,) = [step for step in _steps(path) if str(step.get("uses", "")).startswith(_CACHE_STEP)]
    return step


def test_action_restores_the_service_cache_keyed_on_the_pins() -> None:
    step = _cache_step(_ACTION)
    assert step["with"]["path"] == "~/.cache/spec-kitty/services"
    assert "hashFiles('pins/*.source.yaml')" in step["with"]["key"]


def test_action_pins_actions_cache_to_the_same_commit_as_sync_packs() -> None:
    ours = _cache_step(_ACTION)["uses"]
    assert re.fullmatch(r"actions/cache@[0-9a-f]{40}", ours), ours
    assert ours == _cache_step(_PACKS_ACTION)["uses"]


def test_action_runs_the_script_for_every_service_after_the_cache() -> None:
    steps = _steps(_ACTION)
    runs = [index for index, step in enumerate(steps) if "scripts/sync_services.py --service all" in str(step.get("run", ""))]
    cache = [index for index, step in enumerate(steps) if str(step.get("uses", "")).startswith(_CACHE_STEP)]
    assert runs and cache and cache[0] < runs[0]


def test_action_inputs_match_sync_packs() -> None:
    def inputs(path: Path) -> dict[str, Any]:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))["inputs"]
        assert isinstance(loaded, dict)
        return {name: spec.get("default") for name, spec in loaded.items()}

    assert inputs(_ACTION) == inputs(_PACKS_ACTION)


def _workflows_using_the_action(workflows_dir: Path) -> list[str]:
    users: list[str] = []
    for workflow in sorted(workflows_dir.glob("*.y*ml")):
        jobs = (yaml.safe_load(workflow.read_text(encoding="utf-8")) or {}).get("jobs") or {}
        for job_id, job in jobs.items():
            if any(str(step.get("uses", "")).startswith(_ACTION_REF) for step in (job or {}).get("steps") or []):
                users.append(f"{workflow.name}:{job_id}")
    return users


def wiring_violation(repo: Path) -> str | None:
    """The ratchet: once a pin exists, at least one workflow job must use the action."""
    pins = sorted((repo / PINS_DIR).glob("*.source.yaml"))
    if not pins or _workflows_using_the_action(repo / ".github" / "workflows"):
        return None
    return (
        f"{', '.join(p.name for p in pins)} exist(s) but no workflow job uses {_ACTION_REF}: wire it now "
        "(the cut-over PR adds it to every job that runs the service conformance suites, and sync-services to dev-setup)"
    )


def test_ratchet_once_a_pin_exists_a_workflow_must_use_the_action() -> None:
    violation = wiring_violation(_REPO)
    assert violation is None, violation


def _fake_repo(tmp_path: Path, *, pinned: bool, wired: bool) -> Path:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (tmp_path / PINS_DIR).mkdir()
    if pinned:
        (tmp_path / PINS_DIR / "write-service.source.yaml").write_text("service: write-service\n", encoding="utf-8")
    steps = [{"uses": "actions/checkout@v4"}, *([{"uses": _ACTION_REF}] if wired else []), {"run": "pytest"}]
    (workflows / "ci.yml").write_text(yaml.safe_dump({"on": "push", "jobs": {"test": {"steps": steps}}}), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    ("pinned", "wired", "violates"),
    [(False, False, False), (True, False, True), (True, True, False), (False, True, False)],
    ids=["no-pin-unwired", "pin-unwired", "pin-wired", "no-pin-wired"],
)
def test_ratchet_planted_cases(tmp_path: Path, pinned: bool, wired: bool, violates: bool) -> None:
    violation = wiring_violation(_fake_repo(tmp_path, pinned=pinned, wired=wired))
    assert (violation is not None) is violates
    if violates:
        assert violation is not None and "wire it now" in violation
