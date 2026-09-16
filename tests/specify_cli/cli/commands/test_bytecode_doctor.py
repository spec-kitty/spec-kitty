"""Tests for ``spec-kitty doctor bytecode`` and the doctor.py auto-discovery
seam (#4130, the detection half of #4124's bytecode self-heal).

Mirrors ``test_bytecode_heal.py``'s fixture (a synthetic package whose caches
are built by a real import, then corrupted the way an interrupted install
does: intact 16-byte header, garbage body) and
``test_provenance_doctor.py``'s auto-discovery regression guards.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import marshal
import os
import py_compile
import struct
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

import specify_cli.cli.commands.doctor as doctor_module
from specify_cli.cli.commands import _bytecode_doctor
from tests._support.eacces import mode_bits_enforced

pytestmark = [pytest.mark.fast]

runner = CliRunner()

_PKG = "skbcd_fake_pkg"


@pytest.fixture()
def fake_pkg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A synthetic package with a real, valid ``.pyc`` produced by importing it."""
    root = tmp_path / "site"
    pkg_dir = root / _PKG
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("VALUE = 1\n")
    monkeypatch.syspath_prepend(str(root))
    _purge_pkg_modules()
    importlib.import_module(_PKG)
    yield pkg_dir
    _purge_pkg_modules()


def _purge_pkg_modules() -> None:
    for name in list(sys.modules):
        if name == _PKG or name.startswith(f"{_PKG}."):
            del sys.modules[name]


def _init_pyc(pkg_dir: Path) -> Path:
    return Path(importlib.util.cache_from_source(str(pkg_dir / "__init__.py")))


def _corrupt_truncated_body(pyc: Path) -> None:
    """Intact 16-byte header, garbage body -- the #4124 field signature."""
    data = pyc.read_bytes()
    pyc.write_bytes(data[:16] + b"\x00" * 8)


def _corrupt_non_code_body(pyc: Path) -> None:
    """Header intact; body unmarshals to a non-code object."""
    data = pyc.read_bytes()
    pyc.write_bytes(data[:16] + marshal.dumps(b"not-a-code-object"))


def _corrupt_magic(pyc: Path) -> None:
    """Bad magic number -- Python recompiles this on its own; never a finding."""
    data = pyc.read_bytes()
    pyc.write_bytes(b"\xff\xff\xff\xff" + data[4:])


def _write_hash_based_pyc(source: Path, pyc: Path) -> None:
    """Overwrite *pyc* with a real hash-based cache (``flags & 0x1``) for *source*."""
    py_compile.compile(str(source), cfile=str(pyc), invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)


# ---------------------------------------------------------------------------
# Auto-discovery seam regression guard
# ---------------------------------------------------------------------------


def test_bytecode_is_registered_on_doctor_app_without_hand_wiring() -> None:
    names = {cmd.name for cmd in doctor_module.app.registered_commands}
    assert "bytecode" in names


def test_doctor_py_source_never_hand_imports_the_bytecode_sibling() -> None:
    """Regression guard mirroring ``test_provenance_doctor``'s: no hand-wiring drift."""
    import ast

    tree = ast.parse(Path(doctor_module.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "_bytecode_doctor":
            pytest.fail("doctor.py must not hand-import _bytecode_doctor (discovery seam regression)")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "command":
            for keyword in node.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    assert keyword.value.value != "bytecode", "doctor.py must not hand-write an @app.command(name='bytecode') shell (discovery seam regression)"


def test_register_is_idempotent_safe_to_call_directly() -> None:
    scratch_app = typer.Typer()
    _bytecode_doctor.register(scratch_app)

    names = [cmd.name for cmd in scratch_app.registered_commands]
    assert names == ["bytecode"]


# ---------------------------------------------------------------------------
# scan_bytecode_cache
# ---------------------------------------------------------------------------


class TestScanBytecodeCache:
    def test_valid_cache_yields_no_findings(self, fake_pkg: Path) -> None:
        result = _bytecode_doctor._scan_bytecode_cache(fake_pkg)
        assert result.findings == []
        assert result.unreadable_count == 0

    def test_truncated_body_is_a_finding(self, fake_pkg: Path) -> None:
        _corrupt_truncated_body(_init_pyc(fake_pkg))

        result = _bytecode_doctor._scan_bytecode_cache(fake_pkg)
        findings = result.findings

        assert len(findings) == 1
        assert findings[0].pyc_path.endswith(".pyc")
        assert "EOFError" in findings[0].reason or "ValueError" in findings[0].reason

    def test_non_code_body_is_a_finding(self, fake_pkg: Path) -> None:
        _corrupt_non_code_body(_init_pyc(fake_pkg))

        result = _bytecode_doctor._scan_bytecode_cache(fake_pkg)
        findings = result.findings

        assert len(findings) == 1
        assert "non-code object" in findings[0].reason

    def test_bad_magic_is_not_a_finding(self, fake_pkg: Path) -> None:
        """Python's own loader already recompiles a bad-magic cache -- never a finding."""
        _corrupt_magic(_init_pyc(fake_pkg))

        result = _bytecode_doctor._scan_bytecode_cache(fake_pkg)

        assert result.findings == []

    def test_missing_root_yields_no_findings(self, tmp_path: Path) -> None:
        result = _bytecode_doctor._scan_bytecode_cache(tmp_path / "does-not-exist")
        assert result.findings == []
        assert result.unreadable_count == 0

    def test_unreadable_pyc_is_skipped_not_flagged_but_counted(self, fake_pkg: Path) -> None:
        """An unreadable cache is never a finding -- its body was never inspected --

        but must not silently make an audit that skipped part of the cache report
        "clean" as if it had checked everything (#4130 fold: fail-closed honesty).
        """
        pyc = _init_pyc(fake_pkg)
        os.chmod(pyc, 0o000)
        try:
            if not mode_bits_enforced(pyc):
                pytest.skip(
                    "SKIPPED HONESTLY, not passed: this process can read a 0o000 "
                    "file (running as root, or a filesystem that ignores mode "
                    "bits), so the unreadable branch cannot be constructed here."
                )
            result = _bytecode_doctor._scan_bytecode_cache(fake_pkg)
            assert result.findings == []
            assert result.unreadable_count == 1
        finally:
            os.chmod(pyc, 0o644)


# ---------------------------------------------------------------------------
# Hash-based cache (flags & 0x1) -- the branch left to the body check
# ---------------------------------------------------------------------------


class TestHashBasedCache:
    def test_valid_hash_based_cache_yields_no_findings(self, fake_pkg: Path) -> None:
        source = fake_pkg / "__init__.py"
        pyc = _init_pyc(fake_pkg)
        _write_hash_based_pyc(source, pyc)
        flags = struct.unpack("<I", pyc.read_bytes()[4:8])[0]
        assert flags & 0x1  # sanity: this really is a hash-based cache

        result = _bytecode_doctor._scan_bytecode_cache(fake_pkg)

        assert result.findings == []

    def test_corrupt_hash_based_cache_body_is_a_finding(self, fake_pkg: Path) -> None:
        source = fake_pkg / "__init__.py"
        pyc = _init_pyc(fake_pkg)
        _write_hash_based_pyc(source, pyc)
        flags = struct.unpack("<I", pyc.read_bytes()[4:8])[0]
        assert flags & 0x1  # sanity: this really is a hash-based cache
        data = pyc.read_bytes()
        pyc.write_bytes(data[:16] + b"\x00" * 8)

        result = _bytecode_doctor._scan_bytecode_cache(fake_pkg)

        assert len(result.findings) == 1
        assert result.findings[0].pyc_path.endswith(".pyc")


# ---------------------------------------------------------------------------
# Changed-source false-positive guard -- the docstring's core FP promise
# ---------------------------------------------------------------------------


class TestChangedSourceGuard:
    def test_changed_source_is_not_flagged_python_would_recompile(self, fake_pkg: Path) -> None:
        """A source edited after the cache was written must never be flagged.

        Python's own header check would already reject this cache on mtime/size
        mismatch and recompile from source -- it never bites, so this check must
        not report a finding for it either.
        """
        source = fake_pkg / "__init__.py"
        pyc = _init_pyc(fake_pkg)
        assert pyc.exists()

        source.write_text("VALUE = 1\nEXTRA = 2\n")  # different size than when cached
        far_future = 4102444800.0  # 2100-01-01, far enough that no header could match it
        os.utime(source, (far_future, far_future))

        result = _bytecode_doctor._scan_bytecode_cache(fake_pkg)

        assert result.findings == []


# ---------------------------------------------------------------------------
# Loose .pyc outside a __pycache__ layout -- source_from_cache ValueError skip
# ---------------------------------------------------------------------------


class TestLoosePyc:
    def test_loose_pyc_outside_pycache_layout_is_skipped_without_error(self, tmp_path: Path) -> None:
        loose_dir = tmp_path / "loose"
        loose_dir.mkdir()
        (loose_dir / "module.pyc").write_bytes(b"\x00" * 20)

        result = _bytecode_doctor._scan_bytecode_cache(loose_dir)

        assert result.findings == []
        assert result.unreadable_count == 0


# ---------------------------------------------------------------------------
# CLI surface (human + --json)
# ---------------------------------------------------------------------------


class TestDoctorBytecodeCli:
    def test_human_output_no_findings(self, fake_pkg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_bytecode_doctor, "package_root", lambda: fake_pkg)

        result = runner.invoke(doctor_module.app, ["bytecode"])

        assert result.exit_code == 0, result.output
        assert "no corrupt" in result.output.lower()

    def test_human_output_with_finding_includes_fix_hint(self, fake_pkg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _corrupt_truncated_body(_init_pyc(fake_pkg))
        monkeypatch.setattr(_bytecode_doctor, "package_root", lambda: fake_pkg)

        result = runner.invoke(doctor_module.app, ["bytecode"])

        assert result.exit_code == 1
        assert "__init__.cpython" in result.output or "__init__" in result.output
        assert "recompiles from source" in result.output

    def test_json_output_shape(self, fake_pkg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _corrupt_truncated_body(_init_pyc(fake_pkg))
        monkeypatch.setattr(_bytecode_doctor, "package_root", lambda: fake_pkg)

        result = runner.invoke(doctor_module.app, ["bytecode", "--json"])

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["finding_count"] == 1
        assert "heal_hint" in payload
        assert payload["findings"][0]["path"].endswith(".pyc")

    def test_unresolvable_root_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Root resolution failure is an operational error (exit 2), distinct from

        exit 1 ("finding present") -- the audit itself could not run at all.
        """
        monkeypatch.setattr(_bytecode_doctor, "package_root", lambda: None)

        result = runner.invoke(doctor_module.app, ["bytecode"])

        assert result.exit_code == 2
        assert "could not resolve" in result.output.lower()

    def test_unresolvable_root_json_output_is_parseable_and_exits_2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``--json`` must stay valid JSON even on the operational-error path."""
        monkeypatch.setattr(_bytecode_doctor, "package_root", lambda: None)

        result = runner.invoke(doctor_module.app, ["bytecode", "--json"])

        assert result.exit_code == 2
        payload = json.loads(result.output)
        assert payload["root"] is None
        assert payload["findings"] == []
        assert payload["finding_count"] == 0
        assert "error" in payload

    def test_json_output_surfaces_unreadable_count(self, fake_pkg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pyc = _init_pyc(fake_pkg)
        os.chmod(pyc, 0o000)
        try:
            if not mode_bits_enforced(pyc):
                pytest.skip(
                    "SKIPPED HONESTLY, not passed: this process can read a 0o000 "
                    "file (running as root, or a filesystem that ignores mode "
                    "bits), so the unreadable branch cannot be constructed here."
                )
            monkeypatch.setattr(_bytecode_doctor, "package_root", lambda: fake_pkg)

            result = runner.invoke(doctor_module.app, ["bytecode", "--json"])

            assert result.exit_code == 0  # unreadable is not itself a finding
            payload = json.loads(result.output)
            assert payload["unreadable_count"] == 1
        finally:
            os.chmod(pyc, 0o644)

    def test_human_output_surfaces_unreadable_count(self, fake_pkg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pyc = _init_pyc(fake_pkg)
        os.chmod(pyc, 0o000)
        try:
            if not mode_bits_enforced(pyc):
                pytest.skip(
                    "SKIPPED HONESTLY, not passed: this process can read a 0o000 "
                    "file (running as root, or a filesystem that ignores mode "
                    "bits), so the unreadable branch cannot be constructed here."
                )
            monkeypatch.setattr(_bytecode_doctor, "package_root", lambda: fake_pkg)

            result = runner.invoke(doctor_module.app, ["bytecode"])

            assert result.exit_code == 0
            assert "1" in result.output
            assert "unreadable" in result.output.lower()
        finally:
            os.chmod(pyc, 0o644)
