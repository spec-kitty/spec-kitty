"""Unit tests for ``specify_cli.bytecode_heal`` (#4124).

Builds a synthetic package whose import chain mirrors the real one
(``pkg/__init__`` -> ``pkg.runner`` -> ``pkg.base``), corrupts a ``.pyc`` the
way an interrupted install does (intact 16-byte header, garbage body), and
exercises the discriminator, purge, and heal-and-retry against it. No real
package caches are touched: ``package_root`` is monkeypatched to the
synthetic package for every corruption test.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from specify_cli import bytecode_heal
from tests._support.pyc_corruption import corrupt_non_code_body as _corrupt_non_code
from tests._support.pyc_corruption import corrupt_truncated_body as _corrupt_truncated

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_PKG = "skbh_fake_pkg"


@pytest.fixture()
def fake_pkg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A synthetic package mirroring specify_cli's upgrade import chain."""
    root = tmp_path / "site"
    pkg_dir = root / _PKG
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text(f"from {_PKG}.runner import R\n")
    (pkg_dir / "runner.py").write_text(f"from {_PKG}.base import B\nR = B\n")
    (pkg_dir / "base.py").write_text("B = 1\n")
    monkeypatch.syspath_prepend(str(root))
    monkeypatch.setattr(bytecode_heal, "package_root", lambda: pkg_dir)
    yield pkg_dir
    for name in list(sys.modules):
        if name == _PKG or name.startswith(f"{_PKG}."):
            del sys.modules[name]


def _base_pyc(pkg_dir: Path) -> Path:
    return Path(importlib.util.cache_from_source(str(pkg_dir / "base.py")))


def _purge_pkg_modules() -> None:
    for name in list(sys.modules):
        if name == _PKG or name.startswith(f"{_PKG}."):
            del sys.modules[name]


def _import_pkg() -> None:
    _purge_pkg_modules()
    importlib.import_module(_PKG)


def test_package_root_points_at_real_package() -> None:
    root = bytecode_heal.package_root()
    assert root is not None
    assert root.name == "specify_cli"
    assert (root / "__init__.py").is_file()


def test_truncated_pyc_is_healed_and_retried(fake_pkg: Path) -> None:
    _import_pkg()  # writes valid caches
    _purge_pkg_modules()
    pyc = _base_pyc(fake_pkg)
    _corrupt_truncated(pyc)
    corrupt_bytes = pyc.read_bytes()

    healed_with: list[int] = []

    def operation() -> str:
        _import_pkg()  # first call dies unmarshalling, retry recompiles
        return "done"

    result = bytecode_heal.invoke_with_bytecode_heal(operation, on_healed=healed_with.append)

    assert result == "done"
    assert healed_with and healed_with[0] >= 1
    # The stale cache was purged and the retry recompiled from source.
    assert pyc.exists()
    assert pyc.read_bytes() != corrupt_bytes


def test_non_code_pyc_import_error_is_healed(fake_pkg: Path) -> None:
    _import_pkg()  # writes valid caches
    _purge_pkg_modules()
    pyc = _base_pyc(fake_pkg)
    _corrupt_non_code(pyc)
    corrupt_bytes = pyc.read_bytes()

    def operation() -> str:
        _import_pkg()
        return "done"

    result = bytecode_heal.invoke_with_bytecode_heal(operation)

    assert result == "done"
    assert pyc.exists()
    assert pyc.read_bytes() != corrupt_bytes


def test_ordinary_runtime_bug_is_not_healed(fake_pkg: Path) -> None:
    _import_pkg()  # caches exist and are valid

    def operation() -> None:
        raise RuntimeError("genuine bug in package code")

    with pytest.raises(RuntimeError, match="genuine bug"):
        bytecode_heal.invoke_with_bytecode_heal(operation)
    assert _base_pyc(fake_pkg).exists()  # nothing was purged


def test_package_frame_without_import_machinery_is_not_healed(fake_pkg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The MigrationDiscoveryError shape: raised from the package's own frame,
    # not from the import machinery — must propagate untouched.
    (fake_pkg / "boom.py").write_text("def detonate():\n    raise ValueError('bad marshal data (unknown type code)')\n")
    _import_pkg()
    boom = importlib.import_module(f"{_PKG}.boom")

    purged: list[int] = []
    monkeypatch.setattr(bytecode_heal, "purge_package_bytecode", lambda: purged.append(1) or 0)

    with pytest.raises(ValueError, match="bad marshal data"):
        bytecode_heal.invoke_with_bytecode_heal(boom.detonate)
    assert purged == []


def test_laundered_discovery_failure_is_healed(fake_pkg: Path) -> None:
    """The laundered wrapper: a fresh exception raised ``from`` a corrupt-``.pyc`` import failure.

    ``upgrade.migrations.auto_discover_migrations`` collects per-module import
    failures and raises one ``MigrationDiscoveryError`` chained to the first
    original; the corrupt-cache signature lives only on that cause (#4124).
    Non-vacuity: with the cause-chain walk removed, the wrapper matches no
    direct shape and this test sees the raw wrapper error instead of "done".
    """
    _import_pkg()  # writes valid caches
    _purge_pkg_modules()
    pyc = _base_pyc(fake_pkg)
    _corrupt_truncated(pyc)
    corrupt_bytes = pyc.read_bytes()

    def operation() -> str:
        try:
            _import_pkg()  # first call dies unmarshalling, retry recompiles
        except Exception as exc:  # launder exactly like auto_discover_migrations
            raise RuntimeError(f"Failed to import migration module(s): base: {exc}") from exc
        return "done"

    result = bytecode_heal.invoke_with_bytecode_heal(operation)

    assert result == "done"
    assert pyc.exists()
    assert pyc.read_bytes() != corrupt_bytes


def test_laundered_genuine_import_bug_is_not_healed(fake_pkg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A wrapped genuine import-time bug (``SyntaxError`` in a migration module) stays unhealed.

    A broken migration module fails inside an import too, so its failure
    carries frozen ``importlib`` and package frames — the chained check must
    require the corrupt-cache *signature*, not just any import-time failure,
    or it would purge every cache and fail again (#4124).
    """
    (fake_pkg / "broken.py").write_text("def oops(:\n")

    def operation() -> None:
        try:
            importlib.import_module(f"{_PKG}.broken")
        except Exception as exc:  # launder exactly like auto_discover_migrations
            raise RuntimeError(f"Failed to import migration module(s): broken: {exc}") from exc

    purged: list[int] = []
    monkeypatch.setattr(bytecode_heal, "purge_package_bytecode", lambda: purged.append(1) or 0)

    with pytest.raises(RuntimeError, match="Failed to import migration module"):
        bytecode_heal.invoke_with_bytecode_heal(operation)
    assert purged == []  # no wasteful purge: the retry would fail identically


def test_no_purgeable_cache_propagates_original(fake_pkg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bytecode_heal, "purge_package_bytecode", lambda: 0)

    calls: list[int] = []

    def operation() -> None:
        calls.append(1)
        raise ImportError(f"Non-code object in '{fake_pkg / '__pycache__' / 'base.cpython-311.pyc'}'")

    with pytest.raises(ImportError, match="Non-code object"):
        bytecode_heal.invoke_with_bytecode_heal(operation)
    assert calls == [1]  # no retry — nothing changed, retry would be futile


def test_purge_package_bytecode_removes_only_caches(fake_pkg: Path) -> None:
    _import_pkg()
    pyc = _base_pyc(fake_pkg)
    assert pyc.exists()

    removed = bytecode_heal.purge_package_bytecode()

    assert removed >= 1
    assert not pyc.exists()
    assert (fake_pkg / "base.py").exists()
    assert (fake_pkg / "runner.py").exists()


def test_corrupt_code_attribute_signature_matches() -> None:
    # The exact field signature from the Windows training machine (#4124).
    assert bytecode_heal.failure_during_package_import(AttributeError("'bytes' object has no attribute 'co_filename'"))
    # An unrelated AttributeError is not cache corruption.
    assert not bytecode_heal.failure_during_package_import(AttributeError("'Runner' object has no attribute 'migrate'"))


def test_dotted_name_import_error_is_not_healed() -> None:
    # A genuine missing-name ImportError carries no package file path.
    assert not bytecode_heal.failure_during_package_import(ImportError("cannot import name 'Missing' from 'specify_cli.upgrade.runner'"))
