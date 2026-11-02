"""The warmup environment's events revision comes from the lock, never a stale constant.

The warmup composite used to advertise (and put in its cache key) a
``pinned-events-rev`` default that had drifted from the lock: it said ``10.4.6``
while ``uv.lock`` (and ``pyproject.toml``) required ``spec-kitty-events>=11.3.0,<12``.
``uv sync --frozen`` installs the *locked* version whatever the input says, so the
input was a second authority that lied — and a venv cache hit said nothing about
which revision the environment actually held.

``scripts/ci/warmup_events_rev.py`` is now the one resolver: ``pr`` mode reads the
version ``uv.lock`` locks (the single authority a frozen sync follows), ``full`` mode
resolves the newest published release (the upstream-drift signal). The script is
stdlib-only so it runs before uv or the project environment exist; the tests load it
by file path, the way ``tests/ci/test_sync_services.py`` loads its script.
"""

from __future__ import annotations

import importlib.util
import io
import re
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

pytestmark = pytest.mark.fast

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO / "scripts" / "ci" / "warmup_events_rev.py"
_LOCK_PATH = _REPO / "uv.lock"


def _load_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    spec = importlib.util.spec_from_file_location("warmup_events_rev", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def resolver() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as patch:
        yield _load_module(patch)


def _lock(directory: Path, *versions: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    packages = "".join(f'[[package]]\nname = "spec-kitty-events"\nversion = "{version}"\n\n' for version in versions)
    path = directory / "uv.lock"
    path.write_text(f"version = 1\nrevision = 3\n\n{packages}", encoding="utf-8")
    return path


def _no_pypi(_package: str) -> dict[str, Any]:
    raise AssertionError("pr mode must not consult PyPI")


def _locked_events_version() -> str:
    """Independent oracle: the version the real uv.lock records (no resolver code involved)."""
    lock = tomllib.loads(_LOCK_PATH.read_text(encoding="utf-8"))
    versions = [entry["version"] for entry in lock["package"] if entry.get("name") == "spec-kitty-events"]
    assert len(versions) == 1, versions
    return str(versions[0])


# --------------------------------------------------------------------------- #
# pr mode: uv.lock is the authority
# --------------------------------------------------------------------------- #


def test_pr_revision_is_the_locked_version(resolver: ModuleType) -> None:
    assert resolver.resolve("pr", lock_path=_LOCK_PATH, latest=_no_pypi) == _locked_events_version()


def test_pr_revision_follows_the_lock_not_a_constant(resolver: ModuleType, tmp_path: Path) -> None:
    """Lock invalidation: a different lock means a different (cache-key) revision."""
    older = resolver.resolve("pr", lock_path=_lock(tmp_path / "older", "11.3.0"), latest=_no_pypi)
    newer = resolver.resolve("pr", lock_path=_lock(tmp_path / "newer", "11.4.0"), latest=_no_pypi)

    assert (older, newer) == ("11.3.0", "11.4.0")


def test_the_script_carries_no_hardcoded_events_revision() -> None:
    source = _SCRIPT_PATH.read_text(encoding="utf-8")
    assert "10.4.6" not in source, "the stale 10.4.6 authority must not survive anywhere in the resolver"
    assert re.search(r"uv\.lock|lock_path", source), "pr mode must read the lock"


def test_pr_revision_refuses_a_lock_without_the_events_package(resolver: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "uv.lock"
    path.write_text('version = 1\n\n[[package]]\nname = "something-else"\nversion = "1.0.0"\n', encoding="utf-8")

    with pytest.raises(resolver.EventsRevError) as raised:
        resolver.resolve("pr", lock_path=path, latest=_no_pypi)

    assert raised.value.code == "WARMUP_EVENTS_UNLOCKED"
    assert "spec-kitty-events" in str(raised.value)


def test_pr_revision_refuses_an_ambiguous_lock(resolver: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(resolver.EventsRevError) as raised:
        resolver.resolve("pr", lock_path=_lock(tmp_path, "11.3.0", "11.4.0"), latest=_no_pypi)

    assert raised.value.code == "WARMUP_EVENTS_INVALID"
    assert "11.3.0" in str(raised.value) and "11.4.0" in str(raised.value)


@pytest.mark.parametrize("version", ["", "../../etc/passwd", "11.3.0 11.4.0", "latest"])
def test_pr_revision_refuses_a_value_that_is_not_a_version(resolver: ModuleType, tmp_path: Path, version: str) -> None:
    with pytest.raises(resolver.EventsRevError) as raised:
        resolver.resolve("pr", lock_path=_lock(tmp_path, version), latest=_no_pypi)

    assert raised.value.code == "WARMUP_EVENTS_INVALID"


def test_a_missing_lock_fails_closed_with_the_remedy(resolver: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(resolver.EventsRevError) as raised:
        resolver.resolve("pr", lock_path=tmp_path / "absent.lock", latest=_no_pypi)

    assert raised.value.code == "WARMUP_EVENTS_UNLOCKED"
    assert "absent.lock" in str(raised.value)


# --------------------------------------------------------------------------- #
# full mode: PyPI decides, the lock is ignored
# --------------------------------------------------------------------------- #


def test_full_mode_resolves_the_latest_published_release(resolver: ModuleType, tmp_path: Path) -> None:
    seen: list[str] = []

    def latest(package: str) -> dict[str, Any]:
        seen.append(package)
        return {"info": {"version": "12.0.0"}}

    assert resolver.resolve("full", lock_path=tmp_path / "absent.lock", latest=latest) == "12.0.0"
    assert seen == ["spec-kitty-events"], "full mode asks PyPI for the shared package, and never the lock"


def test_full_mode_refuses_a_payload_without_a_version(resolver: ModuleType) -> None:
    with pytest.raises(resolver.EventsRevError) as raised:
        resolver.resolve("full", latest=lambda _package: {"info": {}})

    assert raised.value.code == "WARMUP_EVENTS_LOOKUP_FAILED"


def test_full_mode_fetch_is_bounded_and_reads_the_pypi_response(resolver: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    def response(url: str, *, timeout: int) -> io.BytesIO:
        assert url == "https://pypi.org/pypi/spec-kitty-events/json"
        assert timeout == 30
        return io.BytesIO(b'{"info": {"version": "12.0.1"}}')

    monkeypatch.setattr(resolver.urllib.request, "urlopen", response)
    assert resolver.resolve("full") == "12.0.1"


@pytest.mark.parametrize("payload", [b"invalid JSON", b"[]", None])
def test_full_mode_transport_and_payload_failures_are_coded_refusals(resolver: ModuleType, monkeypatch: pytest.MonkeyPatch, payload: bytes | None) -> None:
    def response(_url: str, *, timeout: int) -> io.BytesIO:
        assert timeout == 30
        if payload is None:
            raise OSError("test transport failure")
        return io.BytesIO(payload)

    monkeypatch.setattr(resolver.urllib.request, "urlopen", response)
    with pytest.raises(resolver.EventsRevError, match="WARMUP_EVENTS_LOOKUP_FAILED"):
        resolver.resolve("full")


def test_malformed_toml_is_a_coded_refusal(resolver: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "uv.lock"
    path.write_text("invalid =", encoding="utf-8")
    with pytest.raises(resolver.EventsRevError, match="WARMUP_EVENTS_INVALID"):
        resolver.locked_version(path)


def test_an_unknown_mode_is_refused(resolver: ModuleType) -> None:
    with pytest.raises(resolver.EventsRevError) as raised:
        resolver.resolve("nightly", lock_path=_LOCK_PATH, latest=_no_pypi)

    assert raised.value.code == "WARMUP_MODE_INVALID"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def test_cli_prints_only_the_revision(resolver: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    assert resolver.main(["--mode", "pr", "--lock", str(_LOCK_PATH)]) == 0
    assert capsys.readouterr().out.strip() == _locked_events_version()


def test_cli_reports_a_stable_code_on_a_missing_lock(resolver: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert resolver.main(["--mode", "pr", "--lock", str(tmp_path / "absent.lock")]) == 1
    assert "WARMUP_EVENTS_UNLOCKED" in capsys.readouterr().err


def test_cli_rejects_an_unknown_mode(resolver: ModuleType) -> None:
    with pytest.raises(SystemExit) as raised:
        resolver.main(["--mode", "nightly"])

    assert raised.value.code == 2


def test_the_script_imports_only_the_standard_library() -> None:
    """It runs on the bare runner interpreter, before uv installs anything."""
    source = _SCRIPT_PATH.read_text(encoding="utf-8")
    project_imports = set(re.findall(r"^(?:from|import)\s+(specify_cli|charter|runtime|mission_runtime|glossary|doctrine|kernel)\b", source, re.MULTILINE))
    assert project_imports == set(), project_imports
