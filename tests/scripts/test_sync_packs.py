"""``scripts/sync_packs.py`` entry point: exit codes and stable error codes (WP03 / T011)."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from charter.offering.packs.pack_pin import write_pack_pin
from tests.charter_offering.conftest_pack_remote import PackRemote, make_pack_remote

pytestmark = [pytest.mark.git_repo]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "sync_packs.py"
_PLACEHOLDER_SHA = "0" * 40


def _load(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    spec = importlib.util.spec_from_file_location("sync_packs_under_test", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def sync_packs() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as monkeypatch:
        yield _load(monkeypatch)


@pytest.fixture
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cache_home = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_home))
    return cache_home


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, PackRemote]:
    """A fake repo root whose ``packs/built-in.source.yaml`` pins a local bare remote."""
    (tmp_path / "r").mkdir()
    remote = make_pack_remote(tmp_path / "r")
    root = tmp_path / "repo"
    (root / "packs").mkdir(parents=True)
    write_pack_pin(remote.pin(), root / "packs" / "built-in.source.yaml")
    return root, remote


def _run(module: ModuleType, root: Path, *args: str) -> int:
    code: int = module.main([*args], repo_root=root)
    return code


def test_sync_places_tree_then_check_is_ok(sync_packs: ModuleType, repo: tuple[Path, PackRemote], cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, _ = repo
    assert _run(sync_packs, root, "--pack", "built-in") == 0
    assert (root / "packs" / "built-in" / "pack.yaml").is_file()
    assert "built-in" in capsys.readouterr().out
    assert _run(sync_packs, root, "--pack", "built-in", "--check") == 0


def test_check_on_missing_tree_reports_stale(sync_packs: ModuleType, repo: tuple[Path, PackRemote], cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, _ = repo
    assert _run(sync_packs, root, "--pack", "built-in", "--check") == 1
    assert "PACK_TREE_STALE" in capsys.readouterr().err


def test_check_on_altered_tree_reports_stale(sync_packs: ModuleType, repo: tuple[Path, PackRemote], cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, _ = repo
    assert _run(sync_packs, root, "--pack", "built-in") == 0
    (root / "packs" / "built-in" / "directives" / "001-x.directive.yaml").write_text("tampered\n", encoding="utf-8")
    assert _run(sync_packs, root, "--pack", "built-in", "--check") == 1
    assert "PACK_TREE_STALE" in capsys.readouterr().err


def test_digest_mismatch_exits_one_with_code(sync_packs: ModuleType, repo: tuple[Path, PackRemote], cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, remote = repo
    write_pack_pin(remote.pin(digest="f" * 64), root / "packs" / "built-in.source.yaml")
    assert _run(sync_packs, root, "--pack", "built-in") == 1
    assert "PACK_DIGEST_MISMATCH" in capsys.readouterr().err


def test_unresolvable_commit_exits_one_with_code(sync_packs: ModuleType, repo: tuple[Path, PackRemote], cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, remote = repo
    write_pack_pin(remote.pin(sha="1" * 40), root / "packs" / "built-in.source.yaml")
    assert _run(sync_packs, root, "--pack", "built-in") == 1
    assert "PACK_COMMIT_UNRESOLVABLE" in capsys.readouterr().err


def test_offline_without_cache_names_make_sync_packs(
    sync_packs: ModuleType, repo: tuple[Path, PackRemote], cache: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _ = repo
    assert _run(sync_packs, root, "--pack", "built-in", "--offline") == 1
    err = capsys.readouterr().err
    assert "PACK_SYNC_UNAVAILABLE" in err
    assert "make sync-packs" in err


def test_offline_uses_warm_cache(sync_packs: ModuleType, repo: tuple[Path, PackRemote], cache: Path) -> None:
    root, _ = repo
    assert _run(sync_packs, root, "--pack", "built-in") == 0
    assert _run(sync_packs, root, "--pack", "built-in", "--offline") == 0


def test_placeholder_internal_pin_is_refused_clearly_and_built_in_still_syncs(
    sync_packs: ModuleType, repo: tuple[Path, PackRemote], cache: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, remote = repo
    internal = remote.pin(sha=_PLACEHOLDER_SHA, digest="0" * 64)
    write_pack_pin(internal, root / "packs" / "internal.source.yaml")
    assert _run(sync_packs, root, "--pack", "all") == 1
    err = capsys.readouterr().err
    assert "PACK_PIN_INVALID" in err
    assert "internal" in err
    assert (root / "packs" / "built-in" / "pack.yaml").is_file()
    assert not (root / "packs" / "internal").exists()


def test_built_in_alone_ignores_placeholder_internal_pin(sync_packs: ModuleType, repo: tuple[Path, PackRemote], cache: Path) -> None:
    root, remote = repo
    write_pack_pin(remote.pin(sha=_PLACEHOLDER_SHA, digest="0" * 64), root / "packs" / "internal.source.yaml")
    assert _run(sync_packs, root, "--pack", "built-in") == 0


def test_missing_pin_file_is_a_pin_error(sync_packs: ModuleType, tmp_path: Path, cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "packs").mkdir()
    assert _run(sync_packs, tmp_path, "--pack", "built-in") == 1
    assert "PACK_PIN_INVALID" in capsys.readouterr().err


def test_check_with_placeholder_pin_is_refused_not_reported_stale(
    sync_packs: ModuleType, repo: tuple[Path, PackRemote], cache: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, remote = repo
    write_pack_pin(remote.pin(sha=_PLACEHOLDER_SHA, digest="0" * 64), root / "packs" / "internal.source.yaml")
    assert _run(sync_packs, root, "--pack", "internal", "--check") == 1
    assert "PACK_PIN_INVALID" in capsys.readouterr().err
